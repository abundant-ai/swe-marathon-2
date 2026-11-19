"""Record what the original compiler prints for each case, when an image is built; never shipped to
the agent. The agent's image gets the plain runner (runcases.py) and the recorded examples only.

usage: python3 recorder.py record <program> <cases.json> <outputs.json> [--keep <cases-out.json>]
                                   [--report <report.json>] [--renumber <prefix>]

Each case is first settled (`settle`): where its "record" entry asks, files are replaced by the
program's own `format -` output, and of the case's variants the first that runs the way its rule
wants is chosen. The settled case is run twice and a third time perturbed (`perturbed`: another
binary path, environment and stack placement, one CPU, glibc's baseline maths and no malloc cache),
and kept if all three print the same and end normally (`crashed`), and the first two used at most
KEEP_CPU seconds of CPU and KEEP_SEC of wall time each. Last, by rule and by id, `select` leaves out
the cases whose answers take no compiler to give. `--keep` writes the cases kept, without their
"record" entries (renumbered from 1 with `--renumber`), and `--report` how each run went and why
cases were left out.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

try:  # run as a script beside runcases.py, or imported from the verifier package
    from runcases import ENCODING, LIMITS, clear_workspace, limit, run_case
except ImportError:
    from .runcases import ENCODING, LIMITS, clear_workspace, limit, run_case

KEEP_SEC = 1.0   # wall time of each of the two runs, at most: generous, since a busy builder is slow
KEEP_CPU = 0.4   # CPU time of each, at most, which a busy builder hardly changes: a fifth of the run limit
# A run of the original that ends in one of these, or by a signal, is no answer an implementation
# can give: the compiler's own internal error, its JIT failing, a sanitizer or C++ runtime abort.
CRASH_MARKERS = (b"internal error", b"libtcc:", b"Sanitizer", b"terminate called", b"core dumped")
PAIR_SHARE = 0.012       # cases kept with any one (stdout, exit code), command-line cases aside, at most
CHECK_EMPTY_SHARE = 0.05  # check cases kept that answer [], at most
FLOOR_SHARE = 0.045      # cases a dispatcher with no compiler passes (free_cases), at most
PERTURBED_ENV = {"GLIBC_TUNABLES": "glibc.cpu.hwcaps=-AVX2,-FMA,-FMA4:glibc.malloc.tcache_count=0",
                 "GOOSE_PERTURBED_PADDING": "p" * 4096}


def crashed(got: dict) -> bool:
    """A finished run of the original that ended by a signal (an exit code below 0 or from 128), or
    with one of CRASH_MARKERS on its standard error or in a diagnostic of the JSON it printed
    (--diagnostics json reports a JIT failure there). A program's own abort, which the language
    defines, exits 1 and is an answer like any other."""
    if got["exit"] is None:
        return False
    messages = [str(item.get("message", "")).encode() for item in diagnostics(got["stdout"].decode(*ENCODING))]
    return got["exit"] < 0 or got["exit"] >= 128 or any(marker in text for marker in CRASH_MARKERS
                                                         for text in [got.get("stderr", b"")] + messages)


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
    run or check case's answer (a program could collect them; a format answer is its input, and
    the command line's are its help); `format -` cases whose input is already
    formatted; beyond PAIR_SHARE of the cases, those with an answer that many others share (the
    command line aside); beyond CHECK_EMPTY_SHARE of the check cases, those answering []; and
    while more than FLOOR_SHARE of them can be answered without a compiler (free_cases), one of
    those in the largest group. Also the ids left out, by reason."""
    dropped: dict[str, list[str]] = defaultdict(list)
    quoted = set().union(set(), *(fragments(outputs[case["id"]]["stdout"]) for case in cases
                                  if case["id"] not in cli and not group(case).startswith("format")))
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


def perturbed_limits() -> None:
    """`limit`, then a stack 256 KB smaller (another stack placement) and one CPU."""
    limit()
    try:
        resource.setrlimit(resource.RLIMIT_STACK, (LIMITS[resource.RLIMIT_STACK] - (256 << 10),) * 2)
    except (ValueError, OSError):
        pass
    try:
        os.sched_setaffinity(0, {sorted(os.sched_getaffinity(0))[0]})
    except (AttributeError, OSError, IndexError):
        pass


def relocated(program: str) -> str:
    """A copy of the program, with the TinyCC files beside it, under a longer path of its own."""
    place = Path(tempfile.mkdtemp(prefix="goose-perturbed-location-")) / "bin"
    place.mkdir()
    shutil.copy2(program, place / Path(program).name)
    if (Path(program).parent / "tcclib").is_dir():
        shutil.copytree(Path(program).parent / "tcclib", place / "tcclib", symlinks=True)
    return str(place / Path(program).name)


