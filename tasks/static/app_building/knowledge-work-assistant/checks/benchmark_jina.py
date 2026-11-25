"""Measure the supplied embedding helper on a GPU; this is not a task grader."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from jina import embed


async def benchmark() -> dict[str, Any]:
    """Measure cold start, warm queries, corpus throughput, and parity vectors.

    Returns:
        Timings and vectors for comparison with the former helper on the same
        GPU. The corpus batches use 128 distinct development records per round.
        Includes no held-out questions, reference answers, or credentials.
    """
    texts = [
        "Who owns the release?",
        "The platform team owns the November release.",
        "",
        "Café 東京 — rollout notes",
        "Deployment approval requires two reviewers. " * 100,
    ]
    start = time.perf_counter()
    query = await embed(texts, "query")
    cold = time.perf_counter() - start
    document = await embed(texts, "document")
    query_ms: list[float] = []
    for index in range(20):
        start = time.perf_counter()
        await embed([f"Who approved deployment number {index}?"], "query")
        query_ms.append(1000 * (time.perf_counter() - start))
    corpus_path = Path("/data/corpus.json")
    corpus = json.loads(corpus_path.read_text())
    documents_per_second: list[float] = []
    for offset in (0, 128, 256):
        batch = [
            row["title"] + "\n" + row["content"]
            for row in corpus[offset : offset + 128]
        ]
        start = time.perf_counter()
        await embed(batch, "document")
        documents_per_second.append(len(batch) / (time.perf_counter() - start))
    start = time.perf_counter()
    await asyncio.gather(
        *[
            embed([f"Who owns concurrent release {index}?"], "query")
            for index in range(16)
        ]
    )
    return {
        "texts": texts,
        "query": query,
        "document": document,
        "cold_seconds": cold,
        "query_median_ms": statistics.median(query_ms),
        "query_p95_ms": sorted(query_ms)[18],
        "query_samples_ms": query_ms,
        "documents_per_second": documents_per_second,
        "documents_per_second_median": statistics.median(documents_per_second),
        "concurrent_16_seconds": time.perf_counter() - start,
    }


if __name__ == "__main__":
    print("RESULT=" + json.dumps(asyncio.run(benchmark())), flush=True)
