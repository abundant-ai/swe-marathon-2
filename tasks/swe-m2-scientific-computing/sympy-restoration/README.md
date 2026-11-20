# SymPy restoration

Author notes. Nothing in this file is shipped to the candidate or to either image.

SymPy 1.14.0 with the bodies of 2,671 functions and methods in 355 files removed
(37,645 non-blank lines). Signatures, decorators, docstrings and all other code
stay. The candidate writes the bodies back, without network access, using a small
`restore` command that reports progress and checks work against the graded view.

This is a pilot brought over from a v1-style task. It has one implemented step,
run as one 12-hour working session (the version on Oddish since 2026-11-19; the
48-hour chain of sessions it replaced is described under [Workload](#workload)).
It does not yet meet the v2 workload target; see [Workload](#workload) and
[Remaining work](#remaining-work).

## Development log

### 2026-11-15

- Designed the task: remove function bodies from a doctested library, grade the
  restored bodies against the original behaviour.
- Wrote the builder (unit selection, skeleton, recorded calls, sealed tests) and
  the `restore` tool. First build had 3,053 units.

### 2026-11-16

- Two red-team rounds (7 and 4 attacking agents) against the grader. No attack
  reached reward 1. Findings and fixes are in
  [Hackability assessment](#hackability-assessment). Units that could not be given
  a replayable recorded call were removed: 3,053 to 2,671.
- Checked the reference results: all 13,384 calls reproduce on emulated
  linux/amd64 and under hash seeds 0 to 8 plus a random seed; none matches on the
  blank skeleton.
- Ran the v1-layout package on Oddish, experiment
  `sympy-restoration-10k-20261116` (https://www.oddish.app/experiments/c05b779c):
  reference solution 1.0 twice, no-op 0.0 twice, then nine model trials. Results
  are in [Trial evidence](#trial-evidence).

### 2026-11-17

- Compared the best run's bodies with upstream by syntax tree: 20.4% identical,
  concentrated in bodies of one to three lines. Details under
  [Novelty](#novelty).
- Ported the task to the v2 layout: one step under `steps/01-restore-bodies/`,
  verifier entry point `tests/verify.py` with registered requirement checks, a
  reference solution with `oracle.py`, a packaging script, development checks.
- Changed verifier behaviour to the v2 contract: an evaluation that cannot finish
  (not root, cannot drop privileges, unreadable private inputs, runner cannot
  start) now exits non-zero and leaves no reward file. The v1 package wrote
  reward 0 in those cases.
- Ran `checks/` locally: 19 tests pass. Ran `oddish preflight` on bundle
  `e043dc4facdd`: passed. Uploaded it as task
  `swe-m2_scientific-computing_sympy-restoration-66d29774` and queued two
  reference and two no-op baselines in experiment `sympy-restoration-v2-20261117`
  (https://www.oddish.app/experiments/9f377cd3). Results are recorded under
  [Validation](#validation) when they settle.
- Rewrote `instruction.md` as a request with requirements only. The v1 text
  described how the tree is graded, the three measurements with their limits and
  the reward thresholds; v2 keeps assessment mechanics out of candidate-visible
  files. The requirements themselves are unchanged, with one addition stated as
  behaviour: restored code should not be more than about three times slower than
  the original (the enforced budgets allow about five times). Reworded six
  messages of the `restore` tool that mentioned grading.
- Added `scripts/package_single_step.py`. Proximus on Oddish rejects any task
  that declares `[[steps]]`, so it cannot run this bundle. The script writes the
  same files without the steps wrapper under its own task name
  (`...sympy-restoration-single`). Bundle `36876c6104ab` passed preflight, was
  uploaded as task `swe-m2_scientific-computing_sympy-restoration-single-6949ef06`
  and its baselines were queued at 05:52 UTC in the same experiment as version 2.
- Model trials on bundle `8180b51500b1` settled: three `claude-code` runs, all
  reward 0, best 95.7% of units. Proximus runs settled on the single-step
  variant (three) and on the v1 package (two), all reward 0, 25% to 50% of
  units. Numbers are in [Trial evidence](#trial-evidence).
- Found two defects in the sealed test phase from those trials. In trial 17 a
  60-second test timeout fired while pytest was building a failure report; the
  session ended and 2,267 tests were never started. In single-step trial 6 the
  session reported nothing for the whole 40-minute budget, so all 10,428 tests
  counted as not reached. Neither changed a verdict; both understated the test
  share. Checked the other graded trials: no other session ended early.
- Rewrote the sealed test phase (`verifier/engine.py`): one session first, then
  one process per test file for whatever the session did not finish, with a
  watcher that ends a run that stops reporting. Described under
  [Verification](#verification). Added 14 development checks for it and
  reproduced both failures with the pinned pytest, xdist and timeout versions on
  a small synthetic tree (the session alone loses tests; the new phase settles
  all of them).
- Added `scripts/package_regrade.py`, which packages a stored submission in
  place of the reference so that it can be graded again, and
  `scripts/oddish/regrade.yaml`.
- Grading trial 6's submission again showed a third loss of the same kind, in
  the replay of recorded calls: the process of one module ended by itself during
  a call whose code uses random numbers, and the 90 calls queued behind it were
  not reached (12 units, in one grade and not in the other). `run_vectors` now
  starts a module's job again without the call that ended or blocked it, and
  the runner seeds the random generators from the call id before every call.
- Validated the final verifier on Oddish, experiment
  `sympy-restoration-v2-grader3-20261117`
  (https://www.oddish.app/experiments/184f3cb6): see [Validation](#validation).
- Changed the budget from 9 to 48 hours on the owner's instruction: with "9
  hours" in the instruction every run ended at 9 hours. The instruction now gives
  48 hours and says they are spread over working sessions. One attempt on Oddish
  ends after 12 hours with grading included, so the 48 hours run as five
  sessions of 9.6 hours (`scripts/package_session.py`); see [Workload](#workload).
- Started six 48-hour runs (the agents and models of the earlier v2 experiment)
  in experiment `sympy-restoration-v2-48h-20261117`
  (https://www.oddish.app/experiments/ebb4e086) at 17:07 UTC. No result yet.
- Not done: `harbor check` with the v2 rubric, task ratings, any attack on the
  new entry point.

### 2026-11-18

- Held the six 48-hour runs after session 2 (19.2 hours, all reward 0, best 2,568
  of 2,671 units): every further session is a new task row, and the owner wants
  one task row per experiment. Numbers under [Validation](#validation).

### 2026-11-19

- Replaced the 48-hour chain with one 12-hour working session, on the owner's
  decision. The instruction states 12 hours at most and that the run can end
  before then, and asks for a `/app/PROGRESS.md` log every 30 minutes;
  `/app/timer.sh` counts 12 hours from the container's first process and keeps
  no state file. Ran first as version 2 of the `-48h-s1` task row: six model
  trials (Proximus and claude-code, DeepSeek v4.1 Flash and GLM 5.3), all
  reward 0, best 82.3% of units, and no early stops once claude-code ran with
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`. Then uploaded as version 4 of the
  task's own row, `swe-m2_scientific-computing_sympy-restoration-66d29774`,
  where six more model trials run. This is the version this repository carries.
- Oddish's pre-trial audit of version 4 (now a gate before any model trial)
  returned one must-fix finding, information leakage, not exploited: an authoring
  comment in `task.toml` recorded the dated time decision and named the harness
  and its attempt limit. Removed it, and the same class of text elsewhere in the
  shipped files: the packaging notes at the top of both Dockerfiles, the harness
  name in `tests/verify.py` and `tests/Dockerfile`, and the word "budget" in
  `timer.sh`. Comments and docstrings only; no value, code, threshold or
  instruction text changed. The cleaned files go up as version 5 once the
  running trials settle.
- `scripts/package_session.py` stays for the record but cannot stage this task
  any more (the 12-hour timer has no `USED_BEFORE_SEC` line). Its check now
  asserts that refusal, and that the hours the instruction states, the timer's
  total and the agent limit agree. 35 checks pass.

### 2026-11-20

- Delivery (integrity). A process left running after the work could fetch SymPy
  1.14.0 once public egress returns and write it into `/app/sympy` before the
  tree is collected; nothing recorded what was delivered, so a failed or partial
  collection was graded as the work's own 0. The work now runs as the
  unprivileged user `dev`. A root setup step starts `fsmaint-netcheck`, which
  polls a few public hosts with a TLS handshake (as `nobody`) and, on the first
  poll after a long closed stretch in which one answers, records the last closed
  poll as the end of the work and ends every process of `dev`. A root collect
  step (`fsmaint-sweep`) freezes and ends what is left of `dev`, records the type,
  size, times and sha256 of every entry under `/app/sympy` before touching
  anything, probes egress, and writes a record and a mark signed with a key only
  root can read. The verifier raises an evaluation error when nothing arrived,
  the mark is missing or unsigned, or a listed file differs; a file changed at or
  after the end of the work is not taken over (its units are `late`); the
  verifier's own network must be closed. The instruction now says that another
  copy of SymPy's source is not to be used, and that the tool's copies under
  `/opt/restore` are as damaged as the working copy; `ATTRIBUTION.txt` in the
  image keeps licence and citation only. The reference solution waits two
  seconds after writing. 50 checks pass: the setup and collect hooks run whole
  under dash with stand-ins for root and Linux tools; a write after the end is
  refused and an honest delivery is taken; every way a mark can fail is an error.
- Verifier robustness. The docstring phase crashed the verifier (an evaluation
  error) when its budget ran out: a job returned six values where eight were
  read. It also drew random inputs unseeded, and one process that ended or hung
  inside a builtin failed every unit of its module. Each module's runner now
  runs under the process watcher, a death or a stall fails only the unit that was
  running, a used-up budget leaves a row for every unit, results count only from
  runs that reached their own self-check, and every unit's generators are seeded
  from its name (the agent's `restore check` does the same and restarts behind a
  failing unit). Both runners now say when their module is imported, so an
  import that never finishes fails its module in one start instead of one unit
  per restart, and a run that reported every unit but died before its self-check
  counts nothing without blaming a unit. The call replay no longer gives a job up
  after two barren starts: a barren start costs only its unit, and a timeout
  restarts the runner.
  Fixed wall-clock budgets let host load fail the tests: three graded runs lost
  47 to 192 tests to the 40-minute test budget while a third of the verifier's
  time sat unused. The measurement now has one deadline (6,000 s); the test phase
  takes what the earlier phases leave; deadlines use the monotonic clock; a
  restarted job's old records no longer count as its progress; when a verdict
  would turn on items not reached the evaluation is an error, not a 0. Submitted
  code runs under a 4 GiB address-space limit where one can be set. 61 checks
  pass. On real SymPy (Python 3.12, outside the sandbox) the rewritten runners and
  drivers pass 62 of 62 units and match 287 of 287 calls of two modules of the
  original tree, and give the same statuses twice on a stored submission whose
  examples draw random inputs.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-restore-bodies` | Implemented. Instruction, agent image, separate verifier image, reference solution. |
| Further steps | Not designed. See [Workload](#workload). |
| Prepared inputs | Present locally under Git-ignored paths; produced by the builder in `scripts/builder/`. |
| Oracle | Validated: 1.0 twice on the v1 package and 1.0 twice on v2 bundle `e043dc4facdd` in fresh verifier containers. Provenance: the original SymPy 1.14.0 source of the 355 files. |
| Ratings (`harbor check`) | Not run. No `[metadata.task_rating]` yet. |

Layout notes:

- `common/restorelib.py` is the one source of the code that copies unit bodies
  into the skeleton. Packaging stages it into the agent image (for `restore`) and
  into the verifier image.
- `environment/pyproject.toml` lists the Python packages of both images.
  Packaging stages it into the verifier build context as `runtime/pyproject.toml`.
- Git-ignored prepared inputs: `environment/data/` (workspace archive, unit
  list, the key the collect step signs with, written by
  `scripts/builder/delivery_key.py`), `steps/01-restore-bodies/tests/private/`
  (skeleton with the full test suite, sealed test list, recorded calls,
  reference results) and `steps/01-restore-bodies/solution/data/` (original
  source of the 355 files). Packaging stages the key into the verifier's private
  inputs as well.
- `environment/fsmaint-reserve`, `fsmaint-netcheck` and `fsmaint-sweep` are the
  setup and collect hooks (`task.toml`). They live in `/usr/local/lib/fsmaint`,
  mode 0700 and owned by root, off `PATH`; the agent's user cannot read them.
- The agent runs as `dev` (uid 10001). `/app` is root-owned and sticky,
  `/app/sympy` is root-owned and world-writable with everything in it owned by
  `dev`, so `dev` can change every file but cannot replace the tree itself.
  `/app/PROGRESS.md` is created for `dev`; `/opt/restore` is read-only except
  `var/`, where `restore` keeps its delivered-form copy and its state.

## Design dimensions

### Novelty

What it adds: one coherent body of work that is too large for one context window
(2,671 units, 37,645 lines) with a grade per unit, so partial progress is
measured exactly.

Closest comparisons:

- SWE-Marathon v1 `rust-c-compiler`, `zstd-decoder`, `wasm-simd`: build a system
  to pass a conformance suite. Same family (new code matched to a reference).
  This task differs in that the code base already exists and the work is spread
  over thousands of small units instead of one design.
- Commit0 (public): implement a library from its specification and tests.
  Overlap is high. Differences: bodies are graded one by one, hidden replayed
  calls decide correctness, and a third of the tests are withheld.
- Deep SWE, Frontier SWE, Multi-Step SWE: not compared. Unverified.
- Tasks in this repository: no overlap with `knowledge-work-assistant`,
  `titans-training` or `battle-royale`.

Weaknesses, stated plainly:

- SymPy is public and in pre-training data. Measured on the best run (base trial
  5): 546 of 2,671 submitted bodies (20.4%) have the same syntax tree as upstream.
  By size of the original body: 1 to 3 lines 51.6% of 893 units, 4 to 10 lines
  9.1% of 792, 11 to 30 lines 1.8% of 721, over 30 lines 0% of 265. So verbatim
  recall is concentrated in trivial bodies. This does not measure how much
  knowing SymPy's behaviour helps with the rest.
- A third of the units are one to three lines. The task is long but shallow.
- A reviewer raised both points on 2026-11-17. They stand.

Next validation: rebuild on a library published after the models' cutoff and drop
units under about four lines, then repeat the identity measurement.

### Verifiability

Every unit has examples in its own docstring and at least one recorded call whose
reference result comes from the original implementation. Results are counts over
fixed lists, so partial progress needs no judge. See [Verification](#verification).

Evidence: reference solution scores 2,671 / 13,384 / 10,428; no-op scores 0.
Grading the same submission three times gave 2,569, 2,569 and 2,570 passing units
and 9,533, 9,534 and 9,534 passing tests, so run-to-run variation is one unit and
one test. Uncertainty: which unit flips, and why, is not yet identified.

### Realism

Restoring lost implementation from signatures, documentation and tests is real
but uncommon work (damaged checkouts, partial ports, code removed for licensing).
The setting is contrived in one respect: nobody loses 2,671 bodies at once while
keeping every docstring. Realism is the weakest of the five dimensions together
with novelty.

### Difficulty

Where runs fail (base experiment, nine model trials, all reward 0):

- Length. Single-context runs stopped at 588 to 1,824 steps when their 1M-token
  context filled. Only a harness that compacts and delegates reached the end:
  15,678, 38,586 and 45,324 steps in 9 hours.
- Stopping early. One run submitted at 1,001 steps after judging the thresholds
  out of reach. Two runs ended their turn while their helper agents were working.
- The last few percent. The best run restored every unit and passed 96.2% of
  them; 38 failed their own examples and 63 passed their examples but matched no
  hidden call. Failures cluster in physics, combinatorics, stats and polys.

The difficulty is breadth and bookkeeping, not depth. Helpers can split the work.

The same pattern held on the v2 bundle (2026-11-17): `claude-code` with helper
agents took 17,653 to 38,283 steps and passed 92.2% to 95.7% of units; Proximus,
which works in one thread and hands over between context windows, took 1,525 to
5,156 steps and passed 25% to 50%.

### Initial feasibility

Solved by construction: the original source is the reference solution and passes
all three measurements. For an agent, 9 hours was not enough for 99% of units
with either model tried.

## Workload

v2 asks for at least five days of agent execution. This task does not meet that.
Since 2026-11-19 a trial is one 12-hour session. With the earlier 9-hour limit the
best run used all of it at about 4,300 steps per hour and reached 96.2% of units;
one 12-hour session reached 82.3% at best; two 48-hour sessions (19.2 hours)
reached 2,568 of 2,671 units at best (experiment `sympy-restoration-v2-48h-20261117`).

How the 48 hours ran (retired on 2026-11-19 in favour of the single 12-hour
session; kept for the record). Oddish ends an attempt after 12 hours, grading included,
and does not compare a task's limit with that, so a 48-hour agent limit in one
trial would end ungraded. The agent limit in `task.toml` is therefore one
working session of 9.6 hours, and five sessions make the budget:

- Session 1 is the task as it is. A later session is the same task with
  `/app/sympy` starting from the unit files the previous session delivered (the
  verifier's `candidate_unit_files.tar.gz`) and with `/app/timer.sh` counting
  the time already used. `scripts/package_session.py` stages it under its own
  task name.
- The instruction is identical in every session. It gives 48 hours and says that
  a session can end at any moment and that only delivered unit bodies carry
  over. It does not state the session length.
- Every session is graded by the same verifier. The last session's reward is the
  48-hour result; the earlier ones are progress points.
- A harness that states its own time budget (Proximus) states the session's.

Not yet designed, listed as options and not as decisions:

- Follow-up steps that build on the restored library, for example a behaviour
  change that must be applied across the restored code, or a port of a restored
  subsystem. Each needs its own instruction written by the author.
- A larger and deeper unit set on a library the models have not seen.

## Verification

The verifier runs in a separate image with only `/app/sympy` from the candidate.

0. Delivery (`verifier/delivery.py`). The work runs as `dev`. When it ends, the
   collect step (`environment/fsmaint-sweep`, root) freezes and ends every
   process of `dev`, records every entry under `/app/sympy` (type, size,
   modification and change times, sha256) before touching anything, removes
   what a copy cannot carry (pipes, sockets, links leading outside), probes
   whether public hosts answer, and writes a record and a mark into the tree.
   The mark is signed with a key in the agent image that only root can read and
   that the verifier image holds too. Before grading, the verifier checks that
   its own network is closed (a TLS handshake to three public hosts; open is an
   evaluation error), then reads the mark: no tree, no mark, an unreadable or
   unsigned mark, a record that differs from the signed one, or a listed file
   that did not arrive as listed is an evaluation error (no reward file); a tree
   the collect step refused (over 200,000 entries or 2 GB) or found absent is a
   completed evaluation of an empty delivery. The end of the work is the last
   poll in which no public host answered, as `fsmaint-netcheck` recorded it, or
   the collect step's own start when the net check saw no opening. A unit file
   whose change or modification time is at or after that bound, less 0.25 s, is
   not taken over: its units are `late` and count as not restored.
   `late_files`, `egress_open` and the collect step's record go to
   `metrics.json`.
1. Graded tree. Start from the reference skeleton. For each unit, copy in the body
   found in the submitted file for the function of the same qualified name.
   Nothing else from the submission is used. A body containing constructs for
   reaching the process, the file system, the interpreter or a test framework is
   rejected (`common/restorelib.py`).
   The whole measurement has one deadline, 6,000 s from its start
   (`measure_budget_sec`), inside the verifier's 6,600 s. The docstring and call
   phases also have their own caps; the test phase has what they leave. Every
   deadline is on the monotonic clock. Submitted code runs with a 4 GiB
   address-space limit where `prlimit` can set one (a note says when it cannot).
2. Docstring examples. Each restored unit's own examples, run the way SymPy's
   doctest runner runs them, 20 seconds per unit, at most 30 minutes in total.
   Python's and both of SymPy's random generators are seeded from the unit's name
   before its examples run, so a unit's draw is the same in every grading (and in
   `restore check`). One process runs the units of one module, watched: 2 minutes
   to import, then at most 50 seconds without a record. A unit's result counts
   only when its process reached its own closing self-check. When a process ends,
   or stops, without it, the unit it was running fails (`crash`, or `timeout` when
   it stopped) and the rest of the module runs again in a new process, at most
   eight times per module; after a unit that ran out of time the runner checks
   itself and exits, and the units behind it run in a new process, since an
   interrupted body can leave global state behind. Units left when the time is
   up count as not reached.
3. Recorded calls. 13,384 calls, at least one per unit, replayed one at a time in
   the sandbox with a 10-second limit, at most 20 minutes in total. The sandbox
   writes the result; the verifier compares it with the reference result, which
   the sandbox cannot read. Arguments were recorded from SymPy's own test suite
   and, for units it never calls directly, from docstring examples. One process
   replays the calls of one module. If it ends by itself or stays silent for 40
   seconds, the call it was on does not match and the calls behind it are
   replayed in a new process; if not even the first call of that start returned,
   the rest of that call's unit does not match either and the job resumes at the
   next unit. After a call that ran out of time the runner exits and the calls
   behind it run in a new process. A job ends after 16 starts that ended or
   stopped. The random generators (Python's and both of SymPy's) are seeded from
   the call id before every call, so one tree gives the same result each time it
   is graded.
4. Repository tests. 10,428 upstream test cases that pass on the original and
   fail or cannot be collected on the skeleton, each under 8 seconds on the
   original. 7,896 are in the candidate's tree, 2,532 are withheld. 60 seconds
   per test, 40 minutes in total. The tests first run in one pytest session with
   four workers. A session can lose tests that say nothing about the submission:
   an import that never returns blocks collection for every file, and a timeout
   that fires inside pytest's own reporting code ends a worker or the session.
   So a session that starts no test within 10 minutes, or reports nothing for 3
   minutes once tests run, is ended, and every test the session did not finish
   is run again with one process per test file (2 minutes to start its first
   test), where a hang or a crash costs only that file. A file is tried again
   only while it keeps settling tests, never once pytest has reported it as
   uncollectable, and at most four times. A test that was running when its run
   ended gets one more run; left unfinished twice, or named by a session as the
   test that ended it, it counts as failed. All of this stays inside the time the
   measurement has left; a test without an outcome then is not reached, and is
   reported as such.

Submitted code runs only as user `nobody`, which cannot read the verifier code,
the private inputs, the submitted tree or the output directory. While examples
and calls run, the tree the sandbox sees has no test directories.

Where expected values come from: the original SymPy 1.14.0 implementation.
Limits: a recorded call checks one input, so a body can match its calls and still
be wrong elsewhere; reference results that could not be reproduced exactly
(objects that lose state when pickled, bare `None`, exceptions, unstable
ordering) were dropped at build time, which removes those behaviours from the
measurement.

Requirement checks (`steps/01-restore-bodies/tests/verifier/registry.py`):

| Check | Requirement in the instruction | Evidence |
| --- | --- | --- |
| `candidate_tree` | `/app/sympy` exists and at least one unit is restored | unit states from the graded tree |
| `unit_restoration` | at least 99% of units pass | examples pass and one recorded call matches |
| `reference_calls` | at least 90% of replayed calls match | structural comparison with reference results |
| `repository_tests` | at least 95% of graded tests pass | per-test outcomes, cross-checked in every pytest run with that run's own tally |
| `measurement_integrity` | the measurement is not interfered with | control items with known outcomes in each runner |

All five read one measurement pass (`verifier/engine.py`).

### Reward formula

```
unit_pass_rate  = units_passing   / 2671
call_match_rate = calls_matching  / 13384
test_pass_rate  = tests_passing   / 10428

reward = 1  if candidate_tree passed
            and unit_pass_rate  >= 0.99
            and call_match_rate >= 0.90
            and test_pass_rate  >= 0.95
            and measurement_integrity passed
         0  otherwise

partial_score = (units_passing + calls_matching + tests_passing) / 26483
```

- Reward is binary. A library with 4% of its functions wrong is not a usable
  restoration, so there is no credit for it in the reward; `partial_score` and the
  three shares in `metrics.json` carry the progress signal for analysis.
- Denominators are fixed. A unit that is not restored, a skipped or errored test:
  each counts as failed. Units, calls and tests not reached before the deadline
  are counted in `metrics.json` (`units_not_reached`, `vectors_not_reached`,
  `tests_not_reached`); when every other condition is met and a missed bar would
  be met if those items passed, the time, not the submission, would decide, so
  the evaluation ends with an error and no reward.
- A tree that did not arrive, or arrived without the collect step's signed mark
  or not as the mark lists it, is an evaluation error. A delivery the collect
  step refused or found absent, or a tree with no restored unit, fails
  `candidate_tree`; the other checks are skipped and the reward is 0.
- An evaluation error leaves no reward file. `verify.py` exits 1 and
  `report.json` has `status: evaluation_error`.
- One step. `multi_step_reward_strategy = "final"`; with a single step the
  trial reward is this step's reward.
- Thresholds are in `verifier/grade_config.json` and in the instruction.
- Implementation: `verifier/scoring.py`. Boundary tests: `checks/test_scoring.py`
  (exactly at each threshold, one below each, tripped control, missing work) and
  `checks/test_evaluation_errors.py`.

The 99% unit threshold leaves room for 26 units. The thresholds were set before
any model trial and have not been tuned to results.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / MEDIUM (findings 1 and 9: the hooks
have not yet run on the platform). Unassessed boundaries: finding 7.

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A body runs arbitrary code at grading time (for example through `sympify` of a string) and patches the example and test runners in-process, forging those two measurements | Sandbox process | Executed in red-team round 2 | Every unit needs a recorded call whose result is compared by the root process with references the sandbox cannot read; 90% of all calls must match | With constant stubs for units whose references are `True`, `False`, `0`, `1` or an empty list, at most 501 units (18.8%) could be left unrestored, and only by guessing each constant | Replace the self-reported example result with a root-side comparison | 🟡 YELLOW / MEDIUM |
| 2 | Read reference results or the withheld tests | File permissions in the verifier image | Attempted in both rounds; not reached | Private inputs readable by root only; sandbox runs as `nobody`; no test directories in the tree during phases 2 and 3 | Depends on the privilege drop | Re-run on the v2 bundle | 🟢 GREEN / LOW |
| 3 | Edit tests, module-level code or other functions to make checks pass | Graded-tree construction | Executed; no effect | Only unit bodies are copied into the reference skeleton; `checks/test_transplant.py` | None found | Keep the check | 🟢 GREEN / LOW |
| 4 | Return the documented example outputs for the documented inputs | Unit pass rule | Base trial 5: 63 units pass their examples and match no hidden call; six were read and are honest wrong attempts | A unit needs a matching hidden call | A unit with one easy call can pass with a partial body | More calls per unit | 🟢 GREEN / LOW |
| 5 | Change how a runner reports results | Runner control items | Executed in round 1 through module-level `os`/`sys`; fixed | Control items with known outcomes in every pytest run; the records of a run cannot hold more passes than that run's tally; forbidden constructs in bodies. Forged start or collection records can only remove tests from later runs, which lowers the score | A forgery that also gets the controls right falls under finding 1. The per-file runs added on 2026-11-17 have not been attacked | With finding 1 | 🟢 GREEN / LOW |
| 6 | Tamper with reward or result files | Separate verifier container | By design; not attacked | Verifier starts fresh with only `/app/sympy`; output directory closed to the sandbox user | None found | Attack on the v2 bundle | 🟢 GREEN / LOW |
| 7 | Anything that depends on the new entry point, check registry or reporting | v2 verifier code | Not attacked | Same measurement code as v1; reference and no-op baselines on the v2 bundle | Unknown | Red-team run against the v2 bundle | 🟡 YELLOW / UNASSESSED |
| 8 | Reach the network during the work phase to fetch SymPy | Agent network policy | Probe task, 2026-11-15: PyPI and GitHub unreachable from the work phase; 217 in-work fetch attempts in one 12-hour run all failed (TCP connected, TLS did not) | `[agent] network_mode = "no-network"`; the instruction forbids another copy; SymPy is not installed elsewhere; the image's attribution names no download | Agent tooling is installed at setup with public egress; host-name filtering not probed for every route | Probe the routes as `dev` | 🟡 YELLOW / MEDIUM |
| 9 | Leave a process running after the work that fetches SymPy once public egress returns (about 0.2 s after the work ends, before collection: 0.8 s and 11.8 s on two 12-hour runs) and writes the original into `/app/sympy`; the original scores 1.0 | Delivery: user, hooks, record | Reproduced by review with the verifier's own transplant before this change (2,671 restored, a tree identical to the reference) | The work runs as `dev`; the net check ends `dev`'s processes on the first open poll and records the end; the collect step freezes and ends the rest and records every file's change time before touching anything; the verifier takes no unit file changed at or after the end; the mark is signed with a key `dev` cannot read; a missing or short delivery is an evaluation error | A write through a file mapping opened before the end changes content without moving its times; if the net check never sees the opening (no host resolved at setup, or its probe answered during the work), the bound is the collect step's start, after the window, and only `metrics.json` shows it (`end_from`, `egress_open`) | Canary on the platform: a detached fetch-and-overwrite loop scores 0 with its files `late`; reference 1.0 and no-op 0.0 with the record present | 🟡 YELLOW / MEDIUM |

Recall of SymPy from pre-training is not an exploit of the verifier, but it limits
what a high score means. It is recorded under [Novelty](#novelty).

## Trial evidence

Base experiment, v1 package, 2026-11-16. Bars: 99% units, 90% calls, 95% tests.

| Trial | Agent and model | Agent time | Steps | Units passing | Calls | Tests | Reward |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | claude-code, relace/deepseek-v4.1-flash | 9.00 h | 45,324 | 2,563 (96.0%) | 92.3% | 90.6% | 0 |
| 5 | claude-code, relace/deepseek-v4.1-flash | 9.00 h | 38,586 | 2,570 (96.2%) | 92.3% | 91.4% | 0 |
| 7 | claude-code, relace/glm-5.3 | 9.00 h | 15,678 | 2,100 (78.6%) | 78.4% | 75.6% | 0 |
| 14 | mini-swe-agent, relace/deepseek-v4.1-flash | 2.47 h | 1,824 | 716 | 25.5% | 12.0% | 0 |
| 15 | mini-swe-agent, relace/glm-5.3 | 3.41 h | 588 | 346 | 13.1% | 19.7% | 0 |
| 10 | mini-swe-agent, relace/glm-5.3 | 3.77 h | 817 | 274 | 10.3% | 17.3% | 0 |
| 9 | mini-swe-agent, relace/deepseek-v4.1-flash | 1.13 h | 1,001 | 334 | 18.2% | 19.1% | 0 |
| 13 | claude-code, relace/glm-5.3 | 0.68 h | 847 | 15 | 0.7% | 0.7% | 0 |
| 8 | claude-code, relace/glm-5.3 | 0.28 h | 777 | 63 | 4.1% | 0.9% | 0 |

Trials 10, 14 and 15 ended on the context limit. Trial 9 submitted by choice.
Trials 8 and 13 ended their turn with helper agents still running. On trial 6 the
test phase hit its 40-minute budget with 83 tests not reached; the outcome did
not depend on them.

v2 experiment `sympy-restoration-v2-final-20261117`
(https://www.oddish.app/experiments/0b7a142f), 2026-11-17. Trials 16 to 18 ran on
bundle `8180b51500b1`; trials 6 to 8 on the single-step variant, bundle
`36876c6104ab`, which Proximus needs. Same bars.

| Trial | Agent and model | Agent time | Steps | Units passing | Calls | Tests | Reward |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | claude-code, relace/deepseek-v4.1-flash | 9.00 h | 37,373 | 2,557 (95.7%) | 92.4% | 90.1% | 0 |
| 17 | claude-code, relace/deepseek-v4.1-flash | 9.00 h | 38,283 | 2,481 (92.9%) | 91.7% | 71.5% as graded | 0 |
| 18 | claude-code, relace/glm-5.3 | 9.00 h | 17,653 | 2,462 (92.2%) | 89.4% | 88.4% | 0 |
| single 6 | proximus, relace/deepseek-v4.1-flash | 8.72 h | 3,690 | 1,077 (40.3%) | 39.1% | 0% as graded | 0 |
| single 7 | proximus, relace/deepseek-v4.1-flash | 8.93 h | 4,244 | 915 (34.3%) | 35.2% | 35.0% | 0 |
| single 8 | proximus, relace/glm-5.3 | 6.47 h | 1,525 | 992 (37.1%) | 34.5% | 30.7% | 0 |

Proximus on the v1 package, base experiment, 2026-11-17:

| Trial | Agent and model | Agent time | Steps | Units passing | Calls | Tests | Reward |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 23 | proximus, relace/deepseek-v4.1-flash | 8.73 h | 5,156 | 1,325 (49.6%) | 46.2% | 45.3% | 0 |
| 24 | proximus, relace/deepseek-v4.1-flash | 8.81 h | 2,977 | 679 (25.4%) | 30.6% | 29.8% | 0 |

- No trial tripped a control item.
- Trial 16: the test phase hit its 40-minute budget with 47 tests not reached;
  the outcome did not depend on them. Trial 18 left 78 units unrestored at the
  time limit.
- Trial 17: the test session ended early (see the development log) and 2,267
  tests were not started. With all of them passing the share would have been
  93.2%, still under the bar. Graded again with the session restarted for the
  unfinished tests (an intermediate form of the fix): 2,481 units and 12,270
  calls as before, 9,291 tests (89.1%), none unreached.
- Single-step trial 6: the test session reported nothing in 40 minutes and every
  test counted as not reached. Units and calls are unaffected.
- Single-step trial 8 submitted after 6.47 hours, stating that the remaining
  units were blocked.
- Base trial 24 removed every placeholder; 505 of its bodies only return a
  constant and 504 of those failed. Removing placeholders earned nothing.
- Proximus reports no cost. Its runs used 0.66 to 2.19 billion input tokens,
  over 99% of them cached.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (35 tests) | working tree, 2026-11-17 and 2026-11-19 | pass |
| `checks/` (50 tests): delivery hooks under dash with stand-ins, a late write refused, an honest delivery taken, every failing mark an evaluation error, the net check's arming and handshake probe | working tree, 2026-11-20 (delivery) | pass; the hooks have not run on the platform |
| `checks/` (61 tests): the real docstring runner and driver on a stand-in package (a death, a silent block and a timeout each cost one unit; a seeded draw passes twice; an import that never finishes fails its module in one start; a run that dies after its last unit counts nothing; a used-up budget gives a row per unit; `measure()` completes through it; `restore check` fails only the culprit), call replay (a barren start costs only its unit; a timeout restarts behind it; a hung import ends the job in one start), one deadline under the verifier limit, an unreached verdict is an evaluation error, the address-space limit and its fallback | working tree, 2026-11-20 (verifier robustness) | pass |
| Rewritten runners and drivers on real SymPy (Python 3.12, no sandbox) | original tree: `combinatorics.permutations` and `combinatorics.group_numbers`; a stored submission: `group_numbers` twice, `ntheory.generate`, `ntheory.residue_ntheory`, `polys.euclidtools` | original: 62 / 62 units, 287 / 287 calls; submission: identical statuses in both runs, 48 pass and 22 fail with no lost unit |
| `oddish preflight` | bundles `e043dc4facdd` and `8180b51500b1` | pass |
| Reference and no-op baselines on Oddish | bundle `e043dc4facdd` (v1 instruction text, v2 verifier), task version 1, experiment `sympy-restoration-v2-20261117` | reference 1.0 twice (2,671 / 13,384 / 10,428, five checks passed, grading 652 s and 691 s); no-op 0.0 twice (`candidate_tree` failed, four checks skipped, report `completed`) |
| Reference and no-op baselines on Oddish | bundle `8180b51500b1` (rewritten instruction and tool text), task version 2, experiment `sympy-restoration-v2-final-20261117` (https://www.oddish.app/experiments/0b7a142f) | reference 1.0 twice (trials 9, 10: 2,671 / 13,384 / 10,428, five checks passed, grading 658 s and 649 s); no-op 0.0 twice (trials 11, 12). A first attempt at 04:47 UTC targeted the version-1 experiment and created no trials |
| Model trials on Oddish | task version 2, same experiment | trials 16, 17 (claude-code, relace/deepseek-v4.1-flash) and 18 (claude-code, relace/glm-5.3): all reward 0, see [Trial evidence](#trial-evidence) |
| Single-step variant on Oddish | bundle `36876c6104ab`, task `...sympy-restoration-single-6949ef06` version 1, same experiment | reference 1.0 twice (trials 1, 2: 2,671 / 13,384 / 10,428); no-op 0.0 twice (trials 3, 4). Proximus trials 6, 7 (relace/deepseek-v4.1-flash) and 8 (relace/glm-5.3): all reward 0 |
| Regrade of a known partial submission | trial 17's submission, bundle `8c08c076142a` (session restarted for unfinished tests), task `...-regrade-t17-a3369a0f` version 1, experiment `sympy-restoration-v2-regrade-20261117` (https://www.oddish.app/experiments/2ce5306f) | reward 0; 2,481 units and 12,270 calls, identical to the original grade; 9,291 of 10,428 tests with none unreached (7,453 with 2,267 unreached before); four sessions, test phase 1,304 s |
| Sealed test phase against real pytest | working tree, pytest 9.2.0, xdist 3.8.0, timeout 2.4.0, synthetic tree | timeout inside report building: the session alone settles 116 of 120 tests, the phase settles 120 and fails the stalling test. Import that never returns: the session settles nothing, the phase settles every test outside that file |
| Final verifier: reference and no-op baselines | task version 3 (bundle `ab35032fedbc`) and single-step version 2 (bundle `d89ad18c1671`), experiment `sympy-restoration-v2-grader3-20261117` (https://www.oddish.app/experiments/184f3cb6) | reference 1.0 four times (2,671 / 13,384 / 10,428, one pytest run each, first test 90 to 115 s after the phase starts); no-op 0.0 four times |
| Final verifier: two grades of one stored submission | trial 17's submission (`...-regrade-t17-a3369a0f` version 3) and single-step trial 6's (`...-regrade-p6-2f6816d9` version 2), same experiment | trial 17: 2,481 units and 12,270 calls in both grades, as in the original grade; 9,298 and 9,305 tests, none unreached (7,453 with 2,267 unreached originally). Trial 6: both grades identical, 1,077 units, 5,227 calls, 3,002 tests with 8,646 settled (0 of 10,428 originally); one test file, `sympy/physics/quantum/tests/test_represent.py`, never finishes importing and had blocked the whole session. All reward 0 |
| 48-hour session 1: reference and no-op baselines | bundle `6d30d72c0afb`, task `...-48h-s1-6519a8c3` version 1, experiment `sympy-restoration-v2-48h-20261117` (https://www.oddish.app/experiments/ebb4e086) | reference 1.0 twice (trials 1, 2), no-op 0.0 twice (trials 3, 4). Model trials 6 to 11 (session 1 of six runs) started 2026-11-17 17:07 UTC |
| 48-hour runs after two sessions (19.2 h) | session 1 on `...-48h-s1-6519a8c3`; session 2 on one continuation task per run (`...-48h-<run>-s2-...`), same experiment; each session-2 no-op repeated its session-1 unit count exactly | all reward 0. Units passing, session 1 -> 2: cc-deepseek-a 2,375 -> 2,568; cc-deepseek-b 2,338 -> 2,494; cc-glm-a 1,976 -> 2,535; px-deepseek-a 1,159 -> 1,590; px-deepseek-b 1,289 -> 1,723; px-glm-a 1,031 -> 1,509 (of 2,671). Hidden tests passing after session 2: 9,693 / 9,009 / 9,603 / 5,584 / 6,231 / 5,473 (of 10,428). Held after session 2: the owner wants every experiment to be one task row, so no further continuation tasks without his word |
| 12-hour single session | `...-48h-s1-6519a8c3` version 2, experiment ebb4e086, 2026-11-19; the same files under the task's own name as `...-66d29774` version 4 | reference 1.0 twice, no-op 0.0 twice; six model trials all reward 0: claude-code 82.3%, 51.8% and 51.3% of units at the 9.6 h limit, Proximus 48.1%, 46.9% and 40.2%. Version 4: pre-trial audit one must-fix (the `task.toml` comment), fixed in this commit for version 5 |
| `harbor check` with `resources/task-implementation.toml` | working tree, 2026-11-17 | attempted on Modal; failed before review with `NotFoundError: Environment not found` (no default Modal environment). Not run in local Docker. No ratings |
| Local image builds | none | not run for the v2 Dockerfiles; the Oddish baselines are the first build |

## Build and deliver

Prepared inputs are not in Git. They were produced on 2026-11-16 by the scripts
now in `scripts/builder/` (unit selection, twin scan, recorded calls and their
re-checks, sealed tests) and a final staging script that still lives with the v1
package and has not been ported. Until it is, the prepared inputs can only be
copied from an existing build.

With prepared inputs in place:

```bash
cd tasks/swe-m2-scientific-computing/sympy-restoration/scripts
python package_step.py            # writes experiment/dist/bundles/<hash>/<task slug>/
oddish preflight ../experiment/dist/bundles/<hash>/swe-m2_scientific-computing_sympy-restoration
```

`oddish upload <bundle>` followed by `oddish run --task <id>` was used on
2026-11-17 because `oddish run <bundle>` failed with a database error when
creating a new task.

Other bundles, all from the same sources:

```bash
python package_single_step.py                 # same content without the steps wrapper (Proximus)
python package_session.py --session 1         # 48-hour chain, retired 2026-11-19: refused on the 12-hour timer
python package_session.py --session 2 --chain <run> --archive <candidate_unit_files.tar.gz>
python package_regrade.py <candidate_unit_files.tar.gz> --label <name>   # grade a stored submission again
```

Development checks:

```bash
uv run --frozen pytest -q tasks/swe-m2-scientific-computing/sympy-restoration/checks
```

## Remaining work

- The 48-hour chain is retired (2026-11-18 and 19): one task row per experiment,
  one 12-hour session per trial. The six held runs stay as history in experiment
  ebb4e086.
- Apply the same change to the v1 package's `grade.py` if that package is used
  again.
- Run `harbor check` with the v2 rubric and record ratings with the task-rating
  skill.
- Port the staging script that writes the prepared inputs, so a clean checkout
  can rebuild them.
- Decide the follow-up steps and the unit set (see [Workload](#workload) and
  [Novelty](#novelty)). Until then the task is below the v2 workload bar.
- Red-team the v2 bundle (findings 7 and 8).
- Run the delivery hooks on the platform before any model trial (finding 9): a
  canary whose reference leaves a detached fetch-and-overwrite loop must score 0
  with its files `late`; the reference and the no-op twice each with the record
  present; claude-code and Proximus must start and work as `dev`; the flat
  single-step bundle must run the hooks. If the net check's probe does not see
  the opening there, certify copies taken while egress was closed instead.
- Proximus on Oddish cannot run a task that declares steps; either it learns to
  run a one-step task or every v2 task needs a single-step variant.
