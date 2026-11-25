# Available resources

Work in `/app` as user `candidate`. Keep application code, local dependencies,
and generated files there. Supplied files under `/data` and `/opt` are read-only
for this user.

| Path | Contents |
| --- | --- |
| `/data/corpus.json` | Sample company records as a JSON array. Each record has `doc_id`, `source_type`, `title`, and `content`. |
| `/data/practice/qa.json` | 20 practice questions, reference answers, and exact source passages from the sample. |
| `/data/practice/questions.json` | Those 20 questions in the CLI input format. |
| `/opt/resources/resources.json` | Corpus paths, model IDs, endpoints, and credential variable names. |
| `/opt/resources/corpus/manifest.json` | Sample size, sampling seed, and content hash. |
| `/opt/resources/chroma-api.md` | Chroma connection examples, supported operations, and limits. |
| `/opt/resources/jina.py` | GPU embedding helper. |
| `/opt/application/bin/python` | Application Python with PydanticAI, OpenAI, Chroma, PyTorch, Transformers, and safetensors installed. |
| `/opt/runtime/bin/python` | SGLang runtime, including PyTorch, Transformers, NumPy, and safetensors. |

`PATH` includes `/app`, `/opt/application/bin`, and `/opt/runtime/bin`, in that
order. `PYTHONPATH` includes `/opt/resources`. `uv` is installed. Dependency
manifests and locks are in `/opt/application-project` and `/opt/runtime-project`.

## Models

Use the OpenAI Responses API for the assistant model configured in
[resources.json](resources.json). Initialize the client with
`OpenAI(api_key=os.environ["ORANGE_OPENAI_API_KEY"])`.

For embeddings, use `from jina import embed`, then await
`embed(texts, "document")` for indexing or `embed(texts, "query")` for searching.
The helper adds the prefixes and batches inputs. It returns normalized
1,024-dimensional vectors. Send multiple texts per call when indexing.

The first embedding call starts SGLang on this container's GPU using weights
already in `/opt/models/jina`; subsequent processes reuse it. Startup logs are
in `/tmp/orange-jina-<uid>/server.log`.

## Database

Chroma 1.5.9 runs in a separate CPU container. Connect through its HTTP client
using `ORANGE_CHROMA_HOST` and `ORANGE_CHROMA_PORT`. Database files stay in that
container. Reads are capped at 100 records per request; see
[chroma-api.md](chroma-api.md) for examples and pagination.

## Network access

External access is limited to `api.openai.com` for model calls. The supplied
Chroma and local embedding services are reachable. Package registries and
external documentation sites are unavailable; use installed packages, bundled
documentation, and Python's `help()`.

The [batch client contract](integration.md) and [desktop gateway contract](desktop.md) describe the interfaces already used by our workplace tools.
