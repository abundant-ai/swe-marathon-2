"""Turn check results into the published reward."""

from __future__ import annotations

from typing import Sequence

from verifier.contracts import CheckResult, Measurement, VerificationResult

MANDATORY = ("candidate_tree", "unit_restoration", "reference_calls", "repository_tests", "measurement_integrity")


def aggregate_results(checks: Sequence[CheckResult], measurement: Measurement | None) -> VerificationResult:
    """Compute the binary reward and the diagnostic partial score.

    reward is 1 when every mandatory check passed, otherwise 0. partial_score is
    the pooled share of passing units, matching calls and passing tests over
    their fixed totals; it is reported for analysis and never changes the reward.

    Args:
        checks: One result per registered check, in registry order.
        measurement: The evaluation's measurement, or None if no check ran it.

    Returns:
        The verdict with reward, partial_score and the three shares.
    """
    status = {check.requirement: check.status for check in checks}
    passed = all(status.get(name) == "passed" for name in MANDATORY)
    counts = measurement.counts if measurement else {}

    def rate(numerator: str, denominator: str) -> float:
        total = counts.get(denominator, 0)
        return counts.get(numerator, 0) / total if total else 0.0

    totals = sum(counts.get(k, 0) for k in ("units_total", "vectors_total", "tests_total"))
    passing = sum(counts.get(k, 0) for k in ("units_passing", "vectors_passing", "tests_passing"))
    metrics = {
        "reward": 1.0 if passed else 0.0,
        "partial_score": round(passing / totals, 6) if totals else 0.0,
        "unit_pass_rate": round(rate("units_passing", "units_total"), 6),
        "call_match_rate": round(rate("vectors_passing", "vectors_total"), 6),
        "test_pass_rate": round(rate("tests_passing", "tests_total"), 6),
    }
    return VerificationResult(passed, tuple(checks), metrics)
