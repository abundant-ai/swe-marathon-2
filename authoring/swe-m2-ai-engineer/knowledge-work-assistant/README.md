# Knowledge work assistant

Orange answers questions about a fictional software company's documents,
conversations, project history, and directory records. The task asks a coding
agent to build the assistant and improve it over successive steps.

## Current implementation

Only `01-build-rag` is enabled in `task.toml` and included in the bundle. Later
steps are not implemented.

The agent image starts with an empty `/app`. It contains a uniform sample of
1,570 out of 39,268 corpus records (4%, rounded down), local Jina embeddings, and
configuration for `gpt-6-luna`. The agent discovers these through `/data`,
`/opt/resources`, environment variables, and the installed packages. The instruction
asks it to use available resources without listing the tools or sample size.

The full corpus and all 238 content-question references are evaluation inputs.
They are excluded from the agent image. The sample includes source records only;
the agent must create its own development questions and reference answers.

Both development and evaluation allow outbound connections only to `api.openai.com`.
This is a model-service exception, not an air gap: the domain policy does not restrict
individual API features, and the provider may permit DNS. Dependencies, model weights,
and any coding-harness installation that needs public downloads must be provisioned
before the restricted development session starts. The live enforcement of this new
development policy has not yet been tested.

Candidate resources omit the dataset name, upstream repository, and revision.
Provenance and attribution remain in author documentation and the private manifest.
This removes an explicit discovery route; it does not prove that public source records
cannot be recognized or were absent from model training.

The unchanged 1,570-record sample covers the domain described in the prompt:
1,328 Slack records, 158 PRs, 21 documents, 16 meeting transcripts, 2 meeting chats,
17 URL records, and 28 directory records. It contains all seven source types, but
uniform record sampling does not guarantee complete conversations or evidence chains.

## Research and design

### Starting point for iteration

The initial Orange experiments used HERB's corpus and agent harness with Jina
v5 omni small embeddings. Both Luna and Sol completed the baseline run. The
gold-evidence experiment below identifies evidence access as a major bottleneck: Sol's score rose from 44.36 to 90.81 when
given the cited sources and relevant employee/customer directory records directly.

Use Luna for routine iteration and Sol as a comparison when a change looks
promising. Luna finished this run faster; Sol scored 2.28 points higher. These are
single runs with an LLM judge, so that difference needs repeat measurements before
we treat it as a reliable model advantage.

Start with reliable access to directory metadata and fixes for the two role-tool
defects found in HERB. Then measure changes to retrieval and context delivery,
keeping the corpus, generation settings, and judge fixed. Retain the gold-evidence
run as a diagnostic comparison for answers that still score poorly. Track request
failures separately so we can distinguish system reliability from answer quality.

### Measured baseline

These experiments predate the packaged SGLang service and fixed GPT-5.4 judge
described below. Their corpus counts and scores refer to the experimental harness.

The comparison completed on 12 November 2026. Both models answered all 238 HERB
content questions against the full corpus, with no missing answers.

| Generation model | Mean score /100 | Median score | Generation time | HTTP 400 responses |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Luna | 42.08 | 35 | 20m 34s | 5 |
| GPT-6.1 Sol | 44.36 | 40 | 27m 52s | 2 |

The score is the upstream GPT-4o judge's rating of accuracy, completeness, and
relevance against a reference answer. It is an average rubric score, not a
percentage of questions passed. The evaluator does not check generated citations
against source documents.

Generation times exclude indexing and grading. Both runs used five question
workers and ran concurrently. HERB's built-in fallback handled the request
failures; those answers remain in the scores.

### Gold-evidence diagnostic

On 12 November 2026, we reran Sol on the same 238 content questions with the same
generation settings and upstream GPT-4o grader. Every dataset citation resolved
to a source in its owning product. The experimental retriever returned all chunks
from those sources, without a top-k limit. Reference answers went only to the
grader; Sol received source records and the question.

| Sol configuration | Mean score /100 | Gain over baseline |
| --- | ---: | ---: |
| Jina retrieval with HERB's agent | 44.36 | 0.00 |
| Cited evidence with unchanged HERB agent | 74.80 | +30.44 |
| Cited evidence with direct answering | 74.66 | +30.31 |
| Cited evidence and directory records with direct answering | 90.81 | +46.45 |

The agent condition kept HERB's tools, ten-iteration limit, finish check, and
fallback. It used the fallback on 110 questions. Direct answering used HERB's
existing `RetrieverQueryEngine` answer-synthesis path, bypassing the agent loop
and finish check. The final condition also supplied original employee/customer
directory records selected from product membership and identities in the evidence.
All three conditions completed every question, and an audit of the outgoing Sol
requests confirmed that every selected evidence chunk appeared in the model inputs.

Replacing retrieval recovered 30.44 points while preserving the agent harness.
Adding directory records to direct answering recovered another 16.14 points.
For example, two CollaborateForce questions about Engineering Lead and QA
Specialist recommendations each rose from 20 to 95 once Sol could identify the
employees' roles. With directory records, 209 answers improved over baseline,
25 tied, and four scored lower.

Two upstream role-tool defects help explain why this information is difficult
to obtain through the harness. `role_to_id_search` formats a prompt containing
`{text}` without supplying that field, raising `KeyError` before the helper call.
`id_to_role_search` builds an ID-to-role mapping but returns its keys, so the
caller receives employee IDs instead of roles. We reproduced both defects
separately and left them unchanged for the experiment.

These gains measure evidence access broadly. The oracle also removes unrelated
search results and supplies cited PR records directly, so the improvement cannot
be assigned entirely to vector retrieval. The near-equal agent and direct scores
are a single-run observation; they do not establish that agent behavior is
irrelevant. The remaining 9.19 points below 100 include generation errors,
possible gaps or inconsistencies in the evidence and references, and judge
behavior. We have not measured a causal percentage for each source of error.

### Experimental configuration

- Corpus: 34,403 source records, split into 34,531 chunks. The effective splitter
  settings were 1,024 tokens with 200 tokens of overlap. The upstream splitter
  uses these defaults despite the CLI's chunk settings.
- Embeddings: `jinaai/jina-embeddings-v5-omni-small`, revision
  `950200abde3a3bcf3d5bdfe5d28fb5bb5e7dfbb0`, using its text-only retrieval
  adapter, query/document prefixes, and normalized 1,024-dimensional vectors.
  The index was built on a Modal L4. The deployment prefers L4 with A10 fallback.
- Retrieval: top 20 BM25 results plus top 20 vector results, deduplicated, with
  no reranker.
- Agent: HERB's ReAct harness and metadata tools, one attempt per question,
  at most ten agent iterations, and its existing fallback behavior.
- Generation: OpenAI Responses API, medium reasoning, temperature 1, and a
  16,384-token output cap per request. Request timeout was 180 seconds, with
  previous-response tracking disabled.
