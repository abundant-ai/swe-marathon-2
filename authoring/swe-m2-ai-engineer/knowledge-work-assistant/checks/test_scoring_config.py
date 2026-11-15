"""Validate externally configured scoring policy and separate citation credit."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict
from pathlib import Path

from task_paths import TASK_ROOT

import pytest

from verifier.config import load_scoring_config
from verifier.contracts import CheckResult, EvaluationError, VerificationContext
from verifier.reporting import write_report
from verifier.scoring import aggregate_results
from test_verifier import context


@pytest.fixture
def scoring_environment() -> dict[str, str]:
    """Read verifier environment defaults from the deployable task configuration.

    Returns:
        Only scoring settings, without service credentials or unrelated variables.
    """
    task = TASK_ROOT / "task.toml"
    environment = tomllib.loads(task.read_text())["verifier"]["env"]
    return {key: value for key, value in environment.items() if key.startswith("ORANGE_EVAL_")}


@pytest.mark.parametrize("name,value", [
    ("ORANGE_EVAL_QUESTION_CONCURRENCY", None),
    ("ORANGE_EVAL_QUESTION_CONCURRENCY", "0"),
    ("ORANGE_EVAL_QUESTION_CONCURRENCY", "-1"),
    ("ORANGE_EVAL_QUESTION_CONCURRENCY", "1.5"),
    ("ORANGE_EVAL_QUESTION_CONCURRENCY", "nan"),
    ("ORANGE_EVAL_QUALITY_WEIGHT", None),
    ("ORANGE_EVAL_QUALITY_WEIGHT", "not-a-number"),
    ("ORANGE_EVAL_ANSWER_WEIGHT", "nan"),
    ("ORANGE_EVAL_ANSWER_WEIGHT", "inf"),
    ("ORANGE_EVAL_CITATION_WEIGHT", "-0.1"),
    ("ORANGE_EVAL_QUALITY_WEIGHT", "1.2"),
    ("ORANGE_EVAL_QUALITY_WEIGHT", "0.7"),
    ("ORANGE_EVAL_ANSWER_WEIGHT", "0.8"),
    ("ORANGE_EVAL_CITATION_MIN_ANSWER_SCORE", None),
    ("ORANGE_EVAL_CITATION_MIN_ANSWER_SCORE", "nan"),
    ("ORANGE_EVAL_CITATION_MIN_ANSWER_SCORE", "-0.1"),
    ("ORANGE_EVAL_CITATION_MIN_ANSWER_SCORE", "1.1"),
])
def test_invalid_settings_invalidate_evaluation(scoring_environment: dict[str, str], name: str, value: str | None) -> None:
    """Reject missing, malformed, nonfinite, and inconsistent scoring settings.

    Args:
        scoring_environment: Declared defaults to alter independently.
        name: Variable to remove or replace.
        value: Invalid value, or None to remove the variable.
    """
    if value is None:
        scoring_environment.pop(name)
    else:
        scoring_environment[name] = value
    with pytest.raises(EvaluationError):
        load_scoring_config(scoring_environment)


@pytest.mark.parametrize("answer,citation,expected", [(100, 0, .92), (90, 50, .888), (0, 0, 0), (0, 100, 0), (100, 100, 1)])
def test_correctness_has_more_weight(scoring_environment: dict[str, str], answer: float, citation: float, expected: float) -> None:
    """Give answer correctness greater influence without multiplying it by citations.

    Args:
        scoring_environment: Default task weights.
        answer: Answer correctness percentage.
        citation: Citation-support percentage.
        expected: Expected overall reward with passing functional checks.
    """
    config = load_scoring_config(scoring_environment)
    checks = [CheckResult("holdout_accuracy", "passed", "controlled", {
        "nonzero_answer_fraction": float(answer > 0), "accuracy_percent": answer, "citation_support_percent": citation,
    }), CheckResult("functional", "passed", "controlled")]
    assert aggregate_results(checks, config).metrics["reward"] == pytest.approx(expected)


def test_environment_controls_all_scoring_parameters(scoring_environment: dict[str, str]) -> None:
    """Apply custom environment weights to raw scores without target normalization.

    Args:
        scoring_environment: Mutable test copy of deployment settings.
    """
    scoring_environment.update({
        "ORANGE_EVAL_QUALITY_WEIGHT": "0.7",
        "ORANGE_EVAL_FUNCTIONAL_WEIGHT": "0.3", "ORANGE_EVAL_ANSWER_WEIGHT": "0.75",
        "ORANGE_EVAL_CITATION_WEIGHT": "0.25",
    })
    config = load_scoring_config(scoring_environment)
    checks = [CheckResult("holdout_accuracy", "passed", "controlled", {
        "nonzero_answer_fraction": 1.0, "accuracy_percent": 80, "citation_support_percent": 40,
    }), CheckResult("functional", "passed", "controlled")]
    assert aggregate_results(checks, config).metrics["reward"] == pytest.approx(.79)


def test_report_records_effective_policy(context: VerificationContext) -> None:
    """Retain effective policy with the report without dumping process environment.

    Args:
        context: Fixture context with validated scoring settings.
    """
    result = aggregate_results([CheckResult("functional", "passed", "controlled")], context.scoring)
    assert result.metrics["reward"] == 0.0
    write_report(context.output_dir, context, result, None)
    report = json.loads((context.output_dir / "report.json").read_text())
    assert report["scoring_config"] == asdict(context.scoring)


def test_failed_and_skipped_contracts_remain_in_denominator(scoring_environment: dict[str, str]) -> None:
    """Award one third of contract credit when only one of three checks passes.

    Args:
        scoring_environment: Default reward policy.
    """
    config = load_scoring_config(scoring_environment)
    checks = [CheckResult("holdout_accuracy", "passed", "controlled", {
        "nonzero_answer_fraction": 1.0, "accuracy_percent": 100, "citation_support_percent": 100,
    }), CheckResult("one", "passed", "controlled"),
        CheckResult("two", "failed", "controlled"),
        CheckResult("three", "skipped", "controlled")]
    result = aggregate_results(checks, config)
    assert result.metrics["functional_fraction"] == pytest.approx(1 / 3)
    assert result.metrics["reward"] == pytest.approx(.8 + .2 / 3)


@pytest.mark.parametrize("variable", ["ORANGE_EVAL_ANSWER_WEIGHT", "ORANGE_EVAL_QUESTION_CONCURRENCY"])
def test_scoring_settings_are_not_forwarded_to_candidate(context: VerificationContext, monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    """Keep grading policy in the trusted verifier environment.

    Args:
        context: Candidate process adapter with an explicit environment allowlist.
        monkeypatch: Set a verifier-only value in the parent environment.
        variable: Trusted scoring or scheduling setting that must remain private.
    """
    monkeypatch.setenv(variable, "10")
    result = context.app.run([context.app.python(), "-c", f"import os; print(os.getenv({variable!r}, 'absent'))"])
    assert result.stdout.strip() == "absent"
