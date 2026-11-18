"""Run example cases against one compiler executable and compare what it prints.

Each case is written into the same fixed directory, so that paths in an output are the same
for every run. Every run gets the same resource limits: an 8 MB stack, which is where
`goose run` runs a program, and bounds on processes, file size and data.

usage: python3 <this file> check <program> <cases.json> <outputs.json> [-v]
       python3 <this file> record <program> <cases.json> <outputs.json> [--keep <cases-out.json>] [--report <timing.json>]

`record` runs every case twice and keeps the cases that finish in at most KEEP_SEC and print the
same both times; `--keep` writes those cases to a file of their own and `--report` how long each
run took and why cases were left out. Standard output is compared byte for byte; the outputs
file holds it as text, invalid UTF-8 as surrogate escapes.
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
import time
from pathlib import Path

WORKSPACE = Path("/tmp/goose-case")
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
    """Remove whatever is at the workspace path without following a symbolic link: a directory
    with its contents, anything else by itself."""
    try:
        mode = os.lstat(WORKSPACE).st_mode
    except FileNotFoundError:
        return
    if stat.S_ISDIR(mode):
        shutil.rmtree(WORKSPACE)
    else:
        os.unlink(WORKSPACE)


def prepare(case: dict, owner: tuple[int, int] | None) -> None:
    """A new workspace holding the case's files, owned by `owner` (user and group ids) where given."""
    clear_workspace()
    WORKSPACE.mkdir(parents=True)
    for name, text in case["files"].items():
        target = WORKSPACE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if owner:
        for root, directories, files in os.walk(WORKSPACE):
            for name in directories + files:
                os.lchown(os.path.join(root, name), *owner)
        os.lchown(WORKSPACE, *owner)


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


def run_case(program: list[str], case: dict, prefix: list[str] | None = None, owner: tuple[int, int] | None = None) -> dict:
    """Run one case: its exit code, its standard output as bytes and how long it took. A case that
    cannot be set up or started, runs past CASE_SEC or prints more than OUTPUT_LIMIT bytes has no
    exit code and an "error" instead."""
    try:
        prepare(case, owner)
    except OSError as exc:
        return {"exit": None, "stdout": None, "error": f"workspace: {type(exc).__name__}", "seconds": 0.0}
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "NO_COLOR": "1",
           "TERM": "dumb", "GOOSE_PROGRESS": "plain"}
    started = time.monotonic()
    try:
        proc = subprocess.Popen((prefix or []) + program + case["argv"], cwd=WORKSPACE, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True, preexec_fn=limit)
    except (OSError, subprocess.SubprocessError):
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
    if problem:
        return {"exit": None, "stdout": None, "error": problem, "seconds": seconds}
    return {"exit": proc.returncode, "stdout": out, "seconds": seconds}


def matches(got: dict, want: dict) -> bool:
    """A run printed the recorded answer: the same exit code and the same bytes on standard output."""
    return got["exit"] is not None and got["exit"] == want["exit"] and got["stdout"] == want["stdout"].encode(*ENCODING)


def record(program: str, cases: list[dict]) -> tuple[list[dict], dict, dict]:
    """The cases the program finishes the same way twice, each time in at most KEEP_SEC; what it
    printed for them; and how long every run took and why the others were left out."""
    kept, outputs = [], {}
    report = {"keep_seconds": KEEP_SEC, "seconds": {}, "slow": [], "unsteady": []}
    for case in cases:
        first, second = run_case([program], case), run_case([program], case)
        report["seconds"][case["id"]] = [first["seconds"], second["seconds"]]
        if first["exit"] is None or (first["exit"], first["stdout"]) != (second["exit"], second["stdout"]):
            report["unsteady"].append(case["id"])
        elif max(first["seconds"], second["seconds"]) > KEEP_SEC:
            report["slow"].append(case["id"])
        else:
            kept.append(case)
            outputs[case["id"]] = {"exit": first["exit"], "stdout": first["stdout"].decode(*ENCODING)}
    return kept, outputs, report


def main() -> None:
    """Record what a program prints for every case, or compare a program with recorded outputs."""
    mode, program, cases_path, expected_path = sys.argv[1:5]
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))["cases"]
    if mode == "record":
        kept, outputs, report = record(program, cases)
        clear_workspace()
        if len(report["unsteady"]) > 0.15 * len(cases) or len(kept) < 0.6 * len(cases):
            raise SystemExit(f"kept {len(kept)} of {len(cases)} cases: {len(report['unsteady'])} did not finish the same "
                             f"way twice, {len(report['slow'])} took more than {KEEP_SEC} seconds")
        Path(expected_path).write_text(json.dumps(outputs, sort_keys=True))
        if "--keep" in sys.argv:
            Path(sys.argv[sys.argv.index("--keep") + 1]).write_text(json.dumps({"cases": kept}, sort_keys=True, ensure_ascii=False))
        if "--report" in sys.argv:
            Path(sys.argv[sys.argv.index("--report") + 1]).write_text(json.dumps(report, sort_keys=True))
        print(f"recorded {len(kept)} of {len(cases)} cases ({len(report['slow'])} slow, {len(report['unsteady'])} unsteady)")
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
