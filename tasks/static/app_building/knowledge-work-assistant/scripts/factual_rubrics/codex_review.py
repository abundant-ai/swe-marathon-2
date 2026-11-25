"""Review every private rubric using the explicitly authorized temporary judge."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .codex_transport import CodexTransport
from .models import CaseInput, RubricDraft, validate_grounding


def validate_final(draft: RubricDraft, case: CaseInput) -> RubricDraft:
    """Validate exact source anchors and a substantive first criterion.

    Args:
        draft: Model-reviewed rules and corrected example.
        case: Immutable question and complete original sources.

    Returns:
        The validated draft; semantic quality is subsequently calibrated.

    Raises:
        ValueError: Grounding is invalid or the first point is conditional/vacuous.
    """
    validate_grounding(draft, case)
    first = re.sub(r'"[^"\n]*"', "QUOTE", draft.rubric[0]).lower()
    if first.startswith(("must not ", "must avoid ")) or re.search(
        r"\b(?:if|when)\b", first
    ):
        raise ValueError(
            "First criterion must require substantive answer content unconditionally"
        )
    return draft


async def run(args: argparse.Namespace) -> None:
    """Review all cases concurrently, checkpointing each completed source audit.

    Args:
        args: Explicit source, proposal, output, model, retry, and concurrency settings.

    Raises:
        ValueError: Input identity or resume provenance differs.
        RuntimeError: A review cannot complete; completed checkpoints remain.
    """
    originals = [
        CaseInput.model_validate(row["case"])
        for row in json.loads(args.inputs.read_text())
    ]
    proposals = json.loads(args.rubrics.read_text())
    by_id = {row["question_id"]: row for row in proposals}
    if len(by_id) != len(proposals) or set(by_id) != {
        case.question_id for case in originals
    }:
        raise ValueError("Question coverage mismatch")
    prompt = Path(__file__).with_name("final_review.md").read_text()
    args.output.mkdir(parents=True, exist_ok=True)
    config = {
        "model": args.model,
        "reasoning": args.reasoning,
        "inputs_sha256": hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
        "rubrics_sha256": hashlib.sha256(args.rubrics.read_bytes()).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "schema_sha256": hashlib.sha256(
            json.dumps(RubricDraft.model_json_schema(), sort_keys=True).encode()
        ).hexdigest(),
    }
    provenance = args.output / "provenance.json"
    if provenance.exists() and json.loads(provenance.read_text()) != config:
        raise ValueError("Review inputs changed; use a new output directory")
    provenance.write_text(json.dumps(config, indent=2))
    transport = CodexTransport(
        args.output / "calls",
        model=args.model,
        reasoning=args.reasoning,
        timeout=args.timeout,
        retries=args.retries,
    )
    semaphore = asyncio.Semaphore(args.concurrency)

    async def worker(index: int, case: CaseInput) -> dict[str, Any]:
        """Review one full source set or reuse its authenticated checkpoint.

        Args:
            index: Stable source-order position.
            case: Question and original records; no oracle answers are supplied.

        Returns:
            Final reviewed rubric record with original association and provenance.
        """
        target = args.output / f"review-{index:03d}.json"
        if target.exists():
            record = json.loads(target.read_text())
            validate_final(RubricDraft.model_validate(record["draft"]), case)
            return record

        def validate(draft: RubricDraft) -> RubricDraft:
            """Bind this request's original sources to structured-output validation.

            Args:
                draft: Model output awaiting exact-quote checks.

            Returns:
                The source-validated draft.
            """
            return validate_final(draft, case)

        async with semaphore:
            draft, call_id = await transport.run(
                prompt,
                json.dumps(
                    {"case": case.model_dump(), "proposal": by_id[case.question_id]},
                    ensure_ascii=False,
                ),
                RubricDraft,
                validate,
                f"review-{index:03d}",
            )
            record = {
                "question_id": case.question_id,
                "draft": draft.model_dump(),
                "call_id": call_id,
                "changed": draft.rubric != by_id[case.question_id]["rubric"],
            }
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            print(
                f"Reviewed {index + 1}/{len(originals)} {case.question_id}; changed={record['changed']}",
                flush=True,
            )
            return record

    tasks = [
        asyncio.create_task(worker(index, case)) for index, case in enumerate(originals)
    ]
    try:
        records = await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    final = []
    for case, record in zip(originals, records, strict=True):
        draft = record["draft"]
        final.append(
            {
                **by_id[case.question_id],
                "rubric": draft["rubric"],
                "reviewed_reference": draft["correct_answer"],
                "required_indices": [0],
                "guard_indices": list(range(1, len(draft["rubric"]))),
                "grounding": draft["grounding"],
                "reference_status": draft["reference_status"],
                "reference_notes": draft["reference_notes"],
                "review_notes": draft["review_notes"],
                "review_method": "codex_gpt6_astra_high_full_source_review",
                "review_call_id": record["call_id"],
            }
        )
    (args.output / "rubrics.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "completed": len(final),
                "changed": sum(record["changed"] for record in records),
            }
        ),
        flush=True,
    )


def main() -> None:
    """Parse explicit temporary-review settings and start resumable source review."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "rubrics", "output"):
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
