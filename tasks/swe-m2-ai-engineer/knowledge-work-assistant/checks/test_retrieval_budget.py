"""Boundary and coroutine-resumption checks for the trusted CLI call budget."""

from __future__ import annotations

import json

import pytest

from test_verifier import context
from verifier.application.generation import generate_answers
from verifier.contracts import HeldOutCase, VerificationContext


@pytest.mark.parametrize("calls", [49, 50, 51])
@pytest.mark.parametrize("parallel", [False, True])
def test_call_ceiling_is_question_local(context: VerificationContext, calls: int, parallel: bool) -> None:
    """Accept up to fifty calls and reject the fifty-first before its body runs.

    Args:
        context: Local fixture application with no live model calls.
        calls: Number of attempted calls for the first of two questions.
        parallel: Whether the fixture schedules retrieval coroutines concurrently.
    """
    source = context.app.root / "main.py"
    source.write_text(source.read_text() + f'''

import asyncio

async def retrieve(query: str, retrieval_method: RetrievalMethod) -> RetrievedItem:
    """Yield twice to distinguish coroutine resumes from new retrieval calls."""
    with (Path(__file__).parent / "executed.txt").open("a") as stream:
        stream.write(query + "\\n")
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    return RetrievedItem(passages=[])

async def generate(query: str) -> GeneratedAnswer:
    """Exercise the requested retrieval attempts without any external service."""
    count = {calls} if query == "first" else 1
    if {parallel!r}:
        await asyncio.gather(*(retrieve(query, "hybrid") for _ in range(count)))
    else:
        for _ in range(count):
            await retrieve(query, "bm25")
    return GeneratedAnswer(answer="finished", citations=[])
''')
    context.cases = (HeldOutCase("first", "first", "finished"), HeldOutCase("second", "second", "finished"))
    answers = generate_answers(context)
    assert 1 in answers.records
    if calls <= 50:
        assert not answers.errors and 0 in answers.records
    else:
        assert set(answers.errors) == {0}
        assert "exceeded 50 retrieve() calls" in answers.errors[0]
    rows = (context.app.root / "executed.txt").read_text().splitlines()
    assert rows.count("first") == min(calls, 50)
    assert rows.count("second") == 1
    saved = json.loads((context.output_dir / "generation.json").read_text())
    assert len(saved["answers"]) == (2 if calls <= 50 else 1)


def test_child_processes_share_the_question_budget(context: VerificationContext) -> None:
    """Reject combined child calls even when the parent ignores a child failure.

    Args:
        context: Local fixture whose question launches two Python search workers.
    """
    source = context.app.root / "main.py"
    source.write_text(source.read_text() + '''

import asyncio
import subprocess
import sys

async def retrieve(query: str, retrieval_method: RetrievalMethod) -> RetrievedItem:
    """Exercise one budgeted entry without a database or external model."""
    await asyncio.sleep(0)
    return RetrievedItem(passages=[])

async def generate(query: str) -> GeneratedAnswer:
    """Attempt sixty calls across children while ignoring their exit status."""
    code = "import asyncio, main; [asyncio.run(main.retrieve('q', 'bm25')) for _ in range(30)]"
    for _ in range(2):
        subprocess.run([sys.executable, "-c", code], check=False)
    return GeneratedAnswer(answer="finished", citations=[])
''')
    context.cases = (HeldOutCase("child", "question", "finished"),)
    answers = generate_answers(context)
    assert not answers.records
    assert "exceeded 50 retrieve() calls" in answers.errors[0]
