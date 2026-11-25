"""Regression checks for the current interface, CLI-only scoring, and weighted reward."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest
from task_paths import TASK_ROOT
from test_verifier import ExactJudge
from verifier import runner as verify
from verifier.application.process import CommandResult
from verifier.checks import test_accuracy as accuracy
from verifier.checks import (
    test_cli as cli,
)
from verifier.checks import (
    test_interfaces as interfaces,
)
from verifier.checks import test_retrieval as retrieval
from verifier.checks import test_storage as storage
from verifier.contracts import (
    CandidateFailure,
    CheckResult,
    Judgment,
    RegisteredCheck,
    SourceDocument,
    VerificationContext,
)
from verifier.reporting import write_report
from verifier.scoring import aggregate_results


@pytest.mark.parametrize(
    "payload", [{}, {"value": None, "calls": [], "exit_code": 0, "events": []}]
)
def test_forged_probe_output_cannot_replace_interface_declarations(
    context: VerificationContext,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
) -> None:
    """Reject forged success with no interfaces without executing the payload.

    Args:
        context: Candidate workspace to replace with the reproduced exploit.
        monkeypatch: Reject any attempt to run candidate code for this check.
        payload: Empty or correctly shaped success record printed by the exploit.
    """
    marker = context.app.root / "exploit-ran"
    source = (
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        f"print({'\nORANGE_PROBE=' + json.dumps(payload)!r}, flush=True)\n"
        "import os\nos._exit(0)\n"
    )
    (context.app.root / "main.py").write_text(source)

    def forbidden(*args: object, **kwargs: object) -> CommandResult:
        """Reject subprocess execution during trusted interface inspection.

        Args:
            args: Unexpected process arguments.
            kwargs: Unexpected process settings.

        Raises:
            AssertionError: Candidate execution is not part of source inspection.
        """
        raise AssertionError("Interface check must not execute candidate code")

    monkeypatch.setattr(context.app, "run", forbidden)
    with pytest.raises(CandidateFailure, match="Missing or rebound declaration"):
        interfaces.test_interfaces(context)
    assert not marker.exists()


def test_fake_interpreter_and_full_success_cannot_hide_wrong_description(
    context: VerificationContext,
) -> None:
    """Reject metadata drift despite a forged interpreter and import-time exit.

    Args:
        context: Fixture retaining the required declarations except one description.
    """
    payload = json.dumps({"value": None, "calls": [], "exit_code": 0, "events": []})
    marker = context.app.root / "fake-python-ran"
    fake_python = context.app.root / ".venv/bin/python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text(
        f"#!/bin/sh\ntouch '{marker}'\nprintf '\\nORANGE_PROBE={payload}\\n'\n"
    )
    fake_python.chmod(0o755)
    path = context.app.root / "main.py"
    source = path.read_text().replace(
        "Path to the JSON corpus file.", "Wrong description."
    )
    # Future imports must remain first; inject an early exit immediately after it.
    source = source.replace(
        "from __future__ import annotations",
        "from __future__ import annotations\n"
        f"print({'\nORANGE_PROBE=' + payload!r}, flush=True)\n"
        "import os\nos._exit(0)",
    )
    path.write_text(source)
    with pytest.raises(CandidateFailure, match="Incorrect description"):
        interfaces.test_interfaces(context)
    assert not marker.exists()


def test_dead_code_and_rebound_exports_cannot_satisfy_source_contract(
    context: VerificationContext,
) -> None:
    """Reject declarations hidden in a false branch or overwritten at module scope.

    Args:
        context: Working fixture to replace with nonexported declarations.
    """
    path = context.app.root / "main.py"
    original = path.read_text()
    declarations = original.replace("from __future__ import annotations\n", "")
    path.write_text(
        "if False:\n" + "\n".join("    " + line for line in declarations.splitlines())
    )
    with pytest.raises(CandidateFailure, match="Missing or rebound"):
        interfaces.test_interfaces(context)
    path.write_text(original + "\ngenerate = None\n")
    with pytest.raises(CandidateFailure, match="Missing or rebound"):
        interfaces.test_interfaces(context)


def test_instruction_interface_block_passes_without_running_function_bodies(
    context: VerificationContext,
) -> None:
    """Accept the exact published form without executing its imports or stubs.

    Args:
        context: Workspace receiving the instruction's unchanged Python code block.
    """
    instruction = (TASK_ROOT / "instruction.md").read_text()
    source = instruction.split("```python\n", 1)[1].split("```", 1)[0]
    (context.app.root / "main.py").write_text(source)
    assert interfaces.test_interfaces(context).status == "passed"


def test_qualified_imports_and_forward_annotations_preserve_contract(
    context: VerificationContext,
) -> None:
    """Accept equivalent import spellings, forward types, and additional model fields.

    Args:
        context: Working fixture using qualified Pydantic imports and string types.
    """
    path = context.app.root / "main.py"
    source = path.read_text().replace(
        "from pydantic import BaseModel, Field", "import pydantic as pd"
    )
    source = source.replace(
        "(BaseModel):", "(pd.BaseModel):\n    extra: str = 'allowed'"
    )
    source = source.replace("Field(description=", "pd.Field(description=")
    source = source.replace("event: IngestEvent", 'event: "IngestEvent"')
    source = source.replace("-> GeneratedAnswer:", '-> "GeneratedAnswer":')
    path.write_text(source)
    assert interfaces.test_interfaces(context).status == "passed"


def test_empty_runtime_probe_record_is_rejected(
    context: VerificationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject the reproduced empty record for remaining runtime observations too.

    Args:
        context: Application adapter whose process output will be forged.
        monkeypatch: Replace process execution without running candidate code.
    """

    def forged(*args: object, **kwargs: object) -> CommandResult:
        """Return an empty observation with a successful process exit.

        Args:
            args: Unused command arguments.
            kwargs: Unused process settings.

        Returns:
            The malformed success record from the reproduced exploit.
        """
        return CommandResult(0, "\nORANGE_PROBE={}", "")

    monkeypatch.setattr(context.app, "run", forged)
    with pytest.raises(CandidateFailure, match="valid JSON"):
        context.app.probe("ingest", {})
    with pytest.raises(CandidateFailure, match="Unsupported"):
        context.app.probe("interfaces")


