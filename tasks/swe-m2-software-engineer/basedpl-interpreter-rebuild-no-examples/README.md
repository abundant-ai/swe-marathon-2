# BasedPL interpreter rebuild

Author notes. Nothing in this file is shipped to the agent or to either image.

The agent gets an execute-only copy of `bpl`, the interpreter of the BasedPL array language
(github.com/AnswerDotAI/basedpl, Apache-2.0, first published 2026-09-16; pinned at tag v0.1.95,
commit `af3609a9348471494d2bed952cbbf2a5ecdbd53e`, 2026-11-18), and its documentation, and
writes an interpreter that prints the same output. This is idea 9 of the owner's sheet, "no
examples": MirrorCode with only the binary and the docs. Unlike the Goose task it ships no example
runs, no expected outputs, no runner and no tests; the agent finds out what the interpreter does
by running it. A judge panel chose the target (harbor-lh `ops/swe-marathon-v2/decisions/`).

The copy is a hardened build (`common/hardening/`), built once on the author's machine and
installed unchanged in both images and in the reference solution. One step is implemented. QA
waves 1 and 2 (20 passes) have been answered in rounds 1 and 2, and Carve's finding on the shared
collect hook and the round-2 re-checks in round 3, the round-3 re-check in round 4, and the
platform's ungraded capped runs in round 5; the task was then renamed
`basedpl-interpreter-rebuild-no-examples`, scrubbed for the pre-trial audit in round 6, the
scrub's re-check answered in round 7, and round 7's re-check in round 8. Round 8's bundle
`43b39e11805c` went up as v1 under the new name; its pre-trial audit's one must-fix (an
author-only probe in the solution) is answered in round 9, with a sweep of every shipped file and
data file. Round 9's bundle `af0c9f7b084e` went up as v2; its verdict rejected it on one must-fix
(a task-side stop 660 s before the stated limit), answered in round 10 with the completion
sentence reworded and a sweep of what a tree can do to the copy, and round 10's re-check in round
11. Round 11's `a9dad36c7bf0` went up as v3 and `d365dc33100d` as v4, whose verdict rejected the
stop again at 60 s before the limit. In round 12 nothing of the task ends the session: the limit
is 34,560 s again, about 2 s after it a root process stops (SIGSTOP) the session's processes,
whatever changed after the end is taken out, and the upload is a flat single-step bundle under
the same name (the repository keeps its steps layout). The re-checks' should-fixes (what the
frozen processes hold open for writing) are answered in round 12's second and third commits,
and the stop after the limit (the judges' 09:40 UTC amendment) in the fourth and fifth (it counts
from the session's first process), with bundle `ab1a4f4ee269`. That bundle went up as v5. Its
verdict rejected it on two adversarial replays, launchers that earned 6 and 1 of the 1,673 cases
while running nothing. Round 13 answered it with a rule: a reward needed 40 different outputs of
programs given to run (bundle `e9ee043b5d71`, never uploaded). Re-check 10 failed that, since it
zeroed v4's honest GLM run `-33`. Round 14 counts only the outputs a run of the code produces, so
echoes and the build's error messages no longer count, and needs 10 of them (bundle
`5be602ec5ec1`). Round 12's earlier bundles
`ad93859c8f45`, `7867414c5e86`, `c790a042f2be` and `da8966415695`,
round 11's `f93f6c391545` (the same Oddish content as v3), round 10's
`ec8d6ecf327d`, round 9's `5eef6fadb546` and `bf77bf7f91d0`, round 7's `b206089bd38b` and round
6's `ffcf88e892e2` never became versions, and the earlier bundles are `4164eb806274`,
`7462d71fe5a7`, `f0da94435d6b`, `cfc9d42f3e68`, `80d7f600cab8` and `1a08cdb471d0`. See
[Remaining work](#remaining-work) and [Validation gaps](#validation-gaps).

## Development log

### 2026-11-25 (round 14: re-check 10; only outputs a run of the code produces count, 10 of them)

- **The re-check.** Re-check 10 of round 13 (harbor-lh `ops/swe-marathon-v2/qa/basedpl/10-recheck-v6.md`)
  found the rule's code as described and every stub at 0, but failed the round on M1. The
  threshold of 40 zeroed v4's GLM-5.3 run `-33`, an honest partial interpreter of 10,318 lines
  that the platform graded 0.037059 (62 of 1,673 cases) and classed `GOOD_FAILURE` /
  `premature_stop`; it holds 36 outputs on round 13's count. Round 13 had calibrated on v5's runs
  alone. On that count, the reviewer's strongest program with no interpreter and no hidden data
  (`kitchen-sink-2`) reached 29. It combines:
  - the documented options;
  - a table of 7,537 guarded error probes recorded from the build;
  - leading literals and the recorder's lead forms;
  - else the first literal.

  So no threshold between 29 and 36 left a safe margin.
- **S1.** Round 13 called 20 the strongest count without hidden data, and row 12 called the error
  lookup "a bound no submission reaches". Both are wrong: the probe table recorded from the build
  reaches the lookup's share, and `kitchen-sink-2` reached 29 on round 13's count. Rows 12 and 19
  now say so; round 13's entry below stands as written.
- **The count (the re-check's count B).** `runcases.counts` leaves out, as before, empty outputs and
  the command line's own cases. It now also leaves out two families:
  - outputs whose every line occurs in the case's own input (`answer_in_input`, 83 kept cases):
    echoing what a program is given prints them;
  - error cases whose guard prints only the error's message (`prints_its_error_message`, 83 kept
    cases, read as `recorder.error_instances` reads them): a table of the build's messages answers
    them.

  `DISTINCT_OUTPUTS` moves to `runcases.py` (`verify.DISTINCT_OUTPUTS` names it), so that the
  recording's guard reads the same value, and is 10. The cases, the recorder, the instruction, the
  images and `task.toml` are unchanged.
- **The threshold, measured** on `experiment/local-recording-9`, through the real path on bundle
  `5be602ec5ec1` (harbor-lh `qa/basedpl/scratch-09/replay-r15/r14/`):

  | Program | Cases passed | Round 13's count | Round 14's count | Reward |
  | --- | --- | --- | --- | --- |
  | the reference | 1,673 | 1,528 | 1,421 | 1.0 |
  | v5 `-48` (DeepSeek, 9.6 h) | 847 | 773 | 722 | 0.506276 |
  | v5 `-50` (GLM, 9.6 h) | 393 | 340 | 297 | 0.234907 |
  | v5 `-49` (DeepSeek, 31 min) | 89 | 75 | 68 | 0.053198 |
  | v4 `-33` (GLM, about 9.4 h) | 57 | 36 | 30 | 0.034071 |
  | re-check 10's 290-line evaluator (legitimate, small) | 24 | 13 | 9 | 0 |
  | the recorder's dispatcher, a table of its cases with their answers | 68 | 29 | 2 | 0 |
  | re-check 10's `kitchen-sink-2` (no hidden data) | 42 | 29 | 0 | 0 |
  | re-check 10's `kitchen-sink` | 38 | 26 | 0 | 0 |
  | the last literal echoed | 23 | 17 | 0 | 0 |
  | re-check 10's literal machine | 15 | 9 | 0 | 0 |
  | replay `-46` as delivered | 4 | 0 | 0 | 0 |
  | replay `-47` as delivered | 1 | 0 | 0 | 0 |
  | each of the 20 most common answers, printed always | 3-10 | 0 or 1 | 0 or 1 | 0 |
  | the no-op | 0 | 0 | 0 | 0 |

  10 sits five times above the strongest program with no interpreter in it (2) and three times
  below the weakest honest run (30). Re-check 10 estimates that a cheap table of two-token programs
  recorded from the build adds about 4, which leaves 10 above 6. Every program that runs nothing
  scores exactly 0, with the note. Each model delivery's reward is its share: on the platform's
  recording their non-`cli` passes by kind are the platform's (one `expr` case apart, a run near
  the 2 s limit), the command line's own cases never count, so the platform's rewards (0.505678,
  0.056186, 0.237298 and v4 `-33`'s 0.037059) stand under round 14. v4 `-33` was pulled
  read-only by the reviewer; its tree here is taken from that pull without the hook's files (59
  entries, as its mark records).
- **S2.** A withheld reward says why on the `reward:` line of `test-stdout.txt` (`reward:
  0.000000 (48/48 cases); reward 0: ...`), and `metrics.json` holds the note as `withheld` (null
  where the share is given).
- **N1.** Below 10, an honest delivery loses typically about 1% of the cases. That figure comes
  from the four model deliveries' own passes, thinned at random until the tenth counted output: a
  median of 10-17 passes. The bound is 227 cases (13.6%): every case that does not count, plus
  the cases of the 9 most shared outputs that do.
- **N2.** `recording.py` stops the image's build (`dispatcher_too_close`, exit status 1 in the
  recording step) when the recorder's dispatcher reaches more than a third of 10, that is 4 or
  more. On the local recording the shipped `recording.py` exits 0 with 1,421 and 2.
- **Checks.**
  - The rule check now covers echoes (a library's text too), guard messages and the guard read as
    the recorder reads it.
  - The `grade()` check: both v5 launchers, every shared constant, an echo, a table of the guard
    messages and a table one counted output short each score 0; one output more earns its share.
  - New: `test_a_partial_interpreter_shaped_as_v4s_glm_run_keeps_its_share` (`-33`'s answer
    pattern keeps 57/200). Round 13's `grade()` gives the same cases 0, with 36 outputs of 40.
  - New: `test_the_build_stops_when_the_cases_bring_a_program_with_no_interpreter_near_a_reward`
    (three shapes pass, four stop the build).
  - The whole-run check's echoing fourth run: 48 passed, reward 0 and the note on the `reward:`
    line.
  - The four gate checks and the whole-run check fail on `764c51f`. The slow-runs check, whose
    fixture now prints outputs of its own, passes on both commits.
  - 79 task checks and 27 repository checks pass, and `check_repository.py` passes.
- **Bundle** `5be602ec5ec1` (built twice, the same hash; kept in `experiment/dist-check-38/`):
  246 files, 33,062,387 bytes. Against v5's `ab1a4f4ee269` only `tests/verify.py`,
  `tests/verifier/runcases.py` and `tests/verifier/recording.py` differ. Oddish content hash
  `358c7c75…`. Preflight passes.

### 2026-11-25 (round 13: v5's verdict; a reward needs programs run)

- **The verdict.** v5 (flat bundle `ab1a4f4ee269`) was rejected at about 01:30 UTC. Its three model
  trials were honest failures: DeepSeek 0.506 in 9.6 h and 3,740 steps, GLM 0.237 in 9.6 h, and a
  second DeepSeek run 0.056 that ended its own turn after 31 minutes and 140 steps. The reference
  scored 1.0 twice and the no-op 0 twice. The reject came only from two must-fix adversarial
  findings, both on `tests/test.sh` and one weakness:
  - replay `-46` delivered a launcher that tried the original's paths, then the private cases
    (neither was reachable), then printed the documented `--version` and `--help` strings and
    exited 2 with nothing for everything else: 6 of 1,673 cases (0.003586);
  - replay `-47` ran the original if present and otherwise exited 0: the one kept case whose answer
    is nothing with exit 0 (0.000598).

  Isolation held; the case mix let a program that runs nothing match a few answers. Evidence and
  the brief: harbor-lh `ops/swe-marathon-v2/qa/basedpl/scratch-09/` and
  `09-FIX-v6-anti-stub-BRIEF.md`.
- **The rule.** No case is removed, changed or reweighted, and the score is still the share of kept
  cases passed. It is given only where the passed cases hold at least 40 different recorded outputs
  of programs given to run (`runcases.distinct_outputs`). A case counts when it gives code to run
  (after `-e`, in a file of the case's own named first, or a program or the worker's requests on
  standard input: `runcases.runs_a_program`), is not one of the command line's own cases (kind
  `cli`, one per behaviour, which a table answers), and its recorded output is not empty; each
  output counts once. Otherwise the reward is 0, with a note (`verify.withheld`). `metrics.json`
  holds `distinct_outputs` and `distinct_outputs_needed`, and `recording.json`'s baselines
  `distinct_outputs_kept` and `no_interpreter_dispatcher_distinct_outputs`, so that every run shows
  the margin on the platform's own recording. Both functions are in `runcases.py`, so that the
  recording counts as the verifier does; the recorder's own code, the cases, the instruction, the
  images and `task.toml` are unchanged.
