# Oddish execution

Use Oddish for package preflight, uploads, baseline and model trials, QA,
analysis, and artifact collection. It requires access to the private Oddish repository and execution service.

Install the optional CLI through the [shared setup guide](../README.md#optional-tools).
It runs in an isolated uv tool environment.

Use the installed revision's help and bundled skill for current commands:

```bash
oddish --help
oddish skill
oddish skill --path
```

The `references/cli-contract.md` file beside the printed skill belongs to the
same installed revision. Record that revision with execution evidence. These
upstream references describe the customer workflow and service:

- [CLI reference](https://github.com/abundant-ai/oddish/blob/main/docs/customer/reference/commands.md)
- [Oddish agent skill](https://github.com/abundant-ai/oddish/blob/main/oddish/src/oddish/assets/skills/oddish/SKILL.md)
- [CLI/API contract](https://github.com/abundant-ai/oddish/blob/main/oddish/src/oddish/assets/skills/oddish/references/cli-contract.md)
- [API routes](https://github.com/abundant-ai/oddish/tree/main/backend/api/routers)

## Static tasks

Follow the task README to prepare its inputs. If it has a packager, submit
the generated runtime directory. See the [static Orange packaging instructions](../tasks/static/app_building/knowledge-work-assistant/README.md#build-and-deliver).
A single-step bundle has a root `instruction.md` and `tests/`; a multi-step
bundle has `steps/<step>/` and matching `[[steps]]` entries.

## User-sim tasks

Prepare the directory that contains `task.toml`, `user_agent.yaml`, and the
files that the user configuration references. Pass that directory to
`oddish run` with `--user-agent`. The [user-sim Orange README](../tasks/usersim/knowledge-work-assistant/README.md#build-and-deliver)
shows the command and the required local inputs.

## Trial evidence

Before execution, complete any required judge calibration and trace validation
from the [v2 requirements](requirement.md#llm-judges). Check that the installed service
supports the package's task layout and verifier configuration. A rejected
package or failed infrastructure setup is not an agent result.

Keep preflight results, Oddish QA verdicts, trial rewards, and artifact review
separate in the author notes and PR. Tie them to the task revision or bundle hash.
Record unresolved failures and missing evidence.
