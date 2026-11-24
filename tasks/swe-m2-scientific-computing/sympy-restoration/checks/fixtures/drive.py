"""Run one verifier scenario in its own interpreter and print the outcome as JSON.

The checks start this file in a subprocess so that the verifier package of this
task never shares an interpreter with another task's package of the same name.
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(TASK_ROOT / "steps" / "01-restore-bodies" / "tests"), str(TASK_ROOT / "common")]

from verifier import registry, runner, scoring  # noqa: E402
from verifier.config import load_config  # noqa: E402
from verifier.contracts import (  # noqa: E402
    CandidateFailure, CheckResult, EvaluationError, Measurement, RegisteredCheck,
    ScoringConfig, VerificationContext,
)
from verifier.reporting import write_report  # noqa: E402

# 100 units, 80 of which have calls no docstring example or visible test repeats (160 such calls)
TOTALS = {"units_total": 100, "vectors_total": 400, "tests_total": 200, "units_set": 80, "deciding_total": 160}


def measurement(units: int, calls: int, tests: int, set_units: int = 80, deciding: int = 160, *, artifact: bool = True,
                restored: int = 100, trips: tuple[str, ...] = (), unreached: dict | None = None) -> Measurement:
    """Build a measurement with fixed denominators and the given numerators.

    `units`, `calls` and `tests` are the numerators of the three bars of a complete restoration;
    `set_units` and `deciding` those of the reward's unit and call shares.
    """
    counts = dict(TOTALS, units_restored=restored, units_passing=units, vectors_passing=calls, tests_passing=tests,
                  units_set_passing=set_units, deciding_passing=deciding)
    details = dict(counts, tamper=list(trips), notes=[], unit_bar=0.99, vector_bar=0.9, test_bar=0.95,
                   unit_share_if_reached=set_units / 80, call_share_if_reached=deciding / 160, reward_tolerance=0.001)
    details.update(unreached or {})
    return Measurement(artifact, counts, trips, details)


def context(output: Path, measured: Measurement | None) -> VerificationContext:
    """Build a context whose measurement is already present, so no code is run."""
    scoring_config, limits = load_config()
    return VerificationContext(Path("/nonexistent"), Path("/nonexistent"), Path("/nonexistent"),
                               output, output / "work", scoring_config, limits, measurement=measured)


FILE_A, FILE_B = "pkg/tests/test_a.py", "pkg/tests/test_b.py"
SEALED = [f"{FILE_A}::test_{i}" for i in range(1, 7)] + [f"{FILE_B}::test_1", f"{FILE_B}::test_2"]
A1, A2, A3, A4, A5, A6, B1, B2 = SEALED
ALL_A = {A1: "passed", A2: "failed", A3: "passed", A4: "passed", A5: "passed", A6: "passed"}
# One entry per scripted pytest run. "session" is the first run over every test;
# "files" lists, per test file, its runs in the later one-file-per-process passes.
# A run gives the outcomes it records, the tests still "running" when it ended,
# the test a session names as its "crash", whether pytest could not collect the
# file ("uncollectable"), its "state", a wrong "selfcheck" or a forced "tally".
SEALED_SCRIPTS = {
    # one session reports everything
    "sealed_clean": {"session": {"outcomes": dict(ALL_A, **{B1: "passed", B2: "failed"})}},
    # a file that cannot be collected is reported as such and is not run again
    "sealed_uncollectable": {"session": {"outcomes": ALL_A, "uncollectable": [FILE_B]}},
    # the session dies at A3 with half of file a and all of file b not started
    "sealed_abort": {
        "session": {"outcomes": {A1: "passed", A2: "failed"}, "crash": A3},
        "files": {FILE_A: [{"outcomes": {A4: "passed", A5: "passed", A6: "failed"}}],
                  FILE_B: [{"outcomes": {}, "uncollectable": [FILE_B]}]},
    },
    # the session never reports (an import that does not return); file b then hangs alone
    "sealed_stall": {
        "session": {"state": "stalled", "outcomes": {}, "selfcheck": "silent"},
        "files": {FILE_A: [{"outcomes": ALL_A}], FILE_B: [{"state": "stalled", "outcomes": {}, "selfcheck": "silent"}]},
    },
    # the session ends without naming a test while A3 and A4 are running
    "sealed_unnamed": {
        "session": {"outcomes": {A1: "passed", A2: "failed"}, "running": [A3, A4]},
        "files": {FILE_A: [{"outcomes": {A4: "passed"}, "running": [A3]}, {"outcomes": {A5: "passed", A6: "passed"}}],
                  FILE_B: [{"outcomes": {B1: "passed", B2: "passed"}}]},
    },
    # the time budget ends the session
    "sealed_budget": {"session": {"state": "budget", "outcomes": {A1: "passed"}}},
    # one of the later runs reports the must-fail self-check as passed
    "sealed_selfcheck": {
        "session": {"outcomes": {A1: "passed"}, "crash": A2},
        "files": {FILE_A: [{"outcomes": {A3: "passed", A4: "passed", A5: "passed", A6: "passed"}, "selfcheck": "wrong"}],
                  FILE_B: [{"outcomes": {B1: "passed", B2: "passed"}}]},
    },
    # one of the later runs has more passes on record than pytest counted
    "sealed_tally": {
        "session": {"outcomes": {A1: "passed"}, "crash": A2},
        "files": {FILE_A: [{"outcomes": {A3: "passed", A4: "passed", A5: "passed", A6: "passed"}, "tally": 2}],
                  FILE_B: [{"outcomes": {B1: "passed", B2: "passed"}}]},
    },
    # file a settles one test per run and never finishes
    "sealed_limit": {
        "session": {"outcomes": {}, "crash": A1},
        "files": {FILE_A: [{"outcomes": {t: "passed"}} for t in (A2, A3, A4, A5, A6)], FILE_B: [{"outcomes": {}}] * 5},
    },
}


def sealed_run(script: dict, work: Path, pass_limit: int) -> dict:
    """Drive the sealed-test phase with scripted runs in place of pytest.

    Args:
        script: The session and the later per-file runs, as in SEALED_SCRIPTS.
        work: Empty directory for the run's files.
        pass_limit: Largest number of passes the phase may make.

    Returns:
        What the phase returned, the tests each run was given and the log.
    """
    from verifier import engine

    asked: list[dict] = []
    used: dict[str, int] = {}

    def scripted(ids, prefix, *, tag, workers, deadline, pub, scratch, cand, cfg):
        path = sorted({nid.split("::")[0] for nid in ids})
        if workers:
            step = script["session"]
        else:
            assert len(path) == 1, path
            step = script["files"][path[0]][used.get(path[0], 0)]
            used[path[0]] = used.get(path[0], 0) + 1
        asked.append({"tag": tag, "workers": workers, "ids": sorted(ids)})
        outcome = {nid: oc for nid, oc in step["outcomes"].items() if nid in ids}
        if step.get("selfcheck") != "silent":
            outcome[engine.SELFCHECK_PASS] = "passed"
            outcome[engine.SELFCHECK_FAIL] = "passed" if step.get("selfcheck") == "wrong" else "failed"
        state = step.get("state", "done")
        text = ""
        if step.get("crash"):
            text += f"INTERNALERROR> AssertionError: ('{step['crash']}', <WorkerController gw2>)\n"
        if state == "done":
            passed = sum(1 for oc in outcome.values() if oc == "passed")
            text += f"{len(outcome) - passed} failed, {step.get('tally', passed)} passed in 1.00s\n"
        started = set(outcome) | {nid for nid in step.get("running", []) if nid in ids}
        return {"state": state, "text": text, "outcome": outcome, "started": started,
                "uncollectable": set(step.get("uncollectable", [])), "first_test_sec": None if state == "stalled" else 1.5}

    engine.sealed_run = scripted
    for name in ("scratch", "pub", "cand", "art"):
        (work / name).mkdir()
    notes: list[str] = []
    import time

    result = engine.run_sealed_tests(
        SEALED, [], notes, scratch=str(work / "scratch"), pub=str(work / "pub"), cand=str(work / "cand"),
        art=str(work / "art"), cfg={"pytest_pass_limit": pass_limit}, cpus=2, deadline=time.monotonic() + 600)
    return {"outcome": {t: result.outcome.get(t) for t in SEALED}, "selfcheck_ok": result.selfcheck_ok,
            "timed_out": result.timed_out, "runner_passed": result.runner_passed, "tally_exceeded": result.tally_exceeded,
            "runs": result.runs, "passes": result.passes, "first_test_sec": result.first_test_sec,
            "asked": sorted(asked, key=lambda run: run["tag"]), "notes": notes,
            "log": (work / "art" / "pytest_sealed.log").read_text(encoding="utf-8")}


def records_scenario(work: Path) -> dict:
    """Read a scripted record file the way the phase reads one run's records."""
    from verifier import engine

    path = work / "records.jsonl"
    lines = [
        {"id": A1, "when": "start", "outcome": "started"}, {"id": A1, "when": "call", "outcome": "passed"},
        {"id": A2, "when": "start", "outcome": "started"}, {"id": A2, "when": "call", "outcome": "passed"},
        {"id": A2, "when": "teardown", "outcome": "failed"}, {"id": A3, "when": "start", "outcome": "started"},
        {"id": FILE_B, "when": "collect", "outcome": "failed"}, {"id": "other.py::test_x", "when": "call", "outcome": "passed"},
        {"id": 7, "when": "call", "outcome": "passed"}, ["not", "a", "record"],
    ]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines) + "not json\n", encoding="utf-8")
    outcome, started, uncollectable = engine.read_records(str(path), set(SEALED))
    return {"outcome": outcome, "started": sorted(started), "uncollectable": sorted(uncollectable)}


