"""The kit's crime and police expectations (chapter 9, CB-10) over hand-made frames (no Godot).
Each expectation holds on a well-behaved alert and fails on the broken one next to it."""

from __future__ import annotations

import copy

from qakit import expect, play

BASE = {"format": "qa-play/1", "name": "x/y", "template": "x", "role": "solo"}
ME = 1
COP = 50
CIV = 60
CAR = 70


def record(frames: list[dict], marks: dict | None = None) -> play.PlayRecord:
    raw = dict(BASE, steps=[{"run": 1}])
    r = play.RunRecord(index=0, pace_ms=0, frames=copy.deepcopy(frames))
    r.marks = marks or {"a": 0, "b": len(frames) - 1}
    return play.PlayRecord(play.parse_play(raw), [r], 0.0)


def outcome(rec: play.PlayRecord, check: str, args: dict) -> expect.Outcome:
    raw = dict(rec.play.raw, expect=[{"id": "e", "check": check, "args": args}])
    return expect.check_play(play.PlayRecord(play.parse_play(raw), rec.runs, 0.0))[0]


def frame(t: int, level: int = 0, at=(0.0, 0.0), census=(), events=(), **pl) -> dict:
    st = {"id": ME, "alert": level, "money": pl.pop("money", 1000), "health": pl.pop("health", 100),
          "armour": pl.pop("armour", 0), "weapons": pl.pop("weapons", ["fists", "pistol"]),
          "vehicle": pl.pop("vehicle", None)}  # fmt: skip
    rows = [
        {
            "id": ME,
            "k": "player",
            "a": "lead_1",
            "p": [at[0], 0.0, at[1]],
            "bz": [0.0, 0.0, 1.0],
        }
    ]
    rows += list(census)
    return {
        "t": t,
        "state": {"player": st},
        "census": rows,
        "events": list(events),
        "_proc": 0,
    }


def cop(
    x: float, z: float, eid: int = COP, vehicle=None, hostile=False, iv=False
) -> dict:
    return {"id": eid, "k": "npc", "a": "police_officer", "p": [x, 0.0, z], "iv": iv,
            "m": {"vehicle": vehicle, "hostile": hostile}}  # fmt: skip


def police_car(
    x: float, z: float, eid: int = CAR, iv=False, heading_axis_x=False
) -> dict:
    bz = [1.0, 0.0, 0.0] if heading_axis_x else [0.0, 0.0, 1.0]
    return {"id": eid, "k": "vehicle", "a": "police", "p": [x, 0.0, z], "iv": iv, "bz": [0.0, 0.0, 1.0],
            "sh": [{"type": "box", "p": [x, 0.5, z], "size": [1.9, 1.5, 4.8], "bz": bz}]}  # fmt: skip


def crime(kind: str, witnesses: list) -> dict:
    return {"n": "crime", "d": {"type": kind, "witnesses": witnesses, "pos": [0, 0, 0]}}


def changed(level: int, reason: str) -> dict:
    return {"n": "alert_changed", "d": {"level": level, "reason": reason}}


# ------------------------------------------------------------------ AL-1 and AL-2
def test_crime_event_lists_its_witnesses() -> None:
    good = record([frame(0), frame(6, events=[crime("assault", [COP])]), frame(60)])
    args = {
        "from": "a",
        "to": "b",
        "type": "assault",
        "seen_by": [COP],
        "within_s": 1.0,
    }
    assert outcome(good, "crime_event", args).ok is True
    bad = record([frame(0), frame(6, events=[crime("assault", [])]), frame(60)])
    assert outcome(bad, "crime_event", args).ok is False
    none = record([frame(0), frame(60)])
    assert outcome(none, "crime_event", args).ok is False
    late = record([frame(0), frame(120, events=[crime("assault", [COP])])])
    assert outcome(late, "crime_event", args).ok is False


def test_crime_event_counts_one_burst() -> None:
    one = record([frame(0), frame(10, events=[crime("shots_fired", [])]), frame(200)])
    args = {
        "from": "a",
        "to": "b",
        "type": "shots_fired",
        "count": 1,
        "witnessed": False,
    }
    assert outcome(one, "crime_event", args).ok is True
    many = record([frame(0), frame(10, events=[crime("shots_fired", [])]),
                   frame(30, events=[crime("shots_fired", [])])])  # fmt: skip
    assert outcome(many, "crime_event", args).ok is False


