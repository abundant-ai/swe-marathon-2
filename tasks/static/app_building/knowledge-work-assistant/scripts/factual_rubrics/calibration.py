"""Replay saved oracle answers and source-grounded controls through both judges."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from task_paths import TASK_ROOT

sys.path.insert(0, str(TASK_ROOT / "tests"))

from calibrate_judges import run_calibration
from verifier.config import load_answer_scoring_config
from verifier.inputs import load_inputs
from verifier.judging.client import KnowledgeJudge

from .finalize import apply_calibration_repairs
from .models import RubricDraft


def build_fixtures(
    private: Path, saved_answers: Path, controls: Path, mode: str
) -> dict[str, Any]:
    """Join saved answers by stable identity and build pre-labelled factual controls.

    Args:
        private: Authenticated current cases, corpus, and reviewed rubrics.
        saved_answers: Oracle output already matched to original questions and corpus.
        controls: Maintained source-grounded variants and expected scores.
        mode: oracle, references, controls, or all.

    Returns:
        Production calibration fixtures. Oracle ratings have no assumed golden
        score; source-reviewed examples and controls have predeclared expectations.

    Raises:
        ValueError: Question coverage or a controlled citation is ambiguous/invalid.
    """
    corpus_path, cases, manifest = load_inputs(private)
    documents = {row["doc_id"]: row for row in json.loads(corpus_path.read_text())}
    oracle_rows = json.loads(saved_answers.read_text())
    oracle = {row["question_id"]: row for row in oracle_rows}
    if len(oracle) != len(oracle_rows) or set(oracle) != {
        case.question_id for case in cases
    }:
        raise ValueError(
            "Saved oracle answers must cover every active question exactly once"
        )
    definitions = {
        row["question_id"]: row["variants"] for row in json.loads(controls.read_text())
    }
    if not set(definitions).issubset(oracle):
        raise ValueError("Controlled variant references an inactive question")
    entries = []
    for case in cases:
        saved = oracle[case.question_id]
        if saved["question"] != case.question:
            raise ValueError("Saved oracle question differs from active case")
        variants: list[dict[str, Any]] = []
        citation_ids: set[str] = set()
        if mode in ("oracle", "all"):
            variants.append(
                {
                    "name": "oracle",
                    "answer": saved["answer"],
                    "citations": saved["citations"],
                    "expected_answer_scores": [],
                    "expected_citation_scores": [],
                    "old_answer_score": saved["old_answer_judgment"]["score"] / 100,
                    "old_citation_score": saved["old_citation_judgment"]["score"] / 100,
                }
            )
            citation_ids.update(item["doc_id"] for item in saved["citations"])
        if mode in ("references", "all"):
            variants.append(
                {
                    "name": "reviewed_example",
                    "answer": case.reference,
                    "citations": [],
                    "expected_answer_scores": [1.0],
                    "expected_citation_scores": [0.0],
                }
            )
        if mode in ("controls", "all"):
            for variant in definitions.get(case.question_id, []):
                citations = []
                for suffix in variant["source_suffixes"]:
                    matches = [
                        doc
                        for doc in documents.values()
                        if doc["doc_id"].startswith(
                            case.question_id.split(":")[0] + ":"
                        )
                        and doc["doc_id"].endswith(suffix)
                    ]
                    if len(matches) != 1:
                        raise ValueError(
                            f"Controlled source selector is not unique: {suffix}"
                        )
                    doc = matches[0]
                    quote = variant.get("quote_override", doc["content"])
                    if quote not in doc["content"]:
                        raise ValueError("Controlled quotation is not exact")
                    citations.append({"doc_id": doc["doc_id"], "quote": quote})
                    citation_ids.add(doc["doc_id"])
                variants.append(
                    {
                        key: value
                        for key, value in variant.items()
                        if key not in ("source_suffixes", "quote_override")
                    }
                    | {"citations": citations}
                )
        if variants:
            entries.append(
                {
                    **asdict(case),
                    "variants": variants,
                    "citation_documents": [
                        documents[identity] for identity in sorted(citation_ids)
                    ],
                }
            )
    return {
        "corpus_sha256": manifest["corpus_sha256"],
        "rubrics_sha256": manifest["rubrics_sha256"],
        "label_provenance": "source-reviewed author expectations, not human-certified labels",
        "cases": entries,
    }


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    """Compare live outputs to expectations fixed before calls and to old oracle ratings.

    Args:
        result: Complete or interrupted production-flow calibration output.

    Returns:
        Coverage, control disagreements, citation-gate failures, and oracle means.
        Old versus new oracle ratings use different rubrics and are not evidence
        that the oracle implementation improved.
    """
    disagreements, gate_errors, oracle = [], [], []
    for row in result["judgments"]:
        label = result["labels"][row["question_id"]]
        for component in ("answer", "citation"):
            expected = label.get(f"expected_{component}_scores", [])
            if expected and not any(
                math.isclose(row[f"{component}_band"], score, abs_tol=1e-9)
                for score in expected
            ):
                disagreements.append(
                    {
                        "question_id": row["question_id"],
                        "component": component,
                        "expected": expected,
                        "actual": row[f"{component}_band"],
                        "judgment": row[f"{component}_judgment"],
                    }
                )
        calls = [
            call for call in result["calls"] if call["case_id"] == row["question_id"]
        ]
        answer_calls = [call for call in calls if call["kind"] == "answer"]
        citation_calls = [call for call in calls if call["kind"] == "citation"]
        if any(
            row["answer_band"] < result["policy"]["citation_min_answer_score"]
            or not answer_calls
            or call["started"] < answer_calls[0]["finished"]
            for call in citation_calls
        ):
            gate_errors.append(row["question_id"])
        if label["name"] == "oracle":
            oracle.append(
                {
                    "question_id": row["question_id"],
                    "old_answer": label["old_answer_score"],
                    "new_answer": row["answer_band"],
                    "old_citation": label["old_citation_score"],
                    "new_citation": row["citation_band"],
                }
            )
    means = (
        {
            key: sum(row[key] for row in oracle) / len(oracle)
            for key in ("old_answer", "new_answer", "old_citation", "new_citation")
        }
        if oracle
        else {}
    )
    return {
        "completed": len(result["judgments"]),
        "expected": result["expected_rows"],
        "model": result["model"],
        "transport": result["transport"],
        "disagreements": disagreements,
        "gate_errors": gate_errors,
        "oracle_means": means,
        "oracle_comparison": oracle,
        "error": result["error"],
        "peak_concurrent_requests": result["peak_concurrent_requests"],
    }


def apply_review_checkpoints(
    fixtures: dict[str, Any],
    directory: Path,
    exclude: set[str],
    *,
    source_audits: bool = False,
) -> dict[str, Any]:
    """Select completed immutable source reviews while other reviews continue.

    Args:
        fixtures: Current production fixtures before provider calls.
        directory: Full-source review checkpoints with per-question identities.
        exclude: Question IDs already evaluated with these same checkpoints.
        source_audits: Use the later oracle/source audits and their independent
            expected answer scores, instead of initial rubric reviews.

    Returns:
        New fixture mapping using completed reviewed rules and examples only,
        with the exact review call IDs recorded. Unfinished questions are omitted
        explicitly from this calibration shard, not from the held-out dataset.
    """
    pattern = "audit-*.json" if source_audits else "review-*.json"
    reviewed = {
        row["question_id"]: row
        for row in (json.loads(path.read_text()) for path in directory.glob(pattern))
    }
    repairs = json.loads(
        Path(__file__).with_name("source_review_repairs.json").read_text()
    )
    labels = json.loads(Path(__file__).with_name("calibration_labels.json").read_text())
    entries = []
    for entry in fixtures["cases"]:
        if entry["question_id"] not in reviewed or entry["question_id"] in exclude:
            continue
        review = reviewed[entry["question_id"]]
        draft = review["audit"]["revised"] if source_audits else review["draft"]
        if source_audits:
            draft = apply_calibration_repairs(
                RubricDraft.model_validate(draft), entry["question_id"], repairs
            ).model_dump()
        variants = [
            {**variant, "answer": draft["correct_answer"]}
            if variant["name"] == "reviewed_example"
            else variant
            for variant in entry["variants"]
        ]
        if source_audits:
            expected = labels.get(entry["question_id"], {}).get(
                "expected_answer_score", review["expected_judgment"]["score"] / 100
            )
            variants = [
                {**variant, "expected_answer_scores": [expected]}
                if variant["name"] == "oracle"
                else variant
                for variant in variants
            ]
        entries.append(
            {
                **entry,
                "rubric": draft["rubric"],
                "reference": draft["correct_answer"],
                "required_rubric_indices": [0],
                "variants": variants,
                "review_call_id": review["call_id"],
            }
        )
    if not entries:
        raise ValueError("No completed, unevaluated review checkpoints are available")
    return {
        **fixtures,
        "cases": entries,
        "review_checkpoints": str(directory),
        "scoring_rubrics": "per-case reviewed checkpoint in this immutable fixture",
    }


def main() -> None:
    """Save fixtures, then run the pinned production judge through its direct API client."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--controls",
        type=Path,
        default=Path(__file__).with_name("calibration_controls.json"),
    )
    parser.add_argument(
        "--mode", choices=("oracle", "references", "controls", "all"), required=True
    )
    parser.add_argument("--repeats", type=int, required=True)
    parser.add_argument("--retries", type=int, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--review-checkpoints", type=Path)
    parser.add_argument("--source-audit-checkpoints", type=Path)
    parser.add_argument("--exclude-fixtures", type=Path)
    parser.add_argument("--question-id", action="append", default=[])
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("Repeats must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "results.json").exists():
        parser.error(
            "Use a new output directory; previous calibration evidence is immutable"
        )
    fixtures = build_fixtures(args.private, args.answers, args.controls, args.mode)
    if args.review_checkpoints and args.source_audit_checkpoints:
        parser.error("Choose one checkpoint stage")
    if args.review_checkpoints or args.source_audit_checkpoints:
        exclude = (
            {
                row["question_id"]
                for row in json.loads(args.exclude_fixtures.read_text())["cases"]
            }
            if args.exclude_fixtures
            else set()
        )
        fixtures = apply_review_checkpoints(
            fixtures,
            args.source_audit_checkpoints or args.review_checkpoints,
            exclude,
            source_audits=bool(args.source_audit_checkpoints),
        )
    if args.question_id:
        selected = set(args.question_id)
        fixtures["cases"] = [
            entry for entry in fixtures["cases"] if entry["question_id"] in selected
        ]
        if {entry["question_id"] for entry in fixtures["cases"]} != selected:
            parser.error("A selected question has no fixture at this review stage")
    (args.output / "fixtures.json").write_text(
        json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n"
    )
    if args.prepare_only:
        print(
            json.dumps(
                {
                    "questions": len(fixtures["cases"]),
                    "variants": sum(len(row["variants"]) for row in fixtures["cases"]),
                }
            )
        )
        return
    answer_scoring = load_answer_scoring_config(
        tomllib.loads((TASK_ROOT / "task.toml").read_text())["verifier"]["env"]
    )
    result = run_calibration(
        fixtures,
        args.repeats,
        TASK_ROOT / "tests",
        judge=KnowledgeJudge(
            output_retries=args.retries, answer_scoring=answer_scoring
        ),
    )
    (args.output / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    summary = summarize(result)
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in summary.items()
                if key not in ("disagreements", "oracle_comparison")
            }
        )
    )
    print(f"Disagreements: {len(summary['disagreements'])}")
    if result["error"] or summary["completed"] != summary["expected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
