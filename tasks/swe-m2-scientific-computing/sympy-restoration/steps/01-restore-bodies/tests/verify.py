"""Verifier entry point: build the trusted context, run the verifier, publish the result."""

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
ROOM_BYTES = 64 << 20   # set aside on the result's file system before anything runs, given back to write the result


def set_aside(path: Path) -> None:
    """Hold ROOM_BYTES at `path`, so that however full the sandbox leaves the disk, the result still fits."""
    try:
        with open(path, "wb") as handle:
            try:
                os.posix_fallocate(handle.fileno(), 0, ROOM_BYTES)
            except (AttributeError, OSError):
                for _ in range(ROOM_BYTES >> 20):
                    handle.write(bytes(1 << 20))
    except OSError:
        pass


def give_back(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> int:
    """Run one evaluation in this fresh container and write the result files.

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
    room = output / ".room"
    set_aside(room)
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
        give_back(room)
        write_report(output, context, result, None)
        print(f"reward: {result.metrics['reward']:.6f} unit_share: {result.metrics['unit_share']} "
              f"call_share: {result.metrics['call_share']} complete: {result.metrics['complete']}", flush=True)
        code = 0
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        give_back(room)
        try:
            write_report(output, context, None, message)
        except OSError:
            for name in REWARD_FILES:
                (output / name).unlink(missing_ok=True)
    finally:
        give_back(room)
        # nothing of the submission may still be running; results become readable again
        if shutil.which("pkill"):
            subprocess.run(["pkill", "-9", "-u", SANDBOX_USER], check=False)
        subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