def host() -> dict:
    """What of the machine could change an answer: CPU, kernel, CPUs usable and glibc."""
    info = {"machine": platform.machine(), "cpus": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None}
    try:
        cpu = Path("/proc/cpuinfo").read_text(errors="replace")
        info["cpu"] = next((line.split(":", 1)[1].strip() for line in cpu.splitlines() if line.startswith("model name")), "")
        flags = next((line.split(":", 1)[1].split() for line in cpu.splitlines() if line.startswith("flags")), [])
        info["fma"], info["avx2"] = "fma" in flags, "avx2" in flags
        info["kernel"] = Path("/proc/version").read_text(errors="replace").strip()
    except OSError:
        pass
    try:
        info["glibc"] = os.confstr("CS_GNU_LIBC_VERSION")
    except (ValueError, OSError, AttributeError):
        pass
    return info


def record(program: str, cases: list[dict]) -> tuple[list[dict], dict, dict]:
    """The cases kept (settled, without their "record" entries), what the program printed for them,
    and a report: how long and how much CPU every run took, how each case was settled, and why the
    others were left out."""
    finished, outputs, cli = [], {}, set()
    started = time.monotonic()
    report = {"keep_seconds": KEEP_SEC, "keep_cpu": KEEP_CPU, "seconds": {}, "cpu": {}, "slow": [], "unsteady": [],
              "crashed": [], "output_limit": [], "memory_limit": [], "disk_limit": [], "perturbed": [], "settled": {},
              "dropped": {},
              "host": host()}
    elsewhere = relocated(program)
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
        report["cpu"][case["id"]] = [first["cpu"], second["cpu"]]
        errors = {first.get("error"), second.get("error")} - {None}
        if errors:
            report["slow" if "timeout" in errors else "output_limit" if "output limit" in errors else
                   "memory_limit" if "memory limit" in errors else "disk_limit" if errors & {"disk limit", "file limit"}
                   else "unsteady"].append(case["id"])
        elif (first["exit"], first["stdout"]) != (second["exit"], second["stdout"]):
            report["unsteady"].append(case["id"])
        elif crashed(first) or crashed(second):
            report["crashed"].append(case["id"])
        elif max(first["seconds"], second["seconds"]) > KEEP_SEC or max(first["cpu"], second["cpu"]) > KEEP_CPU:
            report["slow"].append(case["id"])
        else:
            third = run_case([elsewhere], settled, keep_stderr=True, env=PERTURBED_ENV, preexec=perturbed_limits)
            if (third["exit"], third["stdout"]) != (first["exit"], first["stdout"]):
                report["perturbed"].append(case["id"])
                continue
            finished.append(settled)
            outputs[case["id"]] = {"exit": first["exit"], "stdout": first["stdout"].decode(*ENCODING)}
    shutil.rmtree(Path(elsewhere).parent.parent, ignore_errors=True)
    kept, dropped = select(finished, outputs, cli)
    for reason, ids in dropped.items():
        report["dropped"].setdefault(reason, []).extend(ids)
    report["cli"] = sorted(cli)
    report["wall_seconds"] = round(time.monotonic() - started, 1)
    return kept, {case["id"]: outputs[case["id"]] for case in kept}, report


def main() -> None:
    """Record what a program prints for every case and keep the cases worth grading."""
    if len(sys.argv) < 5 or sys.argv[1] != "record":
        raise SystemExit(__doc__)
    program, cases_path, expected_path = sys.argv[2:5]
    option = lambda name: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None  # noqa: E731
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))["cases"]
    kept, outputs, report = record(program, cases)
    clear_workspace()
    if len(report["unsteady"]) > 0.15 * len(cases) or len(report["crashed"]) > 0.02 * len(cases) \
            or len(report["perturbed"]) > 0.1 * len(cases) or len(kept) < 0.6 * len(cases):
        raise SystemExit(f"kept {len(kept)} of {len(cases)} cases: {len(report['unsteady'])} did not finish the same "
                         f"way twice, {len(report['crashed'])} crashed, {len(report['perturbed'])} changed when "
                         f"perturbed, {len(report['slow'])} were slow")
    if option("--renumber"):
        renamed = {case["id"]: f"{option('--renumber')}{index:05d}" for index, case in enumerate(kept, 1)}
        kept = [dict(case, id=renamed[case["id"]]) for case in kept]
        outputs = {renamed[key]: value for key, value in outputs.items()}
    report["kept_ids_sha256"] = hashlib.sha256("\n".join(case["id"] for case in kept).encode()).hexdigest()
    Path(expected_path).write_text(json.dumps(outputs, sort_keys=True))
    if option("--keep"):
        Path(option("--keep")).write_text(json.dumps({"cases": kept}, sort_keys=True, ensure_ascii=False))
    if option("--report"):
        Path(option("--report")).write_text(json.dumps(report, sort_keys=True))
    print(f"recorded {len(kept)} of {len(cases)} cases in {report['wall_seconds']} s ({len(report['slow'])} slow, "
          f"{len(report['unsteady'])} unsteady, {len(report['crashed'])} crashed, {len(report['perturbed'])} perturbed, "
          + ", ".join(f"{len(ids)} {why}" for why, ids in report["dropped"].items()) + ")")


if __name__ == "__main__":
    main()
