"""Small deterministic application for verifier tests; not a HERB oracle."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal, TypeAlias

import chromadb
from chromadb.config import Settings
from pydantic import BaseModel, Field

RetrievalMethod: TypeAlias = Literal["bm25", "embed", "hybrid"]  # noqa: UP040 - Match the public alias used by candidate implementations.


class IngestEvent(BaseModel):
    corpus_path: str = Field(description="Path to the JSON corpus file.")
    refresh: bool = Field(
        description="Rebuild the index if true; otherwise skip existing document IDs."
    )


class Passage(BaseModel):
    doc_id: str = Field(description="ID of the source document in the vector database.")
    quote: str = Field(description="Exact text from the document's title or content.")


class RetrievedItem(BaseModel):
    passages: list[Passage] = Field(
        description="Source passages relevant to the query."
    )


class GeneratedAnswer(BaseModel):
    answer: str = Field(description="Answer to the user's question.")
    citations: list[Passage] = Field(
        description="Source passages supporting the answer."
    )


def client() -> chromadb.api.ClientAPI:
    """Connect fixture commands to their isolated HTTP database.

    Returns:
        The real client using test-supplied connection settings.
    """
    return chromadb.HttpClient(
        host=os.environ["ORANGE_CHROMA_HOST"],
        port=int(os.environ["ORANGE_CHROMA_PORT"]),
        settings=Settings(anonymized_telemetry=False),
    )


async def ingest(event: IngestEvent) -> None:
    """Persist fixture documents, preserving existing IDs without refresh.

    Args:
        event: Input corpus and replacement flag.
    """
    database = client()
    if event.refresh:
        for collection in database.list_collections():
            database.delete_collection(collection.name)
    collection = database.get_or_create_collection("documents", embedding_function=None)
    existing = set(collection.get()["ids"])
    for row in json.loads(Path(event.corpus_path).read_text()):
        if row["doc_id"] not in existing:
            collection.add(
                ids=[row["doc_id"]],
                documents=[row["content"]],
                embeddings=[
                    [
                        1.0,
                        float(hashlib.sha256(row["content"].encode()).digest()[0])
                        / 255,
                    ]
                ],
                metadatas=[{"title": row["title"]}],
            )
            existing.add(row["doc_id"])


async def retrieve(query: str, retrieval_method: RetrievalMethod) -> RetrievedItem:
    """Return fixture evidence ordered by exact title occurrence.

    Args:
        query: Question text; only used to order the small fixture corpus.
        retrieval_method: Declared method; this controlled double shares one implementation.

    Returns:
        Literal content passages from at most two records.

    Raises:
        FileNotFoundError: Ingestion has not created an index.
    """
    data = (
        client()
        .get_collection("documents", embedding_function=None)
        .get(include=["documents", "metadatas"])
    )
    rows = [
        {"doc_id": identity, "content": body, "title": metadata["title"]}
        for identity, body, metadata in zip(
            data["ids"], data["documents"], data["metadatas"], strict=True
        )
    ]
    selected = [row for row in rows if row["title"] in query]
    selected += [row for row in rows if row not in selected]
    return RetrievedItem(
        passages=[
            Passage(doc_id=row["doc_id"], quote=row["content"]) for row in selected[:2]
        ]
    )


async def generate(query: str) -> GeneratedAnswer:
    """Echo fixture evidence through the required retrieval call.

    Args:
        query: A fixture question.

    Returns:
        An extractive answer with literal citations.
    """
    evidence = await retrieve(query, "hybrid")
    return GeneratedAnswer(
        answer=" ".join(row.quote for row in evidence.passages),
        citations=evidence.passages,
    )
