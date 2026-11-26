"""Release instances against their playtests, without Godot: scripts/check_disjoint.py on
tiny synthetic plays (one instance per way of repeating a playtest, and one that repeats
nothing; for the vehicle rules also a near miss that must not count), and the "expr"
parameters of scripts/make_instances.py that the instance templates compute their geometry
with."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "scripts"))

import check_disjoint as cd
from make_instances import draw_params, eval_expr

# ---------------------------------------------------------------- check_disjoint.py
# A made-up playtest: a reset, a lead, a wall, a spawn, then a signal-style watch.
TEST = {
    "format": "qa-play/1",
    "name": "demo.family/label",
    "template": "demo.family",
    "role": "solo",
    "args": ["--role=solo", "--variation=3"],
    "steps": [
        {"dev": [["world.reset", {"variation": 3}]]},
        {"dev": [["prop.spawn", {"kind": "wall", "at": [10.0, 0.0, 10.0], "size": [4.0, 1.5, 2.0]}]]},
        {"dev": [["player.spawn", {"lead": "lead_2", "at": [0.0, 0.0, 0.0]}]]},
        {"dev": [["player.spawn", {"lead": "lead_5", "at": [0.0, 0.0, 0.0]}]]},
        {"run": 4},
        {"mark": "a"},
        {"run": 100},
        {"mark": "b"},
    ],
    "expect": [
        {"id": "w", "check": "signal_program", "args": {"from": "a", "to": "b", "reset_step": 0}}
    ],
}  # fmt: skip


def instance(**change: object) -> dict:
    """An instance of TEST that repeats nothing, with the changes asked for."""
    inst = json.loads(json.dumps(TEST))
    inst["name"] = "demo.family/label/0a1b2c3d"
    inst["args"] = ["--role=solo", "--variation=40"]
    inst["steps"][0] = {"dev": [["world.reset", {"variation": 40}]]}
    inst["steps"][1]["dev"][0][1].update(at=[30.0, 0.0, 30.0], size=[4.0, 1.7, 2.0])
    inst["steps"][2]["dev"][0][1].update(lead="lead_5", at=[5.0, 0.0, 5.0])
    inst["steps"][3]["dev"][0][1].update(lead="lead_2", at=[5.0, 0.0, 5.0])
    inst["steps"][4] = {"run": 50}
    for key, value in change.items():
        step, cmd, field = key.split("__") if "__" in key else (key, None, None)
        if cmd is None:
            inst["steps"][int(step[1:])] = value
        else:
            inst["steps"][int(step[1:])]["dev"][int(cmd[1:])][1][field] = value
    return inst


def test_an_instance_that_changes_everything_repeats_nothing() -> None:
    assert cd.repeats(instance(), TEST, None, None) == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"s0__c0__variation": 3.0}, "variation 3"),
        ({"s2__c0__at": [0.6, 5.0, -0.6]}, "m from one of the playtest's"),
        ({"s1__c0__at": [9.5, 0.0, 10.2]}, "m from one of the playtest's"),
        ({"s2__c0__lead": "lead_2", "s3__c0__lead": "lead_5"}, "the same leads"),
        ({"s1__c0__size": [9.0, 1.505, 0.3]}, "a wall as high"),
        ({"s4": {"run": 3}}, "starts watching"),
    ],
)
def test_each_way_of_repeating_is_caught(change: dict, reason: str) -> None:
    why = cd.repeats(instance(**change), TEST, None, None)
    assert len(why) == 1 and reason in why[0], why


def test_the_same_steps_repeat_and_unknown_waits_match_nothing() -> None:
    same = dict(TEST, name="demo.family/label/ffffffff", args=["--variation=9"])
    assert any("the same steps" in w for w in cd.repeats(same, TEST, None, None))
    waits = instance(s4={"wait_for": {"event": "saved", "max_ticks": 4}})
    assert cd.repeats(waits, TEST, None, None) == []


def test_defaults_count_and_malformed_values_do_not() -> None:
    bare = instance()
    bare["args"] = ["--role=solo"]  # starts on the default variation, 1
    test = dict(TEST, args=["--role=solo"])
    assert "variation 1" in cd.repeats(bare, test, None, None)[0]
    odd = instance(s0__c0__variation=[3], s2__c0__at="player", s3__c0__at=[0, 0])
    assert cd.repeats(odd, TEST, None, None) == []


def test_anchors_resolve_against_the_plan() -> None:
    from qakit.plan import Plan

    plan = Plan.load(TASK / "common/design/plan/downtown.json")
    test = json.loads(json.dumps(TEST))
    test["steps"][2]["dev"][0][1]["at"] = {"poi": "plaza_central"}
    near = instance(s2__c0__at={"poi": "plaza_central", "front_m": 0.5})
    far = instance(s2__c0__at={"poi": "plaza_central", "front_m": 3.0})
    assert "m from one of the playtest's" in cd.repeats(near, test, plan, plan)[0]
    assert cd.repeats(far, test, plan, plan) == []


# A made-up vehicle playtest: a parked car (heading east, so right is +z), the player beside
# it to its right and then its left, both ahead of its centre, then a drive at two free
# speeds (45 and 30 km/h) and two the design document fixes (60 and 8 km/h).
VTEST = {
    "format": "qa-play/1",
    "name": "demo.cars/label",
    "template": "demo.cars",
    "role": "solo",
    "args": ["--role=solo", "--variation=3"],
    "steps": [
        {"dev": [["world.reset", {"variation": 3}]]},
        {"dev": [["vehicle.spawn", {"model": "sedan", "at": [0.0, 0.0, 0.0], "heading": 90, "driver": "none", "damage": 0.2}]]},
        {"dev": [["player.spawn", {"at": [0.6, 0.0, 2.4]}]]},
        {"dev": [["player.spawn", {"at": [0.6, 0.0, -2.4]}]]},
        {"dev": [["vehicle.spawn", {"model": "van", "at": [50.0, 0.0, 0.0], "heading": 90, "driver": "player"}]]},
        {"wait_for": {"entity": {"kind": "vehicle", "min_kmh": 45.0}, "max_ticks": 600}},
        {"cruise": {"entity": {"kind": "vehicle"}, "kmh": 30.0, "ticks": 60}},
        {"wait_for": {"entity": {"kind": "vehicle", "min_kmh": 60.0}, "max_ticks": 600}},
        {"cruise": {"entity": {"kind": "vehicle"}, "kmh": 8.0, "ticks": 60}},
    ],
    "expect": [],
}  # fmt: skip


def vehicle_instance(**change: object) -> dict:
    """An instance of VTEST that repeats nothing (another place, other models, a stand-off
    behind the car, other free speeds, another damage), with the changes asked for (keys
    as in instance())."""
    inst = json.loads(json.dumps(VTEST))
    inst["name"] = "demo.cars/label/0a1b2c3d"
    inst["args"] = ["--role=solo", "--variation=40"]
    steps = inst["steps"]
    steps[0] = {"dev": [["world.reset", {"variation": 40}]]}
    steps[1]["dev"][0][1].update(model="suv", at=[100.0, 0.0, 100.0], damage=0.3)
    # right of the car and behind its centre, then left of it and ahead
    steps[2]["dev"][0][1].update(at=[99.2, 0.0, 102.5])
    steps[3]["dev"][0][1].update(at=[100.9, 0.0, 97.3])
    steps[4]["dev"][0][1].update(model="taxi", at=[150.0, 0.0, 100.0])
    steps[5]["wait_for"]["entity"]["min_kmh"] = 52.0
    steps[6]["cruise"]["kmh"] = 33.0
    for key, value in change.items():
        step, cmd, field = key.split("__") if "__" in key else (key, None, None)
        if cmd is None:
            steps[int(step[1:])] = value
        else:
            steps[int(step[1:])]["dev"][int(cmd[1:])][1][field] = value
    return inst


def speed_at(step: int, kmh: float) -> dict:
    """A change of the speed of a wait_for (min_kmh) or cruise step of VTEST."""
    s = json.loads(json.dumps(VTEST["steps"][step]))
    if "cruise" in s:
        s["cruise"]["kmh"] = kmh
    else:
        s["wait_for"]["entity"]["min_kmh"] = kmh
    return {f"s{step}": s}


def test_a_vehicle_instance_that_changes_everything_repeats_nothing() -> None:
    assert cd.repeats(vehicle_instance(), VTEST, None, None) == []
    assert cd.models(VTEST) == ["sedan", "van"]
    assert cd.speeds(VTEST) == [45.0, 30.0]
    assert cd.stand_offs(VTEST, None) == [("right", "ahead"), ("left", "ahead")]
    assert cd.damages(VTEST) == [0.2]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"s1__c0__model": "sedan", "s4__c0__model": "van"}, "the same models"),
        (speed_at(5, 45.4), "a speed of 45.4 km/h"),
        (speed_at(6, 29.5), "a speed of 29.5 km/h"),
        ({"s2__c0__at": [100.8, 0.0, 102.5]}, "the same sides and ends"),
        ({"s1__c0__damage": 0.204}, "at damage 0.204"),
    ],
)
def test_each_vehicle_rule_catches_its_repeat(change: dict, reason: str) -> None:
    why = cd.repeats(vehicle_instance(**change), VTEST, None, None)
    assert len(why) == 1 and reason in why[0], why


# In order: the same models in another order; one model in common; a speed 0.6 km/h off;
# the fixed speeds (every instance's); left and behind, then left and ahead; right and ahead
# but 4.5 m off (not beside the car); a damage 0.006 off; no damage.
@pytest.mark.parametrize(
    "change",
    [
        {"s1__c0__model": "van", "s4__c0__model": "sedan"},
        {"s4__c0__model": "van"},
        speed_at(5, 45.6),
        speed_at(7, 60.0) | speed_at(8, 8.0),
        {"s2__c0__at": [99.2, 0.0, 97.5]},
        {"s2__c0__at": [100.6, 0.0, 104.5]},
        {"s1__c0__damage": 0.206},
        {"s1__c0__damage": 0.0},
    ],
)
def test_near_misses_are_not_repeats(change: dict) -> None:
    assert cd.repeats(vehicle_instance(**change), VTEST, None, None) == []


def test_stand_offs_follow_the_parked_vehicle_and_its_anchor_heading() -> None:
    from qakit.plan import Plan

    plan = Plan.load(TASK / "common/design/plan/downtown.json")
    lane = {"lane": "e_34_35:ab0", "s": 40}  # heading 180: right of the car is -x
    p = plan.resolve(lane).p
    play = json.loads(json.dumps(VTEST))
    play["steps"][1]["dev"][0][1] = {"model": "sedan", "at": lane, "driver": "none"}
    play["steps"][2]["dev"][0][1]["at"] = [p[0] - 2.4, 0.0, p[2] + 0.6]
    play["steps"][3]["dev"][0][1]["at"] = [p[0] + 2.4, 0.0, p[2] + 0.6]
    assert cd.stand_offs(play, plan) == [("right", "ahead"), ("left", "ahead")]
    # nobody stands beside a car the player drives off in
    driven = json.loads(json.dumps(play))
    driven["steps"][1]["dev"][0][1]["driver"] = "player"
    assert cd.stand_offs(driven, plan) == []


def write_set(folder: Path, inst: dict) -> Path:
    """A playtest folder with TEST and a manifest with one instance; returns the manifest."""
    (folder / "tests").mkdir(parents=True)
    (folder / "set" / "plays").mkdir(parents=True)
    (folder / "tests" / "demo.json").write_text(json.dumps(TEST))
    (folder / "set" / "plays" / "i.json").write_text(json.dumps(inst))
    manifest = folder / "set" / "instances.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "qa-instances/1",
                "families": {"A": {"w": 1.0, "n": 1}},
                "instances": [{"file": "plays/i.json", "family": "A"}],
            }
        )
    )
    return manifest


@pytest.mark.parametrize(("inst", "code"), [(instance(), 0), (instance(s0={"run": 1}, s1={"run": 1}) | {"args": ["--variation=3"]}, 1)])  # fmt: skip
def test_the_command_line_fails_on_a_repeat(
    tmp_path: Path, inst: dict, code: int
) -> None:
    manifest = write_set(tmp_path, inst)
    out = subprocess.run(
        [sys.executable, str(TASK / "scripts/check_disjoint.py"), "--manifest", str(manifest),
         "--playtests", str(tmp_path / "tests"), "--json", str(tmp_path / "rows.json")],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert out.returncode == code, out.stdout + out.stderr
    rows = json.loads((tmp_path / "rows.json").read_text())
    assert rows[0]["playtest"] == "demo.family/label"
    assert bool(rows[0]["repeats"]) == bool(code)


def test_an_instance_without_a_playtest_is_listed_not_compared(tmp_path: Path) -> None:
    manifest = write_set(tmp_path, dict(instance(), name="other.family/x/12345678"))
    rows = cd.check_manifest(manifest, tmp_path / "tests", TASK / "common/design/plan")
    assert rows[0]["playtest"] is None and rows[0]["repeats"] == []


# ---------------------------------------------------------------- make_instances.py "expr"
def test_expr_is_arithmetic_over_parameters() -> None:
    values = {"a": 2, "b": 0.5, "o.f": -1.0}
    assert eval_expr("$a * ($b + 1) - $o.f / 4", values) == 3.25
    assert eval_expr("max($a, 3) + min(1, $b) + abs($o.f)", values) == 4.5
    assert eval_expr("-$a", values) == -2


@pytest.mark.parametrize(
    "text",
    ["__import__('os')", "$a ** 2", "$a if $b else 1", "$nope + 1", "$a / 0", "[1][0]",
     "$s + 1", "min()"],
)  # fmt: skip
def test_expr_refuses_anything_else(text: str) -> None:
    with pytest.raises(ValueError):
        eval_expr(text, {"a": 2, "b": 1, "s": "text"})


def test_expr_draws_nothing_and_rounds() -> None:
    plain = {
        "o": {"choice": [{"f": 1.5}, {"f": -2.5}]},
        "u": {"uniform": [0, 1], "round": 4},
        "n": {"randint": [1, 9]},
        "t": {"sum": ["n", 10]},
    }
    more = dict(
        plain,
        x={"expr": "$y * 2", "round": 2},
        y={"expr": "$o.f + $u * $t"},
        k={"expr": "$t * 60 + 0.4", "round": 0},
    )
    a = draw_params(plain, random.Random("d:1"))
    b = draw_params(more, random.Random("d:1"))
    assert {k: b[k] for k in a} == a
    assert b["y"] == round(a["o.f"] + a["u"] * a["t"], 3)
    assert b["x"] == round(b["y"] * 2, 2)
    assert b["k"] == a["t"] * 60 and isinstance(b["k"], int)


def test_expr_cycles_and_unknown_names_are_refused() -> None:
    with pytest.raises(ValueError, match="cycle"):
        draw_params({"x": {"expr": "$y"}, "y": {"expr": "$x"}}, random.Random(1))
    with pytest.raises(ValueError, match="cycle"):
        draw_params({"x": {"expr": "$missing + 1"}}, random.Random(1))
