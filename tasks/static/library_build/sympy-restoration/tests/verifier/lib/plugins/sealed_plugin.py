"""pytest plugin used by the grader: run only the listed node ids; record starts, outcomes and uncollectable files."""

import json
import os

_WANT = None


def _want():
    global _WANT
    if _WANT is None:
        with open(os.environ["SEALED_LIST"], encoding="utf-8") as f:
            _WANT = set(json.load(f))
    return _WANT


def pytest_collection_modifyitems(config, items):
    want = _want()
    keep = [it for it in items if it.nodeid in want]
    drop = [it for it in items if it.nodeid not in want]
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep


def pytest_collectreport(report):
    # a test file that cannot be collected is recorded, so the grader does not try it again
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    if report.outcome != "passed" and str(report.nodeid).endswith(".py"):
        with open(os.environ["SEALED_RESULTS"], "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"id": report.nodeid, "when": "collect", "outcome": "failed"}
                )
                + "\n"
            )


def pytest_runtest_logstart(nodeid, location):
    # lets the grader tell a test that was running when a session died from one never started
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    with open(os.environ["SEALED_RESULTS"], "a", encoding="utf-8") as f:
        f.write(
            json.dumps({"id": nodeid, "when": "start", "outcome": "started"}) + "\n"
        )


def pytest_runtest_logreport(report):
    # with xdist this hook also fires on the controller for every worker report
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    oc = report.outcome
    if oc == "skipped":
        # a sealed test is expected to run; a skip (or xfail) is not a pass
        oc = "failed"
    if report.when != "call" and oc == "passed":
        return
    with open(os.environ["SEALED_RESULTS"], "a", encoding="utf-8") as f:
        f.write(
            json.dumps({"id": report.nodeid, "when": report.when, "outcome": oc}) + "\n"
        )
