"""Algorithm-independent token files and tokenizer identity checks."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

import numpy as np
from numpy.typing import NDArray
from transformers import PreTrainedTokenizerBase, PreTrainedTokenizerFast


@dataclass(frozen=True)
class TokenFile:
    """One stream and its final lookahead, relative to a split directory."""

    path: str
    corpus: str
    inputs: int
    sha256: str


def tokenizer_identity(tokenizer: PreTrainedTokenizerBase) -> dict[str, str | int]:
    """Fingerprint tokenization semantics without encoding input text.

    Args:
        tokenizer: Fast tokenizer shared by preparation and model construction.

    Returns:
        Fingerprint, vocabulary size and EOS ID. Local paths and transient
        padding/truncation settings do not affect identity.

    Raises:
        ValueError: The tokenizer has no fast backend or EOS separator.
    """
    if not isinstance(tokenizer, PreTrainedTokenizerFast) or tokenizer.eos_token_id is None:
        raise ValueError("Pretokenized streams require a fast tokenizer with an EOS token")
    backend = json.loads(tokenizer.backend_tokenizer.to_str())
    backend.pop("padding", None)
    backend.pop("truncation", None)
    payload = {"backend": backend, "eos": tokenizer.eos_token_id,
               "bos": tokenizer.bos_token_id, "unk": tokenizer.unk_token_id,
               "vocab_size": len(tokenizer)}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"fingerprint": digest, "vocab_size": len(tokenizer), "eos_token_id": tokenizer.eos_token_id}


def file_digest(path: Path) -> str:
    """Hash a file without loading it into memory.

    Args:
        path: File whose bytes define artifact identity.

    Returns:
        Hexadecimal SHA-256 digest.
    """
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_tokens(root: Path, path: str, corpus: str,
                 ids: Sequence[int] | NDArray[np.integer]) -> TokenFile:
    """Write a portable uint32 NPY stream for memory-mapped reads.

    Args:
        root: Split output directory.
        path: Relative .npy file name beneath root.
        corpus: Source name or mixed for combined training data.
        ids: Ordered IDs including one final lookahead token.

    Returns:
        Manifest entry with input count and file checksum.

    Raises:
        ValueError: IDs or the relative path are invalid.
        FileExistsError: The destination already exists.
    """
    values = np.asarray(ids)
    if (values.ndim != 1 or len(values) < 2 or not np.issubdtype(values.dtype, np.integer)
            or values.min() < 0 or values.max() > np.iinfo(np.uint32).max):
        raise ValueError("Expected nonnegative integer IDs and one lookahead token")
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".npy":
        raise ValueError("Token path must be relative and end in .npy")
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as handle:
        np.save(handle, values.astype("<u4", copy=False), allow_pickle=False)
    return TokenFile(path, corpus, len(values) - 1, file_digest(destination))


def write_manifest(root: Path, split: str, tokenizer: PreTrainedTokenizerBase,
                    files: Sequence[TokenFile], *, metadata: Mapping[str, object] | None = None) -> None:
    """Record tokenizer identity, token files and preparation provenance.

    Args:
        root: Directory containing the split's token files.
        split: Logical split name.
        tokenizer: Tokenizer used to write these IDs.
        files: Entries returned by write_tokens.
        metadata: JSON-serializable revisions, quotas and preparation details.
    """
    root.mkdir(parents=True, exist_ok=True)
    payload = {"format": "token-streams-v1", "split": split,
               "tokenizer": tokenizer_identity(tokenizer), "files": [asdict(item) for item in files],
               "metadata": dict(metadata or {})}
    with (root / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def read_manifest(root: Path, split: str, tokenizer: PreTrainedTokenizerBase
                  ) -> tuple[tuple[TokenFile, ...], dict[str, object]]:
    """Validate a manifest and tokenizer before reading its token files.

    Args:
        root: Directory containing manifest.json.
        split: Required logical split name.
        tokenizer: Current model tokenizer; no text is encoded.

    Returns:
        Validated entries and preparation metadata.

    Raises:
        ValueError: Structure, tokenizer, paths or checksums are invalid.
        OSError: The manifest cannot be read.
    """
    payload: object = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != "token-streams-v1" or payload.get("split") != split:
        raise ValueError("Invalid pretokenized split manifest")
    if payload.get("tokenizer") != tokenizer_identity(tokenizer):
        raise ValueError("Pretokenized data does not match the model tokenizer")
    entries, metadata = payload.get("files"), payload.get("metadata", {})
    if not isinstance(entries, list) or not isinstance(metadata, dict):
        raise ValueError("Manifest files and metadata have invalid types")
    result: list[TokenFile] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Invalid token file entry")
        path, corpus, count, digest = (item.get(key) for key in ("path", "corpus", "inputs", "sha256"))
        if (not isinstance(path, str) or not isinstance(corpus, str) or not corpus
                or not isinstance(count, int) or isinstance(count, bool) or count < 1
                or not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError("Invalid token file metadata")
        relative = PurePosixPath(path)
        if (relative.is_absolute() or ".." in relative.parts or relative.suffix != ".npy"
                or path in seen or not (root / path).resolve().is_relative_to(root.resolve())):
            raise ValueError("Token files must have unique paths contained by the split")
        seen.add(path)
        result.append(TokenFile(path, corpus, count, digest))
    return tuple(result), {str(key): value for key, value in metadata.items()}


def open_tokens(root: Path, record: TokenFile, vocabulary: int) -> NDArray[np.uint32]:
    """Verify and memory-map an immutable token stream without tokenization.

    Args:
        root: Split directory named by the manifest.
        record: Validated token-file entry.
        vocabulary: Upper exclusive token-ID bound.

    Returns:
        Read-only, one-dimensional uint32 IDs including the lookahead.

    Raises:
        ValueError: Checksum, dtype, shape, token count or vocabulary is wrong.
        OSError: The file cannot be read.
    """
    path = root / record.path
    if file_digest(path) != record.sha256:
        raise ValueError(f"Token file checksum mismatch: {path}")
    values = np.load(path, mmap_mode="r", allow_pickle=False)
    if (values.dtype != np.dtype("<u4") or values.ndim != 1
            or len(values) != record.inputs + 1 or int(values.max()) >= vocabulary):
        raise ValueError(f"Invalid token array dtype, shape, length or vocabulary: {path}")
    return values
