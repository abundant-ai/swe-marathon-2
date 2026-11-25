"""Author and independently review all private factual rubrics with resumable runs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from .models import CaseInput, RubricDraft, validate_grounding


def digest(path: Path) -> str:
    """Hash an input to prevent resuming against different source material.

    Args:
        path: Existing corpus, cases, prompt, or schema source file.

    Returns:
        SHA-256 hex digest of the exact bytes.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Atomically checkpoint a private authoring record on the local filesystem.

    Args:
        path: Destination in the explicitly selected author output directory.
        value: JSON-compatible structured result; never credentials.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def load_cases(private: Path) -> list[CaseInput]:
    """Resolve every pinned case to its full original reference documents.

    Args:
        private: Trusted directory containing corpus.json, cases.json, manifest.json.

    Returns:
        Cases in dataset order; no retrieval, sampling, or document truncation.

    Raises:
        ValueError: Pinned hashes, counts, or uniqueness checks fail.
        KeyError: A reference document is absent from the corpus.
    """
    manifest = json.loads((private / "manifest.json").read_text())
    for filename, key in (
        ("cases.json", "cases_sha256"),
        ("corpus.json", "corpus_sha256"),
    ):
        if digest(private / filename) != manifest[key]:
            raise ValueError(f"Input hash mismatch: {filename}")
    rows = json.loads((private / "corpus.json").read_text())
    documents = {row["doc_id"]: row for row in rows}
    if len(rows) != len(documents):
        raise ValueError("Duplicate document IDs")
    cases = []
    profiles = [
        doc
        for doc in rows
        if doc["source_type"] == "directory"
        and not doc["doc_id"].startswith("directory:salesforce_team:")
    ]
    for row in json.loads((private / "cases.json").read_text()):
        evidence = [documents[doc_id] for doc_id in row["evidence_doc_ids"]]
        supplements = resolve_profiles(evidence, profiles, row["question"])
        cases.append(
            CaseInput(
                question_id=row["question_id"],
                question=row["question"],
                reference_answer=row["reference"],
                reference_documents=[*evidence, *supplements],
                supplemental_reference_doc_ids=[doc["doc_id"] for doc in supplements],
            )
        )
    if len(cases) != manifest["content_questions"] or len(
        {c.question_id for c in cases}
    ) != len(cases):
        raise ValueError("Private case count or uniqueness mismatch")
    return cases


def resolve_profiles(
    evidence: list[dict[str, str]], profiles: list[dict[str, str]], question: str
) -> list[dict[str, str]]:
    """Attach original directory records needed to resolve source IDs and names.

    Args:
        evidence: Original mapped documents for this question.
        profiles: Flat employee/customer records from the same pinned corpus.
        question: Original question, which may name a customer or employee.

    Returns:
        Unmodified directory records matching a referenced ID or full name.
        All homonymous profiles are included; a name alone never selects one
        identity. Existing evidence records are not duplicated.
    """
    text = question + "\n" + "\n".join(doc["content"] for doc in evidence)
    identifiers = set(re.findall(r"eid_[0-9a-f]+|CUST-\d+", text))
    existing = {doc["doc_id"] for doc in evidence}
    supplements = []
    for doc in profiles:
        if doc["doc_id"] in existing:
            continue
        profile = json.loads(doc["content"])
        identity = profile.get("employee_id") or profile.get("id")
        names = [profile.get("name"), profile.get("company")]
        if identity in identifiers or any(
            isinstance(name, str) and name and name in text for name in names
        ):
            supplements.append(doc)
    return supplements


