"""Select whole documents, tokenize once and compile fixed-budget corpus splits."""

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from titans_task import data
from titans_task.token_store import TokenFile, write_manifest, write_tokens
from transformers import PreTrainedTokenizerBase

from .dedup import DuplicateIndex
from .sources import (
    FINEWEB_REV,
    PG19_REV,
    SEED,
    TOKENIZER_ID,
    TOKENIZER_REV,
    WIKITEXT_REV,
    Document,
    fineweb_documents,
    pg19_documents,
    stable_order,
    wikitext_documents,
)


@dataclass
class TokenizedDocument:
    """One accepted document with EOS and its source provenance."""

    ids: list[int]
    provenance: dict[str, object]


def tokenize(document: Document, tokenizer: PreTrainedTokenizerBase,
             duplicates: DuplicateIndex) -> TokenizedDocument | None:
    """Screen a complete document and encode it exactly once.

    Args:
        document: Source record before any excerpt is taken.
        tokenizer: Fixed tokenizer with an EOS token.
        duplicates: Shared exclusion index across all selected splits.

    Returns:
        Tokens and source provenance, or None for an empty or duplicate document.
    """
    if not document.text.strip():
        return None
    digest = duplicates.accept(f"{document.corpus}:{document.group}", document.text)
    if digest is None:
        return None
    if tokenizer.eos_token_id is None:
        raise ValueError("The tokenizer requires an EOS separator")
    ids = tokenizer.encode(document.text, add_special_tokens=False, truncation=False)
    ids.append(tokenizer.eos_token_id)
    return TokenizedDocument(ids, {"id": document.identity, "group": document.group,
                                  "normalized_sha256": digest, "corpus": document.corpus,
                                  "source_tokens": len(ids), "origin": document.origin})


