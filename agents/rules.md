# Repository rules

## Scope and layout

This repository is currently for task design. Each step keeps its `instruction.md`
under `tasks/<family>/<task>/steps/<step>/`. Preserve those files unless the user
asks to revise them. References to runtime files in an instruction describe the
intended environment; they do not mean that environment already exists.

Create implementation files when the user asks for implementation. A request to
discuss a contract or design a verifier is permission to do that design work.
It does not call for scaffolding, downloading a corpus, or launching a GPU run.
Existing authorization in the conversation still counts; do not ask for it again.

Keep deployable Harbor files under `tasks/<family>/<task>/`. Put author checks,
preparation and packaging scripts, author documentation, and author dependencies
under `authoring/<family>/<task>/`. Keep generated bundles out of the task folder;
create them under the corresponding authoring folder only when needed. Do not
create `tasks/swe-m2-ai-engineer/`-level utilities. Add a shared abstraction only when the
user requests one and there is a concrete use for it. Create future steps when
requested, without placeholder implementations or unused directories.

Store repository rules and skills in `agents/`. Keep candidate-facing task
instructions in the step directory. Do not commit or stage changes until the user
asks; leave the branch without a commit for now.

## Task contracts

Use `abundant/swe-m2_<domain>_<task>` for the `[task].name` field in
`task.toml`. For example:

```toml
[task]
name = "abundant/swe-m2_ai-engineering_knowledge-work-assistant"
```

Keep only the slash after the organization; join later components with underscores
to fit Harbor's `org/name` contract. Repository directory names remain unchanged.

Keep packaged task folders limited to runtime artifacts: task configuration,
environment build inputs, step instructions, and verifier or solution files needed
by the runner. Exclude authoring scripts, local checks, and author dependency files.
Generate Oddish upload code when needed and keep it outside the task artifact.

Read the current step instruction and the user's latest decisions before designing
its environment or verifier. Work backward from the requested behavior. Existing
code, a reference solution, and earlier drafts cannot silently add requirements.

Make consequential interfaces explicit: inputs, outputs, types, defaults, state
changes, errors, and resource limits. When a decision would change what counts as
success, surface it before implementing the dependent check. Continue independent
work while it is unresolved. Routine implementation choices do not need approval.

Keep each enforced requirement visible to the candidate. Private cases can test
disclosed behavior, but cannot introduce new restrictions. For successive steps,
identify which earlier requirements still apply and which the new request replaces.

Never explain final evaluation in a task's `instruction.md` or candidate-visible
environment. Keep grading procedures and configuration in author-only material.
Describe the requested work, public interfaces, and deliverables directly. A
candidate's own development experiments are part of the work, not final evaluation.

## Skills to use

- Use [harbor-task-structure](skills/harbor-task-structure/SKILL.md) when organizing
  environments, step inputs, verifier and oracle files, or their Python entry points.
- Use [instruction-writing](skills/instruction-writing/SKILL.md) when drafting or
  editing a step instruction.
- Use [declarative-task-design](skills/declarative-task-design/SKILL.md) when
  designing or changing acceptance criteria, rubrics, or verifiers.
- Use [funtional-programmer](skills/funtional-programmer/SKILL.md) when creating or
  changing functions, including tests and helpers.

## Implementation and evidence

Use the repository-root `pyproject.toml`, `uv.lock`, and `.venv` for local authoring,
testing, and packaging. Run commands with `uv run` from the repository root. Keep
container runtime dependencies in the task's `environment/pyproject.toml`. Keep
generated datasets, environments, caches, credentials, and run artifacts out of
version control. Add dependency files and ignore rules when they become necessary.

Validate the behavior changed by the work. Report local checks, controlled-model
checks, live judge calls, and end-to-end runs separately. A mocked judge does not
establish answer quality; a failing baseline does not establish that the task is
solvable. Mark unavailable validation as unverified.
