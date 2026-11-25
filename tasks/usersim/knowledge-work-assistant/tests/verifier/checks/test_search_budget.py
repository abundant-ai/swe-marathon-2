"""Check the public per-question retrieval ceiling through the real CLI."""

from __future__ import annotations

import json

from verifier.checks.support import answer_records, fixture_document, passed
from verifier.contracts import CheckResult, VerificationContext

__test__ = False


def test_retrieval_budget(context: VerificationContext) -> CheckResult:
    """Answer independent questions with separately enforced retrieval budgets.

    Args:
        context: Application, trusted call limit, and per-question deadline.

    Returns:
        A passing contract check when each CLI completes within its own ceiling.
        The accuracy pipeline applies the same ceiling to every private question.
    """
    document = fixture_document()
    corpus = context.app.write_json("budget-corpus.json", [document])
    context.app.cli("ingest", "--path", str(corpus), "--refresh")
    for identity in range(2):
        question = f"What is the authorization code for {document['title']}?"
        result = context.app.bounded_cli(
            "answer",
            stdin=json.dumps([{"question_id": identity, "question": question}]),
            timeout=context.generation.timeout_sec,
            max_retrieval_calls=context.generation.max_retrieval_calls,
        )
        answer_records(
            json.loads(result.stdout), [identity], questions={identity: question}
        )
    return passed(
        "retrieval_budget",
        "Each question completes within the configured retrieve() call limit",
    )
