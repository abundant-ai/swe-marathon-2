"""Controlled application and judge tests; these do not establish dataset accuracy."""

from __future__ import annotations

import ast
import json
import importlib
import pkgutil
import shutil
import sys
import tomllib
from pathlib import Path

from task_paths import TASK_ROOT
from typing import Any

import pytest

from verifier.application.client import ApplicationClient
from verifier.config import load_ingestion_timeout, load_generation_config, load_scoring_config
from verifier.contracts import Judge
from verifier.contracts import AnswerJudgment, CandidateFailure, CheckResult, EvaluationError, HeldOutCase, Judgment, SourceDocument, RegisteredCheck, VerificationContext
from prepare_data import SAMPLE_FRACTION, SAMPLE_SEED
from verifier.checks import test_cli as cli, test_interfaces as interfaces, test_progress as progress
from verifier.checks import support
from verifier.checks import test_accuracy as accuracy
from verifier.checks import test_storage as storage
from verifier import runner as verifier
from verifier import checks as requirement_package
from verifier.inputs import load_inputs
from verifier.dataset import QUESTION_COUNT
from verifier.reporting import write_report


class ExactJudge(Judge):
    """Controlled judge for orchestration, never a semantic-quality baseline."""

    def grade(self, case: HeldOutCase, answer: str) -> AnswerJudgment:
        """Return full credit only when the fixture reference occurs in the answer.

        Args:
            case: Controlled reference answer.
            answer: Candidate output text.

        Returns:
            A deterministic 100 or zero rating.
        """
        correct = str(case.reference) in answer
        return AnswerJudgment(100 if correct else 0, "Controlled exact-reference judge",
                              "correct" if correct else "incorrect")

    def grade_citations(self, question: str, answer: str, citations: list[dict[str, str]], documents: list[SourceDocument]) -> Judgment:
        """Give controlled credit when quotations occur in the fixture answer.

        Args:
            question: Unused public question.
            answer: Extractive fixture answer.
            citations: Validated quotations.
            documents: Complete original records supplied by the verifier.

        Returns:
            A deterministic support rating, not a live semantic judgment.
        """
        return Judgment(100 if citations and all(row["quote"] in answer for row in citations) else 0,
                        "Controlled support judge")


@pytest.fixture
def context(tmp_path: Path, chroma_endpoint: dict[str, str]) -> VerificationContext:
    """Create an isolated fixture application, its dev artifacts, and two cases.

    Args:
        tmp_path: Pytest-managed temporary workspace.
        chroma_endpoint: Fresh real HTTP service supplied by the fixture.

    Returns:
        A local context with no production credentials or private dataset content.
    """
    app = tmp_path / "app"
    shutil.copytree(Path(__file__).parent / "fixtures", app, ignore=shutil.ignore_patterns("__pycache__"))
    launcher = app / "orange"
    launcher.write_text(f"#!{sys.executable}\nfrom cli import main\nmain()\n")
    launcher.chmod(0o755)
    development = app / "dev"
    development.mkdir()
    (development / "PROGRESS.MD").write_text("Started the fixture.")
    document = {"doc_id": "dev", "source_type": "document", "title": "Development", "content": "Development release is Friday."}
    question = {"question_id": 0, "question": "When is the release?", "reference_answer": document["content"]}
    (development / "corpus.json").write_text(json.dumps([document]) + "\n")
    (development / "questions.json").write_text(json.dumps([question]) + "\n")
    (development / "answers.json").write_text(json.dumps([{"question_id": 0, "answer": document["content"], "citations": [{"doc_id": "dev", "quote": document["content"]}]}]))
    (development / "report.json").write_text(json.dumps({"method": "Exact comparison", "findings": "One of one passed"}))
    corpus = tmp_path / "private-corpus.json"
    rows = [{"doc_id": f"private-{index}", "source_type": "document", "title": f"release-{index}", "content": f"Release {index} is Friday."} for index in range(2)]
    corpus.write_text(json.dumps(rows))
    cases = tuple(HeldOutCase(f"q{index}", row["title"], row["content"], (row,)) for index, row in enumerate(rows))
    output = tmp_path / "logs"
    output.mkdir()
    settings = tomllib.loads((TASK_ROOT / "task.toml").read_text())["verifier"]["env"]
    return VerificationContext(ApplicationClient(app), corpus, cases, ExactJudge(), output, load_scoring_config(settings), load_generation_config(settings), load_ingestion_timeout(settings))


def test_working_fixture_passes_all_registered_checks(context: VerificationContext) -> None:
    """Exercise the whole verifier with a deterministic conforming application.

    Args:
        context: Fresh application and exact-reference judge fixture.
    """
    result = verifier.verify(context)
    assert result.passed, result
    assert len(result.checks) == len(verifier.CHECKS)
    assert result.metrics["accuracy_percent"] == 100


