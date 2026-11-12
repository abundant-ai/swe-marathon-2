"""Deterministic CLI fixture used only for verifier validation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from main import generate, ingest


def main() -> None:
    """Parse fixture commands and exercise the submitted public functions.

    Ingestion failures propagate to the process status. Answers are emitted as
    JSONL on stdout or a JSON array in the requested file.
    """
    parser = argparse.ArgumentParser(description="orange ingest and answer")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("help")
    ingest_parser = subs.add_parser("ingest")
    ingest_parser.add_argument("--path", required=True)
    ingest_parser.add_argument("--refresh", action="store_true")
    answer_parser = subs.add_parser("answer")
    answer_parser.add_argument("--questions", nargs="+")
    answer_parser.add_argument("--output")
    args = parser.parse_args()
    if args.command == "help":
        parser.print_help()
    elif args.command == "ingest":
        asyncio.run(ingest({"corpus_path": args.path, "refresh": args.refresh}))
    else:
        if args.questions:
            questions = [json.loads(line) for filename in args.questions for line in Path(filename).read_text().splitlines()]
        else:
            questions = [{"question_id": f"stdin-{index}", "question": line.strip()} for index, line in enumerate(sys.stdin, 1)]
        answers = [{"question_id": row["question_id"], **asyncio.run(generate(row["question"]))} for row in questions]
        if args.output:
            Path(args.output).write_text(json.dumps(answers))
        else:
            for answer in answers:
                print(json.dumps(answer))


if __name__ == "__main__":
    main()
