"""Controlled application and judge tests; these do not establish HERB accuracy."""

from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from client import ApplicationClient
from contracts import CandidateFailure, CheckResult, EvaluationError, HeldOutCase, Judgment, RegisteredCheck, VerificationContext
from judge import HERB_PROMPT, JUDGE_MODEL, HerbJudge, parse_judgment
from prepare_data import SAMPLE_FRACTION, SAMPLE_SEED, collect_records
import test_requirements as requirements
import verify as verifier


class ExactJudge:
    """Controlled judge for orchestration, never a semantic-quality baseline."""

    def grade(self, case: HeldOutCase, answer: str) -> Judgment:
        """Return full credit only when the fixture reference occurs in the answer.

        Args:
            case: Controlled reference answer.
            answer: Candidate output text.

        Returns:
            A deterministic 100 or zero rating.
        """
        return Judgment(100 if str(case.reference) in answer else 0, "Controlled exact-reference judge")


@pytest.fixture
def context(tmp_path: Path) -> VerificationContext:
    """Create an isolated fixture application, its dev artifacts, and two cases.

    Args:
        tmp_path: Pytest-managed temporary workspace.

    Returns:
        A local context with no production credentials or private HERB content.
    """
    app = tmp_path / "app"
    shutil.copytree(Path(__file__).parent / "fixtures", app, ignore=shutil.ignore_patterns("__pycache__"))
    launcher = app / "orange"
    launcher.write_text(f"#!{sys.executable}\nfrom cli import main\nmain()\n")
    launcher.chmod(0o755)
    development = app / "dev"
    development.mkdir()
    document = {"doc_id": "dev", "source_type": "document", "title": "Development", "content": "Development release is Friday."}
    question = {"question_id": "dev-q", "question": "When is the release?", "reference_answer": document["content"]}
    (development / "corpus.jsonl").write_text(json.dumps(document) + "\n")
    (development / "questions.jsonl").write_text(json.dumps(question) + "\n")
    (development / "answers.json").write_text(json.dumps([{"question_id": "dev-q", "answer": document["content"], "citations": [{"doc_id": "dev", "quote": document["content"]}]}]))
    (development / "report.json").write_text(json.dumps({"method": "Exact comparison", "findings": "One of one passed"}))
    corpus = tmp_path / "private-corpus.jsonl"
    rows = [{"doc_id": f"private-{index}", "source_type": "document", "title": f"release-{index}", "content": f"Release {index} is Friday."} for index in range(2)]
    corpus.write_text("".join(json.dumps(row) + "\n" for row in rows))
    cases = tuple(HeldOutCase(f"q{index}", row["title"], row["content"]) for index, row in enumerate(rows))
    output = tmp_path / "logs"
    output.mkdir()
    return VerificationContext(ApplicationClient(app), corpus, cases, ExactJudge(), output)


def test_working_fixture_passes_all_registered_checks(context: VerificationContext) -> None:
    """Exercise the whole verifier with a deterministic conforming application.

    Args:
        context: Fresh application and exact-reference judge fixture.
    """
    result = verifier.verify(context)
    assert result.passed, result
    assert len(result.checks) == len(verifier.CHECKS)
    assert result.metrics["accuracy_percent"] == 100


def test_every_requirement_function_is_registered() -> None:
    """Prevent a defined acceptance check from silently escaping orchestration."""
    defined = {name for name in vars(requirements) if name.startswith("test_")}
    registered = {check.function.__name__ for check in verifier.CHECKS}
    assert registered == defined
    seen: set[str] = set()
    for check in verifier.CHECKS:
        assert check.name not in seen
        assert set(check.requires) <= seen
        seen.add(check.name)