@pytest.mark.parametrize("filename,before,after,failed_requirement", [
    ("main.py", "Path to the JSON corpus file.", "Path to a JSON corpus file.", "interfaces"),
    ("cli.py", "parser.print_help()", 'print("Orange")', "cli_help"),
])
def test_compliance_failure_does_not_skip_behavior(
    context: VerificationContext, filename: str, before: str, after: str,
    failed_requirement: str,
) -> None:
    """Run the full registry after changing only metadata or help text.

    Args:
        context: Working application with controlled perfect quality judgments.
        filename: Fixture file containing the isolated compliance defect.
        before: Exact source fragment to replace.
        after: Replacement that preserves executable application behavior.
        failed_requirement: The sole check that should lose contract credit.
    """
    path = context.app.root / filename
    source = path.read_text()
    assert before in source
    path.write_text(source.replace(before, after))

    result = verifier.verify(context)

    assert not result.passed
    assert len(result.checks) == len(verifier.CHECKS)
    assert {check.requirement: check.status for check in result.checks} == {
        check.name: "failed" if check.name == failed_requirement else "passed"
        for check in verifier.CHECKS
    }
    assert result.metrics["quality_fraction"] == 1.0
    functional_count = sum(check.requirement != "holdout_accuracy" for check in result.checks)
    expected_fraction = (functional_count - 1) / functional_count
    assert result.metrics["functional_fraction"] == pytest.approx(expected_fraction)
    assert result.metrics["reward"] == pytest.approx(
        context.scoring.quality_weight + context.scoring.functional_weight * expected_fraction
    )


def test_missing_cli_does_not_skip_executable_api_checks(context: VerificationContext) -> None:
    """Report command launch failures while still exercising the importable API.

    Args:
        context: Working application whose CLI executable will be removed.
    """
    (context.app.root / "orange").unlink()

    result = verifier.verify(context)

    outcomes = {check.requirement: check.status for check in result.checks}
    assert len(outcomes) == len(verifier.CHECKS)
    assert "skipped" not in outcomes.values()
    for requirement in ("interfaces", "ingestion_and_persistence", "progress_file"):
        assert outcomes[requirement] == "passed"
    for requirement in ("holdout_accuracy", "cli_help", "duplicate_documents", "cli_stdin"):
        assert outcomes[requirement] == "failed"
    assert not result.passed


