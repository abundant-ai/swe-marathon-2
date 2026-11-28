"""The kit's ray and people expectations over hand-made frames (no Godot)."""

from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

import pytest
from qakit import expect, play

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "scripts"))

from plan_probes import inset

BASE = {"format": "qa-play/1", "name": "x/y", "template": "x", "role": "solo"}


def record(steps: list[dict], frames: list[dict], marks: dict, step_frame: dict):
    """A one-run PlayRecord with the given steps and frames."""
    p = play.parse_play(dict(BASE, steps=steps))
    r = play.RunRecord(index=0, pace_ms=0, frames=copy.deepcopy(frames))
    r.marks, r.step_frame = dict(marks), dict(step_frame)
    return play.PlayRecord(p, [r], 0.0)


def hit(y: float, surface: str | None = "road") -> dict:
    out = {"hit": True, "p": [0.0, y, 0.0]}
    if surface is not None:
        out["surface"] = surface
    return out


def down_record(answers: list) -> play.PlayRecord:
    """A play whose step 1 is one "down" query "q" with one point per answer."""
    steps = [
        {"run": 1},
        {"query": [{"id": "q", "type": "down", "points": [[i, 0] for i in range(len(answers))]}]},
    ]  # fmt: skip
    return record(steps, [{"t": 1}, {"t": 2, "q": {"q": answers}}], {}, {1: 1})


def outcome(rec: play.PlayRecord, check: str, args: dict) -> expect.Outcome:
    return expect.check_play(
        play.PlayRecord(
            play.parse_play(
                dict(rec.play.raw, expect=[{"id": "e", "check": check, "args": args}])
            ),
            rec.runs,
            0.0,
        )
    )[0]


def test_rays_heights_tags_and_shares() -> None:
    """Heights within the tolerance and the right tag; shares per group; misses named."""
    rec = down_record([hit(0.0), hit(0.08), hit(0.3), hit(0.0, "terrain")])
    args = {"step": 1, "query": "q", "y": 0.0, "tol_m": 0.1, "tags": ["road"]}
    o = outcome(rec, "rays", args)
    assert (
        o.ok is False and o.measured["as_planned"] == 2 and o.measured["share"] == 0.5
    )
    assert "height 0.3" in o.measured["first_off_plan"][0]["why"]
    assert outcome(rec, "rays", dict(args, min_share=0.5)).ok is True
    grouped = dict(args, groups=[["a", 2], ["b", 2]], min_share=0.6)
    o = outcome(rec, "rays", grouped)
    assert o.ok is False and o.measured["groups_below_share"] == [
        {"group": "b", "share": 0.0}
    ]
    per_ray = dict(args, y=[0.0, 0.0, 0.3, 0.0], tags=["road", "terrain"])
    assert outcome(rec, "rays", per_ray).ok is True
    assert outcome(rec, "rays", dict(args, groups=[["a", 3]])).ok is None


def test_rays_clear_not_tags_and_unanswered() -> None:
    """clear holds only where nothing is hit; not_tags refuses a surface; no answer is a miss."""
    rec = down_record([{"hit": False}, hit(0.15, "sidewalk"), None])
    assert outcome(rec, "rays", {"step": 1, "query": "q", "clear": True}).ok is False
    o = outcome(rec, "rays", {"step": 1, "query": "q", "clear": True, "min_share": 0.3})
    assert o.ok is True and o.measured["as_planned"] == 1
    side = {
        "step": 1,
        "query": "q",
        "not_tags": ["building"],
        "groups": [["s", 1], ["t", 2]],
    }
    o = outcome(rec, "rays", side)
    assert o.ok is False and o.measured["groups_below_share"] == [
        {"group": "s", "share": 0.0},
        {"group": "t", "share": 0.5},
    ]
    assert o.measured["first_off_plan"][0]["why"] == "the ray hit nothing"
    optional = dict(side, hit_optional=True)
    o = outcome(rec, "rays", optional)
    assert o.measured["groups_below_share"] == [{"group": "t", "share": 0.5}]
    assert outcome(down_record([]), "rays", {"step": 1, "query": "q"}).ok is None
    unanswered = record(
        [{"run": 1}, {"query": [{"id": "q", "type": "down", "points": [[0, 0]]}]}],
        [{"t": 1}], {}, {},
    )  # fmt: skip
    assert outcome(unanswered, "rays", {"step": 1, "query": "q"}).ok is None


