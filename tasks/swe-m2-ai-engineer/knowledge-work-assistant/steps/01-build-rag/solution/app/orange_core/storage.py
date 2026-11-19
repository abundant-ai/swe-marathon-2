"""Persist original records in Chroma and lexical chunks in SQLite FTS5."""

from __future__ import annotations

import asyncio
import fcntl
import os
import re
import sqlite3
from contextlib import contextmanager
from itertools import batched
from pathlib import Path
from typing import Iterator, Literal

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings as ChromaSettings

from orange_core.config import Settings, TOP_K
from orange_core.corpus import read_documents
from orange_core.telemetry import span
from orange_core.retrieval import Document, Hit, chunk_document, mean_vector, reciprocal_rank_fusion


@contextmanager
def state_lock(app_root: Path, exclusive: bool) -> Iterator[None]:
    """Coordinate ingestion and reads across independent CLI processes.

    Args:
        app_root: Installed workspace; the lock is outside replaceable state.
        exclusive: True for ingestion, False for concurrent retrieval readers.

    Yields:
        Control while holding the advisory lock; exceptions release it.
    """
    with (app_root / ".orange-index.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def chroma_client(app_root: Path) -> ClientAPI:
    """Connect to the supplied protected vector service without model downloads.

    Args:
        app_root: Application workspace; database storage belongs to the service.

    Returns:
        Chroma's HTTP client with telemetry disabled.
    """
    return chromadb.HttpClient(
        host=os.environ["ORANGE_CHROMA_HOST"], port=int(os.environ["ORANGE_CHROMA_PORT"]),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def require_index(app_root: Path) -> None:
    """Reject answering before a complete ingestion has finished.

    Args:
        app_root: Workspace containing the index completion marker.

    Raises:
        RuntimeError: State is absent or an ingestion was interrupted.
    """
    if not (app_root / "state/READY").is_file():
        raise RuntimeError("Index unavailable; run orange ingest first (use --refresh after an interrupted ingestion)")


async def embed_texts(texts: list[str], side: Literal["query", "document"]) -> list[list[float]]:
    """Use the environment's GPU helper, imported only when vectors are needed.

    Args:
        texts: Ordered passages or queries to embed.
        side: Jina's retrieval role and prefix selection.

    Returns:
        One embedding per input, supplied by the existing local SGLang service.
    """
    from jina import embed

    return await embed(texts, side)


def ingest_corpus(app_root: Path, path: Path, refresh: bool, settings: Settings) -> None:
    """Ingest a JSON corpus under an exclusive lock, called in a worker thread.

    Validate the complete input before changing state. Existing IDs are skipped
    on append. Refresh deletes both collections and rebuilds lexical state.
    READY is removed during mutation: a failed ingestion cannot silently expose
    mismatched indexes, and must be repaired with refresh.

    Args:
        app_root: Installed application workspace.
        path: Public JSON array of corpus records.
        refresh: Whether to replace all prior records and chunks.
        settings: Chunk sizes and embedding batch size.

    Raises:
        ValueError: Input contains duplicate IDs or invalid records.
        RuntimeError: Append was requested on an interrupted index.
    """
    identities: set[str] = set()
    for document in read_documents(path):
        if document.doc_id in identities:
            raise ValueError("Corpus document IDs must be unique")
        identities.add(document.doc_id)
    del identities
    with state_lock(app_root, exclusive=True):
        state = app_root / "state"
        ready = state / "READY"
        if state.exists() and not refresh and not ready.exists():
            raise RuntimeError("Incomplete index; ingest with --refresh")
        state.mkdir(exist_ok=True)
        client = chroma_client(app_root)
        ready.unlink(missing_ok=True)
        if refresh:
            while collections := client.list_collections(limit=100):
                for collection in collections:
                    client.delete_collection(collection.name)
        originals = client.get_or_create_collection("documents", embedding_function=None)
        chunks = client.get_or_create_collection(
            "chunks", embedding_function=None, configuration={"hnsw": {"space": "cosine"}},
        )
        with sqlite3.connect(state / "lexical.sqlite3") as database:
            if refresh:
                database.execute("DROP TABLE IF EXISTS passages")
            database.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5("
                "chunk_id UNINDEXED, doc_id UNINDEXED, title, body, tokenize='unicode61')"
            )
            for batch_number, items in enumerate(batched(read_documents(path), settings.ingest_batch_size)):
                batch = list(items)
                existing = {
                    identity for page in batched(batch, 100)
                    for identity in originals.get(ids=[row.doc_id for row in page], limit=100, include=[])["ids"]
                }
                batch = [row for row in batch if row.doc_id not in existing]
                if not batch:
                    continue
                grouped = [chunk_document(row, settings.chunk_chars, settings.chunk_overlap) for row in batch]
                # Empty records still need a document vector but no searchable quote.
                inputs = [f"{row.title}\n{hit.quote}" for row, hits in zip(batch, grouped) for hit in hits]
                inputs.extend(row.title or row.doc_id for row, hits in zip(batch, grouped) if not hits)
                with span("ingestion.embed_batch", batch=batch_number, documents=len(batch), chunks=len(inputs)):
                    vectors = asyncio.run(embed_texts(inputs, "document"))
                if len(vectors) != len(inputs):
                    raise ValueError("Embedding count differs from input count")
                hits = [hit for group in grouped for hit in group]
                chunk_vectors = vectors[:len(hits)]
                offset = 0
                empty_offset = len(hits)
                document_vectors: list[list[float]] = []
                for group in grouped:
                    if group:
                        document_vectors.append(mean_vector(chunk_vectors[offset:offset + len(group)]))
                        offset += len(group)
                    else:
                        document_vectors.append(vectors[empty_offset])
                        empty_offset += 1
                originals.add(
                    ids=[row.doc_id for row in batch], documents=[row.content for row in batch],
                    embeddings=document_vectors,
                    metadatas=[{"title": row.title, "source_type": row.source_type} for row in batch],
                )
                # Keep writes below Chroma's maximum even for a long source record.
                limit = client.get_max_batch_size()
                for position in range(0, len(hits), limit):
                    part = hits[position:position + limit]
                    chunks.add(
                        ids=[hit.chunk_id for hit in part], documents=[hit.quote for hit in part],
                        embeddings=chunk_vectors[position:position + limit],
                        metadatas=[{"doc_id": hit.doc_id} for hit in part],
                    )
                database.executemany(
                    "INSERT INTO passages(chunk_id, doc_id, title, body) VALUES (?, ?, ?, ?)",
                    [(hit.chunk_id, hit.doc_id, row.title, hit.quote)
                     for row, group in zip(batch, grouped) for hit in group],
                )
                database.commit()
                if batch_number % 100 == 0:
                    import sys
                    print(f"Ingested {originals.count()} documents", file=sys.stderr, flush=True)
        ready.write_text("Index complete\n")


def lexical_search(app_root: Path, query: str) -> list[Hit]:
    """Rank matching chunks with SQLite's built-in BM25 implementation.

    Args:
        app_root: Workspace containing a complete lexical index.
        query: Free text; tokens are quoted to prevent FTS operator injection.

    Returns:
        Up to 20 matches, best BM25 score first; punctuation-only queries return [].
    """
    tokens = list(dict.fromkeys(re.findall(r"\w+", query, flags=re.UNICODE)))
    if not tokens:
        return []
    match = " OR ".join(f'"{token}"' for token in tokens)
    uri = (app_root / "state/lexical.sqlite3").as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as database:
        rows = database.execute(
            "SELECT chunk_id, doc_id, body FROM passages WHERE passages MATCH ? "
            "ORDER BY bm25(passages), chunk_id LIMIT ?", (match, TOP_K),
        ).fetchall()
    return [Hit(*row) for row in rows]


def search_index(app_root: Path, query: str, method: str, vector: list[float] | None) -> list[Hit]:
    """Read independent lexical/vector rankings and optionally fuse their ranks.

    Args:
        app_root: Workspace containing Chroma and SQLite indexes.
        query: Search phrase for BM25.
        method: bm25, embed, or hybrid.
        vector: Query embedding, required for embed and hybrid.

    Returns:
        At most 20 exact passages; empty indexes produce no hits.
    """
    if method not in {"bm25", "embed", "hybrid"}:
        raise ValueError(f"Unknown retrieval method: {method}")
    with state_lock(app_root, exclusive=False):
        require_index(app_root)
        lexical = lexical_search(app_root, query) if method != "embed" else []
        if method == "bm25":
            return lexical
        if vector is None:
            raise ValueError("Embedding retrieval requires a query vector")
        chunks = chroma_client(app_root).get_collection("chunks", embedding_function=None)
        dense: list[Hit] = []
        if chunks.count():
            result = chunks.query(query_embeddings=[vector], n_results=min(TOP_K, chunks.count()),
                                  include=["documents", "metadatas"])
            for identity, body, metadata in zip(result["ids"][0], result["documents"][0], result["metadatas"][0]):
                dense.append(Hit(identity, str(metadata["doc_id"]), body))
        return reciprocal_rank_fusion([lexical, dense]) if method == "hybrid" else dense
