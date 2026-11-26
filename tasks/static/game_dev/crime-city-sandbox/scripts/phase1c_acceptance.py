"""Phase 1c acceptance runs on macOS (author tool; never packaged).

Parts (run one per invocation, inside scripts/heavy.py so only one heavy job runs; every
game process also waits for QA_MEM_FLOOR, default 30, percent free memory):
  qa       qa run over every playtest, on the starter and on the reference: the text it
           prints (kept for the wording check) and its JSON findings
  grade    the real grader (self-test first) on the starter and on the reference, with the
           playtests as the instance set (manifest from --manifest), and on the reference
           with the Phase 1b private set (tests/private/instances.json)
  replay10 world.replay/two-paces on the reference, ten fresh processes: distinct hashes
Projects come from --starter and --reference (staged with scripts/stage_project.py).
Results go to experiment/phase1c/<part>.json.

Usage:
  python scripts/heavy.py -- python scripts/phase1c_acceptance.py PART --work DIR \\
      --starter DIR --reference DIR [--manifest FILE]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))
sys.path.insert(0, str(TASK / "tests"))

from qakit.play import parse_play, run_play
from qakit.prepare import prepare
from qakit.procs import Limits, kill_all_live, which_godot
from qakit.session import SessionOptions
from verifier.hostenv import memory_gate

LIB = TASK / "common/probe/build/darwin-arm64/libtelemetry.dylib"
GODOT_MAC = (
    Path.home()
    / "Documents/github/Abundant/game-spike/vendor/godot-4.7.2/Godot.app/Contents/MacOS/Godot"
)
PLANS = TASK / "common" / "design" / "plan"
OUT = TASK / "experiment" / "phase1c"
QA = TASK / "common" / "kit" / "qa"


def godot() -> str:
    """The Godot binary: $QA_GODOT, else the spike's vendor copy."""
    return which_godot(os.environ.get("QA_GODOT") or str(GODOT_MAC))


def run_qa(project: Path, work: Path, name: str) -> dict:
    """qa run over every playtest; keep its text and JSON."""
    out_json = work / f"{name}.json"
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(QA), "run", "--game", str(project), "--plans", str(PLANS),
         "--work", str(work / name), "--json", str(out_json), "--godot", godot(),
         "--telemetry", str(LIB)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    (OUT / f"qa-{name}.txt").write_text(proc.stdout)
    found = json.loads(out_json.read_text()) if out_json.exists() else []
    return {
        "exit_code": proc.returncode,
        "wall_s": round(time.monotonic() - t0, 1),
        "playtests": len(found),
        "held": [f["playtest"] for f in found if f["held"]],
        "not_held": {
            f["playtest"]: [e["id"] for e in f["expectations"] if e["ok"] is not True]
            for f in found
            if not f["held"]
        },
        "stopped": {f["playtest"]: f["stopped"] for f in found if f["stopped"]},
        "stderr_tail": proc.stderr[-600:],
    }


def run_grade(
    project: Path, work: Path, instances: Path, name: str, *extra: str
) -> dict:
    """The real grader on one project; the reward, gates and every instance's result."""
    out = work / name / "out"
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(TASK / "tests/verify.py"), "--project", str(project),
         "--out", str(out), "--work", str(work / name / "work"), "--godot", godot(),
         "--library", str(LIB), "--instances", str(instances), "--plans", str(PLANS), *extra],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    report = (
        json.loads((out / "report.json").read_text())
        if (out / "report.json").exists()
        else {}
    )
    reward = (
        (out / "reward.txt").read_text().strip()
        if (out / "reward.txt").exists()
        else None
    )
    return {
        "exit_code": proc.returncode,
        "reward": reward,
        "wall_s": round(time.monotonic() - t0, 1),
        "selftest": {k: report.get("selftest", {}).get(k) for k in ("ok", "wall_s", "problems")},
        "gates": {k: {"passed": v["passed"], "problems": v["problems"][:3], "measured": v.get("measured")}
                  for k, v in report.get("gates", {}).items()},
        "families": report.get("families"),
        "instances": [
            {"name": i["name"], "score": i["score"], "failure": i["failure"],
             "failed": [c["id"] for c in i.get("checks", []) if c.get("ok") is not True]}
            for i in report.get("instances", [])
        ],
        "stderr_tail": proc.stderr[-600:],
    }  # fmt: skip


def replay10(project: Path, work: Path) -> dict:
    """world.replay/two-paces ten times in fresh processes (one run each, no pace)."""
    gate = memory_gate()
    prep = prepare(
        project, work / "game", godot(), LIB, random.Random(), work / "prep",
        Limits(wall_s=600, memory_mb=4096), gate,
    )  # fmt: skip
    if not prep.ready:
        return {"problems": prep.problems}
    raw = json.loads(
        (TASK / "common/kit/playtests/world.replay.two-paces.json").read_text()
    )
    play = parse_play(dict(raw, runs=[{"pace_ms": 0}]))
    hashes, frames, errors = [], [], []
    for k in range(10):

        def options(_k: int, _n: int, folder: Path) -> SessionOptions:
            return SessionOptions(
                home=folder / "home", log_path=folder / "game.log",
                limits=Limits(cpu_s=600, memory_mb=1536, disk_mb=1024), before_start=gate,
            )  # fmt: skip

        rec = run_play(
            play, prep.game_dir, godot(), work / f"r{k:02d}", options, plans=PLANS
        )
        run = rec.runs[0]
        hashes.append(run.chain.replay_hash if run.chain else None)
        frames.append(len(run.frames))
        errors.append(run.error)
    return {
        "runs": 10,
        "distinct_hashes": len(set(hashes)),
        "hash": hashes[0],
        "frames": frames[0],
        "errors": [e for e in errors if e],
    }


def main() -> int:
    """Run one part and write its results."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("part", choices=["qa", "grade", "replay10"])
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--starter", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=None)
    a = ap.parse_args()
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    try:
        if a.part == "qa":
            result = {
                "reference": run_qa(a.reference.resolve(), work, "reference"),
                "starter": run_qa(a.starter.resolve(), work, "starter"),
            }
        elif a.part == "grade":
            manifest = a.manifest.resolve()
            result = {
                "reference_playtests": run_grade(a.reference.resolve(), work, manifest, "ref-playtests"),
                "starter_playtests": run_grade(
                    a.starter.resolve(), work, manifest, "starter-playtests", "--skip-selftest"
                ),
                "reference_private": run_grade(
                    a.reference.resolve(), work, TASK / "tests/private/instances.json",
                    "ref-private", "--skip-selftest",
                ),
            }  # fmt: skip
        else:
            result = replay10(a.reference.resolve(), work / "replay10")
    finally:
        kill_all_live()
    result["_wall_s"] = round(time.monotonic() - t0, 1)
    (OUT / f"{a.part}.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps(result, default=str)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
