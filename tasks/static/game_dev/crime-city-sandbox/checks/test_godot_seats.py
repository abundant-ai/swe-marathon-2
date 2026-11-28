"""Seats are read in world space and follow their vehicle tick by tick (CC_GODOT_CHECKS=1).

A play observes the seats of vehicles with {"observe": {"seats": {"ids": [...]}}}. Every
frame then lists, per vehicle id, the Marker3D nodes under that entity (any depth) in group
"seat", in tree order: the "index" metadata as written, the marker's world origin, and the
"door" and "wheel" metadata (points in the vehicle's space) in world space, null when
missing or not a point. An id that names no live entity is left out. The one-shot "body"
query gives an entity's node class, whether it is a physics body, its mass and its
collision layer and mask. A census with "kinds" lists only the entities of those kinds.

fixtures/seats/project has a frozen RigidBody3D vehicle that moves and turns every tick,
with seats at three depths (two under offset, turned nodes), a Marker3D outside the group
and metadata in each accepted and refused form; a Node3D vehicle that stays put; a
CharacterBody3D person without seats; and a vehicle.spawn command. The play
fixtures/seats/seats.json names the vehicles by role, by id and by a spawn answer, reads
them every tick (full census) and then every 4 ticks (census of vehicles, with metadata),
asks the body query of each entity, and ends with a census of no kinds. The Godot check
runs one heavy job at a time:

    CC_GODOT_CHECKS=1 python scripts/heavy.py -- python -m pytest checks/test_godot_seats.py

It needs the Godot binary ($QA_GODOT or the spike's vendor copy) and the built library
($CC_TELEMETRY_LIB, else common/probe/build/<platform>/). The other checks here (roles and
answers in observe settings, seats in the replay record) need neither.
"""

from __future__ import annotations

import copy
import itertools
import math
import os
import random
import sys
from pathlib import Path

import pytest
from qakit import expect, play, trace
from qakit.play import limits_of, load_play, run_play
from qakit.prepare import prepare
from qakit.procs import Limits, kill_all_live
from qakit.session import SessionOptions
from verifier.hostenv import memory_gate

TASK = Path(__file__).resolve().parent.parent
FIXTURE = TASK / "checks/fixtures/seats"
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

Mat = list[list[float]]
Xf = tuple[Mat, list[float]]  # basis (rows) and origin


def godot() -> str:
    """The Godot binary for these checks."""
    path = os.environ.get("QA_GODOT") or str(VENDOR)
    if not Path(path).is_file():
        pytest.skip("no Godot binary")
    return path


def rot(axis: str, deg: float) -> Mat:
    """The right-handed turn of deg degrees about +x, +y or +z (Godot's Basis(axis, a))."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return {
        "x": [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]],
        "y": [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]],
        "z": [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
    }[axis]


def mul(a: Mat, b: Mat) -> Mat:
    """The product of two 3x3 matrices."""
    return [
        [sum(a[r][i] * b[i][c] for i in range(3)) for c in range(3)] for r in range(3)
    ]


def apply(xf: Xf, p: tuple[float, float, float]) -> list[float]:
    """A point given in xf's space, in the space xf is given in."""
    m, o = xf
    return [sum(m[r][i] * p[i] for i in range(3)) + o[r] for r in range(3)]


def child(parent: Xf, local: Xf) -> Xf:
    """A node's global transform from its parent's global and its own local transform."""
    return mul(parent[0], local[0]), apply(parent, local[1])


# The fixture's geometry (fixtures/seats/project/main.gd). Entity 1 moves: after k ticks of
# the game it stands at ORIGIN + k * STEP, turned YAW + k * TURN degrees about +y, then ROLL
# degrees about +z.
ORIGIN, STEP = (12.0, 0.6, -7.0), (0.25, 0.01, -0.15)
YAW, TURN, ROLL = 35.0, 1.5, 6.0
REAR: Xf = (mul(rot("y", 30.0), rot("x", -8.0)), [0.05, 0.12, 0.85])
BENCH: Xf = (rot("y", -45.0), [0.5, 0.0, 0.1])
VAN: Xf = (mul(rot("y", -110.0), rot("z", 3.0)), [-6.0, 0.3, 4.0])
SPAWNED: Xf = (rot("y", 150.0), [4.0, 0.2, 9.0])  # the play's vehicle.spawn