def watch_scenario(work: Path) -> dict:
    """Run the process watcher on small commands that end, hang or meet the deadline."""
    import time

    from verifier import engine

    start = json.dumps({"id": A1, "when": "start", "outcome": "started"})
    collect = json.dumps({"id": FILE_B, "when": "collect", "outcome": "failed"})
    write = "import sys, time; open(sys.argv[1], 'a').write(sys.argv[2] + chr(10)); "
    states = {}
    for name, code, record, budget, collect_sec in (
        ("ends", write + "pass", start, 60, 30),
        ("never_reports", "import time; time.sleep(60)", "", 60, 2),
        ("collection_error_then_hang", write + "time.sleep(60)", collect, 60, 4),
        ("starts_then_stops", write + "time.sleep(60)", start, 60, 30),
        ("budget", "import time; time.sleep(60)", "", 2, 30),
    ):
        records = work / f"{name}.jsonl"
        records.write_text("")
        began = time.monotonic()
        state, first, code = engine.watch([sys.executable, "-I", "-c", code, str(records), record], cwd=str(work), env=None,
                                          log_path=str(work / f"{name}.log"), res_path=str(records),
                                          deadline=time.monotonic() + budget, collect_sec=collect_sec, stall_sec=1)
        states[name] = {"state": state, "test_started": first is not None, "seconds": round(time.monotonic() - began, 1),
                        "code": code}
    # records an earlier run left in the file do not count as this run's work
    records = work / "left.jsonl"
    records.write_text(start + "\n")
    began = time.monotonic()
    state, first, code = engine.watch([sys.executable, "-I", "-c", "import time; time.sleep(60)"], cwd=str(work), env=None,
                                      log_path=str(work / "left.log"), res_path=str(records), deadline=time.monotonic() + 60,
                                      collect_sec=2, stall_sec=30)
    states["earlier_records"] = {"state": state, "test_started": first is not None, "seconds": round(time.monotonic() - began, 1),
                                 "code": code}
    return states


