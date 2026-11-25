# Chroma 1.5.9 Python API reference

Chroma runs in a separate CPU container. Connect with `chromadb.HttpClient` using
`ORANGE_CHROMA_HOST` and `ORANGE_CHROMA_PORT`. The service owns the database files;
there is no database path to open in the application container.

## Connect, write, and search

This small example uses two-dimensional toy vectors in an `example` collection.
For company records, use your computed document and query embeddings with the
same dimensions and embedding model throughout each collection. Supplying
`embedding_function=None` means you must provide embeddings yourself.

```python
import os
import chromadb
from chromadb.config import Settings

client = chromadb.HttpClient(
    host=os.environ["ORANGE_CHROMA_HOST"],
    port=int(os.environ["ORANGE_CHROMA_PORT"]),
    settings=Settings(anonymized_telemetry=False),
)
collection = client.get_or_create_collection("example", embedding_function=None)
collection.add(
    ids=["doc-1", "doc-2"],
    documents=["The release is Friday.", "Maya owns the release."],
    embeddings=[[1.0, 0.0], [0.0, 1.0]],
    metadatas=[{"title": "Schedule"}, {"title": "Owner"}],
)
records = collection.get(
    ids=["doc-1"],
    include=["documents", "metadatas"],
)
neighbors = collection.query(
    query_embeddings=[[1.0, 0.0]],
    n_results=1,
    include=["documents", "metadatas", "distances"],
)
```

`get()` returns flat lists, such as `records["ids"]` and `records["documents"]`.
`query()` returns one list per query vector: `neighbors["ids"][0]` contains the
first query's matches. IDs are always returned; `include` selects other fields.
Query results are ordered by increasing distance. The default collection distance is
squared L2. Use `configuration={"hnsw": {"space": "cosine"}}` when creating a
collection if you want cosine distance.

## Read limits and pagination

- `get()` and `peek()` return at most 100 records per request. An omitted or
  `None` limit on `get()` becomes 100. Explicit limits must be 1–100, and a
  `get(ids=...)` request may contain at most 100 IDs.
- `query()` requires `number_of_query_vectors * n_results <= 100`.
  Its default `n_results` is 10. Each chunk counts as one record.
- `list_collections(limit=100, offset=0)` is also paginated. Each returned item
  has a `.name`. Use `count_collections()` for the total.
- Oversized reads are rejected, not silently truncated. Request bodies,
  including writes, must fit within 16 MiB. Split larger writes into batches.
  Each write must also stay within `client.get_max_batch_size()` records.

Read all records in pages while keeping the collection unchanged:

```python
all_ids: list[str] = []
for offset in range(0, collection.count(), 100):
    page = collection.get(limit=100, offset=offset, include=["documents"])
    all_ids.extend(page["ids"])
```

## Other operations

| Operation | Use |
| --- | --- |
| `client.get_collection(name, embedding_function=None)` | Open an existing collection. |
| `collection.count()` | Count stored records. |
| `collection.add(ids=..., documents=..., embeddings=..., metadatas=...)` | Insert new IDs. Existing IDs are not overwritten. Parallel lists must have matching lengths. |
| `collection.update(ids=..., ...)` | Change existing records. Supply new embeddings when changing text. |
| `collection.upsert(ids=..., ...)` | Insert or replace records by ID. |
| `collection.delete(ids=[...])` | Remove specified records. |
| `client.delete_collection(name)` | Delete a collection and its records. Recreate it to start empty. |

`get()` and `query()` accept metadata filters such as `where={"doc_id": "doc-1"}`
and text filters such as `where_document={"$contains": "release"}`. Use
`include=["embeddings"]` when you need the stored vectors.

Use the default tenant and database. Server reset, alternate namespaces, and
other administrative APIs are unavailable. Inspect installed Python methods
with `help()` for argument details; this service exposes only the operations
listed here and collection metadata updates.
