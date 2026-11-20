"""Read and authenticate private evaluation inputs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from verifier.contracts import EvaluationError, HeldOutCase
from verifier.dataset import DATASET_REVISION, QUESTION_COUNT


@dataclass(frozen=True)
class ReviewedRubric:
    """Authenticated rules, explicit mandatory indices, and corrected example."""

    rules: tuple[str, ...]
    required_indices: tuple[int, ...]
    reference: str


def load_rubrics(private: Path, rows: list[dict[str, Any]]) -> dict[str, ReviewedRubric]:
    """Join reviewed factual rules to exactly the active questions and references.

    Used by load_inputs after authenticating the rubric file's manifest hash.
    Question text and gold answers must still match the reviewed version.

    Args:
        private: Trusted directory containing the authenticated rubrics.json.
        rows: Active case records in their original evaluation order.

    Returns:
        Reviewed rule partitions and examples keyed by unique question ID.

    Raises:
        ValueError: Coverage, identity, source text, or rule structure is invalid.
    """
    reviewed = json.loads((private / "rubrics.json").read_text())
    if not isinstance(reviewed, list) or not all(isinstance(row, dict) for row in reviewed):
        raise ValueError("Expected a reviewed rubric array")
    by_id = {row["question_id"]: row for row in reviewed}
    if len(by_id) != len(reviewed) or set(by_id) != {row["question_id"] for row in rows}:
        raise ValueError("Rubrics must cover exactly the active question IDs")
    result: dict[str, ReviewedRubric] = {}
    for row in rows:
        reviewed_row = by_id[row["question_id"]]
        if reviewed_row["question"] != row["question"] or reviewed_row["reference"] != row["reference"]:
            raise ValueError("Reviewed rubric question or reference has changed")
        rules = reviewed_row["rubric"]
        if (not isinstance(rules, list) or not rules or
                any(not isinstance(rule, str) or not rule.startswith("must ") or
                    not rule[5:].strip() or "\n" in rule or "\r" in rule for rule in rules)):
            raise ValueError("Expected nonempty, single-line must-have rubric rules")
        if len(set(rules)) != len(rules) or any(not re.search(r'"[^"\n]+"', rule) for rule in rules):
            raise ValueError("Rubric rules must be unique and include a quoted factual anchor")
        required = reviewed_row["required_indices"]
        guards = reviewed_row["guard_indices"]
        if (not isinstance(required, list) or not required or not isinstance(guards, list) or
                any(type(index) is not int for index in required + guards) or
                sorted(required + guards) != list(range(len(rules)))):
            raise ValueError("Required and optional indices must partition the rubric exactly once")
        for index in required:
            outside_quotes = re.sub(r'"[^"\n]*"', 'QUOTE', rules[index]).lower()
            if outside_quotes.startswith(("must not ", "must avoid ")) or re.search(r"\b(?:if|when)\b", outside_quotes):
                raise ValueError("A required core cannot be a negative-only or conditional claim guard")
        reference = reviewed_row["reviewed_reference"]
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Expected a source-reviewed example answer")
        result[row["question_id"]] = ReviewedRubric(tuple(rules), tuple(required), reference)
    return result


def load_inputs(private: Path, *, allow_ci_fixtures: bool = False) -> tuple[Path, tuple[HeldOutCase, ...], dict[str, Any]]:
    """Validate pinned private input hashes and the complete scoring denominator.

    Args:
        private: Trusted directory populated by scripts/prepare_data.py.
        allow_ci_fixtures: Permit explicitly marked structural fixtures in author
            packaging checks only. The production entry point never enables this.

    Returns:
        Corpus path, retained content cases with authenticated must-have rubrics
        and audit source records, and the provenance manifest.

    Raises:
        EvaluationError: Missing, corrupted, or mismatched evaluation inputs.
    """
    try:
        manifest = json.loads((private / "manifest.json").read_text())
        if manifest.get("ci_fixture_only") and not allow_ci_fixtures:
            raise ValueError("CI rubric fixtures cannot be used for evaluation")
        if manifest["herb_revision"] != DATASET_REVISION:
            raise ValueError("HERB revision mismatch")
        for filename, key in (("corpus.json", "corpus_sha256"), ("cases.json", "cases_sha256"),
                              ("rubrics.json", "rubrics_sha256")):
            if hashlib.sha256((private / filename).read_bytes()).hexdigest() != manifest[key]:
                raise ValueError(f"Hash mismatch: {filename}")
        records = json.loads((private / "corpus.json").read_text())
        documents = {row["doc_id"]: row for row in records}
        if len(documents) != len(records):
            raise ValueError("Duplicate corpus document IDs")
        rows = json.loads((private / "cases.json").read_text())
        rubrics = load_rubrics(private, rows)
        resolved: list[HeldOutCase] = []
        for row in rows:
            evidence_ids = row["evidence_doc_ids"]
            if (not isinstance(evidence_ids, list) or not evidence_ids
                    or not all(isinstance(identity, str) for identity in evidence_ids)
                    or len(set(evidence_ids)) != len(evidence_ids)):
                raise ValueError("Expected nonempty, unique reference evidence IDs")
            evidence = tuple(documents[identity] for identity in evidence_ids)
            reviewed = rubrics[row["question_id"]]
            reference = reviewed.reference
            facts = (reference,) if isinstance(reference, str) else tuple(reference)
            if not facts or not all(isinstance(fact, str) and fact.strip() for fact in facts):
                raise ValueError("Expected nonempty reference answer facts")
            resolved.append(HeldOutCase(row["question_id"], row["question"], reference, evidence,
                                       facts, "content", "gold", reviewed.rules, reviewed.required_indices))
        cases = tuple(resolved)
        if (len(cases) != QUESTION_COUNT or len({case.question_id for case in cases}) != QUESTION_COUNT
                or manifest["content_questions"] != QUESTION_COUNT):
            raise ValueError(f"Expected {QUESTION_COUNT} unique held-out questions")
        if set(manifest.get("excluded_question_ids", ())) & {case.question_id for case in cases}:
            raise ValueError("A reviewed exclusion is present in the held-out questions")
        return private / "corpus.json", cases, manifest
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EvaluationError(f"Invalid private inputs: {exc}") from exc
