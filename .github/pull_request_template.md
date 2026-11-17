## What changed

Describe the task or behavior changed. Link the issue, related PRs, and the
task-root README. This repository is dedicated to SWE-Marathon v2.

## Task design

For task changes, explain the professional workflow, intended workload, and
differences from the closest benchmark tasks. Identify the implemented steps and
any follow-up drafts. State which earlier requirements remain in force.

## Reward formula and justification

Write the actual published formula, including components, weights, normalization,
denominators, mandatory conditions, thresholds, missing or skipped cases, and
cross-turn aggregation. Link its implementation and boundary tests. Evaluation
errors must not produce a valid reward.

## Validation and remaining work

List commands and results. Separate local checks, controlled fixtures, live judge
calibration, reference/no-op trials, and end-to-end execution. Link evidence for
this revision and mark unrun checks explicitly. State whether the oracle is
deferred, available but unvalidated, or validated.

Record Oddish preflight and QA separately from trial rewards. Include applicable
Logfire references and the highest unresolved hackability severity from the
task README. For repository-only changes, explain which task evidence is
unaffected instead of filling in inapplicable results.

## Review checklist

- [ ] The instruction discloses every scored requirement and keeps grading details out of candidate-visible files.
- [ ] Task sources and maintained tools live together; local experiments and generated bundles are under Git-ignored `experiment/` folders.
- [ ] The task README includes a dated development-log entry for this work.
- [ ] The task README explains difficulty, solution approach, reward, expected answers, and hackability, with evidence gaps stated.
- [ ] Evaluations use fresh separate containers and only declared submission artifacts.
- [ ] Applicable LLM judge calibration and traces are complete before Oddish execution, or explicitly pending during authoring.
- [ ] Both automatic CI jobs execute and pass. Local and hosted results are identified separately.
