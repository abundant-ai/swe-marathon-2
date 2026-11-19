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


@pytest.mark.parametrize("score", [0, 0.5, 1])
def test_citation_judge_cannot_supply_a_score(score: float) -> None:
    """Reject model-owned scoring even when every other output field is valid.

    Args:
        score: A previously accepted band that must now be an extra field.
    """
    with pytest.raises(ValidationError, match="Extra inputs"):
        CitationRating.model_validate({"score": score, "reason": "No factual claims.", "claims": []})


@pytest.mark.parametrize("secondary_support,expected", [
    ("supported", 100), ("unverified", 50), ("contradicted", 50),
])
def test_supported_core_and_secondary_claim_compute_exact_band(
    source: SourceDocument, secondary_support: str, expected: int,
) -> None:
    """Award full credit only when all claims have support, including secondary claims.

    Args:
        source: Authoritative record for evidence provenance.
        secondary_support: Semantic label supplied for a secondary detail.
        expected: Exact deterministic percentage, without a model-proposed cap.
    """
    evidence = [{"citation_index": 0, "doc_id": "d", "excerpt": source["content"]}]
    rating = CitationRating.model_validate({"reason": "Controlled assessments", "claims": [
        {"claim": "Mira approved.", "importance": "central", "support": "supported",
         "evidence": evidence, "reason": "Explicit."},
        {"claim": "Approval was Friday.", "importance": "secondary", "support": secondary_support,
         "evidence": evidence if secondary_support != "unverified" else [], "reason": "Controlled detail."},
    ]})
    result = finalize_citation_judgment(rating, "test", [{"doc_id": "d", "quote": source["content"]}], [source])
    assert result.score == expected
    assert "score" not in rating.model_dump()


@pytest.mark.parametrize("support", ["unverified", "contradicted", "empty"])
def test_no_supported_material_claims_forces_zero(source: SourceDocument, support: str) -> None:
    """Compute zero when all assessed material claims lack support.

    Args:
        source: Authoritative citation source.
        support: No claims, unverified claims, or evidence contradicting a claim.
    """
    claims = [] if support == "empty" else [{
        "claim": "Tao approved.", "importance": "central", "support": support,
        "evidence": [{"citation_index": 0, "doc_id": "d", "excerpt": "Mira approved"}] if support == "contradicted" else [],
        "reason": "No supporting evidence.",
    }]
    rating = CitationRating.model_validate({"reason": "Original provider explanation", "claims": claims})
    result = finalize_citation_judgment(rating, "response-1", [{"doc_id": "d", "quote": "Mira approved on Friday."}], [source])
    assert result.score == 0
    assert result.adjustment == "no_supported_material_claims"
    assert result.reason == rating.reason and result.response_id == "response-1"
    assert len(result.claims) == len(claims)
    assert "proposed_score" not in json.loads(json.dumps(asdict(result)))


@pytest.mark.parametrize("importance", ["central", "secondary"])
def test_mixed_claim_support_computes_half_credit(source: SourceDocument, importance: str) -> None:
    """Compute half credit when support is mixed, independent of claim importance.

    Args:
        source: Original source record.
        importance: Either kind of material factual claim can establish some support.
    """
    rating = CitationRating.model_validate({"reason": "Some support", "claims": [
        {"claim": "Mira approved.", "importance": importance, "support": "supported",
         "evidence": [{"citation_index": 0, "doc_id": "d", "excerpt": "Mira approved"}], "reason": "Explicit in source."},
        {"claim": "Tao approved.", "importance": "central", "support": "unverified", "evidence": [], "reason": "Absent."},
    ]})
    result = finalize_citation_judgment(rating, "response-2", [{"doc_id": "d", "quote": "Mira approved on Friday."}], [source])
    assert result.score == 50
    assert result.adjustment == "unsupported_material_claims"
    assert result.claims[0].evidence[0].doc_id == "d"


@pytest.mark.parametrize("mutation", ["missing_evidence", "bad_support", "blank_claim", "blank_reason", "negative_index", "boolean_index", "extra_field"])
def test_malformed_claim_assessment_is_rejected(mutation: str) -> None:
    """Reject malformed model assessments rather than treating them as wrong answers.

    Args:
        mutation: Structural defect injected into an otherwise valid supported claim.
    """
    claim = {"claim": "Mira approved", "importance": "central", "support": "supported",
             "evidence": [{"citation_index": 0, "doc_id": "d", "excerpt": "Mira approved"}], "reason": "Explicit."}
    if mutation == "missing_evidence":
        claim["evidence"] = []
    elif mutation == "bad_support":
        claim["support"] = "maybe"
    elif mutation == "blank_claim":
        claim["claim"] = " "
    elif mutation == "blank_reason":
        claim["reason"] = " "
    elif mutation in ("negative_index", "boolean_index"):
        claim["evidence"] = [{"citation_index": -1 if mutation == "negative_index" else True, "doc_id": "d", "excerpt": "Mira approved"}]
    else:
        claim["invented"] = True
    with pytest.raises(ValidationError):
        CitationRating.model_validate({"reason": "Controlled", "claims": [claim]})


@pytest.mark.parametrize("mutation", ["absent_index", "wrong_document", "absent_document", "fabricated_quote", "uncited_excerpt"])
def test_evidence_references_must_match_trusted_inputs(source: SourceDocument, mutation: str) -> None:
    """Reject invented references even when the model labels a claim supported.

    Args:
        source: Trusted original record.
        mutation: Reference or quotation mismatch that must invalidate evaluation.
    """
    rating = CitationRating.model_validate({"reason": "Controlled", "claims": [{
        "claim": "Mira approved.", "importance": "central", "support": "supported", "reason": "Explicit.",
        "evidence": [{"citation_index": 1 if mutation == "absent_index" else 0,
                      "doc_id": "invented" if mutation == "wrong_document" else "d", "excerpt": "Mira approved"}],
    }]})
    quote = "fabricated" if mutation == "fabricated_quote" else source["content"]
    if mutation == "uncited_excerpt":
        quote = "Friday."
    with pytest.raises(EvaluationError):
        finalize_citation_judgment(rating, "response", [{"doc_id": "d", "quote": quote}],
                                   [] if mutation == "absent_document" else [source])


def test_supported_detail_cannot_override_a_contradicted_central_claim(source: SourceDocument) -> None:
    """Enforce the zero band when the judge's own assessment refutes the central answer.

    Args:
        source: Trusted source supporting the date and contradicting the named approver.
    """
    evidence = [{"citation_index": 0, "doc_id": "d", "excerpt": "Mira approved on Friday."}]
    rating = CitationRating.model_validate({"reason": "Central contradiction", "claims": [
        {"claim": "Approval happened Friday.", "importance": "secondary", "support": "supported",
         "evidence": evidence, "reason": "Date appears in the quotation."},
        {"claim": "Tao was the approver.", "importance": "central", "support": "contradicted",
         "evidence": evidence, "reason": "The named approver is Mira."},
    ]})
    result = finalize_citation_judgment(rating, "test", [{"doc_id": "d", "quote": source["content"]}], [source])
    assert result.score == 0
    assert result.adjustment == "central_claim_contradicted"
