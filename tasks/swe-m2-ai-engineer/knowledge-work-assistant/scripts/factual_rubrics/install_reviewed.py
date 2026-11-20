"""Install complete source-audited rubrics without changing questions or corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .codex_review import validate_final
from .finalize import apply_calibration_repairs
from .models import CaseInput, RubricDraft, SourceDocument


def reviewed_rows(private: Path, inputs: Path, audits: Path, repairs: Path) -> list[dict[str, Any]]:
    """Authenticate every source anchor and preserve the original case association.

    Args:
        private: Current runtime corpus and rubric files.
        inputs: Immutable original question and linked-source authoring inputs.
        audits: Complete Codex source-audit checkpoint directory.
        repairs: Narrow, evidence-reviewed calibration wording corrections.

    Returns:
        Runtime rubric rows in the original order, with source-review provenance.

    Raises:
        ValueError: Coverage, original association, or source grounding differs.
    """
    cases = [CaseInput.model_validate(row["case"]) for row in json.loads(inputs.read_text())]
    current = json.loads((private / "rubrics.json").read_text())
    previous = {row["question_id"]: row for row in current}
    records = [json.loads(path.read_text()) for path in sorted(audits.glob("audit-*.json"))]
    indexed = {row["question_id"]: row for row in records}
    expected = {case.question_id for case in cases}
    if (len(expected) != len(cases) or len(indexed) != len(records) or len(previous) != len(current)
            or set(indexed) != expected or set(previous) != expected):
        raise ValueError("Installation requires exactly one source audit for every active question")
    provenance = json.loads((audits / "provenance.json").read_text())
    if (provenance["inputs_sha256"] != hashlib.sha256(inputs.read_bytes()).hexdigest()
            or provenance["corpus_sha256"] != hashlib.sha256((private / "corpus.json").read_bytes()).hexdigest()):
        raise ValueError("Source-audit input hashes no longer match")
    documents = {row["doc_id"]: row for row in json.loads((private / "corpus.json").read_text())}
    corrections = json.loads(repairs.read_text())
    if not set(corrections).issubset(expected):
        raise ValueError("A repair refers to an inactive question")
    rows = []
    for case in cases:
        old, record = previous[case.question_id], indexed[case.question_id]
        if old["question"] != case.question or old["reference"] != case.reference_answer:
            raise ValueError("Original question or reference association changed")
        draft = apply_calibration_repairs(RubricDraft.model_validate(record["audit"]["revised"]), case.question_id, corrections)
        identities = set(record["source_doc_ids"]) | {item.doc_id for item in draft.grounding if item.doc_id != "$reference"}
        sources = [SourceDocument.model_validate(documents[identity]) for identity in sorted(identities)]
        grounded = case.model_copy(update={"reference_documents": sources})
        validate_final(draft, grounded)
        rows.append({**old, "reviewed_reference": draft.correct_answer, "rubric": draft.rubric,
                     "required_indices": [0], "guard_indices": list(range(1, len(draft.rubric))),
                     "grounding": [item.model_dump() for item in draft.grounding],
                     "reference_status": draft.reference_status, "reference_notes": draft.reference_notes,
                     "review_notes": draft.review_notes, "review_method": "codex_full_source_review_and_oracle_audit",
                     "review_call_id": record["review_call_id"], "audit_call_id": record["call_id"],
                     "local_repair": corrections.get(case.question_id),
                     "live_calibration_status": "see_author_calibration_report"})
    return rows


def main() -> None:
    """Validate all reviews, back up replaced artifacts, and update the rubric hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--audits", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repairs", type=Path, default=Path(__file__).with_name("source_review_repairs.json"))
    args = parser.parse_args()
    rows = reviewed_rows(args.private, args.inputs, args.audits, args.repairs)
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("rubrics.json", "manifest.json"):
        backup = args.output / f"before-install-{name}"
        if not backup.exists():
            backup.write_bytes((args.private / name).read_bytes())
    payload = (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode()
    digest = hashlib.sha256(payload).hexdigest()
    manifest = json.loads((args.private / "manifest.json").read_text())
    manifest.update({"rubrics_sha256": digest, "rubric_scoring": "weighted_required_conditional_v2"})
    (args.output / "rubrics.json").write_bytes(payload)
    (args.private / "rubrics.json").write_bytes(payload)
    (args.private / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"questions": len(rows), "rules": sum(len(row["rubric"]) for row in rows), "sha256": digest}))


if __name__ == "__main__":
    main()
