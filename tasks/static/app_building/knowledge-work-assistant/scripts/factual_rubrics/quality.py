"""Audit all active rubrics and save proposed repairs without changing evaluation."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from .build import digest, load_cases, write_json
from .quality_models import QualityInput, RubricQualityAudit, validate_quality_audit


def make_agent(
    client: AsyncOpenAI, args: argparse.Namespace, prompt: Path
) -> Agent[QualityInput, RubricQualityAudit]:
    """Create a source-aware reviewer with native structured output and retries.

    Args:
        client: Caller-owned provider connection using the approved project key.
        args: Explicit model, reasoning, token budget, and validation retry policy.
        prompt: Author-only audit or independent-review prompt.

    Returns:
        A typed agent that validates rule coverage and literal source grounding.
    """
    model = OpenAIResponsesModel(
        args.model, provider=OpenAIProvider(openai_client=client)
    )
    agent: Agent[QualityInput, RubricQualityAudit] = Agent(
        model,
        deps_type=QualityInput,
        output_type=NativeOutput(RubricQualityAudit, strict=True),
        system_prompt="You audit factual assessment rubrics against original evidence.",
        instructions=prompt.read_text(),
        retries=args.output_retries,
        model_settings=OpenAIResponsesModelSettings(
            openai_reasoning_effort=args.reasoning,
            openai_store=False,
            max_tokens=args.max_tokens,
        ),
    )

    @agent.output_validator
    def validate_output(
        context: RunContext[QualityInput], output: RubricQualityAudit
    ) -> RubricQualityAudit:
        """Request a bounded repair for malformed coverage or invented quotations.

        Args:
            context: Immutable question, original rubric, and source documents.
            output: Model's proposed structured quality assessment.

        Returns:
            The validated model output, without altering its semantic judgments.

        Raises:
            ModelRetry: Structural or literal-source validation fails.
        """
        try:
            return validate_quality_audit(output, context.deps)
        except ValueError as error:
            raise ModelRetry(str(error)) from error

    return agent


async def review_one(
    index: int,
    original: QualityInput,
    auditor: Agent[QualityInput, RubricQualityAudit],
    reviewer: Agent[QualityInput, RubricQualityAudit],
    output: Path,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Audit and independently review one question, checkpointing both passes.

    Args:
        index: Stable active-dataset position for checkpoint files.
        original: Active rubric and complete trusted source association.
        auditor: First-pass quality reviewer.
        reviewer: Independent fresh-context second-pass reviewer.
        output: Private authoring directory; never a runtime input directory.
        semaphore: Explicit limit on simultaneous question workflows.

    Returns:
        Whether a validated second-pass review exists. Failures are recorded by
        exception class, without provider bodies or credential values.
    """
    async with semaphore:
        target = output / "records" / f"{index:03d}.json"
        if target.exists():
            cached = json.loads(target.read_text())
            if cached["question_id"] != original.case.question_id:
                raise ValueError("Quality checkpoint identity mismatch")
            validate_quality_audit(
                RubricQualityAudit.model_validate(cached["audit"]), original
            )
            return True
        stage = "audit"
        try:
            draft_path = output / "drafts" / f"{index:03d}.json"
            if draft_path.exists():
                draft = validate_quality_audit(
                    RubricQualityAudit.model_validate(
                        json.loads(draft_path.read_text())["audit"]
                    ),
                    original,
                )
            else:
                result = await auditor.run(original.model_dump_json(), deps=original)
                draft = result.output
                write_json(
                    draft_path,
                    {
                        "question_id": original.case.question_id,
                        "audit": draft.model_dump(),
                        "response_id": result.response.provider_response_id,
                        "usage": {
                            "input_tokens": result.usage.input_tokens,
                            "output_tokens": result.usage.output_tokens,
                        },
                    },
                )
            stage = "review"
            result = await reviewer.run(
                json.dumps(
                    {"original": original.model_dump(), "draft": draft.model_dump()},
                    ensure_ascii=False,
                ),
                deps=original,
            )
            write_json(
                target,
                {
                    "question_id": original.case.question_id,
                    "audit": result.output.model_dump(),
                    "response_id": result.response.provider_response_id,
                    "usage": {
                        "input_tokens": result.usage.input_tokens,
                        "output_tokens": result.usage.output_tokens,
                    },
                },
            )
            (output / "errors" / f"{index:03d}.json").unlink(missing_ok=True)
            print(f"Reviewed {index + 1}: {original.case.question_id}", flush=True)
            return True
        except Exception as error:  # noqa: BLE001 - Handle failures at the task boundary.
            write_json(
                output / "errors" / f"{index:03d}.json",
                {
                    "question_id": original.case.question_id,
                    "stage": stage,
                    "error_type": type(error).__name__,
                    "cause_type": type(error.__cause__).__name__
                    if error.__cause__
                    else None,
                },
            )
            print(f"Failed {index + 1}: {stage} {type(error).__name__}", flush=True)
            return False


