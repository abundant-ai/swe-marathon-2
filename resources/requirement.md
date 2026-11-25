# Repository guidance and v2 task requirements

SWE-Marathon v2 should contain ambitious tasks that produce useful engineering,
research, or domain results. Optimize task design for novelty, verifiability,
realism, and difficulty. At initial design, a rough, reasoned idea of how the
task could be solved is enough. Finding an oracle and demonstrating solvability
can follow in later versions; do not reduce ambition just to fit a solution we
already know how to build.

## Task design dimensions

Evaluate these dimensions separately in each task's author README. For each,
record the design argument, available evidence, uncertainties, and next useful
validation. These assess the quality of the benchmark task; they are separate
from the dimensions and reward used to assess a candidate's submission. Do not
collapse them into an arbitrary weighted task-quality score.

| Dimension | Questions to answer in the initial design |
| --- | --- |
| Novelty | What capability or workflow does this task add? How does it differ from the closest public benchmark tasks, SWE-Marathon v1, and tasks already designed in this repository? |
| Verifiability | What observable evidence establishes success or partial progress? Can programmatic checks, calibrated LLM judges, or a combination compute a meaningful result without requiring a known full solution? |
| Realism | Who would need this result, and why? Do the inputs, tools, constraints, decisions, feedback, and deliverables resemble work an engineer or researcher would actually do? |
| Difficulty | Which capabilities make the work hard for an agent? Where must it reason, maintain state, integrate results, or recover from a wrong decision? |
| Initial feasibility | What rough approach could plausibly solve the task with the available inputs and resources? What remains uncertain? A completed oracle or successful rollout is not required at this stage. |

### Novelty within and beyond the task collection

Compare concrete tasks and their sources, not just benchmark names. Consider
Deep SWE, Frontier SWE, Multi-Step SWE, SWE-Marathon v1, and other relevant public
work when identifying the closest comparisons. Also compare the closest existing
and proposed tasks under `tasks/`. Link external sources and internal task paths;
record overlap as well as differences in workflow, deliverable, constraints,
reasoning demands, or assessment. Explain why each difference matters. Renaming,
enlarging, or changing the domain label of an existing task is insufficient.
Mark missing comparisons as unverified; do not claim exhaustive novelty.

### Realistic sources of difficulty

Explain the task's expected failure points and how they arise from useful work.
Difficulty can come from any combination of the following, and this list is open
to new kinds of work:

- Long-horizon coherence: maintaining context, state, and design consistency
  across hundreds or thousands of consequential decisions.
- Multi-turn dependencies: carrying earlier work forward while integrating new
  requests, user feedback, or information initially held only by the user.
- Spatial reasoning: understanding and manipulating 3D geometry, scenes,
  physical relationships, or motion.
- Frontier research: forming hypotheses, designing experiments, interpreting
  uncertain results, and revising an approach to a difficult research problem.
- Integration and diagnosis: coordinating interacting systems, tracing faults,
  managing resource tradeoffs, and recovering without breaking earlier behavior.

Tasks need not use every source of difficulty. For dynamic user interactions,
explain in author notes what the user knows, when information becomes available,
and how follow-ups can change scope or difficulty. Changes should follow the
workflow and become explicit when introduced. Assess the requirements in force
at that turn; private user information cannot become an undisclosed grading rule.
Record the interaction and resulting scope so trial results can be interpreted.

Retain the workload target of at least five days of agent execution, aiming for
a week across all turns. Count necessary experiments, justify the work, and refine
initial estimates through trials. Forced waiting, busywork, and infrastructure
friction do not establish difficulty. Accept faster valid solutions. Multi-turn
development is encouraged; single-turn tasks must meet the same professional,
difficulty, and workload bar, without manufactured dependencies.

### Evidence as the task develops

At proposal time, document the dimensions above, an observable verification plan,
and a rough solution hypothesis with its assumptions. A missing oracle or an
unsuccessful baseline is not grounds to reject an otherwise promising design.
Known contradictions, unavailable essential inputs, or a success condition with
no credible assessment method still need resolution.

During implementation and later versions, test metric behavior, calibrate judges,
inspect failure modes, and refine resource estimates and the solution hypothesis.
Keep feasibility evidence separate from verifier reliability: a task can be hard
to solve while its submitted results are straightforward to assess. Before
execution, satisfy the runtime, isolation, and judge requirements below. Report
oracle validation as pending until demonstrated; never turn a provisional design
review into a claim that the task has been solved.

## Development scope

### Static tasks

