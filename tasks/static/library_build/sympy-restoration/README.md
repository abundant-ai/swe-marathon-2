# SymPy restoration

Author notes. Nothing in this file is shipped to the candidate or to either image.

SymPy 1.14.0 with the bodies of 2,115 functions and methods in 323 files removed
(32,217 non-blank lines of body). Signatures, decorators, docstrings and all other
code stay. The candidate writes the bodies back, without network access, using a
small `restore` command that reports progress and checks work against the graded
view. The reward is continuous: the smaller of two shares measured on recorded
calls that nothing visible answers (no docstring example or visible test makes
them, even with its symbols renamed, and their result is neither a result their
unit's examples and tests show, nor a documented result of their unit, nor one
of their own arguments; see [Reward formula](#reward-formula)).

This is a pilot brought over from a v1-style task. It has one implemented step,
run as one working session inside Oddish's 12-hour attempt (the agent's limit is
34,560 s; since 2026-11-24 the instruction states no time figure; the 48-hour
chain of sessions it replaced is described under [Workload](#workload)).
It does not yet meet the v2 workload target; see [Workload](#workload) and
[Remaining work](#remaining-work).

## Development log

### 2026-11-25

Moved the single brief, verifier and solution to the task root. Harbor reads the
agent and verifier settings from the root configuration.

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
  no state file (both gone since 2026-11-24: the instruction states no time
  figure and the image has no timer; see that day's entry). Ran first as version 2 of the `-48h-s1` task row: six model
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
  total and the agent limit agree. 35 checks pass. (Since 2026-11-24 the image
  has no timer: the packager refuses for that reason, and the check asserts
  that no time figure is stated.)

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
- Comparison. The recorded-call comparison failed bodies that behave exactly as
  the original on state that is not behaviour. Five units matched none of their
  calls with a body that returns the same object and leaves a lazily filled cache
  empty (`PrimeIdeal.as_submodule`, `round_two`, `restrict_codomain`,
  `homomorphism`, `FreeModule.identity_hom`); a correct `Truss.remove_node`
  failed on a private list in which upstream drops the wrong entry; strings were
  compared exactly while examples are checked with whitespace normalised; and a
  symbol made with `commutative=True` spelled out differed from the same symbol
  without it, though SymPy calls them equal. The canonical form now leaves out
  memo slots (fifteen named attributes), `ReferenceFrame.index` (a process-wide
  counter) and Truss's two parallel coordinate lists; symbols carry the
  assumptions SymPy's equality uses; dense and sparse domain matrices compare by
  shape, domain and entries; strings compare with runs of whitespace as one, as
  the examples do. Every reference result was recorded again with the new form
  (`scripts/builder/regold.py`): the original reproduces 13,382 calls under three
  hash seeds and the skeleton none; two calls whose results outgrew the
  runner's 400 kB line under the new form were dropped (their units keep other
  calls). Re-checked with bodies that behave as the original: the five units
  match 3/3, 8/8, 8/8, 8/8 and 3/3 calls (0 before), `remove_node` by index 1/1
  (0 before). `multiline_latex` from its docstring still matches 0 of 6: upstream
  writes `&- a` for a negative first term, a spacing difference the examples'
  own rule also sees, which no docstring or visible test shows.
- Reward. The binary reward's 99% unit bar sat above a floor of failures no
  visible check shows (39 to 77 units per measured run against 26 allowed), so
  35 of 35 graded sessions scored 0 against pooled partial scores of 0.01 to 0.92
  and the reward ranked nothing. A three-judge panel chose a continuous reward,
  unanimously: min(u, c) over the calls whose arguments no docstring example or
  visible test uses, gated by the delivered tree and the controls. Built here:
  every recorded call was checked against what the visible docstrings and tests
  call at run time (`scripts/builder/documented.py`, directly and inside the
  library): 9,094 of 13,382 repeat one. Calls whose result is one their unit
  returns for a documented call count as documented too, since a table of
  documented outputs could return it (323 more). That left 1,633 units without a
  counted call; for them, 15,164 calls were recorded while the
  withheld tests ran (`rec_withheld.py`) and 18,601 variants made from
  their own arguments (`variants.py make`), screened on the original under three
  hash seeds and on the skeleton (`variants.py screen`), checked against the
  visible run in the same way, and up to four per unit added (`variants.py
  select`): 3,784 calls for 1,045 units. 630 units still have none
  and leave the unit set, counted. Unnamed Dummies are now compared without the
  counter in their names (30 recorded results depended on it). Every result was
  recorded again with the final comparison (`regold.py`): the original
  reproduces 17,166 of 17,166 under three hash seeds, the skeleton none. Today's
  three bars stay in `metrics.json` as `complete`; the tests are reported, not
  rewarded; `partial_score` is gone; `reward_type = "continuous"`. Floor
  (`floor.py`): the documented-output table with a documented fallback scores
  0.0, so a unit needs only one matching counted call (the rule of half its
  counted calls held in reserve is not needed); the after-the-fact
  best constant 0.060. Through the entry point's steps on this machine
  (no privilege drop): reference 1.0, empty delivery 0.0, bare `raise
  NotImplementedError` bodies 0.0.
- Instruction. "Complete" was met at reward 0 and "every other valid input" left
  out the errors 326 graded withheld test ids assert. A right body is now one
  that cannot be told apart from SymPy 1.14.0's for every argument, including the
  error it raises for one it does not accept, down to type, container, order,
  form and object state; the work is complete when no function can be told
  apart, and the visible checks are named as the least of that. `restore status`
  says the examples passed, not the units.
- Regrade. 16 stored submissions graded again with this verifier on this
  machine (examples and calls; the tests are not rewarded): rewards from 0.003 to
  0.897 (claude-code with helpers over a whole session 0.71 to 0.90, two
  claude-code runs that ended their turn within 41 minutes 0.024 and 0.003,
  Proximus 0.32 to 0.42, mini-swe-agent 0.09 to 0.22), in the order of their old
  unit counts,
  against 0 for every one under the binary reward. See [Trial
  evidence](#trial-evidence).
- Re-check of the round above, delivery. The net check armed only after 600
  closed polls (a minute or more), so a turn shorter than that left no end, and
  a SymPy 1.14.0 written after such a turn was taken whole; and a directory link
  let a file written after the end be graded under a unit file's name. The net
  check now counts closed polls from its first poll, records the end of every
  stretch of at least three that an answering poll ends, ends `dev` each time
  and keeps polling, so a stretch during setup cannot end the watch. The collect
  step probes the hosts itself, lets the net check finish one poll after `dev`
  has ended, takes the end of the longest such stretch (its own start only when
  that stretch was still going on and its probe found the hosts closed), and
  otherwise records no end, which the verifier turns into an evaluation error.
  Every link is removed before the copy; a link or an unlisted file that
  arrives anyway is an evaluation error, and the transplant reads no unit file
  through a link. The reference solution waits 10 s, so a few closed polls fall
  inside even its turn. The net check's settings are fixed in the file, no
  longer read from the environment. Checks: a 3-second turn has its end and a
  write 0.6 s after it is refused; each way the end can be unknown is an error,
  the two ways the hosts can be shown closed are graded; file and directory
  links planted during the work, with the files behind them written after it,
  deliver nothing.
- Re-check, comparison. Two rules of the round above accepted wrong answers:
  strings compared with runs of whitespace as one (a `pprint_nodes` that prints
  the tree on one line matched its three counted calls), and every unnamed
  Dummy compared as one token (a `bivariate_type` with its two coefficients
  swapped matched all eight). Strings now compare exactly, except the LaTeX of
  `multiline_latex` and `vlatex`, compared without the whitespace LaTeX
  ignores; a Dummy that came with the call's arguments keeps its name and
  index, Dummies the call makes compare up to one consistent renaming, and a
  Dummy carries its assumptions as a symbol does. The other relaxations of that
  round were probed with a wrong answer each and narrowed where one got through:
  a memo slot counts where both sides hold a value (a wrong pre-set flag in
  `PrimeIdeal.as_submodule` or `round_two` matched before); Truss's parallel
  lists count except in what `remove_node` leaves (an `add_node` that stopped
  keeping them matched 4/4); storage counts for the 24 converters and
  constructors whose result is that storage (dense results of `DDM.to_sdm` and
  `DomainMatrix.to_sparse` matched), and a zero stored in sparse storage always
  counts; a frame's creation counter, which orders a vector's printed
  components, is exact for a frame that came with the arguments and
  order-preserving for frames the call makes (a state-identical copy of a given
  frame matched before). Symbol keywords stay compared as SymPy's own equality
  compares them, so dropping an assumption is told apart. Every reference result
  was recorded again: the original reproduces 17,166 of 17,166 under three hash
  seeds, the skeleton none; 1,424 results changed form. Probes through the
  verifier's own runners: the wrong bodies match none of their counted calls (one
  `disambiguate` call has no assumption to drop and still matches), the bodies
  phase 3 made pass still pass, and `multiline_latex` written from its docstring
  now matches 6 of 6 (0 before).
- Re-check, floor and calls. Bodies that restore nothing reached 0.07 to 0.12
  behind a table of documented outputs, against the decision's 0.05: a fallback
  returning the first argument matched 538 counted calls, a table renaming a
  documented call's symbols answered 322 (316 of them variants added in the round
  above), and flipping a predicate's only documented boolean matched more. Two
  kinds of call are now documented too: calls a docstring example or visible test
  makes up to a renaming of symbols that keeps their assumptions, and calls whose
  result is one of their own arguments unchanged (1,037 of the recorded calls);
  and a result that any documented call of the unit returns is documented, the
  rule applied until nothing changes.
  Variants rename every symbol of a call by one map over all its arguments (a
  rename on one side had graded only fallback paths), shift no integer whose
  docstring states a domain (prime, odd, positive, a polynomial routine's level),
  drop a shifted integer outside the range of the unit's recorded calls unless
  the docstring describes a plain integer, and drop a candidate that breaks a
  stated prime contract (the added calls of `_primitive_root_prime_iter` and
  `_primitive_root_prime_power2_iter` had passed composite or even moduli). The
  documented-call check no longer stops comparing a hot unit after 20,000 calls:
  a call is pickled only when its arguments' kinds and sizes could match a
  recorded one, so 1 unit is capped where 97 were (its calls stay documented).
  Rebuilt from the 13,382 recorded calls: 1,697 units had no counted call, 3,355
  calls were added for 990 of them (1,567 recorded while the withheld tests ran,
  1,788 variants), and every result was recorded again: the original reproduces
  16,737 of 16,737 under three hash seeds, the skeleton none. 6,854 calls count,
  1,955 units are in the set and 716 are left out (the 707 left without a given
  call, and 9 more whose counted calls went when the final results were
  recorded again). Floor, through the verifier
  and behind a table: every fixture a submission could build 0.015 or less
  (bare raise 0.0, first argument 0.0, boolean flip 0.0 through the verifier and 0.013 behind a table),
  so a unit still needs one matching counted call; the after-the-fact best
  constant, which uses the hidden results, bounds at 0.059.
- Re-check, the rest. A collect step that found the tree missing, something
  else under its name, or could not list it (none of which `dev` can bring
  about) now marks the delivery failed, an evaluation error, where it was graded
  as an empty delivery; an oversized mark or record is named as such; removed
  entries are noted one by one only up to 20 per reason. Every `metrics.json` key
  the decision lists is present on every path; an empty unit or call set is an
  evaluation error; a results line nested past the parser's depth is skipped
  instead of ending the evaluation. `units_documented_calls_only` counts only
  units in the set, `units_left_out_passing` the left-out ones. The docstring
  and call phases may each take 40 minutes of the one 6,000 s deadline (30 and
  20 before), so a slow host shortens the unreported tests rather than the
  reward. The key the collect step signs with is replaced before every uploaded
  version (`delivery_key.py --rotate`). The transplant code the agent's tool
  shares holds only the transplant: the body hashes behind `identical_bodies`
  and the withholding of late files moved into the verifier. The solution's
  `ATTRIBUTION.txt` now equals the image's (licence, citation and changes), both
  Dockerfiles lost their build-context notes, and the sealed test list holds the
  list only. Not built: comparing example output in the root process (the
  sandbox reads the expected output in the docstring, so a patched runner could
  report it; the reward stays bounded by c, which it cannot forge (fourth
  re-check: a body can forge what its own unit's calls report, see 2026-11-24),
  a neutral
  name for the net check (its name tells the agent nothing it could use), and a
  bound taken from the end of the harness process (the platform keeping the
  agent's network policy through collection is the fix for the remaining race).
  The 16 stored submissions graded again on the rebuilt calls: reward 0.004 to 0.896, in
  the same order as before; the reference 1.0 and complete with 10,428 of 10,428
  tests, the agent's starting tree 0.0.

### 2026-11-20, second re-check

- The instruction. The two sentences that said a body is right, and the work
  complete, when no function "can be told apart" from SymPy 1.14.0's now state
  the requirement itself (a function "behaves exactly as SymPy 1.14.0's does";
  the work is complete "when every function returns, raises and changes exactly
  what SymPy 1.14.0's does"): the platform rejected a sibling task after one
  solver read that phrase as a description of its own evaluation. Three free
  changes went with it: the progress log is kept so that the work can be taken
  up again after a break (not "so that anyone looking in can see"), restored code
  "should not be much slower" (no factor, since nothing measures one), and the
  checks the agent can run are the least of complete because "a function must
  also behave as the original for arguments that no example or test uses" (not
  "they cover the documented cases only"). "Some of the upstream tests are not in
  this checkout" stays: it is a true description of the copy, whose test files
  show the gaps anyway.
- The end of the work. A poll that failed for a reason of the machine (no free
  port or address, no file, buffer or memory, a thread or probe that would not
  start) counted as a closed poll, so a process that held every local port kept
  the closed stretch going past the turn, and the collect step then moved the
  end to its own start: a SymPy fetched meanwhile was taken. Such a poll is now
  `local`: it neither extends nor breaks a stretch, and three in a row end it as
  an opening does (end recorded at the last closed poll, `dev` ended). The end
  is no longer moved to the collect step's start unless the collect step's own
  probe found the hosts closed. The net check also watches the exec sessions of
  `dev` in `/proc` (a process of `dev` under a root `su` or `runuser`, or with no
  parent in the container), and the end of the work is the earlier of its own
  end and the end of the session that ran the whole work: a detached process
  never has such a parent, so no trick with the network, the CPU or the probe
  moves that end. (Third re-check: that end bounds a turn only when the
  harness's exec ends with it; a turn ended by the time limit keeps its exec,
  and a load that times out the probe's handshakes could then push the net
  check's end past the limit. The limit is now an end of its own.) The session
  end applies only when that session began within
  ten minutes of the start of the work, because a harness that runs one exec per
  command ends many sessions during its turn; such a harness keeps the net
  check's end. The end is not taken from the session for killing `dev`: that
  would end an agent's background jobs between its commands.
- The no-op. A turn shorter than three polls (the platform's no-op turn lasts
  about 0.21 s) had no end, and every no-op would have been an evaluation error.
  The start of the work is now recorded to the fraction of a second, and when no
  end is known and no listed entry changed since the work started, the start is
  the end (`end_from` `unchanged`): the starting tree is graded, 0. A record
  with no end at all grades a tree that restores no unit (0, whatever was
  written when) and stays an evaluation error for any other, unless the work
  itself hid the end: a probe held blind from the start of the turn, or one that
  saw no answer while the hosts answered the collect step, with no exec session
  to bound the work, makes the collect step refuse the tree (0), so that an
  agent under a harness of one exec per command cannot turn its trial into an
  evaluation error that way.
- Hostile errors. Every way the work could turn its own failing trial into an
  evaluation error is now a scored 0 or harmless (third re-check: every way
  through the collect step; bodies that used up a phase's time still left items
  unreached, an evaluation error, until the next round): nothing usable under the
  tree's name (removed, a link, a file, a link to another directory) is a
  signed refusal with an empty tree in its place, as is a tree that cannot be
  listed (the collect step's `failed` state is gone); a tree deeper than 64
  directories, with a path over 1,000 bytes, with a directory whose name a copy
  might not carry, or whose record would pass 48 MB is refused before it can
  break the verifier's limits or the platform's copy; a file whose name a copy
  might not carry is removed and noted; every character of the mark outside
  printable ASCII is escaped and the verifier splits it on line feeds only (a
  link named with a form feed had unsigned the mark); the room the setup step
  set aside is given back as soon as `dev` has ended (third re-check: the
  process listing was still written first, so a disk the work filled voided the
  session end; the room now goes right after the freeze, before anything is
  written); the net check stops and kills `dev` with its own signals as well as
  with tools, so it works when no process can be started, and a poll or probe
  that cannot start is a local poll instead of the end of the net check. A live
  process of `dev` that outlived the collect step (zombies are not counted) is
  now an explicit evaluation error.
- The collect step fails closed (a re-check of the sibling Carve found these
  in the same design). It now puts the tree aside first (third re-check: after
  the freeze, the listing and the kill, which a zombie could stretch to the
  hook's limit; now right after the freeze and the room) and leaves an empty tree
  with a signed refusing mark in its place, and gives the measured tree its name
  back only once its own mark and record are written, so a timeout, a crash or a
  full disk at any later point leaves a tree that scores 0, never one without a
  mark; a refusing mark counts even when the record beside it is newer. The mark
  holds at most 60 notes of at most 240 characters (thousands of removed pipes or
  links had no bound on the mark's size, and a mark over the verifier's 1 MiB
  read limit was an evaluation error); the record keeps every note. Reading only
  a prefix of the mark, as the Carve re-check suggested, would not do here: the
  signature is the mark's last line. A tree there is no room to pack in `/tmp`
  (where the platform packs it inside the sandbox; a disk the work filled made
  the pack fail and an empty directory arrive) is refused after what `dev` left
  in `/tmp`, `/var/tmp` and `/dev/shm` is removed. Not applicable here: link
  chains (no link is resolved, each is removed in one step) and links that climb
  above `/` (no link is kept); the collect step has no early exit.
- The comparison. The canonical form gave a Python value and its SymPy
  counterpart, and the flavours of a container, one form, although the
  instruction asks for "the same type and container": a body returning a Python
  `int` where upstream returns an `Integer` (`nP`), a `bool` for SymPy's `true`
  (`Interval.right_open`), a dense `Matrix` for a `SparseMatrix` (`banded`), a
  mutable matrix for an immutable one (`Vector.to_matrix`), dense storage for
  sparse (`DomainMatrix.nullspace`, outside the 24 units whose storage counted)
  or a 15-digit Float where 20 digits were asked (`gauss_laguerre`) matched
  every counted call, and the best stored submission had 175 such calls. The
  form now keeps every type (step 3 of [Verification](#verification) lists
  them), a call that returns a value and changes an argument is compared on
  both (`ddm_irref` working on a copy matched before), and the LaTeX profile
  keeps a blank line as a paragraph break. Every recorded result was recorded
  again (`regold.py`, hash seeds 0, 1 and 2): the original reproduces 16,737 of
  16,737, 16,593 of them byte for byte and the other 144 up to the Dummies and
  frame counters the call made, the skeleton none, and no call was dropped.
  With the changed arguments beside the result, 27 results of mechanics units
  outgrew the runner's 400 kB line (one unit, `Joint._create_aligned_interframe`,
  would have lost every call), so the line limit is now 2 MB. What a table could
  answer is still judged with the type left out (`canon.erase`,
  `canon.same_loose`): a printed result does not show it, and a table keyed by
  arguments finds an int and an Integer alike, as they are equal and hash
  alike. Echoes now also count an element of a call's `*args` or a value of its
  `**kwargs`, found from each unit's own signature. The reviewer's wrong bodies,
  run through the verifier's own runners on real SymPy, counted calls matched,
  original then wrong body: `nP` returning an int 7/7 then 1/7,
  `right_open` returning a bool 4/4 then 0/4, `banded` returning a dense matrix
  8/8 then 0/8 (both forms), `to_matrix` returning a mutable one 8/8 then 0/8,
  `DomainMatrix.nullspace` returning dense storage 4/4 then 1/4,
  `gauss_laguerre` at the default precision 6/6 then 0/6, `ddm_irref` on a copy
  2/2 then 0/2, `Beam.apply_support` without the slope condition 6/6 then 4/6
  (the two fixed supports fail), `multiline_latex` with blank lines 6/6 then
  0/6; the round-1 controls are unchanged (`pprint_nodes` 0/3, `bivariate_type`
  0/4, `MatrixBase.table` 0/4, `Permutation.rmul` 6/8, `Point.pos_from` 1/8).
  The stand-in checks hold each pair as different (`checks/test_comparison.py`).
- The counted calls. The documented-result rule looked only at recorded calls,
  so results the docstrings print still counted: the re-check measured 0.029
  for the panel's own fixture (a table of the outputs the agent can read,
  falling back to the unit's most often printed one) and 0.041 for every
  buildable strategy together, against the 0.015 stated. The visible run
  (`documented.py`) now also keeps what each unit returned to a call an example
  or a visible test made directly (`shown`, by canonical form with the type left
  out; a returned iterator is left alone, since reading it would empty it for
  the example: a first run that read them failed six combinatorics tests and
  was thrown away), and a call returning such a result is documented, with the
  same closure. The visible run now also covers the slow visible tests (60 s
  each), the tests marked to be skipped (run with pytest's skipping off) and
  the examples marked `+SKIP` (except those of `sympy.testing`, which start
  SymPy's own test runners). Calls a visible run of the round before saw are
  kept documented too: a few visible tests draw random inputs, so which calls
  one run makes varies (12 calls were seen then and not now). Rebuilt: 10,533
  of 16,737 calls documented (9,384 by arguments, 674 because their result is
  shown, 341 because it is one of their arguments or an element of their
  `*args` or `**kwargs`, 76 of units whose comparison stayed capped, 58 because
  it is a documented result), 6,204 counted; 1,844 units in the set, 827 left
  out (111 more than before; see [Verification](#verification)), covering 77.4%
  of the body lines. Two calls that were documented count now: they return
  the same symbol as a documented call but change a different beam. Floor on
  these calls (the table under [Reward formula](#reward-formula)): every
  buildable strategy at most 0.0245 behind a table and 0.0 through the
  verifier; the bounds that use the hidden results 0.0269 and 0.0301. (Third
  re-check, through the verifier's own runners: the combination 0.0166, since
  delegates reach placeholders in a real tree, and an accessor synthesis
  0.0401, 0.0171 of it in units whose body is such an accessor; both under
  0.05.)
- Wording. The collect step's text no longer says "delivery", "the agent's
  user" or "egress": the record key `egress` is now `net_probe`, renamed in the
  hook and the verifier together. The sealed test list's writer
  (`ops/sympy-restoration/builder/package.py`) writes the list only, and
  `package_step.py` refuses a sealed list or documented list that holds any
  other key.
- Checks. The real net check now runs whole under the checks (its probe
  process, polls and record, on a network a scenario file decides) for a probe
  blinded by a lack of ports and for a turn of no length, and its output feeds
  the collect step and the verifier. New checks cover the three kinds of poll,
  the session rule on a stand-in `/proc` (an exec, a command it runs, a
  detached process, `su` run by `dev` itself, a zombie, a root session), the
  earlier end winning, a session that cannot bound the work (began late, still
  alive, not watched), the clamp's removal, every refused tree, odd names, a
  surviving process, and a measurement with no end with and without a restored
  unit; the comparison checks hold the type, storage, precision, in-place and
  LaTeX differences of the probes above as different, on stand-ins. 104 checks
  pass. Not run here: anything that needs Linux
  (`/proc`, `setpriv`, `su`, the kill itself), or the platform.
- Baselines, on this machine through the verifier entry point's own steps (no
  privilege drop, no network probe of the verifier's own): the reference 1.0
  and complete (1,844 of 1,844 units in the set, 6,204 of 6,204 counted calls,
  16,737 of 16,737 calls, 10,428 of 10,428 tests in one plain pytest session,
  none unreached, no control tripped, 1,020 s) and the agent's starting tree
  0.0. A turn of no length went through the delivery path as far as macOS
  allows, with the checks' own harness: the shipped setup and collect hooks ran
  whole under dash, the real net check ran whole (its probe process, 8 polls and
  its record), the collect step listed 1,716 entries and, with no end seen,
  recorded `end_from` `unchanged` at the start of the work; the tree was copied
  as the platform copies it (a tar unpacked with the `data` filter) and the
  verifier read the real mark and record: 0.0, not an evaluation error. Stood in
  for: root and the Linux tools (`setpriv` never kills, `pgrep` and `pkill` find
  nothing, `fallocate` fails, `timeout` and `setsid` run their command), the
  network (every host resolves to a documentation address and every connection
  completes), `/proc` (absent here, so no exec session is seen), the user `dev`,
  and in the verifier the privilege drop and its own network probe.
- Regrade. The 16 stored submissions graded again through the entry point's
  steps (examples and calls): reward 0.003 to 0.857, each lower than in the
  round before by 0.001 to 0.039 and in the same order apart from two 48-hour
  sessions now 0.001 apart the other way round; no unit or call unreached, no
  late file, no control tripped (see [Trial evidence](#trial-evidence)). The six
  full-session claude-code runs now have 107 to 146 units in the set whose
  examples pass and that match no counted call (72 to 101 before): the typed
  comparison fails results of the wrong type or container that matched before,
  and the calls left counted are those whose result nothing visible shows.
  Honest partial work, the original bodies of the first 20% of units in
  `restore next` order, scores 0.150; a random 20% scores 0.033.
- Package. The signing key was replaced (`delivery_key.py --rotate`) and the
  flat 12-hour bundle rebuilt (`package_single_step.py --keep-name`, content
  `2b0d8ccb0c6e`, 415 files) in `ops/sympy-restoration/dist-12h/`, the previous
  one set aside. It had gained 8 bytecode files under `tests/verifier/` after its
  audit, from a run that imported the verifier from the bundle; the new one has
  none, so a reviewer should run anything from it with `-B`. `oddish preflight`
  passed. A word sweep of the whole bundle found nothing the agent can read that
  speaks of grading, the platform, review or measurement: the instruction and
  the tool use "deliver" only as the task's own word ("delivered form", "What to
  deliver", "the deliverable", unfinished work "delivered as it stands"), and
  "platform" only as the name of a Python module the tool refuses to import; no
  shipped text holds a non-ASCII byte, a path of this machine,
  a name, an email outside `task.toml`'s authors, or a date. Two comments of the
  collect step had named the platform's packing; they now say "the copy". The
  hidden data opens on data (`units.json`, `sealed_tests.json` with `tests`
  only, `unit_bodies.json`, `documented.json` with `calls` only, `gold.json`
  keyed by call); the strings of the pickle, the JSON files and the decompressed
  archives hold only SymPy's own names; the archives are owned by root with
  mtime 0, no link and no pax header, and against the SymPy 1.14.0 wheel their
  only changes are bodies turned into placeholders, deleted withheld tests and
  `pytest.ini`; the key's two copies are equal, new, and found in no other file
  or archive member.
- Residuals accepted after this round, each with its reason:
  - The floor. Behind a table of documented outputs, a type default, a delegate
    or the best order of every cheap fallback still matches a few counted calls:
    at most 0.0245 for a strategy a submission can build, 0.0269 and 0.0301 for
    the two bounds that choose with the hidden results. All are under the
    decision's 0.05, each needs the table of documented outputs first, and
    through the verifier every fixture tree scored 0.0. (Third re-check: an
    accessor of the call's own arguments chosen by visible fit reaches 0.0401,
    still under 0.05; see the floor under [Reward formula](#reward-formula).)
  - Predicates and small units. 824 units (31% of the units, 22.4% of the body
    lines) are left out of the reward's unit set, 221 of the 229 whose recorded
    results are all booleans among them: a boolean that an example shows
    documents every boolean result of its unit. Counting them would pay a table
    that flips or repeats a boolean. They are still graded and reported
    (`units_left_out`, `units_left_out_passing`).
  - What the comparison leaves out (step 3 of [Verification](#verification)):
    memo slots one side has not filled, the Dummies and frame counters a call
    makes, `Truss.remove_node`'s coordinate lists, LaTeX whitespace in two units,
    floats within a tolerance scaled to their precision, dict order and a
    matrix's internal domain. Each is not behaviour the instruction promises (a
    cache, whitespace LaTeX ignores, lists upstream itself keeps inconsistently,
    an order no example or test can show, a domain SymPy picks for its own
    arithmetic), not stable in the original (144 of 16,737 results differ
    between runs, only in the names a call makes), or, for the floats, kept for
    a second machine's math library, which only the platform will show (173
    counted results hold a float). (Third re-check: below 53 bits that tolerance
    was a half and an absolute floor of up to 1, and at 53 bits it let a value
    wrong from its eleventh digit pass; it is now a few units in the last place.)
  - Visible runs with random inputs. A few visible tests draw random inputs, so
    the calls one run makes vary: 12 calls were seen in the round before and not
    in this one. Both runs' calls are documented; a call only a third run would
    make stays counted, although the agent could see it by running that test
    again.
  - The session end of the work rests on Linux `/proc`, which the checks cover
    only with a stand-in, and on each harness running the whole work in one exec
    session; for a harness of one exec per command it does not apply (the session
    must begin within ten minutes of the start), and that rule is unverified for
    Proximus (see [Remaining work](#remaining-work)).
  - The tests share stays out of the reward until a regrade on the platform
    leaves no test unreached; the stated 12 hours against the agent's 34,560 s
    stays the owner's exception (decided on 2026-11-24: the hours are dropped).

### 2026-11-21, third re-check

- The end of the work at the time limit. Harbor stops waiting for the agent at
  its limit but never ends the exec, so a turn that ran to the limit had no
  session end, and a process that kept the probe's handshakes timing out after
  the limit (the net check reads that as closed) could have a fetch graded. The
  end of the work is now never later than the start of the work plus 34,560 s,
  the agent's limit (a check holds `task.toml`, the collect step and the
  verifier to one number), in the collect step and again in the verifier; with
  no other end known and an exec session still alive after the limit, the limit
  is the end. No kill enforces it: a killed claude-code exits 137, and Harbor
  classifies that exit by its transcript, whose failed fetches read as network
  errors that void the score. A check reproduces the re-check's probe with the
  real net check: a file written after the limit is late.
- The order after the freeze. The process listing was written while the room
  set aside at setup was still held, so a disk the work filled voided the
  session end even of a turn that ended normally, and the tree was put aside
  only after the listing and a kill loop that counted zombies (100 passes with
  one zombie left, before any mark existed; commit `9d2ee5a` had said the tree
  went aside first). The room now goes back right after
  the freeze, then the tree is put aside, then the listing is written; a
  listing that cannot be written leaves the session end to the net check's own
  record of the sessions; the kill counts live processes only and stops after
  30 s.
- The probe. Its hosts are given on its standard input, so `ps` names none (the
  round before had put them on its command line). A refusal for an end the work
  hid ("answered") now needs the collect step's probe to have reached one of the
  net check's own addresses within the time the net check's polls allow; an
  answer that only a fresh lookup or a longer wait gets leaves the end unknown
  (an evaluation error for a tree that restores a unit), since a slow network is
  not the work's doing. Commit `d8bd65b` said both causes are always the work's;
  that held only for the blind probe. Three local polls in a row while an exec
  session is alive no longer end `dev`, which ended the agent's harness: the end
  of the stretch is recorded, and `dev` is ended at the next open poll or once
  no session is alive.
- Smaller. A tree over 256 MB is refused (2 GB before; such a tree must cross
  the platform's file transfer twice); the `task.toml` justification is one
  neutral line; the Dockerfiles carry no comment.
- Low-precision Floats. Below 53 bits the tolerance had been a relative half and
  an absolute floor of up to 1, so `nroots` at two digits, `Expr.round` one place
  early and `racah` without its sign factor matched their counted calls, and at
  53 bits a value wrong from its eleventh digit matched. A SymPy Float (of the
  same precision) and an mpmath number are now alike within a few units in their
  last place, a relative 2^(2 - precision), a Python float within 2^-50, and zero
  only zero. The reference graded again matched 16,737 of 16,737 calls, and once
  more in the timing run, so no tolerance was needed; the checks hold one unit in
  the last place alike and 1%, a sign flip and a value inside the old floor apart
  at 13, 17, 20, 27 and 40 bits.
- The runners' records. A body could import `__main__` (the runners kept their
  nonce, output and payload there) or `posix`, write a result line of its own,
  and forge a docstring pass by wrapping the runner's `emit`; and `same()`
  raised on five shapes such a line can carry, which `engine.py` did not catch,
  an evaluation error the work caused. A list of forbidden imports alone would
  not close it, since SymPy itself hands out its modules' imports as attributes
  and evaluates strings. So each start of a runner now gets its own key on its
  standard input, the runner keeps that key, its output and its work inside a
  function, never on `__main__`, and the verifier reads only lines that carry the
  HMAC of their text with that key: a line a body writes, to the runner's file
  or to any open descriptor, is not read. `__main__`, `posix`, `nt` and every
  module whose name starts with an underscore are forbidden in a body as well
  (every original body still passes the rules). `same()` is total (an identity
  that is not a name binds nothing, a memo dict whose items are not pairs is no
  match), and the engine counts a result it cannot compare as not matching. A
  body that takes over its interpreter through SymPy's own string evaluation
  could still reach the key on the runner's stack; what that buys is what
  finding 1 of the hackability table already bounds: forged examples, with the
  reward never above the call share, which is compared outside with results the
  sandbox never sees. (Fourth re-check: no string evaluation was needed, since a
  body could rebind `json.dumps` or walk to the runner's frame from an
  exception, and a forged call could hide the state it left in its arguments;
  the runners now hold no key at all, see 2026-11-24.)
- Time the submission's bodies used. Bodies that never end or are very slow
  used up the 40-minute example and call phases (each time-out cost its whole
  limit and a fresh runner, and was not counted as a restart), and the items
  left raised "The reward depends on items the measurement did not reach": an
  all-looping tree and a tree with 5% of its units looping were evaluation
  errors. The re-checks suggested per-item budgets from the original's times;
  those alone cannot bound a tree whose every body runs just under its budget,
  and set tight they would fail honest code on a slower machine. What decides
  now is who used the time. Before any submitted code runs, the verifier times a
  fixed piece of pure-Python work (0.16 s on the machine the reference results
  were recorded on) to know how much slower its machine is, and the original's
  own seconds for every module and unit (`tests/private/timing.json`, 299 s of
  examples and 318 s of calls on one worker, most of it the runners' imports)
  say what the original would need for the restored units. When a phase runs
  out of time with items left and the original would need at most half of the
  phase's worker-seconds, the items left fail; only a machine so slow that the
  original itself would need more keeps them not reached, an evaluation error.
  On the platform's four workers that leaves room for a machine sixteen times
  slower (fifteen for the calls). A unit whose calls ran out of time, or stopped
  the runner, twice is not run again, and the phases now count their starts,
  time-outs and stops. (Fourth re-check: units merely queued behind the
  time-outs failed too; replaced on 2026-11-24 by a bound for every item.)
- Caches and thin forms. `AlgebraicField._converter`, a converter the field
  builds for itself, is a memo slot, so a body that converts one more time no
  longer changes its argument (`dup_monic` matched 1 of 3 that way); the sieve's
  range units count only what they return, not how far they grew the module's
  sieve, a cache (`primerange` 6 of 8 and `totientrange` 2 of 5 with the right
  primes), while `Sieve.extend` and `extend_to_no` count the growth; a sieve is
  compared by every value of its lists, no longer by its printed head and tail,
  and a sparse polynomial with its ring's symbols, domain and order. Every
  result was recorded again (seeds 0 and 1): 16,737 of 16,737 kept, 16,593 byte
  for byte and the rest only in the names a call makes, the skeleton none; 66
  results changed form (33 with a ring, 21 with a sieve, 12 with a field), 31 of
  them counted. Objects past 40,000 nodes are still compared by their printed
  form (9 counted calls change an argument that large), now named with the
  other relaxations.
- The visible runs the re-check found short. The capture counted every call
  into a unit toward its cap, repeats included, so nine hot units stopped being
  compared and every call of theirs stayed documented; it now counts distinct
  arguments, and the slow tests of the five packages concerned ran again: three
  units are compared to the end now (`to_NNF`, `ExpBase.as_numer_denom`,
  `dmp_neg`, whose 10 calls count again), five still pass 500,000 distinct
  arguments (`ecm` `Point.add` and `double`, `dup_reverse`, `dup_shift`,
  `dup_sign_variations`; their 33 calls stay documented) and `fastlog` stays
  capped from the regular tests, with no counted call. The slow tests of
  `sympy.stats`, whose session had ended in a pytest INTERNALERROR, ran again one
  file at a time, and the eleven visible tests the 60-second limit had cut ran
  again one at a time with 600 s: seven finished (two of them fail on the
  original here), four ran out of 600 s again (`test_bicycle`,
  `test_linear_new_order1_type2_de_lorentz_slow_check`, and the skip-marked
  `test_issue_25820` and `test_I11`), and one call more is documented
  (`MultivariateT`, from `test_JointPSpace_marginal_distribution`, as the re-check
  found). Rebuilt: 10,524 of 16,737 calls documented, 6,213 counted, 1,847 units
  in the set and 824 left out.
- Baselines on the final verifier, on this machine through the entry point's
  own steps (no privilege drop, no network probe of its own, one worker): the
  reference 1.0 and complete (1,847 of 1,847 units in the set, 6,213 of 6,213
  counted calls, 16,737 of 16,737 calls, 10,428 of 10,428 tests, none
  unreached, no control tripped, 1,043 s); the agent's starting tree 0.0; a turn
  of no length through the shipped hooks, the real net check (8 polls) and the
  real mark, copied as the platform copies it: `end_from` `unchanged`, 0.0. Stood
  in for, as before: root and the Linux tools, the network, `/proc`, the user
  `dev`, and in the verifier the privilege drop and its own network probe.

### 2026-11-24

- The time line, on the owner's decision. The instruction no longer states a
  time: "You have 12 hours of wall-clock time at most, and the run can end
  before then", with the timer that printed the seconds left of 43,200, gave
  way to one line, that the run can end at any time, so the work should stay
  runnable and the `/app/PROGRESS.md` log current; the log and its cadence are
  unchanged. `/app/timer.sh` is gone from the image as well, since a timer
  counting down from 12 hours states the same figure (the platform's audit
  makes a must-fix of a stated time that differs from the agent's limit, here
  34,560 s), and no sibling task carries one. The retired session packager
  now refuses because the image has no timer, and its check asserts that
  refusal, that the instruction states no hours, no wall-clock and no timer,
  and that the log requirement stays.
- The three hostile trees of the brief, through the verifier's own `measure()` and
  scoring (a local driver runs the entry point's steps), one worker and
  the phases cut to 900 s of examples and 1,200 s of calls, about a tenth of the
  platform's 9,600 worker-seconds per phase, so that each tree takes about 35
  minutes; the rule that decides is the same at any budget. Each completed with
  a reward, none an evaluation error, and every item a phase did not reach was
  counted as failed, since the original needs about 299 s and 318 s of those
  phases here:
  - every body `while True: pass`: 0.0000 (0 of 1,847 units in the set, 0 of
    6,213 counted calls; examples 37 time-outs in 44 starts, 2,628 units'
    examples not reached and failed; calls 108 time-outs in 110 starts, 45
    units cut after two, 16,411 calls not reached and not matching).
  - 5% of the units (134) never end, the rest original: 0.0254 (47 of 1,847
    units in the set, 180 of 6,213 counted calls; examples 32 time-outs in 57
    starts, 2,538 units' examples not reached and failed; calls 104 time-outs
    in 129 starts, 39 units cut after two, 15,746 calls not reached and not
    matching).
  - 50% of the units (1,336) first wait 0.05 s on the clock, then run the
    original body: 0.0341 (71 of 1,847 units in the set, 212 of 6,213 counted
    calls; examples 16 time-outs in 57 starts, 2,338 units' examples not
    reached and failed; calls 48 time-outs in 78 starts, 17 units cut after
    two, 15,732 calls not reached and not matching).
  The 5% tree scores low here because its 134 looping units' time-outs, about
  28 s per unit in the examples phase and 11.5 s per call, use up the cut phases
  before the original's own work is done; on the platform's budget the same
  time-outs take about 3,800 s of examples and 3,100 s of calls of 9,600 each, so
  the phases would finish and only the looping units and the units that call
  them would fail. (Fourth re-check: wrong; 955 units' examples and 4,622 calls
  start a looping body, so the phases did not finish and 666 units in the set
  that touch none failed for want of time; see 2026-11-24.) The slow tree is slow everywhere: a call into one unit runs
  many others, each waiting 0.05 s when it is one of the 1,336, so its calls
  and examples run past their limits or crawl, and it scores like a tree whose
  bodies mostly fail.
- Package. The signing key was replaced again (`delivery_key.py --rotate`) and
  the flat bundle rebuilt (`package_single_step.py --keep-name`, content
  `966f2b531f52`, 415 files: one fewer source file, the timer, and none of the
  bytecode the round before's had gained during its audit) in
  `ops/sympy-restoration/dist-12h/`, the previous one set aside. The platform's
  content hash of the new bundle, `27ceda8716e8…`, differs from version 4's
  (`4ce37762a342…`). `oddish preflight` passed (1 task). The bundle equals the
  worktree file for file and commit `4ef634c` for every tracked source. A word
  sweep of the whole bundle again found nothing the agent can read that speaks
  of grading, the platform, trials or the verifier's image: the only hits are
  the task's own "deliver", the standard library's `platform` in the list of
  forbidden imports, SymPy's own module and class names (`benchmarking`,
  `GradedLexOrder`) and the instruction's "image" for the machine the work runs
  on; 0 non-ASCII bytes; the key's two copies are equal and new, and held by no
  other file.
- Regrade of the 16 stored submissions on the final verifier (examples and
  calls, one worker): every reward within 0.0023 of the round before's (10 down,
  6 up; v2 trial 16 0.856, the weakest 0.003), the order unchanged, no unit or
  call unreached or failed for lack of time, no late file, no control tripped
  (the stored submissions are the verifier's own copies of the unit files, with
  no times from their runs, so a regrade cannot show what the end of a run cost).
  The submissions' own bodies ran past their limits up to 15 times in the
  examples and 24 in the calls, and up to 7 units per submission stopped being
  run after two; every phase finished. Table under
  [Trial evidence](#trial-evidence), with `RESULTS_12H.md` updated.

### 2026-11-24, fourth re-check

- Late saves at the limit (integrity N1, auditor R2). The limit was counted from
  the setup hook, which runs before Harbor starts the agent's clock, and Harbor
  does not end the agent at its limit: claude-code works on until it is stopped
  and saves by writing a new file and renaming it, so one save in that second or
  two returned the whole unit file, with every body written in it hours before,
  to the skeleton (up to 154 units for `polys/polytools.py`, and everything that
  calls them). The limit now counts from the start of the first process of `dev`
  that began after the work did and whose parent is not one of `dev`'s, read
  from `/proc`, as the sibling task counts its own; that process starts after
  Harbor's clock. The net check copies every unit file that changed, each second
  from 300 s before the limit until it, into a folder only root can read (a file
  only when it has not changed since that look began and stays the same file with
  the same times while it is read), keeping the last two copies of each with the
  time at which the file held that content; room for them is set aside at setup.
  The collect step puts the last copy that held a file's content by the end in
  place of a unit file changed after it, and records the copy, what it replaced
  and the units whose bodies differ between the two; the verifier takes the file
  as that copy. A capped turn now loses at most the edits of its last second,
  never a file. Where no copy exists (the net check did not run), a late file is
  not taken, as before. No freeze and no kill: nothing stops the agent before its
  limit.
- A blip mid-turn (auditor R1, integrity N2). Three polls that failed for want
  of ports, buffers or memory ended the stretch, and when that came after the
  middle of a turn the collect step took the blip as the end of the work and
  withheld every unit file saved after it. Local polls now end nothing, however
  many come in a row (they are counted); an opening seen while an exec session
  is alive, within the time the work is given, is no end of the work (the hosts
  answer again only once it has ended) and ends no process; `dev` is ended at an
  opening only once a fresh look finds no session alive, or the time has run out,
  and never while the sessions cannot be seen. The re-check's probe is a check:
  three local polls two thirds into a turn, the session's end ends the work, and
  what was saved after the blip is graded.
- Items queued behind time-outs (reward M1). When a phase ran out of time every
  unit still queued failed, so the 5% tree scored 0.24 at the platform's budgets
  against 0.61 with every item run. Every item now has its own time: a unit's
  examples ten times the original's own time for them on this machine, at least
  2 s; a call ten times the original's time for its unit's calls, at least 1.5 s;
  a module's import five times its own, at least 10 s. An item past its time
  fails, the rest of its unit is not run, and the module goes on in a new runner
  (an interrupted body can leave global state behind). The phases stay only as a
  guard (examples 2,700 s, calls 2,400 s), sized so that a tree whose every body
  runs out of its time still finishes both on the platform's four workers
  (estimated at about 2,250 s and 1,930 s at this machine's speed; measured at
  2,194 s and 2,205 s, below); the rule for a guard that runs out stays. The reviewer's two passes (a short time first, the old limits
  for what ran out) were not built: with ten times the original's own time and
  floors above what almost every original item takes (99% of units' examples
  take under 0.16 s here, 99% of units' calls together under 0.64 s), an honest
  body is not near its time, and a second pass would spend the phase on bodies
  that never end. With the new runners the reference passes 2,671 of 2,671
  units' examples and 16,737 of 16,737 calls, none out of time.
- Disk fill (reward M2). `sympy.preview(outputTexFile=...)` wrote files the
  sandbox user kept, and the runners' next write raised. The sandbox now runs
  with a 256 MiB limit on the size of a file and 1,024 processes; each start of
  a runner gets a private folder for its temporary files, removed after it, and
  what the sandbox user left in the folders it can write to is removed between
  phases; the runners no longer write files at all (they answer over pipes);
  every file the verifier writes is guarded (cleared and tried once more, else
  noted); 64 MiB set aside on the result's file system is given back just before
  the result is written. `preview` and SymPy's other file writers and module
  loaders (`autowrap`, `codegen`, `plotting`, `importtools`) are denied in a body.
- Forged records (verifier N1, N3). A body could rebind `json.dumps`, which the
  runners called to write their signed lines, and so have them sign a list as a
  call's id or an example record that said it was not reached, and scoring
  raised; a walk to the runner's frame reached its signer. The runners now hold
  no key: the verifier is their parent and reads each one's lines over a pipe,
  in pieces, at most 4 MiB a line (1 MiB for examples) and 256 MiB a start (64
  MiB), only in their order (the import, then each item's start and its result),
  rebuilds every record from the runner's own fields (a status of its own set,
  counts as integers, text cut to length) and never raises on one; whether a
  unit was reached is the verifier's own count, never a record's. The re-check
  suggested a separate parent that signs; with the verifier itself as the parent
  there is nothing left to sign and no key to guard. A body can still lie about
  the item it runs in (hackability finding 1, now worded as it holds); a line for
  any other item breaks the order and fails its own.
- Unbounded reads (verifier N2). The runners' output is read in bounded pieces
  (above); the test phase's watcher looks at a run's new records a megabyte at a
  time and ends a run whose records pass 256 MiB; the tests' records and logs are
  read within limits; the file-size limit stops a sparse output in the sandbox.
- A collect step that cannot start a process (integrity N2, its error part). A
  tree that arrived without the collect step's mark was an evaluation error, and
  a work that forks without end leaves the collect step unable to start any
  process. It now first says that it has begun, with the shell's own commands
  only, in a file the setup step made whole for it and that is copied beside the
  tree (`/var/lib/fsmaint/out`, a new artifact); with no signed mark and that word
  the delivery is an empty one, scored 0 with a note; with neither, the copy
  failed, still an evaluation error. And the net check gives every process of
  `dev` a limit of 8,192 processes of its user, so that such a process leaves
  room for the steps after the work.
- Should-fixes, all taken: the limit is the end whenever the collect step began
  after it, live session or not (integrity N3); the README's claims the
  re-checks named are corrected in place (integrity N4, verifier N3; hackability
  rows 1, 5 and 9); the body rules deny the route class (`posixpath`, `ntpath`,
  `genericpath`, `codecs`, `fileinput`, `logging`, `json`, `hashlib`, `hmac` and
  others; the attributes `os`, `_os`, `sys`, `modules`, `__traceback__`, `open`,
  `write` and others; literal names given to `getattr`, `attrgetter`,
  `methodcaller` and `import_module`), and every original body still passes
  (verifier N4); the sieve's range units compare the sieve they leave as a cache,
  alike where both hold values, so a sieve grown wrong no longer passes
  (verifier N5); a Float is said to compare within 2 to 4 units in its last place,
  and compares exactly below 4 bits (verifier N6); the hooks no longer say
  "collect step" (auditor R3).
- The hostile trees again, now at the platform's worker-seconds: one worker
  with four workers' phases (examples 4 x 2,700 s, calls 4 x 2,400 s), through
  the verifier's own `measure()` and scoring, the tests not run. Each completed
  with a reward, none an evaluation error:
  - 5% of the units (134) never end, the rest original: 0.5950 (u 0.5950, c
    0.6721; 1,099 of 1,847 units in the set, 4,176 of 6,213 counted calls; 955
    units' examples and 870 calls ran out of their time, 779 units' other calls
    were not run; the phases took 3,526 and 3,017 of 10,800 and 9,600
    worker-seconds; every item reached).
  - 50% of the units (1,336) first wait 0.05 s, then run the original body:
    0.7423 (u 0.7423, c 0.8062; 1,371 of 1,847 units in the set, 5,009 of 6,213
    counted calls; 549 units' examples and 505 calls ran out of their time, 442
    units' other calls were not run; the phases took 2,975 and 4,866 of 10,800
    and 9,600 worker-seconds; every item reached).
  - every body never ends: 0.0000 (u 0.0000, c 0.0000; 0 of 1,847 units in the
    set, 0 of 6,213 counted calls; 2,671 units' examples and 2,671 calls ran
    out of their time, 2,430 units' other calls were not run; the phases took
    8,776 and 8,820 of 10,800 and 9,600 worker-seconds; every item reached).
  The re-check put the 5% tree at 0.6053 with every item run and at 0.2447
  at these budgets before this round; the gap to 0.6053 is the rule that a
  unit's other calls are not run once one has run out of its time, which
  costs a unit with a call into a looping body its other counted calls. With
  the phases cut to a tenth the round before, the slow tree scored 0.0341 and
  the 5% tree 0.0254. A tree whose every body runs out of its time used 81%
  and 92% of the guards here (host factor 1.03): on a machine slower than
  this one by more than about a tenth, its calls would reach the guard, and
  the calls left would be counted as failed, as they would fail anyway.
- Regrade of the 16 stored submissions on this round's verifier (examples and
  calls, one worker): every reward the same or lower, by at most 0.0043 (9
  down, 7 the same; v2 trial 16 0.852, the weakest 0.003), the order unchanged,
  no unit or call unreached or failed for lack of time, no late file, no control
  tripped. Every item now has a time of its own, ten times the original's, and a
  unit's other calls are not run once one has run out of its time, so a
  submission's own slowest bodies cost a little more than under the old 20 s and
  10 s limits: they ran past their times 0 to 22 times in the examples and 0 to
  15 times in the calls, and 0 to 13 units per submission had their other calls
  not run; every phase finished. Table under [Trial evidence](#trial-evidence),
  with `RESULTS_12H.md` updated.
- Two items of a sibling task's pre-trial audit, checked here. The reference
  solution is readable source: `solution/` holds `oracle.py`, `solve.sh`, the
  license and attribution, and the original text of the 355 SymPy files that
  hold units (a prepared input, git-ignored in this repository and copied into
  the bundle by the packager), with no bytecode, archive or other opaque file.
  The verifier image's build installs system and Python packages while its
  environment was declared without network, so `[verifier.environment]
  network_mode` is now `"public"`, for that environment's build, with
  `[verifier] network_mode = "no-network"` kept for the verification itself
  and the open-internet justification extended to the second image's build
  (see [Verification](#verification)).
- The new hostile cases. On the verifier's side, through its own `measure()`
  and scoring with real SymPy (one worker, the tests not run), a tree of the
  original bodies with one unit each writing through `sympy.preview(...,
  outputTexFile=...)`, writing a sparse file through `open` and a seek,
  rebinding `json.dumps`, forking in a loop through `os.fork`, returning a 64
  MiB string, and printing 256 MiB before its original body: 0.9962 (u 0.9962,
  c 0.9979), completed, nothing unreached, no control tripped. The body rules
  refused the first four (`rejected: attribute '.preview'`, `use of builtin
  'open'`, `import of 'json'`, `import of 'os'`); with the two that ran they
  cost their own units and three callers (`JointsMethod.form_eoms` and
  `System.form_eoms` of `Vector.diff`, `homomorphism` of `Module.subset`):
  1,840 of 1,847 units in the set and 6,200 of 6,213 counted calls. The
  flooding unit's examples and the oversized result's ran out of their time
  (the flood's output went nowhere); the refused units' callers failed. A
  memory blow-up and a file written through a route the rules do not list are
  left to the sandbox's limits (4 GiB of address space, 256 MiB a file, a
  private folder for temporary files), which need Linux, so they were not run
  on this machine. On the delivery's side the checks run the
  hooks whole under stand-ins: a collect step that a fork bomb leaves unable to
  start a process scores 0 with a note; a save by rename just after the limit
  keeps the file, `copied`; three local polls two thirds into a turn end
  nothing; a disk the bodies fill leaves the score; forged and oversized runner
  lines cost their item and never raise.
- What the instruction names, against what is graded (two more items of a
  sibling task's pre-trial audit).
  - Errors. No recorded call expects one: the builder drops every call whose
    original raises (`regold.py`, `variants.py`). The instruction now asks for
    the error raised for an argument a function does not accept only where an
    example or a test shows it, and for every other argument it accepts. 53
    units' examples show an error, 37 of them in the set, and the examples gate
    the units in the set.
  - The tests. The 10,428 tests run but are not rewarded until the platform
    shows their phase complete (see [Remaining work](#remaining-work)); what
    they test counts through the counted calls recorded while the withheld
    tests ran.
  - Units. 824 units have no counted call of their own, 43 files none, and the
    package `sympy.liealgebras` none. Traced on the original tree, 244 of them
    run inside the counted calls of other units, 289 inside the examples of
    units in the set, 297 inside either, and 527 inside no graded item (31
    files, 60 units, `sympy.liealgebras` among them); those are mostly small
    public functions and predicates in 28 packages. Covering them needs counted
    calls the builder could not make (each of their recorded calls is shown in
    the checkout) or the tests in the reward, and stating them out of scope
    would name them; this stays open for a decision (decided the same day:
    left whole, see 2026-11-25).
  - Restrictions. The progress log is not collected, so the instruction now
    says that it is not part of what is delivered. Another copy of SymPy's
    source is kept out by the work's lack of network and by what the image
    holds, and one fetched after the work is not taken (the delivery's end of
    the work), not by a graded item. The body rules, a unit's place and name,
    edits outside bodies, the file form and speed are enforced where the tree
    is read or measured: a rejected or missing unit fails, edits outside
    bodies are not taken, a file that does not parse gives no bodies, an item
    past its time fails.
- Package. The signing key was replaced again and the flat bundle rebuilt
  (`package_single_step.py --keep-name`, content `fb5eada8e82c`, 415 files, no
  bytecode) in `ops/sympy-restoration/dist-12h/`, the round's first build
  (`87c717883415`) set aside. The platform's content hash of the new bundle,
  `a27c3b88f2d0…`, differs from version 4's (`4ce37762a342…`), and Harbor
  resolves its network plan as intended: the verifier's environment public,
  the verification without network. `oddish preflight` passed (1 task). The
  bundle equals the worktree file for file and commit `03cc17f` for every
  tracked source; the word sweep of the whole bundle found the same hits as the
  round before's, none new. After the instruction's change the key was replaced
  once more and the bundle rebuilt from commit `408818d`: content
  `54a8b4898f6e`, 415 files, platform content hash `a311bc14c28e…` (version 4's
  `4ce37762a342…`), `oddish preflight` passed; it differs from `fb5eada8e82c`
  only in the instruction and the key's two copies, and the sweep's one new hit
  is the task's own "deliver" in the line about the log.

### 2026-11-25, the units no graded item runs left whole

- The decision (panel, three of three: leave them whole now; the withheld tests
  in the reward later, once a platform run shows their phase completing;
  `swe-marathon-v2/decisions/2026-11-25-sympy-527-ungraded-units-DECISION.md`).
- The rule is the builder's, not a list: `scripts/builder/graded_coverage.py`
  traces on the original tree which unit bodies the graded items run (the 6,213
  counted calls, a returned iterator read as far as the comparison reads it,
  and the examples of the 1,847 units in the set, with `sys.monitoring` on
  every unit's body), and `scripts/builder/keep_whole.py` keeps a unit removed
  only if one of them runs it: its own counted call, or a counted call or an
  example of another unit. 527 units are run by none. Of those, 32 stay removed
  by the one exception, also by rule: a graded unit's body is a near-copy of
  theirs by the twin scan's own tests (`twin_scan.py`, with the bodies left
  whole as the visible side; 34 pairs: 4 the same tree under the same name, 6
  the same once every name is blinded, 1 text 85% alike under the same name, 24
  text 85% alike in the same file), so a whole copy would give a graded body
  away: sibling functions written the same way, such as a quadrature beside
  another or a predicate beside its converse. Each is recorded in the builder's
  report, which stays with the prepared inputs (the repository is public, and
  the names would tell which removed units nothing grades). The other 495 have
  their original bodies back.
- The checkout now: 2,176 units (numbered again from U0001 in their old order)
  in 324 files, 32,710 non-blank lines of body (37,293 before); 31 files are
  whole again, all of `sympy.liealgebras` among them. 14,867 recorded calls: the
  1,870 of the units left whole leave the call data, and none of them counted,
  so the 6,213 counted calls and the 1,847 units in the set are unchanged, and
  329 units stay out of the set (the 297 that only run inside other units'
  graded items, and the 32 near-copies).
- Every prepared input that names units was written again: the unit list, the
  agent's tree and the verifier's skeleton (each of the 355 old unit-bearing
  files rebuilt from the original with `units.blank_source`, after checking
  that the same function gives back the old file from the old list), the body
  facts, the per-unit times, the calls and the reference's files. The skeleton
  with the reference over it is the original in every file.
- Where the unit set lives, old against new: the instruction (2,671 bodies in
  355 files, now 2,176 in 324) and `task.toml`'s description; the grader's unit
  list, staged from `environment/data/units.json` (the same units in the same
  order, every field kept but the id and the rank); the placeholders in both
  trees (2,176, one per unit); the reference solution (324 files, each the
  upstream file); the body facts and times. Edits outside unit bodies: a body
  left whole is outside every unit now, so the transplant never takes it; an
  edit to one (`Quaternion._eval_evalf`) in a submitted file is not taken, and
  the file's 25 units are restored as before.
- No body left whole gives a graded unit away: none is a near-copy of a graded
  body (those stay removed), and a scan of their literals against the leaves of
  the counted calls' arguments and results matched three strings in two
  bodies, each a word of the class's own vocabulary that its file shows
  elsewhere 14 to 127 times; no long number matched. Their docstrings, and
  so their examples, were always in the checkout; only their code is new to it.
- `checks/test_graded_units.py` traces again on the skeleton with the reference
  over it and fails if a removed unit is run by no graded item (but for the
  near-copy exception, recomputed); it also holds the stated counts, the unit
  list, the placeholders, the body facts, the times and the reference's files
  together. 135 checks pass.
- Reference 1.000000 and complete (1,847 / 1,847 units, 6,213 / 6,213 counted
  calls, 14,867 / 14,867 calls, 10,428 / 10,428 tests, none unreached, nothing
  out of its time, no control tripped); the starting tree 0.0; a turn of no
  length through the hooks 0.0 (`end_from` `unchanged`, 1,716 entries listed).
- Package: key replaced, bundle `e4c15ab38d70` (384 files: 31 reference files
  fewer), platform content hash `39e86fd83463…` (version 4's `4ce37762a342…`),
  `oddish preflight` passed, the word sweep's hits the same as the round's
  last bundle, the bundle equal to the worktree and to commit `ef1561c`; the
  reference files are the upstream files and the archives differ from the
  upstream wheel only by the 2,176 placeholders, the withheld tests and
  `pytest.ini`; the call data's pickle holds only SymPy names.
- Regrade of the 16 stored submissions (examples and calls, one worker): every
  reward the same or moved by at most 0.0050 (11 down, 1 up by 0.0005, 4 the
  same; v2 trial 16 0.852, the weakest 0.003), the order unchanged, nothing
  unreached, no late file, no control tripped. 99 units moved, in 13
  submissions, and each move is explained. 96 of them run a body now left
  whole inside their own graded items, traced in each submission's own tree:
  the submission had written its own version of that function, and its body
  now meets the original (one submission's `Prufer.prev` takes its rank modulo
  the tree's `size`, whose original is computed through `prev`, so the two now
  recurse). One more calls two bodies now left whole and runs out of its time
  in an endless loop against them; one is flaky in its submission (its examples
  fail in the old tree too, under hash seeds 0 to 3); one moved up because its
  calls ran within their times this time. Table under
  [Trial evidence](#trial-evidence), with `RESULTS_12H.md` updated.
- Floor through the verifier, its fixtures built again for the 2,176 units:
  bare `raise NotImplementedError`, the first argument and the other boolean
  0.0, and the other boolean behind a table of documented outputs 0.0034, as
  before; the counted calls are the same 6,213, so the static strategies stand.

### 2026-11-26, fifth re-check and fix round 9: every removed unit graded

- The fifth re-check (four lenses, `swe-marathon-v2/qa/sympy/25-recheck-*.md`)
  failed on all four. Must-fix: removed units that no graded item checks (the
  32 near-copies kept removed, and 2 units whose graded items still pass on the
  placeholder); the examples' time records emptied by the renumbering, so every
  unit's examples ran on the 2 s floor and the check passed on an empty table;
  the instruction asking for errors that only a test shows; the time limit
  counted from the first process of `dev`, so that the end of a capped run
  could pass for a blip and a save after egress returned was graded.
  Should-fix: bodies left whole that a token-level test finds near-copies of
  graded ones; no record of what grades a unit without a counted call; a body
  that rebinds the encoder breaking the records after it in its runner;
  namespace routes past the body rules; stale counts here.
- The rule is now: a unit stays removed only if some graded item fails without
  its body. `scripts/builder/absorbed.py` makes, on the original tree, the body
  of each unit without a counted call of its own raise as its placeholder does
  (a `sys.monitoring` callback at the start of its code) and replays the graded
  items that run it, the calls compared as the verifier compares them and the
  examples run as it runs them; the unit stays removed only if one of them
  fails. The 2 units whose every item still passes (SymPy catches the error
  there and tries another way) are left whole.
- Near-copies. The near-copy tests now also compare tokens across names and
  files (a graded body of 40 tokens or more: 80% alike with names kept, 90% with
  every name blinded, or 90% of its tokens found in order in the body left
  whole), on the tokens both without and with the line and indentation tokens
  (the second is how the integrity review counts them, and finds the last 2 of
  its 8 pairs). 46 units that no graded item ran have a body that is a
  near-copy of a graded one. Each first got counted calls of its own where the
  variant builder allows them (`scripts/builder/twin_calls.py`: its twin's
  recorded arguments where the parameters fit, else variants of its own
  arguments; then the contract, the three-seed and skeleton screens, the
  echoes, the visible runs and the selection), so that every such call is
  deterministic, differs from the placeholder's result and is answered by
  nothing visible: 23 got 62 calls (54 from a twin's arguments for 21 of them,
  8 from their own for 2), and 20 of them stay removed with 56. Where no such
  call exists (23 near-copies), the near-copy is left whole with its twins (23),
  and so is every graded unit that a body left whole then gives away by the
  same tests, applied until nothing changes (32 more, among them the other 3
  near-copies that had been given calls): 78 units left whole by decision,
  whose 138 counted calls leave the reward. After each round the trace and the
  probe ran again; no other unit lost its grading with those calls.
- What the reward counts now: D is 6,137 of 14,508 calls (6,213 of 14,867
  before: 62 added, 138 out with the units left whole by decision); the set
  1,825 of 2,114 units (1,847 of 2,176: 20 joined, 42 left); the 289 units
  outside the set are each graded through a counted call (241) or the examples
  (48) of another unit that fail without their body. The checkout: 2,114 units
  in 322 files, 32,183 non-blank lines of body; against the build before, 71
  more units are whole (the 69 left whole by decision that were removed then,
  and the 2 the probe found) and 9 are removed again (6 near-copies with counted
  calls of their own, and 3 units that the new calls and the examples of the
  units joining the set fail without). A first build with the token tests
  counted one way only (commit `38486fe`, bundle `7c7478e2ca00`: 2,121 units)
  passed the preflight and the sweep; the second way then found 2 more pairs,
  and this build replaced it before any grade of it finished.
- Reference 1.000000 and complete (1,825 / 1,825 units in the set, 6,137 /
  6,137 counted calls, 14,508 / 14,508 calls, 2,114 / 2,114 units' examples,
  10,428 / 10,428 tests, none unreached, nothing out of its time, no control
  tripped); the starting tree 0.0; a turn of no length through the hooks 0.0
  (`end_from` `unchanged`). With the examples' own times back, 7 units' examples
  have a bound above the 2 s floor (up to 7.8 s) and 102 units' calls one above
  1.5 s (up to 34.8 s), at this machine's factor of 1.024; no item of the
  reference used more than half of its bound (the verifier now counts such
  items, `over_half_bound`), so no margin was widened.
- Regrade of the 16 stored submissions (examples and calls, one worker): every
  reward within 0.006 of the regrade with the units left whole (8 up by at most
  0.0027, 8 down by at most 0.0058; v2 trial 16 0.853, the weakest 0.003), the
  order unchanged but for two sessions 0.0015 apart, which swapped. Each move is
  made of the 42 units that left the set (a submission had passed 0 to 38 of
  them), the 20 that joined it (0 to 18 passing), and 32 verdict changes of
  units in both builds, in 8 submissions; each of the 32 runs, in the
  submission's own graded tree, a body whose state changed this round (31 a body
  now whole, where the original runs instead of the submission's own version,
  and 1 a body removed again). Nothing unreached, no late file, no control
  tripped. Table under [Trial evidence](#trial-evidence), with `RESULTS_12H.md`
  updated.
- Floor on these calls: bare `raise NotImplementedError`, the first argument
  and the other boolean 0.0 through the verifier (the other boolean behind a
  table 0.0034); the static strategies as before but one. A same-named
  function rose from 0.0053 to 0.0132 in the original tree, because some bodies
  left whole by decision are module-level wrappers that call back a method of
  the same name that stays removed; replayed as the unit's own body (a call
  back into the unit fails, as it would recurse in a submission) it reaches
  nothing, and the static combination 0.0163 (0.0324 in the original tree). The
  bounds that choose with the hidden results 0.0350 and 0.0290; all under the
  decision's 0.05.
- Hostile cases through the verifier's steps (one unit each, chosen by the same
  rule over this unit list: `preview` to a file, `open` with a seek, `json`
  imported and rebound, `os.fork` in a loop, a 64 MiB result, a 256 MiB print
  before the original body): 0.9721, completed; the first four refused by the
  body rules, the other two failing their own items; 1,774 / 1,825 units in the
  set and 6,048 / 6,137 counted calls, the six units and the units that call
  them (one of the refused hosts this time is a polynomial method much of
  `sympy.polys` calls, where the round before's hosts had 3 callers); nothing
  unreached, no control tripped, no evaluation error.
- Hostile trees graded as the platform grades (the shipped limits: 4 workers,
  examples 2,700 s, calls 2,400 s, the measurement 6,000 s; the rounds before
  ran one worker with four times the time): 5% of the units never end 0.6164,
  completed (691 + 708 items out of time, the phases 689 s and 694 s); half the
  units wait 0.05 s first 0.7211, completed (468 + 437 out of time, 620 s and
  1,107 s); every body never ends 0.0000, completed (2,114 + 2,114 out of time,
  1,769 s and 1,554 s); nothing unreached, no control tripped, none an
  evaluation error.
- `checks/test_graded_units.py` runs the trace and the probe on the shipped
  inputs and fails on a removed unit that no graded item fails without, and on
  a body left whole that is a near-copy of a removed one (the builder's report,
  kept beside the prepared inputs, names the bodies left whole). The
  verifier's private inputs now hold `tests/private/unit_coverage.json` (not in
  the agent's image, and nothing of it here): for each unit its counted calls,
  or the counted calls and examples of others that run it and the one that
  fails without its body.
- The examples' times are carried through the renumbering by the unit's dotted
  name, as the examples runner names its items; the check fails on an empty or
  partial table, a time for a unit not in the list, or a missing import time.
- The instruction asks for an error only where an example in its docstring
  shows it, and its completion sentence for what the examples show. The rest of
  it states what the examples and the hidden calls compare (results, types,
  containers, order, form, the state of what a call builds or changes, speed
  through each item's own time) or rules the verifier enforces, and names the
  repository tests as a help, not as what is delivered.
- The time limit counts from the start of the work again (step 0); the first
  process of `dev` only bounds when `dev` may be ended while a session runs.
  `checks/test_delivery.py` runs the real net check with a three-second limit: a
  fetch saved after egress returns is late and the file is taken from its last
  copy, and an honest rename save in the last second before the limit is kept.
- The runners make their encoder (from `json`'s C encoder) and bind their
  channel's write before any submitted code loads, so a body that rebinds the
  `json` module changes no record (`checks/test_doctest_phase.py` and
  `checks/test_comparison.py`, one check per runner, each failing on the
  runners before). Hackability finding 1 now says how far a lie reaches.
- The body rules reject a listed name taken from a namespace by a literal
  (`x.__dict__['os']`, or through `get`, `pop`, `setdefault` or `__getitem__`);
  a name computed at run time still passes, and what that buys is finding 1.
- Counts here: "12 submissions" in the entry before is 13; the stated counts are
  this build's. The integrity review's 39 functions that were never units and
  are strong twins of 22 graded units are not changed (all 22 stay removed; see
  [Remaining work](#remaining-work)).

### 2026-11-26, sixth re-check and fix round 10: the requirement in the requester's terms

- The sixth re-check (four lenses, `swe-marathon-v2/qa/sympy/26-recheck-*.md`)
  found every round-5 must-fix resolved and the build sound, and failed three
  lenses on one cause: the instruction stated the requirement as a comparison
  with SymPy 1.14.0 for every other argument a function accepts, the sentence
  class on which the platform's verdict rejected another task that day (its
  solvers described the session as an evaluation). Also: with no first process
  seen, the net check could end `dev` a moment before the platform's limit; a
  garbage-collection pause of the verifier's own process could turn an answer
  that came in time into a timeout; 7 units outside the set have examples that
  show an error that nothing counted; a short removed body is nearly its whole
  siblings' (one operator apart); listed names passed as literal keys through a
  variable or `getattr`; the floor's strongest strategy was quoted from the
  fourth re-check's calls.
- The instruction (M1) is reworded in the requester's voice. A faulty clean-up
  step in their packaging blanked the bodies of the copy their offline build
  takes in; what they need is what their code relies on for any argument a
  function accepts (the same value, type and container, order, form, and state
  of what a function builds or changes, values kept only as a cache aside; an
  equal value of another kind breaks it), the error only where an example shows
  it, and speed; they switch their build back to the copy once every function
  gives back what SymPy 1.14.0 gives. Every requirement, exception and number is
  kept, and no code span is lost; the requirement map is in
  `swe-marathon-v2/qa/sympy/FIX10-REPORT.md`. `restore`'s help and messages say
  "as the build takes it", "blanked" and "uses a listed construct", and a body
  that uses one is in the state "not allowed". A cue sweep of everything the
  agent can read or see running finds none of the comparison or judging words
  left; the hits kept are SymPy's own text, the tool's command `check`, "tests"
  for the repository's tests and doctest's "expected" output (counts in the
  report).
- The stop (M2): with no first process of `dev` seen, the net check never ends
  `dev` by time, only once a fresh look finds no session, or the collect step
  does. `checks/test_delivery.py` runs the real net check with no first process
  and an opening after the limit: the opening is an end of the work, and `dev`
  is not ended (the net check before ends it).
- The readers (M3): before it calls an item out of its time the verifier reads
  once more, without blocking, what is already waiting, and it freezes its
  loaded inputs out of the collector's reach (`gc.freeze()`) before anything
  runs. Checks: an answer waiting in the pipe when the reader looks only after
  the deadline is taken (the reader before called it a timeout), and the freeze
  comes after the inputs load and before the delivery is read. A probe with the
  private inputs loaded (3.83 million objects the collector tracks; a full
  collection 1.62 s): a stand-in runner answers 0.9 s before the reader's
  deadline while a collection runs; the reader before called it a timeout 3
  times of 3, the new one took the answer 3 times of 3, and with the inputs
  frozen the collection took 0.00 s.
- Errors the examples show (S1): 7 units outside the set have docstring
  examples that show an error, 6 by doctest's own reading and one at a `sage:`
  prompt, which the auditor's text search counted and doctest does not run.
  Each has a counted call that expects that error: the example's own call,
  taken at the unit's entry on the original tree and replayed under three
  seeds (8 calls, `scripts/builder/error_calls.py`), compared by class. They are
  counted although the example makes them, since what they grade is the one
  thing the example states; a body that raises that error for every argument it
  does not know would answer them too (7 units and 8 calls at most). The 7
  units join the set, so their examples now count, and two units whose bodies
  those examples run, whole before, are removed again by the rule.
- The short twin (S2): the near-copy tests also compare a graded body of 20 to
  39 tokens, at 90% alike as tokens with names kept. Over the whole build this
  finds one pair: a predicate whose two whole siblings differ from it by one
  operator. The siblings cannot get a counted call of their own (every
  candidate's result is a boolean their examples show), so the predicate is left
  whole with them; the closure ran again to a fixed point with nothing more
  given away.
- The body rules (S3): any listed name as a literal key is refused, whatever
  holds it (`x['os']`, `d.get('sys')`, a namespace kept in a variable or taken
  with `getattr`); no reference body is refused. A name built at run time from
  pieces, never written whole in the body, still passes; what that buys is
  hackability finding 1.
- The build: 2,115 units in 323 files, 32,217 non-blank lines of body; 14,523
  calls, 6,145 counted (8 of them errors), 1,832 units in the set; the 283
  outside it each graded through a counted call (233) or the examples (50) of
  another unit that fail without their body. Against round 9's build: one unit
  whole again (the predicate), two removed again, 7 units and 8 counted calls
  joined.
- Reference 1.000000 and complete (1,832 / 1,832 units in the set, 6,145 /
  6,145 counted calls, the 8 errors among them, 14,523 / 14,523 calls, 2,115 /
  2,115 units' examples, 10,428 / 10,428 tests, nothing unreached, no item out of
  its time or over half of it, no control tripped, 903 s); the starting tree
  0.0; a turn of no length through the hooks 0.0 (`end_from` `unchanged`).
- Package: key replaced, bundle `1f1b2f2ab4fa` (384 files), platform content
  hash `5cefe91fe0fe…` (version 4's `4ce37762a342…`), `oddish preflight` passed;
  the bundle equal to the worktree and to commit `c55180c`; the 323 reference
  files the upstream files, the archives the upstream wheel but for the 2,115
  placeholders, the withheld tests and `pytest.ini`; the word sweep's agent and
  hook lines those of `32fbeb905028` less every "deliver" of the tool and the
  instruction.
- Floor on these calls (S4): bare `raise NotImplementedError`, the first
  argument and the other boolean 0.0 through the verifier (the other boolean
  behind a table 0.0034); one constant 0.0065, a type default 0.0103,
  delegation 0.0052 and 0.0132 in the original tree (0.0003 and 0.0 as the
  unit's own body), the combination 0.0324 (0.0163); the integrity reviewer's
  rules 0.0063 (0.0120); the bounds that choose with the hidden results 0.0350
  (0.0172) and 0.0290. The accessor synthesis, the strongest strategy a
  submission could build, graded again on this build (the fourth re-check's
  tree, of which only the current units' bodies are taken): 0.0175 as a tree,
  0.0356 behind a table of documented outputs, 0.0384 with its per-call tables
  (0.0173, 0.0373 and 0.0401 on the fourth re-check's calls). 8 of its bodies
  now fall under the body rules; were all 18 of their counted calls matched,
  0.0413, and 0.0426 with the error strategy of S1 too. All under the
  decision's 0.05; the sixth re-check's bound, 0.0497, counted every new call
  as matched.
- One hostile tree graded as the platform grades (5% of the units never end;
  the shipped limits: 4 workers, examples 2,700 s, calls 2,400 s, the
  measurement 6,000 s): 0.5862, completed (775 + 733 items out of time, the
  phases 681 s and 635 s); nothing unreached, no control tripped, no
  evaluation error. Round 9's tree had 0.6164: the draw is the same rule (106
  units, the same seed) over unit ids the rebuild renumbered, so other units
  never end.

### 2026-11-26, seventh re-check and fix round 11: a first process seen twice, the placeholders in the story

- The seventh re-check (`swe-marathon-v2/qa/sympy/27-recheck-*.md`) passed the
  verifier and reward lenses and raised concerns in the auditor and integrity
  lenses, with no must-fix. Its items: Harbor's short `pwd`, run as `dev` after
  the setup step and before Harbor's clock, could be taken for the first
  process if a look caught it, so that a blip of egress during the turn would
  end `dev` before Harbor's limit (0.79 s early in the integrity lens's probe);
  `/app/ATTRIBUTION.txt` said that the bodies of "selected" functions "were
  replaced by placeholder statements", a curated change at odds with the
  instruction's faulty clean-up step; nothing in the story wrote the numbered
  placeholders; the error comparison also took a base of the expected class; the
  last line of `restore rules` stated a rule ("another way") that nothing
  checks; two claims of this README about the limit no longer held; and
  `RESULTS_12H.md` was a round behind.
- The first process (made a must-fix by the brief, since the platform's verdict
  rejects any stop before `timeout_sec`): a process counts only once two looks
  at least 1 s apart both see it alive, with the same start, so a command that
  lives milliseconds never does; the record counts the ones seen once and gone
  (`first_process_passed_over`). `first_process()` takes no process from one
  look in any call, so the re-check's own probe, which calls it once, now finds
  no first process and ends nothing. `checks/test_delivery.py` runs the shipped
  watch on a stand-in `/proc` with the limit scaled to 3 s: `pwd` under a root
  `su` for one look, Harbor's clock at 1.0 s, the agent's session from 1.3 s, a
  blip at 1.7 s. The first process is the session, the blip waits, and `dev` is
  ended only after the agent's limit; on the net check before, the first
  process is the `pwd` (the check fails there).
- The story: `ATTRIBUTION.txt` now says that a faulty clean-up step in the
  requester's packaging blanked the bodies of functions and methods in this copy
  and dropped part of its test suite, and that their recovery tooling then
  marked each blanked body with a numbered placeholder statement; the
  instruction ("Once we noticed, our recovery tooling marked each blanked body
  with one numbered placeholder statement") and `restore`'s help credit the
  placeholders and the tool to the same tooling. `restore rules` ends with the
  literal-key line; the sentence about reaching the same things "another way"
  is gone, since nothing checked it. `checks/test_packaging.py` pins each of
  these.
- The error comparison: a call whose expected result is an error is answered
  by that class or a subclass of it, never by a base (`canon.same`, in which
  the verifier gives the candidate's form first; the build's two comparisons of
  errors now do too). One of the 8 error calls expects a class with named bases;
  its unit's examples ask for the exact class already. A check compares the
  class, a subclass, a base, the root base, a sibling, the placeholder's error
  and a value (it fails on the comparison before, which took the base).
- This README: the time limit counts from the start of the work, and the first
  process is one two looks a second apart saw alive, which Harbor's `pwd`
  cannot be (both under [Verification](#verification)); the rules passage and
  the error-call passage say what the code does.
- Checks: 147 pass at `1b6a171` (the three new ones among them), and the
  delivery, packaging, comparison and transplant checks (93) again at
  `93d26de`, which changed only the net check. Package: key replaced,
  bundle `cbe004ce22d8` (384 files; only the instruction, `ATTRIBUTION.txt`, the
  net check, `restore.py`, `unitcheck.py`, both staged copies of
  `restorelib.py`, `canon.py` and the key differ from `1f1b2f2ab4fa`), platform
  content hash `22886dfb8414…`, `oddish preflight` passed, the bundle equal to
  the worktree at commit `93d26de`. The call data, the units and the
  archives are round 10's.
- Reference 1.000000 and complete (1,832 / 1,832 units in the set, 6,145 /
  6,145 counted calls, 14,523 / 14,523 calls, 2,115 / 2,115 units' examples,
  10,428 / 10,428 tests, nothing unreached, no item out of its time or
  over half of it, no control tripped, 974 s); the starting tree 0.0; a
  turn of no length through the shipped hooks 0.0 (`end_from` `unchanged`).
- The 16 stored submissions regraded on this build (one worker, as in round 9):
  0.003 to 0.853, each within 0.0005 of round 9's regrade (11 up, 5 down), the
  order unchanged; table under [Trial evidence](#trial-evidence), with
  `RESULTS_12H.md` updated to this build's basis.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-restore-bodies` | Implemented. Instruction, agent image, separate verifier image, reference solution. |
| Further steps | Not designed. See [Workload](#workload). |
| Prepared inputs | Present locally under Git-ignored paths; produced by the builder in `scripts/builder/`. |
| Oracle | 1.0 on the platform under the binary reward (at least 14 grades); 1.0 under the continuous reward through the entry point's steps on this machine (2026-11-20, and after each re-check and rebuild since, last 2026-11-26). Not yet re-run on the platform. Provenance: the original SymPy 1.14.0 source of the 323 files. |
| Ratings (`harbor check`) | Not run. No `[metadata.task_rating]` yet. |

Layout notes:

- `common/restorelib.py` is the one source of the code that copies unit bodies
  into the skeleton. Packaging stages it into the agent image (for `restore`) and
  into the verifier image.
- `environment/pyproject.toml` lists the Python packages of both images.
  Packaging stages it into the verifier build context as `runtime/pyproject.toml`.
- Git-ignored prepared inputs: `environment/data/` (workspace archive, unit
  list, the key the collect step signs with, written by
  `scripts/builder/delivery_key.py`), `tests/private/`
  (skeleton with the full test suite, sealed test list, recorded calls,
  reference results) and `solution/data/` (original
  source of the 323 files). Packaging stages the key into the verifier's private
  inputs as well.
- `environment/fsmaint-reserve`, `fsmaint-netcheck` and `fsmaint-sweep` are the
  setup and collect hooks (`task.toml`). They live in `/usr/local/lib/fsmaint`,
  mode 0700 and owned by root, off `PATH`; the agent's user cannot read them,
  and `ps` shows only the net check (root) and its probe (`nobody`) by their
  paths: the probe gets the hosts it polls on its standard input, so no command
  line names one. The names were kept: the sibling Carve passed two audits with
  the same ones. What the probe can be made to see is bounded elsewhere: a probe
  whose handshakes time out under load still reads as closed, and the session
  end and the time limit bound the work whatever it read.
- The agent runs as `dev` (uid 10001). `/app` is root-owned and sticky,
  `/app/sympy` is root-owned and world-writable with everything in it owned by
  `dev`, so `dev` can change every file but cannot replace the tree itself.
  `/app/PROGRESS.md` is created for `dev`; `/opt/restore` is read-only except
  `var/`, where `restore` keeps its delivered-form copy and its state.

## Design dimensions

### Novelty

What it adds: one coherent body of work that is too large for one context window
(2,115 units, 32,217 non-blank lines of body) with a grade per unit, so partial progress is
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
- Tasks in this repository: no overlap with `knowledge-work-assistant`.

Weaknesses, stated plainly:

- SymPy is public and in pre-training data, and for a strong model much of the
  work is recall. On the best run of the flash model every trial so far used
  (base trial 5, relace/deepseek-v4.1-flash) 546 of the 2,671 bodies it submitted (the unit set then)
  (20.4%) had the same syntax tree as upstream: 51.6% of bodies of one to three
  lines, 9.1% of four to ten, 1.8% of eleven to thirty, none over thirty (sizes
  by `ast.unparse` lines). That figure does not carry to frontier models. A
  frontier model reviewing the task (Claude Opus 5.5), working from the agent's
  view only, restored 22 sampled units (ten at random, six graded on object
  state, six from the units every run failed): 22 of 22 passed, 106 of 106
  hidden calls matched, and 18 of the 22 bodies had upstream's syntax tree,
  long ones included (8 of 9 at eleven to thirty lines, 2 of 4 over thirty).
  All 35 graded sessions so far used relace/deepseek-v4.1-flash or
  relace/glm-5.3, so difficulty for the models this benchmark targets has not
  been measured.
- Before a frontier model's score is read as difficulty, probe its recall: a
  stratified sample of at least 60 units, one shot each from the agent's view,
  scored by syntax-tree identity with upstream and by hidden-call match. Every
  grade reports `identical_bodies` in `metrics.json` (the share of restored
  bodies whose syntax tree equals the original's, by size of the original body,
  from hashes of the original bodies; no body is shipped), so a recalled result
  shows next to its reward.
- 852 units (31.9%) have one to three non-blank lines; they hold 3.2% of the
  lines. Most of the effort is in the other two thirds, but a unit count
  overstates the work. `metrics.json` reports the unit share weighted by the
  original bodies' lines (`unit_share_by_lines`).

Next validation: the recall probe above for each target model; durable: rebuild
on a library or release the target models have not seen, take subsystems whole,
drop units under four lines.

### Verifiability

Every unit has examples in its own docstring and at least one recorded call whose
reference result comes from the original implementation. Results are counts over
fixed lists, so partial progress needs no judge. See [Verification](#verification).

Evidence: the reference solution scores 1.0 (every counted unit and call; all
2,115 units and 14,523 calls on the bars of a complete restoration); an empty
delivery and a tree of bare `raise NotImplementedError` bodies score 0. Grading
one submission twice on the platform gave 9,298 and 9,305 passing tests before
the deadline and seeding fixes of 2026-11-20; the examples are now seeded per
unit, which removed the one known source of unit flips (a random draw).

### Realism

Restoring lost implementation from signatures, documentation and tests is real
but uncommon work (damaged checkouts, partial ports, code removed for licensing).
The setting is contrived in one respect: nobody loses 2,115 bodies at once while
keeping every docstring. Realism is the weakest of the five dimensions together
with novelty.

### Difficulty

Time is not the barrier. Two things are:

- An invisible floor. A hidden call compares the value, type, container, order,
  form and object state the function produces. For some units nothing the agent
  can see fixes the property a call compares: the container `permute_signs`
  yields for a list, the split `BlockMatrix.LUdecomposition` uses, the
  tie-break in `allcombinations`. Every
  measured run had 39 to 77 units that passed every check the agent can run and
  matched no hidden call. A second 9.6-hour session fixed 0 to 7 of them while
  fixing 74 to 133 visible failures, and the pool grew; 9.0 hours gave 96.2% of
  units and 19.2 hours 96.1%. Under the binary reward this floor sat above the 26
  units the 99% bar allowed, so no honest run could reach 1 and 35 of 35 graded
  sessions scored 0. On the counted calls the residue is larger than the unit
  count suggests, since counted calls are exactly what nothing visible shows: the
  six full-session claude-code runs have 107 to 146 units in the set whose
  examples pass and that match no counted call (5.8% to 7.9% of the
  1,844), 51% of them matching a documented call.
- Recall. Closing the floor needs upstream's exact internals, which only memory
  of SymPy supplies (see [Novelty](#novelty)). A frontier model may score high by
  recall; probe it before reading its score as difficulty.

Partial credit follows the call graph: a unit counts only once the units it
calls work, so work in `restore next` order scores about its share (the first 20%
of units, 0.150) and scattered work far less (a random 20%, 0.033).

The rest is breadth. Single-context runs stopped at 588 to 1,824 steps when their
context filled; only a harness that compacts and delegates to helpers reached the
end (15,678 to 45,324 steps in 9 hours), and the unit share tracks steps and
helper count more than anything else. On the continuous reward the stored
submissions read 0.003 to 0.857: 0.685 to 0.857 for claude-code with helpers over a
whole session, 0.33 to 0.40 for Proximus in one thread, 0.09 to 0.22 for
mini-swe-agent, 0.020 and 0.003 for two runs that ended their turn within 41 minutes (see
[Trial evidence](#trial-evidence)). For a parallel harness with a flash model that is the
easy end beside the sibling rebuild tasks; compare models within one harness only.

### Initial feasibility

Solved by construction: the original source is the reference solution and scores
1.0. For an agent, reward 1 needs every counted unit and call, the invisible
residue included; no run has reached it, and more time did not shrink it.

## Workload

v2 asks for at least five days of agent execution. This task does not meet that.
Since 2026-11-19 a trial is one working session inside Oddish's 12-hour attempt (the
agent's limit 34,560 s); since 2026-11-24 the instruction states no time figure and
says only that the run can end at any time. With the earlier 9-hour limit the
best run used all of it at about 4,300 steps per hour and reached 96.2% of units;
one 12-hour session reached 82.3% at best; two 48-hour sessions (19.2 hours)
reached 2,568 of the 2,671 units of the set then at best (experiment `sympy-restoration-v2-48h-20261117`).

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
That image's build installs its system and Python packages, so its environment
has public egress (`[verifier.environment] network_mode = "public"`); the
verification itself runs with none (`[verifier] network_mode = "no-network"`,
to which Harbor switches that environment before it runs the tests), and the
verifier refuses to measure, an evaluation error, when a public host answers
its handshake.

0. Delivery (`verifier/delivery.py`). The work runs as `dev`. A root setup step
   records when the work started, to the fraction of a second, and starts
   `fsmaint-netcheck`, which keeps watch until the collect step stops it. It
   polls three public hosts with a TLS handshake (as `nobody`, in a probe
   process of its own that gets the addresses on its standard input) every
   0.1 s: a poll is open when a handshake completes, local when none does and
   an attempt failed for a reason of the machine rather than of the network (no
   free local port or address, no file, buffer or memory, a thread or probe that
   would not start), and closed otherwise. Closed polls in a row make a stretch;
   local polls neither extend nor end one, however many come in a row (they are
   counted, and the longest run of them kept). A stretch of at least three ends
   at an open poll: its last closed poll is recorded, with whether an exec
   session was seen alive then and whether the time the work is given had run
   out; every process of `dev` is then stopped and ended once a fresh look finds
   no session alive, or once that time, counted from the first process (below),
   has run out, and not before, so nothing ends the agent while its session runs
   within its limit; with no first process seen it is never ended by time. It looks at `/proc`
   every 0.1 s for the exec sessions of `dev`: a process of `dev` whose parent is
   a process named `su` or `runuser` of the real user root (not the first
   process), or that has no parent in the container. Harbor runs every command
   of the agent as `su dev -s /bin/bash -c ...` on Modal and as `docker exec -u
   dev` under Docker; a process the agent starts, in the background or detached,
   has a parent of `dev`, then the first process, never such a parent, so it is
   never a session. The time the work is given, 34,560 s (the agent's limit in
   `task.toml`; a check holds the two equal), counts from the start of the work,
   which the setup step takes before Harbor starts the agent's own clock, so the
   work ends no later than Harbor's limit and a fetch after it saves nothing
   that counts. The same looks find the first process of `dev`: one that began
   after the work did, whose parent is not one of `dev`'s (its start read from
   `/proc` in clock ticks since boot), and that two looks at least 1 s apart
   both saw alive, with the same start. After the setup step and before its own
   clock starts, Harbor runs a short `pwd` as `dev` (Harbor 0.20's step
   preparation); a look can catch it, but it is gone within milliseconds, so it
   is never the first process (since fix round 11; the record counts such
   processes in `first_process_passed_over`). The agent's exec session, which
   Harbor starts after its clock, counts a second after it starts (claude-code,
   mini-swe-agent and the oracle run one for the whole turn; a harness that runs
   one exec per command gives its first command that lives a second or more,
   later still). The first process serves only to say when `dev` may be ended
   while a session still runs: not before that time counted from its start, so
   nothing ends the agent within its own limit; with none seen, never by time. A
   save in the last seconds before the end is kept by the copies below. It gives
   every process of `dev` a limit of 8,192 processes of that user, so that a process that forks
   without end leaves room for the steps after the work. And from 300 s before
   that time runs out until it does, every second, it copies each unit file that
   changed since its last copy into a folder only root can read (room for this
   was set aside at setup and is given back before the first copy, or by the
   collect step when there was none), when the
   file has not changed since that look began and stays the same file with the
   same times while it is read; it keeps the last two copies of each, with the
   time at which the file held that content, and makes its last look once the
   time has run out, of what had not changed by then. When the work ends, the
   collect step (`environment/fsmaint-sweep`, root) first says that it has
   begun, with the shell's own commands only, in a file the setup step made
   whole for it (`/var/lib/fsmaint/out/progress`, copied beside the tree), so
   that this is said even when no process can be started. Then it stops every
   process of `dev`, gives back the room the setup step set aside, and puts the
   tree aside with an empty tree in its place holding a signed mark that refuses
   it ("the step that measures the tree did not finish"), so that a timeout, a
   crash or a full disk from then on leaves a tree copied as refused (0), never
   one without a mark; then it lists the stopped processes and ends them (live
   ones only, for at most 30 s). It probes the hosts itself, lets the net check
   finish one poll and one look that started after that and stops it, records
   every entry of the tree (type, size, modification and change times, sha256)
   before touching anything, removes every link (one step each: no link is
   resolved), anything that is neither a file nor a directory and any file whose
   name a copy might not carry as it is, checks that there is room for the
   platform to pack the tree in `/tmp` (removing first what `dev` left in `/tmp`,
   `/var/tmp` and `/dev/shm` when it is short), puts the copies in place of the
   unit files changed after the end (below), writes a record and a mark into the
   tree, gives it back its name (the two names exchanged in one step where Linux
   allows it), and says that it has finished. The mark holds at most 60 notes of
   at most 240 characters; the record keeps them all. The end of the work is the
   earliest of three. One is the last closed poll of the longest stretch an
   opening ended, except an opening seen while an exec session was alive before
   the time the work is given ran out: the hosts answer again only once the work
   has ended, so such an opening says nothing of its end. A stretch still going
   on, or one whose last closed poll came after the collect step began, gives the
   collect step's start only when the collect step's own probe found the hosts
   closed, and nothing otherwise. The second is the last time the exec session
   that ended last was seen alive, when that session began within ten minutes of
   the start of the work (one session for the whole of the work, as claude-code,
   mini-swe-agent and the oracle run) and no session was alive when the collect
   step began; a harness that runs one exec per command gives no such end. The
   third is the time limit: the start of the work plus 34,560 s. No end is later
   than it, and when the collect step began
   after it with no other end known, it is the end, whatever the sessions show
   (nothing fetched can come before it); no kill enforces it (a killed
   claude-code exits 137, and Harbor classifies that exit by its transcript,
   whose failed fetches read as network errors that void the score). Without
   any, the start of the work is the end when nothing in the tree changed since
   then (the no-op); when the work itself hid the end from the probe (it could
   not see the network at all, or saw no answer while the hosts answered the
   collect step at the net check's own addresses within the time its polls
   allow) the tree is refused, a scored 0; otherwise there is no end. A unit
   file whose change or modification time is at or after the end, less 0.25 s,
   is replaced by the last copy the net check took of it that held its content
   by the end, and its entry in the record says so (the copy's size, digest and
   times, when the file held that content, what was replaced, and the units
   whose bodies differ between the two). Only a turn run to its limit needs
   this: Harbor does not end the agent at its limit, claude-code goes on until
   it is stopped and saves by writing a new file and renaming it, so without the
   copy one save in that second or two returned the whole file, with every body
   written in it before, to the skeleton. The collect step refuses a tree over
   256 MB (the starting tree is 23 MB), which the platform's copy might not carry
   through its two transfers.
   The mark is signed with a key in the agent image
   that only root can read and that the verifier image holds too. Before
   grading, the verifier checks that its own network is closed (a TLS handshake
   to three public hosts; open is an evaluation error), then reads the mark: no
   tree, no mark, an unreadable, oversized or unsigned mark, a record that
   differs from the signed one, a listed file that did not arrive as listed, a
   link or an unlisted file that arrived, or a record that says a live process
   of `dev` outlived the collect step is an evaluation error (no reward file),
   since the collect step always leaves a marked tree and these come from the
   infrastructure; except when no mark the key signs arrived and the collect
   step's progress file says it began and did not finish: the work kept it from
   running (a process that forks without end leaves it unable to start any), so
   what arrived is an empty delivery, scored 0 with a note. A tree the collect
   step refused is a completed evaluation of
   an empty delivery (0): nothing usable under its name (nothing at all, a link,
   a file), a tree it could not list, one past its limits (200,000 entries,
   256 MB, 64 directories deep, a path over 1,000 bytes, a record over 48 MB, a
   directory whose name a copy might not carry), one there is no room to copy, or
   the empty tree left by a collect step that did not finish (a refusing mark is
   taken as signed even when the record beside it is newer: nothing of a refused
   tree is graded). A record without an end of the
   work grades a tree that restores no unit (0) and is an evaluation error for
   any other. A unit file the collect step replaced by its last copy is taken as
   that copy (`copied_files`, and the units whose bodies changed after it in
   `units_changed_after_the_end`); any other file whose change or modification
   time is at or after the end, less 0.25 s, is not taken over: its units are
   `late` and count as not restored. The transplant never reads a unit file
   through a link. `late_files`, `egress_open`, `end_from`, `end_note` and the
   collect step's record go to `metrics.json`.
1. Graded tree. Start from the reference skeleton. For each unit, copy in the body
   found in the submitted file for the function of the same qualified name.
   Nothing else from the submission is used. A body containing one of the listed
   constructs for reaching the process, the file system, the interpreter or a
   test framework is refused (`common/restorelib.py`); the rules are lists of
   names, which the agent can read in full (`restore rules`), and since fix
   round 11 they state nothing beyond them: a body that names a listed name only
   through a string built at run time passes, and runs as every body does, in
   the sandbox (see the hackability table, finding 1).
   The whole measurement has one deadline, 6,000 s from its start
   (`measure_budget_sec`), inside the verifier's 6,600 s. The docstring and call
   phases also have their own caps (45 and 40 minutes), now only a guard: each
   item has a bound of its own (below), and the caps are sized so that a tree
   whose every body runs out of its bound still finishes both phases on the
   platform's four workers (about 37 and 32 minutes at this machine's speed);
   the test phase has what they leave. Every deadline is on the monotonic clock.
   Submitted code runs with a 4 GiB address-space limit, a 256 MiB limit on the
   size of a file and 1,024 processes, where `prlimit` can set them (a note says
   when it cannot); each start of a runner gets a private folder for its
   temporary files, removed after it, and what the sandbox user left in the
   folders it can write to is removed between phases. Every file the verifier
   writes is guarded: when a write fails (a disk the sandbox filled), what the
   sandbox left is removed and the write tried once more, else it is noted and
   the measurement goes on; 64 MiB set aside on the result's file system before
   anything runs is given back just before the result is written.
2. Docstring examples. Each restored unit's own examples, run the way SymPy's
   doctest runner runs them. Python's and both of SymPy's random generators are
   seeded from the unit's name before its examples run, so a unit's draw is the
   same in every grading (and in `restore check`). One process runs the units of
   one module: it gets them on its standard input and answers on a descriptor of
   its own, one JSON line at a time (its standard streams go nowhere), and holds
   no key. The verifier reads those lines in pieces, at most 1 MiB a line and
   64 MiB in all, and takes them only in their order (the module imported, then
   each unit's start and its record), rebuilding each record from the runner's
   own fields; anything else ends the process. Before it calls an item out of
   its time it reads once more, without blocking, what is already waiting, and
   it keeps its loaded inputs out of the garbage collector's reach
   (`gc.freeze()`), so that a pause of its own process does not turn an answer
   that came in time into a timeout (fix round 10). A unit's examples get ten times
   the original's own time for them on this machine (measured before any
   submitted code runs), never less than 2 s; a module's import five times its
   own, never less than 10 s. A unit that takes longer, or during which the
   process ends or writes anything else, fails (`timeout`, `crash` or `error`),
   and the module's other units run in a new process, since an interrupted body
   can leave global state behind. After each unit the runner checks that it
   still fails a wrong example and passes a right one; a failed check fails the
   whole module and trips a control. Units left when the phase's time is up are
   not reached (see Reward formula for how they count).
3. Recorded calls. 14,523 calls, at least one per unit, replayed one at a time
   in the sandbox, the same way: one process per module gets its calls on its
   standard input and answers one line per call, at most 4 MiB a line and
   256 MiB in all, taken only in order. Each call gets ten times the original's
   own time for its unit's calls on this machine, never less than 1.5 s; a call
   past it does not match (its result is a Timeout), nor one during which the
   process ends or writes out of order, and the rest of that call's unit is not
   run (it does not match either); the module's other calls go on in a new
   process. The verifier compares each result with the reference result, which
   the sandbox cannot read. They are the calls of the units that stay removed
   among the 16,803 recorded for the 2,671 units of the first unit list: 13,382
   from SymPy's own test suite and, for units it never calls directly, from
   docstring examples; 3,355 added on 2026-11-20 for 990 of the 1,697 units whose
   recorded calls were all documented; 66 added in fix round 9 for near-copies
   of graded bodies (their twins' recorded arguments where the parameters fit,
   else variants of their own, through the same screens); and 8 added in fix
   round 10 that expect the error a docstring example shows (below). Of the 3,355, 1,567 were
   recorded while the withheld tests ran and 1,788 made from
   the unit's own arguments, with every symbol renamed by one map over all of
   them or one integer shifted (never an integer whose docstring states a domain,
   such as prime, odd or positive, nor a polynomial routine's level, and an
   integer argument never to a value outside the range of the unit's recorded
   calls unless the docstring describes a plain integer; a candidate that breaks
   a prime contract its docstring states is dropped), each result taken from the
   original. A call is
   documented when a docstring example or a visible test (slow ones, ones marked
   to be skipped and examples marked `+SKIP` included: the agent can read them)
   makes a call with the same arguments, directly or inside the library while it
   runs, or with the same arguments up to a renaming of symbols that keeps their
   assumptions; when its result is one an example or a visible test shows, that
   is, one its unit returned to a call an example or a test made directly; when
   its result is one of its own arguments unchanged, or an element of its
   `*args` or a value of its `**kwargs` (a body that returns that argument
   answers it); or when its result is one that another documented call of its
   unit returns (applied until nothing changes). These relations compare with
   the type of a value left out, since a printed result does not show it. 8,378 calls are
   documented and listed privately (`tests/private/vectors/documented.json`),
   6,145 are not, and only those count for the reward. A result is
   compared by its canonical form (`verifier/lib/canon.py`), which keeps the
   value and the type and container of every part of it, the order, the form of
   a returned expression and the state of every object the call builds or
   changes: a Python `int` and a SymPy `Integer` are different results, as are a
   `bool` and SymPy's `true`, a `tuple` and a `Tuple`, a `Fraction`, a
   `PythonMPQ` and a `Rational`, a Python `float` and a SymPy `Float`, two
   Floats of different precision, the matrix classes (mutable or immutable,
   dense or sparse), a domain matrix's dense or sparse storage, a `set`, a
   `frozenset` and a set subclass, a `dict`, a `defaultdict` (with its factory),
   an `OrderedDict` (with its order) and a `Counter`, a list, a range and a dict
   view, and each kind of iterator. A call that returns a value and changes an
   argument is compared on both (188 recorded results); a memo slot it fills is
   no change. What the comparison leaves out is all of this, each for the
   reason given: a memo slot an object fills lazily counts where both sides hold
   a value (for a dict of them, on the keys both hold), as the instruction
   exempts values kept only as a cache (197 counted results hold one); Dummies
   the call makes compare up to one consistent renaming, and a frame's creation
   counter (`ReferenceFrame.index`, which orders a vector's printed components)
   for frames the call makes up to an order-preserving one, because both are
   numbered from a process-wide counter: the original's own results differ
   between runs exactly there and nowhere else (144 of the 16,737 recorded then differ in text over
   three runs, every one only in those names), while a Dummy or frame that came
   with the arguments is exact; Truss's coordinate lists in what
   `Truss.remove_node` leaves, where upstream keeps them inconsistently; the
   LaTeX of `multiline_latex` and `vlatex`, compared without the whitespace LaTeX
   ignores (a blank line, which is a paragraph break, is kept); a SymPy Float of
   the same precision (compared exactly), or an mpmath number at its precision,
   within a relative 2^(2 - precision) of the larger value, 2 to 4 units in its
   last place by where it lies in its binade, and exactly below 4 bits; and a
   Python float within a relative 2^-50, zero only against zero, with no
   absolute tolerance: the reference results were recorded on one machine and
   are compared on another (the third re-check replayed every call with another
   allocator and with every transcendental result of `math` and `cmath` one unit
   off, and no recorded result moved, so this is a margin for the image's own
   Python and C arithmetic, not a need; 173 counted results hold a float, 158 of
   them a SymPy Float, 16 below 53 bits);
   the order of a dict's items,
   which Python's equality ignores and SymPy prints sorted, so that no example
   or test can show it (401 counted results hold a dict of two or more items);
   and a SymPy matrix's internal domain, which SymPy picks for its own
   arithmetic (the class, shape and entries are compared); the module's sieve as grown by `Sieve.primerange`, `totientrange` and `mobiusrange`, a cache they may fill as they like (only what they return counts; `Sieve.extend` and `extend_to_no`, whose growth is the behaviour, count the sieve whole); and, past 40,000 nodes, an object's state, which is then compared by its printed form (9 counted calls change an argument that large: `Joint._create_aligned_interframe` 5, `Point.v2pt_theory` 4), where a frame shows only its name. One process
   replays the calls of one module. If it ends by itself or stays silent for 40
   seconds, the call it was on does not match and the calls behind it are
   replayed in a new process; if not even the first call of that start returned,
   the rest of that call's unit does not match either and the job resumes at the
   next unit. After a call that ran out of time the runner exits and the calls
   behind it run in a new process; a unit whose calls ran out of time, or stopped
   the runner, twice does not match on the rest of its calls, which are not run.
   A job ends after 16 starts that ended or stopped. The random generators
   (Python's and both of SymPy's) are seeded from
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
Limits:

- A recorded call checks one input, so a body can match its calls and still be
  wrong elsewhere.
- Reference results that could not be reproduced exactly (objects that lose state
  when pickled, bare `None`, exceptions, unstable ordering, results over 2 MB)
  were dropped at build time, so error behaviour is measured by the examples
  (an example that shows an error passes only on that error's class) and the
  repository tests (309 withheld test functions assert an exception, reported
  and not rewarded). The 7 units outside the set whose docstring examples show
  an error have, since fix round 10, a counted call that expects it: the
  example's own call (8 in all, `scripts/builder/error_calls.py`), its result
  that error, compared by class: the expected class or a subclass of it, never
  a base of it (one way since fix round 11). It is counted although
  the example makes it, since what it grades is the one thing the example
  states; a body that raises that error for every argument it does not know
  would answer it too (7 units, 8 calls).
- 283 units have no call that nothing visible answers. Of the 2,671 units of
  the first list, 824 had none (2026-11-21: 716 from the first re-check's round,
  for which no candidate survived the screens, a visible run made every
  candidate, or every candidate returned an argument or a documented result;
  108 more from the second re-check's rules); most of those are whole now (no
  graded item fails without them), 27 have counted calls of their own since
  fix rounds 9 and 10, and these 283 stay removed because a counted call (233)
  or the examples (50) of another unit fail without their body (`absorbed.py`;
  the verifier's private `tests/private/unit_coverage.json` names that item for
  each of them). They are left out of the reward's unit set and counted
  (`units_left_out`), and graded through those items. They are smaller than the
  units in the set (median 5 non-blank lines against 9) and hold 91 of the 99
  units whose recorded results are all booleans, since any boolean an example
  shows documents every boolean result of its unit. The set covers 89.4% of the
  body lines. Their examples and calls are still run and reported
  (`units_left_out_passing`).
- For some units no visible evidence fixes the property a hidden call compares
  (see [Difficulty](#difficulty)); that residue is part of the reward.
- A unit counts only once the units it calls work, so partial credit follows the
  call graph rather than the number of bodies written: on the final calls, the
  first 20% of units in `restore next` order restored from the original (534
  units: 17.2% of the units in the set, 15.5% of the counted calls) scored 0.150
  (u 0.169, c 0.150) through the verifier's steps, and a random 20% (seed 0;
  19.4% of the set, 19.1% of the counted calls) 0.033 (u 0.033, c 0.058), since
  most of its units fail their examples through units not restored yet (0.157
  and 0.044 in the second re-check, on the calls before this rebuild).
- Three added calls carry an integer outside the range of their unit's recorded
  calls (`isolate` twice, `_invert_modular` once) and one a pair of indices that
  together fall outside the function's domain (`flip_index`); each is a valid
  input or follows the documented formula.
- Strings are compared exactly, layout included, while the docstring examples
  are checked with whitespace normalised; only the LaTeX of two units ignores
  whitespace. A memo slot filled with a wrong value where upstream leaves it
  empty is not seen by the call that fills it. A dict's order and a matrix's
  internal domain are not compared (see step 3).

Requirement checks (`tests/verifier/registry.py`):

| Check | Role | Requirement | Evidence |
| --- | --- | --- | --- |
| `candidate_tree` | gates the reward | `/app/sympy` arrived and at least one unit is restored | unit states from the graded tree |
| `measurement_integrity` | gates the reward | the measurement is not interfered with | control items with known outcomes in each runner |
| `unit_restoration` | bar of `complete` | at least 99% of units pass their examples and match one recorded call | examples and the call comparison |
| `reference_calls` | bar of `complete` | at least 90% of replayed calls match | the call comparison |
| `repository_tests` | bar of `complete` | at least 95% of graded tests pass | per-test outcomes, cross-checked in every pytest run with that run's own tally |

All five read one measurement pass (`verifier/engine.py`).

### Reward formula

```
D      = recorded calls that are not documented (step 3): 6,145 of 14,523
set    = units with at least one call in D: 1,832 of 2,115 (283 left out, counted)
u      = units in the set whose docstring examples pass and that match at least
         one of their calls in D  /  1,832
c      = calls in D that match  /  6,145
reward = min(u, c)  if candidate_tree and measurement_integrity passed, else 0
```

- Continuous (`reward_type = "continuous"`), written to `reward.txt` with six
  decimals. Chosen on 2026-11-20 over the binary reward, whose bar sat above the
  invisible floor (see [Difficulty](#difficulty)).
- `complete` in `metrics.json` keeps the old verdict of the binary reward, not the
  instruction's sense of done (every function gives back what SymPy 1.14.0 gives): all five checks passed, that
  is at least 99% of all units passing their examples and matching one recorded
  call, 90% of all calls and 95% of the graded tests. It is `null` when only items
  the measurement did not reach keep a bar from being met.
- The repository tests are reported (`test_share`), not rewarded, until a regrade
  under the one-deadline measurement leaves no test unreached; they would then
  join inside the min, never as a weight. The pooled `partial_score` is gone: it
  took the test share from the sandbox and ignored the controls.
- Denominators are fixed. A unit that is not restored or is late counts as not
  passing; its calls as not matching. Every item has its own time (a unit's
  examples ten times the original's own time for them on this machine, at least
  2 s; a call ten times the original's time for its unit's calls, at least 1.5 s):
  an item past it fails, the rest of its unit is not run, and the others go on,
  so a body that never ends costs its own unit and the units that call it, and
  the phases finish even when every body runs out of its time. Only if a phase's
  own guard runs out with units or calls left does the verifier ask who used it: before any submitted code runs it
  times a fixed piece of pure-Python work and compares it with the same work on
  the machine the reference results were recorded on (`host_factor`), and the
  original's own seconds for every module and unit (`tests/private/timing.json`)
  scaled by that factor say what the original would need for the restored units.
  If that is at most half of the phase's worker-seconds, the submission's own
  bodies (slow, never ending or crashing) used the time, and what is left fails
  (`units_not_reached_failed`, `vectors_not_reached_failed`, with a note). Only
  when the original would need more, so that the machine decided, do the items
  stay not reached, and if they could raise the reward by more than 0.001
  (`unit_share_if_reached`, `call_share_if_reached`) the evaluation ends with an
  error and no reward. Units and calls left after their module's restarts ran
  out are failures, not unreached items.
- Also in `metrics.json`: `unit_share`, `call_share`, `test_share`, the bars'
  shares (`unit_pass_rate`, `call_match_rate`, `test_pass_rate`),
  `units_examples_passing`, `units_documented_calls_only` (units in the set
  whose examples pass and that match a documented call but no counted one: what
  a table of documented outputs would show), `units_left_out`,
  `units_left_out_passing` (left-out units whose examples pass and that match a
  documented call), `tests_not_reached`, `unit_share_by_lines`,
  `identical_bodies`, `late_files`, `egress_open`, `end_from` and `end_note`;
  every key is present on every completed evaluation, at 0 when the measurement
  stopped early (`tests_not_reached` then counts every test, since none ran).
  An evaluation error writes `status` and `error` only, and no reward.
- Floor, measured again on fix round 10's calls (6,145 counted): bodies that
  restore nothing, graded as trees through the verifier's own steps
  (`scripts/builder/fixtures.py`), and behind a table of documented outputs,
  which makes every example pass and answers no counted call (the same
  counted-call matches with every unit's examples counted as passing). The
  strategies that need a table of their own are measured statically, with the
  verifier's own comparison, in the original tree (so delegation reaches
  complete code) and with every example counted as passing: upper bounds for
  what such bodies could reach (`scripts/builder/floor.py`, and the reviewers'
  scripts). Since fix round 9 a delegation is also replayed as the unit's own
  body, so that a call back into the unit fails, as it would recurse in a
  submission: the bodies left whole by decision include module-level wrappers
  whose methods of the same name stay removed, and each wrapper calls its
  method back, which raised the same-name delegation in the original tree from
  0.0053 to 0.0132; as the unit's own body it reaches nothing. The third
  re-check wrote its strongest strategies as bodies; fix round 10 graded the
  accessor synthesis again on these calls (the fourth re-check's tree, the
  current units' bodies taken from it, every call's result kept and scored as
  that re-check scored it); the combination's tree is the fourth re-check's
  figure. Unit rule "one counted call":

| Strategy (bodies that restore nothing) | Through the verifier | Behind a table |
| --- | --- | --- |
| Bare `raise NotImplementedError` | 0.0 | 0.0 |
| The first argument unchanged; `sympify` of it | 0.0 (17 units pass their examples, 0 counted calls match) | 0.0; 0.0 |
| The other boolean (of the same kind) where a unit's documented results are one boolean, else the first argument | 0.0 (16 units pass their examples, 21 counted calls match) | 0.0034 |
| The unit's most frequent documented or shown output; any output its examples or tests show | | 0.0; 0.0 |
| One common constant for every unit, the best of 27 | | 0.0065 |
| A default of the type the unit's visible results have (an empty container, a zero, an empty string, an empty matrix of the shown class) | | 0.0103 |
| Delegation: the method further up the class hierarchy; a same-named function elsewhere | | 0.0052; 0.0132 in the original tree (0.0003; 0.0 as the unit's own body) |
| A table keyed by the arguments of any unit's visible direct calls; one that also answers a documented call with its symbols renamed | | 0.0013; 0.0021 |
| All of the above in one body per unit: per-call tables first, then one fallback per unit in a fixed order (the best of six orders) | 0.0135; 0.0166 with its per-call tables (fourth re-check, on the calls then) | 0.0324 in the original tree (0.0163 as the units' own bodies) |
| Raise the error a unit's examples show for every argument a table does not hold (the 7 units whose only counted call expects an error, since fix round 10) | | at most 0.0013 (8 calls; 7 units) |
| An accessor of the call's own arguments (`x.args`, `x[0]`, `len(x)`, `list(x)`, `-x`, `str(x)` and eleven more, per argument), chosen per unit by how many of its visible calls it reproduces, then the combination above | as a tree with its examples run and no table, 0.0175 (fix round 10, on these calls; 0.0173 in the fourth re-check) | 0.0356; 0.0384 with the per-call tables (fix round 10, on these calls; 0.0373 and 0.0401 in the fourth re-check); 8 of its bodies now fall under the body rules (4 import a plotting module, 4 take `eval` from a namespace), and were every one of their 18 counted calls matched, 0.0413 |
| The integrity reviewer's rules together (first argument, its `sympify`, any renamed documented call, the other boolean), with every call cut at 3 s counted as a match | | 0.0063 (0.0120) |
| The best strategy for each call, chosen with the hidden results (a bound, not buildable) | | 0.0350 in the original tree (0.0172 with delegation as the units' own bodies) |
| The best constant per unit, chosen with the hidden results (a bound, not buildable) | | 0.0290 |

  Every strategy measured stays under the decision's 0.05: the strongest a
  submission could build is the re-checks' accessor synthesis, graded again
  on these calls: 0.0384 behind a table of documented outputs with its per-call
  tables (0.0356 without them, 0.0175 as a tree; at most 0.0413 were the bodies
  the rules refuse to match every call, and 0.0426 with the errors above), the
  static combination reaches 0.0324 in the original tree and 0.0163 once its
  delegations run as the units' own bodies, and the bounds that use the hidden
  results stay at 0.0350; so a unit still needs one matching counted call.
  The rounds before stated 0.015 and then 0.0245 for every buildable strategy:
  the first missed results the docstrings print, the second the accessors,
  which reproduce a visible call's result from its arguments and so also some
  counted ones; the 38 units (fourth re-check) whose original body is such an
  accessor (or coincides with one on every recorded call) are not a floor but
  the restoration itself.
- A tree that did not arrive, or arrived without the collect step's signed mark,
  not as the mark lists it, or after a live process of `dev` outlived the
  collect step, is an evaluation error; so is a tree with a restored unit and no
  known end of the work. A delivery the collect step refused (nothing usable
  under the tree's name, or past its limits), or a tree with no restored unit,
  fails `candidate_tree`; the other checks are skipped and the reward is 0.
- An evaluation error leaves no reward file. `verify.py` exits 1 and
  `report.json` has `status: evaluation_error`.
- One step. `multi_step_reward_strategy = "final"`; with a single step the
  trial reward is this step's reward.
- The bars of `complete` are in `verifier/grade_config.json`; the instruction
  states behaviour, not bars.
- Implementation: `verifier/scoring.py`. Tests: `checks/test_scoring.py` (the min
  of the shares, the gates, `complete` at and below each bar, items not reached
  that could or could not change the reward) and
  `checks/test_evaluation_errors.py`.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / MEDIUM (findings 1 and 9: the hooks
have not yet run on the platform). Unassessed boundaries: finding 7.

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A body runs arbitrary code at grading time (through `sympify` of a string, a rebound `json.dumps`, a frame reached from an exception, or a computed attribute name) and lies about its own items: patches the example runner so its unit's examples report a pass, or reports a call's result without the state it left in its arguments | Sandbox process | Executed in red-team round 2; fourth re-check: a rebound `json.dumps` and a walk to the runner's frame forged a docstring pass and a call without its argument state, and two shapes of record made scoring raise; fifth re-check: a body that rebound the encoder broke the next records of its runner (19 counted calls of the same submission lost), now closed (`checks/test_doctest_phase.py`) | The runners hold no key and are trusted with nothing: each answers over a pipe, the verifier reads its lines within limits and only in their order, rebuilds every record from the runner's own fields and never raises on one; the runners encode their records with an encoder and write them through a channel of their own, both made before any submitted code loads, so a body that rebinds the `json` module changes no record. Until its runner is replaced, a body's lie reaches the items that runner reports after it, its own and other units' of the same module; never another module, the verifier or a reference. The reward is min(u, c); c compares what a call reports with references the sandbox never sees | A lie can raise u up to the share of units whose counted calls already match, and c only by calls whose result is right and whose argument state is wrong (the lie hides that state); with no way to see the references, a lie cannot make a wrong result match. Comparing example output in the root process would not close this: the expected output is in the docstring the sandbox reads, so a patched runner can report it | Red-team the runners with forged output | 🟡 YELLOW / MEDIUM |
| 2 | Read reference results or the withheld tests | File permissions in the verifier image | Attempted in both rounds; not reached | Private inputs readable by root only; sandbox runs as `nobody`; no test directories in the tree during phases 2 and 3 | Depends on the privilege drop | Re-run on the v2 bundle | 🟢 GREEN / LOW |
| 3 | Edit tests, module-level code or other functions to make checks pass | Graded-tree construction | Executed; no effect | Only unit bodies are copied into the reference skeleton; `checks/test_transplant.py` | None found | Keep the check | 🟢 GREEN / LOW |
| 4 | Return the documented outputs for the documented inputs, and something cheap otherwise: a constant, the first argument, the other boolean, a default of the type the visible results have, an output the examples print, delegation to another function, or a documented result renamed | Which calls count | Review of the binary version: tables passed `trig_split`, `viete`, `wigner_3j` and 14 more units through the real verifier. First re-check of 2026-11-20: behind a table, a first-argument fallback and a renaming table reached 0.07 to 0.12. Second re-check: results the docstrings print still counted (the panel's own fixture 0.029, every buildable strategy together 0.041). Third re-check: an accessor of the call's own arguments chosen by visible fit, then the cheap fallbacks, 0.0401 behind a table through the verifier's own runners | Only calls nothing visible answers count (D): no docstring example or visible test (slow, skip-marked and `+SKIP` ones included) makes them, even with its symbols renamed, and their result is neither one an example or a visible test shows, nor a documented result of their unit, nor one of their own arguments or an element of their `*args` or `**kwargs`, all compared with the type left out; variants rename with one map over all arguments and shift no integer with a stated domain. Measured (see the floor under [Reward formula](#reward-formula)): the strongest buildable strategy 0.0384 behind a table (the third re-check's accessor synthesis, graded again on these calls in fix round 10; 0.0401 on the fourth re-check's; at most 0.0426 were its refused bodies to match and with the error strategy of fix round 10), the cheap fallbacks together 0.0324 statically in the original tree (0.0163 with each delegation run as the unit's own body, since fix round 9) and 0.0166 through the verifier; through the verifier 0.0 for each fixture tree | An accessor, a type default or a delegate can still equal some counted results, up to 0.0384 (0.0426 at most); with the hidden results in hand, 0.0350 (best per call, in the original tree) and 0.0290 (best constant per unit), which no submission can build; all under the decision's 0.05 | Re-run `fixtures.py`, `floor.py` and the reviewers' scripts after any rebuild of the calls | 🟢 GREEN / LOW |
| 5 | Change how a runner reports results | Runner control items | Executed in round 1 through module-level `os`/`sys`; fixed. Third re-check: a body that imported `__main__` or `posix` wrote a result line of its own and forged a pass. Fourth re-check: the same through `posixpath.os`, `random._os`, `sympy.external.import_module('posix')`, `attrgetter` frame walks and a rebound `json.dumps`; a sparse 2^50-byte output read whole ended in a MemoryError | No key exists where a body runs: the verifier is the runners' parent and reads their pipes in pieces, at most a line limit and a total, in order; the runners serialise with a function bound before the tree is imported, and their standard streams go nowhere; the body rules deny the route class (the modules and attributes that reach the process or the files, literal names given to `getattr`, `attrgetter`, `methodcaller` and `import_module`, and since fix round 10 any of the names as a literal key, whatever holds it: `x['os']`, `d.get('sys')`, a namespace kept in a variable or taken with `getattr(x, '__dict__')`); a self-check after every unit's examples; control items with known outcomes in every pytest run; the records of a run cannot hold more passes than that run's tally; the sandbox's files are bounded in size | The rules are a list of names: a name built at run time from pieces, never written whole in the body, still reaches the process, and what that buys is finding 1 | With finding 1 | 🟢 GREEN / LOW |
| 6 | Tamper with reward or result files | Separate verifier container | By design; not attacked | Verifier starts fresh with only `/app/sympy`; output directory closed to the sandbox user | None found | Attack on the v2 bundle | 🟢 GREEN / LOW |
| 7 | Anything that depends on the new entry point, check registry or reporting | v2 verifier code | Not attacked | Same measurement code as v1; reference and no-op baselines on the v2 bundle | Unknown | Red-team run against the v2 bundle | 🟡 YELLOW / UNASSESSED |
| 8 | Reach the network during the work phase to fetch SymPy | Agent network policy | Probe task, 2026-11-15: PyPI and GitHub unreachable from the work phase; 217 in-work fetch attempts in one 12-hour run all failed (TCP connected, TLS did not) | `[agent] network_mode = "no-network"`; the instruction forbids another copy; SymPy is not installed elsewhere; the image's attribution names no download | Agent tooling is installed at setup with public egress; host-name filtering not probed for every route | Probe the routes as `dev` | 🟡 YELLOW / MEDIUM |
| 9 | Leave a process running after the work that fetches SymPy once public egress returns (about 0.2 s after the work ends, before collection: 0.8 s and 11.8 s on two 12-hour runs) and writes the original into `/app/sympy`, directly or behind a link; the original scores 1.0. Variants: hold every local port (or exhaust another resource of the machine) so the net check's probe fails and its closed stretch runs on past the turn; load the CPU or the link so its handshakes time out | Delivery: user, hooks, record | Reproduced by review with the verifier's own transplant: before 2026-11-20 (2,671 restored, a tree identical to the reference); on 2026-11-20, a write after a turn shorter than the net check's old one-minute arming taken whole, a late file graded through a directory link, and (re-check 2) a fetch while the probe failed for want of ports, taken because such a failure counted as a closed poll and the end was moved to the collect step's start. All fixed; `checks/test_delivery.py` runs the real net check whole for a blinded probe and a no-op turn, and covers a 3-second turn, every unknown end, the session end, file and directory links and every refused tree. Fifth re-check: with the limit counted from the first process, a capped run's end could pass for a blip, so a save after egress returned was graded; the limit counts from the start of the work again, and the real net check is run with a fetch saved after egress returns (late, the file taken from its last copy) and an honest rename save in the last second before the limit (kept) | The work runs as `dev`; a poll that fails for a reason of the machine is not a closed poll and ends nothing; the net check records the end of every stretch an opening ends, but an opening seen while an exec session is alive, within the time the work is given, is no end, and `dev` is ended only once no session is alive or that time has run out; it also watches the agent's exec sessions, and the end of the work is the earliest of the net check's end, the end of the session that ran the whole work, which no process the agent starts can move, and the start of the work plus the time limit (34,560 s; the setup step takes that start before Harbor starts the agent's clock), which bounds a turn run to the limit whatever the probe read and ends no later than Harbor's own limit, so a fetch once egress returns lands after it; a unit file saved after that limit is taken as the last copy the net check made of it before the limit, so a capped turn loses only its edits after that copy, never a file; while a session is alive, `dev` is ended no earlier than its first process's start plus that limit (a process two looks a second apart saw alive, so never Harbor's short pre-clock `pwd`, fix round 11), and with no first process seen never by time (fix round 10); the end is never moved to the collect step's start unless its own probe found the hosts closed; the collect step gives back the room the setup step set aside and puts the tree aside right after it has stopped every process of `dev`, then stops and ends the rest, lets the net check finish one more poll and look, records every file's change time before touching anything and removes every link; the verifier takes no other unit file changed at or after the end and none reached through a link; a link or an unlisted file that arrived, a short delivery or a surviving process is an evaluation error; a collect step that began and did not finish leaves a noted 0; the mark is signed with a key `dev` cannot read | A write through a file mapping dirtied before the end can change content without moving its times. It needs a live process: the net check ends `dev` once the turn's session is over and the hosts answer, but a probe made to time out by load still reads as closed, so such a process can live until the collect step; the session end (for a harness whose exec ends with the turn) and the time limit (for a turn run to it) stop every write that moves a file's times, not one through a mapping. A harness that runs one exec per command, or a run Harbor resumes in place after a provider error, has neither, and only the net check's end bounds it, which such a load can push back. A harness that does its work outside its own exec sessions, and whose last session began within ten minutes of the start, would have its later writes counted late (claude-code, mini-swe-agent and the oracle run the whole work in one session; Proximus is not yet seen). A capped turn's edits after the last copy before the end of the work are lost: the seconds by which Harbor's clock started after the setup step, and at most one more. Closing the mapping residual needs the platform to keep the agent's network policy through collection | Canaries on the platform: a detached fetch-and-overwrite loop scores 0 with its files `late`; a reference that keeps working past the time limit with a load process and a fetch scores 0 with its fetched files `late`; an honest reference that saves a unit file by rename just after the limit keeps that file as copied; reference 1.0 (`end_from` `session`) and no-op 0.0 (`end_from` `unchanged`) with the record present; the start of the work against Harbor's start of the agent (what a capped turn loses); Proximus's process model read from its record (`sessions`) | 🟡 YELLOW / MEDIUM |

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

Regraded on the continuous reward after fix round 11 (2026-11-26: the call
data of fix round 10, 2,115 units, errors compared one way; this machine, the
entry point's steps without the privilege drop, one worker; examples and calls,
the tests not run since they are not rewarded). The three columns before u are
the regrades after the fourth re-check, with the units no graded item ran left
whole, and after fix round 9. Against fix round 9 every reward moved by at most
0.0005 (11 up, 5 down) and the order is unchanged: the 7 units whose examples
show an error joined the set (a submission passes 0 to 7 of them), and 2 units
changed their verdict through a call that ran out of its time, one each way.
The twelve-hour trials' own files were not downloaded, so these are the
stored submissions of the earlier sessions of the same task; every one scored
0 under the binary reward.

| Submission | Agent / model | Units passing, binary era (of the 2,671 then) | Reward, binary | Reward after the fourth re-check | Reward with the units left whole | Reward, fix round 9 | u | c | Reward now | Units whose examples pass | Bodies identical to upstream |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2 trial 16 | claude-code / DeepSeek v4.1 Flash | 2,557 | 0 | 0.852 | 0.852 | 0.853 | 0.895 | 0.853 | **0.853** | 2,065 | 19.8% |
| v2 trial 17 | claude-code / DeepSeek v4.1 Flash | 2,481 | 0 | 0.842 | 0.838 | 0.834 | 0.860 | 0.835 | **0.835** | 1,988 | 18.4% |
| v2 trial 18 | claude-code / GLM 5.3 | 2,462 | 0 | 0.826 | 0.826 | 0.824 | 0.861 | 0.823 | **0.823** | 1,989 | 16.8% |
| 48 h run a, session 1 | claude-code / DeepSeek v4.1 Flash | 2,375 | 0 | 0.807 | 0.802 | 0.802 | 0.819 | 0.803 | **0.803** | 1,905 | 19.5% |
| 48 h run b, session 1 | claude-code / DeepSeek v4.1 Flash | 2,338 | 0 | 0.807 | 0.803 | 0.800 | 0.807 | 0.800 | **0.800** | 1,864 | 19.8% |
| 48 h run, session 1 | claude-code / GLM 5.3 | 1,976 | 0 | 0.686 | 0.685 | 0.679 | 0.692 | 0.679 | **0.679** | 1,600 | 16.2% |
| 48 h run b, session 1 | Proximus / DeepSeek v4.1 Flash | 1,289 | 0 | 0.399 | 0.398 | 0.399 | 0.419 | 0.399 | **0.399** | 1,064 | 11.8% |
| 48 h run a, session 1 | Proximus / DeepSeek v4.1 Flash | 1,159 | 0 | 0.363 | 0.362 | 0.365 | 0.365 | 0.367 | **0.365** | 950 | 14.6% |
| single-step trial 6 | Proximus / DeepSeek v4.1 Flash | 1,077 | 0 | 0.347 | 0.346 | 0.341 | 0.349 | 0.341 | **0.341** | 869 | 16.2% |
| 48 h run, session 1 | Proximus / GLM 5.3 | 1,031 | 0 | 0.331 | 0.330 | 0.325 | 0.344 | 0.325 | **0.325** | 842 | 15.0% |
| base trial 14 | mini-swe-agent / DeepSeek v4.1 Flash | 716 | 0 | 0.216 | 0.216 | 0.211 | 0.221 | 0.211 | **0.211** | 580 | 13.3% |
| base trial 15 | mini-swe-agent / GLM 5.3 | 346 | 0 | 0.116 | 0.116 | 0.116 | 0.120 | 0.116 | **0.116** | 286 | 10.7% |
| base trial 9 | mini-swe-agent / DeepSeek v4.1 Flash | 334 | 0 | 0.099 | 0.099 | 0.100 | 0.099 | 0.139 | **0.099** | 264 | 8.2% |
| base trial 10 | mini-swe-agent / GLM 5.3 | 274 | 0 | 0.094 | 0.094 | 0.092 | 0.100 | 0.092 | **0.092** | 246 | 7.7% |
| base trial 8 | claude-code / GLM 5.3 | 63 | 0 | 0.019 | 0.019 | 0.020 | 0.021 | 0.037 | **0.021** | 51 | 57.7% |
| base trial 13 | claude-code / GLM 5.3 | 15 | 0 | 0.003 | 0.003 | 0.003 | 0.003 | 0.004 | **0.003** | 10 | 14.3% |

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (35 tests) | working tree, 2026-11-17 and 2026-11-19 | pass |
| `checks/` (50 tests): delivery hooks under dash with stand-ins, a late write refused, an honest delivery taken, every failing mark an evaluation error, the net check's arming and handshake probe | working tree, 2026-11-20 (delivery) | pass; the hooks have not run on the platform |
| `checks/` (61 tests): the real docstring runner and driver on a stand-in package (a death, a silent block and a timeout each cost one unit; a seeded draw passes twice; an import that never finishes fails its module in one start; a run that dies after its last unit counts nothing; a used-up budget gives a row per unit; `measure()` completes through it; `restore check` fails only the culprit), call replay (a barren start costs only its unit; a timeout restarts behind it; a hung import ends the job in one start), one deadline under the verifier limit, an unreached verdict is an evaluation error, the address-space limit and its fallback | working tree, 2026-11-20 (verifier robustness) | pass |
| Rewritten runners and drivers on real SymPy (Python 3.12, no sandbox) | original tree: `combinatorics.permutations` and `combinatorics.group_numbers`; a stored submission: `group_numbers` twice, `ntheory.generate`, `ntheory.residue_ntheory`, `polys.euclidtools` | original: 62 / 62 units, 287 / 287 calls; submission: identical statuses in both runs, 48 pass and 22 fail with no lost unit |
| Reference results recorded again with the new comparison (`scripts/builder/regold.py`) | the verifier's own runner and `canon.py`, original and skeleton trees without test directories, hash seeds 0, 1, 2 | original 13,382 / 13,382 under every seed (2 of 13,384 dropped: result over the 400 kB line); skeleton 0; slowest call 419 ms; 8,602 results unchanged in form |
| Behaviour-equal bodies of the units the old comparison failed | one unit swapped at a time in the original tree, the verifier's `rdoctest.py` and `rvector.py`, new reference results | as_submodule and round_two without their pre-set flags 3/3 and 8/8; restrict_codomain testing equality first 8/8; homomorphism without the no-op steps 8/8 and identity_hom through it 3/3; Truss.remove_node by index 1/1; multiline_latex from its docstring 0/6 (`&- a`, see the development log). Examples pass in every case |
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
| `checks/` (66 tests): the reward as min of the shares, its gates, `complete`, items not reached that could or could not change the reward, the continuous reward type, the comparison on stand-ins | working tree, 2026-11-20 (reward) | pass |
| Final calls recorded again (`scripts/builder/regold.py`) | the verifier's runner and `canon.py`, hash seeds 0, 1, 2 | original 17,166 / 17,166, skeleton 0 |
| Floor (`scripts/builder/floor.py`) | final calls, documented list | documented-output table with a documented fallback 0.0; best constant per unit after the fact 0.060; a tree returning every first argument unchanged, through the verifier: 0.003 (6 / 2,041 units, 498 / 7,568 calls) |
| Reference, empty delivery and bare `raise NotImplementedError` bodies through the entry point's steps | this machine, no privilege drop, no network probe, the delivery mark taken as listed | reference 1.000000 and complete: 2,041 / 2,041 units, 7,568 / 7,568 counted calls, 17,166 / 17,166 calls, 10,428 / 10,428 tests in one plain pytest session with none unreached, no control tripped, 577 s; the agent's starting tree 0.0 (`candidate_tree` failed, the rest skipped); bare `raise NotImplementedError` bodies 0.0 (2,671 restored, no unit or call matched, no control tripped) |
| Regrade of the stored submissions on the continuous reward | this machine, the entry point's steps, examples and calls | 16 submissions, rewards 0.003 to 0.897 (see [Trial evidence](#trial-evidence)) |
| `oddish preflight` | flat 12-hour bundle `d00941d22a69` (`ops/sympy-restoration/dist-12h/`) | pass |
| `checks/` (73 tests): a 3-second turn has its end and a later write is refused; every unknown end is an evaluation error; file and directory links deliver nothing; the comparison tells apart given Dummies trading places, merged renamings, wrong memo values, frames made in another order or copied for a given one, storage where it is the contract, stored zeros and every non-LaTeX whitespace | working tree, 2026-11-20 (re-check fixes) | pass |
| All calls recorded again with the narrowed comparison (`regold.py`) | the verifier's runner and `canon.py`, hash seeds 0, 1, 2 | original 17,166 / 17,166, skeleton 0; 1,424 results changed form |
| Comparison probes: one unit's body edited in a copy of the original, its examples and every recorded call run through the verifier's `rdoctest.py`, `rvector.py` and `canon.py` | working tree, 2026-11-20 | wrong bodies, counted calls matched: one-line `pprint_nodes` 0/3 (examples pass), swapped `bivariate_type` 0/8 (examples pass), one-line `MatrixBase.table` 0/4, side-by-side `stringPict.below` 0/4, `fcode` without its columns 0/8, dense `DDM.to_sdm` 0/1 and `DomainMatrix.to_sparse` 0/1, a wrong pre-set flag in `round_two` 0/1 (and in `as_submodule` 0/3 documented calls), `add_node` without its parallel lists 0/4, `disambiguate` dropping assumptions 1/4 (that call has none); right bodies: `as_submodule` and `round_two` without their pre-set flags, `restrict_codomain` testing equality first, `homomorphism` without no-op steps (and `identity_hom` through it), `remove_node` by index and an extra frame made first all match in full, `multiline_latex` from its docstring 6/6 |
| Counted calls rebuilt (`documented.py`, `echoes.py`, `rec_withheld.py`, `variants.py`, `regold.py`, `finalize_documented.py`) | working tree, 2026-11-20 (re-check) | 16,737 calls, 9,883 documented (9,270 by arguments, 334 of them only up to a renaming; 323 returning an argument; 282 returning a documented result; 8 of the one capped unit), 6,854 counted; 1,955 units in the set, 716 left out; original 16,737 / 16,737 under hash seeds 0, 1, 2, skeleton 0 |
| Floor fixtures through the verifier and behind a table (`fixtures.py`, `floor.py`), with the reviewers' own fixture scripts | working tree, 2026-11-20 (re-check) | see the floor under [Reward formula](#reward-formula); reviewers' scripts: first argument 0.0015, flip 0.0136, flip with first argument 0.0150, renaming tables 0.0007 to 0.0026, renaming with first argument 0.0028 |
| Reference and the agent's starting tree through the entry point's steps, after the re-check | this machine, no privilege drop, no network probe, the delivery read stubbed | reference 1.000000 and complete: 1,955 / 1,955 units, 6,854 / 6,854 counted calls, 16,737 / 16,737 calls, 10,428 / 10,428 tests in one plain pytest session, none unreached, no control tripped, 672 s; starting tree 0.0 (`candidate_tree` failed, every metric present) |
| Regrade of the stored submissions after the re-check | this machine, the entry point's steps, examples and calls | 16 submissions, reward 0.004 to 0.896 (see [Trial evidence](#trial-evidence)) |
| `checks/` (99 tests): the real net check run whole for a blinded probe and a no-op turn; local, closed and open polls; the session rule on a stand-in `/proc`; the earlier end; no clamp; every refused tree scored 0; odd names; a surviving process; no end with and without a restored unit; the packager's private lists | working tree, 2026-11-20 (second re-check, the end of the work) | pass |
| All calls recorded again with the typed comparison (`regold.py`) | the verifier's runner and `canon.py`, hash seeds 0, 1, 2, 2 MB result line | original 16,737 / 16,737 (16,593 byte for byte, 144 differing only in Dummies and frame counters the call made), skeleton 0, none dropped; 188 results record changed arguments |
| Wrong-type, wrong-state and LaTeX probes on real SymPy (one unit's body changed in a copy of the original, its module replayed through the verifier's `rvector.py`, counted calls) | working tree, 2026-11-20 (second re-check) | `nP` 7/7 to 1/7, `right_open` 4/4 to 0/4, `banded` 8/8 to 0/8 (twice), `to_matrix` 8/8 to 0/8, `nullspace` 4/4 to 1/4, `gauss_laguerre` 6/6 to 0/6, `ddm_irref` 2/2 to 0/2, `apply_support` 6/6 to 4/6, `multiline_latex` 6/6 to 0/6; controls unchanged |
| `checks/` (103 tests) | working tree, 2026-11-20 (second re-check, the comparison) | pass |
| Counted calls rebuilt (`documented.py` over every docstring, the `+SKIP` examples, the visible tests, the skip-marked and the slow ones; `echoes.py`; `finalize_documented.py` with both rounds' visible runs) | working tree, 2026-11-20 (second re-check) | 16,737 calls, 10,533 documented (9,384 by arguments, 674 shown, 341 echoes, 76 capped, 58 documented results), 6,204 counted; 1,844 units in the set, 827 left out |
| Floor fixtures through the verifier and behind a table (`fixtures.py`, `floor.py`), with both reviewers' scripts rerun on these calls | working tree, 2026-11-20 (second re-check) | through the verifier: raise 0.0, first argument 0.0, flip 0.0; behind a table at most 0.0245 for every buildable strategy (composite), 0.0064 for the integrity reviewer's rules (0.0124 counting every cut call); bounds with the hidden results 0.0269 and 0.0301 |
| `checks/` (104 tests) | working tree, 2026-11-20 (second re-check, the counted calls) | pass |
| Reference, the agent's starting tree and a turn of no length, after the second re-check | this machine, the entry point's steps, no privilege drop, no network probe; the no-op through the shipped hooks under dash, the real net check, a platform-style copy (a tar unpacked with the `data` filter) and the real mark and record, with root, the Linux tools, the network, `/proc` and the user `dev` stood in for | reference 1.000000 and complete: 1,844 / 1,844 units, 6,204 / 6,204 counted calls, 16,737 / 16,737 calls, 10,428 / 10,428 tests in one plain pytest session, none unreached, no control tripped, 1,020 s; starting tree 0.0; no-op 0.0, `end_from` `unchanged` (8 polls, no opening, 1,716 entries listed), no evaluation error |
| Regrade of the stored submissions after the second re-check | this machine, the entry point's steps, examples and calls, one replay worker | 16 submissions, reward 0.003 to 0.857, none with a unit or call unreached, a late file or a control tripped (see [Trial evidence](#trial-evidence)) |
| Honest partial work through the entry point's steps | the original bodies of the first 20% of units in `restore next` order, and of a random 20% (seed 0), every other unit a placeholder | 0.150 (u 0.169, c 0.150) and 0.033 (u 0.033, c 0.058) |
| `checks/` (104 tests) and the repository check | working tree, 2026-11-20 (second re-check, before the package) | pass |
| `oddish preflight` | flat 12-hour bundle `2b0d8ccb0c6e` (`ops/sympy-restoration/dist-12h/`, key rotated) | pass (1 task) |
| Word sweep of the whole bundle (the word list of the round-2 audit on every text file, the hidden data by structure, an opcode walk of the pickle, `strings` over the data and the decompressed archives, the archives against the SymPy 1.14.0 wheel, the key) | bundle `2b0d8ccb0c6e` | clean: the agent's files use "deliver" only as the task's word (delivered form, what to deliver, the deliverable, unfinished work delivered as it stands); 0 non-ASCII bytes; data and archive strings are SymPy names only; archive changes are placeholders, deleted withheld tests and `pytest.ini`; the key's copies are equal, rotated, and nowhere else; no bytecode |
| The reference graded twice with the few-unit Float comparison and the signed runners (examples and calls) | working tree, 2026-11-21 (third re-check) | 16,737 / 16,737 calls and 2,671 / 2,671 examples both times; 6,204 / 6,204 counted calls |
| All calls recorded again with the converter memo slot and the sieve and ring forms (`regold.py`, seeds 0 and 1) | the verifier's runner and `canon.py` | 16,737 / 16,737 kept, 16,593 byte for byte and the rest only in the names a call makes, skeleton 0; 66 results changed form (33 ring, 21 sieve, 12 field), 31 of them counted |
| Visible reruns: the slow tests of the five packages whose units the cap stopped (cap on distinct arguments), the slow tests of `sympy.stats` one file at a time, the eleven tests the 60-second limit cut with 600 s each | `documented.py` on the original with the visible tests | 3 units compared to the end (10 calls count again), 5 still past 500,000 distinct arguments; 1 call more documented (`MultivariateT`); 7 of the 11 cut tests finished, 4 ran out of 600 s again |
| Counted calls rebuilt (`finalize_documented.py` over both rounds' visible runs, this round's reruns and new echoes) | working tree, 2026-11-21 (third re-check) | 16,737 calls, 10,524 documented (9,410 by arguments, 674 shown, 341 echoes, 41 capped, 58 documented results), 6,213 counted; 1,847 units in the set, 824 left out |
| Floor on these calls (`fixtures.py`, `floor.py`, the reviewers' scripts) | working tree, 2026-11-21 (third re-check) | through the verifier: raise, first argument and flip 0.0; behind a table: flip 0.0034, the combination 0.0249 statically; integrity rules 0.0064 (0.0124); hidden-result bounds 0.0274 and 0.0296; the re-check's accessor synthesis 0.0401 (on the calls before) |
| Reference, the agent's starting tree and a turn of no length, after the third re-check | this machine, the entry point's steps, one worker; the no-op through the shipped hooks, the real net check, a platform-style copy and the real mark, with root, the Linux tools, the network, `/proc` and the user `dev` stood in for | reference 1.000000 and complete: 1,847 / 1,847 units, 6,213 / 6,213 counted calls, 16,737 / 16,737 calls, 10,428 / 10,428 tests, none unreached, no control tripped, 1,043 s; starting tree 0.0; no-op 0.0 with `end_from` `unchanged` (8 polls, 1,716 entries listed) |
| Hostile trees (all bodies loop; 5% loop; 50% slow) through the verifier's `measure()` and scoring | this machine, the entry point's steps, one worker, phases cut to 900 s and 1,200 s | loop-all 0.0000, completed, 2,628 units and 16,411 calls not reached counted as failed; loop-5 0.0254, completed, 2,538 units and 15,746 calls not reached counted as failed; slow-50 0.0341, completed, 2,338 units and 15,732 calls not reached counted as failed; none an evaluation error |
| `checks/` (122 tests) and the repository check | commit `4ef634c` (2026-11-24, before the package) | pass |
| `oddish preflight` | flat bundle `966f2b531f52` (`ops/sympy-restoration/dist-12h/`, key rotated; platform content hash `27ceda8716e8…`, version 4's `4ce37762a342…`) | pass (1 task) |
| Word sweep of the whole bundle, its data, archives and key (the same scripts as the round before) | bundle `966f2b531f52` | clean: the agent's files use "deliver" only as the task's word; `platform` only as the forbidden standard-library module; SymPy's own names in the data and archives; 0 non-ASCII bytes; the key's copies equal, new and held by no other file; no bytecode |
| Regrade of the stored submissions after the third re-check | this machine, the entry point's steps, examples and calls, one replay worker, 2026-11-24 | 16 submissions, reward 0.003 to 0.856, each within 0.0023 of the round before, the order unchanged; none with a unit or call unreached or failed for lack of time, a late file or a control tripped (see [Trial evidence](#trial-evidence)) |
| Reference, the agent's starting tree and a turn of no length, after the fourth re-check | this machine, the entry point's steps, one worker, runners over pipes with a time for every item; the no-op through the shipped hooks, the real net check, a platform-style copy and the real mark, with root, the Linux tools, the network, `/proc` and the user `dev` stood in for | reference 1.000000 and complete: 1,847 / 1,847 units, 6,213 / 6,213 counted calls, 16,737 / 16,737 calls, 10,428 / 10,428 tests, none unreached, no item out of its time (355 starts in each phase), no control tripped, 1,209 s; starting tree 0.0; no-op 0.0 with `end_from` `unchanged` (12 polls, no opening, 1,716 entries listed) |
| Floor on these calls with the final runners (`fixtures.py`, `floor.py`, the reviewers' scripts) | working tree, 2026-11-24 (fourth re-check) | the same as the round before: through the verifier raise, first argument and flip 0.0; behind a table flip 0.0034, the combination 0.0249 statically; integrity rules 0.0064 (0.0124); hidden-result bounds 0.0274 and 0.0296; the re-checks' accessor synthesis 0.0401 behind a table (the fourth re-check's figure, on these calls); all under 0.05 |
| Regrade of the stored submissions after the fourth re-check | this machine, the entry point's steps, examples and calls, one worker, 2026-11-25 | 16 submissions, reward 0.003 to 0.852, each the same or up to 0.0043 lower than the round before, the order unchanged; none with a unit or call unreached or failed for lack of time, a late file or a control tripped (see [Trial evidence](#trial-evidence)) |
| Hostile cases through the verifier's `measure()` and scoring (one unit each: `preview` to a file, `open` with a seek, `json.dumps` rebound, `os.fork` in a loop, a 64 MiB result, a 256 MiB print before the original body) | this machine, the entry point's steps, one worker, real SymPy, 2026-11-25 | 0.9962, completed: the first four refused by the body rules; 1,840 / 1,847 units in the set and 6,200 / 6,213 counted calls (the six units and three callers); nothing unreached, no control tripped, none an evaluation error |
| What the graded items run, traced on the original tree (`sys.monitoring` on the 2,671 unit bodies) | the 6,213 counted calls and the examples of the 1,847 units in the set, 2026-11-25 | no counted call expects an error; of the 824 units with no counted call of their own, 244 run inside counted calls of others, 289 inside the examples, 297 inside either, 527 inside neither (31 files, 60 units, `sympy.liealgebras` among them) |
| `checks/` (133 tests) and the repository check | commit `03cc17f` (2026-11-25, before the package) | pass |
| `oddish preflight` | flat bundle `fb5eada8e82c` (`ops/sympy-restoration/dist-12h/`, key rotated; platform content hash `a27c3b88f2d0…`, version 4's `4ce37762a342…`; Harbor's network plan for it: agent environment public, work no network, verifier environment public, verification no network) | pass (1 task) |
| Word sweep of the whole bundle; the bundle against the worktree and the commit; the key | bundle `fb5eada8e82c` | the same hits as the round before's bundle, all of the classes found clean then (the task's "deliver", `platform` as a forbidden module, SymPy's own names, the root-only hooks' own words); 0 non-ASCII bytes; no bytecode; 415 files equal to the worktree, the 48 tracked ones to commit `03cc17f`; only the key's two copies, `fsmaint-sweep` and `task.toml` differ from the round's first build (`87c717883415`), and the prepared data and archives are byte for byte those of bundle `966f2b531f52` but for the key, so that bundle's data and archive scans stand; the key's copies equal, new and held by no other file |
| Hostile trees at the platform's worker-seconds (one worker, examples 10,800 s, calls 9,600 s) | this machine, the entry point's steps, the tests not run | loop-5 0.5950, completed, 955 + 870 items out of time, 0 not reached; slow-50 0.7423, completed, 549 + 505 items out of time, 0 not reached; loop-all 0.0000, completed, 2671 + 2671 items out of time, 0 not reached; none an evaluation error |
| `checks/` (133 tests) and the repository check | commit `408818d` (2026-11-25, the instruction's change, before the package) | pass |
| `oddish preflight` | flat bundle `54a8b4898f6e` (`ops/sympy-restoration/dist-12h/`, key rotated; platform content hash `a311bc14c28e…`, version 4's `4ce37762a342…`; network plan as for `fb5eada8e82c`) | pass (1 task) |
| Word sweep of the whole bundle; the bundle against the worktree and the commit; the key | bundle `54a8b4898f6e` | the hits of `fb5eada8e82c` and one more, the task's own "deliver" in the line about the log; 0 non-ASCII bytes; no bytecode; 415 files equal to the worktree, the 48 tracked ones to commit `408818d`; only the instruction and the key's two copies differ from `fb5eada8e82c`; the key's copies equal, new and held by no other file |
| The units no graded item runs left whole (`graded_coverage.py`, `keep_whole.py`) | the prepared inputs, 2026-11-25 | 527 run by no graded item, 32 of them kept removed as near-copies of graded bodies, 495 left whole; 2,176 units in 324 files, 14,867 calls (6,213 counted, 1,847 units in the set); the skeleton with the reference over it is the original in all 355 old unit-bearing files; literal scan 3 hits, each the class's own visible vocabulary |
| Reference, the agent's starting tree and a turn of no length, with the units left whole | this machine, the entry point's steps, one worker; the no-op through the shipped hooks and the real net check | reference 1.000000 and complete: 1,847 / 1,847 units, 6,213 / 6,213 counted calls, 14,867 / 14,867 calls, 10,428 / 10,428 tests, none unreached, nothing out of its time (324 starts in each phase), no control tripped, 1,427 s; starting tree 0.0; no-op 0.0 with `end_from` `unchanged` (1,716 entries listed) |
| `checks/` (135 tests: the re-trace and the counts added) and the repository check | commit `e2d1d7e` (2026-11-25, before the package) | pass |
| `oddish preflight` | flat bundle `e4c15ab38d70` (`ops/sympy-restoration/dist-12h/`, key rotated, 384 files; platform content hash `39e86fd83463…`, version 4's `4ce37762a342…`; network plan as before) | pass (1 task) |
| Word sweep of the whole bundle; the archives and reference against the SymPy 1.14.0 wheel's record; the call data's pickle by opcode; the bundle against the worktree and the commit; the key | bundle `e4c15ab38d70` | the sweep's hits those of `54a8b4898f6e`; 0 non-ASCII bytes; no bytecode; the 324 reference files identical to upstream; the archives differ from upstream by 2,176 placeholders, the withheld tests and `pytest.ini`; the pickle holds SymPy names only; 384 files equal to the worktree, the 48 tracked ones to commit `ef1561c`; the key's copies equal, new and held by no other file |
| Regrade of the stored submissions with the units left whole | this machine, the entry point's steps, examples and calls, one worker, 2026-11-26 | 16 submissions, reward 0.003 to 0.852, each the same or within 0.0050 of the fourth re-check's (11 down, 1 up, 4 the same), the order unchanged; none with a unit or call unreached, a late file or a control tripped; of the 99 units that moved, 96 run a body now left whole in the submission's own tree, 1 loops against two of them, 1 is flaky in its submission, 1 ran within its time this time (see [Trial evidence](#trial-evidence)) |
| Floor fixtures through the verifier, built again for the 2,176 units (`fixtures.py`) | the same three rules | raise, first argument and flip 0.0; flip behind a table 0.0034; the same as before |
| Fix round 9's build (`absorbed.py`, `twin_calls.py` and the variant builder, `keep_whole.py` with the token tests counted both ways) | the prepared inputs, 2026-11-26 | 46 near-copies of graded bodies: 23 given 62 counted calls (20 stay removed with 56), 23 with no valid call left whole with their 23 twins and the 32 graded bodies those give away (78 by decision, 138 counted calls out); 2 units no graded item fails without left whole; 2,114 units in 322 files, 14,508 calls (6,137 counted, 1,825 units in the set, 289 graded only through others: 241 by a call, 48 by examples); the skeleton with the reference over it is the original; two runs of the rule give the same files |
| `checks/` (140 tests: every removed unit has an item that fails without it, no body left whole is a near-copy of a removed one, the example times complete, a post-egress fetch late and a last-second save kept, both runners' own encoder, namespace literals) and the repository check | commit `6735e56` (2026-11-26, before the package) | pass |
| `oddish preflight` | flat bundle `32fbeb905028` (`ops/sympy-restoration/dist-12h/`, key rotated, 383 files; platform content hash `721d414d1e66…`, version 4's `4ce37762a342…`; network plan: agent environment public, work no network, verifier environment public, verification no network) | pass (1 task) |
| Word sweep of the whole bundle; the archives and reference against the SymPy 1.14.0 wheel's record; the call data's pickle by opcode; the bundle against the worktree and the commit; the key | bundle `32fbeb905028` | the agent's and the hooks' lines and the counts the same as the round's first bundle's (`7c7478e2ca00`); 0 non-ASCII bytes; no bytecode; the 322 reference files identical to upstream; the archives differ from upstream by 2,114 placeholders, the withheld tests and `pytest.ini`; the pickle holds SymPy names only; 383 files equal to the worktree, the 48 tracked ones to commit `6735e56`; the key's copies equal, new and held by no other file |
| Reference, the agent's starting tree and a turn of no length, after fix round 9 | this machine, the entry point's steps, one worker; the no-op through the shipped hooks and the real net check | reference 1.000000 and complete: 1,825 / 1,825 units in the set, 6,137 / 6,137 counted calls, 14,508 / 14,508 calls, 2,114 / 2,114 units' examples, 10,428 / 10,428 tests, none unreached, nothing out of its time and no item over half of its bound (322 starts in each phase; host factor 1.024: 7 units' example bounds above the 2 s floor, up to 7.8 s, 102 units' call bounds above 1.5 s, up to 34.8 s), no control tripped, 963 s; starting tree 0.0; no-op 0.0 with `end_from` `unchanged` (1,716 entries listed) |
| Regrade of the stored submissions after fix round 9 | this machine, the entry point's steps, examples and calls, one worker, 2026-11-26 | 16 submissions, reward 0.003 to 0.853, each within 0.006 of the regrade with the units left whole (8 up, 8 down), the order unchanged but for two sessions 0.0015 apart; every move made of the 42 units that left the set, the 20 that joined it and 32 verdict changes in 8 submissions, each of the 32 running a body whose state changed this round (31 now whole, 1 removed again), traced in the submission's own tree; none with a unit or call unreached, a late file or a control tripped (see [Trial evidence](#trial-evidence)) |
| Floor on fix round 9's calls (`fixtures.py`, `floor.py`, the reviewers' composite with each delegation also run as the unit's own body, the integrity reviewer's rules) | this machine, 2026-11-26 | through the verifier raise, first argument and flip 0.0 (flip behind a table 0.0034); one constant 0.0065, type default 0.0103, delegation 0.0052 and 0.0132 in the original tree (0.0003 and 0.0 as the unit's own body), the combination 0.0324 (0.0163); the reviewer's rules 0.0064 (0.0121); hidden-result bounds 0.0350 (0.0173) and 0.0290; all under 0.05 |
| Hostile cases through the verifier's steps (one unit each: `preview` to a file, `open` with a seek, `json` rebound, `os.fork` in a loop, a 64 MiB result, a 256 MiB print before the original body), on fix round 9's build | this machine, the entry point's steps, one worker, 2026-11-26 | 0.9721, completed: the first four refused by the body rules; 1,774 / 1,825 units in the set and 6,048 / 6,137 counted calls (the six units and their callers, a polynomial method much of `sympy.polys` calls among the hosts); nothing unreached, no control tripped, none an evaluation error |
| Hostile trees as the platform grades them (the shipped limits: 4 workers, examples 2,700 s, calls 2,400 s, measurement 6,000 s), on fix round 9's build | this machine, the entry point's steps, the tests not run, 2026-11-26 | loop-5 0.6164, completed, 691 + 708 items out of time, 0 not reached; slow-50 0.7211, completed, 468 + 437 out of time, 0 not reached; loop-all 0.0000, completed, 2,114 + 2,114 out of time, 0 not reached, the phases 1,769 s and 1,554 s; none an evaluation error, no control tripped |
| Fix round 10's build (`error_calls.py`, `keep_whole.py` with the short-body test, the closure) | the prepared inputs, 2026-11-26 | 7 units outside the set with an error example given the example's own call (8 counted calls, the error expected); the short-body test finds one pair, left whole; 2,115 units in 323 files, 14,523 calls (6,145 counted, 1,832 units in the set, 283 graded only through others: 233 by a call, 50 by examples); a fixed point in one round |
| `checks/` (144 tests: the instruction's wording, no stop by time without a first process, a late reader, the freeze, literal keys, the short-body test, the graded units) and the repository check | commit `c55180c` (2026-11-26, before the package) | pass |
| `oddish preflight` | flat bundle `1f1b2f2ab4fa` (`ops/sympy-restoration/dist-12h/`, key rotated, 384 files; platform content hash `5cefe91fe0fe…`, version 4's `4ce37762a342…`; network plan as before) | pass (1 task) |
| Cue sweep of everything the agent can read or see running (back office v14's list and the sixth re-check's phrases), and the word sweep, the upstream check, the pickle and the key | bundles `32fbeb905028` → `1f1b2f2ab4fa` | the instruction: "exactly as", "exactly", "original", "rejected", "every other", "no example or test", "checks your work", "delivered form", "the same means", "not a restoration", "documented outputs", "behaves", "session" and "upstream" all to 0; the tool's text: "delivered form", "original", "rejected", "exactly" to 0; kept: SymPy's own text, the command `check`, the repository's tests, doctest's "expected"; the task's own 48 text files 0 non-ASCII bytes; the 384 files equal to the worktree at commit `c55180c`; the key's copies equal, new and held by no other file |
| Reference, the agent's starting tree and a turn of no length, after fix round 10 | this machine, the entry point's steps, one worker; the no-op through the shipped hooks and the real net check | reference 1.000000 and complete: 1,832 / 1,832 units in the set, 6,145 / 6,145 counted calls, 14,523 / 14,523 calls, 2,115 / 2,115 units' examples, 10,428 / 10,428 tests, none unreached, nothing out of its time and no item over half of its bound (323 starts in each phase), no control tripped, 903 s; starting tree 0.0; no-op 0.0 with `end_from` `unchanged` (1,716 entries listed) |
| A collection pause while a reader waits (the private inputs loaded: 3.83 million tracked objects, a full collection 1.62 s; a stand-in runner answering at 1.1 s, a collection from 0.95 s, the deadline at 2.0 s) | this machine, 2026-11-26 | the reader before fix round 10: a timeout 3 times of 3 (at 2.34 to 2.39 s); the reader after: the answer 3 times of 3; the reader before with the inputs frozen: the answer at 1.11 to 1.12 s, the collection 0.00 s |
| Floor on fix round 10's calls, with the accessor synthesis graded again (`fixtures.py`, `floor.py`, the reviewers' composite, the integrity reviewer's rules; the fourth re-check's synthesis tree through the verifier's runners with every call's result kept, scored as that re-check scored it) | this machine, 2026-11-26 | through the verifier raise, first argument and flip 0.0 (flip behind a table 0.0034); one constant 0.0065, type default 0.0103, delegation 0.0052 and 0.0132 in the original tree (0.0003 and 0.0 as the unit's own body), the combination 0.0324 (0.0163); the reviewer's rules 0.0063 (0.0120); hidden-result bounds 0.0350 (0.0172) and 0.0290; the accessor synthesis 0.0175 as a tree, 0.0356 behind a table, 0.0384 with its per-call tables (at most 0.0413 were its 8 refused bodies to match, 0.0426 with the error strategy); all under 0.05 |
| One hostile tree as the platform grades it (5% of the units never end; the shipped limits: 4 workers, examples 2,700 s, calls 2,400 s, measurement 6,000 s), on fix round 10's build | this machine, the entry point's steps, the tests not run, 2026-11-26 | loop-5 0.5862, completed, 775 + 733 items out of time, 0 not reached, the phases 681 s and 635 s (round 9's 0.6164: the same draw over renumbered unit ids); no evaluation error, no control tripped |
| `checks/` (147 tests: the first process seen twice on a stand-in `/proc`, the placeholders in the story and the rules' last line, an error compared one way) and the repository check | commit `1b6a171` (2026-11-26); the delivery, packaging, comparison and transplant checks (93) again at `93d26de` | pass |
| The seventh re-check's stop path on the shipped watch (`pwd` under a root `su` for one look before the clock, the session from 0.3 s after it, a blip mid-turn; the limit scaled to 3 s) | this machine, a stand-in `/proc` | the net check of fix round 10: the first process the `pwd`, `dev` ended 0.7 to 0.79 s before the agent's limit (two runs); fix round 11's: the session, the `pwd` passed over, `dev` ended 0.31 to 0.41 s after the agent's limit; the re-check's own probe, which calls `first_process` once, now finds no first process and ends nothing |
| `oddish preflight` | flat bundle `cbe004ce22d8` (`ops/sympy-restoration/dist-12h/`, key rotated, 384 files; platform content hash `22886dfb8414…`; network plan as before) | pass (1 task) |
| Cue sweep with the seventh re-check's words ("selected", "replaced by placeholder", "another way", "skeleton", "curated", "constructed", "deliberate", "exercise" and others) | bundles `1f1b2f2ab4fa` → `cbe004ce22d8` | "selected" and "replaced by placeholder" gone from the instruction, the tool's text and `ATTRIBUTION.txt`, "another way" from `restore rules` (the instruction's one is the requirement's "the same expression written another way"); "recovery tooling" in the instruction, `restore`'s help, the library and `ATTRIBUTION.txt`; "skeleton" left only as the tool's own path and code; nothing else moved but one root-only comment |
| Reference, the agent's starting tree and a turn of no length, after fix round 11 | this machine, the entry point's steps, one worker; the no-op through the shipped hooks and the real net check | reference 1.000000 and complete: 1,832 / 1,832 units in the set, 6,145 / 6,145 counted calls, 14,523 / 14,523 calls, 2,115 / 2,115 units' examples, 10,428 / 10,428 tests, none unreached, nothing out of its time and no item over half of its bound, no control tripped, 974 s; starting tree 0.0; no-op 0.0 with `end_from` `unchanged` |
| Regrade of the stored submissions after fix round 11 | this machine, the entry point's steps, examples and calls, one worker, 2026-11-26 (the machine shared with other work during the last grades) | 16 submissions, reward 0.003 to 0.853, each within 0.0005 of fix round 9's regrade (11 up, 5 down), the order unchanged; every move made of the 7 units that joined the set (a submission passes 0 to 7 of them, the full-session claude-code runs 6 or 7) and 2 units whose verdict a call's time-out changed, one each way; none unreached, no late file, no control tripped |
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
cd tasks/static/library_build/sympy-restoration/scripts
python package_step.py            # writes experiment/dist/bundles/<hash>/<task slug>/
oddish preflight ../experiment/dist/bundles/<hash>/swe-m2_scientific-computing_sympy-restoration
```

`oddish upload <bundle>` followed by `oddish run --task <id>` was used on
2026-11-17 because `oddish run <bundle>` failed with a database error when
creating a new task.

Other bundles, all from the same sources:

```bash
python package_single_step.py                 # same runtime files (Proximus)
python package_session.py --session 1         # 48-hour chain, retired 2026-11-19: refused, the image has no timer
python package_session.py --session 2 --chain <run> --archive <candidate_unit_files.tar.gz>
python package_regrade.py <candidate_unit_files.tar.gz> --label <name>   # grade a stored submission again
```

Rebuilding the counted calls (2026-11-20, as rebuilt after the re-check), in
order, from the original tree with only the visible tests (`original_visible`),
the original with every test (`original_full`) and test-free copies of the
original and the skeleton. `recorded.pkl` holds the calls recorded from SymPy's
own tests and docstrings, without the calls added earlier:

```bash
python builder/regold.py original_nt skeleton_nt recorded.pkl out/            # every result with the current comparison
python builder/documented.py doctests|tests original_visible units.json recorded.pkl lib recorded.json <packages>
python builder/echoes.py original_nt echoes.json --calls recorded.pkl out/gold.json   # results that are an argument
# units left without a counted call get candidates: calls recorded while the withheld tests run
# (one candidate per argument list not recorded yet) and variants of their own arguments
python builder/rec_withheld.py original_full units.json uids.json withheld_functions.json calls.pkl
python builder/variants.py make original_nt recorded.pkl uids.json variants.pkl
python builder/variants.py contract original_nt candidates.pkl kept.pkl       # stated prime contracts
python builder/variants.py screen original_nt skeleton_nt kept.pkl screened/
python builder/echoes.py original_nt echoes-c.json --screened screened/screened.pkl
python builder/documented.py doctests|tests original_visible units.json screened-payload.pkl lib cand.json <packages>
python builder/variants.py select recorded.pkl out/gold.json screened/screened.pkl sel/ \
    --documented recorded.json,cand.json --echoes echoes.json,echoes-c.json
python builder/regold.py original_nt skeleton_nt sel/inputs.pkl final/
python builder/echoes.py original_nt final-echoes.json --calls final/inputs.pkl final/gold.json
python builder/finalize_documented.py final/inputs.pkl final/gold.json final/documented.json recorded.json --echoes final-echoes.json
python builder/unit_bodies.py solution/data units.json tests/private/unit_bodies.json
python builder/floor.py original_nt final/inputs.pkl final/gold.json final/documented.json
python builder/fixtures.py raise|identity|flip original_root fixture/ [final/inputs.pkl final/gold.json final/documented.json]
```

Since 2026-11-25 the unit list ends with one more step: the units that no graded
item fails without are left whole (the rule and its one exception are in
`keep_whole.py`), and the prepared inputs that name units are written again into
`out/`, at the task's own paths, to be put in place. Since 2026-11-26 a near-copy
of a graded body first gets counted calls of its own (`twin_calls.py`, then the
variant builder's steps above), and where it gets none it is left whole with its
twins (`--whole`); the trace, the probe and the rule repeat until no removed unit
is ungraded:

```bash
python builder/graded_coverage.py original_root units.json private/vectors ../tests/verifier/lib coverage.json
python builder/absorbed.py original_root units.json private/vectors ../tests/verifier/lib coverage.json absorbed.json
python builder/keep_whole.py <task_dir> original_root coverage.json out/ --absorbed absorbed.json --pairs-only pairs.json
python builder/twin_calls.py original_nt units.json inputs.pkl gold.json documented.json pairs.json twin.pkl   # then contract ... select
python builder/twin_calls.py shown sel/ before_gold_keys.json units.json <documented.py outputs>
python builder/keep_whole.py <task_dir> original_root coverage.json out/ --absorbed absorbed.json --whole whole.json
```

Since fix round 10 the selection first takes, for the units outside the set
whose docstring examples show an error, the example's own call as a counted call
that expects that error, before the trace:

```bash
python builder/error_calls.py original_root units.json uids.json sel/ sel_with_errors/
```

The builder's report (`out/keep_whole_report.json`) is kept beside the prepared
inputs as `experiment/keep_whole_report.json`, where `checks/test_graded_units.py`
reads which bodies were left whole.

Before each uploaded version, `python builder/delivery_key.py <task_dir> --rotate`
replaces the key the collect step signs with.

Development checks:

```bash
uv run --frozen pytest -q tasks/static/library_build/sympy-restoration/checks
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
- Before any model trial of the continuous version: reference 1.0 and no-op 0.0
  twice each on the platform, the platform's pre-trial audit clean, and a
  regrade there of a stored submission with no test unreached (the condition for
  the tests to join the reward inside the min).
- Probe each target model's recall (see [Novelty](#novelty)) before reading a
  frontier score as difficulty.
- Read the reference's first platform grade for its 17 counted results that
  hold a Python float: the image's Python 3.12.3, its float `**` and C complex
  arithmetic are the only unknowns the few-unit bound is there for.
- Run the delivery hooks on the platform before any model trial (finding 9): a
  canary whose reference leaves a detached fetch-and-overwrite loop must score 0
  with its files `late`; a time-limit canary, a reference that keeps working
  past the limit with a load process and a fetch, must score 0 with its files
  `late` and `end_from` `limit` or earlier; a reference that saves a unit file
  by rename just after the limit must keep that file, `copied`, with its
  content at the limit; the reference twice with the record present and
  `end_from` `session` (one session seen, began within seconds of the start),
  the no-op twice with `end_from` `unchanged`; claude-code and Proximus must
  start and work as `dev`; the flat single-step bundle must run the hooks. If
  the net check's probe does not see the opening there, certify copies taken
  while egress was closed instead.
- On the platform's first grade of this version, confirm that Harbor switches
  the verifier's environment, now declared with public egress for its build, to
  no network before the tests run: the verifier refuses to measure otherwise
  (an evaluation error), so the reference's first grade shows it either way.
- Before a Proximus trial on this version, read the `sessions` of one Proximus
  record: if its work runs outside its exec sessions and its last session began
  within ten minutes of the start, the session end would cut its later writes,
  and the session window has to change for it.
- Look again at the withheld tests in the reward (option B of the 2026-11-25
  decision on the units no graded item ran) once a platform run shows their
  phase completing reliably.
- The integrity review's 39 functions that were never units and are strong
  twins of 22 graded units (plain token ratio 0.80 or more, a graded body of 40
  tokens or more; fifth re-check): reported, not changed. Leaving the 22 whole
  would take their counted calls out of the reward; removing the 39 would add
  units with no graded item of their own. A decision for the panel.
- Proximus on Oddish cannot run a task that declares steps; either it learns to
  run a one-step task or every v2 task needs a single-step variant.
