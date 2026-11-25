"""Validate claim evidence references and enforce citation scoring invariants."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import ModelRetry, RunContext

from verifier.contracts import (
    ClaimAssessment,
    ClaimEvidence,
    EvaluationError,
    Judgment,
    SourceDocument,
)
from verifier.judging.schemas import CitationRating


@dataclass(frozen=True)
class CitationInputs:
    """Trusted request evidence for validating structured citation assessments."""

    citations: list[dict[str, str]]
    documents: list[SourceDocument]


def retry_invalid_citation(
    context: RunContext[CitationInputs], rating: CitationRating
) -> CitationRating:
    """Repair fabricated or mislocated evidence within the configured output budget.

    Args:
        context: Trusted quotations and original documents for this request.
        rating: Provider output that passed the structural schema.

    Returns:
        The unchanged rating after request-specific evidence validation.

    Raises:
        ModelRetry: An evidence reference or excerpt does not match the inputs.
    """
    try:
        finalize_citation_judgment(
            rating, "validation", context.deps.citations, context.deps.documents
        )
    except EvaluationError as error:
        raise ModelRetry(str(error)) from error
    return rating


def finalize_citation_judgment(
    rating: CitationRating,
    response_id: str,
    citations: list[dict[str, str]],
    documents: list[SourceDocument],
) -> Judgment:
    """Compute citation credit entirely from validated claim assessments.

    Args:
        rating: Validated structured output from the citation judge.
        response_id: Provider trace identifier.
        citations: Candidate quotations sent to the judge, in original order.
        documents: Authoritative originals supplied alongside those quotations.

    Returns:
        Computed percentage and full claim audit: zero for no support or a central
        contradiction, fifty for mixed support, and one hundred for full support.

    Raises:
        EvaluationError: The judge references an absent citation, mismatched
            document, or quotation without authoritative provenance. This is a
            judge-output failure, not a wrong-answer score.
    """
    originals = {document["doc_id"]: document for document in documents}
    claims: list[ClaimAssessment] = []
    for claim in rating.claims:
        references: list[ClaimEvidence] = []
        for evidence in claim.evidence:
            if evidence.citation_index >= len(citations):
                raise EvaluationError("Citation judge referenced an absent citation")
            citation = citations[evidence.citation_index]
            original = originals.get(evidence.doc_id)
            if citation["doc_id"] != evidence.doc_id or original is None:
                raise EvaluationError(
                    "Citation judge evidence document does not match the supplied citation"
                )
            quote = citation["quote"]
            if not quote.strip() or not (
                quote in original["content"] or quote in original["title"]
            ):
                raise EvaluationError(
                    "Citation judge evidence has no authoritative quotation provenance"
                )
            if not evidence.excerpt.strip():
                raise EvaluationError("Citation judge evidence excerpt is blank")
            allowed = (
                (quote,)
                if claim.support == "supported"
                else (original["content"], original["title"])
            )
            if not any(evidence.excerpt in source for source in allowed):
                raise EvaluationError(
                    "A supported claim needs an exact excerpt from the candidate quotation; context alone cannot supply support"
                )
            references.append(
                ClaimEvidence(
                    evidence.citation_index, evidence.doc_id, evidence.excerpt
                )
            )
        claims.append(
            ClaimAssessment(
                claim.claim,
                claim.importance,
                claim.support,
                tuple(references),
                claim.reason,
            )
        )
    supported = any(claim.support == "supported" for claim in claims)
    central_contradiction = any(
        claim.importance == "central" and claim.support == "contradicted"
        for claim in claims
    )
    if not supported or central_contradiction:
        adjustment = (
            "no_supported_material_claims"
            if not supported
            else "central_claim_contradicted"
        )
        return Judgment(0, rating.reason, response_id, tuple(claims), adjustment)
    incomplete = any(claim.support != "supported" for claim in claims)
    score = 50 if incomplete else 100
    return Judgment(
        score,
        rating.reason,
        response_id,
        tuple(claims),
        "unsupported_material_claims" if incomplete else None,
    )
