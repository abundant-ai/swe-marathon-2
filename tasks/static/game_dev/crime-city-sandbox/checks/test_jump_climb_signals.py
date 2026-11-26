"""The kit's jump, climb, vault, camera and signal expectations over hand-made frames, and
the wait_for near step (no Godot). Each holds on a well-behaved game and fails on the
broken one next to it."""

from __future__ import annotations

import copy
import math

import pytest
from qakit import expect, play

BASE = {"format": "qa-play/1", "name": "x/y", "template": "x", "role": "solo"}
Y0 = 0.15
HIP = 0.89


def record(frames: list[dict], marks: dict, steps: list[dict] | None = None):
    """A one-run PlayRecord over the given frames."""
    p = play.parse_play(dict(BASE, steps=steps or [{"run": 1}]))
    r = play.RunRecord(index=0, pace_ms=0, frames=copy.deepcopy(frames))
    r.marks = dict(marks)
    return play.PlayRecord(p, [r], 0.0)


def outcome(rec: play.PlayRecord, check: str, args: dict) -> expect.Outcome:
    raw = dict(rec.play.raw, expect=[{"id": "e", "check": check, "args": args}])
    return expect.check_play(play.PlayRecord(play.parse_play(raw), rec.runs, 0.0))[0]


def body(t: int, pos: list[float], **bones: list[float]) -> dict:
    """A frame with the player at pos and the given bones (Hips defaults above pos)."""
    b = {"Hips": [pos[0], pos[1] + HIP, pos[2]]}
    b.update(bones)
    return {
        "t": t,
        "census": [{"id": 1, "k": "player", "a": "lead_1", "f": "player", "p": pos}],
        "bones": {"1": b},
    }


def framed(frames: list[dict]) -> play.PlayRecord:
    return record(frames, {"a": 0, "b": len(frames) - 1})


JUMP = {
    "from": "a", "to": "b", "kind": "player", "bone": "Hips", "ground_y": Y0, "off_m": 0.02,
    "min_rise_m": 0.4, "max_rise_m": 0.8, "min_air_s": 0.5, "max_air_s": 0.9,
}  # fmt: skip


def jump_frames(v0: float) -> list[dict]:
    out, y, v = [], Y0, 0.0
    for t in range(80):
        if t == 1:
            v = v0
        elif t > 1:
            v -= 9.81 / 60
        y = max(Y0, y + v / 60)
        if y == Y0 and t > 1:
            v = 0.0
        out.append(body(t, [0.0, y, 0.0]))
    return out


def test_jump_rise_and_time_off_the_ground() -> None:
    o = outcome(framed(jump_frames(3.4)), "jump", JUMP)
    assert o.ok is True and 0.5 < o.measured["rise_m"] < 0.65
    assert 0.65 < o.measured["airborne_s"] < 0.75
    flat = outcome(framed(jump_frames(0.0)), "jump", JUMP)
    assert flat.ok is False and "rose 0.00 m" in flat.note
    high = outcome(framed(jump_frames(5.5)), "jump", JUMP)
    assert high.ok is False and high.measured["rise_m"] > 0.8


# A 1.2 m ledge 2 m deep, its near face 1 m north of the origin (heading 0: depth along -z).
LEDGE = {"p": [0.0, Y0, -2.0], "size": [4.0, 1.2, 2.0], "heading": 0}
TOP = Y0 + 1.2
EDGE = [[-2.0, TOP, -1.0], [2.0, TOP, -1.0]]
CLIMB = {
    "from": "a", "to": "b", "kind": "player", "box": LEDGE, "edge": EDGE, "within_s": 3.5,
    "hand_m": 0.35, "on_top_m": 0.1, "max_into_m": 0.05,
}  # fmt: skip


def climb_frames(
    hand: bool = True, knee_in: float = 0.0, rise_ticks: int = 60
) -> list[dict]:
    """Stand 0.4 m out from the face, rise to the top with the hands on the edge, step on."""
    out = []
    for t in range(rise_ticks + 30):
        if t <= rise_ticks:
            pos = [0.0, Y0 + (TOP + 0.03 - Y0) * t / rise_ticks, -0.6]
        else:
            pos = [0.0, TOP, -0.6 - 0.85 * min(1.0, (t - rise_ticks) / 20)]
        hands = {}
        if hand and t <= rise_ticks:
            hands = {
                "LeftHand": [-0.2, TOP + 0.05, -1.04],
                "RightHand": [0.2, TOP + 0.05, -1.04],
            }
        knee = {"LeftLowerLeg": [0.0, Y0 + 0.5, -1.0 - knee_in]} if t == 10 else {}
        out.append(body(t, pos, **hands, **knee))
    return out


