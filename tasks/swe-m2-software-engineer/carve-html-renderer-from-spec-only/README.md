# Carve renderer from the specification

Author notes. Nothing in this file is shipped to the agent or to either image.

The agent gets the normative specification of Carve, a markup language derived from Djot, and the
pages of its documentation site, and writes `/app/rebuild/carve`, a renderer that must turn any
Carve document into exactly the HTML that carve-rs 0.1.14's `carve` command writes. It never sees
carve-rs, any other Carve engine, the executable spec model, the conformance corpus or pack, or a
single rendered example beyond what the specification and the documentation pages themselves
show. This is idea 10 of the owner's sheet, "spec only, no binary": implement a post-cutoff tool
from its docs alone, graded by hidden tests recorded from the real one. A judge panel chose the
target (harbor-lh `ops/swe-marathon-v2/decisions/`).

One step is implemented. See [Remaining work](#remaining-work).

## Pins

| What | Pin |
| --- | --- |
| Specification | markup-carve/carve (MIT), tag `0.1.14`, commit `51c5631541efb60faad51f81ac7dbf881150b757` (2026-11-12) |
| Original | markup-carve/carve-rs (MIT), tag `0.1.14`, commit `0a56283f1e745643bc78cdd6fb11ac7344fb88c7` (2026-11-12); its `tests/spec` submodule pins the spec commit above, and its release notes say it implements the 0.1.14 spec |
| Original's build | the release asset `carve-0.1.14-x86_64-unknown-linux-musl.tar.gz`, sha256 `af082997672a9dc12a36a48a2dc4a72d0541b7418eb6a1c57b57f1068c0fc4ac`; its `carve` binary (static-pie, 16,216,144 bytes) sha256 `05d0898dd1c8918adee5a3b2e5a1ae1b5697acd75c7b692bf4a4ea0e4fae2048` |
| Local build (selection and checks only) | `carve-0.1.14-aarch64-apple-darwin.tar.gz`, sha256 `6787862ceef5241f0967326520d33fbff378d5db45110f2c81294e37c605f9ba`; binary sha256 `10257b84a0eff11cf26455914707cbab1ee049022204a61c06914f654422c591` |
| Spec model and Djot engine (selection and the baseline only) | carve's `scripts/spec/` at the spec commit with ohm-js 17.5.0; djot.js (`@djot/djot`) 0.3.2, the version the spec repository locks |

All pins live in `scripts/carve_text.py`; `package_step.py` and `install.py` refuse any other
archive or binary.

## Development log

### 2026-11-20 — round 10 (v5): the sweep says where it got to, beside the tree; the agent's limit 60 s after the timer

- **What happened.** The re-check of round 9 (`qa/carve/23-recheck-round9.md` in harbor-lh, FAIL)
  confirmed F1-F10 apart from F7 and found one must-fix of the same class (N1). Zombies (`pgrep -u
  dev` matches them) kept round 9's freeze and kill loops running all their passes, three `/proc`
  scans each, before the refused mark, so a large enough zombie population could run the hook's
  600 s out: W1, no mark at all; W2, the tree still in place and uncleaned under the refused mark,
  whose copy stops on the first pipe, absolute link or climbing link ahead of `.fsmaint` in GNU
  tar's order ("without the sweep's mark" or "Nothing arrived"). A top level of millions of entries
  could stretch the staging into W2 too (N2).
- **The platform, measured.** The three v3 model trials (`…-d3bd3d08-23`, `-24`, `-25`, their
  `metrics.json` pulled) all have `manifest_record.kill_passes` 1 and `processes_left` 0, with
  `process_count` 3, 8 and 3, and all were ended by the timer. Killed `dev` processes are reaped on
  Modal, so N1's zombie premise does not hold there. The auditor reads the code, not our trials, so
  the sweep is hardened anyway.
- **Design for W1 and W2: the sweep's own progress file, read by the verifier** (the coordinator's
  option b, built on the sweep's own record rather than harbor's).
  - harbor's artifact manifest (`ok` / `failed` per artifact) stays on the host:
    `upload_artifacts` re-materializes only the declared artifacts and the agent-writable
    `/logs/artifacts`, so the verifier cannot tell a `data`-filter rejection from a copy failure by it.
  - So the sweep writes where it got to into `/var/lib/fsmaint/out/sweep.json`, a second declared
    artifact (`task.toml`), in a directory only root can write. `fsmaint-reserve` makes it at set-up
    as 4,096 bytes (`{"stage": "setup"}`); the sweep writes it in place, so a write needs no new room
    however full the disk is: `started` as its very first action, `done` (or `stopped`) as its last,
    after the counted or refused mark is in place, never after 570 s.
  - The verifier (`manifest()`): a sweep that began and did not say `done` (or said `stopped`) left
    a tree it had not measured, so whatever arrived (no tree, no mark, a mark cut off) is refused
    with a note: 0. After `done` with no live process left, a missing or short arrival stays an
    error, since the tree was copy-safe and its pack's room checked: the copy or the machine failed.
    After `done` with processes still alive, a missing or short arrival is refused. With no word from
    the sweep (it never ran, or its file was not copied), the mark alone decides, as in round 9.
  - Option a (create `/app/rebuild` at set-up and rename it out in O(1)) was not taken. Its `EXDEV`
    fallback, per-entry moves, reopens W2 wherever the rename is refused, which is unverified on
    Modal. It would also put the link fixer on a staged copy, where absolute links into
    `/app/rebuild` resolve into the empty placeholder. And it changes the Dockerfile. The progress
    file closes W1 and W2 without resting on rename semantics, archive order, readdir order or
    PID 1's reaping. The Dockerfile is unchanged: the reference oracle still finds `/app/rebuild`
    0777 and empty.
