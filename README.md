<p align="center">
  <img src="assets/repo-icon.png" width="128" height="128" alt="SWE Marathon 2: a running track shaped like an M with two checkpoints">
</p>

# SWE Marathon 2

Tasks for evaluating coding agents over successive rounds of software development. An agent builds an application, then improves it as requirements change. Each step should preserve the earlier behavior that still matters and provide evidence that the new requirements work.

The repository is under development. The first knowledge-assistant step has a Harbor environment and verifier. Its answer-quality target still needs an oracle implementation and calibration.

## Task progress

Status as of 12 November 2026. “Implemented” refers to task infrastructure; it does not mean an agent has solved the task.

| Task | Step | Progress | Remaining work |
| --- | --- | --- | --- |
| [Knowledge work assistant](authoring/swe-m2-ai-engineer/knowledge-work-assistant/README.md) | [1. Build RAG](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/01-build-rag/instruction.md) | Environment, verifier, data preparation, and packaging implemented; controlled checks validated | Build an oracle, run all 238 quality questions with the fixed judge, and calibrate the 80% target |
| Knowledge work assistant | [2. Expand the corpus](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/02-expand-corpus/instruction.md) | Draft instruction | Define additional data and evaluation splits; implement and calibrate the 95% target |
| Knowledge work assistant | [3. Harden ingestion](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/03-harden-ingestion/instruction.md) | Draft instruction | Define the workload and failure scenarios; build the environment, verifier, and oracle |
| Knowledge work assistant | [4. Optimize retrieval](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/04-optimize-retrieval/instruction.md) | Draft instruction | Define latency and quality criteria; build the environment, verifier, and oracle |
| [Titans training](tasks/swe-m2-ai-research/titans-training/design.md) | Improve a training baseline | Source inspection and initial design | Define data, compute, and success criteria; measure a baseline and build the environment and verifier |
| [London battle royale](tasks/swe-m2-game-developer/london-battle-royale/steps/01-build-game/instruction.md) | 1. Build the game | Instruction, ten component briefs, and reference images prepared | Implement the runnable environment and evaluation; validate a complete game |

Only knowledge-assistant step 1 is enabled in a `task.toml`. Later instructions are design drafts.

## Knowledge-assistant foundation

Orange is a RAG assistant over a fictional company's documents, conversations, project history, and directory records. The agent defines typed ingestion, retrieval, and generation interfaces, implements a CLI, and creates its own development questions and reference answers.

The development environment contains a uniform 4% sample of HERB: 1,570 of 39,268 source records. Evaluation rebuilds the index from the full sanitized corpus and asks 238 withheld content questions. HERB is public; withholding its questions from the container does not establish freedom from pretraining contamination.

SGLang serves Jina v5 small's merged text-retrieval checkpoint locally on the container's GPU using bundled, pinned weights. The available generation model is `gpt-6-luna`. The verifier uses HERB's answer-rating rubric with the fixed judge `gpt-5.4-2026-03-05` and an explicit answer verdict. A separate citation judgment runs only after a correct or partial verdict and successful quotation checks. The task has no numerical success target. Both judges use five anchored bands from 0 to 1; the citation judge receives the full original documents. Reward uses raw normalized scores: 80% answer/citation quality and 20% functional checks, with answer and citation weights of 90% and 10% within quality.

Every evaluation starts in a fresh container and restores the declared `/app` artifacts. Both development and verification allow HTTPS only to `api.openai.com`; Jina needs no network connection. Modal's domain allowlist still permits DNS and does not restrict individual API paths. Private references, judge credentials, and reward files remain outside the submitted application's control.

### What has been validated

- All 112 local author checks pass, covering verifier orchestration, targeted broken submissions, five-band structured judging, per-question failures, packaging, and network configuration.
- A controlled Linux application and judge passed all 11 registered requirement checks. This establishes verifier behavior, not RAG answer quality.
- The SGLang helper passed offline L4 validation: 22.5 ms median warm queries and 111.7 corpus records/second, versus 159.1 ms and 37.3 previously. First startup takes about 73 seconds; later CLI processes reuse the server.
- On 13 November, a controlled Harbor run built the exact Dockerfile and exercised SGLang in both L4 agent and fresh L4 verifier containers. GPU embeddings, artifact transfer, and the restricted network checks passed without evaluation exceptions. This validates the runtime setup; full RAG answer quality remains unverified.
- Live judge examples scored correct, wrong, partial, unsupported-extra-claims, and prompt-injection answers at 100, 0, 65, 82, and 0. The **82 for an answer with unsupported additions** shows that the inherited rubric remains permissive.

A full 238-question run with the final judge and a working oracle remains unverified. Coding-harness trials are handled by Oddish. See the [task README](authoring/swe-m2-ai-engineer/knowledge-work-assistant/README.md) for exact contracts, credentials, validation details, and limitations.

## Local development setup

Use Python 3.13 and `uv` from the repository root. The root `pyproject.toml` and
`uv.lock` manage the local `.venv` used to author, test, and package tasks. The root
project reuses the first task's authoring dependencies through a local path dependency.
Task-container dependencies remain in each task's `environment/pyproject.toml`.
Orange's judge has separate locked dependencies under `steps/01-build-rag/tests/`
because PydanticAI and SGLang require different OpenAI SDK versions.

| Tool or dependency | Purpose |
| --- | --- |
| Python 3.13 | Run authoring scripts and verifier checks locally |
| `uv` | Create `.venv`, resolve dependencies, and run project commands |
| Harbor with its Modal extra | Parse task packages, build distributions, and support remote trials |
| Pydantic | Validate the public interfaces and configuration models |
| Chroma 1.5.9 | Exercise the local database contract in controlled checks |
| pytest | Run authoring, packaging, and verifier regression checks |

The task authoring project pins Harbor, Pydantic, and Chroma; the root project pins
pytest. The root lock records all resolved dependencies, including Modal and SDKs
required by Harbor. GPU inference packages are supplied by the task image.

```bash
uv sync --frozen
source .venv/bin/activate
uv run pytest -q
```

`uv run` selects the project environment even when the shell is not activated.

## Build the first task

Run these commands from the repository root. Data preparation requires a local
HERB checkout at the revision recorded in the task README.

```bash
uv run python authoring/swe-m2-ai-engineer/knowledge-work-assistant/scripts/prepare_data.py --herb /path/to/HERB
uv run pytest -q
uv run python authoring/swe-m2-ai-engineer/knowledge-work-assistant/scripts/package_step.py
```

The archive is written to the task's `dist/knowledge-work-assistant-step1.tar.gz`.
Extract it and provide the enclosed task directory to Oddish or Harbor. Generated
corpora, private evaluation inputs, archives, credentials, and run logs are excluded
from Git; preparing the data is required before packaging. Image builds download
pinned dependencies and model weights before network-restricted evaluation begins.

## Repository conventions

Task code stays under `tasks/<family>/<task>/`. Each step has an `instruction.md`; runnable steps add their verifier and environment inputs using Harbor's layout. The verifier's `verify()` function orchestrates explicit `test_...` checks and distinguishes candidate failure from evaluation failure.

Read [agents/rules.md](agents/rules.md) before contributing. Repository skills cover [task design](agents/skills/declarative-task-design/SKILL.md), [Harbor structure](agents/skills/harbor-task-structure/SKILL.md), [instruction writing](agents/skills/instruction-writing/SKILL.md), and [typed functions and docstrings](agents/skills/funtional-programmer/SKILL.md).

HERB data and its copied rubric retain their CC BY-NC 4.0 license. Prepared task bundles include the source license and attribution.
