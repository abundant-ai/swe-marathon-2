---
name: harbor-task-structure
description: Organize Harbor multi-step tasks in this repository, including environment files, step inputs, Python verifier and oracle contracts, and shell adapters. Use when designing or implementing task packaging and entry points.
---

# Harbor task structure

Use Harbor's standard directory layout and shell entry points. Apply the Python
contracts below consistently across steps. These are repository conventions for
benchmark authors; they do not add interfaces to the submitted application.
Create only the files needed for the requested work. A design discussion or skill
update does not call for scaffolding the runtime.

## Allocate files by who uses them

```text
<task>/
├── task.toml
├── environment/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── starter/
│   ├── tools/
│   └── data/
├── tests/
│   └── common/
└── steps/
    └── <step>/
        ├── instruction.md
        ├── workdir/                 # Optional new inputs for this step
        │   └── setup.sh             # Optional setup after upload
        ├── tests/
        │   ├── test.sh
        │   ├── verify.py
        │   ├── test_requirements.py
        │   └── private/
        └── solution/
            ├── solve.sh
            ├── oracle.py
            └── src/
```

Declare steps in execution order in `task.toml`; names must match their folders.
The tree shows where files belong when needed, not a list of empty folders to create.

The agent Dockerfile installs dependencies with `uv` and explicitly copies initial
application files, tools, and public data from `environment/`. Keep private tests,
labels, oracle code, and judge credentials out of the agent image.

Put later inputs in the corresponding step's `workdir/`. Harbor uploads its contents
into the application working directory before the step and optionally runs
`setup.sh`. For example, with `/app` as the working directory, Orange's step-2
`workdir/data/new-documents.jsonl` becomes `/app/data/new-documents.jsonl`.
Earlier application state persists; avoid overwriting the agent's code with setup
files or reference implementations.

Keep shared grading code in task-level `tests/common/` and private cases beside
the tests that use them. Keep oracle code in each step's `solution/`. Each uploaded
component must resolve its dependencies inside the container without relying on
host repository paths. Keep shared definitions within the task and package them
explicitly where needed; do not introduce family-level utilities.

## Define the Python contracts

```python
def verify(context: VerificationContext) -> VerificationResult:
    """Run this step's registered test functions and aggregate their results."""


def oracle(context: OracleContext) -> None:
    """Implement this step in the application workspace."""
```

`VerificationContext` provides the application location, evaluation inputs, output
directory, and execution limits. `OracleContext` provides the application location
and candidate-accessible inputs, without private answers or judge credentials.
Use explicitly typed records for both contexts.

`VerificationResult` contains `passed: bool`, `checks: tuple[CheckResult, ...]`,
and `metrics: Mapping[str, float]`. Each `CheckResult` contains a requirement
identifier, `status: Literal["passed", "failed", "skipped"]`, an explanation,
and relevant measurements. A skipped check includes the unmet prerequisite and
does not count as a pass. Derive the overall pass condition from the task's
declared criteria.

### Orchestrate every requirement check

Put all requirement-checking logic in named functions with this contract:

```python
def test_requirement(context: VerificationContext) -> CheckResult:
    """Evaluate one declared requirement and return its evidence and outcome."""
```

Maintain an explicit, ordered registry of the step's `test_...` callables and any
prerequisite relationships. A plain typed collection is enough. Every requirement
test must appear in it; do not leave checks defined but unregistered.

`verify()` runs each registered check whose prerequisites are satisfied, collects
its `CheckResult`, and aggregates the checks and metrics into `VerificationResult`.
Keep orchestration and aggregation in `verify()`; keep individual assertions,
measurements, and quality judgments in the test functions or their helpers.
The shell and Python entry-point adapters do not run a separate set of checks.

Continue independent checks after a candidate failure. When a prerequisite fails,
record an explicit skipped result for each dependent check. Account for every
registered check in a completed verification report; never silently omit one.
For Orange, persistence, duplicate handling, and HERB answer quality each have
their own registered `test_...` function.

