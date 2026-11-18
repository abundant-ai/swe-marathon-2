"""Run example cases against one compiler executable and compare what it prints.

Each case is written into the same fixed directory, so that paths in an output are the same
for every run, and each run gets new empty directories as its HOME and TMPDIR. Every run gets
the same resource limits: an 8 MB stack, which is where `goose run` runs a program, and bounds
on processes, file size and data.

usage: python3 <this file> check <program> <cases.json> <outputs.json> [-v]
       python3 <this file> record <program> <cases.json> <outputs.json> [--keep <cases-out.json>] [--report <timing.json>]

`record` first settles each case (`settle`): where its "record" entry asks, files are replaced by
the program's own `format -` output, and of the case's variants the first that runs the way its
rule wants is chosen. It then runs the case twice and keeps it if both runs finish in at most
KEEP_SEC, print the same and end normally (`crashed`). Last it leaves out, by rule and by id,
cases whose answers take no compiler to give (`select`). `--keep` writes the cases kept,
without their "record" entries, and `--report` how long each run took and why cases were left
out. Standard output is compared byte for byte; the outputs file holds it as text, invalid
UTF-8 as surrogate escapes.
"""

from __future__ import annotations

import json
import os
import resource
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

WORKSPACE = Path("/tmp/goose-case")
HOME = Path("/tmp/goose-home")   # HOME and TMPDIR of a run, new and empty for each
TEMP = Path("/tmp/goose-tmp")
CASE_SEC = 2
KEEP_SEC = 0.5  # a recorded case finished in at most this, both times: a margin for slower machines
OUTPUT_LIMIT = 1_000_000  # bytes of standard output read at most; more fails the run
LIMITS = {
    resource.RLIMIT_STACK: 8 << 20,   # `goose run` runs the program on the main thread's stack
    resource.RLIMIT_NPROC: 512,       # processes and threads of the user running the case
    resource.RLIMIT_FSIZE: 256 << 20,
    # Writable private mappings: the original reserves 2 GB of address space per data stack
    # (MAP_NORESERVE, counted here) and takes smaller stacks where refused, so the bound is high.
    resource.RLIMIT_DATA: 256 << 30,
    resource.RLIMIT_CORE: 0,
}
ENCODING = ("utf-8", "surrogateescape")
STDERR_LIMIT = 1 << 16  # bytes of standard error kept from a recording run
# A run of the original that ends in one of these, or by a signal, is no answer anyone can be asked
# to copy: the compiler's own internal error, its JIT failing, a sanitizer or C++ runtime abort.
CRASH_MARKERS = (b"internal error", b"libtcc:", b"Sanitizer", b"terminate called", b"core dumped")
PAIR_SHARE = 0.012       # cases kept with any one (stdout, exit code), command-line cases aside, at most
CHECK_EMPTY_SHARE = 0.05  # check cases kept that answer [], at most
FLOOR_SHARE = 0.045      # cases answered without a compiler (free_cases), at most


def limit() -> None:
    """In a child about to run a case: the resource limits, the same for every run, and the first
    claim on the out-of-memory killer. The process count only bounds runs that root starts: in a
    user's own shell the user's other processes count too."""
    for which, value in LIMITS.items():
        if which == resource.RLIMIT_NPROC and os.geteuid() != 0:
            continue
        try:
            resource.setrlimit(which, (value, value))
        except (ValueError, OSError):  # a hard limit below the value, or a platform maximum (macOS's data size)
            _, hard = resource.getrlimit(which)
            try:
                resource.setrlimit(which, (hard if hard != resource.RLIM_INFINITY and 0 <= hard < value else value, hard))
            except (ValueError, OSError):
                pass
    try:
        Path("/proc/self/oom_score_adj").write_text("1000")
    except OSError:
        pass


def clear_workspace() -> None:
    """Remove whatever is at the workspace, HOME and TMPDIR paths without following a symbolic
    link: a directory with its contents, anything else by itself."""
    for path in (WORKSPACE, HOME, TEMP):
        try:
            mode = os.lstat(path).st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(mode):
            shutil.rmtree(path)
        else:
            os.unlink(path)


