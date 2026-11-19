"""Keep source-review concerns separate from unchanged dataset references."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def make_review_report(records: Sequence[Mapping[str, Any]],
                       triage: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    """Join reviewed reference concerns to explicit author triage.

    Called after rubric authoring to preserve the original reference and source
    evidence alongside a proposed correction. This report never changes the
    dataset or accepts a correction automatically.

    Args:
        records: Exported question, original reference, source, and review records.
        triage: One issue category and explanation for each flagged question ID.

    Returns:
        A report of flagged findings and an explicit unchanged-reference marker.

    Raises:
        ValueError: IDs repeat, triage coverage differs from flagged questions,
            or a triage entry lacks its category or explanation.
    """
    identities = [record["question_id"] for record in records]
    if len(set(identities)) != len(identities):
        raise ValueError("Reference review requires unique question IDs")
    flagged = [record for record in records if record["reference_status"] != "supported"]
    if set(triage) != {record["question_id"] for record in flagged}:
        raise ValueError("Triage must cover exactly the flagged questions")
    findings = []
    for record in flagged:
        decision = triage[record["question_id"]]
        if any(not decision.get(key, "").strip() for key in ("issue_category", "triage_summary")):
            raise ValueError("Every triage entry needs a category and explanation")
        findings.append({
            "question_id": record["question_id"], "question": record["question"],
            "original_gold_answer": record["reference_answer"],
            "proposed_correct_answer": record["correct_answer"],
            "evidence_documents": record["reference_documents"],
            "reference_status": record["reference_status"],
            "reference_notes": record["reference_notes"],
            "issue_category": decision["issue_category"],
            "triage_summary": decision["triage_summary"],
        })
    return {"original_gold_answers_modified": False, "findings": findings}