def test_alert_rise_by_police_and_by_phone() -> None:
    police = record([frame(0), frame(6, events=[crime("assault", [COP])]),
                     frame(30, 1, events=[changed(1, "assault")]), frame(90, 1)])  # fmt: skip
    args = {"from": "a", "to": "b", "type": "assault", "level": 1, "max_s": 1.0}
    assert outcome(police, "alert_rise", args).ok is True
    slow = record([frame(0), frame(6, events=[crime("assault", [COP])]),
                   frame(200, 1, events=[changed(1, "assault")]), frame(260, 1)])  # fmt: skip
    assert outcome(slow, "alert_rise", args).ok is False
    phone = {
        "from": "a",
        "to": "b",
        "type": "assault",
        "level": 1,
        "min_s": 10.0,
        "max_s": 11.0,
    }
    rang = record([frame(0), frame(6, events=[crime("assault", [CIV])]),
                   frame(606, 1, events=[changed(1, "assault")]), frame(700, 1)])  # fmt: skip
    assert outcome(rang, "alert_rise", phone).ok is True
    early = record([frame(0), frame(6, events=[crime("assault", [CIV])]),
                    frame(66, 1, events=[changed(1, "assault")]), frame(700, 1)])  # fmt: skip
    assert outcome(early, "alert_rise", phone).ok is False


def test_alert_steady_and_sequence() -> None:
    calm = record([frame(0), frame(300), frame(900)])
    assert (
        outcome(calm, "alert_steady", {"from": "a", "to": "b", "level": 0}).ok is True
    )
    rose = record(
        [frame(0), frame(300, 1, events=[changed(1, "assault")]), frame(900, 1)]
    )
    assert (
        outcome(rose, "alert_steady", {"from": "a", "to": "b", "level": 0}).ok is False
    )
    seq = record([frame(0), frame(10, 1, events=[changed(1, "assault")]),
                  frame(400, 2, events=[changed(2, "shots_fired")]),
                  frame(800, 3, events=[changed(3, "shots_fired")])])  # fmt: skip
    assert (
        outcome(seq, "alert_sequence", {"from": "a", "to": "b", "levels": [1, 2, 3]}).ok
        is True
    )
    assert (
        outcome(seq, "alert_sequence", {"from": "a", "to": "b", "levels": [1, 2, 2]}).ok
        is False
    )


# ------------------------------------------------------------------ AL-6, AL-7
def arrival(arrive_t: int) -> list[dict]:
    frames = [frame(0), frame(6, 1, events=[changed(1, "red_light")])]
    for t in range(60, arrive_t + 61, 60):
        x = 300.0 - 280.0 * min(1.0, t / arrive_t)
        frames.append(frame(t, 1, census=[police_car(x, 0.0)]))
    return frames


def test_police_arrival_in_time() -> None:
    args = {"from": "a", "to": "b", "within_s": 60.0}
    assert outcome(record(arrival(1800)), "police_arrival", args).ok is True
    assert outcome(record(arrival(4800)), "police_arrival", args).ok is False


def test_police_origin_far_and_out_of_view() -> None:
    good = record([frame(0), frame(6, 1, events=[changed(1, "red_light")]),
                   frame(60, 1, census=[police_car(150.0, 0.0)])])  # fmt: skip
    args = {"from": "a", "to": "b"}
    assert outcome(good, "police_origin", args).ok is True
    near = record([frame(0), frame(6, 1, events=[changed(1, "red_light")]),
                   frame(60, 1, census=[police_car(40.0, 0.0)])])  # fmt: skip
    assert outcome(near, "police_origin", args).ok is False
    seen = record([frame(0), frame(6, 1, events=[changed(1, "red_light")]),
                   frame(60, 1, census=[police_car(150.0, 0.0, iv=True)])])  # fmt: skip
    assert outcome(seen, "police_origin", args).ok is False


def test_police_kinematics_speed_and_buildings() -> None:
    args = {"from": "a", "to": "b", "top_kmh": {"police": 210.0}, "foot_mps": 9.6,
            "buildings": [[[50.0, 50.0], [60.0, 50.0], [60.0, 60.0], [50.0, 60.0]]]}  # fmt: skip
    ok = record(
        [
            frame(0, census=[police_car(0.0, 0.0)]),
            frame(60, census=[police_car(30.0, 0.0)]),
        ]
    )
    assert outcome(ok, "police_kinematics", args).ok is True
    fast = record(
        [
            frame(0, census=[police_car(0.0, 0.0)]),
            frame(60, census=[police_car(90.0, 0.0)]),
        ]
    )
    assert outcome(fast, "police_kinematics", args).ok is False
    wall = record(
        [
            frame(0, census=[police_car(54.0, 40.0)]),
            frame(60, census=[police_car(55.0, 55.0)]),
        ]
    )
    assert outcome(wall, "police_kinematics", args).ok is False


