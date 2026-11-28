"""Collision shapes are read in world space and follow their body tick by tick
(CC_GODOT_CHECKS=1).

A census with "shapes": [kinds] gives the entities of those kinds a list "sh": for each
CollisionShape3D that is a direct child of the entity and not disabled, the box of its shape's
own mesh placed by the shape node's transform, as its centre and its three half-axis vectors in
world space (12 numbers). Shapes of other bodies under the entity and disabled shapes are left
out; an entity without shapes lists none; entities of other kinds carry no "sh".

fixtures/shapes/project has a frozen RigidBody3D vehicle that moves and turns every tick with
two box shapes (one offset and turned), a disabled shape and a child body with a shape of its
own; a CharacterBody3D person with a capsule; and a Node3D vehicle without shapes. The play
fixtures/shapes/shapes.json reads vehicles' shapes every tick, then people's (a census of
people only) every 2 ticks, then a census without shapes. The Godot check runs one heavy job
at a time:

    CC_GODOT_CHECKS=1 python scripts/heavy.py -- python -m pytest checks/test_godot_shapes.py
"""

from __future__ import annotations

import math
import os
import random
from pathlib import Path

import pytest
from qakit import expect
from qakit.play import limits_of, load_play, run_play
from qakit.prepare import prepare
from qakit.procs import Limits, kill_all_live
from qakit.session import SessionOptions
from test_godot_seats import LIB, apply, godot, mul, rot
from verifier.hostenv import memory_gate

TASK = Path(__file__).resolve().parent.parent
FIXTURE = TASK / "checks/fixtures/shapes"
TOL_M = 1e-4
CAPSULE_TOL_M = 0.01

# The fixture's geometry (fixtures/shapes/project/main.gd).
ORIGIN, STEP = (5.0, 0.2, -3.0), (0.2, 0.0, -0.1)
YAW, TURN, ROLL = 20.0, 2.0, 4.0
# Each box shape: its node's turn and position in the car's space, and its size.
BOXES = [
    (rot("y", 0.0), (0.0, 0.7, 0.1), (1.8, 1.4, 4.4)),
    (rot("y", 10.0), (0.0, 0.4, -2.3), (1.0, 0.5, 0.6)),
]
WALKER = ((-2.0, 0.85, 1.0), (0.3, 0.85, 0.3))  # the capsule's centre and half extents


def wanted_boxes(k: int) -> list[list[float]]:
    """The car's two boxes after k ticks: centre and half-axis vectors in world space."""
    car_m = mul(rot("y", YAW + TURN * k), rot("z", ROLL))
    car_o = [ORIGIN[i] + STEP[i] * k for i in range(3)]
    out = []
    for turn, at, size in BOXES:
        m = mul(car_m, turn)
        centre = apply((car_m, car_o), at)
        axes = [[m[r][c] * size[c] / 2 for r in range(3)] for c in range(3)]
        out.append(centre + axes[0] + axes[1] + axes[2])
    return out


@pytest.mark.godot
def test_shapes_follow_the_body_in_world_space(tmp_path: Path) -> None:
    """Every box of every frame is where the game put it, in world space, while the body
    moves and turns; the disabled shape and the child body's shape are left out; the vehicle
    without shapes lists none; a person's capsule reads as its bounding box; and a census
    without "shapes" carries no "sh"."""
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    exe = godot()
    assert LIB.is_file(), f"no library at {LIB} (common/probe/native/build.sh)"
    gate = memory_gate()
    shapes_play = load_play(FIXTURE / "shapes.json")

    def options(_k: int, _n: int, folder: Path) -> SessionOptions:
        return SessionOptions(
            home=folder / "home",
            log_path=folder / "game.log",
            limits=limits_of(shapes_play),
            boot_s=float(shapes_play.limits["boot_s"]),
            step_s=float(shapes_play.limits["step_s"]),
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
            shapes_play,
            prep.game_dir,
            exe,
            tmp_path / "play",
            options,
            write_traces=False,
        )
    finally:
        kill_all_live()
    run = rec.runs[0]
    assert run.error is None, run.error
    compared, worst, cars, walkers, plain = 0, 0.0, 0, 0, 0
    for fr in run.frames:
        step = fr.get("_step")
        census = {e["id"]: e for e in fr.get("census") or []}
        k = expect.state_of(fr).get("k")
        if step == 1:
            car, sign = census[1], census[3]
            assert sign.get("sh") == [], sign
            plain += 1
            assert "sh" not in census[2], census[2]
            got = car.get("sh")
            want = wanted_boxes(k)
            assert isinstance(got, list) and len(got) == len(want), (fr["t"], got)
            for g, w in zip(got, want, strict=True):
                assert len(g) == 12, g
                for i in range(0, 12, 3):
                    d = math.dist(g[i : i + 3], w[i : i + 3])
                    compared, worst = compared + 1, max(worst, d)
                    assert d <= TOL_M, (fr["t"], i, g, w)
            cars += 1
        elif step == 3:
            assert list(census) == [2], census
            got = census[2].get("sh")
            assert isinstance(got, list) and len(got) == 1, got
            centre, half = WALKER
            assert math.dist(got[0][0:3], centre) <= CAPSULE_TOL_M, got
            lengths = [math.dist(got[0][i : i + 3], (0, 0, 0)) for i in (3, 6, 9)]
            assert all(
                abs(a - b) <= CAPSULE_TOL_M for a, b in zip(lengths, half, strict=True)
            ), lengths
            walkers += 1
        elif step == 5:
            assert all("sh" not in e for e in census.values()), census
    assert cars == 10 and walkers == 2 and plain == 10, (cars, walkers, plain)
    print(f"shapes: {compared} points in {cars} frames, worst {worst:.2e} m")
