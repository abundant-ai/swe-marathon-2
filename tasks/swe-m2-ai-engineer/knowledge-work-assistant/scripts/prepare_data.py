"""Prepare sanitized evaluation inputs and a uniform 4% development sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from pathlib import Path

from task_paths import TASK_ROOT
from typing import Any, Final, Mapping, Sequence

HERB_REVISION: Final = "db3bf9b3f911745726c579c9dbf9f7f6b2c05b36"
SOURCE_KEYS: Final = ("slack", "documents", "meeting_transcripts", "meeting_chats", "urls", "prs")
METADATA_FILES: Final = ("employee.json", "customers_data.json", "salesforce_team.json")
SAMPLE_FRACTION: Final = 0.04
SAMPLE_SEED: Final = 20261112


def collect_records(data_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]], dict[str, str]]:
    """Read allowlisted records while separating every question and reference.

    Args:
        data_dir: HERB data directory containing products/ and metadata/.

    Returns:
        Sanitized corpus, content-only held-out cases with normalized reference
        evidence IDs, and source-file hashes.
        Product team/customer membership fields are deliberately excluded;
        directory records are included as permitted by HERB's task definition.

    Raises:
        ValueError: Duplicate generated identities, malformed content questions,
            or missing/ambiguous reference citations within a product.
    """
    corpus: list[dict[str, str]] = []
    cases: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for path in sorted((data_dir / "products").glob("*.json")):
        hashes[str(path.relative_to(data_dir))] = hashlib.sha256(path.read_bytes()).hexdigest()
        product = json.loads(path.read_text())
        source_ids: dict[str, list[str]] = {}
        for source_type in SOURCE_KEYS:
            for index, record in enumerate(product.get(source_type, [])):
                native_id = str(record.get("id", index))
                doc_id = f"{path.stem}:{source_type}:{index}:{native_id}"
                source_ids.setdefault(native_id, []).append(doc_id)
                corpus.append({
                    "doc_id": doc_id,
                    "source_type": source_type,
                    "title": f"{path.stem} / {source_type} / {record.get('title', native_id)}",
                    "content": json.dumps(record, ensure_ascii=False, indent=2),
                })
        for index, row in enumerate(product.get("answerable_questions", [])):
            if row.get("type") == "content":
                reference = row["ground_truth"]
                if not isinstance(reference, (str, list)) or not isinstance(row["question"], str):
                    raise ValueError("Malformed HERB content question")
                citations = row.get("citations")
                if not isinstance(citations, list) or not citations or not all(isinstance(value, str) for value in citations):
                    raise ValueError(f"Missing or malformed reference citations: {path.stem}:{index}")
                evidence_ids: list[str] = []
                for citation in dict.fromkeys(citations):
                    matches = source_ids.get(citation, [])
                    if len(matches) != 1:
                        raise ValueError(f"Unresolved or ambiguous reference citation: {path.stem}:{citation}")
                    evidence_ids.append(matches[0])
                cases.append({"question_id": f"{path.stem}:content:{index}", "question": row["question"],
                              "reference": reference, "evidence_doc_ids": evidence_ids})
    for filename in METADATA_FILES:
        path = data_dir / "metadata" / filename
        hashes[str(path.relative_to(data_dir))] = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = json.loads(path.read_text())
        rows = list(metadata.values()) if isinstance(metadata, dict) else metadata
        for index, row in enumerate(rows):
            corpus.append({"doc_id": f"directory:{path.stem}:{index}", "source_type": "directory", "title": f"{path.stem} / {row.get('name', index)}", "content": json.dumps(row, ensure_ascii=False, indent=2)})
    if len({row["doc_id"] for row in corpus}) != len(corpus):
        raise ValueError("Duplicate generated corpus IDs")
    return corpus, cases, hashes


def write_json(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    """Write a canonical UTF-8 JSON array and return its content hash.

    Args:
        path: Destination in the public or private bundle.
        rows: Already separated records; no implicit field filtering occurs here.

    Returns:
        SHA-256 of the exact serialized bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(list(rows), ensure_ascii=False, sort_keys=True) + "\n").encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def select_holdout_cases(
    cases: Sequence[dict[str, Any]], excluded_question_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """Remove reviewed exclusions when rebuilding the private question set.

    Called by prepare_data after loading the pinned upstream questions. This
    transformation preserves retained records and their order without I/O.

    Args:
        cases: Complete upstream content cases with unique question IDs.
        excluded_question_ids: Explicit author-approved IDs to remove.

    Returns:
        A new list of retained cases; the original record objects are unchanged.

    Raises:
        ValueError: IDs are duplicated or an exclusion is absent upstream.
    """
    identities = {case["question_id"] for case in cases}
    excluded = set(excluded_question_ids)
    if len(identities) != len(cases) or len(excluded) != len(excluded_question_ids):
        raise ValueError("Question and exclusion IDs must be unique")
    if not excluded <= identities:
        raise ValueError("Excluded question is absent from the upstream content set")
    return [case for case in cases if case["question_id"] not in excluded]


def prepare_data(herb_root: Path, task_root: Path, rubrics_path: Path | None = None) -> dict[str, Any]:
    """Build ignored data artifacts from the pinned upstream checkout.

    Args:
        herb_root: Existing HERB checkout; this function does not download data.
        task_root: Knowledge-work-assistant task directory.
        rubrics_path: Previously reviewed private rubric array. Defaults to the
            existing private/rubrics.json; a clean build must supply this artifact.

    Returns:
        Manifest with provenance, full-corpus hashes, sample definition, and
        the retained question count after applying holdout_exclusions.json.

    Raises:
        ValueError: Wrong upstream revision or unexpected holdout size.
    """
    revision = subprocess.check_output(["git", "-C", str(herb_root), "rev-parse", "HEAD"], text=True).strip()
    if revision != HERB_REVISION:
        raise ValueError(f"Expected HERB revision {HERB_REVISION}")
    corpus, cases, hashes = collect_records(herb_root / "data")
    if len(cases) != 238:
        raise ValueError(f"Expected 238 content questions; found {len(cases)}")
    source_question_count = len(cases)
    exclusion_path = Path(__file__).with_name("holdout_exclusions.json")
    exclusion_policy = json.loads(exclusion_path.read_text())
    cases = select_holdout_cases(cases, exclusion_policy["excluded_question_ids"])
    private = task_root / "steps/01-build-rag/tests/private"
    reviewed_rubrics = json.loads((rubrics_path or private / "rubrics.json").read_text())
    if (len(reviewed_rubrics) != len(cases) or
            {row["question_id"] for row in reviewed_rubrics} != {row["question_id"] for row in cases}):
        raise ValueError("Reviewed rubrics must cover exactly the retained questions")
    sample_size = int(len(corpus) * SAMPLE_FRACTION)
    sample = random.Random(SAMPLE_SEED).sample(corpus, sample_size)
    sample_path = task_root / "environment/data/corpus.json"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(json.dumps(sample, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    provenance = task_root / "environment/resources/corpus"
    provenance.mkdir(parents=True, exist_ok=True)
    manifest = {
        "herb_revision": revision, "corpus_records": len(corpus), "content_questions": len(cases),
        "source_content_questions": source_question_count,
        "excluded_question_ids": exclusion_policy["excluded_question_ids"],
        "exclusion_policy_sha256": hashlib.sha256(exclusion_path.read_bytes()).hexdigest(),
        "source_attribution": {
            "creator": "Salesforce AI Research", "title": "HERB",
            "source": "https://github.com/SalesforceAIResearch/HERB",
            "license": "https://creativecommons.org/licenses/by-nc/4.0/",
            "changes": "Normalized source records to JSON, included directories, and selected a seeded 4% development sample.",
        },
        "corpus_sha256": write_json(private / "corpus.json", corpus),
        "cases_sha256": write_json(private / "cases.json", cases),
        "rubrics_sha256": write_json(private / "rubrics.json", reviewed_rubrics),
        "sample_sha256": hashlib.sha256(sample_path.read_bytes()).hexdigest(),
        "sample_records": sample_size, "sample_fraction": SAMPLE_FRACTION,
        "sample_seed": SAMPLE_SEED, "sampling_unit": "corpus record, without replacement",
        "source_sha256": hashes,
    }
    (private / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    public_manifest = {key: manifest[key] for key in ("sample_records", "sample_fraction", "sample_seed", "sample_sha256", "sampling_unit")}
    (provenance / "manifest.json").write_text(json.dumps(public_manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    """Parse author-side paths and print counts without private question text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--herb", type=Path, required=True)
    parser.add_argument("--rubrics", type=Path, help="Reviewed private rubric array; required for first preparation")
    args = parser.parse_args()
    manifest = prepare_data(args.herb.resolve(), TASK_ROOT, args.rubrics)
    print(json.dumps({key: manifest[key] for key in ("corpus_records", "sample_records", "content_questions")}, indent=2))


if __name__ == "__main__":
    main()
