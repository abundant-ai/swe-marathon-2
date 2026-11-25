"""Build deployable factual rubrics from source-reviewed drafts and local repairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .models import CaseInput, Grounding, RubricDraft, validate_grounding


def apply_calibration_repairs(
    draft: RubricDraft, question_id: str, repairs: dict[str, Any]
) -> RubricDraft:
    """Apply narrowly reviewed wording fixes without changing source anchors.

    Args:
        draft: Source-audited rubric before local calibration fixes.
        question_id: Original stable identity selecting an optional repair.
        repairs: Explicit old/new wording and factual rationale per question.

    Returns:
        A new draft with repair provenance; unchanged when no repair applies.

    Raises:
        ValueError: Expected source wording changed or a replacement invents an anchor.
    """
    if question_id not in repairs:
        return draft
    repair = repairs[question_id]
    rules = list(draft.rubric)
    grounding = list(draft.grounding)
    for item in repair.get("additional_grounding", []):
        anchor = Grounding.model_validate(item)
        if anchor not in grounding:
            grounding.append(anchor)
    for old, new in repair["replacements"].items():
        if old not in rules:
            if new in rules:
                continue
            raise ValueError(f"Calibration repair no longer matches {question_id}")
        index = rules.index(old)
        anchors = [item.quote for item in grounding if item.rubric_index == index]
        if any(
            not any(quote in anchor for anchor in anchors)
            for quote in re.findall(r'"([^"\n]+)"', new)
        ):
            raise ValueError("Calibration repair introduces an ungrounded quote")
        rules[index] = new
    for addition in repair.get("additions", []):
        if addition["rule"] in rules:
            continue
        index = len(rules)
        rules.append(addition["rule"])
        grounding.extend(
            Grounding(rubric_index=index, doc_id=item["doc_id"], quote=item["quote"])
            for item in addition["grounding"]
        )
    for index, rule in enumerate(rules):
        anchors = [item.quote for item in grounding if item.rubric_index == index]
        if any(
            not any(quote in anchor for anchor in anchors)
            for quote in re.findall(r'"([^"\n]+)"', rule)
        ):
            raise ValueError("Calibration repair introduces an ungrounded quote")
    reference = draft.correct_answer
    if repair.get("reference_context") and repair["reference_context"] not in reference:
        reference += " " + repair["reference_context"]
    notes = (
        draft.review_notes
        if repair["reason"] in draft.review_notes
        else [*draft.review_notes, repair["reason"]]
    )
    return RubricDraft.model_validate(
        {
            **draft.model_dump(),
            "rubric": rules,
            "grounding": grounding,
            "correct_answer": reference,
            "reference_status": repair.get("reference_status", draft.reference_status),
            "review_notes": notes,
        }
    )


def finalize_record(
    review: dict[str, Any], case: CaseInput, repairs: dict[str, str]
) -> dict[str, Any]:
    """Replace accidental list-completeness requirements with one factual core.

    Used by the author-only build command after reading the complete prior
    reviews. Retains the original reference for association checks and supplies
    the source-reviewed example to the judge. This is not a new model review.

    Args:
        review: Complete prior audit, including source grounding and rule kinds.
        case: Original question, reference, and linked source documents.
        repairs: Reviewed per-question core replacements; other cores are retained.

    Returns:
        Runtime-ready rule list, explicit partition, provenance, and example.

    Raises:
        ValueError: A core needs an unprovided repair, or an anchor lacks provenance.
    """
    old = RubricDraft.model_validate(review["revised"])
    core_indices = review["required_indices"]
    if len(core_indices) != 1 and case.question_id not in repairs:
        raise ValueError(f"Unresolved multiple-core rubric: {case.question_id}")
    core = repairs.get(case.question_id, old.rubric[core_indices[0]])
    rules = [core] + [old.rubric[index] for index in review["guard_indices"]]
    mapping = {index: 0 for index in core_indices}
    mapping.update(
        {
            old_index: new_index
            for new_index, old_index in enumerate(review["guard_indices"], 1)
        }
    )
    grounding = [
        Grounding(
            rubric_index=mapping[item.rubric_index],
            doc_id=item.doc_id,
            quote=item.quote,
        )
        for item in old.grounding
    ]
    # Exhaustiveness is an assertion of fact; simply omitting another item is not.
    if case.question.startswith("Find all unresolved"):
        names = [
            re.findall(r'"([^"\n]+)"', old.rubric[index])[0] for index in core_indices
        ]
        if len(names) > 1:
            rule = (
                "must not call a proper subset the only unresolved issues; the discussion also identifies "
                + "; ".join(f'"{name}"' for name in names)
                + "."
            )
            rule_index = len(rules)
            rules.append(rule)
            grounding.extend(
                Grounding(rubric_index=rule_index, doc_id=item.doc_id, quote=item.quote)
                for item in old.grounding
                if item.rubric_index in core_indices
            )
    revised = old.model_copy(update={"rubric": rules, "grounding": grounding})
    revised = RubricDraft.model_validate(revised.model_dump())
    validate_grounding(revised, case)
    return {
        "question_id": case.question_id,
        "question": case.question,
        "reference": case.reference_answer,
        "reviewed_reference": revised.correct_answer,
        "rubric": rules,
        "required_indices": [0],
        "guard_indices": list(range(1, len(rules))),
        "grounding": [item.model_dump() for item in grounding],
        "reference_status": revised.reference_status,
        "reference_notes": revised.reference_notes,
        "review_method": review["review_method"],
        "local_repair": "correctness_only_core_and_exhaustiveness",
        "live_calibration_status": "pending",
    }


def build(
    review_directory: Path, output: Path, repairs_path: Path
) -> list[dict[str, Any]]:
    """Validate complete source coverage and write a reproducible rubric artifact.

    Args:
        review_directory: Prior audit directory containing reviews and immutable inputs.
        output: Destination JSON; parents must already exist.
        repairs_path: Maintained local core revisions.

    Returns:
        Complete finalized rows in original question order.

    Raises:
        ValueError: Reviews, repairs, or source inputs have mismatched identities.
        OSError: An input cannot be read or output cannot be written.
    """
    reviews = json.loads((review_directory / "reviews.json").read_text())
    inputs = [
        CaseInput.model_validate(row["case"])
        for row in json.loads((review_directory / "inputs.json").read_text())
    ]
    repairs = json.loads(repairs_path.read_text())
    by_id = {row["question_id"]: row for row in reviews}
    if (
        len(by_id) != len(reviews)
        or set(by_id) != {case.question_id for case in inputs}
        or not set(repairs).issubset(by_id)
    ):
        raise ValueError("Review, source, and repair coverage mismatch")
    rows = [finalize_record(by_id[case.question_id], case, repairs) for case in inputs]
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    return rows


def main() -> None:
    """Build reviewed artifacts and optionally install them with updated hashes.

    Explicit --private installs only the rubric and manifest. Existing files
    are backed up beside the author output, and neither corpus nor cases change.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--repairs", type=Path, default=Path(__file__).with_name("core_repairs.json")
    )
    parser.add_argument("--private", type=Path)
    args = parser.parse_args()
    rows = build(args.review_directory, args.output, args.repairs)
    if args.private:
        for name in ("rubrics.json", "manifest.json"):
            backup = args.output.parent / f"before-{name}"
            if not backup.exists():
                backup.write_bytes((args.private / name).read_bytes())
        manifest = json.loads((args.private / "manifest.json").read_text())
        (args.private / "rubrics.json").write_bytes(args.output.read_bytes())
        manifest["rubrics_sha256"] = hashlib.sha256(
            args.output.read_bytes()
        ).hexdigest()
        manifest["rubric_scoring"] = "weighted_required_conditional_v2"
        (args.private / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    print(
        json.dumps(
            {
                "questions": len(rows),
                "required": sum(len(row["required_indices"]) for row in rows),
                "guards": sum(len(row["guard_indices"]) for row in rows),
                "live_calibration": "pending",
            }
        )
    )


if __name__ == "__main__":
    main()
