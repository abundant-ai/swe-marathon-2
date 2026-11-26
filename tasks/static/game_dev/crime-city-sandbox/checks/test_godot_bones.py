"""Bones are read as the game shows them, after its skeleton modifiers (CC_GODOT_CHECKS=1).

The engine applies the pose of a SkeletonModifier3D (IK, look-at, a ragdoll, a script's
_process_modification_with_delta) only while it updates the skeleton, then puts the
unmodified pose back, so a read at the start of the next tick misses it unless the
telemetry node keeps the pose of each update. fixtures/bone_modifiers/project has two
rigged people whose modifiers turn the left arm to a new angle at every update and move the
head (the player's modifier in the idle step, the other's in the physics step), while the
game turns the player's right arm directly every tick; its state report gives the angles
used last. The play fixtures/bone_modifiers/bones.json reads those bones tick by tick and
asks two line-of-sight questions, which start at the Head bone. Run it one heavy job at a
time:

    CC_GODOT_CHECKS=1 python scripts/heavy.py -- python -m pytest checks/test_godot_bones.py

Needs the Godot binary ($QA_GODOT or the spike's vendor copy) and the built library
($CC_TELEMETRY_LIB, else common/probe/build/<platform>/).
"""

from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

import pytest
from qakit import expect
from qakit.play import limits_of, load_play, run_play
from qakit.prepare import prepare
from qakit.procs import Limits, kill_all_live
from qakit.session import SessionOptions
from verifier.hostenv import memory_gate

TASK = Path(__file__).resolve().parent.parent
FIXTURE = TASK / "checks/fixtures/bone_modifiers"
BUILT = (
    TASK
    / "common/probe/build"
    / ("darwin-arm64" if sys.platform == "darwin" else "linux-x86_64")
)
LIB = Path(
    os.environ.get("CC_TELEMETRY_LIB")
    or BUILT / ("libtelemetry.dylib" if sys.platform == "darwin" else "libtelemetry.so")
)
VENDOR = (
    Path.home()
    / "Documents/github/Abundant/game-spike/vendor/godot-4.7.2/Godot.app/Contents/MacOS/Godot"
)
TOL_M = 1e-4
pytestmark = pytest.mark.godot

# Each person of the fixture: where its body stands, its turn about y (degrees), the state
# field with its modifier's last angle, and how far the modifier moves its head along z.
PEOPLE = {
    1: {"at": (3.0, 0.0, -2.0), "yaw": 90.0, "deg": "player_deg", "head_dz": 0.3},
    2: {"at": (-4.0, 0.0, 5.0), "yaw": 0.0, "deg": "npc_deg", "head_dz": -0.25},
}


def godot() -> str:
    """The Godot binary for these checks."""
    path = os.environ.get("QA_GODOT") or str(VENDOR)
    if not Path(path).is_file():
        pytest.skip("no Godot binary")
    return path


def to_world(eid: int, p: tuple[float, float, float]) -> list[float]:
    """A skeleton-space point of person eid in world space (the skeleton sits at the body)."""
    (ax, ay, az), yaw = PEOPLE[eid]["at"], math.radians(PEOPLE[eid]["yaw"])
    c, s = math.cos(yaw), math.sin(yaw)
    x, y, z = p
    return [c * x + s * z + ax, y + ay, -s * x + c * z + az]


def arm(side: int, deg: float, length: float) -> tuple[float, float, float]:
    """The point `length` m along an upper arm (side 1 left, -1 right) turned deg about +z."""
    a = math.radians(deg)
    return (side * (0.2 + length * math.cos(a)), 1.4 + side * length * math.sin(a), 0.0)


def placed(frame: dict, eid: int) -> dict[str, list[float]]:
    """Where the game put each observed bone of person eid, by the frame's state report."""
    st = expect.state_of(frame)
    left = float(st[PEOPLE[eid]["deg"]])
    right = float(st["arm_deg"]) if eid == 1 else 0.0
    local = {
        "LeftLowerArm": arm(1, left, 0.3),
        "LeftHand": arm(1, left, 0.55),
        "Head": (0.0, 1.65, PEOPLE[eid]["head_dz"]),
        "RightHand": arm(-1, right, 0.55),
        "LeftToes": (0.1, 0.0, -0.12),
    }
    return {name: to_world(eid, p) for name, p in local.items()}


def test_bones_are_read_after_the_skeleton_modifiers(tmp_path: Path) -> None:
    """Every bone read and line-of-sight start is where the game put the bone in its latest
    update: the bones a modifier moves (in the idle or the physics step) as it left them, the
    others (a leg at rest, an arm the game turns itself every tick) as before."""
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    exe = godot()
    assert LIB.is_file(), f"no library at {LIB} (common/probe/native/build.sh)"
    gate = memory_gate()
    play = load_play(FIXTURE / "bones.json")

    def options(_k: int, _n: int, folder: Path) -> SessionOptions:
        return SessionOptions(
            home=folder / "home",
            log_path=folder / "game.log",
            limits=limits_of(play),
            boot_s=float(play.limits["boot_s"]),
            step_s=float(play.limits["step_s"]),
            before_start=gate,
        )

    try:
        prep = prepare(
            FIXTURE / "project",
            tmp_path / "game",
            exe,
            LIB,
            random.Random(),
            tmp_path / "prep",
            Limits(wall_s=300),
            gate,
        )
        assert prep.ready, prep.problems
        rec = run_play(
            play, prep.game_dir, exe, tmp_path / "play", options, write_traces=False
        )
    finally:
        kill_all_live()
    run = rec.runs[0]
    assert run.error is None, run.error
    frames = [fr for fr in run.frames if fr.get("bones")]
    assert len(frames) >= 15, len(frames)
    worst: dict[str, float] = {}
    for fr in frames:
        for eid in PEOPLE:
            want = placed(fr, eid)
            # The fixture's modifier keeps the hand far from where it would be without it.
            assert math.dist(want["LeftHand"], to_world(eid, arm(1, 0.0, 0.55))) > 0.1
            got = fr["bones"][str(eid)]
            for name, p in want.items():
                key = f"{eid}:{name}"
                worst[key] = max(worst.get(key, 0.0), math.dist(got[name], p))
    off = {k: v for k, v in worst.items() if v > TOL_M}
    assert not off, f"bones read away from where the game put them (m): {off}"
    answers = {k: a for fr in run.frames for k, a in (fr.get("q") or {}).items()}
    for qid, eid in (("npc_eyes", 2), ("player_eyes", 1)):
        head = to_world(eid, (0.0, 1.65, PEOPLE[eid]["head_dz"]))
        got = answers.get(qid) or {}
        assert got.get("ok") and math.dist(got["from"], head) <= TOL_M, (qid, got, head)
