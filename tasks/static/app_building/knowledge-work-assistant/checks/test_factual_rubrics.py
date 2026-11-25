"""Prevent malformed, ungrounded, or incomplete private rubric exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from factual_rubrics.build import export_results, resolve_profiles, write_json
from factual_rubrics.gold_report import make_review_report
from factual_rubrics.models import (
    CaseInput,
    Grounding,
    RubricDraft,
    SourceDocument,
    validate_grounding,
)
from pydantic import ValidationError


@pytest.fixture
def case() -> CaseInput:
    """Provide original evidence whose entity and deadline can be independently checked.

    Returns:
        An authoring case with a supported reference and one exact source record.
    """
    return CaseInput(
        question_id="release:1",
        question="Who owns the release, and when is it due?",
        reference_answer="Maya owns the release; it is due November 22.",
        reference_documents=[
            SourceDocument(
                doc_id="release-note",
                title="Release update",
                content="Maya owns the release. It is due November 22.",
                source_type="message",
            )
        ],
    )


@pytest.fixture
def draft() -> RubricDraft:
    """Provide a factually scoped rubric that permits an incomplete correct answer.

    Returns:
        A valid rubric with conditional deadline accuracy and literal provenance.
    """
    return RubricDraft(
        correct_answer="Maya owns the release.",
        rubric=[
            'must name "Maya" as the owner if identifying the release owner.',
            'must give "November 22" as the deadline if specifying a deadline.',
        ],
        grounding=[
            Grounding(
                rubric_index=0, doc_id="release-note", quote="Maya owns the release."
            ),
            Grounding(
                rubric_index=1, doc_id="release-note", quote="It is due November 22."
            ),
        ],
        reference_status="supported",
        reference_notes=[],
        review_notes=[],
    )


@pytest.mark.parametrize(
    "rule",
    [
        "Must state the owner.",
        "should state the owner.",
        "must ",
        "must state the owner.",
        'must name "Maya".\nAnother rule.',
    ],
)
def test_rejects_non_must_statements(draft: RubricDraft, rule: str) -> None:
    """Reject strings that do not implement the requested private rubric format.

    Args:
        draft: Otherwise valid structured authoring result.
        rule: Invalid prefix or empty must statement.
    """
    payload = draft.model_dump()
    payload["rubric"] = [rule]
    with pytest.raises(ValidationError):
        RubricDraft.model_validate(payload)


@pytest.mark.parametrize(
    "doc_id,quote,index",
    [
        ("invented-source", "Maya owns the release.", 0),
        ("release-note", "Maya owns the release on November 22.", 0),
        ("release-note", "Maya owns the release.", 9),
    ],
)
def test_rejects_false_provenance(
    case: CaseInput, draft: RubricDraft, doc_id: str, quote: str, index: int
) -> None:
    """Reject invented documents, fabricated quotes, and nonexistent rule links.

    Args:
        case: Trusted original documents.
        draft: Valid result before provenance corruption.
        doc_id: Source ID to check.
        quote: Claimed exact excerpt to check.
        index: Claimed rule index to check.
    """
    corrupted = draft.model_copy(
        update={
            "grounding": [Grounding(doc_id=doc_id, quote=quote, rubric_index=index)]
        }
    )
    with pytest.raises(ValueError):
        validate_grounding(corrupted, case)


def test_validates_without_completeness_requirement(
    case: CaseInput, draft: RubricDraft
) -> None:
    """Accept a grounded example answer that omits an optional reference detail.

    Args:
        case: Reference containing both owner and deadline.
        draft: Example giving only the correct owner.
    """
    assert validate_grounding(draft, case) is draft


def test_partial_run_cannot_export_complete_dataset(
    tmp_path: Path, case: CaseInput, draft: RubricDraft
) -> None:
    """Keep the denominator fixed and publish a final dataset only after all cases.

    Args:
        tmp_path: Isolated checkpoint/export directory.
        case: First expected case.
        draft: Source-grounded model output stored as a completed review.
    """
    other = case.model_copy(update={"question_id": "release:2"})
    write_json(
        tmp_path / "records/000.json",
        {"question_id": case.question_id, "review": draft.model_dump()},
    )
    assert export_results([case, other], tmp_path)["completed"] == 1
    assert not (tmp_path / "rubrics.json").exists()
    write_json(
        tmp_path / "records/001.json",
        {"question_id": other.question_id, "review": draft.model_dump()},
    )
    assert export_results([case, other], tmp_path)["completed"] == 2
    exported = json.loads((tmp_path / "rubrics.json").read_text())
    assert exported[0]["reference_answer"] == case.reference_answer
    assert exported[0]["reference_documents"] == [
        doc.model_dump() for doc in case.reference_documents
    ]
    assert exported[0]["rubric"] == draft.rubric


def test_conflict_requires_explanation(case: CaseInput, draft: RubricDraft) -> None:
    """Prevent silent rewriting of the dataset's reference answer.

    Args:
        case: Trusted original case and documents.
        draft: Valid result whose reference status is changed without justification.
    """
    with pytest.raises(ValueError):
        validate_grounding(
            draft.model_copy(update={"reference_status": "conflicted"}), case
        )


def test_rejects_unbacked_inline_quote(case: CaseInput, draft: RubricDraft) -> None:
    """Reject an invented inline anchor even when separate grounding is genuine.

    Args:
        case: Source record naming Maya as the release owner.
        draft: Otherwise valid rubric with a deliberately substituted inline name.
    """
    corrupted = draft.model_copy(
        update={"rubric": [draft.rubric[0].replace('"Maya"', '"Zoe"'), draft.rubric[1]]}
    )
    with pytest.raises(ValueError, match="Inline quote"):
        validate_grounding(corrupted, case)


def test_accepts_exact_gold_answer_anchor(case: CaseInput, draft: RubricDraft) -> None:
    """Accept the user's allowed gold-answer source without fabricating a document.

    Args:
        case: Original reference answer preserved separately from corpus sources.
        draft: Rubric whose first anchor is moved to the unchanged gold answer.
    """
    revised = draft.model_copy(
        update={
            "grounding": [
                Grounding(
                    rubric_index=0, doc_id="$reference", quote="Maya owns the release"
                ),
                draft.grounding[1],
            ]
        }
    )
    assert validate_grounding(revised, case) is revised


def test_resolves_role_ids_and_retains_homonyms() -> None:
    """Supply role lookup evidence without guessing identity from duplicate names."""
    profiles = [
        {
            "doc_id": "person:1",
            "source_type": "directory",
            "title": "Alex",
            "content": json.dumps(
                {
                    "employee_id": "eid_aaa",
                    "name": "Alex Smith",
                    "role": "Engineering Lead",
                }
            ),
        },
        {
            "doc_id": "person:2",
            "source_type": "directory",
            "title": "Alex",
            "content": json.dumps(
                {
                    "employee_id": "eid_bbb",
                    "name": "Alex Smith",
                    "role": "QA Specialist",
                }
            ),
        },
    ]
    source = [{"doc_id": "msg", "content": "eid_aaa suggested adding benchmarks."}]
    assert (
        resolve_profiles(source, profiles, "What did the Engineering Lead suggest?")
        == profiles[:1]
    )
    assert (
        resolve_profiles(source, profiles, "What did Alex Smith suggest?") == profiles
    )
    assert (
        resolve_profiles([*source, profiles[0]], profiles, "What did the lead suggest?")
        == profiles[1:]
    )


def test_gold_report_preserves_original_and_source(
    case: CaseInput, draft: RubricDraft
) -> None:
    """Keep corrections separate from the original gold and retain cited evidence.

    Args:
        case: Unchanged dataset reference and original source document.
        draft: Review result modified to represent an explicit source conflict.
    """
    record = (
        case.model_dump()
        | draft.model_dump()
        | {
            "reference_status": "conflicted",
            "reference_notes": ["Check release-note before changing the gold."],
        }
    )
    report = make_review_report(
        [record],
        {
            case.question_id: {
                "issue_category": "source_conflict",
                "triage_summary": "Inspect the release note.",
            }
        },
    )
    finding = report["findings"][0]
    assert finding["original_gold_answer"] == case.reference_answer
    assert finding["proposed_correct_answer"] == draft.correct_answer
    assert finding["evidence_documents"] == [
        doc.model_dump() for doc in case.reference_documents
    ]
    assert report["original_gold_answers_modified"] is False


def test_gold_report_rejects_missing_triage(
    case: CaseInput, draft: RubricDraft
) -> None:
    """Prevent a gold-answer issue from silently disappearing from the review.

    Args:
        case: Source-linked private question to include in the report.
        draft: Review output carrying a source discrepancy requiring triage.
    """
    record = (
        case.model_dump()
        | draft.model_dump()
        | {"reference_status": "conflicted", "reference_notes": ["Check release-note."]}
    )
    with pytest.raises(ValueError, match="exactly the flagged"):
        make_review_report([record], {})
