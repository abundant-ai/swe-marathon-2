"""Requirement checks run by the explicit registry in verify.py, not pytest."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict
from typing import Any, Mapping, Sequence

from contracts import CandidateFailure, CheckResult, VerificationContext

__test__ = False
ACCURACY_TARGET = 80.0


def require(condition: bool, message: str) -> None:
    """Raise a candidate failure for an unmet public requirement.

    Args:
        condition: Requirement-specific observation.
        message: Explanation retained in the verification report.
    """
    if not condition:
        raise CandidateFailure(message)


def passed(name: str, explanation: str, **metrics: float) -> CheckResult:
    """Build a successful requirement result.

    Args:
        name: Registry requirement identifier.
        explanation: Observed behavior.
        metrics: Numeric evidence to aggregate into the run report.

    Returns:
        An immutable check record.
    """
    return CheckResult(name, "passed", explanation, metrics)


def fixture_document(label: str = "launch") -> dict[str, str]:
    """Generate a fresh public fact so checks do not rely on memorized answers.

    Args:
        label: Subject used in the document title.

    Returns:
        A complete corpus record with unpredictable identifiers and content.
    """
    token = uuid.uuid4().hex
    return {"doc_id": f"doc-{token}", "source_type": "document", "title": f"{label} {token}", "content": f"The {label} authorization code is {uuid.uuid4().hex}."}


def check_passages(value: object, corpus: Mapping[str, Mapping[str, str]]) -> list[dict[str, str]]:
    """Validate passage shape, document identity, and literal quotation.

    Args:
        value: Candidate passages or citations.
        corpus: Authoritative input records, not the candidate's index.

    Returns:
        Validated passage records; an empty list remains allowed.

    Raises:
        CandidateFailure: A record is malformed or cites nonexistent evidence.
    """
    require(isinstance(value, list), "Passages/citations must be a list")
    for passage in value:
        require(isinstance(passage, dict), "Each passage must be an object")
        doc_id, quote = passage.get("doc_id"), passage.get("quote")
        require(isinstance(doc_id, str) and doc_id in corpus, "Unknown citation doc_id")
        require(isinstance(quote, str) and bool(quote.strip()), "A citation needs a nonempty quote")
        document = corpus[doc_id]
        require(quote in document["content"] or quote in document["title"], "Quote is not an exact passage in the cited document")
    return value


def retrieve_document(context: VerificationContext, document: dict[str, str], corpus: Sequence[dict[str, str]]) -> None:
    """Check retrieval in a fresh process against a known, query-specific fact.

    Args:
        context: Application execution boundary.
        document: Expected record in the current index.
        corpus: Records allowed to be cited.

    Raises:
        CandidateFailure: The target cannot be retrieved with supporting content.
    """
    result = context.app.probe("retrieve", f"What is the authorization code for {document['title']}?")["value"]
    require(isinstance(result, dict) and "passages" in result, "retrieve must return passages")
    passages = check_passages(result["passages"], {doc["doc_id"]: doc for doc in corpus})
    require(any(item["doc_id"] == document["doc_id"] and item["quote"] in document["content"] for item in passages), "retrieve omitted the requested document's content")


def answer_records(raw: object, question_ids: Sequence[str], corpus: Sequence[dict[str, str]], *, allow_missing: bool = False) -> dict[str, dict[str, Any]]:
    """Validate CLI answer records and their correspondence to question IDs.

    Args:
        raw: Parsed answer array or collected JSONL rows.
        question_ids: Expected identities in the input batch.
        corpus: Authoritative documents for citation checks.
        allow_missing: Leave absent answers for the quality check to score zero.

    Returns:
        Answers keyed by their unique question IDs.

    Raises:
        CandidateFailure: Invalid schema, duplicate/extra IDs, or bad citations.
    """
    require(isinstance(raw, list), "Answer output must be a JSON array or JSONL records")
    answers: dict[str, dict[str, Any]] = {}
    documents = {document["doc_id"]: document for document in corpus}
    for record in raw:
        require(isinstance(record, dict), "Answer records must be objects")
        key = record.get("question_id")
        require(isinstance(key, str) and key in question_ids, "Unexpected question_id")
        require(key not in answers, "Duplicate question_id")
        require(isinstance(record.get("answer"), str), "answer must be a string")
        check_passages(record.get("citations"), documents)
        answers[key] = record
    if not allow_missing:
        require(set(answers) == set(question_ids), "Expected one answer per question")
    return answers


def test_interfaces(context: VerificationContext) -> CheckResult:
    """Check exported async functions and the declared TypedDict contracts.

    Args:
        context: Submitted workspace and subprocess adapter.

    Returns:
        Evidence that all three public interfaces have the requested types.
    """
    context.app.probe("interfaces")
    return passed("interfaces", "Three async functions and their typed inputs/outputs are exported")


def test_cli_help(context: VerificationContext) -> CheckResult:
    """Check the executable exposes useful help for the public commands.

    Args:
        context: Submitted workspace and subprocess adapter.

    Returns:
        Help command outcome.
    """
    result = context.app.cli("help")
    require(all(word in result.stdout.lower() for word in ("ingest", "answer")), "Help must describe ingest and answer")
    return passed("cli_help", "orange help describes ingestion and answering")


def test_answer_before_ingestion(context: VerificationContext) -> CheckResult:
    """Check answering fails when the persisted index is absent.

    Args:
        context: Fresh verifier copy; transferred index state is removed.

    Returns:
        Observed failure before ingestion.
    """
    context.app.clear_state()
    result = context.app.cli("answer", stdin="Who owns the launch?\n", require_success=False)
    require(result.code != 0, "Answering without an index must fail")
    return passed("answer_before_ingestion", "No-index answering exits unsuccessfully")


def test_ingestion_and_persistence(context: VerificationContext) -> CheckResult:
    """Ingest through the async API and retrieve after restarting Python.

    Args:
        context: Application with a fresh generated corpus.

    Returns:
        Persistence and ingest return-value evidence.
    """
    document = fixture_document()
    path = context.app.write_jsonl("persistence.jsonl", [document])
    result = context.app.probe("ingest", {"corpus_path": str(path), "refresh": True})
    require(result["value"] is None, "ingest must return None")
    require((context.app.root / "state").is_dir(), "Persist the index under /app/state")
    retrieve_document(context, document, [document])
    return passed("ingestion_and_persistence", "API ingestion persists evidence across processes")


def test_duplicate_documents(context: VerificationContext) -> CheckResult:
    """Check append ingestion skips an existing ID while adding a new document.

    Args:
        context: Application and generated conflicting document versions.

    Returns:
        Evidence that original content survives and the new ID is searchable.
    """
    original, new = fixture_document(), fixture_document("handover")
    first = context.app.write_jsonl("duplicate-first.jsonl", [original])
    context.app.cli("ingest", "--path", str(first), "--refresh")
    changed = {**original, "content": "This replacement must be skipped without refresh."}
    second = context.app.write_jsonl("duplicate-next.jsonl", [changed, new])
    context.app.cli("ingest", "--path", str(second))
    retrieve_document(context, original, [original, new])
    retrieve_document(context, new, [original, new])
    return passed("duplicate_documents", "Existing IDs are preserved; new IDs become retrievable")


def test_refresh_replaces_index(context: VerificationContext) -> CheckResult:
    """Check refresh updates an existing ID and removes records absent from input.

    Args:
        context: Application and two successive generated corpora.

    Returns:
        Evidence for replacement and removal through retrieval.
    """
    original, removed = fixture_document(), fixture_document("retired")
    first = context.app.write_jsonl("refresh-first.jsonl", [original, removed])
    context.app.cli("ingest", "--path", str(first), "--refresh")
    updated = {**original, "content": f"The new authorization code is {uuid.uuid4().hex}."}
    second = context.app.write_jsonl("refresh-next.jsonl", [updated])
    context.app.cli("ingest", "--path", str(second), "--refresh")
    retrieve_document(context, updated, [updated])
    result = context.app.probe("retrieve", removed["title"])["value"]
    require(isinstance(result, dict), "retrieve must return an object")
    check_passages(result.get("passages"), {updated["doc_id"]: updated})
    return passed("refresh_replaces_index", "Refresh replaces changed content and removes stale IDs")


def test_required_call_paths(context: VerificationContext) -> CheckResult:
    """Observe CLI-to-ingest, CLI-to-generate, and generate-to-retrieve calls.

    Args:
        context: Application and a small answerable corpus.

    Returns:
        Call observations plus validation of the typed generate result.
    """
    document = fixture_document()
    corpus = context.app.write_jsonl("calls-corpus.jsonl", [document])
    observation = context.app.probe("cli", ["ingest", "--path", str(corpus), "--refresh"])
    require(observation["exit_code"] == 0 and "ingest" in observation["calls"], "CLI ingest must call the exported ingest function")
    query = f"What is the authorization code for {document['title']}?"
    observation = context.app.probe("generate", query)
    require("retrieve" in observation["calls"], "generate must call retrieve")
    require(isinstance(observation["value"], dict), "generate must return a typed answer object")
    answer_records([{"question_id": "direct", **observation["value"]}], ["direct"], [document])
    questions = context.app.write_jsonl("calls-questions.jsonl", [{"question_id": "call", "question": query}])
    observation = context.app.probe("cli", ["answer", "--questions", str(questions)])
    require(observation["exit_code"] == 0 and {"generate", "retrieve"} <= set(observation["calls"]), "CLI answer must call generate, which calls retrieve")
    return passed("required_call_paths", "Required function calls observed through the Python CLI and API")


def test_cli_question_files(context: VerificationContext) -> CheckResult:
    """Check multiple question files and JSON-array output with valid citations.

    Args:
        context: Application and generated input/output paths.

    Returns:
        Evidence of one answer per question across both files.
    """
    document = fixture_document()
    corpus = context.app.write_jsonl("files-corpus.jsonl", [document])
    context.app.cli("ingest", "--path", str(corpus), "--refresh")
    paths = [context.app.write_jsonl(f"questions-{index}.jsonl", [{"question_id": f"q{index}", "question": document["title"]}]) for index in range(2)]
    output = context.app.inputs / "file-answers.json"
    context.app.cli("answer", "--questions", *(str(path) for path in paths), "--output", str(output))
    answer_records(context.app.read_json(output), ["q0", "q1"], [document])
    return passed("cli_question_files", "Multiple JSONL inputs produce one JSON array with valid citations")


def test_cli_stdin(context: VerificationContext) -> CheckResult:
    """Check stdin question IDs, EOF handling, and terminal JSONL output.

    Args:
        context: Application and a known input document.

    Returns:
        Evidence that both typed questions produce distinct answer records.
    """
    document = fixture_document()
    corpus = context.app.write_jsonl("stdin-corpus.jsonl", [document])
    context.app.cli("ingest", "--path", str(corpus), "--refresh")
    output = context.app.cli("answer", stdin=f"{document['title']}\n{document['title']}\n")
    try:
        rows = [json.loads(line) for line in output.stdout.splitlines() if line.strip()]
    except ValueError as exc:
        raise CandidateFailure("Terminal answer output must be JSONL") from exc
    answer_records(rows, ["stdin-1", "stdin-2"], [document])
    return passed("cli_stdin", "stdin questions receive sequential IDs and terminal JSONL answers")


def test_self_generated_evaluation(context: VerificationContext) -> CheckResult:
    """Validate the candidate's development corpus, Q&A, outputs, and report.

    Args:
        context: Submitted development artifacts, kept separate from final data.

    Returns:
        Structural evidence of a reproducible self-evaluation dataset. This check
        cannot prove who authored the questions or when the interfaces were written.
    """
    root = context.app.root / "dev"
    corpus = context.app.read_data(root / "corpus.jsonl", jsonl=True)
    questions = context.app.read_data(root / "questions.jsonl", jsonl=True)
    require(bool(corpus) and bool(questions), "Generate development documents and questions")
    for row in corpus:
        require(isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key].strip() for key in ("doc_id", "source_type", "title", "content")), "Invalid development corpus record")
    require(len({row["doc_id"] for row in corpus}) == len(corpus), "Development document IDs must be unique")
    for row in questions:
        require(isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key].strip() for key in ("question_id", "question", "reference_answer")), "Generated questions need IDs, questions, and reference answers")
    ids = [row["question_id"] for row in questions]
    require(len(set(ids)) == len(ids), "Development question IDs must be unique")
    answer_records(context.app.read_json(root / "answers.json"), ids, corpus)
    report = context.app.read_json(root / "report.json")
    require(isinstance(report, dict) and bool(report), "Provide a JSON report of evaluation method and findings")
    return passed("self_generated_evaluation", "Development corpus, reference Q&A, answers, and report are present", development_questions=float(len(questions)))


def test_holdout_accuracy(context: VerificationContext) -> CheckResult:
    """Evaluate all held-out content questions using HERB's single-score mean.

    Args:
        context: Sanitized corpus, private references, and fixed semantic judge.

    Returns:
        Threshold result with a score over every case, including missing answers
        as zero. Per-question judgments are saved only to trusted diagnostics.

    Raises:
        CandidateFailure: Invalid CLI output, citations, or application failure.
        EvaluationError: A judge request failed; this invalidates the run.
    """
    app = context.app
    public_corpus = app.inputs / "evaluation-corpus.jsonl"
    shutil.copyfile(context.corpus_path, public_corpus)
    corpus = [json.loads(line) for line in context.corpus_path.read_text().splitlines()]
    questions = app.write_jsonl("evaluation-questions.jsonl", [
        {"question_id": case.question_id, "question": case.question} for case in context.cases
    ])
    app.cli("ingest", "--path", str(public_corpus), "--refresh", timeout=2700)
    output = app.inputs / "evaluation-answers.json"
    app.cli("answer", "--questions", str(questions), "--output", str(output), timeout=5400)
    answers = answer_records(app.read_json(output), [case.question_id for case in context.cases], corpus, allow_missing=True)
    scores: list[int] = []
    missing = 0
    # Write each judgment before the next request so an outage retains evidence.
    with (context.output_dir / "judgments.jsonl").open("w") as stream:
        for case in context.cases:
            answer = answers.get(case.question_id, {}).get("answer", "")
            if not answer.strip():
                score = 0
                missing += 1
                record = {"score": 0, "reason": "Missing or empty answer", "response_id": ""}
            else:
                judgment = context.judge.grade(case, answer)
                score, record = judgment.score, asdict(judgment)
            scores.append(score)
            stream.write(json.dumps({"question_id": case.question_id, "answer": answer, **record}) + "\n")
            stream.flush()
    mean = sum(scores) / len(context.cases)
    status = "passed" if mean >= ACCURACY_TARGET and missing == 0 else "failed"
    return CheckResult("holdout_accuracy", status, f"Mean answer rating {mean:.2f}%; {missing} missing/empty answers", {"accuracy_percent": mean, "holdout_questions": float(len(scores)), "missing_answers": float(missing)})