@pytest.mark.parametrize("before,after,check", [
    ("rows.setdefault(row[\"doc_id\"], row)", "rows[row[\"doc_id\"]] = row", "duplicate_documents"),
    ("event[\"refresh\"] or not STATE.exists()", "not STATE.exists()", "refresh_replaces_index"),
    ("evidence = await retrieve(query)", "evidence = {\"passages\": []}", "required_call_paths"),
    ("async def retrieve(query: str)", "async def retrieve(query)", "interfaces"),
])
def test_targeted_broken_applications_are_rejected(context: VerificationContext, before: str, after: str, check: str) -> None:
    """Exercise ingestion and contract regressions through the public boundary.

    Args:
        context: Fresh fixture application.
        before: Known source fragment to mutate.
        after: Broken replacement behavior.
        check: Requirement expected to reject the mutation.
    """
    path = context.app.root / "main.py"
    assert before in path.read_text()
    path.write_text(path.read_text().replace(before, after))
    function = next(item.function for item in verifier.CHECKS if item.name == check)
    with pytest.raises(CandidateFailure):
        function(context)


def test_missing_answers_use_the_full_denominator(context: VerificationContext) -> None:
    """Confirm an omitted answer contributes zero instead of shrinking the mean.

    Args:
        context: Two-case fixture with one answer removed by a CLI regression.
    """
    path = context.app.root / "cli.py"
    path.write_text(path.read_text().replace("if args.output:", "answers = answers[:1]\n        if args.output:"))
    result = requirements.test_holdout_accuracy(context)
    assert result.status == "failed"
    assert result.metrics["accuracy_percent"] == 50
    assert result.metrics["missing_answers"] == 1


def test_bad_citations_and_duplicate_answer_ids_are_rejected() -> None:
    """Prevent unsupported quotes and duplicate IDs from reaching semantic grading."""
    corpus = [{"doc_id": "d", "source_type": "document", "title": "title", "content": "Friday"}]
    with pytest.raises(CandidateFailure):
        requirements.answer_records([{"question_id": "q", "answer": "Monday", "citations": [{"doc_id": "d", "quote": "Monday"}]}], ["q"], corpus)
    answer = {"question_id": "q", "answer": "Friday", "citations": []}
    with pytest.raises(CandidateFailure):
        requirements.answer_records([answer, answer], ["q"], corpus)


