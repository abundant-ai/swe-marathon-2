"""Harbor entry point: replay the private scenarios against the submitted server and publish the result."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.replay import EvaluationError, evaluate  # noqa: E402

SANDBOX_USER = "nobody"
REWARD_FILES = ("reward.txt", "reward.json")


def main() -> int:
    """Run one evaluation in this fresh container.

    Returns:
        Zero for a completed evaluation, including a failed submission; one for
        an evaluation error, which leaves no reward file.
    """
    tests = Path(__file__).resolve().parent
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    for name in REWARD_FILES + ("metrics.json",):
        (output / name).unlink(missing_ok=True)
    code = 1
    try:
        if os.geteuid() != 0:
            raise EvaluationError("Verifier must start as root to isolate submitted code")
        for closed in (tests, output):
            closed.chmod(0o700)
        scenarios = tests / "private" / "scenarios.json.gz"
        metrics = evaluate(Path("/app/server"), scenarios if scenarios.exists() else tests / "private" / "scenarios.json", Path("/work"), output)
        (output / "metrics.json").write_text(json.dumps(dict(metrics, status="completed"), indent=1, sort_keys=True) + "\n")
        (output / "reward.txt").write_text(f"{metrics['reward']:.6f}")
        print(f"reward: {metrics['reward']:.6f} ({metrics['scenarios_matched']}/{metrics['scenarios_total']} scenarios)", flush=True)
        code = 0
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        for name in REWARD_FILES:
            (output / name).unlink(missing_ok=True)
        (output / "metrics.json").write_text(json.dumps({"status": "evaluation_error", "error": message}) + "\n")
        (output / "verifier_error.txt").write_text(traceback.format_exc())
    finally:
        if shutil.which("pkill"):
            subprocess.run(["pkill", "-9", "-u", SANDBOX_USER], check=False)
        subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
