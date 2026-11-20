"""Typed quality-review records for mandatory facts and conditional error checks."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import CaseInput, RubricDraft, validate_grounding


class RuleAssessment(BaseModel):
    """Semantic classification of one existing rule, with a short explanation."""

    model_config = ConfigDict(extra="forbid")
    rubric_index: int = Field(ge=0, description="Zero-based index in the original rubric.")
    kind: Literal["required_fact", "conditional_guard", "ambiguous"] = Field(
        description="Required facts demand substantive answer content; guards constrain optional claims; ambiguous rules need rewriting.")
    reason: str = Field(min_length=1, description="Why this rule does or does not require a substantive fact answering the question.")


class QualityIssue(BaseModel):
    """One actionable quality concern in the existing question rubric."""

    model_config = ConfigDict(extra="forbid")
    code: Literal[
        "no_required_fact", "weak_required_fact", "mixed_claims", "redundancy",
        "unsupported_fact", "overconstraint", "ambiguity", "irrelevance",
        "source_reference_concern", "missing_error_guard",
    ]
    rubric_indices: list[int] = Field(description="Affected original rule indices; empty for a whole-rubric omission.")
    explanation: str = Field(min_length=1, description="Concise concern tied to this question and, for factual concerns, source IDs.")


class QualityInput(BaseModel):
    """Immutable question evidence and the exact active rubric being audited."""

    case: CaseInput
    original_rubric: list[str]


class RubricQualityAudit(BaseModel):
    """Audit every old rule and propose a grounded rubric with a mandatory core."""

    model_config = ConfigDict(extra="forbid")
    original_assessments: list[RuleAssessment] = Field(description="Classify every original rule exactly once, preserving its index.")
    original_issues: list[QualityIssue]
    revised: RubricDraft = Field(description="Proposed corrected rubric, example answer, exact source grounding, and reference notes. Do not modify the active dataset.")
    required_indices: list[int] = Field(min_length=1, description="Indices of substantive unconditional required facts in the revised rubric; at least one per question.")
    guard_indices: list[int] = Field(description="All remaining revised indices: conditional checks which earn no credit when untriggered or satisfied, but penalize violations.")
    core_justification: str = Field(min_length=1, description="Explain why the mandatory facts directly answer this question without requiring optional details or an arbitrary exhaustive list.")


def validate_quality_audit(audit: RubricQualityAudit, original: QualityInput) -> RubricQualityAudit:
    """Check complete review coverage, nonvacuous core syntax, and exact provenance.

    Called after each model pass and again when exporting review artifacts.
    These checks establish structure and literal provenance, not semantic truth.

    Args:
        audit: Proposed or independently reviewed quality assessment.
        original: Active rules and original source records supplied to the reviewer.

    Returns:
        The unchanged audit if its associations and exact quotations validate.

    Raises:
        ValueError: A rule is omitted, duplicated, misclassified by obvious syntax,
            or associated with an invalid index or unsupported quotation.
    """
    original_indices = [item.rubric_index for item in audit.original_assessments]
    if sorted(original_indices) != list(range(len(original.original_rubric))):
        raise ValueError("Classify every original rubric index exactly once")
    for issue in audit.original_issues:
        if any(index < 0 or index >= len(original.original_rubric) for index in issue.rubric_indices):
            raise ValueError("Quality issue refers to a nonexistent original rubric index")
    if not any(item.kind == "required_fact" for item in audit.original_assessments):
        if not any(issue.code == "no_required_fact" for issue in audit.original_issues):
            raise ValueError("A rubric with no mandatory fact needs an explicit no_required_fact finding")
    if sorted(audit.required_indices + audit.guard_indices) != list(range(len(audit.revised.rubric))):
        raise ValueError("Required and guard indices must partition the revised rubric exactly once")
    for index in audit.required_indices:
        # 'if' inside an evidence quote can describe the domain, not an answer condition.
        rule = re.sub(r'"[^"\n]*"', '"QUOTE"', audit.revised.rubric[index]).lower()
        if (rule.startswith(("must not ", "must avoid ")) or
                re.search(r"\b(?:if|when)\b|\bany (?:mentioned|listed|included)\b", rule)):
            raise ValueError("Mandatory facts cannot be optional claim conditions or negative-only guards")
    validate_grounding(audit.revised, original.case)
    return audit