Keep tasks with fixed briefs under `tasks/static/<category>/<task>/`. A single
step uses `instruction.md`, `tests/`, and any `solution/` at the task root.
Use root agent and verifier settings in `task.toml` and omit `[[steps]]`.
For two or more scripted steps, move each brief, verifier and solution into
`steps/<step>/` and declare the steps in execution order.

### User-sim tasks

Keep tasks with a simulated user under `tasks/usersim/<task>/`. Configure the
user in the task-root `user_agent.yaml`. One run of the opening brief can
include many exchanges with that user. Use the single-step layout for that
conversation. Use step directories when the task declares multiple Harbor steps.

### Shared development rules

Preserve candidate briefs unless the user asks to revise them. References to runtime files in an instruction describe the
intended environment; they do not mean that environment already exists.

Create implementation files when the user asks for implementation. A request to
discuss a contract or design a verifier is permission to do that design work.
It does not call for scaffolding, downloading a corpus, or launching a GPU run.
Existing authorization in the conversation still counts; do not ask for it again.

Keep each task in its own directory, including its README, maintained
checks, preparation and packaging scripts, and development dependencies. Put
shared resources in task-root `common/`; each image includes only the files it
needs. Store scratch work, experiment results, and generated bundles in the task's
Git-ignored `experiment/` directory. Exclude development tools, the task README,
and experiments from runtime packages and candidate images. Do not create
utilities shared across a task category. Add a shared abstraction only when the
user requests one and there is a concrete use for it. Create future steps when
requested, without placeholder implementations or unused directories.

Task-root `checks/` and `scripts/` are optional development folders for local
testing, data preparation, and packaging. They may be tracked and run locally;
they are not required folders for every task. Never include either folder or its
contents in an uploaded runtime bundle, Docker build context, or task image.
No agent or verifier Dockerfile may `COPY`, `ADD`, or mount them, including through
a broad parent-directory copy or an intermediate build stage. Do not mount them
into runtime containers. Run preparation scripts locally and stage only
the required generated runtime inputs. Keep runtime code in the appropriate
runtime directory. This restriction applies to task-root `checks/` and `scripts/`,
not the runtime `tests/` beside the brief, including its nested
`verifier/checks/` modules.

Every task, including a draft, must have a task-root `README.md` with a
`Development log` section. Use dated entries (`### YYYY-MM-DD`) to record changes,
reasoning, validation performed and its results, and remaining work. Preserve
earlier entries, distinguish plans from executed work, and do not invent dates
for historical work. Keep durable findings in the README even when detailed
outputs remain local in `experiment/`.

Keep repository guidance in `resources/requirement.md` and skills in
`resources/skills/`. Candidate-facing task instructions stay in the step directory.
Do not commit or stage changes until the user asks.

## Task domains

These are starting points for proposals, not validated tasks or a closed taxonomy.

| Domain | Possible work |
| --- | --- |
| AI applications | Knowledge assistants, voice agents, multimodal ingestion, retrieval and latency improvements. |
| AI research | Memory mechanisms, text-to-LoRA systems, architecture search, iterative training experiments. |
| Games | Multiplayer systems, team coordination, physics, and complete playable experiences. |
| Scientific computing | Transportation models, PDE solvers, inverse problems, computational chemistry. |
| Software engineering | Rebuild substantial software, improve reliability, or perform controlled security engineering. |
| Spatial systems | Scene reconstruction, CAD, motion planning, geospatial forecasting, warehouse fleets. |
| Data engineering | Data platforms, backfills, schema evolution, and recovery from corrupt inputs. |
| Compilers and systems | Toolchains, runtimes, storage, and distributed systems under faults. |

## Instructions and layout

Read the current step's `instruction.md` and the user's latest decisions before
designing its environment or verifier. Derive the environment, verifier, reward,
and oracle from the requested behavior. Existing code, reference solutions, and
earlier drafts cannot silently add requirements. Follow the
[contribution guide](../CONTRIBUTING.md).

Make consequential interfaces explicit: inputs, outputs, types, defaults, state
changes, errors, and resource limits. When a decision would change what counts as
success, surface it before implementing the dependent check. Continue independent
work while it is unresolved. Routine implementation choices do not need approval.

Keep each enforced requirement visible to the candidate. Private cases can test
disclosed behavior, but cannot introduce new restrictions. For successive steps,
identify which earlier requirements still apply and which the new request replaces.

Keep final-evaluation procedures and private configuration outside every
candidate-visible file, including `instruction.md` and the task environment.
Describe the requested work, public interfaces, and deliverables directly. The
candidate's own development experiments can remain part of the assignment.

This repository has no version directory under `tasks/`. Each declared step uses
the [Harbor layout and contracts](skills/multi-turn-task-structure/SKILL.md), including
`tests/test.sh` and `tests/verify.py`. Optional `verifier/` modules live inside that
brief's `tests/` directory. For tasks with a packager, run it before preflight.

