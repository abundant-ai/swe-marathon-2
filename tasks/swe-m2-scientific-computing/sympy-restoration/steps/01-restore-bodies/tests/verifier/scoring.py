"""Turn check results into the published reward."""

from __future__ import annotations

from typing import Sequence

from verifier.contracts import CheckResult, EvaluationError, Measurement, VerificationResult

MANDATORY = ("candidate_tree", "unit_restoration", "reference_calls", "repository_tests", "measurement_integrity")
# each bar: its check, its numerator and denominator, the items the measurement did not reach, the bar
BARS = (
    ("unit_restoration", "units_passing", "units_total", "units_not_reached", "unit_bar"),
    ("reference_calls", "vectors_passing", "vectors_total", "vectors_not_reached", "vector_bar"),
    ("repository_tests", "tests_passing", "tests_total", "tests_not_reached", "test_bar"),
)


def undetermined(status: dict, measurement: Measurement | None) -> list[str]:
    """The failed bars that the items the measurement did not reach could still have met."""
    if measurement is None:
        return []
    counts, details = measurement.counts, measurement.details
    open_bars = []
    for check, passing, total, unreached, bar in BARS:
        if status.get(check) != "failed" or not counts.get(total):
            continue
        reach = counts.get(passing, 0) + int(details.get(unreached) or 0)
        if reach / counts[total] >= float(details.get(bar, 1.0)):
            open_bars.append(check)
    return open_bars


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

    Raises:
        EvaluationError: Every other condition is met and a failed bar would be
            met if the items the measurement did not reach passed.
    """
    status = {check.requirement: check.status for check in checks}
    passed = all(status.get(name) == "passed" for name in MANDATORY)
    counts = measurement.counts if measurement else {}
    open_bars = undetermined(status, measurement)
    if open_bars and all(status.get(name) == "passed" for name in MANDATORY if name not in open_bars):
        # the time the measurement had, not the submission, would decide the verdict
        raise EvaluationError("The verdict depends on items the measurement did not reach: " + ", ".join(open_bars))

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
