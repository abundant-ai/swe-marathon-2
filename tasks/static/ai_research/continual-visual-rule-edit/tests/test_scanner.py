"""Requirement-level diagnostics for a measured continual-learning installation."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Status = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class VerificationContext:
    """Paths and trusted measurements for this physical deployment and its individual checks."""

    target: str
    work: Path
    output: Path
    build: str = "pending"
    matched_smoke: bool | None = None
    station_scores: tuple[dict, ...] = ()
    reward: float = 0.0
    frozen_comparison: Mapping[str, float] | None = None


@dataclass(frozen=True)
class CheckResult:
    """A measured requirement with its fixed eligibility and quantitative evidence."""

    requirement_id: str
    status: Status
    explanation: str
    measurements: Mapping[str, float]


@dataclass(frozen=True)
class VerificationResult:
    """Mandatory conditions and the original continuous reward."""

    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: Mapping[str, float]


def test_installation(context: VerificationContext) -> CheckResult:
    """Report whether the transferred program returned a budget-compliant installation."""
    return CheckResult(
        "installation",
        "passed" if context.build == "valid" else "failed",
        f"The independent numerical rebuild was {context.build}.",
        {},
    )


def test_smoke(context: VerificationContext) -> CheckResult:
    """Check the submitted source receipt independently of learning performance."""
    status: Status = (
        "skipped"
        if context.matched_smoke is None
        else ("passed" if context.matched_smoke else "failed")
    )
    return CheckResult(
        "final_test",
        status,
        {
            "skipped": "The transferred editor source was unavailable for a staging rebuild.",
            "passed": "The final source and all three staging measurements reproduced.",
            "failed": "No final-source rehearsal record reproduced all three staging measurements.",
        }[status],
        {},
    )


def test_archive(context: VerificationContext) -> CheckResult:
    """Measure the six original systems against their public retention and drift limits."""
    if context.build != "valid":
        return CheckResult(
            "old_inspections", "skipped", "Requires a deployable checkpoint edit.", {}
        )
    loss = max(r["legacy_loss"] for r in context.station_scores)
    drift = max(r["score_drift"] for r in context.station_scores)
    return CheckResult(
        "old_inspections",
        "passed" if loss <= 0.02 and drift <= 0.08 else "failed",
        "Worst accuracy loss during deployment and normalized score drift at installation.",
        {"worst_archived_accuracy_loss": loss, "worst_installation_rms_drift": drift},
    )


DIMENSIONS = (
    "early_acquisition",
    "end_of_order",
    "final_revisit",
    "weakest_subgroup",
    "peak_forgetting",
)


def _learning(context: VerificationContext, index: int) -> CheckResult:
    """Report one completed behavioral measurement and the associated normalized gain.

    Args:
        context: Trusted station measurements on the frozen task target.
        index: Its position in the scorer's station metrics and gains.

    Full credit requires the calibrated outcome at all six sites. The report
    retains partial outcomes and raw values across the same six sites.
    """
    name = DIMENSIONS[index]
    if context.build != "valid":
        return CheckResult(
            name, "skipped", "Requires a deployable checkpoint edit.", {}
        )
    values = [s["metrics"][index] for s in context.station_scores]
    if name == "peak_forgetting":
        values = [-v for v in values]
    gains = [s["gains"][index] for s in context.station_scores]
    full_sites = sum(gain >= 1.0 - 1e-10 for gain in gains)
    return CheckResult(
        name,
        "passed" if full_sites == 6 else "failed",
        f"{full_sites} of six sites attained full credit across three draws of four orders.",
        {
            "mean_" + name: sum(values) / len(values),
            "mean_gain_" + name: sum(gains) / len(gains),
            "full_credit_sites_" + name: float(full_sites),
        },
    )


def test_early_acquisition(context: VerificationContext) -> CheckResult:
    """Report early acquisition on the selected deployment."""
    return _learning(context, 0)


def test_end_of_order(context: VerificationContext) -> CheckResult:
    """Report end of order on the selected deployment."""
    return _learning(context, 1)


def test_final_revisit(context: VerificationContext) -> CheckResult:
    """Report final revisit on the selected deployment."""
    return _learning(context, 2)


def test_weakest_subgroup(context: VerificationContext) -> CheckResult:
    """Report weakest subgroup on the selected deployment."""
    return _learning(context, 3)


def test_peak_forgetting(context: VerificationContext) -> CheckResult:
    """Report peak forgetting on the selected deployment."""
    return _learning(context, 4)


def test_adaptation(context: VerificationContext) -> CheckResult:
    """Compare the same installation learning versus frozen on the same four future orders."""
    if context.build != "valid":
        return CheckResult(
            "trunk_learning", "skipped", "Requires a deployable checkpoint edit.", {}
        )
    contrast = context.frozen_comparison
    if contrast is None or contrast["anchor"] < 0.01:
        raise RuntimeError("Missing measurable frozen-copy anchor")
    return CheckResult(
        "trunk_learning",
        "passed" if contrast["normalized"] >= 1 - 1e-10 else "failed",
        "End-of-order accuracy gained from training the installed rows across both banks.",
        {
            "gain_over_frozen_copy": contrast["mean"],
            "informed_gain": contrast["anchor"],
            "normalized_gain_over_frozen_copy": contrast["normalized"],
        },
    )


def requirement_results(context: VerificationContext) -> VerificationResult:
    """Collect independently reported requirements without changing the frozen model reward."""
    if context.build == "valid" and len(context.station_scores) != 6:
        raise RuntimeError("A valid build requires six complete station reports")
    checks = (
        test_installation(context),
        test_smoke(context),
        test_archive(context),
        test_adaptation(context),
        test_early_acquisition(context),
        test_end_of_order(context),
        test_final_revisit(context),
        test_weakest_subgroup(context),
        test_peak_forgetting(context),
    )
    expected = (
        "installation",
        "final_test",
        "old_inspections",
        "trunk_learning",
        *DIMENSIONS,
    )
    if tuple(c.requirement_id for c in checks) != expected:
        raise RuntimeError("Incomplete scanner requirement registry")
    metrics = {
        key: value for check in checks for key, value in check.measurements.items()
    }
    metrics["reward"] = context.reward
    return VerificationResult(
        all(c.status == "passed" for c in checks), checks, metrics
    )
