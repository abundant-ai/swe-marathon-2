# Step 1 Harbor package

Only `01-build-rag` is enabled in `task.toml` and included in the bundle. Later
instructions remain in the authoring repository; their environments, verifiers,
and oracle solutions are not implemented.

The agent image starts with an empty `/app`. It contains a uniform sample of
1,570 out of 39,268 corpus records (4%, rounded down), local Jina embeddings, and
configuration for `gpt-6-luna`. The agent discovers these through `/data`,
`/opt/resources`, environment variables, and the installed packages. The instruction
asks it to use available resources without listing the tools or sample size.

The full corpus and all 238 content-question references are evaluation inputs.
They are excluded from the agent image. The sample includes source records only;
the agent must create its own development questions and reference answers.

## Build and deliver

From this task directory:

```bash
uv sync --frozen
uv run python scripts/prepare_data.py --herb /path/to/HERB
uv run pytest checks -q
uv run python scripts/package_step.py
```

The archive is `dist/knowledge-work-assistant-step1.tar.gz`, with a SHA-256 file
beside it. It contains a complete step-1 task, including prepared sample data and
private verifier inputs. Extract it and pass the `knowledge-work-assistant/`
directory to Oddish. It does not need the author's HERB checkout or virtualenv.
`BUNDLE_MANIFEST.json` records the hash of every included source/input file.

Source preparation requires HERB revision `db3bf9b3f911745726c579c9dbf9f7f6b2c05b36`.
It generates ignored files under `environment/data/` and
`steps/01-build-rag/tests/private/`. Prepare those before building or publishing
the task. Git ignores these generated files; Harbor still needs to upload the
private files to the separate verifier. Do not exclude them from a verifier upload.

The authoring project pins upstream Harbor to
`feea734de84bf2479b329dc6315a6d98d1596f4f` (0.25.0). The task also passes the parser
from Oddish's pinned revision `8ea3df67962fdd8d590c6044e060151756cdc326`.
The agent image has Python 3.12 and its own locked runtime dependencies. Keep local
virtualenvs outside `environment/`: Harbor validates uploaded paths and rejects
external interpreter symlinks even when Docker would ignore them.

The image provides standard installation dependencies, including Node/npm, curl,
Git, Bash, and Python/uv. It does not bake in a coding harness, model-specific
solver, or reference solution. Oddish selects and installs the coding harness.
The application, generated code, and index are transferred through the standard
`artifacts = ["/app"]` contract; grading does not import a harness SDK.

Sampling uses Python's seeded sampling without replacement over source records,
including directories, PRs, and links. It is not stratified by product or source
type. Original source IDs remain in content; corpus IDs include the product,
source type, and record position to distinguish repeated native IDs. Product-level
`team`, `customers`, and question fields are excluded from the candidate corpus.
The manifests record source hashes, generated-file hashes, and the sampling seed.

## Verification

Harbor's [separate verifier](https://github.com/harbor-framework/harbor/blob/main/docs-mintlify/tasks/separate-verifier.mdx)
starts a fresh copy of the agent image, transfers `/app`, uploads step tests,
and invokes `tests/test.sh`. The adapter calls
`verify(context: VerificationContext) -> VerificationResult`.
Its explicit registry runs every named requirement check and records dependency
skips. It continues independent checks after an application failure.

Both environments request one L4 GPU on Modal. The image installs Jina v5 omni small
at revision `950200abde3a3bcf3d5bdfe5d28fb5bb5e7dfbb0`, including weights, adapters,
tokenizer, and custom model code. The helper loads `/opt/models/jina` locally;
evaluation needs no Hugging Face or Modal service connection for embeddings.
Model downloads happen during the image build, before evaluation.

The verifier's startup and grading policies both allow only `api.openai.com`.
Development retains internet access for installing dependencies and the coding
harness. The submitted app must keep additional runtime dependencies under `/app`
so they survive the transfer. The fresh verifier inherits no development processes,
temporary files, or changes outside the declared artifacts.