@pytest.mark.parametrize(
    "before,after",
    [
        ("class Passage(BaseModel):", "class HiddenPassage(BaseModel):"),
        ('"Path to the JSON corpus file."', '"Path to a JSON corpus file."'),
        ('Literal["bm25", "embed", "hybrid"]', 'Literal["bm25", "embed"]'),
        ("retrieval_method: RetrievalMethod", "retrieval_method: str"),
        ("quote: str = Field", "quote: int = Field"),
    ],
)
def test_interface_mutations_fail(
    context: VerificationContext, before: str, after: str
) -> None:
    """Reject missing exports, description drift, and incorrect type contracts.

    Args:
        context: Controlled candidate workspace.
        before: Valid source fragment.
        after: Deliberately invalid replacement.
    """
    path = context.app.root / "main.py"
    assert before in path.read_text()
    text = path.read_text().replace(before, after)
    if "HiddenPassage" in after:
        text = text.replace("list[Passage]", "list[HiddenPassage]").replace(
            "Passage(doc_id=", "HiddenPassage(doc_id="
        )
    path.write_text(text)
    with pytest.raises(CandidateFailure):
        interfaces.test_interfaces(context)


def test_extra_model_fields_are_allowed(context: VerificationContext) -> None:
    """Accept extended Pydantic models that retain the mandatory public fields.

    Args:
        context: Fixture app whose four models gain optional metadata.
    """
    path = context.app.root / "main.py"
    text = path.read_text()
    for model in ("IngestEvent", "Passage", "RetrievedItem", "GeneratedAnswer"):
        text = text.replace(
            f"class {model}(BaseModel):",
            f"class {model}(BaseModel):\n    extra_info: str = 'optional'",
        )
    path.write_text(text)
    interfaces.test_interfaces(context)
    cli.test_required_call_paths(context)


