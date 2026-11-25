"""Exercise actual async overlap, ordered outputs, and fail-closed cancellation."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from verifier.checks.accuracy_inputs import AccuracyAnswers
from verifier.contracts import (
    AnswerJudgment,
    CheckResult,
    EvaluationError,
    HeldOutCase,
    Judge,
    Judgment,
    SourceDocument,
    VerificationContext,
)
from verifier.judging.evaluation import grade_questions
from verifier.scoring import aggregate_results


@pytest.mark.parametrize("limit", [1, 3, 10])
def test_question_pipelines_overlap_with_bounded_concurrency(
    context: VerificationContext, limit: int
) -> None:
    """Reach the configured limit while keeping each citation after its answer.

    Args:
        context: Fixture with writable diagnostics and authoritative records.
        limit: Positive concurrency setting, including the deployment value ten.
    """
    context.scoring = replace(context.scoring, question_concurrency=limit)
    context.cases = tuple(
        HeldOutCase(str(index), str(index), "reference", ()) for index in range(23)
    )
    document: SourceDocument = {
        "doc_id": "d",
        "title": "title",
        "content": "source",
        "source_type": "document",
    }
    answers = AccuracyAnswers(
        {
            index: {
                "answer": "answer",
                "citations": [{"doc_id": "d", "quote": "source"}],
            }
            for index in range(23)
        },
        {},
        0,
    )
    active = 0
    peak = 0
    answered: set[str] = set()
    cited: set[str] = set()

    class ConcurrentJudge(Judge):
        """Yield during both stages so tests exercise overlapping pipelines."""

        async def grade_async(self, case: HeldOutCase, answer: str) -> AnswerJudgment:
            """Track an active question until its final eligible judge completes.

            Args:
                case: Unique test question.
                answer: Unused candidate text.

            Returns:
                Alternating zero, half, three-quarter, and full credit.
            """
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.002)
            answered.add(case.question)
            score = [0, 50, 75, 100][int(case.question) % 4]
            if score < 75:
                active -= 1
            return AnswerJudgment(
                score,
                "controlled",
                "incorrect" if score == 0 else "correct" if score == 100 else "partial",
            )

        async def grade_citations_async(
            self,
            question: str,
            answer: str,
            citations: list[dict[str, str]],
            documents: list[SourceDocument],
        ) -> Judgment:
            """Require a completed eligible answer and finish the pipeline.

            Args:
                question: Unique test identity.
                answer: Candidate answer text.
                citations: Validated quotation.
                documents: Trusted source context.

            Returns:
                Full citation support.
            """
            nonlocal active
            assert question in answered
            assert int(question) % 4 in (2, 3)
            await asyncio.sleep(0.002)
            cited.add(question)
            active -= 1
            return Judgment(100, "controlled")

    context.judge = ConcurrentJudge()
    rows = asyncio.run(grade_questions(context, answers, {"d": document}))
    assert peak == limit and active == 0
    assert cited == {str(index) for index in range(23) if index % 4 in (2, 3)}
    assert [row["question_id"] for row in rows] == [str(index) for index in range(23)]
    assert json.loads(
        (context.output_dir / "judgments.json").read_text()
    ) == json.loads(json.dumps(rows))
    metrics = {
        "accuracy_percent": sum(row["answer_judgment"]["score"] for row in rows)
        / len(rows),
        "citation_support_percent": sum(
            row["citation_judgment"]["score"] for row in rows
        )
        / len(rows),
        "nonzero_answer_fraction": sum(row["reward_eligible"] for row in rows)
        / len(rows),
    }
    result = aggregate_results(
        [
            CheckResult("holdout_accuracy", "passed", "controlled", metrics),
            CheckResult("contract", "passed", "controlled"),
        ],
        context.scoring,
    )
    expected = sum(
        0.8 * row["accuracy_reward"] + 0.2 if row["reward_eligible"] else 0
        for row in rows
    ) / len(rows)
    assert result.metrics["reward"] == pytest.approx(expected)


def test_provider_failure_cancels_inflight_questions(
    context: VerificationContext,
) -> None:
    """Cancel unfinished judge work without dropping already completed diagnostics.

    Args:
        context: Writable fixture whose three questions simulate success, failure,
            and an in-flight request respectively.
    """
    context.cases = tuple(
        HeldOutCase(str(index), str(index), "reference", ()) for index in range(3)
    )
    answers = AccuracyAnswers(
        {index: {"answer": "answer", "citations": []} for index in range(3)}, {}, 0
    )
    cancelled: list[str] = []

    class FailingJudge(Judge):
        """Allow one result to finish before a peer fails."""

        async def grade_async(self, case: HeldOutCase, answer: str) -> AnswerJudgment:
            """Return, fail, or await cancellation according to the question ID.

            Args:
                case: Controlled question identity.
                answer: Unused candidate text.

            Returns:
                Half-credit result for the first question only.

            Raises:
                EvaluationError: Controlled provider failure on question one.
            """
            if case.question_id == "0":
                return AnswerJudgment(50, "controlled", "partial")
            if case.question_id == "1":
                await asyncio.sleep(0.002)
                raise EvaluationError("controlled outage")
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(case.question_id)
                raise
            raise AssertionError("Unreachable")

    context.judge = FailingJudge()
    with pytest.raises(EvaluationError, match="controlled outage"):
        asyncio.run(grade_questions(context, answers, {}))
    assert cancelled == ["2"]
    assert [
        row["question_id"]
        for row in json.loads((context.output_dir / "judgments.json").read_text())
    ] == ["0"]
