"""WD-8's plan swap without Godot: the generator's drawn layouts, the plan-swap playtest,
and the grader running an instance on the plan folder its manifest entry names."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from qakit.play import parse_play, substitute
from verifier import grade

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "scripts"))

import gen_plan
from check_plan import Plan as CheckedPlan
from check_plan import gdd_problems
from make_plan_swap import add_to_manifest, plan_swap
from make_playtests import plan_compliance

PLANS = TASK / "common/design/plan"
SHIPPED = json.loads((PLANS / "downtown.json").read_text())
GDD = (TASK / "common/design/GDD.md").read_text()
# Draws for these checks only, large enough that a plan cannot hold one by chance.
DRAWS = [10**30 + 7, 10**30 + 8, 10**30 + 9]


def drawn(draw: int) -> dict:
    return gen_plan.build_plan(gen_plan.draw_layout(draw), draw)


def kinds(plan: dict) -> dict:
    return {p["id"]: p["kind"] for p in plan["pois"]}


def portals(plan: dict) -> list:
    return sorted((p["node"], p["link"]) for p in plan["pois"] if p["kind"] == "portal")


@pytest.mark.parametrize("draw", DRAWS)
def test_a_drawn_layout_holds_with_the_same_points_of_interest(draw: int) -> None:
    """A drawn Downtown follows the format, has every point of interest of the shipped
    plan (same ids and kinds, the GDD's included) and the same portals, and never names
    its draw."""
    plan = drawn(draw)
    assert CheckedPlan(plan).check() == []
    assert gdd_problems(GDD, [plan])[0] == []
    assert kinds(plan) == kinds(SHIPPED)
    assert portals(plan) == portals(SHIPPED)
    assert str(draw) not in json.dumps(plan)


@pytest.mark.parametrize("draw", DRAWS)
def test_a_drawn_layout_moves_every_junction_and_parcel(draw: int) -> None:
    """No junction and no parcel of a drawn Downtown is where the shipped plan has one."""
    plan = drawn(draw)
    junctions = {tuple(n["p"]) for n in SHIPPED["nodes"] if n["kind"] != "portal"}
    assert not [n["id"] for n in plan["nodes"] if tuple(n["p"]) in junctions]
    parcels = {json.dumps(p["poly"]) for p in SHIPPED["parcels"]}
    assert not [p["id"] for p in plan["parcels"] if json.dumps(p["poly"]) in parcels]


def test_a_draw_always_gives_the_same_plan(tmp_path: Path) -> None:
    """The command line writes what the same draw gives in process, every time; a random
    layout needs a draw."""
    out = tmp_path / "downtown.json"
    draw_file = tmp_path / "draw.json"
    draw_file.write_text(json.dumps({"draw": DRAWS[0]}))
    cmd = [sys.executable, str(TASK / "scripts/gen_plan.py"), "--layout", "random"]
    subprocess.run(
        [*cmd, "--draw-file", str(draw_file), "--out", str(out)],
        check=True,
        capture_output=True,
    )
    assert out.read_text() == json.dumps(drawn(DRAWS[0]), indent=1) + "\n"
    assert drawn(DRAWS[0]) == drawn(DRAWS[0])
    refused = subprocess.run(
        [*cmd, "--out", str(out)], check=False, capture_output=True
    )
    assert refused.returncode == 2


def test_the_plan_swap_play_is_plan_compliance_on_another_plan() -> None:
    """On the shipped plan, world.plan_swap differs from world.plan_compliance/downtown only
    in its name, template, rules (WD-8 added) and description."""
    swap, base = plan_swap(SHIPPED, "x").raw, plan_compliance().raw
    assert {k for k in base.keys() | swap.keys() if base.get(k) != swap.get(k)} == {
        "name",
        "template",
        "rules",
        "about",
    }
    assert (swap["name"], swap["template"]) == ("world.plan_swap/x", "world.plan_swap")
    assert swap["rules"] == ["WD-8", *base["rules"]]


def test_the_plan_swap_play_reads_the_plan_it_is_given() -> None:
    """Its rays and expected heights come from the other plan: one roof height per built
    parcel of that plan, one ray per point of interest."""
    plan = drawn(DRAWS[1])
    raw = plan_swap(plan, "y").raw
    parse_play(raw)
    roofs = next(e for e in raw["expect"] if e["id"] == "roofs")
    built = [p for p in plan["parcels"] if p["zoning"] in gen_plan.BUILT]
    want = {round(p["base_m"] + p["height_m"], 3) for p in built}
    assert set(roofs["args"]["y"]) == want
    assert [g[0] for g in roofs["args"]["groups"]] == sorted(p["id"] for p in built)
    pois = next(e for e in raw["expect"] if e["id"] == "pois")
    assert pois["args"]["rays"]["count"] == len(plan["pois"])


def test_the_manifest_gains_one_plan_swap_entry(tmp_path: Path) -> None:
    """--manifest adds the instance with its plan folder, replaces an earlier plan-swap
    entry on the same folder, and keeps the family's count in step."""
    manifest = tmp_path / "instances.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "qa-instances/1",
                "release": "t",
                "families": {"H": {"w": 0.07, "n": 1}, "K": {"w": 0.04, "n": 1}},
                "instances": [
                    {"file": "plays/world.replay.a.json", "family": "H"},
                    {"file": "plays/persistence.b.json", "family": "K"},
                ],
            }
        )
    )
    plans = tmp_path / "plans"
    first = add_to_manifest(
        manifest, tmp_path / "plays/world.plan_swap.downtown-1.json", plans, "H"
    )
    assert first == {
        "file": "plays/world.plan_swap.downtown-1.json",
        "family": "H",
        "plans": "plans",
    }
    add_to_manifest(
        manifest, tmp_path / "plays/world.plan_swap.downtown-2.json", plans, "H"
    )
    data = json.loads(manifest.read_text())
    assert [i["file"] for i in data["instances"]] == [
        "plays/world.replay.a.json",
        "plays/persistence.b.json",
        "plays/world.plan_swap.downtown-2.json",
    ]
    assert data["families"] == {"H": {"w": 0.07, "n": 2}, "K": {"w": 0.04, "n": 1}}