Keep packaged task folders limited to runtime artifacts: task configuration,
environment build inputs, step instructions, and verifier or solution files needed
by the runner. Exclude authoring scripts, local checks, and author dependency files.
Generate Oddish upload code when needed and keep it outside the task artifact.

For packaged releases, use `abundant/swe-m2_<domain>_<task>` for `[task].name`. A directly uploaded task uses `abundant/<directory-name>`. A packaged example follows.

```toml
[task]
name = "abundant/swe-m2_ai-engineering_knowledge-work-assistant"
```

Keep only the slash after the organization; join later components with underscores
to fit Harbor's `org/name` contract. Repository directory names remain unchanged.
Include a task-specific description and actual author names and emails. Only
implemented steps belong in `task.toml`; proposals can contain instructions and
design notes.

## Verification and solvability

Define how each metric can be computed from available evidence before requiring
a full solution. Depending on the task, evidence may include behavioral checks,
invariants, independently derived references, measured outcomes, or calibrated
LLM judgments against an explicit rubric. Explain where expected values or
trusted judgments come from and their limits. An oracle's output is not the only
possible source of evidence, and agreement with one implementation is not a
general definition of correctness.

For open-ended research or optimization, distinguish measuring a submitted
result from knowing the best achievable result. Define useful partial progress
and any success threshold without assuming an unknown optimum. Specify metric
inputs, units, aggregation, and treatment of missing or invalid evidence. Check
whether meaningful defects lower the result and legitimate alternatives receive
appropriate credit. Assess judge disagreement and run-to-run variation where
relevant; a clean formula alone does not establish reliable verification.

Break verification into dimensions and assess each independently before applying
the reward formula. Every evaluation, retry, and regrade starts in a fresh
separate container with only declared artifacts. Protect checks, private answers,
credentials, and reward files from submitted code. Exercise the boundary with
adversarial attempts and record its limitations.

The author README must explain the task design dimensions, verification coverage,
and the derivation and validation of expected answers or judgments. Initially,
describe a rough plausible solution strategy and its unresolved assumptions;
do not require a worked-out algorithm, completed implementation, or successful
trial. Develop stronger solvability evidence during iteration. An oracle may
arrive in a later version. Mark its validation as pending until a legitimate
implementation has passed the real verifier in a fresh container. A rollout can
provide the oracle: record its provenance, review its behavior, and describe any
adaptations. High reward alone does not demonstrate solvability.

## LLM judges

Use Pydantic AI with an explicit prompt and structured Pydantic output models.
Before an Oddish run, calibrate each judge locally against golden examples with
trusted expected assessments. Include correct, wrong, partial, unsupported, and
instruction-injection cases where applicable. Record model, prompt, rubric, and
schema versions; expected and observed ratings; disagreements; and the decision
to accept or revise the judge. Repeat calibration after material changes.

Provide retrievable Logfire traces for calibration and evaluation named
`swem2.<taskname>.test_accuracy.jugde.<name>`, preserving the `jugde` spelling.
During authoring, explicitly pending calibration and trace validation are
acceptable. Complete both before Oddish execution. Mocked judges establish
orchestration behavior only. Keep all evaluation details author-only.

## Reward justification

