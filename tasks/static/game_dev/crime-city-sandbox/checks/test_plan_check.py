"""The plan checker on the shipped Downtown plan, and the mutations it must catch (no Godot)."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
PLAN = TASK / "common/design/plan/downtown.json"
GDD = TASK / "common/design/GDD.md"
sys.path.insert(0, str(TASK / "scripts"))

from check_plan import Plan, gdd_problems

SHIPPED = json.loads(PLAN.read_text())


def problems(data: dict) -> list[str]:
    return Plan(data).check()


def find(items: list[dict], ident: str) -> dict:
    return next(i for i in items if i["id"] == ident)


def first_signal(d: dict) -> dict:
    return next(i for i in d["intersections"] if i["control"] == "signal")


def oneway_edge(d: dict) -> dict:
    return next(e for e in d["edges"] if e["oneway"])


def safehouse_parcel(d: dict) -> dict:
    return find(d["parcels"], find(d["pois"], "safehouse_downtown")["parcel"])


def drop_phase(d):
    first_signal(d)["signal"]["phases"].pop(0)


def poi_off_ground(d):
    (x0, z0) = d["bounds"]["min"]
    find(d["pois"], "d1_pickup")["p"] = [x0 + 5.0, 0.15, z0 + 5.0]


def reverse_oneway(d):
    oneway_edge(d)["lanes"][0]["dir"] = "ba"


def door_off_wall(d):
    door = safehouse_parcel(d)["interior"]["door"]
    xs = [v[0] for v in safehouse_parcel(d)["poly"]]
    zs = [v[1] for v in safehouse_parcel(d)["poly"]]
    door["p"] = [sum(xs) / 4.0, sum(zs) / 4.0]


def height_out_of_range(d):
    next(p for p in d["parcels"] if p["zoning"] == "commercial")["height_m"] = 99.0


def stop_line_in_box(d):
    leg = next(lg for lg in first_signal(d)["legs"] if lg["approach"])
    leg["approach"]["stop_line_m"] = leg["box_m"] - 1.0


def dead_end(d):
    find(d["nodes"], "pt_east")["kind"] = "junction"


def checkpoint_gap(d):
    d["pois"].remove(find(d["pois"], "r1_cp4"))


def missing_field(d):
    del find(d["pois"], "police_station_downtown")["exit"]


def portal_inside(d):
    node = find(d["nodes"], "pt_east")
    node["p"][0] -= 5.0
    find(d["pois"], "highway_downtown_port")["p"][0] -= 5.0


def portal_names_junction(d):
    find(d["pois"], "highway_downtown_port")["node"] = "j_74"


def curve_out_of_bounds(d):
    find(d["edges"], "e_hw_north")["points"][-1][2] -= 40.0


def crosswalk_past_straight(d):
    edge = find(d["edges"], "e_hw_north")
    a = find(d["nodes"], edge["a"])["p"]
    edge["points"][0] = [a[0] + 1.0, 0.0, a[2] - 2.0]


def district_gap(d):
    core = find(d["districts"], "downtown_core")
    (x0, z0), (x1, z1) = d["bounds"]["min"], d["bounds"]["max"]
    core["poly"] = [[x0, z0], [x1 - 60.0, z0], [x1 - 60.0, z1], [x0, z1]]


def unknown_class(d):
    d["edges"][0]["class"] = "boulevard"


def duplicate_district(d):
    d["districts"].append(copy.deepcopy(find(d["districts"], "downtown_core")))


def bend_lane_mismatch(d):
    """A bend joining a one-lane street to a two-lane one: the extra lane is never fed."""
    bend = next(n for n in d["nodes"] if n["kind"] == "bend")
    edge = next(e for e in d["edges"] if bend["id"] in (e["a"], e["b"]))
    edge["lanes"] += [
        {"id": f"{edge['id']}:ab1", "dir": "ab", "index": 1},
        {"id": f"{edge['id']}:ba1", "dir": "ba", "index": 1},
    ]


MUTATIONS = [
    (drop_phase, "every approach must be green in exactly one phase"),
    (poi_off_ground, "p is not on a road or a block"),
    (reverse_oneway, "one-way edge with lanes not all ab"),
    (door_off_wall, "door not on the footprint outline"),
    (height_out_of_range, "height outside its range"),
    (stop_line_in_box, "stop line inside the box"),
    (dead_end, "no way out at pt_east"),
    (checkpoint_gap, "checkpoint indices not 1..n"),
    (missing_field, "missing ['exit']"),
    (portal_inside, "not on the edge of bounds"),
    (portal_names_junction, "not a portal node"),
    (curve_out_of_bounds, "a point outside the bounds"),
    (crosswalk_past_straight, "past the first straight"),
    (district_gap, "is in no district"),
    (unknown_class, "unknown class boulevard"),
    (duplicate_district, "districts: duplicate id downtown_core"),
    (bend_lane_mismatch, "not strongly connected"),
]


def test_the_shipped_plan_has_no_problems() -> None:
    """downtown.json follows the format, and the GDD's Downtown places are all in it."""
    assert problems(copy.deepcopy(SHIPPED)) == []
    found, pending = gdd_problems(GDD.read_text(), [SHIPPED])
    assert found == []
    assert set(pending) == {"port", "hills"}


@pytest.mark.parametrize(
    ("mutate", "expected"), MUTATIONS, ids=[m.__name__ for m, _ in MUTATIONS]
)
def test_each_mutation_is_caught(mutate, expected: str) -> None:
    """A plan with one deliberate mistake gets a problem that names it."""
    d = copy.deepcopy(SHIPPED)
    mutate(d)
    found = problems(d)
    assert any(expected in p for p in found), found


def test_the_plan_is_what_the_generator_writes(tmp_path: Path) -> None:
    """common/design/plan/downtown.json is scripts/gen_plan.py's output."""
    out = tmp_path / "downtown.json"
    subprocess.run(
        [sys.executable, str(TASK / "scripts/gen_plan.py"), "--out", str(out)],
        check=True,
        capture_output=True,
    )
    assert out.read_text() == PLAN.read_text()


def test_the_format_examples_name_what_the_plan_has() -> None:
    """Every id FORMAT.md's examples quote exists in downtown.json, which they are taken from."""
    text = (TASK / "common/design/plan/FORMAT.md").read_text()
    quoted = set(re.findall(r'"id": "([^"]+)"', text))
    d = SHIPPED
    ids = {x["id"] for key in ("nodes", "edges", "intersections", "blocks", "sidewalks",
                               "parcels", "pois", "districts", "turfs") for x in d[key]}  # fmt: skip
    ids |= {ln["id"] for e in d["edges"] for ln in e["lanes"]}
    for it in d["intersections"]:
        for leg in it["legs"]:
            ids |= {(leg.get(k) or {}).get("id") for k in ("crosswalk", "approach")}
    elsewhere = {
        "bay",
        "hw_downtown_port",
        "main",
    }  # the water and links examples, a room
    assert quoted - ids - elsewhere == set()