@pytest.mark.parametrize("mutation", ["omit", "change"])
def test_echoed_question_is_required(
    context: VerificationContext, mutation: str
) -> None:
    """Reject CLI answers with absent or altered original question text.

    Args:
        context: Controlled application with JSON output.
        mutation: Whether to omit or alter the echoed question.
    """
    path = context.app.root / "cli.py"
    replacement = "" if mutation == "omit" else '"question": "wrong question", '
    path.write_text(
        path.read_text().replace('"question": row["question"], ', replacement)
    )
    with pytest.raises(CandidateFailure, match="Original question"):
        cli.test_cli_question_files(context)


def test_each_generation_requires_nested_retrieval(
    context: VerificationContext,
) -> None:
    """Reject a batch whose first answer retrieves but second generation bypasses it.

    Args:
        context: Fixture with different questions in the call-path scenario.
    """
    path = context.app.root / "main.py"
    path.write_text(
        path.read_text().replace(
            'evidence = await retrieve(query, "hybrid")',
            'evidence = RetrievedItem(passages=[]) if query.startswith("Summarize") else await retrieve(query, "hybrid")',
        )
    )
    with pytest.raises(CandidateFailure, match="Each generate"):
        cli.test_required_call_paths(context)


def test_cli_must_generate_each_question(context: VerificationContext) -> None:
    """Reject a CLI that skips generation for all but the first batch question.

    Args:
        context: Fixture CLI whose input iteration is truncated.
    """
    path = context.app.root / "cli.py"
    path.write_text(
        path.read_text().replace("for row in questions]", "for row in questions[:1]]")
    )
    with pytest.raises(CandidateFailure, match="every question"):
        cli.test_required_call_paths(context)


