"""Load the published thresholds and the measurement limits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verifier.contracts import EvaluationError, ScoringConfig

CONFIG_PATH = Path(__file__).resolve().parent / "grade_config.json"


def load_config(path: Path = CONFIG_PATH) -> tuple[ScoringConfig, dict[str, Any]]:
    """Read thresholds and limits from the verifier's own configuration file.

    Args:
        path: JSON file shipped with this code.

    Returns:
        The three published thresholds, and the timing and worker limits.

    Raises:
        EvaluationError: The file is missing, malformed, or a threshold is not
            a share in (0, 1].
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        scoring = ScoringConfig(float(raw["unit_bar"]), float(raw["vector_bar"]), float(raw["test_bar"]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise EvaluationError(f"Verifier configuration is unreadable: {type(e).__name__}") from e
    for value in (scoring.unit_bar, scoring.call_bar, scoring.test_bar):
        if not 0 < value <= 1:
            raise EvaluationError("Verifier thresholds must be shares in (0, 1]")
    return scoring, raw