def test_ray_queries_by_prefix_and_clear_runs() -> None:
    """ "rays" reads the ray queries p0..pn-1; clear_run measures the widest clear run."""
    answers = [{"hit": False}] * 13 + [hit(1.0, "building")] + [{"hit": False}] * 3
    queries = [
        {"id": f"o.{k}", "type": "ray", "from": [0, 1, k], "to": [1, 1, k]}
        for k in range(len(answers))
    ]
    rec = record(
        [{"run": 1}, {"query": queries}],
        [{"t": 1}, {"t": 2, "q": {f"o.{k}": a for k, a in enumerate(answers)}}],
        {}, {1: 1},
    )  # fmt: skip
    rays = {"prefix": "o.", "count": len(answers)}
    o = outcome(
        rec,
        "clear_run",
        {"step": 1, "rays": rays, "spacing_m": 0.1, "min_width_m": 1.2},
    )
    assert o.ok is True and o.measured["clear_width_m"]["all"] == 1.3
    narrow = {"step": 1, "rays": rays, "spacing_m": 0.1, "min_width_m": 1.35}
    assert outcome(rec, "clear_run", narrow).ok is False
    o = outcome(rec, "rays", {"step": 1, "rays": rays, "clear": True})
    assert o.ok is False and o.measured["first_off_plan"][0]["at"] == [
        [0, 1, 13],
        [1, 1, 13],
    ]


def test_surface_tags_none_listed_and_skeleton() -> None:
    """Every hit carries a listed tag; "unregistered" lists nothing; one profile skeleton."""
    answers = {
        "q": [hit(0.0), hit(0.0, None), {"hit": False}],
        "r": hit(1.0, "rooftop"),
        "u": ["/root/Ghost"],
        "s": {"ok": True, "skeletons": 1, "bones": ["Hips", "Head"], "bound_meshes": 2},
        "z": [],
    }
    rec = record(
        [{"run": 1}, {"query": []}], [{"t": 1}, {"t": 2, "q": answers}], {}, {1: 1}
    )
    o = outcome(rec, "surface_tags", {"step": 1, "allowed": ["road"]})
    assert o.ok is False and o.measured["other_tags"] == {"untagged": 1, "rooftop": 1}
    assert outcome(rec, "none_listed", {"step": 1, "query": "u"}).ok is False
    assert outcome(rec, "none_listed", {"step": 1, "query": "z"}).ok is True
    sk = {"step": 1, "query": "s", "bones": ["Hips", "Head"]}
    assert outcome(rec, "skeleton", sk).ok is True
    o = outcome(rec, "skeleton", dict(sk, bones=["Hips", "LeftToes"]))
    assert o.ok is False and o.measured["missing_bones"] == ["LeftToes"]
    assert outcome(rec, "skeleton", dict(sk, min_bound_meshes=3)).ok is False


def person(t: int, x: float, z: float, bones: dict, cam: dict | None = None, **meta):
    """A frame with the player at (x, 0, z), its bones, and optionally the camera."""
    fr = {
        "t": t,
        "census": [
            {"id": 1, "k": "player", "a": "lead_1", "f": "player", "p": [x, 0.0, z]}
        ],
        "bones": {"1": bones},
    }
    if meta:
        fr["census"][0]["m"] = meta
    if cam is not None:
        fr["camera"] = cam
    return fr


def test_pace_uses_the_bone_and_the_ticks() -> None:
    """Horizontal speed of the Hips bone between two marks, at 60 ticks per second."""
    frames = [
        person(10, 0.0, 0.0, {"Hips": [0.0, 1.0, 0.0]}),
        person(70, 0.0, 0.0, {"Hips": [3.0, 2.0, -4.0]}),
    ]
    rec = record([{"run": 1}], frames, {"a": 0, "b": 1}, {})
    args = {"from": "a", "to": "b", "bone": "Hips", "min_mps": 4.6, "max_mps": 6.4}
    o = outcome(rec, "pace", args)
    assert o.ok is True and o.measured["speed_mps"] == 5.0
    assert outcome(rec, "pace", dict(args, min_mps=5.5)).ok is False
    assert outcome(rec, "pace", dict(args, bone="Head")).ok is None