State the published formula in the task’s README and the PR.
Define components, weights, normalization, denominators, thresholds, mandatory
conditions, missing or skipped cases, and aggregation across turns. Explain why
the result measures the requested outcome. Link each term to its implementation
and boundary tests. Use the current formula from the
[knowledge-assistant notes](../tasks/static/app_building/knowledge-work-assistant/README.md#reward-formula)
as an example of task-specific documentation, not as universal weights.

Keep denominators fixed when candidate checks fail or skip. Evaluation errors
produce no valid reward. Binary and continuous rewards are both allowed when
justified. Keep formulas and grading procedures out of candidate-visible files.

## Hackability assessment

Every task author README needs a `Hackability assessment` section. Cover ways
to earn credit without meeting the instruction, private-answer or credential
access, judge manipulation where applicable, and result tampering. For each
finding record the attack and impact, affected boundary, inspected or executed
evidence, mitigation, residual risk, and next validation.

| Severity | Meaning |
| --- | --- |
| 🟢 GREEN / LOW | Tests support low residual risk within the assessed scope. |
| 🟡 YELLOW / MEDIUM | A limited or plausible weakness needs mitigation or further validation. |
| 🔴 RED / HIGH | An exploit defeats assessment integrity or compromises protected data or systems. |
| 🟡 YELLOW / UNASSESSED | Evidence is missing; this does not establish low risk. |

Summarize the highest unresolved severity and identify unassessed boundaries.
A complete report can document a failed boundary; the report does not make the
boundary acceptable. Keep the assessment author-only.

## Skills to use

- Use [multi-turn-task-structure](skills/multi-turn-task-structure/SKILL.md) when organizing
  environments, step inputs, verifier and oracle files, or their Python entry points.
- Use [instruction-writing](skills/instruction-writing/SKILL.md) when drafting or
  editing a step instruction.
- Use [declarative-task-design](skills/declarative-task-design/SKILL.md) when
  initially designing a task, assessing its design dimensions, or changing its
  acceptance criteria, rubrics, or verifiers.
- Use [task-rating](skills/task-rating/SKILL.md) immediately after a completed
  Harbor review to assess its findings and record task-quality metadata.
- Use [funtional-programmer](skills/funtional-programmer/SKILL.md) when creating or
  changing functions, including tests and helpers.
- Use [judge-prompt-writing](skills/judge-prompt-writing/SKILL.md) when writing or
  revising LLM judge prompts, structured outputs, or rendered evaluation examples.
- Use [Humanizer](skills/humanizer/SKILL.md) when drafting or editing prose,
  including task instructions and author documentation.

## Implementation and evidence

Use the repository-root `pyproject.toml`, `uv.lock`, and `.venv` for local authoring,
testing, and packaging. Follow the [shared setup guide](../README.md#local-setup-and-checks)
for installation and optional tools; keep install commands there instead of
repeating them in task notes. Run project commands with `uv run --frozen` from
the repository root. Keep
container runtime dependencies in the task's `environment/pyproject.toml`. Keep
generated datasets, environments, caches, credentials, and run artifacts out of
version control. Add dependency files and ignore rules when they become necessary.

Validate the behavior changed by the work. Report local checks, controlled-model
checks, live judge calls, and end-to-end runs separately. A mocked judge does not
establish answer quality; a failing baseline does not establish that the task is
solvable. Mark unavailable validation as unverified.

## Review and execution

Use [task-implementation.toml](task-implementation.toml) for v2 semantic review.
Its first five criteria rate novelty, verifiability, realism, difficulty, and
initial feasibility independently on a 1–5 scale, using dimension-specific
anchors. Record the review stage, confidence, evidence, rationale, and unresolved
gaps for each rating. Proposal ratings assess the design argument; implementation
and trial evidence can revise them later. Initial feasibility rates the rough
solution hypothesis, not possession of an oracle. Do not average these ratings
or use them as candidate reward.

The installed Harbor report supports an `outcome` and an `explanation` per
criterion. The rubric requests `Rating: N/5` in the explanation; it does not add
a native numeric field or mechanically validate the rating text. Ratings 3–5
map to `pass`, and 1–2 to `fail`, for that dimension. Insufficient evidence is
`Rating: UNASSESSED` with `not_applicable` and an explicit evidence gap; the
dimension still applies and has not passed. Report confidence separately so a
promising proposal is not assigned a low quality rating simply for lacking trials.
Check the returned report for all five ratings and their supporting evidence.

After `harbor check` completes, follow the
[task-rating skill](skills/task-rating/SKILL.md). Reconcile its ratings with the
evidence and store the five supported integer scores, or `unassessed`, under
`[metadata.task_rating.scores]` in the task's `task.toml`. Keep confidence, review
stage, report reference, timestamp, and provenance alongside them, following the
skill's schema. Preserve unrelated metadata and configuration. Record rationale
and gaps in the task README, and mark ratings stale after material design changes.
Drafts without runtime configuration keep their assessment in the README until
`task.toml` is needed. Never invent ratings after a failed or missing review.
This is a required agent follow-up, not a callback installed inside Harbor.

The remaining criteria check implementation contracts, security, packaging,
and validation evidence. Keep these findings separate from task-design ratings;
high design ratings cannot establish runtime readiness. The rubric contains no
v1 reward or oracle requirements.

`harbor check` performs a model-based file review and needs the credentials for
the chosen model. Inspect the installed command's options before running it:

```bash
uv run --frozen harbor check --help
uv run --frozen harbor check -r resources/task-implementation.toml tasks/static/app_building/knowledge-work-assistant
```

Read the task README alongside the result. A file review may not see
those notes, PR discussion, or remote trial evidence. Report unavailable evidence
as a gap. The rubric can guide proposals before an oracle is available; a file
review pass does not establish release readiness.

The [commit hook](CI.md) runs Ruff.
[Oddish](ODDISH.md) handles package preflight, remote trials, QA, and artifacts.
Report their results separately and tie evidence to the evaluated revision.
