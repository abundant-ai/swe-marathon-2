"""Prepare a game project and run plays on it, printing what each frame carried (author tool).

Never packaged. For debugging a game against the QA kit: one preparation (copy, telemetry,
import), then each play in turn, then a frame-by-frame summary (DevConsole answers, events,
entity counts, chosen state values), every expectation's outcome and the tail of the game's
log. Run it inside scripts/heavy.py (it starts Godot; every process waits for free memory):

  python scripts/heavy.py -- python scripts/play_once.py --project DIR --work DIR PLAY ...
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))
sys.path.insert(0, str(TASK / "tests"))

from qakit import expect
from qakit.play import load_play, run_play
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


def summary(frame: dict, paths: list[str]) -> str:
    """One line for a frame: tick, step, answers, events, census counts, state values."""
    parts = [f"t={frame.get('t')} step={frame.get('_step')}"]
    for d in frame.get("dev") or []:
        res = json.dumps(d.get("res"))[:160]
        parts.append(
            f"dev {d.get('cmd')} -> {res}{' ' + d['unanswered'] if 'unanswered' in d else ''}"
        )
    for e in frame.get("events") or []:
        parts.append(f"event {e.get('n')} {json.dumps(e.get('d'))[:120]}")
    if "census" in frame:
        kinds: dict[str, int] = {}
        for e in frame["census"]:
            kinds[e.get("k")] = kinds.get(e.get("k"), 0) + 1
        parts.append(f"census {kinds}")
    st = expect.state_of(frame)
    for p in paths:
        parts.append(f"{p}={json.dumps(expect.dig(st, p))}")
    return " | ".join(parts)


def main() -> int:
    """Prepare once, run each play, print the summaries."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--plans", type=Path, default=PLANS)
    ap.add_argument("--godot", default=None)
    ap.add_argument("--state", default="clock,weather,player.money", help="state paths")
    ap.add_argument("--all-frames", action="store_true")
    ap.add_argument("plays", nargs="+", type=Path)
    a = ap.parse_args()
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    godot = which_godot(a.godot or str(GODOT_MAC))
    work = a.work.resolve()
    gate = memory_gate()
    try:
        prep = prepare(
            a.project.resolve(),
            work / "game",
            godot,
            LIB,
            random.Random(),
            work / "prep",
            Limits(wall_s=600, memory_mb=4096),
            gate,
        )
        print(
            f"prepared in {prep.import_s} s, cache {prep.cache_mb} MB, problems {prep.problems}"
        )
        if not prep.ready:
            return 2
        for path in a.plays:
            play = load_play(path)
            folder = work / "plays" / play.name.replace("/", ".")

            def options(_k: int, _n: int, run_folder: Path, _p=play) -> SessionOptions:
                return SessionOptions(
                    home=run_folder / "home",
                    log_path=run_folder / "game.log",
                    limits=Limits(cpu_s=600, memory_mb=1536, disk_mb=1024),
                    boot_s=float(_p.limits.get("boot_s", 60)),
                    step_s=float(_p.limits.get("step_s", 30)),
                    before_start=gate,
                )

            rec = run_play(
                play, prep.game_dir, godot, folder, options, plans=a.plans.resolve()
            )
            print(f"== {play.name}: {rec.wall_s} s")
            paths = [p for p in a.state.split(",") if p]
            for run in rec.runs:
                print(f"-- run {run.index} error={run.error} boot_s={run.boot_s}")
                for fr in run.frames:
                    if (
                        a.all_frames
                        or fr.get("dev")
                        or fr.get("events")
                        or fr.get("_step") == -1
                    ):
                        print("  " + summary(fr, paths))
                log = folder / f"run{run.index}" / "game.log"
                if log.exists():
                    lines = [
                        ln
                        for ln in log.read_text(errors="replace").splitlines()
                        if ln.strip()
                    ]
                    bad = [
                        ln
                        for ln in lines
                        if "ERROR" in ln or "SCRIPT" in ln or "WARNING" in ln
                    ]
                    print(f"  log: {len(lines)} lines, {len(bad)} errors or warnings")
                    for ln in bad[:25]:
                        print("    " + ln[:220])
            for o in expect.check_play(rec) + expect.standing(rec):
                print(
                    f"  [{'held' if o.ok else 'NOT HELD'}] {o.id} ({o.check}) {o.note} {json.dumps(o.measured)[:300]}"
                )
    finally:
        kill_all_live()
    return 0


if __name__ == "__main__":
    sys.exit(main())
