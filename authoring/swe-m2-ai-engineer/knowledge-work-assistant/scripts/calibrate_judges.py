"""Run private answer variants through the production judge flow on Modal."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import modal

app = modal.App("orange-judge-calibration")


def run_calibration(fixtures: dict[str, Any], repeats: int) -> dict[str, Any]:
    """Execute live judgments on Modal with a fresh controlled replay workspace.

    Args:
        fixtures: Private questions, original sources, and pre-labeled answer variants.
        repeats: Independent repetitions of each variant; no judge result caching.

    Returns:
        Judgments, actual call sequence, policy, prompt hashes, and any run error.
        This measures judge behavior, not retrieval or candidate implementation quality.
    """
    import hashlib
    import time
    from contextvars import ContextVar
    import os
    import sys
    import tempfile
    import tomllib
    from dataclasses import asdict
    from datetime import datetime, timezone

    sys.path.insert(0, "/opt/calibration")
    from verifier.application.client import ApplicationClient
    from verifier.checks.test_accuracy import test_holdout_accuracy
    from verifier.config import load_generation_config, load_scoring_config
    from verifier.contracts import AnswerJudgment, HeldOutCase, Judgment, SourceDocument, VerificationContext
    from verifier.judging.client import (
        ANSWER_PROMPT_SHA256, ANSWER_SCHEMA_SHA256, CITATION_PROMPT_SHA256,
        CITATION_SCHEMA_SHA256, HerbJudge, JUDGE_MODEL, JUDGE_REASONING,
    )

    os.environ["ORANGE_JUDGE_API_KEY"] = os.environ["OPENAI_API_KEY"]
    calls: list[dict[str, Any]] = []
    active_case: ContextVar[str] = ContextVar("calibration_case")
    concurrency = {"active": 0, "peak": 0}

    class ObservedJudge(HerbJudge):
        """Record real provider calls while retaining production judgment behavior."""

        async def grade_async(self, case: HeldOutCase, answer: str) -> AnswerJudgment:
            """Judge an answer and record its band and trace ID.

            Args:
                case: Private reference and complete source records.
                answer: Controlled answer variant.

            Returns:
                Unmodified production judgment.
            """
            active_case.set(case.question_id)
            started = time.monotonic()
            concurrency["active"] += 1
            concurrency["peak"] = max(concurrency["peak"], concurrency["active"])
            try:
                result = await super().grade_async(case, answer)
            finally:
                concurrency["active"] -= 1
            calls.append({"kind": "answer", "case_id": case.question_id, "started": started, "finished": time.monotonic(), **asdict(result)})
            print(f"ANSWER {case.question_id}: {result.score}", flush=True)
            if result.score < 100:
                print(result.reason, flush=True)
            return result

        async def grade_citations_async(self, question: str, answer: str, citations: list[dict[str, str]],
                            documents: list[SourceDocument]) -> Judgment:
            """Record a citation call only when the production verifier invokes it.

            Args:
                question: Original private question.
                answer: Variant that has met answer eligibility.
                citations: Exact quotations from the replay CLI.
                documents: Full authoritative cited records.

            Returns:
                Unmodified production citation judgment.
            """
            case_id = active_case.get()
            started = time.monotonic()
            concurrency["active"] += 1
            concurrency["peak"] = max(concurrency["peak"], concurrency["active"])
            try:
                result = await super().grade_citations_async(question, answer, citations, documents)
            finally:
                concurrency["active"] -= 1
            calls.append({"kind": "citation", "case_id": case_id, "started": started, "finished": time.monotonic(), **asdict(result)})
            print(f"CITATION {case_id}: {result.score}", flush=True)
            if result.score < 100:
                print(result.reason, flush=True)
            return result

    settings = tomllib.loads(Path("/opt/calibration/task.toml").read_text())["verifier"]["env"]
    os.environ["ORANGE_JUDGE_OUTPUT_RETRIES"] = settings["ORANGE_JUDGE_OUTPUT_RETRIES"]
    policy = load_scoring_config(settings)
    cases: list[HeldOutCase] = []
    answers: list[dict[str, Any]] = []
    labels: dict[str, dict[str, Any]] = {}
    corpus = {doc["doc_id"]: doc for entry in fixtures["cases"]
              for doc in [*entry["documents"], *entry.get("citation_documents", [])]}
    for repeat in range(repeats):
        for entry in fixtures["cases"]:
            for variant in entry["variants"]:
                identity = f"{entry['question_id']}/{variant['name']}/repeat-{repeat + 1}"
                cases.append(HeldOutCase(identity, entry["question"], entry["reference"], tuple(entry["documents"])))
                answers.append({"question_id": len(answers), "question": entry["question"],
                                "answer": variant["answer"], "citations": variant["citations"]})
                labels[identity] = {"source_question_id": entry["question_id"], "repeat": repeat + 1,
                                    **{key: value for key, value in variant.items() if key not in ("answer", "citations")}}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        workspace = root / "app"
        workspace.mkdir()
        output = root / "results"
        output.mkdir()
        corpus_path = root / "corpus.json"
        corpus_path.write_text(json.dumps(list(corpus.values())))
        (workspace / "answers.json").write_text(json.dumps(answers))
        # A deterministic CLI transports labeled variants through the real accuracy
        # check. It deliberately makes no claim to implement a retrieval system.
        launcher = workspace / "orange"
        launcher.write_text(f"#!{sys.executable}\n" + '''import json, pathlib, sys
args = sys.argv[1:]
if args[0] == "ingest":
    assert "--refresh" in args
    json.loads(pathlib.Path(args[args.index("--path") + 1]).read_text())
elif args[0] == "answer":
    ids = {row["question_id"] for row in json.loads(pathlib.Path(args[args.index("--questions") + 1]).read_text())}
    answers = [row for row in json.loads(pathlib.Path("answers.json").read_text()) if row["question_id"] in ids]
    pathlib.Path(args[args.index("--output") + 1]).write_text(json.dumps(answers))
else:
    raise SystemExit(2)
''')
        launcher.chmod(0o755)
        context = VerificationContext(ApplicationClient(workspace), corpus_path, tuple(cases),
                                      ObservedJudge(), output, policy, load_generation_config(settings))
        error = None
        try:
            test_holdout_accuracy(context)
        except Exception as exc:
            error = type(exc).__name__
            cause = exc.__cause__
            if cause is not None:
                error += f": {type(cause).__name__} status={getattr(cause, 'status_code', None)}"
        path = output / "judgments.json"
        judgments = json.loads(path.read_text()) if path.exists() else []
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "model": JUDGE_MODEL,
                "reasoning": JUDGE_REASONING, "policy": asdict(policy), "repeats": repeats,
                "peak_concurrent_requests": concurrency["peak"], "expected_rows": len(cases), "labels": labels, "calls": calls, "judgments": judgments,
                "error": error, "fixture_sha256": hashlib.sha256(json.dumps(fixtures, sort_keys=True).encode()).hexdigest(),
                "hashes": {"answer_prompt": ANSWER_PROMPT_SHA256, "answer_schema": ANSWER_SCHEMA_SHA256,
                           "citation_prompt": CITATION_PROMPT_SHA256, "citation_schema": CITATION_SCHEMA_SHA256}}


def main() -> None:
    """Parse explicit run settings and save the private calibration evidence.

    Raises:
        SystemExit: Invalid arguments or an incomplete remote evaluation.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--credential-source", choices=("modal-secret", "project-env"), required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    task = repo / "tasks/swe-m2-ai-engineer/knowledge-work-assistant"
    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install("pydantic==2.14.3", "pydantic-ai-slim[openai]==2.68.0", "openai==3.49.0")
        .add_local_dir(task / "steps/01-build-rag/tests/verifier", "/opt/calibration/verifier")
        .add_local_file(task / "task.toml", "/opt/calibration/task.toml")
    )
    if args.repeats < 1:
        parser.error("repeats must be positive")
    if args.credential_source == "project-env":
        from dotenv import dotenv_values

        key = dotenv_values(repo / ".env").get("OPENAI_API_KEY")
        if not key:
            parser.error("Project .env has no OPENAI_API_KEY")
        secret = modal.Secret.from_dict({"OPENAI_API_KEY": key})
    else:
        secret = modal.Secret.from_name("openai-keys", environment_name="")
    remote = app.function(image=image, secrets=[secret],
                          timeout=args.timeout)(run_calibration)
    fixtures = json.loads(args.fixtures.read_text())
    results: list[dict[str, Any]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with modal.enable_output(), app.run(environment_name=args.environment):
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(remote.remote, {**fixtures, "cases": [entry]}, args.repeats)
                       for entry in fixtures["cases"]]
            for future in as_completed(futures):
                results.append(future.result())
                args.output.write_text(json.dumps({"groups": results}, indent=2) + "\n")
    if len(results) != len(fixtures["cases"]):
        raise SystemExit("Calibration interrupted before all groups completed")
    print(json.dumps({"completed": sum(len(result["judgments"]) for result in results),
                      "errors": [result["error"] for result in results if result["error"]], "output": str(args.output)}))
    if any(result["error"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