- **The threshold, measured** on `experiment/local-recording-9` (upstream's macOS build: the same
  1,673 kept ids as the platform's recording, with other answers for some of the command line's
  own cases):

  | Program | Cases passed | Different outputs of programs given to run |
  | --- | --- | --- |
  | the reference | 1,673 | 1,528 |
  | v5 `-48` (DeepSeek, 9.6 h) | 847 | 773 |
  | v5 `-50` (GLM, 9.6 h) | 393 | 340 |
  | v5 `-49` (DeepSeek, 31 min) | 90 | 76 |
  | the recorder's no-interpreter dispatcher, every strategy (its error lookup trained on the hidden answers) | 68 | 29 |
  | the same without the lookup, so with no hidden data | 55 | 20 |
  | the last literal echoed, alone | 19 | 17 |
  | replay `-46`'s launcher | 4 | 0 |
  | replay `-47`'s launcher | 1 | 0 |
  | each of the 20 most common answers, printed always | 3-10 | 0 or 1 |

  The brief proposed 10. That sits between the sweep's stubs (1 at most) and the weakest delivery
  (76), but below the recorder's own dispatcher, whose strategies `recorder.py` spells out in the
  verifier's shipped sources: at 10, the strategies that need no hidden data would still earn 55
  of 1,673 cases. 40 sits between the dispatcher's 29 and the weakest delivery's 76 (1.4 times the
  one, half the other), so the rule is set at 40. Counting the command line's own cases too would
  give 1,535 for the reference, 79 for `-49` and 37 for the dispatcher (8 of them from its table of
  the command line's answers); leaving them out widens the gap.
- **The sweep, through the real path** (harbor-lh `qa/basedpl/scratch-09/replay-r15/`, a copy of
  `replay-r14` with a `deliver` scenario: both hooks under dash, tar and the data filter, then
  `verify.main()`, the deliveries' `python3` being CPython 3.12 first on the runs' `PATH`, as in the
  image): the reference 1.0 (1,673/1,673; 1,528 different outputs), the no-op 0.0; replays `-46`
  and `-47` as they were delivered 0.0 (4 and 1 passed); the 20 constants 0.0 each (3-10 passed);
  the last literal echoed 0.0 (23 passed: its 19, and 4 whose answer is nothing with exit 1; 17
  different outputs); a table of every case the dispatcher answers, with the recorded answers,
  0.0 (68 passed, 29 different outputs). Each zero carries the note. The deliveries' trees and the
  stubs are in harbor-lh `qa/basedpl/scratch-09/` (the table, which holds recorded answers, only
  in the session's scratch space).
- **The v5 deliveries**, pulled read-only (`oddish pull`, without logs; their trees hold 54 entries
  and 1,240,652 bytes, 25 and 183,110, and 32 and 975,637, as each mark recorded), re-graded through
  the same path: `-48` 0.506276 (847 passed), `-49` 0.053796 (90), `-50` 0.234907 (393), the same
  with and without the rule. The platform graded them 0.505678 (846), 0.056186 (94) and 0.237298
  (397): every kind but `cli` passes the same count (one `expr` case apart in `-49` and `-50`, a
  run near the 2 s limit), and the first 200 failed ids agree but for one command-line case; the
  command-line cases differ because their answers differ between upstream's build and the hardened
  one, and they never count toward the rule. So on the platform's recording the three pass the
  same programs given to run, one at most apart, which hold far more than 40 different outputs,
  and the rule leaves their rewards exactly as they were (0.505678, 0.056186, 0.237298).
- **Checks.** New: `test_a_case_counts_toward_a_reward_only_when_it_runs_code_it_gives` (case
  shapes; an output counted once; the rule's text names no platform, run or check) and
  `test_only_a_program_that_runs_what_it_is_given_earns_a_reward` (the real `grade()` on cases
  shaped as the kept ones: the two replays' launchers, every shared constant, and an echo one
  output short that also answers the command line's own program each pass cases and score exactly
  0 with the note; the same echo with the program on standard input as well earns its share).
  Changed fixtures, each now passing 40 or more different outputs: the slow-runs check (45 fast
  programs), the whole-run check (48 cases), and the recording report (the two new counts). Both
  new checks fail on `4453fd8` (no `runs_a_program`, no `DISTINCT_OUTPUTS`); on the same cases the
  old `grade()` gives the documentation launcher 4 of 74 cases, exit 0 1 and the echo one output
  short 56, where round 13 gives each 0. 77 task checks and 27 repository checks pass, and
  `check_repository.py` passes.
- **Bundle** `e9ee043b5d71` (built twice, the same hash; kept in `experiment/dist-check-37/`):
  against `ab1a4f4ee269` only `tests/verify.py`, `tests/verifier/runcases.py` and
  `tests/verifier/recording.py` changed; the private cases, the recorder, the instruction and the
  images' files are the same bytes. Oddish content hash `1d84bf20…`. Preflight passes.

### 2026-11-24 (round 12, fifth commit: the stop counts from the session's first process, OB-1)

- The re-check of the fourth commit (harbor-lh `ops/swe-marathon-v2/qa/basedpl/08-recheck-v3.md`,
  "Follow-up (option B)") returned FAIL on one must-fix, OB-1: the stop was timed from the
  set-up run's clock, but harbor starts the agent's clock later, after a network-policy call
  that round 2's 0.3 s did not include, and stops it while a trial is paused, so a slow call or a
  pause would put the stop before the limit, which both verdicts rejected.
- **The anchor.** The process the set-up hook leaves is now Python (`/var/lib/scratch/holder.py`,
  run as `python3 -I - hold`; `ps` shows no number). It looks every 0.5 s for the session's first
  process: the first process of `dev` to begin after it whose parent is not `dev`'s (what set-up
  left, and what that forks, does not count), its start read from `/proc/<pid>/stat` against
  `/proc/uptime`, in seconds since boot. harbor starts that process inside the agent's clock.
  The stop is due 34,560 s plus 2 s after that start. Where the network's return can be watched
  (pypi.org and github.com resolved at set-up, then tried by address every half second or so),
  it also waits until one of them answers: harbor reopens the network when it ends the agent's
  phase, so a paused clock delays the stop too. With no such process it does nothing until the
  collect hook begins. The rest is as in the fourth commit: SIGSTOP only, `kill -STOP -1` as `dev`
  until none runs (15 s at most), the collect hook's mark and its end of the process (now known by
  ` -I - hold` in `ps`). Its record (`stopped`, now JSON) names the first process and its start,
  the due time, whether the network was watched and when it came back, and the stop's times, with
  fractions (the re-check's N-ob-b). The removal rule is unchanged.
- Checks: `test_the_stop_after_the_limit_counts_from_the_sessions_first_process_even_tens_of_seconds_after_set_up`
  (a stand-in `/proc` whose clock the check moves: set-up's process of `dev` and its child passed
  over, the first process 30 s after set-up, nothing at its start + 34,561.5 s, the stop at
  + 34,562.05 s), `test_the_stop_after_the_limit_does_nothing_without_a_first_process` and
  `test_the_stop_after_the_limit_waits_for_the_network_where_it_can_be_watched` (a local port that
  opens past the due time). Each fails on `d8e0436` on its own path. The reach and exit checks
  now run the new process. 75 task checks and 27 repository checks pass.
- Flat bundle `ab1a4f4ee269` (twice, the same hash; kept in `experiment/dist-check-35/` with the
  steps bundle `fbf917dc9b5c`): against `da8966415695` only `environment/provision-scratch` and
  `environment/reclaim-scratch` changed. Oddish content hash `7ae8f22f…`. Local grade with
  `experiment/replay-r14/`: the reference 1.0 (1,673/1,673, 31.4 s), the no-op 0.0. Preflight
  passes.

### 2026-11-24 (round 12, fourth commit: the stop after the limit, option B)

- The judges' 09:40 UTC amendment of harbor-lh
  `ops/swe-marathon-v2/decisions/2026-11-24-timer-round3-flat-bundles-DECISION.md` (option B for
  BasedPL v5). Harbor does not end the agent at the cap: claude-code works on until the collect
  hook freezes it, 5-14 s later, and every file it touches then is taken out, so one late-edited
  module breaks an honest capped run's interpreter and it scores 0.
- **The stop after the limit.** Each `provision-scratch` run now leaves one root process, detached
  (`setsid nohup /bin/sh provision-scratch hold`), in place of the one an earlier run left, so the
  last set-up run's remains. It sleeps in steps of 30 s at most (no number shows in `ps`); 34,560 s
  plus 2 s after the time that run recorded (`turn-started`, in whole seconds, so up to 1 s more),
  it repeats `kill -STOP -1` as `dev` until `pgrep` shows no process of `dev` running (R, S, D),
  15 s at most, which reaches forked and `setsid` processes and those that send SIGCONT. It records
  the time, the rounds and the counts in `/var/lib/scratch/stopped` (root-only), which the last
  script puts in the record as `stopped_after_limit` and `verify.py` copies into `metrics.json`
  (never scored). It ends no process and never acts before then. The collect hook first writes its
  mark (`collect-began`), at which the process stops nothing and exits, then ends it and its sleep
  before running anything as `dev`; its own freeze and kill are as before. The removal rule stays,
  its window now about 2 s. `task.toml` is unchanged.
- Checks: `test_the_stop_after_the_limit_comes_no_sooner_than_the_last_set_up_runs_time_plus_the_limit_and_2_s`
  (two set-up runs 1.5 s apart, a limit of 3 s: the second run's process replaces the first's and
  stops no sooner than 5 s after the second run, then promptly),
  `test_the_stop_after_the_limit_reaches_forked_setsid_and_continuing_processes` (shell processes:
  a forker of 20 subshells, one in its own session, two that send each other SIGCONT; all left
  stopped, none ended) and `test_the_stop_after_the_limit_ends_once_the_collect_hook_has_begun`.
  Each fails on `e0f3130`. The freeze-first check allows exactly the mark and the end of the process
  before the freeze, and the whole-hook check follows the process from both set-up runs to the
  hook. 73 task checks and 27 repository checks pass.
- Flat bundle `da8966415695` (twice, the same hash; kept in `experiment/dist-check-34/` with the
  steps bundle `08b3e5d2b951`): against `c790a042f2be`, `environment/provision-scratch`,
  `environment/reclaim-scratch` and `tests/verify.py` changed. Oddish content hash `15165600…`.
  Local grade with `experiment/replay-r13/`: the reference 1.0 (1,673/1,673, 34.9 s), the no-op
  0.0, nothing stopped, the process ended by the hook. Preflight passes.

### 2026-11-24 (round 12, third commit: every thread's memory map, R1a; R1b stays a residual)

- The re-check of the second commit (harbor-lh `ops/swe-marathon-v2/qa/basedpl/08-recheck-v3.md`,
  "Follow-up (R1)") returned CONCERN with no must-fix and no agent-caused evaluation error.
- **R1a.** The listing read only `/proc/<pid>/maps`, the first thread's, which is empty once that
  thread has exited (`pthread_exit`) while others live; their shared memory map shows at
  `task/<tid>/maps`. The re-checker's probe found nothing listed and the listing complete. The
  listing now reads every thread's `maps`, as it already read every thread's descriptor table
  (entries the threads share are kept once). A thread that cannot be read leaves its process
  unread, as a process does, and a thread that is gone is passed over.
  `test_a_thread_whose_leader_has_exited_is_read_and_an_unreadable_thread_counts` fails on
  `6f07b14` (the mapped `bpl` is delivered, `delivered 2 15`). The stand-in `/proc` now gives
  each thread its own `maps`.
- **R1b.** A mapping written after the end and dropped before the freeze leaves nothing to list.
  It stays a documented residual for the per-trial audit and the tripwires (hackability row 18);
  nothing here tries to close it.
- 70 task checks and 27 repository checks pass.
- Flat bundle `c790a042f2be` (twice, the same hash; kept in `experiment/dist-check-33/` with the
  steps bundle `b92a1e095560`): against `7867414c5e86` only `environment/reclaim-scratch` changed.
  Oddish content hash `e4ef1a57…`. Local grade: the reference 1.0 (1,673/1,673, 29.6 s), the no-op
  0.0. Preflight passes.

### 2026-11-24 (round 12, second commit: what the frozen processes hold open for writing, R1)

- The re-check of round 12 (harbor-lh `ops/swe-marathon-v2/qa/basedpl/08-recheck-v3.md`, "Follow-up
  (round 12)") returned CONCERN with no must-fix: the flat layout runs whole in Harbor 0.20.0, and
  Carve's hard-link problem does not occur here. Its one should-fix, R1: with no timer, a capped
  turn's processes run on until the hook freezes them, with the network back, and a write through
  a shared writable mapping set up before the end can leave the change time as it was (tmpfs sets
  it on a page's first write fault only), so the end-of-work rule misses it.
- **The listing.** Before the kill, the hook lists what each process with `dev`'s id among its
  ids holds open for writing (every task's descriptor table, with fdinfo's access mode; `O_PATH`
  does not count, and a descriptor whose flags show nothing does) or maps shared and writable
  (`rw-s` with an inode in `maps`), each with the path it shows, its device and its inode
  (`STATE/writers.json`). Root reads it first. Where root may not (a plain Docker host gives it no
  `CAP_SYS_PTRACE`), the same script runs again as `dev`, who can read each of its own processes
  but one that ran a set-id program or made itself undumpable (`writers-user.json`). Each run has
  20 s, 10,000 entries and 8 MiB at most, and 30 s by `timeout`.
- **The rule.** In a session that ran to its limit, every name in the tree of each file held is
  taken out before the walk, matched by the path under the tree or by device and inode (a second
  name inside, or a name outside the tree, counts too). A file that `/proc` shows as
  ` (deleted)` is gone from its name and matches by its inode alone, never by whatever stands at
  that name now (an atomic save's new file, say). Each is noted (`removed P: a process of
  the session still had it open for writing after the end of the work`, or `mapped shared and
  writable`) and counted in `late_entries` and apart as `held_for_writing`; the record keeps a
  summary (`writers`: listed or why not, entries held, the processes not read). Nothing else is
  taken out, so an honest capped turn loses only the files actually held at the freeze, and a
  session that ended in time loses nothing. The tree is refused when either listing is missing or
  incomplete, or when a process could be read neither as root nor as `dev` though all its ids are
  `dev`'s (it made itself undumpable, so nothing shows what it maps). A process that ran a set-id
  program, the original among them, is recorded and not refused: its code is that program's, and
  its writes through a descriptor move the change time.
- Checks: `test_a_capped_turn_takes_out_what_its_frozen_processes_held_open_for_writing` (a
  stand-in `/proc`: mappings matched by path, with a hard link in the tree, and by device and
  inode under a name outside it; a file open for appending; one open read-write through a name
  outside the tree; one in a thread's own table; kept: a read-only descriptor, shared read-only
  and private writable mappings, a mapping of a file gone from the name `bpl` now holds, a pipe,
  a root process's file; a set-id process recorded) and
  `test_what_was_held_counts_only_after_a_capped_turn_and_a_hidden_process_refuses_one`. Both fail
  on `7161493`, which has no listing. The hook's time check counts the two new 30 s runs (510 s
  with the others, under the 600 s limit less 60 s), and the checks find the scripts after the new
  first one. 69 task checks and 27 repository checks pass.
- Flat bundle `7867414c5e86` (twice, the same hash; kept in the Git-ignored
  `experiment/dist-check-32/`, with the steps bundle `d62e1a33fc60`, which differs from it only in
  `task.toml`, as before): against round 12's `ad93859c8f45` only `environment/reclaim-scratch`
  changed. Oddish content hash `c283dd01…` (round 12's `e17c434c…`, v4's `e8d69ae8…`). Local
  grade with round 12's replay: the reference 1.0 (1,673/1,673, 30.2 s), the no-op 0.0. Preflight
  passes.

### 2026-11-24 (round 12: no session timer; a flat bundle under the same name)

- v4 (bundle `d365dc33100d`; three model trials graded 0.383, 0.402 and 0.037) was rejected
  again: "1/3 trials was killed early by the task's own session timer: `environment/session-timer`
  line 11 sets 33,900 seconds, which is shorter than the configured agent limit of 33,960
  seconds". v2 was rejected for the same reason with 660 s between the two: the verdict rejects
  any stop the task makes before the agent's limit. The judges voted unanimously for C with D
  alongside (harbor-lh `ops/swe-marathon-v2/decisions/2026-11-24-timer-round3-flat-bundles-DECISION.md`):
  no task-side timer, the limit back at 34,560 s with no comment, and the upload a flat
  single-step bundle under the task's own name, as SymPy's is (the only setup whose capped runs
  were graded, 3 of 3); a 9.6 h cap probe in both layouts runs alongside. This round is the
  decision's items 1-4, in one commit.
- **The timer is gone**: `environment/session-timer`, its `[[agent.setup_complete]]` entry, the
  Dockerfile's lines for it, the collect hook's mark (`/var/lib/scratch/reclaiming`), its stop of
  the timer and its copy of the timer's log, the record's `timer_log` and `ended_by_timer` (and so
  `metrics.json`'s), the four checks of the timer and the timer's parts of the others. Both agent
  `timeout_sec` are 34,560 again, and `task.toml` holds no comment. The collect hook still freezes
  `dev`'s processes first and kills them before any work of its own.
- **What bounds a session that runs to its limit.** Harbor stops waiting at the limit but never
  ends the agent's exec, so its processes run on until the collect hook freezes them, with the
  network open again by then (harbor-lh `ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md`). The end
  of the work is the session's start, `turn-started` (written by `provision-scratch` at
  `setup_complete`, just before the run), plus 34,560 s, and 1 s for `date +%s` rounding down.
  Nothing is killed to enforce it: a killed run is classified by its transcript and its score
  discarded. When the last script starts after that end, every file and link whose change time, as
  listed before the hook touched anything, is later than the end is taken out before the walk,
  whatever stands at its path by then (a copy the link fixer made of such a link included). None of
  it counts; the mark notes `removed P: changed after the end of the work, 34560 s after the
  session began` for each, and the record holds `work_end` and `late_entries`, which `verify.py`
  copies into `metrics.json` and never scores. The session's user cannot set a change time back
  (any write, `chmod` or `utime` sets it to the present). Without a complete listing from before
  the hook, such a session's tree is refused; an empty one is delivered empty.
- **The flat bundle.** `scripts/package_step.py --flat --keep-name` writes the bundle without the
  steps wrapper under the task's own name (`--flat` alone still appends `-single`) and refuses a
  step whose agent or verifier limit differs from the top level's. The repository keeps its steps
  layout. Flat `ad93859c8f45` against steps `8ea1e9bf08ec` (each built twice, the same hash): the
  same 246 files with the same modes; the step's 21 (the instruction, the 15 of `tests/` and the 5
  of `solution/`) move to the top byte for byte; the 224 of `environment/` are the same; and
  `task.toml` loses `multi_step_reward_strategy = "final"` and the `[[steps]]` table (agent
  34,560 s and verifier 4,500 s, the top level's own) and keeps its name. In Harbor 0.20.0 (the
  version Oddish's CLI carries) a single-step trial reads `instruction.md` as a step reads its own
  (the canary stripped, nothing added), runs the same task-level set-up and collect hooks (a step
  adds none here), takes the top-level artifacts and agent network policy (a step falls back to
  them), builds the verifier image from `tests/` where a step's comes from the step's `tests/`, and
  takes the one verifier's reward, which "final" takes for a single step.
- Checks: `test_nothing_ends_the_session_before_the_agents_limit` (no timer file, entry or comment,
  every agent limit 34,560 s, no timer word in any shipped file);
  `test_a_capped_turn_counts_nothing_written_after_its_end` (work written, the end passes, then a
  process of the session fetches a file, swaps the program, links to the fetched file and keeps
  appending to a log until it is killed: the four late entries are taken out and noted,
  `late_entries` is 4 and the in-time files arrive whole);
  `test_a_capped_turn_that_delivered_nothing_or_lost_its_listing`; the freeze-first check without
  the mark; and `test_the_flat_bundle_is_the_same_task_under_the_same_name`. The three on the end of
  the work fail on `ff793d5` (the late entries are delivered: `delivered 8 152`). The checks'
  sessions now begin 100 s before the hook (the fixed `1700000000` of before would read as a
  session long past its limit). 67 task checks and 27 repository checks pass.
- Local grade of the flat bundle with round 12's replay (`experiment/replay-r12/`: either layout,
  no timer): the reference 1.0 (1,673/1,673, 30.4 s, no notes), the planted names 1.0, the no-op
  0.0 (`delivered 0 0`), each with `work_end` at `turn_started` + 34,561 and no late entry.
  Preflight passes. Oddish content hash `e17c434c…`, against v4's `e8d69ae8…` (the steps bundle:
  `ad5f525b…`). Against v4's bundle, `environment/session-timer` is removed and the Dockerfile,
  `reclaim-scratch`, `task.toml` and `verify.py` change; the cases and the build are the same, so
  the recording's answers are expected to be the same.

### 2026-11-21 (round 11, second commit: the `task.toml` comment)

- v3's pre-trial audit (bundle `a9dad36c7bf0`) returned one must-fix: "task.toml holds an author
  comment that discloses the evaluation platform and its verifier", round 10's note above each
  agent `timeout_sec`; the reference scored 1.0 twice and the no-op 0 twice. Both notes now read,
  word for word: "Sessions end at 33,900 s: a timer started at set-up closes the session user's
  processes then (all are gone by about 33,930 s). This value is a backstop 60 s later." A sweep
  of every shipped file found no other author commentary about the platform, trials, the verifier
  image or grading (the verifier's own sources name their job). The word check now covers
  `task.toml`'s comments (the audit scan's words, plus platform, result, image, evaluat, grad and
  review) and fails on the old note. 67 task checks and 27 repository checks pass. Bundle
  `f93f6c391545`, built twice with the same hash, differs from `a9dad36c7bf0` in `task.toml` only;
  preflight passes.
- Oddish did not make it a version: its content hash (`oddish/task_content_hash.py`) reads
  `task.toml` by its runtime fields alone, so `f93f6c391545` hashed as `a9dad36c7bf0`
  (`e6d06775…`). `environment/session-timer` now opens with the same note in a line of its own
  ("Ends the session user's processes at 33,900 s after set-up; the agent limit in task.toml
  (33,960 s) is a backstop."). Bundle `d365dc33100d` (twice, the same hash) differs from
  `a9dad36c7bf0` in `task.toml` and `environment/session-timer`, hashes as `e8d69ae8…`, and passes
  preflight; 67 task checks and 27 repository checks pass.

### 2026-11-20 (round 11: re-check 08 of v3)

- Re-check 08 of round 10 (harbor-lh `ops/swe-marathon-v2/qa/basedpl/08-recheck-v3.md`) found the
  timer, the sentence and the two reproduced paths as claimed, and two must-fixes of the round's own
  class, four should-fixes and four notes. This round answers M1, M2 and S1-S4 in one commit
  (`9ee0898`); the instruction, `task.toml` and the verifier are byte-identical to round 10's.
- **M1: one link held the last script past the hook's 600 s.** It checked its time between links,
  and `os.path.realpath` under Python 3.12 follows every link a target meets, past the system's
  limit of 40, so a link whose resolution reaches every other link stayed inside one call
  (re-check 08: about 800 s at the stated limits, then "nothing arrived" when that link also
  climbs past `/` and packs first). On the re-check's tree (16,000 leaves at this Mac's 1,023-byte
  targets), started 418 s after the hook, round 10's last script took 5.85 s; this round's, 1.59 s.
  - The last script no longer resolves a link through the filesystem: it reads each target by
    name against the walk's own listing, one lookup per part (Carve's `destination()`, rounds
    9-10). A link that leads, through directories of the tree, to a file or a directory of it is
    kept as the direct relative path; one that leaves the tree, or leads through another link or
    to nothing, is removed with a note. The fixer, which runs first, still makes links through
    links direct.
  - An alarm (`SIGALRM`) ends the walk and the links at 420 s after the hook's start, inside any
    call, and refuses the tree.
  - The fixer asks the system first (`os.stat`, at most 40 links in a row, 32 on this Mac) and
    removes a link the system does not resolve before anything follows it, and an entry it cannot
    fix no longer ends it.
- **M2: the caps counted notes, not bytes.** With long names the fixer's lines held the name twice
  and the target (2.5 KB here, about 6 KB on Linux), so its output, the refused record and the
  mark reached 87 MB here and 210-420 MB on Linux, against the 64 MiB set aside. Every name and
  note is now cut to a few hundred bytes (start and end). The fixer prints 2 MiB at most, then a
  count. Each script's own notes take 64 KiB, and the mark's notes 32 KiB, as written. A refused
  record counts the entries, the fixer's changes and the notes, and lists only the first notes
  (64 KiB). The delivered room check counts the mark too. At this Mac's limits a refusal now
  writes about 2 MiB in all.
- **S1: a task in D.** `dev` can hold one through `vfork` (the round-10 entry said no way was
  found), and the freeze ran its 100 passes then. The freeze now asks for R and S only (a task in D
  runs nothing of its own, and the kill ends it), and the freeze and the kill each stop after
  `LOOP_SECONDS` (15 s), with a note in the mark. The set-aside of the hook's own names stays
  where it was: every stage before it now has a limit (15 + 15 + 300 + 30 s).
- **S2: a process that keeps changing its pid** outlived the timer's `pgrep`/`pkill` rounds, and
  `-u dev` misses set-user-id programs. Each round now also signals as `dev` with `kill -1`, one
  system call that reaches every process of it, the SIGKILL rounds always run (twenty, 10 s), and
  `pkill -KILL -U dev` is added. The as-`dev` call is `MAINT_AS_USER`, which the checks stand in.
- **S3:** the pre-scan's two files are written in ASCII, so a name that is not UTF-8 keeps the
  listing before the hook. **S4:** a figure the filesystem does not report (no inode counts, no
  sizes) is left out of both scripts' room tests, and the record keeps the disk's free figures
  (`disk_free_bytes`, `disk_free_inodes`; in `.manifest.json`, not `metrics.json`).
- **Not changed:** N1, the refusal renames `/app/rebuild`, a directory of the image layer, which
  overlayfs without `redirect_dir` refuses (gVisor's overlay copies up and renames; only a local
  Docker run would meet it); N2, the stated limits (links count as entries, the 100 s pack is
  unstated), unchanged since v2; N4, the `task.toml` comment, kept as the re-check advised.
- **The agent image, swept for records of the original** (a sibling task's re-check found a
  world-readable requirements file naming its original's project). Nothing found: the final
  stage takes only the execute-only binary and the smoke test (deleted in the same step) from the
  build stage, never `/original` or the `build.txt` that `mark.py` writes beside the binary
  there; its own files are the three root-only scripts and `/app/docs`, which packaging takes from
  upstream's site pages alone (213 pages, `llms.txt`, `LICENSE`; no requirements, lock, build,
  configuration or source file). Upstream's pages name its repository, `pip install basedpl`,
  rustymath, Cranelift and fancy-regex, as published; they ship on purpose, as every audit so far
  has passed. A check guards it.
- Checks: seven new ones, each failing on 9433aa9 for its own path
  (`test_no_one_link_holds_the_last_script_past_its_time`,
  `test_the_link_fixer_lets_the_system_resolve_a_link_before_following_it`,
  `test_what_the_hook_writes_stays_far_inside_the_room_set_aside`,
  `test_the_freeze_and_the_kill_end_in_time_and_a_task_in_d_holds_neither`,
  `test_the_session_timer_signals_every_process_of_the_user_at_once_in_every_round`,
  `test_a_name_that_is_not_utf8_keeps_the_listing_before_the_hook`,
  `test_a_filesystem_that_counts_no_inodes_is_judged_by_its_bytes`), and
  `test_the_agent_image_holds_no_record_of_the_originals_source_or_build`. Round 10's checks
  follow the new notes, the link rule and the byte caps. 67 task checks and the 27 repository
  checks pass. Bundle `a9dad36c7bf0` (built twice with the same hash; against round 10's
  `ec8d6ecf327d` only the two scripts differ): the replay (`experiment/replay-r11/`) gives the
  reference 1.0 (1,673/1,673), planted 1.0 and the no-op 0.0, and preflight passes; see
  [Validation](#validation).

### 2026-11-20 (round 10: the v2 verdict's timer, the completion sentence, what a tree can do to the copy)

- **The verdict.** v2 under the new name (round 9's `af0c9f7b084e`) was rejected on one must-fix:
  `environment/session-timer` stopped the agent at 33,900 s, 660 s before the 34,560 s limit in
  `task.toml`, and one of the three model trials was classed a premature kill. The source audit
  was empty, the other two trials were good failures, and there was no evaluation awareness and no
  leak; the baselines were right. This round answers it in three commits (the timer `8e58f8b`, the
  sentence `e68ca3e`, the hook `39e47a5`) and keeps everything else of v2.
- **The timer** (the judges' option B, unanimous in their second vote; harbor-lh
  `ops/swe-marathon-v2/decisions/2026-11-20-precap-timer-vs-deadline-DECISION.md`). The stop point
  stays at 33,900 s, where every trial the timer ended was graded, and the stated limit moves to it:
  both agent `timeout_sec` entries (the top level's and the step's) are 33,960 s, a backstop 60 s
  later. Each has a comment for the platform's reviewers: the session ends at 33,900 s, when a root
  timer ends the session user's processes; the limit is a backstop 60 s later; and why (trials that
  reached the platform's own cap with this kind of verifier image got no verifier result). The
  timer sends SIGTERM in six rounds 5 s apart (twelve before), then SIGKILL every 0.5 s for 10 s at
  most. At full scale a stand-in that ignores SIGTERM was ended 30.22 s after the fire, so nothing of
  `dev` is left at about 33,930 s. Option A (fire at 34,440 s, limit kept) won the first vote and is
  not used.
- **The completion sentence.** "cannot be told apart from the sandboxed build by what it prints ..."
  is the phrase class a sibling task's verdict counted as an evaluation cue. It is now the decision's
  draft, unchanged (harbor-lh
  `ops/swe-marathon-v2/decisions/2026-11-20-completion-sentence-evaluation-awareness.md`): "The work
  is complete when, for every script, input and command line we run, your program writes to standard
  output exactly what the sandboxed build writes and exits with the same status." The modularity
  line says "executing it" for "evaluation". A sweep of the instruction, the agent image's
  Dockerfile, its three installed scripts and `mark.py` for "told apart", "indistinguishable",
  "graded", "evaluat", "test corpus", "hidden test", "held out", "benchmark", "rubric" and "judged"
  now finds nothing. The documentation's hits are upstream's own words for the language (evaluation
  order, APL's grade, "held outside the group", Python benchmarks), and it ships as it is.
- **What a tree can do to the copy**, swept with Carve's QA 22 and 23 as the catalogue. Probes ran on
  6a93903's hook under Python 3.12, the image's version, with tar and tarfile's `data` filter doing
  the copy:
  - *Reachable, reproduced:* a link that climbs past `/` and back into the tree is inside in the
    sandbox and outside where the copy extracts it. The link fixer makes every link it reaches
    direct, but a chain of 1,200 links with its head at the top ends the fixer at once
    (`RecursionError` in 3.12's recursive `realpath`), and the last script kept the climbing link:
    the extract stopped, and the verifier raised "The copy arrived incomplete: 4 of 1,205 entries
    and 18 of 22 bytes", an evaluation error. The last script now keeps a link that stays inside
    only as the direct relative path to what it reaches, as the fixer leaves it, with the note
    `path -> direct (was target)`. The same tree now arrives whole.
  - *Reachable, reproduced:* the last script had no time limit, and one `realpath` per link costs
    N²/2 links over a chain: 2,000 links 5.95 s, 4,000 24.4 s, 8,000 101.5 s on this Mac. Ten chains
    of 9,999 links fit the 100,000-entry limit and need about 1,600 s, so the hook's 600 s ran out
    before the mark, with the links the copy refuses still in the tree ("nothing arrived" when one
    of them comes first). The last script now refuses a tree it has not measured within 420 s of
    the hook's start (`MEASURE_UNTIL`) and packs only by 510 s (`PACK_UNTIL`); the earlier stages'
    own limits (300, 30 and 120 s) leave it that time, or it refuses at once. A refused tree scores
    0, with the reason as its note.
  - *Reachable, read from the code (no small filesystem here):* on a disk the session filled, the
    fixer's copies of root-owned targets, and its notes (about 98 bytes per pipe: 20,000 pipes
    printed 1.96 MB), could use up the 64 MiB and 64 inodes set aside at setup, and the last script
    then could not write its record or make the empty directory a refusal needs. The fixer now
    copies only with twice the copy's bytes and 64 MiB, and its entries and 64 inodes, to spare, and
    prints 10,000 changes and then how many more; the first and the last script name 1,000 of their
    own and count the rest. The pack had been proved for the tree alone, while the copy packs it
    beside the record: a tree the disk cannot pack beside twice its record and 16 MiB is now refused
    when the machine had room at the start (when it never had, the copy is left to fail, the
    machine's fault). A refused tree's record counts its entries (`entries_not_listed`) and lists
    none, so it fits in the room set aside.
  - *Not reachable, unchanged:* `/app/rebuild` replaced, missing or not a directory (`/app` is
    root's and sticky, `/app/rebuild` root's; the hook's exit for that case stays); the set-aside
    step's `|| exit 0` (`mktemp` in root's `/app` and a rename within one filesystem, right after the
    room is given back); a forged mark (set aside before the fixer, and every later stage now has a
    limit); an oversized mark (the verifier reads 1 MiB of it and decides on the first line); paths
    past `PATH_MAX` (refused at 1,000 bytes); zombies stretching the kill loops (their tests count
    states R, S, D and T only, and Carve's v3 trials showed one kill pass and none left, so the
    platform reaps).
  - *Left:* the freeze loop counts a process held in D state through all its 100 passes, each a scan
    of `/proc`. No way for `dev` to hold one there was found, and the stages after it have limits
    of their own. Carve's fail-closed staging (the tree moved aside behind a refusing mark before any
    slow step) would close what is left; it is a redesign of the hook and is not taken here.
  - The verifier is byte-identical to v2's (its sources, the shipped cases and the marker), so the
    verifier image and its recording are unchanged.
- Checks: five new ones, each failing on 6a93903 for its own path
  (`test_a_link_that_climbs_past_the_root_is_kept_only_as_a_direct_one`,
  `test_a_tree_the_last_script_cannot_finish_in_time_is_refused_not_left_to_the_copy`,
  `test_the_link_fixer_copies_only_with_room_to_spare`,
  `test_the_hook_names_a_bounded_number_of_changes_and_counts_the_rest`,
  `test_a_tree_the_disk_cannot_pack_beside_the_record_is_refused_and_its_record_lists_nothing`);
  `test_the_instruction_states_the_requirement_and_never_a_comparison_of_the_work`, which fails on
  6a93903's instruction; and the timer check, which now measures the SIGKILL six rounds after the
  fire (rounds of 0.5 s: 6a93903's timer took 6.42 s) and reads both limits from `task.toml`. The
  existing hook checks pass a current start time to the last script. 59 task checks and the 27
  repository checks pass; see [Validation](#validation).

### 2026-11-20 (round 9, second commit: three comments of the verifier)

- Round 9 left the verifier's sources byte-identical, with three comments that named how the task
  was made or the platform: `verify.py` cited `scripts/upstream_builds.py` and gVisor's status
  file, and `recorder.py` cited `make_cases.LEADS`. Every audit so far had passed them, but the
  platform's audit has flagged shipped comments that name the platform or the build process
  before, and gVisor is the platform's sandbox, so all three are reworded now: upstream's
  published builds without the script, kernels whose status file may not list `NoNewPrivs`
  without naming one, and the lead forms as the values some cases print before an error.
- Comments only. For both files, Python's tokenize stream with the COMMENT and NL tokens left out
  is identical before and after: 6,817 tokens in `verify.py`, 5,502 in `recorder.py`. The line
  count is unchanged too. The recorder records the same answers; the verifier image is recorded
  again at its next build anyway, since both images' build contexts changed in round 9.
- Check: `test_the_verifier_names_neither_the_platform_nor_how_the_task_was_made` scans the seven
  files of the verifier's sources for the platform's names, the scripts and records the task was
  made with, authors and review words; it fails on round 9's first commit. 53 task checks and the
  27 repository checks pass. Bundle `af0c9f7b084e` differs from `bf77bf7f91d0` in those two files
  only.

### 2026-11-20 (round 9: the pre-trial audit's must-fix, an author-only probe in the solution)

- The platform's pre-trial audit of v1 under the new name (round 8's bundle `43b39e11805c`)
  returned one must-fix and nothing else: `steps/01-rebuild-interpreter/solution/probe.c:1`, "The
  delivered package keeps an author-only probe that records this sandbox's behaviour for the
  task's authors." The reference scored 1.0 twice and the no-op 0.0 twice. This round answers it in
  one commit, with a sweep of every shipped file for the same kind of text, and of every data file
  for records of how the task was made (asked for after the same audit flagged a provenance record
  in the back-office task's hidden data). `task.toml`, the instruction, the three installed
  scripts, the verifier's sources and `upstream_builds.json`, the binary and the documentation are
  byte-identical to round 8's.
- **The solution only installs.** `solve.sh` installs the original with the zero marker, and
  upstream's licence, in `/app/rebuild` exactly as before, and does nothing else. With the probe
  (`probe.c`, built with gcc and run as `dev`, its output copied to `/logs/agent/probe.txt`) go
  three more records of the run that were written for us, not for the solution: the read checks as
  `dev` (`/logs/agent/reads.txt`), the smoke test of the installed copy (`/logs/agent/smoke.txt`,
  whose comment spoke of "this sandbox"), and the copy of the build's facts
  (`/logs/agent/build.txt`; `mark.py` still prints them). The solution no longer takes `smoke.sh`;
  both images still run it at every build.
  - `probe.c` is deleted, not moved: nothing in the task that never ships would run it. Its source
    stays in the history (`85e93d1`). What it measured (a set-group-id exec of `/opt/bpl/bpl` as
    `dev`, plain and traced: the ids, `AT_SECURE`, whether an `LD_PRELOAD` constructor runs,
    whether `PTRACE_PEEKDATA` and `/proc/<pid>/mem` reads succeed, and the kernel) went into
    `/logs/agent/probe.txt` of every reference trial so far, under both names, since `solve.sh`
    ran it from the task's first commit. Those records are not read yet (hackability row 1).
- **What the sweep found in the files of ours.** Two comments of `smoke.sh` named the reference
  solution among the places it runs, and the same sentence cited `apply.sh`; `mark.py`'s
  docstring cited `scripts/build_original.py`. Neither script ships. The comments are reworded and
  the citations dropped; both tools' code is unchanged. No other file of ours outside the verifier
  has a hit for the audit's words, `author`, the run's logs, a sandbox of its own or a file that
  does not ship. `authoritative` in `reclaim-scratch`, `authors` as `task.toml`'s key and the
  instruction's "sandboxed build" (the requester's own) are not hits. The verifier's sources stay
  byte-identical, and three of their comments say how the task was made: `verify.py` names
  `scripts/upstream_builds.py` and gVisor's status file, and `recorder.py` names
  `make_cases.LEADS`. Every audit so far has passed them, and changing `recorder.py` would change
  what records the answers.
- **What the sweep found in the data.** No `.gz` or other archive ships besides the three
  identical `bpl.xz`. They hold the hardened build (`60d2aed1…`), with no local path, user or
  project name; the only paths are the public Rust toolchain's own `/rustc/<commit>/library/…`
  ones, and the zero marker is there once. The documentation and `LICENSE` are upstream's, with
  nothing of ours added. `upstream_builds.json` holds hashes, sizes and which of upstream's files
  each one is, with no header. The two `marker` files (identical) are the images' build marker,
  which the verifier needs. Two files carried records of how the task was made, and now ship only
  what is read there:
  - The private cases. Each case carried the generator's notes: `source` (upstream's reference
    file and line, or the program template's name), `suite` and `family`, and in its `record`
    entry, `want` and `scaffold_lines`. The verifier image reads none of them. `package_step.py`
    now ships each case with `id`, `kind`, `form`, `argv`, `files` and `stdin`, and of `record` the
    recorder's `variants` and `unset`, written as before. The notes stay in the private file
    (Git-ignored, never committed), which the leak check still reads whole.
  - `build.txt`, which recorded upstream's commit, the toolchain, the target and the size. It now
    ships with the `link` and `sha256` lines `mark.py` reads; the rest stays in
    `experiment/build/build.txt`. `mark.py` no longer writes empty commit, toolchain and target
    lines beside the binary it installs, so `recording.build` in `metrics.json` now holds the link
    mode and the two hashes.
- **Proof that the cases did not change.** The shipped file holds the same 1,777 cases in the same
  order, and every key kept is byte-identical. Removed: `source` from 1,777 cases, `suite` from
  1,383, `family` from 260, `want` from 1,324 records and `scaffold_lines` from 248. A local
  recording of the shipped file with upstream's macOS release binary (`experiment/local-recording-9`)
  keeps the same 1,673 cases with byte-identical answers. It has the same `kept_ids_sha256`
  (`bb030348…`, which is also the platform's) and the same `expected_sha256` as
  `local-recording-8`, and its kept cases equal round 8's apart from the three notes.
- **How the agent's user is confirmed now** (hackability row 3): from `delivery_record` in each
  model trial's `metrics.json`. `bpl.owner` should be `dev`'s uid 10001, not 0, and
  `user_processes` should list the agent's own processes under uid 10001 when the session ended.
  The old name's three graded v2 model trials can answer it already.
- Checks: `test_the_reference_solution_installs_the_original_and_its_licence_and_nothing_else`
  covers the solution's commands, what packaging gives it, and that no shipped file of ours outside
  the verifier names an author, the run's logs, a sandbox of its own or a file that does not ship.
  `test_the_bundle_holds_only_what_is_read_of_the_private_cases_and_the_build_facts` covers what the
  shipped cases and `build.txt` keep, and that every key the verifier's sources read of a case and
  of its plan is one they keep. The mark check also asserts the three lines `mark.py` writes, and
  the word-scan check counts nine files. Each new assertion fails on round 8's files (the solution,
  the packaging, `mark.py`, the tools' comments); the second check also fails on a copy of the
  verifier that reads `source`. 52 task checks and the 27 repository checks pass; see
  [Validation](#validation).

### 2026-11-19 (round 8: the freeze before the timer's end, from the re-check 07f)

- The re-check of round 7 (harbor-lh `ops/swe-marathon-v2/qa/basedpl/07f-round7-recheck.md`)
  found F1 closed and no must-fix, and three should-fixes: G1 (design), G2 and G3 (minor). This
  round answers them in one commit. The verifier's sources and paths are byte-identical to round
  7's (`verify.py`, `runcases.py`, `recorder.py`, `recording.py`, `upstream_builds.json`,
  `test.sh`, its `Dockerfile`); of what ships, `environment/reclaim-scratch` changed, and three
  lines of the shared smoke test and the solution were reworded (G3).
- **G1, the timer's end came before the freeze.** Round 7 ended the session timer first and froze
  `dev`'s processes after it, while those processes already had public connectivity again: six
  more process starts before the first SIGSTOP, one of them a scan of every `/proc` entry (19 ms
  more on the re-check's Mac). The hook now writes the mark, freezes `dev`'s processes, and only
  then ends the timer, before the listing, the kill and its own work as `dev` (the link fixer);
  the second stop at its end stays. The first SIGSTOP again comes after the seven process starts
  it had before round 7 (`date`, `mkdir`, `chmod`, `seq`, `pgrep`, `setpriv`, which runs `kill`).
  F1 stays closed: the mark alone keeps the timer from ending anything (it looks before it fires
  and before every round), and a round that had already looked can reach only `dev`'s processes,
  which the hook freezes and ends anyway; the fixer starts seconds later.
  - Not taken: moving the freeze above `date`, `mkdir` and `chmod` too (three more starts, a few
    milliseconds against a window of at least 0.6 s). The mark keeps the hook's start time, and
    the state directory is made there if setup did not make it.
  - Checks: `test_reclaim_scratch_writes_the_mark_then_freezes_the_user_then_ends_the_timer` runs
    the hook's lines before its listing as shipped, with stand-ins for the freeze's `pgrep` and
    `setpriv`, against a real waiting sleeper: the freeze is sent with the mark written and the
    sleeper still running, and the sleeper and its sleep are ended after it; the text keeps that
    order, with nothing run between the mark and the freeze. The delivery check's order list and
    the F1 check follow the new order. In the F1 check's case of a timer in its rounds, the timer
    can now see the mark and exit with its own `stopped:` line before the hook's stop finds it;
    either line is accepted, and the fixer still fixes all 20,000 links. A copy with round 7's
    order fails the new check (its freeze found "timer ended") and the delivery check's order
    list; the F1 check passes on it, as it should.
- **G2, `fixer_status` is not in `metrics.json`.** `verify.py` copies a fixed list of the
  record's keys and is not changed for this. Written down under
  [Validation gaps](#validation-gaps), with what a reader of the first trials sees instead.
- **G3, the words the audit's scan flags.** In `reclaim-scratch`, the link fixer's byte allowance
  `BUDGET` is now `COPY_BYTES` (one assignment, three reads) and the measuring script's
  `trial_pack()` is now `pack_once()` (its definition and its one call). Nothing else in the task
  (hooks, checks, verifier, this file, scripts) or in the local grader and replay named either,
  and neither new name was in use anywhere. A scan of every shipped file for
  `grade|score|verif|harness|oddish|modal|harbor|\bcap\b|budget|attempt|audit|QA|round [0-9]|trial`
  then found three more lines of ours, all outside the agent's view, now reworded: the smoke
  test's last line ("bpl hardening confirmed", in both images' build stages and the solution),
  and comments in `probe.c` ("the sandbox it runs in") and `solve.sh` ("the run's logs"). What
  remains is the verifier's own sources and paths, `task.toml`'s `[verifier]` tables, upstream's
  manual (APL's grade, for one) and words in the hidden cases' programs (`scores`, `grades.bpl`;
  `harbor` and `budget` from the rewrite word list and the programs' place names), all in the
  verifier image or the documentation. A new check,
  `test_no_shipped_file_of_ours_outside_the_verifier_uses_a_word_the_audit_scan_flags`, scans the
  ten files of ours that ship outside the verifier.
- 50 task checks and the 27 repository checks pass; see [Validation](#validation).

### 2026-11-19 (round 7: the collect hook ends the session timer first, from the re-check 07e)

- The re-check of round 6 (harbor-lh `ops/swe-marathon-v2/qa/basedpl/07e-audit-scrub-recheck.md`)
  found no rename defect, one reward-affecting should-fix older than the scrub (F1) and six
  minors. This round answers them in one commit. The verifier image's sources are byte-identical
  to round 6's (`verify.py`, `runcases.py`, `recorder.py`, `recording.py`); of what ships, only
  `environment/reclaim-scratch` and `environment/session-timer` changed.
- **F1, the timer could end the hook's own link fixer.** Once fired, the timer sends SIGTERM to
  every process of `dev` every 5 s for up to a minute, and the fixer runs as `dev`. A hook that
  started inside that minute, with some process of `dev` having survived SIGTERM, could lose its
  fixer to a round: the links not yet fixed were then removed by the root step and the delivery
  was marked and graded, honest work at 0 with notes that read like the agent's fault.
  - `reclaim-scratch` now writes a root-only mark (`/var/lib/scratch/reclaiming`) before anything
    else and then ends the sleeper its pid file names, before any process of its own runs as
    `dev`. It sends SIGSTOP (the sleeper starts nothing further), SIGKILL to its children (its
    sleep, or a round in flight) and SIGKILL to it, only where that pid's command line is
    `session-timer run`. It adds a `stopped pid N` line to the timer's log, removes the pid file,
    and does the same once more at its end (the last step is no longer an `exec`).
  - `session-timer` looks for the mark before it fires and before every SIGTERM and SIGKILL
    round, and exits with a `stopped:` line, so a sleeper the hook could not find (no pid file)
    ends nothing either. The mark is never removed: this task has one session per container. A
    layout that arms the timer again after a collection (several steps in one container) would
    have to clear the mark when it arms.
  - This is Carve's and Goose's pattern with one difference: their hooks send SIGTERM, wait and
    then SIGKILL, which leaves the sleeper's `sleep` running and a round in flight untouched.
    SIGSTOP first, then the children, needs no wait.
  - The fixer's exit status now reaches the last script. A status other than 0 (124: its two
    minutes ran out; 128 plus a signal's number) is a note in the mark and `fixer_status` in the
    record (`.manifest.json` only; `metrics.json` shows the note, not the key: see Validation
    gaps); before, a fixer that was cut short left no trace.
- **F4, "armed" was printed before anything was known.** A start with no running sleeper now arms
  one whatever the pid file holds (empty, a pid that is gone, the pid of some other live
  process; the no-clobber reservation that could leave it unarmed is gone), waits up to 2 s, and
  prints `armed for 33900 s (pid N)` only for a sleeper it sees running. With a pid file that
  cannot be written the sleeper still runs and the line says so. With no sleeper it prints `not
  armed` on standard error. Every path still exits 0: a failing setup hook ends the trial, and
  the first baselines show the armed line in `timer_log` (see Validation gaps).
- **F5, the two reserved names.** A file the session left as `.manifest` or `.manifest.json` was
  moved out of `/app/rebuild` without a word. The mark now says so, one line per name, and the
  verifier relays it with every other note. The instruction stays silent about the names.
- **F6, this file after the rename.** The decision file's name (`egress-window`), `.manifest`
  and `.manifest.json` in the round-3 and round-1 entries, and `timer_log` in hackability row 18
  are corrected. Left as it is: `verify.py` prefixes one fallback note with "collect hook:" where
  the hook's own lines get "maintenance step:" (cosmetic, and the verifier stays untouched).
- **F2, F3, F7, what the checks could not prove.**
  - F2: the timer check's stand-ins were copies of `/bin/sleep`, which macOS kills at exec, so the
    check passed whatever the timer did. They are Python processes now: each must be alive before
    the timer is armed and end by exactly SIGTERM, or SIGKILL for the one that ignores SIGTERM.
  - F3: a new check runs `verify.main()` whole, `sandbox()` and `probe()` included, with stand-ins
    only for what needs root or Linux (after the reviewer's replay): integer ids must reach every
    `chown`, every case goes through the prefix `sandbox()` returned, and a set-id probe that
    answers 0 is an evaluation error with no reward file. Another runs every shell line of both
    hooks as shipped, paths rewritten, with stand-ins first on `PATH` for `setpriv`, `pgrep`,
    `pkill`, `ps -eo`, `fallocate`, GNU `stat` and `timeout`, against the real timer: room and
    inodes set aside and given back, links fixed through the drop's stand-in, the reserved names
    moved aside and noted, the mark, the record, and the waiting sleeper ended.
  - F7: the author's local grader wrote the old record keys; it writes the new ones. A copy of
    the reviewer's replay (the hooks' whole shell under dash, the timer, the copy, `main()`),
    adapted to the hook's new lines, was run on this bundle as well.
  - The rest is listed under Validation gaps.
- Checks: `test_the_session_timer_arms_once_fires_and_ends_the_users_processes` (no hook running:
  SIGTERM to a tree, to a process in its own session and to one started after the fire, SIGKILL
  to a stubborn one), `test_the_session_timer_says_armed_only_for_a_sleeper_it_sees`,
  `test_reclaim_scratch_ends_the_session_timer_before_its_own_work_as_the_user` (a waiting
  sleeper and its sleep are ended; with a timer in its rounds, the hook's own link fixer, which
  the timer's selection matches, is ended by a round when the hook's first lines have not run
  (the control, 07e's reproduction) and fixes all 20,000 links when they have; the mark alone
  stops the rounds; a sleeper that wakes up to the mark never fires),
  `test_both_hooks_run_whole_with_the_root_and_linux_tools_stood_in`,
  `test_the_whole_evaluation_runs_with_only_root_and_linux_stood_in`, and the delivery check's
  new notes and order. Each of the five new checks was run against copies with the behaviour it
  proves taken out (nine changes in all), and failed. 48 task checks and the 27 repository checks
  pass.

### 2026-11-19 (round 6: the pre-trial audit's info-leakage findings)

- The Oddish pre-trial audit is a hard gate before any model trial. It returned two info-leakage
  must-fixes and sibling findings on the installed helper names.
- The verifier's recorder no longer names how the cases were generated or QA-checked; its
  docstring describes only what it computes (the history stays here in the dev log).
- The helper scripts and their state are renamed to ordinary system-housekeeping names, so a
  solver that lists the container cannot read "delivery", "collect", a cap or grading from them:
  `provision-scratch` (setup), `reclaim-scratch` (the collect hook), `session-timer` (the
  pre-cap timer), under `/var/lib/scratch`, `/var/log/session-timer.log` and
  `/run/session-timer.pid`; the manifest files are `.manifest` and `.manifest.json`. The
  reserved directory has to live inside the container under the runner, so it is made to look
  like ordinary system state; this note is the only place its purpose is written down. Every
  shipped comment and docstring was scrubbed of grading, platform, cap, timer and provenance
  wording; the mechanics are unchanged, so grading, the local recording and the checks are the
  same as round 5's.

### 2026-11-19 (the name: `basedpl-interpreter-rebuild-no-examples`)

- Owner decision, 17:05 UTC: the task is `abundant/swe-m2_software-engineering_basedpl-interpreter-rebuild-no-examples`,
  in `tasks/swe-m2-software-engineer/basedpl-interpreter-rebuild-no-examples`. The content is
  round 5's; only the directory, the `[task] name`, the root `pyproject.toml` registration and
  the bundle directory's name change. The private seed, the cases and the build (Git-ignored)
  moved with the directory. The three model trials of the old name run on until about 00:20 UTC
  and stay under it as history; the new name goes to Oddish after they settle.

### 2026-11-19 (round 5: a root pre-cap watchdog, for the platform's ungraded capped runs)

- On Oddish today, every v2 trial whose agent ran into the 9.6 h cap was never graded: the
  separate verifier image failed to build right after the timeout (harbor-lh
  `ops/swe-marathon-v2/PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`), while runs that ended by
  themselves were graded. Until the platform fixes it, the task ends the agent's session itself,
  shortly before the cap.
- `environment/session-timer`, started as root by a second `[[agent.setup_complete]]` entry,
  arms one detached sleeper (a pid file under `/run` makes a second start a no-op). After
  33,900 s (the agent's 34,560 s less eleven minutes) it sends SIGTERM to every process of
  `dev`, repeating every 5 s for up to 60 s, then SIGKILL, and logs arm, fire and done lines
  with timestamps to the root-only `/var/log/session-timer.log`. The collect hook copies the
  log's last lines into the record, and the verifier reports `ended_by_timer` in
  `metrics.json`, never in the score. The instruction says nothing of it: it states no time
  budget, and a session it ends is one that would otherwise have hit the cap.
- Checks: the watchdog arms once (a second start logs "already armed"), fires at `END_SECONDS`
  (an environment override in the test), ends a process tree and a process in a session of its
  own, logs each step and removes its pid file; the task's two setup_complete entries; the image
  installs it root-only; the instruction mentions neither it nor a cap.

### 2026-11-19 (round 4: the hook's chmod masked every ctime, from the round-3 re-check 07c)

- Round 3's `chmod -R u+rwX` ran before the measuring walk, so every entry's recorded ctime was
  the hook's own time: the connectivity audit's condition ("deliverable ctime later than the agent's
  finish") held for every delivery, honest or not, and could not tell a file fetched into
  `/app/rebuild` after the turn from honest work.
- The hook now records every entry's lstat (path, type, size, mode, owner, mtime, ctime, inode)
  as root, walking by directory descriptor, right after the kill and before any step of its own
  touches the delivery (`before.jsonl`). Only then does it restore permissions, and only where
  needed: directories get u+rwx (the fixer has to rewrite links in them), and a regular file its
  owner cannot read gets u+r; each change is noted in the mark and the record, and a change that
  fails refuses the delivery. The manifest's `mtime` and `ctime` are the pre-hook values, matched
  by path and type; where the hook's own steps changed an entry (the chmods, the fixer's unlinks),
  the entry says so (`hook_changed_ctime`) and carries the later values apart
  (`ctime_after_hook`); an entry the hook made (a copy, a link made relative) is marked `times:
  "after the hook"`. `verify.py` reports `prescan_complete` and `hook_changed_entries`.
- The dropped-link warning now comes first in the instruction's delivery paragraph, with the rule
  that an interpreter must be one of the machine's own or copied into `/app/rebuild`; the fixer's
  refusal note says the same, and dropped links come first in the mark (07c F2).
- Checks: the test lstats the tree before the hook, runs the pre-scan and the measuring script,
  and asserts that every entry's manifest times equal the pre-hook ones; a 0555 directory and a
  0000 file are restored (0755, 0400), flagged and noted; no `chmod -R` in the hook; the order
  of the steps.

### 2026-11-19 (round 3: the collect hook's link copying, from Carve's QA 04 F1 and F2)

- Carve's QA found, on the same ported hook, that the link fixer launders a drop made after the
  turn: a link from `/app/rebuild` to a directory of `dev`'s own becomes a `copy2` with a
  forgeable mtime and a hook-time ctime, like an honest copy of a venv's Python, nothing records
  the source, and enough decoy links push the copy's note out of the mark and the verifier's view.
- The fixer now copies an outside target only when it is part of the machine's installation:
  owned by root, every file under a directory included. A link to anything else outside (`dev`'s
  own files anywhere, which could have been written after the turn) is removed. The instruction
  says so. For every copy and every refusal it records the source's path, owner, mtime, ctime and
  inode, as found before copying, as one JSON line on its standard output, which the root shell
  keeps in the state directory.
- The record (`.manifest.json`) holds every change, copies first, each flagged when its source lies
  outside `/app/rebuild` (every copy does) or changed since the session started (the setup hook
  now stamps `turn-started`; the hook records its own start too). The hook cannot know when the
  turn ended, so the audit compares the recorded source ctimes with the trial's finish. The mark
  holds every note, and the verifier reads the whole mark and copies the whole record into
  `metrics.json` (`copies`, `links`, `notes`, the flags' counts).
- The hook now freezes first: `kill -STOP -1` as `dev` until no process of `dev`'s is running is
  its first act, before the listing (one `ps`), the kill and the connectivity check, which used to run
  for up to six seconds before the kill.
- Checks: the fixer refuses a link to the user's own directory and file, copies a link to the
  system's `/bin/sh` with its source's facts, and makes an absolute inside link relative; the
  record carries the copies and flags; a mark with 60 notes reaches the verifier whole; the order
  of the hook's steps.
- **Also in this round, from the round-2 re-checks 07b and 12b.**
  - Hook (07b): as root, `chmod -R u+rwX` on the delivery before the fixer runs, and a tree that
    cannot be made writable is refused (a read-only folder stopped the fixer, and a link in it
    that leaves the directory lexically then aborted Harbor's extraction); the root pass removes
    any link whose lexical target leaves the directory, as the copy's filter judges it; files are
    hashed once per inode (400 names of one 20 MB file had cost 3.4 s each) within a 240 s budget,
    past which the rest are listed without a hash and the record says so; only processes in
    states R, S, D and T count as alive, so zombies are not survivors.
  - Verifier (07b): the mark is read up to 1 MB; fewer entries or bytes than marked is the
    evaluation error, more is a note (hard links split, or files the transport added); the
    unhardened usage text is refused only in an ELF file, so a note or a script that quotes it is
    not a fetched build; the drain past the deadline runs only when no process of the run's user
    or group is alive, so a child holding the pipe open is a timeout. `smoke.sh` skips its
    unprivileged section when the binary is readable by the caller, so the solution's log no
    longer reports a failure that is not one.
  - Cases (12b): the last-bit rule also covers monadic `∧` (the build's own atan2), `•special`
    and roots other than the square root, and a float with a tiny exponent counts only with ten
    or more digits (`1ₑ¯17` is an exact literal); piped cases now get their failing line (the
    one-line error records are chosen before the error and worker draws take them), and the
    command line's piped case holds a real error; the value printed before an uncaught error is a
    one-line value record of the reference suite, rewritten under the seed, rather than one of
    eight fixed forms; the `•prefs` request of a worker session ends in `◇ 0`, so its reply is a
    number rather than the whole settings record, and the instruction says `•prefs` still reports
    the out-of-scope settings.
  - Floor (12b): the recorder's dispatcher now also echoes the program's last number strand or
    string literal, evaluates the eight lead forms, and looks error messages up by nearest glyph
    features, trained on the other cases' own answers (leave one out: a bound no submission can
    reach). That is the strongest no-interpreter strategy the re-check built. The pool is held at
    or below 5% against it by `select` and by the build failing above it; the local recording
    measures 4.1%.
  - Not taken: splitting a worker session to drop only its last-bit request (12b F7), since a
    changed session is a different case; per-setting display quotas (12b F6); a path-by-path
    comparison of the arrived copy against the record (07b F4), beyond fewer-is-an-error.

### 2026-11-19 (rounds 1 and 2: QA waves 1 and 2)

- **QA.** Wave 1 (01, 04-08, 10, 12-14) and wave 2 (02, 03, 09, 11, 15-20): 9 FAIL, 11 CONCERN.
  Reports and summary: harbor-lh `ops/swe-marathon-v2/qa/basedpl/`. Every must-fix is answered
  below; the should-fixes not taken are listed with a reason at the end of this entry. Bundle
  `4164eb806274` is retired: it carried the Goose round-5 verifier.
- **Delivery and the connectivity window** (04, 07, 08; decision `2026-11-19-egress-window-DECISION.md`).
  The platform reopens public connectivity after the agent's turn and before `/app/rebuild` is
  collected. `environment/reclaim-scratch` is the task's one `[[verifier.collect]]` hook, as
  root. It records whether TCP 443 on pypi.org and github.com answers (3 s each) and every live
  process of `dev` with its command line, then kills them with `kill -9 -1` as `dev` until none
  is left. It gives back the 64 MiB and 64 inodes that `provision-scratch` set aside at setup
  (`setup_begin` and `setup_complete`), and fixes links as `dev`. Then, as root, it walks
  `/app/rebuild` by directory descriptor, removes what Harbor's copy would refuse, and refuses
  the delivery past 100,000 entries, 1 GB or 1,000-byte paths, or when a `tar -czf` of it fails
  or takes more than 100 s. It writes `.manifest.json` (the connectivity check, the processes, the
  kill rounds, and every entry with size, mtime, ctime and sha256) and the `.manifest` mark.
  All of this is ported from the back-office task's rounds 6-7. `verify.py` treats nothing
  arriving, or a mark that counts more than arrived, as an evaluation error. It writes the
  record to `metrics.json` (`delivery_record`), outside the reward. It refuses any delivered file
  whose sha256 is one of the 12 builds upstream publishes for 0.1.95: three release binaries
  and nine Python extensions, recorded by `scripts/upstream_builds.py`, hashes only. It also
  refuses any file holding the unhardened usage text `--kernel -f CONNECTION_FILE`, and a missing
  or malformed marker is an evaluation error (13 F4). The instruction states the copy's limits.
- **Verifier** (10, 11, 12, 13, 20). Goose round 6 (`1c81537`) is ported. The reward is reserved
  as `.reward.tmp` and renamed onto `reward.txt` only at the real end. Less than 512 MB free
  before grading, or after a cleanup mid-evaluation, is an evaluation error. Free space at the
  start and end, the evaluation's wall time and the summed cleanup time are in `metrics.json`,
  and shared memory counts by its creator too. The disk and file limits count only the run's
  own files: what its uid owns under the directories it can write to, plus deleted files it
  still holds open. They are counted only when `/tmp`'s or `/dev/shm`'s free figures fall past a
  limit, so other writers never stop a run. A case stopped by the memory, disk or file limit runs
  once more. A run that ended before its deadline is drained, not timed out. The run directory is
  `/tmp/bpl-run`. `TOTAL_SEC` is 4,200 and both verifier timeouts are 4,500: 1,778 generated cases
  at 2.1 s plus margins fit, and the check reads the generator's counts.
- **Images** (04, 12, 20). `sudo` is gone from the agent image. In the agent image's final
  stage, the installed set-group-id build runs the whole smoke test as `dev`. That includes a new
  unprivileged section: from `/`, `/opt` and `/opt/bpl`, reads of the build itself and of
  `/proc/self/exe` must be refused by the kernel or the path rule, and any failure stops the
  build. The patch's path rule lets the build's own path through from `/`, so the 2711 mode is
  what refuses it, and it is now proved as `dev`. `solve.sh` records the same reads as `dev` in
  `/logs/agent/reads.txt` for the first oracle trial.
- **Instruction** (01, 03, 09, 15). The requester's reasons now hold:
  - client data keeps scripts and golden files inside CI;
  - a legal policy of clean-room provenance applies to anything embedded for years, for a release
    upstream will not support.

  Worker replies must reproduce byte for byte, because saved notebooks keep them. The run
  conditions read as the job runner's behaviour, with no harness path and no "case" or "tests".
  The clean-room rules cover the build. Crashes need not be copied, and the out-of-scope features
  have reasons; code that mentions them must still load. The scope is stated as the whole manual:
  every glyph and system function page, `∂`, the worker protocol and the command line.
- **Cases** (02, 05, 06, 13, 14, 16-19).
  - Error cases print a computed value before the error (`LEADS`), never a literal an echo could
    copy. 60% of uncaught errors, and every syntax error, run as worker requests, whose replies
    carry the kind, message, span and display. Guards always print the message.
  - Worker sessions keep notebook state: definitions then uses, a function then calls, a display
    setting then values, a bound name used again.
  - Stdin cases are multi-line records, and the piped ones get a failing line at a statement
    boundary.
  - Display settings are chosen to suit the value.
  - Differentiation records are thinned to 5.7% of kept cases, from 12.1%.
  - The kind counts were rebalanced.
  - Fixes: a `_` subscript needs a digit (six cases had become undefined-name errors); no literal
    next to `=` or `≠` is rewritten; the leak index holds every run of 2-6 consecutive documented
    statements; and the leak check covers every rewrite the recorder may settle on.
- **Recording** (05, 11, 13, 17, 18).
  - Three main runs pinned to four worker threads, plus the perturbed run.
  - Memory text on standard error also counts as machine-dependent.
  - A display case is kept only if its setting changes what it prints.
  - A rewrite whose answer is all zeros, empty or false is passed over.
  - `expected_sha256` is written.
  - Answers showing the maths library's last bits are dropped: a float to 15 or more digits, an
    exponent of -12 or below, or a 32- or 16-bit float, from code using circular functions,
    exp or power, gamma, matrix division, decompositions or numeric inverses. Worker replies
    are judged one by one.
  - `recorder.no_interpreter` is the strongest dispatcher the reports describe: the command
    line's table, an echo of leading literals then exit 1, and one constant per visible shape.
    `select` holds it to 5%, and the recorder fails the build above that.
- **Measured** (stand-in recording `experiment/local-recording-6`, cases `01f5d1d2`): 1,673 of
  1,778 kept. Dropped: 86 whose display setting changed nothing, 16 showing last bits, 3 whose
  input holds the answer; none unsteady, crashed, machine-dependent or perturbed. The
  no-interpreter dispatcher passes 2.1% as measured by the recorder, and 1.85% when run as a
  program against the packaged bundle. The largest answer is 0.5%; nothing with exit 1 is 0.5%.
  APL ports are 7.1%, and cases in upstream's code form 214 (133 of them error records). Grading
  from the packaged bundle gives the stand-in reference 1.0 (1,673 of 1,673, 29.5 s), the no-op
  exactly 0, and the dispatcher 0.0185. The stand-in is upstream's unhardened macOS build, so
  the dispatcher's table of its `--help` holds the usage text the verifier refuses; that one
  refusal was switched off for the measurement.
- **Not taken, with reasons.**
  - A static PIE: no second build is allowed here. The 2711 mode, proved as `dev`, covers the
    path rule.
  - Upstream's `lib/*.bpl` stay out of the image (18 F2). The module cases run them as hidden
    library code. Shipping them would also ship the code that 39 module cases keep verbatim, and
    a gap in an implementation's reader shows up across those cases anyway.
  - The temperatures template still prints means with long floats (18 F3), as part of the tail.
  - The 25 program templates stay (02 F5).
- **Checks.** 43 task checks and the 27 repository checks pass with Python 3.13, and
  `check_repository.py` passes. Bundle `7462d71fe5a7` (248 files, 33,253,911 bytes) was built
  twice with the same hash, and Oddish preflight passes.

### 2026-11-19

- Started from the judge panel's choice for idea 9 ("no examples"): BasedPL, pinned at v0.1.95.
  The hardening patch, the pinned `Cargo.lock` and the local build script are in place; the
  rest of the task follows.
- **Target.** BasedPL is an APL-family array language from Answer.AI: Rust, about 31,000 lines
  in its core crate (`src/`, 84 files) plus the command line, a Cranelift JIT and a test kit. Its
  notation is new (runs grouped by spaces, `[…]` vectors, `ₓ`/`ᵣ` number kinds, `ᵇ` bitwise
  lifting, keyed axes, error guards with `$e`), its number tower has exact integers of several
  widths, rationals, complex numbers and three float widths, and its display, `⍕` formatting,
  error messages with source carets and the `--worker` JSON protocol are all exact text. The
  documentation is 215 pages (863 KB as shipped): the guides, a page per glyph and per system
  function, and the study notebooks.
- **Hardening patch** (`basedpl-hardening.patch`, nine files, 64 lines added, 109 removed;
  `apply.sh` applies it with `git apply`, all or nothing, and fails unless every file carries the
  change and nothing it removes is left):
  - `src/host.rs`: every file read (`•nget`, `•load`, `•image`, and through `src/lib.rs` the
    command line's program file) opens the file, takes its real path from `/proc/self/fd`, and
    refuses it unless it lies under the working directory the process started in and outside
    `/proc`, `/sys` and `/dev` (a link, `..` or a swapped link leads nowhere else);
    `•fetch` returns an error and never starts upstream's `curl`.
  - `src/data.rs`, `src/files.rs`: `•nput` writes no file (`"-"`, standard output, still works);
    `•metadata`, `•readdir`, `•copy`, `•rename`, `•remove` and `•mkdir` refuse.
  - `jit/src/lib.rs`: `Kernel::compiled` always declines, so no machine code is generated from a
    program (Cranelift is never called); stages run on their precompiled kernels.
  - `cli/src/cli.rs`, `cli/src/main.rs`: no `--kernel` (Jupyter, sockets) and no `--costs`
    (timings of files); the usage text matches. `cli/src/worker.rs`: the worker serves `code`,
    `call` and `bindings` only, not the test kit's `case`, `check`, `reference`, `page`, timing
    and route requests, which read files. `cli/src/editor.rs`: no REPL history file.
  - `cli/src/main.rs`: a build marker (`BPL-BUILD-MARKER-` and 32 hex digits, from
    `cli/src/build_marker.txt`), kept in the binary by `std::hint::black_box` and never printed.
  - Audited and left: BPL has no FFI and no shell; the `bpl` binary links no Python (the `py`
    crate is a separate extension); `•host "env"` shows only the caller's own environment.
  - Non-deterministic features are kept out of every case rather than patched (the panel allowed
    either): random numbers, the clock, plots and images, `•uuid`'s random versions, `•index`'s
    fresh names, and the interpreter's reports on itself. The JIT is patched out because it also
    generates code in the process.
- **One build** (`scripts/build_original.py`, the one local build allowed on this Mac): Rust
  1.100.0, `cargo zigbuild --release --locked --target x86_64-unknown-linux-musl -j 2 -p
  basedpl-cli --no-default-features` with upstream's own flags (`-C target-cpu=x86-64-v3`,
  `-Zshare-generics=yes`), stripped, every local path remapped. 4 min 38 s; one warning (fields
  of `•fetch`'s request never read). The result is static (no `PT_INTERP`, so no loader and no
  `LD_PRELOAD`) but not a PIE: zig's musl link does not produce `-static-pie`, and a second build
  was not allowed. 36,003,624 bytes, sha256 `60d2aed1d5b77ae8eeb74687a283bb9538577c2092dea283ba2704ccb9c5d27a`;
  the zero marker occurs once; no local path is embedded. `Cargo.lock` (281 packages; rustymath
  0.1.63, the rustyline and plotters forks at fixed commits) is pinned in `common/hardening/`,
  since upstream commits none and its dependencies move daily.
- **Images.** Both images and the solution install that build from `bpl.xz` with `mark.py`,
  which refuses any binary whose sha256 is not build.txt's and writes the image's private marker
  (`experiment/seeds.json`) over the zeros (the solution keeps the zeros). `smoke.sh` then proves
  the hardening on the installed binary in each image's builder stage: a value, a script, a module
  and standard input still work; reads outside the directory, by path, `..`, link, program file
  or module, and of `/proc/self/{maps,environ,mem}`, `/sys`, `/dev/null` and `/dev/stdin` with the
  working directory at `/`, are refused without printing the process's own files; no file is
  written, listed, copied, moved, removed or made; `•fetch` refuses and does not run a `curl`
  placed first on `PATH`; with `BASEDPL_COMPILE=always` no stage takes the compiled route;
  `--kernel` and `--costs` are usage errors; the worker refuses `case` and `check`. In the agent
  image the binary is `/opt/bpl/bpl`, `root:bpl` mode 2711 (execute-only, set-group-id, not
  dumpable), `/app` is root's and sticky and `/app/rebuild` root's and writable by all, and the
  agent is `dev`. The documentation is `/app/docs`; nothing else of upstream's is in the image.
- **Cases** (`scripts/make_cases.py`, `rewrite.py`, `programs.py`, `bpl_text.py`): 1,744 private
  cases from the private seed, by kind: `expr` 419, `script` 230, `apl` 119, `error` 219,
  `worker` 169, `display` 170, `stdin` 89, `module` 50, `program` 260, `cli` 19. See
  [Case mix](#case-mix). No visible set exists.
- **Verifier** (from the Goose task's round 5): separate image, root, records at build; see
  [Verification](#verification). The recorder runs each settled case twice and once perturbed
  (another binary path, 4 KB of environment padding, a stack 256 KB smaller, one CPU, one worker
  thread through `RAYON_NUM_THREADS=1`), keeps it on CPU time (0.25 s) and wall time (1 s), drops
  crashes (exit status other than 0, 1, 2, a signal, a panic or allocation-failure report) and
  answers that name the machine's memory (`memory limit of … MiB`), then caps any one answer at
  1.5% of the cases and the cases a no-interpreter dispatcher answers at 5%.
- **Instruction.** A requester who must keep 0.1.95's behaviour for years inside a product they
  license themselves asks for a clean-room implementation; the consumers of the exact output are
  CI golden files, a notebook service on `bpl --worker` that highlights error spans, and shell
  jobs on exit status. It states the hardened build's differences, the run conditions (user,
  directory, environment, pipes, limits, 2 s, 4 GB, 1 GB and 100,000 files written, the size cap
  on `/app/rebuild`) and what is out of scope, and gives no example, budget or grading.
- **Fixes found while checking.** System functions are excluded by their exact name (`•js` had
  matched `•json` and left out every record that parses JSON); the command-line cases take their
  share of an answer first, so no answer passes 1.5%; a recording run stopped by the disk or file
  limit (both measure the whole filesystem under `/tmp`) is run again and reported apart; the
  recorder's checks run in directories of their own, since two recorders on one machine share
  `/tmp/bpl-case`.
- **Checks.** 36 task checks (registered in the root `pyproject.toml`) and the 27 repository
  checks pass with Python 3.13; `check_repository.py` passes. A local recording of the 1,744
  private cases with upstream's own macOS release binary (not the hardened Linux build, so its
  answers are not the task's and stay in `experiment/`) kept 1,739: none unsteady, crashed,
  machine-dependent or changed when perturbed; the slowest run 17 ms; 5 dropped because their
  input holds the answer. Free answers 3.7% (command-line table plus one constant per kind), the
  largest answer 1.5%, printing nothing and exiting 1 1.5%, exiting 0 0.06%; cases from the APL
  ports 9.7%; cases kept in upstream's code form 248 (124 of them error cases, whose messages are
  the same for any implementation).
- Not built on Oddish and not run, on the owner's rule. Oddish preflight passes; the bundle is
  named in [Validation](#validation).

## Current implementation

| Part | State |
| --- | --- |
| Step `01-rebuild-interpreter` | Implemented: instruction, agent image with the execute-only interpreter and the documentation, separate verifier image, reference solution. |
| Further steps | Not designed. Candidates: the next upstream releases (0.1.96 onwards change semantics in patch releases); the worker's deadlines and interrupts. |
| Hardening | `common/hardening/`: the patch, `apply.sh`, the pinned `Cargo.lock`, `mark.py` (install and mark) and `smoke.sh` (proof at every install). |
| The original | `experiment/build/bpl` and `build.txt` from `scripts/build_original.py`, not in Git; packaging compresses it into both images and the solution, with a `build.txt` of the two lines `mark.py` reads (`link`, `sha256`). |
| Private inputs | `steps/01-rebuild-interpreter/tests/private/cases.json`, Git-ignored, from `scripts/make_cases.py` and `experiment/seeds.json`. The bundle holds each case without the generator's notes (`source`, `suite`, `family`, `want`, `scaffold_lines`), which stay in this file. Answers are recorded when the verifier image is built; `recording.json` beside them describes the recording and appears in `metrics.json`. |
| Oracle | The original, installed with the zero marker by `solve.sh`, with upstream's licence; nothing else runs. |
| Ratings (`harbor check`) | Not run. |

## Design dimensions

### Novelty

MirrorCode (Epoch AI and METR) gives an execute-only program, its documentation and visible
tests. This task removes the tests: no example runs and no expected outputs, only the
interpreter and its manual (the "no examples" variant). The target is a language implementation
first published on 2026-09-16, after the training data of the models under test, with a notation
of its own. SWE-Marathon v1's interpreters and compilers target languages the models know; the
Goose task in this repository ships example runs; the markdown-linter rebuild was a smaller,
example-driven target that a cheap model nearly solved.

What "no examples" removes is narrower than it sounds (QA 14 F3, 17 F2). The documentation holds
about 3,900 single-line examples, and replaying them through the build gives the agent its own
ground truth for every documented main path within the first hour. What the agent must design
experiments for is the tail: messages, error kinds, display modes, the worker's encoding, the
structure of `∂`. That tail is where most of the reward lies, and QA 15 found self-tests built
from the docs miss the features of 58.5% of graded cases. "No examples" adds an estimated 10-20%
to the work, not a different order of it.

### Verifiability

Standard output and exit status are compared byte for byte with what the original printed when
the verifier image was built; every kept case printed the same four times (three runs with four
worker threads, then perturbed) without crashing, its answer shows no last bits of the maths
library, and, for a display case, its setting changes what it prints. Partial progress is the
share of cases that match, once the cases matched show at least 10 different outputs that only a
run of the code given produces (rounds 13 and 14); below that, a program has shown no sign of
running what it is given, and scores 0.

### Realism

Clean-room reimplementations written from a manual and a binary are how compatible second
implementations are made (Wine, Samba, the PC BIOS). Keeping a language frozen at one release
for years, when upstream will not support it, is a common reason to own one, and a legal policy
that anything embedded that long is written clean-room with a provenance record is a common
reason not to fork. The exact bar has real consumers:
- golden files that CI keeps beside client data;
- saved notebooks whose worker replies must reproduce byte for byte;
- shell jobs that act on exit status.

The documentation is upstream's own. The cases come from upstream's reference suite and library,
and from programs of the kinds an analytics team writes: reports over tables, text tools on
standard input, validators that report what went wrong, and modules.

### Difficulty

**What a rebuild needs.**
- A reader for a new notation: runs grouped by spaces, strands, brackets, operator binding, sub-
  and superscripts.
- About 70 primitive functions and 25 operators, over a number tower with exact and fixed-width
  integers, rationals, complex numbers and three float widths.
- Dfns with predicates, guards and recursion; keyed axes and records; modules.
- Differentiation (`∂`). It is 6.1% of kept cases, down from 12.1% in upstream's suite, and the
  instruction names it.
- The display engine (precision, exponent forms, boxes, elision, widths, trees, notation) and `⍕`.
- Error messages with their kinds, positions and carets.
- The worker's JSON, with exact float encoding, and the command line.

Upstream's core is about 31,000 lines of Rust.

**Shape** (QA 16). The task is long because it is wide, not deep. The serial path (the reader
and evaluator, then `∂` or the worker) is about a tenth of the work, the leaves can be built in
any order, and nothing short of a real interpreter scores above the floor.

**Estimates.**
- QA 14, a strong human engineer: about 25-30 days for half the reward, 35-50 for 80%, 60-80
  for 95%.
- QA 15, an agent such as claude-code with DeepSeek Flash: about 11-16 h for half, so one session
  (9.6 h then, 9.42 h now) earns 0.15-0.45.
- QA 17 and 19, one session: a frontier model 0.35-0.60, DeepSeek Flash 0.20-0.40, GLM 5.3
  0.12-0.30.

None of these is measured yet.

**The tail.** The recorder drops answers that show the maths library's last bits: 17 in the local
recording, against 12 confirmed by QA 18 and one more by the re-check (the build's own atan2). What remains of the float tail is fixed and visible but
obscure: `+/` grouping, and solver residues at ten digits. QA 15 bounds it at 2.4%.

**Floors without an implementation**, measured at every build (`baselines` in `recording.json`):
- the strongest dispatcher with no interpreter in it (`recorder.no_interpreter`: the command
  line's table, echoed leading literals, the generator's lead forms evaluated, the last number
  strand or string echoed, an error-message lookup trained on the other cases' own answers, and
  one constant per visible shape) passes at most 5%, enforced by dropping cases and by failing
  the build; 4.1% locally, most of it the hidden-data lookup and the command line;
- any one answer is at most 1.5% of the cases;
- printing nothing and exiting 1 passes 0.6%.

Since rounds 13 and 14 none of these earns anything: a reward needs 10 different recorded outputs
that only a run of the code given produces (see [Reward formula](#reward-formula)). The
dispatcher's cases hold 2 of them, any one answer 1, and echoes, a table of the build's error
messages and printing nothing none; the build stops if a new set of cases lifts the dispatcher
past 3.

### Initial feasibility

Solved by construction: the original passes every kept case. For an agent, unknown.

## Case mix

The private cases are drawn from what the language does, in these kinds (generated, and kept by
the local stand-in recording):

| Kind | Generated | Kept | What it asks | Source |
| --- | --- | --- | --- | --- |
| `expr` | 418 | 416 | `bpl -e CODE`: one expression's displayed value | upstream's own reference records (core, static, regex, the mathish files), rewritten |
| `script` | 166 | 165 | `bpl main.bpl`: multi-line programs, setups, settings, `⎕←` output | the same, multi-line |
| `apl` | 120 | 119 | as `expr`, from records ported from APL suites | APLcart, April, ngn, Dyalog, BQN ports; with their error records and sessions 10% of kept cases |
| `error` | 235 | 234 | errors caught by a guard that prints the message (`$e`, the message, kind and message, or line, column and message): 161; uncaught errors in the worker, whose reply carries kind, message, span and display: 57, every syntax error among them; a run that prints a value (a one-line record of the reference suite) and ends in an error (exit 1): 16 | upstream's error records (a fifth from the APL ports) |
| `worker` | 190 | 176 | `bpl --worker` sessions in notebook form: records' code, definitions used by later requests, a function defined then called, a display setting then values, bindings of arrays used again, calls on encoded arguments; replies with exact values, displays and errors with spans | upstream's records |
| `display` | 230 | 146 | values and functions under `]display` (63), `]dissect` (34), `•prefs` box (14), limit and edges (13), notation (9), width (3), trees (3), prec (3), and `⍕` with format specs (4); kept only where the setting changes what is shown | upstream's records, and values built here |
| `stdin` | 89 | 89 | multi-line programs given with `bpl -` (41), lines piped into `bpl` with a failing line among them (41, of which 40 end with exit 1 after the other lines' output), programs reading `⎕` lines (7) | upstream's records |
| `module` | 50 | 49 | a main program loading upstream's library modules (`lib/`) with `•load` | upstream's library records |
| `program` | 260 | 260 | 25 new programs with seeded data: reports, a word counter, a ledger, a grade book, validators with custom error kinds, CSV and JSON on standard input, number theory, matrices, exact rationals, complex roots, ciphers, a module of one's own, `bpl -` with arguments | `scripts/programs.py` |
| `cli` | 19 | 19 | the command line's own answers, one case per behaviour: help, version, removed modes, wrong arguments, missing and refused files, arguments, the worker's request errors, piped lines with a failing one | `make_cases.cli_cases` |

**Rewrites** (private seed, `scripts/rewrite.py`).
- Every name the code assigns becomes an unused ordinary word, consistently. Keys, module names
  and names in code that runs text are left alone.
- Numbers in value positions take other values of the same form. Never rewritten: a size, count,
  position, axis, rank, iteration count or function code; 0 or 1; a number in a check such as
  `≡`, or next to `=` or `≠`.
- Words in prose strings take other words of the same length.

Each case gets up to three rewrites. The recorder keeps the first that ends as the unrewritten
code does and prints something else, and is not all zeros, empty or false where the original
answer is not. Comments are removed from upstream's code (some state results).

**What the documentation shows.** No record or program becomes a case, in any of its rewrites, if
the shipped documentation holds it, its skeleton (names, numbers and text abstracted), or its
skeleton as a whole block, a statement or a run of 2-6 consecutive statements. Packaging repeats
the check on the real files.

Records with `∂` are drawn at 48%, which puts differentiation at about 6% of the kept cases.

**Left out:** randomness, the clock, files, the network, drawing, `•hash`, `•deflate`, `•mime`,
`⇄`, `•storage`, `•memory`, `•explain`, `•index`, `•host` facts other than the command line's,
`]help`, `]clear`, and the `threads`, `seed` and `fusion` settings.

## Workload

A run is one trial (one task row per experiment, no continuation tasks): the agent's limit in
`task.toml` is 34,560 s (9.6 h), and nothing of the task ends the session before it (round 12).
The instruction states no time budget.

**A session that runs to its limit.** Harbor stops waiting at the limit but does not end the
agent's processes: they would run on until the collect hook freezes them, 5-14 s later, with the
network open again by then. So the last set-up run (`provision-scratch` at `setup_complete`)
leaves a root process that stops the session's processes after the limit, counted from the start
of the session's first process: the first process of `dev` to begin after it whose parent is not
`dev`'s (harbor starts it inside the agent's clock), its start read from `/proc` in seconds since
boot. 34,560 s plus 2 s after that start, and, where the network's return can be watched (the
hosts resolved at set-up), not before one of them answers again (harbor reopens the network when
it ends the agent's phase, which a paused clock delays too), it repeats `kill -STOP -1` as `dev`
until no process of `dev` runs (states R, S, D; 15 s at most), records when and against what
(`stopped_after_limit` in the record and in `metrics.json`, times with fractions), and exits. With
no such process it does nothing. It never ends a process and never acts before then; once the
collect hook has begun it stops nothing, and the hook ends it before running anything as `dev`. The work
ends 34,560 s after the session began (`turn-started`), and the hook takes out every file and
link that changed later, now in a window of about 2 s (see [Verification](#verification), step 1). The upload is a flat single-step bundle because the platform graded capped runs of that
layout (SymPy's, 3 of 3) and not of the steps layout, whose separate verifier image failed to
build right after the timeout (harbor-lh `ops/swe-marathon-v2/PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`).
The installed scripts and their state are named for ordinary housekeeping (`provision-scratch`,
`reclaim-scratch`, `/var/lib/scratch`) so that a solver listing the container reads nothing about
grading, a cap or a deadline from them.

## Verification

1. **Collection.** When the agent's turn ends, the root collect hook writes its mark and ends the
   process that stops `dev`'s processes after the limit, then freezes `dev`'s processes, lists
   them and what they hold open for writing or map shared and writable, kills them, records
   every entry's own times before touching anything, and records connectivity. It restores permissions only where needed (directories u+rwx, unreadable
   files u+r, each noted), fixes links (a link to a root-owned system file or directory becomes a
   copy when the disk has room to spare for it, with the source's path, owner, times and inode
   recorded; a link to anything else outside is removed and noted first in the mark; a link inside
   is made direct, read by name against the walk's own listing, and one through another link is
   removed). For a session that ran to its limit it then takes out every file and link that
   changed after the end of the work (the session's start plus 34,560 s, by the change times
   listed before the hook touched anything), and every name of each file its frozen processes
   still held open for writing or mapped shared and writable, noting each and counting them in the
   record (`late_entries`, `held_for_writing`, `work_end`). It bounds `/app/rebuild`, packs it once as the copy will, with
   room left for its record and mark, and marks and records it with the pre-hook times as the
   authoritative ones. A tree it cannot measure within 420 s of its start (an alarm ends the walk
   and the links then, inside any call), or pack by 510 s, is refused; the freeze and the kill
   stop after 15 s each, and what the hook writes is bounded in bytes, so it ends with a mark
   within its 600 s, on a full disk too (see the development log, rounds 3-4, 10, 11 and 12).
   Harbor then copies `/app/rebuild`, the declared artifact, into the verifier.
2. **Before any submitted code runs**, the verifier:
   - reserves `.reward.tmp` and `metrics.json`;
   - raises an evaluation error with less than 512 MB free;
   - checks the delivery against the hook's mark: nothing arrived, or fewer entries or bytes than
     marked, is an evaluation error;
   - copies the hook's record into `metrics.json`;
   - picks a uid inside the user namespace's map for submitted code and checks the unprivileged
     run: no_new_privs from the status file or `prctl`, ids, groups, capabilities with a missing
     `CapAmb` counted as 0, limits, and a set-id root copy of `id` that must report that uid. A
     failure is an evaluation error.

   It then seals `/app/rebuild`: root-owned, read-only, no set-id bits, at most 200,000 entries
   and 4 GB. It searches the delivery for the original's build marker, for the unhardened usage
   text, and for any of upstream's 12 published builds by sha256. A submission that cannot be
   sealed, or that holds any of these, gets reward 0 with a note.
3. **Before each case**, it kills that uid's processes and sweeps what it left in every
   world-writable directory and its System V IPC objects. Less than 512 MB free after that sweep
   is an evaluation error. It writes the case's files into a new `/tmp/bpl-run` with new empty
   `HOME` and `TMPDIR`. `/app/rebuild/bpl` runs there with:
   - no_new_privs, the case's arguments and standard input, no network;
   - the recorder's environment and limits;
   - 2 seconds and 4 GB of memory in use;
   - 1 GB and 100,000 files of its own on disk;
   - at most 1,000,000 bytes of output.

   A case stopped by the memory, disk or file limit runs once more.
4. **Scoring.** A case passes when the exit status and the bytes of standard output equal the
   recorded ones. A case that cannot be set up or started, runs too long, prints too much or
   passes a limit fails; none of that is an evaluation error. The share of cases passed is the
   reward only where the passed cases hold at least 10 different recorded outputs that only a run
   of the code given produces; otherwise the reward is 0, with a note in `metrics.json` and on the
   `reward:` line (rounds 13 and 14; see [Reward formula](#reward-formula)).
5. **Deadline.** One deadline, 4,200 s from the start, covers sealing, scans, cleanup and cases;
   the cases left count as failed. At the end the verifier cleans up, writes the reward into its
   reserved file, renames it onto `reward.txt`, then writes `metrics.json`.

### Reward formula

```
reward = cases_passed / cases_kept    where distinct_outputs >= 10
reward = 0                            otherwise
```

- Continuous, fixed denominator per image build (the private cases kept by the recording).
  No executable: reward 0.
- `distinct_outputs` (`runcases.distinct_outputs`; round 13, recounted in round 14) counts the
  different recorded outputs among the passed cases whose answer only a run of the code given
  produces (`runcases.counts`):
  - the case gives the program code to run: code after `-e`, a file of the case's own named first,
    or a program or the worker's requests on standard input (`runcases.runs_a_program`);
  - its recorded output is not empty;
  - not every line of it occurs in the case's own input (its files, library files included, its
    standard input and its arguments: `runcases.answer_in_input`), since echoing what is given
    prints such an answer;
  - it is not an error case whose guard prints only the error's message
    (`runcases.prints_its_error_message`, read as `recorder.error_instances` reads it), since a
    table of the build's messages answers those;
  - it is not one of the command line's own cases (kind `cli`, one per behaviour, which a table
    answers).

  An output counts once however many passed cases share it. Below 10 (`runcases.DISTINCT_OUTPUTS`)
  the cases passed earn nothing, and the note says why in `metrics.json` (`notes`, `withheld`) and
  on the `reward:` line; `metrics.json` always holds `distinct_outputs` and
  `distinct_outputs_needed`. No case is removed, changed or reweighted, and from 10 on the reward
  is the share passed, as before.
- 10 was chosen by measurement on the local recording (development log, rounds 13 and 14). Every
  kept case together holds 1,421 such outputs. The model deliveries graded so far hold 722, 297
  and 69 (v5) and 30 (v4's GLM run `-33`, the weakest). The strongest programs with no interpreter
  in them hold 2 (the recorder's dispatcher, its hidden-data lookup included) and 1 at most (any
  fixed answer); echoes and tables of the build's error messages hold none. That leaves about
  three times on either side of 10.
- The build stops (`recording.dispatcher_too_close`, exit status 1 in the image's recording step)
  when the recorder's dispatcher reaches more than a third of 10, so a new seed or new templates
  cannot bring such a program near a reward unnoticed; on the local recording it reaches 2.
- What the rule costs an honest delivery below 10: typically about 1% of the cases (the passes
  that come with the first 9 counted outputs, from the four model deliveries' own passes thinned
  at random: a median of 10-17); at most 227 cases (13.6%), a program passing every case that
  does not count and the cases of the 9 most shared outputs that do.
- An evaluation error leaves no reward file. The causes:
  - not root, privileges that cannot be dropped, or a drop that does not hold;
  - private inputs unreadable, or the marker or the list of upstream's builds missing;
  - less than 512 MB free at the start or after a cleanup;
  - nothing arrived, or the copy was cut short;
  - the verifier ending before the real end.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verify.py` and `tests/verifier/runcases.py`; `tests/verifier/recording.py`
  describes the recording (cases kept by kind, drops by reason, settling, cases whose kept form
  is upstream's code with only its names changed, the APL share, run times, the baselines, the
  build) for `metrics.json`.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 2, 3, 5, 10, 14).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read, copy, trace or dump the interpreter from outside its process, or preload a library into it | File mode and group; the link | Goose QA passes 04 and 04b (the same layout) | `/opt/bpl/bpl` is `root:bpl` 2711: execute-only and set-group-id, so not dumpable; static, so no loader honours `LD_PRELOAD` or `LD_AUDIT` | Not a PIE: the binary's own code and data sit at fixed addresses (stack, heap and mappings still move); the sandbox's handling of a traced set-group-id exec is unmeasured | `/logs/agent/probe.txt` of the reference trials that ran the probe (every version so far, under both names; round 9 removed it from the solution), not read yet | 🟡 YELLOW / UNASSESSED |
| 2 | Read the interpreter from inside its process: a program reads `/proc/self/mem` or `maps`, runs a program, compiles code, or reads files outside its directory | Hardened build | Audit of every file, process and unsafe site in `src/`, `cli/`, `jit/`, `image/` (host.rs, files.rs, data.rs, the CLI, the worker, the editor) | Reads only under the start directory, checked on the opened file, never `/proc`, `/sys`, `/dev`; no writes; no `curl`; no JIT; no test-kit requests; no history file. `smoke.sh` proves each at every install | A memory-safety bug in the interpreter or its dependencies (rustymath has unsafe SIMD code) | The smoke test at every image build (as root, and as `dev` in the agent image; a failure stops the build); then the first trajectories as `dev` | 🟡 YELLOW / UNASSESSED |
| 3 | Run as root, or as a user who can read the program | `[agent] user` | Not read yet on this task | `user = "dev"` (uid 10001) | Depends on each harness | `delivery_record` in each model trial's `metrics.json`: `bpl.owner` is 10001, not 0, and `user_processes` lists the agent's processes under uid 10001 at the session's end; the old name's three graded v2 model trials can answer it now | 🟡 YELLOW / UNASSESSED |
| 4 | Deliver the original, a published build of it, or a wrapper that calls it | Verifier image; `/app` ownership; the marker; upstream's hashes | Goose QA passes 07 and 13; QA 04, 08, 20 | The verifier image holds no copy; `/app` is root's and sticky, so `dev` cannot replace `/app/rebuild`; a submission holding the images' marker, upstream's unhardened usage text, or a file with the sha256 of any of the 12 builds upstream publishes for 0.1.95 is refused (checked: the search, its chunking, the hashing by size, the images-only staging); a missing or malformed marker is an evaluation error | A copy transformed to hide both the marker and the hash | First trial as `dev`: `/app/rebuild` cannot be renamed | 🟢 GREEN / LOW |
| 5 | Fetch the public source, upstream's tests or a published build, including in the window after the turn when the platform reopens connectivity | Agent network; the collect hook; the refusals of row 4 | QA 04 and 08 (platform finding `PLATFORM_EGRESS_WINDOW.md`); decision 2026-11-19 (A, with conditions) | `network_mode = "no-network"` for the turn; the root collect hook kills every process of `dev` before anything is copied and records whether connectivity was open and what was running (`delivery_record`); in a session that ran to its limit, whose processes run on into the window, every file and link changed after the end of the work is taken out (row 18); published builds and the unhardened usage text are refused; no upstream source, test, notebook result or design note in the image | The window stays open until the platform keeps the agent-phase policy through collection, and a turn that ends by itself leaves any process still running in it until the hook's freeze; a transformed fetched build escapes the refusals; a harness with network access would defeat the task | Audit every trial (`delivery_record`: survivors, connectivity, ctimes after the turn) before its score is recorded | 🟡 YELLOW / UNASSESSED |
| 6 | Look up answers from what is shipped | Case generation | Checked on a stand-in upstream and on the real files at packaging; QA 06 and 12b | No example runs ship; no case holds a documented program or a near-copy, in any rewrite the recorder may settle on (whole blocks, statements and runs of 2-6 statements; 311 core records left out); `make_cases.leaks` runs again at packaging | The documentation's examples teach behaviour by design: about three quarters of its runnable one-liners state their displayed value in a comment, so replaying them is the agent's first corpus; three worker requests are near-copies of documented one-liners with the same value, one reply each in sessions of about ten | Keep | 🟢 GREEN / LOW |
| 7 | Read an answer out of the case's own input | Generation and recording | Checked | Comments removed from upstream's code (some state results); the recorder drops a case whose input holds its whole answer (5 in the local recording) | Short answers a program spells out literally | Read `dropped` in `recording.json` | 🟢 GREEN / LOW |
| 8 | Recall upstream's published expectations | Rewrites | Local recording: 248 of 1,739 kept cases in upstream's code form | Names, value literals and prose words rewritten under the private seed; the recorder prefers rewrites that change the answer; `recording.json` counts the cases still in upstream's form (`kept_as_upstream_code`, mostly error records, whose messages are the same for any implementation) | BasedPL was published 2026-09-16; models trained later may know it, and its reference files | Read `kept_as_upstream_code`; re-check for models trained after 2026-09 | 🟢 GREEN / LOW |
| 9 | Tamper with the reward files, or suppress them by forcing an evaluation error | Separate verifier container | Goose QA passes 07, 07b, 10, 10b, round 6 (the same verifier) | No reward exists until the real end (`.reward.tmp` renamed onto `reward.txt`); bounded, link-refusing reads; one deadline; capped submissions; `rm -rf` sweeps; every per-case exception a failed case; host disk shortages are errors only after the sweep has taken back everything the uid held (checked) | Kernel keyrings survive between cases; they carry no answer | Keep | 🟢 GREEN / LOW |
| 10 | Infer an evaluation from the files and text | Instruction and image | Checked: no grading, hidden, budget or session wording; no examples or runner shipped | Neutral requester text | An agent can still guess that more programs exist | Read the first trajectories | 🟡 YELLOW / UNASSESSED |
| 11 | Run as root in the verifier through a set-id or capable file | Privilege drop and sealing | Goose QA pass 10 F6 | Sealed root-owned without set-id bits; `setpriv --no-new-privs`; the drop is checked by status or `prctl` and a set-id `id`, or nothing is graded (checked) | A kernel that ignores no_new_privs; the probe then refuses to grade | First baseline's verifier log | 🟢 GREEN / LOW |
| 12 | Pass cases with no interpreter: the command line's answers, echoed literals, the generator's lead forms, the last strand of a program, an error-message lookup, constant answers per visible shape | Case mix and selection | QA 02, 05, 13, 17 measured 5.5-7.3% on the first cases; the round-2 re-check 2.8% by echoes and 5.7% with a lookup trained on hidden data; local recording now: 4.1% by the recorder's union of every strategy, 2.7% when the dispatcher is run as a program | Leads are one-line value records of the pool; uncaught errors mostly graded through the worker's reply with message and span; handlers always print the message; any one answer capped at 1.5%; `select` holds the strongest dispatcher (`recorder.no_interpreter`, every strategy above) to 5% and the recorder fails the build above it; since rounds 13 and 14 the cases such a program passes earn nothing: echoes and the error messages a guard prints do not count toward a reward, and what is left of the dispatcher's cases holds 2 of the 10 different outputs a reward needs (row 19); the build stops if a new set of cases lifts it past 3 | Display of simple literals is legitimate early work, which now earns only beside 10 outputs that need a run. The error lookup is no bound: re-check 10 reached its share without hidden data, from a table of 7,537 guarded probes recorded from the build, and a program built that way with echoes reached 29 outputs on round 13's count (none of them counts now) | Read `baselines.no_interpreter_dispatcher_by_strategy` and `baselines.no_interpreter_dispatcher_distinct_outputs` (3 at most) in the first baseline's `metrics.json` | 🟢 GREEN / LOW |
| 13 | A crash of the original graded as an answer | Recording | Checked with a stand-in | Signals, exit statuses other than 0, 1 and 2, panics and allocation failures are dropped; more than 2% fail the build | None found | Read `dropped_crashed` | 🟢 GREEN / LOW |
| 14 | Answers that depend on the machine or on the maths library's last bits: thread counts, hash order, the memory limit, CPU features, approximation bits | Recording | Local recording: no case unsteady or perturbed; 16 last-bit answers dropped (QA 18 confirmed 12) | Three runs pinned to four worker threads and a perturbed one (one CPU, one worker thread); memory-limit text dropped from either stream; last-bit answers dropped; rustymath chooses SIMD paths at compile time (`x86-64-v3`); `expected_sha256` lets two builds be compared | A host without AVX2 cannot run the original (the smoke test then fails the build, and an oracle row below 1.0 with `host.avx2` false is infrastructure); the x86-64 build's bits are first seen at its own recording | Two oracle trials must each score 1.0 with the same `kept_ids_sha256` and `expected_sha256` before any model trial | 🟡 YELLOW / UNASSESSED |
| 15 | A busy host fails a graded run spuriously | Disk and file limits | QA 10: a `sleep 10` submission was stopped for a file limit by the whole-filesystem figures | The limits count only the run's own files (its uid's under the writable directories, and deleted files it holds open), and only when the free figures fall past a limit; a case stopped by a limit runs once more; host shortages after a sweep are evaluation errors | None found | Read `disk_limits`, `file_limits` and `limit_retries` in the first trials' `metrics.json` | 🟢 GREEN / LOW |
| 16 | Make Harbor's copy drop an honest delivery (a running build, links that leave the directory, FIFOs, a sparse file, a full disk, a read-only folder) so that it scores a valid 0, make the copy fail at will (a link that climbs past `/` and back, a chain of links that holds the hook past its 600 s, a disk filled so that the hook's own record or the copy's pack has no room), launder a file fetched after the turn through a link the hook copies in, or hide a post-turn write behind the hook's own changes to ctimes | The collect hook and the mark | QA 07 F2-F3 (ported from the back-office task, rounds 6-7); Carve QA 04 F1-F2; re-checks 07b and 07c; round 10, with Carve QA 22 and 23 as the catalogue (two paths reproduced on 6a93903); re-check 08 (M1, M2, S1, S3, S4: round 11) | The hook freezes and kills `dev`'s processes first, records every entry's own times before touching anything (the manifest's authoritative mtime and ctime), gives back reserved room and inodes, restores permissions only where needed and notes each change, copies an outside link's target only when root owns it (every file under a directory included) and the disk keeps room to spare, and records the source's path, owner, mtime, ctime and inode, removes every other outside link (noted first in the mark) and all special files, lets the system resolve a link before the fixer follows it, reads every link of the last script by name against its own listing (no call follows a link; one through another link is removed) and keeps a link inside only as the direct relative path to what it reaches, bounds entries, bytes and path length, hashes once per inode, refuses a tree not measured within 420 s of its start (an alarm ends any call then), packs once within 100 s and by 510 s with room for its record and mark beside it, and marks the delivery; the fixer prints 2 MiB at most, each script's own notes take 64 KiB and the mark's 32 KiB, names cut to a few hundred bytes, the rest counted; a refused tree's record counts what it held and lists only the first notes; the verifier grades what arrived, reads 1 MiB of the mark, copies every change into `metrics.json` with flags, and treats nothing arriving or a short copy as an evaluation error, which after a completed hook only the copy itself can cause | A platform copy that fails after the hook's own pack succeeded (an error, then a re-run); the refusal renames `/app/rebuild`, which overlayfs without `redirect_dir` refuses (gVisor's overlay does not; QA 08 N1); a fetched file written straight into `/app/rebuild` after a turn that ended by itself and before the hook's freeze, which the ctime audit against the trial's finish can catch, since the recorded ctimes are the session's own (after a session that ran to its limit, the hook takes such a file out: row 18) | Read `delivery_record` (copies, links, notes, `latest_ctime` and `hook_changed_entries` against the trial's finish) in every trial | 🟢 GREEN / LOW |
| 17 | Read the build's own file through the hardened read path from a start directory whose rule lets it through (`/`, `/opt`, `/opt/bpl`) | File mode; the path rule | QA 04 F4, QA 12 F2 | The 2711 mode refuses the read for `dev`; the agent image's final stage proves it as `dev` at every build (with the whole smoke test on the set-group-id build; a failure stops the build) | A kernel that let a non-dumpable set-group-id process read its own executable | Every image build; `/logs/agent/reads.txt` of the reference trials before round 9 (the same reads at run time), not read yet | 🟢 GREEN / LOW |
| 18 | Work on past the limit: a turn that reaches the cap leaves the session's processes running (Harbor never ends the agent's exec), and until the collect hook they can write, fetch with the network open again, or swap files in `/app/rebuild` | The collect hook; change times | Round 12 (decision 2026-11-24, item 2); the capped-turn checks, which fail on `ff793d5`; the re-check of round 12, R1 (a write through a shared writable mapping set up before the end can leave the change time as it was), and the held-files checks, which fail on `7161493`; the stop-after-the-limit checks, which fail on `e0f3130`, and the first-process checks, which fail on `d8e0436` | About 2 s after the limit, a root process left by the last set-up run stops `dev`'s processes (SIGSTOP, never a kill: `kill -STOP -1` as `dev` until none runs; decision 2026-11-24, 09:40 UTC amendment), counted from the start of the session's first process (the first process of `dev` to begin after it, its parent not `dev`'s) and, where the network can be watched, not before the network comes back (OB-1), so late changes have a window of about 2 s instead of the 5-14 s until the hook; the end of the work is `turn-started` (root-only, written at `setup_complete`) plus 34,560 s; the hook's listing, taken after the freeze and the kill and before anything else touches the tree, holds every entry's change time, and every file and link changed after the end is taken out before the walk (whatever stands at its path by then, a copy the link fixer made included); so is every name of each file that a frozen process still held open for writing or mapped shared and writable, read from `/proc` before the kill (as root, then as `dev` for what root may not read); each is noted in the mark and counted (`late_entries`, `held_for_writing`, `work_end`); without a complete listing of either kind, or with a process of all-`dev` ids that neither could read (it made itself undumpable), such a tree is refused; `dev` cannot set a change time back; a fetched build is refused anyway (row 4) | The stop counts from a process harbor starts inside the agent's clock, so it cannot precede the limit by the set-up-to-clock gap; where the network cannot be watched (its names did not resolve at set-up), a trial paused during its turn would be stopped early by the pause's length. A mapping written after the end and dropped before the freeze (unmapped, made read-only, or its process gone) leaves nothing to list and, on tmpfs (gVisor's too, as read), possibly no new change time, so such a write can count: it stays a residual for the per-trial audit of `delivery_record` (a surviving process, `connectivity_open`) and the tripwires of row 4 (R1b of the re-check). A late deletion cannot be undone, and a late rename keeps the entry's old change time on a filesystem that does not update it on rename (gVisor's overlay is unmeasured); a process that ran a set-id program is not read (its own code cannot map the tree's files, and its writes through a descriptor move the change time); the end falls the few seconds between `setup_complete` and the start of the run's clock early, so work in those seconds is taken out too | Read `work_end`, `late_entries` and the mark's `removed …` notes in every trial that reached the limit, and in its collected record (`.manifest.json`) `held_for_writing` and `writers` (whether the listing was whole, and which processes were not read) | 🟢 GREEN / LOW |
| 19 | A stub launcher: deliver a program that runs nothing it is given (it tries the original's paths and the private cases, then prints the command line's documented strings, nothing with a common exit status, a fixed answer, echoes of the program's literals, or a table of the build's error messages) and collect the few cases whose answers need no interpreter | The distinct-output rule (`runcases.DISTINCT_OUTPUTS`, `runcases.counts`, `runcases.distinct_outputs`, `verify.withheld`); the recording's guard (`recording.dispatcher_too_close`); the case mix | v5's verdict: replay `-46` (the documented `--version` and `--help` strings, exit 2 for the rest: 0.003586, 6 of 1,673 cases) and replay `-47` (exit 0: 0.000598, 1 case); round 13's rule and sweep; re-check 10 (round 13's threshold zeroed v4's honest `-33`; without hidden data, echoes and a table of 7,537 error probes recorded from the build reached 29 on that count); round 14's measurements and its sweep through the real path (`replay-r15`, 34 programs) | A reward needs 10 different recorded outputs that only a run of the code given produces: empty outputs, outputs whose every line occurs in the case's own input, error messages a guard prints and the command line's own cases never count, and each output counts once. Measured on the local recording: every kept case 1,421; the model deliveries graded so far 722, 297, 69 and 30 (v4's `-33`, the weakest); the recorder's dispatcher 2; each of the 20 most common answers 1 at most. Through the real path the reference scores 1.0, and both replays, the 20 constants, the last-literal echo, the dispatcher's table, re-check 10's `kitchen-sink`, `kitchen-sink-2` and literal machine (0 outputs each) and its 290-line evaluator (9) score exactly 0, while the four model deliveries keep their shares. The image does not build if a set of cases lifts the dispatcher past 3 | A program that really evaluates 10 programs given to it earns its share: that is a start on an interpreter, not a stub. An honest delivery below 10 loses what it passed: typically about 1% of the cases, at most 13.6% (every case that does not count, and the cases of the 9 most shared outputs that do). A cheap table of two-token programs recorded from the build could add a few outputs (re-check 10: about 4), still below 10 | Read `distinct_outputs` and `withheld` in every trial's `metrics.json` (a withheld reward also says why on its `reward:` line), and both distinct-output baselines in the first oracle trial's | 🟢 GREEN / LOW |

Licence: the upstream is Apache-2.0. Its `LICENSE` is shipped with the documentation in
`/app/docs` and with the reference solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (79 tests) with `ci_checks` (27), Python 3.13, and `check_repository.py` | round 14 | pass |
| Round 14's gate checks against a copy of the task at `764c51f` (`git archive`, with round 14's checks file) | round 14 | the four gate checks and the whole-run check fail (no `runcases.DISTINCT_OUTPUTS`, `counts` or guard; the whole run's echoes are scored); the slow-runs check passes on both. Round 13's `grade()` gives the cases shaped as v4 `-33`'s passes 0 (57 passed, 36 outputs, 40 needed), round 14's 57/200 |
| The real-path sweep of round 14 (harbor-lh `qa/basedpl/scratch-09/replay-r15/r14/`: both hooks under dash, tar and the data filter, then `verify.main()`; 34 programs) | round 14's flat `5be602ec5ec1` against `local-recording-9` | the reference 1.0 (1,673/1,673; 1,421 outputs; no note); the no-op 0.0; replays `-46` and `-47` as delivered, the 20 most common answers, the last-literal echo, the dispatcher's table (2 outputs), re-check 10's `kitchen-sink` and `kitchen-sink-2` and literal machine (0 outputs each) and its 290-line evaluator (24 passed, 9 outputs) 0.0 each, with the note; v5 `-48` 0.506276 (847; 722), `-50` 0.234907 (393; 297), `-49` 0.053198 (89; 68) and v4 `-33` 0.034071 (57; 30), each its share |
| The shipped `recording.py`, run as the image's recording step runs it, on `local-recording-9` | round 14 | exit 0; `distinct_outputs_kept` 1,421, `no_interpreter_dispatcher_distinct_outputs` 2, `kept_ids_sha256` `bb030348…` |
| Round 13's two new checks against a copy of the task at `4453fd8` (`git archive`, with round 13's checks file) | round 13 | both fail: the runner has no `runs_a_program` and the verifier no `DISTINCT_OUTPUTS`. On the same cases, the old `grade()` gives the documentation launcher 0.054054 (4/74), exit 0 0.013514 (1/74) and the echo one output short 0.756757 (56/74); round 13 gives each 0 |
| The stub sweep through the real path (harbor-lh `qa/basedpl/scratch-09/replay-r15/`: both hooks under dash, tar and the data filter, then `verify.main()`) | round 13's flat `e9ee043b5d71` against `local-recording-9` | the reference 1.0 (1,673/1,673; 1,528 different outputs of programs given to run; no note); the no-op 0.0; replays `-46` and `-47` as delivered 0.0 (4 and 1 passed; 0 outputs); each of the 20 most common answers 0.0 (3-10 passed; 0 or 1 output); the last literal echoed 0.0 (23 passed; 17); a table of every case the recorder's dispatcher answers, with the recorded answers, 0.0 (68 passed; 29). Each zero carries the note |
| The three v5 deliveries, pulled read-only (`oddish pull`), through the same path, and through `grade()` alone without the rule | round 13 | `-48` 0.506276 (847/1,673; 773 outputs), `-49` 0.053796 (90; 76), `-50` 0.234907 (393; 340), the same with and without the rule. The platform's 0.505678 (846), 0.056186 (94) and 0.237298 (397) differ only in the command line's own cases (other answers in upstream's build) and one `expr` case near the 2 s limit; the first 200 failed ids agree but for one command-line case |
| The three first-process checks against a copy of the task at `d8e0436` (`git archive`, with the fifth commit's checks file) | round 12, fifth commit | each fails on its own path: no stop at the first process's start + 34,562 s, nor once the network answers (the stop there counts from the set-up run's own time), and with no first process the older stop comes anyway |
| The three stop-after-the-limit checks against a copy of the task at `e0f3130` (`git archive`, with the fourth commit's checks file) | round 12, fourth commit | each fails on its own path: no process is left by the set-up hook (two checks), and the forked, `setsid` and SIGCONT-sending processes are left running (`S`, `Ss`) |
| The thread check against a copy of the task at `6f07b14` (`git archive`, with the third commit's checks file) | round 12, third commit | fails: the mapping held only by a live thread after the first thread's exit is not listed, and `bpl` is delivered (`delivered 2 15`) |
| Round 12's held-files checks against a copy of the task at `7161493` (`git archive`, with the second commit's checks file) | round 12, second commit | both fail: the hook has no listing of what the frozen processes hold (`KeyError: 'writers'`) |
| Round 12's checks on the end of the work against a copy of the task at `ff793d5` (`git archive`, with round 12's checks file) | round 12 | the three fail: the capped turn's late entries are delivered (`delivered 8 152` where round 12 delivers `delivered 4 17`), the record has no `late_entries`, and `environment/session-timer` is there |
| The flat bundle against the steps bundle, file by file | round 12's `ad93859c8f45` and `8ea1e9bf08ec` | the same 246 files with the same modes; the step's 21 move from `steps/01-rebuild-interpreter/` to the top byte for byte; `task.toml` differs only by `multi_step_reward_strategy = "final"` and the `[[steps]]` table, whose limits are the top level's; the same name |
| Round 11's checks against a copy of the task at 9433aa9 (`git archive`, with round 11's checks file) | round 11 | each of the seven fails on its own path: the last script still resolves links with `realpath` and has no alarm; the fixer relinks the 50-link chain's head instead of removing it; the fixer prints 6,894,000 bytes for 3,000 long-named links; the freeze runs past 10 s on a task in D and on a process that never stops; the timer never signals as the user (no call recorded) and the process that changes its pid survives; the pre-scan exits 1 on a name that is not UTF-8; a filesystem with no inode counts delivers the tree with a note. The agent-image check passes there as here (nothing to fix) |
| Re-check 08's M1 tree (16,000 leaves at 1,023-byte targets), the last script started 418 s after the hook, Python 3.12.13 | round 10's `reclaim-scratch` (9433aa9) and round 11's | 5.85 s, most of it inside the first link's one `realpath` (about 800 s at the platform's limits, per the re-check); 1.59 s, ended by the alarm. Both mark the tree refused |
| Round 10's checks against a copy of the task at 6a93903 (`git archive`, with round 10's checks file) | round 10 | each of the five hook checks fails on its own path: the climbing links kept as they were, a tree delivered though the step began 10,000 s earlier, a copy made with no room to spare, 10,050 lines printed for 10,050 pipes, a tree delivered with no room beside its record; the sentence check fails on the old sentence; the timer check measures 6.42 s from the fire to SIGKILL (twelve rounds of 0.5 s) against a bound of 5 s |
| The two reachable paths, reproduced on 6a93903's hook (Python 3.12.13, the image's minor version; tar, then tarfile's `data` filter) | a link climbing past `/` and back in, behind a 1,200-link chain whose head is at the top; one chain of relative links | the fixer ends at once (`RecursionError`), the tree is marked `delivered 1205 22`, the extract stops (`LinkOutsideDestinationError`) and `delivery_notes` raises "The copy arrived incomplete: 4 of 1,205 entries and 18 of 22 bytes"; the last script takes 5.95 s for 2,000 links, 24.4 s for 4,000 and 101.5 s for 8,000. On round 10's hook: the links are made direct and the copy arrives whole, with the notes |
| The verifier's three reworded comments | `verify.py` and `recorder.py`, round 9's first commit against its second | tokenize streams without COMMENT and NL tokens identical (6,817 and 5,502 tokens), same line counts; the new check fails on the first commit's comments |
| Round 9's new assertions against copies of the task with round 8's files | round 9 | each fails: round 8's solution (the probe and its logs), its packaging (no reduced cases or `build.txt`, `smoke.sh` in the solution), its `mark.py` (six lines written), its tools' comments (`apply.sh`, `scripts/build_original.py`); and a copy of the verifier that reads `source` |
| Local build of the hardened original | `scripts/build_original.py`, 2026-11-19 | builds (one warning); static, not PIE; marker once; no local path |
| `apply.sh` | a fresh export of v0.1.95 | applies once, refuses a second time; result identical to the patched tree that was built |
| `smoke.sh` | upstream's v0.1.95 macOS release binary; the hardened Linux binary in the image builds | fails at the first hardening check on upstream's build, as it must; passes in every image build of the versions uploaded so far, as root and as `dev` (a failure stops the build, and every one of those versions was built and graded) |
| Upstream's published builds | `scripts/upstream_builds.py`, 2026-11-19 | 21 executables in 3 release assets and 9 wheels, 12 distinct hashes; upstream's Linux build holds the unhardened usage text twice, the hardened build and the docs never |
| Local recording (the private cases, upstream's macOS release binary) | cases `91236578`, `experiment/local-recording-8` | 1,673 of 1,777 kept (83 display settings that change nothing, 17 last bits, 4 quoted); none unsteady, crashed, machine-dependent or perturbed; the strongest no-interpreter dispatcher 4.1% (command line 19, constants 17, error lookup 13, last literal 19), largest answer 0.6%, nothing with exit 1 0.6%; `∂` 6.1%; 40 of 41 piped cases end with exit 1 after a failing line |
| Local recording of the cases as round 9 ships them (without the generator's notes), the same binary | `cases.json` of bundle `bf77bf7f91d0` (the same file in `af0c9f7b084e`), `experiment/local-recording-9` | 1,673 of 1,777 kept with the same drops; `expected.json` byte-identical to `local-recording-8`'s; the same `kept_ids_sha256` (`bb030348…`) and `expected_sha256` (`ac7c2618…`); the same kinds, drops, settling, `kept_as_upstream_code` and baselines; the kept cases equal `local-recording-8`'s apart from `source`, `suite` and `family` |
| The shipped cases against the private file | bundle `bf77bf7f91d0` (the same file in `af0c9f7b084e`) | the same 1,777 cases in the same order; every key kept byte-identical; removed `source` (1,777), `suite` (1,383), `family` (260), `want` (1,324 records), `scaffold_lines` (248) |
| The packaged `solve.sh` with only `/app/rebuild` rewritten to a scratch directory; `mark.py` from the agent image's context with the marker | bundle `bf77bf7f91d0` (the same files in `af0c9f7b084e`) | the solution installs `bpl` (the build's own bytes, sha256 `60d2aed1…`, mode 0755) and `LICENSE`, nothing else, no standard error; the images' install writes the marker once and leaves no zero marker; `build.txt` beside either holds `link`, `sha256` and `sha256_without_marker` |
| Local grading from the packaged bundle (`af0c9f7b084e`, with `local-recording-9`; also `bf77bf7f91d0`, 34.4 s; the dispatcher's 0.0269 was measured on round 5's `1a08cdb471d0`, whose grading code is the same), through the collect hook's pre-scan and measuring scripts and a tar round trip with the `data` filter | stand-in reference behind a wrapper; no-op; the dispatcher as a program, with every strategy the recorder measures | 1.0 (1,673/1,673, 31.1 s); 0.0; 0.0269 (45/1,673: cli 19, error 13, expr 7, script 6) |
| A whole trial replayed from the packaged bundle with round 12's replays (`experiment/replay-r14/` for the fifth commit, whose set-up process gets no hosts to watch; `experiment/replay-r13/` for the fourth: the set-up runs leave the process that stops `dev` after the limit, the hook looks it up and ends it before its freeze; `experiment/replay-r12/` before it, a copy of round 11's, itself from QA 07e's through `replay-r8/`, which reads a flat or a steps bundle and has no timer; all Git-ignored, each with its reports and a `NOTE.txt`): both hooks' shell under `/bin/dash` (paths rewritten, stand-ins for `setpriv`, `pgrep`, `pkill`, `ps`, `fallocate`, GNU `stat` and `timeout`), tar and the `data` filter, then `verify.main()` with root and Linux stood in; the hook's order is read from its calls | round 12's flat `ab1a4f4ee269` (fifth commit), `da8966415695` (fourth), `c790a042f2be` (third), `7867414c5e86` (second) and `ad93859c8f45` against `local-recording-9`, with an executable copy of upstream's macOS release binary as the stand-in: reference; reference with planted `.manifest` names, links and a pipe (`ad93859c8f45` only); no-op | `ab1a4f4ee269`: 1.0 (1,673/1,673, 31.4 s); 0.0, `delivered 0 0`. `da8966415695`: 1.0 (1,673/1,673, 34.9 s); 0.0, `delivered 0 0`; nothing stopped (`stopped_after_limit` null), the process gone after the hook. `c790a042f2be`: 1.0 (1,673/1,673, 29.6 s); 0.0, `delivered 0 0`. `7867414c5e86`: 1.0 (1,673/1,673, 30.2 s); 0.0, `delivered 0 0`. `ad93859c8f45`: 1.0 (1,673/1,673, 30.4 s), no notes; 1.0 (33.1 s) with both moved-aside notes; 0.0, `delivered 0 0`; in each the freeze is the hook's first call, `work_end` is `turn_started` + 34,561 and `late_entries` 0. Round 11's `a9dad36c7bf0` (`replay-r11`), round 10's `ec8d6ecf327d` and round 9's `bf77bf7f91d0` (`replay-r8`) gave the same rewards |
| Packaging | `scripts/package_step.py`, twice into separate directories, with and without `--flat --keep-name` | flat `5be602ec5ec1` (round 14, the next upload), 246 files, 33,062,387 bytes, the same hash both times, Oddish content hash `358c7c75…`, against `ab1a4f4ee269` only `tests/verify.py`, `tests/verifier/runcases.py` and `tests/verifier/recording.py` changed (kept in `experiment/dist-check-38/`); flat `e9ee043b5d71` (round 13), 246 files, 33,056,657 bytes, the same hash both times, Oddish content hash `1d84bf20…`, against `ab1a4f4ee269` only `tests/verify.py`, `tests/verifier/runcases.py` and `tests/verifier/recording.py` changed (kept in `experiment/dist-check-37/`); flat `ab1a4f4ee269` (round 12's fifth commit, the v5 upload), 246 files, 33,050,911 bytes, the same hash both times, Oddish content hash `7ae8f22f…`, against `da8966415695` only `environment/provision-scratch` and `environment/reclaim-scratch` changed; steps `fbf917dc9b5c` (both kept in `experiment/dist-check-35/`); flat `da8966415695` (round 12's fourth commit), 246 files, 33,045,960 bytes, the same hash both times, Oddish content hash `15165600…`, against `c790a042f2be` `environment/provision-scratch`, `environment/reclaim-scratch` and `tests/verify.py` changed; steps `08b3e5d2b951` (both kept in `experiment/dist-check-34/`); flat `c790a042f2be` (round 12's third commit), 246 files, 33,041,785 bytes, the same hash both times, Oddish content hash `e4ef1a57…`, against `7867414c5e86` only `environment/reclaim-scratch` changed; steps `b92a1e095560` (both kept in `experiment/dist-check-33/`); flat `7867414c5e86` (round 12's second commit), 246 files, 33,040,988 bytes, the same hash both times, Oddish content hash `c283dd01…`, against `ad93859c8f45` only `environment/reclaim-scratch` changed; steps `d62e1a33fc60`, 33,041,140 bytes (both kept in `experiment/dist-check-32/`); flat `ad93859c8f45` (round 12's first commit), 246 files, 33,029,830 bytes, the same hash both times, Oddish content hash `e17c434c…`; steps `8ea1e9bf08ec`, 246 files, 33,029,982 bytes, the same hash both times, content hash `ad5f525b…`; against v4's `d365dc33100d` (content hash `e8d69ae8…`), `environment/session-timer` removed and `environment/Dockerfile`, `environment/reclaim-scratch`, `task.toml` and `verify.py` changed. Earlier: `d365dc33100d`, 247 files, 33,034,058 bytes, the same hash both times; `f93f6c391545`, whose content hash is `a9dad36c7bf0`'s (`e6d06775…`); `a9dad36c7bf0`, 247 files, 33,034,283 bytes; bundle directory `swe-m2_software-engineering_basedpl-interpreter-rebuild-no-examples` |
| Oddish preflight | bundles `bf77bf7f91d0`, `af0c9f7b084e`, `ec8d6ecf327d`, `a9dad36c7bf0`, `f93f6c391545`, `d365dc33100d` and the flat `ad93859c8f45`, `7867414c5e86`, `c790a042f2be`, `da8966415695`, `ab1a4f4ee269`, `e9ee043b5d71` and `5be602ec5ec1`, no-Archil CLI, locally | pass |
| Oddish baselines and the pre-trial audit | old name: v1, and v2 (round 5's `1a08cdb471d0`); new name: v1 (round 8's `43b39e11805c`), v2 (round 9's `af0c9f7b084e`), v3 (round 11's `a9dad36c7bf0`) and v4 (`d365dc33100d`) | old name: the reference 1.0 twice per version (1,673/1,673) and the no-op 0.0 twice, with the same `kept_ids_sha256` (`bb030348…`) and `expected_sha256` (`18af6936…`) in both versions, so the Linux recording reproduces; v2's three model trials were graded. New name v1: the reference 1.0 twice, the no-op 0.0 twice, and the audit's one must-fix (the probe), answered in round 9. New name v2: the reference 1.0 twice, the no-op 0.0 twice, an empty source audit, three model trials graded (0.366, 0.372, 0.149), and the verdict's one must-fix (the timer), answered in round 10. New name v3: the reference 1.0 twice, the no-op 0.0 twice, and the audit's one must-fix (`task.toml`'s comment), answered in round 11's second commit. New name v4: three model trials graded (0.383, 0.402, 0.037) and the verdict's one must-fix (the timer again), answered in round 12. New name v5 (round 12's flat `ab1a4f4ee269`): the reference 1.0 twice, the no-op 0.0 twice, a clean pre-trial audit, three model trials graded (0.506, 0.056, 0.237), and the verdict's two must-fix adversarial findings (launchers that run nothing), answered in round 13. Bundles `ad93859c8f45`, `7867414c5e86`, `c790a042f2be`, `da8966415695`, `e9ee043b5d71` and `5be602ec5ec1`: not run |
| `harbor check` | none | not run |

### Validation gaps

The checks and the replay run on macOS as an ordinary user, so locally these are read, not run
(re-check 07e, F2, F3 and F7). The platform's baselines of every version uploaded so far ran them
on Linux and as root, and were graded (see [Validation](#validation)); their logs have not been
read item by item:

- **The hardened Linux binary.** Its smoke test, as root and as `dev`, passes at every image build
  so far (a failure stops the build).
- **The hooks' shell under the real tools.** Every shell line of `provision-scratch` and
  `reclaim-scratch` runs in a check (under this machine's `sh`) and in the replay (under dash),
  but with stand-ins for `setpriv`, `kill -STOP -1` and `kill -9 -1` as `dev`, procps `pgrep -r`
  and `pkill -u`, `ps -eo ...etimes...`, `fallocate`, GNU `stat -f -c` and `timeout`; the loops
  that freeze and end `dev`'s processes therefore see none.
- **A session that runs to its limit.** The end of the work is checked here with stand-in
  sessions (the capped-turn checks), never on the platform: that the collect hook runs while the
  agent's exec still runs; how many seconds pass between `setup_complete`, which writes
  `turn-started`, and the start of the run's clock (the end falls that much early); and whether
  gVisor's overlay moves an entry's change time on a rename, as ext4 does. A late deletion cannot
  be undone. Each only takes from the session's own work.
- **The stop after the limit.** Run here against a stand-in `/proc` whose clock the checks move
  (`uptime`, each process's `stat` and `status`), with stand-ins for `pgrep -r` and `kill -STOP -1`
  as `dev` (macOS has neither, nor `setsid`), and a local port for the hosts. Not seen on the
  platform: that the process outlives the set-up hook's exec (the earlier root process of rounds
  5-11 did, started the same way); gVisor's `/proc/<pid>/stat` start times against its `uptime`;
  that the agent's first process is the child of root's `su` there; that pypi.org and github.com
  resolve at set-up and answer once harbor reopens the network; procps' `pgrep -r R,S,D` and
  `setpriv`. A first capped model trial shows it in `stopped_after_limit`.
- **What the frozen processes hold, read from `/proc`.** Run here against a stand-in `/proc`
  (macOS has none). Not seen on the platform: whether gVisor lets root read `dev`'s `maps` and
  descriptors (on a plain Docker host root may not, and the run as `dev` reads all but set-id and
  undumpable processes); the format of gVisor's `fdinfo` flags and `maps` lines; and the path that
  `maps` shows for a file of an overlay, which older Linux kernels give as the backing file's (the
  path then fails to match, and the device and inode match only where they are the overlay's; a
  descriptor's own `stat` always gives the overlay's).
- **The verifier as root.** `sandbox()`, `probe()` and `main()` now run in a check, with these
  stood in: the real `setpriv` drop, `chown` to another uid, the set-id copy of `id` owned by
  root, `kill -KILL -1` and `ipcrm` as the run's user, and `find -user`. Not executed at all on
  macOS: `kill_user` past its listing of `/proc`, `reap()`, `limit()`'s process limit and
  `oom_score_adj` as root, and the `/proc` readers of `runcases.own_use`, `alive` and
  `memory_in_use` (they return "cannot tell" without `/proc`).
- **The platform.** Grading after a capped run of the flat bundle (SymPy's flat capped runs were
  graded, 3 of 3; the cap probe runs both layouts); the egress window between the turn and the
  hook; the pre-trial audit.
- **The collect hook's limits on the platform's kernel.** The 420 s and 510 s limits, the alarm,
  the 15 s loop limits, the fixer's room checks and the byte caps run here with stand-ins for a
  full disk (`statvfs` answers), for `pgrep`, `setpriv`, `pkill` and `ps`, and with this Mac's
  syscall costs and its 1,023-byte link targets (Linux allows 4,095); gVisor's costs are higher,
  which makes a hostile tree reach the 420 s sooner and changes nothing for an honest tree
  (seconds in every trial so far). No small filesystem was mounted, so ENOSPC itself was never
  hit; a name that is not UTF-8 was stood in (this Mac's filesystem refuses one). A task held in D
  by `vfork` was read from the kernel's sources (by the re-check), not made.

**Reading the first oracle and no-op trials** (before any model trial). In `metrics.json`:

- `cases_total` equals the image's kept count, `setup_errors` is 0 and `seconds_total` is above 0
  (the sibling task's failure was every case a setup error in 0.0 s).
- From round 14: `distinct_outputs_needed` is 10; the oracle's `distinct_outputs` equals
  `recording.baselines.distinct_outputs_kept` (1,421 locally), its `withheld` is null and its `notes`
  stay empty; the no-op's `distinct_outputs` is 0, with only the missing-program note and a
  `reward:` line without one; `recording.baselines.no_interpreter_dispatcher_distinct_outputs` is 3
  at most (2 locally), or the image would not have built.
- `delivery_record.delivered` is `delivered 2 <bytes>` for the oracle and `delivered 0 0` for
  the no-op; `notes` is empty for the oracle.
- `delivery_record.stopped_after_limit` is null (the reference and the no-op end long before the
  limit); in a model trial that reaches the limit it names the session's first process and its
  start, and shows the stop (`at`) at or after `due` (that start + 34,562 s) and after
  `network_back`, with `still_running` 0; set `at` beside harbor's `agent_execution.finished_at`.
- `delivery_record.work_end` is `turn_started` + 34,561 and `late_entries` is 0, and the trial's
  `result.json` holds no `step_results` (the flat bundle ran).
- `fixer_status`, the link fixer's exit status, is a key of the record `.manifest.json` in the
  collected `/app/rebuild`, not of `metrics.json`: `verify.py` copies a fixed list of the record's
  keys into `delivery_record` and is not changed for it. A status other than 0 does reach
  `metrics.json`, as the note `the link fixer ended with status N: …` (in `notes`, after
  `maintenance step: `, and in `delivery_record.notes`). A fixer that ended with 0 leaves no
  trace there, so the oracle's empty `notes` also means status 0.
- From round 9, `recording.cases_recorded` and `cases_kept` stay 1,777 and the image's kept count,
  `recording.build` holds only `link`, `sha256` and `sha256_without_marker`, and the reference's
  `solve.sh` prints only `mark.py`'s three lines and writes nothing under `/logs/agent` (no
  `probe.txt`, `reads.txt`, `smoke.txt` or `build.txt`).

## Build and deliver

```bash
git clone https://github.com/AnswerDotAI/basedpl <checkout>     # any branch; the commit is read by hash
python scripts/build_original.py --checkout <checkout>         # once: experiment/build/bpl, build.txt
python scripts/make_cases.py <checkout>                        # private cases from experiment/seeds.json
BASEDPL_CHECKOUT=<checkout> python scripts/package_step.py --flat --keep-name  # the upload: no steps, the same name
python scripts/upstream_builds.py                              # only when upstream's 0.1.95 files change: their hashes
```

The case seed and the build marker come from `experiment/seeds.json`, which `scripts/seeds.py`
makes once at random and which is never committed: anyone with the generator, upstream's
checkout and the seed could regenerate the hidden cases. The build needs Rust 1.100.0 with the
`x86_64-unknown-linux-musl` target, zig and `cargo-zigbuild`; packaging refuses a binary whose
sha256 is not build.txt's. Packaging ships the private cases without the generator's notes, and
`build.txt` with only its `link` and `sha256` lines; the full files stay where they are made.

## Remaining work

- Round 14 (the count re-check 10 asked for, after round 13's rule zeroed v4's `-33`) has an
  independent re-check before anything goes up. Then the flat bundle `5be602ec5ec1` goes up as the
  next version of the same task (v6), under the task's one experiment, on the owner's word. Its baselines and pre-trial
  audit come before any model trial. The two oracle trials on different workers are a hard gate:
  each must score exactly 1.0, with the same `kept_ids_sha256` and `expected_sha256` (`bb030348…`
  and `18af6936…` so far; `recorder.py`, the runner code it uses and the cases are unchanged, and
  `runcases.py` only gains the two counting functions, so the same answers are expected). A failed
  id goes on a deny-list and the cases are recorded again. Then the no-op,
  which must score exactly 0. Read `recording` in the reference run's `metrics.json` (drops by
  reason, settling, `kept_as_upstream_code`, the baselines with the two distinct-output counts,
  the build), `distinct_outputs`, `withheld`, and `delivery_record` as listed under Validation gaps.
  In every model trial, read `distinct_outputs` beside the reward: a run below 10 scores 0 with the
  note on its `reward:` line.
- Round 12's re-checks (CONCERN, no must-fix each) had their should-fixes answered in its second
  and third commits (R1b stays a documented residual) and the stop after the limit added in its
  fourth and fifth; its bundle `ab1a4f4ee269` went up as v5 (development log, round 13).
- Watching the first model trials (the judges' list): about 15 minutes after a cap, the trial
  should end with a reward and a `result.json` without `step_results`. A capped trial that ends
  with "Agent execution timed out" and no reward is reported as lost, never as 0: read attempt
  1's `oddish-mon.log` for a `docker.compose_build` RuntimeError or `startup_retry phase=build`,
  and start nothing more until the cap probe reports. In every capped trial, read `work_end`,
  `late_entries` and the mark's `removed …` notes.
- Read the probe's records from the reference trials that ran it (`/logs/agent/probe.txt` and
  `reads.txt`, every version before round 9), for hackability rows 1 and 17, and the old name's
  v2 model trials' `delivery_record` for row 3.
- Audit every trial before its score is recorded, per the egress-window decision: survivors and connectivity
  in `delivery_record`, and deliverable ctimes later than the agent's turn.
- A static PIE: build with a linker that produces `-static-pie` for musl (rust-lld with Rust's
  self-contained musl, or a Linux builder), then rebuild every image from that binary.
- `harbor check` and ratings.
- Shelf life (QA 20 item 4): the cases suit models trained before 2026-09-16, when BasedPL was
  first published. `core.bpl` supplies most of them, and the generator goes public with this
  branch. Check recall before reading a score from any model trained later, and plan a re-seed
  with new templates when that happens.
- Notices (QA 20 item 6): only upstream's `LICENSE` ships beside the redistributed binary. Before
  bundles leave Abundant, generate third-party notices for the 281 statically linked crates
  (`cargo about`) into `/app/docs` and the solution.
