"""Report each reconstruction requirement independently from the continuous task reward."""

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class VerificationContext:
    report: dict


@dataclass(frozen=True)
class CheckResult:
    requirement_id: str
    status: Literal["passed", "failed", "skipped"]
    explanation: str
    measurements: Mapping[str, float]


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: Mapping[str, float]


def test_transferred_scene(context: VerificationContext) -> CheckResult:
    valid = context.report["build"] == "valid"
    return CheckResult(
        "scene",
        "passed" if valid else "failed",
        "Transferred source produced a valid scene."
        if valid
        else context.report["reason"],
        {},
    )


def test_final_source(context: VerificationContext) -> CheckResult:
    if "source_sha256" not in context.report:
        return CheckResult(
            "final_test", "skipped", "No transferred source digest is available.", {}
        )
    valid = context.report["test_receipt_matches"]
    return CheckResult(
        "final_test",
        "passed" if valid else "failed",
        "Independent rebuild reproduced the source and mesh recorded in the rehearsal."
        if valid
        else "No rehearsal record matched the independently rebuilt geometry.",
        {},
    )


def measure(
    context: VerificationContext, ident: str, field: tuple[str, ...], explanation: str
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


def test_functional_parts(context: VerificationContext) -> CheckResult:
    return measure(
        context,
        "fine_parts",
        ("part_success",),
        "Mean per-part silhouette success on unseen views.",
    )


def test_metric_objects(context: VerificationContext) -> CheckResult:
    return measure(
        context,
        "parent_surfaces",
        ("object_depth_f1",),
        "Macro object F1 for surface depth within 3 cm.",
    )


def test_colored_scene(context: VerificationContext) -> CheckResult:
    return measure(
        context,
        "colored_scene",
        ("whole_scene", "rgbd_5cm_10percent_coverage"),
        "Fraction of measured pixels recovered within 5 cm and the color tolerance.",
    )


BASE_CHECKS: tuple[tuple[str, Callable[[VerificationContext], CheckResult]], ...] = (
    ("scene", test_transferred_scene),
    ("final_test", test_final_source),
    ("fine_parts", test_functional_parts),
    ("parent_surfaces", test_metric_objects),
    ("colored_scene", test_colored_scene),
)


def verify(context: VerificationContext) -> VerificationResult:
    checks = BASE_CHECKS
    results = tuple(check(context) for _, check in checks)
    if tuple(r.requirement_id for r in results) != tuple(key for key, _ in checks):
        raise RuntimeError("A check did not report its registered requirement")
    metrics = {k: v for r in results for k, v in r.measurements.items()}
    metrics["reward"] = float(context.report["reward"])
    return VerificationResult(
        all(r.status == "passed" for r in results), results, metrics
    )


def as_report(report):
    return asdict(verify(VerificationContext(report)))
