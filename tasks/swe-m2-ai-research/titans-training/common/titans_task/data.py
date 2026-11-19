"""Fixed task budgets and runtime access to pretokenized, memory-mapped streams."""

from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor
from transformers import PreTrainedTokenizerBase

from .token_store import TokenFile, open_tokens, read_manifest

EvaluationSplit = Literal["public", "private"]
TokenIds = Tensor | NDArray[np.uint32]
BLOCK_SIZE = 4096
STREAM_TOKENS = 65_536
TRAINING_QUOTAS = (("fineweb_edu", 8_388_608), ("pg19", 2_097_152))
EVALUATION_COUNTS = {
    "public": (("fineweb_edu", 8), ("pg19", 4), ("wikitext103", 4)),
    "private": (("fineweb_edu", 32), ("pg19", 16), ("wikitext103", 16)),
}
EVALUATION_WEIGHTS = (("fineweb_edu", 0.5), ("pg19", 0.25), ("wikitext103", 0.25))


def input_count(tokens: TokenIds) -> int:
    """Count inputs, excluding the final lookahead.

    Args:
        tokens: Int64 reference tensor or one-dimensional uint32 memory map.

    Returns:
        The number of scored input positions.
    """
    return (tokens.numel() if isinstance(tokens, Tensor) else tokens.size) - 1


def training_tokens(data_dir: Path, tokenizer: PreTrainedTokenizerBase) -> NDArray[np.uint32]:
    """Validate the fixed training recipe and open its pretokenized stream.

    Args:
        data_dir: Prepared root containing train/manifest.json and its token file.
        tokenizer: Model tokenizer whose identity must match the prepared data.

    Returns:
        Read-only uint32 memory map of 10,485,761 IDs, including the lookahead.

    Raises:
        ValueError: The tokenizer, quotas, token file or manifest is invalid.
        OSError: Prepared data is missing or unreadable.
    """
    root = data_dir / "train"
    files, metadata = read_manifest(root, "train", tokenizer)
    if (len(files) != 1 or files[0].corpus != "mixed"
            or files[0].inputs != sum(count for _, count in TRAINING_QUOTAS)
            or metadata.get("source_token_counts") != dict(TRAINING_QUOTAS)):
        raise ValueError("Training manifest does not match the fixed source quotas")
    return open_tokens(root, files[0], len(tokenizer))


def packed_batches(tokens: TokenIds) -> Iterator[tuple[Tensor, Tensor]]:
    """Read consecutive pretokenized batches with one shared lookahead position.

    Args:
        tokens: Uint32 memory map or int64 tensor [1, N + 1] for reference checks.

    Yields:
        Writable CPU int64 input/label tensors [1, 4096], with a shorter final
        batch when needed. Only the current mapped block is converted.

    Raises:
        ValueError: Shape or dtype does not represent one nonempty token stream.
    """
    if isinstance(tokens, Tensor):
        if tokens.ndim != 2 or tokens.shape[0] != 1 or tokens.shape[1] < 2 or tokens.dtype != torch.int64:
            raise ValueError("Expected int64 tokens [1, N + 1] for one nonempty stream")
    elif tokens.ndim != 1 or len(tokens) < 2 or tokens.dtype != np.dtype("<u4"):
        raise ValueError("Expected a one-dimensional uint32 stream with a lookahead token")
    count = input_count(tokens)
    for start in range(0, count, BLOCK_SIZE):
        end = min(start + BLOCK_SIZE, count)
        if isinstance(tokens, Tensor):
            block = tokens[:, start:end + 1]
        else:
            block = torch.from_numpy(np.array(tokens[start:end + 1], dtype=np.int64, copy=True))[None, :]
        yield block[:, :-1], block[:, 1:]


def evaluation_files(data_dir: Path, split: EvaluationSplit, tokenizer: PreTrainedTokenizerBase
                     ) -> tuple[tuple[str, TokenFile], ...]:
    """Validate the fixed evaluation mix and ordered pretokenized streams.

    Args:
        data_dir: Prepared data root.
        split: Public development or private final evaluation.
        tokenizer: Current model tokenizer; no text is encoded.

    Returns:
        Corpus/record pairs in the manifest's fixed playback order.

    Raises:
        ValueError: The split, tokenizer, counts or stream lengths are invalid.
        OSError: The prepared manifest cannot be read.
    """
    if split not in EVALUATION_COUNTS:
        raise ValueError("Evaluation split must be 'public' or 'private'")
    records, _ = read_manifest(data_dir / split, split, tokenizer)
    if Counter(record.corpus for record in records) != dict(EVALUATION_COUNTS[split]):
        raise ValueError(f"{split} manifest must contain exactly the fixed corpus stream counts")
    if any(record.inputs != STREAM_TOKENS for record in records):
        raise ValueError(f"Every {split} stream requires exactly {STREAM_TOKENS} input tokens")
    return tuple((record.corpus, record) for record in records)


def evaluation_tokens(data_dir: Path, split: EvaluationSplit, record: TokenFile,
                       tokenizer: PreTrainedTokenizerBase) -> NDArray[np.uint32]:
    """Open a verified evaluation stream without runtime tokenization.

    Args:
        data_dir: Prepared data root.
        split: Split containing the file.
        record: Entry obtained from evaluation_files.
        tokenizer: Model tokenizer providing the vocabulary bound.

    Returns:
        Read-only uint32 IDs, including the final lookahead.
    """
    return open_tokens(data_dir / split, record, len(tokenizer))
