"""Validate dataset citation resolution and trusted answer-evidence loading."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from prepare_data import (
    HERB_REVISION,
    METADATA_FILES,
    collect_records,
    select_holdout_cases,
)
from verifier.contracts import EvaluationError
from verifier.dataset import QUESTION_COUNT
from verifier.inputs import load_inputs


@pytest.fixture
def source_data(tmp_path: Path) -> Path:
    """Create two products sharing a native ID but containing different facts.

    Args:
        tmp_path: Temporary source dataset location.

    Returns:
        A minimal HERB-shaped directory with complete reference citations.
    """
    products = tmp_path / "products"
    products.mkdir()
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    for filename in METADATA_FILES:
        (metadata / filename).write_text("[]")
    for product, owner in (("alpha", "Mira"), ("beta", "Tao")):
        (products / f"{product}.json").write_text(
            json.dumps(
                {
                    "documents": [
                        {
                            "id": "shared",
                            "content": f"{owner} owns it. Deadline Friday.",
                        }
                    ],
                    "answerable_questions": [
                        {
                            "type": "content",
                            "question": "Who owns it?",
                            "ground_truth": owner,
                            "citations": ["shared", "shared"],
                        }
                    ],
                }
            )
        )
    return tmp_path


def test_reference_ids_resolve_within_the_owning_product(source_data: Path) -> None:
    """Preserve complete records and deduplicate citations without crossing products.

    Args:
        source_data: Two products whose native source IDs deliberately collide.
    """
    corpus, cases, _ = collect_records(source_data)
    documents = {row["doc_id"]: row for row in corpus}
    for case, product, owner in zip(
        cases, ("alpha", "beta"), ("Mira", "Tao"), strict=True
    ):
        assert case["reference"] == owner
        assert case["evidence_doc_ids"] == [f"{product}:documents:0:shared"]
        assert owner in documents[case["evidence_doc_ids"][0]]["content"]
        assert "Deadline Friday." in documents[case["evidence_doc_ids"][0]]["content"]


@pytest.mark.parametrize("defect", ["missing", "ambiguous", "empty"])
def test_bad_reference_citations_fail_preparation(
    source_data: Path, defect: str
) -> None:
    """Reject missing or ambiguous evidence instead of falling back to references alone.

    Args:
        source_data: Valid source fixture to corrupt.
        defect: Unknown ID, duplicate matching source, or empty reference evidence.
    """
    path = source_data / "products/alpha.json"
    product = json.loads(path.read_text())
    if defect == "ambiguous":
        product["documents"].append({"id": "shared", "content": "Different source."})
    else:
        product["answerable_questions"][0]["citations"] = (
            ["unknown"] if defect == "missing" else []
        )
    path.write_text(json.dumps(product))
    with pytest.raises(ValueError, match="reference citation"):
        collect_records(source_data)


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "ci_fixture",
        "missing",
        "duplicate",
        "empty",
        "old_format",
        "excluded",
        "count",
        "rubric_missing",
        "rubric_duplicate",
        "rubric_empty",
        "rubric_invalid",
        "rubric_question_changed",
        "rubric_reference_changed",
        "rubric_hash",
    ],
)
def test_private_loader_requires_resolvable_evidence(
    tmp_path: Path, defect: str | None
) -> None:
    """Resolve authenticated corpus records and reject unusable case evidence.

    Args:
        tmp_path: Temporary private verifier directory.
        defect: Evidence corruption to reject; None exercises the valid path.
    """
    document = {
        "doc_id": "d",
        "source_type": "documents",
        "title": "Owner",
        "content": "Mira owns the project. Deadline Friday.",
    }
    rows = [
        {
            "question_id": str(index),
            "question": "Who?",
            "reference": "Mira",
            "evidence_doc_ids": ["d"],
        }
        for index in range(QUESTION_COUNT)
    ]
    rubrics = [
        {key: row[key] for key in ("question_id", "question", "reference")}
        | {
            "rubric": ['must identify "Mira" as owner.'],
            "required_indices": [0],
            "guard_indices": [],
            "reviewed_reference": "Mira",
        }
        for row in rows
    ]
    if defect == "rubric_missing":
        rubrics.pop()
    elif defect == "rubric_duplicate":
        rubrics[-1] = rubrics[0]
    elif defect == "rubric_empty":
        rubrics[0]["rubric"] = []
    elif defect == "rubric_invalid":
        rubrics[0]["rubric"] = ["should name Mira"]
    elif defect == "rubric_question_changed":
        rubrics[0]["question"] = "Another question"
    elif defect == "rubric_reference_changed":
        rubrics[0]["reference"] = "Another answer"
    if defect == "old_format":
        rows[0].pop("evidence_doc_ids")
    elif defect in {"missing", "duplicate", "empty"}:
        rows[0]["evidence_doc_ids"] = {
            "missing": ["unknown"],
            "duplicate": ["d", "d"],
            "empty": [],
        }[defect]
    manifest = {"herb_revision": HERB_REVISION, "content_questions": QUESTION_COUNT}
    if defect == "ci_fixture":
        manifest["ci_fixture_only"] = True
    if defect == "excluded":
        manifest["excluded_question_ids"] = [rows[0]["question_id"]]
    elif defect == "count":
        manifest["content_questions"] += 1
    for filename, value, key in (
        ("corpus.json", [document], "corpus_sha256"),
        ("cases.json", rows, "cases_sha256"),
        ("rubrics.json", rubrics, "rubrics_sha256"),
    ):
        payload = json.dumps(value).encode()
        (tmp_path / filename).write_bytes(payload)
        manifest[key] = hashlib.sha256(payload).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    if defect == "rubric_hash":
        (tmp_path / "rubrics.json").write_text("[]")
    if defect is not None:
        with pytest.raises(EvaluationError):
            load_inputs(tmp_path)
        if defect == "ci_fixture":
            assert (
                len(load_inputs(tmp_path, allow_ci_fixtures=True)[1]) == QUESTION_COUNT
            )
    else:
        _, cases, _ = load_inputs(tmp_path)
        assert len(cases) == QUESTION_COUNT
        assert all(case.documents == (document,) for case in cases)
        assert all(case.rubric == tuple(rubrics[0]["rubric"]) for case in cases)


def test_holdout_exclusions_preserve_retained_records(source_data: Path) -> None:
    """Exclude approved IDs without rewriting retained questions or source links.

    Args:
        source_data: Two valid source products used to exercise selection.
    """
    _, cases, _ = collect_records(source_data)
    retained = select_holdout_cases(cases, [cases[0]["question_id"]])
    assert retained == cases[1:]
    assert retained[0] is cases[1]
    assert len(cases) == 2
    with pytest.raises(ValueError, match="absent"):
        select_holdout_cases(cases, ["missing:content:0"])
