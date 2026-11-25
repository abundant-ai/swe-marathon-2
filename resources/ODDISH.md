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

## Screen tasks for a score below 0.5

Proximus uses single-session Linux CPU tasks. When a task has a cumulative
final verifier, package the fixed briefs and that verifier in one session.
Run all three models on the same bundle.

1. Propose or revise the task. Use previous checkpoint and trajectory evidence
   to choose the capability to strengthen. Qualify the reference and no-op,
   pass preflight, and record the hosted task version and bundle hash. Verify
   that all three model routes support the same task execution format.
2. Run one fresh `openai/gpt-6.2-sol` trial at `xhigh`. If it scores below
   0.5, run up to two more trials on the same version, one at a time. Any
   valid score of 0.5 or above sends the task back for revision.
3. After three qualifying GPT scores, start one
   `relace/deepseek-v4.1-flash` and one `relace/glm-5.3` trial in parallel
   through Proximus.
   Submit each model's next trial only after its previous score qualifies.
   Stop scheduling trials for that version as soon as either model scores
   0.5 or above. Otherwise collect three valid trial scores from each model.
4. Commit and push the benchmark version once all nine trial scores are below 0.5.
   Keep the task version, baseline results, and trial links with the review.

Progress independent tasks in parallel. Within a version, pin every
confirmation to the recorded task and version and reuse its qualified baseline
results. For stored tasks, use `oddish run --task TASK_ID --version VERSION`
with `--n-trials 1` in a new confirmation experiment. Verify that exactly one
solver trial was created on the requested version and record its ID and
experiment alongside the original reference and no-op. Match its native task
checksum to those controls before counting it in the screening sequence. If
a submission loses its response, check the requested experiment's existing
trials before repeating the request.

Use `oddish status TRIAL_ID --json` to track the named solver trial. Once
it finishes, match its `result.json` task checksum to the qualified baseline
and check `reward_valid`. Inspect the verifier report for any failure that
could invalidate the reward. A new task version can also trigger automatic
Oddish review jobs. Count only the named solver trials.

A service failure can be retried on the same version. If a problem in the
instructions, verifier, fixture, or environment changes the meaning of a score,
fix it and start the screening sequence on the new version. Preserve earlier
results for diagnosis and track the individual rewards, since the gate applies
to each trial.

For tasks that support native extensions, build and load a small library in
both the agent and separate verifier images. If the agent ran its application
and the hosted verifier fails before any domain check, compare their runtime
dependencies before counting the score. A successful platform status can
still contain a score caused by an incompatible verifier image.

For physical command limits, qualify exact-boundary inputs and nearby
violations. Roundoff in a sampled rate can otherwise prevent an admissible
plan from reaching the native checks that measure task difficulty.
