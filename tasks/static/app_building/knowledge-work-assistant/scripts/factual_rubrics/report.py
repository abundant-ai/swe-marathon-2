"""Reconstruct historical two-stage calibration reports from saved artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def collect(
    root: Path, private: Path, runs: list[str], quotation_replay: Path
) -> dict[str, Any]:
    """Select current rubric results and apply independent quotation-check overlays.

    Args:
        root: Private calibration artifact directory.
        private: Installed private dataset, used to reject obsolete rubric outputs.
        runs: Completed calibration directories in ascending replacement priority.
        quotation_replay: Completed historical overlay from the retired quote-only judge.

    Returns:
        Validated coverage, disagreements, replay means, and selected judgments.

    Raises:
        ValueError: Evidence is incomplete, inconsistent, or not from Codex.
    """
    rubrics = {
        row["question_id"]: row
        for row in json.loads((private / "rubrics.json").read_text())
    }
    overlay = {
        (row["source_run"], row["question_id"]): row
        for row in json.loads((quotation_replay / "results.json").read_text())
    }
    selected: dict[str, dict[str, Any]] = {}
    gate_errors: list[str] = []
    peaks: list[int] = []
    for name in runs:
        directory = root / name
        result = json.loads((directory / "results.json").read_text())
        summary = json.loads((directory / "summary.json").read_text())
        if (
            result["error"]
            or len(result["judgments"]) != result["expected_rows"]
            or result["transport"] != "codex_cli_temporary_calibration"
        ):
            raise ValueError(f"Invalid or non-Codex calibration: {name}")
        fixtures = {
            row["question_id"]: row
            for row in json.loads((directory / "fixtures.json").read_text())["cases"]
        }
        gate_errors.extend(summary["gate_errors"])
        peaks.append(result["peak_concurrent_requests"])
        for judgment in result["judgments"]:
            identity, variant, repeat = judgment["question_id"].split("/")
            fixture, current = fixtures[identity], rubrics[identity]
            if (
                fixture["rubric"] != current["rubric"]
                or fixture["reference"] != current["reviewed_reference"]
                or fixture["required_rubric_indices"] != current["required_indices"]
            ):
                continue
            audit = overlay.get((str(directory), judgment["question_id"]))
            if name in ("codex-final-validation", "codex-final-tail") and audit is None:
                raise ValueError(
                    "A saved context judgment lacks its quotation-check reconciliation"
                )
            citation = audit["judgment"] if audit else judgment["citation_judgment"]
            selected[judgment["question_id"]] = {
                "question_id": identity,
                "variant": variant,
                "repeat": repeat,
                "source_run": name,
                "answer": judgment["answer_judgment"],
                "citation": citation,
                "answer_score": judgment["answer_band"],
                "citation_score": citation["score"] / 100,
                "expected": result["labels"][judgment["question_id"]],
            }
    oracle = {
        row["question_id"]: row
        for row in selected.values()
        if row["variant"] == "oracle" and row["repeat"] == "repeat-1"
    }
    references = {
        row["question_id"]: row
        for row in selected.values()
        if row["variant"] == "reviewed_example" and row["repeat"] == "repeat-1"
    }
    if set(oracle) != set(rubrics) or set(references) != set(rubrics):
        raise ValueError(
            f"Incomplete current-rubric coverage: oracle={len(oracle)}, reference={len(references)}"
        )
    differences = []
    for key, row in selected.items():
        for component in ("answer", "citation"):
            expected = row["expected"].get(f"expected_{component}_scores", [])
            if expected and not any(
                math.isclose(row[f"{component}_score"], value, abs_tol=1e-9)
                for value in expected
            ):
                differences.append(
                    {
                        "case": key,
                        "component": component,
                        "expected": expected,
                        "actual": row[f"{component}_score"],
                        "judgment": row[component],
                    }
                )
    controls = [
        row
        for row in selected.values()
        if row["variant"] not in ("oracle", "reviewed_example")
    ]
    means = {
        "old_answer": sum(
            row["expected"]["old_answer_score"] for row in oracle.values()
        )
        / len(oracle),
        "new_answer": sum(row["answer_score"] for row in oracle.values()) / len(oracle),
        "old_citation": sum(
            row["expected"]["old_citation_score"] for row in oracle.values()
        )
        / len(oracle),
        "new_citation": sum(row["citation_score"] for row in oracle.values())
        / len(oracle),
    }
    repeated: dict[str, set[tuple[float, float]]] = defaultdict(set)
    for row in selected.values():
        repeated[row["question_id"] + "/" + row["variant"]].add(
            (row["answer_score"], row["citation_score"])
        )
    return {
        "questions": len(rubrics),
        "rules": sum(len(row["rubric"]) for row in rubrics.values()),
        "selected_decisions": len(selected),
        "control_repetitions": len(controls),
        "reference_status": dict(
            Counter(row["reference_status"] for row in rubrics.values())
        ),
        "rubrics_sha256": hashlib.sha256(
            (private / "rubrics.json").read_bytes()
        ).hexdigest(),
        "oracle_means": means,
        "disagreements": differences,
        "gate_errors": gate_errors,
        "peak_concurrent_questions": max(peaks),
        "varying_repeats": {
            key: sorted(value) for key, value in repeated.items() if len(value) > 1
        },
        "selected": selected,
    }


def main() -> None:
    """Write version-matched results and explain their provenance and limits."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--quotation-replay", type=Path, required=True)
    args = parser.parse_args()
    report = collect(args.root, args.private, args.run, args.quotation_replay)
    (args.root / "final-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    means = report["oracle_means"]
    lines = [
        "# Codex rubric review and calibration",
        "",
        f"Reviewed and installed rubrics for all {report['questions']} active questions: 218 mandatory points and {report['rules'] - 218} optional factual constraints. Original questions, gold answers, corpus records, and the development sample are preserved.",
        "",
        "Live judge: **Codex CLI, GPT-6 Astra High**, with tools disabled and three output-repair retries. Production remains Terra High; this temporary provider substitution does not establish Terra calibration.",
        "",
        "## Final validation",
        "",
        f"- Every active question has a current-rubric oracle judgment and reviewed-example judgment: {report['questions']} each.",
        f"- {report['control_repetitions']} control repetitions; {len(report['disagreements'])} remaining score disagreements across all selected results.",
        f"- {len(report['gate_errors'])} citation-gate/order errors; peak concurrency {report['peak_concurrent_questions']} questions.",
        f"- {len(report['varying_repeats'])} repeated variants had different observed scores. See the machine-readable report for their identities.",
        "",
        "These combine immutable full-context judgments with the independent quotation check. These are historical two-stage results; current production uses one full-context citation judge. Selected results must match the installed rules, mandatory indices, and reference text; obsolete rubric runs are excluded.",
        "",
        "## Saved oracle comparison",
        "",
        "| Mean component | Historical judge | Revised judge |",
        "| --- | ---: | ---: |",
        f"| Factual answer score | {means['old_answer']:.2%} | {means['new_answer']:.2%} |",
        f"| Citation score | {means['old_citation']:.2%} | {means['new_citation']:.2%} |",
        "",
        "Both columns use the same 218 saved answers from oracle trial `swe-m2_ai-engineering_knowledge-work-assistant-727a668e-15`, linked through experiment `6d33bbbd`. The rubrics and judge differ; this is not an improvement to the oracle implementation or a new task reward. No answers were regenerated, and no full-container RAG trial was run.",
        "",
        "## What changed",
        "",
        "The answer judge returns per-criterion decisions. Python computes `passed required / (required count + distinct optional violations)`. Correct, absent, and unverified optional claims affect neither count. Required facts cannot be skipped. A nonexhaustive answer can receive full factual credit; explicit false exclusivity cannot. Attribution, chronology, valid alternatives, and project boundaries are encoded in source-grounded rules.",
        "",
        "In these historical runs, citation assessment first checked the complete original document, then checked predicate support using only the actual quotations. The second check sees no original document, document ID, or earlier reasoning and can only reduce support. This separation fixed observed credit for irrelevant quotations. Exact excerpts, explicit corrections, central contradictions, zero-support enforcement, and the 0.75 gate are checked separately. Citation bands remain 0, 0.5, and 1.",
        "",
        "## Source findings and limitations",
        "",
        "The initial full-source review and separate saved-answer audit covered all 218 questions; the latter changed 91 rubrics. Some source-audit expectations were corrected after evidence inspection. Six nonexhaustive issue lists remain factually supported; they are not six wrong gold answers. Three golds overstate what the sources establish, and one has conflicting lifecycle records. Original versions and source-specific notes are preserved.",
        "",
        "One Codex source-audit output required only conditional-clause reordering to satisfy the literal `must ` prefix. Its facts, evidence, and score were unchanged; the raw response is retained. Live call inputs, schemas, responses, retries, and version hashes are stored under each run.",
        "",
        "All current questions have one mandatory core, so positive answer scores are `1 / (1 + optional violations)`. With this set, the 0.75 citation gate admits only a clean factual score of 1. An arbitrary unverified extra cannot be declared false solely because it is absent from a closed rubric; citation support assesses that extra separately.",
        "",
        "These are model-assisted source audits and calibration labels, not human-certified gold or proof against every possible response. The same model family performed review and temporary judging. Live Terra and Logfire validation remain pending. No commit, upload, or new Oddish trial was performed.",
        "",
        "See [every question and rubric](rubric-review.md), [gold-answer findings](gold-answer-review.md), [oracle provenance](oracle-provenance.json), and [all selected results](final-results.json).",
        "",
    ]
    if report["disagreements"]:
        lines.extend(["## Remaining disagreements", ""])
        lines.extend(
            f"- `{row['case']}` ({row['component']}): expected {row['expected']}, observed {row['actual']}."
            for row in report["disagreements"]
        )
    (args.root / "report.md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in ("selected", "disagreements")
            }
        )
    )
    print(f"Disagreements: {len(report['disagreements'])}")


if __name__ == "__main__":
    main()
