"""Anchor resolution against the Downtown plan, and drawing instances from templates."""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import pytest
from qakit.plan import AnchorError, Plan, heading_of

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "scripts"))
PLAN = Plan.load(TASK / "common/design/plan/downtown.json")


def test_headings_follow_the_plan_convention() -> None:
    """0 is north (-z), 90 east (+x), 180 south, 270 west."""
    assert [round(heading_of(*d)) for d in ((0, -1), (1, 0), (0, 1), (-1, 0))] == [
        0,
        90,
        180,
        270,
    ]


def test_lane_points_lie_beside_their_edge() -> None:
    """Every lane point sits its lane offset to the right of travel, between the nodes."""
    for lane_id, (edge, lane) in PLAN.lanes.items():
        length = PLAN.lane_length(lane_id)
        assert length > 0, lane_id
        if edge.get("points"):
            continue
        a = PLAN.nodes[edge["a"]]["p"]
        b = PLAN.nodes[edge["b"]]["p"]
        start, end = (a, b) if lane["dir"] == "ab" else (b, a)
        dx, dz = end[0] - start[0], end[2] - start[2]
        n = math.hypot(dx, dz)
        for s in (0.0, length / 2, length):
            pl = PLAN.lane_point(lane_id, s)
            rel = (pl.p[0] - start[0], pl.p[2] - start[2])
            side = (rel[0] * -dz + rel[1] * dx) / n  # right of travel is positive
            assert abs(side - PLAN.lane_offset(edge, lane)) < 1e-6, lane_id
            assert abs(pl.heading_deg - heading_of(dx, dz)) < 1e-6


def test_before_m_counts_back_from_the_stop_line() -> None:
    """An intersection anchor d metres before the stop line is d before the lane's end."""
    inter = next(i for i in PLAN.data["intersections"] if i.get("control") == "signal")
    leg = next(lg for lg in inter["legs"] if lg.get("approach"))
    edge = PLAN.edges[leg["edge"]]
    lane = next(ln for ln in edge["lanes"] if ln["dir"] == leg["approach"]["dir"])
    end = PLAN.lane_point(lane["id"], PLAN.lane_length(lane["id"]))
    pl = PLAN.resolve(
        {
            "intersection": inter["id"],
            "approach": 0,
            "before_m": 30,
            "lane_index": lane["index"],
        }
    )
    back = PLAN.lane_point(lane["id"], PLAN.lane_length(lane["id"]) - 30)
    assert math.dist(pl.p, back.p) < 1e-6  # 30 m back along the lane, curves included
    assert math.dist((pl.p[0], pl.p[2]), (end.p[0], end.p[2])) <= 30 + 1e-6


def test_poi_and_front_m() -> None:
    """A point of interest resolves to its point; front_m moves along its heading."""
    poi = PLAN.pois["safehouse_downtown"]
    base = PLAN.resolve({"poi": poi["id"]})
    ahead = PLAN.resolve({"poi": poi["id"], "front_m": 4})
    assert base.p == tuple(poi["p"])
    assert (
        abs(math.dist(base.p, ahead.p) - 4) < 1e-6
        and base.heading_deg == poi["heading_deg"]
    )


def test_bad_anchors_are_refused() -> None:
    """Unknown ids, s past the lane end and unsupported kinds raise AnchorError."""
    lane_id = next(iter(PLAN.lanes))
    for anchor in (
        {"poi": "nowhere"},
        {"lane": lane_id, "s": 1e6},
        {"sidewalk": "sw_nowhere", "s": 1},
        {"corner_of": "j_10", "approach": 0},
        "x",
    ):
        with pytest.raises(AnchorError):
            PLAN.resolve(anchor)


def test_sidewalk_points_follow_the_ring() -> None:
    """A sidewalk anchor is on its ring at its elevation, and s wraps around the ring."""
    sw = PLAN.sidewalks["sw_00"]
    ring = sw["ring"]
    first = PLAN.resolve({"sidewalk": "sw_00", "s": 0})
    assert first.p == (ring[0][0], sw["elevation_m"], ring[0][1])
    side = math.dist(ring[0], ring[1])
    corner = PLAN.resolve({"sidewalk": "sw_00", "s": side})
    assert math.dist((corner.p[0], corner.p[2]), ring[1]) < 1e-9
    total = sum(math.dist(a, b) for a, b in zip(ring, ring[1:] + ring[:1]))
    again = PLAN.resolve({"sidewalk": "sw_00", "s": total + 2.5})
    once = PLAN.resolve({"sidewalk": "sw_00", "s": 2.5})
    assert math.dist(again.p, once.p) < 1e-9 and again.heading_deg == once.heading_deg


def test_expand_fills_every_value_and_records_the_draw() -> None:
    """A template plus a draw gives an explicit play; the same draw gives the same play."""
    from make_instances import expand

    template = {
        "format": "qa-play/1",
        "name": "people.locomotion/same-tick",
        "template": "people.locomotion",
        "family": "A",
        "role": "solo",
        "params": {"v": {"randint": [1, 999]}, "d": {"uniform": [2, 6], "round": 2}},
        "anchors": {"spawn": {"poi": "safehouse_downtown", "front_m": "$d"}},
        "args": ["--role=solo", "--variation=$v"],
        "steps": [
            {"dev": [["world.reset", {"variation": "$v"}]]},
            {"dev": [["player.spawn", {"at": "$anchor:spawn"}]]},
        ],
        "expect": [{"id": "x", "check": "moved", "args": {"from": "a", "to": "b"}}],
    }
    a = expand(template, random.Random("k:1"), PLAN)
    b = expand(template, random.Random("k:1"), PLAN)
    assert a == b and "$" not in json.dumps(a)
    assert a["steps"][0]["dev"][0][1]["variation"] == a["drawn"]["v"]
    assert a["steps"][1]["dev"][0][1]["at"] == a["anchors"]["spawn"]["p"]
    assert a["args"][1] == f"--variation={a['drawn']['v']}"
    c = expand(template, random.Random("k:2"), PLAN)
    assert c["name"] != a["name"]
