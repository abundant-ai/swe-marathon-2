"""Ad hoc CPU checks for corpus preparation and optional real-artifact auditing."""

import argparse
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from preparation import sources  # noqa: E402
from preparation.build import TokenizedDocument, training_stream  # noqa: E402
from preparation.dedup import DuplicateIndex  # noqa: E402
from titans_task import data  # noqa: E402
from titans_task.token_store import open_tokens, read_manifest  # noqa: E402


def check_duplicates() -> None:
    """Check whole-identity, normalized-copy and long-excerpt exclusions."""
    index = DuplicateIndex()
    words = [f"word{number:05d}" for number in range(4000)]
    original = " ".join(words)
    assert index.accept("book", original) is not None
    assert index.accept("book", "a different version") is None
    assert index.accept("mirror", original.upper().replace(" ", "  ")) is None
    assert index.accept("excerpt", " ".join(words[500:3000]) + " new ending") is None
    assert index.accept("unrelated", " ".join(f"other{number}" for number in range(2000))) is not None
    assert index.counts == {"examined": 5, "accepted": 2, "repeat_group": 1,
                            "exact_copy": 1, "near_copy": 1}
    assert sources.canonical_url("https://www.Example.org/story/?utm_source=a#part") == \
        sources.canonical_url("http://example.org/story")


def check_wikitext(root: Path) -> None:
    """Check article reconstruction, nested headings and cross-shard continuity.

    Args:
        root: Temporary directory for two miniature source shards.
    """
    texts = (["\n", " = First = \n", "first text\n", " = = Section = = \n"],
             ["continued text\n", " = Second = \n", "second text\n"])
    for index, rows in enumerate(texts):
        pq.write_table(pa.table({"text": rows}), root / f"train-{index:05d}-of-00002.parquet")

    def cached_download(url: str, destination: Path, *, expected_sha256: str | None = None) -> Path:
        """Substitute local shards for the public download adapter.

        Args:
            url: Unused source URL.
            destination: Cache path identifying the requested shard.
            expected_sha256: Unused published digest for the real shard.

        Returns:
            The corresponding local synthetic Parquet file.
        """
        return root / destination.name

    with patch.object(sources, "download", cached_download):
        documents = list(sources.wikitext_documents(root))
    assert len(documents) == 2
    assert documents[0].text == "".join(texts[0][1:] + texts[1][:1])
    assert documents[1].text == "".join(texts[1][1:])
    assert documents[0].group == "wikitext:first"
    assert documents[0].origin["first_record"] == 1
    assert documents[1].origin["first_record"] == 1


def check_training_packing(root: Path) -> None:
    """Check exact quotas, EOS at trimmed documents and both lookahead cases.

    Args:
        root: Temporary output root for independent packing cases.
    """
    for name, final_documents, expected in (
        ("within", [[3, 3, 2]], [3, 3, 2, 4, 2, 3, 3, 2, 3, 3, 2]),
        ("next", [[3, 2], [5, 2]], [3, 3, 2, 4, 2, 3, 3, 2, 3, 2, 5]),
    ):
        documents = {
            "fineweb_edu": [TokenizedDocument(ids, {}) for ids in [[3, 3, 2], [3, 3, 2], *final_documents]],
            "pg19": [TokenizedDocument([4, 4, 2], {})],
        }
        with patch.object(data, "TRAINING_QUOTAS", (("fineweb_edu", 8), ("pg19", 2))):
            record = training_stream(root / name, documents)
        values = open_tokens(root / name, record, 10)
        np.testing.assert_array_equal(values, expected)
        records = [json.loads(line) for line in (root / name / "documents.jsonl").read_text().splitlines()]
        assert records[1]["closed_with_eos"] and records[1]["used_tokens"] == 2
        with patch.object(data, "BLOCK_SIZE", 4):
            batches = list(data.packed_batches(values))
        assert [inputs.shape[1] for inputs, _ in batches] == [4, 4, 2]
        for index in range(len(batches) - 1):
            assert batches[index][1][0, -1] == batches[index + 1][0][0, 0]


def audit_artifacts(root: Path) -> dict[str, object]:
    """Verify real stream coverage, source quotas and document separation.

    Args:
        root: Prepared root with all three split manifests and saved tokenizer.

    Returns:
        Counts suitable for a local JSON audit report. Token contents are checked
        through the same checksum, vocabulary and shape checks used at runtime.
    """
    tokenizer = AutoTokenizer.from_pretrained(root / "tokenizer", local_files_only=True, use_fast=True)
    groups: set[tuple[str, str]] = set()
    hashes: set[str] = set()
    report: dict[str, object] = {}
    for split in ("train", "public", "private"):
        files, _ = read_manifest(root / split, split, tokenizer)
        if split == "train":
            data.training_tokens(root, tokenizer)
        else:
            data.evaluation_files(root, split, tokenizer)
        provenance = [json.loads(line) for line in (root / split / "documents.jsonl").read_text().splitlines()]
        streams: dict[str, list[dict[str, object]]] = defaultdict(list)
        documents: Counter[str] = Counter()
        sources_used: Counter[str] = Counter()
        input_tokens = 0
        batches = 0
        for item in provenance:
            group = (item["corpus"], item["group"])
            assert group not in groups, f"Repeated document group: {group}"
            assert item["normalized_sha256"] not in hashes, "Repeated normalized document text"
            groups.add(group)
            hashes.add(item["normalized_sha256"])
            if item["corpus"] == "pg19":
                assert item["origin"]["source_split"] == {"train": "train", "public": "validation", "private": "test"}[split]
            if item["corpus"] == "wikitext103":
                assert split != "train" and item["origin"]["source_split"] == "train"
            documents[item["corpus"]] += 1
            streams[item["stream"]].append(item)
        assert set(streams) == {record.path for record in files}
        for record in files:
            ids = open_tokens(root / split, record, len(tokenizer))
            position = 0
            for item in streams[record.path]:
                assert item["start"] == position and item["source_token_start"] == 0
                used = item["used_tokens"]
                assert 0 < used <= item["source_tokens"]
                sources_used[item["corpus"]] += max(0, min(used, record.inputs - position))
                position += used
                if item["closed_with_eos"]:
                    assert ids[position - 1] == tokenizer.eos_token_id
            assert position == record.inputs + 1
            for inputs, labels in data.packed_batches(ids):
                assert inputs.shape == labels.shape == (1, data.BLOCK_SIZE)
                assert (inputs[:, 1:] == labels[:, :-1]).all()
                input_tokens += inputs.numel()
                batches += 1
        expected = dict(data.TRAINING_QUOTAS) if split == "train" else {
            corpus: count * data.STREAM_TOKENS for corpus, count in data.EVALUATION_COUNTS[split]
        }
        assert sources_used == expected
        report[split] = {"inputs": input_tokens, "batches": batches, "streams": len(files),
                         "documents": dict(documents), "source_input_tokens": dict(sources_used),
                         "token_file_bytes": sum((root / split / record.path).stat().st_size for record in files)}
    return report


def main() -> None:
    """Run small CPU checks and audit a prepared artifact tree when requested."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    check_duplicates()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        check_wikitext(root)
        check_training_packing(root)
    print("PASS duplicate screening, article reconstruction and exact-budget packing", flush=True)
    if args.data_dir is not None:
        report = audit_artifacts(args.data_dir)
        serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
        args.data_dir.with_name(args.data_dir.name + ".audit.json").write_text(serialized)
        print(serialized, end="")


if __name__ == "__main__":
    main()