def prepare(case: dict, owner: tuple[int, int] | None) -> None:
    """A new workspace holding the case's files and a new empty HOME and TMPDIR, all owned by
    `owner` (user and group ids) where given."""
    clear_workspace()
    for path in (WORKSPACE, HOME, TEMP):
        path.mkdir(parents=True)
    for name, text in case["files"].items():
        target = WORKSPACE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if owner:
        for top in (WORKSPACE, HOME, TEMP):
            for root, directories, files in os.walk(top):
                for name in directories + files:
                    os.lchown(os.path.join(root, name), *owner)
            os.lchown(top, *owner)


def collect(proc: subprocess.Popen, data: bytes, deadline: float) -> tuple[bytes, str | None]:
    """Feed `data` to the program's standard input and read its standard output until it closes
    it. Returns what was read and None, or what stopped the reading: "timeout" at the deadline,
    "output limit" past OUTPUT_LIMIT bytes."""
    chunks, size = [], 0
    pending = memoryview(data)
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdout, selectors.EVENT_READ)
        if pending:
            os.set_blocking(proc.stdin.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE)
        else:
            proc.stdin.close()
        while selector.get_map():
            left = deadline - time.monotonic()
            if left <= 0:
                return b"", "timeout"
            for key, _ in selector.select(left):
                if key.fileobj is proc.stdin:
                    try:
                        pending = pending[os.write(proc.stdin.fileno(), pending[:65536]):]
                    except BlockingIOError:
                        continue
                    except OSError:  # the program closed its input
                        pending = pending[:0]
                    if not pending:
                        selector.unregister(proc.stdin)
                        proc.stdin.close()
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    selector.unregister(proc.stdout)
                    continue
                size += len(chunk)
                if size > OUTPUT_LIMIT:
                    return b"", "output limit"
                chunks.append(chunk)
    return b"".join(chunks), None


def stop(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()


def run_case(program: list[str], case: dict, prefix: list[str] | None = None, owner: tuple[int, int] | None = None,
             keep_stderr: bool = False) -> dict:
    """Run one case: its exit code, its standard output as bytes and how long it took, and with
    `keep_stderr` the first STDERR_LIMIT bytes of its standard error. A case that cannot be set up
    or started, runs past CASE_SEC or prints more than OUTPUT_LIMIT bytes has no exit code and an
    "error" instead."""
    try:
        prepare(case, owner)
    except OSError as exc:
        return {"exit": None, "stdout": None, "error": f"workspace: {type(exc).__name__}", "seconds": 0.0}
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(HOME), "TMPDIR": str(TEMP), "LC_ALL": "C.UTF-8",
           "LANG": "C.UTF-8", "NO_COLOR": "1", "TERM": "dumb", "GOOSE_PROGRESS": "plain"}
    errors = tempfile.TemporaryFile() if keep_stderr else None
    started = time.monotonic()
    try:
        proc = subprocess.Popen((prefix or []) + program + case["argv"], cwd=WORKSPACE, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=errors or subprocess.DEVNULL, start_new_session=True,
                                preexec_fn=limit)
    except (OSError, subprocess.SubprocessError):
        if errors:
            errors.close()
        return {"exit": None, "stdout": None, "error": "could not start", "seconds": 0.0}
    deadline = started + CASE_SEC
    try:
        out, problem = collect(proc, (case["stdin"] or "").encode("utf-8"), deadline)
        if problem is None:
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                problem = "timeout"
    finally:
        if proc.returncode is None:
            stop(proc)
        for stream in (proc.stdin, proc.stdout):
            if not stream.closed:
                stream.close()
    seconds = round(time.monotonic() - started, 4)
    stderr = b""
    if errors:
        errors.seek(0)
        stderr = errors.read(STDERR_LIMIT)
        errors.close()
    if problem:
        return {"exit": None, "stdout": None, "error": problem, "seconds": seconds, "stderr": stderr}
    return {"exit": proc.returncode, "stdout": out, "seconds": seconds, "stderr": stderr}


def matches(got: dict, want: dict) -> bool:
    """A run printed the recorded answer: the same exit code and the same bytes on standard output."""
    return got["exit"] is not None and got["exit"] == want["exit"] and got["stdout"] == want["stdout"].encode(*ENCODING)


