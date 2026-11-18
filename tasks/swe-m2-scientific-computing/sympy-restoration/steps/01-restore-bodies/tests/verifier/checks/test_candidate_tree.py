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
        CandidateFailure: `/app/sympy` is missing, or every unit still carries
            its placeholder or was rejected.
        EvaluationError: The measurement could not be completed.
    """
    m = measurement(context)
    if not m.artifact_present:
        raise CandidateFailure("The artifact /app/sympy is missing or is not a directory")
    restored = m.counts["units_restored"]
    if restored == 0:
        raise CandidateFailure("No unit body was restored")
    return CheckResult(
        "candidate_tree", "passed",
        f"{restored} of {m.counts['units_total']} unit bodies were accepted into the graded tree",
        {"units_restored": float(restored), "units_total": float(m.counts["units_total"])},
    )