def append_provenance(root: Path, document: TokenizedDocument, stream: str,
                      start: int, used: int, *, close_with_eos: bool = False) -> None:
    """Record the exact source excerpt consumed by one output stream.

    Args:
        root: Split output directory.
        document: Tokenized source with complete-document provenance.
        stream: Relative output token-file name.
        start: First output position occupied by this document.
        used: Number of token positions consumed, including any lookahead.
        close_with_eos: Whether the final excerpt position replaces a token with EOS.
    """
    root.mkdir(parents=True, exist_ok=True)
    record = {**document.provenance, "stream": stream, "start": start, "used_tokens": used,
              "source_token_start": 0, "closed_with_eos": close_with_eos}
    with (root / "documents.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


class EvaluationBuilder:
    """Fill independent fixed-length streams without reusing a source document."""

    def __init__(self, root: Path, corpus: str, streams: int) -> None:
        """Create a builder for one corpus within one evaluation split.

        Args:
            root: Split output directory.
            corpus: Name used in the fixed evaluation mix.
            streams: Required independent stream count.
        """
        self.root, self.corpus, self.streams = root, corpus, streams
        self.pending: list[int] = []
        self.files: list[TokenFile] = []

    @property
    def done(self) -> bool:
        """Return whether every required stream has been written."""
        return len(self.files) == self.streams

    def add(self, document: TokenizedDocument) -> None:
        """Add a document to the current stream and discard any unused final tail.

        Args:
            document: New whole document, already assigned exclusively to this split.
        """
        if self.done:
            raise ValueError("Evaluation builder is already complete")
        relative = f"{self.corpus}/{len(self.files):02d}.npy"
        needed = data.STREAM_TOKENS + 1 - len(self.pending)
        used = min(needed, len(document.ids))
        append_provenance(self.root, document, relative, len(self.pending), used)
        self.pending.extend(document.ids[:used])
        if len(self.pending) == data.STREAM_TOKENS + 1:
            self.files.append(write_tokens(self.root, relative, self.corpus, self.pending))
            self.pending = []
            print(f"prepared {self.root.name}/{relative}: {data.STREAM_TOKENS} inputs", flush=True)


def fill_evaluation(builder: EvaluationBuilder, documents: Iterator[Document],
                    tokenizer: PreTrainedTokenizerBase, duplicates: DuplicateIndex) -> None:
    """Select and encode enough complete records to fill one evaluation corpus.

    Args:
        builder: Destination corpus builder.
        documents: Records from the assigned source split.
        tokenizer: Fixed tokenizer.
        duplicates: Shared complete-document duplicate index.

    Raises:
        ValueError: Eligible source records are exhausted before reaching the quota.
    """
    for document in documents:
        encoded = tokenize(document, tokenizer, duplicates)
        if encoded is not None:
            builder.add(encoded)
        if builder.done:
            return
    raise ValueError(f"Insufficient eligible documents for {builder.root.name}/{builder.corpus}")


def training_stream(root: Path, documents: dict[str, Sequence[TokenizedDocument]]) -> TokenFile:
    """Combine already-tokenized sources using the fixed document-level 80/20 rule.

    Args:
        root: Training split output directory.
        documents: Ordered accepted documents for each required source.

    Returns:
        One mixed token file with exact input quotas and one real lookahead.
    """
    budgets = dict(data.TRAINING_QUOTAS)
    consumed = {name: 0 for name in budgets}
    iterators = {name: iter(documents[name]) for name in budgets}
    pieces: list[np.ndarray] = []
    position = 0
    while any(consumed[name] < quota for name, quota in data.TRAINING_QUOTAS):
        eligible = [name for name, quota in data.TRAINING_QUOTAS if consumed[name] < quota]
        name = min((consumed[name] / budgets[name], rank, name)
                   for rank, name in enumerate(eligible))[2]
        document = next(iterators[name])
        remaining = budgets[name] - consumed[name]
        final = len(eligible) == 1
        close = len(document.ids) > remaining and not final
        used = min(len(document.ids), remaining + int(final))
        ids = np.array(document.ids[:used], dtype="<u4")
        if close:
            ids[-1] = document.ids[-1]
        append_provenance(root, document, "stream.npy", position, used, close_with_eos=close)
        pieces.append(ids)
        position += used
        consumed[name] += min(used, remaining)
        if final and used > remaining:
            break
        if final and consumed[name] == budgets[name]:
            lookahead = next(iterators[name])
            append_provenance(root, lookahead, "stream.npy", position, 1)
            pieces.append(np.array(lookahead.ids[:1], dtype="<u4"))
    values = np.concatenate(pieces)
    if len(values) != sum(budgets.values()) + 1:
        raise ValueError("Training packing did not satisfy the exact token budget")
    return write_tokens(root, "stream.npy", "mixed", values)


def build(root: Path, cache: Path, tokenizer: PreTrainedTokenizerBase) -> dict[str, object]:
    """Prepare all approved corpus splits using whole-document source selection.

    Args:
        root: Fresh staging output directory.
        cache: Pinned-source download cache.
        tokenizer: Fixed Llama-2 tokenizer, loaded before preparation begins.

    Returns:
        Preparation statistics, also recorded in each split manifest.
    """
    duplicates = DuplicateIndex()
    builders = {(split, corpus): EvaluationBuilder(root / split, corpus, count)
                for split, counts in data.EVALUATION_COUNTS.items() for corpus, count in counts}
    fill_evaluation(builders["public", "pg19"], pg19_documents("validation", cache), tokenizer, duplicates)
    fill_evaluation(builders["private", "pg19"], pg19_documents("test", cache), tokenizer, duplicates)
    for document in wikitext_documents(cache):
        split = "public" if int(stable_order(document.group)[:8], 16) % 5 == 0 else "private"
        builder = builders[split, "wikitext103"]
        if not builder.done:
            encoded = tokenize(document, tokenizer, duplicates)
            if encoded is not None:
                builder.add(encoded)
        if builders["public", "wikitext103"].done and builders["private", "wikitext103"].done:
            break
    budgets = dict(data.TRAINING_QUOTAS)
    training: dict[str, list[TokenizedDocument]] = {name: [] for name in budgets}
    totals = {name: 0 for name in budgets}
    for document in pg19_documents("train", cache):
        encoded = tokenize(document, tokenizer, duplicates)
        if encoded is not None:
            training["pg19"].append(encoded)
            totals["pg19"] += len(encoded.ids)
        if totals["pg19"] > budgets["pg19"]:
            break
    print(f"selected PG19 training: {len(training['pg19'])} books, {totals['pg19']} available tokens", flush=True)
    for document in fineweb_documents(cache):
        bucket = int(stable_order(document.group)[:8], 16) % 100
        split = "train" if bucket < 76 else "public" if bucket < 81 else "private"
        if split == "train" and totals["fineweb_edu"] > budgets["fineweb_edu"]:
            continue
        if split != "train" and builders[split, "fineweb_edu"].done:
            continue
        encoded = tokenize(document, tokenizer, duplicates)
        if encoded is not None:
            if split == "train":
                training["fineweb_edu"].append(encoded)
                totals["fineweb_edu"] += len(encoded.ids)
                if len(training["fineweb_edu"]) % 500 == 0:
                    print(f"selected FineWeb training: {totals['fineweb_edu']} available tokens", flush=True)
            else:
                builders[split, "fineweb_edu"].add(encoded)
        if (totals["fineweb_edu"] > budgets["fineweb_edu"]
                and builders["public", "fineweb_edu"].done and builders["private", "fineweb_edu"].done):
            break
    if any(not builder.done for builder in builders.values()) or any(totals[name] <= quota for name, quota in budgets.items()):
        raise ValueError("The pinned source selection did not fill every required split")
    revisions = {"fineweb_edu": FINEWEB_REV, "pg19": PG19_REV, "wikitext103": WIKITEXT_REV,
                 "tokenizer": {"repo": TOKENIZER_ID, "revision": TOKENIZER_REV}}
    metadata = {"source_revisions": revisions, "selection_seed": SEED,
                "duplicate_screen": "normalized exact + sampled 5-word shingle containment >=0.8, min 8 matches",
                "duplicate_counts": dict(duplicates.counts)}
    record = training_stream(root / "train", training)
    write_manifest(root / "train", "train", tokenizer, [record],
                   metadata={**metadata, "source_token_counts": budgets})
    for split in ("public", "private"):
        files = [record for corpus, _ in data.EVALUATION_COUNTS[split]
                 for record in builders[split, corpus].files]
        write_manifest(root / split, split, tokenizer, files, metadata=metadata)
    tokenizer.save_pretrained(root / "tokenizer")
    return {**metadata, "training_source_tokens_before_trimming": totals,
            "training_documents": {name: len(value) for name, value in training.items()}}
