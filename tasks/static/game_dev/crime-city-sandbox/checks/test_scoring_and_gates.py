"""Reward arithmetic and the static gate (no Godot)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from verifier import gates, scoring

TASK = Path(__file__).resolve().parent.parent
SELFTEST = TASK / "tests/selftest/project"
C = scoring.Check


def test_instance_score_weights_assertions() -> None:
    """s_i is the weighted share of assertions that held."""
    checks = [
        C("p", "standing", 0, True),
        C("a", "assert", 0.75, True),
        C("b", "assert", 0.25, False),
    ]
    assert scoring.instance_score(checks) == (0.75, None)


def test_standing_or_precondition_failure_zeroes_the_instance() -> None:
    """A failed standing check or precondition zeroes s_i and says which."""
    base = [C("a", "assert", 1.0, True)]
    assert scoring.instance_score([C("process", "standing", 0, False), *base]) == (
        0.0,
        "standing:process",
    )
    assert scoring.instance_score([C("saved", "pre", 0, None), *base]) == (
        0.0,
        "pre:saved",
    )


def test_family_denominator_is_fixed() -> None:
    """A family's missing instances count 0 within its fixed N_f."""
    res = [scoring.InstanceResult("x", "H", 1.0, None)]
    assert scoring.family_scores(res, {"H": {"w": 1, "n": 4}}) == {"H": 0.25}
    with pytest.raises(ValueError):
        scoring.family_scores(res * 2, {"H": {"w": 1, "n": 1}})


def test_reward_is_zero_when_a_gate_fails() -> None:
    """Any failed gate zeroes the reward; weights are normalised otherwise."""
    fam = {"A": {"w": 0.3, "n": 1}, "B": {"w": 0.1, "n": 1}}
    assert (
        scoring.total_reward(
            {"static": True, "import": True, "boot": True}, fam, {"A": 1.0, "B": 0.0}
        )
        == 0.75
    )
    assert (
        scoring.total_reward(
            {"static": True, "import": False, "boot": True}, fam, {"A": 1.0, "B": 1.0}
        )
        == 0.0
    )


def test_retry_budget_is_fifteen_percent() -> None:
    """At most 15% of instances (rounded down) may rerun."""
    assert [scoring.retry_budget(n) for n in (6, 7, 20, 170)] == [0, 1, 3, 25]


def test_integration_gap() -> None:
    """Foundation minus integration families; None without all eight."""
    s = {f: 1.0 for f in "ABHI"} | {f: 0.5 for f in "EFLM"}
    assert scoring.integration_gap(s) == 0.5
    assert scoring.integration_gap({"A": 1.0}) is None


def test_selftest_project_passes_the_static_gate() -> None:
    """Our own project has Jolt, the settings, all 28 actions with both bindings."""
    g = gates.static_gate(SELFTEST, ["Grand Theft Auto", "Vice City"])
    assert g.passed, g.problems


@pytest.mark.parametrize(
    ("mutation", "problem"),
    [
        (lambda t: t.replace('"Jolt Physics"', '"GodotPhysics3D"'), "not Jolt"),
        (lambda t: t.replace("common/physics_jitter_fix=0.0\n", ""), "jitter fix"),
        (
            lambda t: t.replace(
                'rendering_method="gl_compatibility"', 'rendering_method="forward_plus"'
            ),
            "Compatibility",
        ),
        (
            lambda t: t.replace(
                "3d/run_on_separate_thread=false", "3d/run_on_separate_thread=true"
            ),
            "separate thread",
        ),
        (lambda t: t.replace("horn={", "honk={"), "action horn is missing"),
        (
            lambda t: _drop_pad_binding(t, "pause"),
            "action pause has no gamepad binding",
        ),
    ],
)
def test_static_gate_catches_settings_and_actions(
    tmp_path: Path, mutation, problem: str
) -> None:
    """Each broken setting or binding fails the gate with its reason."""
    dst = tmp_path / "p"
    shutil.copytree(SELFTEST, dst)
    pg = dst / "project.godot"
    pg.write_text(mutation(pg.read_text()))
    g = gates.static_gate(dst, [])
    assert not g.passed and any(problem in p for p in g.problems), g.problems


def _drop_pad_binding(text: str, action: str) -> str:
    """project.godot text with the gamepad events of one action removed."""
    head, rest = text.split(f"{action}={{", 1)
    block, tail = rest.split("\n}", 1)
    kept = "\n".join(ln for ln in block.split("\n") if "InputEventJoypad" not in ln)
    return f"{head}{action}={{{kept}\n}}{tail}"


def test_static_gate_refuses_native_code_and_csharp(tmp_path: Path) -> None:
    """A .gdextension, a library or a C# file fails the gate (PF-1)."""
    dst = tmp_path / "p"
    shutil.copytree(SELFTEST, dst)
    (dst / "native").mkdir()
    (dst / "native" / "x.gdextension").write_text("[configuration]\n")
    (dst / "Player.cs").write_text("class Player {}\n")
    g = gates.static_gate(dst, [])
    assert not g.passed and "native" in g.problems[0]


def test_denylist_matches_names_and_text_but_not_the_vendor_library(
    tmp_path: Path,
) -> None:
    """Denylisted names in file names or text fail; the vendor library is not scanned."""
    dst = tmp_path / "p"
    shutil.copytree(SELFTEST, dst)
    (dst / "assets/vendor").mkdir(parents=True)
    (dst / "assets/vendor/vice_city_road.txt").write_text("Vice City\n")
    assert gates.static_gate(dst, ["Vice City"]).passed
    (dst / "scripts").mkdir()
    (dst / "scripts/hud.gd").write_text('var title = "welcome to vice city"\n')
    g = gates.static_gate(dst, ["Vice City"])
    assert not g.passed and "scripts/hud.gd" in g.problems[-1]
    (dst / "scripts/hud.gd").write_text('var title = "Merrow Bay"\n')
    (dst / "scripts/vice_city_map.gd").write_text("\n")
    assert not gates.static_gate(dst, ["Vice City"]).passed


def test_denylist_needs_whole_words() -> None:
    """A denylist entry does not match inside a longer word."""
    pat = gates.denylist_pattern(["GTA", "# a comment"])
    assert pat is not None
    assert pat.search("play GTA now") and not pat.search("vegetables")


def test_project_settings_parser_keeps_multiline_values() -> None:
    """Multi-line values (the input map) are joined; plain values keep their text."""
    text = '[a]\n\nx=1\ny={\n"k": [1,\n2]\n}\nz="s"\n'
    s = gates.project_settings(text)
    assert s["a/x"] == "1" and s["a/z"] == '"s"' and s["a/y"].count("\n") == 3