def test_climb_on_top_hands_and_no_bone_inside() -> None:
    o = outcome(framed(climb_frames()), "climb", CLIMB)
    assert o.ok is True and o.measured["hand_to_edge_m"] < 0.1
    assert o.measured["on_top_after_s"] < 1.5
    no_hands = outcome(framed(climb_frames(hand=False)), "climb", CLIMB)
    assert no_hands.ok is False and "no hand" in no_hands.note
    knee = outcome(framed(climb_frames(knee_in=0.1)), "climb", CLIMB)
    assert knee.ok is False and "LeftLowerLeg is 0.100 m inside" in knee.note
    slow = outcome(framed(climb_frames(rise_ticks=300)), "climb", CLIMB)
    assert slow.ok is False and "not on top" in slow.note


# A 0.8 m barrier 0.4 m deep, its near face 1.2 m north of the origin.
BARRIER = {"p": [0.0, Y0, -1.4], "size": [3.0, 0.8, 0.4], "heading": 0}
VAULT = {
    "from": "a", "to": "b", "kind": "player", "box": BARRIER, "within_s": 1.2,
    "clear_m": 0.1, "max_into_m": 0.05,
}  # fmt: skip


def vault_frames(lift: float, speed: float = 5.5) -> list[dict]:
    out = []
    for t in range(40):
        z = -speed * t / 60
        inside = -1.65 < z < -1.15
        pos = [0.0, Y0 + (lift if inside else 0.0), z]
        out.append(body(t, pos, LeftToes=[0.1, pos[1] + 0.02, z - 0.2]))
    return out


def test_vault_over_clear_and_through() -> None:
    o = outcome(framed(vault_frames(0.95)), "vault", VAULT)
    assert o.ok is True and o.measured["hips_clearance_m"] > 0.5
    through = outcome(framed(vault_frames(0.0)), "vault", VAULT)
    assert through.ok is False and "above the top" in through.note
    slow = outcome(framed(vault_frames(0.95, speed=1.0)), "vault", VAULT)
    assert slow.ok is False and "not past" in slow.note


WALL = {"p": [0.0, Y0, 2.0], "size": [8.0, 3.0, 0.4], "heading": 0}


def camera_frames(pull_in: bool) -> list[dict]:
    out = []
    for t in range(60):
        yaw = math.radians(3 * t)
        dist = 1.5 if pull_in else 4.0
        cam = [math.sin(yaw) * dist, 1.8, math.cos(yaw) * dist]
        fr = body(t, [0.0, Y0, 0.0], Head=[0.0, 1.75, 0.0])
        fr["camera"] = {"p": cam, "bz": [0.0, 0.0, 1.0], "fov": 75.0}
        out.append(fr)
    return out


def test_camera_clear_of_walls() -> None:
    args = {
        "from": "a",
        "to": "b",
        "kind": "player",
        "boxes": [WALL],
        "min_share": 0.99,
    }
    assert outcome(framed(camera_frames(True)), "camera_clear", args).ok is True
    o = outcome(framed(camera_frames(False)), "camera_clear", args)
    assert o.ok is False and o.measured["through_a_wall"] > 0