def test_application_uses_runtime_instead_of_judge_interpreter(context: VerificationContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """Select the application runtime in a container, retaining submitted venv precedence.

    Args:
        context: Local application adapter.
        monkeypatch: Simulate the preinstalled container runtime path.
    """
    original = Path.exists

    def exists(path: Path) -> bool:
        """Expose the container runtime without modifying the local filesystem.

        Args:
            path: Candidate path queried by the adapter.

        Returns:
            True for the container runtime or any existing local path.
        """
        return str(path) in {"/opt/application/bin/python", "/opt/runtime/bin/python"} or original(path)

    monkeypatch.setattr(Path, "exists", exists)
    assert context.app.python() == "/opt/application/bin/python"
    assert context.app.environment["PATH"].split(":")[1:3] == ["/opt/application/bin", "/opt/runtime/bin"]
    submitted = context.app.root / ".venv/bin/python"
    submitted.parent.mkdir(parents=True)
    submitted.touch()
    assert context.app.python() == str(submitted)


def test_every_requirement_function_is_registered() -> None:
    """Prevent a defined acceptance check from silently escaping orchestration."""
    modules = [importlib.import_module(info.name) for info in pkgutil.iter_modules(
        requirement_package.__path__, requirement_package.__name__ + "."
    ) if info.name.rsplit(".", 1)[-1].startswith("test_")]
    defined = {value for module in modules for name, value in vars(module).items()
               if name.startswith("test_") and callable(value) and value.__module__ == module.__name__}
    registered = {check.function for check in verifier.CHECKS}
    assert registered == defined
    seen: set[str] = set()
    for check in verifier.CHECKS:
        assert check.name not in seen
        assert set(check.requires) <= seen
        seen.add(check.name)


@pytest.mark.parametrize("before,after,check", [
    ("if row[\"doc_id\"] not in existing:", "if True:", "duplicate_documents"),
    ("if event.refresh:", "if False:", "refresh_replaces_index"),
    ('evidence = await retrieve(query, "hybrid")', "evidence = RetrievedItem(passages=[])", "required_call_paths"),
    ("query: str, retrieval_method: RetrievalMethod", "query: str", "interfaces"),
    ("from pydantic import BaseModel, Field", "from typing import TypedDict as BaseModel\nfrom pydantic import Field", "interfaces"),
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
    modified = path.read_text().replace(before, after)
    if check == "duplicate_documents":
        modified = modified.replace("collection.add(", "collection.upsert(")
    path.write_text(modified)
    function = next(item.function for item in verifier.CHECKS if item.name == check)
    with pytest.raises(CandidateFailure):
        function(context)


@pytest.mark.parametrize("operation,model", [("retrieve", "RetrievedItem"), ("generate", "GeneratedAnswer")])
def test_plain_dictionary_returns_are_rejected(context: VerificationContext, operation: str, model: str) -> None:
    """Reject correctly shaped dictionaries where the API promises model instances.

    Args:
        context: Fixture app with valid Pydantic annotations.
        operation: Public function whose return value is changed to a dictionary.
        model: Model constructor identifying the fixture's return statement.
    """
    corpus = context.app.write_json("model-returns.json", json.loads(context.corpus_path.read_text()))
    context.app.probe("ingest", {"corpus_path": str(corpus), "refresh": True})
    path = context.app.root / "main.py"
    lines = path.read_text().splitlines()
    path.write_text("\n".join(
        line + '.model_dump(mode="json")' if line.strip().startswith(f"return {model}(") else line
        for line in lines
    ) + "\n")
    with pytest.raises(CandidateFailure, match="must return"):
        context.app.probe(operation, "release-0")


def test_missing_answers_use_the_full_denominator(context: VerificationContext) -> None:
    """Confirm an omitted answer contributes zero instead of shrinking the mean.

    Args:
        context: Two-case fixture with one answer removed by a CLI regression.
    """
    path = context.app.root / "cli.py"
    path.write_text(path.read_text().replace("if args.output:", "answers = [row for row in answers if row['question_id'] == 0]\n        if args.output:"))
    result = accuracy.test_holdout_accuracy(context)
    assert result.status == "passed"
    assert result.metrics["accuracy_percent"] == 50
    assert result.metrics["missing_answers"] == 1


def test_bad_citations_and_duplicate_answer_ids_are_rejected() -> None:
    """Reject false provenance during accuracy evaluation and duplicate CLI IDs."""
    document = {"doc_id": "d", "source_type": "document", "title": "title", "content": "Friday"}
    from verifier.judging.evaluation import citations_are_exact
    assert not citations_are_exact([{"doc_id": "d", "quote": "Monday"}], {"d": document})
    answer = {"question_id": 0, "answer": "Friday", "citations": []}
    with pytest.raises(CandidateFailure):
        support.answer_records([answer, answer], [0])


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
        RegisteredCheck("cli_help", cli.test_cli_help),
    ))
    result = verifier.verify(context)
    assert [check.status for check in result.checks] == ["failed", "skipped", "passed"]


def test_judge_failure_keeps_diagnostics_and_removes_rewards(context: VerificationContext) -> None:
    """Preserve earlier judgments while refusing a reward after provider failure.

    Args:
        context: Local application and two controlled questions.
    """
    class FailingJudge(ExactJudge):
        """Judge that fails after recording one successful rating."""

        def grade(self, case: HeldOutCase, answer: str) -> AnswerJudgment:
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
            return AnswerJudgment(100, "Controlled correct answer", "correct")

    context.judge = FailingJudge()
    for filename in ("reward.json", "reward.txt"):
        (context.output_dir / filename).write_text("1")
    with pytest.raises(EvaluationError):
        verifier.verify(context)
    write_report(context.output_dir, context, None, "Controlled outage")
    assert len(context.completed) == 0
    assert len(json.loads((context.output_dir / "judgments.json").read_text())) == 1
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
    It never downloads dataset or prints private question text.
    """
    task = TASK_ROOT
    private = task / "steps/01-build-rag/tests/private"
    if not private.exists():
        pytest.skip("Run scripts/prepare_data.py before checking real bundle")
    corpus_path, cases, manifest = load_inputs(private)
    from verifier.corpus import open_corpus
    corpus = open_corpus(corpus_path)
    public = json.loads((task / "environment/data/corpus.json").read_text())
    import random

    ids = list(corpus)
    assert public == [corpus[ids[index]] for index in random.Random(SAMPLE_SEED).sample(range(len(corpus)), int(len(corpus) * SAMPLE_FRACTION))]
    assert 0 < len(public) / len(corpus) < 0.05
    assert len(cases) == QUESTION_COUNT
    policy = json.loads((task / "scripts/holdout_exclusions.json").read_text())
    assert not {case.question_id for case in cases} & set(policy["excluded_question_ids"])
    assert manifest["excluded_question_ids"] == policy["excluded_question_ids"]
    assert all(set(row) == {"doc_id", "source_type", "title", "content"} for row in public)
    assert manifest["sample_records"] == len(public)


@pytest.mark.parametrize("check", ["cli_stdin", "cli_question_files"])
def test_line_delimited_answer_output_is_rejected(context: VerificationContext, check: str) -> None:
    """Reject separate JSON objects where the CLI promises one JSON array.

    Args:
        context: Conforming application fixture whose stdout is mutated.
        check: Requirement exercising stdin or file-based question input.
    """
    path = context.app.root / "cli.py"
    path.write_text(path.read_text().replace(
        "print(json.dumps(answers))",
        "print('\\n'.join(json.dumps(answer) for answer in answers))",
    ))
    function = next(item.function for item in verifier.CHECKS if item.name == check)
    with pytest.raises(CandidateFailure, match="one JSON array"):
        function(context)


def test_only_progress_file_is_required(context: VerificationContext) -> None:
    """Accept progress presence without inspecting development dataset contents.

    Args:
        context: Application with a development directory.
    """
    root = context.app.root / "dev"
    shutil.rmtree(root)
    root.mkdir()
    (root / "progress.md").touch()
    assert progress.test_progress_file(context).status == "passed"
    (root / "progress.md").unlink()
    with pytest.raises(CandidateFailure):
        progress.test_progress_file(context)
