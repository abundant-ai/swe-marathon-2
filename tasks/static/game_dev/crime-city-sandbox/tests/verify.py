"""Grade the collected game and publish the reward (verifier entry point).

In the verifier container: python3 -I -B /tests/verify.py (tests/test.sh). On the
development Mac, every path can be given on the command line (see --help) and
QA_MEM_FLOOR=30 makes every game process wait for 30% free memory.

Exit code 0: a reward was written (whatever it is). Exit code 1: an evaluation error
(the self-test failed or the grader's inputs are broken); no reward file exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# test.sh runs this file with python -I: imports resolve only from these folders.
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
if not (HERE / "kit").is_dir():  # the source tree: the kit lives in common/kit
    sys.path.insert(0, str(HERE.parent / "common" / "kit"))

from verifier.grade import REPORT, EvaluationError, GradeConfig, grade


def main() -> int:
    """Parse the command line, grade, and map the outcome to the exit code."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=Path, default=Path("/app/game"))
    ap.add_argument("--out", type=Path, default=Path("/logs/verifier"))
    ap.add_argument("--work", type=Path, default=Path("/tmp/qa-grade"))
    ap.add_argument("--godot", default="/opt/godot/godot")
    ap.add_argument(
        "--library", type=Path, default=HERE / "telemetry" / "libtelemetry.so"
    )
    ap.add_argument(
        "--instances", type=Path, default=HERE / "private" / "instances.json"
    )
    ap.add_argument("--selftest", type=Path, default=HERE / "selftest")
    ap.add_argument("--denylist", type=Path, default=HERE / "private" / "denylist.txt")
    ap.add_argument("--deadline-s", type=float, default=4800.0)
    ap.add_argument("--import-cap-s", type=float, default=600.0)
    ap.add_argument("--cache-cap-mb", type=float, default=1024.0)
    ap.add_argument("--boot-s", type=float, default=60.0)
    ap.add_argument("--no-server-boot", action="store_true")
    ap.add_argument("--skip-selftest", action="store_true", help="development only")
    ap.add_argument("--memory-mb", type=float, default=None, help="development only")
    ap.add_argument("--step-s", type=float, default=None, help="development only")
    a = ap.parse_args()
    cfg = GradeConfig(
        project=a.project.resolve(),
        out=a.out.resolve(),
        work=a.work.resolve(),
        godot=a.godot,
        library=a.library.resolve(),
        instances=a.instances.resolve(),
        selftest_dir=a.selftest.resolve(),
        denylist=a.denylist,
        deadline_s=a.deadline_s,
        import_cap_s=a.import_cap_s,
        cache_cap_mb=a.cache_cap_mb,
        boot_s=a.boot_s,
        server_boot=not a.no_server_boot,
        skip_selftest=a.skip_selftest,
        memory_mb=a.memory_mb,
        step_s=a.step_s,
    )
    try:
        reward = grade(cfg)
    except EvaluationError as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        report = cfg.out / REPORT
        if not report.exists():
            report.write_text(
                json.dumps({"status": "evaluation_error", "error": str(exc)})
            )
        return 1
    print(f"reward: {reward:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
