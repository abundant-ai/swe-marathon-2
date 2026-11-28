"""The kit's vehicle, getting in and out, ragdoll and damage expectations over hand-made
frames, the wait_for entity and cruise steps, and the registry check with a census limited to
some kinds (no Godot). Each expectation holds on a well-behaved game and fails on the broken
one next to it."""

from __future__ import annotations

import copy
import math

from qakit import expect, play

BASE = {"format": "qa-play/1", "name": "x/y", "template": "x", "role": "solo"}
KMH = 1 / 3.6
VID = 7  # the vehicle's id, as the first dev command answered
SPAWN = {"_step": 0, "dev": [{"cmd": "vehicle.spawn", "res": {"ok": True, "id": VID}}]}
IDF = {"id_from": {"step": 0, "index": 0}}
G = 9.81


def record(frames: list[dict], marks: dict) -> play.PlayRecord:
    """A one-run PlayRecord over the given frames (the first carries the spawn answer)."""
    p = play.parse_play(dict(BASE, steps=[{"run": 1}]))
    first = dict(frames[0], **SPAWN) if "dev" not in frames[0] else frames[0]
    r = play.RunRecord(index=0, pace_ms=0, frames=copy.deepcopy([first, *frames[1:]]))
    r.marks = dict(marks)
    return play.PlayRecord(p, [r], 0.0)


def framed(frames: list[dict]) -> play.PlayRecord:
    return record(frames, {"a": 0, "b": len(frames) - 1})


def outcome(rec: play.PlayRecord, check: str, args: dict) -> expect.Outcome:
    raw = dict(rec.play.raw, expect=[{"id": "e", "check": check, "args": args}])
    return expect.check_play(play.PlayRecord(play.parse_play(raw), rec.runs, 0.0))[0]


def car(t: int, p: list[float], **meta: object) -> dict:
    row = {"id": VID, "k": "vehicle", "a": "sedan", "f": "none", "p": p}
    if meta:
        row["m"] = dict(meta)
    return {"t": t, "census": [row]}


def straight(speeds: list[float], t0: int = 0) -> list[dict]:
    """Frames of a vehicle driving north (-z) at the given speed each tick."""
    out, z = [], 0.0
    for k, v in enumerate(speeds):
        z -= v / 60
        out.append(car(t0 + k, [0.0, 0.0, z]))
    return out


def accelerating(a: float, ticks: int = 900) -> list[float]:
    return [min(60.0, a * k / 60) for k in range(ticks)]


# ---------------------------------------------------------------- handling
def test_accel_time_to_60() -> None:
    args = {"from": "a", "to": "b", **IDF, "kmh": 60.0, "min_s": 4.5, "max_s": 6.5}
    good = outcome(framed(straight(accelerating(3.0))), "accel", args)
    assert good.ok is True and abs(good.measured["seconds"] - 60 * KMH / 3.0) < 0.05
    slow = outcome(framed(straight(accelerating(1.5))), "accel", args)
    assert slow.ok is False and slow.measured["seconds"] > 10


def stop(decel: float, v0: float = 61 * KMH) -> list[float]:
    out, v = [v0] * 10, v0
    while v > 0:
        v = max(0.0, v - decel / 60)
        out.append(v)
    return out + [0.0] * 20


def test_brake_distance_and_wet_ratio() -> None:
    args = {"from": "a", "to": "b", **IDF, "kmh": 60.0, "min_m": 13.5, "max_m": 19.5}
    good = outcome(framed(straight(stop(8.42))), "brake", args)
    assert good.ok is True and abs(good.measured["metres"] - 16.5) < 0.6
    weak = outcome(framed(straight(stop(4.0))), "brake", args)
    assert weak.ok is False and weak.measured["metres"] > 30
    dry, wet = straight(stop(8.42)), straight(stop(6.57), t0=1000)
    marks = {"a": 0, "b": len(dry) - 1, "c": len(dry), "d": len(dry) + len(wet) - 1}
    rec = record(dry + wet, marks)
    ratio = {"from": "c", "to": "d", **IDF, "kmh": 60.0, "min_ratio": 1.15, "max_ratio": 1.6,
             "dry": {"from": "a", "to": "b", **IDF}}  # fmt: skip
    o = outcome(rec, "brake", ratio)
    assert o.ok is True and 1.2 < o.measured["ratio"] < 1.35
    same = record(dry + straight(stop(8.42), t0=1000), marks)
    assert outcome(same, "brake", ratio).ok is False


