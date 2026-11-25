"""Prepare real public corpus inputs with structural, non-evaluation CI rubrics."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from prepare_data import collect_records, prepare_data
from task_paths import TASK_ROOT


def structural_rubric(case: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic schema fixture from an unchanged public reference.

    Args:
        case: Public question record emitted by the production corpus normalizer.

    Returns:
        An explicitly unreviewed rubric used only to test packaging and parsing.
        It is not a semantic grading rubric or a replacement for private review.

    Raises:
        ValueError: The public reference has no usable textual anchor.
    """
    reference = case["reference"]
    text = reference if isinstance(reference, str) else " ".join(reference)
    anchor = re.search(r"\w+", text)
    if anchor is None:
        raise ValueError("CI fixture needs a nonempty reference")
    return {key: case[key] for key in ("question_id", "question", "reference")} | {
        "rubric": [f'must state the reference fact anchored by "{anchor.group()}".'],
        "required_indices": [0],
        "guard_indices": [],
        "reviewed_reference": text,
        "review_method": "unreviewed_ci_schema_fixture",
    }


def prepare_ci_inputs(herb: Path, task_root: Path) -> dict[str, Any]:
    """Exercise production preparation without requiring unpublished rubrics.

    Args:
        herb: Checkout of the public HERB revision pinned by production preparation.
        task_root: Clean task directory receiving generated CI-only inputs.

    Returns:
        Production provenance with an additional CI-only marker, which causes
        the normal evaluation loader to reject this dataset.

    Raises:
        ValueError: Existing private inputs would be overwritten, or corpus
            preparation rejects the revision or fixture coverage.
    """
    private = task_root / "tests/private"
    if private.exists():
        raise ValueError(
            "CI preparation requires a clean task; refusing to overwrite private inputs"
        )
    _, cases, _ = collect_records(herb / "data")
    excluded = set(
        json.loads((task_root / "scripts/holdout_exclusions.json").read_text())[
            "excluded_question_ids"
        ]
    )
    rubrics = [
        structural_rubric(case) for case in cases if case["question_id"] not in excluded
    ]
    with TemporaryDirectory(prefix="orange-ci-rubrics-") as temporary:
        path = Path(temporary) / "rubrics.json"
        path.write_text(json.dumps(rubrics))
        manifest = prepare_data(herb, task_root, path)
    manifest["ci_fixture_only"] = True
    (private / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    """Prepare CI inputs in a clean checkout and print counts without answer text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--herb", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_ci_inputs(args.herb.resolve(), TASK_ROOT)
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in (
                    "corpus_records",
                    "sample_records",
                    "content_questions",
                    "ci_fixture_only",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
