"""Turn check results into the published reward."""

from __future__ import annotations

from collections.abc import Sequence

from verifier.contracts import (
    CheckResult,
    EvaluationError,
    Measurement,
    VerificationResult,
)

# the reward is published only when these hold; without them it is 0
GATES = ("candidate_tree", "measurement_integrity")
# all five hold for a complete restoration (`complete` in metrics.json)
MANDATORY = (
    "candidate_tree",
    "unit_restoration",
    "reference_calls",
    "repository_tests",
    "measurement_integrity",
)
# each bar of a complete restoration: its check, its numerator and denominator, the items the
# measurement did not reach, the bar
BARS = (
    (
        "unit_restoration",
        "units_passing",
        "units_total",
        "units_not_reached",
        "unit_bar",
    ),
    (
        "reference_calls",
        "vectors_passing",
        "vectors_total",
        "vectors_not_reached",
        "vector_bar",
    ),
    (
        "repository_tests",
        "tests_passing",
        "tests_total",
        "tests_not_reached",
        "test_bar",
    ),
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


def aggregate_results(
    checks: Sequence[CheckResult], measurement: Measurement | None
) -> VerificationResult:
    """Compute the reward and the diagnostic shares.

    The reward is min(unit_share, call_share) when `candidate_tree` and
    `measurement_integrity` passed, otherwise 0. The counted calls are those
    that are not documented (no docstring example or visible test makes them,
    and their result is neither a documented result of their unit nor one of
    their own arguments); unit_share is the share of the units with a counted
    call whose examples pass and at least `unit_deciding_share` of whose counted
    calls (at least one) match; call_share is the share of counted calls that
    match. The repository tests are reported, not rewarded. `complete` keeps the
    three bars of the binary reward, not the instruction's sense of complete:
    True when all five checks passed, None when only items the measurement did
    not reach keep a bar from being met.

    Args:
        checks: One result per registered check, in registry order.
        measurement: The evaluation's measurement, or None if no check ran it.

    Returns:
        The verdict with the reward, `complete` and the shares.

    Raises:
        EvaluationError: Items the measurement did not reach could change the
            reward by more than its tolerance: the time the measurement had, not
            the submission, would decide it.
    """
    status = {check.requirement: check.status for check in checks}
    gated = all(status.get(name) == "passed" for name in GATES)
    counts = measurement.counts if measurement else {}
    details = measurement.details if measurement else {}

    def rate(numerator: str, denominator: str) -> float:
        total = counts.get(denominator, 0)
        return counts.get(numerator, 0) / total if total else 0.0

    unit_share, call_share = (
        rate("units_set_passing", "units_set"),
        rate("deciding_passing", "deciding_total"),
    )
    reward = round(min(unit_share, call_share), 6) if gated else 0.0
    if gated:
        reachable = min(
            float(details.get("unit_share_if_reached", unit_share)),
            float(details.get("call_share_if_reached", call_share)),
        )
        if reachable - min(unit_share, call_share) > float(
            details.get("reward_tolerance", 0.001)
        ):
            raise EvaluationError(
                f"The reward depends on items the measurement did not reach: {min(unit_share, call_share):.4f} as "
                f"measured, up to {reachable:.4f} had they been reached"
            )
    complete = all(status.get(name) == "passed" for name in MANDATORY)
    open_bars = undetermined(status, measurement)
    if (
        not complete
        and open_bars
        and all(
            status.get(name) == "passed" for name in MANDATORY if name not in open_bars
        )
    ):
        complete = (
            None  # the time the measurement had, not the submission, keeps a bar open
        )
    metrics = {
        "reward": reward,
        "complete": complete,
        "unit_share": round(unit_share, 6),
        "call_share": round(call_share, 6),
        "test_share": round(rate("tests_passing", "tests_total"), 6),
        "unit_pass_rate": round(rate("units_passing", "units_total"), 6),
        "call_match_rate": round(rate("vectors_passing", "vectors_total"), 6),
        "test_pass_rate": round(rate("tests_passing", "tests_total"), 6),
    }
    return VerificationResult(gated, tuple(checks), metrics)
