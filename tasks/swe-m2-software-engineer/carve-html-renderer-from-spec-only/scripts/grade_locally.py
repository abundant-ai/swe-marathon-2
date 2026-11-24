"""Grade the reference and a no-op locally from a packaged bundle, without Docker or root.

usage: grade_locally.py <bundle dir> [--original PATH] [--out DIR]

Does what the bundle's verifier image does, with this machine's build of the original (default
experiment/original/carve-macos, the same carve-rs 0.1.14 release for macOS): records the
bundle's private cases with the bundle's own recorder.py and recording.py into a private
directory, as the builder stage does; then, with the bundle's own verify.py, reads three
trees the way an evaluation reads /app/rebuild (marked by the bundle's own sweep
program, run on a copy) and grades them: the reference (the original as /app/rebuild/carve), an
empty tree, and a program that prints nothing. The privilege drop, sealing and the sweeps
between cases need root and Linux, so they are left out; what the runs print is compared exactly
as in an evaluation.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
STEP = "steps/01-implement-renderer"


ROLES = {"List the processes": "processes", "Record whether": "egress", "Put a mark": "mark",
         "Make /app/rebuild safe": "fixing", "Measure /app/rebuild": "measuring", "Move aside what": "artifacts"}


def hook_programs(bundle: Path) -> dict[str, str]:
    """The Python blocks of the bundle's sweep (environment/fsmaint-sweep) by what each does, read
    from the start of its docstring: the process listing, the egress probe, the refused mark, the
    link fixing and the measuring (the end-bound reader has none: "bound")."""
    text = (bundle / "environment" / "fsmaint-sweep").read_text()
    found = {}
    for program in re.findall(r"<<'EOF'\n(.*?)\nEOF", text, re.S):
        head = program.lstrip('"')
        found[next((role for start, role in ROLES.items() if head.startswith(start)), "bound")] = program
    return found


def mark(bundle: Path, top: Path) -> str:
    """Run the sweep's blocks on `top` in the sweep's order, as this user: the process and egress
    records into a state dir, the refused mark, the link fixing and the measuring (which reads the
    state and the notes). A far-future end bound, so an honest source read now is never taken for
    one written after the end; the mark's first line."""
    programs = hook_programs(bundle)
    state = top.parent / ".state"
    state.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-I", "-", str(state / "procs.json")], input=programs["processes"], text=True,
                   check=True, capture_output=True, timeout=120)
    egress = programs["egress"].replace(
        '("github.com", 443), ("pypi.org", 443), ("proxy.golang.org", 443), ("registry.npmjs.org", 443)', '("127.0.0.1", 9),')
    subprocess.run([sys.executable, "-I", "-", str(state / "netprobe.json")], input=egress, text=True,
                   check=True, capture_output=True, timeout=120)
    if "mark" in programs:
        subprocess.run([sys.executable, "-I", "-", str(top), str(state)], input=programs["mark"], text=True,
                       check=True, capture_output=True, timeout=120)
    end = f"{time.time() + 10 ** 9}"
    notes = top.parent / ".fsmaint-notes"
    with open(notes, "w") as handle:
        subprocess.run([sys.executable, "-I", "-", str(top), "200000", "2000000000", end, "start"], input=programs["fixing"],
                       text=True, check=True, stdout=handle, stderr=subprocess.STDOUT, timeout=300)
    subprocess.run([sys.executable, "-I", "-", str(top), "200000", "2000000000", str(notes), str(state), "1", "0",
                    end, end, end, "start"], input=programs["measuring"], text=True, check=True, capture_output=True, timeout=600)
    return (top / ".fsmaint").read_text().splitlines()[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--original", type=Path, default=TASK_ROOT / "experiment" / "original" / "carve-macos")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    step = bundle / STEP if (bundle / STEP).is_dir() else bundle   # a flat bundle has the step's files at its top
    work = (args.out or Path(tempfile.mkdtemp(prefix="carve-grade-"))).resolve()
    tests = work / "tests"
    if tests.exists():
        shutil.rmtree(tests)
    shutil.copytree(step / "tests", tests)
    record = work / "record"
    record.mkdir(parents=True, exist_ok=True)
    original = args.original.resolve()
    verifier = tests / "verifier"
    subprocess.run([sys.executable, "-B", str(verifier / "recorder.py"), "record", str(original), str(tests / "private" / "cases.json"),
                    str(record / "expected.json"), "--keep", str(record / "kept.json"), "--report", str(record / "timing.json"),
                    "--probes", str(tests / "private" / "probes.json"), "--probes-out", str(record / "probes_expected.json")],
                   check=True, timeout=3600)
    (record / "build.txt").write_text(f"version carve-rs 0.1.14 (local build {original.name})\n")
    subprocess.run([sys.executable, "-B", str(verifier / "recording.py"), str(tests / "private" / "cases.json"), str(record / "kept.json"),
                    str(record / "expected.json"), str(record / "timing.json"), str(record / "recording.json"),
                    "--build", str(record / "build.txt")], check=True, timeout=600, cwd=verifier, capture_output=True)
    private = work / "private"
    private.mkdir(exist_ok=True)
    shutil.copy(record / "kept.json", private / "cases.json")
    shutil.copy(record / "expected.json", private / "expected.json")
    shutil.copy(record / "recording.json", private / "recording.json")
    shutil.copy(tests / "private" / "probes.json", private / "probes.json")
    shutil.copy(record / "probes_expected.json", private / "probes_expected.json")
    deliveries = {}
    reference = work / "deliveries" / "reference" / "rebuild"
    reference.mkdir(parents=True, exist_ok=True)
    # As solve.sh installs it: the original with the bundle's blank.json strings overwritten in place.
    binary = original.read_bytes()
    for text in json.loads((step / "solution" / "blank.json").read_text())["strings"]:
        binary = binary.replace(text.encode(), b"x" * len(text.encode()))
    (reference / "carve").write_bytes(binary)
    (reference / "carve").chmod(0o755)
    if sys.platform == "darwin":  # a changed Mach-O needs a new ad-hoc signature to run
        subprocess.run(["codesign", "-s", "-", "-f", str(reference / "carve")], check=True, capture_output=True, timeout=120)
    shutil.copy(step / "solution" / "LICENSE", reference / "LICENSE")
    empty = work / "deliveries" / "empty" / "rebuild"
    empty.mkdir(parents=True, exist_ok=True)
    silent = work / "deliveries" / "silent" / "rebuild"
    silent.mkdir(parents=True, exist_ok=True)
    (silent / "carve").write_text("#!/bin/sh\nexit 0\n")
    (silent / "carve").chmod(0o755)
    for name, top in (("reference", reference), ("empty", empty), ("silent", silent)):
        deliveries[name] = {"mark": mark(bundle, top)}
    driver = f"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, {str(tests)!r})
import verify
work = Path({str(work)!r})
verify.runcases.WORKSPACE = work / "tmp" / "carve-case"
verify.runcases.HOME = work / "tmp" / "carve-home"
verify.runcases.TEMP = work / "tmp" / "carve-tmp"
(work / "tmp").mkdir(exist_ok=True)
results = {{}}
builds = verify.upstream_builds()
for name in ("reference", "empty", "silent"):
    top = work / "deliveries" / name / "rebuild"
    verify.SWEEP_STATE = top.parent / ".state" / "out" / "sweep.json"   # where this sweep got to
    notes, refused = verify.manifest(top)
    record = verify.manifest_record(top)
    fetched = verify.fetched_build(top, builds)
    started = time.monotonic()
    if refused or fetched:
        metrics = {{"reward": 0.0, "cases_passed": 0, "cases_total": None, "notes": [fetched or "refused"], "by_kind": {{}},
                   "timeouts": 0, "failed_sample": [], "fingerprint": {{}}, "diagnostics": {{}}}}
    else:
        metrics = verify.run_cases(top / "carve", work / "private", [], None)
        metrics["fingerprint"] = verify.fingerprint(top / "carve", work / "private", [], None, time.monotonic() + 600)
    results[name] = {{"reward": metrics["reward"], "passed": metrics["cases_passed"], "total": metrics["cases_total"],
                     "notes": notes + metrics["notes"], "seconds": round(time.monotonic() - started, 1),
                     "by_kind": metrics["by_kind"], "timeouts": metrics["timeouts"], "failed_sample": metrics["failed_sample"][:10],
                     "fingerprint": metrics.get("fingerprint"), "diagnostics": metrics.get("diagnostics"),
                     "sweep_flags": record.get("flags"), "sweep_stage": (verify.sweep_state() or {{}}).get("stage")}}
print(json.dumps(results))
"""
    done = subprocess.run([sys.executable, "-B", "-c", driver], capture_output=True, text=True, timeout=7200)
    if done.returncode != 0:
        raise SystemExit(done.stdout[-3000:] + done.stderr[-3000:])
    results = json.loads(done.stdout.strip().splitlines()[-1])
    for name, result in results.items():
        result.update(deliveries[name])
    recording = json.loads((record / "recording.json").read_text())
    summary = {"work": str(work), "recording": {key: recording[key] for key in ("cases_recorded", "cases_kept", "baselines", "djot_engine",
                                                                              "kept_ids_sha256", "wall_seconds")},
               "results": results}
    (work / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({name: {k: v for k, v in result.items() if k in ("reward", "passed", "total", "mark", "notes", "seconds",
                                                                        "fingerprint", "sweep_flags", "sweep_stage")}
                      for name, result in results.items()} | {"recording": summary["recording"]}, indent=1))


if __name__ == "__main__":
    main()
