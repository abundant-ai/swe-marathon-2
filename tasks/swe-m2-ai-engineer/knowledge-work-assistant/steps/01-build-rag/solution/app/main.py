"""Step-1 public Pydantic contracts and baseline application entry points."""

import asyncio
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

from orange_core.agent import run_agent
from orange_core.config import load_settings
from orange_core.retrieval import Hit
from orange_core.storage import embed_texts, ingest_corpus, require_index, search_index

APP_ROOT = Path(__file__).resolve().parent
RetrievalMethod: TypeAlias = Literal["bm25", "embed", "hybrid"]


class IngestEvent(BaseModel):
    """Public ingestion request."""

    corpus_path: str = Field(description="Path to the JSON corpus file.")
    refresh: bool = Field(description="Rebuild the index if true; otherwise skip existing document IDs.")


class Passage(BaseModel):
    """Exact source excerpt returned by retrieval or cited in an answer."""

    doc_id: str = Field(description="ID of the source document in the vector database.")
    quote: str = Field(description="Exact text from the document's title or content.")


class RetrievedItem(BaseModel):
    """Ranked retrieval results."""

    passages: list[Passage] = Field(description="Source passages relevant to the query.")


class GeneratedAnswer(BaseModel):
    """Final user-facing answer and supporting excerpts."""

    answer: str = Field(description="Answer to the user's question.")
    citations: list[Passage] = Field(description="Source passages supporting the answer.")


async def ingest(event: IngestEvent) -> None:
    """Persist a corpus in the local Chroma and BM25 indexes.

    Args:
        event: JSON corpus path and replacement/append mode. Existing IDs are
            skipped on append; refresh removes all old documents and chunks.
    """
    await asyncio.to_thread(ingest_corpus, APP_ROOT, Path(event.corpus_path), event.refresh, load_settings(APP_ROOT))


async def retrieve(query: str, retrieval_method: RetrievalMethod) -> RetrievedItem:
    """Retrieve at most 20 passages using lexical, dense, or fused ranking.

    Args:
        query: Search text; the original wording is passed to embedding search.
        retrieval_method: bm25, embed, or hybrid (RRF with fixed rank constant 20).

    Returns:
        Typed exact source excerpts, ordered by the chosen retrieval method.

    Raises:
        RuntimeError: A complete index has not been ingested.
        ValueError: The retrieval method is unsupported.
    """
    if retrieval_method not in {"bm25", "embed", "hybrid"}:
        raise ValueError("retrieval_method must be bm25, embed, or hybrid")
    require_index(APP_ROOT)
    vector = None if retrieval_method == "bm25" else (await embed_texts([query], "query"))[0]
    hits = await asyncio.to_thread(search_index, APP_ROOT, query, retrieval_method, vector)
    return RetrievedItem(passages=[Passage(doc_id=hit.doc_id, quote=hit.quote) for hit in hits])


async def generate(query: str) -> GeneratedAnswer:
    """Orchestrate iterative agentic search using retrieve as the model's tool.

    Args:
        query: User question, independent of all other active requests.

    Returns:
        Grounded prose and exact citations selected from this request's retrievals.

    Raises:
        TimeoutError: Search and generation exceed the configured 30-minute ceiling.
        RuntimeError: The index is missing or the assistant cannot finish validly.
    """
    require_index(APP_ROOT)
    settings = load_settings(APP_ROOT)

    async def search_tool(text: str, method: RetrievalMethod) -> list[Hit]:
        """Route each model search through the required public function.

        Args:
            text: Model-selected search phrase.
            method: Model-selected retrieval mode.

        Returns:
            Exact public passages adapted to the agent's internal evidence records.
        """
        result = await retrieve(text, method)
        return [Hit(str(index), row.doc_id, row.quote) for index, row in enumerate(result.passages)]

    async with asyncio.timeout(settings.question_timeout_seconds):
        result = await run_agent(query, search_tool, settings)
    return GeneratedAnswer(answer=result.answer, citations=[Passage(doc_id=hit.doc_id, quote=hit.quote) for hit in result.citations])