def test_police_count_reaches_and_caps() -> None:
    def frames_with(n: int) -> list[dict]:
        out = [frame(0), frame(6, 2, events=[changed(2, "shots_fired")])]
        for t in range(60, 6000, 60):
            out.append(
                frame(
                    t,
                    2,
                    census=[
                        police_car(50.0 + 5 * i, 0.0, eid=CAR + i) for i in range(n)
                    ],
                )
            )
        return out

    args = {"from": "a", "to": "b", "count": 2}
    assert outcome(record(frames_with(2)), "police_count", args).ok is True
    assert outcome(record(frames_with(1)), "police_count", args).ok is False
    assert outcome(record(frames_with(5)), "police_count", args).ok is False


# ------------------------------------------------------------------ AL-8
ROAD = {"id": "e_1", "pts": [[0.0, 0.0], [0.0, -400.0]], "width": 7.0}


def roadblock(axis_x: bool, gap: float) -> list[dict]:
    frames = [frame(0, 3, vehicle=CAR + 9)]
    me = {
        "id": CAR + 9,
        "k": "vehicle",
        "a": "sedan",
        "p": [1.6, 0.0, -10.0],
        "bz": [0.0, 0.0, 1.0],
    }
    for t in range(6, 400, 30):
        cars = [police_car(-1.7, -150.0, CAR, heading_axis_x=axis_x),
                police_car(-1.7 + gap, -150.0, CAR + 1, heading_axis_x=axis_x)]  # fmt: skip
        frames.append(frame(t, 3, census=[me, *cars], vehicle=CAR + 9))
    return frames


def test_roadblock_across_and_ahead() -> None:
    args = {"from": "a", "to": "b", "roads": [ROAD], "reach": {}}
    assert outcome(record(roadblock(True, 3.6)), "roadblock", args).ok is True
    along = record(roadblock(False, 3.6))
    assert outcome(along, "roadblock", args).ok is False
    gappy = record(roadblock(True, 0.3))  # both on one side: about 64% of the width
    assert outcome(gappy, "roadblock", args).ok is False
    far = {"from": "a", "to": "b", "roads": [ROAD], "reach": {}, "ahead_m": 100.0}
    assert outcome(record(roadblock(True, 3.6)), "roadblock", far).ok is False


# ------------------------------------------------------------------ AL-9, AL-10
def arrest_frames(at_t: int, officer_m: float = 1.0) -> list[dict]:
    out = [frame(0, 1)]
    for t in range(6, 400, 6):
        evs = [{"n": "arrested", "d": {"entity": ME}}] if t == at_t else []
        out.append(frame(t, 1, census=[cop(officer_m, 0.0)], events=evs))
    return out


def test_arrest_timing() -> None:
    args = {"from": "a", "to": "b", "officer": COP}
    assert outcome(record(arrest_frames(6 + 186)), "arrest", args).ok is True
    assert outcome(record(arrest_frames(6 + 60)), "arrest", args).ok is False
    assert outcome(record(arrest_frames(6 + 300)), "arrest", args).ok is False
    away = {"from": "a", "to": "b", "officer": COP, "expect": False}
    assert outcome(record(arrest_frames(-1, 3.0)), "arrest", away).ok is True
    assert outcome(record(arrest_frames(6 + 186, 3.0)), "arrest", away).ok is False


def test_came_back_after_arrest() -> None:
    station = [10.0, 0.15, 20.0]
    good = [frame(0, 1), frame(6, 1, events=[{"n": "arrested", "d": {"entity": ME}}]),
            frame(186, 0, at=(10.0, 20.0), money=500, weapons=["fists"],
                  events=[{"n": "teleport", "d": {"entity": ME}},
                          {"n": "respawned", "d": {"entity": ME, "poi": "police_station_x"}},
                          changed(0, "arrested")]),
            frame(300, 0, at=(10.0, 20.0), money=500, weapons=["fists"])]  # fmt: skip
    args = {"from": "a", "to": "b", "after": "arrested", "poi": "police_station_x", "respawn": station,
            "money": 500, "weapons": ["fists"]}  # fmt: skip
    assert outcome(record(good), "came_back", args).ok is True
    kept = copy.deepcopy(good)
    for fr in kept[2:]:
        fr["state"]["player"]["weapons"] = ["fists", "pistol"]
    assert outcome(record(kept), "came_back", args).ok is False
    late = copy.deepcopy(good)
    late[2]["t"] = 900
    late[3]["t"] = 1000
    assert outcome(record(late), "came_back", args).ok is False


