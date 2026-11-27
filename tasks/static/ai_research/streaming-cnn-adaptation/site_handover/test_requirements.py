"""Registered acceptance checks for source training and paired scanner deployments."""

from dataclasses import dataclass

from test_training import CheckResult


@dataclass(frozen=True)
class MeasurementContext:
    """Trusted observations and classified candidate errors from independent measurement runs."""

    outcomes: dict[str, CheckResult]
    evidence: dict


def test_checkpoint(context: MeasurementContext) -> CheckResult:
    """Require a validated checkpoint with a digest of its numerical state."""
    if "source_state_sha256" not in context.evidence:
        return context.outcomes["submitted_checkpoint"]
    return CheckResult(
        "submitted_checkpoint",
        "passed",
        "Loaded fixed CNN state and computed held-out predictions.",
    )


def test_training(context: MeasurementContext) -> CheckResult:
    """Report whether a fresh invocation produced a loadable CNN."""
    return context.outcomes["source_training"]


def test_source_labels(context: MeasurementContext) -> CheckResult:
    """Require paired predictions to track the sensor-specific source assignments."""
    info = context.evidence
    if "relabeled_source_accuracy" not in info:
        return context.outcomes["source_label_dependence"]
    score, floor = info["relabeled_source_accuracy"], info["relabeled_source_minimum"]
    return CheckResult(
        "source_label_dependence",
        "passed" if score + 1e-12 >= floor else "failed",
        "Paired accuracy under two different source vocabularies.",
        {"accuracy": score, "minimum": floor},
    )


def test_reproducibility(context: MeasurementContext) -> CheckResult:
    """Test source agreement and the accuracy gap on held-out predictions."""
    if "training_replay" not in context.evidence:
        return context.outcomes["reproducibility"]
    replay = context.evidence["training_replay"]
    delta = abs(replay["submitted_accuracy"] - replay["rebuilt_accuracy"])
    ok = replay["prediction_agreement"] >= 0.8 and delta <= 0.05 + 1e-12
    return CheckResult(
        "reproducibility",
        "passed" if ok else "failed",
        "Held-out source predictions agree.",
        {"agreement": replay["prediction_agreement"], "accuracy_delta": delta},
    )


def test_source_competence(context: MeasurementContext) -> CheckResult:
    """Compare both independently evaluated source accuracies with the same floor."""
    if "training_replay" not in context.evidence:
        return context.outcomes["source_competence"]
    replay = context.evidence["training_replay"]
    floor = context.evidence["source_competence"]["minimum"]
    observed = min(replay["submitted_accuracy"], replay["rebuilt_accuracy"])
    return CheckResult(
        "source_competence",
        "passed" if observed + 1e-12 >= floor else "failed",
        "Weaker of the submitted and rebuilt headquarters accuracies.",
        {"accuracy": observed, "minimum": floor},
    )


def test_stream_program(context: MeasurementContext) -> CheckResult:
    """Report source presence and isolated replay eligibility."""
    return context.outcomes["stream_program"]


def installation(context: MeasurementContext, world: str) -> CheckResult:
    """Count completed native measurements against the twelve expected start/order/schedule combinations."""
    name = "deployment_" + world
    runs = context.evidence.get("runs")
    if not runs:
        return context.outcomes[name]
    completed = sum("error" not in r for start in runs.values() for r in start[world])
    return CheckResult(
        name,
        "passed" if completed == 12 else "failed",
        "Completed independent CNN and itinerary measurements.",
        {"completed": completed, "expected": 12},
    )


def test_first_installation(context: MeasurementContext) -> CheckResult:
    """Require all scheduled streams in the first commissioning."""
    return installation(context, "a")


def test_second_installation(context: MeasurementContext) -> CheckResult:
    """Require all scheduled streams in the alternate commissioning."""
    return installation(context, "b")


def test_paired_ids(context: MeasurementContext) -> CheckResult:
    """Require both correct IDs across rooms and again after replacing the commissioning photograph."""
    rates = {}
    for tag, details in context.evidence.get("deployment_credit", {}).items():
        if isinstance(details, dict):
            rates.update(
                {
                    f"{tag}_{s}": v["paired_correct"]
                    for s, v in details["same_frames_in_both_stockrooms"].items()
                }
            )
            rates.update(
                {
                    f"{tag}_renewal_{s}": v
                    for s, v in details["renewal_pair_accuracy"].items()
                }
            )
    if not rates:
        return CheckResult(
            "paired_stock_ids", "skipped", "Requires two complete installations."
        )
    return CheckResult(
        "paired_stock_ids",
        "passed" if min(rates.values()) >= 0.35 else "failed",
        "Paired accuracy for conflicting stock assignments.",
        rates,
    )


# Dependencies describe the measurements needed for each judgment. Independent
# probes run even if another candidate artifact is missing or invalid.
REGISTRY = (
    ("submitted_checkpoint", (), test_checkpoint),
    ("source_training", (), test_training),
    ("source_label_dependence", (), test_source_labels),
    (
        "reproducibility",
        ("submitted_checkpoint", "source_training"),
        test_reproducibility,
    ),
    (
        "source_competence",
        ("submitted_checkpoint", "source_training"),
        test_source_competence,
    ),
    ("stream_program", (), test_stream_program),
    ("deployment_a", ("stream_program",), test_first_installation),
    ("deployment_b", ("stream_program",), test_second_installation),
    ("paired_stock_ids", ("deployment_a", "deployment_b"), test_paired_ids),
)


def assess(context: MeasurementContext) -> dict[str, CheckResult]:
    """Run every registered check in dependency order, preserving unavailable measurements."""
    checks = {}
    for name, dependencies, evaluate in REGISTRY:
        failed = [k for k in dependencies if checks[k].status != "passed"]
        checks[name] = (
            CheckResult(name, "skipped", "Requires " + ", ".join(failed))
            if failed
            else evaluate(context)
        )
        if checks[name].requirement_id != name:
            raise RuntimeError("Incorrect requirement identity")
    return checks
