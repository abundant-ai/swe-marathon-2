"""Step-1 baseline tests using real stores/CLI and controlled model services."""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from oracle_support import SOLUTION, InstalledOracle, install_oracle, model_service
from task_paths import TASK_ROOT
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
    RegisteredCheck,
    SourceDocument,
    VerificationContext,
)
from verifier.registry import CHECKS


class UnusedJudge(Judge):
    """Reject accidental accuracy grading in this functional test suite."""

    def grade(self, case: HeldOutCase, answer: str) -> AnswerJudgment:
        """Fail if a functional test attempts to rate an answer.

        Args:
            case: Unused private-reference argument.
            answer: Unused candidate text.

        Raises:
            AssertionError: Accuracy evaluation is outside this controlled suite.
        """
        raise AssertionError("These tests do not grade accuracy")

    def grade_citations(
        self,
        question: str,
        answer: str,
        citations: list[dict[str, str]],
        documents: list[SourceDocument],
    ) -> Judgment:
        """Fail if a functional test attempts semantic citation grading.

        Args:
            question: Unused user question.
            answer: Unused candidate text.
            citations: Unused citations.
            documents: Unused original records.

        Raises:
            AssertionError: Semantic grading requires a separate live evaluation.
        """
        raise AssertionError("These tests do not grade citation quality")


@pytest.fixture
def installed(
    tmp_path: Path, chroma_endpoint: dict[str, str]
) -> Iterator[InstalledOracle]:
    """Install a fresh baseline and local model service for each behavioral test.

    Args:
        tmp_path: Isolated test directory, separate from source and private inputs.
        chroma_endpoint: Isolated HTTP database inherited by the application.

    Yields:
        Installed public application and model request log.
    """
    with model_service() as server:
        yield install_oracle(tmp_path / "app", server)


FUNCTIONAL_CHECKS = [
    check
    for check in CHECKS
    if check.name not in {"holdout_accuracy", "full_corpus_persistence"}
]


@pytest.mark.parametrize(
    "check", FUNCTIONAL_CHECKS, ids=[check.name for check in FUNCTIONAL_CHECKS]
)
def test_existing_functional_contract(
    installed: InstalledOracle, check: RegisteredCheck
) -> None:
    """Run each existing functional verifier check against the installed oracle.

    Args:
        installed: Real application with deterministic model adapters.
        check: One registered functional requirement; no private corpus is loaded.
    """
    settings = tomllib.loads((TASK_ROOT / "task.toml").read_text())["verifier"]["env"]
    context = VerificationContext(
        installed.app,
        installed.app.root / "unused.json",
        (),
        UnusedJudge(),
        installed.app.root,
        load_scoring_config(settings),
        load_generation_config(settings),
        load_ingestion_timeout(settings),
    )
    assert check.function(context).status == "passed"


