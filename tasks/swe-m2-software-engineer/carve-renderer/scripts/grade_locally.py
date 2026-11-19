"""Grade the reference and a no-op locally from a packaged bundle, without Docker or root.

usage: grade_locally.py <bundle dir> [--original PATH] [--out DIR]

Does what the bundle's verifier image does, with this machine's build of the original (default
experiment/original/carve-macos, the same carve-rs 0.1.14 release for macOS): records the
bundle's private cases with the bundle's own recorder.py and recording.py into a private
directory, as the builder stage does; then, with the bundle's own verify.py, reads three
deliveries the way an evaluation reads /app/rebuild (marked by the bundle's own collect hook
program, run on a copy) and grades them: the reference (the original as /app/rebuild/carve), an
empty delivery, and a program that prints nothing. The privilege drop, sealing and the sweeps
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


def hook_programs(bundle: Path) -> list[str]:
    """The five Python blocks of the bundle's collect hook (environment/session-finish): the process
    listing, the egress probe, the turn-end reader, the link fixing and the measuring."""
    text = (bundle / "environment" / "session-finish").read_text()
    return re.findall(r"<<'EOF'\n(.*?)\nEOF", text, re.S)


def mark(bundle: Path, top: Path) -> str:
    """Run the hook's blocks on `top`, as this user: the process and egress records into a state dir,
    the link fixing and the measuring (which reads the state and the notes). A far-future turn end,
    so an honest source read now is never taken for one written after the turn; the mark's first
    line."""
    processes, egress, _turn, fixing, measuring = hook_programs(bundle)
    state = top.parent / ".state"
    state.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-I", "-", str(state / "processes.json")], input=processes, text=True,
                   check=True, capture_output=True, timeout=120)
    egress = egress.replace('("github.com", 443), ("pypi.org", 443), ("proxy.golang.org", 443), ("registry.npmjs.org", 443)',
                            '("127.0.0.1", 9),')
    subprocess.run([sys.executable, "-I", "-", str(state / "egress.json")], input=egress, text=True,
                   check=True, capture_output=True, timeout=120)
    end = f"{time.time() + 10 ** 9}"
    notes = top.parent / ".delivery-notes"
    with open(notes, "w") as handle:
        subprocess.run([sys.executable, "-I", "-", str(top), "200000", "2000000000", end, "start"], input=fixing, text=True,
                       check=True, stdout=handle, stderr=subprocess.STDOUT, timeout=300)
    subprocess.run([sys.executable, "-I", "-", str(top), "200000", "2000000000", str(notes), str(state), "1", "0",
                    end, end, end, "start"], input=measuring, text=True, check=True, capture_output=True, timeout=300)
    return (top / ".delivered").read_text().splitlines()[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--original", type=Path, default=TASK_ROOT / "experiment" / "original" / "carve-macos")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    work = (args.out or Path(tempfile.mkdtemp(prefix="carve-grade-"))).resolve()
    tests = work / "tests"
    if tests.exists():
        shutil.rmtree(tests)
    shutil.copytree(bundle / STEP / "tests", tests)
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
    for text in json.loads((bundle / STEP / "solution" / "blank.json").read_text())["strings"]:
        binary = binary.replace(text.encode(), b"x" * len(text.encode()))
    (reference / "carve").write_bytes(binary)
    (reference / "carve").chmod(0o755)
    if sys.platform == "darwin":  # a changed Mach-O needs a new ad-hoc signature to run
        subprocess.run(["codesign", "-s", "-", "-f", str(reference / "carve")], check=True, capture_output=True, timeout=120)
    shutil.copy(bundle / STEP / "solution" / "LICENSE", reference / "LICENSE")
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
    notes, refused = verify.delivery(top)
    record = verify.delivery_record(top)
    fetched = verify.fetched_build(top, builds)
    started = time.monotonic()
    if refused or fetched:
        metrics = {{"reward": 0.0, "cases_passed": 0, "cases_total": None, "notes": [fetched or "refused"], "by_kind": {{}},
                   "timeouts": 0, "failed_sample": [], "fingerprint": {{}}, "diagnostics": {{}}}}
    else:
        metrics = verify.grade(top / "carve", work / "private", [], None)
        metrics["fingerprint"] = verify.fingerprint(top / "carve", work / "private", [], None, time.monotonic() + 600)
    results[name] = {{"reward": metrics["reward"], "passed": metrics["cases_passed"], "total": metrics["cases_total"],
                     "notes": notes + metrics["notes"], "seconds": round(time.monotonic() - started, 1),
                     "by_kind": metrics["by_kind"], "timeouts": metrics["timeouts"], "failed_sample": metrics["failed_sample"][:10],
                     "fingerprint": metrics.get("fingerprint"), "diagnostics": metrics.get("diagnostics"),
                     "delivery_flags": record.get("flags")}}
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
                                                                        "fingerprint", "delivery_flags")}
                      for name, result in results.items()} | {"recording": summary["recording"]}, indent=1))


if __name__ == "__main__":
    main()
