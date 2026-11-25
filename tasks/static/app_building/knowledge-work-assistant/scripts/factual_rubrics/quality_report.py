"""Render a completed rubric audit for author review without changing evaluation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .quality_models import QualityInput, RubricQualityAudit, validate_quality_audit

ISSUE_LABELS: dict[str, str] = {
    "no_required_fact": "No required answer fact",
    "weak_required_fact": "Required fact does not answer the question",
    "mixed_claims": "Several factual checks combined",
    "redundancy": "Duplicate checks",
    "unsupported_fact": "Unsupported factual rule",
    "overconstraint": "Unnecessary requirement",
    "ambiguity": "Ambiguous rule",
    "irrelevance": "Irrelevant rule",
    "source_reference_concern": "Source or reference concern",
    "missing_error_guard": "Missing check on an optional claim",
}


def review_path(directory: Path, index: int) -> Path:
    """Choose an Astra final review or an explicitly recorded local fallback.

    Args:
        directory: Author-only run directory containing separate review stores.
        index: Stable zero-based input position.

    Returns:
        The Astra checkpoint when present, otherwise the local checkpoint path.
        Reading a missing fallback still fails; this never creates a result.
    """
    astra = directory / "records" / f"{index:03d}.json"
    return (
        astra if astra.exists() else directory / "local-records" / f"{index:03d}.json"
    )


def load_reviewed_audits(
    directory: Path,
) -> list[tuple[QualityInput, RubricQualityAudit]]:
    """Read every reviewed checkpoint and recheck its original source association.

    Used by the report exporter after source review finishes. Partial runs
    cannot produce a report described as complete.

    Args:
        directory: Author-only run directory containing inputs and final records.

    Returns:
        Original inputs paired with validated audits in dataset order.

    Raises:
        ValueError: A checkpoint has the wrong identity or invalid rule grounding.
        FileNotFoundError: Any expected final review checkpoint is missing.
    """
    inputs = [
        QualityInput.model_validate(row)
        for row in json.loads((directory / "inputs.json").read_text())
    ]
    if not inputs or len({item.case.question_id for item in inputs}) != len(inputs):
        raise ValueError("A nonempty set of unique question inputs is required")
    pairs: list[tuple[QualityInput, RubricQualityAudit]] = []
    for index, original in enumerate(inputs):
        path = review_path(directory, index)
        record = json.loads(path.read_text())
        if (
            path.parent.name == "local-records"
            and record.get("review_method")
            != "local_codex_source_review_after_api_quota"
        ):
            raise ValueError("Local fallback must disclose its review method")
        if record["question_id"] != original.case.question_id:
            raise ValueError("Report checkpoint identity mismatch")
        audit = validate_quality_audit(
            RubricQualityAudit.model_validate(record["audit"]), original
        )
        pairs.append((original, audit))
    return pairs


def render_question(
    original: QualityInput, audit: RubricQualityAudit, method: str
) -> str:
    """Render one review with required facts, optional guards, and source findings.

    Args:
        original: Unchanged question, reference, sources, and original rules.
        audit: Source-validated proposal from its recorded review method.
        method: Actual review method, disclosed separately for local fallbacks.

    Returns:
        Markdown for one question, preserving the proposed rule text verbatim.
        Rule numbers are one-based for readers; JSON indices remain zero-based.
    """
    lines = [
        f"## {original.case.question_id}",
        "",
        original.case.question,
        "",
        f"Review method: {method}.",
        "",
        "**Original rule classifications**",
        "",
    ]
    classifications = {item.rubric_index: item for item in audit.original_assessments}
    for index, rule in enumerate(original.original_rubric):
        item = classifications[index]
        lines.append(f"{index + 1}. [{item.kind}] {rule} — {item.reason}")
    lines.extend(["", "**Findings**", ""])
    lines.extend(
        f"- {ISSUE_LABELS[issue.code]}: {issue.explanation}"
        for issue in audit.original_issues
    )
    if not audit.original_issues:
        lines.append("No concrete defect reported by the model review.")
    lines.extend(["", "**Proposed required facts**", ""])
    lines.extend(
        f"- Rule {index + 1}: {audit.revised.rubric[index]}"
        for index in audit.required_indices
    )
    lines.extend(["", "**Proposed conditional error checks**", ""])
    lines.extend(
        f"- Rule {index + 1}: {audit.revised.rubric[index]}"
        for index in audit.guard_indices
    )
    if not audit.guard_indices:
        lines.append("None.")
    lines.extend(
        [
            "",
            "**Why this required content answers the question**",
            "",
            audit.core_justification,
            "",
            f"**Reference status:** {audit.revised.reference_status}",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in audit.revised.reference_notes)
    lines.extend(["", "**Source anchors**", ""])
    for anchor in audit.revised.grounding:
        quote = " ".join(anchor.quote.splitlines())
        lines.append(f"- Rule {anchor.rubric_index + 1}, `{anchor.doc_id}`: {quote}")
    return "\n".join(lines).rstrip() + "\n"


def export_report(directory: Path) -> dict[str, Any]:
    """Write summary and full question-by-question reports for a complete audit.

    Args:
        directory: Completed author-only run directory. Writes only report files
            there; never replaces active rubrics, references, or judge prompts.

    Returns:
        Aggregate audit counts and IDs with new reference concerns. These are
        model-review findings, not a measured ground-truth error rate.

    Raises:
        ValueError: A reviewed proposal fails source or coverage validation.
        FileNotFoundError: The complete reviewed dataset is unavailable.
    """
    pairs = load_reviewed_audits(directory)
    methods = [
        "astra_two_pass"
        if review_path(directory, index).parent.name == "records"
        else "local_codex_source_review_after_api_quota"
        for index in range(len(pairs))
    ]
    method_counts = Counter(methods)
    issue_counts: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    concerns: list[dict[str, Any]] = []
    for original, audit in pairs:
        issue_counts.update({issue.code for issue in audit.original_issues})
        kinds.update(item.kind for item in audit.original_assessments)
        if audit.revised.reference_status != "supported" or any(
            issue.code == "source_reference_concern" for issue in audit.original_issues
        ):
            concerns.append(
                {
                    "question_id": original.case.question_id,
                    "question": original.case.question,
                    "original_reference": original.case.reference_answer,
                    "reference_status": audit.revised.reference_status,
                    "reference_notes": audit.revised.reference_notes,
                    "issues": [
                        issue.model_dump()
                        for issue in audit.original_issues
                        if issue.code
                        in {"source_reference_concern", "unsupported_fact"}
                    ],
                    "proposed_answer": audit.revised.correct_answer,
                    "grounding": [
                        anchor.model_dump() for anchor in audit.revised.grounding
                    ],
                }
            )
    summary = {
        "questions_reviewed": len(pairs),
        "review_methods": dict(method_counts),
        "original_rules_reviewed": sum(
            len(original.original_rubric) for original, _ in pairs
        ),
        "original_rule_types": dict(kinds),
        "questions_by_issue": dict(issue_counts),
        "questions_without_original_required_fact": sum(
            not any(item.kind == "required_fact" for item in audit.original_assessments)
            for _, audit in pairs
        ),
        "proposed_required_rules": sum(
            len(audit.required_indices) for _, audit in pairs
        ),
        "proposed_guard_rules": sum(len(audit.guard_indices) for _, audit in pairs),
        "questions_without_proposed_required_fact": sum(
            not audit.required_indices for _, audit in pairs
        ),
        "reference_concern_ids": [item["question_id"] for item in concerns],
        "model_reference_status_counts": dict(
            Counter(audit.revised.reference_status for _, audit in pairs)
        ),
        "longest_proposed_rule_words": max(
            len(rule.split()) for _, audit in pairs for rule in audit.revised.rubric
        ),
        "active_evaluation_changed": False,
        "human_certified": False,
    }
    followup_path = directory / "proposal-followups.json"
    followups = (
        json.loads(followup_path.read_text()) if followup_path.exists() else None
    )
    if followups is not None:
        summary["proposed_rewrites_needing_policy_review"] = followups[
            "questions_flagged"
        ]
    lines = [
        "# Rubric quality review",
        "",
        (
            f"Reviewed all {len(pairs)} active questions and {summary['original_rules_reviewed']} original rules. "
            f"GPT-6 Astra High completed both a source-backed audit and a separate fresh-context review for "
            f"{method_counts['astra_two_pass']} questions. Local Codex source review completed "
            f"{method_counts['local_codex_source_review_after_api_quota']} remaining questions after the API account "
            "quota was exhausted. Each question's method is disclosed in the detailed report."
        ),
        "",
        (
            f"The review found **{summary['questions_without_original_required_fact']} questions without a substantive "
            "unconditional required fact**. Every proposed revision has at least one."
        ),
        "",
        (
            "Proposals remain separate from the active evaluator. No private question, original gold answer, "
            "judge prompt, citation rule, or reward calculation was changed by this review."
        ),
        "",
        (
            "[Every question, original classification, proposed rule, and source anchor](all-rubrics.md) · "
            "[Proposed structured rubrics](proposed_rubrics.json) · [Full review records](reviews.json) · "
            "[New reference concerns](reference-concerns.json)"
        ),
        "",
        "## Scoring interpretation used for this review",
        "",
        (
            "Required facts are the smallest substantive answer to the question. Missing or incorrect required facts "
            "fail; background details are not made mandatory merely because they appear in the gold answer."
        ),
        "",
        (
            "Conditional checks constrain optional claims. An omitted optional claim or a correct optional claim "
            "adds nothing to either numerator or denominator. An incorrect optional claim remains an error. "
            "Every question must have required facts, so no question can consist only of these checks. "
            "The new per-criterion scoring calculation has not been installed."
        ),
        "",
        "## Why the original lists need revision",
        "",
        (
            "The original authoring prompt kept optional details conditional and assigned the substantive-answer "
            "requirement to the overall judge, outside the question-specific list. That design is incompatible "
            "with using the list alone as the denominator. The revised proposals put the minimum responsive "
            "factual content inside each list, while keeping optional-detail checks separate."
        ),
        "",
        "## Findings",
        "",
        "Counts overlap because a question can have several defects.",
        "",
        "| Finding | Questions |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {ISSUE_LABELS[code]} | {count} |"
        for code, count in issue_counts.most_common()
    )
    lines.extend(
        [
            "",
            (
                f"Proposed totals: {summary['proposed_required_rules']} required facts and "
                f"{summary['proposed_guard_rules']} conditional error checks. The longest proposed rule is "
                f"{summary['longest_proposed_rule_words']} words; explicit alternatives can make a core requirement "
                "longer than a single optional-detail check."
            ),
            "",
        ]
    )
    if followups is not None:
        lines.extend(
            [
                "## Further review of the proposed rewrites",
                "",
                (
                    f"An additional local policy review flagged {followups['questions_flagged']} proposals with multiple "
                    "required facts. Some demand several list items or recommendations; others may count an answer "
                    "and its explanation separately. This can introduce completeness penalties into a correctness-only score. "
                    "Questions asking for 'all' also need a distinction between an incomplete list and a false claim of exhaustiveness."
                ),
                "",
                (
                    "[Affected proposals and exact required rules](proposal-followups.json). These are follow-up concerns "
                    "about the proposed rewrites, separate from the original-rubric findings above. Having at least one "
                    "required fact is necessary, but does not by itself make a proposal ready for activation."
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Reference concerns",
            "",
            (
                "These are flagged source or gold-answer concerns, not confirmed errors. Original references "
                "and active question membership are preserved. The model's conflicted label can include an "
                "incomplete list whose stated facts are correct; the notes explain each case. Inspect the "
                "source context before deciding to exclude a question."
            ),
            "",
        ]
    )
    if not concerns:
        lines.append("No additional reference concern was reported in the active set.")
    for concern in concerns:
        notes = concern["reference_notes"] or [
            item["explanation"] for item in concern["issues"]
        ]
        lines.append(
            f"- `{concern['question_id']}` ({concern['reference_status']}): {' '.join(notes)}"
        )
    lines.extend(
        [
            "",
            "## Validation and limits",
            "",
            (
                "Every original rule was classified exactly once. Every revised rule belongs to exactly one group. "
                "Every question has a positive required fact. Exact quotations and document IDs were checked against "
                "the source inputs after review. Obvious conditional or negative-only required rules are rejected."
            ),
            "",
            (
                "These checks establish coverage and literal provenance. They do not prove semantic correctness. "
                "The second pass uses the same model family, so correlated judgment errors remain possible. "
                "Local fallback reviews are not completed independent Astra second passes. "
                "No live answer-scoring calibration was run for these proposed revisions."
            ),
            "",
            (
                "A finite list of requirements also cannot establish the truth of every possible extra claim. "
                "A scorer that checks only the listed facts can miss an unrelated false assertion. Correct "
                "optional claims must remain neutral, and a single factual error must not be counted again "
                "merely because both a required fact and a conditional check refer to it."
            ),
        ]
    )
    (directory / "quality-review.md").write_text("\n".join(lines) + "\n")
    (directory / "all-rubrics.md").write_text(
        "# All active rubric reviews\n\nProposals only; original answers and active evaluation are unchanged.\n\n"
        + "\n".join(
            render_question(original, audit, method)
            for (original, audit), method in zip(pairs, methods, strict=True)
        )
    )
    rows = [
        {
            "question_id": original.case.question_id,
            "question": original.case.question,
            "reference": original.case.reference_answer,
            "original_rubric": original.original_rubric,
            **audit.model_dump(),
            "review_method": method,
            "status": "proposed_only_not_human_certified",
        }
        for (original, audit), method in zip(pairs, methods, strict=True)
    ]
    (directory / "reviews.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    )
    proposed = [
        {
            "question_id": row["question_id"],
            "question": row["question"],
            "reference": row["reference"],
            "rubric": row["revised"]["rubric"],
            "required_indices": row["required_indices"],
            "guard_indices": row["guard_indices"],
            "grounding": row["revised"]["grounding"],
            "review_method": row["review_method"],
        }
        for row in rows
    ]
    (directory / "proposed_rubrics.json").write_text(
        json.dumps(proposed, ensure_ascii=False, indent=2) + "\n"
    )
    (directory / "quality-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    (directory / "reference-concerns.json").write_text(
        json.dumps(concerns, ensure_ascii=False, indent=2) + "\n"
    )
    return summary


def main() -> None:
    """Read a completed run path and export author-only Markdown and JSON reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_report(args.run_directory)))


if __name__ == "__main__":
    main()
