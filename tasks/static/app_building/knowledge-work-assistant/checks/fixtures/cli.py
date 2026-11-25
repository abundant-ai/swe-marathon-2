"""Deterministic CLI fixture used only for verifier validation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from main import IngestEvent, generate, ingest


def main() -> None:
    """Parse fixture commands and exercise the submitted public functions.

    Ingestion failures propagate to the process status. Answers are emitted as
    a JSON array on stdout or in the requested file.
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
        asyncio.run(ingest(IngestEvent(corpus_path=args.path, refresh=args.refresh)))
    else:
        if args.questions:
            questions = [
                row
                for filename in args.questions
                for row in json.loads(Path(filename).read_text())
            ]
        else:
            questions = json.load(sys.stdin)
        answers = [
            {
                "question_id": row["question_id"],
                "question": row["question"],
                **asyncio.run(generate(row["question"])).model_dump(mode="json"),
            }
            for row in questions
        ]
        if args.output:
            Path(args.output).write_text(json.dumps(answers))
        else:
            print(json.dumps(answers))


if __name__ == "__main__":
    main()