STUB_RUNNER = """
import json, os, pickle, sys, time
cand, mod = sys.argv[1:3]
data = pickle.loads(sys.stdin.buffer.read())
out = os.fdopen(os.dup(1), "wb", buffering=0)
with open(os.path.join(cand, "starts.txt"), "a") as f:
    f.write(mod + chr(10))
def send(record):
    out.write(json.dumps(record).encode() + chr(10).encode())
if mod == "mod_dead":
    sys.exit(1)
if mod == "mod_import_hang":
    time.sleep(120)
send({"loaded": True})
for vid, uid, blob in data["vectors"]:
    send({"start": vid})
    if vid.endswith("_crash"):
        out.write(b'{"v": "half a line')
        os._exit(1)
    if vid.endswith("_die"):
        os._exit(1)
    if vid.endswith("_hang") or vid.endswith("_slow"):
        time.sleep(120)
    if vid.endswith("_forged"):
        # a body that reached the process writes a result of its own for the next call
        send({"v": vid.replace("_forged", "_victim"), "c": ["forged"], "ms": 1})
    if vid.endswith("_flood"):
        out.write(b"x" * (5 << 20))
    if vid.endswith("_listid"):
        send({"v": [vid], "c": ["ok", vid], "ms": 1})
        continue
    send({"v": vid, "c": ["ok", vid], "ms": 1})
send({"done": True})
"""


