
Build a knowledge work assistant (the project is called 'orange') based on agentic RAG in `/app`, reaching at least 80% accuracy on questions about company documents, conversations, and project history. Design your system for generalization.

You will be working with a fictional software company's Slack conversations, meeting records, documents, pull requests, links, and employee/customer directory records. Use the resources already available in the environment. Generate your own questions and reference answers to test the system during development; do not download benchmark questions or reference answers.

First define these three async, typed functions, then implement the system behind them. They are the entry points for the main features:

```python
async def ingest(event: IngestEvent) -> None:
    """Ingest the raw document corpus into a local database."""

async def retrieve(query: str) -> RetrievedItem:
    """Retrieve the items from the local database relevant to the query."""

async def generate(query: str) -> GeneratedAnswer:
    """Generate an answer. This function must call retrieve() internally."""
```

Export these functions from `/app/main.py`. Define the named types as `TypedDict`s: `IngestEvent` has `corpus_path: str` and `refresh: bool`; `RetrievedItem` has `passages`, a list of objects with `doc_id: str` and `quote: str`; `GeneratedAnswer` has `answer: str` and `citations`, using that same passage format. Put the CLI in `/app/cli.py` and provide an executable `/app/orange` that launches it.

Users run the app with these commands:

```bash
orange help
orange ingest --path CORPUS.jsonl [--refresh]
orange answer [--questions FILE ...] [--output ANSWERS.json]
```

`orange ingest --path` reads a corpus JSONL (`doc_id`, `source_type`, `title`, `content`), calls `ingest`, and writes the index to `/app/state`. `--refresh` rebuilds that index. If the doc id already appears and we didn't ask for refresh, that item is going to be skipped.

Refresh replaces the index with the supplied corpus, removing documents absent from it. Quotes must be exact passages from a document's title or content.

`orange answer` sends each question to `generate`, and `generate` looks it up with `retrieve`, so ingest first. `--questions` can point at several JSONL files, each line a `question_id` and a `question`. If you skip the files, type the questions yourself, one per line. You get one answer record per question. Add `--output` to write those records to a file. Leave it off and they print in the terminal.

Terminal output is one JSON record per line. For typed questions, use IDs `stdin-1`, `stdin-2`, and so on; stop at EOF. Answering before ingestion should fail.

`--output` writes `ANSWERS.json` as a list of answer records:

```json
[
  {
    "question_id": "example",
    "answer": "A concise answer.",
    "citations": [
      {
        "doc_id": "dsid_example",
        "quote": "An exact supporting passage from the document."
      }
    ]
  }
]
```

Save your development corpus to `/app/dev/corpus.jsonl`, your generated questions to `/app/dev/questions.jsonl` (each with `question_id`, `question`, and `reference_answer`), and the application's answers to `/app/dev/answers.json`. In `/app/dev/report.json`, describe how you evaluated those answers and what you found. Keep this test data out of the production index.

Final evaluation starts in a fresh container with your files from `/app`, checks the functions and commands above, rebuilds the index from company records, and asks held-out questions about them. Keep any additional runtime dependencies under `/app`; evaluation can reach only the provided model API. Accuracy is the average answer rating from 0% to 100%, based on correctness, completeness, and relevance; partial answers receive partial credit. Reach at least 80%, and pass the functional checks. Missing answers receive zero. Small checks allow three minutes per command, full ingestion 45 minutes, and the answer batch 90 minutes. Each captured output or answer file is limited to 30 MB.
