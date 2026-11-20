"""Harbor entry point: build the trusted context, run the verifier, publish the result."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.config import load_config  # noqa: E402
from verifier.contracts import EvaluationError, VerificationContext  # noqa: E402
from verifier.reporting import REWARD_FILES, write_report  # noqa: E402
from verifier.runner import verify  # noqa: E402

SANDBOX_USER = "nobody"


def main() -> int:
    """Run one evaluation in this fresh container and map it to Harbor's files.

    Returns:
        Zero for a completed evaluation, including a failed submission; one for
        an evaluation error, which leaves no reward file.
    """
    tests = Path(__file__).resolve().parent
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    (output / "artifacts").mkdir(exist_ok=True)
    for name in REWARD_FILES + ("metrics.json", "report.json"):
        (output / name).unlink(missing_ok=True)
    context: VerificationContext | None = None
    code = 1
    try:
        if os.geteuid() != 0:
            raise EvaluationError("Verifier must start as root to isolate submitted code")
        # submitted code runs as an unprivileged user that can read none of these
        for closed in (tests, Path("/opt/grader"), output):
            closed.chmod(0o700)
        app = Path("/app")
        if app.is_dir():
            app.chmod(app.stat().st_mode & 0o700)
        scoring, limits = load_config()
        context = VerificationContext(
            work_tree=app, skeleton=Path("/opt/grader/skeleton"), private=tests / "private",
            output=output, scratch=Path("/work"), scoring=scoring, limits=limits,
        )
        result = verify(context)
        write_report(output, context, result, None)
        print(f"reward: {int(result.metrics['reward'])} partial_score: {result.metrics['partial_score']}", flush=True)
        code = 0
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        try:
            write_report(output, context, None, message)
        except OSError:
            for name in REWARD_FILES:
                (output / name).unlink(missing_ok=True)
    finally:
        # nothing of the submission may still be running; results become readable again
        if shutil.which("pkill"):
            subprocess.run(["pkill", "-9", "-u", SANDBOX_USER], check=False)
        subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
