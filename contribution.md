# Contributing to SWE-Marathon 2
# 
## What's SWE-Marathon 2
SWE-Marathon 2 evaluates coding agents over successive rounds of software
development. An agent builds something, then adapts it as requirements change.
We want tasks where later work depends on earlier decisions and where we can
check that the resulting software works.

## Taxonomy
You can contribute a task idea, develop an existing task, build its environment
or verifier, implement a reference solution, or review another contributor's
work. Design drafts are welcome. State what is ready and what still needs work.

## Pick a task and coordinate

Open an issue or join an existing discussion before substantial implementation.
Describe what the agent will build, why the work is difficult, how the requirements
could evolve, and what evidence would establish success. Include any data,
licenses, external services, or unusual compute needs that affect feasibility.

Name the part you intend to own so others can help without duplicating it. Keep
each task PR focused on one task, including its matching authoring directory.
Several contributors can work on the same task through separate PRs for agreed
parts. Link those PRs and identify dependencies between them.

Start with one concrete step. Sketch later requests when they help explain the
task, but create their runtime files only when you are implementing them. A
later step should introduce a meaningful change to the same application, with
clear expectations about which earlier behavior must survive.

## Read the contracts

Read [agents/rules.md](agents/rules.md) before editing. The repository carries
the task-building guidance alongside the code:

| Work | Guidance |
| --- | --- |
| Define requirements and evidence | [Declarative task design](agents/skills/declarative-task-design/SKILL.md) |
| Organize environments, steps, verifiers, and solutions | [Harbor task structure](agents/skills/harbor-task-structure/SKILL.md) |
| Write a candidate's instructions | [Instruction writing](agents/skills/instruction-writing/SKILL.md) |
| Implement functions and tests | [Function contracts](agents/skills/funtional-programmer/SKILL.md) |

If you use a coding agent, have it read [AGENTS.md](AGENTS.md) and the relevant
skills before starting. Some current writing instructions reference files on the
maintainer's machine. Flag those missing references when working from another
checkout; they need repository-local equivalents before onboarding is fully
self-contained.

## Organize the contribution

Runnable v2 tasks use this layout. Add only the files your task needs.

```text
tasks/<family>/<task>/
├── task.toml
├── environment/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── uv.lock
├── tests/
│   └── common/                  # Optional shared verifier code
└── steps/
    └── 01-<step>/
        ├── instruction.md
        ├── workdir/             # Optional inputs introduced at this step
        ├── tests/
        │   ├── test.sh
        │   └── verify.py
        └── solution/
            ├── solve.sh
            ├── oracle.py
            └── src/

authoring/<family>/<task>/
├── README.md                    # Design, evaluation, and reproduction notes
├── checks/                      # Author checks, outside the task artifact
├── scripts/                     # Preparation and packaging
└── dist/                        # Generated bundles; ignored by Git
```

Declare implemented steps in execution order in `task.toml`, using names that
match their directories. Use `abundant/swe-m2_<domain>_<task>` for `[task].name`;
for example, `abundant/swe-m2_ai-engineering_knowledge-work-assistant`. The slash
after the organization is the only slash in that name.

Keep preparation tools, local checks, author documentation, and author dependencies
under `authoring/`. A packaged task contains only the configuration, environment
inputs, instructions, and verifier or solution files the runner needs. Keep
generated data, archives, credentials, caches, and run logs out of version control.
Retain required licenses and attribution when redistributing data or code.

## Write the task before its checks

Explain the work as you would to a capable colleague. State what the agent needs
to build or change, the available inputs, and the required deliverables. Use
absolute runtime paths such as `/app/output.json`. Make consequential interfaces
explicit: input and output types, defaults, state changes, errors, and resource
limits. Leave implementation choices open unless the task requires a particular
method.

For each later step, say which earlier requirements remain and which are replaced.
New inputs belong in that step's `workdir/`; setup must preserve the agent's
existing application. Avoid a sequence of unrelated exercises that merely share
a directory.

Map every requirement to a scenario, observable evidence, and a pass condition in
the author notes. Resolve ambiguities that would change what counts as success
before implementing the dependent checks. The reference solution must satisfy
the task as written; its internal design does not add requirements.

Keep final-evaluation details out of `instruction.md` and every candidate-visible
file, including starter code, resource READMEs, comments, and help text. State
required behavior and deliverable paths directly. Private cases may test disclosed
behavior, but cannot introduce undisclosed restrictions. Grading procedures,
private cases, judge configuration, scoring formulas, and artifact-transfer
mechanics belong in author-only documentation and verifier configuration.

Review the prose with Humanizer as required by the writing instructions. Preserve
exact requirements while removing filler and unnecessary implementation advice.

## Build an environment and verifier that can be trusted

Use explicit Dockerfile copies for public inputs. Keep private tests, answers,
oracle source, and judge credentials out of the agent image. Provision dependencies
and model weights before restricted execution begins. Choose CPU, memory, storage,
GPU, and time budgets from the task's needs and measurements.

