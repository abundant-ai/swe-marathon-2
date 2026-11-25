"""The time the submission's own bodies take is the submission's: a tree whose bodies never end, or
that call one that never ends, completes with those items failed; only a machine too slow for the
original keeps the evaluation open (an evaluation error).

measure() and the scoring run whole here (registry, checks, report) on a stand-in `sympy` package:
the names the runners import and one module of units, with the privilege drop, the network probe,
the collect step's mark and the test phase stood in for, and phase budgets of a few seconds.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from test_comparison import STANDIN as CANON_STANDIN
from test_doctest_phase import STANDIN, unit

LIMITS = {
    "doctest_floor_sec": 1,
    "vector_floor_sec": 1,
    "load_floor_sec": 20,
    "doctest_budget_sec": 10,
    "vector_budget_sec": 10,
    "measure_budget_sec": 60,
    "workers": 1,
}


def stand_in_grade(
    verifier_call,
    tmp_path: Path,
    bodies: dict,
    *,
    limits: dict,
    per_unit: float = 0.01,
    patch: str = "",
) -> dict:
    """Grade a tree whose units are `bodies` ({name: body}), three recorded calls each returning 1."""
    names = list(bodies)
    uids = {name: f"U{index + 1:04d}" for index, name in enumerate(names)}
    head = "import time\n\n\n"
    for root, text in (
        (
            tmp_path / "skel",
            head
            + "".join(
                unit(n, f'raise NotImplementedError("RESTORE {uids[n]}")')
                for n in names
            ),
        ),
        (
            tmp_path / "work" / "sympy_parent",
            head + "".join(unit(n, body) for n, body in bodies.items()),
        ),
    ):
        for rel, content in dict(
            CANON_STANDIN, **STANDIN, **{"sympy/demo.py": text}
        ).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(content)
    private = tmp_path / "private"
    (private / "vectors").mkdir(parents=True)
    units = [
        {
            "uid": uids[n],
            "file": "sympy/demo.py",
            "module": "sympy.demo",
            "qualname": n,
            "dotted": f"sympy.demo.{n}",
            "occ": 0,
            "nocc": 1,
            "order": i,
        }
        for i, n in enumerate(names)
    ]
    (private / "units.json").write_text(json.dumps(units))
    (private / "sealed_tests.json").write_text(json.dumps({"tests": []}))
    gold = {f"V{uids[n]}{k}": ["I", "1"] for n in names for k in "abc"}
    (private / "vectors" / "gold.json").write_text(json.dumps(gold))
    (private / "vectors" / "documented.json").write_text(json.dumps({"calls": []}))
    (private / "unit_bodies.json").write_text(
        json.dumps({uids[n]: [1, None] for n in names})
    )
    timing = {
        "benchmark_sec": 1000.0,
        "doctest": {
            "load": {"sympy.demo": 0.1},
            "units": {f"sympy.demo.{n}": per_unit for n in names},
        },
        "vector": {
            "load": {"sympy.demo": 0.1},
            "units": {uids[n]: per_unit for n in names},
        },
    }
    (private / "timing.json").write_text(json.dumps(timing))
    meta = {
        uids[n]: {
            "file": "sympy/demo.py",
            "qualname": n,
            "name": n,
            "occ": 0,
            "nocc": 1,
        }
        for n in names
    }
    payload = {
        "sympy.demo": {
            "units": meta,
            "vectors": [(vid, vid[1:6], pickle.dumps({})) for vid in gold],
        }
    }
    (private / "vectors" / "inputs.pkl").write_bytes(pickle.dumps(payload, protocol=4))
    out = tmp_path / "out"
    (out / "artifacts").mkdir(parents=True)
    return verifier_call(
        f"""
import json
from pathlib import Path
from verifier import delivery, engine
from verifier.config import load_config
from verifier.contracts import EvaluationError, VerificationContext
from verifier.reporting import write_report
from verifier.runner import verify
engine.delivery.network_open = lambda *a, **k: None
engine.delivery.read_delivery = lambda top, key, *rest: delivery.Delivery("listed", end_bound=float("inf"), end_from="netcheck")
engine.sandbox_prefix = lambda *a, **k: []
engine.reap = lambda prefix: None
engine.run_sealed_tests = lambda sealed_ids, prefix, notes, **kw: engine.SealedResult({{}}, True, False, None, False, 0, 0, None)
{patch}
scoring, limits = load_config()
limits = dict(limits, **{limits!r})
work = Path({str(tmp_path / "work" / "sympy_parent")!r})
ctx = VerificationContext(work, Path({str(tmp_path / "skel")!r}), Path({str(private)!r}), Path({str(out)!r}),
                          Path({str(tmp_path / "scratch")!r}), scoring, limits)
