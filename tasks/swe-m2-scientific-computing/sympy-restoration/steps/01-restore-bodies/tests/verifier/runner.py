"""Run the registry, keep every outcome, and separate invalid evaluations."""

from __future__ import annotations

from verifier.contracts import CandidateFailure, CheckResult, VerificationContext, VerificationResult
from verifier.registry import CHECKS
from verifier.scoring import aggregate_results


def verify(context: VerificationContext) -> VerificationResult:
    """Run registered requirement checks and aggregate their results.

    Args:
        context: Trusted paths, thresholds and limits for one fresh container.

    Returns:
        One result per registry entry and the reward. A failed or skipped
        `candidate_tree` or `measurement_integrity` gives reward 0.

    Raises:
        EvaluationError: Infrastructure failure. Completed results stay in
            context.completed for the entry point to record.
    """
    context.completed.clear()
    outcomes: dict[str, CheckResult] = {}
    for check in CHECKS:
        unmet = [name for name in check.requires if outcomes[name].status != "passed"]
        if unmet:
            result = CheckResult(check.name, "skipped", f"Unmet prerequisites: {', '.join(unmet)}")
        else:
            try:
                result = check.function(context)
            except CandidateFailure as exc:
                result = CheckResult(check.name, "failed", str(exc))
        outcomes[check.name] = result
        context.completed.append(result)
    return aggregate_results(context.completed, context.measurement)
