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
(the session timer stopped the agent 660 s before the stated limit), answered in round 10 with the
completion sentence reworded and a sweep of what a tree can do to the copy, and round 10's
re-check in round 11. Bundle `a9dad36c7bf0` (round 11) replaces it; round 10's `ec8d6ecf327d` was
never uploaded; round 9's `5eef6fadb546` and `bf77bf7f91d0`, round 7's `b206089bd38b` and
round 6's `ffcf88e892e2` were never uploaded, and the earlier bundles are `4164eb806274`,
`7462d71fe5a7`, `f0da94435d6b`, `cfc9d42f3e68`, `80d7f600cab8` and `1a08cdb471d0`. See
[Remaining work](#remaining-work) and [Validation gaps](#validation-gaps).

## Development log

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
share of cases that match.

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

A run is one trial (one task row per experiment, no continuation tasks): the session ends at
33,900 s (9.42 h), and the agent's limit in `task.toml` is 33,960 s. The instruction states no
time budget.

**Run condition: the session timer.** A root timer (`session-timer`) started at `setup_complete`
ends the agent's session at 33,900 s: SIGTERM to every process of `dev` in six rounds 5 s apart
while any is seen, then SIGKILL in twenty rounds 0.5 s apart, which always run, so nothing of
`dev` is left at about 33,930 s. Each round signals as `dev` too, with `kill -1`, one system call
that reaches every process of it (a process that keeps changing its pid included, which no
listing sees; round 11). The agent's `timeout_sec` (33,960 s, at the top level and in the step) is a backstop 60 s
later, with a comment beside each for the platform's reviewers. The timer exists because on the
platform a turn that runs into the cap is never graded (the separate verifier image fails to
build right after the timeout; harbor-lh
`ops/swe-marathon-v2/PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`) while a turn that ends by itself
is. Until round 10 the limit was 34,560 s and the timer stopped the agent 660 s before it, which
v2 under the new name was rejected for; the judges kept the stop point and moved the stated limit
(option B of harbor-lh `ops/swe-marathon-v2/decisions/2026-11-20-precap-timer-vs-deadline-DECISION.md`).
A session it ended shows as `ended_by_timer: true` in `metrics.json`. The collect hook first
writes the mark the timer stops on, then freezes `dev`'s processes and ends the timer, so none of
its rounds can reach the hook's own work as `dev`. The agent is not told; the instruction states
no budget either way. The installed scripts and their state are
named for ordinary housekeeping (`provision-scratch`, `reclaim-scratch`, `session-timer`,
`/var/lib/scratch`) so that a solver listing the container reads nothing about grading, a cap or a
deadline from them. One thing does show: `ps` lists root's `session-timer run` and its
`sleep 33900` (07e, a remark, not changed here; the Goose task sleeps in one-minute steps so that
the number shows nowhere).

## Verification

1. **Collection.** When the agent's turn ends, the root collect hook writes the mark the session
   timer stops on, freezes `dev`'s processes, ends the timer, lists the processes and kills them,
   records every entry's own times before touching anything, and records connectivity. It
   restores permissions only where needed (directories u+rwx, unreadable files u+r, each noted),
   fixes links (a link to a root-owned system file or directory becomes a copy when the disk has
   room to spare for it, with the source's path, owner, times and inode recorded; a link to
   anything else outside is removed and noted first in the mark; a link inside is made direct,
   read by name against the walk's own listing, and one through another link is removed), bounds
   `/app/rebuild`, packs it once as the copy will, with room left for its record and mark, and
   marks and records it with the pre-hook times as the authoritative ones. A tree it cannot
   measure within 420 s of its start (an alarm ends the walk and the links then, inside any call),
   or pack by 510 s, is refused; the freeze and the kill stop after 15 s each, and what the hook
   writes is bounded in bytes, so it ends with a mark within its 600 s, on a full disk too (see
   the development log, rounds 3-4, 10 and 11). Harbor then copies `/app/rebuild`, the declared
   artifact, into the verifier.
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
   passes a limit fails; none of that is an evaluation error.
5. **Deadline.** One deadline, 4,200 s from the start, covers sealing, scans, cleanup and cases;
   the cases left count as failed. At the end the verifier cleans up, writes the reward into its
   reserved file, renames it onto `reward.txt`, then writes `metrics.json`.

### Reward formula

```
reward = cases_passed / cases_kept
```

- Continuous, fixed denominator per image build (the private cases kept by the recording).
  No executable: reward 0.
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
| 5 | Fetch the public source, upstream's tests or a published build, including in the window after the turn when the platform reopens connectivity | Agent network; the collect hook; the refusals of row 4 | QA 04 and 08 (platform finding `PLATFORM_EGRESS_WINDOW.md`); decision 2026-11-19 (A, with conditions) | `network_mode = "no-network"` for the turn; the root collect hook kills every process of `dev` before anything is copied and records whether connectivity was open and what was running (`delivery_record`); published builds and the unhardened usage text are refused; no upstream source, test, notebook result or design note in the image | The window stays open until the platform keeps the agent-phase policy through collection; a transformed fetched build escapes the refusals; a harness with network access would defeat the task | Audit every trial (`delivery_record`: survivors, connectivity, ctimes after the turn) before its score is recorded | 🟡 YELLOW / UNASSESSED |
| 6 | Look up answers from what is shipped | Case generation | Checked on a stand-in upstream and on the real files at packaging; QA 06 and 12b | No example runs ship; no case holds a documented program or a near-copy, in any rewrite the recorder may settle on (whole blocks, statements and runs of 2-6 statements; 311 core records left out); `make_cases.leaks` runs again at packaging | The documentation's examples teach behaviour by design: about three quarters of its runnable one-liners state their displayed value in a comment, so replaying them is the agent's first corpus; three worker requests are near-copies of documented one-liners with the same value, one reply each in sessions of about ten | Keep | 🟢 GREEN / LOW |
| 7 | Read an answer out of the case's own input | Generation and recording | Checked | Comments removed from upstream's code (some state results); the recorder drops a case whose input holds its whole answer (5 in the local recording) | Short answers a program spells out literally | Read `dropped` in `recording.json` | 🟢 GREEN / LOW |
| 8 | Recall upstream's published expectations | Rewrites | Local recording: 248 of 1,739 kept cases in upstream's code form | Names, value literals and prose words rewritten under the private seed; the recorder prefers rewrites that change the answer; `recording.json` counts the cases still in upstream's form (`kept_as_upstream_code`, mostly error records, whose messages are the same for any implementation) | BasedPL was published 2026-09-16; models trained later may know it, and its reference files | Read `kept_as_upstream_code`; re-check for models trained after 2026-09 | 🟢 GREEN / LOW |
| 9 | Tamper with the reward files, or suppress them by forcing an evaluation error | Separate verifier container | Goose QA passes 07, 07b, 10, 10b, round 6 (the same verifier) | No reward exists until the real end (`.reward.tmp` renamed onto `reward.txt`); bounded, link-refusing reads; one deadline; capped submissions; `rm -rf` sweeps; every per-case exception a failed case; host disk shortages are errors only after the sweep has taken back everything the uid held (checked) | Kernel keyrings survive between cases; they carry no answer | Keep | 🟢 GREEN / LOW |
| 10 | Infer an evaluation from the files and text | Instruction and image | Checked: no grading, hidden, budget or session wording; no examples or runner shipped | Neutral requester text | An agent can still guess that more programs exist | Read the first trajectories | 🟡 YELLOW / UNASSESSED |
| 11 | Run as root in the verifier through a set-id or capable file | Privilege drop and sealing | Goose QA pass 10 F6 | Sealed root-owned without set-id bits; `setpriv --no-new-privs`; the drop is checked by status or `prctl` and a set-id `id`, or nothing is graded (checked) | A kernel that ignores no_new_privs; the probe then refuses to grade | First baseline's verifier log | 🟢 GREEN / LOW |
| 12 | Pass cases with no interpreter: the command line's answers, echoed literals, the generator's lead forms, the last strand of a program, an error-message lookup, constant answers per visible shape | Case mix and selection | QA 02, 05, 13, 17 measured 5.5-7.3% on the first cases; the round-2 re-check 2.8% by echoes and 5.7% with a lookup trained on hidden data; local recording now: 4.1% by the recorder's union of every strategy, 2.7% when the dispatcher is run as a program | Leads are one-line value records of the pool; uncaught errors mostly graded through the worker's reply with message and span; handlers always print the message; any one answer capped at 1.5%; `select` holds the strongest dispatcher (`recorder.no_interpreter`, every strategy above) to 5% and the recorder fails the build above it | Display of simple literals is legitimate early work; the lookup's share is a bound no submission reaches | Read `baselines.no_interpreter_dispatcher_by_strategy` in the first baseline's `metrics.json` | 🟢 GREEN / LOW |
| 13 | A crash of the original graded as an answer | Recording | Checked with a stand-in | Signals, exit statuses other than 0, 1 and 2, panics and allocation failures are dropped; more than 2% fail the build | None found | Read `dropped_crashed` | 🟢 GREEN / LOW |
| 14 | Answers that depend on the machine or on the maths library's last bits: thread counts, hash order, the memory limit, CPU features, approximation bits | Recording | Local recording: no case unsteady or perturbed; 16 last-bit answers dropped (QA 18 confirmed 12) | Three runs pinned to four worker threads and a perturbed one (one CPU, one worker thread); memory-limit text dropped from either stream; last-bit answers dropped; rustymath chooses SIMD paths at compile time (`x86-64-v3`); `expected_sha256` lets two builds be compared | A host without AVX2 cannot run the original (the smoke test then fails the build, and an oracle row below 1.0 with `host.avx2` false is infrastructure); the x86-64 build's bits are first seen at its own recording | Two oracle trials must each score 1.0 with the same `kept_ids_sha256` and `expected_sha256` before any model trial | 🟡 YELLOW / UNASSESSED |
| 15 | A busy host fails a graded run spuriously | Disk and file limits | QA 10: a `sleep 10` submission was stopped for a file limit by the whole-filesystem figures | The limits count only the run's own files (its uid's under the writable directories, and deleted files it holds open), and only when the free figures fall past a limit; a case stopped by a limit runs once more; host shortages after a sweep are evaluation errors | None found | Read `disk_limits`, `file_limits` and `limit_retries` in the first trials' `metrics.json` | 🟢 GREEN / LOW |
| 16 | Make Harbor's copy drop an honest delivery (a running build, links that leave the directory, FIFOs, a sparse file, a full disk, a read-only folder) so that it scores a valid 0, make the copy fail at will (a link that climbs past `/` and back, a chain of links that holds the hook past its 600 s, a disk filled so that the hook's own record or the copy's pack has no room), launder a file fetched after the turn through a link the hook copies in, or hide a post-turn write behind the hook's own changes to ctimes | The collect hook and the mark | QA 07 F2-F3 (ported from the back-office task, rounds 6-7); Carve QA 04 F1-F2; re-checks 07b and 07c; round 10, with Carve QA 22 and 23 as the catalogue (two paths reproduced on 6a93903); re-check 08 (M1, M2, S1, S3, S4: round 11) | The hook freezes and kills `dev`'s processes first, records every entry's own times before touching anything (the manifest's authoritative mtime and ctime), gives back reserved room and inodes, restores permissions only where needed and notes each change, copies an outside link's target only when root owns it (every file under a directory included) and the disk keeps room to spare, and records the source's path, owner, mtime, ctime and inode, removes every other outside link (noted first in the mark) and all special files, lets the system resolve a link before the fixer follows it, reads every link of the last script by name against its own listing (no call follows a link; one through another link is removed) and keeps a link inside only as the direct relative path to what it reaches, bounds entries, bytes and path length, hashes once per inode, refuses a tree not measured within 420 s of its start (an alarm ends any call then), packs once within 100 s and by 510 s with room for its record and mark beside it, and marks the delivery; the fixer prints 2 MiB at most, each script's own notes take 64 KiB and the mark's 32 KiB, names cut to a few hundred bytes, the rest counted; a refused tree's record counts what it held and lists only the first notes; the verifier grades what arrived, reads 1 MiB of the mark, copies every change into `metrics.json` with flags, and treats nothing arriving or a short copy as an evaluation error, which after a completed hook only the copy itself can cause | A platform copy that fails after the hook's own pack succeeded (an error, then a re-run); the refusal renames `/app/rebuild`, which overlayfs without `redirect_dir` refuses (gVisor's overlay does not; QA 08 N1); a fetched file written straight into `/app/rebuild` after the turn, which the ctime audit against the trial's finish now can catch, since the recorded ctimes are the session's own | Read `delivery_record` (copies, links, notes, `latest_ctime` and `hook_changed_entries` against the trial's finish) in every trial | 🟢 GREEN / LOW |
| 17 | Read the build's own file through the hardened read path from a start directory whose rule lets it through (`/`, `/opt`, `/opt/bpl`) | File mode; the path rule | QA 04 F4, QA 12 F2 | The 2711 mode refuses the read for `dev`; the agent image's final stage proves it as `dev` at every build (with the whole smoke test on the set-group-id build; a failure stops the build) | A kernel that let a non-dumpable set-group-id process read its own executable | Every image build; `/logs/agent/reads.txt` of the reference trials before round 9 (the same reads at run time), not read yet | 🟢 GREEN / LOW |
| 18 | Outlast the session timer, so that the session runs into the platform's cap and goes ungraded, or stop it to gain time | Process ownership | Round 5; re-check 07e | The sleeper is root's and `dev` cannot signal it; its pid file, log and the hook's mark are root-only (`/run`, `/var/log`, `/var/lib/scratch`); `kill -TERM` then `kill -KILL` reach every process of `dev`, by its selection as root and, in every round, as `dev` with `kill -1` (one system call, so a process that keeps changing its pid is ended too; round 11, re-check 08 S2) | A harness that ran the agent as root, which hackability row 3 gates on the first trial | Read `ended_by_timer` and `timer_log` in `delivery_record`: `armed pid N` first, then `stopped pid N` when the hook found the sleeper still running, or `fired after 33900 s` when it ended the session | 🟢 GREEN / LOW |
| 19 | The session timer's own rounds end the collect hook's link fixer, which runs as `dev`: links not yet fixed are then removed and honest work scores 0, with notes that read like the agent's fault | The collect hook and the timer | Re-check 07e F1 (reproduced with the unmodified timer); 07f G1 (the order) | The hook writes a root-only mark first, freezes `dev`'s processes, then ends the sleeper (SIGSTOP, its children, SIGKILL), all before its own work as `dev` (the link fixer); the timer stops on the mark before it fires and before every round; a fixer that does not end with status 0 is noted in the mark (checked: the hook's real fixer under a timer in its rounds, ended without the hook's first lines, finishing 20,000 links with them) | The real `setpriv`, procps and `/proc` have not run yet (Validation gaps) | `timer_log` and `notes` in the first trials' `delivery_record` | 🟢 GREEN / LOW |

Licence: the upstream is Apache-2.0. Its `LICENSE` is shipped with the documentation in
`/app/docs` and with the reference solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (67 tests) with `ci_checks` (27), Python 3.13, and `check_repository.py` | round 11 (`9ee0898`) | pass |
| Round 11's checks against a copy of the task at 9433aa9 (`git archive`, with round 11's checks file) | round 11 | each of the seven fails on its own path: the last script still resolves links with `realpath` and has no alarm; the fixer relinks the 50-link chain's head instead of removing it; the fixer prints 6,894,000 bytes for 3,000 long-named links; the freeze runs past 10 s on a task in D and on a process that never stops; the timer never signals as the user (no call recorded) and the process that changes its pid survives; the pre-scan exits 1 on a name that is not UTF-8; a filesystem with no inode counts delivers the tree with a note. The agent-image check passes there as here (nothing to fix) |
| Re-check 08's M1 tree (16,000 leaves at 1,023-byte targets), the last script started 418 s after the hook, Python 3.12.13 | round 10's `reclaim-scratch` (9433aa9) and round 11's | 5.85 s, most of it inside the first link's one `realpath` (about 800 s at the platform's limits, per the re-check); 1.59 s, ended by the alarm. Both mark the tree refused |
| Round 10's checks against a copy of the task at 6a93903 (`git archive`, with round 10's checks file) | round 10 | each of the five hook checks fails on its own path: the climbing links kept as they were, a tree delivered though the step began 10,000 s earlier, a copy made with no room to spare, 10,050 lines printed for 10,050 pipes, a tree delivered with no room beside its record; the sentence check fails on the old sentence; the timer check measures 6.42 s from the fire to SIGKILL (twelve rounds of 0.5 s) against a bound of 5 s |
| The two reachable paths, reproduced on 6a93903's hook (Python 3.12.13, the image's minor version; tar, then tarfile's `data` filter) | a link climbing past `/` and back in, behind a 1,200-link chain whose head is at the top; one chain of relative links | the fixer ends at once (`RecursionError`), the tree is marked `delivered 1205 22`, the extract stops (`LinkOutsideDestinationError`) and `delivery_notes` raises "The copy arrived incomplete: 4 of 1,205 entries and 18 of 22 bytes"; the last script takes 5.95 s for 2,000 links, 24.4 s for 4,000 and 101.5 s for 8,000. On round 10's hook: the links are made direct and the copy arrives whole, with the notes |
| The session timer at full scale (its own 5 s rounds, fire after 2 s) | round 10; a stand-in that ignores SIGTERM and one that does not | SIGTERM ends the second at the fire; SIGKILL ends the first 30.22 s after it; `done: 0 process(es)` |
| The verifier's three reworded comments | `verify.py` and `recorder.py`, round 9's first commit against its second | tokenize streams without COMMENT and NL tokens identical (6,817 and 5,502 tokens), same line counts; the new check fails on the first commit's comments |
| Round 9's new assertions against copies of the task with round 8's files | round 9 | each fails: round 8's solution (the probe and its logs), its packaging (no reduced cases or `build.txt`, `smoke.sh` in the solution), its `mark.py` (six lines written), its tools' comments (`apply.sh`, `scripts/build_original.py`); and a copy of the verifier that reads `source` |
| The order check against a copy with round 7's order (the timer's end before the freeze) | round 8 | the new order check fails (its freeze found "timer ended") and so does the delivery check's order list; the F1 check passes |
| Local build of the hardened original | `scripts/build_original.py`, 2026-11-19 | builds (one warning); static, not PIE; marker once; no local path |
| `apply.sh` | a fresh export of v0.1.95 | applies once, refuses a second time; result identical to the patched tree that was built |
| `smoke.sh` | upstream's v0.1.95 macOS release binary; the hardened Linux binary in the image builds | fails at the first hardening check on upstream's build, as it must; passes in every image build of the versions uploaded so far, as root and as `dev` (a failure stops the build, and every one of those versions was built and graded) |
| Upstream's published builds | `scripts/upstream_builds.py`, 2026-11-19 | 21 executables in 3 release assets and 9 wheels, 12 distinct hashes; upstream's Linux build holds the unhardened usage text twice, the hardened build and the docs never |
| Local recording (the private cases, upstream's macOS release binary) | cases `91236578`, `experiment/local-recording-8` | 1,673 of 1,777 kept (83 display settings that change nothing, 17 last bits, 4 quoted); none unsteady, crashed, machine-dependent or perturbed; the strongest no-interpreter dispatcher 4.1% (command line 19, constants 17, error lookup 13, last literal 19), largest answer 0.6%, nothing with exit 1 0.6%; `∂` 6.1%; 40 of 41 piped cases end with exit 1 after a failing line |
| Local recording of the cases as round 9 ships them (without the generator's notes), the same binary | `cases.json` of bundle `bf77bf7f91d0` (the same file in `af0c9f7b084e`), `experiment/local-recording-9` | 1,673 of 1,777 kept with the same drops; `expected.json` byte-identical to `local-recording-8`'s; the same `kept_ids_sha256` (`bb030348…`) and `expected_sha256` (`ac7c2618…`); the same kinds, drops, settling, `kept_as_upstream_code` and baselines; the kept cases equal `local-recording-8`'s apart from `source`, `suite` and `family` |
| The shipped cases against the private file | bundle `bf77bf7f91d0` (the same file in `af0c9f7b084e`) | the same 1,777 cases in the same order; every key kept byte-identical; removed `source` (1,777), `suite` (1,383), `family` (260), `want` (1,324 records), `scaffold_lines` (248) |
| The packaged `solve.sh` with only `/app/rebuild` rewritten to a scratch directory; `mark.py` from the agent image's context with the marker | bundle `bf77bf7f91d0` (the same files in `af0c9f7b084e`) | the solution installs `bpl` (the build's own bytes, sha256 `60d2aed1…`, mode 0755) and `LICENSE`, nothing else, no standard error; the images' install writes the marker once and leaves no zero marker; `build.txt` beside either holds `link`, `sha256` and `sha256_without_marker` |
| Local grading from the packaged bundle (`af0c9f7b084e`, with `local-recording-9`; also `bf77bf7f91d0`, 34.4 s; the dispatcher's 0.0269 was measured on round 5's `1a08cdb471d0`, whose grading code is the same), through the collect hook's pre-scan and measuring scripts and a tar round trip with the `data` filter | stand-in reference behind a wrapper; no-op; the dispatcher as a program, with every strategy the recorder measures | 1.0 (1,673/1,673, 31.1 s); 0.0; 0.0269 (45/1,673: cli 19, error 13, expr 7, script 6) |
| A whole trial replayed from the packaged bundle with round 8's replay (round 8's is a copy of round 7's, itself QA 07e's, adapted to round 8's order; kept in the Git-ignored `experiment/replay-r8/`, the reports and a `NOTE.txt` in `results-r9/` and `results-r10/`; round 11's copy, `experiment/replay-r11/`, follows the freeze's `R,S` and the SIGKILL rounds that always run, with its reports in `results/`): both hooks' shell under `/bin/dash` (paths rewritten, stand-ins for `setpriv`, `pgrep`, `fallocate`, GNU `stat` and `timeout`), the real timer against stand-in processes, tar and the `data` filter, then `verify.main()` with root and Linux stood in; the hook's order is read from its calls | round 11's `a9dad36c7bf0` (with `replay-r11`; round 10's `ec8d6ecf327d` with `replay-r8`, the same results) against `local-recording-9`, with an executable copy of upstream's macOS release binary as the stand-in (as before, `bf77bf7f91d0`): reference; reference with planted `.manifest` names, links and a pipe; no-op with a sleeper still waiting | 1.0 (1,673/1,673, 28.3 s), no notes, `ended_by_timer` true, the dummy that ignores SIGTERM ended by SIGKILL after six rounds; 1.0 with both moved-aside notes; 0.0, `delivered 0 0`: both freezes sent with the mark written and the sleeper running, then the hook ended the sleeper and its `sleep` (`stopped pid N` in `timer_log`). The same results on `bf77bf7f91d0` in round 9 |
| Packaging | `scripts/package_step.py`, twice into separate directories | `a9dad36c7bf0`, 247 files, 33,034,283 bytes, the same hash both times; bundle directory `swe-m2_software-engineering_basedpl-interpreter-rebuild-no-examples`; against round 10's `ec8d6ecf327d` only `environment/session-timer` and `environment/reclaim-scratch` changed; against v2's `af0c9f7b084e`, those two, `task.toml` and the instruction, every other file byte-identical (the verifier image's context among them) |
| Oddish preflight | bundles `bf77bf7f91d0`, `af0c9f7b084e`, `ec8d6ecf327d` and `a9dad36c7bf0`, no-Archil CLI, locally | pass |
| Oddish baselines and the pre-trial audit | old name: v1, and v2 (round 5's `1a08cdb471d0`); new name: v1 (round 8's `43b39e11805c`) and v2 (round 9's `af0c9f7b084e`) | old name: the reference 1.0 twice per version (1,673/1,673) and the no-op 0.0 twice, with the same `kept_ids_sha256` (`bb030348…`) and `expected_sha256` (`18af6936…`) in both versions, so the Linux recording reproduces; v2's three model trials were graded. New name v1: the reference 1.0 twice, the no-op 0.0 twice, and the audit's one must-fix (the probe), answered in round 9. New name v2: the reference 1.0 twice, the no-op 0.0 twice, an empty source audit, three model trials graded (0.366, 0.372, 0.149), and the verdict's one must-fix (the timer), answered in round 10. Bundles `ec8d6ecf327d` and `a9dad36c7bf0`: not run |
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
  that freeze and end `dev`'s processes therefore see none. The timer's end runs with BSD `ps`
  and `pkill`; procps' `ps -ww -o args= -p` and `pkill -KILL -P` are read.
- **The timer's Linux branches.** The procps branch of `alive()` (`pgrep -r R,S,D,T`) and the
  `setsid` branch of the start. On macOS the sleeper is not a session leader and `pgrep` has no
  state filter. A timer in its rounds is ended in the check through the hook's first lines only,
  not through a whole hook run.
- **The verifier as root.** `sandbox()`, `probe()` and `main()` now run in a check, with these
  stood in: the real `setpriv` drop, `chown` to another uid, the set-id copy of `id` owned by
  root, `kill -KILL -1` and `ipcrm` as the run's user, and `find -user`. Not executed at all on
  macOS: `kill_user` past its listing of `/proc`, `reap()`, `limit()`'s process limit and
  `oom_score_adj` as root, and the `/proc` readers of `runcases.own_use`, `alive` and
  `memory_in_use` (they return "cannot tell" without `/proc`).
- **The platform.** Whether the detached sleeper outlives the setup hook's exec; that an agent
  the timer ended exits in a way the runner treats as "continue to verification"; the egress
  window between the turn and the hook; grading after a capped run; the pre-trial audit. From
  round 10: that the verifier image still builds when the agent ends about 30 s before the 60 s
  backstop rather than 660 s before the cap (every trial the timer ended so far was graded, from
  the same 33,900 s stop point), and that the agent is gone within the 30 s of SIGTERM rounds.
- **The collect hook's limits on the platform's kernel.** The 420 s and 510 s limits, the alarm,
  the 15 s loop limits, the fixer's room checks and the byte caps run here with stand-ins for a
  full disk (`statvfs` answers), for `pgrep`, `setpriv`, `pkill` and `ps`, and with this Mac's
  syscall costs and its 1,023-byte link targets (Linux allows 4,095); gVisor's costs are higher,
  which makes a hostile tree reach the 420 s sooner and changes nothing for an honest tree
  (seconds in every trial so far). No small filesystem was mounted, so ENOSPC itself was never
  hit; a name that is not UTF-8 was stood in (this Mac's filesystem refuses one). The timer's
  `kill -1` as `dev` was stood in by a signal to one process group: as this machine's own user it
  would reach every process of the test's. A task held in D by `vfork` was read from the kernel's
  sources (by the re-check), not made.
- **What `ps` shows the agent.** Root's `session-timer run` and its `sleep 33900` (see Workload).

**Reading the first oracle and no-op trials** (before any model trial). In `metrics.json`:

- `cases_total` equals the image's kept count, `setup_errors` is 0 and `seconds_total` is above 0
  (the sibling task's failure was every case a setup error in 0.0 s).
- `delivery_record.delivered` is `delivered 2 <bytes>` for the oracle and `delivered 0 0` for
  the no-op; `notes` is empty for the oracle.
- `delivery_record.timer_log[0]` reads `armed pid N: ... in 33900 s`, and the last line reads
  `stopped pid N: reclaim-scratch has begun` with the same N: the sleeper was armed, outlived the
  setup hook and was still waiting when the hook ended it. A first line that says `not armed`, or
  no `stopped pid` line, means capped runs would go ungraded: fix that before any model trial.
- `ended_by_timer` is false.
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
BASEDPL_CHECKOUT=<checkout> python scripts/package_step.py     # add --flat for a bundle without steps
python scripts/upstream_builds.py                              # only when upstream's 0.1.95 files change: their hashes
```

The case seed and the build marker come from `experiment/seeds.json`, which `scripts/seeds.py`
makes once at random and which is never committed: anyone with the generator, upstream's
checkout and the seed could regenerate the hidden cases. The build needs Rust 1.100.0 with the
`x86_64-unknown-linux-musl` target, zig and `cargo-zigbuild`; packaging refuses a binary whose
sha256 is not build.txt's. Packaging ships the private cases without the generator's notes, and
`build.txt` with only its `link` and `sha256` lines; the full files stay where they are made.

## Remaining work

- A narrow re-check of round 11 (the last script's link rule and alarm, the byte caps, the timer's
  rounds), then bundle `a9dad36c7bf0` goes up as v3 of the new name, under the task's one experiment, on the owner's
  word. Its baselines and pre-trial audit come before any model trial. The two oracle trials on
  different workers are a hard gate: each must score exactly 1.0, with the same `kept_ids_sha256`
  and `expected_sha256` (`bb030348…` and `18af6936…` so far; the verifier image's context is
  v2's, byte for byte, so the same answers are expected). Check in the oracle's `timer_log` that
  the sleeper was armed for 33900 s, and in the model trials that an agent the timer ended is gone
  by the SIGKILL about 30 s after the fire, well before the 33,960 s backstop. A failed id goes on a
  deny-list and the cases are recorded again. Then the no-op, which must score exactly 0. Read
  `recording` in the reference run's `metrics.json` (drops by reason, settling,
  `kept_as_upstream_code`, the baselines, the build) and `delivery_record` as listed under
  Validation gaps.
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