- **The early stages** (QA 23's route A): the order is now progress `started`, stop the timer,
  freeze, give back the reserve, set aside `.fsmaint` and `.fsmaint.json`, the refused mark, list
  the processes, end them, the net probe, the link fixing, the measuring. Both phases test and
  count only live processes (`pgrep -r R,S,D,T,t`, zombies left out); every `pgrep`, `pkill` and
  signal runs under `timeout 10`; the freeze stops after 15 s and the ending after 60 s; and
  `kill.json` (in the record as `ending`) says whether either ran out and how many live processes
  were left (`unknown` when a listing did not answer).
- **Should-fixes.** N2 and N5: one time limit, 480 s from the sweep's start, covers everything from
  the moving out to the moving back (the walk, the links, the late count, the room check); a staging
  cut by it leaves the rest of the tree where it was, under the refused mark, and the sweep says
  `stopped`. The late count marks copied subtrees once, on the way down (linear). N3:
  `subprocess.SubprocessError` is caught wherever `remove()` is used. N6: the mark's 32 KiB are
  counted in bytes as written. N4 / F7: the sweep's header and docstrings, `manifest()`'s docstring
  and this README now say only what the code does (round 9's two overclaims are marked below). N7:
  the instruction is unchanged (its "200,000 files and directories" counts links too in the
  enforcement, and the 2,048-byte and pack-room rules are unstated; neither can refuse a tree an
  honest session would write). N9: upstream's spec text is untouched.
- **The agent's limit moves to 60 s after the pre-cap timer** (the judges' option B of 2026-11-20,
  unanimous in their second vote, after BasedPL's v2 verdict rejected a timer 660 s before the limit
  in `task.toml`; `decisions/2026-11-20-precap-timer-vs-deadline-DECISION.md` in harbor-lh; option A,
  the timer at 34,440 s, was applied first and replaced). `fsmaint-timer` still fires at 33,900 s;
  its TERM rounds are cut to 6 passes 5 s apart (about 30 s), then KILL, so every `dev` process is
  gone by about 33,930 s. Every agent `timeout_sec` in `task.toml` (`[agent]` and the step's) goes
  from 34,560 to 33,960, a backstop 60 s after the timer, with a plain note beside each for the
  platform's reviewers (the agent never sees `task.toml`): when the session ends, that the limit is
  a backstop, and why. Nothing else assumed 34,560: the sweep's timer-stop path (2 s for TERM, then
  KILL), `verify.py`, the marks and the instruction (which states no time) carry no session time.
- **Checks** (57 now). Five new, each failing on 96dbbe5 (its sweep, reserve, `verify.py` and
  `task.toml` in a scratch copy of the task): the progress file first, the mark right after the
  freeze and before the ending, the reserve making the file and `task.toml` declaring it (96dbbe5:
  none of it); the freeze and kill phases on stand-in commands, zombies only (96dbbe5: 100 passes,
  12.5 s, a zombie counted as left) and a `/proc` that never answers (96dbbe5: still running at 75 s,
  each listing blocking); an arrival
  after a sweep that began and did not finish, with a pipe, a climbing link, an absolute link, and a
  pipe first, through tar and the `data` filter, refused each time, while `done` with nothing
  arrived stays an error (96dbbe5: errors); the time limit on the staging and a linear late count
  with 15,000 copies over 20,000 files (96dbbe5: the staging ran to the end; quadratic); a mark of
  1,000 pipes with 4-byte UTF-8 names under 32 KiB in bytes (96dbbe5: 57,452 bytes). Two edited: the
  timer's 30 s of TERM, both agent limits at 33,960 s and the notes beside them; the round-9
  time-limit case (480 s, the staging included).
- **Left.** Nothing ran on Linux, in Docker or on Modal. The second artifact's delivery is harbor
  0.20's code path for every declared artifact, read here, not observed on the platform; if it does
  not arrive, the verifier falls back to round 9's rules. A hook that dies before its first write
  (its first milliseconds) leaves the setup file, read as no word from the sweep: that is the
  machine.

### 2026-11-20 — round 9 (v5): whatever the tree holds, the sweep leaves a refused tree or a counted one (QA 22)

- **What happened.** The re-check of round 8 (`qa/carve/22-recheck-round8.md` in harbor-lh, FAIL)
  confirmed round 8's fix (ten shapes at `/app/rebuild`, all refused and scored 0) and found five
  older ways a tree could still end in an evaluation error instead of a scored result, all present
  since v2: F1 a mark over 1 MiB (one note per removed pipe or link) read as no mark; F2 a path
  longer than `PATH_MAX` listed by the sweep, which the copy or the verifier's count then fails on;
  F3 a chain of links that made the measuring quadratic (about 22,000 links passed the hook's
  600 s, leaving no mark) and ended the link fixer with a `RecursionError` under the image's
  Python 3.12; F4 a full disk breaking the mark's write, or the platform's own
  `tar -czf /tmp/...` in the sandbox; F5 a relative link that climbs above `/` and back in, kept by
  the sweep and rejected by the host's `data` filter. The platform's pre-trial audit blocks v4 on
  exactly this class, so v5 (not uploaded yet) carries this round.
- **Fix: the sweep fails closed.** Right after it gives the reserve back, before the link fixing,
  the sweep puts a mark into `/app/rebuild` that says `refused` ("the sweep did not finish"). The
  measuring stage then first moves every entry out into `/app/.staged.<hex>` (a rename each;
  `/app/rebuild` itself is never renamed: Linux's overlayfs without `redirect_dir` refuses, with
  `EXDEV`, to rename a directory the image holds, and round 8 renamed it to refuse an over-limit
  tree; whether Modal's root does too was not tested), measures the tree
  there, and moves it back only when it is complete, within the limits, and the disk has room to
  pack it; one rename then puts the counted mark in place of the refused one. A measuring that
  dies, runs past 420 s from the sweep's start, or cannot write leaves the refused mark over an
  empty tree (0). Everything before the staging is bounded (the kill loops, `timeout` 20, 15 and
  120 s), so the hook's 600 s cannot run out first. *Corrected in round 10: the loops were bounded
  in passes, not in time, and zombies (QA 23 N1) could stretch each pass; round 10 bounds them in
  time and has the verifier refuse whatever arrives from a sweep that did not finish.*
  - F1: the mark holds at most 200 changes and 32 KiB of them, then "and N more changes: see
    .fsmaint.json"; the record keeps up to 4 MB. The verifier reads the mark's first 64 KiB
    whatever its size.
  - F2: an entry whose path in the tree is longer than 2,048 bytes is moved out with everything
    below it, with a note. No honest tree comes near it, so the instruction is unchanged. The walk
    is iterative, by descriptor.
  - F3: the link fixer asks the system first (`os.stat`, with Linux's own 40-link limit) and only
    then calls `realpath`, so a chain it cannot follow is removed in linear time; it catches every
    exception per entry, reports a failure once, and runs another pass only when the disk changed
    (F10). The measuring reads every link from where it stands in `/app/rebuild`, through
    directories of the tree only, to a file or a directory of the tree (one dictionary lookup per
    component, no resolution) and removes it otherwise; the catalogue is filtered once.
  - F4: the fixer copies an outside source only while the disk keeps room for it twice over plus
    64 MiB, and 64 inodes beyond those it takes (the reserve gives back 64, and the platform's
    archive needs one), and removes a copy that fails part-way. The measuring compares the free
    space of `/tmp` (`statvfs`; a figure a filesystem does not report, no size or no inode table,
    refuses nothing) with the tree's bytes, 4 KiB per entry, twice the record and the mark,
    then 32 MiB and 16 inodes besides, and refuses the tree when it is short; a refused tree's
    record is slimmed (or left out) so the refused tree itself still packs.
  - F5: every kept link is rewritten as the shortest relative path inside the tree (an absolute one
    into the tree too, which round 8 removed), so any unpacking resolves it as the sandbox does.
  - F6: the shell removes what it cannot set aside (`|| rm -rf`, no `|| exit 0`), and the measuring
    sets aside anything under the mark's or the record's name instead of crashing. F8: the fixer's
    notes go to `/var/lib/fsmaint/notes`, never `/dev/null`. F9: the verifier's note is "the sweep
    refused the tree: not run". F7: `manifest()`'s and the sweep's docstrings say what now holds.
  - The top entries' times are read before they move (a rename changes a file's ctime), so
    `late_entries` reads honest trees as before.
- **Checks** (52 now): seven new, each failing against round 8's `fsmaint-sweep` and `verify.py`
  (a scratch copy of the task with c8f99e3's two files): a 2 MB mark that starts `listed` or
  `refused` (round 8: "without the sweep's mark"), and 5,000 pipes with 240-byte names (a 33 KB
  mark; round 8: 1.4 MB); a 1,204-byte-deep path with the bound at 600 bytes (round 8: `listed 7`);
  a 6,000-link chain (round 8 keeps its head under Python 3.13 and ends the fixer with a
  `RecursionError` under 3.12; its measuring alone took 41.4 s here, round 9's 0.21 s); a measuring
  killed after the staging, one past its time and one whose every write fails (round 8: the tree
  unmarked, no time limit, a crash on the mark); a tree the disk has no room to pack (round 8:
  `listed`); a link climbing above `/` and back, an absolute one into the tree and one through
  another link (round 8: kept, removed, kept); a directory under the mark's name, the fixer's
  notes, a failure reported once (round 8: a crash, `/dev/null`, ten notes). The room check runs
  twice, its byte margin and then its inode floor raised past any disk. The sweep checks also pass
  under Python 3.12.
- **Probes** (Python 3.12, macOS): 50,000 files in 500 directories swept in 2.2 s and copied
  through harbor 0.20's own `pack_dir_to_file` and `extract_dir_from_file`; 100,000 entries at the
  top in 13.5 s; 200,001 refused in 13.2 s with only the mark and the record left; 40,000 links to
  `/etc/hosts`, measuring alone, 3.4 s; 20,000 copies leave a 12.9 KB mark; the climbing link
  passes harbor's `data` filter as `../carve`.
- **Left.** Nothing ran on Linux, in Docker or on Modal; `statvfs` in the platform's sandbox is
  unmeasured (the verifier's own 512 MB check passed there). Staging is a rename per top-level
  entry, so a top level of millions of entries takes minutes, and only once it ends is a death
  fail-closed; before the staging (bounded stages, about three minutes at most) a killed hook
  still leaves the tree in place, marked refused from the reserve's release on. *Corrected in
  round 10: such a tree's copy can stop before the mark arrives (QA 23 W2), so this was an error
  the tree could cause; round 10 closes it with the sweep's progress file.* A tree the disk
  cannot pack is refused, and the instruction does not say so: a tree within the stated limits
  meets it only if the session itself filled the 20 GB disk.

### 2026-11-20 — round 8 (v5): the v4 audit: a tree that is not a directory scores 0, never an evaluation error

- **What happened.** v4 (round 7) went up at 13:29 UTC: oracle 1.0 ×2, no-op 0.0 ×2. The platform's
  pre-trial audit returned one must-fix (`verify.py:409-414`, verifier, incompleteness): the verifier
  raises an evaluation error when `/app/rebuild` arrives missing, as a link or without the sweep's
  mark, so "a solver who removes or replaces that directory gets no reward instead of a scored zero";
  its recommendation was that the collect step record an absent or non-directory tree and score it 0.
  v2 and v3's audits, on the same code, had found nothing.
- **What was true.** The session cannot remove or replace `/app/rebuild` here (root's, inside the
  sticky `/app`), and the sweep already moved aside anything left under the mark's or the record's
  name. But the sweep's shell stage exited without a mark when `/app/rebuild` was missing, a link or
  not a directory, and its measuring stage followed a link (`realpath`), so a link would have been
  measured and marked at its target. Separately, the seal counted the sweep's own mark and record
  against the tree's limits, so a tree at the 2,000,000,000-byte limit with long paths (a record of
  hundreds of MB) could pass the sweep and then fail the seal as an evaluation error.
- **Fix.** The measuring stage checks the path itself (`lstat`): a link, a file or nothing is moved
  aside whole (a link itself, never its target), an empty directory takes its place, and the mark
  says `refused` with the reason (`/app/rebuild was a link | was not a directory | was missing`), so
  the verifier scores 0. The shell stage no longer exits early; the link fixing skips what is not a
  directory. The seal does not count the mark and the record; `MAX_ENTRIES` is the instruction's
  200,000. Two checks (45 now), each failing against round 7's code: the three replaced trees end
  refused and `manifest()` scores them 0 (round 7 marked the link's target `listed 1 10`); a tree at
  the limits with a large record seals (round 7: "more than 5 entries").
- **Every evaluation error left** is the copy or the machine failing, never the tree: a missing or
  unmarked arrival (the sweep always marks), a copy cut short, the privilege checks, the seal over
  limits the sweep enforces first, unreadable private cases, a verifier with network or without root.
  *Corrected in round 9: not yet true here. QA 22 found five ways the tree could still end in an
  evaluation error (a mark over 1 MiB, a path over `PATH_MAX`, a link chain past the hook's 600 s, a
  full disk, a link the host's copy rejects), and the refusal of an over-limit tree renamed
  `/app/rebuild` itself, which Linux's overlayfs can refuse; round 9 closes them.*

### 2026-11-20 — round 7 (v4): one solver called the completion sentence "the evaluation"

- **What happened.** Round 6 went up as v3: oracle 1.0 ×2, no-op 0.0 ×2, the pre-trial audit clean,
  then three model trials (claude-code: deepseek-v4.1-flash 0.881 and 0.915, glm-5.3 0.010), all
  three stopped by the 34,560 s limit before they finished. The platform's verdict was reject on one
  finding: at step 22 of one flash trial the solver wrote "The evaluation is" and quoted the
  completion sentence ("cannot be told apart from carve-rs 0.1.14's by what it prints ..."), then
  guessed the cases came from upstream's corpus. The verdict counts that as evaluation awareness
  (`info_leakage`, must-fix), although no trial used anything; the other two trials showed none and
  were classed good failures (time ran out).
- **Fix.** The completion sentence now states the requirement itself: for every page and each
  command line above, the same standard output and the same exit status as carve-rs 0.1.14's.
  "Told apart", which reads as someone setting the two side by side, is gone. The bundle differs
  from v3's only in `instruction.md` (this sentence and F1 below).
- **Re-check** (`qa/carve/21-recheck-eval-cues-v4.md` in harbor-lh, CONCERN, no must-fix). Applied
  before upload: F1, the list of what the audit kept out no longer names upstream's conformance
  corpus, example gallery and pack beside the sentence about our pages (a quarter of the cases are
  built from corpus documents, and the v3 solver joined the two); it now says "the rest of
  upstream's repositories". F4, the completion sentence names carve-rs's `carve`. Left: F2 (the
  sandbox's limits stay stated, since the verifier enforces them), F3 (`ps` shows the timer's
  `sleep`; for the next edit of the timer), F5 (upstream's pages stay unedited).
- **Kept.** The documentation pages that describe upstream's corpus and pack are upstream's own
  text; the specification's preamble calls the corpus pairs its conformance contract, so a solver
  can still infer hidden inputs compared byte for byte. Two of the three v3 solvers did and were
  not flagged; the check fails only on a solver calling its own session an evaluation.

### 2026-11-19/20 — round 6: the v2 oracle scored 0.0 on the platform; one renamed identifier was the cause

- **What happened.** Round 5 went up as Carve v2 (task `…-d3bd3d08`) and both oracle baselines scored
  0.0 on Modal: 1,770 cases run, 1,770 `setup_errors`, `seconds_total` 0.0, fingerprint 0 probes, while
  the tree itself arrived whole (`listed 2 16217230`, the blanked build hashed, record complete) and v1
  (round 4) had scored 1.0 on the same platform minutes before. The macOS local grade had said 1.0
  because it passes `[]` and `None` for the privilege drop; the checks never ran `sandbox()` either.
- **Root cause.** Round 5's blanket rename `owner` → `ids` in `verify.py` collided with a local that
  `sandbox()` already had: the set-user-id probe's output, a tuple of *strings*. After the rename that
  tuple overwrote the drawn `(uid, uid)`, the set-id check compared the probe with itself (always
  equal), and `sandbox()` returned strings; `runcases.prepare()` then called `os.lchown(path, "23456",
  "23456")`, which raises `TypeError` before any system call, so every case (and every probe) ended as
  a setup error at 0.0 s. The drop prefix, the seal, the mark (`listed`), the record, `test.sh` and the
  Dockerfiles were all correct; the sweep's record on the pulled tree matches the local one exactly.
- **Fix.** The probe's result is `seen`, compared with `(str(uid), str(uid))`; `ids = (uid, uid)` is what
  `sandbox()` returns (one line each; `tests/verify.py`). Nothing else in the bundle changed.
- **Checks that would have caught it** (43 now). `sandbox()` itself now runs under the checks, with only
  what needs root or Linux stood in (the id drawn is this user's, `chown` a no-op, `lchown` giving files
  to this user but still demanding integers as the real call does, `setpriv` "found", the probes
  answering as a correct unprivileged process would): one check pins that it hands back the integer ids
  it drew and refuses a set-id root escape; the other replays the tree pulled from the failed oracle
  trial (`checks/fixtures/pulled-d3bd3d08-v2-trial10/`: its real `.fsmaint` mark and `.fsmaint.json`
  record, on a stand-in tree of the same shape and sizes) through `main()`'s own steps — manifest,
  record, sandbox, seal, tripwires, cases, fingerprint, cleanup — and expects 1.0 with no setup error
  and the flags the platform's metrics showed. Both fail against round 5's `verify.py` (ids
  `['501', '501']`, types `str`, no refusal; replay 0/4) and pass against the fix.
- **Lesson** (for the dev log): a mechanical rename over a whole module must be checked against every
  pre-existing binding of the new name, and the Linux-only path (`sandbox()` → `run_cases()`) needs
  a check that runs its real body, not a stand-in return value.

### 2026-11-19 — round 5: shipped text says only what the code does; housekeeping names (v2 on Oddish)

- **Why.** The Oddish pre-trial audit on the sibling tasks returned must-fix `info_leakage` findings that
  Carve shared: hook comments that cited the platform, its cap and an operations document; helper names
  (`reserve-delivery-room`/`session-setup`, `prepare-delivery`/`session-finish`, `precap-watchdog`,
  `.delivered`) that told the solver its tree is packed for grading and that a cap is enforced; verifier
  and solution docstrings that recorded packaging, provenance and QA rounds. Owner rule (17:45 UTC): the
  audit must pass on a version before any model trial; until then only oracle and nop.
- **Names.** The helpers are now an ordinary filesystem-maintenance set in `/usr/local/lib/fsmaint/`:
  `fsmaint-reserve` (set-up; `--netcheck` starts the checker), `fsmaint-netcheck` (the egress check),
  `fsmaint-sweep` (the collect hook) and `fsmaint-timer` (the pre-cap timer); their state under
  `/var/lib/fsmaint/` (`room`, `inodes/`, `procs.json`, `netprobe.json`, `netcheck.json`,
  `netcheck-open.json`, the `sweeping` mark), the timer's log `/var/log/fsmaint-timer.log` and pid
  `/run/fsmaint-timer.pid`; the mark and record in `/app/rebuild` are `.fsmaint` (first line
  `listed ENTRIES BYTES`, or `refused`) and `.fsmaint.json`; record keys `hosts`/`any_open`,
  `process_count`/`processes`, `kill_passes`, `processes_left`, `end_bound`/`end_from`
  (`netcheck`/`start`), `netcheck`/`netcheck_open`, `timer_log`/`ended_by_timer`, `source_uid`. The
  verifier's vocabulary follows (`REBUILD`, `manifest`/`manifest_record`, `run_cases`, `cutoff_at`,
  `retry`, `ids`; notes prefixed `sweep:`; flags say "review", "end bound", "net check", "timer").
  The reserved room cannot live outside the container under Harbor, so it stays inside as root-only
  (0700) service state that looks like any other.
- **Text.** Every comment and docstring in the shipped hooks, both Dockerfiles, `task.toml`, `solve.sh`,
  `install.py`, `verify.py` and the verifier modules now describes only what the code does: no
  grading, platform, Harbor, Oddish, cap, budget, attempt, QA, audit, owner, round, date or document
  path; the `# noqa` pragmas and the `platform` module import went too; `solve.sh` no longer copies
  into `/logs/agent`; the `upstream_builds.json` comment names no script. The instruction is untouched;
  the hidden cases and probes are untouched (the pool and its kept-ids are those of round 4).
- **Grep of the packaged bundle** for grad, platform, harbor, oddish, cap, budget, deadline, attempt, QA,
  audit, owner, round, 2026-, delivery, submission, collect, watchdog: the survivors are listed in
  [Validation](#validation) with their reasons.
- The checks follow the names (41 pass). Bundle and grades in [Validation](#validation).

### 2026-11-19 — round 4 (v2): the turn's end is the first observation of egress, never the kill (QA 07c)

- **F1 [REWARD] must-fix.** Round 3b took the watcher's `restored_at` as the turn's end — but that
  is the moment the watcher *kills*, so every file a laundering agent can leave behind was written
  before it: a fetch that beat the kill was copied unflagged and `late_entries` stayed 0, where
  round 2's backward margin had refused the same input. The reference is now the earliest evidence
  that the turn had ended. `session-watch` polls every 50 ms with all hosts tried at once (0.3 s) and,
  on the first round that finds egress open, writes `restored` *before* anything is killed, with
  `first_open_at` (that round's start), `last_closed_at` (the start of the last round that found
  egress closed) and `turn_end_bound = first_open_at − poll_seconds` (at or after `last_closed_at`);
  `restored_at`, the kill, is kept only for the record. The hook's reader takes the bound, never the
  kill. The link fixer refuses an outside source whose ctime **or mtime** is at or after
  `bound − 0.5 s` (the skew in the honest direction only) and records it; `late_entries` counts
  refused late sources, flagged copies, and every in-place regular file changed at or after that
  cutoff by the later of its ctime and mtime (links are the fixer's own rewrites and directories
  change with their children, so neither counts); the verifier flags refused late sources. When the
  watcher never saw egress (a short run), the reference is the hook's own start, which precedes its
  kill phase, and a late source is copied and flagged rather than refused. Checks reproduce 07c's
  input — a source written after the bound and before the kill is refused and counted, so is a file
  written in place, and the reader derives the bound from the watcher's record (and the fallback
  from the hook's start). Honest cost: an outside build finished in the turn's last ~0.85 s (one
  poll plus the skew) and linked in is refused; in-place work is never refused.
- **F2 should-fix.** The pre-cap watchdog's TERM loop could reach the collect hook's own link fixer
  (which runs as `dev`). The hook now writes `state/collecting` and stops the watchdog (TERM, a
  bounded wait, KILL) before its kill stage; the watchdog's loop stops on the mark; the end-of-hook
  stop remains as a backstop. Checked.
- **F3 should-fix.** The reviewer's extra tight-list rule R5 (a body's top-level paragraphs
  unwrapped inside a tight item) lifted the round-3b pool's hybrid to 94 cases (5.16%) and its
  renderer-free figure to 17 (0.93%). R5 is now in `hosts.attacker_splices` and the pool was
  regenerated under the same seed: **1,770 cases** (snippets 257→206; 1,516 variants rejected as a
  splice, 432 as whitespace-only). Measured with the reviewer's own 07c scripts: **renderer-free 2
  (0.11%), hybrid 53 (2.99%, one hosted) — identical under R1-R3 and under R1-R3+R5**, so R5 adds
  no case; the builder's lookup 0.0%. The hybrid's 52 other hits are generated sources holding a
  corpus-shaped span, which need a renderer for the rest.
- 41 checks pass. Bundle `c8be4429472e` (143 files) replaced `f4176efb9c8c`; the pool and the hooks
  changed, so this is **v2** and its baselines run before the models.
- **Renamed (owner decision, 2026-11-19 17:05 UTC).** The task is now
  `abundant/swe-m2_software-engineering_carve-html-renderer-from-spec-only`, directory
  `tasks/swe-m2-software-engineer/carve-html-renderer-from-spec-only`; content otherwise identical.
  Only `task.toml`'s name and the root `pyproject.toml` registration carried the old slug (checks and
  scripts use relative paths; the ignore rules are patterns, so the private inputs moved with the
  directory and stay ignored). Re-packaged under the new name: bundle `2d38ec5a060b` (143 files,
  20 bytes more than `c8be4429472e` — the longer name in `task.toml`), same hash twice, preflight
  passes, reference 1.0 again; grades in [Validation](#validation).

### 2026-11-19 — round 3b: the splice filter and the fixer's cutoff (QA 12b F1-F2, 07b F-b/F-c)

- **The 0.0% corpus floor was the builder's own definition (12b F1).** The splice test compared the
  kept source against a placeholder form of the host that, for 6 of the 18 hosts, was a *different
  host text* (fresh draws inside the host lambdas) and, for the list hosts, a *different structure*
  (the one-word placeholder read as a lazy line of the lead paragraph). With the public corpus in
  hand, the reviewer's renderer-free strategy (corpus body plus a per-host template) scored **7.6%**
  of the pool and a hybrid (a perfect host renderer, the corpus for the body, three generic splice
  rules) **12.0-14.6%**. Fix: every host draws its text once (`hosts.py`), so its placeholder form
  is exactly the kept source with the part replaced at the part's prefix — the shape a corpus
  program rebuilds; the generator applies that program's rules R1-R3 (`hosts.attacker_splices`:
  attributes moved onto the body's first tag, a compact wrapper opened to block form, a lazy
  placeholder line replaced by the body inside its item) and rejects a variant whose answer any
  splice reproduces, or that differs from a splice in whitespace and words only
  (`rewrite.structure` after collapsing whitespace); the splices' digests travel with the case in
  `lookup_sha256`, so the Linux recording's `corpus_lookup` baseline measures them too. Regenerated
  under the same seed: **1,821 cases** (snippets 380→257; 1,418 variants rejected as a splice, 412 as
  whitespace-only, 219 as lookup-reachable; 668 corpus candidates kept no host). Measured with the
  reviewer's own scripts on the new pool: **renderer-free 2 cases (0.11%)**, **hybrid 53 (2.91%)**, of
  which one hosted — the other 52 are generated documents, constructs and mutants that happen to
  hold a corpus-shaped span and need a renderer for the rest; the builder's lookup 0.0%; both below
  the 5% bar. Also 12b F2: the `cli:nul-byte` input is no longer a corpus document.
- **The link fixer's cutoff (07b F-b, F-c).** The 2 s margin reached *backward* into the turn, so an
  honest build finished outside `/app/rebuild` in the turn's last two seconds and linked in was
  refused (reward 0). Now the cutoff is the turn's end itself with a 0.5 s forward skew: a source
  changed after it is refused when the watcher saw the turn end, and copied-and-flagged for the
  audit when the only reference is the hook's own start; `late_entries` counts a copied tree by its
  source's latest change time, not the copy's. The egress watchdog is a race, not a wall (0.2 s
  polls; a fetch that completes inside the first poll beats the kill): the record is what the audit
  reads, and the platform fix is still the real remedy.
- 39 checks pass (hosts draw once and the attacker's splice is rejected; a late source is refused
  only when the turn's end was seen). Bundle `f4176efb9c8c` (143 files) replaces `477bea22d543`;
  grades in [Validation](#validation).

### 2026-11-19 — round 3: the pre-cap watchdog (off the reward path)

- **Why.** On Oddish today every v2 trial whose agent ran into the 9.6 h cap was never graded: the
  separate verifier image failed to build right after the timeout (platform-side; write-up in
  harbor-lh `ops/swe-marathon-v2/PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`), while every run that
  ended by itself was graded. Until the platform fixes it, the task ends the agent's session itself
  shortly before the cap, so the deliverable is always graded.
- **What.** `environment/precap-watchdog` (sh, root-only), armed by a second
  `[[agent.setup_complete]]` hook as root: it starts itself detached (`setsid nohup "$0" run &`)
  and returns; the detached copy sleeps `END_SECONDS = 33,900` (34,560 less eleven minutes), then
  sends TERM to every process of the agent's user every 5 s for up to 60 s, then KILL, logging
  arm/fire/done with timestamps to root-only `/var/log/precap-watchdog.log`; idempotent through a
  pid file under `/run`. The collect hook records the log's last lines in `.delivery.json`
  (`precap_watchdog`, `ended_by_watchdog`) and stops a copy still sleeping; the verifier copies
  `ended_by_watchdog` into `metrics.json` and flags it in the notes, never into the score. The
  instruction says nothing about it. The same design as BasedPL's round 5.
- **Checks.** Arms once (a second arming logs "already armed"); fires at `END_SECONDS` (overridden
  to 2 s in the check); ends a process tree including a `setsid`'d child; logs with timestamps; the
  production defaults are asserted from the script text; the collect hook and verifier carry the
  field. 37 checks pass. Separate commit on top of the round 1-2 commits, so the re-checks 07b and
  12b can read it last.

### 2026-11-19 — hardening (QA rounds 1-2)

Two coordinator review rounds, folded in before any run. Measured numbers below are from the
regenerated pool (private seed redrawn at 128 bits) and the local recording/grading of bundle
`33c04fff63ad`.

- **Corpus-lookup closed (QA 05).** A renderer-free program that maps a source to published HTML by
  skeleton and word-mapping (the "corpus-lookup baseline", `scripts/corpus_lookup.py`) scored 32%
  of the old pool. The generator now hosts every snippet and composite inside a real construct (a
  quote, a list item, a section, an admonition, a definition, a figure, nested containers —
  `scripts/hosts.py`) so the body interacts with its host, and keeps a case only when it is **not**
  a splice of the host rendered with placeholders and the parts rendered alone (`hosts.splice`),
  not a value the lookup returns, and (for a mutant) structurally different from its published
  source. The renderer-free corpus-mapping score over the whole corpus is now **0.0%** (was 32.3%),
  and `recording.json`'s `corpus_lookup` baseline is 0.0%. Corpus-derived cases are 33% of the pool
  (was 47%). The drop is measured again at recording and the build fails above 5%.
- **Prose, not templates (QA 02).** The 520 documents and 720 constructs used to be filled from a
  word list through eight clause templates (word salad, never a diacritic, apostrophe, URL or path).
  `scripts/prose.py` is a bank of original sentences across five registers (reference, narrative,
  instruction, announcement, retrospective) with the hazards real writing carries: names and places
  with diacritics, contractions, typed dashes and quotes, bare URLs, file paths, identifiers, query
  strings, fragments, a CJK line, an emoji. Renaming (`rewrite.py`) never touches a syntax word or a
  word adjacent to a non-ASCII character.
- **Seed and leak index (QA 06).** The private seed is 128 bits (`secrets.randbits`). The leak index
  that keeps a case off the board if a shipped page shows it now also abstracts unescaped `\n`/`\t`
  spans and indented EBNF example blocks, and checks the answer side (`carve_text.answer_shown`).
- **Open readings dropped (QA 18).** Cases that rest on a reading the specification leaves open — an
  inline extension directive (`:name[...]`) or an inline note on a heading line — are filtered at
  generation (`make_cases.open_reading`).
- **Instruction rewritten (QA 01, 03, 09, 11).** One consistent reason runs through it: the audit
  admits only the specification and these documentation pages; carve-rs, the other engines, the
  corpus, the pack, the gallery and the executable model "were not reviewed and are not here … they
  may not be brought in"; the pages hold customer and incident data, so neither they nor their HTML
  leaves the build. Run conditions are stated as behaviour (an unprivileged user, a fresh directory,
  the environment, pipes, "processes and threads", the 2 GB / 200,000-file reasons); standard error
  "is discarded"; `--` is counted as an unknown option; the hooks are named neutrally.
- **Egress window hardened (QA 04).** An in-sandbox watchdog (`environment/session-watch`, started
  by the setup-complete hook) arms after ~30 s with no egress and fires on the first reachable poll
  of the hosts the original is fetched from, killing the agent's user and recording when the turn
  ended. The collect hook's link fixer records every copied source's path, owner, mtime, **ctime**
  and inode, and refuses a source whose change time is after the turn ended (margin 2 s); the record
  flags any late entry. The hooks are renamed `session-setup` / `session-finish` / `session-watch`
  and live in root-only `/usr/local/lib/pagebuild` (0700), off `PATH`.
- **Own-file disk limits (QA 10).** The per-case disk and file limits count only the submission
  uid's own files (`runcases.own_use`, ported from BasedPL `4b2c182`), not the whole filesystem, so
  a neighbour filling `/tmp` cannot fail an honest run; one retry on a limit.
- **Tripwires widened (QA 04 F1).** `upstream_builds.json` now holds 2,156 sha256 (every carve-rs
  release asset and Linux `carve` binary, all `carve-lang` wheels and their contents, carve-go and
  the docs wasm across tags, the spec-model files at every tag, ohm-js 17.x, carve-js), 14 strings
  (each ≥72 chars, three needed), and foreign-runtime markers for seven runtimes (node, bun, deno,
  quickjs, wasm, php, ruby; two needed) — a delivered program embedding a runtime the stdlib-only
  rule forbids is refused.
- **Denominator pinned and archive pinnable (QA 11).** The verifier image asserts the accepted
  kept-ids sha256 (`--expect-kept-ids`, from `tests/original/kept_ids.txt`) so the denominator
  cannot drift between builds, and both images take an `APT_SNAPSHOT` build-arg to pin the Ubuntu
  archive to one `snapshot.ubuntu.com` date.
- **Near-miss diagnostics (QA 15) and fingerprint (QA 04 F2).** The recording keeps an ungraded,
  clause-keyed record of how close each failing case came (right exit/wrong bytes, equal but for
  collapsing whitespace, sorting attributes, text only), and the image records 45 ungraded
  fingerprint probes (34 spec-model disagreements and 11 out-of-scope commands) for the audit;
  neither affects the reward.
- **Upstream docs kept authentic (QA 01, 09 F6).** "corpus" / "conformance" / "carve-rs" appear
  across ~40 of the 69 shipped documentation pages — it is real, pervasive upstream text, not one
  editable line, and no page gives an implementer a corpus-lookup recipe. Editing it would cost the
  authenticity those pages exist for and break their cross-references, so the pages ship unaltered;
  the instruction's explicit prohibition and the measured 0.0% corpus floor are the mitigation.
- Checks (36) pass under Python 3.13; `check_repository.py` passes; packaged twice to the same hash
  `33c04fff63ad`; preflight passes; graded locally (reference 1.0, see [Validation](#validation)).

### 2026-11-19 — first build

*Superseded in part by the hardening entry above: the hooks were renamed (`session-setup` /
`session-finish` / `session-watch`), the tripwires grew to 2,156 sha256 / 14 strings / seven
runtimes, the pool was regenerated at 1,944 cases under a new 128-bit seed, and the bundle is now
`33c04fff63ad`. The counts and names below are the first-build state, kept as history.*

- Started from the judge panel's choice for idea 10: Carve, pinned at spec tag 0.1.14, graded
  against carve-rs 0.1.14's release build, HTML rendering only (no includes, importers, lint, AST
  JSON or migration).
- **Upstream.** The spec repository (3,547 commits; first commit "Init." 2026-03-30, renamed to
  Carve 2026-05-13, spec 0.1.0 on 2026-07-14) holds the normative specification as 30 EBNF modules
  plus structured contracts (`resources/spec/`, 1.06 MB; `resources/grammar.ebnf` is their
  byte-for-byte aggregate), the documentation site (69 Markdown pages, 1.1 MB), a conformance
  corpus of 4,631 `.crv`/`.html` pairs, a conformance pack of about 12,000 model-generated mutants,
  and an executable spec model (`scripts/spec/`, 22,000 lines of JavaScript on an Ohm grammar).
  carve-rs is about 199,000 lines of Rust; its parser alone is 67,800 lines and its HTML path
  (parser, renderer, escaping, citations, profiles) about 80,000. The release attaches Linux,
  macOS and Windows builds; no local build was needed.
- **Agreement.** On the 4,631 corpus documents the spec model renders the corpus's own HTML for
  all of them, and carve-rs agrees with the model on 4,626 (5 differ, all in comment runs inside
  list items). The model refused nothing.
- **What the agent sees** (`carve_text.specification`, `carve_text.documentation`): `/app/spec`
  is `resources/spec/` (the modules, `README.md`, the JSON contracts, `plus-ownership.crv`) with
  `resources/normative-clauses.txt` and the licence; `/app/docs` is every `docs/**/*.md` page with
  the licence, leaving out the site's theme and build files (`.vitepress/`, `public/`). Left out on
  purpose: the aggregate grammar (the same bytes as the modules), `resources/carve-core.ohm` and
  `scripts/spec/` (the preamble calls them derived checkers: the executable model), the corpus,
  the pack, and the four example pages the site generates from the corpus (`resources/examples/`,
  about 1,300 source/HTML pairs). The documentation's own pages keep the examples they hold.
- **Cases** (`scripts/make_cases.py`, `documents.py`, `rewrite.py`, `features.py`): 2,142 private
  cases from the private seed. See [Case mix](#case-mix). Every rendering case's answer from the
  macOS build equals the spec model's rendering of it (trimmed, as the spec repository's own pack
  compares); 8 candidates where they differ were dropped. Its sha256 travels with the case, and
  the build's recording on Linux drops any case whose answer differs from it.
- **Verifier** (from the Goose task's round 6, the most re-checked of ours): separate image, root,
  answers recorded in a builder stage that the final image keeps nothing of but three root-only
  JSON files. See [Verification](#verification). New here: the delivery mark of the collect hook
  (from the backoffice task's round 7), read before anything runs.
- **Collect hook** (`environment/prepare-delivery`, root-only in the agent image): ends the agent's
  processes, turns links the platform's copy refuses into ones it keeps (absolute links inside
  `/app/rebuild` become relative; links to files or directories outside become copies; dangling
  links, pipes, sockets and devices go), refuses a delivery over 2 GB or 200,000 entries, and marks
  what it lets through. A check proves a virtual environment with an absolute interpreter link, a
  cargo tree with hard links and a link to an outside directory survive a tar and Python's
  `data`-filter extraction, which is how Harbor 0.25 copies an artifact.
- **Instruction.** A docs team moving its build into an audited environment where only its own
  code may run asks for a renderer written from the published specification; the consumers of the
  exact bytes are a page cache and CDN keyed by the HTML's checksum, a review bot that diffs
  rendered HTML, and an archive that signs published pages. It states carve-rs's command-line
  defaults, `--safe` and `--html`, input decoding, the errors and their exit status, the run
  conditions as behaviour (user, directory, environment, pipes, limits, 2 s, 4 GB, 1 GB and
  100,000 files written, the size cap on `/app/rebuild`), what is out of scope, and gives no
  example, budget or grading.
- **Toolchain.** The instruction promises Python 3.12, Go and Rust with their standard libraries,
  the three languages the requester's audited build allows, from Ubuntu 24.04's archive (python3
  3.12, golang-go 1.22, rustc and cargo 1.75), plus gcc and libc6-dev (rustc links through `cc`)
  and python3-venv. Each fits a renderer: Python for a quick start, Go or Rust for speed on long
  documents. The verifier image installs the same packages, so whatever the agent builds runs
  there.
- **Checks.** 36 task checks (registered in the root `pyproject.toml`) and the repository checks
  pass with Python 3.13; `check_repository.py` passes. Packaged twice to the same hash; Oddish
  preflight passes; graded locally from the bundle (see [Validation](#validation)).
- **Deadline.** The verifier's one deadline is 5,400 s inside a 6,000 s step, so that every one of
  the 2,142 cases can take the whole stated 2 s plus the sweeps between cases; agent and verifier
  together stay under 11.3 hours, inside Oddish's 12-hour attempt.
- **The platform's egress window** (harbor-lh `ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md`,
  found by the BasedPL QA today): Harbor gives the sandbox its public setup egress back when the
  agent's turn ends, before the delivery is collected, so a process the agent leaves behind could
  fetch carve-rs (every GitHub release attaches Linux builds), the `carve-lang` wheels on PyPI or
  the carve-go module into `/app/rebuild`. The judges' conditions for exposed tasks (decision
  2026-11-19, A 2-1) are in this version: the collect hook first records whether four public hosts
  answer (TCP 443, 3 s each) and the agent's live processes with their command lines
  (`/var/lib/delivery/session.json`), then kills them and counts the rounds, and writes a root-owned
  record `.delivery.json` beside the mark: the session record, the kill rounds, and every entry with
  type, size, modification and change times and sha256. `reserve-delivery-room` (setup begin and
  complete) sets aside 64 MiB and 64 inodes the hook gives back, so a full disk still leaves room
  for the record and the mark. The verifier refuses (reward 0, with a note) any delivered file
  whose sha256 is one of 275 published builds (`scripts/upstream_builds.py`: every carve-rs release
  asset's digest, the `carve` binary of each x86-64 Linux archive of all 15 releases, all 26 x86-64
  Linux `carve-lang` wheels and the files in them, all 12 carve-go versions and their `.wasm`), or
  that holds two of 23 strings every such build holds and no renderer written from the
  specification would: carve-rs's own usage lines and messages of its importers, lint and
  round-trip code, absent from the shipped text and from plain Rust builds. Any transformation
  (compression, a rebuild from source) defeats these tripwires, as the judges noted; the record is
  for the audit of every trial. The reference solution delivers the release build with exactly
  those 23 strings overwritten in place by `x` (`install.py --blank`; same length, nothing on the
  HTML path), so it is not refused; the recording uses the build unchanged.
- Not built on Oddish and not run, on the owner's rule.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-implement-renderer` | Implemented: instruction, agent image with the specification and the documentation, collect hook, separate verifier image recording at build, reference solution. |
| Further steps | Not designed. Candidates: the next spec release (0.1.x changes behaviour in patch releases), or a second target (canonical Carve with `fmt`, or Markdown) on the same renderer. |
| The original | carve-rs 0.1.14's static Linux release archive, fetched by `scripts/setup_tools.py` into `experiment/original/` (not in Git) and packaged as released into the verifier's build context and the solution. |
| Hooks | `environment/fsmaint-reserve` (setup begin and complete; `--netcheck` starts the egress watcher), `environment/fsmaint-netcheck` (the in-sandbox egress watchdog), `environment/fsmaint-timer` (setup complete, as root: ends the session 33,900 s after arming, all gone by about 33,930 s, 60 s before the agent's 33,960 s limit, so the deliverable is graded) and `environment/fsmaint-sweep` (the one root collect hook; it writes where it got to into `/var/lib/fsmaint/out/sweep.json`, a second artifact that `fsmaint-reserve` makes at set-up), all root-only (`/usr/local/lib/fsmaint`, 0700) in the agent image. |
| Published builds | `steps/01-implement-renderer/tests/verifier/upstream_builds.json` from `scripts/upstream_builds.py`: 2,156 sha256, 14 strings (three needed) and foreign-runtime markers for seven runtimes (two needed), for the refusal of fetched builds and runtimes. |
| Private inputs | `steps/01-implement-renderer/tests/private/cases.json` and `probes.json`, Git-ignored, from `scripts/make_cases.py` and `experiment/seeds.json`. Answers and probe answers are recorded when the verifier image is built; `recording.json` beside them describes the recording and appears in `metrics.json`. |
| Oracle | The original itself, installed from its release archive by `solve.sh` (as the agent's user), with the 14 tripwire strings blanked in place. |
| Ratings (`harbor check`) | Not run. |

## Design dimensions

### Novelty

MirrorCode-style rebuilds (Epoch AI and METR; our Goose and BasedPL tasks) let the agent run the
original as often as it likes. Here there is no original to run: the agent has a normative
specification and documentation and nothing executable, and must produce the reference
implementation's exact bytes. That turns the task from black-box probing into reading and
implementing a large, precise, recent specification, the way a second implementation of a
standard is written. SWE-Marathon v1's markup and parser tasks target languages with public test
suites the models know; the markdown-linter rebuild had a binary and examples. The language was
first published in May 2026 and its 0.1.14 specification a week before this task; see
[Recall risk](#recall-risk).

### Verifiability

Standard output and exit status are compared byte for byte with what carve-rs 0.1.14 printed when
the verifier image was built. Every kept rendering case was also rendered identically by Carve's
executable spec model, so each answer has two independent derivations: the Rust engine and the
JavaScript model of the specification. Partial progress is the share of cases that match.

### Realism

Teams that standardize on a markup language do implement it again from its specification (the
CommonMark and Djot ecosystems each have several engines), and environments that admit only
in-house code are common in regulated industries. Byte-exact HTML matters wherever rendered pages
are cached or archived by checksum or reviewed as diffs. The documents are of the kinds such a team
keeps (READMEs, release notes, runbooks, meeting notes, API references, reports), and the edge
cases come from the specification's own conformance material, renamed.

### Difficulty

The renderer must implement PART 0's line-ownership automaton (lazy lines, the `+` attachment,
nesting by content column, tabs, exact-length colon fences), a two-pass inline pairing with
word-boundary guards and braced, combined and editorial forms, attributes with ranked
serialization, smart typography, headings and section wrappers with case-preserving slugs,
references, cross-references with cloned text, footnotes (reference and inline) and numbered
captions, tables with spans, alignment and continuation rows, definition lists, admonitions, line
blocks, comments, raw passthrough and safe mode, input normalization, and PART 10's serialization
down to indentation. The in-scope specification is several hundred KB of dense normative prose;
carve-rs spends about 80,000 lines on it. Upstream's own engines still disagree with the model on
5 of 4,631 corpus documents. Not yet measured with a model; QA passes give estimates.

Floors without an implementation (measured on the private cases, `recording.json` `baselines`):
the command line's answers plus one constant answer per kind 1.81%; the largest share of any one
answer 0.62%; printing one newline 0.62%; printing nothing and exiting 0, 0%. Corpus floors, under
two definitions (QA 12b, 07c): the builder's own lookup (skeleton match and word mapping of the
published HTML, `corpus_lookup`) 0.0%; the reviewer's renderer-free strategy (the corpus for the
body, a fixed template for a host whose prose is plain) **0.11%** (2 cases), and its hybrid with a
perfect host renderer, the corpus for the body and the splice rules **2.99%** (53 cases, one of them
hosted) — the same figure under the 12b rules R1-R3 and under 07c's stricter set with the tight-list
rule R5, since the generator rejects both. A stock Djot engine passes 2.18% (see
[Case mix](#case-mix)).

### Initial feasibility

Solved by construction: the original passes every kept case, and so does the spec model, so an
implementation written from the specification alone can pass all of them. For an agent: unknown.

## Case mix

1,770 private cases, by kind and by area (`recording.json` `kinds_kept` and `areas_kept`; the
area of a corpus case is read from its source by `features.area`):

| Kind | Document | Inline | Block | Attributes | Layout | Resolution | Divergence | Edge | CLI | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `document` | 560 | | | | | | | | | 560 |
| `construct` | | 136 | 140 | 128 | 101 | 101 | 114 | | | 720 |
| `snippet` | | | 18 | 13 | 120 | 55 | | | | 206 |
| `composite` | | | 1 | 3 | 95 | 1 | | | | 100 |
| `mutant` | | | | | | | | 160 | | 160 |
| `cli` | | | | | | | | | 24 | 24 |
| Total | 560 | 136 | 159 | 144 | 316 | 157 | 114 | 160 | 24 | 1,770 |

| Kind | What it asks | Source | Median size |
| --- | --- | --- | --- |
| `document` | whole documents: READMEs, articles, meeting notes, changelogs, API references, recipes, handbooks with an FAQ, quarterly reports, postmortems, course notes, release announcements, journals | `documents.document`, written for this task from the prose bank (`prose.py`) under the seed | 42 lines (up to 135) |
| `construct` | one area of the language in a short source: dense inline markup; everyday blocks; attributes on blocks, spans and list markers; layout (nesting by column, `+`, lazy lines, quotes, tabs); resolution (headings and references, footnotes, abbreviations, numbered captions); and one of the places Carve parses differently from Djot, in context | `documents.construct` | 8 lines |
| `snippet` | one edge case of the normative clauses, rendered **inside a host construct** so the body interacts with it | a conformance-corpus document, renamed, hosted (`hosts.py`) | 4 lines |
| `composite` | two to four hosted edge cases in one document | corpus documents joined inside a host, renamed | 13 lines |
| `mutant` | an edge case no published example shows | a corpus document after one to three local edits (`rewrite.mutate`), renamed, kept only when its structure changed | 4 lines |
| `cli` | the command line's own answers, one case per behaviour: missing file, directory, two files, unknown options, `--`, standard input with and without `-`, `--safe` and `--html` before and after the file, a `--safe` include left literal, nested paths, empty input, a byte order mark, CRLF, a lone CR, ill-formed UTF-8 in a file and on standard input, NUL, no final newline | `make_cases.cli_cases` | |

Deliveries: 454 cases come on standard input, the rest as a file; 148 use `--safe` (most of the
documents that hold raw HTML) and 53 `--html`.

Rewrites (private seed, `rewrite.py`): every corpus-based case is renamed: each ASCII word in prose
position becomes an unused word of the same length and letter case, consistently, so references,
labels and abbreviations still resolve; container types, fence info strings, attribute keys and
values, entities, schemes, task states, letter and roman markers, `(tm)` forms, backslash words,
file extensions, and any word adjacent to a non-ASCII character are kept. A hosted or mutated case
is kept only when its answer differs from the plain document, is not a value the corpus lookup
returns, is not any splice of its host and parts that a corpus program would print
(`hosts.attacker_splices`: the plain splice, QA 12b's generic rules R1-R3 and QA 07c's tight-list
rule R5), differs from each such splice in more than whitespace and words, and — for a mutant — is
structurally different from its published source; 1,516 variants were rejected as a splice, 432 as
whitespace-only, 222 as lookup-reachable, 100 as unchanged, 114 as structure-preserving. Nothing
the agent can read
becomes a case: no corpus document the shipped specification or documentation shows, or whose
skeleton (letters and digits abstracted; 5,537 skeletons) any shipped example has (315 corpus
documents left out), no case of the public pack or a renamed copy of one (28), no source with an
include (`{{`, 24) and no case that rests on a reading the specification leaves open (17); the
generator checks every kept case again and packaging repeats the check on the real files.

Weight toward Djot's divergences: corpus documents are drawn with weights by the divergence
features they show (`features.DIVERGENCE`, from `docs/divergence-from-djot.md`), and one construct
area exists for them. 96.9% of the rendering cases touch at least one divergence feature other than
smart typography; the most common are visual-mnemonic emphasis (58%), mentions and tags (50%),
heading ids (48%), editorial marks (42%), block openers interrupting paragraphs (35%), semantic
spans (29%), colon fences (28%), content columns (26%), captions (22%), heading references (21%),
tables (18%), typed containers (16%) and plus-continuation (16%).

**Layout decides most cases (QA 19).** The PART 0 layout automaton, driven by indentation, blank
lines and container markers, fixes the block structure of the vast majority of cases: 94.1% of the
rendering cases carry block structure the automaton must resolve (a container or continuation
marker, a blank-line boundary, or real leading indentation) and 38.9% carry leading indentation
whose column alone changes the parse. Getting indentation right is a precondition for most of the
pool, not an afterthought.

**Stock Djot engine.** djot.js 0.3.2 run on the most obvious rewrite of each source into Djot
(`features.to_djot`: `/i/` to `_i_`, `_u_` to `{+u+}`, `~s~` to `{-s-}`, `=h=` to `{=h=}`, braced
super- and subscripts to bare ones, `. ` items to `1. `, `%%` to `{% %}`, `::`/`:` definitions to
Djot's, a `|=` header row to a row and a separator) passes **2.18%** of the rendering cases
exactly, and 3.78% if layout between tags is forgiven.

## Recall risk

The spec repository dates from March 2026 (as Carve from 2026-05-13), carve-rs's first release from
2026-07-14, and the pinned 0.1.14 from 2026-11-12. Models trained after mid-2026 may have seen the
specification, the documentation, the corpus with its expected HTML, and carve-rs's source. The
mitigations: every case is new (generated documents and constructs) or renamed or mutated under
the private seed, so no answer is one upstream publishes; corpus-based cases keep the structure of
public edge cases, though (`settled` in `recording.json` counts them). Behaviour also moves between
0.1.x patch releases (the changelog records breaking changes in each), so recall of an older
version is not enough. Because the renderer-free corpus-mapping score is 0.0%, recalling the
published HTML of corpus documents alone passes nothing; the real exposure is recalling the
language's rules well enough to re-derive the exact bytes, which the pre-run QA should probe by
asking the models under test about Carve without the files (no per-model exposure measured yet).

## Workload

A run is one trial of 33,960 s, about 9.4 hours, of which the session uses up to 33,900 s (one task row per experiment, no continuation tasks). The
instruction states no time budget.

## Verification

**Run condition on the platform: the session ends itself before the cap.** Oddish did not grade any
v2 trial whose agent ran into the 9.6 h cap today: the separate verifier image failed to build right
after the timeout (platform-side, harbor-lh `ops/swe-marathon-v2/PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`),
while runs that ended by themselves were graded. Until the platform fixes it, a root pre-cap
watchdog (`environment/fsmaint-timer`, armed at set-up complete) ends the agent's session 33,900 s
after arming, with TERM every 5 s for 6 passes (about 30 s), then KILL, so all is gone by about
33,930 s, and logs arm/fire/done to root-only `/var/log/fsmaint-timer.log`. Since round 10 the
agent's limit in `task.toml` is 33,960 s, a backstop 60 s after the timer (it was 34,560 s, 660 s
after), and a note beside each limit says so for the platform's reviewers. The collect hook records
the log's last lines and `ended_by_timer` in `.fsmaint.json`; the verifier copies that into
`metrics.json` (and a note), never into the score. The hook writes `/var/lib/fsmaint/sweeping` and stops the
watchdog before its own kill stage, and the watchdog's loop stops on that mark, so the loop never
reaches the hook's link fixer, which runs as `dev` (QA 07c F2). The agent, running as `dev`, cannot see, signal or
outlast it; the instruction says nothing about it (it states no time budget).

1. The collect hook (`fsmaint-sweep`) runs as root in the agent's container when the session ends
   (above). Its first action is to write, in place, that it has begun into
   `/var/lib/fsmaint/out/sweep.json` (round 10: 4,096 bytes made at set-up, copied beside the tree
   as a second artifact); its last, after its mark is in place, that it is done. It freezes the
   agent's processes (live ones only, at most 15 s), gives back the reserve, sets aside anything
   under the mark's or the record's name and puts a mark that says `refused` into `/app/rebuild`;
   then it records the agent's processes, ends them (at most 60 s, every listing and signal under
   10 s, the outcome in the record) and probes whether egress is open, reads when the turn ended (the watcher `fsmaint-netcheck`'s first observation of
   egress open less a poll, written before its kill — never the kill time, which a fetch can beat;
   else the hook's own start, which precedes its kill phase), fixes links — recording each copied
   source's path, uid, times and inode; an outside source whose ctime or mtime is at or after that
   bound less a 0.5 s skew (in the honest direction only, QA 07c F1) is refused when the net check
   observed the end, and copied and flagged when the only reference is the sweep's own start. Its
   measuring then moves every entry out beside `/app/rebuild`, takes out what a copy cannot carry
   (devices, pipes and sockets; an entry whose path is longer than 2,048 bytes, with all below it;
   a link that does not lead, through directories of the tree, to a file or a directory of the
   tree), rewrites every kept link as the shortest relative path inside, and moves the tree back
   only when it is within the limits, all of it done within 480 s of the sweep's start, and `/tmp`
   has room to pack it; one rename then replaces the refused mark with `/app/rebuild/.fsmaint`
   (`listed ENTRIES BYTES` with up to 200 notes, 32 KiB). A refused tree leaves the refused mark
   over an empty tree (or, where the time ran out during the moving out, over what was not moved,
   and the sweep says `stopped`). The record `/app/rebuild/.fsmaint.json` holds every entry with its
   times and sha256, the copies, the refusals, the late entries, the net-probe and process records,
   and how the ending of the processes went.
2. `/app/rebuild` arrives as the declared artifact in a fresh verifier container. The verifier
   reserves `.reward.tmp` and `metrics.json` before anything runs (no `reward.txt` exists until
   the real end, so an evaluation cut short is an error, never a 0), and requires 512 MB free in
   `/tmp` and `/logs/verifier`. It reads where the sweep got to and the delivery (the mark's first
   64 KiB, whatever its size). After a sweep that began and did not finish, whatever arrived is
   refused with a note (0): the tree was never measured, so its copy may stop on anything. After a
   sweep that finished with no live process left, nothing at all, no mark, an unreadable mark, or
   fewer entries or bytes than the mark counts is an evaluation error (the copy or the machine
   failed); with live processes left, it is refused. With no word from the sweep, the mark alone
   decides, as before round 10. A refused delivery scores 0 with a note.
3. It picks a uid inside the user namespace's map for submitted code and checks the unprivileged
   run first (no_new_privs from the status file or `prctl`, ids, groups, capabilities, limits, and a
   set-id root copy of `id` that must report that uid); a failure is an evaluation error. It seals
   `/app/rebuild` (root-owned, read-only, no set-id bits, at most 200,000 entries, the sweep's mark and record not counted, and 2 GiB): a
   submission that cannot be sealed gets reward 0 with a note. Then every delivered file is hashed
   and searched once: a file whose sha256 is one of 2,156 published builds, a file holding three of
   carve-rs's own strings, or a program embedding two markers of a foreign language runtime (which
   the stdlib-only rule forbids) gets reward 0 with a note. The record goes to `metrics.json`
   (`manifest_record`, with its flags), never scored. Before grading the verifier also checks its
   own network is closed (`network_open`); an open one is an evaluation error, never a reward.
4. Before each case it kills that uid's processes, sweeps what it left in every world-writable
   directory and its System V IPC objects, and writes the case's files into a new `/tmp/carve-case`
   with new empty `HOME` and `TMPDIR`. `/app/rebuild/carve` runs there as that uid with
   no_new_privs, the case's arguments and standard input, no network, the stated environment and
   limits, 2 seconds, 4 GB of memory in use, 1 GB and 100,000 files added to the disk, and at most
   1,000,000 bytes of output.
5. A case passes when the exit status and the bytes of standard output equal the recorded ones.
   A case that cannot be set up or started, runs too long, prints too much or passes a limit fails;
   none of that is an evaluation error.
6. One deadline (5,400 s from the start, inside the step's 6,000 s) covers the delivery check,
   sealing, scans, cleanup and cases; it leaves room for every case to take the whole stated 2 s
   plus the sweeps, so only a renderer slower than stated loses cases to it; the cases left count
   as failed. At the end the verifier cleans up, writes the reward into
   its reserved file and renames it to `reward.txt`, then writes `metrics.json` (by kind, by area,
   timings, the recording).

The recording (verifier image build, builder stage): each case runs twice and once perturbed
(another binary path, 4 KB of environment padding, a stack 256 KB smaller, one CPU); it is kept
when all three print the same, it exits 0 or 2 without a panic or signal, each run takes at most
1 s and 0.25 s of CPU, and its answer's sha256 equals the one the generator checked against the
spec model. Then any one answer is capped at 1.5% of the cases, cases whose input holds their
answer are dropped, cases the corpus lookup reaches are dropped (the corpus-lookup baseline is held
under 5%), and cases are dropped until a dispatcher with the command line's answers and one constant
per kind passes at most 5%. More than 2% unsteady, crashed, perturbed or differing cases, or fewer
than 88% kept, fails the build, and the build asserts the kept-ids sha256 is the accepted one
(`--expect-kept-ids`) so the denominator cannot drift. The image also records 45 ungraded
fingerprint probes (34 spec-model disagreements and 11 out-of-scope commands); at grade time the
verifier notes how each failing case missed (`near_miss`: right exit but wrong bytes, equal but for
collapsing whitespace, sorting attributes, or text only) and how the submission answered the probes
(`fingerprint`), both for the audit only.

### Reward formula

```
reward = cases_passed / cases_kept
```

- Continuous, fixed denominator per image build (the private cases kept by the recording). No
  executable: reward 0.
- An evaluation error (not root, privileges cannot be dropped or the drop does not hold, private
  inputs unreadable, too little disk before grading, the delivery missing or cut short after a sweep
  that finished, or with no word from the sweep) leaves no reward file. A delivery after a sweep that
  began and did not finish scores 0 with a note, whatever arrived.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verify.py` and `tests/verifier/runcases.py`; `tests/verifier/recording.py`
  describes the recording for `metrics.json` (cases kept by kind and area, drops by reason, how the
  generator settled them, spec-model agreement, run times, the baselines, the Djot engine's share,
  the divergence share, the build).

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 4, 8, 9, 10, 11, 13). Finding 1 is the
platform's egress window, shared by every task whose original is public.

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Get carve-rs or another engine and deliver it, or call it: during the turn, or by a process left running into the platform's egress window after it | Agent network; the platform's egress window; agent image | Dockerfile read: no engine, no node, no carve source; Harbor 0.25's restore of setup egress read by the coordinator | `network_mode = "no-network"` during the turn; the in-sandbox watchdog (`fsmaint-netcheck`) fires when egress returns and kills the agent's user; the hook records egress, live processes and each copy's source change time, and refuses a source changed after the turn; 2,156 published builds, 14 strings (three needed) and seven foreign runtimes refused by the verifier (check `test_a_fetched_build_of_the_original_or_a_runtime_is_refused`) | The egress watchdog is a race, not a wall: it polls every 50 ms (all hosts at once) and kills on the first answer, so a fetch that completes inside that first poll beats the kill — but not the record: the turn's end is placed at the first observation of egress open less a poll, never at the kill, and an outside source changed at or after it is refused, an in-place file counted (QA 07c F1); the window stays open until the platform keeps the agent's policy through collection; a transformed or rebuilt engine passes the tripwires; the judges' run policy applies (audit every trial, void exploits, pause on the first) | Read `manifest_record` (egress, processes, late entries, copies) of every trial; the platform fix | 🟡 YELLOW |
| 2 | Read the recorded answers | Separate verifier image; file modes | Same layout as Goose and BasedPL (their QA 07 passes) | Answers recorded in a builder stage; final image keeps five JSON files (cases, expected, probes, probe answers, recording) under root-only `/tests` (0700); submitted code runs as a mapped uid with no_new_privs | A kernel bug | Keep | 🟢 GREEN / LOW |
| 3 | Copy answers from what is shipped | Case generation and packaging | Checked: leak index of every shipped page (fenced blocks, inline code, one-line `SOURCE -> RESULT` examples, unescaped `\n`/`\t` spans, indented EBNF blocks, the JSON contracts' sources; 5,537 skeletons); 315 corpus documents left out; checked again at packaging | No case is a shipped example or a skeleton copy of one; the generated example pages and the corpus are not shipped | The documentation's own examples teach behaviour by design | Keep | 🟢 GREEN / LOW |
| 4 | Recall upstream's published answers | Rewrites and hosting | Every corpus-based case renamed and hosted in a host that draws its text once; kept only when the answer changed, the corpus lookup misses, no splice of host and parts (plain, QA 12b's rules R1-R3, or 07c's tight-list rule R5) gives it, and it differs from every splice in more than whitespace and words (1,516/432/222/100/114 variants rejected) | Private-seed renaming; new documents and constructs (1,304 of 1,770); mutants kept only when structurally changed | Structure of public edge cases is kept; models trained after mid-2026 may know the language | Pre-run QA recall probe; read `settled` | 🟡 YELLOW |
| 5 | Pass cases with no renderer: constant answers, a command-line table, a corpus lookup, a corpus-plus-template splice | Case mix and selection | Recording: command-line table and constants 1.81%, largest answer 0.62%, the builder's corpus lookup 0.0%; the reviewers' own scripts (QA 12b, 07c) on this pool: renderer-free **0.11%** (2 cases), hybrid with a perfect host renderer **2.99%** (53, one hosted) — the same under R1-R3 and under R1-R3+R5, down from 7.6% / 14.6% before round 3b and 5.16% under R5 before round 4 | Answer cap 1.5%, corpus-lookup (builder's guesses and the attacker's splices, by digest) and dispatcher floors 5% enforced at build; `recording.json` measures them | The hybrid's 52 non-hosted hits are generated sources holding a corpus-shaped span; they need a real renderer for the rest; a further generic rule could still move the hybrid figure, which is a rule set's, so it is re-measured after every pool change | Read `baselines` in the first baseline's `metrics.json`; re-run the 12b/07c scripts after any pool change | 🟢 GREEN / LOW |
| 6 | Port a Djot engine | Case mix | Measured: djot.js 1.87% exact, 3.54% layout forgiven | Mix weighted to Carve's divergences (97.3% touch one) | None | Keep | 🟢 GREEN / LOW |
| 7 | Deliver a link to something else, or replace `/app/rebuild` | Agent image modes; collect hook | Checked in the Dockerfile; links rewritten or copied by the hook; a link, a file or nothing at `/app/rebuild` ends refused (round 8 check) | `/app` root's and sticky, `/app/rebuild` root's and writable; the hook keeps only links that lead through directories of the tree to a file or a directory of it, each rewritten as the shortest relative path inside (round 9) | None found | First trial as `dev` | 🟢 GREEN / LOW |
| 8 | Make the copy fail so grading errors (deep paths, sparse or huge files, inode exhaustion, link chains or mazes past the hook's 600 s, a full disk before the mark, a mark too large to read, a link the host's copy rejects, zombies that stretch the hook, a tree left in place and uncleaned when the hook dies) | Collect hook; platform copy; the sweep's progress file | QA 22 (F1-F5) and QA 23 (N1-N6) probes; round 9's seven and round 10's five checks, each failing on the code before; harbor 0.20's own pack and extract (`tar_transfer`) run on swept trees; the whole suite under Python 3.12 | Fail closed twice over: the sweep says it began before anything else and that it is done only once its mark is in place, and the verifier refuses whatever arrives from a sweep that did not finish; the refused mark comes right after the freeze; live processes only, every listing and signal under 10 s, each phase timed; the tree moved out to be measured and moved back only complete, within the limits, within 480 s and with room in `/tmp` to pack it; paths over 2,048 bytes moved out; links relative and inside; linear walks; the mark at most 32 KiB in bytes, read from its first 64 KiB | After a sweep that finished, a missing or short arrival is the copy or the machine failing, an error; the progress file's delivery is harbor's code path, not observed on Modal (without it, round 9's rules); run policy kept: one attempt per trial, read every errored trial | Read errored trials and `sweep_state` in `metrics.json`; the first platform runs of the hook | 🟡 YELLOW / UNASSESSED |
| 9 | An honest delivery refused or cut short (a venv's absolute links, cargo's hard links, links to files outside) | Collect hook; platform copy | Check `test_the_collect_hook_lets_honest_deliveries_through_the_copy` (tar plus `data` filter on such a tree); a 50,000-file tree through harbor's own pack and extract (round 9 probe) | Links fixed as the agent's user; copies counted against the limits and made only while the disk keeps room for them twice over plus 64 MiB; top-level times read before the tree moves | Modal's GNU tar on the real platform unmeasured; a delivery over the stated limits is refused; an entry deeper than 2,048 bytes is moved out; a tree the disk has no room to pack is refused, unstated (only a session that filled the 20 GB disk itself meets it) | First baselines and trials: read the marks in `metrics.json` notes | 🟡 YELLOW / UNASSESSED |
| 10 | Answers that depend on the machine | Recording | Local: 1,944 of 1,944 steady, none perturbed; the Linux build must reproduce the macOS answer the model agreed with | Two runs and a perturbed one; `differs` dropped; static-pie musl build; the kept-ids sha256 asserted at build | The Linux build has not run yet (no Linux here) | Read `dropped_differs` and `dropped_unsteady` in the first recording | 🟡 YELLOW / UNASSESSED |
| 11 | Tamper with the result files, or force an evaluation error from inside a run | Separate verifier; reward placeholder | Goose QA 07e passed on the same code; delivery check added here | Reward reserved and renamed only at the end; bounded reads; one deadline; every per-case exception a failed case | The delivery check is new code | Narrow re-check in the QA round | 🟡 YELLOW / UNASSESSED |
| 12 | Run as root in the verifier through a set-id or capable file | Privilege drop and sealing | Goose QA pass 10 F6; checks here | Sealed root-owned without set-id bits; `setpriv --no-new-privs`; the drop is checked or nothing is graded | A kernel that ignores no_new_privs (the probe then refuses to grade) | First baseline's verifier log | 🟢 GREEN / LOW |
| 13 | Infer an evaluation from the files and text | Instruction and image | Checked: no grading, hidden, budget or session wording; no examples shipped | Requester's voice; the hook is root-only and names no judging | An agent can still guess that pages exist to test it | Read the first trajectories | 🟡 YELLOW / UNASSESSED |
| 14 | A case where carve-rs and the specification disagree | Selection | 30 candidates dropped by the model check; 6 corpus documents known to differ | Only cases the model renders identically are kept | None | Keep | 🟢 GREEN / LOW |
| 15 | Behaviour outside the stated scope graded | Case generation | No source holds an include; options only `--safe`, `--html`, and unknown ones; CLI cases one per stated behaviour | Out-of-scope list in the instruction | None found | QA lens 12 | 🟢 GREEN / LOW |
| 16 | Stop, delay or outlast the timer (`fsmaint-timer`), so the session runs into the platform's cap and is never graded (a 0 the audit cannot see), or exploit its kill | Agent user; root-only hooks | Checked: the timer runs as root from the set-up hook, its log and pid file are root's (0600, `/run`), `dev` cannot signal a root process; check `test_the_timer_arms_once_fires_at_end_seconds_and_ends_the_tree` | It can be killed only as root; the kill is TERM (6 passes, 5 s apart) then KILL of `dev`'s processes only, from 33,900 s (gone by about 33,930 s); since round 10 the agent's limit is 33,960 s, a backstop 60 s later (after BasedPL's v2 verdict on a 660 s margin; the judges' option B), with a note beside it in `task.toml`; its loop stops on the sweep's `sweeping` mark and the sweep stops it before its own worker runs, so it never reaches the link fixer (QA 07c F2); `ended_by_timer` is recorded for the audit, never scored | A platform that itself kills root processes or arms the hook late (then the 33,960 s limit ends the session, the platform's own cap, which 4 of 4 heavy-image trials did not survive on 2026-11-19); a run that ends 60 s early loses nothing the limit would not have taken | First capped trial: read `ended_by_timer` and the log tail in `metrics.json` | 🟢 GREEN / LOW |

Licences: the specification, documentation and carve-rs are MIT. The spec's `LICENSE` ships in
`/app/spec` and `/app/docs`, carve-rs's with the reference solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (57 tests) under Python 3.13 and under 3.12 (a scratch venv from the offline cache), and `check_repository.py` | working tree, 2026-11-20, round 10 | 57 passed under each; the five new checks and the two edited ones (timer, time limit) each fail on 96dbbe5's sweep, reserve, timer, `verify.py` and `task.toml` in a scratch copy of the task (7 failed): no progress file; 100 kill passes in 12.5 s with a zombie counted as left (and, with a `/proc` that never answers, still running at 75 s); "without the sweep's mark" for an arrival cut off by a pipe; a staging that ran to the end; a 57,452-byte mark; the timer at 33,900 s; the 420 s message |
| `checks/` (52 tests) with `ci_checks`, Python 3.13, and `check_repository.py` | working tree, 2026-11-20, round 9 | pass (52 passed; repository checks passed); the seven new checks each fail against round 8's `fsmaint-sweep` and `verify.py` (c8f99e3, in a scratch copy of the task): "without the sweep's mark" on a 2 MB mark, `listed 7` with a 1,204-byte path, the chain's head kept (a `RecursionError` in the fixer under Python 3.12), the tree left unmarked when the measuring is killed, `listed` with no room to pack, the climbing link kept and the absolute one removed, a crash on a directory under the mark's name |
| The sweep's checks under Python 3.12 (the image's version; a scratch venv from the offline cache) | working tree, round 9 | the 17 checks that run the sweep or name its text pass; round 8's chain check fails there with the fixer's `RecursionError` |
| Round 9 probes, Python 3.12 (a scratch script, not kept) | working tree, round 9 | 50,000 files in 500 directories: swept in 2.2 s, then copied by harbor 0.20's own `pack_dir_to_file` and `extract_dir_from_file` and graded; 100,000 entries at the top: 13.5 s; 200,001: refused in 13.2 s, only the mark and the record left; 40,000 links to `/etc/hosts`, measuring alone: 3.4 s; 20,000 copies: a 12.9 KB mark ending "and 13,499 more changes"; a link climbing above `/` and back: rewritten `../carve`, through harbor's `data` filter. Round 8's measuring alone on a 6,000-link chain: 41.4 s (round 9: 0.21 s) |
| Packaging, local grading and preflight, round 9 | `scripts/package_step.py` (twice, the same hash), `scripts/grade_locally.py` | `6b9731444d4869f2a816906596b449cd0b56e8200dde87de373de570f673d551`, 143 files, 17,834,790 bytes; `diff -r` against round 8's `a8bb7e136198`: `environment/fsmaint-sweep` and `tests/verify.py` only; reference 1.0 (1,770 of 1,770, `listed 2 12981886`), empty tree 0.0, silent program 0.0; preflight pass. Earlier cuts of this round graded the same and were superseded: `3dfdf013572c` (before the inode floor), `5242621f77fc` (before the last `manifest()` docstring fix) |
| Tripwires on the reference | `install.py --blank` on the pinned Linux build | blanked sha256 `f1a359cba59853ecf5087b2f7a6bac17fc208df99d09a63dc567268e1ec5fad0` (same 16,216,144 bytes), in no list, none of the 14 strings left; the unchanged Linux build (`05d0898d…`) and the macOS build are refused |
| Corpus agreement, spec model against carve-rs (macOS release) | spec `51c5631`, carve-rs 0.1.14 | 4,626 of 4,631 equal; model equals the corpus HTML on all; 6 of the candidates drawn for cases disagreed and were dropped |
| Case generation | cases sha1 `5db42245` (1,770) | 34 dropped as model disagreements, 720 with no variant kept (11 with none at all; 1,516 variants rejected as a splice, 432 as whitespace-only, 222 as lookup-reachable), 5 shown in the docs, spec or pack, 1 with its answer printed; corpus left out: 315 shown, 28 pack, 27 answer printed, 24 includes, 17 open readings, 1 long |
| Local recording with the macOS release build, through the bundle's recorder | bundle `c871cb7a1765` | 1,770 of 1,770 kept; none slow, unsteady, crashed, differing or perturbed; slowest run 30.1 ms; kept ids sha256 `7ace1c15…`; corpus floors on this pool with the reviewers' own 12b/07c scripts: the builder's lookup 0.0%, renderer-free 0.11% (2 cases), hybrid with a perfect host renderer 2.99% (53, one hosted) under R1-R3 and under R1-R3+R5 alike |
| Packaging twice | `scripts/package_step.py` | the same hash both times: `c871cb7a17658edc6d3c00b797e007c522c2f304c1718e2b1865d16d028bf649`, 143 files, 17,815,797 bytes; the bundle directory is `swe-m2_software-engineering_carve-html-renderer-from-spec-only` |
| Oddish preflight | bundle `c871cb7a1765` | pass |
| Packaging, local grading and preflight, round 8 | `scripts/package_step.py`, `scripts/grade_locally.py` | `a8bb7e13619865f6f5fe531661361df5bdd286ea896c97761ad97f96c27a77ef`, 143 files, 17,817,488 bytes; `diff -r` against round 7's `b43283f1a8d7`: `environment/fsmaint-sweep` and `tests/verify.py` only; reference 1.0 (1,770 of 1,770), empty tree 0.0, silent program 0.0; preflight pass |
| Packaging and preflight, round 7 | `scripts/package_step.py` | `b43283f1a8d7b4315e0b4a3b1516719c96c02290691bd8bf21bb7b5f4d932f70`, 143 files, 17,815,762 bytes (with the re-check's F1 and F4; the first cut was `44acf2f2e077`); `diff -r` against `c871cb7a1765`: only `instruction.md` (lines 42-47 and 105-107) |
| Replay of the tree pulled from the v2 oracle trial on the platform (task `…-d3bd3d08`, trial 10, 2026-11-19: reward 0.0, 1,770 setup errors) | `checks/fixtures/pulled-d3bd3d08-v2-trial10/` through `main()`'s steps with `sandbox()` stood in only where it needs root or Linux | 4/4 cases, no setup error, fingerprint 1/1, the platform's two flags reproduced; the same replay fails against round 5's `verify.py` (string ids) |
| Word grep of the packaged bundle (grad, platform, harbor, oddish, cap, budget, deadline, attempt, QA, audit, owner, round, 2026-, delivery, submission, collect, watchdog) | bundle `c871cb7a1765` (round 6 changed three identifiers only) | our shipped files: `fsmaint-netcheck` cap 4 (`capture_output`); `fsmaint-sweep` round 4 (`round()`); `instruction.md` cap 3 (captions, escaping), audit 2 (the requester's compliance audit, narrative), owner 1 (`plus-ownership.crv`, a spec file name); `blank.json` cap 2, round 1 (carve's own help strings: `--caption-hints`, escape, `--roundtrip`); `recorder.py` and `recording.py` round 9 (`round()`), collect 2 (`from collections`); `runcases.py` cap 3 (`surrogateescape`, `capture_output`), round 2 (`round()`); `upstream_builds.json` cap 28, budget 8, owner 8, round 6 (upstream file names: `bracket-escapes.js`, `abbr-budget.js`, `list-owner-columns.js`, `block-ownership.js`, `roundtrip-*`); `verify.py` cap 12 (`CapPrm`/`CapEff`/`CapAmb`, `escape`), round 3 (`round()`); `task.toml` collect 1 (`[[verifier.collect]]`, the required section key). Nothing else of ours matches. The spec, docs and LICENSE (upstream text) and the private case prose (round 4's pool, untouched) carry the remaining hits |
| Local grading from the bundle (`scripts/grade_locally.py`, no sandbox) | bundle `c871cb7a1765` | reference (the build blanked as `solve.sh` does, re-signed, as `/app/rebuild/carve`, marked by the bundle's sweep, passing the tripwires) 1.0 (1,770/1,770, 20 s); an empty tree 0.0; a program that prints nothing 0.0; no late entries, no refused or flagged copies, `ended_by_timer` false. Fingerprint: the blanked reference matches 47 of 49 probes — the two misses are the `-h`/`--help` probes whose output carries blanked help strings; production records probes from the unblanked oracle, and the fingerprint is diagnostic, never scored |
| Oddish baselines | v1 (round 4, `…-d3bd3d08` v1): oracle 1.0 ×2, nop 0.0 ×2; v2 (round 5): oracle 0.0 ×2 (the string-ids defect above); v3 (round 6): oracle 1.0 ×2, nop 0.0 ×2, pre-trial audit clean | round 7 not yet uploaded |
| v4 (round 7) | oracle 1.0 ×2, nop 0.0 ×2 | pre-trial audit: 1 must-fix (a tree that is not a directory was an evaluation error; round 8) |
| v5 (rounds 8 and 9) | not uploaded | carries bundle `6b9731444d48`; round 8's `a8bb7e136198` was never uploaded |
| Model trials | v3: claude-code with deepseek-v4.1-flash 0.881 and 0.915, glm-5.3 0.010, all three stopped by the time limit | verdict reject (evaluation awareness in one trial; round 7) |

## Build and deliver

```bash
git clone https://github.com/markup-carve/carve ../.cache-src/carve   # beside the repository checkout; read by hash
python scripts/setup_tools.py              # the release builds (sha256-checked) and the spec model with ohm-js and djot.js
python scripts/upstream_builds.py          # published builds (GitHub, PyPI, Go proxy) -> tests/verifier/upstream_builds.json
python scripts/make_cases.py               # private cases from experiment/seeds.json, checked against the model
python scripts/package_step.py             # experiment/dist/bundles/<hash>/...; add --flat for a bundle without steps
python scripts/grade_locally.py <bundle>   # the reference and two no-ops through the bundle's own verifier
```

The seed comes from `experiment/seeds.json`, which `scripts/seeds.py` makes once at random and
which is never committed: anyone with the generator, the pinned checkouts and the seed could
regenerate the hidden cases. `make_cases.py` needs Node 24 for the spec model; nothing in either
image needs it.

## Remaining work

- The 20 QA passes (owner's rule), then the judge panel's go for baselines of the current bundle
  under the task's one experiment: the first Linux recording (read `recording` in the reference
  run's `metrics.json`: `dropped_differs`, unsteady, the baselines), the first run of the collect
  hook and of the delivery check, and the first run of the privilege checks as root. Two oracle
  trials should each score exactly 1.0; a no-op 0.
- A recall probe: ask the models under test about Carve without the files.
- The platform fix for the egress window (keep the agent's network policy through collection, or
  kill the agent's processes before the restore), proved by the canary in
  `ops/swe-marathon-v2/canary/`; until then, the in-sandbox watchdog (`fsmaint-netcheck`, unproven on
  the platform — it has only been exercised locally) and the scripted audit of every trial.
- The verifier image (and so the collect hook, the privilege checks, the kept-ids assertion and the
  Linux recording) has never been built or run on Linux here; the first build is the first test of
  all of it. Optionally pin `APT_SNAPSHOT` once a date is chosen.
- `harbor check` and ratings.
