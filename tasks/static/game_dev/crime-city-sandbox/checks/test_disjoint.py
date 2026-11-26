"""Release instances against their playtests, without Godot: scripts/check_disjoint.py on
tiny synthetic plays (one instance per way of repeating a playtest, and one that repeats
nothing), and the "expr" parameters of scripts/make_instances.py that the instance
templates compute their geometry with."""

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
