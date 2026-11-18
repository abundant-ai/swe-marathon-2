"""Share of replayed calls whose result equals the reference result."""

from __future__ import annotations

from verifier.checks.support import measurement, share
from verifier.contracts import CandidateFailure, CheckResult, VerificationContext


def test_reference_calls(context: VerificationContext) -> CheckResult:
    """Require the published share of matching replayed calls.

    Args:
        context: Evaluation context.

    Returns:
        A passed result with the share and its numerator and denominator.

    Raises:
        CandidateFailure: The share is below the published threshold.
    """
    m = measurement(context)
    passing, total = m.counts["vectors_passing"], m.counts["vectors_total"]
    rate, bar = share(passing, total), context.scoring.call_bar
    text = f"{passing} of {total} replayed calls match the reference ({rate:.4f}); required {bar:.2f}"
    if rate < bar:
        raise CandidateFailure(text)
    return CheckResult("reference_calls", "passed", text, {"call_match_rate": rate})