def crashed(got: dict) -> bool:
    """A finished run of the original that ended by a signal (an exit code below 0 or from 128) or
    with one of CRASH_MARKERS on its standard error. A program's own abort, which the language
    defines, exits 1 and is an answer like any other."""
    return got["exit"] is not None and (got["exit"] < 0 or got["exit"] >= 128 or
                                        any(marker in got.get("stderr", b"") for marker in CRASH_MARKERS))


def settle(program: str, case: dict, plan: dict) -> tuple[dict | None, str]:
    """The case as it is recorded, from its "record" entry (`plan`), and how it was settled.

    - "formatted": files replaced by what the program's `format -` prints for them, where it
      formats them (a case built on files already formatted).
    - "variants": other file sets for the case, tried after its own files in order. With "want"
      "same", the last of them is the base: the program the others edit, and a file set is kept
      if it ends as the base does (the same exit code, printing something where the base does),
      one that prints something else first; failing that, the base. With "complete" set, a base
      that does not exit 0 drops the case (None). With "want" "diagnostics", the first file set
      whose check reports something is kept, failing that the last.
    """
    files = dict(case["files"])
    for name in plan.get("formatted", []):
        got = run_case([program], {"files": {}, "argv": ["format", "-"], "stdin": files[name]}, keep_stderr=True)
        if got["exit"] == 0 and not crashed(got):
            files[name] = got["stdout"].decode(*ENCODING)
    case = dict(case, files=files)
    options = [files] + plan.get("variants", [])
    if len(options) == 1:
        return case, "as generated"
    runs = lambda chosen: run_case([program], dict(case, files=chosen), keep_stderr=True)  # noqa: E731
    if plan.get("want") == "diagnostics":
        for index, chosen in enumerate(options):
            got = runs(chosen)
            if got["exit"] is not None and not crashed(got) and got["stdout"].strip() not in (b"", b"[]"):
                return dict(case, files=chosen), f"variant {index}"
        return dict(case, files=options[-1]), "no variant reports"
    base = runs(options[-1])
    if plan.get("complete") and base["exit"] != 0:
        return None, "base does not complete"
    fallback = None
    for index, chosen in enumerate(options[:-1]):
        got = runs(chosen)
        if got["exit"] is None or crashed(got) or got["exit"] != base["exit"] or (base["stdout"] and not got["stdout"]):
            continue
        if got["stdout"] != base["stdout"]:
            return dict(case, files=chosen), f"variant {index}"
        fallback = fallback if fallback is not None else (index, chosen)
    if fallback is not None:
        return dict(case, files=fallback[1]), f"variant {fallback[0]}, output as the base's"
    return dict(case, files=options[-1]), "base"


def group(case: dict) -> str:
    """What a case asks, as seen without reading a file: the command, and for run
    and check whether diagnostics come as JSON; for format, standard input, files or --check."""
    argv = case["argv"]
    words = [arg for arg in argv if not arg.startswith("-")]
    command = "run" if words and words[0].endswith(".goose") else words[0] if words else ""
    if command == "format":
        return "format --check" if "--check" in argv else "format -" if case.get("stdin") is not None else "format"
    return command + (" --diagnostics json" if "json" in argv else "")


def every_file(case: dict) -> dict:
    """What `format --check <target>` prints and exits with when every .goose file it reaches is
    unformatted: their paths, sorted, ./-prefixed for the target `.`."""
    target = case["argv"][-1]
    names = sorted(name for name in case["files"] if name.endswith(".goose"))
    if target == ".":
        listed = sorted(f"./{name}" for name in names)
    elif target in case["files"]:
        listed = [target]
    else:
        listed = [name for name in names if name.startswith(target.rstrip("/") + "/")]
    return {"exit": 1 if listed else 0, "stdout": "".join(f"{name}\n" for name in listed)}