def walking_toes(planted: bool) -> list[dict]:
    """Frames of a walk at 1 m/s: toes either step in turn (planted) or glide on the ground."""
    frames = []
    for t in range(0, 240, 2):
        x = t / 60.0
        bones = {}
        for side, phase in (("Left", 0), ("Right", 30)):
            cyc = (t + phase) % 60
            if planted:
                stance = cyc < 36
                foot_x = ((t + phase) // 60) * 1.0 + (0.6 if not stance else 0.0)
                y = 0.0 if stance else 0.12
            else:
                foot_x, y = x, 0.0
            bones[f"{side}Toes"] = [foot_x, y, 0.0]
        frames.append(person(t, x, 0.0, bones))
    return frames


@pytest.mark.parametrize("planted", [True, False])
def test_feet_steps_alternation_and_slide(planted: bool) -> None:
    """Planted, alternating toes hold FT-2's walk limit; toes that glide never step."""
    frames = walking_toes(planted)
    rec = record([{"run": 1}], frames, {"a": 0, "b": len(frames) - 1}, {})
    o = outcome(rec, "feet", {"from": "a", "to": "b", "max_slide_mps": 0.25})
    assert o.ok is planted, o.measured
    if planted:
        assert o.measured["alternation"] == 1.0 and o.measured["slide_p95_mps"] == 0.0
    else:
        assert o.measured["steps"] == 0


def cam_at(p: list[float], heading_deg: float, pitch_deg: float, fov: float = 75.0):
    """A camera at p looking along a heading (clockwise from north) and a pitch."""
    h, a = math.radians(heading_deg), math.radians(pitch_deg)
    fwd = [math.sin(h) * math.cos(a), math.sin(a), -math.cos(h) * math.cos(a)]
    return {"p": p, "bz": [-c for c in fwd], "fov": fov}


def test_camera_frame_distance_and_middle() -> None:
    """The camera 4 m behind the head looking at it frames the hips; one turned away does not."""
    head, hips = [0.0, 1.6, 0.0], [0.0, 0.95, 0.0]
    behind = cam_at([0.0, 1.6, 4.0], 0.0, 0.0)
    frames = [person(t, 0, 0, {"Head": head, "Hips": hips}, behind) for t in (1, 7)]
    rec = record([{"run": 1}], frames, {"a": 0, "b": 1}, {})
    args = {"from": "a", "to": "b", "min_m": 2.5, "max_m": 6.0, "aspect": 16 / 9}
    o = outcome(rec, "camera_frame", args)
    assert o.ok is True and o.measured["head_distance_m"] == [4.0, 4.0]
    away = cam_at([0.0, 1.6, 4.0], 30.0, 0.0)
    frames[1] = person(7, 0, 0, {"Head": head, "Hips": hips}, away)
    rec = record([{"run": 1}], frames, {"a": 0, "b": 1}, {})
    assert outcome(rec, "camera_frame", args).ok is False
    assert outcome(rec, "camera_frame", dict(args, max_m=3.0)).ok is False


def test_look_rate_tilt_and_moves_along_camera() -> None:
    """Heading change per second, pitch limits, and movement along the camera's forward."""
    frames = [
        person(t, 0, 0, {}, cam_at([0, 2, 4], 180.0 * t / 60.0, -60.0 * t / 120.0))
        for t in range(0, 121, 6)
    ]
    rec = record([{"run": 1}], frames, {"a": 0, "b": len(frames) - 1}, {})
    o = outcome(
        rec, "look_rate", {"from": "a", "to": "b", "min_dps": 120, "max_dps": 240}
    )
    assert o.ok is True and o.measured["rate_dps"] == pytest.approx(180.0, abs=0.01)
    tilt = {"from": "a", "to": "b", "min_deg": -60, "max_deg": 30}
    assert (
        outcome(rec, "camera_tilt", dict(tilt, falls=True, min_change_deg=1)).ok is True
    )
    assert (
        outcome(rec, "camera_tilt", dict(tilt, rises=True, min_change_deg=1)).ok
        is False
    )
    assert outcome(rec, "camera_tilt", dict(tilt, min_deg=-50)).ok is False
    cam = cam_at([0, 2, 4], 90.0, -15.0)
    moved = [person(0, 0, 0, {}, cam), person(30, 5.0, 0.6, {}, cam)]
    rec = record([{"run": 1}], moved, {"a": 0, "b": 1}, {})
    args = {"from": "a", "to": "b", "within_deg": 15}
    assert outcome(rec, "moves_along_camera", args).ok is True
    moved[1] = person(30, 3.0, 3.0, {}, cam)
    rec = record([{"run": 1}], moved, {"a": 0, "b": 1}, {})
    assert outcome(rec, "moves_along_camera", args).ok is False


LEAD_1 = {
    "body": "female", "hair": "long", "skin": "#8d5524", "top": "#b03a2e",
    "bottom": "#1c2833", "shoes": "#17202a", "hair_colour": "#1b1b1b", "props": [],
    "scale": 1.0,
}  # fmt: skip


def test_look_and_looks_distinct() -> None:
    """Colours within 0.02 per channel; every AC-11 field; pairs differ enough."""
    near = dict(LEAD_1, top="#b23a2e")
    other = dict(LEAD_1, body="male", hair="buzzed", top="#f4d03f")
    frames = [person(1, 0, 0, {}, look=near), person(2, 0, 0, {}, look=other)]
    rec = record([{"run": 1}], frames, {"a": 0, "b": 1}, {})
    want = {k: LEAD_1[k] for k in ("body", "hair", "skin", "top", "bottom", "shoes")}
    assert outcome(rec, "look", {"mark": "a", "expect": want}).ok is True
    assert outcome(rec, "look", {"mark": "b", "expect": want}).ok is False
    frames[0] = person(
        1, 0, 0, {}, look={k: v for k, v in near.items() if k != "props"}
    )
    rec = record([{"run": 1}], frames, {"a": 0, "b": 1}, {})
    o = outcome(rec, "look", {"mark": "a", "expect": want})
    assert o.ok is False and "props" in o.note
    rec = record([{"run": 1}], [person(1, 0, 0, {}, look=near), person(2, 0, 0, {}, look=other)],
                 {"a": 0, "b": 1}, {})  # fmt: skip
    assert outcome(rec, "looks_distinct", {"marks": ["a", "b"]}).ok is True
    twin = dict(LEAD_1, top="#b53f33")
    rec = record([{"run": 1}], [person(1, 0, 0, {}, look=near), person(2, 0, 0, {}, look=twin)],
                 {"a": 0, "b": 1}, {})  # fmt: skip
    assert outcome(rec, "looks_distinct", {"marks": ["a", "b"]}).ok is False


def test_hips_ratio() -> None:
    """Crouched hips at most 75% of their standing height above the ground."""
    frames = [
        person(1, 0, 0, {"Hips": [0.0, 1.10, 0.0]}),
        person(2, 0, 0, {"Hips": [0.0, 0.80, 0.0]}),
    ]
    rec = record([{"run": 1}], frames, {"up": 0, "down": 1}, {})
    args = {"standing": "up", "crouched": "down", "ground_y": 0.15, "max_ratio": 0.75}
    o = outcome(rec, "hips_ratio", args)
    assert o.ok is True and o.measured["ratio"] == pytest.approx(0.684, abs=0.001)
    assert outcome(rec, "hips_ratio", dict(args, max_ratio=0.6)).ok is False


def test_inset_moves_edges_inwards() -> None:
    """The sampler's inset keeps a rectangle's shape, either winding."""
    square = [[0.0, 0.0], [10.0, 0.0], [10.0, 6.0], [0.0, 6.0]]
    for poly in (square, square[::-1]):
        got = sorted(tuple(round(c, 6) for c in v) for v in inset(poly, 1.0))
        assert got == [(1.0, 1.0), (1.0, 5.0), (9.0, 1.0), (9.0, 5.0)]