# Each vehicle's seats in tree order: index as written, the node the marker hangs under
# ("" for the vehicle), its position there, and the door and wheel points in vehicle
# space (None where the metadata is missing or not a point).
CAR_SEATS = [
    (1, "", (0.37, 0.5, -0.25), (0.95, 0.55, -0.25), None),
    (0, "", (-0.37, 0.5, -0.25), (-0.95, 0.55, -0.25), (-0.37, 0.95, -0.7)),
    (2.0, "rear", (-0.4, 0.1, 0.2), None, None),
    (3, "bench", (0.1, 0.1, 0.0), (1, 0.55, 0.9), None),
]
VAN_SEATS = [
    (0, "", (-0.36, 0.48, -0.2), (-1.0, 0.6, 0.1), (-0.36, 0.97, -0.62)),
    (None, "", (0.36, 0.48, -0.2), None, None),
]
SPAWNED_SEATS = [(0, "", (-0.35, 0.45, 0.0), (-0.9, 0.5, 0.0), (-0.35, 0.9, -0.5))]

# The vehicles each run step of the play observes, in the order its frames list them: the
# role "vehicle" is entity 1, the spawn answer entity 4; 99 names no entity, and an id
# asked twice is listed once.
ASKED = {3: ["1", "2", "4", "3"], 5: ["2", "1"]}
# The census of each run step: every entity, then kinds "vehicle" and "boat" (no boat
# exists) with their "faction" metadata, then an empty list of kinds.
CENSUS = {
    3: ([1, 2, 3, 4], None),
    5: ([1, 2, 4], {"faction": "civilian"}),
    7: ([], None),
}


def body(cls: str, physics: bool, mass=None, layer=None, mask=None) -> dict:
    """A body query's answer for a live entity."""
    return {
        "ok": True,
        "class": cls,
        "physics": physics,
        "mass": mass,
        "layer": layer,
        "mask": mask,
    }


BODIES = {
    "body_car": body("RigidBody3D", True, 1350.0, 2, 23),
    "body_van": body("Node3D", False),
    "body_walker": body("CharacterBody3D", True, None, 4, 7),
    "body_spawned": body("Node3D", False),
    "body_none": {"ok": False},
}


def seat_rows(vehicle: Xf, table: list[tuple], under: dict[str, Xf]) -> list[dict]:
    """The seat rows a frame should list for a vehicle at `vehicle`, from its table."""
    nodes = dict(under, **{"": vehicle})
    return [
        {
            "index": index,
            "p": apply(nodes[node], p),
            "door": None if door is None else apply(vehicle, door),
            "wheel": None if wheel is None else apply(vehicle, wheel),
        }
        for index, node, p, door, wheel in table
    ]


def wanted(k: int) -> dict[str, list[dict]]:
    """Every observed entity's seat rows after k ticks of the game."""
    car = (
        mul(rot("y", YAW + TURN * k), rot("z", ROLL)),
        [ORIGIN[i] + STEP[i] * k for i in range(3)],
    )
    rear = child(car, REAR)
    return {
        "1": seat_rows(car, CAR_SEATS, {"rear": rear, "bench": child(rear, BENCH)}),
        "2": seat_rows(VAN, VAN_SEATS, {}),
        "3": [],
        "4": seat_rows(SPAWNED, SPAWNED_SEATS, {}),
    }


