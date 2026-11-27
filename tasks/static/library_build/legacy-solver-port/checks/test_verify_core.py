"""Boundary tests of the cumulative verifier with synthetic references (no MOPAC, no private data).

Run from the repository root: uv run --frozen pytest tasks/static/library_build/legacy-solver-port/checks
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common" / "verifier"))
import verify_core

ANSWER = {
    "heat_of_formation": -10.0,
    "gradients": [0.1, 0.2],
    "atom_charges": [0.3, -0.3],
    "ionization_potential": 10.0,
    "dipole": 1.0,
}
GOOD = "import json, sys\nv = json.loads(open(sys.argv[1]).read().splitlines()[2][8:])\njson.dump(v, open(sys.argv[2], 'w'))\n"
CRASH = "raise SystemExit(3)\n"


def make_refs(root, hidden=2, visible=1):
    for step, group, n in (("step1", "hidden", hidden), ("step1", "visible", visible)):
        for i in range(n):
            d = root / step / group / f"case{group}{i}"
            d.mkdir(parents=True)
            name = d.name
            (d / f"{name}.mop").write_text(
                f"PM7 1SCF\n{name}\nanswer: {json.dumps(ANSWER)}\n"
            )
            (d / f"{name}.json").write_text(json.dumps({"kind": "sp", **ANSWER}))


def run(tmp_path, solver_src, **kw):
    refs = tmp_path / "refs"
    make_refs(refs, **kw)
    solver = tmp_path / "solver"
    solver.mkdir()
    if solver_src is not None:
        (solver / "run.py").write_text(solver_src)
    out = tmp_path / "reward.json"
    verify_core.main(
        ["--step", "1", "--solver", str(solver), "--refs", str(refs), "--out", str(out)]
    )
    return json.loads(out.read_text())


def test_correct_solver_scores_one(tmp_path):
    assert run(tmp_path, GOOD)["reward"] == 1.0


def test_missing_solver_scores_zero_and_writes_reward(tmp_path):
    assert run(tmp_path, None)["reward"] == 0.0


def test_crashing_solver_scores_zero_with_fixed_denominator(tmp_path):
    reward = run(tmp_path, CRASH)
    assert reward["reward"] == 0.0
    details = json.loads((tmp_path / "reward_details.json").read_text())
    assert details["steps"]["1"]["hidden_total"] == 2


def test_one_wrong_case_lowers_reward_by_its_share(tmp_path):
    bad_first = GOOD.replace(
        "json.dump(v,",
        "v['heat_of_formation'] += 1.0 if 'hidden0' in sys.argv[1] else 0.0\njson.dump(v,",
    )
    assert run(tmp_path, bad_first)["reward"] == pytest.approx(0.5)


def test_visible_cases_do_not_count(tmp_path):
    only_visible_good = GOOD.replace(
        "json.dump(v,", "v = {} if 'hidden' in sys.argv[1] else v\njson.dump(v,"
    )
    assert run(tmp_path, only_visible_good)["reward"] == 0.0


def test_no_hidden_references_is_a_harness_error_without_reward(tmp_path):
    refs = tmp_path / "refs"
    make_refs(refs, hidden=0)
    solver = tmp_path / "solver"
    solver.mkdir()
    (solver / "run.py").write_text(GOOD)
    out = tmp_path / "reward.json"
    with pytest.raises(SystemExit) as stop:
        verify_core.main(
            [
                "--step",
                "1",
                "--solver",
                str(solver),
                "--refs",
                str(refs),
                "--out",
                str(out),
            ]
        )
    assert stop.value.code == 3
    assert not out.exists()
