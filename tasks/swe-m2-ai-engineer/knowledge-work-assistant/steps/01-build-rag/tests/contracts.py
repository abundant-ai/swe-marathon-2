"""Author-side records; the submitted application never imports this module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, Mapping, Protocol

if TYPE_CHECKING:
    from client import ApplicationClient


class CandidateFailure(Exception):
    """The application did not meet a declared requirement."""


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
class HeldOutCase:
    """A private question and its original reference value."""

    question_id: str
    question: str
    reference: str | list[str]


@dataclass(frozen=True)
class Judgment:
    """A validated single HERB rating, with provider trace information."""

    score: int
    reason: str
    response_id: str = ""


class Judge(Protocol):
    """Boundary for the fixed production judge and controlled test doubles."""

    def grade(self, case: HeldOutCase, answer: str) -> Judgment:
        """Rate one answer against its reference.

        Args:
            case: Private question and reference; never passed to the candidate.
            answer: Candidate answer text, without extra citation context.

        Returns:
            The validated rating and explanation.

        Raises:
            EvaluationError: The provider failed or returned an invalid rating.
        """
        ...


@dataclass
class VerificationContext:
    """Trusted inputs and accumulated diagnostics for one verification run."""

    app: ApplicationClient
    corpus_path: Path
    cases: tuple[HeldOutCase, ...]
    judge: Judge
    output_dir: Path
    completed: list[CheckResult] = field(default_factory=list)


@dataclass(frozen=True)
class RegisteredCheck:
    """Explicit requirement identifier, implementation, and prerequisites."""

    name: str
    function: Callable[[VerificationContext], CheckResult]
    requires: tuple[str, ...] = ()
