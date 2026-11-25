"""Verify source-preserving rubric repairs and explicit factual-scoring metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from factual_rubrics.finalize import apply_calibration_repairs, finalize_record
from factual_rubrics.install_reviewed import reviewed_rows
from factual_rubrics.models import CaseInput, RubricDraft, SourceDocument
from verifier.inputs import load_rubrics


def reviewed_pair() -> tuple[dict[str, Any], CaseInput]:
    """Construct a two-item source list accidentally treated as mandatory coverage.

    Returns:
        A small complete audit record and immutable original source input.
    """
    case = CaseInput(
        question_id="q",
        question="Find all unresolved issues for Acme?",
        reference_answer="Cache failure.",
        reference_documents=[
            SourceDocument(
                doc_id="d",
                title="Issues",
                source_type="document",
                content="Cache failure and login timeout remain unresolved for Acme.",
            )
        ],
    )
    review = {
        "required_indices": [0, 1],
        "guard_indices": [],
        "review_method": "controlled_fixture",
        "revised": {
            "correct_answer": "Cache failure and login timeout remain unresolved.",
            "rubric": [
                'must identify "Cache failure".',
                'must identify "login timeout".',
            ],
            "grounding": [
                {"rubric_index": i, "doc_id": "d", "quote": quote}
                for i, quote in enumerate(("Cache failure", "login timeout"))
            ],
            "reference_status": "supported",
            "reference_notes": ["Original list is incomplete."],
            "review_notes": [],
        },
    }
    return review, case


def test_list_repair_accepts_one_correct_item_without_erasing_exclusivity_check() -> (
    None
):
    """Require a substantive answer while keeping false exhaustive claims checkable."""
    review, case = reviewed_pair()
    result = finalize_record(
        review,
        case,
        {"q": 'must identify an unresolved issue: "Cache failure" or "login timeout".'},
    )
    assert result["required_indices"] == [0] and result["guard_indices"] == [1]
    assert "proper subset" in result["rubric"][1]
    assert result["reference"] == "Cache failure."
    assert "login timeout" in result["reviewed_reference"]


def test_unreviewed_multicore_repair_fails() -> None:
    """Do not silently choose one arbitrary list item as the answer requirement."""
    review, case = reviewed_pair()
    with pytest.raises(ValueError, match="multiple-core"):
        finalize_record(review, case, {})


def test_repair_cannot_invent_a_source_quote() -> None:
    """Keep exact source provenance even for concise locally written replacements."""
    review, case = reviewed_pair()
    with pytest.raises(ValueError, match="grounding"):
        finalize_record(review, case, {"q": 'must identify "invented issue".'})


def test_calibration_repair_is_source_preserving_and_idempotent() -> None:
    """Allow a scoped wording fix, but reject a fabricated quoted anchor."""
    review, _ = reviewed_pair()
    draft = RubricDraft.model_validate(review["revised"])
    repair = {
        "q": {
            "replacements": {
                draft.rubric[0]: 'must identify the unresolved "Cache failure".'
            },
            "reference_context": "The issues are distinct.",
            "reason": "Clarify scope.",
        }
    }
    revised = apply_calibration_repairs(draft, "q", repair)
    repeated = apply_calibration_repairs(revised, "q", repair)
    assert repeated.rubric == revised.rubric
    assert repeated.correct_answer.count("The issues are distinct.") == 1
    assert revised.grounding == draft.grounding
    repair["q"]["replacements"] = {draft.rubric[0]: 'must identify "invented failure".'}
    with pytest.raises(ValueError, match="ungrounded"):
        apply_calibration_repairs(draft, "q", repair)


@pytest.mark.parametrize(
    "defect", [None, "missing_audit", "changed_corpus", "changed_question"]
)
def test_review_installation_requires_complete_authenticated_sources(
    tmp_path: Path, defect: str | None
) -> None:
    """Refuse partial or stale author inputs before replacing any runtime artifacts.

    Args:
        tmp_path: Isolated private dataset and checkpoint directory.
        defect: Input inconsistency, or None for a valid source-preserving install.
    """
    review, case = reviewed_pair()
    row = finalize_record(
        review, case, {"q": 'must identify "Cache failure" or "login timeout".'}
    )
    draft = {
        **review["revised"],
        "rubric": row["rubric"],
        "grounding": row["grounding"],
    }
    private, audits = tmp_path / "private", tmp_path / "audits"
    private.mkdir()
    audits.mkdir()
    inputs, repairs = tmp_path / "inputs.json", tmp_path / "repairs.json"
    inputs.write_text(json.dumps([{"case": case.model_dump()}]))
    repairs.write_text("{}")
    (private / "corpus.json").write_text(
        json.dumps([doc.model_dump() for doc in case.reference_documents])
    )
    (audits / "provenance.json").write_text(
        json.dumps(
            {
                "inputs_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
                "corpus_sha256": hashlib.sha256(
                    (private / "corpus.json").read_bytes()
                ).hexdigest(),
            }
        )
    )
    record = {
        "question_id": "q",
        "source_doc_ids": ["d"],
        "audit": {"revised": draft},
        "review_call_id": "source-review",
        "call_id": "oracle-audit",
    }
    if defect != "missing_audit":
        (audits / "audit-000.json").write_text(json.dumps(record))
    if defect == "changed_question":
        row["question"] = "A different question"
    if defect == "changed_corpus":
        (private / "corpus.json").write_text("[]")
    (private / "rubrics.json").write_text(json.dumps([row]))
    if defect:
        with pytest.raises(ValueError):
            reviewed_rows(private, inputs, audits, repairs)
    else:
        installed = reviewed_rows(private, inputs, audits, repairs)
        assert installed[0]["reference"] == case.reference_answer
        assert installed[0]["required_indices"] == [0]
        assert installed[0]["audit_call_id"] == "oracle-audit"


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "empty_core",
        "overlap",
        "missing_index",
        "conditional_core",
        "missing_reference",
    ],
)
def test_loader_authenticates_explicit_rule_semantics(
    tmp_path: Path, defect: str | None
) -> None:
    """Reject ambiguous partitions instead of letting the judge decide applicability.

    Args:
        tmp_path: Isolated fixture directory.
        defect: Metadata violation, or None for a valid reviewed record.
    """
    review, case = reviewed_pair()
    record = finalize_record(
        review, case, {"q": 'must identify "Cache failure" or "login timeout".'}
    )
    if defect == "empty_core":
        record["required_indices"] = []
    elif defect == "overlap":
        record["guard_indices"] = [0, 1]
    elif defect == "missing_index":
        record["guard_indices"] = []
    elif defect == "conditional_core":
        record["rubric"][0] = 'must name "Cache failure" if naming an issue.'
    elif defect == "missing_reference":
        record["reviewed_reference"] = ""
    (tmp_path / "rubrics.json").write_text(json.dumps([record]))
    rows = [
        {
            "question_id": case.question_id,
            "question": case.question,
            "reference": case.reference_answer,
        }
    ]
    if defect:
        with pytest.raises(ValueError):
            load_rubrics(tmp_path, rows)
    else:
        loaded = load_rubrics(tmp_path, rows)["q"]
        assert (
            loaded.required_indices == (0,)
            and loaded.reference == record["reviewed_reference"]
        )
