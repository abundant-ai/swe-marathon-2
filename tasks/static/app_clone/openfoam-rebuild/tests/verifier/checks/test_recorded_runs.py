"""Each recorded OpenFOAM run, replayed with the submitted programs, gives the recorded result."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

from .. import recorded as R
from ..contracts import CheckResult, Test, VerificationContext

SLOWDOWN = (
    30  # a run may take thirty times as long as OpenFOAM's (stated in the instruction)
)
MIN_SECONDS = 10  # and at least ten seconds


def time_limit(test: Test) -> float:
    return max(SLOWDOWN * test.seconds, MIN_SECONDS)


def replay(test: Test, dataset: str, app: str, uid: int, gid: int, work: str):
    """{check: (passed, first mismatch)} for the checks of one test that count."""
    rec = R.Record.load(
        os.path.join(dataset, test.record), os.path.join(dataset, "files")
    )
    env = {
        "PATH": f"{app}/bin:/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "USER": "dev",
        "LOGNAME": "dev",
        "PMIX_MCA_psec": "none",
    }  # as in the candidate's environment (environment/Dockerfile)
    run = R.Run(
        rec,
        R.Limits(env=env, timeout=time_limit(test), uid=uid, gid=gid),
        work_root=work,
    )
    try:
        res = R.check(run, test.tolerances, test.masked)
    except (
        Exception  # noqa: BLE001 - Handle failures at the task boundary.
    ) as e:  # output the comparison cannot handle, e.g. a link where a file belongs
        return {
            n: (False, f"output could not be compared: {type(e).__name__}")
            for n in test.checks
        }
    finally:
        run.close()
    return {
        n: (res[n].ok, res[n].mismatches[0] if res[n].mismatches else "")
        if n in res
        else (False, "not produced")
        for n in test.checks
    }


def test_recorded_runs(context: VerificationContext) -> CheckResult:
    total = sum(len(t.checks) for t in context.tests)
    # longest first, so a long run does not start last; a parallel run gets the processors it uses
    order = sorted(context.tests, key=lambda t: -t.seconds)
    jobs = [
        (
            t.processes,
            replay,
            t,
            str(context.dataset),
            str(context.app),
            context.uid,
            context.gid,
            str(context.work),
        )
        for t in order
    ]
    with ProcessPoolExecutor(max_workers=context.workers) as pool:
        for i, out in R.run_packed(pool, jobs, context.workers):
            context.outcomes[order[i].record] = out
    passed = sum(ok for out in context.outcomes.values() for ok, _ in out.values())
    resolved_tests = sum(
        all(ok for ok, _ in out.values()) for out in context.outcomes.values()
    )
    metrics = {
        "checks": float(total),
        "checks_passed": float(passed),
        "recorded_runs": float(len(context.tests)),
        "recorded_runs_passed": float(resolved_tests),
    }
    status = "passed" if passed == total else "failed"
    return CheckResult(
        "recorded_runs", status, f"{passed} of {total} checks pass", metrics
    )