def export_reviews(inputs: list[QualityInput], output: Path) -> dict[str, Any]:
    """Summarize all reviewed rules and export complete proposed repairs for review.

    Args:
        inputs: Entire active set, in checkpoint order.
        output: Private directory containing validated review checkpoints.

    Returns:
        Counts of completed questions, original defects, and proposed core sizes.
        Full proposed exports are written only when every question is reviewed.
    """
    rows: list[dict[str, Any]] = []
    issues: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    for index, original in enumerate(inputs):
        path = output / "records" / f"{index:03d}.json"
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        if record["question_id"] != original.case.question_id:
            raise ValueError("Quality checkpoint identity mismatch")
        audit = validate_quality_audit(
            RubricQualityAudit.model_validate(record["audit"]), original
        )
        issues.update({issue.code for issue in audit.original_issues})
        kinds.update(item.kind for item in audit.original_assessments)
        rows.append(
            {
                "question_id": original.case.question_id,
                "question": original.case.question,
                "reference": original.case.reference_answer,
                "original_rubric": original.original_rubric,
                **audit.model_dump(),
                "status": "proposed_only_model_reviewed_not_human_certified",
            }
        )
    summary = {
        "expected": len(inputs),
        "completed": len(rows),
        "original_rule_types": dict(kinds),
        "questions_by_issue": dict(issues),
        "original_questions_without_required_fact": sum(
            not any(
                item["kind"] == "required_fact" for item in row["original_assessments"]
            )
            for row in rows
        ),
        "revised_questions_without_required_fact": sum(
            not row["required_indices"] for row in rows
        ),
        "proposed_required_rules": sum(len(row["required_indices"]) for row in rows),
        "proposed_guard_rules": sum(len(row["guard_indices"]) for row in rows),
        "runtime_modified": False,
        "human_certified": False,
    }
    write_json(output / "summary.json", summary)
    if len(rows) == len(inputs):
        write_json(output / "reviews.json", rows)
        write_json(
            output / "proposed_rubrics.json",
            [
                {
                    "question_id": row["question_id"],
                    "question": row["question"],
                    "reference": row["reference"],
                    "rubric": row["revised"]["rubric"],
                    "required_indices": row["required_indices"],
                    "guard_indices": row["guard_indices"],
                    "grounding": row["revised"]["grounding"],
                }
                for row in rows
            ],
        )
    return summary


async def run(args: argparse.Namespace) -> None:
    """Run the complete source-grounded quality audit using the approved API.

    Args:
        args: Explicit local input/output paths and provider/runtime policy.

    Raises:
        ValueError: Source hashes, question associations, credentials, or resume
            configuration do not match the requested audit.
        SystemExit: A question fails both-pass processing; checkpoints remain.
    """
    cases = load_cases(args.private)
    manifest = json.loads((args.private / "manifest.json").read_text())
    if digest(args.private / "rubrics.json") != manifest["rubrics_sha256"]:
        raise ValueError("Active rubric hash mismatch")
    current = {
        row["question_id"]: row
        for row in json.loads((args.private / "rubrics.json").read_text())
    }
    if set(current) != {case.question_id for case in cases}:
        raise ValueError("Active rubric coverage mismatch")
    inputs = [
        QualityInput(case=case, original_rubric=current[case.question_id]["rubric"])
        for case in cases
    ]
    here = Path(__file__).parent
    configuration = {
        "model": args.model,
        "reasoning": args.reasoning,
        "max_tokens": args.max_tokens,
        "output_retries": args.output_retries,
        "inputs": {
            name: digest(args.private / name)
            for name in ("cases.json", "corpus.json", "rubrics.json", "manifest.json")
        },
        "sources": {
            name: digest(here / name)
            for name in (
                "quality.py",
                "quality_models.py",
                "quality_audit.md",
                "quality_review.md",
                "models.py",
                "build.py",
            )
        },
    }
    provenance = args.output / "provenance.json"
    if (
        provenance.exists()
        and json.loads(provenance.read_text())["configuration"] != configuration
    ):
        raise ValueError("Quality-review inputs changed; use a new output directory")
    if not provenance.exists():
        write_json(
            provenance,
            {
                "created_at": datetime.now(UTC).isoformat(),
                "configuration": configuration,
            },
        )
    write_json(args.output / "inputs.json", [item.model_dump() for item in inputs])
    key = dotenv_values(args.credentials).get("OPENAI_API_KEY")
    if not key:
        raise ValueError("Project credential file must contain OPENAI_API_KEY")
    async with AsyncOpenAI(
        api_key=key,
        base_url="https://api.openai.com/v1",
        timeout=args.timeout,
        max_retries=args.transport_retries,
    ) as client:
        auditor = make_agent(client, args, here / "quality_audit.md")
        reviewer = make_agent(client, args, here / "quality_review.md")
        semaphore = asyncio.Semaphore(args.concurrency)
        print(
            f"Auditing {len(inputs)} questions with {args.concurrency} concurrent workflows",
            flush=True,
        )
        results = await asyncio.gather(
            *(
                review_one(index, item, auditor, reviewer, args.output, semaphore)
                for index, item in enumerate(inputs)
            )
        )
    print(json.dumps(export_reviews(inputs, args.output)), flush=True)
    if not all(results):
        raise SystemExit(1)


def main() -> None:
    """Read explicit audit settings and run both passes without runtime edits."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("private", "output", "credentials"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning", choices=("low", "medium", "high"), required=True)
    for name in (
        "concurrency",
        "output-retries",
        "transport-retries",
        "max-tokens",
        "timeout",
    ):
        parser.add_argument(f"--{name}", type=int, required=True)
    args = parser.parse_args()
    if (
        min(args.concurrency, args.max_tokens, args.timeout) < 1
        or min(args.output_retries, args.transport_retries) < 0
    ):
        parser.error(
            "Concurrency, tokens and timeout must be positive; retries must be nonnegative"
        )
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
