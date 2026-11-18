"""Harbor entry point: replay the private scenarios against the submitted server and publish the result."""

from __future__ import annotations

import contextlib
import json
import os
import pwd
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.replay import RUN_AS, EvaluationError, end_user_processes, evaluate  # noqa: E402

REWARD_FILES = ("reward.txt", "reward.json")
PENDING = ".reward.pending"
PLACEHOLDER = b"0.000000"  # a reward in [0, 1] written with six decimals always has this length


def reserve(output: Path) -> None:
    """Before any submitted code runs, write a placeholder the size of the reward under another name.

    The server may fill the disk while it runs (QA 07 F2). The reward is later written over the
    placeholder's bytes in place and renamed, which needs no free space.
    """
    with open(output / PENDING, "wb") as placeholder:
        placeholder.write(PLACEHOLDER)
        placeholder.flush()
        os.fsync(placeholder.fileno())


def publish(output: Path, metrics: dict[str, Any]) -> None:
    """Write the reward first, then the summary, then the per-scenario diagnostics.

    The reward goes over the placeholder `reserve` wrote, when there is one; the diagnostics can be
    large, and a full disk or any other failure writing them costs only those files.
    """
    results = metrics.pop("results", [])
    reward = f"{metrics['reward']:.6f}".encode()
    pending = output / PENDING
    if pending.is_file():
        with open(pending, "r+b") as placeholder:
            placeholder.write(reward)
            placeholder.truncate(len(reward))
        os.replace(pending, output / "reward.txt")
    else:
        (output / "reward.txt").write_bytes(reward)
    for name, text in (("metrics.json", json.dumps(dict(metrics, status="completed"), indent=1, sort_keys=True) + "\n"),
                       ("scenario_results.json", json.dumps(results))):
        try:
            (output / name).write_text(text)
        except OSError as exc:
            print(f"could not write {name}: {exc}", flush=True)


def main() -> int:
    """Run one evaluation in this fresh container.

    Returns:
        Zero for a completed evaluation, including a failed submission; one for
        an evaluation error, which leaves no reward file.
    """
    tests = Path(__file__).resolve().parent
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    for name in REWARD_FILES + ("metrics.json", PENDING):
        (output / name).unlink(missing_ok=True)
    code = 1
    try:
        if os.geteuid() != 0:
            raise EvaluationError("Verifier must start as root to isolate submitted code")
        for closed in (tests, output):
            closed.chmod(0o700)
        reserve(output)
        scenarios = tests / "private" / "scenarios.json.gz"
        metrics = evaluate(Path("/app/server"), scenarios if scenarios.exists() else tests / "private" / "scenarios.json", Path("/work"), output)
        publish(output, metrics)
        print(f"reward: {metrics['reward']:.6f} ({metrics['units_matched']}/{metrics['units_total']} units)", flush=True)
        code = 0
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        for name in REWARD_FILES + (PENDING,):
            with contextlib.suppress(OSError):
                (output / name).unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            (output / "metrics.json").write_text(json.dumps({"status": "evaluation_error", "error": message}) + "\n")
            (output / "verifier_error.txt").write_text(traceback.format_exc())
    finally:
        with contextlib.suppress(Exception):
            end_user_processes(pwd.getpwnam(RUN_AS).pw_uid)
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False, capture_output=True, timeout=120)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