def test_segment_and_box_geometry() -> None:
    turned = {"p": [0.0, 0.0, 0.0], "size": [2.0, 1.0, 0.5], "heading": 90}
    assert expect.depth_into(turned, [0.2, 0.5, 0.0]) == pytest.approx(0.05)
    assert expect.depth_into(turned, [0.0, 0.5, 0.9]) == pytest.approx(0.1)
    assert expect.depth_into(turned, [0.0, 0.5, 1.1]) == 0.0
    assert expect.segment_hits_box(turned, [-1.0, 0.5, 0.0], [1.0, 0.5, 0.0])
    assert not expect.segment_hits_box(turned, [-1.0, 1.5, 0.0], [1.0, 1.5, 0.0])
    assert (
        expect.segment_distance([0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        == 1.0
    )


# Signals: one junction, two approaches in their own phases, then a walk-only phase.
PROGRAM = {
    "offset": 30, "cycle": 360,
    "phases": [
        {"start": 0, "green_end": 60, "amber_end": 90, "green": ["n"], "walk": []},
        {"start": 120, "green_end": 180, "amber_end": 210, "green": ["e"], "walk": []},
        {"start": 240, "green_end": 300, "amber_end": 330, "green": [], "walk": ["cw"]},
    ],
}  # fmt: skip
RESET_T = 100


def signal_frame(t: int, states: dict) -> dict:
    census = [{"id": i, "k": "signal", "a": "x", "f": "none", "p": [0, 0, 0],
               "m": {"intersection": "j", ("crosswalk" if key == "cw" else "approach"): key,
                     "state": st}}
              for i, (key, st) in enumerate(sorted(states.items()), start=2)]  # fmt: skip
    return {"t": t, "_step": 2, "census": census}


def signal_record(shift: int = 0, edit=None) -> play.PlayRecord:
    steps = [{"observe": {}}, {"run": 1}, {"dev": [["world.reset", {}]]}, {"run": 1}]
    frames = [{"t": RESET_T + 1, "_step": 2, "dev": [{"cmd": "world.reset", "res": {"ok": True},
                                                       "t": RESET_T}]}]  # fmt: skip
    for t in range(RESET_T + 2, RESET_T + 2 + 720, 7):
        states = expect.program_states(PROGRAM, t - 1 - RESET_T - shift)
        if edit:
            states = edit(dict(states))
        frames.append(signal_frame(t, states))
    return record(frames, {"a": 1, "b": len(frames) - 1, "m": 1}, steps)


PROG_ARGS = {"from": "a", "to": "b", "programs": {"j": PROGRAM}, "reset_step": 2}


def test_signal_program_within_one_tick() -> None:
    assert expect.program_states(PROGRAM, -30) == {
        "n": "green",
        "e": "red",
        "cw": "dont_walk",
    }
    assert expect.program_states(PROGRAM, 30) == {
        "n": "amber",
        "e": "red",
        "cw": "dont_walk",
    }
    assert expect.program_states(PROGRAM, 210)["cw"] == "walk"
    assert outcome(signal_record(), "signal_program", PROG_ARGS).ok is True
    assert outcome(signal_record(shift=1), "signal_program", PROG_ARGS).ok is True
    late = outcome(signal_record(shift=3), "signal_program", PROG_ARGS)
    assert late.ok is False and late.measured["off_program"] > 0


def test_signal_greens_walks_and_entities() -> None:
    def both_green(s: dict) -> dict:
        return dict(s, e="green") if s["n"] == "green" else s

    def walk_in_amber(s: dict) -> dict:
        return dict(s, cw="walk") if "amber" in s.values() else s

    args = {"from": "a", "to": "b", "programs": {"j": PROGRAM}}
    assert outcome(signal_record(), "signal_greens", args).ok is True
    assert outcome(signal_record(edit=both_green), "signal_greens", args).ok is False
    assert outcome(signal_record(), "signal_walks", args).ok is True
    o = outcome(signal_record(edit=walk_in_amber), "signal_walks", args)
    assert o.ok is False and "shows walk while" in o.note
    ents = {
        "mark": "m",
        "approaches": [["j", "n"], ["j", "e"]],
        "crosswalks": [["j", "cw"]],
    }
    assert outcome(signal_record(), "signal_entities", ents).ok is True
    missing = dict(ents, approaches=[["j", "n"], ["j", "w"]])
    o = outcome(signal_record(), "signal_entities", missing)
    assert o.ok is False and "w at j: 0 signal entities" in o.note


def test_wait_for_near_steps() -> None:
    step = {
        "wait_for": {"near": {"p": [0.0, 0.0, 1.0], "within_m": 1.2}, "max_ticks": 9}
    }
    play.parse_play(dict(BASE, steps=[step]))
    with pytest.raises(play.PlayError, match="lockstep"):
        play.parse_play(dict(BASE, mode="realtime", steps=[step]))
    bad = {"wait_for": {"near": {"p": [0.0, 1.0], "within_m": 1.2}}}
    with pytest.raises(play.PlayError):
        play.parse_play(dict(BASE, steps=[bad]))
    fr = {
        "census": [
            {"k": "player", "p": [0.0, 5.0, 0.0]},
            {"k": "npc", "p": [0.0, 0.0, 1.0]},
        ]
    }
    assert play.is_near(fr, {"p": [0.5, 0.0, 0.5], "within_m": 1.0})
    assert not play.is_near(fr, {"p": [0.0, 0.0, 1.5], "within_m": 1.0})
    assert play.is_near(fr, {"kind": "npc", "p": [0.0, 0.0, 1.5], "within_m": 1.0})
