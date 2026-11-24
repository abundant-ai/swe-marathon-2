# Oddish execution

Use Oddish for package preflight, uploads, baseline and model trials, QA,
analysis, and artifact collection. It requires access to the private Oddish
repository and execution service.

Install the optional CLI through the [shared setup guide](../README.md#optional-tools).
It runs in an isolated uv tool environment and is not part of default setup.

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

Prepare and package the task using its authoring scripts. For the existing
knowledge-work assistant, follow the [packaging instructions](../tasks/enterprise/knowledge-work-assistant/README.md#build-and-deliver).
Use the generated task directory for preflight and upload. It contains prepared
inputs that are intentionally absent from a clean source checkout.

Before execution, complete any required judge calibration and trace validation
from the [v2 requirements](requirement.md#llm-judges). Check that the installed service
supports the package's multi-step schema and verifier configuration. A rejected
package or failed infrastructure setup is not an agent result.

Keep preflight results, Oddish QA verdicts, trial rewards, and artifact review
separate in the author notes and PR. Tie them to the task revision or bundle hash.
Record unresolved failures and missing evidence. Automatic CI does not submit
Oddish experiments or post a handoff comment in place of running tests.
