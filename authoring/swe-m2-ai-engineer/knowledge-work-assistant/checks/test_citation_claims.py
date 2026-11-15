"""Verify structured claim validation and deterministic zero-support scoring."""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from pydantic import ValidationError

from verifier.contracts import EvaluationError, SourceDocument
from verifier.judging.citation_scoring import finalize_citation_judgment
from verifier.judging.schemas import CitationRating


@pytest.fixture
def source() -> SourceDocument:
    """Supply an authoritative record with one supporting quotation.

    Returns:
        Complete original record used by deterministic evidence-reference checks.
    """
    return {"doc_id": "d", "source_type": "document", "title": "Approval", "content": "Mira approved on Friday."}


@pytest.mark.parametrize("score", [0, .25, .5, .75, 1])
@pytest.mark.parametrize("support", ["unverified", "contradicted", "empty"])
def test_no_supported_material_claims_forces_zero(source: SourceDocument, score: float, support: str) -> None:
    """Zero every proposed band when all material claims lack support, retaining audit.

    Args:
        source: Authoritative citation source.
        score: Any model-proposed band, including contradictory nonzero proposals.
        support: No claims, unverified claims, or evidence contradicting a claim.
    """
    claims = [] if support == "empty" else [{
        "claim": "Tao approved.", "importance": "central", "support": support,
        "evidence": [{"citation_index": 0, "doc_id": "d"}] if support == "contradicted" else [],
        "reason": "No supporting evidence.",
    }]
    rating = CitationRating.model_validate({"score": score, "reason": "Original provider explanation", "claims": claims})
    result = finalize_citation_judgment(rating, "response-1", [{"doc_id": "d", "quote": "Mira approved on Friday."}], [source])
    assert result.score == 0
    assert result.proposed_score == round(score * 100)
    assert result.adjustment == "no_supported_material_claims"
    assert result.reason == rating.reason and result.response_id == "response-1"
    assert len(result.claims) == len(claims)
    assert json.loads(json.dumps(asdict(result)))["proposed_score"] == round(score * 100)


@pytest.mark.parametrize("importance", ["central", "secondary"])
@pytest.mark.parametrize("score", [0, .25, .5, .75, 1])
def test_supported_material_claim_preserves_proposed_band(source: SourceDocument, score: float, importance: str) -> None:
    """Retain the proposed band for real supporting evidence without forcing full credit.

    Args:
        source: Original source record.
        score: Proposed five-band score to preserve.
        importance: Either kind of material factual claim can establish some support.
    """
    rating = CitationRating.model_validate({"score": score, "reason": "Some support", "claims": [
        {"claim": "Mira approved.", "importance": importance, "support": "supported",
         "evidence": [{"citation_index": 0, "doc_id": "d"}], "reason": "Explicit in source."},
        {"claim": "Tao approved.", "importance": "central", "support": "unverified", "evidence": [], "reason": "Absent."},
    ]})
    result = finalize_citation_judgment(rating, "response-2", [{"doc_id": "d", "quote": "Mira approved on Friday."}], [source])
    assert result.score == result.proposed_score == round(score * 100)
    assert result.adjustment is None
    assert result.claims[0].evidence[0].doc_id == "d"


@pytest.mark.parametrize("mutation", ["missing_evidence", "bad_support", "blank_claim", "blank_reason", "negative_index", "boolean_index", "extra_field"])
def test_malformed_claim_assessment_is_rejected(mutation: str) -> None:
    """Reject malformed model assessments rather than treating them as wrong answers.

    Args:
        mutation: Structural defect injected into an otherwise valid supported claim.
    """
    claim = {"claim": "Mira approved", "importance": "central", "support": "supported",
             "evidence": [{"citation_index": 0, "doc_id": "d"}], "reason": "Explicit."}
    if mutation == "missing_evidence":
        claim["evidence"] = []
    elif mutation == "bad_support":
        claim["support"] = "maybe"
    elif mutation == "blank_claim":
        claim["claim"] = " "
    elif mutation == "blank_reason":
        claim["reason"] = " "
    elif mutation in ("negative_index", "boolean_index"):
        claim["evidence"] = [{"citation_index": -1 if mutation == "negative_index" else True, "doc_id": "d"}]
    else:
        claim["invented"] = True
    with pytest.raises(ValidationError):
        CitationRating.model_validate({"score": 1, "reason": "Controlled", "claims": [claim]})


@pytest.mark.parametrize("mutation", ["absent_index", "wrong_document", "absent_document", "fabricated_quote"])
def test_evidence_references_must_match_trusted_inputs(source: SourceDocument, mutation: str) -> None:
    """Reject invented references even when the model labels a claim supported.

    Args:
        source: Trusted original record.
        mutation: Reference or quotation mismatch that must invalidate evaluation.
    """
    rating = CitationRating.model_validate({"score": 1, "reason": "Controlled", "claims": [{
        "claim": "Mira approved.", "importance": "central", "support": "supported", "reason": "Explicit.",
        "evidence": [{"citation_index": 1 if mutation == "absent_index" else 0,
                      "doc_id": "invented" if mutation == "wrong_document" else "d"}],
    }]})
    quote = "fabricated" if mutation == "fabricated_quote" else source["content"]
    with pytest.raises(EvaluationError):
        finalize_citation_judgment(rating, "response", [{"doc_id": "d", "quote": quote}],
                                   [] if mutation == "absent_document" else [source])
