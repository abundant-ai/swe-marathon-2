"""Shared access to the single measurement pass."""

from __future__ import annotations

from verifier.contracts import Measurement, VerificationContext
from verifier.engine import measure


def measurement(context: VerificationContext) -> Measurement:
    """Return this evaluation's measurement, running it on first use.

    Args:
        context: Evaluation context; the result is stored on it.

    Returns:
        The one measurement every check of this evaluation reads.

    Raises:
        EvaluationError: The measurement could not be completed.
    """
    if context.measurement is None:
        context.measurement = measure(context)
    return context.measurement


def share(passing: int, total: int) -> float:
    """Return passing/total with a fixed denominator; zero when total is zero."""
    return passing / total if total else 0.0
