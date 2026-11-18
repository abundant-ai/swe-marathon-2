"""Share of the graded SymPy test cases that pass."""

from __future__ import annotations

from verifier.checks.support import measurement, share
from verifier.contracts import CandidateFailure, CheckResult, VerificationContext


def test_repository_tests(context: VerificationContext) -> CheckResult:
    """Require the published share of passing repository tests.

    Tests not reached within the time budget, skipped or errored count as
    failed; the denominator is the full graded list.

    Args:
        context: Evaluation context.

    Returns:
        A passed result with the share and its numerator and denominator.

    Raises:
        CandidateFailure: The share is below the published threshold.
    """
    m = measurement(context)
    passing, total = m.counts["tests_passing"], m.counts["tests_total"]
    rate, bar = share(passing, total), context.scoring.test_bar
    text = f"{passing} of {total} graded repository tests pass ({rate:.4f}); required {bar:.2f}"
    if rate < bar:
        raise CandidateFailure(text)
    return CheckResult("repository_tests", "passed", text, {"test_pass_rate": rate})
