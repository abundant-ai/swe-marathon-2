# Enterprise Knowledge Work Assistant

Build Orange, a Mac desktop assistant for employees at a software company. An employee can ask what changed in a project, follow an answer back to a source, prepare an internal handoff or edit a customer reply. The agent starts with a [project brief](instruction.md) and the company's [integration contracts](environment/resources/desktop.md).

## Build and deliver

From the repository root, use the Oddish preview CLI to submit the prepared task folder.

```sh
oddish run tasks/enterprise/knowledge-work-assistant --user-agent -a codex -m openai/gpt-5 --env modal
```

The CLI reads the upstream Harbor pin from [oddish.toml](oddish.toml). The preview worker reads the user model, persona and template from the task root and assigns credentials. A copy of this prepared directory includes the public sample and private grading inputs. Git omits those generated inputs. [Oddish preview PR](https://github.com/abundant-ai/oddish/pull/3585)

Edit [user_agent.md](user_agent.md) to change the user's profile, hidden information or answering rules. Edit [prompt.j2](prompt.j2) to change how the conversation opens. Harbor fills in `persona`, `bridge_instructions` and `instruction` when it starts the user agent.

## Development log

### 2026-11-24

Removed `ci_checks`, including `prepare_data.py` and `prepare_ci_inputs.py`. This README no longer tells a fresh checkout to rebuild inputs with those scripts.

### 2026-11-23

The prepared folder runs directly through the Oddish preview CLI. Each image has its own Chroma build context. The private grading corpus and rubrics live under `tests/private/`.
