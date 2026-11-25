"""The submission exists and restores at least one unit."""

from __future__ import annotations

from verifier.checks.support import measurement
from verifier.contracts import CandidateFailure, CheckResult, VerificationContext


def test_candidate_tree(context: VerificationContext) -> CheckResult:
    """Require the declared artifact and at least one restored unit body.

    Args:
        context: Evaluation context.

    Returns:
        A passed result with the number of restored units.

    Raises:
        CandidateFailure: The collect step found no tree to deliver (refused or
            absent), or every unit still carries its placeholder, was rejected
            or was changed after the end of the work.
        EvaluationError: The measurement could not be completed, among others
            because nothing arrived or the copy does not match its record.
    """
    m = measurement(context)
    if not m.artifact_present:
        raise CandidateFailure(
            "No tree was delivered: the collect step found it refused or absent"
        )
    restored = m.counts["units_restored"]
    if restored == 0:
        raise CandidateFailure("No unit body was restored")
    return CheckResult(
        "candidate_tree",
        "passed",
        f"{restored} of {m.counts['units_total']} unit bodies were accepted into the measured tree",
        {
            "units_restored": float(restored),
            "units_total": float(m.counts["units_total"]),
        },
    )
