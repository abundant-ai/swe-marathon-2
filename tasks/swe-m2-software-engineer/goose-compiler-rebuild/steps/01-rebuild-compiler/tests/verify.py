"""Harbor entry point: run the private cases against the submitted program and publish the result."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.runcases import CASE_SEC, WORKSPACE, run_case  # noqa: E402

SANDBOX_USER = "nobody"
REWARD_FILES = ("reward.txt", "reward.json")
TOTAL_SEC = 3300  # the step verifier has 3,600 s; 1,500 runs at the per-run limit take at most 3,000 s


class EvaluationError(Exception):
    """Evaluation could not be carried out; no valid reward may be published."""


def grade(program: Path, private: Path) -> dict:
    """Run every private case as the unprivileged user and count exact matches.

    Raises:
        EvaluationError: Private inputs are unreadable or privileges cannot be dropped.
    """
    try:
        cases = json.loads((private / "cases.json").read_text())["cases"]
        expected = json.loads((private / "expected.json").read_text())
    except (OSError, ValueError, KeyError) as exc:
        raise EvaluationError("Private cases are unreadable") from exc
    if not cases or any(case["id"] not in expected for case in cases):
        raise EvaluationError("Private cases and recorded answers do not match")
    prefix = ["setpriv", "--reuid", SANDBOX_USER, "--regid", "nogroup", "--clear-groups"]
    if shutil.which("setpriv") is None or subprocess.run(prefix + ["true"], capture_output=True).returncode != 0:
        raise EvaluationError("Could not drop privileges; submitted code was not run")
    metrics = {"cases_total": len(cases), "cases_passed": 0, "reward": 0.0, "timeouts": 0, "notes": [], "by_command": {}}
    for case in cases:
        metrics["by_command"].setdefault(case["argv"][0], {"total": 0, "passed": 0})["total"] += 1
    if not program.is_file() or not os.access(program, os.X_OK):
        metrics["notes"].append("/app/rebuild/goose is missing or not executable")
        return metrics
    subprocess.run(["chmod", "-R", "a+rX", str(program.parent)], check=False)
    failed = []
    started = time.monotonic()
    for case in cases:
        if time.monotonic() - started > TOTAL_SEC:
            metrics["notes"].append(f"stopped after {TOTAL_SEC} seconds of runs; the remaining cases count as failed")
            break
        got, want = run_case([str(program)], case, prefix=prefix, owner=f"{SANDBOX_USER}:nogroup"), expected[case["id"]]
        if got.get("error") == "timeout":
            metrics["timeouts"] += 1
        if got["exit"] == want["exit"] and got["stdout"] == want["stdout"]:
            metrics["cases_passed"] += 1
            metrics["by_command"][case["argv"][0]]["passed"] += 1
        else:
            failed.append(case["id"])
        if metrics["timeouts"] >= 60:
            metrics["notes"].append(f"stopped after 60 runs that took longer than {CASE_SEC} seconds; the remaining cases count as failed")
            break
    shutil.rmtree(WORKSPACE, ignore_errors=True)
    metrics["reward"] = round(metrics["cases_passed"] / len(cases), 6)
    metrics["failed_sample"] = failed[:200]
    return metrics


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
        metrics = grade(Path("/app/rebuild/goose"), tests / "private")
        (output / "metrics.json").write_text(json.dumps(dict(metrics, status="completed"), indent=1, sort_keys=True) + "\n")
        (output / "reward.txt").write_text(f"{metrics['reward']:.6f}")
        print(f"reward: {metrics['reward']:.6f} ({metrics['cases_passed']}/{metrics['cases_total']} cases)", flush=True)
        code = 0
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        for name in REWARD_FILES:
            (output / name).unlink(missing_ok=True)
        (output / "metrics.json").write_text(json.dumps({"status": "evaluation_error", "error": message}) + "\n")
    finally:
        if shutil.which("pkill"):
            subprocess.run(["pkill", "-9", "-u", SANDBOX_USER], check=False)
        subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
