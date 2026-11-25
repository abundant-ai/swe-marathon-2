"""Check coverage and source integrity of the author-only rubric quality audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from factual_rubrics.models import CaseInput, Grounding, RubricDraft, SourceDocument
from factual_rubrics.quality_models import (
    QualityInput,
    QualityIssue,
    RubricQualityAudit,
    RuleAssessment,
    validate_quality_audit,
)
from factual_rubrics.quality_report import export_report
from pydantic import ValidationError


@pytest.fixture
def quality_case() -> tuple[QualityInput, RubricQualityAudit]:
    """Build a conditional-only original and a grounded mandatory-core proposal.

    Returns:
        Original question evidence and a structurally valid proposed repair.
    """
    original = QualityInput(
        case=CaseInput(
            question_id="q",
            question="Who owns the release?",
            reference_answer="Maya",
            reference_documents=[
                SourceDocument(
                    doc_id="d",
                    title="Release",
                    source_type="document",
                    content="Maya owns the release. The deadline is Friday.",
                )
            ],
        ),
        original_rubric=['must name "Maya" if identifying the owner.'],
    )
    audit = RubricQualityAudit(
        original_assessments=[
            RuleAssessment(
                rubric_index=0, kind="conditional_guard", reason="Owner is optional."
            )
        ],
        original_issues=[
            QualityIssue(
                code="no_required_fact",
                rubric_indices=[],
                explanation="No answer is demanded.",
            )
        ],
        revised=RubricDraft(
            correct_answer="Maya owns the release.",
            rubric=[
                'must identify "Maya" as the release owner.',
                'must give "Friday" if mentioning the deadline.',
            ],
            grounding=[
                Grounding(rubric_index=0, doc_id="d", quote="Maya owns the release."),
                Grounding(rubric_index=1, doc_id="d", quote="The deadline is Friday."),
            ],
            reference_status="supported",
            reference_notes=[],
            review_notes=[],
        ),
        required_indices=[0],
        guard_indices=[1],
        core_justification="The question asks for the owner.",
    )
    return original, audit


def test_quality_audit_accepts_grounded_core(
    quality_case: tuple[QualityInput, RubricQualityAudit],
) -> None:
    """Accept mandatory answer content with a separate optional error guard.

    Args:
        quality_case: Grounded original and revised rubric fixture.
    """
    original, audit = quality_case
    assert validate_quality_audit(audit, original) is audit


@pytest.mark.parametrize(
    "defect",
    [
        "missing_original",
        "duplicate_original",
        "missing_partition",
        "overlapping_partition",
        "missing_finding",
        "bad_quote",
    ],
)
def test_quality_audit_rejects_incomplete_or_ungrounded_review(
    quality_case: tuple[QualityInput, RubricQualityAudit],
    defect: str,
) -> None:
    """Reject incomplete review coverage and invalid quote provenance.

    Args:
        quality_case: Valid audit to mutate independently for each test.
        defect: Review-structure or source-integrity failure to exercise.
    """
    original, audit = quality_case
    payload = audit.model_dump()
    if defect == "missing_original":
        payload["original_assessments"] = []
    elif defect == "duplicate_original":
        payload["original_assessments"] *= 2
    elif defect == "missing_partition":
        payload["guard_indices"] = []
    elif defect == "overlapping_partition":
        payload["guard_indices"] = [0, 1]
    elif defect == "missing_finding":
        payload["original_issues"] = []
    else:
        payload["revised"]["grounding"][0]["quote"] = "Invented quote."
    with pytest.raises(ValueError):
        validate_quality_audit(RubricQualityAudit.model_validate(payload), original)


@pytest.mark.parametrize(
    "rule",
    [
        'must name "Maya" if identifying the owner.',
        'must not name anyone except "Maya".',
        'must attribute any mentioned release ownership to "Maya".',
    ],
)
def test_quality_audit_rejects_guard_as_mandatory(
    quality_case: tuple[QualityInput, RubricQualityAudit],
    rule: str,
) -> None:
    """Prevent obvious conditional or negative-only rules from becoming the core.

    Args:
        quality_case: Valid audit whose first rule is designated mandatory.
        rule: A guard that could pass without demonstrating an answer.
    """
    original, audit = quality_case
    payload = audit.model_dump()
    payload["revised"]["rubric"][0] = rule
    with pytest.raises(ValueError, match="Mandatory facts"):
        validate_quality_audit(RubricQualityAudit.model_validate(payload), original)


def test_quality_schema_rejects_empty_mandatory_core(
    quality_case: tuple[QualityInput, RubricQualityAudit],
) -> None:
    """Require an explicit nonempty list of mandatory factual requirements.

    Args:
        quality_case: Valid audit before removing its mandatory core.
    """
    _, audit = quality_case
    payload = audit.model_dump()
    payload["required_indices"] = []
    with pytest.raises(ValidationError):
        RubricQualityAudit.model_validate(payload)


def test_quality_report_preserves_required_guard_distinction(
    quality_case: tuple[QualityInput, RubricQualityAudit],
    tmp_path: Path,
) -> None:
    """Keep original defects separate from corrected proposals in the report.

    Args:
        quality_case: One conditional original and a core-plus-guard proposal.
        tmp_path: Isolated author-output directory supplied by pytest.
    """
    original, audit = quality_case
    (tmp_path / "inputs.json").write_text(json.dumps([original.model_dump()]))
    (tmp_path / "records").mkdir()
    (tmp_path / "records/000.json").write_text(
        json.dumps({"question_id": "q", "audit": audit.model_dump()})
    )
    summary = export_report(tmp_path)
    assert summary["questions_without_original_required_fact"] == 1
    assert summary["questions_without_proposed_required_fact"] == 0
    assert summary["proposed_required_rules"] == summary["proposed_guard_rules"] == 1
    assert summary["active_evaluation_changed"] is False
    text = (tmp_path / "all-rubrics.md").read_text()
    assert 'Rule 1: must identify "Maya"' in text
    assert 'Rule 2: must give "Friday"' in text


def test_quality_report_refuses_partial_review(
    quality_case: tuple[QualityInput, RubricQualityAudit],
    tmp_path: Path,
) -> None:
    """Prevent a partial audit from producing a complete-review report.

    Args:
        quality_case: Expected input whose review checkpoint is absent.
        tmp_path: Isolated author-output directory supplied by pytest.
    """
    original, _ = quality_case
    (tmp_path / "inputs.json").write_text(json.dumps([original.model_dump()]))
    with pytest.raises(FileNotFoundError):
        export_report(tmp_path)
    assert not (tmp_path / "quality-review.md").exists()


@pytest.mark.parametrize("disclosed", [True, False])
def test_quality_report_requires_local_review_disclosure(
    quality_case: tuple[QualityInput, RubricQualityAudit],
    tmp_path: Path,
    disclosed: bool,
) -> None:
    """Accept local completion only when its different review method is explicit.

    Args:
        quality_case: Source-grounded local review used as a fallback.
        tmp_path: Isolated author-output directory supplied by pytest.
        disclosed: Whether the fallback truthfully names its local review method.
    """
    original, audit = quality_case
    (tmp_path / "inputs.json").write_text(json.dumps([original.model_dump()]))
    (tmp_path / "local-records").mkdir()
    record = {"question_id": "q", "audit": audit.model_dump()}
    if disclosed:
        record["review_method"] = "local_codex_source_review_after_api_quota"
    (tmp_path / "local-records/000.json").write_text(json.dumps(record))
    if not disclosed:
        with pytest.raises(ValueError, match="disclose"):
            export_report(tmp_path)
        return
    summary = export_report(tmp_path)
    assert summary["review_methods"] == {"local_codex_source_review_after_api_quota": 1}
    proposed = json.loads((tmp_path / "proposed_rubrics.json").read_text())
    assert proposed[0]["review_method"] == "local_codex_source_review_after_api_quota"
