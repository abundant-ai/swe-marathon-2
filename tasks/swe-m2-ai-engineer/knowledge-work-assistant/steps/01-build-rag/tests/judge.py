"""HERB's answer_likert_score prompt with one pinned replacement judge."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

from contracts import EvaluationError, HeldOutCase, Judgment

if TYPE_CHECKING:
    from openai import OpenAI

JUDGE_MODEL: Final = "gpt-5.4-2026-03-05"
JUDGE_REASONING: Final = "medium"
HERB_REVISION: Final = "db3bf9b3f911745726c579c9dbf9f7f6b2c05b36"
# Verbatim template from HERB/code/evaluate.py::answer_likert_score.
HERB_PROMPT: Final = Path(__file__).with_name("herb_prompt.md").read_text(encoding="utf-8").removesuffix("\n")
PROMPT_SHA256: Final = hashlib.sha256(HERB_PROMPT.encode()).hexdigest()


def parse_judgment(text: str, response_id: str = "") -> Judgment:
    """Validate a provider response and apply HERB's integer conversion.

    Args:
        text: JSON object containing score and reason, as requested by HERB.
        response_id: Provider response identifier for audit records.

    Returns:
        A score in [0, 100]. Numeric strings are accepted like upstream HERB.

    Raises:
        EvaluationError: Missing, nonfinite, out-of-range, or malformed output.
    """
    try:
        value = json.loads(text)
        score = value["score"]
        reason = value["reason"]
        if isinstance(score, bool) or not isinstance(score, (str, int, float)):
            raise ValueError("score must be numeric")
        number = float(score)
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise ValueError("score outside [0, 100]")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be nonempty text")
        return Judgment(int(number), reason, response_id)
    except (ValueError, TypeError, KeyError) as exc:
        raise EvaluationError("Judge returned an invalid rating") from exc


class HerbJudge:
    """Use the official Responses endpoint with no model override or fallback."""

    def __init__(self, client: OpenAI | None = None) -> None:
        """Create a bounded client, or accept a client double for local tests.

        Args:
            client: Test-only dependency injection; production always constructs
                this class without arguments and reads ORANGE_JUDGE_API_KEY.
        """
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=os.environ["ORANGE_JUDGE_API_KEY"],
                base_url="https://api.openai.com/v1", timeout=120, max_retries=2
            )
        self.client = client

    def grade(self, case: HeldOutCase, answer: str) -> Judgment:
        """Score answer text using the unchanged HERB prompt and fixed settings.

        Args:
            case: Original reference is formatted as upstream, including lists.
            answer: Candidate text. Citations are checked separately.

        Returns:
            One integer score and the judge's explanation.

        Raises:
            EvaluationError: Provider failure, truncation, or invalid output.
        """
        prompt = HERB_PROMPT.format(
            question=case.question, reference=case.reference, candidate=answer
        )
        try:
            response = self.client.responses.create(
                model=JUDGE_MODEL,
                reasoning={"effort": JUDGE_REASONING},
                input=[{"role": "user", "content": prompt}],
                text={"format": {"type": "json_object"}},
                max_output_tokens=4096,
                store=False,
            )
        except Exception as exc:
            # Do not copy HTTP headers, credentials, or raw request bodies to logs.
            raise EvaluationError(f"Judge request failed: {type(exc).__name__}") from exc
        if response.status != "completed":
            raise EvaluationError(f"Judge response was {response.status}")
        return parse_judgment(response.output_text, response.id)