- Helpers and evaluation: the upstream GPT-4o metadata helpers, finish check,
  and content evaluator.
- HERB revision: `db3bf9b3f911745726c579c9dbf9f7f6b2c05b36`.

Use Responses for these models. Sol repeatedly timed out through Chat Completions,
including with a 600-second timeout. A separate diagnostic on the same HERB
prompt consumed all 4,096 allowed output tokens as reasoning and returned no text
through Chat Completions; Responses returned text in seven seconds. The final
comparison reran both models through Responses. Earlier runs and diagnostics are
excluded from the table.

### What this establishes for the task

These experiments provide a measured starting point for improving the assistant.
All 238 questions are public, and the runs used the full HERB corpus available to
the experimental harness. They do not validate a private evaluation split or the
early step targets of 80% and 95%. The current verifier defines partial-credit
scoring and checks citation validity, but its threshold still needs calibration
on the task's actual corpus with the fixed judge. Step 1 now asks for an optimized assistant without a numerical success target. Full
calibration with the fixed answer and citation judges remains outstanding.

### Research artifacts

The local HERB checkout and run artifacts are gitignored. These links resolve in
the development workspace; the files are not included in the tracked task.

- [Comparison results](../../../HERB/code/local-run/jina-responses-comparison/summary.json)
- [Configuration and provenance](../../../HERB/code/local-run/jina-responses-comparison/manifest.json)
- [Luna answers and scores](../../../HERB/code/local-run/jina-responses-comparison/gpt-6-luna/scored-answers.json)
- [Sol answers and scores](../../../HERB/code/local-run/jina-responses-comparison/gpt-6.1-sol/scored-answers.json)
- [Gold-evidence comparison and paired scores](../../../HERB/code/local-run/sol-gold-evidence/comparison.json)
- [Gold-evidence agent and direct summaries](../../../HERB/code/local-run/sol-gold-evidence/summary.json)
- [Directory-augmented answers and scores](../../../HERB/code/local-run/sol-gold-evidence-with-metadata/oracle_direct-scored-answers.json)
- [Gold-evidence configuration](../../../HERB/code/local-run/sol-gold-evidence/manifest.json)
- [Directory-augmented configuration](../../../HERB/code/local-run/sol-gold-evidence-with-metadata/manifest.json)
- [Role-tool reproduction results](../../../HERB/code/local-run/sol-gold-evidence/tool-audit.json)
- [Gold-evidence runner](../../../HERB/code/run_gold_evidence.py)
- [Comparison runner](../../../HERB/code/run_jina_comparison.py)
- [Modal embedding service](../../../HERB/code/jina_modal.py)

The `citations` field in the exported results contains the dataset's reference
citations. It is not a record of verified citations produced by the assistant.

## Build and deliver

`tasks/swe-m2-ai-engineer/knowledge-work-assistant/` contains the Harbor task sources: `task.toml`, agent image inputs under `environment/`, the candidate instruction at `steps/01-build-rag/instruction.md`, and the verifier under `steps/01-build-rag/tests/`. Run the generated bundle with Harbor or Oddish; packaging stages the GPU build inputs and gives the task directory its declared name. The candidate reads the instruction and works in the agent image. The separate verifier image receives `tests/`, including the private evaluation inputs.

`authoring/swe-m2-ai-engineer/knowledge-work-assistant/` is the author workspace for the same task. It contains this README, local checks in `checks/`, preparation and packaging scripts in `scripts/`, and the author dependency files `pyproject.toml` and `uv.lock`. `checks/` runs the verifier, packaging, and runtime from the author's machine. The runner scores the candidate with the task's `steps/01-build-rag/tests/`. `scripts/prepare_data.py` writes the generated corpus and private cases into the task tree. `scripts/package_step.py` copies runtime files from that tree into `dist/` here. `scripts/calibrate_judges.py` writes ignored reports under `artifacts/`.

The repository-root `pyproject.toml` depends on this authoring project for local commands. Container dependencies stay in the task's `environment/pyproject.toml`. The verifier image has its own lock under `steps/01-build-rag/tests/`.

Runtime paths below are relative to the Harbor task. `checks/` and `scripts/` refer to this authoring folder. The packaging script creates `dist/` here on demand; it can be removed after use.

From the repository root:

```bash
uv sync --frozen
uv run python authoring/swe-m2-ai-engineer/knowledge-work-assistant/scripts/prepare_data.py --herb /path/to/HERB
uv run pytest -q
uv run python authoring/swe-m2-ai-engineer/knowledge-work-assistant/scripts/package_step.py
```

The archive is `authoring/swe-m2-ai-engineer/knowledge-work-assistant/dist/knowledge-work-assistant-step1.tar.gz`, with a SHA-256 file
beside it. It contains a complete step-1 task, including prepared sample data and
private verifier inputs. Extract it and pass the `swe-m2_ai-engineering_knowledge-work-assistant/`
directory to Oddish. It does not need the author's HERB checkout or virtualenv.
The packaging script derives that directory name from `[task].name`; the repository
folder keeps its shorter name. `[metadata].reward_type` declares the continuous reward.
`BUNDLE_MANIFEST.json` records the hash of every included source/input file.
The packaged folder contains only `task.toml`, `environment/`, `steps/01-build-rag/`,
and that manifest. Authoring scripts, local checks, and author dependency files stay
outside it. Generate Oddish upload code when needed, outside the artifact folder.
Packaging also stages the canonical GPU runtime inputs under the verifier's
`tests/gpu-runtime/` build context. Launch the packaged task, rather than the
authoring directory: Harbor builds each Dockerfile from its own directory and
cannot copy sibling environment files. The manifest covers these staged copies.

Source preparation requires HERB revision `db3bf9b3f911745726c579c9dbf9f7f6b2c05b36`.
It generates ignored files under `environment/data/`, `environment/resources/corpus/`, and
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
builds a distinct image from `steps/01-build-rag/tests/Dockerfile`, starts a fresh
GPU container, transfers `/app`, and invokes `/tests/test.sh`. Tests and private
inputs are baked into that image; Harbor does not upload them at runtime when a
dedicated verifier Dockerfile is present. The adapter calls
`verify(context: VerificationContext) -> VerificationResult`.
Its explicit registry attempts every named requirement check independently. A wrong
field description or incomplete help text fails its own check without skipping
CLI, ingestion, or retrieval checks. Each check prepares its own inputs and reports
any execution failure it encounters. Judge and infrastructure errors still invalidate
evaluation rather than become candidate failures.

Both environments request one L4 GPU on Modal. SGLang 0.5.9 serves the merged
`jinaai/jina-embeddings-v5-text-small-retrieval` checkpoint at revision
`6856e76bb72982e58de0620458a4e8b3614da340`. This is Jina's text-retrieval tower;
image, audio, and video encoding are not exposed by this task. The first `embed`
call starts a detached local service, and later CLI processes reuse it. Query and
document prefixes, last-token pooling, and normalized 1,024-dimensional vectors
are preserved. The service uses BF16 and batches requests on the GPU.

