"""Pinned public corpus readers with verified local download caches."""

import hashlib
import json
import re
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pyarrow.parquet as pq

FINEWEB_REV = "87f09149ef4734204d70ed1d046ddc9ca3f2b8f9"
WIKITEXT_REV = "b08601e04326c79dfdd32d625aee71d232d685c3"
PG19_REV = "4d28bd77e66947ad3835cf78ed7aaeb4dd87ad8b"
TOKENIZER_ID = "NousResearch/Llama-2-7b-hf"
TOKENIZER_REV = "8efe6c9b93655b934e27bd9981e3ec13e55aee9d"
SEED = "titans-lm-data-v1-2026-11-19"


@dataclass(frozen=True)
class Document:
    """A complete source document before tokenization or stream packing."""

    corpus: str
    identity: str
    group: str
    text: str
    origin: dict[str, str | int]


def stable_order(value: str) -> str:
    """Return a deterministic selection key.

    Args:
        value: Stable source identity.

    Returns:
        Seeded SHA-256 used only for source ordering and partitioning.
    """
    return hashlib.sha256(f"{SEED}|{value}".encode()).hexdigest()


def download(url: str, destination: Path, *, expected_sha256: str | None = None) -> Path:
    """Download public bytes, resume interrupted transfers and verify cached files.

    Args:
        url: Public HTTPS source URL, pinned by revision where supported.
        destination: Local author-side cache path.
        expected_sha256: Published source digest, if available.

    Returns:
        Verified local file. A sidecar records URL, SHA-256 and GCS generation.

    Raises:
        ValueError: Downloaded bytes fail the expected digest or resume range.
        OSError: The source remains unavailable after three attempts.
    """
    sidecar = destination.with_name(destination.name + ".source.json")
    if destination.exists() and sidecar.exists():
        metadata = json.loads(sidecar.read_text())
        with destination.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if metadata.get("url") == url and digest == (expected_sha256 or metadata.get("sha256")):
            return destination
        raise ValueError(f"Cached source identity or digest mismatch: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    generation = ""
    for attempt in range(3):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "titans-corpus-preparation/1"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=90) as response:
                append = offset > 0 and response.status == 206
                if append and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                    raise ValueError("Unexpected Content-Range while resuming a corpus file")
                generation = response.headers.get("x-goog-generation", "")
                written = offset if append else 0
                next_report = written + 128 * 1024 * 1024
                with partial.open("ab" if append else "wb") as handle:
                    while chunk := response.read(4 * 1024 * 1024):
                        handle.write(chunk)
                        written += len(chunk)
                        if written >= next_report:
                            print(f"download {destination.name}: {written // (1024 * 1024)} MiB", flush=True)
                            next_report = written + 128 * 1024 * 1024
            break
        except OSError:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    with partial.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"Downloaded source digest mismatch: {destination}")
    partial.replace(destination)
    sidecar.write_text(json.dumps({"url": url, "sha256": digest,
                                   "bytes": destination.stat().st_size, "gcs_generation": generation},
                                  indent=2) + "\n")
    return destination


def tokenizer_directory(cache: Path) -> Path:
    """Fetch only the pinned tokenizer files, without downloading model weights.

    Args:
        cache: Preparation cache root.

    Returns:
        Directory loadable by AutoTokenizer with local_files_only=True.
    """
    root = cache / "tokenizer"
    for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"):
        download(f"https://huggingface.co/{TOKENIZER_ID}/resolve/{TOKENIZER_REV}/{name}", root / name)
    return root


