"""The measurements' own control results were reported correctly."""

from __future__ import annotations

from verifier.checks.support import measurement
from verifier.contracts import CandidateFailure, CheckResult, VerificationContext


def test_measurement_integrity(context: VerificationContext) -> CheckResult:
    """Fail when a runner reported a wrong outcome for a control item.

    Each runner carries items whose outcome is known in advance. A wrong
    report means submitted code changed how results are reported.

    Args:
        context: Evaluation context.

    Returns:
        A passed result when no control item was misreported.

    Raises:
        CandidateFailure: At least one control result was wrong.
    """
    m = measurement(context)
    if m.self_check_trips:
        raise CandidateFailure(
            "Control results were misreported: " + "; ".join(m.self_check_trips[:5])
        )
    return CheckResult(
        "measurement_integrity", "passed", "All control results were reported correctly"
    )