def test_independent_checks_continue_and_dependencies_skip(context: VerificationContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure candidate failure does not silently truncate the check registry.

    Args:
        context: Local fixture context.
        monkeypatch: Temporary registry replacement.
    """
    def fail(ctx: VerificationContext) -> CheckResult:
        """Raise a controlled candidate failure.

        Args:
            ctx: Unused local context.

        Raises:
            CandidateFailure: Always, to test orchestration.
        """
        raise CandidateFailure("controlled failure")

    monkeypatch.setattr(verifier, "CHECKS", (
        RegisteredCheck("broken", fail),
        RegisteredCheck("dependent", fail, ("broken",)),
        RegisteredCheck("cli_help", requirements.test_cli_help),
    ))
    result = verifier.verify(context)
    assert [check.status for check in result.checks] == ["failed", "skipped", "passed"]


@pytest.mark.parametrize("payload", ["not json", '{}', '{"score":true,"reason":"x"}', '{"score":101,"reason":"x"}', '{"score":"NaN","reason":"x"}', '{"score":70,"reason":""}'])
def test_invalid_judge_output_invalidates_evaluation(payload: str) -> None:
    """Reject malformed ratings instead of converting provider errors to zero.

    Args:
        payload: Invalid provider output.
    """
    with pytest.raises(EvaluationError):
        parse_judgment(payload)


def test_judge_is_fixed_and_preserves_herb_reference_format() -> None:
    """Check request model, prompt formatting, and integer score conversion."""
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> SimpleNamespace:
        """Capture a mocked Responses request and return a valid rating.

        Args:
            kwargs: Outgoing request fields.

        Returns:
            Minimal completed response for parser validation.
        """
        calls.append(kwargs)
        return SimpleNamespace(status="completed", output_text='{"score":"84","reason":"Partial coverage"}', id="test-response")

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    case = HeldOutCase("q", "Who approved?", ["Mira", "Tao"])
    result = HerbJudge(client).grade(case, "Mira")
    assert result.score == 84
    assert calls[0]["model"] == JUDGE_MODEL
    assert calls[0]["input"][0]["content"] == HERB_PROMPT.format(question=case.question, reference=case.reference, candidate="Mira")


def test_judge_failure_keeps_diagnostics_and_removes_rewards(context: VerificationContext) -> None:
    """Preserve earlier judgments while refusing a reward after provider failure.

    Args:
        context: Local application and two controlled questions.
    """
    class FailingJudge:
        """Judge that fails after recording one successful rating."""

        def grade(self, case: HeldOutCase, answer: str) -> Judgment:
            """Rate the first case and simulate an outage on the second.

            Args:
                case: Fixture case identity.
                answer: Unused candidate output.

            Returns:
                A perfect first rating.

            Raises:
                EvaluationError: On the second case.
            """
            if case.question_id == "q1":
                raise EvaluationError("Controlled outage")
            return Judgment(100, "Controlled correct answer")

    context.judge = FailingJudge()
    for filename in ("reward.json", "reward.txt"):
        (context.output_dir / filename).write_text("1")
    with pytest.raises(EvaluationError):
        verifier.verify(context)
    verifier.write_report(context.output_dir, context, None, "Controlled outage")
    assert len(context.completed) == len(verifier.CHECKS) - 1
    assert len((context.output_dir / "judgments.jsonl").read_text().splitlines()) == 1
    assert not (context.output_dir / "reward.json").exists()
    assert not (context.output_dir / "reward.txt").exists()


def test_candidate_does_not_inherit_judge_credentials(context: VerificationContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the subprocess environment omits a parent-only judge credential.

    Args:
        context: Local application execution boundary.
        monkeypatch: Synthetic parent environment variable.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-judge-only-value")
    monkeypatch.setenv("ORANGE_JUDGE_API_KEY", "synthetic-judge-only-value")
    result = context.app.run([sys.executable, "-c", "import os; print(os.getenv('OPENAI_API_KEY', 'absent'))"])
    assert result.stdout.strip() == "absent"
    result = context.app.run([sys.executable, "-c", "import os; print(os.getenv('ORANGE_JUDGE_API_KEY', 'absent'))"])
    assert result.stdout.strip() == "absent"


def test_escaping_artifact_is_rejected(context: VerificationContext, tmp_path: Path) -> None:
    """Ensure a submitted symlink cannot cause root to read a private reference.

    Args:
        context: Candidate workspace adapter.
        tmp_path: Parent directory outside the candidate workspace.
    """
    private = tmp_path / "secret.json"
    private.write_text('{"private":true}')
    link = context.app.root / "leak.json"
    link.symlink_to(private)
    with pytest.raises(CandidateFailure):
        context.app.read_json(link)


def test_actual_prepared_bundle_has_only_a_uniform_sample() -> None:
    """Check generated public inputs and private denominator against pinned data.

    This check skips when author-generated data is absent from a clean checkout.
    It never downloads HERB or prints private question text.
    """
    task = Path(__file__).resolve().parents[1]
    private = task / "steps/01-build-rag/tests/private"
    if not private.exists():
        pytest.skip("Run scripts/prepare_data.py before checking real bundle")
    corpus_path, cases, manifest = verifier.load_inputs(private)
    corpus = [json.loads(line) for line in corpus_path.read_text().splitlines()]
    public = [json.loads(line) for line in (task / "environment/data/corpus.jsonl").read_text().splitlines()]
    import random

    assert public == random.Random(SAMPLE_SEED).sample(corpus, int(len(corpus) * SAMPLE_FRACTION))
    assert 0 < len(public) / len(corpus) < 0.05
    assert len(cases) == 238
    assert all(set(row) == {"doc_id", "source_type", "title", "content"} for row in corpus)
    assert manifest["sample_records"] == len(public)


def test_prompt_matches_upstream_if_checkout_is_present() -> None:
    """Compare the full prompt template to HERB's pinned source without imports."""
    root = Path(__file__).resolve().parents[4]
    source = root / "HERB/code/evaluate.py"
    if not source.exists():
        pytest.skip("Optional author-side HERB checkout is absent")
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "answer_likert_score")
    assignment = function.body[0]
    assert ast.literal_eval(assignment.value.func.value) == HERB_PROMPT