def make_agent(
    client: AsyncOpenAI, args: argparse.Namespace, prompt: Path, role: str
) -> Agent[CaseInput, RubricDraft]:
    """Build a typed model call with exact-source validation and bounded repairs.

    Args:
        client: Caller-owned official OpenAI client using the local project key.
        args: Explicit model, reasoning, output-token, and retry settings.
        prompt: Author-only rubric instructions file.
        role: System role for either initial drafting or independent review.

    Returns:
        PydanticAI agent with strict native structured output and grounding checks.
    """
    model = OpenAIResponsesModel(
        args.model, provider=OpenAIProvider(openai_client=client)
    )
    agent = Agent(
        model,
        deps_type=CaseInput,
        output_type=NativeOutput(RubricDraft, strict=True),
        system_prompt=role,
        instructions=prompt.read_text(),
        retries=args.output_retries,
        model_settings=OpenAIResponsesModelSettings(
            openai_reasoning_effort=args.reasoning,
            openai_store=False,
            max_tokens=args.max_tokens,
        ),
    )

    @agent.output_validator
    def check_grounding(ctx: RunContext[CaseInput], output: RubricDraft) -> RubricDraft:
        """Ask for a bounded correction if source quotations cannot be verified.

        Args:
            ctx: Original case supplied to this isolated authoring call.
            output: Model-authored rubric and evidence excerpts.

        Returns:
            Structurally and literally validated output, without asserting semantic accuracy.

        Raises:
            ModelRetry: Source validation failed and a repair is needed.
        """
        try:
            return validate_grounding(output, ctx.deps)
        except ValueError as error:
            raise ModelRetry(str(error)) from error

    return agent


