# Contributing to SWE-Marathon v2

Task creation is an iterative process: explore an idea, write the important parts
of the instructions, build the environment and verifier, run the task, and use
what happens to improve the design. You can contribute at any stage. Keep the
current state and remaining work clear so someone else can pick it up.

Use the [v2 requirements](resources/requirement.md) for design criteria and
technical contracts. This guide explains how to move from an idea to a task and
then develop more tasks from what you learn.

## 1. Ideation

Add ideas to the [task brainstorming sheet](https://docs.google.com/spreadsheets/d/1s24wFUJZHy4nhDNLEVkLbEVdYaA2DBUytSEK66rtqa0/edit?gid=1811373541#gid=1811373541).
Keep this free-form and open-ended. A workflow you find interesting, a difficult
research question, a rough scenario, or a capability agents struggle with is
enough to start a discussion. Add links, questions, and variations if useful.
There is no required proposal template or completed feasibility analysis at this
stage. Build on other people's ideas as well as adding your own.

## 2. Initial task design

Choose an idea and sketch a realistic workflow with multiple steps. Write the
important parts of each step's `instruction.md` by hand: the user's intent, what
they need done, the consequential constraints, and what they should receive.
Author judgment should establish the core of the task. Agents can help develop
and refine that draft using the
[instruction-writing skill](resources/skills/instruction-writing/SKILL.md) and
[Humanizer](resources/skills/humanizer/SKILL.md).

Explain how the steps fit together. What does the first step produce? What does
a later request build on or change? Which requirements remain in force, and what
new information does the user provide? Follow-ups should reflect how the work
would develop in practice. Single-turn tasks remain possible under the same
quality and workload requirements, but start by exploring a multi-step workflow.

Use [declarative task design](resources/skills/declarative-task-design/SKILL.md)
to assess the [design dimensions](resources/requirement.md#task-design-dimensions):
novelty, verifiability, realism, difficulty, and initial feasibility. Compare the
closest public benchmark tasks, SWE-Marathon v1, and tasks already designed here.
Identify what makes this task different and what evidence could establish success.
A rough plausible solution approach is enough initially; an oracle or successful
baseline can come later. Keep the ambition even when the solution is uncertain.

### Static tasks

Put a fixed brief under `tasks/static/<category>/<task>/`. For one step, put
`instruction.md` at the task root. When you implement it, add `tests/` and,
if you have a reference solution, `solution/` beside the brief. Set the agent
and verifier settings at the top level of `task.toml`.

If the task has two or more scripted steps, put each brief and its runtime
files under `steps/<step>/`. List the implemented steps in execution order
with `[[steps]]` in `task.toml`. The [fixed-lag fusion task](tasks/static/robotics/fixed-lag-fusion/)
shows how later briefs build on earlier work.

### User-sim tasks

Put the task under `tasks/usersim/<task>/`. A conversation can span many
messages within one Harbor step. Keep its opening brief in `instruction.md`
and configure the user agent in `user_agent.yaml` at the task root. The
[user-sim Orange task](tasks/usersim/knowledge-work-assistant/) shows how to
reference a persona and opening prompt and how to start a run with `--user-agent`.
Use `steps/<step>/` only when the runner must advance through multiple
separately declared steps.

### Task notes

Describe the inputs, outputs, interfaces, and constraints for either format.
Keep private cases and grading details in author notes. State each requirement
the candidate must meet in the brief or the conversation.

Start a task-root `README.md` with the design rationale and a `Development log`.
Use `### YYYY-MM-DD` entries throughout development to record changes, reasons,
checks actually run, results, and remaining work. Preserve earlier entries.
Instruction-only drafts do not need placeholder runtime files. Identify who is
working on which parts and link related discussions or contributions.

## 3. Build the environment and verification system

Once the initial instructions establish the work, make the task runnable. Follow
the [shared setup guide](README.md#local-setup-and-checks) and the
[multi-turn task structure skill](resources/skills/multi-turn-task-structure/SKILL.md)
for layout, configuration, packaging, and verifier interfaces. Add runtime files
as you implement the task.

Prepare the inputs, dependencies, tools, and resources the agent needs. Check data
licenses and external-service access. Keep shared task resources in task-root
`common/` and copy only what each image needs. Maintained checks and preparation
scripts belong in the task directory; local experiments, generated bundles, and
run outputs belong in a Git-ignored `experiment/` folder. Exclude author notes,
development tools, private answers, verifier code, and oracle code from the
candidate image. Keep credentials and generated artifacts out of Git.

Task-root `checks/` and `scripts/` are optional development tooling that can be
tracked and run locally. Never upload them in runtime bundles or include
them in Docker build contexts, images, or runtime mounts. Agent and verifier
Dockerfiles must not copy, add, or mount their contents. Run preparation outside
the task images and stage only the required generated inputs. The runtime
verifier lives beside its brief in `tests/`.

Map the instruction's requirements to observable evidence. Build programmatic
checks, LLM judges, or a combination as appropriate, and define how the metrics
are computed even if a complete solution is still unknown. Exercise the real
interfaces and record results for each assessed dimension before aggregation.
Follow the [verification requirements](resources/requirement.md#verification-and-solvability)
and [function-contract skill](resources/skills/funtional-programmer/SKILL.md).

Document the [reward formula](resources/requirement.md#reward-justification) in
the task README, including partial credit, missing or skipped cases, and turn
aggregation. Keep denominators fixed on candidate failures. Infrastructure or
judge errors invalidate an evaluation and must not leave a valid or stale reward.

Run every evaluation, retry, and regrade in a fresh separate verifier container
with only declared submission artifacts. Configure resources and connections,
protect private data and result files, and test the actual boundaries. Maintain
a task-specific [Hackability assessment](resources/requirement.md#hackability-assessment)
in the README; mark untested boundaries `YELLOW / UNASSESSED`.

## 4. Review locally with Harbor checks

Start reviewing the task with `harbor check` and the
[v2 review rubric](resources/task-implementation.toml). You can also use this
review during initial design to identify gaps before implementation. Follow the
[Harbor review instructions](resources/requirement.md#review-and-execution) for
commands and model credentials.

Read the findings against the instructions and task README. Resolve unclear
contracts, weak verification, or unsupported claims, then review the revised
files. Distinguish proposal-stage gaps from defects in a runnable task. Harbor
check is a model-based file review; a pass does not show that the environment
runs or that the task has been solved.

Read the five dimension ratings in the report: novelty, verifiability, realism,
difficulty, and initial feasibility. Each explanation should include a 1–5 rating
or `UNASSESSED`, review stage, confidence, evidence, rationale, and gaps. Use the
individual findings to guide iteration; do not average them into one score.
Implementation and readiness findings remain separate. See the
[rating convention](resources/requirement.md#review-and-execution) for Harbor's
pass/fail mapping and treatment of missing evidence.

After the review completes, use the [task-rating skill](resources/skills/task-rating/SKILL.md)
to reconcile those ratings with the evidence and record scores in `task.toml`
metadata. Keep rationale and gaps in the task README. This is the next agent
action after Harbor review; the Harbor CLI does not update metadata itself.

Use the task's local checks to exercise the packaged environment and verifier.
Record the oracle’s provenance when you validate one. The repository’s
[commit hook](resources/CI.md) runs Ruff.
Record commands, results, and the revision reviewed in the development log.

## 5. Test the task with Oddish

Use [Oddish](resources/ODDISH.md) for package preflight, trials, QA, and artifact
collection. Prepare the generated task bundle, check that the service supports
its task layout and verifier configuration, and follow the installed CLI's skill
and help for current commands. Complete required
[LLM judge calibration and trace validation](resources/requirement.md#llm-judges)
before execution.

Run the implemented step sequence and inspect what happened: the agent's actions,
deliverables, preserved state, check results, and failure points. Record task and
bundle versions alongside model settings and execution evidence. Keep preflight,
QA verdicts, trial rewards, and artifact review separate. A package rejection or
infrastructure failure is not evidence that the task is difficult for an agent.

Use the task README for durable findings and links to evidence. Detailed local
outputs can stay in `experiment/`. State what remains untested; a high reward
alone does not establish that the agent legitimately satisfied the instruction.

## 6. Iterate on difficulty and task quality

Use the trials to improve the design, with particular attention to difficulty
and the other [design dimensions](resources/requirement.md#task-design-dimensions).
Identify where the agent succeeds, loses coherence, makes consequential mistakes,
or finds a shortcut. Separate genuine capability limits from instruction ambiguity,
broken environments, unreliable judges, and verifier defects.

Increase difficulty through meaningful work: deeper dependencies, more demanding
research or spatial reasoning, interacting systems, or follow-ups that require
adapting earlier decisions. Aim for at least five days of useful agent execution
across the task, roughly a week, and refine that estimate from trials. Necessary
experiments count; forced waiting and repeated busywork do not. Accept faster
valid solutions. Low scores alone are not evidence of a good task.

Revisit novelty, realism, and verifiability as the task changes. Keep a rough
feasibility hypothesis and strengthen solvability evidence over time without
shrinking the task merely to fit an easy oracle. When instructions change, update
the corresponding checks and reward, explain the effect on comparisons with
previous results, and rerun the affected validation. Recalibrate judges after
material changes. Repeat local review and Oddish trials as needed.

## 7. Finalize a version and develop related tasks

Finalize a version when its scope and evidence are clear enough for review.
Check the full implemented sequence, packaging, verification, and assessment
boundaries. Resolve known exploits and document remaining limits. Keep oracle
status explicit: deferred, available but unvalidated, or validated. A finalized
version must not imply that pending validation has happened.

Open a focused PR using the [PR template](.github/pull_request_template.md). Link
the task README, explain the design and reward formula, and provide validation
results for the proposed revision. Include novelty comparisons, execution
artifacts, applicable judge calibration, and the highest unresolved hackability
severity. Report the task checks you ran.

Then consider how to create more tasks that exercise the same underlying
capability. Document which parts of the workflow and verifier can be reused,
which inputs or scenarios can vary, and what needs expert design or review for
each new task. Variations should change meaningful decisions while preserving
realism and reliable assessment; renaming the same task is not enough.

Try a small set of variations before generating a large collection. Check their
novelty against each other, inspect how difficulty changes, and validate that
shared verification still measures the intended outcomes. Record the generation
approach and its limits, bring new ideas back to the brainstorming sheet, and
continue the design and testing cycle.