The CUDA development image supplies the compiler needed by SGLang's kernels.
Weights and dependencies are installed during the build. Runtime inference uses
localhost only, including in the fresh verifier; no embedding-service host needs
to be added to the external network allowlist. The service receives no API keys.

Development and verifier policies allow only `api.openai.com`, from container
startup through execution. Packages and coding harnesses that require public
downloads must be provisioned before development starts. The submitted app must
keep any local dependencies under `/app` so they survive the transfer. The fresh verifier inherits no development processes,
temporary files, or changes outside the declared artifacts.

Modal enforces this allowlist on TLS hostnames, not individual API paths or model
names. Its [network policy documentation](https://modal.com/docs/guide/sandbox-networking)
also notes that DNS remains available and domain fronting is not prevented by the
allowlist alone. This is restricted model-service access, not a completely offline
container or a guarantee against every possible exfiltration channel.

| Requirement | Test |
| --- | --- |
| Required async function and Pydantic model source declarations | `test_interfaces` |
| Executable help | `test_cli_help` |
| Answering before ingestion fails | `test_answer_before_ingestion` |
| Ingest API and persistence across processes | `test_ingestion_and_persistence` |
| Complete corpus persisted after the end-to-end CLI refresh | `test_full_corpus_persistence` |
| Skip existing IDs while adding new documents | `test_duplicate_documents` |
| Refresh changes content and removes absent IDs | `test_refresh_replaces_index` |
| CLI calls the public functions; generation calls retrieval | `test_required_call_paths` |
| Multiple question files and JSON answer arrays | `test_cli_question_files` |
| JSON questions on stdin, preserved IDs, EOF, and JSON array output | `test_cli_stdin` |
| bm25 returns nonempty passages from a fresh ten-document corpus | `test_bm25_behavior` |
| embed returns nonempty passages from a fresh ten-document corpus | `test_embed_behavior` |
| hybrid returns nonempty passages from a fresh ten-document corpus | `test_hybrid_behavior` |
| Progress file exists | `test_progress_file` |
| Held-out answer quality and citation validity | `test_holdout_accuracy` |

The verifier unconditionally clears transferred index state. Its first registered
check refreshes the private corpus using `orange ingest --path ... --refresh`. It then asks all 238 questions
using `orange answer --questions ... --output ...`. Accuracy never invokes the
application's Python functions directly and does not depend on an interface-check
pass. Later functional checks use their own small corpora.

`test_accuracy.py` runs the answer judge first for each question. It uses HERB's
accuracy, completeness, and relevance criteria with five anchored score bands.
The answer judge returns `incorrect` for 0, `partial` for 0.25/0.5/0.75, and
`correct` for 1. Missing or inconsistent verdicts invalidate evaluation.

Both judges use PydanticAI 2.68.0 with
[`NativeOutput(..., strict=True)`](https://ai.pydantic.dev/output/#native-output).
The Responses API receives a strict JSON Schema generated from `AnswerRating` or
`CitationRating`. Each model's `score` field description contains its full band
guidance; the prompt directs the judge to that field. Evaluator roles are supplied
through each PydanticAI agent's `system_prompt`; the Markdown files contain Goal,
Criteria, and Inputs sections. The citation `reason` field
asks for the claims and document IDs that justify the selected band. Its required
`claims` array contains each material claim's text, central/secondary importance,
`supported`/`contradicted`/`unverified` status, evidence references, and reason.
References identify the supplied citation by zero-based index and matching document
ID. The full quotation remains in the input rather than being copied by the judge.
Scores must be one of the five numeric bands, reasons must be
nonblank, and extra fields are rejected. Numeric strings, booleans, and scores
between bands are rejected. Pydantic also validates the answer verdict against its
band. Trusted rubric instructions are separate from the JSON evidence supplied in
the user message. The upstream template is retained for provenance; its informal
JSON example is not sent.

The answer template exposes `{question}`, `{reference_answer}`, `{candidate_answer}`,
and `{documents}`. Preparation preserves HERB's reference citation IDs, resolves
them within each question's product to normalized corpus IDs, and rejects missing
or ambiguous matches. The private loader verifies corpus and case hashes, then
attaches the complete original records to each question. Old cases without
reference evidence must be regenerated. These selections stay private and do not
depend on the candidate's retrieved passages or citations.
`{reference_answer}` contains only the original ground-truth answer value;
reference citation IDs are used to select `{documents}`, never appended to the answer.

The citation template exposes `{question}`,
`{candidate_answer}`, `{citations}`, and `{documents}`. The loader splits at
`## Inputs`: Goal and Criteria become trusted agent instructions, while the input
section becomes the user message. Each value is JSON-encoded before a single
formatting pass, preserving lists, full documents, literal braces, and newlines.
Missing or unused fields fail rather than silently dropping evidence. Reported
prompt hashes cover the complete Markdown templates, including placeholders.

The answer procedure adapts the reference-based, rubric-specific assessment in
[Prometheus](https://arxiv.org/abs/2310.08491) and its
[published prompt](https://github.com/prometheus-eval/prometheus-eval/blob/main/libs/prometheus-eval/prometheus_eval/prompts.py):
compare the response with a reference, stay within the supplied criteria, and
justify the rating. The citation procedure adapts the claim decomposition and
context-support checks in [RAGAS, section 3](https://aclanthology.org/2024.eacl-demo.16.pdf).
Here those checks guide one citation judgment over quotations and complete original
documents. These are adaptations: Prometheus's 1–5 output and RAGAS's separate
statement calls and supported-statement fraction are not used. Both judges retain
the five bands below, their existing Pydantic output schemas, and the conditional
answer-then-citation call order. Published results do not establish calibration
for these adapted prompts.

| Band | Answer quality | Citation quality |
| ---: | --- | --- |
| 0 | No correct substance answering the question | No material support, or context contradicts the central answer |
| 0.25 | A few relevant facts; the central answer is absent or largely wrong | Only a few minor claims supported |
| 0.5 | A meaningful part is correct, with major gaps, errors, or unsupported additions | Some central claims supported, with substantial gaps or misleading quotations |
| 0.75 | Central answer correct and mostly complete, with minor gaps | Most material claims supported in context, with minor coverage gaps |
| 1 | Accurate, complete, relevant; no unsupported material additions | Every material claim supported by its citations in full context |

Relevant additions supported by the authoritative documents receive credit even
when the reference omits them. The judge checks contradictions, dates, and
corrections in context; absence from the reference alone is not an unsupported
claim. Materially contradicting additions cap the answer band at 0.5.
Reference-selected records may not establish every fact in the
full corpus, so the judge must distinguish unestablished claims from contradictions.
These are provisional anchors requiring human review and live judge validation.
Historical HERB scores elsewhere in this README used the earlier continuous rubric
and are not directly comparable. The adapter maps each band to 0/25/50/75/100 for
existing percentage metrics; diagnostics also retain `answer_band` and `citation_band`.

`ORANGE_JUDGE_OUTPUT_RETRIES=3` allows up to three structured-output repair retries
after the initial response. A valid rating, including zero, is accepted immediately.
Exhausted retries, refusals, and incomplete responses invalidate evaluation; there
is no model fallback. The SDK separately allows at most two transport retries.
`checks/test_judge.py` exercises the real PydanticAI agents and
OpenAI SDK through an offline HTTP transport, including the outgoing strict schema.

Only an answer band of at least 0.75 can trigger the separate citation judge under
the declared configuration. Bands 0, 0.25, and 0.5 skip citation judging and receive
zero citation credit; any answer credit is retained. Before
that call, the verifier checks that every quote occurs in its cited source. The
citation judge receives each cited original document in full, including its title,
source type, and content. The verifier fetches these records from its authoritative
corpus and sends each source once, without truncation or candidate substitutions.
The rubric checks quotations against the full context, including negation,
qualifications, and later corrections. Uncited context cannot substitute for a
supporting quotation. Incorrect or missing answers skip citation judging and receive zero
in both components. Missing or invalid citations also skip citation judging and
receive zero citation credit, while retaining the answer score. The calls are
sequential within each question; a provider error invalidates evaluation instead
of becoming an incorrect verdict. These are partial-credit ratings, not a binary
correct-answer rate.

After a valid citation judgment, `judging/citation_scoring.py` validates every
reference against the supplied citation and original document. Supported and
contradicted claims require evidence references. Missing indices, mismatched
IDs, and quotes absent from the source invalidate evaluation as judge-output errors.
If no material claim is marked supported, the effective citation score is zero,
regardless of the model's proposed band. An empty claim list also earns zero.
Otherwise the proposed band is retained; one supported claim does not imply full
credit. The judge assesses only claims present in the answer, leaving omitted
answer content to the answer judge.

Diagnostics retain `proposed_score`, the effective `score`, structured `claims`,
and `adjustment="no_supported_material_claims"` when the zero-support rule applies.
Both scores use the existing percentage scale. This enforces consistency with the
structured assessments; it does not prove the model correctly classified every
claim or included every material claim. The answer judge and 0.75 citation gate
are unchanged.

Malformed records with identifiable question IDs receive zero for that question;
other answers remain eligible. Duplicate IDs invalidate all records for that ID.
Wrong question text and malformed citation objects also fail only their own
question. Records without usable expected IDs are counted separately, and omitted
expected questions score zero. Each question runs in its own CLI process. Unreadable JSON, a non-array outer
value, a timeout, or CLI failure earns zero only for that question. Ingestion
failure still prevents grading the batch. The quality check's status records output
validity, not whether an answer score crosses a threshold.

Scoring policy comes from the trusted `[verifier.env]` section in `task.toml`:

| Environment variable | Default |
| --- | ---: |
| `ORANGE_EVAL_QUALITY_WEIGHT` | `0.8` |
| `ORANGE_EVAL_FUNCTIONAL_WEIGHT` | `0.2` |
| `ORANGE_EVAL_ANSWER_WEIGHT` | `0.9` |
| `ORANGE_EVAL_CITATION_WEIGHT` | `0.1` |
| `ORANGE_EVAL_CITATION_MIN_ANSWER_SCORE` | `0.75` |
| `ORANGE_EVAL_QUESTION_CONCURRENCY` | `10` |

The entry point parses these once into an immutable `ScoringConfig`. Missing,
nonnumeric, nonfinite, out-of-range, or unnormalized settings invalidate evaluation.
There are no policy fallbacks in Python. Settings are recorded in the trusted report
and are not forwarded to candidate processes. The question concurrency must be a
positive integer. The judge runs up to ten question pipelines concurrently in one
async event loop. Each pipeline awaits its answer judgment before deciding whether
to call the citation judge. Completed diagnostics retain input question order; a
provider failure cancels unfinished pipelines and invalidates the run.

For question i in trial t, let a_it be the answer score divided by 100. Let c_it
be the citation score divided by 100, or zero when citation judging is skipped.
Both values are in [0, 1]. With the declared default weights:

```text
r_it = 0.9 * a_it + 0.1 * c_it
R_acc(t) = sum(r_it for every held-out question i) / N
F(t) = passing functional checks / all functional checks
e_it = 1 if a_it > 0 else 0
R_it = e_it * (0.8 * r_it + 0.2 * F(t))
R(t) = sum(R_it for every held-out question i) / N
     = 0.8 * R_acc(t) + 0.2 * F(t) * mean(e_it)
```

N is the total held-out question count (currently 238), including missing answers.
Failed and skipped functional checks remain in the contract denominator. With the
current 14 functional checks, each passing check earns 1/14 of contract credit, awarded only on questions with
a nonzero answer score. An all-zero answer batch earns zero total reward even
when every functional check passes.
`judgments.json` records each answer verdict, both ratings, the citation disposition,
`reward_eligible` (e_it), and `accuracy_reward` (r_it). The trial report records their weighted mean as
`quality_fraction`, the raw contract fraction as `functional_fraction`, the eligible question fraction
as `nonzero_answer_fraction`, and the final reward.

The weights come from environment configuration. At the defaults, answer correctness
accounts for up to 72% of reward, citations 8%, and functional checks 20%. Full reward
requires perfect answer and citation scores and every functional check to pass.
There is no numerical success target or `min_reward` step gate. Harbor records the
continuous weighted reward; a completed run does not need a perfect reward.

For example, an answer band of 0.75 with citation support 0.5 earns question credit
0.725 in the quality component, or 0.78 total when all contracts pass. An incorrect
answer earns zero total even if its quotations are exact and all contracts pass.
One perfect answer and one zero-scored answer, with all contracts passing, earn
a trial reward of 0.5. If the
trial averages 90 for answers and 100 for eligible citations, with no skipped
citation judgments and all functional checks passing, the reward is 0.928.
Perfect answers with zero citation credit and all functional checks passing earn
0.92. Model-service errors invalidate the run and produce no reward.

The verifier separates requirement checks, candidate execution, judging, and result
handling. `verify.py` remains Harbor's entry point; it constructs the context and
calls `verifier.runner.verify()`. The registry runs CLI accuracy evaluation before
the functional checks.

```text
steps/01-build-rag/tests/
├── test.sh
├── verify.py                    # Harbor setup and exit handling
├── private/                     # Private corpus, questions, and manifest
└── verifier/
    ├── contracts.py             # Shared types and errors
    ├── config.py                # Validated verifier environment settings
    ├── registry.py              # Ordered checks and prerequisites
    ├── runner.py                # Execution and dependency skips
    ├── scoring.py               # Pure reward aggregation
    ├── inputs.py                # Private-input loading and hash checks
    ├── reporting.py             # Diagnostics and reward files
    ├── checks/
    │   ├── support.py           # Scenario fixtures and strict contract validation
    │   ├── accuracy_inputs.py   # Per-question validation for partially malformed batches
    │   ├── test_interfaces.py
    │   ├── test_retrieval.py    # Independent per-method behavior checks
    │   ├── test_cli.py
    │   ├── test_storage.py
    │   ├── test_accuracy.py
    │   └── test_progress.py
    ├── application/
    │   ├── client.py            # CLI/probe adapter and workspace artifacts
    │   ├── source.py            # Trusted source parsing; never imports candidate code
    │   └── process.py           # Identity, timeouts, output limits, cleanup
    ├── judging/
    │   ├── client.py            # Typed PydanticAI agents and prompt loading
    │   ├── schemas.py           # Strict provider-output models and validation
    │   ├── answer_prompt.md     # Accuracy judge instructions
    │   ├── citation_prompt.md   # Citation judge instructions
    │   └── herb_prompt.md       # Upstream template retained for provenance
    └── probes/
        ├── test_application.py  # Candidate API execution and call tracing
        └── test_chroma.py       # Stored document/vector inspection
```

Checks share helpers without importing one another. Candidate probes are
self-contained because the candidate UID cannot import private verifier files.
The interface check reads `main.py` as bounded source data and inspects its syntax
tree in the trusted verifier. It checks the published model fields, literal
descriptions, type alias, and async signatures, allowing additional model fields,
qualified imports, and forward annotations. It never imports the application,
executes its interpreter, or accepts stdout as proof of interface compliance.
The old `interfaces` subprocess probe is removed.

This establishes the declared source contract, not the runtime behavior of
arbitrary Python. Decorators, dynamic namespace changes, and import side effects
are not executed or proven safe by static inspection. Separate CLI and storage
checks establish observed behavior. Remaining runtime probe records have strict
outer schemas, but their contents and internal call traces remain untrusted.
The packaging check runs the complete controlled verifier from an extracted
bundle in an isolated Python process, including its relocated probes and prompt.

Chroma 1.5.9 is pinned in both dependency locks. `/app/state/chroma` holds a
`documents` collection with original IDs, complete bodies, and vectors. Storage
checks reopen it using the trusted interpreter, compare actual UTF-8 body SHA-256
hashes and exact live IDs, and reject chunks belonging to removed documents.
They remove the ingestion input and temporarily move state away to test persistence
and dependence on that directory. These checks do not prove forensic deletion,
absence of all undeclared caches, or that no alternative index is used.

The candidate receives a version-matched offline Chroma API reference through
`environment/resources/chroma-api.md`; the Docker build checks its version heading
against the installed package. No grading details appear in that reference.

The judge is fixed in code to `gpt-6.1-terra`, Responses API, high reasoning,
with separate answer and citation agents. Both use strict native Pydantic output
schemas. There is no model override or fallback. Keep complete evidence records
in each request; do not silently truncate evidence. The earlier GPT-5.4 and
GPT-6 Luna calibrations remain in the author artifacts for comparison. Their
results do not establish GPT-6.1 Terra's behavior.

The trusted report records the model, reasoning setting, structured-output mode,
hashes of the HERB template, both prompts, and both output schemas (including band
guidance), input hashes, and per-check results.
Per-question diagnostics record scores, reasons, answer verdicts, and citation skips. Provider failures invalidate
the run, preserve completed diagnostics, and remove any stale reward files.

## Credentials and process boundary

The agent and verifier have distinct images built from the same CUDA base and
locked Jina/SGLang runtime inputs. Evaluation never runs in the agent image.
The verifier image has two locked Python environments. `/opt/runtime` keeps SGLang's
OpenAI 2.6.1 dependency and runs the submitted application. `/opt/verifier` uses
PydanticAI 2.68.0 and OpenAI 3.49.0, with dependencies declared in
`steps/01-build-rag/tests/pyproject.toml` and its lockfile. The agent image has only
the application runtime. `tests/test.sh` launches
`/opt/verifier/bin/python -I /tests/verify.py`. Chroma is pinned to 1.5.9 in both
environments so the trusted storage probe can inspect the application's database.
An application's own `/app/.venv` still takes precedence for its API probes.

The runner supplies `OPENAI_API_KEY` through its secret management. Oddish resolves
this supported source from its platform settings. `task.toml` maps it to:

- `ORANGE_JUDGE_API_KEY`: verifier-only judge variable.
- `ORANGE_OPENAI_API_KEY`: application credential for `gpt-6-luna`.

`task.toml` exposes `ORANGE_OPENAI_API_KEY` to the application so a coding harness's
`OPENAI_API_KEY` cannot overwrite it. The runner uses its own Modal credentials to
create the GPU containers; those credentials are not exposed inside them.
The verifier receives its judge key separately and
passes only the explicitly allowlisted application variables to candidate processes.
Credentials are never baked into images or written to the task files.
The chosen coding harness's credentials are supplied separately by Oddish.
The agent has an 8-hour limit. The verifier has a separate 24-hour limit, declared
at both root and step level. After CLI refresh ingestion, it runs up to ten
single-question CLI processes against the shared index. Each receives 1,800 seconds
from launch; queue time does not count. For 238 questions, 24 waves take at most
12 hours. The remaining budget covers ingestion, judging, functional checks, and
overhead. Functional answer checks use the same 30-minute allowance per question,
with batch deadlines scaled by their question count.
Answer generation completes before the existing ten concurrent judging pipelines
run; citation judging remains conditional on the answer score.

`ORANGE_EVAL_GENERATION_CONCURRENCY=10` and
`ORANGE_EVAL_GENERATION_TIMEOUT_SEC=1800` are required verifier environment settings.
They are parsed once into `GenerationConfig` and recorded in the report. Each
process has distinct JSON input/output paths, and failed process groups are killed.
A process can submit answers only for its assigned question. `generation.json`
records accepted answers and per-question failures in the trusted verifier logs.

For a direct Harbor run outside Oddish, supply `OPENAI_API_KEY` and the selected
harness's credentials, then run the extracted task with the standard CLI:

```bash
MODAL_ENVIRONMENT=testing uv run harbor run \
  --path /path/to/extracted/knowledge-work-assistant \
  --agent "$HARNESS" --model "$CODING_MODEL" --env modal
```

The verifier runs as root and the submitted app as UID/GID 10001. `/tests` and
`/logs/verifier` are restricted to the verifier. Application subprocesses have
deadlines and bounded captured output. CLI call-path checks launch `/app/orange`
itself and collect Python startup-hook observations from that execution, including
shell launchers forwarding to Python. They do not run `cli.py` as a substitute.
If the launcher disables Python startup hooks, tracing is unavailable and this
check cannot establish the call path; it fails rather than silently bypassing the
launcher. Trace files and imported aliases remain candidate-process observations,
not authenticated evidence against deliberate instrumentation evasion.

Immediately after the end-to-end CLI run, a separate functional check inspects
the full persisted corpus before any small fixture replaces it. It compares exact
IDs and body hashes, requires finite nonzero vectors, and rejects stale chunk
owners. It never reingests to repair a partial index. Answer-quality failure does
not skip this storage check. Each retrieval method then has an independent
behavior test: clear state, ingest ten documents with the real executable and
`--refresh`, and require nonempty passages for an answerable query. These checks
do not grade ranking or distinguish algorithm internals; retrieval quality remains
part of the end-to-end answer evaluation.

## Validation and remaining work

Local author checks use a deterministic Chroma fixture application
and controlled judge responses. They cover the
complete registry, targeted broken submissions, full-denominator scoring, malformed
judge responses, dependency skips, and stale reward cleanup. These fixtures are
not oracle solutions and do not establish the answer quality of an actual RAG system.
The verdict extension and conditional citation flow have controlled-test coverage,
including SDK transport tests for native schemas, invalid outputs,
verdict consistency, refusals, and incomplete responses.

A live calibration on 14 November 2026 used three private questions and controlled
answer variants, with two repetitions: 72 answer judgments and 50 citation judgments.
The production 0.75 gate matched every observed call, including nine at the boundary;
all 22 below-threshold answers skipped citation judging. Relevant supported additions
received 1.0 from both judges in all six follow-up cases. Calibration also exposed
undeserved partial credit for wholly contradictory answers and irrelevant citations,
unstable treatment of unverified additions, and missing role-identification evidence
in the answer judge's context. These are unresolved semantic issues. See the
[private local calibration report](artifacts/judge-calibration-2026-11-14/report.md)
and [reusable runner](scripts/calibrate_judges.py). Generated fixtures and results
are ignored by Git; expectations have not been independently human-reviewed.

The updated Chroma runtime image and the full RAG evaluation still need container
and model validation. The judge calibration ran in fresh CPU containers with a
controlled replay CLI; earlier GPU/container results below predate these changes.

A prior Modal Linux runtime passed all 11 registered checks with the verifier,
controlled application, and controlled judge. It verified that
candidate UID 10001 could neither read `/tests/verify.py` nor write the reward,
and did not inherit the synthetic judge credential. Its entry point is
`checks/test_container_smoke.py`; its fixture modules belong only in the smoke image.
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
reward zero. `checks/test_environment_smoke.py` contains the boundary probes.
This control overrode the GPU type to A10 after L4 startup stalled; the delivered
configuration retains L4, whose offline embedding inference passed separately.

A five-answer live smoke check on the fixed judge scored correct/wrong/partial/
unsupported-extra-claims/prompt-injection examples at 100/0/65/82/0. The score of 82
shows that the inherited rubric can still reward an otherwise correct answer with
unsupported additions. A single example of each kind is not a calibration study.

The 2026-11-14 GPT-6 Luna High recalibration completed 72 answer judgments and
51 conditional citation judgments on variants of three private questions. All six
fully contradicting answers scored zero. In the follow-up with complete role
citations, all six supported-extra-detail answers scored 1 for both components.
The 0.75 gate held in every case, and baseline groups reached ten concurrent
requests. Irrelevant citations still received 0.25 in five of six cases, and
unverified additions varied between answer scores 0.5 and 0.75. See the
[calibration report](artifacts/judge-calibration-luna-high-2026-11-14/report.md)
for distributions, comparisons, and limitations.

A matched rerun with the lower-band tie-break instruction did not resolve either
issue: unverified extras still split three times at 0.5 and three at 0.75, and
five of six irrelevant citations still earned nonzero credit, including one at
0.5. All six supported-extra follow-up answers retained full answer and citation
credit. The 72 answer and 51 citation calls completed successfully with the gate
intact. The [lower-band comparison](artifacts/judge-calibration-luna-high-lower-band-2026-11-14/report.md)
records the unchanged inputs, exact prompt change, and remaining limitations.

Structured citation assessments and deterministic zero-support enforcement then
reduced nonzero credit on irrelevant citations from five of six cases to zero of
six. The verifier overrode five raw 0.25 proposals. All six supported-extra
follow-up cases retained full answer and citation credit. One correct-answer
control lost citation credit because the model joined the wrong employee record;
answer-judge variability also remains. The run completed 72 answer and 52 citation
judgments, and all 214 local author checks passed. See the
[structured-claim comparison](artifacts/judge-calibration-luna-high-claims-2026-11-14/report.md)
for the raw/effective scores and remaining errors.

The progress check establishes only that a progress file exists. It does not
validate development experiments or question authorship, and it does not attempt
to establish when the application interfaces were written. The full final corpus includes the public sample; it is the Q&A
set that is held out. HERB itself is public, so withheld files do not establish
absence of model pretraining contamination.

An oracle RAG implementation, a full 238-question run using the fixed judge, and
broader calibration beyond these three questions remain separate work.

HERB's data and copied rubric retain its CC BY-NC 4.0 license. The bundle includes
the original license and attribution in the resource README, alongside the source
revision and a description of the data transformations. Chroma attribution and its
license are included in the offline API reference. This package does not grant additional commercial-use rights.

## SGLang performance

On 2026-11-12, both helpers were measured on a Modal L4 with four CPUs, 16 GB of
host memory, and external networking blocked. The benchmark uses 20 warm queries,
three disjoint batches of 128 development records, and 16 concurrent queries.
`checks/benchmark_jina.py` contains the workload.

| Measurement | Previous helper | SGLang helper |
| --- | ---: | ---: |
| Warm query, median | 159.1 ms | 22.5 ms |
| Warm query, p95 | 172.3 ms | 24.3 ms |
| Corpus records/second, median | 37.3 | 111.7 |
| 16 concurrent queries, total | 2.376 s | 0.064 s |
| First call, including startup | 25.4 s | 72.6 s |

SGLang stays resident after the calling process exits. A second CLI process reused
the same server PID and returned an embedding in 1.10 seconds, including its
one-time readiness check. Warm calls reuse HTTP connections and skip that check.
The first call includes local kernel compilation, so cold startup is slower.

Five texts, including empty input, multilingual text, and a longer passage, were
compared in both query and document roles. All ten vector comparisons had cosine
similarity above 0.99987 against the previous Omni helper. Full HERB answer quality
has not been rerun for this serving change. The runtime check used the CUDA task
image with Python development headers added as a layer; the Dockerfile now
installs those headers directly.

On 2026-11-13, a controlled Harbor run built the exact task Dockerfile and ran
`checks/test_environment_smoke.py` in both the agent and separate verifier containers.
Both used an NVIDIA L4 and SGLang 0.5.9, and produced normalized 1,024-dimensional
query and document embeddings as UID 10001. No separate embedding deployment or
agent-side package installation was needed; the bundled helper started the service
on its first call in each container.

The verifier had a different container ID, restored the declared `/app` artifact,
and had no undeclared development marker from `/tmp`. It reached `api.openai.com`
with an unauthenticated 401 response and could not reach the tested non-approved
HTTPS or HTTP destinations. The control completed without evaluation exceptions.
Its reward records infrastructure checks only; full RAG answer-quality evaluation
remains outstanding. The check used synthetic, unused API-key values and made no
paid model calls.

## Corpus attribution


The company records are adapted from [Salesforce AI Research's HERB benchmark](https://github.com/SalesforceAIResearch/HERB), revision `db3bf9b3f911745726c579c9dbf9f7f6b2c05b36`, under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Source records were normalized to JSON, directory records included, and a seeded 4% sample selected.

<details>
<summary>Creative Commons Attribution-NonCommercial 4.0 license</summary>

```text
Creative Commons Attribution-NonCommercial 4.0 International Public
License

By exercising the Licensed Rights (defined below), You accept and agree
to be bound by the terms and conditions of this Creative Commons
Attribution-NonCommercial 4.0 International Public License ("Public
License"). To the extent this Public License may be interpreted as a
contract, You are granted the Licensed Rights in consideration of Your
acceptance of these terms and conditions, and the Licensor grants You
such rights in consideration of benefits the Licensor receives from
making the Licensed Material available under these terms and
conditions.


Section 1 -- Definitions.

  a. Adapted Material means material subject to Copyright and Similar
     Rights that is derived from or based upon the Licensed Material
     and in which the Licensed Material is translated, altered,
     arranged, transformed, or otherwise modified in a manner requiring
     permission under the Copyright and Similar Rights held by the
     Licensor. For purposes of this Public License, where the Licensed
     Material is a musical work, performance, or sound recording,
     Adapted Material is always produced where the Licensed Material is
     synched in timed relation with a moving image.

  b. Adapter's License means the license You apply to Your Copyright
     and Similar Rights in Your contributions to Adapted Material in
     accordance with the terms and conditions of this Public License.

  c. Copyright and Similar Rights means copyright and/or similar rights
     closely related to copyright including, without limitation,
     performance, broadcast, sound recording, and Sui Generis Database
     Rights, without regard to how the rights are labeled or
     categorized. For purposes of this Public License, the rights
     specified in Section 2(b)(1)-(2) are not Copyright and Similar
     Rights.
  d. Effective Technological Measures means those measures that, in the
     absence of proper authority, may not be circumvented under laws
     fulfilling obligations under Article 11 of the WIPO Copyright
     Treaty adopted on December 20, 1996, and/or similar international
     agreements.

  e. Exceptions and Limitations means fair use, fair dealing, and/or
     any other exception or limitation to Copyright and Similar Rights
     that applies to Your use of the Licensed Material.

  f. Licensed Material means the artistic or literary work, database,
     or other material to which the Licensor applied this Public
     License.

  g. Licensed Rights means the rights granted to You subject to the
     terms and conditions of this Public License, which are limited to
     all Copyright and Similar Rights that apply to Your use of the
     Licensed Material and that the Licensor has authority to license.

  h. Licensor means the individual(s) or entity(ies) granting rights
     under this Public License.

  i. NonCommercial means not primarily intended for or directed towards
     commercial advantage or monetary compensation. For purposes of
     this Public License, the exchange of the Licensed Material for
     other material subject to Copyright and Similar Rights by digital
     file-sharing or similar means is NonCommercial provided there is
     no payment of monetary compensation in connection with the
     exchange.

  j. Share means to provide material to the public by any means or
     process that requires permission under the Licensed Rights, such
     as reproduction, public display, public performance, distribution,
     dissemination, communication, or importation, and to make material
     available to the public including in ways that members of the
     public may access the material from a place and at a time
     individually chosen by them.

  k. Sui Generis Database Rights means rights other than copyright
     resulting from Directive 96/9/EC of the European Parliament and of
     the Council of 11 March 1996 on the legal protection of databases,
     as amended and/or succeeded, as well as other essentially
     equivalent rights anywhere in the world.

  l. You means the individual or entity exercising the Licensed Rights
     under this Public License. Your has a corresponding meaning.


Section 2 -- Scope.

  a. License grant.

       1. Subject to the terms and conditions of this Public License,
          the Licensor hereby grants You a worldwide, royalty-free,
          non-sublicensable, non-exclusive, irrevocable license to
          exercise the Licensed Rights in the Licensed Material to:

            a. reproduce and Share the Licensed Material, in whole or
               in part, for NonCommercial purposes only; and

            b. produce, reproduce, and Share Adapted Material for
               NonCommercial purposes only.

       2. Exceptions and Limitations. For the avoidance of doubt, where
          Exceptions and Limitations apply to Your use, this Public
          License does not apply, and You do not need to comply with
          its terms and conditions.

       3. Term. The term of this Public License is specified in Section
          6(a).

       4. Media and formats; technical modifications allowed. The
          Licensor authorizes You to exercise the Licensed Rights in
          all media and formats whether now known or hereafter created,
          and to make technical modifications necessary to do so. The
          Licensor waives and/or agrees not to assert any right or
          authority to forbid You from making technical modifications
          necessary to exercise the Licensed Rights, including
          technical modifications necessary to circumvent Effective
          Technological Measures. For purposes of this Public License,
          simply making modifications authorized by this Section 2(a)
          (4) never produces Adapted Material.

       5. Downstream recipients.

            a. Offer from the Licensor -- Licensed Material. Every
               recipient of the Licensed Material automatically
               receives an offer from the Licensor to exercise the
               Licensed Rights under the terms and conditions of this
               Public License.

            b. No downstream restrictions. You may not offer or impose
               any additional or different terms or conditions on, or
               apply any Effective Technological Measures to, the
               Licensed Material if doing so restricts exercise of the
               Licensed Rights by any recipient of the Licensed
               Material.

       6. No endorsement. Nothing in this Public License constitutes or
          may be construed as permission to assert or imply that You
          are, or that Your use of the Licensed Material is, connected
          with, or sponsored, endorsed, or granted official status by,
          the Licensor or others designated to receive attribution as
          provided in Section 3(a)(1)(A)(i).

  b. Other rights.

       1. Moral rights, such as the right of integrity, are not
          licensed under this Public License, nor are publicity,
          privacy, and/or other similar personality rights; however, to
          the extent possible, the Licensor waives and/or agrees not to
          assert any such rights held by the Licensor to the limited
          extent necessary to allow You to exercise the Licensed
          Rights, but not otherwise.

       2. Patent and trademark rights are not licensed under this
          Public License.

       3. To the extent possible, the Licensor waives any right to
          collect royalties from You for the exercise of the Licensed
          Rights, whether directly or through a collecting society
          under any voluntary or waivable statutory or compulsory
          licensing scheme. In all other cases the Licensor expressly
          reserves any right to collect such royalties, including when
          the Licensed Material is used other than for NonCommercial
          purposes.


Section 3 -- License Conditions.

Your exercise of the Licensed Rights is expressly made subject to the
following conditions.

  a. Attribution.

       1. If You Share the Licensed Material (including in modified
          form), You must:

            a. retain the following if it is supplied by the Licensor
               with the Licensed Material:

                 i. identification of the creator(s) of the Licensed
                    Material and any others designated to receive
                    attribution, in any reasonable manner requested by
                    the Licensor (including by pseudonym if
                    designated);

                ii. a copyright notice;

               iii. a notice that refers to this Public License;

                iv. a notice that refers to the disclaimer of
                    warranties;

                 v. a URI or hyperlink to the Licensed Material to the
                    extent reasonably practicable;

            b. indicate if You modified the Licensed Material and
               retain an indication of any previous modifications; and

            c. indicate the Licensed Material is licensed under this
               Public License, and include the text of, or the URI or
               hyperlink to, this Public License.

       2. You may satisfy the conditions in Section 3(a)(1) in any
          reasonable manner based on the medium, means, and context in
          which You Share the Licensed Material. For example, it may be
          reasonable to satisfy the conditions by providing a URI or
          hyperlink to a resource that includes the required
          information.

       3. If requested by the Licensor, You must remove any of the
          information required by Section 3(a)(1)(A) to the extent
          reasonably practicable.

       4. If You Share Adapted Material You produce, the Adapter's
          License You apply must not prevent recipients of the Adapted
          Material from complying with this Public License.


Section 4 -- Sui Generis Database Rights.

Where the Licensed Rights include Sui Generis Database Rights that
apply to Your use of the Licensed Material:

  a. for the avoidance of doubt, Section 2(a)(1) grants You the right
     to extract, reuse, reproduce, and Share all or a substantial
     portion of the contents of the database for NonCommercial purposes
     only;

  b. if You include all or a substantial portion of the database
     contents in a database in which You have Sui Generis Database
     Rights, then the database in which You have Sui Generis Database
     Rights (but not its individual contents) is Adapted Material; and

  c. You must comply with the conditions in Section 3(a) if You Share
     all or a substantial portion of the contents of the database.

For the avoidance of doubt, this Section 4 supplements and does not
replace Your obligations under this Public License where the Licensed
Rights include other Copyright and Similar Rights.


Section 5 -- Disclaimer of Warranties and Limitation of Liability.

  a. UNLESS OTHERWISE SEPARATELY UNDERTAKEN BY THE LICENSOR, TO THE
     EXTENT POSSIBLE, THE LICENSOR OFFERS THE LICENSED MATERIAL AS-IS
     AND AS-AVAILABLE, AND MAKES NO REPRESENTATIONS OR WARRANTIES OF
     ANY KIND CONCERNING THE LICENSED MATERIAL, WHETHER EXPRESS,
     IMPLIED, STATUTORY, OR OTHER. THIS INCLUDES, WITHOUT LIMITATION,
     WARRANTIES OF TITLE, MERCHANTABILITY, FITNESS FOR A PARTICULAR
     PURPOSE, NON-INFRINGEMENT, ABSENCE OF LATENT OR OTHER DEFECTS,
     ACCURACY, OR THE PRESENCE OR ABSENCE OF ERRORS, WHETHER OR NOT
     KNOWN OR DISCOVERABLE. WHERE DISCLAIMERS OF WARRANTIES ARE NOT
     ALLOWED IN FULL OR IN PART, THIS DISCLAIMER MAY NOT APPLY TO YOU.

  b. TO THE EXTENT POSSIBLE, IN NO EVENT WILL THE LICENSOR BE LIABLE
     TO YOU ON ANY LEGAL THEORY (INCLUDING, WITHOUT LIMITATION,
     NEGLIGENCE) OR OTHERWISE FOR ANY DIRECT, SPECIAL, INDIRECT,
     INCIDENTAL, CONSEQUENTIAL, PUNITIVE, EXEMPLARY, OR OTHER LOSSES,
     COSTS, EXPENSES, OR DAMAGES ARISING OUT OF THIS PUBLIC LICENSE OR
     USE OF THE LICENSED MATERIAL, EVEN IF THE LICENSOR HAS BEEN
     ADVISED OF THE POSSIBILITY OF SUCH LOSSES, COSTS, EXPENSES, OR
     DAMAGES. WHERE A LIMITATION OF LIABILITY IS NOT ALLOWED IN FULL OR
     IN PART, THIS LIMITATION MAY NOT APPLY TO YOU.

  c. The disclaimer of warranties and limitation of liability provided
     above shall be interpreted in a manner that, to the extent
     possible, most closely approximates an absolute disclaimer and
     waiver of all liability.


Section 6 -- Term and Termination.

  a. This Public License applies for the term of the Copyright and
     Similar Rights licensed here. However, if You fail to comply with
     this Public License, then Your rights under this Public License
     terminate automatically.

  b. Where Your right to use the Licensed Material has terminated under
     Section 6(a), it reinstates:

       1. automatically as of the date the violation is cured, provided
          it is cured within 30 days of Your discovery of the
          violation; or

       2. upon express reinstatement by the Licensor.

     For the avoidance of doubt, this Section 6(b) does not affect any
     right the Licensor may have to seek remedies for Your violations
     of this Public License.

  c. For the avoidance of doubt, the Licensor may also offer the
     Licensed Material under separate terms or conditions or stop
     distributing the Licensed Material at any time; however, doing so
     will not terminate this Public License.

  d. Sections 1, 5, 6, 7, and 8 survive termination of this Public
     License.


Section 7 -- Other Terms and Conditions.

  a. The Licensor shall not be bound by any additional or different
     terms or conditions communicated by You unless expressly agreed.

  b. Any arrangements, understandings, or agreements regarding the
     Licensed Material not stated herein are separate from and
     independent of the terms and conditions of this Public License.


Section 8 -- Interpretation.

  a. For the avoidance of doubt, this Public License does not, and
     shall not be interpreted to, reduce, limit, restrict, or impose
     conditions on any use of the Licensed Material that could lawfully
     be made without permission under this Public License.

  b. To the extent possible, if any provision of this Public License is
     deemed unenforceable, it shall be automatically reformed to the
     minimum extent necessary to make it enforceable. If the provision
     cannot be reformed, it shall be severed from this Public License
     without affecting the enforceability of the remaining terms and
     conditions.

  c. No term or condition of this Public License will be waived and no
     failure to comply consented to unless expressly agreed to by the
     Licensor.

  d. Nothing in this Public License constitutes or may be interpreted
     as a limitation upon, or waiver of, any privileges and immunities
     that apply to the Licensor or You, including from the legal
     processes of any jurisdiction or authority.
```

</details>