def circle(radius: float, v: float, ticks: int = 900) -> list[dict]:
    w = v / radius
    return [
        car(k, [radius * math.cos(w * k / 60), 0.0, radius * math.sin(w * k / 60)])
        for k in range(ticks)
    ]


def test_turning_circle() -> None:
    args = {"from": "a", "to": "b", **IDF, "kmh": 8.0, "kmh_tol": 1.5,
            "min_turn_deg": 180.0, "min_m": 10.0, "max_m": 13.0}  # fmt: skip
    good = outcome(framed(circle(5.75, 8 * KMH)), "turn_circle", args)
    assert good.ok is True and abs(good.measured["diameter_m"] - 11.5) < 0.05
    wide = outcome(framed(circle(9.0, 8 * KMH)), "turn_circle", args)
    assert wide.ok is False and wide.measured["diameter_m"] > 17
    fast = outcome(framed(circle(5.75, 20 * KMH)), "turn_circle", args)
    assert fast.ok is None and "km/h" in fast.note


def test_handbrake_deceleration() -> None:
    args = {"from": "a", "to": "b", **IDF, "min_kmh": 35.0, "over_s": 1.0,
            "min_mps2": 2.0, "max_mps2": 6.0}  # fmt: skip
    good = outcome(framed(straight(stop(3.4, 41 * KMH))), "decel", args)
    assert good.ok is True and abs(good.measured["mps2"] - 3.4) < 0.1
    weak = outcome(framed(straight(stop(1.0, 41 * KMH))), "decel", args)
    assert weak.ok is False


def test_body_query() -> None:
    def rec(answer: dict) -> play.PlayRecord:
        r = record([car(0, [0, 0, 0]), dict(car(1, [0, 0, 0]), q={"body": answer})], {})
        r.runs[0].step_frame[1] = 1
        return r

    good = {
        "ok": True,
        "class": "RigidBody3D",
        "physics": True,
        "mass": 1350.0,
        "layer": 2,
    }
    args = {"step": 1, "query": "body", "layer": 2, "mass_kg": 1350.0, "tol": 0.1}
    assert outcome(rec(good), "body", args).ok is True
    assert outcome(rec(dict(good, mass=900.0)), "body", args).ok is False
    assert outcome(rec(dict(good, layer=1)), "body", args).ok is False
    assert (
        outcome(rec(dict(good, physics=False, cls="Node3D")), "body", args).ok is False
    )


# ---------------------------------------------------------------- getting in and out
SEAT = [-0.6, 1.15, 0.0]
DOOR = [-1.6, 0.0, 0.0]
WHEEL = [-0.6, 1.45, -0.4]


def seats(*, wheel: bool = True, n: int = 4) -> list[dict]:
    rows = []
    for i in range(n):
        side = -1 if i % 2 == 0 else 1
        z = 0.0 if i < 2 else 0.8
        rows.append({"index": i, "p": [0.6 * side, 1.15, z], "door": [1.6 * side, 0.0, z],
                     "wheel": WHEEL if i == 0 and wheel else None})  # fmt: skip
    return rows


def scene(t: int, player: list[float], vehicle: object, seat: object, hips: list[float],
          hands: list[float] | None = None, rows: list[dict] | None = None) -> dict:  # fmt: skip
    hands = hands or [hips[0], hips[1] + 0.4, hips[2] - 0.3]
    return {
        "t": t,
        "census": [
            {"id": 1, "k": "player", "a": "lead_1", "f": "player", "p": player},
            {
                "id": VID,
                "k": "vehicle",
                "a": "sedan",
                "f": "none",
                "p": [0.0, 0.0, 0.0],
            },
        ],
        "bones": {"1": {"Hips": hips, "LeftHand": hands, "RightHand": hands}},
        "seats": {str(VID): rows if rows is not None else seats()},
        "state": {
            "ok": True,
            "player": {"vehicle": vehicle, "seat": seat, "limp": False},
        },
    }