async def process_case(
    case: CaseInput,
    index: int,
    author: Agent[CaseInput, RubricDraft],
    reviewer: Agent[CaseInput, RubricDraft],
    output: Path,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Draft and review one question, checkpointing each independently completed pass.

    Args:
        case: Complete source-linked case; no private data is logged to stdout.
        index: Stable dataset position for checkpoint filenames.
        author: Structured first-pass author.
        reviewer: Independent fresh-context reviewer with all original sources.
        output: Private authoring output directory, excluded from candidate inputs.
        semaphore: Explicit concurrency ceiling across question workflows.

    Returns:
        True when both passes validate; False on a recorded provider/output failure.
        A retry resumes the completed pass without repeating its API cost.
    """
    async with semaphore:
        path = output / "records" / f"{index:03d}.json"
        if path.exists():
            cached = json.loads(path.read_text())
            validate_grounding(RubricDraft.model_validate(cached["review"]), case)
            return True
        stage = "author"
        try:
            draft_path = output / "drafts" / f"{index:03d}.json"
            if draft_path.exists():
                draft_record = json.loads(draft_path.read_text())
                draft = validate_grounding(
                    RubricDraft.model_validate(draft_record["draft"]), case
                )
            else:
                result = await author.run(case.model_dump_json(), deps=case)
                draft = result.output
                draft_record = {
                    "question_id": case.question_id,
                    "draft": draft.model_dump(),
                    "response_id": result.response.provider_response_id,
                    "usage": {
                        "input_tokens": result.usage.input_tokens,
                        "output_tokens": result.usage.output_tokens,
                    },
                }
                write_json(draft_path, draft_record)
            stage = "review"
            payload = {"case": case.model_dump(), "draft": draft.model_dump()}
            result = await reviewer.run(
                json.dumps(payload, ensure_ascii=False), deps=case
            )
            write_json(
                path,
                {
                    "question_id": case.question_id,
                    "review": result.output.model_dump(),
                    "response_id": result.response.provider_response_id,
                    "usage": {
                        "input_tokens": result.usage.input_tokens,
                        "output_tokens": result.usage.output_tokens,
                    },
                },
            )
            error_path = output / "errors" / f"{index:03d}.json"
            error_path.unlink(missing_ok=True)
            print(
                f"Reviewed {index + 1}: {case.question_id} ({result.output.reference_status})",
                flush=True,
            )
            return True
        except Exception as error:  # noqa: BLE001 - Handle failures at the task boundary.
            # Provider exception bodies can contain sensitive request data.
            write_json(
                output / "errors" / f"{index:03d}.json",
                {
                    "question_id": case.question_id,
                    "stage": stage,
                    "error_type": type(error).__name__,
                    "cause_type": type(error.__cause__).__name__
                    if error.__cause__
                    else None,
                },
            )
            print(f"Failed {index + 1}: {stage} {type(error).__name__}", flush=True)
            return False


def export_results(cases: list[CaseInput], output: Path) -> dict[str, Any]:
    """Build a self-contained private dataset and explicit outstanding-review list.

    Args:
        cases: Full, ordered private dataset, including cases not yet processed.
        output: Directory holding pinned provenance and validated checkpoints.

    Returns:
        Counts and source/reference warnings. Writes final rubrics only if every
        case is present; partial runs cannot masquerade as a complete dataset.
    """
    records: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    for index, case in enumerate(cases):
        path = output / "records" / f"{index:03d}.json"
        if not path.exists():
            continue
        checkpoint = json.loads(path.read_text())
        if checkpoint["question_id"] != case.question_id:
            raise ValueError("Checkpoint question identity mismatch")
        reviewed = validate_grounding(
            RubricDraft.model_validate(checkpoint["review"]), case
        )
        records.append(
            {
                **case.model_dump(),
                **reviewed.model_dump(),
                "validation_status": "model_reviewed_not_human_certified",
            }
        )
        statuses[reviewed.reference_status] += 1
        if reviewed.reference_status != "supported":
            warnings.append(
                {
                    "question_id": case.question_id,
                    "status": reviewed.reference_status,
                    "notes": reviewed.reference_notes,
                }
            )
    summary = {
        "expected": len(cases),
        "completed": len(records),
        "reference_statuses": dict(statuses),
        "rubric_items": sum(len(row["rubric"]) for row in records),
        "source_conflicts_require_author_review": len(warnings),
        "human_reviewed": False,
        "production_judge_updated": False,
    }
    write_json(output / "summary.json", summary)
    write_json(output / "reference-review.json", warnings)
    if len(records) == len(cases):
        write_json(output / "rubrics.json", records)
    return summary


async def run(args: argparse.Namespace) -> None:
    """Run the explicitly configured local authoring job without remote secrets upload.

    Args:
        args: CLI paths, provider settings, concurrency, and optional pilot size.

    Raises:
        ValueError: Source/configuration drift or missing local API credential.
        SystemExit: Any selected case fails; successful checkpoints remain reusable.
    """
    cases = load_cases(args.private)
    here = Path(__file__).parent
    provenance = {
        "model": args.model,
        "reasoning": args.reasoning,
        "output_retries": args.output_retries,
        "max_tokens": args.max_tokens,
        "input_hashes": {
            name: digest(args.private / name)
            for name in ("cases.json", "corpus.json", "manifest.json")
        },
        "authoring_hashes": {
            name: digest(here / name)
            for name in ("author.md", "review.md", "models.py", "build.py")
        },
    }
    manifest = args.output / "provenance.json"
    if (
        manifest.exists()
        and json.loads(manifest.read_text())["configuration"] != provenance
    ):
        raise ValueError(
            "Authoring inputs or settings changed; choose a new output directory"
        )
    if not manifest.exists():
        write_json(
            manifest,
            {
                "created_at": datetime.now(UTC).isoformat(),
                "configuration": provenance,
            },
        )
    key = dotenv_values(args.credentials).get("OPENAI_API_KEY")
    if not key:
        raise ValueError("Project credential file must contain OPENAI_API_KEY")
    async with AsyncOpenAI(
        api_key=key,
        base_url="https://api.openai.com/v1",
        timeout=args.timeout,
        max_retries=args.transport_retries,
    ) as client:
        author = make_agent(
            client,
            args,
            here / "author.md",
            "You author source-grounded factual-correctness rubrics.",
        )
        reviewer = make_agent(
            client,
            args,
            here / "review.md",
            "You independently audit factual-correctness rubrics against original evidence.",
        )
        semaphore = asyncio.Semaphore(args.concurrency)
        selected = cases[: args.limit] if args.limit else cases
        results = await asyncio.gather(
            *(
                process_case(case, i, author, reviewer, args.output, semaphore)
                for i, case in enumerate(selected)
            )
        )
    print(json.dumps(export_results(cases, args.output)), flush=True)
    if not all(results):
        raise SystemExit(1)


def main() -> None:
    """Parse explicit authoring configuration and start the resumable local job.

    All input/output paths and model policy are CLI arguments. This entry point
    neither changes the production judge nor publishes the resulting rubrics.
    """
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
    parser.add_argument(
        "--limit",
        type=int,
        help="Pilot only; final export still requires every question",
    )
    args = parser.parse_args()
    if (
        min(args.concurrency, args.max_tokens, args.timeout) < 1
        or min(args.output_retries, args.transport_retries) < 0
    ):
        parser.error(
            "Concurrency, tokens and timeout must be positive; retry counts must be nonnegative"
        )
    if args.limit is not None and args.limit < 1:
        parser.error("Pilot size must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
