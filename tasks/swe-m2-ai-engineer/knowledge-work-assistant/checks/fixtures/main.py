"""Small deterministic application for verifier tests; not a HERB oracle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class IngestEvent(TypedDict):
    """Public ingestion event."""

    corpus_path: str
    refresh: bool


class Passage(TypedDict):
    """Literal source evidence."""

    doc_id: str
    quote: str


class RetrievedItem(TypedDict):
    """Retrieved evidence."""

    passages: list[Passage]


class GeneratedAnswer(TypedDict):
    """Public answer object."""

    answer: str
    citations: list[Passage]


STATE = Path(__file__).parent / "state/index.json"


async def ingest(event: IngestEvent) -> None:
    """Persist fixture documents, preserving existing IDs without refresh.

    Args:
        event: Input corpus and replacement flag.
    """
    rows = {} if event["refresh"] or not STATE.exists() else json.loads(STATE.read_text())
    for line in Path(event["corpus_path"]).read_text().splitlines():
        row = json.loads(line)
        rows.setdefault(row["doc_id"], row)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(rows))


async def retrieve(query: str) -> RetrievedItem:
    """Return fixture evidence ordered by exact title occurrence.

    Args:
        query: Question text; only used to order the small fixture corpus.

    Returns:
        Literal content passages from at most two records.

    Raises:
        FileNotFoundError: Ingestion has not created an index.
    """
    rows = list(json.loads(STATE.read_text()).values())
    selected = [row for row in rows if row["title"] in query]
    selected += [row for row in rows if row not in selected]
    return {"passages": [{"doc_id": row["doc_id"], "quote": row["content"]} for row in selected[:2]]}


async def generate(query: str) -> GeneratedAnswer:
    """Echo fixture evidence through the required retrieval call.

    Args:
        query: A fixture question.

    Returns:
        An extractive answer with literal citations.
    """
    evidence = await retrieve(query)
    return {"answer": " ".join(row["quote"] for row in evidence["passages"]), "citations": evidence["passages"]}
