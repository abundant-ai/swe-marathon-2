---
name: multi-turn-task-structure
description: Use when creating or reorganizing a task, adding turns, or packaging environments, shared resources, verifiers, and oracles. Keep each task self-contained with a dated development README, selectively copied common resources, and ignored local experiments. Also applies to single-turn tasks.
---

# Multi-turn task structure

Read the current instruction and [v2 requirements](../../requirement.md) before
building runtime files. Use `harbor check` during ideation and proposal, and
[Oddish](../../ODDISH.md) for package preflight, uploads, execution, QA, and
artifacts. Follow the [review guidance](../../requirement.md#review-and-execution)
for the evidence each stage supplies.

After a completed Harbor review, follow [task-rating](../task-rating/SKILL.md) to
record supported task-quality scores under `[metadata.task_rating]`. Preserve
this metadata when reorganizing the task; mark it stale after material changes.
Keep runner configuration and its ratings outside candidate-visible files.

## Layout and packaging

For static tasks, use `tasks/static/<category>/<task>/`. For tasks that run a
user agent, use `tasks/usersim/<task>/` and keep `user_agent.yaml` at the root.

With one implemented step, put `instruction.md`, `tests/`, and any `solution/`
beside `task.toml`. Omit `[[steps]]` and set timeouts and artifact paths at
the task level. Several messages between the solver and user agent can belong
to this one step.

For two or more scripted steps, use the following layout.

```text
<task-root>/
├── README.md                        # Task rationale and dated development log
├── task.toml                        # Add when a step is implemented
├── common/                          # Shared resources selected by each image
├── environment/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   └── resources/                   # Public runtime inputs, when needed
├── checks/                          # Optional development tests; never ship
├── scripts/                         # Optional development tooling; never ship
├── experiment/                      # Local experiments and outputs; Git-ignored
└── steps/<step>/
    ├── instruction.md
    ├── workdir/                     # Optional inputs introduced at this step
    ├── tests/
    │   ├── test.sh
    │   ├── verify.py                # Context, execution, and report entry point
    │   ├── verifier/                # Supporting modules, when needed
    │   │   ├── __init__.py
    │   │   ├── contracts.py
    │   │   ├── registry.py
    │   │   ├── runner.py
    │   │   ├── scoring.py
    │   │   ├── checks/              # Requirement checks in test_*.py
    │   │   ├── judging/             # Prompts, schemas, and judge clients
    │   │   └── application/         # Candidate-process adapters
    │   ├── Dockerfile              # Optional dedicated verifier image
    │   └── private/                # Private inputs, when needed
    └── solution/                   # Add when an oracle is available
        ├── solve.sh
        └── oracle.py
```

Keep each task's source and development material together. Create only the files
needed; a design-only task still needs its README but does not need empty runtime
folders. Maintained checks, preparation scripts, and development dependency files
can live at the task root. Select runtime files explicitly when packaging so
these tools and the task README stay outside the uploaded runtime artifact.
A bundle manifest is optional.

Task-root `checks/` and `scripts/` are optional tools for local task development
and testing. They may be tracked and run locally. Never put either folder or its
contents in uploaded runtime bundles, Docker build contexts, or agent or verifier
images. Dockerfiles must not `COPY`, `ADD`, or mount them, even through a broad
parent-directory copy or an intermediate build stage. Runtime containers must
not mount them either. Run preparation scripts locally, then stage only
their required generated runtime inputs. Put any code needed at runtime in the
appropriate runtime directory. The runtime `tests/` beside the brief and its nested
`verifier/checks/` are runtime code and are not the task-root development suite.

Create `experiment/` inside the task when running local experiments. Store scratch
scripts, generated bundles, trial outputs, calibration reports, and other local
results there. It must be Git-ignored and excluded from image builds and runtime
packages. Promote reproducible scripts and regression tests into maintained task
source when they become necessary to reproduce or validate the task. Local regression checks must not
depend on files available only in an ignored experiment directory.

## Record development progress

Every task, including a proposal or single-turn task, must have a task-root
`README.md`. Explain its purpose, current implementation, solution strategy,
verification, reward, and remaining uncertainties as applicable. Keep assessment
details outside candidate-visible files and image build inputs.

Maintain a `Development log` section with dated entries such as
`### 2026-11-17`. Record what changed, why, what was actually inspected or run,
the observed result, and the next unresolved work. Add entries as development
proceeds; preserve earlier entries and label later corrections. Do not invent
historical work or treat a planned test as executed evidence. Summarize durable
findings in the README even when detailed local outputs remain in `experiment/`.

## Share and package resources

For a multi-step task, declare the implemented steps in execution order in `task.toml`. Add later inputs through that step's `workdir/`, preserving
prior application state where the instruction requires it. Put resources shared
across steps or images in task-root `common/`. Organize public and verifier-only
resources separately so an image can select exactly what it needs.

Use `abundant/swe-m2_<domain>_<task>` for `[task].name`, with exactly one slash,
a task-specific description, and actual authors. Follow Oddish preflight for
packaged-directory naming and identity checks.

Build the agent image from `environment/Dockerfile`. For a dedicated verifier
image, the brief’s `tests/` directory is its Docker build context. Its Dockerfile must copy
the entry point, supporting modules, private inputs, and `test.sh` into the image.
A Dockerfile can selectively `COPY` or `ADD` resources only from its build
context. When Harbor uses a narrower context, have the packaging script stage
only the needed subset of `common/` into that context before building. For
example, the agent image may copy a shared public schema while the verifier
image also copies private fixtures. Never copy all of `common/` into the agent
image merely because both images need one shared file. Keep the README, task-root
`checks/` and `scripts/`, and `experiment/` out of both image inputs. Do not assume runtime overlays will
populate a dedicated verifier image.

Use the task's packaging script before preflight, upload, or execution. The
[knowledge-work assistant packager](../../../tasks/static/app_building/knowledge-work-assistant/scripts/package_step.py)
is an example for that task. Write generated bundles under `experiment/dist/`,
edit only maintained source files, and validate an extracted bundle from an
isolated process. Exclude `experiment/` from input selection to prevent a bundle
from including its own output.
Every component must resolve its dependencies inside its container without
access to the host checkout.

## Fixed Python interfaces

```python
def verify(context: VerificationContext) -> VerificationResult:
    """Run registered requirement checks and aggregate their results."""


def test_requirement(context: VerificationContext) -> CheckResult:
    """Return evidence and an outcome for one declared requirement."""


def oracle(context: OracleContext) -> None:
    """Produce the working submission in the application workspace."""
```

These signatures describe author interfaces; they are not completed functions
or interfaces the candidate must implement. Use typed contexts.
`VerificationContext` provides application paths, evaluation inputs, output
locations, and limits. `OracleContext` provides application paths and
candidate-accessible inputs, never private answers or judge credentials.

`VerificationResult` contains `passed: bool`, `checks: tuple[CheckResult, ...]`,
and `metrics: Mapping[str, float]`. Each `CheckResult` has a requirement identifier,
`status: Literal["passed", "failed", "skipped"]`, explanation, and measurements.
Define `passed` from mandatory task conditions; it does not force binary reward.

Register every check explicitly with its prerequisites and test registry
completeness. Continue independent checks after candidate failure and report
dependent skips with reasons. Put assertions, including subprocess probes, in
`test_*.py`; keep orchestration and aggregation in `verify()`. Keep `test.sh` and
`solve.sh` as thin adapters to Python entry points.

An oracle may arrive during iteration, including from a legitimate agent rollout.
Record its provenance and adaptations. It writes a working submission, raises on
failure, and never writes rewards. Run the real verifier afterward to establish
correctness. Until then, mark oracle validation pending in the author README.

Separate verification dimensions before implementing checks. For LLM assessment,
follow the [judge contract](../declarative-task-design/SKILL.md#llm-rubric-judges):
Pydantic AI, explicit prompts and output classes, local golden-data calibration
before an Oddish run, and retrievable Logfire traces. Use
[function contracts](../funtional-programmer/SKILL.md) for the implementation.

## Evaluation boundary

Set `verifier.environment_mode = "separate"`. Every evaluation, retry, and regrade
starts from trusted image inputs in a fresh container with only declared
submission artifacts. Specify verifier resources and network policy explicitly,
at creation and during grading. Preinstall needed dependencies and model weights.
Keep private tests, answers, oracle code, judge credentials, and reward files
inaccessible to submitted code during grading.

Candidate defects produce check results. Infrastructure and judge failures raise
a distinct evaluation error: retain diagnostics, exit unsuccessfully, and leave
no valid reward file, including stale files. Validate this behavior with the
selected runner. Use [task design](../declarative-task-design/SKILL.md) for boundary
tests, scoring, and the limits that must be documented.