def free_cases(cases: list[dict], outputs: dict, cli: set[str]) -> dict[str, list[str]]:
    """The cases a program with no compiler in it answers, by group (`group`): every command-line case
    (`cli`, a table of the original's answers), and in each other group the cases that answer its
    most common (stdout, exit code) where two or more share it, or more where they are more: those
    whose standard input is already formatted (an echo, for `format -`) or whose every file is
    unformatted (a listing, for `format --check`)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        groups["command line" if case["id"] in cli else group(case)].append(case)
    free = {}
    for name, members in groups.items():
        if name == "command line":
            free[name] = [case["id"] for case in members]
            continue
        answer = lambda case: (outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"])  # noqa: E731
        common, shared = max(Counter(map(answer, members)).items(), key=lambda item: (item[1], repr(item[0])))
        options = [[case["id"] for case in members if answer(case) == common] if shared > 1 else []]
        if name == "format -":
            options.append([case["id"] for case in members if answer(case) == (case["stdin"], 0)])
        if name == "format --check":
            options.append([case["id"] for case in members
                            if answer(case) == (every_file(case)["stdout"], every_file(case)["exit"])])
        free[name] = max(options, key=len)
    return free


def comments(text: str) -> list[str]:
    """The comments of a Goose text, // and nested /* */, outside string and character literals."""
    found, at, size = [], 0, len(text)
    while at < size:
        if text.startswith('"""', at):
            end = text.find('"""', at + 3)
            at = size if end < 0 else end + 3
        elif text[at] in "\"'":
            end = at + 1
            while end < size and text[end] not in (text[at], "\n"):
                end += 2 if text[end] == "\\" else 1
            at = end + 1
        elif text.startswith("//", at):
            end = text.find("\n", at)
            end = size if end < 0 else end
            found.append(text[at + 2:end])
            at = end
        elif text.startswith("/*", at):
            depth, end = 1, at + 2
            while end < size and depth:
                depth += 1 if text.startswith("/*", end) else -1 if text.startswith("*/", end) else 0
                end += 2 if text.startswith(("/*", "*/"), end) else 1
            found.append(text[at + 2:end - 2])
            at = end
        else:
            at += 1
    return found


def diagnostics(stdout: str) -> list[dict]:
    """The objects of the JSON array that --diagnostics json ends standard output with, if any."""
    lines = stdout.split("\n")
    for at in range(len(lines) - 1, -1, -1):
        if lines[at].startswith("["):
            try:
                found = json.loads("\n".join(lines[at:]))
            except ValueError:
                continue
            return [item for item in found if isinstance(item, dict)] if isinstance(found, list) else []
    return []


def fragments(stdout: str) -> set[str]:
    """What of a recorded answer no comment may quote: every diagnostic's message, and every line
    of standard output of 12 characters or more."""
    found = {line.strip() for line in stdout.splitlines() if len(line.strip()) >= 12}
    return found | {item["message"] for item in diagnostics(stdout) if len(str(item.get("message", ""))) >= 8}