# ------------------------------------------------------------------ AL-11
def test_escape_window() -> None:
    def drop_at(t: int) -> list[dict]:
        return [
            frame(0, 1),
            frame(60, 1),
            frame(t, 0, events=[changed(0, "escaped")]),
            frame(t + 60, 0),
        ]

    marks = {"a": 0, "move": 1, "b": 3}
    args = {"from": "a", "to": "b", "anchor": "move", "cooling_s": 20.0}
    assert outcome(record(drop_at(60 + 1260), marks), "escape", args).ok is True
    assert outcome(record(drop_at(60 + 600), marks), "escape", args).ok is False
    assert outcome(record(drop_at(60 + 1600), marks), "escape", args).ok is False


# ------------------------------------------------------------------ CB-10, AL-12
def test_police_force_by_level() -> None:
    hitme = {
        "n": "damaged",
        "d": {"entity": ME, "source": COP, "amount": 25, "health": 75, "armour": 0},
    }
    calm = record(
        [frame(0, 1, census=[cop(5.0, 0.0)]), frame(60, 1, census=[cop(4.0, 0.0)])]
    )
    assert outcome(calm, "police_force", {"from": "a", "to": "b"}).ok is True
    shot = record(
        [
            frame(0, 1, census=[cop(5.0, 0.0)]),
            frame(60, 1, census=[cop(4.0, 0.0)], events=[hitme]),
        ]
    )
    assert outcome(shot, "police_force", {"from": "a", "to": "b"}).ok is False
    fight = record([frame(0, 3, census=[cop(20.0, 0.0, hostile=True)]),
                    frame(300, 3, census=[cop(20.0, 0.0, hostile=True)], events=[hitme])])  # fmt: skip
    assert (
        outcome(fight, "police_force", {"from": "a", "to": "b", "fight": True}).ok
        is True
    )
    idle = record(
        [frame(0, 3, census=[cop(20.0, 0.0)]), frame(1200, 3, census=[cop(20.0, 0.0)])]
    )
    assert (
        outcome(idle, "police_force", {"from": "a", "to": "b", "fight": True}).ok
        is False
    )


def test_left_alone_at_zero() -> None:
    def frames_for(follow: bool) -> list[dict]:
        out = [
            frame(0, 1, census=[cop(30.0, 0.0)]),
            frame(6, 0, census=[cop(30.0, 0.0)], events=[changed(0, "escaped")]),
        ]
        x = 60.0
        for t in range(660, 3000, 60):
            x = x - 3.0 if follow else x + 3.0
            out.append(frame(t, 0, census=[cop(max(x, 6.0), 0.0)]))
        return out

    args = {"from": "a", "to": "b"}
    assert outcome(record(frames_for(False)), "left_alone", args).ok is True
    assert outcome(record(frames_for(True)), "left_alone", args).ok is False


# ------------------------------------------------------------------ inv.alert_honest
def test_alert_honest() -> None:
    good = record([frame(0), frame(6, events=[crime("assault", [COP])]),
                   frame(12, 1, events=[changed(1, "assault")]),
                   frame(400, 1, events=[crime("shots_fired", [COP])]),
                   frame(406, 2, events=[changed(2, "shots_fired")]),
                   frame(1000, 2, events=[crime("shots_fired", [CIV])]),
                   frame(1606, 3, events=[changed(3, "shots_fired")]),
                   frame(2000, 0, events=[changed(0, "escaped")])], {"a": 0, "b": 7})  # fmt: skip
    args = {"from": "a", "to": "b", "police": [COP]}
    assert outcome(good, "alert_honest", args).ok is True
    unseen = record([frame(0), frame(6, events=[crime("assault", [])]),
                     frame(12, 1, events=[changed(1, "assault")])])  # fmt: skip
    assert outcome(unseen, "alert_honest", args).ok is False
    jump = record([frame(0), frame(6, events=[crime("assault", [COP])]),
                   frame(12, 3, events=[changed(3, "assault")])])  # fmt: skip
    assert outcome(jump, "alert_honest", args).ok is False
    slip = record([frame(0, 2), frame(6, 1, events=[changed(1, "cooling")])])
    assert outcome(slip, "alert_honest", args).ok is False
