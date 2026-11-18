"""Author-side records; submitted code never imports this module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping


class CandidateFailure(Exception):
    """The submission did not meet a declared requirement."""


class EvaluationError(Exception):
    """Evaluation could not finish; no valid reward may be published."""


@dataclass(frozen=True)
class CheckResult:
    """One requirement's outcome and supporting measurements."""

    requirement: str
    status: Literal["passed", "failed", "skipped"]
    explanation: str
    metrics: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationResult:
    """Completed evaluation, including explicit dependency skips."""

    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: Mapping[str, float]


@dataclass(frozen=True)
class ScoringConfig:
    """Published thresholds; each is a share of a fixed denominator."""

    unit_bar: float
    call_bar: float
    test_bar: float


@dataclass(frozen=True)
class Measurement:
    """One grading pass over the submission.

    `counts` holds the fixed denominators and the passing numerators. `details`
    is the full diagnostic record written to metrics.json. `self_check_trips`
    lists measurements whose own control result was wrong.
    """

    artifact_present: bool
    counts: Mapping[str, int]
    self_check_trips: tuple[str, ...]
    details: Mapping[str, Any]


@dataclass
class VerificationContext:
    """Trusted paths and limits for one evaluation in a fresh container."""

    work_tree: Path
    skeleton: Path
    private: Path
    output: Path
    scratch: Path
    scoring: ScoringConfig
    limits: Mapping[str, Any]
    completed: list[CheckResult] = field(default_factory=list)
    measurement: Measurement | None = None


@dataclass(frozen=True)
class RegisteredCheck:
    """A named requirement check and the checks it depends on."""

    name: str
    function: Callable[[VerificationContext], CheckResult]
    requires: tuple[str, ...] = ()
