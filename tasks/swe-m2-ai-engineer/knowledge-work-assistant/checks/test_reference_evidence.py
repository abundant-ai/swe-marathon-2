"""Validate dataset citation resolution and trusted answer-evidence loading."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from prepare_data import HERB_REVISION, METADATA_FILES, collect_records
from verifier.contracts import EvaluationError
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
        (products / f"{product}.json").write_text(json.dumps({
            "documents": [{"id": "shared", "content": f"{owner} owns it. Deadline Friday."}],
            "answerable_questions": [{"type": "content", "question": "Who owns it?",
                                      "ground_truth": owner, "citations": ["shared", "shared"]}],
        }))
    return tmp_path


def test_reference_ids_resolve_within_the_owning_product(source_data: Path) -> None:
    """Preserve complete records and deduplicate citations without crossing products.

    Args:
        source_data: Two products whose native source IDs deliberately collide.
    """
    corpus, cases, _ = collect_records(source_data)
    documents = {row["doc_id"]: row for row in corpus}
    for case, product, owner in zip(cases, ("alpha", "beta"), ("Mira", "Tao"), strict=True):
        assert case["reference"] == owner
        assert case["evidence_doc_ids"] == [f"{product}:documents:0:shared"]
        assert owner in documents[case["evidence_doc_ids"][0]]["content"]
        assert "Deadline Friday." in documents[case["evidence_doc_ids"][0]]["content"]


@pytest.mark.parametrize("defect", ["missing", "ambiguous", "empty"])
def test_bad_reference_citations_fail_preparation(source_data: Path, defect: str) -> None:
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
        product["answerable_questions"][0]["citations"] = ["unknown"] if defect == "missing" else []
    path.write_text(json.dumps(product))
    with pytest.raises(ValueError, match="reference citation"):
        collect_records(source_data)


@pytest.mark.parametrize("defect", [None, "missing", "duplicate", "empty", "old_format"])
def test_private_loader_requires_resolvable_evidence(tmp_path: Path, defect: str | None) -> None:
    """Resolve authenticated corpus records and reject unusable case evidence.

    Args:
        tmp_path: Temporary private verifier directory.
        defect: Evidence corruption to reject; None exercises the valid path.
    """
    document = {"doc_id": "d", "source_type": "documents", "title": "Owner",
                "content": "Mira owns the project. Deadline Friday."}
    rows = [{"question_id": str(index), "question": "Who?", "reference": "Mira",
             "evidence_doc_ids": ["d"]} for index in range(238)]
    if defect == "old_format":
        rows[0].pop("evidence_doc_ids")
    elif defect is not None:
        rows[0]["evidence_doc_ids"] = {"missing": ["unknown"], "duplicate": ["d", "d"], "empty": []}[defect]
    manifest = {"herb_revision": HERB_REVISION}
    for filename, value, key in (("corpus.json", [document], "corpus_sha256"),
                                  ("cases.json", rows, "cases_sha256")):
        payload = json.dumps(value).encode()
        (tmp_path / filename).write_bytes(payload)
        manifest[key] = hashlib.sha256(payload).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    if defect is not None:
        with pytest.raises(EvaluationError):
            load_inputs(tmp_path)
    else:
        _, cases, _ = load_inputs(tmp_path)
        assert len(cases) == 238
        assert all(case.documents == (document,) for case in cases)
