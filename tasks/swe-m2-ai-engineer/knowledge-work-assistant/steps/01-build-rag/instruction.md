
Your task is to build a knowledge work assistant (the project is called 'orange') based on agentic RAG in `/app`, reaching at least 80% accuracy for production useage! Design your system for generalizaiton.

The development site that you can have access to: 
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

The public functions live in `/app/main.py`. Import `IngestEvent`, `RetrievedItem`,
and `GeneratedAnswer` from `orange_types`; their definitions are in
`/opt/runtime/orange_types.py`. `IngestEvent` contains `corpus_path: str` and
`refresh: bool`. `RetrievedItem` contains a `passages` list, each with a `doc_id`
and an exact `quote`. `GeneratedAnswer` contains the `answer` string and the
`citations` list shown above. Return that object from `generate`; the CLI handles
JSON serialization. The supplied `/app/cli.py` implements the commands and can
be edited. `orange` launches that file.

Refresh replaces the index with the supplied corpus, including removing documents
that are no longer present. Answering before ingestion must fail. Terminal output
uses one JSON answer record per line. For questions typed into the terminal, use
IDs `stdin-1`, `stdin-2`, and so on. File output remains a single JSON array.

Use the supplied Qwen3-Embedding-0.6B model for embeddings and Qwen3-8B for answer
generation. Their paths are `/opt/models/embedding` and `/opt/models/generation`;
`rag_runtime` provides local inference helpers. You have one H100. Keep your work
under `/app`, which is copied into a fresh verifier environment.

The evaluator first checks the commands, function signatures and call path,
persistence, duplicate handling, and refresh behavior. These checks must pass.
It then rebuilds the full index and answers 300 held-out questions. A question
passes when the answer is correct, includes every required fact, and supports
its material claims with exact source quotations. Paraphrases and equivalent
quantities are accepted. Missing answers count as incorrect. Reach at least
240 passing answers and return one record per question. Citation recall is
reported separately; valid alternative sources are accepted.

GPT-6.1 Sol grades answer meaning outside your application. Use only the corpus
as the assistant's knowledge source; development labels are for checking your
work, not retrieval or hard-coded answers. The full ingestion run has 45 minutes
and the held-out answering run has 90 minutes. Small functional checks have
three minutes per command; the complete verifier has four hours. Output capture
and answer files have a 30 MB execution allowance.