def entering(seat_at: int, start: list[float]) -> list[dict]:
    """The player walks from start to the left front door, then sits at tick seat_at."""
    out = []
    for t in range(seat_at + 60):
        if t < seat_at - 60:
            k = t / max(1, seat_at - 60)
            p = [
                start[0] + (DOOR[0] - start[0]) * k,
                0.0,
                start[2] + (DOOR[2] - start[2]) * k,
            ]
            out.append(scene(t, p, None, None, [p[0], 0.9, p[2]]))
        elif t < seat_at:
            out.append(scene(t, DOOR, None, None, [DOOR[0], 0.9, DOOR[2]]))
        else:
            out.append(
                scene(t, [-0.6, 0.6, 0.0], VID, 0, SEAT, [WHEEL[0], WHEEL[1], WHEEL[2]])
            )
    return out


def test_get_in_seated_and_out() -> None:
    args = {"from": "a", "to": "b", **IDF, "near_m": 3.0, "door_m": 1.0, "min_s": 1.0,
            "max_s": 4.0}  # fmt: skip
    good = outcome(framed(entering(120, [-3.0, 0.0, -0.3])), "get_in", args)
    assert (
        good.ok is True
        and good.measured["seat"] == 0
        and good.measured["seconds"] == 2.0
    )
    snap = outcome(framed(entering(10, [-3.0, 0.0, -0.3])), "get_in", args)
    assert snap.ok is False and "seated 0.17 s" in snap.note
    far = outcome(framed(entering(120, [-6.0, 0.0, -0.3])), "get_in", args)
    assert far.ok is None and "nearest door" in far.note
    sit = {"from": "a", "to": "b", **IDF, "hips_m": 0.35, "hands_m": 0.30}
    assert outcome(framed(entering(120, [-3.0, 0.0, -0.3])), "seated", sit).ok is True
    slouch = entering(120, [-3.0, 0.0, -0.3])
    slouch[-1]["bones"]["1"]["Hips"] = [-0.6, 0.6, 0.0]
    assert outcome(framed(slouch), "seated", sit).ok is False
    loose = entering(120, [-3.0, 0.0, -0.3])
    loose[-1]["bones"]["1"]["LeftHand"] = [-0.6, 0.9, 0.3]
    bad = outcome(framed(loose), "seated", sit)
    assert bad.ok is False and "LeftHand" in bad.note


def leaving(out_at: int, end: list[float]) -> list[dict]:
    out = [scene(t, [-0.6, 0.6, 0.0], VID, 0, SEAT) for t in range(out_at)]
    out += [
        scene(out_at + k, end, None, None, [end[0], 0.9, end[2]]) for k in range(30)
    ]
    return out


def test_get_out() -> None:
    args = {"from": "a", "to": "b", **IDF, "min_s": 1.0, "max_s": 3.0, "door_m": 2.5}
    good = outcome(framed(leaving(120, [-1.7, 0.0, 0.1])), "get_out", args)
    assert good.ok is True and good.measured["seconds"] == 2.0
    assert outcome(framed(leaving(12, [-1.7, 0.0, 0.1])), "get_out", args).ok is False
    assert outcome(framed(leaving(120, [-6.0, 0.0, 0.1])), "get_out", args).ok is False


def test_seats_read() -> None:
    def rec(rows: list[dict]) -> play.PlayRecord:
        return record([scene(0, DOOR, None, None, [0, 0.9, 0], rows=rows)], {"m": 0})

    args = {"mark": "m", **IDF, "count": 4}
    assert outcome(rec(seats()), "seats", args).ok is True
    assert outcome(rec(seats(wheel=False)), "seats", args).ok is False
    twice = seats()
    twice[3]["index"] = 2
    assert outcome(rec(twice), "seats", args).ok is False
    assert outcome(rec(seats(n=2)), "seats", args).ok is False