Modal enforces this allowlist on TLS hostnames, not individual API paths or model
names. Its [network policy documentation](https://modal.com/docs/guide/sandbox-networking)
also notes that DNS remains available and domain fronting is not prevented by the
allowlist alone. This is restricted model-service access, not a completely offline
container or a guarantee against every possible exfiltration channel.

| Requirement | Test |
| --- | --- |
| Async functions and typed records | `test_interfaces` |
| Executable help | `test_cli_help` |
| Answering before ingestion fails | `test_answer_before_ingestion` |
| Ingest API and persistence across processes | `test_ingestion_and_persistence` |
| Skip existing IDs while adding new documents | `test_duplicate_documents` |
| Refresh changes content and removes absent IDs | `test_refresh_replaces_index` |
| CLI calls the public functions; generation calls retrieval | `test_required_call_paths` |
| Multiple question files and JSON answer arrays | `test_cli_question_files` |
| Terminal questions, IDs, EOF, and JSONL output | `test_cli_stdin` |
| Development corpus, Q&A, answers, and report | `test_self_generated_evaluation` |
| Held-out answer quality and citation validity | `test_holdout_accuracy` |

The held-out test refreshes the index from the full sanitized corpus and asks all
238 content questions. It validates IDs and quoted evidence, then passes only the
question, original reference value, and answer text to the judge. A completed run
passes when every mandatory check passes and mean answer quality reaches 80.
Missing or empty answers contribute zero to the full denominator and also fail
the requirement to answer every question.

The rubric is the verbatim `answer_likert_score` prompt from
[HERB's evaluator](https://github.com/SalesforceAIResearch/HERB/blob/db3bf9b3f911745726c579c9dbf9f7f6b2c05b36/code/evaluate.py).
Scores retain HERB's integer conversion and arithmetic mean. In the instruction,
“accuracy” means this partial-credit answer-quality percentage, not a binary
correct-answer rate. This is a changed-judge evaluation and should not be compared
directly with the earlier GPT-4o results.

The judge is fixed in code to `gpt-5.4-2026-03-05`, Responses API, medium reasoning,
one rating per answer. There is no model override or fallback. The dated snapshot
is listed in [OpenAI's model documentation](https://developers.openai.com/api/docs/models/gpt-5.4).
GPT-5.4 was selected because it has published judge-evaluation evidence in
[this RewardBench 2 study](https://arxiv.org/html/2604.13717v1); that result does
not establish its calibration on HERB.

The trusted report records the model, reasoning setting, prompt hash, input hashes,
per-check results, and per-question scores and reasons. Provider failures invalidate
the run, preserve completed diagnostics, and remove any stale reward files.

## Credentials and process boundary

Supply these host environment variables through the runner's secret management:

- `ORANGE_JUDGE_API_KEY`: verifier-only judge credential. Map the approved
  `openai-keys` secret's `OPENAI_API_KEY` value to this variable in the runner.
- `ORANGE_OPENAI_API_KEY`: application credential for `gpt-6-luna`.

`task.toml` exposes `ORANGE_OPENAI_API_KEY` to the application so a coding harness's
`OPENAI_API_KEY` cannot overwrite it. The runner uses its own Modal credentials to
create the GPU containers; those credentials are not exposed inside them.
The verifier receives its judge key separately and
passes only the explicitly allowlisted application variables to candidate processes.
Credentials are never baked into images or written to the task files.
The chosen coding harness's credentials are supplied separately by Oddish.
The verifier's 12-hour limit is separate from the candidate command limits.

For a direct Harbor run outside Oddish, supply the variables above and the selected
harness's credentials, then run the extracted task with the standard CLI:

```bash
MODAL_ENVIRONMENT=testing uv run harbor run \
  --path /path/to/extracted/knowledge-work-assistant \
  --agent "$HARNESS" --model "$CODING_MODEL" --env modal
```

The verifier runs as root and the submitted app as UID/GID 10001. `/tests` and
`/logs/verifier` are restricted to the verifier. Application subprocesses have
deadlines and bounded captured output. The Python call probe records calls to the
exported functions, including imported aliases. It does not establish resistance
to deliberate instrumentation evasion or arbitrary sandbox escape.

## Validation and remaining work

All 25 local checks pass using a deterministic fixture application and judge. They cover the
complete registry, targeted broken submissions, full-denominator scoring, malformed
judge responses, dependency skips, and stale reward cleanup. These fixtures are
not oracle solutions and do not establish that an actual RAG system reaches 80%.

A prior Modal Linux runtime passed all 11 registered checks with the verifier,
controlled application, and controlled judge. It verified that
candidate UID 10001 could neither read `/tests/verify.py` nor write the reward,
and did not inherit the synthetic judge credential. Its entry point is
`checks/container_smoke.py`; its fixture modules belong only in the smoke image.
This was an adapter/process-boundary check, not a complete Harbor agent trial.
An earlier Harbor no-op trial built the then-current Dockerfile and completed with
zero exceptions and reward zero for an empty submission, exercising the separate
verifier, private-input upload, and reward collection. Coding-harness installation
and model trials are left to Oddish.
A fresh Modal L4 container produced a normalized 1,024-dimensional Jina vector as
UID 10001 with `block_network=True`, no credentials, and the verifier's restricted
process environment. This establishes that embedding inference uses the bundled
weights and GPU without downloads. A prior live `gpt-6-luna` Responses check also
completed successfully.

A controlled Harbor run completed in 56 seconds with no evaluation exceptions.
It compared Modal container IDs, restored a declared `/app` marker, and confirmed
an undeclared `/tmp` marker was absent. As UID 10001, it generated query and document
embeddings locally, reached the approved OpenAI API (401 without credentials), and
could not connect to the tested HTTPS destinations `example.com`, `huggingface.co`,
`pypi.org`, or `1.1.1.1`, or to plain HTTP at `example.com`. The unchanged production
verifier then accounted for all 11 checks and correctly gave the empty submission
reward zero. `checks/environment_smoke.py` contains the boundary probes.
This control overrode the GPU type to A10 after L4 startup stalled; the delivered
configuration retains L4, whose offline embedding inference passed separately.

A five-answer live smoke check on the fixed judge scored correct/wrong/partial/
unsupported-extra-claims/prompt-injection examples at 100/0/65/82/0. The score of 82
shows that the inherited rubric can still reward an otherwise correct answer with
unsupported additions. A single example of each kind is not a calibration study.

The development-artifact check establishes that the files and reference answers
exist and are structurally consistent. It cannot prove question authorship, that
the reported experiment was run, or that interfaces were written before their
implementations. The full final corpus includes the public sample; it is the Q&A
set that is held out. HERB itself is public, so withheld files do not establish
absence of model pretraining contamination.

An oracle RAG implementation, a full 238-question run using the fixed judge, and
calibration of the 80% threshold remain separate work.

HERB's data and copied rubric retain its CC BY-NC 4.0 license. The bundle includes
the original license, attribution, source revision, and a description of the data
transformations. This package does not grant additional commercial-use rights.
