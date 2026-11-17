# Continuous integration

Both jobs below must pass before merging. They check different failure modes:
source and workflow validity, then execution of the maintained tests with real
packaging inputs. The workflows run on every pull request, push, merge-queue
request, and manual dispatch, without path filters or job-level skip conditions.

## Required checks and GitHub enforcement

| Required job name | Workflow | Purpose |
| --- | --- | --- |
| `V2 structure and CI regression tests` | [static-checks.yml](../.github/workflows/static-checks.yml) | Reject malformed tasks, invalid sources, broken contributor links, missing test registration, and invalid workflows. |
| `Author tests and package round trip` | [validate-task.yml](../.github/workflows/validate-task.yml) | Verify dependency consistency, execute the maintained tests, and validate a prepared task through packaging, extraction, and controlled verifier execution. |

On 2026-11-17, the repository's [branch-protection settings](https://github.com/abundant-ai/swe-marathon-2/settings/branches)
and [rulesets](https://github.com/abundant-ai/swe-marathon-2/settings/rules) contained
no rules. The workflow files were still local changes. GitHub therefore did not
enforce these jobs as merge requirements at the time of this audit.

After publishing the workflows and completing their first hosted runs, require
both exact job names on `main`, with GitHub Actions as the expected source.
Require the branch to be up to date before merging, or use a merge queue, and
apply the rule to administrators if they must meet the same gate. Check the
rule's bypass list explicitly. Keep the job names unique and update the rule
when renaming a job. Workflow YAML alone does not configure
[required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## Static checks

The static job uses Python 3.13 and standard-library checkers. It has a 15-minute
timeout and checks all Git-tracked and new nonignored source files, rather than
only files changed in the PR.

| Check | What fails |
| --- | --- |
| Task discovery and layout | No configured tasks; misplaced `task.toml`; malformed identity or authors; unsafe or duplicate step names; missing or empty runtime entry points. |
| Evaluation configuration | A step that does not resolve to separate verification; missing, relative, or traversing submission artifact paths; required files resolving outside the task. These are configuration checks, not proof of runtime isolation. |
| Development records | Any task, including a proposal, without a task-root README containing a `Development log` and nonempty entries with valid calendar dates. |
| Source syntax | Invalid Python, TOML, lockfile TOML, or shell syntax. Shell files are checked with `bash -n`; they are not executed. |
| Contributor links | Missing or escaping local inline link targets in `AGENTS.md`, root README, CONTRIBUTING, and Markdown files under `resources/`. External URLs and heading anchors are not checked. |
| Test registration | A maintained task suite missing from root pytest `testpaths`; a configured task without regression tests; an empty, duplicated, missing, or escaping suite path. Drafts without a runtime configuration do not need a test suite. |
| Checker regressions | Broken fixtures that the checker incorrectly accepts, or valid fixtures that it incorrectly rejects. Tests cover malformed configuration, artifacts, paths, development logs, syntax, suite discovery, and test-report failure handling. |
| Workflow validation | actionlint errors in workflow syntax, expressions, action inputs, or embedded shell commands. ShellCheck must be available; its absence fails the job. |

CI installs actionlint 1.7.7 through Go 1.24.2. For local validation, use the same
actionlint version with ShellCheck on `PATH`:

```bash
uv run --no-project python ci_checks/check_repository.py
uv run --no-project python -m unittest discover -s ci_checks -v
shellcheck --version
actionlint
```

## Task tests and packaging

The author-test job uses the [shared development environment](../README.md#local-setup-and-checks),
Python 3.13, and a 30-minute timeout. It first runs `uv lock --check --offline` to
reject stale dependency declarations, then installs from the frozen root lockfile.
The freshness check is separate because
[`--frozen` does not check whether a lockfile is current](https://docs.astral.sh/uv/concepts/projects/sync/).
The default `dev` group supplies pytest. Oddish CLI and Titans are optional and
are not installed by CI.

The job checks out SalesforceAIResearch/HERB at
`db3bf9b3f911745726c579c9dbf9f7f6b2c05b36` and runs the task's preparation script.
This supplies the public sample and private evaluation inputs needed by the
packaging tests. Missing prerequisites must fail instead of turning those tests
into an accepted skip.

The full root pytest suite covers the following implemented task behavior:

| Area | Evidence produced by the tests |
| --- | --- |
| Application contracts | Controlled working and broken applications, API and CLI behavior, typed results, artifact paths, independent checks, and dependency failures. |
| Retrieval and generation | Chroma pagination, embedding request contracts, generation limits, bounded concurrency, timeouts, malformed outputs, and provider cancellation. |
| Scoring and references | Fixed denominators, missing answers, configured thresholds and weights, authoritative reference lookup, citation validity, duplicate IDs, and conditional judge execution. |
| Judge integration | Mock HTTP requests and responses exercising structured schemas, retries, prompt boundaries, provider errors, and invalid output. These tests do not measure a live model's judgment. |
| Process boundaries | Credential filtering and artifact traversal rejection in controlled local execution. These tests do not establish container or network isolation. |
| Package round trip | Actual prepared inputs, Harbor parsing and network-plan resolution, archive extraction, staged verifier resources, development-file exclusions, and controlled verifier execution in a fresh Python process from the extracted package. |

The pytest report is written to `ci-results/pytest.xml`, after removing any older
report. The final checker runs even if earlier steps fail. It rejects missing or
malformed XML, a non-JUnit root, zero cases, inconsistent declared totals,
failures, errors, and skips, including expected failures recorded as skips.
Every maintained `test_*.py` or `*_test.py` module must have at least one testcase
in the report. The inventory comes from source files independently of pytest's
configuration, so a passing subset cannot satisfy the full-suite check.

The report is uploaded on success or failure with 14-day retention; a missing
report also fails artifact upload. The test process's exit status remains a
separate failure signal. Per-module evidence does not prove that every intended
assertion exists: review test changes for lost cases and weakened assertions.

## Adding or reproducing checks

Keep shared checker regressions in `ci_checks/` and task-specific tests in
`tasks/<family>/<task>/checks/`. Register each suite explicitly in the root
`pyproject.toml`. Add a failing example for the bug or boundary being covered,
plus a legitimate case that should still pass. Keep automatic tests independent
of private accounts and local `experiment/` contents; pin public input revisions.

Manual probes use names outside pytest's collection patterns. The knowledge-work
assistant's `checks/smoke_container.py` and `checks/smoke_environment.py` require
controlled container execution described in its README. They are not automatic
pytest tests.

Follow the [shared setup guide](../README.md#local-setup-and-checks), then the
[task input preparation procedure](../tasks/swe-m2-ai-engineer/knowledge-work-assistant/README.md#build-and-deliver).
Run the static commands above and:

```bash
uv lock --check --offline
uv run --frozen pytest -q --junitxml=ci-results/pytest.xml
uv run --no-project python ci_checks/check_test_results.py ci-results/pytest.xml
```

Both workflows use `ubuntu-24.04`, read-only repository permissions, and checkouts
with credential persistence disabled. They require no repository secrets.
Do not introduce path-filtered required jobs, `continue-on-error`, or
secret-dependent skips. A prerequisite failure must remain visible as a failure.

## Evidence still needed outside CI

Only the knowledge-work assistant currently has a runnable configuration and an
automatic task suite. The game and Titans proposals receive source and
development-log checks; passing CI does not validate their intended behavior.

GPU image builds, real container privileges and network restrictions, fresh
container transfer on evaluations/retries/regrades, live judge calibration,
agent and oracle trials, and adversarial runtime assessments require separate
execution. Follow [Oddish guidance](ODDISH.md) and record that evidence in the
task README. Semantic review must also assess instruction quality, solvability,
reward validity, and the task-specific Hackability assessment. None follows
from a green structural check or mocked judge test.

## Local audit: 2026-11-17

The full suite passed **262 tests with no skips** in 88.69 seconds after rerunning
HERB preparation. The JUnit checker confirmed execution from all 14 maintained
test modules. This includes 27 checker regression tests, which also passed
independently through standard-library unittest discovery.

Repository source, layout, link, and suite-registration checks passed.
actionlint 1.7.7 passed with ShellCheck 0.11.0 available. The offline lockfile
check passed, including from an empty cache in a temporary checkout of the
dependency files; changing the pytest pin without updating the lockfile failed
as intended. Regression fixtures also confirmed that omitted suites, empty
suites, partial reports, malformed counters, failures, errors, and skips fail.

These results came from the local macOS checkout. The updated workflows have
not been exercised on a GitHub-hosted Ubuntu runner. GitHub merge enforcement
remains pending as described above; no remote settings were changed.
