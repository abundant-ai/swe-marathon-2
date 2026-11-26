"""Typed records shared by the build, the case runner and the scoring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Limits:
    """Resource limits, as the brief states them to the requester's CI."""

    case_timeout_sec: float = 5.0
    case_memory_bytes: int = 2 << 30
    case_stdout_bytes: int = 8 << 20
    build_timeout_sec: float = 1200.0
    deadline_sec: float = 2400.0
    max_files: int = 100_000
    max_bytes: int = 1 << 30


@dataclass(frozen=True)
class VerificationContext:
    """Where the delivered project, the private cases and the outputs live."""

    submission: Path
    private: Path
    logs: Path
    work: Path
    limits: Limits = field(default_factory=Limits)


@dataclass(frozen=True)
class Case:
    """One command line over one bundle of input files, with its expected result."""

    case_id: str
    family: str
    bundle: str
    args: tuple[str, ...]
    fmt: Literal["human", "json"]
    pair: str | None
    expected_rc: int
    expected_stdout: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    family: str
    pair: str | None
    passed: bool
    detail: str


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    binary: Path | None
    detail: str
    seconds: float


@dataclass(frozen=True)
class VerificationResult:
    """A completed evaluation. An evaluation that cannot complete raises EvaluationError."""

    reward: float
    metrics: Mapping[str, object]


class EvaluationError(RuntimeError):
    """The evaluation itself failed (not the submission); no reward may be written."""