class Ran(Exception):
    """Raised by the stand-in for run_play once it has recorded its arguments."""


def test_an_instance_runs_on_the_plan_folder_its_entry_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The game processes of an entry with "plans" get --plan-dir=<a fresh copy of that
    folder>; every other entry keeps the shipped plans; a missing folder is the grader's
    own error."""
    folder = tmp_path / "private"
    (folder / "plays").mkdir(parents=True)
    (folder / "plans").mkdir()
    (folder / "plans" / "downtown.json").write_text('{"format": "city-plan/1"}\n')
    play = {
        "format": "qa-play/1",
        "name": "world.plan_swap/t",
        "template": "world.plan_swap",
        "role": "solo",
        "args": ["--role=solo", "--save-dir={save_dir}"],
        "steps": [{"run": 1}],
    }
    (folder / "plays" / "t.json").write_text(json.dumps(play))
    manifest = folder / "instances.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "qa-instances/1",
                "release": "t",
                "families": {"H": {"w": 0.07, "n": 2}},
                "instances": [
                    {"file": "plays/t.json", "family": "H", "plans": "plans"},
                    {"file": "plays/t.json", "family": "H"},
                ],
            }
        )
    )
    cfg = grade.GradeConfig(
        project=tmp_path,
        out=tmp_path / "out",
        work=tmp_path / "work",
        godot="godot",
        library=tmp_path / "lib",
        instances=manifest,
        selftest_dir=tmp_path,
        plans=PLANS,
    )
    g = grade.Grading(cfg, time.monotonic())
    g.families, g.manifest_instances = grade.load_manifest(manifest)
    seen = []

    def run_play(play, _game, _godot, work, _options, write_traces=True, plans=None):
        folders = {"save_dir": work / "run0" / "saves", "home": work / "run0" / "home"}
        if plans is not None:
            folders["plans"] = Path(plans)
        seen.append((work, plans, substitute(play.args, folders)))
        raise Ran

    monkeypatch.setattr(grade, "run_play", run_play)
    monkeypatch.setattr(grade, "verify_telemetry", lambda *_: [])

    def once(entry: dict, work: Path) -> None:
        with pytest.raises(Ran):
            grade.grade_instance(g, entry, tmp_path, lambda *_: None, None, work)

    own, shipped = g.manifest_instances
    (folder / "plans" / "downtown.json").chmod(0o600)  # as root-only private inputs
    (folder / "plans").chmod(0o700)
    once(own, cfg.work / "000")
    work, plans, args = seen[-1]
    assert plans == work / "plans"
    assert (plans / "downtown.json").read_text() == '{"format": "city-plan/1"}\n'
    assert f"--plan-dir={plans}" in args
    assert plans.stat().st_mode & 0o777 == 0o755
    assert (plans / "downtown.json").stat().st_mode & 0o777 == 0o644
    (plans / "stray.json").write_text("{}")
    once(own, cfg.work / "000")
    assert sorted(p.name for p in seen[-1][1].iterdir()) == ["downtown.json"]
    once(shipped, cfg.work / "001")
    assert seen[-1][1] == PLANS and f"--plan-dir={PLANS}" in seen[-1][2]
    with pytest.raises(grade.EvaluationError):
        grade.grade_instance(
            g, dict(own, plans="nowhere"), tmp_path, None, None, cfg.work / "002"
        )