def test_accuracy_uses_only_cli_and_forces_refresh(
    context: VerificationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Observe forced refresh as the first operation and prohibit direct API probes.

    Args:
        context: Working CLI fixture and deterministic judge.
        monkeypatch: Temporary observation wrappers.
    """
    calls: list[tuple[str, ...]] = []
    original = context.app.cli
    original_bounded = context.app.bounded_cli

    def cli(*args: str, **kwargs: Any) -> Any:
        """Record CLI arguments and delegate execution.

        Args:
            args: Public command arguments.
            kwargs: Subprocess options.

        Returns:
            The real child-process result.
        """
        calls.append(args)
        return original(*args, **kwargs)

    def bounded_cli(*args: str, **kwargs: Any) -> Any:
        """Observe answer commands while preserving real budget enforcement.

        Args:
            args: Public command arguments.
            kwargs: Retrieval budget and subprocess options.

        Returns:
            The real bounded child-process result.
        """
        calls.append(args)
        return original_bounded(*args, **kwargs)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        """Fail if accuracy tries to invoke an API probe.

        Args:
            args: Unexpected probe arguments.
            kwargs: Unexpected probe options.
        """
        raise AssertionError("Accuracy must use the CLI only")

    monkeypatch.setattr(context.app, "cli", cli)
    monkeypatch.setattr(context.app, "bounded_cli", bounded_cli)
    monkeypatch.setattr(context.app, "probe", forbidden)
    assert accuracy.test_holdout_accuracy(context).status == "passed"
    assert calls[0][0] == "ingest" and "--refresh" in calls[0]
    assert calls[1][0] == "answer"
    assert verify.CHECKS[0].name == "holdout_accuracy"
    assert not verify.CHECKS[0].requires


def test_citation_support_reduces_quality_without_erasing_accuracy(
    context: VerificationContext,
) -> None:
    """Keep answer correctness visible while applying semantic citation penalties.

    Args:
        context: Fixture with fully correct answers and a partial-support judge.
    """

    class PartialSupport(ExactJudge):
        """Controlled citation scorer for the weighted quality formula."""

        def grade_citations(
            self,
            question: str,
            answer: str,
            citations: list[dict[str, str]],
            documents: list[SourceDocument],
        ) -> Judgment:
            """Return a controlled partial support rating.

            Args:
                question: Unused public question.
                answer: Unused candidate answer.
                citations: Unused source quotations.
                documents: Unused original source records.

            Returns:
                A 50-point support rating.
            """
            return Judgment(50, "Half supported")

    context.judge = PartialSupport()
    result = accuracy.test_holdout_accuracy(context)
    assert result.metrics["answer_rating_percent"] == 100
    assert result.metrics["accuracy_percent"] == 100
    assert result.metrics["citation_support_percent"] == 50
    assert result.status == "passed"
    assert aggregate_results([result], context.scoring).metrics[
        "quality_fraction"
    ] == pytest.approx(0.95)


@pytest.mark.parametrize(
    "score,pass_functional,expected",
    [
        (90, True, 0.928),
        (45, True, 0.604),
        (0, True, 0),
        (100, False, 0.8),
        (0, False, 0),
        (100, True, 1),
    ],
)
def test_weighted_reward(
    context: VerificationContext,
    monkeypatch: pytest.MonkeyPatch,
    score: float,
    pass_functional: bool,
    expected: float,
) -> None:
    """Check raw reward boundaries and functional partial credit.

    Args:
        context: Verifier context without live model calls.
        monkeypatch: Temporary registry override.
        score: Controlled grounded answer percentage.
        pass_functional: Whether the controlled functional check passes.
        expected: Expected reward in [0, 1].
    """

    def quality(ctx: VerificationContext) -> CheckResult:
        """Return a controlled quality score.

        Args:
            ctx: Unused evaluation context.

        Returns:
            A thresholded accuracy result.
        """
        return CheckResult(
            "holdout_accuracy",
            "passed",
            "controlled",
            {
                "nonzero_answer_fraction": float(score > 0),
                "accuracy_percent": score,
                "citation_support_percent": 100 if score > 0 else 0,
            },
        )

    def functional(ctx: VerificationContext) -> CheckResult:
        """Return a controlled functional outcome.

        Args:
            ctx: Unused evaluation context.

        Returns:
            One equally weighted functional result.
        """
        return CheckResult(
            "functional", "passed" if pass_functional else "failed", "controlled"
        )

    monkeypatch.setattr(
        verify,
        "CHECKS",
        (
            RegisteredCheck("holdout_accuracy", quality),
            RegisteredCheck("functional", functional),
        ),
    )
    result = verify.verify(context)
    assert result.metrics["reward"] == pytest.approx(expected)
    write_report(context.output_dir, context, result, None)
    assert json.loads((context.output_dir / "reward.json").read_text())[
        "reward"
    ] == pytest.approx(expected)


def test_call_chain_accepts_async_child_task(context: VerificationContext) -> None:
    """Accept nested retrieval scheduled through an asyncio child task.

    Args:
        context: Valid fixture whose generate function creates a retrieval task.
    """
    path = context.app.root / "main.py"
    text = path.read_text().replace("import json", "import json\nimport asyncio")
    text = text.replace(
        'await retrieve(query, "hybrid")',
        'await asyncio.create_task(retrieve(query, "hybrid"))',
    )
    path.write_text(text)
    cli.test_required_call_paths(context)


@pytest.mark.parametrize(
    "launcher", ["#!/bin/sh\nexit 0\n", "#!/usr/bin/env python3\nprint('[]')\n"]
)
def test_call_chain_rejects_real_launcher_bypassing_cli(
    context: VerificationContext, launcher: str
) -> None:
    """Reject an executable that bypasses the otherwise correct cli.py implementation.

    Args:
        context: Working Python application whose actual entry point is replaced.
        launcher: Successful shell or Python no-op hiding a valid implementation.
    """
    (context.app.root / "orange").write_text(launcher)
    with pytest.raises(CandidateFailure):
        cli.test_required_call_paths(context)


def test_call_chain_executes_shell_launcher(context: VerificationContext) -> None:
    """Exercise shell forwarding through the real executable, preserving arguments.

    Args:
        context: Working fixture using a shell launcher with an observable side effect.
    """
    marker = context.app.root / "launcher-calls"
    (context.app.root / "orange").write_text(
        f"#!/bin/sh\nprintf 'launched\\n' >> {shlex.quote(str(marker))}\n"
        f'exec {shlex.quote(sys.executable)} {shlex.quote(str(context.app.root / "cli.py"))} "$@"\n'
    )
    cli.test_required_call_paths(context)
    assert marker.read_text().splitlines() == ["launched", "launched"]


@pytest.mark.parametrize("partial", [False, True])
def test_full_corpus_persistence_inspects_original_cli_refresh(
    context: VerificationContext, partial: bool
) -> None:
    """Inspect the actual full refresh and reject partial ingestion without repairing it.

    Args:
        context: Two-document private corpus and controlled answer judge.
        partial: Whether ingestion silently drops all but the first record.
    """
    if partial:
        path = context.app.root / "main.py"
        path.write_text(
            path.read_text().replace(
                "for row in json.loads(Path(event.corpus_path).read_text()):",
                "for row in json.loads(Path(event.corpus_path).read_text())[:1]:",
            )
        )
    accuracy.test_holdout_accuracy(context)
    if partial:
        with pytest.raises(CandidateFailure, match="Stored document IDs"):
            storage.test_full_corpus_persistence(context)
    else:
        assert storage.test_full_corpus_persistence(context).status == "passed"


@pytest.mark.parametrize("method", ["bm25", "embed", "hybrid"])
def test_each_retrieval_behavior_rejects_empty_results(
    context: VerificationContext, method: str
) -> None:
    """Reject a typed but empty result for each independently exercised method.

    Args:
        context: Working retrieval fixture to mutate for one mode only.
        method: Mode that silently returns no evidence.
    """
    path = context.app.root / "main.py"
    source = path.read_text()
    anchor = (
        '    data = client().get_collection("documents", embedding_function=None).get('
    )
    assert anchor in source
    path.write_text(
        source.replace(
            anchor,
            f"    if retrieval_method == {method!r}:\n        return RetrievedItem(passages=[])\n"
            + anchor,
        )
    )
    check = getattr(retrieval, f"test_{method}_behavior")
    with pytest.raises(CandidateFailure, match=f"{method} behavior"):
        check(context)


def test_retrieval_behaviors_each_refresh_ten_documents(
    context: VerificationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Give each mode its own empty state and ten answerable documents.

    Args:
        context: Working fixture whose real ingestion and retrieval execute.
        monkeypatch: Observe setup while retaining the actual executable.
    """
    actual_cli = context.app.cli
    corpora: list[list[dict[str, str]]] = []

    def observe(*args: str, **kwargs: Any) -> CommandResult:
        """Check isolation before forwarding the actual CLI invocation.

        Args:
            args: Command arguments selected by the behavior test.
            kwargs: Normal process limits and stdin settings.

        Returns:
            Actual CLI process result.
        """
        assert args[0] == "ingest" and "--refresh" in args
        assert not (context.app.root / "state").exists()
        rows = json.loads(Path(args[args.index("--path") + 1]).read_text())
        assert len(rows) == 10
        corpora.append(rows)
        return actual_cli(*args, **kwargs)

    monkeypatch.setattr(context.app, "cli", observe)
    for check in (
        retrieval.test_bm25_behavior,
        retrieval.test_embed_behavior,
        retrieval.test_hybrid_behavior,
    ):
        assert check(context).status == "passed"
    assert len({row["doc_id"] for rows in corpora for row in rows}) == 30
