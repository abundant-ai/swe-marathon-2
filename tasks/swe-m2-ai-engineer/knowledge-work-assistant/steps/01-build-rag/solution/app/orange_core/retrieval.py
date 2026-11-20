"""Pure chunking and rank-fusion operations used by the persisted index."""

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from pydantic import BaseModel, Field

from orange_core.config import RRF_K, TOP_K


class Document(BaseModel):
    """One public corpus record, retaining its exact original content."""

    doc_id: str = Field(min_length=1)
    source_type: str
    title: str
    content: str


@dataclass(frozen=True)
class Hit:
    """A stable chunk identity and its exact source passage."""

    chunk_id: str
    doc_id: str
    quote: str


def chunk_document(document: Document, size: int, overlap: int) -> list[Hit]:
    """Split a body into overlapping exact excerpts for both search indexes.

    Args:
        document: Original record; its body is never normalized or rewritten.
        size: Maximum characters per chunk.
        overlap: Shared characters between adjacent chunks, smaller than size.

    Returns:
        Stable chunk IDs and verbatim passages. Empty bodies use the title;
        a record with neither text nor title has no searchable chunks.
    """
    if not 0 <= overlap < size:
        raise ValueError("Require 0 <= overlap < size")
    text = document.content or document.title
    prefix = hashlib.sha256(document.doc_id.encode()).hexdigest()
    hits: list[Hit] = []
    for start in range(0, len(text), size - overlap):
        hits.append(Hit(f"{prefix}:{start}", document.doc_id, text[start:start + size]))
        if start + size >= len(text):
            break
    return hits


def mean_vector(vectors: Sequence[Sequence[float]]) -> list[float]:
    """Pool chunk vectors into a normalized document vector for Chroma.

    Args:
        vectors: Nonempty, equal-dimensional embedding vectors for one document.

    Returns:
        Unit-length arithmetic mean, or the first vector if the mean cancels.
    """
    if not vectors or not vectors[0] or len({len(row) for row in vectors}) != 1:
        raise ValueError("Expected nonempty equal-dimensional embeddings")
    mean = [sum(column) / len(vectors) for column in zip(*vectors)]
    norm = math.sqrt(sum(value * value for value in mean))
    return [value / norm for value in mean] if norm else list(vectors[0])


def reciprocal_rank_fusion(rankings: Sequence[Sequence[Hit]]) -> list[Hit]:
    """Fuse independent rankings with equal weights and fixed k=20.

    Args:
        rankings: Ordered retrieval results; repeated IDs within a list count once.

    Returns:
        At most 20 chunks ordered by sum(1 / (20 + one_based_rank)). Chunk ID
        breaks ties deterministically. Raw BM25 and vector scores are not mixed.
    """
    scores: dict[str, float] = defaultdict(float)
    hits: dict[str, Hit] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, hit in enumerate(ranking, start=1):
            if hit.chunk_id not in seen:
                scores[hit.chunk_id] += 1 / (RRF_K + rank)
                hits[hit.chunk_id] = hit
                seen.add(hit.chunk_id)
    ordered = sorted((-score, identity) for identity, score in scores.items())
    return [hits[identity] for _, identity in ordered[:TOP_K]]
