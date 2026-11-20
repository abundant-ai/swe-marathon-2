# SymPy restoration

Author notes. Nothing in this file is shipped to the candidate or to either image.

SymPy 1.14.0 with the bodies of 2,671 functions and methods in 355 files removed
(37,293 non-blank lines of body). Signatures, decorators, docstrings and all other
code stay. The candidate writes the bodies back, without network access, using a
small `restore` command that reports progress and checks work against the graded
view. The reward is continuous: the smaller of two shares measured on recorded
calls that nothing visible answers (no docstring example or visible test makes
them, even with its symbols renamed, and their result is neither a documented
result of their unit nor one of their own arguments; see
[Reward formula](#reward-formula)).

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
  1,955 units are in the set and 716 are left out. Floor, through the verifier
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
  report it; the reward stays bounded by c, which it cannot forge), a neutral
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
  moves that end. The session end applies only when that session began within
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
  written when) and stays an evaluation error for any other.
- Hostile errors. Every way the work could turn its own failing trial into an
  evaluation error is now a scored 0 or harmless: nothing usable under the
  tree's name (removed, a link, a file, a link to another directory) is a
  signed refusal with an empty tree in its place, as is a tree that cannot be
  listed (the collect step's `failed` state is gone); a tree deeper than 64
  directories, with a path over 1,000 bytes, with a directory whose name a copy
  might not carry, or whose record would pass 48 MB is refused before it can
  break the verifier's limits or the platform's copy; a file whose name a copy
  might not carry is removed and noted; every character of the mark outside
  printable ASCII is escaped and the verifier splits it on line feeds only (a
  link named with a form feed had unsigned the mark); the room the setup step
  set aside is given back as soon as `dev` has ended, before anything else is
  written; the net check stops and kills `dev` with its own signals as well as
  with tools, so it works when no process can be started, and a poll or probe
  that cannot start is a local poll instead of the end of the net check. A live
  process of `dev` that outlived the collect step (zombies are not counted) is
  now an explicit evaluation error.
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
  unit. 99 checks pass. Not run here: anything that needs Linux (`/proc`,
  `setpriv`, `su`, the kill itself), or the platform.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-restore-bodies` | Implemented. Instruction, agent image, separate verifier image, reference solution. |
| Further steps | Not designed. See [Workload](#workload). |
| Prepared inputs | Present locally under Git-ignored paths; produced by the builder in `scripts/builder/`. |
| Oracle | 1.0 on the platform under the binary reward (at least 14 grades); 1.0 under the continuous reward through the entry point's steps on this machine (2026-11-20). Not yet re-run on the platform. Provenance: the original SymPy 1.14.0 source of the 355 files. |
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
  mode 0700 and owned by root, off `PATH`; the agent's user cannot read them,
  but `ps` shows the net check (root) and its probe (`nobody`) polling three
  public hosts. The names were kept: the sibling Carve passed two audits with
  the same ones, and what `ps` shows no longer gives anything to aim at (a probe
  that cannot see ends the work, and the session end does not depend on the
  probe).
- The agent runs as `dev` (uid 10001). `/app` is root-owned and sticky,
  `/app/sympy` is root-owned and world-writable with everything in it owned by
  `dev`, so `dev` can change every file but cannot replace the tree itself.
  `/app/PROGRESS.md` is created for `dev`; `/opt/restore` is read-only except
  `var/`, where `restore` keeps its delivered-form copy and its state.

## Design dimensions

### Novelty

What it adds: one coherent body of work that is too large for one context window
(2,671 units, 37,293 non-blank lines of body) with a grade per unit, so partial progress is
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

- SymPy is public and in pre-training data, and for a strong model much of the
  work is recall. On the best run of the flash model every trial so far used
  (base trial 5, relace/deepseek-v4.1-flash) 546 of 2,671 submitted bodies
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
2,671 units and 16,737 calls on the bars of a complete restoration); an empty
delivery and a tree of bare `raise NotImplementedError` bodies score 0. Grading
one submission twice on the platform gave 9,298 and 9,305 passing tests before
the deadline and seeding fixes of 2026-11-20; the examples are now seeded per
unit, which removed the one known source of unit flips (a random draw).

### Realism

Restoring lost implementation from signatures, documentation and tests is real
but uncommon work (damaged checkouts, partial ports, code removed for licensing).
The setting is contrived in one respect: nobody loses 2,671 bodies at once while
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
  six full-session claude-code runs have 72 to 101 units in the set whose
  examples pass and that match no counted call (3.7% to 5.2% of the
  1,955), 59% of them matching a documented call.
- Recall. Closing the floor needs upstream's exact internals, which only memory
  of SymPy supplies (see [Novelty](#novelty)). A frontier model may score high by
  recall; probe it before reading its score as difficulty.

The rest is breadth. Single-context runs stopped at 588 to 1,824 steps when their
context filled; only a harness that compacts and delegates to helpers reached the
end (15,678 to 45,324 steps in 9 hours), and the unit share tracks steps and
helper count more than anything else. On the continuous reward the stored
submissions read 0.004 to 0.896: 0.71 to 0.90 for claude-code with helpers over a
whole session, 0.36 to 0.42 for Proximus in one thread, 0.10 to 0.23 for
mini-swe-agent, 0.021, 0.004 for two runs that ended their turn within 41 minutes (see
[Trial evidence](#trial-evidence)). For a parallel harness with a flash model that is the
easy end beside the sibling rebuild tasks; compare models within one harness only.

### Initial feasibility

Solved by construction: the original source is the reference solution and scores
1.0. For an agent, reward 1 needs every counted unit and call, the invisible
residue included; no run has reached it, and more time did not shrink it.

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

0. Delivery (`verifier/delivery.py`). The work runs as `dev`. A root setup step
   records when the work started, to the fraction of a second, and starts
   `fsmaint-netcheck`, which does two things until the collect step stops it.
   It polls three public hosts with a TLS handshake (as `nobody`, in a probe
   process of its own) every 0.1 s: a poll is open when a handshake completes,
   local when none does and an attempt failed for a reason of the machine
   rather than of the network (no free local port or address, no file, buffer
   or memory, a thread or probe that would not start), and closed otherwise.
   Closed polls in a row make a stretch; a local poll neither extends nor
   breaks one; a stretch of at least three ends at an open poll, or at three
   local polls in a row (the network can no longer be seen), and then its last
   closed poll is recorded and every process of `dev` is stopped and ended. And
   it looks at `/proc` every 0.1 s for the exec sessions of `dev`: a process of
   `dev` whose parent is a process named `su` or `runuser` of the real user
   root (not the first process), or that has no parent in the container. Harbor
   runs every command of the agent as `su dev -s /bin/bash -c ...` on Modal and
   as `docker exec -u dev` under Docker; a process the agent starts, in the
   background or detached, has a parent of `dev`, then the first process, never
   such a parent, so it is never a session. When the work ends, the collect step
   (`environment/fsmaint-sweep`, root) stops, lists and ends every process of
   `dev`, gives back the room the setup step set aside, probes the hosts
   itself, lets the net check finish one poll and one look that started after
   that and stops it, records every entry under `/app/sympy` (type, size,
   modification and change times, sha256) before touching anything, removes
   every link, anything that is neither a file nor a directory and any file
   whose name a copy might not carry as it is, and writes a record and a mark
   into the tree. The end of the work is the earlier of two. One is the last
   closed poll of the longest stretch an opening ended; a stretch still going
   on, or one whose last closed poll came after the collect step began, gives
   the collect step's start only when the collect step's own probe found the
   hosts closed, and nothing otherwise. The other is the last time the exec
   session that ended last was seen alive, when that session began within ten
   minutes of the start of the work (one session for the whole of the work, as
   claude-code, mini-swe-agent and the oracle run) and no session was alive
   when the collect step began; a harness that runs one exec per command gives
   no such end, and the first one stands. Without either, the start of the work
   is the end when nothing in the tree changed since then (the no-op);
   otherwise there is no end. The mark is signed with a key in the agent image
   that only root can read and that the verifier image holds too. Before
   grading, the verifier checks that its own network is closed (a TLS handshake
   to three public hosts; open is an evaluation error), then reads the mark: no
   tree, no mark, an unreadable, oversized or unsigned mark, a record that
   differs from the signed one, a listed file that did not arrive as listed, a
   link or an unlisted file that arrived, or a record that says a live process
   of `dev` outlived the collect step is an evaluation error (no reward file),
   since the collect step always leaves a marked tree and these come from the
   infrastructure. A tree the collect step refused is a completed evaluation of
   an empty delivery (0): nothing usable under its name (nothing at all, a link,
   a file), a tree it could not list, or one past its limits (200,000 entries,
   2 GB, 64 directories deep, a path over 1,000 bytes, a record over 48 MB, a
   directory whose name a copy might not carry). A record without an end of the
   work grades a tree that restores no unit (0) and is an evaluation error for
   any other. A unit file whose change or modification time is at or after the
   end, less 0.25 s, is not taken over: its units are `late` and count as not
   restored. The transplant never reads a unit file through a link.
   `late_files`, `egress_open`, `end_from`, `end_note` and the collect step's
   record go to `metrics.json`.
1. Graded tree. Start from the reference skeleton. For each unit, copy in the body
   found in the submitted file for the function of the same qualified name.
   Nothing else from the submission is used. A body containing constructs for
   reaching the process, the file system, the interpreter or a test framework is
   rejected (`common/restorelib.py`).
   The whole measurement has one deadline, 6,000 s from its start
   (`measure_budget_sec`), inside the verifier's 6,600 s. The docstring and call
   phases also have their own caps (40 minutes each, so a slow host has room
   for the two rewarded phases); the test phase has what they leave. Every
   deadline is on the monotonic clock. Submitted code runs with a 4 GiB
   address-space limit where `prlimit` can set one (a note says when it cannot).
2. Docstring examples. Each restored unit's own examples, run the way SymPy's
   doctest runner runs them, 20 seconds per unit, at most 40 minutes in total.
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
3. Recorded calls. 16,737 calls, at least one per unit, replayed one at a time
   in the sandbox with a 10-second limit, at most 40 minutes in total. The sandbox
   writes the result; the verifier compares it with the reference result, which
   the sandbox cannot read. 13,382 calls were recorded from SymPy's own test suite
   and, for units it never calls directly, from docstring examples; 3,355 more
   were added for 990 of the 1,697 units whose recorded calls are all
   documented: 1,567 recorded while the withheld tests ran and 1,788 made from
   the unit's own arguments, with every symbol renamed by one map over all of
   them or one integer shifted (never an integer whose docstring states a domain,
   such as prime, odd or positive, nor a polynomial routine's level, and an
   integer argument never to a value outside the range of the unit's recorded
   calls unless the docstring describes a plain integer; a candidate that breaks
   a prime contract its docstring states is dropped), each result taken from the
   original. A call is
   documented when a docstring example or a visible test makes a call with the
   same arguments, directly or inside the library while it runs, or with the
   same arguments up to a renaming of symbols that keeps their assumptions; when
   its result is one of its own arguments unchanged (a body that returns that
   argument answers it); or when its result is one that another documented call
   of its unit returns (applied until nothing changes). 9,883 calls are
   documented and listed privately (`tests/private/vectors/documented.json`),
   6,854 are not, and only those count for the reward. A result is
   compared by its canonical form (`verifier/lib/canon.py`): value, type and
   container, order, the form of a returned expression, and the state of an
   object the call builds or changes. What is not behaviour is left out, and
   nothing more: a memo slot an object fills lazily from its other state counts
   where both sides hold a value (for a dict of them, on the keys both hold); a
   symbol, Dummies included, is its name and the assumptions SymPy's equality
   uses; Dummies the call makes are numbered from a process-wide counter, so they
   compare up to one consistent renaming, while a Dummy that came with the
   arguments keeps its name and index; likewise a frame's creation counter
   (`ReferenceFrame.index`, which orders a vector's printed components) is exact
   for a frame that came with the arguments and compares up to an
   order-preserving renaming for frames the call makes; dense or sparse storage
   of a domain matrix counts for the 24 converters and constructors whose result
   is that storage, and a zero stored in sparse storage always counts; Truss's
   coordinate lists kept beside its nodes count, except in what
   `Truss.remove_node` leaves, where upstream keeps them inconsistently. Strings
   compare exactly, except the LaTeX of `multiline_latex` and `vlatex`, compared
   without the whitespace LaTeX ignores; floats with a relative tolerance of
   1e-9. One process
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
Limits:

- A recorded call checks one input, so a body can match its calls and still be
  wrong elsewhere.
- Reference results that could not be reproduced exactly (objects that lose state
  when pickled, bare `None`, exceptions, unstable ordering, results over 400 kB)
  were dropped at build time, so error behaviour is measured only by the
  repository tests (309 withheld test functions assert an exception), which are
  reported and not rewarded.
- 716 units have no call that nothing visible answers (319 for which no candidate survived the screens, 148 whose every candidate a visible run makes, 248 whose every candidate returns an argument or a documented result, and the one unit whose run-time comparison stayed capped). They
  are left out of the reward's unit set and counted (`units_left_out`). They
  are smaller than the units in the set (median 5 non-blank lines
  against 9) and hold 177 of the 229 units whose recorded
  results are all booleans, so predicates are hardly rewarded; the set covers
  80.3% of the body lines. Their examples and calls are
  still run and reported (`units_left_out_passing`).
- For some units no visible evidence fixes the property a hidden call compares
  (see [Difficulty](#difficulty)); that residue is part of the reward.
- Strings are compared exactly, layout included, while the docstring examples
  are checked with whitespace normalised; only the LaTeX of two units ignores
  whitespace. A memo slot filled with a wrong value where upstream leaves it
  empty is not seen by the call that fills it.

Requirement checks (`steps/01-restore-bodies/tests/verifier/registry.py`):

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
D      = recorded calls that are not documented (step 3): 6,854 of 16,737
set    = units with at least one call in D: 1,955 of 2,671 (716 left out, counted)
u      = units in the set whose docstring examples pass and that match at least
         one of their calls in D  /  1,955
c      = calls in D that match  /  6,854
reward = min(u, c)  if candidate_tree and measurement_integrity passed, else 0
```

- Continuous (`reward_type = "continuous"`), written to `reward.txt` with six
  decimals. Chosen on 2026-11-20 over the binary reward, whose bar sat above the
  invisible floor (see [Difficulty](#difficulty)).
- `complete` in `metrics.json` keeps the old verdict of the binary reward, not the
  instruction's sense of complete (every function behaves exactly as the original): all five checks passed, that
  is at least 99% of all units passing their examples and matching one recorded
  call, 90% of all calls and 95% of the graded tests. It is `null` when only items
  the measurement did not reach keep a bar from being met.
- The repository tests are reported (`test_share`), not rewarded, until a regrade
  under the one-deadline measurement leaves no test unreached; they would then
  join inside the min, never as a weight. The pooled `partial_score` is gone: it
  took the test share from the sandbox and ignored the controls.
- Denominators are fixed. A unit that is not restored or is late counts as not
  passing; its calls as not matching. A unit or call not reached before the
  deadline counts as failing in `unit_share` and `call_share`; if the items not
  reached could raise the reward by more than 0.001
  (`unit_share_if_reached`, `call_share_if_reached`), the time, not the
  submission, would decide, so the evaluation ends with an error and no reward.
  Units and calls left after their module's restarts ran out are failures, not
  unreached items.
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
- Floor, on the final calls: bodies that restore nothing, graded as trees
  through the verifier's own steps (`scripts/builder/fixtures.py`), and behind a
  table of documented outputs, which makes every example pass and answers no
  counted call (the same counted-call matches with every unit's examples counted
  as passing; `scripts/builder/floor.py` computes the same bounds statically).
  Unit rule "one counted call" (in force) and "half the counted calls":

| Fixture (bodies that restore nothing) | Through the verifier | Behind a table, one call | Behind a table, half the calls |
| --- | --- | --- | --- |
| Bare `raise NotImplementedError` | 0.0 | 0.0 | 0.0 |
| The first argument unchanged | 0.0 (23 units pass their examples, no counted call matches) | 0.0 | 0.0 |
| The other boolean where a unit's documented results are one boolean, else the first argument | 0.0 (20 units pass their examples, 88 counted calls match) | 0.0128 | 0.0128 |
| The unit's most frequent documented output (static) | | 0.0 | 0.0 |
| One common constant for every unit, the best of 27 (static) | | 0.0150 | 0.0133 |
| A table that also answers a documented call with its symbols renamed (static) | | 0.0019 | 0.0019 |
| Renaming table, boolean flip and first argument together (static) | | 0.0147 | 0.0147 |
| Best constant per unit, chosen after seeing the hidden results (static; a bound, not buildable) | | 0.0585 | 0.0583 |

  Every fixture that a submission could build stays at or below 0.015. The
  one bound above 0.05 lets every unit choose its constant after seeing the
  hidden results, which no submission can, and the half rule would not lower
  it (the call share binds); so a unit still needs one matching counted call.
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
| 1 | A body runs arbitrary code at grading time (for example through `sympify` of a string) and patches the example and test runners in-process, forging those two measurements | Sandbox process | Executed in red-team round 2 | The reward is min(u, c); c is compared by the root process with references the sandbox cannot read, and a counted unit also needs a matching counted call; the tests are not rewarded | Forged examples can raise u up to the share of units whose counted calls already match, so the reward is at most c, which cannot be forged; what bodies that restore nothing match on the counted calls is the floor (finding 4). Comparing example output in the root process would not close this: the expected output is in the docstring the sandbox reads, so a patched runner can report it, and that was not built | Red-team the runners with forged output | 🟡 YELLOW / MEDIUM |
| 2 | Read reference results or the withheld tests | File permissions in the verifier image | Attempted in both rounds; not reached | Private inputs readable by root only; sandbox runs as `nobody`; no test directories in the tree during phases 2 and 3 | Depends on the privilege drop | Re-run on the v2 bundle | 🟢 GREEN / LOW |
| 3 | Edit tests, module-level code or other functions to make checks pass | Graded-tree construction | Executed; no effect | Only unit bodies are copied into the reference skeleton; `checks/test_transplant.py` | None found | Keep the check | 🟢 GREEN / LOW |
| 4 | Return the documented outputs for the documented inputs, and something cheap otherwise: a constant, the first argument, the other boolean, or a documented result renamed | Which calls count | Review of the binary version: tables passed `trig_split`, `viete`, `wigner_3j` and 14 more units through the real verifier. Re-check of 2026-11-20: behind a table, a first-argument fallback and a renaming table reached 0.07 to 0.12, most of it on the variants added that day | Only calls nothing visible answers count (D): no docstring example or visible test makes them, even with its symbols renamed, and their result is neither a documented result of their unit nor one of their own arguments; variants rename with one map over all arguments and shift no integer with a stated domain. Measured on the final calls, through the verifier and behind a table (see the floor under [Reward formula](#reward-formula)): every buildable fixture 0.015 or less | A constant can still equal some counted results by chance; chosen per unit after seeing the hidden results it would reach 0.059, which no submission can | Re-run `fixtures.py` and `floor.py` after any rebuild of the calls | 🟢 GREEN / LOW |
| 5 | Change how a runner reports results | Runner control items | Executed in round 1 through module-level `os`/`sys`; fixed | Control items with known outcomes in every pytest run; the records of a run cannot hold more passes than that run's tally; forbidden constructs in bodies. Forged start or collection records can only remove tests from later runs, which lowers the score | A forgery that also gets the controls right falls under finding 1. The per-file runs added on 2026-11-17 have not been attacked | With finding 1 | 🟢 GREEN / LOW |
| 6 | Tamper with reward or result files | Separate verifier container | By design; not attacked | Verifier starts fresh with only `/app/sympy`; output directory closed to the sandbox user | None found | Attack on the v2 bundle | 🟢 GREEN / LOW |
| 7 | Anything that depends on the new entry point, check registry or reporting | v2 verifier code | Not attacked | Same measurement code as v1; reference and no-op baselines on the v2 bundle | Unknown | Red-team run against the v2 bundle | 🟡 YELLOW / UNASSESSED |
| 8 | Reach the network during the work phase to fetch SymPy | Agent network policy | Probe task, 2026-11-15: PyPI and GitHub unreachable from the work phase; 217 in-work fetch attempts in one 12-hour run all failed (TCP connected, TLS did not) | `[agent] network_mode = "no-network"`; the instruction forbids another copy; SymPy is not installed elsewhere; the image's attribution names no download | Agent tooling is installed at setup with public egress; host-name filtering not probed for every route | Probe the routes as `dev` | 🟡 YELLOW / MEDIUM |
| 9 | Leave a process running after the work that fetches SymPy once public egress returns (about 0.2 s after the work ends, before collection: 0.8 s and 11.8 s on two 12-hour runs) and writes the original into `/app/sympy`, directly or behind a link; the original scores 1.0. Variants: hold every local port (or exhaust another resource of the machine) so the net check's probe fails and its closed stretch runs on past the turn; load the CPU or the link so its handshakes time out | Delivery: user, hooks, record | Reproduced by review with the verifier's own transplant: before 2026-11-20 (2,671 restored, a tree identical to the reference); on 2026-11-20, a write after a turn shorter than the net check's old one-minute arming taken whole, a late file graded through a directory link, and (re-check 2) a fetch while the probe failed for want of ports, taken because such a failure counted as a closed poll and the end was moved to the collect step's start. All fixed; `checks/test_delivery.py` runs the real net check whole for a blinded probe and a no-op turn, and covers a 3-second turn, every unknown end, the session end, file and directory links and every refused tree | The work runs as `dev`; a poll that fails for a reason of the machine is not a closed poll, and three in a row end the stretch; the net check records the end of every stretch an opening ends and ends `dev` each time; it also watches the agent's exec sessions, and the end of the work is the earlier of the net check's end and the end of the session that ran the whole work, which no process the agent starts can move; the end is never moved to the collect step's start unless its own probe found the hosts closed; the collect step stops and ends the rest, lets the net check finish one more poll and look, records every file's change time before touching anything and removes every link; the verifier takes no unit file changed at or after the end and none reached through a link; a link or an unlisted file that arrived, a short delivery or a surviving process is an evaluation error; the mark is signed with a key `dev` cannot read | A write through a file mapping dirtied before the end can change content without moving its times. It needs a live process: the net check ends `dev` at the first open poll (about 0.2 to 0.5 s after the turn) or after three blind polls, but a probe made to time out by load still reads as closed, so such a process can live until the collect step; the session end stops every write that moves a file's times, not one through a mapping. A harness that does its work outside its own exec sessions, and whose last session began within ten minutes of the start, would have its later writes counted late (claude-code, mini-swe-agent and the oracle run the whole work in one session; Proximus is not yet seen). Three polls in a row that fail for want of ports, files or memory end `dev` during the work as an opening would. Closing the mapping residual needs the platform to keep the agent's network policy through collection | Canary on the platform: a detached fetch-and-overwrite loop scores 0 with its files `late`; reference 1.0 (`end_from` `session`) and no-op 0.0 (`end_from` `unchanged`) with the record present; Proximus's process model read from its record (`sessions`) | 🟡 YELLOW / MEDIUM |

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

Regraded on the continuous reward after the re-check (2026-11-20: the rebuilt
counted calls and the narrowed comparison; this machine, the entry point's steps
without the privilege drop; examples and calls, the tests not run since they are
not rewarded). "Reward before the re-check" is the regrade of the round before. The twelve-hour trials' own files were not downloaded, so these
are the stored submissions of the earlier sessions of the same task; every one
scored 0 under the binary reward.

| Submission | Agent / model | Units passing, binary era (of 2,671) | Reward, binary | Reward before the re-check | u | c | Reward now | Units whose examples pass | Bodies identical to upstream |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2 trial 16 | claude-code / DeepSeek v4.1 Flash | 2,557 | 0 | 0.897 | 0.931 | 0.896 | **0.896** | 2,623 | 21.9% |
| v2 trial 17 | claude-code / DeepSeek v4.1 Flash | 2,481 | 0 | 0.887 | 0.906 | 0.882 | **0.882** | 2,541 | 20.3% |
| v2 trial 18 | claude-code / GLM 5.3 | 2,462 | 0 | 0.866 | 0.893 | 0.862 | **0.862** | 2,531 | 18.2% |
| 48 h run a, session 1 | claude-code / DeepSeek v4.1 Flash | 2,375 | 0 | 0.860 | 0.863 | 0.849 | **0.849** | 2,432 | 21.4% |
| 48 h run b, session 1 | claude-code / DeepSeek v4.1 Flash | 2,338 | 0 | 0.843 | 0.845 | 0.843 | **0.843** | 2,384 | 21.8% |
| 48 h run, session 1 | claude-code / GLM 5.3 | 1,976 | 0 | 0.714 | 0.722 | 0.713 | **0.713** | 2,027 | 18.0% |
| 48 h run b, session 1 | Proximus / DeepSeek v4.1 Flash | 1,289 | 0 | 0.418 | 0.445 | 0.425 | **0.425** | 1,352 | 12.7% |
| 48 h run a, session 1 | Proximus / DeepSeek v4.1 Flash | 1,159 | 0 | 0.382 | 0.390 | 0.395 | **0.390** | 1,226 | 15.3% |
| single-step trial 6 | Proximus / DeepSeek v4.1 Flash | 1,077 | 0 | 0.361 | 0.375 | 0.369 | **0.369** | 1,116 | 17.3% |
| 48 h run, session 1 | Proximus / GLM 5.3 | 1,031 | 0 | 0.322 | 0.373 | 0.355 | **0.355** | 1,054 | 15.0% |
| base trial 14 | mini-swe-agent / DeepSeek v4.1 Flash | 716 | 0 | 0.216 | 0.246 | 0.234 | **0.234** | 745 | 11.8% |
| base trial 15 | mini-swe-agent / GLM 5.3 | 346 | 0 | 0.114 | 0.127 | 0.126 | **0.126** | 359 | 9.7% |
| base trial 9 | mini-swe-agent / DeepSeek v4.1 Flash | 334 | 0 | 0.109 | 0.109 | 0.154 | **0.109** | 350 | 7.4% |
| base trial 10 | mini-swe-agent / GLM 5.3 | 274 | 0 | 0.092 | 0.107 | 0.100 | **0.100** | 281 | 9.3% |
| base trial 8 | claude-code / GLM 5.3 | 63 | 0 | 0.024 | 0.021 | 0.037 | **0.021** | 63 | 62.4% |
| base trial 13 | claude-code / GLM 5.3 | 15 | 0 | 0.003 | 0.004 | 0.005 | **0.004** | 15 | 14.3% |

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

Before each uploaded version, `python builder/delivery_key.py <task_dir> --rotate`
replaces the key the collect step signs with.

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
- Before any model trial of the continuous version: reference 1.0 and no-op 0.0
  twice each on the platform, the platform's pre-trial audit clean, and a
  regrade there of a stored submission with no test unreached (the condition for
  the tests to join the reward inside the min).
- Probe each target model's recall (see [Novelty](#novelty)) before reading a
  frontier score as difficulty.
- Run the delivery hooks on the platform before any model trial (finding 9): a
  canary whose reference leaves a detached fetch-and-overwrite loop must score 0
  with its files `late`; the reference twice with the record present and
  `end_from` `session` (one session seen, began within seconds of the start),
  the no-op twice with `end_from` `unchanged`; claude-code and Proximus must
  start and work as `dev`; the flat single-step bundle must run the hooks. If
  the net check's probe does not see the opening there, certify copies taken
  while egress was closed instead.
- Before a Proximus trial on this version, read the `sessions` of one Proximus
  record: if its work runs outside its exec sessions and its last session began
  within ten minutes of the start, the session end would cut its later writes,
  and the session window has to change for it.
- Proximus on Oddish cannot run a task that declares steps; either it learns to
  run a one-step task or every v2 task needs a single-step variant.
