"""Phase 1h acceptance runs on macOS (author tool; never packaged).

Parts (run one per invocation, inside scripts/heavy.py so only one heavy job runs; every
game process also waits for QA_MEM_FLOOR, default 30, percent free memory):
  qa       qa run over every playtest, on the reference and on the starter: the text it
           prints (kept for the wording check) and its JSON findings
  grade    the real grader (self-test first) on the reference and on the starter, with every
           playtest as the instance set
  private  the grader on the reference and on the starter with the private set
           (tests/private/instances.json)
  replay10 a replay playtest on the reference (--play, default world.replay/car-and-ragdoll),
           ten fresh processes, one run each: distinct hashes
Projects come from --starter and --reference (staged with scripts/stage_project.py).
Results go to experiment/phase1h/<part>.json; the qa part also keeps what qa run found, as
JSON, in experiment/phase1h/qa-<project>-found.json (scripts/margin_sweep.py reads it).

Usage:
  python scripts/heavy.py -- python scripts/phase1h_acceptance.py PART --work DIR \\
      --starter DIR --reference DIR [--play NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "scripts"))

import phase1c_acceptance as base
from qakit.play import parse_play, run_play
from qakit.prepare import prepare
from qakit.procs import Limits, kill_all_live
from qakit.session import SessionOptions
from verifier.hostenv import memory_gate

OUT = TASK / "experiment" / "phase1h"
PLAYTESTS = TASK / "common" / "kit" / "playtests"
# Template -> family (notes/PHASE1-PLAN.md, section 1; T is the telemetry family of WS3).
FAMILY = {
    "contract.devconsole": "M",
    "inv.telemetry": "T",
    "people.locomotion": "A",
    "people.lineup": "A",
    "people.jump_climb_vault": "A",
    "people.fall_ragdoll": "A",
    "people.vehicle_entry": "A",
    "vehicle.handling": "B",
    "vehicle.crash": "B",
    "persistence.round_trip": "K",
    "traffic.intersection_watch": "C",
    "traffic.stop_junction": "C",
    "traffic.obstacle": "C",
    "traffic.speed": "C",
    "traffic.panic_horn": "C",
    "combat.weapons": "D",
    "combat.lock_on": "D",
    "combat.armour": "D",
    "combat.cover_firefight": "D",
    "combat.crew_hostility": "D",
    "world.clock_lights": "I",
    "world.weather": "I",
    "world.replay": "H",
    "world.same_start": "H",
    "world.plan_compliance": "H",
}
WEIGHTS = {
    "A": 0.09, "B": 0.10, "C": 0.09, "D": 0.08, "H": 0.07, "I": 0.04, "K": 0.04, "M": 0.04,
    "T": 0.04,
}  # fmt: skip


def manifest(work: Path) -> Path:
    """Every playtest as a qa-instances/1 manifest in work."""
    folder = work / "manifest"
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "plays").mkdir(parents=True)
    instances, counts = [], {}
    for path in sorted(PLAYTESTS.glob("*.json")):
        play = json.loads(path.read_text())
        fam = FAMILY[play["template"]]
        shutil.copy2(path, folder / "plays" / path.name)
        instances.append({"file": f"plays/{path.name}", "family": fam})
        counts[fam] = counts.get(fam, 0) + 1
    data = {
        "format": "qa-instances/1",
        "release": "phase1h-playtests",
        "families": {f: {"w": WEIGHTS[f], "n": n} for f, n in sorted(counts.items())},
        "instances": instances,
    }
    (folder / "instances.json").write_text(json.dumps(data, indent=1))
    return folder / "instances.json"


def replay10(project: Path, work: Path, name: str) -> dict:
    """A replay playtest ten times in fresh processes (one run each, no pace)."""
    gate = memory_gate()
    prep = prepare(
        project, work / "game", base.godot(), base.LIB, random.Random(), work / "prep",
        Limits(wall_s=600, memory_mb=4096), gate,
    )  # fmt: skip
    if not prep.ready:
        return {"problems": prep.problems}
    raw = json.loads((PLAYTESTS / (name.replace("/", ".") + ".json")).read_text())
    play = parse_play(dict(raw, runs=[{"pace_ms": 0}]))
    hashes, frames, errors = [], [], []
    for k in range(10):

        def options(_k: int, _n: int, folder: Path) -> SessionOptions:
            return SessionOptions(
                home=folder / "home", log_path=folder / "game.log",
                limits=Limits(cpu_s=600, memory_mb=1536, disk_mb=1024), before_start=gate,
            )  # fmt: skip

        rec = run_play(
            play,
            prep.game_dir,
            base.godot(),
            work / f"r{k:02d}",
            options,
            plans=base.PLANS,
        )
        run = rec.runs[0]
        hashes.append(run.chain.replay_hash if run.chain else None)
        frames.append(len(run.frames))
        errors.append(run.error)
    return {
        "play": name,
        "runs": 10,
        "distinct_hashes": len(set(hashes)),
        "hash": hashes[0],
        "frames": frames[0],
        "errors": [e for e in errors if e],
    }


def main() -> int:
    """Run one part and write its results."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("part", choices=["qa", "grade", "private", "replay10"])
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--starter", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--play", default="world.replay/car-and-ragdoll")
    a = ap.parse_args()
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    base.OUT = OUT
    t0 = time.monotonic()
    private = TASK / "tests/private/instances.json"
    try:
        if a.part == "qa":
            result = {
                "reference": base.run_qa(a.reference.resolve(), work, "reference"),
                "starter": base.run_qa(a.starter.resolve(), work, "starter"),
            }
            for name in ("reference", "starter"):
                found = work / f"{name}.json"
                if found.exists():
                    shutil.copy2(found, OUT / f"qa-{name}-found.json")
        elif a.part == "grade":
            m = manifest(work)
            result = {
                "reference_playtests": base.run_grade(a.reference.resolve(), work, m, "ref-playtests"),
                "starter_playtests": base.run_grade(
                    a.starter.resolve(), work, m, "starter-playtests", "--skip-selftest"
                ),
            }  # fmt: skip
        elif a.part == "private":
            result = {
                "reference_private": base.run_grade(
                    a.reference.resolve(),
                    work,
                    private,
                    "ref-private",
                    "--skip-selftest",
                ),
                "starter_private": base.run_grade(
                    a.starter.resolve(),
                    work,
                    private,
                    "starter-private",
                    "--skip-selftest",
                ),
            }
        else:
            slug = a.play.replace("/", ".")
            result = replay10(a.reference.resolve(), work / f"replay10-{slug}", a.play)
    finally:
        kill_all_live()
    result["_wall_s"] = round(time.monotonic() - t0, 1)
    suffix = "" if a.part != "replay10" else "-" + a.play.replace("/", ".")
    (OUT / f"{a.part}{suffix}.json").write_text(
        json.dumps(result, indent=1, default=str)
    )
    print(json.dumps(result, default=str)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
