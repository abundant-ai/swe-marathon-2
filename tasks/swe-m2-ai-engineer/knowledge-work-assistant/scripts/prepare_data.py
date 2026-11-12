"""Prepare sanitized evaluation inputs and a uniform 4% development sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
from pathlib import Path
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
        Sanitized corpus, content-only held-out cases, and source-file hashes.
        Product team/customer membership fields are deliberately excluded;
        directory records are included as permitted by HERB's task definition.

    Raises:
        ValueError: Duplicate generated identities or malformed content questions.
    """
    corpus: list[dict[str, str]] = []
    cases: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for path in sorted((data_dir / "products").glob("*.json")):
        hashes[str(path.relative_to(data_dir))] = hashlib.sha256(path.read_bytes()).hexdigest()
        product = json.loads(path.read_text())
        for source_type in SOURCE_KEYS:
            for index, record in enumerate(product.get(source_type, [])):
                native_id = str(record.get("id", index))
                corpus.append({
                    "doc_id": f"{path.stem}:{source_type}:{index}:{native_id}",
                    "source_type": source_type,
                    "title": f"{path.stem} / {source_type} / {record.get('title', native_id)}",
                    "content": json.dumps(record, ensure_ascii=False, indent=2),
                })
        for index, row in enumerate(product.get("answerable_questions", [])):
            if row.get("type") == "content":
                reference = row["ground_truth"]
                if not isinstance(reference, (str, list)) or not isinstance(row["question"], str):
                    raise ValueError("Malformed HERB content question")
                cases.append({"question_id": f"{path.stem}:content:{index}", "question": row["question"], "reference": reference})
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


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    """Write canonical UTF-8 JSONL and return its content hash.

    Args:
        path: Destination in the public or private bundle.
        rows: Already separated records; no implicit field filtering occurs here.

    Returns:
        SHA-256 of the exact serialized bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def prepare_data(herb_root: Path, task_root: Path) -> dict[str, Any]:
    """Build ignored data artifacts from the pinned upstream checkout.

    Args:
        herb_root: Existing HERB checkout; this function does not download data.
        task_root: Knowledge-work-assistant task directory.

    Returns:
        Manifest with provenance, full-corpus hashes, and sample definition.

    Raises:
        ValueError: Wrong upstream revision or unexpected holdout size.
    """
    revision = subprocess.check_output(["git", "-C", str(herb_root), "rev-parse", "HEAD"], text=True).strip()
    if revision != HERB_REVISION:
        raise ValueError(f"Expected HERB revision {HERB_REVISION}")
    corpus, cases, hashes = collect_records(herb_root / "data")
    if len(cases) != 238:
        raise ValueError(f"Expected 238 content questions; found {len(cases)}")
    private = task_root / "steps/01-build-rag/tests/private"
    sample_size = int(len(corpus) * SAMPLE_FRACTION)
    sample = random.Random(SAMPLE_SEED).sample(corpus, sample_size)
    manifest = {
        "herb_revision": revision, "corpus_records": len(corpus), "content_questions": len(cases),
        "corpus_sha256": write_jsonl(private / "corpus.jsonl", corpus),
        "cases_sha256": write_jsonl(private / "cases.jsonl", cases),
        "sample_sha256": write_jsonl(task_root / "environment/data/corpus.jsonl", sample),
        "sample_records": sample_size, "sample_fraction": SAMPLE_FRACTION,
        "sample_seed": SAMPLE_SEED, "sampling_unit": "corpus record, without replacement",
        "source_sha256": hashes,
    }
    (private / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    public_manifest = {key: manifest[key] for key in ("herb_revision", "corpus_records", "sample_records", "sample_fraction", "sample_seed", "sample_sha256", "sampling_unit")}
    (task_root / "environment/data/manifest.json").write_text(json.dumps(public_manifest, indent=2) + "\n")
    for directory in (private, task_root / "environment/data"):
        shutil.copyfile(herb_root / "LICENSE.txt", directory / "HERB_LICENSE.txt")
        (directory / "NOTICE.txt").write_text(
            "Data adapted from Salesforce AI Research's HERB benchmark.\n"
            "Source: https://github.com/SalesforceAIResearch/HERB\n"
            f"Revision: {HERB_REVISION}\n"
            "License: Creative Commons Attribution-NonCommercial 4.0 International.\n"
            "Changes: source records normalized to JSONL, directory records included, "
            "questions separated, and a seeded 4% development sample selected.\n"
        )
    return manifest


def main() -> None:
    """Parse author-side paths and print counts without private question text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--herb", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_data(args.herb.resolve(), Path(__file__).resolve().parents[1])
    print(json.dumps({key: manifest[key] for key in ("corpus_records", "sample_records", "content_questions")}, indent=2))


if __name__ == "__main__":
    main()
