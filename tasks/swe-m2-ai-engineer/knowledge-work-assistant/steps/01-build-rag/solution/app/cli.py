"""JSON command-line adapter for the public Orange functions."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter

import main as application
from orange_core import telemetry


class Question(BaseModel):
    """One public batch question; IDs need not be contiguous."""

    question_id: int = Field(ge=0, strict=True)
    question: str = Field(min_length=1, strict=True)


def read_questions(paths: list[Path] | None) -> list[Question]:
    """Load JSON arrays from files or stdin and reject duplicate IDs.

    Args:
        paths: Input files in requested order, or None for stdin until EOF.

    Returns:
        Validated questions preserving input order and original question text.

    Raises:
        ValueError: JSON, records, or cross-file IDs violate the input contract.
    """
    adapter = TypeAdapter(list[Question])
    payloads = [path.read_text() for path in paths] if paths else [sys.stdin.read()]
    questions = [question for payload in payloads for question in adapter.validate_json(payload)]
    if len({row.question_id for row in questions}) != len(questions):
        raise ValueError("question_id must be unique across the input batch")
    return questions


async def answer_questions(questions: list[Question], concurrency: int = 1,
                           output: Path | None = None, keep_going: bool = False) -> list[dict[str, object]]:
    """Call the public generator for each question and preserve its identity.

    Separate CLI processes remain supported. Author runs can instead share one
    process and index, avoiding a copy of a large vector index in every worker.

    Args:
        questions: Validated batch with unique IDs.
        concurrency: Maximum simultaneously active question pipelines.
        output: Optional final-answer checkpoint, replaced after each completion.
        keep_going: Record an empty answer on individual errors instead of aborting.

    Returns:
        JSON-ready answer records in input order, with original question strings.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    semaphore = asyncio.Semaphore(concurrency)
    records: dict[int, dict[str, object]] = {}

    async def answer_one(index: int, question: Question) -> None:
        """Generate one isolated answer and atomically checkpoint final records.

        Args:
            index: Stable input position for deterministic output order.
            question: Public question, without reference evidence or answers.
        """
        async with semaphore:
            try:
                with telemetry.span("enterprise_rag_testing.question", question_id=question.question_id,
                                    question=question.question):
                    answer = await application.generate(question.question)
                    result = answer.model_dump(mode="json")
                    with telemetry.span("agent.final_answer", **result):
                        pass
            except Exception as error:
                if not keep_going:
                    raise
                result = {"answer": "", "citations": []}
                print(f"Question {question.question_id} failed: {type(error).__name__}", file=sys.stderr, flush=True)
            records[index] = {**question.model_dump(mode="json"), **result}
            if output:
                temporary = output.with_suffix(".tmp")
                temporary.write_text(json.dumps([records[key] for key in sorted(records)], ensure_ascii=False) + "\n")
                temporary.replace(output)
            print(f"Answered {len(records)}/{len(questions)} questions", file=sys.stderr, flush=True)

    tasks = [asyncio.create_task(answer_one(index, question)) for index, question in enumerate(questions)]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return [records[index] for index in range(len(questions))]


def main() -> None:
    """Dispatch the CLI without emitting diagnostic text into answer JSON.

    Reads process arguments and, for stdin batches, until EOF. Errors are written
    to stderr and produce a nonzero exit; output files are replaced only after
    the complete batch has been generated.
    """
    parser = argparse.ArgumentParser(description="Orange knowledge assistant")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("help", help="Describe ingest and answer commands")
    ingestion = commands.add_parser("ingest", help="Ingest company records")
    ingestion.add_argument("--path", type=Path, required=True)
    ingestion.add_argument("--refresh", action="store_true")
    answering = commands.add_parser("answer", help="Answer JSON questions")
    answering.add_argument("--questions", type=Path, nargs="+")
    answering.add_argument("--output", type=Path)
    answering.add_argument("--concurrency", type=int, default=int(os.environ.get("ORANGE_ANSWER_CONCURRENCY", "1")))
    answering.add_argument("--keep-going", action="store_true")
    args = parser.parse_args()
    if args.command == "help":
        parser.print_help()
        return
    try:
        telemetry.configure()
        if args.command == "ingest":
            asyncio.run(application.ingest(application.IngestEvent(corpus_path=str(args.path), refresh=args.refresh)))
            return
        result = asyncio.run(answer_questions(read_questions(args.questions), args.concurrency, args.output, args.keep_going))
        serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(serialized, encoding="utf-8")
        else:
            sys.stdout.write(serialized)
    except Exception as error:
        print(f"orange: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    finally:
        telemetry.flush()


if __name__ == "__main__":
    main()