def driving(cam_back: float) -> list[dict]:
    out = []
    for t in range(60):
        f = scene(t, [-0.6, 0.6, 0.0], VID, 0, SEAT)
        cam = [0.0, 1.6 + cam_back * 0.2, cam_back]
        back = [cam[k] - [0.0, 1.6, 0.0][k] for k in range(3)]
        n = math.sqrt(sum(c * c for c in back))
        f["camera"] = {"p": cam, "bz": [c / n for c in back], "fov": 75.0}
        out.append(f)
    return out


def test_camera_while_driving() -> None:
    args = {"from": "a", "to": "b", **IDF, "min_m": 5.0, "max_m": 10.0, "middle": 0.4,
            "aspect": 16 / 9}  # fmt: skip
    assert outcome(framed(driving(7.0)), "camera_vehicle", args).ok is True
    far = outcome(framed(driving(12.0)), "camera_vehicle", args)
    assert far.ok is False and "from the vehicle" in far.note


# ---------------------------------------------------------------- ragdoll
Y0 = 0.15
STAND = 0.9


def person(t: int, pos: list[float], hips: list[float], limp: bool, low: float | None = None,
           state_limp: object = "same") -> dict:  # fmt: skip
    low = hips[1] - 0.2 if low is None else low
    return {
        "t": t,
        "census": [
            {
                "id": 1,
                "k": "player",
                "a": "lead_1",
                "f": "player",
                "p": pos,
                "m": {"limp": limp},
            }
        ],
        "bones": {"1": {"Hips": hips, "LeftToes": [hips[0], low, hips[2]]}},
        "state": {
            "ok": True,
            "player": {"limp": limp if state_limp == "same" else state_limp},
        },
    }


def fall(height: float, limp_after: int = 0, limp_ticks: int = 120, get_up: int = 60,
         below: float = 0.0, teleport: bool = False, free: bool = False) -> list[dict]:  # fmt: skip
    """Standing on a tower, falling height m, landing (limp limp_after ticks later for
    limp_ticks), then getting up over get_up ticks; free: limp from the first falling tick."""
    out, t, y, v = [], 0, Y0 + height, 0.0
    for _ in range(10):
        out.append(person(t, [0, y, 0], [0, y + STAND, 0], False))
        t += 1
    land = None
    while y > Y0:
        v += G / 60
        y = max(Y0, y - v / 60)
        limp = free and t >= 12
        hips_y = y + (0.3 if limp else STAND)
        out.append(person(t, [0, y, 0], [0, hips_y, 0], limp, low=hips_y - 0.3))
        t += 1
    land = t
    for k in range(limp_after + limp_ticks):
        limp = free or k >= limp_after
        hx = 5.0 if teleport and k == limp_after + 5 else 0.0
        out.append(
            person(t, [hx, Y0, 0], [hx, Y0 + 0.15, 0], limp, low=Y0 + 0.02 - below)
        )
        t += 1
    for k in range(get_up):
        h = Y0 + 0.15 + (STAND - 0.15) * (k + 1) / get_up
        out.append(person(t, [0, Y0, 0], [0, h, 0], False, low=Y0 + 0.02))
        t += 1
    for _ in range(30):
        out.append(person(t, [0, Y0, 0], [0, Y0 + STAND, 0], False))
        t += 1
    assert land is not None
    return out


RAGDOLL = {"from": "a", "to": "b", "kind": "player", "trigger": {"landing_y": Y0, "near_m": 0.25},
           "within_ticks": 12, "min_s": 1.0, "below_m": 0.05, "step_m": 1.0, "ground_y": Y0,
           "boxes": []}  # fmt: skip