def test_chunking_and_rrf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Check exact overlapping excerpts and fixed-k fusion on known rankings.

    Args:
        monkeypatch: Add the solution source only for pure helper imports.
    """
    monkeypatch.syspath_prepend(str(SOLUTION / "app"))
    retrieval = importlib.import_module("orange_core.retrieval")
    document = retrieval.Document(
        doc_id="doc", source_type="test", title="title", content="abcdefghij"
    )
    hits = retrieval.chunk_document(document, 4, 1)
    assert [hit.quote for hit in hits] == ["abcd", "defg", "ghij"]
    a, b, c = hits
    assert retrieval.reciprocal_rank_fusion([[a, b], [b, c]]) == [b, a, c]
    assert [
        hit.chunk_id for hit in retrieval.reciprocal_rank_fusion([[a, a], [b]])
    ] == sorted([a.chunk_id, b.chunk_id])
    config = importlib.import_module("orange_core.config")
    assert config.TOP_K == config.RRF_K == 20


def test_top_twenty_and_exact_passages(installed: InstalledOracle) -> None:
    """Exercise all retrieval modes over more than k real persisted documents.

    Args:
        installed: Independent oracle with controlled embeddings.
    """
    documents = [
        {
            "doc_id": str(index),
            "source_type": "test",
            "title": "Cedar",
            "content": f"Cedar release detail {index}.",
        }
        for index in range(30)
    ]
    path = installed.app.write_json("corpus.json", documents)
    installed.app.cli("ingest", "--path", str(path), "--refresh")
    original = {row["doc_id"]: row["content"] for row in documents}
    for method in ("bm25", "embed", "hybrid"):
        result = installed.app.probe(
            "retrieve", {"query": "Cedar", "retrieval_method": method}
        )["value"]
        assert len(result["passages"]) == 20
        assert all(
            row["quote"] in original[row["doc_id"]] for row in result["passages"]
        )


def test_iterative_generation_and_ten_processes(installed: InstalledOracle) -> None:
    """Run ten independent answer processes sharing one persistent index.

    Args:
        installed: Real CLI with a model that requires two tool rounds per answer.
    """
    corpus = installed.app.write_json(
        "corpus.json",
        [
            {
                "doc_id": "cedar",
                "source_type": "test",
                "title": "Cedar",
                "content": "Cedar followup owner is Ada Chen.",
            }
        ],
    )
    installed.app.cli("ingest", "--path", str(corpus), "--refresh")

    def answer(index: int) -> dict[str, object]:
        """Invoke a separate CLI with its own output path and original question.

        Args:
            index: Unique request identifier.

        Returns:
            Parsed single answer record from that process's output file.
        """
        question = f"Who owns Cedar followup? Request {index}"
        output = installed.app.root / f"answer-{index}.json"
        installed.app.cli(
            "answer",
            "--output",
            str(output),
            stdin=json.dumps([{"question_id": index, "question": question}]),
        )
        row = json.loads(output.read_text())[0]
        assert row["question_id"] == index and row["question"] == question
        assert row["citations"] == [
            {"doc_id": "cedar", "quote": "Cedar followup owner is Ada Chen."}
        ]
        return row

    with ThreadPoolExecutor(max_workers=10) as pool:
        assert len(list(pool.map(answer, range(10)))) == 10
    assert len(installed.server.requests) == 30
    assert (
        sum(row["tool_choice"] == "required" for row in installed.server.requests) == 10
    )
    assert all(row["text"]["format"]["strict"] for row in installed.server.requests)
    tool = installed.server.requests[0]["tools"][0]
    assert tool["name"] == "retrieve" and tool["strict"] is True
    assert set(tool["parameters"]["required"]) == {"query", "retrieval_method"}
    assert tool["parameters"]["properties"]["retrieval_method"]["enum"] == [
        "bm25",
        "embed",
        "hybrid",
    ]


def test_duplicate_question_ids_fail_before_generation(
    installed: InstalledOracle,
) -> None:
    """Reject duplicate IDs across files without calling the model service.

    Args:
        installed: Fresh installed CLI with no index required for input validation.
    """
    first = installed.app.write_json(
        "first.json", [{"question_id": 0, "question": "first"}]
    )
    second = installed.app.write_json(
        "second.json", [{"question_id": 0, "question": "second"}]
    )
    result = installed.app.cli(
        "answer", "--questions", str(first), str(second), require_success=False
    )
    assert result.code != 0 and "unique" in result.stderr
    assert not installed.server.requests


@pytest.mark.parametrize("mode", ["fabricated_citation", "incomplete"])
def test_invalid_model_output_fails_cleanly(
    installed: InstalledOracle, mode: str
) -> None:
    """Reject invented references and truncated responses without emitting answers.

    Args:
        installed: Independent CLI and configurable controlled model endpoint.
        mode: Malformation deliberately produced by the endpoint.
    """
    installed.server.answer_mode = mode
    path = installed.app.write_json(
        "corpus.json",
        [
            {
                "doc_id": "cedar",
                "source_type": "test",
                "title": "Cedar",
                "content": "Ada owns Cedar.",
            }
        ],
    )
    installed.app.cli("ingest", "--path", str(path), "--refresh")
    result = installed.app.cli(
        "answer",
        stdin='[{"question_id":0,"question":"Who owns Cedar?"}]',
        require_success=False,
    )
    assert result.code != 0 and not result.stdout.strip()
    if mode == "incomplete":
        assert "did not complete" in result.stderr, result.stderr
    else:
        assert "retries" in result.stderr, result.stderr
        settings = json.loads((installed.app.root / "oracle-config.json").read_text())
        assert (
            len(installed.server.requests)
            == installed.server.search_rounds + 1 + settings["output_retries"]
        )


def test_interrupted_ingestion_requires_refresh(installed: InstalledOracle) -> None:
    """Do not serve partially populated or inconsistent lexical/vector state.

    Args:
        installed: Fresh application whose state is marked incomplete below.
    """
    state = installed.app.root / "state"
    state.mkdir()
    path = installed.app.write_json("empty.json", [])
    append = installed.app.cli("ingest", "--path", str(path), require_success=False)
    assert append.code != 0 and "--refresh" in append.stderr
    installed.app.cli("ingest", "--path", str(path), "--refresh")
    for method in ("bm25", "embed", "hybrid"):
        assert not installed.app.probe(
            "retrieve", {"query": "anything", "retrieval_method": method}
        )["value"]["passages"]


def test_solution_installs_outside_checkout(tmp_path: Path) -> None:
    """Install an isolated copy using no imports or relative paths from the repo.

    Args:
        tmp_path: Temporary extracted-solution and application directories.
    """
    source = tmp_path / "solution"
    shutil.copytree(
        SOLUTION, source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    app = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-I",
            str(source / "oracle.py"),
            "--app-root",
            str(app),
            "--install-only",
        ],
        cwd=tmp_path,
        check=True,
    )
    help_result = subprocess.run(
        [str(app / "orange"), "help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ingest" in help_result.stdout and "answer" in help_result.stdout
    assert not (app / "oracle.py").exists() and not (app / "tests").exists()


def test_complete_oracle_entry_point(
    installed: InstalledOracle, tmp_path: Path
) -> None:
    """Run development generation and ensure the final index uses only the sample.

    Args:
        installed: Public workspace and controlled endpoint.
        tmp_path: Isolated solution copy whose public model configuration is changed.
    """
    source = tmp_path / "isolated-solution"
    shutil.copytree(
        SOLUTION, source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    shutil.copy2(
        installed.app.root / "oracle-config.json", source / "app/oracle-config.json"
    )
    sample = installed.app.write_json(
        "sample.json",
        [
            {
                "doc_id": "sample",
                "source_type": "document",
                "title": "Public sample",
                "content": "Public company record.",
            }
        ],
    )
    installed.app.run(
        [
            sys.executable,
            str(source / "oracle.py"),
            "--app-root",
            str(installed.app.root),
            "--corpus",
            str(sample),
        ]
    )
    development = installed.app.root / "dev/v1"
    assert {path.name for path in development.iterdir()} == {
        "corpus.json",
        "questions.json",
        "answers.json",
        "report.json",
    }
    report = json.loads((development / "report.json").read_text())
    assert all(row["reference_present"] for row in report["results"])
    passages = installed.app.probe(
        "retrieve", {"query": "Public", "retrieval_method": "hybrid"}
    )["value"]["passages"]
    assert {row["doc_id"] for row in passages} == {"sample"}
    assert "Completed" in (installed.app.root / "dev/PROGRESS.MD").read_text()


def test_search_budget_forces_final_answer(installed: InstalledOracle) -> None:
    """Stop offering search tools after the configured round budget is consumed.

    Args:
        installed: Application whose policy is reduced to one search round.
    """
    path = installed.app.root / "oracle-config.json"
    settings = json.loads(path.read_text())
    settings["max_search_rounds"] = 1
    path.write_text(json.dumps(settings))
    corpus = installed.app.write_json(
        "sample.json",
        [
            {
                "doc_id": "sample",
                "source_type": "document",
                "title": "Cedar",
                "content": "Ada owns Cedar.",
            }
        ],
    )
    installed.app.cli("ingest", "--path", str(corpus), "--refresh")
    answer = installed.app.cli(
        "answer", stdin='[{"question_id":0,"question":"Who owns Cedar?"}]'
    )
    assert "Ada" in json.loads(answer.stdout)[0]["answer"]
    assert installed.server.requests[0]["tool_choice"] == "required"
    assert len(installed.server.requests) == 2
    assert not installed.server.requests[-1].get("tools")


def test_oracle_stops_at_fifty_retrievals(installed: InstalledOracle) -> None:
    """Require a search-hungry model to answer after exactly fifty tool calls.

    Args:
        installed: Real oracle with a controlled model requesting further search.
    """
    installed.server.search_rounds = 100
    settings = json.loads((installed.app.root / "oracle-config.json").read_text())
    assert settings["max_search_rounds"] == settings["max_tool_calls"] == 50
    corpus = installed.app.write_json(
        "sample.json",
        [
            {
                "doc_id": "sample",
                "source_type": "document",
                "title": "Cedar",
                "content": "Ada owns Cedar.",
            }
        ],
    )
    installed.app.cli("ingest", "--path", str(corpus), "--refresh")
    result = installed.app.bounded_cli(
        "answer",
        stdin='[{"question_id":0,"question":"Who owns Cedar?"}]',
        max_retrieval_calls=50,
        timeout=60,
    )
    assert "Ada" in json.loads(result.stdout)[0]["answer"]
    assert len(installed.server.requests) == 51
    assert not installed.server.requests[-1].get("tools")
