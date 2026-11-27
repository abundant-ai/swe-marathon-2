"""Report each reconstruction requirement independently from the continuous task reward."""

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class VerificationContext:
    """Trusted protocol version for the separate numerical rebuild."""

    mode: str


@dataclass(frozen=True)
class ReconstructionMeasurements:
    """Outcome of rebuilding this submission and measuring its held-out views."""

    mode: str
    report: dict


@dataclass(frozen=True)
class CheckResult:
    requirement_id: str
    status: Literal["passed", "failed", "skipped"]
    explanation: str
    measurements: Mapping[str, float]


@dataclass(frozen=True)
class VerificationResult:
    """Independent requirement outcomes and the physical evidence used to compute them."""

    report: dict
    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: Mapping[str, float]


def test_transferred_scene(context: ReconstructionMeasurements) -> CheckResult:
    valid = context.report["build"] == "valid"
    return CheckResult(
        "scene",
        "passed" if valid else "failed",
        "Transferred source produced a valid scene."
        if valid
        else context.report["reason"],
        {},
    )


def test_final_source(context: ReconstructionMeasurements) -> CheckResult:
    if "source_sha256" not in context.report:
        return CheckResult(
            "final_test", "skipped", "No transferred source digest is available.", {}
        )
    valid = context.report["test_receipt_matches"]
    return CheckResult(
        "final_test",
        "passed" if valid else "failed",
        "Final-source smoke receipt matched."
        if valid
        else "No matching final-source smoke receipt.",
        {},
    )


def measure(
    context: ReconstructionMeasurements,
    ident: str,
    field: tuple[str, ...],
    explanation: str,
) -> CheckResult:
    if context.report["build"] != "valid":
        return CheckResult(
            ident, "skipped", "Requires a valid reconstructed scene.", {}
        )
    data = context.report["measured"]
    for key in field:
        data = data[key]
    value = float(data)
    return CheckResult(
        ident, "passed" if value >= 0.5 else "failed", explanation, {field[-1]: value}
    )


def test_functional_parts(context: ReconstructionMeasurements) -> CheckResult:
    return measure(
        context,
        "fine_parts",
        ("part_success",),
        "Mean per-part silhouette success on unseen views.",
    )


def test_metric_objects(context: ReconstructionMeasurements) -> CheckResult:
    return measure(
        context,
        "parent_surfaces",
        ("object_depth_f1",),
        "Macro object F1 for surface depth within 3 cm.",
    )


def test_colored_scene(context: ReconstructionMeasurements) -> CheckResult:
    return measure(
        context,
        "colored_scene",
        ("whole_scene", "rgbd_5cm_10percent_coverage"),
        "Fraction of measured pixels recovered within 5 cm and the color tolerance.",
    )


def test_registration(context: ReconstructionMeasurements) -> CheckResult:
    return measure(
        context,
        "physical_registration",
        ("rig_registration", "reacquisition_rate"),
        "Independent rig poses hitting measured contact-scale tolerances.",
    )


BASE_CHECKS: tuple[
    tuple[str, Callable[[ReconstructionMeasurements], CheckResult]], ...
] = (
    ("scene", test_transferred_scene),
    ("final_test", test_final_source),
    ("fine_parts", test_functional_parts),
    ("parent_surfaces", test_metric_objects),
    ("colored_scene", test_colored_scene),
)


def summarize(context: ReconstructionMeasurements) -> VerificationResult:
    """Collect the complete check registry for one rebuilt or invalid source."""
    checks = BASE_CHECKS
    if context.mode == "rig":
        checks += (("physical_registration", test_registration),)
    results = tuple(check(context) for _, check in checks)
    if tuple(r.requirement_id for r in results) != tuple(key for key, _ in checks):
        raise RuntimeError("A check did not report its registered requirement")
    metrics = {k: v for r in results for k, v in r.measurements.items()}
    metrics["reward"] = float(context.report["reward"])
    return VerificationResult(
        context.report, all(r.status == "passed" for r in results), results, metrics
    )


def as_report(result: VerificationResult) -> dict:
    """Serialize diagnostics without duplicating the archived raw measurements."""
    return {
        "passed": result.passed,
        "checks": [asdict(check) for check in result.checks],
        "metrics": dict(result.metrics),
    }
