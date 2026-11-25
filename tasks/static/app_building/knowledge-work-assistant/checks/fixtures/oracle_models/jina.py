"""Deterministic CPU vectors for oracle contract tests, never shipped at runtime."""

import hashlib
import math
import re
from typing import Literal


async def embed(
    texts: list[str], side: Literal["query", "document"]
) -> list[list[float]]:
    """Hash tokens into normalized vectors without GPU or network access.

    Args:
        texts: Inputs in retrieval order.
        side: Accepted helper role; both use the same controlled feature space.

    Returns:
        One 64-dimensional unit vector per input, unrelated to Jina quality.
    """
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * 64
        for token in re.findall(r"\w+", text.lower()) or ["empty"]:
            vector[hashlib.sha256(token.encode()).digest()[0] % 64] += 1
        norm = math.sqrt(sum(value * value for value in vector))
        vectors.append([value / norm for value in vector])
    return vectors
