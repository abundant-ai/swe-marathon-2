"""Check saved oracle answers against full sources and repair factual blind spots."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from task_paths import TASK_ROOT

sys.path.insert(0, str(TASK_ROOT / "tests"))

from verifier.config import load_answer_scoring_config
from verifier.contracts import HeldOutCase
from verifier.judging.answer_scoring import (
    AnswerInputs,
    finalize_answer_judgment,
    validate_answer_rating,
)
from verifier.judging.schemas import AnswerRating

from .codex_review import validate_final
from .codex_transport import CodexTransport
from .models import CaseInput, RubricDraft, SourceDocument


class OracleAudit(BaseModel):
    """Source-grounded rubric repair and independent expected criterion decisions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    revised: RubricDraft
    expected: AnswerRating
    audit_notes: list[str] = Field(
        description="Specific factual errors, valid alternatives, rubric blind spots repaired, or unresolved source ambiguities."
    )


def answer_inputs(case: CaseInput, draft: RubricDraft, answer: str) -> AnswerInputs:
    """Bind source-reviewed factual rules to the original saved candidate text.

    Args:
        case: Immutable question identity and source records.
        draft: Revised example and rule list from source review.
        answer: Saved oracle answer, never modified to satisfy the rubric.

    Returns:
        Production-compatible scoring input with one mandatory core criterion.
    """
    return AnswerInputs(
        HeldOutCase(
            case.question_id,
            case.question,
            draft.correct_answer,
            rubric=tuple(draft.rubric),
            required_rubric_indices=(0,),
        ),
        answer,
    )


async def run(args: argparse.Namespace) -> None:
    """Audit all saved answers after each corresponding source review is available.

    Args:
        args: Explicit private inputs, review checkpoints, output, and model settings.

    Raises:
        ValueError: Source/candidate coverage or persisted input hashes differ.
        RuntimeError: A constrained model call or structured repair cannot complete.
    """
    answer_scoring = load_answer_scoring_config(
        tomllib.loads((TASK_ROOT / "task.toml").read_text())["verifier"]["env"]
    )
    cases = [
        CaseInput.model_validate(row["case"])
        for row in json.loads(args.inputs.read_text())
    ]
    saved = {row["question_id"]: row for row in json.loads(args.answers.read_text())}
    docs = {row["doc_id"]: row for row in json.loads(args.corpus.read_text())}
    if set(saved) != {case.question_id for case in cases}:
        raise ValueError("Oracle and source question coverage differs")
    prompt = Path(__file__).with_name("oracle_audit.md").read_text()
    args.output.mkdir(parents=True, exist_ok=True)
    config = {
        "answer_scoring": asdict(answer_scoring),
        "model": args.model,
        "reasoning": args.reasoning,
        "inputs_sha256": hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
        "answers_sha256": hashlib.sha256(args.answers.read_bytes()).hexdigest(),
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "schema_sha256": hashlib.sha256(
            json.dumps(OracleAudit.model_json_schema(), sort_keys=True).encode()
        ).hexdigest(),
    }
    provenance = args.output / "provenance.json"
    if provenance.exists() and json.loads(provenance.read_text()) != config:
        raise ValueError("Oracle audit inputs changed; use a new output directory")
    provenance.write_text(json.dumps(config, indent=2))
    transport = CodexTransport(
        args.output / "calls",
        model=args.model,
        reasoning=args.reasoning,
        timeout=args.timeout,
        retries=args.retries,
    )
    semaphore = asyncio.Semaphore(args.concurrency)

    async def worker(index: int, original: CaseInput) -> dict[str, Any]:
        """Join the original sources and cited originals, then audit one saved answer.

        Args:
            index: Stable source position used by review checkpoint names.
            original: Original case with complete linked source records.

        Returns:
            Validated source audit and deterministic expected factual score.
        """
        review_path = args.reviews / f"review-{index:03d}.json"
        while not review_path.exists():
            await asyncio.sleep(5)
        review = json.loads(review_path.read_text())
        if review["question_id"] != original.question_id:
            raise ValueError("Review checkpoint identity mismatch")
        extras = {item["doc_id"] for item in saved[original.question_id]["citations"]}
        linked = {doc.doc_id: doc for doc in original.reference_documents}
        linked.update(
            {
                identity: SourceDocument.model_validate(docs[identity])
                for identity in extras
            }
        )
        case = original.model_copy(
            update={"reference_documents": list(linked.values())}
        )
        answer = saved[case.question_id]["answer"]
        target = args.output / f"audit-{index:03d}.json"

        def validate(result: OracleAudit) -> OracleAudit:
            """Check source grounding and exact candidate evidence before accepting labels.

            Args:
                result: Structured independent source audit.

            Returns:
                Unchanged audit after source and criterion validation.
            """
            validate_final(result.revised, case)
            validate_answer_rating(
                result.expected, answer_inputs(case, result.revised, answer)
            )
            return result

        if target.exists():
            record = json.loads(target.read_text())
            if record["review_call_id"] != review["call_id"]:
                raise ValueError("Source review changed after oracle audit")
            validate(OracleAudit.model_validate(record["audit"]))
            return record
        async with semaphore:
            payload = {
                "case": case.model_dump(),
                "reviewed_rubric": review["draft"],
                "oracle_answer": answer,
            }
            result, call_id = await transport.run(
                prompt,
                json.dumps(payload, ensure_ascii=False),
                OracleAudit,
                validate,
                f"audit-{index:03d}",
            )
            judgment = finalize_answer_judgment(
                result.expected,
                answer_inputs(case, result.revised, answer),
                call_id,
                answer_scoring,
            )
            record = {
                "question_id": case.question_id,
                "audit": result.model_dump(),
                "call_id": call_id,
                "review_call_id": review["call_id"],
                "expected_judgment": asdict(judgment),
                "rubric_changed": result.revised.rubric != review["draft"]["rubric"],
                "source_doc_ids": sorted(linked),
            }
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            print(
                f"Audited oracle {index + 1}/{len(cases)} {case.question_id}: {judgment.score:.2f}; rubric_changed={record['rubric_changed']}",
                flush=True,
            )
            return record

    tasks = [
        asyncio.create_task(worker(index, case)) for index, case in enumerate(cases)
    ]
    try:
        records = await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    (args.output / "audits.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "completed": len(records),
                "rubrics_changed": sum(row["rubric_changed"] for row in records),
            }
        ),
        flush=True,
    )


def main() -> None:
    """Parse explicit source-audit settings and run the author-only Codex workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "answers", "corpus", "reviews", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("model", "reasoning"):
        parser.add_argument(f"--{name}", required=True)
    for name in ("concurrency", "timeout", "retries"):
        parser.add_argument(f"--{name}", type=int, required=True)
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("Concurrency must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