def vector_scenario(work: Path) -> dict:
    """Run the call-replay phase with a stub runner whose jobs finish, crash, hang, never report or
    write out of order or out of form."""
    from verifier import engine

    for name in ("scratch", "pub", "cand"):
        (work / name).mkdir()
    (work / "pub" / "rvector.py").write_text(STUB_RUNNER, encoding="utf-8")

    def module(unit: str, *ids: str) -> dict:
        return {"units": {unit: {}}, "vectors": [(vid, unit, b"") for vid in ids]}

    def units(*pairs) -> dict:
        return {"units": {unit: {} for unit, _vid in pairs}, "vectors": [(vid, unit, b"") for unit, vid in pairs]}

    payload = {
        "mod_ok": module("U1", "ok1", "ok2"),
        "mod_crash": units(("U2", "c1"), ("U2", "c2_crash"), ("U3", "c3"), ("U3", "c4")),
        "mod_hang": units(("U4", "h1"), ("U4", "h2_hang"), ("U4", "h3"), ("U14", "h4")),
        "mod_dead": module("U5", "d1", "d2", "d3"),
        "mod_barren": units(("U6", "b1_die"), ("U6", "b2_die"), ("U7", "b3"), ("U7", "b4")),
        "mod_slow": units(("U8", "w1_slow"), ("U8", "w2"), ("U15", "w3"), ("U15", "w4")),
        "mod_not_restored": module("U9", "s1"),
        "mod_import_hang": units(("U10", "i1"), ("U11", "i2")),
        "mod_forged": units(("U12", "f1_forged"), ("U13", "f2_victim"), ("U13", "f3")),
        "mod_flood": units(("U16", "x1_flood"), ("U16", "x2"), ("U17", "x3")),
        "mod_listid": units(("U18", "l1_listid"), ("U19", "l2")),
    }
    import time

    stats: dict = {}
    results = engine.run_vectors(
        payload, {f"U{k}" for k in range(1, 20)} - {"U9"}, [], pub=str(work / "pub"), cand_nt=str(work / "cand"), cpus=4,
        deadline=time.monotonic() + 90, bound=lambda uid: 1.0, load_bound=lambda mod: 5.0, tmp_root=str(work / "scratch"),
        stats=stats)
    starts: dict[str, int] = {}
    for line in (work / "cand" / "starts.txt").read_text().split():
        starts[line] = starts.get(line, 0) + 1
    return {"results": results, "starts": starts, "stats": stats}


