"""Author-only adapter from a local Chroma index to authenticated Modal SGLang."""

from __future__ import annotations

import asyncio
import math
import os
from functools import lru_cache
from typing import Literal

import httpx


@lru_cache(maxsize=1)
def client() -> httpx.Client:
    """Create a shared authenticated GPU connection pool from runner settings.

    Returns:
        Thread-safe HTTP client; the ephemeral embedding token is never logged.
    """
    return httpx.Client(
        base_url=os.environ["ORACLE_EMBEDDING_URL"],
        timeout=300,
        headers={"Authorization": "Bearer " + os.environ["ORACLE_EMBEDDING_TOKEN"]},
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=100),
    )


def encode(texts: list[str], side: Literal["query", "document"]) -> list[list[float]]:
    """Send bounded batches with the same Jina prefixes as the offline helper.

    Args:
        texts: Ordered strings, never references or private question answers.
        side: Query or document retrieval tower role.

    Returns:
        Validated normalized 1,024-dimensional vectors, in input order.
    """
    prefix = "Query: " if side == "query" else "Document: "
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 64):
        batch = texts[start : start + 64]
        response = client().post(
            "/v1/embeddings",
            json={
                "model": "jina-retrieval",
                "input": [prefix + text for text in batch],
            },
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        if [row["index"] for row in rows] != list(range(len(batch))):
            raise ValueError("Embedding response indices do not match input")
        for row in rows:
            vector = row["embedding"]
            if len(vector) != 1024 or not all(math.isfinite(value) for value in vector):
                raise ValueError("Invalid embedding dimensions or values")
            if abs(math.sqrt(sum(value * value for value in vector)) - 1) > 0.01:
                raise ValueError("Embedding is not normalized")
            vectors.append(vector)
    return vectors


async def embed(
    texts: list[str], side: Literal["query", "document"]
) -> list[list[float]]:
    """Adapt the existing oracle embedding interface to the authorized GPU host.

    Args:
        texts: Input strings in their original order.
        side: Retrieval prefix, query or document.

    Returns:
        One vector per input; no corpus or trajectories are persisted remotely.
    """
    if side not in ("query", "document"):
        raise ValueError("Invalid embedding role")
    return await asyncio.to_thread(encode, texts, side)
