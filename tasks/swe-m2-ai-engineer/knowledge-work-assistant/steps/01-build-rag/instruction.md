
Build a knowledge work assistant (the project is called 'orange') based on agentic RAG in `/app`, reaching at least 80% accuracy for production useage! Design your system for generalizaiton.

You have access to: 
Raw Data: You have 5,000 documents available `/data/corpus.jsonl`, for indexing and development.
Development QA: You have 100 labeled development question–answer pairs in `/data/dev.jsonl`. 

Implement these three async, typed functions. They are the entry points for the main features:

```python
async def ingest(event: IngestEvent) -> None:
    """Ingest the raw document corpus into a local database."""

async def retrieve(query: str) -> RetrievedItem:
    """Retrieve the items fro mthe local database relevant to the query."""

async def generate(query: str) -> GeneratedAnswer:
    """Generate an answer. This function must call retrieve() internally."""
```

Users run the app with these commands:

```bash
orange help
orange ingest --path CORPUS.jsonl [--refresh]
orange answer [--questions FILE ...] [--output ANSWERS.json]
```

`orange ingest --path` reads a corpus JSONL (`doc_id`, `source_type`, `title`, `content`), calls `ingest`, and writes the index to `/app/state`. `--refresh` rebuilds that index. If the doc id already appears and we didn't ask for refresh, that item is going to be skipped.

`orange answer` sends each question to `generate`, and `generate` looks it up with `retrieve`, so ingest first. `--questions` can point at several JSONL files, each line a `question_id` and a `question`. If you skip the files, type the questions yourself, one per line. You get one answer record per question. Add `--output` to write those records to a file. Leave it off and they print in the terminal.

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