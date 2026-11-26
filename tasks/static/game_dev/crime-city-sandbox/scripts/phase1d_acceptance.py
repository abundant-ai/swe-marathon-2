"""Phase 1d acceptance runs on macOS (author tool; never packaged).

Parts (run one per invocation, inside scripts/heavy.py so only one heavy job runs; every
game process also waits for QA_MEM_FLOOR, default 30, percent free memory):
  qa       qa run over every playtest, on the reference and on the starter: the text it
           prints (kept for the wording check) and its JSON findings
  grade    the real grader (self-test first) on the reference and on the starter, with the
           playtests the reference holds as the instance set, and on the reference with the
           private set (tests/private/instances.json)
  replay10 world.replay/two-paces on the reference, ten fresh processes: distinct hashes
Projects come from --starter and --reference (staged with scripts/stage_project.py).
Results go to experiment/phase1d/<part>.json.

The reference does not hold NOT_YET until module 3 (people) lands: they are left out of
the instance set and reported apart.

Usage:
  python scripts/heavy.py -- python scripts/phase1d_acceptance.py PART --work DIR \\
      --starter DIR --reference DIR
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "scripts"))

import phase1c_acceptance as base
from qakit.procs import kill_all_live

OUT = TASK / "experiment" / "phase1d"
PLAYTESTS = TASK / "common" / "kit" / "playtests"
NOT_YET = {"people.locomotion/feet", "people.locomotion/crouch"}
# Template -> family (notes/PHASE1-PLAN.md, section 1; T is the telemetry family of WS3).
FAMILY = {
    "contract.devconsole": "M",
    "inv.telemetry": "T",
    "people.locomotion": "A",
    "people.lineup": "A",
    "persistence.round_trip": "K",
    "world.clock_lights": "I",
    "world.weather": "I",
    "world.replay": "H",
    "world.same_start": "H",
    "world.plan_compliance": "H",
}
WEIGHTS = {"A": 0.09, "H": 0.07, "I": 0.04, "K": 0.04, "M": 0.04, "T": 0.04}


def manifest(work: Path) -> Path:
    """The playtests the reference holds, as a qa-instances/1 manifest in work."""
    folder = work / "manifest"
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "plays").mkdir(parents=True)
    instances, counts = [], {}
    for path in sorted(PLAYTESTS.glob("*.json")):
        play = json.loads(path.read_text())
        if play["name"] in NOT_YET:
            continue
        fam = FAMILY[play["template"]]
        shutil.copy2(path, folder / "plays" / path.name)
        instances.append({"file": f"plays/{path.name}", "family": fam})
        counts[fam] = counts.get(fam, 0) + 1
    data = {
        "format": "qa-instances/1",
        "release": "phase1d-playtests",
        "families": {f: {"w": WEIGHTS[f], "n": n} for f, n in sorted(counts.items())},
        "instances": instances,
    }
    (folder / "instances.json").write_text(json.dumps(data, indent=1))
    return folder / "instances.json"


def run_qa(project: Path, work: Path, name: str) -> dict:
    """qa run over every playtest; Phase 1c's runner, results kept under phase1d."""
    base.OUT = OUT
    found = base.run_qa(project, work, name)
    found["not_yet"] = sorted(NOT_YET)
    return found


def main() -> int:
    """Run one part and write its results."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("part", choices=["qa", "grade", "replay10"])
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--starter", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    a = ap.parse_args()
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    base.OUT = OUT
    t0 = time.monotonic()
    try:
        if a.part == "qa":
            result = {
                "reference": run_qa(a.reference.resolve(), work, "reference"),
                "starter": run_qa(a.starter.resolve(), work, "starter"),
            }
        elif a.part == "grade":
            m = manifest(work)
            result = {
                "reference_playtests": base.run_grade(a.reference.resolve(), work, m, "ref-playtests"),
                "starter_playtests": base.run_grade(
                    a.starter.resolve(), work, m, "starter-playtests", "--skip-selftest"
                ),
                "reference_private": base.run_grade(
                    a.reference.resolve(), work, TASK / "tests/private/instances.json",
                    "ref-private", "--skip-selftest",
                ),
            }  # fmt: skip
        else:
            result = base.replay10(a.reference.resolve(), work / "replay10")
    finally:
        kill_all_live()
    result["_wall_s"] = round(time.monotonic() - t0, 1)
    (OUT / f"{a.part}.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps(result, default=str)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
