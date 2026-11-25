"""Harbor entry point: builds the submission, replays every recorded OpenFOAM run with it and
writes the report and reward to /logs/verifier."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # run with python -I

from verifier import recorded as R
from verifier.contracts import EvaluationError, Test, VerificationContext
from verifier.runner import verify

APP = Path("/app/rebuild")
DATASET = Path("/data/openfoam-tests")
OUTPUT = Path("/logs/verifier")
WORK = Path("/work")
UID = GID = 10001
BUILD_TIMEOUT = 2 * 3600


def processors() -> int:
    """Processors this container may use: those it is allowed to run on, fewer if a CPU quota
    (cgroup v2 cpu.max) allows less. os.cpu_count() would give the host's count."""
    n = len(os.sched_getaffinity(0))
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
        if quota != "max":
            n = min(n, max(1, int(quota) // int(period)))
    except (OSError, ValueError):
        pass
    return n


def load_tests(dataset: Path) -> tuple[Test, ...]:
    tests = []
    for line in open(dataset / "tests.jsonl"):
        t = json.loads(line)
        if not (dataset / t["record"]).is_file():
            raise EvaluationError(f"dataset incomplete: {t['record']} missing")
        tests.append(Test(t["record"], t["source"], t["program"], tuple(t["checks"]),
                          tuple(t["masked"]), t["tolerances"], t["seconds"],
                          R.processes(t["program"], t["args"])))
    return tuple(tests)


def write_report(output: Path, context, result, error):
    report = {"error": error}
    if result is not None:
        report |= {"metrics": dict(result.metrics),
                   "checks": [{"requirement": c.requirement, "status": c.status,
                               "explanation": c.explanation, "metrics": dict(c.metrics)}
                              for c in result.checks],
                   "tests": {r: {n: {"passed": ok, "mismatch": m} for n, (ok, m) in out.items()}
                             for r, out in context.outcomes.items()}}
    (output / "report.json").write_text(json.dumps(report, indent=1))
    if result is not None and error is None:
        (output / "reward.json").write_text(json.dumps({"reward": result.metrics["reward"]}) + "\n")


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("reward.json", "reward.txt"):
        (OUTPUT / name).unlink(missing_ok=True)
    context = None
    try:
        if os.geteuid() != 0:
            raise EvaluationError("the verifier must start as root to run the submission as another user")
        if not APP.is_dir():
            raise EvaluationError(f"{APP} was not delivered")
        shutil.rmtree(WORK, ignore_errors=True)
        WORK.mkdir(mode=0o711)
        context = VerificationContext(app=APP, dataset=DATASET, tests=load_tests(DATASET), output=OUTPUT,
                                      uid=UID, gid=GID, workers=processors(),
                                      build_timeout=BUILD_TIMEOUT, work=WORK)
        result = verify(context)
        write_report(OUTPUT, context, result, None)
        print(json.dumps(dict(result.metrics)))
        return 0
    except Exception as e:
        write_report(OUTPUT, context, None, f"{type(e).__name__}: {e}")
        print(f"evaluation error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
