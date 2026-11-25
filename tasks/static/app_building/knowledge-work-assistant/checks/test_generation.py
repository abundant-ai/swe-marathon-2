"""Exercise bounded CLI concurrency, deadlines, and isolated question failures."""

from __future__ import annotations

import json
import sys
import threading
import time
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from task_paths import TASK_ROOT
from verifier.application.generation import generate_answers
from verifier.application.process import CommandResult
from verifier.config import GenerationConfig, load_generation_config
from verifier.contracts import EvaluationError, HeldOutCase, VerificationContext


@pytest.mark.parametrize(
    "name",
    [
        "ORANGE_EVAL_GENERATION_CONCURRENCY",
        "ORANGE_EVAL_GENERATION_TIMEOUT_SEC",
        "ORANGE_EVAL_MAX_RETRIEVAL_CALLS",
    ],
)
@pytest.mark.parametrize("value", [None, "0", "-1", "1.5", "nan"])
def test_generation_rejects_invalid_limits(name: str, value: str | None) -> None:
    """Require valid explicit limits instead of silently applying defaults.

    Args:
        name: Required environment setting to invalidate.
        value: Invalid value, or None to remove the setting.
    """
    settings = tomllib.loads((TASK_ROOT / "task.toml").read_text())["verifier"]["env"]
    if value is None:
        settings.pop(name)
    else:
        settings[name] = value
    with pytest.raises(EvaluationError):
        load_generation_config(settings)


def test_ten_questions_generate_concurrently(
    context: VerificationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fill ten workers, bound concurrency, and preserve IDs across later waves.

    Args:
        context: Fixture with the production generation policy.
        monkeypatch: Substitute a coordinated CLI transport without model calls.
    """
    context.cases = tuple(
        HeldOutCase(str(i), f"Question {i}", "Answer") for i in range(23)
    )
    lock = threading.Lock()
    barrier = threading.Barrier(10)
    active = 0
    peak = 0
    deadlines: list[int] = []
    paths: set[str] = set()

    def cli(*args: str, **kwargs: Any) -> CommandResult:
        """Hold the first ten CLI calls together and write independent outputs.

        Args:
            args: Single-question CLI arguments.
            kwargs: Process timeout from the trusted generation policy.

        Returns:
            Successful CLI status after writing the assigned answer.
        """
        nonlocal active, peak
        question_path = args[args.index("--questions") + 1]
        questions = json.loads(Path(question_path).read_text())
        assert len(questions) == 1
        row = questions[0]
        with lock:
            active += 1
            peak = max(peak, active)
            deadlines.append(kwargs["timeout"])
            assert kwargs["max_retrieval_calls"] == 50
            paths.add(question_path)
        try:
            if row["question_id"] < 10:
                barrier.wait(timeout=5)
            time.sleep(0.01)
            row.update(answer="Answer", citations=[])
            Path(args[args.index("--output") + 1]).write_text(json.dumps([row]))
        finally:
            with lock:
                active -= 1
        return CommandResult(0, "", "")

    monkeypatch.setattr(context.app, "bounded_cli", cli)
    answers = generate_answers(context)
    assert peak == 10
    assert deadlines == [1800] * 23
    assert len(paths) == 23
    assert list(answers.records) == list(range(23))
    assert not answers.errors


def test_timeout_and_invalid_outputs_are_question_local(
    context: VerificationContext,
) -> None:
    """Run real CLI processes and reject late output without losing other answers.

    Args:
        context: Temporary application whose launcher is replaced by a controlled
            slow, malformed, wrong-ID, or successful process for each question.
    """
    context.generation = GenerationConfig(
        concurrency=2, timeout_sec=1, max_retrieval_calls=50
    )
    context.cases = tuple(
        HeldOutCase(str(i), f"Question {i}", "Answer") for i in range(5)
    )
    launcher = context.app.root / "orange"
    launcher.write_text(
        f"#!{sys.executable}\n"
        + """import json, pathlib, sys, time
args = sys.argv[1:]
row = json.loads(pathlib.Path(args[args.index("--questions") + 1]).read_text())[0]
output = pathlib.Path(args[args.index("--output") + 1])
index = row["question_id"]
row.update(answer="Answer", citations=[])
if index == 0:
    output.write_text(json.dumps([row]))
    time.sleep(3)
    pathlib.Path("late-marker").write_text("must never happen")
elif index == 1:
    output.write_text("{broken")
elif index == 2:
    row["question_id"] = 4
    output.write_text(json.dumps([row]))
elif index == 3:
    raise SystemExit(2)
else:
    output.write_text(json.dumps([row]))
"""
    )
    answers = generate_answers(context)
    assert set(answers.records) == {4}
    assert set(answers.errors) == {0, 1, 2, 3}
    assert "exceeded 1 seconds" in answers.errors[0]
    assert "Unexpected answer record ID" in answers.errors[2]
    time.sleep(2.1)
    assert not (context.app.root / "late-marker").exists()
    diagnostics = json.loads((context.output_dir / "generation.json").read_text())
    assert len(diagnostics["errors"]) == 4


def test_generation_limits_are_in_report(context: VerificationContext) -> None:
    """Record effective injected limits for reproducibility.

    Args:
        context: Fixture report destination and generation policy.
    """
    from verifier.reporting import write_report

    context.generation = replace(context.generation, concurrency=3, timeout_sec=7)
    write_report(context.output_dir, context, None, "controlled")
    report = json.loads((context.output_dir / "report.json").read_text())
    assert report["generation_config"] == {
        "concurrency": 3,
        "timeout_sec": 7,
        "max_retrieval_calls": 50,
    }
