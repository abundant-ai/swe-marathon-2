"""Run the bundled Jina retrieval encoder on this container's GPU."""

from __future__ import annotations

import asyncio
import math
from functools import lru_cache
from threading import Lock
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_ID = "jinaai/jina-embeddings-v5-omni-small"
MODEL_REVISION = "950200abde3a3bcf3d5bdfe5d28fb5bb5e7dfbb0"
MODEL_PATH = "/opt/models/jina"
_LOCK = Lock()


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load the baked model once per process, using only local files.

    Returns:
        The text retrieval encoder on the container's CUDA device. Imports are
        deferred so CLI help and interface discovery do not load model weights.

    Raises:
        RuntimeError: The environment has no available GPU.
        OSError: The image's pinned model files are missing or unreadable.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    if not torch.cuda.is_available():
        raise RuntimeError("The bundled Jina encoder requires the task's GPU")
    return SentenceTransformer(
        MODEL_PATH, device="cuda", trust_remote_code=True, local_files_only=True,
        model_kwargs={"modality": "text", "default_task": "retrieval"},
    )


def _encode(texts: list[str], side: Literal["query", "document"]) -> list[list[float]]:
    """Serialize GPU calls so concurrent requests cannot change adapter state.

    Args:
        texts: Nonempty text batch in input order.
        side: Query or document role, selecting the matching retrieval prefix.

    Returns:
        Finite, normalized 1,024-dimensional vectors.

    Raises:
        ValueError: The encoder returns malformed vectors.
        RuntimeError: Model loading or GPU inference fails.
    """
    with _LOCK:
        model = _load_model()
        encoder = model.encode_query if side == "query" else model.encode_document
        vectors: list[list[float]] = encoder(
            texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False,
        ).tolist()
    if len(vectors) != len(texts) or any(
        len(row) != 1024 or any(not math.isfinite(value) for value in row)
        for row in vectors
    ):
        raise ValueError("Jina returned invalid embeddings")
    return vectors


async def embed(texts: list[str], side: Literal["query", "document"]) -> list[list[float]]:
    """Embed queries or passages locally without blocking the event loop.

    Args:
        texts: Texts to encode in order; empty batches return immediately.
        side: Retrieval role, selecting query or document encoding.

    Returns:
        One normalized 1,024-dimensional vector per input. No service credentials
        or network connection are needed; weights are installed in the image.

    Raises:
        ValueError: The role is invalid or the encoder returns malformed output.
        RuntimeError: The GPU is unavailable or inference fails.
        OSError: Bundled model files cannot be read.
    """
    if side not in ("query", "document"):
        raise ValueError("side must be query or document")
    if not texts:
        return []
    return await asyncio.to_thread(_encode, texts, side)
