"""Types shared by the verifier modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping


class EvaluationError(Exception):
    """Evaluation could not finish; no valid reward may be published."""


@dataclass(frozen=True)
class CheckResult:
    requirement: str
    status: Literal["passed", "failed", "skipped"]
    explanation: str
    metrics: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: Mapping[str, float]


@dataclass(frozen=True)
class Test:
    """One recorded run (a line of tests.jsonl) and the checks of it that count."""
    record: str
    source: str
    program: str
    checks: tuple[str, ...]
    masked: tuple[str, ...]
    tolerances: Mapping[str, float]
    seconds: float
    processes: int = 1    # processors the run keeps busy (mpirun's process count)


@dataclass
class VerificationContext:
    app: Path                 # the submission; compile.sh builds app/bin
    dataset: Path             # tests.jsonl, records/, files/
    tests: tuple[Test, ...]
    output: Path              # report and reward
    uid: int                  # unprivileged user that builds and runs the submission
    gid: int
    workers: int
    build_timeout: float
    work: Path                # scratch space for case folders
    outcomes: dict = field(default_factory=dict)   # record -> {check: [passed, message]}
