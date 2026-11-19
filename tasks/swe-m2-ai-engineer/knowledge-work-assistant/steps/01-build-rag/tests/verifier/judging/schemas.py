"""Strict provider-output schemas, separate from verifier audit records."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from verifier.contracts import ClaimImportance, ClaimSupport

CitationScoreBand = Literal[0.0, 0.5, 1.0]


class AssessmentBase(BaseModel):
    """Shared explanation validation for decision-only citation outputs."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    reason: str = Field(min_length=1, description=(
        "Explain the supported, unsupported, or contradicted claims "
        "and the relevant document IDs. Explain any misleading quotation in its original context."
    ))

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        """Require an explanation with substantive text.

        Args:
            value: Provider's explanation after string validation.

        Returns:
            The original explanation, preserving its wording.

        Raises:
            ValueError: The explanation contains only whitespace.
        """
        if not value.strip():
            raise ValueError("reason must contain non-whitespace text")
        return value


class CitationEvidence(BaseModel):
    """Pin the assessment to a verifiable excerpt of the candidate's quotation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    citation_index: int = Field(ge=0, description="Zero-based index into the supplied citations array.")
    doc_id: str = Field(min_length=1, description="Document ID of that same supplied citation; do not invent IDs.")
    excerpt: str = Field(min_length=1, description=(
        "Exact contiguous text establishing this assessment. For a supported claim, copy it from the "
        "candidate's quotation at citation_index, never from uncited text elsewhere in the original. "
        "For contradicted or unverified claims, an exact excerpt of the original document is allowed."
    ))


class CitationClaim(BaseModel):
    """Assessment of one material claim; Python computes the overall score."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim: str = Field(min_length=1, description=(
        "One atomic material factual claim actually made in the candidate answer. "
        "Include factual additions and role, date, entity, or number qualifications. "
        "Exclude generic topic overlap, politeness, facts absent from the answer, and assertions "
        "explicitly retracted and replaced by a correction. Assess the corrected assertion."
    ))
    importance: ClaimImportance = Field(description=(
        "central if needed to answer the question; secondary for another substantive factual assertion. "
        "Both are material claims. A generic acknowledgment is not a supported secondary claim."
    ))
    support: ClaimSupport = Field(description=(
        "supported only if supplied quotations establish this claim in their original context; "
        "contradicted if that context conflicts with the claim; unverified if it establishes neither. "
        "A quotation about the same topic or saying 'sounds like a solid plan' does not establish specific facts."
    ))
    evidence: list[CitationEvidence] = Field(description=(
        "References to supplied quotations supporting or contradicting the claim. "
        "Every supported or contradicted claim needs at least one reference. "
        "Use an empty list for an unverified claim when no quotation bears on it."
    ))
    reason: str = Field(min_length=1, description="Explain briefly how the referenced evidence does or does not establish this claim.")

    @field_validator("claim", "reason")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Reject empty assessments disguised as whitespace.

        Args:
            value: Claim or explanation supplied by the provider.

        Returns:
            Original nonblank text.

        Raises:
            ValueError: No substantive text was supplied.
        """
        if not value.strip():
            raise ValueError("Claim and reason must contain non-whitespace text")
        return value

    @model_validator(mode="after")
    def require_evidence(self) -> Self:
        """Require traceable evidence for supported and contradicted classifications.

        Returns:
            Validated assessment; reference existence is checked against inputs later.

        Raises:
            ValueError: A supported or contradicted claim has no evidence reference.
        """
        if self.support != "unverified" and not self.evidence:
            raise ValueError("Supported or contradicted claims require evidence")
        return self


class CitationRating(AssessmentBase):
    """Claim decisions only; the verifier owns all numerical citation scoring."""

    claims: list[CitationClaim] = Field(description=(
        "Assess every material factual claim actually made in the answer. "
        "An empty list is appropriate only when the answer makes no material factual claims. "
        "Return claim assessments and an explanation, without a numerical score or band. "
        "The verifier computes citation credit from the final support decisions."
    ))


class CriterionRating(BaseModel):
    """One factual decision; arithmetic and applicability are checked by Python."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    rubric_index: int = Field(ge=0, description="Zero-based index in the supplied must-have list; assess every index exactly once.")
    status: Literal["passed", "failed", "not_applicable"] = Field(description=(
        "For a required point: passed means the candidate states the substantive fact or an accepted alternative; "
        "failed means wrong or absent. Required points cannot be not_applicable. "
        "For an optional condition: passed means a present claim satisfies it; failed means a present claim "
        "demonstrably violates it; not_applicable means the claim is absent or cannot be checked against supplied facts. "
        "An unverified addition is not a demonstrated error. Never award credit for a fact present only in the reference."
    ))
    candidate_quote: str = Field(description=(
        "Exact contiguous excerpt from the candidate answer bearing on this decision. "
        "Required for passed decisions and failed optional conditions; empty for an omitted required fact "
        "or an absent optional claim. Do not quote the reference as candidate evidence."
    ))
    reason: str = Field(min_length=1, description=(
        "Explain the factual match, omission, or contradiction for this one point, accepting paraphrases. "
        "Distinguish a false claim from an unverified one. Do not assess style or optional coverage."
    ))
    duplicate_of: int | None = Field(description=(
        "Index of an earlier failed point assessing exactly the same false assertion, otherwise null. "
        "This is audit metadata; every applicable rubric item still counts in scoring. "
        "Only failed optional points can be duplicates. Reuse its exact candidate_quote; "
        "independent errors in the same sentence are not duplicates."
    ))

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        """Reject empty reasoning in provider assessments.

        Args:
            value: Provider explanation for one criterion.

        Returns:
            Original nonblank explanation.

        Raises:
            ValueError: The explanation is whitespace only.
        """
        if not value.strip():
            raise ValueError("Criterion reason must contain text")
        return value


class AnswerRating(BaseModel):
    """Structured factual decisions; the model cannot choose an aggregate score."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    criteria: list[CriterionRating] = Field(min_length=1, description=(
        "Assess every supplied rubric index exactly once. Required indices are trusted metadata. "
        "Required and applicable conditional items are scored in separate groups. "
        "Passed conditional items earn credit; not_applicable items are excluded from that group. "
        "Return per-item decisions only, without a numerical score or overall verdict. "
        "The verifier calculates the aggregate accuracy and verdict."
    ))
    unverified_claims: list[str] = Field(description=(
        "Exact excerpts of material candidate claims the supplied rubric and reference cannot establish or refute. "
        "These are audit notes, not factual errors or invented additional criteria. Use an empty list if none."
    ))
