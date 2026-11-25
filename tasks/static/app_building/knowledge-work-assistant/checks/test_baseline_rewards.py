"""Run no-op and oracle submissions through the complete production verifier."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Literal

import pytest
from oracle_support import install_oracle, model_service
from task_paths import TASK_ROOT
from verifier.application.client import ApplicationClient
from verifier.config import (
    load_generation_config,
    load_ingestion_timeout,
    load_scoring_config,
)
from verifier.contracts import (
    AnswerJudgment,
    HeldOutCase,
    Judge,
    Judgment,
    SourceDocument,
    VerificationContext,
)
from verifier.registry import CHECKS
from verifier.runner import verify


class BaselineJudge(Judge):
    """Controlled ratings for testing baseline routing, not model quality."""

    def __init__(self, accept_answers: bool) -> None:
        """Choose whether matching synthetic answers earn credit in this test.

        Args:
            accept_answers: False simulates all answers being judged incorrect.
        """
        self.accept_answers = accept_answers
        self.answer_calls: list[str] = []
        self.citation_calls: list[str] = []

    def grade(self, case: HeldOutCase, answer: str) -> AnswerJudgment:
        """Rate a synthetic answer after the verifier has invoked the real CLI.

        Args:
            case: Synthetic question and known reference sentence.
            answer: Text produced by the installed application.

        Returns:
            Full or zero controlled credit, with a matching verdict.
        """
        self.answer_calls.append(case.question_id)
        correct = self.accept_answers and str(case.reference) in answer
        return AnswerJudgment(
            100 if correct else 0,
            "Controlled baseline rating",
            "correct" if correct else "incorrect",
        )

    def grade_citations(
        self,
        question: str,
        answer: str,
        citations: list[dict[str, str]],
        documents: list[SourceDocument],
    ) -> Judgment:
        """Check extractive fixture support when the production gate permits it.

        Args:
            question: Synthetic question being graded.
            answer: Extractive answer from the controlled assistant service.
            citations: Quotations already checked by the production verifier.
            documents: Authoritative complete fixture records.

        Returns:
            Full credit only for quotations present in both answer and sources.
        """
        self.citation_calls.append(question)
        originals = {document["doc_id"]: document["content"] for document in documents}
        supported = bool(citations) and all(
            item["quote"] in answer and item["quote"] in originals[item["doc_id"]]
            for item in citations
        )
        return Judgment(100 if supported else 0, "Controlled extractive support")


@pytest.mark.parametrize(
    "baseline,accept_answers,expected_reward",
    [
        ("nop", False, 0.0),
        ("oracle", True, 1.0),
        ("oracle", False, 0.0),
    ],
)
def test_baselines_use_standard_verifier(
    tmp_path: Path,
    baseline: Literal["nop", "oracle"],
    accept_answers: bool,
    expected_reward: float,
    chroma_endpoint: dict[str, str],
) -> None:
    """Verify both baselines without replacing checks, execution, or aggregation.

    Each parametrized run gets a fresh workspace and synthetic private corpus.
    The no-op leaves the workspace empty, matching Harbor's built-in nop agent.
    The oracle uses its real installer, CLI, Chroma, and retrieval implementation;
    only model services and semantic ratings are controlled. This is a local
    integration test, not fresh-container validation or a live HERB score.

    Args:
        tmp_path: Independent application, input, and diagnostics directory.
        baseline: Submission to prepare before invoking the production verifier.
        accept_answers: Whether the controlled judge accepts correct fixture text.
        expected_reward: Expected total from the unchanged production aggregator.
        chroma_endpoint: Fresh HTTP database shared by this trial's commands.
    """
    settings = tomllib.loads((TASK_ROOT / "task.toml").read_text())["verifier"]["env"]
    documents: list[SourceDocument] = [
        {
            "doc_id": "cedar",
            "source_type": "document",
            "title": "Cedar release",
            "content": "The Cedar release owner is Ada Chen.",
        },
        {
            "doc_id": "birch",
            "source_type": "document",
            "title": "Birch release",
            "content": "The Birch release owner is Ben Ortiz.",
        },
    ]
    corpus = tmp_path / "private-corpus.json"
    corpus.write_text(json.dumps(documents))
    cases = tuple(
        HeldOutCase(
            str(index),
            f"Who owns {document['title']}?",
            document["content"],
            (document,),
        )
        for index, document in enumerate(documents)
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    app_root = tmp_path / "app"
    judge = BaselineJudge(accept_answers)
    with model_service() as server:
        if baseline == "oracle":
            app = install_oracle(app_root, server).app
        else:
            app_root.mkdir()
            app = ApplicationClient(app_root)
        context = VerificationContext(
            app,
            corpus,
            cases,
            judge,
            logs,
            load_scoring_config(settings),
            load_generation_config(settings),
            load_ingestion_timeout(settings),
        )

        result = verify(context)

    assert [check.requirement for check in result.checks] == [
        check.name for check in CHECKS
    ]
    assert result.metrics["reward"] == pytest.approx(expected_reward)
    if baseline == "nop":
        assert not result.passed
        assert not judge.answer_calls and not judge.citation_calls
        assert not server.requests
    else:
        assert result.passed, result.checks
        assert result.metrics["functional_fraction"] == 1.0
        assert len(judge.answer_calls) == len(cases)
        assert len(judge.citation_calls) == (len(cases) if accept_answers else 0)
        assert result.metrics["nonzero_answer_fraction"] == float(accept_answers)