def pg19_documents(split: str, cache: Path) -> Iterator[Document]:
    """Read official PG19 books in deterministic hash order within their split.

    Args:
        split: Official train, validation or test split.
        cache: Source download cache.

    Yields:
        Complete books with pinned split-list and individual object provenance.
    """
    if split not in {"train", "validation", "test"}:
        raise ValueError("Unknown PG19 split")
    index = download(f"https://huggingface.co/datasets/deepmind/pg19/resolve/{PG19_REV}/data/{split}_files.txt",
                     cache / "pg19" / f"{split}_files.txt")
    for relative in sorted(index.read_text().splitlines(), key=stable_order):
        path = download(f"https://storage.googleapis.com/deepmind-gutenberg/{relative}", cache / "pg19" / relative)
        metadata = json.loads(path.with_name(path.name + ".source.json").read_text())
        identity = f"pg19:{Path(relative).stem}"
        yield Document("pg19", identity, identity, path.read_text(encoding="utf-8"),
                       {"repo": "deepmind/pg19", "revision": PG19_REV, "source_split": split,
                        "file": relative, "sha256": metadata["sha256"],
                        "gcs_generation": metadata["gcs_generation"]})


def wikitext_documents(cache: Path) -> Iterator[Document]:
    """Reassemble raw WikiText-103 training records into whole articles.

    Args:
        cache: Cache for the pinned Parquet shards.

    Yields:
        Whole articles; subsection headings do not create new document boundaries.
    """
    digests = ("74da360f23826045b3e6ac6375411fdb15f003030aa74f2596ed08b857cb9212",
               "ba090ac30dbf5461e8dcbdd1a1b8e6f3cf9c2c756d64f0c1220450acd514f720")
    title = ""
    pieces: list[str] = []
    origin: dict[str, str | int] = {}
    for shard, digest in enumerate(digests):
        relative = f"wikitext-103-raw-v1/train-{shard:05d}-of-00002.parquet"
        path = download(f"https://huggingface.co/datasets/Salesforce/wikitext/resolve/{WIKITEXT_REV}/{relative}",
                        cache / "wikitext" / Path(relative).name, expected_sha256=digest)
        position = 0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1024, columns=["text"]):
            for text in batch.column(0).to_pylist():
                heading = re.fullmatch(r"=\s*([^=]+?)\s*=", text.strip())
                if heading:
                    if title:
                        identity = f"wikitext:{title.casefold()}"
                        yield Document("wikitext103", identity, identity, "".join(pieces), origin)
                    title, pieces = heading.group(1).strip(), []
                    origin = {"repo": "Salesforce/wikitext", "revision": WIKITEXT_REV,
                              "source_split": "train", "file": relative, "first_record": position}
                if title:
                    pieces.append(text)
                position += 1
    if title:
        identity = f"wikitext:{title.casefold()}"
        yield Document("wikitext103", identity, identity, "".join(pieces), origin)


def canonical_url(url: str) -> str:
    """Group repeat crawls of a web page independently of common tracking fields.

    Args:
        url: Source URL from FineWeb-Edu.

    Returns:
        Scheme-independent canonical page key with fragments removed.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold().removeprefix("www.")
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.casefold().startswith("utm_") and key.casefold() not in {"fbclid", "gclid"}]
    return urlunsplit(("", host, parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))


def fineweb_documents(cache: Path) -> Iterator[Document]:
    """Read the pinned 10BT sample's first shard, which exceeds the pilot budget.

    Args:
        cache: Cache for the source Parquet file.

    Yields:
        Complete web documents with canonical URL groups and exact source positions.
    """
    relative = "sample/10BT/000_00000.parquet"
    path = download(f"https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu/resolve/{FINEWEB_REV}/{relative}",
                    cache / "fineweb" / "000_00000.parquet",
                    expected_sha256="b1ba7b2ce4cb5ea6ef42dca40263eabb85f37700d01693a68e9b30a31d78e871")
    position = 0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=128, columns=["id", "url", "text"]):
        for record in batch.to_pylist():
            identity = f"fineweb:{record['id']}"
            yield Document("fineweb_edu", identity, canonical_url(record["url"]), record["text"],
                           {"repo": "HuggingFaceFW/fineweb-edu", "revision": FINEWEB_REV,
                            "source_split": "sample-10BT/train", "file": relative,
                            "record": position, "url": record["url"]})
            position += 1
