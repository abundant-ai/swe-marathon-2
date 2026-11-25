"""Publish diagnostics, and a reward only for a completed evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from verifier.contracts import VerificationContext, VerificationResult

REWARD_FILES = ("reward.txt", "reward.json")


def write_report(
    output: Path,
    context: VerificationContext | None,
    result: VerificationResult | None,
    error: str | None,
) -> None:
    """Write report.json and metrics.json, and reward.txt only for a valid result.

    Args:
        output: Trusted verifier log directory.
        context: Partial observations, if the context was built.
        result: Completed evaluation; None means no valid reward.
        error: Safe diagnostic for an evaluation error.
    """
    for name in REWARD_FILES:
        (output / name).unlink(missing_ok=True)
    measurement = context.measurement if context else None
    payload = {
        "status": "evaluation_error" if result is None else "completed",
        "error": error,
        "scoring": asdict(context.scoring) if context else None,
        "result": asdict(result) if result else None,
        "completed_checks": [asdict(check) for check in context.completed]
        if context
        else [],
    }
    (output / "report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metrics = dict(measurement.details) if measurement else {}
    metrics["status"] = payload["status"]
    if result is None:
        metrics["error"] = error
        metrics.pop("reward", None)
    else:
        metrics.update(result.metrics)
        metrics["reward"] = float(result.metrics["reward"])
        metrics["checks"] = {check.requirement: check.status for check in result.checks}
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if result is not None:
        (output / "reward.txt").write_text(
            f"{float(result.metrics['reward']):.6f}", encoding="utf-8"
        )