def test_ragdoll_on_landing() -> None:
    good = outcome(framed(fall(10.0)), "ragdoll", RAGDOLL)
    assert good.ok is True and good.measured["limp_s"] == 2.0
    never = fall(10.0)
    for f in never:
        f["census"][0]["m"]["limp"] = False
        f["state"]["player"]["limp"] = False
    assert (
        outcome(framed(never), "ragdoll", RAGDOLL).note == "the entity never went limp"
    )
    late = outcome(framed(fall(10.0, limp_after=30)), "ragdoll", RAGDOLL)
    assert late.ok is False and "ticks after" in late.note
    short = outcome(framed(fall(10.0, limp_ticks=30)), "ragdoll", RAGDOLL)
    assert short.ok is False and "limp for 0.50 s" in short.note
    sunk = outcome(framed(fall(10.0, below=0.2)), "ragdoll", RAGDOLL)
    assert sunk.ok is False and "under the ground" in sunk.note
    jumpy = outcome(framed(fall(10.0, teleport=True)), "ragdoll", RAGDOLL)
    assert jumpy.ok is False and "moved" in jumpy.note
    liar = fall(10.0)
    for f in liar:
        f["state"]["player"]["limp"] = False
    assert "differs" in outcome(framed(liar), "ragdoll", RAGDOLL).note


def test_free_fall_and_get_up() -> None:
    args = {"from": "a", "to": "b", "kind": "player", "ground_y": Y0, "clear_m": 0.3,
            "tol": 0.2, "min_ticks": 10}  # fmt: skip
    good = outcome(framed(fall(16.0, free=True)), "free_fall", args)
    assert good.ok is True and abs(good.measured["accel_mps2"] - G) < 0.3
    floaty = fall(16.0, free=True)
    for f in floaty:
        f["bones"]["1"]["Hips"][1] = Y0 + (f["bones"]["1"]["Hips"][1] - Y0) * 0.5 + 8.0
        f["bones"]["1"]["LeftToes"][1] = f["bones"]["1"]["Hips"][1] - 0.3
    assert outcome(framed(floaty), "free_fall", args).ok is False
    up = {
        "from": "a",
        "to": "b",
        "kind": "player",
        "ground_y": Y0,
        "within_s": 6.0,
        "ratio": 0.9,
    }
    o = outcome(framed(fall(10.0)), "get_up", up)
    assert o.ok is True and 2.5 < o.measured["seconds"] < 3.5
    stays = outcome(framed(fall(10.0, limp_ticks=500)), "get_up", up)
    assert stays.ok is False


# ---------------------------------------------------------------- damage
def crash(dv_kmh: float, added: float, part: bool = True) -> list[dict]:
    out, z, v = [], 0.0, 45 * KMH
    dmg = 0.15
    for t in range(200):
        if t == 60:
            v = 45 * KMH - dv_kmh * KMH
        if t == 72:
            dmg = 0.15 + added
        z -= v / 60
        f = car(t, [0.0, 0.0, z], damage=dmg)
        if part and t == 75:
            f["events"] = [
                {"n": "part_detached", "d": {"vehicle": VID, "debris": 9, "tick": 75}}
            ]
            f["census"].append({"id": 9, "k": "debris", "a": "part", "f": "none",
                                "p": [0, 1, z], "m": {"vehicle": VID}})  # fmt: skip
        out.append(f)
    return out


def test_impact_damage_and_parts() -> None:
    args = {"from": "a", "to": "b", **IDF, "rate": 0.004, "free_kmh": 8.0, "tol": 0.25}
    good = outcome(framed(crash(45.0, 0.004 * 37)), "impact_damage", args)
    assert good.ok is True and abs(good.measured["dv_kmh"] - 45.0) < 0.5
    none = outcome(framed(crash(45.0, 0.0)), "impact_damage", args)
    assert none.ok is False
    part = {"from": "a", "to": "b", **IDF, "min_dv_kmh": 25.0, "min_damage": 0.25,
            "within_s": 0.5}  # fmt: skip
    assert outcome(framed(crash(45.0, 0.148)), "part_off", part).ok is True
    assert outcome(framed(crash(45.0, 0.148, part=False)), "part_off", part).ok is False


def test_engine_failure_cap() -> None:
    args = {"from": "a", "to": "b", **IDF, "max_kmh": 10.0}
    assert outcome(framed(straight([8 * KMH] * 300)), "max_speed", args).ok is True
    assert outcome(framed(straight([20 * KMH] * 300)), "max_speed", args).ok is False


