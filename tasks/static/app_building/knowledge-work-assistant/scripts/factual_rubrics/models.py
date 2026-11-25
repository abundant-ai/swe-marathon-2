"""Typed authoring outputs and source-grounding validation for private rubrics."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceDocument(BaseModel):
    """Original private corpus record, copied without changing its contents."""

    doc_id: str
    title: str
    content: str
    source_type: str


class CaseInput(BaseModel):
    """Question, untouched dataset reference, and all mapped source records."""

    question_id: str
    question: str
    reference_answer: str | list[str]
    reference_documents: list[SourceDocument]
    supplemental_reference_doc_ids: list[str] = Field(default_factory=list)


class Grounding(BaseModel):
    """Exact source excerpt supporting a factual condition in a rubric."""

    model_config = ConfigDict(extra="forbid")
    rubric_index: int = Field(
        ge=0, description="Zero-based index of the supported rubric item."
    )
    doc_id: str = Field(
        description="Original document ID, or $reference for the unchanged gold answer."
    )
    quote: str = Field(
        min_length=1,
        description="Exact contiguous excerpt from original title, content, or gold answer.",
    )


class RubricDraft(BaseModel):
    """Structured authoring/review result; the rubric itself stays list[str]."""

    model_config = ConfigDict(extra="forbid")
    correct_answer: str = Field(
        min_length=1,
        description="Evidence-grounded example answer, qualified where sources conflict; not an exhaustive mandatory answer.",
    )
    rubric: list[str] = Field(
        min_length=1,
        description="One short sentence per item, starting with lowercase 'must ', targeting ONE factual point and including an exact source/gold excerpt in double quotes. Optional details are conditional; no completeness checklist.",
    )
    grounding: list[Grounding] = Field(
        min_length=1,
        description="Exact excerpts grounding EVERY rubric item, with its zero-based index and original source ID or $reference.",
    )
    reference_status: Literal["supported", "conflicted", "insufficient"] = Field(
        description="Whether the original dataset answer is supported, conflicts with sources, or lacks enough source support. This is not a candidate-answer grade."
    )
    reference_notes: list[str] = Field(
        description="Specific discrepancies or limitations, with source IDs. Empty when none exist."
    )
    review_notes: list[str] = Field(
        description="Brief corrections or checks performed; do not claim human review or certainty beyond the supplied documents."
    )

    @field_validator("rubric")
    @classmethod
    def validate_must_rules(cls, rules: list[str]) -> list[str]:
        """Require the user's exact list syntax and prevent duplicate conditions.

        Args:
            rules: Proposed private conditions returned by the authoring model.

        Returns:
            The unchanged list after checking nonempty lowercase must statements.

        Raises:
            ValueError: An item is malformed, repeated, or contains no condition.
        """
        if any(not rule.startswith("must ") or not rule[5:].strip() for rule in rules):
            raise ValueError(
                "Every rubric item must start with lowercase 'must ' followed by a condition"
            )
        if any(
            "\n" in rule or "\r" in rule or not re.findall(r'"([^"\n]+)"', rule)
            for rule in rules
        ):
            raise ValueError(
                "Every item must be one line with an exact excerpt in double quotes"
            )
        if len(set(rules)) != len(rules):
            raise ValueError("Rubric conditions must be unique")
        return rules


def validate_grounding(draft: RubricDraft, case: CaseInput) -> RubricDraft:
    """Check reference provenance before accepting a generated or reviewed record.

    Args:
        draft: Typed model output, not yet trusted as source-grounded.
        case: Original question and complete linked documents.

    Returns:
        The unchanged draft if every quoted excerpt exists in its stated source.

    Raises:
        ValueError: A source, rubric index, or exact quotation is invalid, or a
            flagged reference has no explanation. Semantic support still needs
            separate model review and eventual human calibration.
    """
    documents = {doc.doc_id: doc for doc in case.reference_documents}
    reference = (
        case.reference_answer
        if isinstance(case.reference_answer, str)
        else "\n".join(case.reference_answer)
    )
    for item in draft.grounding:
        doc = documents.get(item.doc_id)
        if (doc is None and item.doc_id != "$reference") or item.rubric_index >= len(
            draft.rubric
        ):
            raise ValueError("Grounding refers to an unknown document or rubric index")
        originals = (
            (reference,) if item.doc_id == "$reference" else (doc.content, doc.title)
        )
        if not any(item.quote in original for original in originals):
            raise ValueError(f"Quotation is not verbatim in {item.doc_id}")
    for index, rule in enumerate(draft.rubric):
        linked_quotes = [
            item.quote for item in draft.grounding if item.rubric_index == index
        ]
        for quote in re.findall(r'"([^"\n]+)"', rule):
            if not any(quote in linked for linked in linked_quotes):
                raise ValueError(
                    f"Inline quote in rubric {index} lacks matching exact grounding: {quote}"
                )
    if draft.reference_status != "supported" and not draft.reference_notes:
        raise ValueError(
            "Conflicted or insufficient references require source-specific notes"
        )
    return draft
