# Available resources

`resources.json` describes the corpus and models. API credentials are supplied
at runtime through environment variables; none are stored in these files.

`/data/corpus.jsonl` contains a uniform sample of company records without replacement.
`/data/manifest.json` records its size, seed, and content hash. Each row has `doc_id`,
`source_type`, `title`, and `content`. IDs and timestamps within a source record
are preserved in its content. Directory records describe people and organizations.

The assistant model is `gpt-6-luna`, accessed through the OpenAI Responses API.
Pass `ORANGE_OPENAI_API_KEY` to the installed `openai` client. This keeps the
application's credential independent of the coding harness's credentials:

```python
from openai import OpenAI
import os

response = OpenAI(api_key=os.environ["ORANGE_OPENAI_API_KEY"]).responses.create(
    model="gpt-6-luna",
    input="Your question and supporting context",
    reasoning={"effort": "medium"},
)
print(response.output_text)
```

For embeddings, import `embed` from `jina` and await
`embed(texts, "document")` when indexing or `embed(texts, "query")` when searching.
The helper loads pinned weights from `/opt/models/jina` onto this container's GPU.
It needs no credentials or network access. The runtime provides PyTorch,
Sentence Transformers, and the model's dependencies under `/opt/runtime`.

Use `uv` for project dependencies. The application workspace starts empty. Evaluation
uses a fresh copy of this image and restores only `/app`. Keep additional dependencies
there. `/opt/runtime/bin/python` provides the bundled packages. You can install extra
packages with `uv pip install --python /opt/runtime/bin/python --target /app/packages PACKAGE`
and add that directory to your application's Python module path. A separate virtualenv
must explicitly include the packages it uses.
Evaluation permits HTTPS to `api.openai.com`; package and model downloads are blocked.