def burning(explode_at: int, wreck: float = 1.0, loss: int = 50) -> list[dict]:
    out = []
    for t in range(900):
        f = {
            "t": t,
            "census": [
                {"id": VID, "k": "vehicle", "a": "sedan", "f": "none", "p": [0.0, 0.15, 0.0],
                 "m": {"damage": wreck if t > explode_at else 0.85,
                       "burning": t <= explode_at}},
                {"id": 1, "k": "player", "a": "lead_1", "f": "player", "p": [-4.5, 0.15, 0.0]},
                {"id": 8, "k": "vehicle", "a": "sedan", "f": "none",
                 "p": [0.0, 0.15, -5.0 - (1.0 if t > explode_at else 0.0)],
                 "m": {"damage": 0.3 if t > explode_at else 0.0}},
            ],
            "state": {"ok": True, "player": {"health": 100 - (loss if t > explode_at else 0)}},
        }  # fmt: skip
        if t == explode_at:
            f["events"] = [{"n": "vehicle_exploded", "d": {"vehicle": VID, "tick": t}}]
        out.append(f)
    return out


def test_explosion_timing_and_blast() -> None:
    args = {"from": "a", "to": "b", **IDF, "min_s": 8.0, "max_s": 12.0}
    good = outcome(framed(burning(600)), "explosion", args)
    assert good.ok is True and good.measured["seconds"] == 10.0
    assert outcome(framed(burning(180)), "explosion", args).ok is False
    assert outcome(framed(burning(600, wreck=0.9)), "explosion", args).ok is False
    harm = {"from": "a", "to": "b", **IDF, "what": "harm", "tol": 0.1}
    o = outcome(framed(burning(600)), "blast", harm)
    assert o.ok is True and o.measured["expected_loss"] == 50.0
    assert outcome(framed(burning(600, loss=0)), "blast", harm).ok is False
    rec = framed(burning(600))
    rec.runs[0].frames[0]["dev"].append(
        {"cmd": "vehicle.spawn", "res": {"ok": True, "id": 8}}
    )
    push = {"from": "a", "to": "b", **IDF, "what": "push", "push_m": 0.3,
            "of": {"id_from": {"step": 0, "index": 1}}}  # fmt: skip
    assert outcome(rec, "blast", push).ok is True


# ---------------------------------------------------------------- steps and the registry
def test_wait_for_entity_and_cruise_steps_parse() -> None:
    ok = [
        {"wait_for": {"entity": {"id": 3, "min_kmh": 60.0}, "max_ticks": 10}},
        {"wait_for": {"entity": {"kind": "player", "below_y": 4.0}}},
        {
            "cruise": {
                "entity": {"id": 3},
                "kmh": 8.0,
                "ticks": 20,
                "hold": {"steer_left": 1.0},
            }
        },
    ]
    play.parse_play(dict(BASE, steps=ok))
    for bad in (
        {"wait_for": {"entity": {"id": 3}}},
        {"wait_for": {"entity": {"id": 3, "min_kmh": 1, "max_kmh": 2}}},
        {"cruise": {"entity": {"id": 3}, "kmh": 8.0}},
    ):
        try:
            play.parse_play(dict(BASE, steps=[bad]))
        except play.PlayError:
            continue
        raise AssertionError(f"accepted {bad}")
    a = car(10, [0.0, 0.0, 0.0])
    b = car(11, [0.0, 0.0, -0.5])
    assert abs(play.speed_between(a, b, {"id": VID}) - 30.0) < 1e-9


def test_registry_with_a_census_of_some_kinds() -> None:
    signal = {"id": 2, "k": "signal", "a": "s", "f": "none", "p": [0, 0, 0]}
    full = dict(car(0, [0, 0, 0]), _proc=0)
    full["census"].append(dict(signal))
    part = dict(car(1, [0, 0, 0]), _proc=0, _kinds=["vehicle"])
    again = dict(car(2, [0, 0, 0]), _proc=0)
    again["census"].append(dict(signal))
    rec = framed([full, part, again])
    assert expect.standing_registry(rec).ok is True
    gone = dict(
        car(1, [0, 0, 0]), _proc=0
    )  # unfiltered: the signal left, then came back
    rec2 = framed([full, gone, again])
    assert expect.standing_registry(rec2).ok is False