Candidate failures produce check results. Evaluation failures, such as a judge
outage or broken fixture, raise a distinct evaluation exception. Do not reduce
both to an integer or catch every exception as a failed candidate check. Preserve
completed check diagnostics when an evaluation error prevents a final result.

The oracle's output is the working application on disk. It raises on execution
failure and returns `None` on completion. Run the verifier afterward to establish
correctness. Later oracles build on the preceding step's application state.

Use [funtional-programmer](../funtional-programmer/SKILL.md) for implementation:
explicit parameter and return types and Google-style docstrings for every function.
The signatures above describe interfaces, not completed implementations.

## Keep the adapters thin

```text
Harbor → tests/test.sh → verify.py entry point → verify(context)
Harbor → solution/solve.sh → oracle.py entry point → oracle(context)
```

Python entry points construct contexts and handle process I/O. The verifier adapter
serializes diagnostics and maps completed evaluation results to Harbor rewards in
`/logs/verifier/reward.json` or `reward.txt`. On evaluation failure, exit unsuccessfully
and leave no valid reward file, including one left by an earlier run. Confirm this
behavior against the Harbor version used by the task.

The oracle adapter calls `oracle()` and propagates failures. Harbor uploads the
selected solution directory to `/solution`; do not assume sibling steps are there.
Keep adapters inside `verify.py` and `oracle.py` unless real reuse warrants another
module. No base class, plugin registry, or custom harness protocol is required.

## Choose how verification receives files

Run each evaluation in a fresh separate verifier container. Reuse the trusted agent
image when it meets the task's needs. In this mode, Harbor uploads task-level tests to `/tests/`, then
overlays the current step's tests. Reserve `common/` for shared modules to avoid
accidental filename collisions. Declare application artifacts explicitly: the
fresh verifier does not inherit the modified agent filesystem.

Set `verifier.environment_mode = "separate"` explicitly. Set the restricted network
policy in both `[verifier.environment]` (at creation) and `[verifier]` (during grading).
When providing `[verifier.environment]`, specify the resources it needs, including
GPUs; do not assume omitted values inherit from `[environment]`. Preinstall runtime
dependencies and weights. Allow only approved service endpoints when remote models
are required. Follow the isolation checks in
[declarative-task-design](../declarative-task-design/SKILL.md).

If using a dedicated verifier image or `tests/Dockerfile`, bundle its tests and
dependencies into that image, including `/tests/test.sh`. Do not assume runtime
test uploads or overlays will populate a dedicated image. Keep private files and
credentials inaccessible to submitted code when executing it during grading.

## Preserve the application boundary

The candidate implements the task's public application interface. For Orange,
that includes `ingest`, `retrieve`, `generate`, and the CLI. Neither the candidate
nor the application imports `VerificationContext` or implements `oracle()`.
Use a small application client when subprocess invocation is needed; do not make
the submission depend on grading modules or the oracle's internal architecture.

Let the agent discover installed tools through the environment, normal help text,
and inspectable files. Keep tool inventories out of `instruction.md`. Required
application behavior and mandatory restrictions still need to be visible.

When implementation is requested, validate the adapters and the full sequence
from a fresh environment, including inherited requirements and targeted failing
submissions. Use [declarative-task-design](../declarative-task-design/SKILL.md) to
choose the evidence. Report packaging checks separately from actual task success.

Check the task's Harbor version when implementing file transfers. See Harbor's
[multi-step layout](https://github.com/harbor-framework/harbor/blob/main/docs-mintlify/tasks/multi-step.mdx),
[separate verifier rules](https://github.com/harbor-framework/harbor/blob/main/docs-mintlify/tasks/separate-verifier.mdx),
and [oracle entry point](https://github.com/harbor-framework/harbor/blob/main/docs-mintlify/tasks/solution.mdx).