@pytest.mark.godot
def test_seats_follow_the_vehicle_in_world_space(tmp_path: Path) -> None:
    """Every seat, door and wheel point of every frame is where the game put it, in world
    space, while the vehicle moves and turns; missing or malformed metadata reads null; the
    Marker3D outside group "seat" and the id of no entity are left out; the body query
    reads each entity's class, physics, mass, layer and mask; and a census with kinds lists
    only those (its metadata as before)."""
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    exe = godot()
    assert LIB.is_file(), f"no library at {LIB} (common/probe/native/build.sh)"
    gate = memory_gate()
    seats_play = load_play(FIXTURE / "seats.json")

    def options(_k: int, _n: int, folder: Path) -> SessionOptions:
        return SessionOptions(
            home=folder / "home",
            log_path=folder / "game.log",
            limits=limits_of(seats_play),
            boot_s=float(seats_play.limits["boot_s"]),
            step_s=float(seats_play.limits["step_s"]),
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
            seats_play,
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
    spawn = run.frames[run.step_frame[0]]["dev"][0]["res"]
    assert spawn == {"ok": True, "id": 4}, spawn
    bodies = run.frames[run.step_frame[1]].get("q")
    assert bodies == BODIES, bodies

    compared, worst, off = 0, 0.0, []
    ticks: dict[int, list[int]] = {step: [] for step in ASKED}
    drivers: list[list[float]] = []
    censuses = 0
    for fr in run.frames:
        step = fr.get("_step")
        if step in CENSUS:
            ids, meta = CENSUS[step]
            census = fr.get("census")
            assert [e.get("id") for e in census] == ids, (fr["t"], census)
            assert all(e.get("m") == meta for e in census), (fr["t"], census)
            censuses += 1
        if step not in ASKED:
            continue
        seats = fr.get("seats")
        assert isinstance(seats, dict) and list(seats) == ASKED[step], (fr["t"], seats)
        k = expect.state_of(fr)["k"]
        ticks[step].append(k)
        want = wanted(k)
        for vid, rows in seats.items():
            assert isinstance(rows, list) and len(rows) == len(want[vid]), (vid, rows)
            for i, (got, row) in enumerate(zip(rows, want[vid])):
                where = f"tick {fr['t']} vehicle {vid} seat {i}"
                assert set(got) == {"index", "p", "door", "wheel"}, (where, got)
                # The index as written: an int reads as an int, a whole float as a float.
                assert got["index"] == row["index"], (where, got["index"])
                assert type(got["index"]) is type(row["index"]), (where, got["index"])
                for key in ("p", "door", "wheel"):
                    if row[key] is None:
                        assert got[key] is None, (where, key, got[key])
                        continue
                    d = math.dist(got[key], row[key])
                    compared, worst = compared + 1, max(worst, d)
                    if d > TOL_M:
                        off.append((where, key, d))
        if step == 3:
            drivers.append(seats["1"][1]["p"])
    assert not off, f"seat points away from where the game put them (m): {off[:8]}"
    # Read every tick, then every 4 ticks, and the vehicle moved between reads.
    assert ticks[3] == list(range(ticks[3][0], ticks[3][0] + 12)), ticks
    assert ticks[5] == list(range(ticks[5][0], ticks[5][0] + 24, 4)), ticks
    assert all(math.dist(a, b) > 0.2 for a, b in itertools.pairwise(drivers)), drivers
    assert censuses == 12 + 6 + 2, censuses
    frames = sum(map(len, ticks.values()))
    print(f"seats: {compared} points in {frames} frames, worst {worst:.2e} m")


def test_roles_and_answers_name_the_observed_entities(tmp_path: Path) -> None:
    """Roles in bone and seat ids become the first entity of that kind in the latest census,
    ids that are not numbers are left out, and an observe step fills in earlier answers."""
    fr = {
        "census": [
            {"id": 4, "k": "npc"},
            {"id": 9, "k": "player"},
            {"id": 12, "k": "vehicle"},
            {"id": 13, "k": "vehicle"},
        ]
    }
    unfilled = {"$answer": [0, "id"]}
    obs = {
        "census": True,
        "bones": {"ids": ["player", 4], "names": ["Hips"]},
        "seats": {"ids": ["vehicle", 13, None, 7.0, True, "boat", unfilled]},
    }
    got = play.resolve_observe(obs, fr)
    assert got["bones"] == {"ids": [9, 4], "names": ["Hips"]}
    assert got["seats"] == {"ids": [12, 13, 7.0]}
    assert obs["seats"]["ids"][0] == "vehicle"  # the settings as written are left alone
    assert play.resolve_observe({"seats": {"ids": ["vehicle"]}}, None)["seats"] == {
        "ids": []
    }

    p = play.parse_play(
        {
            "format": "qa-play/1",
            "name": "seats.read/answers",
            "template": "seats.read",
            "role": "solo",
            "steps": [
                {"dev": [["vehicle.spawn", {}]]},
                {"observe": {"seats": {"ids": [unfilled, "vehicle"]}}},
            ],
        }
    )
    answer = {"cmd": "vehicle.spawn", "res": {"ok": True, "id": 21}, "t": 5}
    rec = play.RunRecord(
        index=0,
        pace_ms=0,
        frames=[
            {"t": 5, "_step": -1, "_proc": 0},
            {"t": 6, "_step": 0, "_proc": 0, "dev": [answer]},
        ],
    )
    runner = play._LockstepRun(p, None, None, rec, tmp_path)
    runner.do(1, "observe", p.steps[1]["observe"])
    assert runner.obs == {"census": True, "every": 6, "seats": {"ids": [21, "vehicle"]}}
    assert play.resolve_observe(runner.obs, fr)["seats"] == {"ids": [21, 12]}


def test_seat_points_are_part_of_the_replay_record() -> None:
    """Seat points are hashed with the census and bones, so runs whose seats differ do not
    replay equal; a frame without seats hashes as before."""
    a = {
        "t": 7,
        "census": [{"id": 1, "k": "vehicle", "p": [0.0, 0.0, 0.0]}],
        "seats": {
            "1": [{"index": 0, "p": [1.0, 0.5, 0.0], "door": None, "wheel": None}]
        },
        "dev": [],
    }
    b = copy.deepcopy(a)
    b["seats"]["1"][0]["p"][0] = 1.25
    assert trace.physical(a)["seats"] == a["seats"]
    assert trace.chain([a]).replay_hash != trace.chain([b]).replay_hash
    div = trace.first_divergence([a], [b])
    assert div is not None and div.detail == "seat points", div
    plain = {"t": 7, "census": a["census"], "dev": []}
    assert trace.physical(plain) == {"t": 7, "census": a["census"]}