Follow the Harbor skill's Python contracts: `verify(context)` orchestrates an
explicit registry of named `test_...` functions and returns a `VerificationResult`.
Each check produces a requirement identifier, status, explanation, and relevant
measurements. Put executable assertions in `test_*.py` modules. Keep shell entry
points thin, and use explicit parameter and return types with useful docstrings.

Exercise the application's declared public interface. Use deterministic checks
for behavior and structure, and calibrated rubrics where meaning or quality needs
judgment. Continue independent checks after a failure. Record dependent checks as
skipped with a reason; never silently drop them or count them as passes.

Evaluate in a fresh, separate verifier container using only declared submission
artifacts. Configure its resources and network policy explicitly. Protect private
inputs, judge credentials, and reward files from the submitted application during
execution. Prefer isolation and capability restrictions to source-code regexes
that reject harmless text and miss equivalent evasions. Test the boundary and
document what it actually prevents.

A candidate failure produces a check result. A broken fixture, unavailable judge,
or invalid credential is an evaluation error. Preserve diagnostics, fail the
evaluation, and leave no valid reward file, including a stale one from an earlier
run. Verify that the selected Harbor version reports this distinction correctly.

### Scoring and compatibility with v1

The [v1 contribution guide](https://github.com/abundant-ai/swe-marathon/blob/main/CONTRIBUTING.md)
requires binary `reward.txt` and a normalized `partial_score` in `metrics.json`.
The current v2 knowledge-assistant task declares continuous reward. Preserve the
contract of the task you are changing; don't silently convert between these
formats or introduce a success threshold that the task never specified.

Document the reward mapping, component weights, normalization, missing or skipped
case treatment, and any threshold in author-only material. Keep weighted scoring
independent of the number of assertions, with a fixed denominator when checks
fail or skip. Record diagnostic measurements alongside the final result.

For work submitted through v1's existing checks, retain its required substantive
`difficulty_explanation`, `solution_explanation`, and `verification_explanation`
metadata and its reward/metrics format. For v2, explain the same rationale in the
task's author notes and follow the declared v2 configuration. Compatibility with
v1 CI needs validation before applying those workflows to multi-step tasks.

## Validate the contribution

Use Python 3.13 and the repository-root `uv` project for local authoring:

```bash
uv sync --frozen
uv run harbor --version
uv run pytest -q authoring/swe-m2-ai-engineer/knowledge-work-assistant/checks
```

The test command above exercises the existing knowledge-assistant author checks;
use your task's checks when adding another task. The root dependencies currently
include a private Titans Git dependency, so setup requires access to that repository.
Task data preparation and cloud credentials have their own prerequisites; document
them in the task's author README. Use the locked Harbor version for v2 work because
its multi-step and separate-verifier behavior matters.

Before treating an implemented task as ready, collect evidence for the following:

- The packaged or extracted artifact builds and runs without depending on files
  elsewhere in the author's checkout.
- A readable reference solution runs from a fresh environment and satisfies the
  declared criteria. Keep source files in `solution/`; avoid patch-only solutions.
  Later step oracles build on the previous application's state.
- A no-op submission receives the expected result. Explain any legitimate credit
  it receives from starter behavior or earlier steps.
- Targeted broken submissions fail the relevant checks, while legitimate alternative
  implementations pass. Include regression checks for inherited requirements.
- The real launcher and full implemented step sequence work, including new inputs,
  persisted application state, and transfer into the separate verifier.
- Isolation checks cover private inputs, result-file access, undeclared development
  state, and allowed or blocked network destinations.

For judged tasks, calibrate with correct, wrong, partial, unsupported, and
instruction-injection examples. Pin the judge and rubric, and record their versions.
A mocked judge establishes orchestration behavior; answer quality needs live
evaluation. A failing baseline alone does not establish solvability or difficulty.

Report local checks, controlled application/model checks, live judge calls, and
end-to-end runs separately. Include commands, relevant configuration, results, and
links to durable logs where available. Mark anything you could not run as unverified.
Discuss paid cloud trials with a maintainer before launching them.

## Open the PR

Include the task's purpose, the steps covered, and the design decisions a reviewer
needs to assess. Link the issue and related work. Summarize validation with the
commands and results, including oracle and no-op behavior, known limitations, and
any strong-model attempts. A draft PR can leave implementation or calibration
unfinished if it identifies that work clearly.

Reviewers should be able to trace each check back to a disclosed requirement,
reproduce the submitted evidence, and distinguish a candidate failure from a
problem with evaluation. If changing an existing task, explain how the change
affects earlier behavior and comparability with previous results.

The v1 repository documents static checks, automated PR comments, and maintainer
commands such as `/validate`, `/review`, `/run`, and `/cheat`. This v2 checkout does
not currently include those workflows or `ci_checks/`. Use the local validation
above and confirm multi-step support before relying on v1 automation for a v2 PR.
