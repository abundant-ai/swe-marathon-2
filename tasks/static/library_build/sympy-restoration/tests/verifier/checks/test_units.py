"""Bar of a complete restoration: share of units whose examples pass and that match a recorded call."""

from __future__ import annotations

from verifier.checks.support import measurement, share
from verifier.contracts import CandidateFailure, CheckResult, VerificationContext


def test_unit_restoration(context: VerificationContext) -> CheckResult:
    """Require the published share of passing units for a complete restoration.

    A unit passes when every example in its own docstring passes and at least
    one of its replayed calls matches the reference result.

    Args:
        context: Evaluation context.

    Returns:
        A passed result with the share and its numerator and denominator.

    Raises:
        CandidateFailure: The share is below the published threshold.
    """
    m = measurement(context)
    passing, total = m.counts["units_passing"], m.counts["units_total"]
    rate, bar = share(passing, total), context.scoring.unit_bar
    text = f"{passing} of {total} units pass ({rate:.4f}); required {bar:.2f}"
    if rate < bar:
        raise CandidateFailure(text)
    return CheckResult("unit_restoration", "passed", text, {"unit_pass_rate": rate})