def scenario(name: str) -> dict:
    """Run a named scenario and return what a check needs to assert on."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        if name in SEALED_SCRIPTS:
            return sealed_run(SEALED_SCRIPTS[name], output, 4 if name == "sealed_limit" else 5)
        if name == "sealed_records":
            return records_scenario(output)
        if name == "sealed_watch":
            return watch_scenario(output)
        if name == "vector_jobs":
            return vector_scenario(output)
        if name == "runner_tally":
            from verifier import engine

            return {"finished": engine.runner_tally("...F.\n709 failed, 7454 passed, 71 warnings in 673.16s (0:11:13)\n"),
                    "none_passed": engine.runner_tally("FFF\n3 failed in 0.20s\n"),
                    "cut_off": engine.runner_tally("....F....\n")}
        if name == "registry":
            return {"checks": [c.name for c in registry.CHECKS], "mandatory": list(scoring.MANDATORY),
                    "requires": {c.name: list(c.requires) for c in registry.CHECKS}}
        if name == "config":
            scoring_config, limits = load_config()
            return {"scoring": asdict(scoring_config), "limits": limits}
        cases = {
            "reference": measurement(100, 400, 200),
            "pass": measurement(99, 360, 190, 79, 150),
            "partial": measurement(50, 200, 20, 48, 80),
            "units_below": measurement(98, 400, 200, 78, 160),
            "calls_below": measurement(100, 359, 200, 80, 140),
            "tests_below": measurement(100, 400, 189),
            "tripped": measurement(100, 400, 200, trips=("test-runner self-check",)),
            "nothing_delivered": measurement(0, 0, 0, 0, 0, artifact=False, restored=0),
            "nothing_restored": measurement(0, 0, 0, 0, 0, restored=0),
        }
        if name in cases:
            ctx = context(output, cases[name])
            result = runner.verify(ctx)
            write_report(output, ctx, result, None)
            return {
                "passed": result.passed, "metrics": dict(result.metrics),
                "status": {c.requirement: c.status for c in result.checks},
                "reward_txt": (output / "reward.txt").read_text(),
                "metrics_json": json.loads((output / "metrics.json").read_text()),
                "report_status": json.loads((output / "report.json").read_text())["status"],
            }
        if name == "evaluation_error":
            ctx = context(output, None)
            (output / "reward.txt").write_text("1")  # a stale reward that must not survive

            def broken(_: VerificationContext) -> CheckResult:
                raise EvaluationError("sandbox unavailable")

            runner.CHECKS = (RegisteredCheck("candidate_tree", broken),)
            try:
                runner.verify(ctx)
            except EvaluationError as exc:
                write_report(output, ctx, None, str(exc))
                return {"raised": True, "reward_exists": (output / "reward.txt").exists(),
                        "report": json.loads((output / "report.json").read_text()),
                        "metrics_json": json.loads((output / "metrics.json").read_text())}
            return {"raised": False}
        if name in ("units_unreached", "calls_unreached", "unreached_not_the_minimum", "unreached_within_tolerance",
                    "tests_unreached", "tests_unreached_units_below", "tests_unreached_short", "unreached_tripped"):
            cases = {
                # 60 of 80 units pass; 8 more were not reached and could pass: the reward could move
                "units_unreached": measurement(100, 400, 200, 60, 160, unreached={"unit_share_if_reached": 68 / 80}),
                "calls_unreached": measurement(100, 400, 200, 80, 120, unreached={"call_share_if_reached": 130 / 160}),
                # the calls are the smaller share and every call was reached: the units cannot move it
                "unreached_not_the_minimum": measurement(100, 400, 200, 60, 80, unreached={"unit_share_if_reached": 68 / 80}),
                "unreached_within_tolerance": measurement(100, 400, 200, 60, 160,
                                                          unreached={"unit_share_if_reached": 60.05 / 80}),
                # tests are reported, not rewarded: tests not reached only leave `complete` open
                "tests_unreached": measurement(100, 400, 189, unreached={"tests_not_reached": 5}),
                "tests_unreached_units_below": measurement(98, 400, 189, 78, 160, unreached={"tests_not_reached": 5}),
                "tests_unreached_short": measurement(100, 400, 180, unreached={"tests_not_reached": 5}),
                "unreached_tripped": measurement(100, 400, 200, 60, 160, trips=("test-runner self-check",),
                                                 unreached={"unit_share_if_reached": 68 / 80}),
            }
            ctx = context(output, cases[name])
            try:
                result = runner.verify(ctx)
            except EvaluationError as exc:
                return {"error": str(exc)}
            return {"reward": result.metrics["reward"], "complete": result.metrics["complete"],
                    "status": {c.requirement: c.status for c in result.checks}}
        if name == "candidate_failure_text":
            ctx = context(output, measurement(98, 400, 200))
            result = runner.verify(ctx)
            return {"explanation": {c.requirement: c.explanation for c in result.checks}}
        if name == "transplant":
            import restorelib

            skeleton = (
                'import math\n\n\ndef f(x):\n    """Doc."""\n    raise NotImplementedError("RESTORE U0001")\n\n\n'
                'def g(x):\n    raise NotImplementedError("RESTORE U0002")\n\n\n'
                'def h(x):\n    raise NotImplementedError("RESTORE U0003")\n\n\ndef keep(x):\n    return x + 1\n'
            )
            work = (
                'import math\nimport os\n\nHELPER = 5\n\n\ndef f(x):\n    """Doc."""\n    return x * 2\n\n\n'
                'def g(x):\n    raise NotImplementedError("RESTORE U0002")\n\n\n'
                'def h(x):\n    import os\n    return os.getcwd()\n\n\ndef keep(x):\n    return x + 100\n'
            )
            candidate, states = restorelib.transplant_file(skeleton, work, {"f": "U0001", "g": "U0002", "h": "U0003"})
            missing, missing_states = restorelib.transplant_file(skeleton, None, {"f": "U0001"})
            return {"candidate": candidate, "states": states, "missing_states": missing_states,
                    "missing_is_skeleton": missing == skeleton}
        raise SystemExit(f"unknown scenario {name}")


if __name__ == "__main__":
    print(json.dumps(scenario(sys.argv[1]), sort_keys=True))
