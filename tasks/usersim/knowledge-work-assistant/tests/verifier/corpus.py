"""Read authoritative JSON records by byte offset without loading a multi-GB corpus."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from pathlib import Path

from verifier.contracts import SourceDocument


def file_hash(path: Path) -> str:
    """Hash an input file without retaining its contents in memory.

    Args:
        path: Existing regular input file.

    Returns:
        Lowercase SHA-256 of the exact bytes.
    """
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class IndexedCorpus(Mapping[str, SourceDocument]):
    """Read-only document lookup; the companion index contains offsets, not vectors."""

    def __init__(self, path: Path) -> None:
        """Select the JSON corpus and its trusted, separately authenticated index.

        Args:
            path: Corpus JSON array whose offsets are stored beside it.
        """
        self.path = path
        self.index = path.with_suffix(".index.sqlite")

    def connect(self) -> sqlite3.Connection:
        """Open the trusted byte-offset table read-only.

        Returns:
            A short-lived SQLite connection owned by the calling method.
        """
        return sqlite3.connect(self.index.resolve().as_uri() + "?mode=ro", uri=True)

    def __len__(self) -> int:
        """Return the indexed record count without reading document bodies."""
        connection = self.connect()
        try:
            return connection.execute("SELECT count(*) FROM records").fetchone()[0]
        finally:
            connection.close()

    def __iter__(self) -> Iterator[str]:
        """Yield source IDs in their original corpus order, closing on completion."""
        connection = self.connect()
        try:
            for row in connection.execute(
                "SELECT doc_id FROM records ORDER BY ordinal"
            ):
                yield row[0]
        finally:
            connection.close()

    def __getitem__(self, identity: str) -> SourceDocument:
        """Resolve one original record from its authenticated byte range.

        Args:
            identity: Original corpus document ID, including candidate-proposed IDs.

        Returns:
            A fresh original record; candidate text is never used as source evidence.

        Raises:
            KeyError: The requested identity is absent.
            ValueError: The index points at a different record.
        """
        connection = self.connect()
        try:
            location = connection.execute(
                "SELECT offset, length FROM records WHERE doc_id=?", (identity,)
            ).fetchone()
        finally:
            connection.close()
        if location is None:
            raise KeyError(identity)
        with self.path.open("rb") as stream:
            stream.seek(location[0])
            record = json.loads(stream.read(location[1]))
        if record["doc_id"] != identity:
            raise ValueError("Corpus offset index disagrees with source identity")
        return record

    def body_hashes(self) -> dict[str, str]:
        """Return original body hashes for persistence checks without parsing bodies.

        Returns:
            Trusted document ID to SHA-256 mapping for all source records.
        """
        connection = self.connect()
        try:
            return dict(connection.execute("SELECT doc_id, body_sha256 FROM records"))
        finally:
            connection.close()


def open_corpus(path: Path) -> Mapping[str, SourceDocument]:
    """Open prepared inputs efficiently, allowing small unindexed test fixtures.

    Args:
        path: Authoritative corpus array. Production input loading authenticates
            and requires the companion index before calling this function.

    Returns:
        Lazy production mapping or an in-memory mapping for controlled fixtures.
    """
    if path.with_suffix(".index.sqlite").is_file():
        return IndexedCorpus(path)
    rows = json.loads(path.read_text())
    documents = {row["doc_id"]: row for row in rows}
    if len(documents) != len(rows):
        raise ValueError("Duplicate corpus document IDs")
    return documents