try:
    result = verify(ctx)
    write_report(ctx.output, ctx, result, None)
    m = json.loads((ctx.output / "metrics.json").read_text())
    print(json.dumps({{"status": "completed", "reward": m["reward"], "units_set_passing": m["units_set_passing"],
                       "deciding_passing": m["deciding_passing"], "units_not_reached": m["units_not_reached"],
                       "vectors_not_reached": m["vectors_not_reached"], "examples_failed_unreached": m.get("units_not_reached_failed"),
                       "calls_failed_unreached": m.get("vectors_not_reached_failed"), "notes": m["notes"],
                       "doctest_runs": m.get("doctest_runs"), "vector_runs": m.get("vector_runs")}}))
except EvaluationError as exc:
    print(json.dumps({{"status": "evaluation_error", "error": str(exc)}}))
""",
        timeout=300,
    )


def test_a_tree_whose_every_body_never_ends_completes_with_its_items_failed(
    tmp_path, verifier_call
):
    bodies = {f"loop{index:02d}": "while True:\n    pass" for index in range(12)}
    data = stand_in_grade(verifier_call, tmp_path, bodies, limits=LIMITS)
    assert data["status"] == "completed" and data["reward"] == 0.0, data
    assert data["units_not_reached"] == 0 and data["vectors_not_reached"] == 0, data
    assert (data["examples_failed_unreached"] or 0) + (
        data["calls_failed_unreached"] or 0
    ) > 0, data
    assert any(
        "count as failed" in note or "count as not matching" in note
        for note in data["notes"]
    ), data["notes"]
    # a unit whose call ran out of time is not run again
    assert (
        data["vector_runs"]["units_cut"] >= 1 and data["vector_runs"]["timeouts"] >= 1
    ), data["vector_runs"]


def test_one_never_ending_body_that_others_call_still_leaves_a_score(
    tmp_path, verifier_call
):
    bodies = {
        "c": "return 1",
        "d": "return 1",
        "e": "return 1",
        "f": "return 1",
        "core": "while True:\n    pass",
        "a": "return core()",
        "b": "return core()",
    }
    data = stand_in_grade(
        verifier_call, tmp_path, bodies, limits=dict(LIMITS, vector_budget_sec=20)
    )
    assert (
        data["status"] == "completed"
        and data["units_not_reached"] == 0
        and data["vectors_not_reached"] == 0
    ), data
    assert (
        data["units_set_passing"] == 4
        and data["deciding_passing"] == 12
        and data["reward"] == round(4 / 7, 6)
    ), data
    # each of the three never-ending units ran out of time once and its other two calls were not run
    assert (
        data["vector_runs"]["timeouts"] == 3 and data["vector_runs"]["units_cut"] == 3
    ), data["vector_runs"]


def test_a_machine_too_slow_for_the_original_still_ends_in_an_evaluation_error(
    tmp_path, verifier_call
):
    """Right bodies, and a measurement whose time is gone before they run, where the original itself
    would need more than that time: the time, not the submission, decided, so there is no reward."""
    bodies = {f"fine{index}": "return 1" for index in range(3)}
    data = stand_in_grade(
        verifier_call,
        tmp_path,
        bodies,
        limits=dict(LIMITS, measure_budget_sec=0),
        per_unit=100.0,
    )
    assert data["status"] == "evaluation_error" and "did not reach" in data["error"], (
        data
    )


def test_a_disk_the_bodies_fill_costs_no_evaluation(tmp_path, verifier_call):
    """The sandbox filled the disk: no runner's private folder can be made, and the verifier's own files
    cannot be written. The runners run without a folder, the files are noted as not written, and the
    measurement completes with its score."""
    bodies = {"good": "return 1", "other": "return 1"}
    patch = """
import builtins, errno
def full(*args, **kwargs):
    raise OSError(errno.ENOSPC, "No space left on device")
engine.gradelib.tempfile.mkdtemp = full
real_open = builtins.open
def guarded_open(path, mode="r", *args, **kwargs):
    if "w" in mode and str(path).endswith(("unit_results.json", "sealed_test_failures.json")):
        full()
    return real_open(path, mode, *args, **kwargs)
engine.open = guarded_open
cleared = []
engine.clear_leftovers = lambda extra=(): cleared.append(1) or 0
"""
    data = stand_in_grade(verifier_call, tmp_path, bodies, limits=LIMITS, patch=patch)
    assert data["status"] == "completed" and data["reward"] == 1.0, data
    assert any("could not write unit_results.json" in note for note in data["notes"]), (
        data["notes"]
    )
