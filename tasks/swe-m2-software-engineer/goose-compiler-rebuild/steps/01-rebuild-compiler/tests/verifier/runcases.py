"""Run example cases against one compiler executable and compare what it prints.

Each case is written into the same fixed directory, so that paths in an output are the same
for every run.

usage: python3 <this file> check <program> <cases.json> <outputs.json> [-v]
       python3 <this file> record <program> <cases.json> <outputs.json> [--keep <cases-out.json>]

`record` runs every case twice and keeps the cases that finish within the time limit and print
the same both times; `--keep` writes those cases to a file of their own.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/tmp/goose-case")
CASE_SEC = 2
OUTPUT_LIMIT = 1_000_000


def run_case(program: list[str], case: dict, prefix: list[str] | None = None, owner: str | None = None) -> dict:
    """Run one case and return its exit code and standard output."""
    shutil.rmtree(WORKSPACE, ignore_errors=True)
    WORKSPACE.mkdir(parents=True)
    for name, text in case["files"].items():
        target = WORKSPACE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if owner:
        subprocess.run(["chown", "-R", owner, str(WORKSPACE)], check=False)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "NO_COLOR": "1",
           "TERM": "dumb", "GOOSE_PROGRESS": "plain"}
    try:
        proc = subprocess.Popen((prefix or []) + program + case["argv"], cwd=WORKSPACE, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return {"exit": None, "stdout": None, "error": "could not start"}
    try:
        out, _ = proc.communicate((case["stdin"] or "").encode("utf-8"), timeout=CASE_SEC)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
        return {"exit": None, "stdout": None, "error": "timeout"}
    return {"exit": proc.returncode, "stdout": out.decode("utf-8", "replace")[:OUTPUT_LIMIT]}


def record(program: str, cases: list[dict]) -> tuple[list[dict], dict]:
    """The cases the program finishes the same way twice, and what it printed for them."""
    kept, outputs = [], {}
    for case in cases:
        first, second = run_case([program], case), run_case([program], case)
        if first["exit"] is not None and first == second and len(first["stdout"]) < OUTPUT_LIMIT:
            kept.append(case)
            outputs[case["id"]] = first
    return kept, outputs


def main() -> None:
    """Record what a program prints for every case, or compare a program with recorded outputs."""
    mode, program, cases_path, expected_path = sys.argv[1:5]
    cases = json.loads(Path(cases_path).read_text())["cases"]
    if mode == "record":
        kept, outputs = record(program, cases)
        if len(kept) < 0.85 * len(cases):
            raise SystemExit(f"only {len(kept)} of {len(cases)} cases finished the same way twice")
        Path(expected_path).write_text(json.dumps(outputs, sort_keys=True))
        if "--keep" in sys.argv:
            Path(sys.argv[sys.argv.index("--keep") + 1]).write_text(json.dumps({"cases": kept}, sort_keys=True, ensure_ascii=False))
        print(f"recorded {len(kept)} of {len(cases)} cases")
        return
    expected = json.loads(Path(expected_path).read_text())
    passed = 0
    for case in cases:
        got, want = run_case([program], case), expected[case["id"]]
        ok = got["exit"] == want["exit"] and got["stdout"] == want["stdout"]
        passed += ok
        if not ok and "-v" in sys.argv:
            print(f"FAIL {case['id']}: goose {' '.join(case['argv'])} (exit {got['exit']}, expected {want['exit']})")
    print(f"{passed} of {len(cases)} cases pass")


if __name__ == "__main__":
    main()