def select(cases: list[dict], outputs: dict, cli: set[str]) -> tuple[list[dict], dict[str, list[str]]]:
    """The recorded cases less, in this order and each time by id: those with a comment quoting any
    case's answer (a program could collect them); `format -` cases whose input is already
    formatted; beyond PAIR_SHARE of the cases, those with an answer that many others share (the
    command line aside); beyond CHECK_EMPTY_SHARE of the check cases, those answering []; and
    while more than FLOOR_SHARE of them can be answered without a compiler (free_cases), one of
    those in the largest group. Also the ids left out, by reason."""
    dropped: dict[str, list[str]] = defaultdict(list)
    quoted = set().union(*(fragments(output["stdout"]) for output in outputs.values())) if outputs else set()
    kept = []
    for case in cases:
        said = "\n".join(note for text in list(case["files"].values()) + [case.get("stdin") or ""] for note in comments(text))
        if said and any(piece in said for piece in quoted):
            dropped["comment quotes an answer"].append(case["id"])
        elif group(case) == "format -" and outputs[case["id"]] == {"exit": 0, "stdout": case["stdin"]}:
            dropped["input already formatted"].append(case["id"])
        else:
            kept.append(case)
    limit, seen, cases, kept = max(1, int(PAIR_SHARE * len(kept))), Counter(), kept, []
    for case in cases:
        answer = (outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"])
        seen[answer] += 1
        if seen[answer] > limit and case["id"] not in cli:
            dropped["answer shared by many cases"].append(case["id"])
        else:
            kept.append(case)
    checks = [case for case in kept if group(case).startswith("check")]
    limit, empty, cases, kept = max(1, int(CHECK_EMPTY_SHARE * len(checks))), 0, kept, []
    for case in cases:
        if group(case).startswith("check") and outputs[case["id"]] == {"exit": 0, "stdout": "[]\n"}:
            empty += 1
            if empty > limit:
                dropped["check answering []"].append(case["id"])
                continue
        kept.append(case)
    while True:
        free = free_cases(kept, outputs, cli)
        groups = [name for name in free if name != "command line" and free[name]]
        if sum(map(len, free.values())) <= FLOOR_SHARE * len(kept) or not groups:
            break
        victim = max(free[max(groups, key=lambda name: (len(free[name]), name))])
        dropped["passed with no compiler"].append(victim)
        kept = [case for case in kept if case["id"] != victim]
    return kept, dict(dropped)


def record(program: str, cases: list[dict]) -> tuple[list[dict], dict, dict]:
    """The cases kept (settled, without their "record" entries): those the program finishes the
    same way twice, each time in at most KEEP_SEC and without crashing, less those `select` leaves
    out; what it printed for them; and how long every run took, how each case was settled and why
    the others were left out."""
    finished, outputs, cli = [], {}, set()
    report = {"keep_seconds": KEEP_SEC, "seconds": {}, "slow": [], "unsteady": [], "crashed": [], "settled": {},
              "dropped": {}}
    for case in cases:
        plan = case.get("record", {})
        case = {key: value for key, value in case.items() if key != "record"}
        if plan.get("cli"):
            cli.add(case["id"])
        settled, how = settle(program, case, plan)
        report["settled"][case["id"]] = how
        if settled is None:
            report["dropped"].setdefault(how, []).append(case["id"])
            continue
        first, second = (run_case([program], settled, keep_stderr=True) for _ in range(2))
        report["seconds"][case["id"]] = [first["seconds"], second["seconds"]]
        if first["exit"] is None or (first["exit"], first["stdout"]) != (second["exit"], second["stdout"]):
            report["unsteady"].append(case["id"])
        elif crashed(first) or crashed(second):
            report["crashed"].append(case["id"])
        elif max(first["seconds"], second["seconds"]) > KEEP_SEC:
            report["slow"].append(case["id"])
        else:
            finished.append(settled)
            outputs[case["id"]] = {"exit": first["exit"], "stdout": first["stdout"].decode(*ENCODING)}
    kept, dropped = select(finished, outputs, cli)
    for reason, ids in dropped.items():
        report["dropped"].setdefault(reason, []).extend(ids)
    report["cli"] = sorted(cli)
    return kept, {case["id"]: outputs[case["id"]] for case in kept}, report


def main() -> None:
    """Record what a program prints for every case, or compare a program with recorded outputs."""
    mode, program, cases_path, expected_path = sys.argv[1:5]
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))["cases"]
    if mode == "record":
        kept, outputs, report = record(program, cases)
        clear_workspace()
        if len(report["unsteady"]) > 0.15 * len(cases) or len(report["crashed"]) > 0.02 * len(cases) \
                or len(kept) < 0.6 * len(cases):
            raise SystemExit(f"kept {len(kept)} of {len(cases)} cases: {len(report['unsteady'])} did not finish the same "
                             f"way twice, {len(report['crashed'])} crashed, {len(report['slow'])} took more than "
                             f"{KEEP_SEC} seconds")
        Path(expected_path).write_text(json.dumps(outputs, sort_keys=True))
        if "--keep" in sys.argv:
            Path(sys.argv[sys.argv.index("--keep") + 1]).write_text(json.dumps({"cases": kept}, sort_keys=True, ensure_ascii=False))
        if "--report" in sys.argv:
            Path(sys.argv[sys.argv.index("--report") + 1]).write_text(json.dumps(report, sort_keys=True))
        print(f"recorded {len(kept)} of {len(cases)} cases ({len(report['slow'])} slow, {len(report['unsteady'])} unsteady, "
              f"{len(report['crashed'])} crashed, " + ", ".join(f"{len(ids)} {why}" for why, ids in report["dropped"].items()) + ")")
        return
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    passed = 0
    for case in cases:
        got, want = run_case([program], case), expected[case["id"]]
        ok = matches(got, want)
        passed += ok
        if not ok and "-v" in sys.argv:
            print(f"FAIL {case['id']}: goose {' '.join(case['argv'])} (exit {got['exit']}, expected {want['exit']})")
    clear_workspace()
    print(f"{passed} of {len(cases)} cases pass")


if __name__ == "__main__":
    main()
