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
| [Knowledge work assistant](tasks/swe-m2-ai-engineer/knowledge-work-assistant/README.md) | [1. Build RAG](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/01-build-rag/instruction.md) | Environment, verifier, data preparation, and packaging implemented; controlled checks validated | Build an oracle, run all 238 quality questions with the fixed judge, and calibrate the 80% target |
| Knowledge work assistant | [2. Expand the corpus](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/02-expand-corpus/instruction.md) | Draft instruction | Define additional data and evaluation splits; implement and calibrate the 95% target |
| Knowledge work assistant | [3. Harden ingestion](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/03-harden-ingestion/instruction.md) | Draft instruction | Define the workload and failure scenarios; build the environment, verifier, and oracle |
| Knowledge work assistant | [4. Optimize retrieval](tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/04-optimize-retrieval/instruction.md) | Draft instruction | Define latency and quality criteria; build the environment, verifier, and oracle |
| [Titans training](tasks/swe-m2-ai-research/titans-training/design.md) | Improve a training baseline | Source inspection and initial design | Define data, compute, and success criteria; measure a baseline and build the environment and verifier |
| [London battle royale](tasks/swe-m2-game-developer/london-battle-royale/steps/01-build-game/instruction.md) | 1. Build the game | Instruction, ten component briefs, and reference images prepared | Implement the runnable environment and evaluation; validate a complete game |

Only knowledge-assistant step 1 is enabled in a `task.toml`. Later instructions are design drafts.

## Knowledge-assistant foundation

Orange is a RAG assistant over a fictional company's documents, conversations, project history, and directory records. The agent defines typed ingestion, retrieval, and generation interfaces, implements a CLI, and creates its own development questions and reference answers.

The development environment contains a uniform 4% sample of HERB: 1,570 of 39,268 source records. Evaluation rebuilds the index from the full sanitized corpus and asks 238 withheld content questions. HERB is public; withholding its questions from the container does not establish freedom from pretraining contamination.

Jina v5 omni small runs locally on the container's GPU using bundled, pinned weights. The available generation model is `gpt-6-luna`. The verifier uses HERB's answer-rating prompt with the fixed judge `gpt-5.4-2026-03-05`. The 80% target is a mean partial-credit answer rating, not the fraction of questions answered perfectly.

Every evaluation starts in a fresh container and restores the declared `/app` artifacts. The verifier allows HTTPS only to `api.openai.com`; Jina needs no network connection. Modal's domain allowlist still permits DNS and does not restrict individual API paths. Private references, judge credentials, and reward files remain outside the submitted application's control.

### What has been validated

- All 25 local author checks pass, covering verifier orchestration, targeted broken submissions, scoring, packaging, and network configuration.
- A controlled Linux application and judge passed all 11 registered requirement checks. This establishes verifier behavior, not RAG answer quality.
- Local Jina inference produced a normalized 1,024-dimensional embedding on a Modal L4 with all networking blocked.
- A Harbor boundary control completed on A10 with distinct development and verifier containers, correct artifact transfer, local GPU embeddings, and blocked non-approved destinations. The empty submission correctly received reward zero with no evaluation exceptions. The A10 control followed stalled L4 startup; the delivered configuration retains L4.
- Live judge examples scored correct, wrong, partial, unsupported-extra-claims, and prompt-injection answers at 100, 0, 65, 82, and 0. The **82 for an answer with unsupported additions** shows that the inherited rubric remains permissive.

A full 238-question run with the final judge and a working oracle remains unverified. Coding-harness trials are handled by Oddish. See the [task README](tasks/swe-m2-ai-engineer/knowledge-work-assistant/README.md) for exact contracts, credentials, validation details, and limitations.

## Build the first task

Use `uv` from the task directory. Data preparation requires a local HERB checkout at the revision recorded in the task README.

```bash
cd tasks/swe-m2-ai-engineer/knowledge-work-assistant
uv sync --frozen
uv run python scripts/prepare_data.py --herb /path/to/HERB
uv run pytest checks -q
uv run python scripts/package_step.py
```

The archive is written to `dist/knowledge-work-assistant-step1.tar.gz`. Extract it and provide the enclosed task directory to Oddish or Harbor. Generated corpora, private evaluation inputs, archives, credentials, and run logs are excluded from Git; preparing the data is required before packaging. Image builds download pinned dependencies and model weights before network-restricted evaluation begins.

## Repository conventions

Task code stays under `tasks/<family>/<task>/`. Each step has an `instruction.md`; runnable steps add their verifier and environment inputs using Harbor's layout. The verifier's `verify()` function orchestrates explicit `test_...` checks and distinguishes candidate failure from evaluation failure.

Read [agents/rules.md](agents/rules.md) before contributing. Repository skills cover [task design](agents/skills/declarative-task-design/SKILL.md), [Harbor structure](agents/skills/harbor-task-structure/SKILL.md), [instruction writing](agents/skills/instruction-writing/SKILL.md), and [typed functions and docstrings](agents/skills/funtional-programmer/SKILL.md).

HERB data and its copied rubric retain their CC BY-NC 4.0 license. Prepared task bundles include the source license and attribution.
