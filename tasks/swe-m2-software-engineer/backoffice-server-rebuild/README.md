# Back-office server rebuild

Author notes. Nothing in this file is shipped to the candidate or to either image.

A wholesale back-office application, Stockwell, runs in the candidate's container. Its
server is sealed: it answers on `127.0.0.1:8080` but its files belong to another user and
cannot be read. The candidate has the web client's source and unlimited access to the
running server, and writes a replacement server that answers every API request the same
way. The idea comes from a review of the SymPy pilot: use an application that cannot be in
pre-training, hide its backend, and grade a rebuild against hardened recorded cases.

One step is implemented. See [Remaining work](#remaining-work).

## Development log

### 2026-11-24 (round 15: no task-side timer, late writes removed from the work's end, a flat bundle under the task's own name; version 11)

- The judges' third decision on the timer (harbor-lh
  `ops/swe-marathon-v2/decisions/2026-11-24-timer-round3-flat-bundles-DECISION.md`, unanimous: C,
  with D alongside). BasedPL's version 4 verdict rejected round 12's option B again ("the task's
  own session timer ... is shorter than the configured agent limit ..., so the timer stops the
  agent before its time is up"), as its version 2 verdict had with a 660 s gap: any task-side stop
  before `timeout_sec` is rejected. The timer is gone: `environment/fsmaint-timer`, its
  `setup_complete` entry, its lines in the Dockerfile and the packager, the sweep's stop and its
  `timer:` lines, and `ended_by_timer` and `timer_log` in `metrics.json`, now `sweep_log` (the
  sweep's own `sweep:` lines, whole). Both agent `timeout_sec` values are 34,560 again, with no
  comment. The process cap of round 13 stays.
- The bound after the turn, without the timer. At the limit harbor stops waiting but never ends
  the agent's commands, and the network comes back once the turn is over (harbor-lh
  `ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md`), so a capped turn's processes can write, and
  fetch, until the collect hook ends them; ending them at the limit is ruled out (a killed
  claude-code run is classified by its transcript, and Oddish would discard the score). The
  set-up now records the work's start at each successful exit (`/var/lib/fsmaint/work-started`;
  it fails if it cannot), and the work's end is that start plus 34,560 s (the bound of SymPy's
  integrity N1 fix). The sweep ends the user's processes as before, does every other step that
  could touch `/app/server` (the `/logs/artifacts` set-aside, the manifest name's), then writes a
  fence. The fixer, as `dev`, leaves a link that itself changed between the end and the fence to
  the walk, and copies in no outside file or directory in which a file or link changed after the
  end. The walk, as root, removes every entry other than a directory whose change time (the
  kernel's; the agent cannot set it) falls between the end and the fence, with every other name of
  the same file (removing one name moves the others' change time past the fence, where they would
  pass for the sweep's own), a note each (`removed PATH: it changed after the work's end`) and a
  `sweep: N entries that changed after the work's end were removed` line. A turn that ends by
  itself ends before the end, so nothing is removed for it. A directory is not judged by its own
  change time, which any entry added or removed in it moves (the files in it are). What this
  leaves is under Remaining work.
- Carve's re-check found that its sweep moved top-level entries before judging lateness, which
  moved those files' change times past the end, so another name of the same file deeper in the
  tree read as late: an honest tree lost two names. Checked here: before its fence the sweep
  changes nothing in the tree but the agent's own file under the manifest's name (moved aside) and,
  where `/logs/artifacts` cannot be renamed, what that directory holds (removed); whatever it
  changes after the fence (the fixer's copies and rewritten links, the walk's removals) has a
  change time at or after the fence and is never judged late. So no move of the sweep's own makes
  another name read as late, and the times need no record by inode. The two cases before the fence
  judge a file hard-linked into the tree from there as late in a capped session, which only a tree
  built against the hooks has. `test_an_honest_capped_tree_with_hard_links_loses_no_name`: an
  honest capped tree with a file named at the top and three levels down, a link with two names
  that the fixer replaces by a copy under each in turn (replacing the first moves the second's
  change time), a name hard-linked to a cache outside the tree (as uv links a package), a link made
  relative and one replaced by a copy loses no name and gets no note about the work's end. On
  `1a6b87b`, which has no rule on late writes, it loses no name either (`complete 14 2658`; it
  fails there only on the timer's line in the manifest); on this round's sweep with the fence's
  upper bound taken out, every change after the end judged (Carve's shape), it loses three
  (`complete 11 658`): `venv-python` and `inside`, which the fixer had just written, and
  `a/python-again`, whose change time the replacement of its other name had moved.
- BasedPL's re-check R1, which holds for every task without the timer: a capped turn's processes
  run on, with the network back, until the collect hook, and a file one of them maps shared and
  writable, or holds open for writing, from before the end can be written after it without its
  change time moving (a write through a mapping of a file kept in memory, as on tmpfs, never moves
  it), which the rule on late writes misses. The sweep now first stops every process of the user
  (`kill -STOP -1` as `dev`, repeated while any still runs where `pgrep` can tell), then lists the
  regular files that a process of the user maps shared and writable (`/proc/PID/maps`, `rw-s`) or
  holds open for writing (`/proc/PID/fd` and the flags in `fdinfo`), and only then ends them. The
  list is made as `dev`: root may read another user's maps and open files only with the capability
  to trace them, which Docker's root lacks. Once the end has passed, the walk removes every name of
  those files with a note (`removed PATH: a process of the user could still write it after the
  work's end (open for writing or mapped writable)`), the fixer copies in no outside file so held,
  and `sweep_log` says how many there were; before the end nothing is taken. Where the list cannot
  be made once the end has passed (`/proc` unreadable, a process of the user made undumpable, more
  than 100,000 files, past 60 s), the tree is refused. Check
  `test_a_file_a_process_could_still_write_after_the_end_is_left_out`, on a stand-in `/proc`: a
  shared writable mapping (with a second name of its file), a file open for writing and a held file
  outside behind a link go; another user's process, a private and a read-only mapping and a file
  open for reading count for nothing; before the end all of it stays; an unreadable `/proc` and an
  undumpable process refuse the tree. On `bbae97b` the held files arrive (`complete 16 1716`).
- `sweep_log` takes the manifest's lines that start with `sweep: `, and one note did start with a
  name the agent chose: a link the walk writes again was noted as `PATH -> TARGET (was OLD)`, so a
  link named `sweep: 0 entries ...` read as the sweep's own line. That note is now
  `link PATH -> TARGET (was OLD)`; every note starts with what was done.
- Checks, both failing on `1a6b87b`: `test_a_capped_session_keeps_nothing_written_or_fetched_after_its_end`
  (a detached process fetches over HTTP from a server on this machine and writes into the tree and
  outside it until the sweep's own loop ends it, through stand-ins for `pgrep` and `setpriv` that
  see and end that one process, so the fence must come after the kill; round 14 keeps all of it,
  `complete 11 10479`; now `complete 5 1035`, four entries removed, the link to the fetched file
  outside not copied, and a session that ended before its limit keeps everything) and
  `test_a_late_file_cannot_keep_its_content_through_another_name` (without the set of late files,
  two of the three names survive). The timer's four checks and its helpers are gone; the others
  read `sweep_log`; the configuration check pins 34,560 in both places, no comment, nothing but
  the sealed server at set-up and no timer in the image or the packager; the new check ties the
  sweep's two 34,560s to `task.toml`; the manifest check adds the link named like a `sweep:` line;
  the bundle check builds the flat bundle under the task's own name and holds it to the steps
  bundle as below, and has `--keep-name` without `--flat` refused. With R1's check (below)
  `checks/` has 62 tests; with `ci_checks` (27), 89 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes (one timing check, a hanging and a dripping server against
  a 4 s deadline, failed once under load in a first full run and passed alone and in every full run
  since); the sweep and the set-up pass `dash -n`, and the sweep's three scripts and `verify.py`
  compile under Python 3.12.13.
- A flat single-step bundle under the task's own name, as SymPy's (the only setup whose capped
  runs were graded, 3 of 3): `package_step.py --flat --keep-name` writes the steps bundle's files
  without the `steps/01-rebuild-server/` prefix and keeps the name
  `abundant/swe-m2_software-engineering_backoffice-server-rebuild`, so that the upload becomes the
  next version of the same task (`--keep-name` alone is refused); the repository keeps its steps
  layout. Steps bundle `8725378e9033` and flat bundle `9c6f8371270f` (`bbae97b`, before R1, built
  `7b68392e5eb4` and `4079a1748e67`, which differ from them in the sweep alone), 1,160 files each
  (round 14's less the timer), 247.3 MB, each built twice with the same hash and `diff -r`-identical
  files.
  The flat bundle against the steps bundle: the same 1,160 names once the prefix is dropped, and the
  same bytes and executable bits in every file but `task.toml`, which lacks
  `multi_step_reward_strategy = "final"` (with one step its reward is the trial's either way) and
  the `[[steps]]` table: the step's name, `01-rebuild-server`, and its agent and verifier limits,
  34,560 s and 6,000 s, the values of the top-level `[agent]` and `[verifier]` tables the flat
  task runs with. The instruction, the image, the set-up and collect hooks, the verifier and its
  image, the artifacts (`/app/server`) and the reward are the same.
- Proof. The local grade of the flat bundle `9c6f8371270f` (the regrade reading the bundle's root;
  its solution installed from an isolated copy by its own `oracle.py`, only the interpreter path
  swapped for this Mac): the reference 1.0, 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned
  restarts, no other restart, no second try, nothing unfinished, no note, 509.3 s of replay; an
  empty server 0.0, 0 of 4,002 ("/app/server/run is missing or not executable"). `bbae97b`'s flat
  bundle `4079a1748e67` scored the same (4,002 of 4,002 in 514.4 s, and 0.0), and so did the first
  build, `77c04a446699` (519.5 s). `oddish preflight` on the flat bundle passes. Oddish's
  `compute_task_content_hash` (`sha256-harbor-publishable-v1`) of the flat bundle is
  `7f631001774d...`, against `2c5d937b30d5...` for version 10's `7a92d0bd02fe` (the steps
  bundle's is `53c4468a49e9...`; `4079a1748e67`'s was `2160b86bc5b9...`).
  `scripts/scan_uploads.py` on the flat bundle: no leak and nothing missing among 495 agent-image
  files (round 14's 496 less the timer).

### 2026-11-24 (round 14: the cap's record under bash, a neutral `task.toml` comment, `/logs/artifacts` set aside; version 11)

- Re-check v11b of round 13 returned CONCERN, no must-fix, one should-fix: the set-up recorded the
  cap with `su dev -s /bin/sh -c 'ulimit -Hu'`, and the image's `/bin/sh` is dash, whose `ulimit`
  has no `-u` ("Illegal option -u", status 2), so nothing was written and the baselines could never
  have shown the cap. It now runs `-s /bin/bash`, the shell harbor itself names for the agent's
  commands. Measured here: under dash the old line exits 2 and writes nothing; the new one writes
  the limit (6000 on this Mac). The check now runs the set-up's own line through a stand-in `su`
  that uses the shell it names (dash for `/bin/sh`), with a timer armed, and follows the value into
  `timer_log`, third after the timer's `armed` line and the sweep's line about its stop, as the
  baseline criterion under Remaining work reads.
- BasedPL's version 3 audit called the same comment in its `task.toml` "an author comment that
  discloses the evaluation platform and its verifier" (must-fix). Both comments here now read
  exactly: "# Sessions end at 33,900 s: a timer started at set-up closes the session user's
  processes then" / "# (all are gone by about 33,930 s). This value is a backstop 60 s later." A
  sweep of the other shipped files for author commentary on the platform, trials, the verifier's
  image or grading found none: `verify.py` and `replay.py` name their own results, reward and
  evaluation, which the verifier may. The `task.toml` checks now reject such words in any comment
  (platform, trial, verifier, image, grading, results, the providers' names).
- Carve's re-check found that the agent can fill `/logs/artifacts` without bound, and it holds here
  too (harbor 0.20, read: on Modal `ensure_dirs` makes the directory with `chmod 777`, the
  collection prepends it before `/app/server`, and `upload_artifacts` puts it into the verifier's
  machine with nothing to catch a failure, an evaluation error; the collect hook runs before the
  download). The sweep now moves what the directory holds aside by one rename (never following or
  copying anything) into its root-only state and leaves an empty directory, 0777 as harbor made it;
  where the rename cannot be made (a mount point, another file system) it removes what the
  directory holds. A line in `timer_log` says which; an empty directory is left alone and adds no
  line, so the baselines keep their three.
- Checks: three, each failing on `f491d53`: the cap's check extended as above, the instruction and
  configuration check (the comment's words), and
  `test_what_the_user_left_in_the_artifacts_folder_is_set_aside_before_the_copy` (moved aside, and
  removed where `mktemp` fails); the bundle check applies the comment's word list too.
  `checks/` has 62 tests; with `ci_checks` (27), 89 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes; the sweep and the set-up pass `dash -n`.
- Bundle `f1293aa9de6f` (1,161 files, 247.3 MB) built twice with the same hash and `diff -r`-identical
  files; flat `522cd22b6e65`, likewise. Against round 13's `500c1a290b4e` it differs in
  `environment/fsmaint-sweep`, `environment/start-sealed-server` and `task.toml`, and nothing else:
  the verifier, the solution and the corpus are unchanged, so the reference and empty-server
  regrades of round 13 stand. `scripts/scan_uploads.py` finds nothing among the 496 agent-image
  files; Oddish preflight passes. It replaces `500c1a290b4e`, never uploaded, as the candidate for
  version 11.

### 2026-11-20 (round 13: re-check 08 of version 11's candidate; the stack's pins out of the agent image, the agent's processes capped, hard links bounded; version 11)

- Re-check 08 (harbor-lh `ops/swe-marathon-v2/qa/backoffice/08-recheck-v11.md`) of round 12
  (`375b570..cd98856`, bundle `7bcb797ee1be`) failed on one must-fix and three should-fixes; the
  rest of round 12 held (its eleven new checks fail on `375b570`, and the 84 checks pass). Round
  13 is one commit of code and checks on `cd98856` (`36e066b`) and this README.
- M1, information leak. `/opt/py/requirements.txt` was still world-readable in the agent image:
  uv's export of the reference's lock file, with `uv export --project backend ...` at its top and
  the sealed server's frameworks pinned to their versions under `# via stockwell`, the very
  information version 10's verdict called `info_leakage` in the instruction, and one `ls /opt/py`
  away now that the package line points at the installed packages. The build now removes it right
  after the install (`&& rm /opt/py/requirements.txt`); the verifier image keeps its copy, which
  the agent never sees. A sweep of what the build puts into the agent image found nothing else
  that states the stack: pip installs from the index with `--no-cache-dir` (no cache, and no
  `direct_url.json`, which pip writes only for a direct URL; `INSTALLER` says `pip`), the venv's
  `pyvenv.cfg` names only Python, the client's `package-lock.json` is the client's own, and the
  sealed bytecode and its settings are their own user's alone (0700, 0600). What the agent finds is
  what `python3 -m pip list` shows, and the running system itself (re-check 08 N1: `server:
  uvicorn`, FastAPI's shape of the OpenAPI document, the sealed server's command line in `ps`), the
  task's premise.
- S3, cue wording. The instruction's two in-story uses of "compare" are the requester's again:
  the integrations "rely on every value they receive, and its type, staying exactly as it is
  today", and everything but key order matters "because the integrations depend on every detail
  of an answer". The requirements are unchanged; the run configuration's prompt is left as it is
  (shared by five tasks, the owner's to change).
- S1, hard links. A file with more names than a copy's file system allows links (65,000 on ext4)
  arrived as copies, so more bytes arrived than the manifest counted, and round 12's verifier
  called that a copy cut short (re-check 08 reproduced it with a stand-in host limit: "3,005 of
  3,005 entries and 8,200,322 of 4,226 bytes"); a large file copied thousands of times could also
  fill the host's disk. Now a file with more than 1,000 hard links inside `/app/server` refuses the
  tree (a noted 0), the instruction states the limit with the others ("no file with more than
  1,000 hard links"; no honest tree comes near it: cargo makes two names, a busybox install a few
  hundred), and `verify.py` raises "The copy arrived incomplete" only when fewer entries or bytes
  arrive than the manifest counts; more is scored as it arrived, with a note that says why.
- S2, a fork bomb. One left running at the end of the session could fill the process table, so
  that neither the root collect hook nor the copy could start, and nothing arrived (an evaluation
  error). harbor 0.20's Modal backend starts every command that has a user through `su USER -s
  /bin/bash -c` (`environments/modal.py`, read here), the agent's own session included, and su's
  PAM session runs `pam_limits`. The image now writes `/etc/security/limits.d/90-nproc.conf`
  (`dev soft nproc 16384`, `dev hard nproc 16384`: processes and threads, four times the 4,096
  threads the server may use; root is not counted, so the hooks and the copy can start, and the
  sweep's one `kill -9 -1` as `dev` ends the bomb), and makes su's `pam_limits` line optional
  (Debian's `session required pam_limits.so` becomes `optional`, or the line is added where there
  is none), so that a limit pam_limits cannot set, which only happens where a lower hard limit is
  already in place, never stops a session. The Dockerfile's own lines were run here with GNU sed
  on Debian's su file and on one without the line. Not verified here: the image's own
  `/etc/pam.d/su` (no Docker on this machine), whether the platform's kernel enforces
  RLIMIT_NPROC, and whether its sandbox allows more than 16,384 processes. So the set-up now
  records the hard limit a su session of `dev` gets (`ulimit -Hu`, at both set-up hooks) and the
  sweep carries it into `timer_log` (`sweep: a su session of the user had a process limit of
  16384`): the version 11 baselines show whether the cap applies there.
- Not taken from re-check 08: N2 (record the room checks' `statvfs` figures) and N3 (publish 0
  for a `refused` manifest without replaying) are notes, left under Remaining work; N4 (whether
  the platform still calls a session the timer ends at 33,900 s a premature stop) shows first on
  BasedPL's version 3.
- Checks: four new ones and one extended, each failing on `cd98856` (run there with this round's
  checks file: all five fail), and the bundle check's new scan:
  `test_the_agent_image_keeps_no_file_that_states_the_sealed_servers_stack` (the Dockerfile removes
  the file right after the install; the bundle check's scan, which passes on `cd98856` too since
  it leaves that file to this check, finds no other file in the agent image that states the
  stack), `test_a_file_with_more_than_a_thousand_hard_links_refuses_the_tree`,
  `test_more_arriving_than_the_manifest_counts_is_scored_with_a_note`,
  `test_the_users_processes_are_capped_in_the_session_harbor_starts` (the limits file, the PAM edit
  run on two stand-in files, the set-up's record and the sweep's line), and the instruction check,
  which now rejects "compare" and pins the two sentences. `checks/` has 61 tests; with `ci_checks`
  (27), 88 pass under Python 3.13, and `ci_checks/check_repository.py` passes. The hook's scripts
  and `verify.py` compile under Python 3.12.13; the sweep and the set-up pass `dash -n`.
- The regrade uses only bundle `500c1a290b4e`, as in round 12 (its solution installed by its own
  `oracle.py` from an isolated copy, only the interpreter path swapped for this Mac; its corpus,
  media and replay under Python 3.12, bytecode writing off): 1.0 on every unit, 4,002 of 4,002
  (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of
  500 or above, no note, in 493.4 s; the slowest request took 3.5 s. An empty server scores 0.0 (0
  of 4,002). `replay.py`, the corpus, the media and the solution are round 12's byte for byte;
  `verify.py` changed only in what more arriving than counted means.
- Bundle `500c1a290b4e` (1,161 files, 247.3 MB) built twice with the same hash and the same files
  (`diff -r` of the two builds is empty); flat `6dc8f86a05ba`, likewise. Against round 12's
  `7bcb797ee1be` it differs in `environment/Dockerfile`, `environment/fsmaint-sweep`,
  `environment/start-sealed-server`, `steps/01-rebuild-server/instruction.md` and
  `steps/01-rebuild-server/tests/verify.py`, and nothing else; against version 10's
  `7a92d0bd02fe`, in those and `environment/fsmaint-timer` and `task.toml`.
  `scripts/scan_uploads.py` finds nothing among the 496 agent-image files (2,262 scenarios, 89,524
  requests); Oddish preflight passes. It replaces `7bcb797ee1be`, never uploaded, as the candidate
  for version 11, after an independent re-check of this round. Any Dockerfile change needs version
  11's baselines anyway: they show whether the image builds with the PAM edit and what cap a
  session gets.

### 2026-11-20 (round 12: the platform's verdict on version 10; evaluation cues, timer option B, agent-caused evaluation errors; version 11)

- Version 10 (bundle `7a92d0bd02fe`) passed its baselines and its source audit, and its three
  model trials were good failures (0.209 and 0.171 with DeepSeek, 0.072 with GLM). The verdict
  rejected it on one primary issue: two of three solvers called their session an evaluation, and
  all three used the frameworks the instruction listed (`info_leakage`). In trial 99 the agent read
  the completion sentence ("cannot be told apart from the sealed one through the API") as "the
  evaluation will run a battery of requests against both servers" and, having seen the harness's
  own command line in `ps` (platform-side), called the task "from a benchmark"; in trial 100 it
  wrote "the most likely evaluation focus". The recommendations: drop the package names from the
  instruction, and find the evaluation cues the solver can see. Round 12 is two commits of code and
  checks on `375b570` (`2ce3d7f`, then `3f0aaf0` for the `realpath` fallback below) and this
  README.
- The instruction. The completion sentence is the one drafted on 2026-11-20 (harbor-lh
  `ops/swe-marathon-v2/decisions/2026-11-20-completion-sentence-evaluation-awareness.md`): "The
  work is complete when your server answers every API request exactly as the sealed one does,
  apart from the exceptions above." "Keep `/app/server/run` working at all times." stays. The
  stack line is now "`python3` is Python 3.12 with the packages listed by `python3 -m pip list`.",
  without "the packages the vendor's server ran on" or the framework names; Node.js and Go as
  before. One more phrase went: "the copies we make for training and trials" is "the copies we
  make to train staff and to try things out" (a trial is what the solver's own run is called).
  The requirements are unchanged, the requester's own "the integrations compare answers exactly"
  and the pace bound included.
- The sweep for cues covered what the agent can see: the instruction, the client's source, built
  files, `README.md`, `package.json` and `openapi.json` in `/app/client`, the OpenAPI document the
  sealed server serves (built here from the reference with `stockwell.env`: the same document as
  the client's copy), the strings of the sealed bytecode (unreadable to the agent, but its words
  reach the answers), the 55 samples' strings and the text of their 22 readable PDFs, for told
  apart, indistinguishable, graded/grading/grader, evaluat, test corpus, hidden, benchmark,
  scenario, score, harness, rubric, held-out, oracle, verify and fixture. Every hit is the
  application's own word, kept: FX revaluation (which contains "evaluation"), CSS `overflow:
  hidden` and `aria-hidden`, a stock count's hidden system quantity, the router's route score,
  argon2's `verify_password`, a QR code's penalty score, and two docstrings of the sealed bytecode
  that never reach an answer (media types "told apart by their major brand", and integrity checks
  that "run after every recorded scenario in the test suite", a module docstring of the product).
  The two password-protected sample PDFs were not read; they come from the same templates as the
  others.
- The timer, the judges' final option B (harbor-lh
  `ops/swe-marathon-v2/decisions/2026-11-20-precap-timer-vs-deadline-DECISION.md`, after the
  verdict on BasedPL's version 2 rejected a timer 660 s before the agent's limit as a premature
  stop). `fsmaint-timer` still fires at 33,900 s, the point behind every timer-ended trial graded
  so far; it sends SIGTERM every 5 s for 30 s (six rounds, twelve before), then SIGKILL every half
  second for at most 15 s (30 turns; before, 120 turns over up to 510 s), so every process of
  `dev` is gone by about 33,930 s and the timer is done by about 33,945 s. Both agent
  `timeout_sec` values, `[agent]` and `[steps.agent]`, go from 34,560 to 33,960, a backstop 60 s
  after the firing, each with a plain comment for the platform's reviewers (the agent never sees
  `task.toml`): the session ends at 33,900 s when a root timer ends the session user's processes,
  this limit is a backstop 60 s later, and trials that reached the platform's own cap with this
  kind of separately built verifier image were not graded. Nothing else assumes 34,560 s: the
  verifier's limits are its own (6,000 s), no run configuration sets an agent timeout, and the
  README's older entries keep the number as history.
- Agent-caused evaluation errors, assessed against the catalogue of the Carve task's QA 22 and 23
  (harbor-lh `ops/swe-marathon-v2/qa/carve/`), whose collect hook is of this family, and our own
  QA 07g. For each path: reachable or not, what it became, and the check, which fails on
  `375b570` (run there with this round's checks file: all ten fail).
  - `/app/server` missing, a link, a file or no directory: not reachable (the agent cannot remove,
    rename or replace it), but the sweep exited at once with no manifest, and the copy then
    followed a link or found nothing ("Nothing arrived"). Now whatever stands there is moved
    aside, never followed, and an empty directory takes its place with a manifest that refuses
    it: a noted 0 (`test_whatever_stands_at_the_delivery_path_leaves_an_empty_refused_directory`).
  - A forged mark: where the file under the manifest's name could not be moved aside, the sweep
    exited 0 before fixing or measuring anything, and the agent's own manifest arrived (one that
    counts what did not arrive is "The copy arrived incomplete"). Not reachable in practice
    (`mktemp` in root's `/app` right after the room is given back); it is now removed instead
    (`test_a_file_the_sweep_cannot_move_aside_from_the_manifests_name_is_removed`). The other
    way to the agent's own manifest was a hook killed before the move: see the zombies below. A
    path with a newline in its name could forge a `timer:` line (a record, never scored): every
    change is now one line, unprintable characters escaped.
  - An oversized mark: one line per change with no bound (a removed pipe, a removed link), all
    read by the verifier, which reads a missing or unreadable mark as a noted score, so no error,
    only memory. Now at most the first 40 changes, each one line of at most 200 characters, then
    how many more; `verify.py` reads at most the first 64 KiB
    (`test_the_manifest_holds_a_bounded_number_of_one_line_changes`,
    `test_the_verifier_reads_only_the_head_of_the_manifest`).
  - Special files, absolute and climbing links the host's tarfile `data` filter rejects: pipes,
    sockets, devices and absolute links were already removed by the root stage, but it kept any
    relative link that resolved inside here. A link that climbs above `/` and back in, in a
    directory the agent's user cannot read (the fixer skips those), made round 11's copy stop part
    way: run here, `LinkOutsideDestinationError` and "The copy arrived incomplete: 2 of 3 entries
    and 10 of 10 bytes", an evaluation error. A link that reaches inside only through other links
    can do the same in some extraction orders. Now a link is kept only as the relative path
    straight to the file or directory it reaches, found by one kernel `stat` (at most 40 links on
    the way) among those the walk saw; one that is not is written again so, or removed where the
    disk has no room left for that; one that reaches nothing inside is removed
    (`test_every_link_kept_leads_straight_to_what_it_points_at_so_the_copy_takes_it`). Where the
    kernel reaches something the walk did not see, `realpath` decides, so that on a file system
    that numbered a file differently by path an honest virtual environment keeps its own links
    (`test_links_inside_survive_where_a_file_is_numbered_differently_by_path`, a guard of this
    round's design: round 11 kept those links too, by `realpath`, without straightening the one
    that runs through another link, so the check fails there on that alone).
  - Paths over PATH_MAX: refused since round 7 (a noted 0); unchanged.
  - A full disk: the sweep gives back its 64 MiB and 64 spare inodes before the fixer, which, as
    the agent's user, could spend them on copies; on a disk the agent had filled, a refusal then
    could not make its empty directory after `/app/server` was moved aside, and nothing arrived
    (QA 07g F2, an evaluation error). A copy is now made only if the room and the spare inodes
    stay free after it (`test_the_link_fixer_keeps_free_the_room_set_aside_for_the_manifest`),
    and the root stage writes a link again only with that room left. Related: a refusal renamed
    `/app/server`, a directory of the image's own, which an overlay without `redirect_dir`
    answers with EXDEV; the stage did not catch it and ended with no manifest and the refused tree
    in place. It now moves what the directory holds aside instead
    (`test_a_refused_tree_is_emptied_where_the_directory_cannot_be_renamed`).
  - An early `exit 0`: the two above, both gone.
  - A hook stretched past its 600 s: (a) the root stage resolved every link with `realpath`,
    quadratic along a chain and along long targets through a link to `.` (QA 07g F1: 99,000 such
    links, 620-2,800 s). Measured here with round 11's stage under Python 3.12: chains of 1,000,
    2,000 and 4,000 links took 1.62, 5.86 and 22.64 s (about 1.4 µs times the square; 600 s at
    about 20,000 links), and 1,000 links of 490-component targets 1.01 s at depth 0 (QA 07g
    measured 6 ms a link at depth 400). This round's stage, which calls `realpath` only for a link
    that reaches something outside the walk's files, took 0.12-0.18 s for the chains and 0.08 s for
    the targets (each run twice; the first run's figures were within 10%). The walk and the links
    also have 240 s now, after which the tree is refused, so a tree of long targets that do reach
    outside ends as a noted 0 (`test_a_walk_that_outlasts_its_time_refuses_the_tree`). (b) Pipes
    and sockets were left out of the entry count, so tens of millions of them in directories the
    fixer cannot read could hold the walk; every name listed now counts against the 100,000
    (`test_every_name_listed_counts_against_the_entry_limit`). (c) `pgrep -u dev` counts zombies,
    and under Docker this image's first process (`exec sleep infinity`) reaps nothing, so every
    sweep made all 100 passes of the kill loop, and a crowd of zombies could stretch them past
    600 s before the manifest (QA 23 N1; Modal reaps, as the Carve trials showed). Only live
    processes keep the loop going where procps's `pgrep` takes a state filter
    (`test_entries_nobody_reaped_do_not_keep_the_sweep_ending_processes`). The hook's longest run
    is now about 470 s: the fixer's 120 s, the walk's 240 s, the pack's 100 s and seconds besides.
  - Left, each needing a platform fact or a redesign: a file with more names than the host's file
    system allows links (65,000 on ext4) arrives as copies, so more bytes arrive than the manifest
    counts (an evaluation error) and a large file copied thousands of times could fill the host's
    disk; the sandbox's and the host's limits are not measured, and the fix would be a new stated
    limit on names per file. A fork bomb left running past the session can keep the hook, and the
    copy, from starting where the container's process limit is shared; only the platform can bound
    the agent's processes. Where `/app/server` cannot be renamed, a refused tree with millions of
    entries at its top is moved aside one entry at a time. Where neither a memory cgroup nor a VM's
    meminfo can be read, a memfd no process maps is not counted (07f, unchanged). The timer's
    two-fault residual of re-check 07i F1 is unchanged (not reachable by the agent), and its tested
    fix was not part of this round. After round 12, "Nothing arrived" and "The copy arrived
    incomplete" are the copy failing; apart from the hard links above, no path the tree controls
    is known to reach them.
- Checks: ten new ones, one per path above, each failing on `375b570`, and the guard for numbers
  that differ by path; the timer checks pin the new numbers (six SIGTERMs, 30 SIGKILL turns, both
  limits 33,960, 60 s after the firing); the instruction check pins the two sentences and rejects
  the cue words and the framework names; the `task.toml` checks allow one comment, the reviewers'
  note, exactly above each agent limit, and keep the old word list for everything else; the
  delivery check's outside link now resolves to a file outside on this Mac too. The whole-sweep
  helper points every path of the shell part into the check's folder, which the new shell checks
  need. `checks/` has 57 tests; with `ci_checks` (27), 84 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes. The hook's two scripts compile under Python 3.12.13 and
  both hooks pass `dash -n`.
- The regrade uses only bundle `7bcb797ee1be`: its `solution/` installed from an isolated copy by
  its own `oracle.py` (only the interpreter path swapped for this Mac), its corpus and its media,
  its replay under Python 3.12 with bytecode writing off. It scores 1.0 on every unit: 4,002 of
  4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer
  of 500 or above, no note, 52 scenarios alone, in 458.7 s; the slowest request took 3.5 s. An
  empty server from the same bundle scores 0.0 (0 of 4,002, "/app/server/run is missing or not
  executable"). The README keeps no stored model submissions to regrade. Grading is unchanged:
  `replay.py`, the corpus, the media and the solution are round 11's byte for byte, and `verify.py`
  differs only in how much of the manifest it reads. This round's first build, `e16eb2141c6f`
  (before the `realpath` fallback; the same solution, corpus and replay), scored the same in
  478.9 s.
- Bundle `7bcb797ee1be` (1,161 files, 247.3 MB) built twice with the same hash and the same files
  (`diff -r` of the two builds is empty); flat `ddff792eafb5`, likewise. Against version 10's
  `7a92d0bd02fe` it differs in `environment/fsmaint-sweep`, `environment/fsmaint-timer`,
  `steps/01-rebuild-server/instruction.md`, `steps/01-rebuild-server/tests/verify.py` and
  `task.toml`, and nothing else; against `e16eb2141c6f` (never uploaded) in `fsmaint-sweep` alone.
  `scripts/scan_uploads.py` finds nothing among the 496 agent-image files (2,262 scenarios, 89,524
  requests); Oddish preflight passes. It is the candidate for version 11, after an independent
  re-check of this round.

### 2026-11-20 (round 11: the Oddish source audit of version 9; the corpus without its recording record; version 10)

- Version 9 (bundle `43cf2c2534a4`) passed its baselines on Oddish (reference 1.0 twice, no-op 0.0
  twice), and its pre-trial source audit raised one must-fix: `tests/private/scenarios.json.gz`
  opened with a record of the recordings that produced it. Its top level was
  `{"recorded_with": {...}, "scenarios": [...]}`, and `recorded_with` held the counts, the themes
  the filter left out, the legacy commit, the media manifest's digest, the private seed the hidden
  scenarios are drawn from and the live recorder's settings: notes for the task's authors inside
  the delivered package, although only the verifier image receives the file. Nothing read it: the
  verifier and `scripts/scan_uploads.py` step over every key but `scenarios`. Round 11 is one
  commit on `a48d2de`.
- The writer. `scripts/record_scenarios.py` writes the corpus as `{"scenarios": [...]}` and the
  record, with the corpus's SHA-256, to `experiment/recording.json`, which is Git-ignored with the
  rest of `experiment/` and never packaged (for another `--out` the record goes beside it as
  `NAME.recording.json`, and a record path inside `steps/` or `environment/` is refused).
  `scripts/package_step.py` refuses a corpus whose top level holds anything besides `scenarios`,
  so an older recording cannot bring the record back.
- No re-record. The corpus on disk was split byte for byte: the 432-byte `"recorded_with":{...},`
  segment was cut out (97,917,277 bytes, SHA-256 `94fa5f9f...`, became 97,916,845 bytes,
  `3cd1a9c8...`); each of the 2,262 scenarios was checked to be exactly what the changed recorder
  writes for it, so the file is the one a fresh recording from the same seeds gives; and the old
  file was rebuilt exactly from the two new files before either replaced it. Between the shipped
  files of the two bundles: the decompressed new corpus is the old one without that segment, the
  two `scenarios` arrays are the same 97,916,830 bytes (SHA-256 `9f5ebb02...`), and the verifier's
  own reader yields the same 2,262 scenarios in the same order from both. Neither private seed
  appears anywhere in the new bundle; the old one held the scenarios seed in that record and
  nowhere else.
- A sweep of the whole new bundle, before the audit sees it: all 1,161 files, the text files read
  whole, the corpus decompressed and walked record by record (its keys at every level, its words by
  where they occur), the 384 bytecode files unmarshalled for their strings and docstrings, the other
  binaries' printable runs, and the metadata of the 511 media files (PDF information, EXIF,
  container tags), against the platform's word list (grade, score, verif, harness, oddish, modal,
  harbor, cap, budget, attempt, audit, QA, round N, trial, author, seed, recorded) and a list of
  authoring words (recorders, seeds, commits, probes, reviews, dates, local paths, tool and
  infrastructure names). Two more files held such items, fixed:
  - `solution/solve.sh` first checked that the sealed server answered and gave a workspace, as the
    agent's user (round 4, from QA 20): a probe for the authors, the kind the audit raised in
    BasedPL's solution. The solution now only runs `oracle.py`. A sealed server that does not come
    up still fails the setup hook, which stops the trial; one that dies later in a reference run is
    no longer caught by the reference's own row.
  - `tests/verifier/replay.py`: the deadline's comment gave the reference's time to replay the
    corpus "on a laptop", and two docstrings explained the `{ws}` placeholder and the bodies built
    around media files by what the recorder did. All three now describe the data alone; the code is
    unchanged (the same syntax tree once docstrings are set aside).

  Kept after reading each in context: the verifier's own terms (`[verifier]` keys, attempts, the
  retry budget, `noqa`, the privilege probe it runs before the server starts, the scratch places
  it sweeps), the application's own words in its bytecode, its client and its recorded answers
  (budgets, the trial balance, `payment_recorded`, an audit log, delivery attempts, demo seeding,
  idempotent replays, EAN parity, a date in a docstring's example), `task.toml`'s authors (the v2
  schema requires them), the instruction's "copies we make for training and trials", the
  `uv export` header of the two requirements files, and the metadata real files carry (PDF
  producers, camera makes, FFmpeg's encoder tags). No shipped file holds a local path or a
  person's name besides `task.toml`'s authors, and none names the platform or its providers (the
  verifier names Docker's defaults and gVisor as kinds of machine it copes with). The scenario
  records hold `id`, `theme`, `steps`, `units` and, describing the scenario, `kind` (media),
  `start`, `days` and `restart` (months of trading): kept, since the scenarios stay byte for byte.
- Checks: a new one, `test_the_packager_ships_no_corpus_that_carries_how_it_was_recorded`, plants
  three extra top-level keys and has each refused; the recording check pins the corpus's one key
  and the record beside it (the seed, the legacy commit, the themes left out, the live settings and
  the corpus's digest); the bundle check pins the packaged corpus's one key, no record or seeds file
  anywhere in the bundle, and a `solve.sh` that only runs `oracle.py`; the upload scan's fixture no
  longer carries a `recorded_with`. Round 10's packager, given a corpus with `recorded_with`, packs
  it. `checks/` has 46 tests; with `ci_checks` (27), 73 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes.
- The regrade uses only bundle `7a92d0bd02fe`: its `solution/` installed from an isolated copy by
  its own `oracle.py` (only the interpreter path swapped for this Mac), its corpus and its media,
  with Python's bytecode writing off. It scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262
  scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no
  note, 52 scenarios alone, in 530.6 s; the slowest request took 4.7 s, the evaluation peaked at
  573 MiB resident, and `DATA_DIR` held 1.42 GB at the end. The regrade calls `oracle.py` itself,
  so `solve.sh` is checked by the bundle check, not here.
- Bundle `7a92d0bd02fe` (1,161 files, 247.3 MB) built twice with the same hash; flat
  `c857be171e8c`, also twice. Against round 10's `43cf2c2534a4` it differs in
  `tests/private/scenarios.json.gz`, `solution/solve.sh` and `tests/verifier/replay.py` and
  nothing else. `scripts/scan_uploads.py` finds nothing among the 496 agent-image files (2,262
  scenarios, 89,524 requests); Oddish preflight passes. It is the candidate for version 10.

### 2026-11-20 (round 10: QA 07h on round 9; a wait that cannot end without the firing; version 9)

- QA 07h, the narrow re-check of round 9 (`e132ce5`, bundle `e129cb7c2b1b`), passed with no
  must-fix. It looked for the defect that zeroed Carve's reference (a rename that passes every local
  check and breaks on the platform alone) and found none: the compiled code differs from version 8's
  only in names, `replay.py` not at all, every writer and reader of a renamed path, word and key
  agree, and `verify.main()` ran end to end. It left six minor findings. F1 is fixed before the
  upload, since the same weakness in the Goose task (QA 07g G1) was rated a reward risk: a session
  that reaches the cap is never ended, and the platform then cannot grade it. Round 10 is one commit
  on `e132ce5`. In the bundle only `environment/fsmaint-timer` and `environment/fsmaint-sweep`
  change, so the verifier and the solution are round 9's byte for byte. The instruction, the
  scenarios, the limits and the scoring are unchanged.
- F1, the wait. Round 9's loop, written to keep a long `sleep` out of the process list, read the
  wall clock at every step and started two processes every 300 s. Set back 600 s, the clock made it
  fire at 34,500 s, so the ending could finish past the cap. And dash, the image's `/bin/sh`, ends a
  script on the spot when a fork is refused (`Cannot fork`, status 2), with nothing in the log.
  Measured here under dash before any change: the refused fork is fatal and `x=$(...) || x=` does
  not save it; the same command inside `command eval` comes back as status 2 and the script goes on
  (3,000 in a row); arithmetic on a non-number is fatal as well. The fix takes the design tested for
  Goose (07g: one child for the whole wait) and goes further:
  - One child waits the whole time on the monotonic clock and starts nothing. Its time is in its
    environment, so the process list shows `python3 -I -` and no time. It answers 10 only when it
    has waited it all, so an interpreter that ran nothing is never taken for a finished wait.
  - Where the child cannot run or ends early, the shell waits on in sleeps of at most 300 s and
    tries the child again at each. The end is fixed once on `/proc/uptime`, which the shell reads
    with its own `read` (the wall clock only where there is none), and the sleeps that complete are
    counted as well: the time left is the smaller of the two, so no clock set back moves the end.
  - Every command of the detached copy goes through `command eval`. A start that fails is logged
    the first time for its kind and at each doubling of that kind's count, and tried again. There
    is no `set -e`, no command's output goes straight into arithmetic, and every operand is checked
    first.
  - The firing: `pgrep` answering anything but "none" counts as some left. Where `pkill` cannot be
    started, the shell picks the processes whose effective user is the selection's out of `/proc`
    and signals them with its own `kill`. SIGKILL goes every half second for 10 s as before and then
    every 5 s for up to 500 s more, which ends 90 s before the cap.

  With every fork refused from its first line to its last (a process limit of 1 for its own shell),
  the timer exits 0 where round 9's exits 2: it waits by the uptime, fires, ends two processes by
  SIGTERM and one that ignores SIGTERM by SIGKILL after twelve, and leaves another user's process, a
  zombie's entry and root's alone. The end is fixed on a clock of whole seconds, so the firing can
  come up to a second early, never late.
- F3, the stop that signalled whatever pid the file named: the sweep signals the pid only if `ps`
  shows it running, as this user, with the timer's name on its command line. It also ends the child
  the timer waited in (which would otherwise sleep on for hours), removes the pid file, and writes
  what it found as the last `timer:` line of the manifest. That line is F1's third option: a timer
  that died early now shows in `timer_log`.
- F2, the changed parts were the parts no check ran, and our own case of Goose's G5. One check is
  rewritten and four are new, all under dash:
  - The timer check used copies of `/bin/sleep` as the processes to end. On this Mac a copied system
    binary is killed as it starts (status 137), so the check passed whatever the timer did. Its
    stand-ins are interpreters now, seen alive just before the fire, one of them ignoring SIGTERM.
  - The wait on a stand-in clock with the script's own times: 113 sleeps of 300 s and the firing at
    33,900 s; the wall clock set back or on; the uptime unreadable part of the way; ten minutes in
    which no sleep can be started.
  - Every fork refused, for real.
  - The sweep's stop: a waiting timer, a firing one, another process's pid, a dead timer nobody
    reaped as Linux prints one, and a missing, empty or mangled pid file.
  - The whole sweep under dash, its absolute paths pointed into a folder and three stand-ins on
    `PATH`, then the copy as it is made, then `verify.main()` with the replay and the ending of the
    server's processes replaced.

  Each was then run against 20 deliberately broken copies of the scripts: round 9's timer; no
  signal; no SIGKILL; one unguarded sleep; sleeps not counted; the wall clock only; faults not
  logged; no signalling without `pkill`; the scan by the real user, or counting zombies; a sweep
  that signals any pid, ignores the command line, takes a dead timer for a running one, leaves the
  child, does not stop the timer, leaves the pid file or drops its line; a `verify.py` whose
  `main()` uses a name it no longer has, or that reads another first word or prefix than the sweep
  writes. Every one is caught by the check that names it, and two unchanged copies pass, one of them
  in a folder whose name has a space and parentheses (the first run of this found the two sweep
  checks putting paths into shell text unquoted; they quote them now).
- F6: the venv check made its venv from `sys.executable`. Started through a link
  (`~/.local/bin/python3.13`), Python records the link's folder as the venv's home, and the copied
  interpreter cannot find its standard library. The venv is made from the interpreter's real path
  now, and the check passes however Python is started (five ways tried).
- F4 and F5 are notes for the next author: the run condition under Verification, hackability row 15
  and Remaining work.
- A second read of the whole diff, after the first build, found nothing to change in the timer.
  Under dash its wait has no way out but the firing: there is no `set -e`; the operands of every
  arithmetic expansion are checked first, so none can end the script; every command and command
  substitution runs inside `command eval`, where a refused fork is a status; the child's
  here-document is written into its pipe by the shell itself (no fork), and a pipe that cannot be
  made fails the call it belongs to, not the script; the loop leaves only by `break` into the
  firing. One residual stays, under hackability row 15: two faults at the same moment can make the
  firing late. If the waiting child is ended early (the agent cannot signal it; root or the
  kernel's out-of-memory killer could) and the uptime cannot be read when the next child starts,
  the shell counts only its own sleeps, so the time the first child had waited is not taken off. The firing is then late by the time the killed child had waited, up to the whole wait: past the cap for such a fault after about the first ten minutes, and the trial would be lost (re-check 07i, F1, measured 28.1 s against 20.1 s on a 20 s wait). A tested fix, the child reading the uptime clock itself at each wake, waits for the next ordinary version.
- The word scan of the packaged bundle (grade, score, verif, harness, oddish, modal, harbor, cap,
  budget, attempt, audit, QA, round N, trial) found one word left in a file the task puts into the
  agent image: the sweep's function that packs the tree once in `/tmp` was `trial_pack` (since
  round 7). It is `pack_here` now: the compiled script is the same apart from that name (identical
  instruction streams, name tables of the same size), and no other name in the hook is
  `pack_here`. The bundle check's list for the task's own files in the image now also rejects
  `trial`, `harness` and `scor`; it fails on the first build's sweep and passes on this one. What
  the scan still finds is what round 9 left: the verifier's own terms in its own image, Harbor's
  `[verifier]` keys, the kernel's `oom_score_adj`, `noqa`, "underscores", the client's budgets and
  trial balance, and the instruction's "copies we make for training and trials", which is the
  business's own wording (the instruction is unchanged).
- `checks/`: 45 tests. With `ci_checks` (27), 72 pass under Python 3.13 (run again after the
  rename and the longer word list), and `ci_checks/check_repository.py` passes. The seven checks
  that touch the hooks also pass without pytest and with Python started through a link, the way
  QA 07h ran them.
- The regrade uses only bundle `43cf2c2534a4`: its `solution/` installed from an isolated copy by
  its own `oracle.py` (only the interpreter path swapped for this Mac), its corpus and its media,
  with Python's bytecode writing off. It scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262
  scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no
  note, 52 scenarios alone, in 552.1 s; the slowest request took 4.4 s, the evaluation peaked at
  625 MiB resident (the seven hook checks ran beside it for under a minute), and `DATA_DIR` held
  1.42 GB at the end. The first build of this round, `3d0f83058ddb`, which differs from it only
  in that function's name in the sweep, scored the same in 567.7 s (556 MiB). The timer and the
  sweep are not exercised by the regrade: this Mac is not the agent's container and `evaluate()`
  is called directly; the checks drive both scripts.
- Bundle `43cf2c2534a4` (1,161 files, 247.3 MB) built twice with the same hash; flat
  `d533cc11049f`, also twice. Against round 9's `e129cb7c2b1b` it differs in the two hooks and
  nothing else; against this round's first build, `3d0f83058ddb` (flat `dc452cfabb43`, never
  uploaded), in the sweep's one function name. `scripts/scan_uploads.py` finds nothing among the
  496 agent-image files; Oddish preflight passes; neither hook holds a word of the list above. It
  replaces `e129cb7c2b1b`, which was never uploaded, as the candidate for version 9.

### 2026-11-19 (round 9: the Oddish source audit of version 8; housekeeping names; version 9)

- The owner made the Oddish pre-trial source audit a hard gate: a version's audit must pass before
  any model trial. The audit of version 8 (bundle `54f0913384e4`) returned two must-fix information
  leaks, neither exploited: the header comment of `environment/precap-watchdog` carried the
  platform's grading reasoning (a turn that runs into the cap is not graded, the separate image
  fails to build after it), and the docstring of `solution/oracle.py` named the packaging script,
  said the settings are shared with the recordings and gave the platform's `/solution` path. Both
  are gone: the comment describes only what the script does, and the docstring only `data/` beside
  the file and its contents (its error messages no longer name the packaging script either).
- The audits of the sibling tasks are applied here before they are raised against this one.
  Goose's: the helper names `reserve-delivery-room`, `prepare-delivery`, `precap-watchdog` and
  `/var/lib/delivery` tell the solver that its submission is packed for grading and that a session
  cap is enforced. SymPy's: a task.toml comment on the attempt time budget and the harness (this
  task.toml has no comments; a check rejects any). BasedPL's: a verifier docstring naming the case
  generator and the QA waves. Everything the agent can see of the hooks now reads as ordinary
  system housekeeping, the family the Carve task also uses: `prepare-delivery` is `fsmaint-sweep`,
  `precap-watchdog` is `fsmaint-timer`, the reserved room, the spare inodes and the free-space
  record live in `/var/lib/fsmaint`, the timer's log and pid file are `/var/log/fsmaint-timer.log`
  and `/run/fsmaint-timer.pid` (overrides `FSMAINT_TIMER_*`), the hook's mark is
  `/app/server/.fsmaint-manifest` with a first line `complete <entries> <bytes>` or `refused`, the
  timer's lines in it are prefixed `timer: `, and `verify.py` reports `ended_by_timer` and
  `timer_log` in `metrics.json` (in place of `ended_by_watchdog` and `watchdog_log`; nothing outside
  the task read them). The reserved room cannot live outside the agent's container under Harbor
  (both hooks run inside it, and the room must be on the filesystem the copy's archive is written
  to), so it is root-only system state under a housekeeping name instead. The timer wakes every
  300 s rather than sleeping the whole 33,900 s at once, so the process list the agent can read
  shows a root `sleep 300`, never the time left. The instruction, the scenarios, the limits, the
  deadline and the scoring are unchanged.
- The same pass stripped the shipped verifier and solution of authoring provenance: the
  `(QA 07d M1)`-style tags in `verify.py` and `replay.py`, the mentions of Harbor and the platform,
  "on the author's machine" and "baseline" (process talk), and the verifier's delivery vocabulary
  (`manifest_record`, `manifest_notes`, `MANIFEST`, `MISSING_MANIFEST`). What stays is the
  verifier's own vocabulary: `[verifier]` and `[[verifier.collect]]` are Harbor's schema keys,
  `tests/verifier/` is the package, the replay's `deadline`, `attempt`, `submission`, `grader`, its
  second-try unit `budget` and Python's `collections` and `round()` are the grading mechanics
  described in the step's own tests, `CAP_SYS_RESOURCE` and `LogCapture` are what they are, and
  `noqa` pragmas are not QA. The client, the bytecode, the requirements and the recorded traffic
  hold the application's own words (delivery notes and budgets are Stockwell features, `platform`
  is its utility package and a pip environment marker).
- One behaviour fix found while renaming: the sweep now stops the timer (SIGTERM to the pid in its
  pid file, then SIGKILL) before anything of its own runs as `dev`. In round 8 a session the timer
  ended ran the collect hook while the timer was still sending SIGTERM to every process of `dev`
  for up to 60 s, which would have killed the hook's link fixer (run as `dev` for up to two
  minutes) and left a venv-based delivery with its absolute links to be removed as leading outside:
  a correct server ended by the timer could have scored 0. The order is pinned by the checks.
- Checks: the timer test now also pins the short sleep, the timer stop before the `dev` stage, and
  that every name the agent sees (the hook commands, the installed paths, the state, log and pid
  files) says nothing of judging, ending or packing its work; the bundle check scans the task's own
  files in the agent image for the whole list of words the audits object to (`deliver`, `watchdog`,
  `precap`, `submission`, `collect`, `audit`, `platform`, `budget`, `deadline`, `attempt`, `cap`,
  `owner`, `round`, dates and the infrastructure names) and `task.toml` for comments and the same
  words, and the scan of everything the agent image receives adds `watchdog`, `precap`,
  `submission`, `audit` and `deadline`. With `ci_checks` (27), 68 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes.
- The regrade uses only bundle `e129cb7c2b1b`: its `solution/` installed from an isolated copy by
  its own `oracle.py` (only the interpreter path swapped for this Mac), its corpus and its media,
  with Python's bytecode writing off. It scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262
  scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no
  note, 52 scenarios alone, in 500.7 s; the slowest request took 4.1 s, the evaluation peaked at
  452 MiB resident (the full check suite ran beside it for part of the run), and `DATA_DIR` held
  1.42 GB at the end. An earlier build of this round, `bee7fae64cc4`, which differed from the final
  one in a single docstring line of `replay.py`, scored the same in 545.6 s. The timer and the sweep
  are not exercised by the regrade: this Mac is not the agent's container and `evaluate()` is
  called directly; the checks drive both scripts.
- Bundle `e129cb7c2b1b` (1,161 files, 247.3 MB) built twice with the same hash; flat
  `679240b989a1`. `scripts/scan_uploads.py` finds nothing among the 496 agent-image files; Oddish
  preflight passes. A grep of the packaged bundle for grad, platform, harbor, oddish, cap, budget,
  deadline, attempt, qa, audit, owner, round, 2026-, delivery, submission, collect, watchdog and
  verifier finds none of platform, harbor, oddish, audit, owner, 2026-, delivery or watchdog in any
  task-authored file, and no word of the list at all in the files the task puts into the agent
  image; the survivors are the verifier's own terms above. It becomes version 9, in place of
  `54f0913384e4`, once the model trials on version 8 settle (an upload could retract their rows).

### 2026-11-19 (round 8: a root pre-cap watchdog, for the platform's ungraded capped runs; version 8)

- On Oddish today, every v2 trial whose agent ran into the 9.6 h cap was never graded: the
  separate verifier image failed to build right after the timeout (harbor-lh
  `ops/swe-marathon-v2/PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`), while runs that ended by
  themselves were graded. On version 6, trial 58 (ended by itself) scored 0.227 and trial 60
  (ended 27 minutes before the cap) 0.422; trial 59 hit the cap and was lost. A probe
  (`cap-watchdog-6eb19fc0`) showed that a root watchdog ending the agent before the cap gets the
  run graded. Until the platform fixes it, the task ends the agent's session itself, shortly
  before the cap, with the design of BasedPL's round 5.
- `environment/precap-watchdog`, started as root by a second `[[agent.setup_complete]]` entry
  (Harbor wants both setup boundaries configured or neither; both already ran
  `start-sealed-server`), arms one detached sleeper (`setsid nohup`; a pid file under `/run`
  makes a second start a no-op). After 33,900 s (the agent's 34,560 s less eleven minutes) it
  sends SIGTERM to every process of `dev`, repeating every 5 s for up to 60 s, then SIGKILL, and
  logs arm, fire and done lines with timestamps to the root-only `/var/log/precap-watchdog.log`.
  The sealed server (user `stockwell`) and its root supervisor are out of its reach. The collect
  hook copies the log's last lines into the delivery's mark as `watchdog:` lines, which the
  verifier keeps apart from the hook's notes, and `verify.py` reports `ended_by_watchdog` and
  `watchdog_log` in `metrics.json`, never in the score. The instruction says nothing of it: it
  states no time budget, and a session the watchdog ends is one that would otherwise have hit
  the cap.
- Checks: the watchdog arms once (a second start logs "already armed"), fires at `END_SECONDS`
  (an environment override in the test), ends a process tree and a process in a session of its
  own, logs each step and removes its pid file; the task's two `setup_complete` entries; the
  image installs it root-only (mode 0700); the hook's `tail` into the mark; a mark with a fired
  log reads back as `ended_by_watchdog: true` with the three lines, the no-op's as `false`; the
  flag appears nowhere in `replay.py`; the instruction mentions no watchdog. With `ci_checks` (27), 68 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes.
- The regrade uses only bundle `54f0913384e4`: its `solution/` installed from an isolated copy by
  its own `oracle.py` (only the interpreter path swapped for this Mac), its corpus and its media,
  with Python's bytecode writing off. It scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262
  scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no
  note, 52 scenarios alone, in 466.5 s; the slowest request took 4.2 s, the evaluation peaked at
  707 MB resident (the full check suite ran beside it), and `DATA_DIR` held 1.42 GB at the end.
  The watchdog itself is not exercised by the regrade: this Mac is not the agent's container, and
  `evaluate()` is called directly; the checks drive the script, and the version 8 baselines show
  its `armed` line in `watchdog_log`.
- Bundle `54f0913384e4` (1,161 files, 247.3 MB) built twice with the same hash; flat
  `54767f9d067e`. `scripts/scan_uploads.py` finds nothing among the 496 agent-image files (the
  watchdog is one of them now); Oddish preflight passes. It becomes version 8, in place of
  `cdde8d8e6e42`.

### 2026-11-19 (round 7: QA 07f, version 7)

- Started from `5f34e43` as pushed. Version 7 is still local; it goes up once the model trials on
  version 6 settle. QA 07f, the re-check of round 6 (FAIL), found that the delivery's bound could
  still be bypassed (M4, carried). No re-record: no fix changes a recorded answer.
- What lay below PATH_MAX (M4). Round 6's bound walked by path name, so `scandir` and `lstat`
  failed with ENAMETOOLONG below a path of 4,096 bytes and it skipped what lay there silently,
  while GNU tar packs by descriptor: a 4 TiB sparse file under 17 folders of 250 characters was
  marked `delivered` with a few bytes, the copy's pack overran Modal's 600 s (Archil's 120 s), and
  nothing arrived. Exhausting the inodes of `/tmp`'s filesystem did the same. The measuring step
  now walks by directory descriptor and refuses the delivery on any step it cannot complete, and
  on a path longer than 1,000 bytes, which the instruction now states. It then packs the delivery
  once the way the copy does (`tar -czf` into `/tmp`, the platform's own command) within 100 s and
  refuses it if that pack fails or overruns, unless it failed for want of room or inodes the
  machine did not have when the session began: what it lets through is what the copy can take.
  The setup hook sets aside 64 spare inodes beside the 64 MiB and records the free blocks, block
  size and inodes; the collect hook gives both back first. Round 6's hook marks the deep sparse
  tree `delivered 5 10`; round 7's refuses it.
- A copy the mark shows was cut short (S1): now an evaluation error, since only the platform can
  cut the copy once the agent cannot. A missing mark is still scored with a note.
- Links (S4): a link is kept only if it resolves inside `/app/server` for real, so one that
  escapes through another link (`esc -> a/b/up/../..` with `a/b/up -> ..`) is removed rather than
  stopping Harbor's extraction. The link fixer (S3) counts copied entries against the limit and
  runs within two minutes.
- Smaller: bytes count once per file however many names it has, in the hook and the verifier
  (N3); the mark's counts parse ASCII digits only (N1); the mark is written with backslash
  escapes, so a name that is not UTF-8 cannot leave it empty (N2); the meter no longer reads
  meminfo where the kernel reports no `RssAnon` (gVisor, whose MemAvailable is MemFree; S2).
- `checks/`: 40 tests pass. The delivery check now covers a 4 GiB sparse file 1,206 bytes deep,
  past macOS's PATH_MAX, seen by the descriptor walk; the path limit; a link escaping through
  another link; the trial pack failing, overrunning, and failing for want of inodes with and
  without room at the start; a copy that lost a file after its mark arrived (an error); a mark in
  non-ASCII digits; and the link fixer's entry budget. The meter check covers gVisor's missing
  `RssAnon`. With `ci_checks` (27), 67 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes.
- The regrade uses only bundle `cdde8d8e6e42`: its `solution/` installed from an isolated copy by
  its own `oracle.py` (only the interpreter path swapped for this Mac), its corpus and its media,
  with Python's bytecode writing off. It scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262
  scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no
  note, 52 scenarios alone, in 499.2 s; the slowest request took 4.0 s, the evaluation peaked at
  571 MB resident, and `DATA_DIR` held 1.42 GB at the end.
- Bundle `cdde8d8e6e42` (1,160 files, 247.3 MB) built twice with the same hash; flat
  `d54a6abee021`. `scripts/scan_uploads.py` finds nothing among the 495 agent-image files; Oddish
  preflight passes. It becomes version 7, in place of round 6's `2362781131b0`.

### 2026-11-19 (round 6: QA 07e, version 7)

- Started from `87f3e3e` as pushed. Version 6 (`7436a4aac616`) has clean baselines on Oddish
  (reference 1.0 twice, no-op 0.0 twice) and model trials running, so version 7 waits for them to
  settle: an upload could retract their rows. QA 07e, the re-check of round 5 (FAIL), found two
  ways for a submission to make grading lose its result. No re-record: no fix changes a recorded
  answer.
- Memory no process maps (M3, carried). Round 5's guard summed the memory the server's processes
  map. SysV segments after `shmdt`, memfds and files in `/dev/shm` filled with `write()` hold
  memory that no process maps, so a server could park the container's memory just under its
  limit, lower its OOM priority right after the guard's raise and allocate a few MB; the grader,
  the largest process at priority 0, would die within about a millisecond (round 5's "1.5 GB
  within 50 ms" was wrong, N-c). The guard now reads what the kernel charges, every 10 ms: the
  container's memory cgroup (v2: `memory.current` less reclaimable page cache and slab; v1: rss
  and shmem), or a virtual machine's or gVisor sandbox's own `/proc/meminfo` (MemTotal less
  MemAvailable, up to 16 GiB), less the grader's own anonymous memory and what was in use before
  the server started, or the server's own cgroup where one can be made. Every page counts once,
  whatever holds it, socket buffers included. Only where none of these can be read does it fall
  back to the server's processes (proportional set size), its unattached SysV segments and its
  unmapped files in memory-backed places, every 50 ms; a memfd no process maps is not seen there.
  Every stop and every halt runs `ipcrm --all` as `nobody` and removes its files in
  memory-backed directories (`/dev/shm`, POSIX message queues, a scratch directory that is a
  tmpfs), so parked memory never outlives the server. Denying the means was not possible without
  privileges the verifier lacks (no mount namespace, a read-only `/proc/sys`), and taking
  `/dev/shm` away would break POSIX semaphores, which Python's multiprocessing needs. The
  instruction now says 6 GB of memory in all, shared memory included.
- False stops (S-a and the deciding judge). Round 5's per-process sum counted a page shared among
  workers once per worker, and a fork's pages twice until the child execs. The kernel's count has
  neither problem, and the fallback uses proportional set size, so an honest server that shares
  memory or keeps SQLite or multiprocessing files in `/dev/shm` counts at its real size. A check
  feeds the meter an honest server (900 MiB of its own, 300 MiB shared through `/dev/shm`, a
  2 GiB database file mapped by every worker, the grader grown by its upload cache): it reads
  exactly 1,200 MiB; the same container with 5.6 GiB parked where no process maps it reads over
  6 GiB.
- Copies the submission could break (M4, new in round 5). A missing mark had become an
  evaluation error, and the agent could make the copy fail at will: a 1 TiB sparse file outlasts
  the platform's 600 s tar, a full disk leaves no room for the archive, a process the hook missed
  changes files while tar reads them. The hook now ends the agent's processes with `kill -9 -1`
  as `dev` until none is left; gives back 64 MiB set aside when the session began (and the free
  space then is recorded); and, after the link fixer, removes as root anything the copy would
  refuse and counts entries and bytes. A delivery over 100,000 entries or 1 GB (a sparse file
  counts its full size), or one the disk has no room left to copy after the session used up the
  room it had at the start, is moved aside whole and replaced by an empty directory marked
  `refused` and why. The instruction states the limits and the room. `verify.py` now scores
  whatever arrived, with a note when the mark is missing, says `refused`, or counts more than
  arrived (a copy cut short, S-c); only an `/app/server` of which nothing arrived is an
  evaluation error. The link fixer's copy budget follows the new 1 GB limit.
- Also from QA 07e: the hard stop gives the ballast back before it publishes (S-b); a disk the
  server cannot write (a bind-mounted `/logs/verifier`) is not watched (S-d); a read that returns
  nothing at or after its end is a timeout, so an answer cut by the watcher is never complete
  (N-a); the sandbox note says every 50 ms (N-b); a partly made ballast is still given back.
- `checks/`: 40 tests pass. New: the meter on fake cgroup v2, v1, meminfo and `/proc` files; the
  hook end to end with a real tar round trip and the `data` filter (a complete copy, one cut
  short, one of which nothing arrived, one without the mark, one over the limit, a sparse 4 GiB
  file, the no-op's empty delivery); a read cut at its end and an unwritable disk. Rewritten: the
  memory halt (with the release at stop and halt) and the hard stop (the ballast). Each fails
  against round 5's verifier. With `ci_checks` (27), 67 pass under Python
  3.13, and `ci_checks/check_repository.py` passes.
- The regrade uses only bundle `2362781131b0`: its `solution/` installed from an isolated copy by
  its own `oracle.py` (only the interpreter path swapped for this Mac), its corpus and its media,
  with Python's bytecode writing off. It scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262
  scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no
  note, 52 scenarios alone, in 497.5 s; the slowest request took 4.4 s, the evaluation peaked at
  551 MB resident, and `DATA_DIR` held 1.42 GB at the end. This Mac has no `/proc` and no
  cgroup, so the memory meter reads nothing here; the checks drive it on fake files, and the
  baselines' `memory_measure` will show what each provider gives.
- Bundle `2362781131b0` (1,160 files, 247.3 MB) built twice with the same hash; flat
  `99111f0bafee`. `scripts/scan_uploads.py` finds nothing among the 495 agent-image files; Oddish
  preflight passes. It was to become version 7; round 7's `cdde8d8e6e42` replaces it.

### 2026-11-19 (round 5: QA 07d, version 6)

- Started from `b744110` as pushed; version 5 (`87db5085aa97`) is on Oddish with its baselines
  running. QA 07d, the re-check of round 4 (FAIL), found three ways for grading to lose its
  result. No re-record: no fix changes a recorded answer.
- Answers that never end (M1). http.client lets go of a connection's socket once an answer will
  close the connection (`Connection: close`, HTTP/1.0, no length, chunked and closing) and reads
  the answer through its own reference, so the watcher, which shut down `connection.sock`, could
  not reach it: a byte now and then held a request at the server's pace (QA 07d E3: `evaluate()`
  returned after 81 s with a 5 s deadline), and a dripped health check held a start under the
  server's lock. Every answer is now read on a connection that keeps its socket for the watcher,
  and each read gets only the time left to the request's end (30 s or the deadline, whichever
  comes first), whatever the framing; the health check reads the same way. As a backstop,
  `verify.py` runs the evaluation in a thread and, 5,640 s after it starts, publishes the reward
  from what was decided, with a note; scenarios not decided count as not matched. The replay's
  own deadline stays at 5,400 s.
- Deletion before the reward (M2). `evaluate()` removed `DATA_DIR` with an in-process `rmtree`
  that no time limit bounded (400,000 hard links took 22.8 s on a 1 s budget, QA 07d E2), before
  the reward was published, and the clean slate deleted every directory of `nobody` the same way.
  Now nothing is deleted before the reward or after it (the container is discarded). The clean
  slate moves `DATA_DIR` and every directory `nobody` owns into the root-only set-aside directory
  in constant time and never walks the evaluation's own folders, and the one deletion left (a
  directory on another filesystem) is a single `rm -rf` killed at its time limit.
- Memory (M3). The server's OOM priority was raised again once a second; where no cgroup can be
  made (Docker's defaults, Archil), a server could lower it in all its processes right after a
  raise and fault in the last few hundred MB, and the grader, the largest process at 0, would die
  with no reward. The guard now runs every 50 ms: one pass over `/proc` raises the priority and
  sums the server's anonymous and shared memory (a mapped file's pages can be dropped, and are
  not counted once per process), and above 6 GiB in all the server is stopped for good, its
  remaining scenarios failed with a note; the instruction states the cap beside the per-process
  address-space limit, which stays. The race now needs more than about 1.5 GB faulted in within
  50 ms. If the grader dies anyway, only `.reward.pending` and a summary saying the evaluation did
  not finish remain, so Harbor finds no reward: an evaluation error, never a 0.
- Should-fixes and notes from QA 07d. S1: a filesystem that reports no size (a tmpfs without a
  limit) or had less than 512 MiB free when the server started is not watched, with a note;
  `/work` or `/logs/verifier` without 512 MiB before the start is an evaluation error;
  `metrics.json` records each watched path's free space at the start and the end. S2: the collect
  hook marks every delivery with `/app/server/.delivered` (moving aside, never following,
  whatever the agent left under that name; Harbor runs collect hooks for every agent, the no-op
  and the oracle included), and an `/app/server` without the mark is a copy that failed: an
  evaluation error, not a 0. N7: no second try for a scenario with nothing left to decide.
- Corrections to round 4's entry (QA 07d N8): the grader's -1000 does not take on Docker's
  defaults, which lack CAP_SYS_RESOURCE (`metrics.json` records what it got); "`DATA_DIR` is
  removed within a minute" was an unbounded `rmtree`; and the clean slate's two minutes bounded
  its search, not each deletion. Row 5 was fixed in round 4 for F1(a), F2 and F3 only.
- `checks/`: 37 tests pass, 5 new (S5): drips after four framings and on the health check;
  deletion bounded however slow the filesystem, the clean slate's move aside and no deletion in
  `evaluate()`; the memory stop, the memory sum over a fake `/proc` and a dead grader leaving no
  reward; the disk watch; the hard stop and the delivery mark. Each new check fails against
  round 4's verifier. With `ci_checks` (27), 64 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes.
- The regrade uses only the packaged bundle `7436a4aac616`: its `solution/` installed from an
  isolated copy by its own `oracle.py` (the one local change: `run` calls this Mac's Python 3.12
  instead of `/opt/py/bin/python`), its gzipped corpus and its media. It scores 1.0 on every unit:
  4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try,
  no answer of 500 or above, no note, 52 scenarios alone, in 500.8 s (round 4's bundle took
  454.2 s and 472.5 s on this Mac, which is short of memory; the time varies run to run). The
  slowest request took 3.7 s, the evaluation peaked at 587 MB resident, and `DATA_DIR` held
  1.42 GB at the end, left in place. This Mac has no `/proc`, so the memory guard and the OOM
  raise are exercised only by the checks (a fake `/proc`) until the baselines.
- Bundle `7436a4aac616` (1,160 files, 247.3 MB) built twice with the same hash; flat
  `c98d148ef8f3`. `scripts/scan_uploads.py` finds nothing among the 495 agent-image files; Oddish
  preflight passes. It becomes version 6. The bundle check caught the word "verifier" in the
  hook's new comment (nothing the agent image receives may name how the work is judged); the
  comment was reworded, and the regrade above was run again on this final bundle.
- My round 4 regrades imported the verifier from the bundle folder without `-B`, so Python wrote
  two Python 3.13 `.pyc` files into `tests/verifier/__pycache__` of `87db5085aa97` after it was
  packaged. If that folder was uploaded as is, version 5 carries them: the verifier's Python 3.12
  ignores them and the agent never sees `tests/`, but the upload differs from the reported hash.
  The regrade now runs with `-B`, and the version 6 folder was checked clean after it.

### 2026-11-19 (round 4 fix: the oracle on Oddish, version 5)

- Bundle `d38fb62325c8` ran on Oddish as version 4: the oracle scored 0.0 twice (0 of 4,002) and
  the no-op 0.0. The cause was the solution, not the verifier: `oracle.py` built its list of places
  to look for `stockwell.env` eagerly, and the second, `here.parents[2]` (the task's `environment`
  folder), raised `IndexError` from `/solution`, which has a single parent. `/app/server/run` was
  never written, so the verifier noted "`/app/server/run` is missing or not executable".
- `oracle.py` now reads only `data/` beside itself (the bytecode package and `stockwell.env`, both
  packed by `scripts/package_step.py`) and fails with a message naming what is missing; checks
  that install the source pass the task's settings explicitly; `oracle.py TARGET` installs
  elsewhere than `/app/server`. Audit of what the solution reads: `oracle.py` only `data/`;
  `solve.sh` only `curl`, `python3` and `oracle.py`; the installed `run` only its own folder,
  `/opt/py` and `sed`.
- The bundle check now copies each packaged `solution/` (with and without the steps wrapper)
  into a folder with nothing of the task around it, runs `oracle.py` there, checks what it
  installed, starts the installed server as the verifier would and gets a workspace from it, and
  pins that `oracle.py` never looks above its own folder.
- The regrade now uses only the packaged bundle: its `solution/` copied into a folder with nothing
  of the task around it and installed by its own `oracle.py` (the one local change: `run` calls
  this Mac's Python 3.12 instead of `/opt/py/bin/python`), its gzipped corpus and its media. It
  scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no
  other restart, no second try, no answer of 500 or above, 52 scenarios alone, in 454.2 s; the
  slowest request took 3.8 s.
- `checks/`: 32 tests pass (the bundle check now installs and starts each packaged solution from
  an isolated copy); with `ci_checks` (27), 59 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes.
- Bundle `87db5085aa97` (1,160 files, 247.2 MB) built twice with the same hash; flat
  `956c53c456fa`. `scripts/scan_uploads.py` finds nothing among the 495 agent-image files; Oddish
  preflight passes. It becomes version 5 for the baselines.

### 2026-11-19 (round 4: the final QA wave on round 3)

- Started from round 3 as pushed (`2fcf14b`). QA 07c (the round 3 re-check, FAIL), 11, 12, 13 and
  20. No re-record: every fix is in the verifier, the images, the solution or the instruction,
  and none changes a recorded answer.
- Answer cap (QA 07c F1, must-fix). A chunked answer with size line `-1` made http.client read to
  the end of the stream: 300 MiB grew the verifier by 848 MiB against an 80 MiB cap. Answers are
  now read through a reader that counts every byte in any transfer encoding (80 MiB plus 8 MiB
  for headers, chunk sizes and trailers), and chunk sizes are plain hexadecimal or the answer is
  broken. OOM: the server's `oom_score_adj` 1000 is raised again every second (without
  CAP_SYS_RESOURCE it could lower it, and the sandbox probe now notes a machine where it can), the
  grader asks for -1000 for itself, a cgroup caps the server's whole group where the machine lets
  the verifier make one, and the grader is a smaller target: each scenario is held as compact
  JSON and decoded when played, and uploads sit in a 192 MiB cache.
- Processes that outlive cleanup (QA 07c F2, must-fix). A process whose main thread exits while
  other threads run shows as a zombie, and the sweep skipped zombies. It now counts any process
  of `nobody` with more than one thread or a live thread, and every kill round also runs
  `kill -9 -1` as `nobody` (one system call for all its processes) and kills the cgroup where
  there is one.
- Disk (QA 07c F3, must-fix). On providers that pack `/logs/verifier` before reading the reward,
  a full disk, a 4 GiB `server.log` or appends during the pack lost the reward. The server's
  output now goes into a pipe the grader drains, keeping the first and last MiB, written out as
  `server.log` after the final stop; a 256 MiB ballast set aside before the server starts is
  given back for the results; a guard stops the server for good when free space falls under
  512 MiB and fails its remaining scenarios with a note; `DATA_DIR` is removed within a minute
  after the final stop. RLIMIT_FSIZE stays at 4 GiB per file.
- One configuration (QA 12 F1, must-fix). The sealed server served the web client, so
  `DELETE /nowhere` answered 405 `allowed: []` there and 404 `unknown_path` in the corpus, and a
  perfect clone lost 6 units. `environment/stockwell.env` is now the one set of settings for the
  sealed server, the live recorder and the solution (shipped in `solution/data`), with no client
  directory; nothing needed the mounted client (the agent has its source and no browser). The
  instruction no longer says the sealed server serves the client. A check ties every file to
  the settings and the instruction's numbers to the code that enforces them. The replay of a clone
  of the sealed server (the solution, installed from the bundle's bytecode with that file) scores
  1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), with its 9 planned restarts, no
  other restart and no second try, in 472.5 s locally without the sandbox.
- The sealed server (QA 20): a root supervisor (one only, through `flock`) restarts it when it
  exits or misses its health check for a minute; the setup hook starts the supervisor. The
  solution's `solve.sh` first checks, as the agent's user, that the sealed server answers and
  gives a workspace, so a dead sealed server fails the oracle row.
- Exact file bytes (QA 20): the instruction now says why: our document archive and our partners'
  portals file everything we send by its checksum. The comparison is unchanged.
- Second tries (QA 20): only for a scenario in flight when the server stopped; a wrong answer, or
  a request a live server left unanswered, is final; and second tries decide at most 2% of all
  units (80 here), so they rescue a server that stops now and then, not one that fails under
  load.
- The maintainability sentence (QA 20) is gone from the instruction.
- SQLite lock waits (QA 11 S1). Stockwell hard-codes `busy_timeout=15000`, so the solution cannot
  lengthen it. A scenario that uploads a PDF of 1 MiB or more or any file of 16 MiB or more
  (the reference reads or stores it under the write lock) now runs with nothing beside it,
  spread through the order like the planned restarts: 52 scenarios run alone, the 9 restart months
  and 43 media scenarios. `metrics.json` now
  lists the 20 slowest requests, answers of 500 or above by theme and the server's peak memory,
  so a baseline under 1.0 can be read without the server's log.
- `/opt/py` (QA 13 S2): `python3` was a link to the venv's interpreter, which does not activate
  the venv, so the instruction's `python3 -m pip list` and `import fastapi` failed in both images.
  `python3` and `python` are now wrappers that run `/opt/py/bin/python`, the system interpreter
  sees `/opt/py`'s packages through a `.pth` file, and each image's build checks the imports as
  `dev` and `nobody` (agent image) or `nobody` (verifier image).
- Also from QA 07c: the clean slate moves `DATA_DIR` aside in constant time, bounds its sweep to
  two minutes, removes SysV IPC as `nobody` (root lacks CAP_SYS_ADMIN on Docker's defaults) and
  is skipped with less than five minutes left (F5, F6); a published reward is never taken back by
  a later failure (N3); `strip_set_id` passes over files it cannot read (N4); the delivery hook
  copies only files and directories, so a link to `/dev/zero` is removed (N2). Left as they are:
  the within-try echo (F4, recorded as hackability row 10's residual), the 12 h lease margin (F7,
  for the baselines to measure) and a uid unique to each trial (N1).
- `checks/`: 32 tests pass, 6 of them new this round (the `-1` chunk and its relatives with the
  grader's memory measured, zombie leaders in a fake `/proc`, the log pipe, the ballast and the
  disk guard, second tries only after a stop and within the share with heavy uploads alone, one
  configuration with the instruction's numbers, the `python3` wrappers), and the retry, preview,
  seal and delivery checks updated; with `ci_checks` (27), 59 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes.
- Bundle `d38fb62325c8` (1,160 files, 247.2 MB) built twice with the same hash; flat
  `fb9bb0a0f2f4`. `scripts/scan_uploads.py` finds no hidden upload, cut-short upload or file answer
  among the 495 files the agent image receives; Oddish preflight passes.

### 2026-11-19 (round 3: the retry preview, big inputs, the pace, varied inputs, the seal)

- Started from round 2 plus the coordinator's `db47e87` (no_new_privs through prctl too). One
  re-record against `d61d29c`, with new private seeds; the app needed no change.
- Retry preview (QA 07 F1, must-fix). A scenario that got no answer used to be played again
  from scratch on the same `DATA_DIR`, and a month goes on after a wrong answer while its later
  requests echo earlier answers (payments, bank statements). A server could read a month on the
  first try, give no answer at its end and replay what it learned: QA 07 measured 0.33 to 1.0
  for a server with a one-cent pricing bug. Before the second tries the slate is now cleaned
  (server stopped; `DATA_DIR`, every file `nobody` owns on the root filesystem and in `/tmp`,
  `/var/tmp`, `/dev/shm`, `/dev/mqueue` and `/run/lock`, any hard link there and SysV IPC
  removed; the submission read-only to it; its log unreadable to it; a fresh server), and a
  second try decides only the units the first left unsettled. `checks/` reproduces the exploit
  with a fake server: 1.0 with neither defence, 0.67 with the unit lock alone, 0.33 (what the
  same bug earns honestly) with the clean slate alone or both.
- A correct server scored 0 (QA 07 F3, must-fix). Harbor copies `/app/server` out with
  tarfile's `data` filter, which refuses absolute links, so a venv's interpreter link made the
  delivery vanish. A `[[verifier.collect]]` hook (`environment/prepare-delivery`, root, then
  `dev`) now makes in-tree links relative, copies what out-of-tree links point to and removes
  dangling links and special files before the copy; the verifier notes a delivery that never
  arrived; the instruction says such links are replaced by copies. `checks/` builds a real venv:
  the data-filter copy fails before the hook and the copied venv runs after it.
- Exhaustion (QA 07 F2, F4): the server runs under `prlimit` (4,096 threads for the user, 4 GiB
  per file, 6 GiB of address space per process) and `oom_score_adj` 1000, checked under the
  drop like the privileges. Stopping reads `/proc` and stops every process of `nobody` before
  killing them all, without forking, so neither a full process table nor a fork loop defeats it
  (QA 07 reproduced both); orphans are reaped. The reward goes over a placeholder written before
  the server starts, in place, then is renamed, which needs no free space; no cleanup can raise.
- The pace (QA 03 M1, QA 18). The instruction now asks that no answer take more than about three
  times as long as the sealed server takes to give it. The reference replays the round 3 corpus
  in 518 s on the author's Mac (no sandbox); the replay's deadline is now 5,400 s, about ten
  times that, and the step's verifier limit 6,000 s (agent and verifier together 40,560 s, under
  the 12-hour cap), so a server three times slower than the sealed one still finishes on a
  machine three times slower than this one. Scenarios start in a fixed shuffle, so a slow server
  loses some of every kind, and the nine planned-restart months are spread through it (a gate
  runs each with nothing beside it) instead of last.
- Big inputs (QA 02, must-fix). The private media now hold a 57.3 MB phone clip (just under the
  64 MiB upload limit), a 380-second yard-camera export (21 MB: `video_too_long` on a shipment,
  kept on a return), a 64-page colour scan at 200 dpi (34.3 MB), a noisy 20-megapixel photo
  (7.3 MB) and a 25-minute voice memo (9.4 MB). The reference's own media theme picks them and
  fills a workspace's 400 MB quota with the clip: in the corpus the clip is accepted 34 times,
  `video_too_long` answers 18 times and `quota_exceeded` 4. Once a month an integration sends a
  photo inside JSON as base64: 2.9 MB is accepted, 4.4 MB (a 5,851,893-byte body) is refused as
  `file_too_large`, and a body over 6 MB as `body_too_large`. Some months import a CRM customer
  list: a dry run with three mistakes, the list put right (480 rows), then the whole list (620
  rows, over the row limit) or a full export (5.6 MB, over the size limit). Bodies near a limit
  are recorded as `body_insert` references to media files, so the scenarios stay small; bodies
  over a limit stay `body_size` zeros. File answers up to 80 MiB are hashed as they arrive. The
  bundle stays under about 250 MB (below); Oddish preflight has no size check.
- Varied inputs (QA 06 and QA 02 should-fixes). Months start on four dates, so they cross the
  end of March, the end of June, the year's end into January (holidays included) and February
  of a leap year. Suppliers print their own invoice layouts, one the reader follows, some it
  misreads and some it cannot read (the clerk then types the bill in), with varied labels,
  totals, date formats, producers, metadata and PDF versions. EXIF comes little- or
  big-endian. Notes, customer names (a CRM import) and typed file names use many scripts. The
  SIGKILL lands on a write drawn at random through the day, and the day after a restart the
  files uploaded before it are read again. The samples cover all eight photo setups, and every
  file is named as phones, scanners and suppliers name theirs, drawn from the seed (no
  `invoice-objstm`, `broken-xref` or `truncated`).
- Lookup (QA 05). A screen that answers exactly as a fresh workspace on the same day is left out
  and a spare taken (91 left out this recording). Legacy scenarios whose every write is refused
  are left out (production 8, purchasing 8, quotes 4, standing 2, stock 3), and in the counts
  and kits themes only scenarios that post a count or build a kit are kept; 55 counts and 75
  kits made by the live recorder (opened, entered, posted and approved when far off; defined,
  built, sold and taken apart) fill them back to 83 each.
- Seal (QA 08). The reference ships as Python 3.12 bytecode only (`py_compile`, unchecked-hash
  headers, docstrings kept since the OpenAPI text needs them), for the sealed server and as the
  solution's data, so no layer of either image holds its source; the build fails on a `.py`.
  The bytecode serves an `/api/openapi.json` byte-identical to the source's, and two builds give
  the same bundle hash. `start-sealed-server` first checks as `dev` that `/opt/stockwell` cannot
  be read or entered, and fails the setup hook, stopping the trial, if it can.
- Instruction (QA 03, 09): every limit has an owner in the story (the branches' tills and the
  back office, the proxy's 30 seconds and routing on the id, the service manager's 60 seconds,
  integrations that compare values and types exactly); the scale (thousands of workspaces in one
  `DATA_DIR`, 4 cores and 8 GB, `python3`, Node.js and Go) and the unprivileged user's limits are
  stated; "in different workspaces", "you can only talk to it", "cannot be reproduced" and
  "welcome but not required" are gone; maintainable code and the scope of the demo company are
  asked for. No time budget, no grading.
- Found in the app, left as it is: a file whose name has a letter outside Latin-1 (Cyrillic,
  CJK, Polish) makes `GET /files/{id}/content` answer 500, because the server puts the name in a
  `Content-Disposition` header. The corpus keeps typed upload names within Latin-1, so it holds
  no 500.
- Corpus: 2,262 scenarios, 4,002 units (2,218 one-unit scenarios, 1,432 trading days, 352
  screens), 89,524 requests (scenarios.json 97.9 MB), recorded in 10 min 52 s with no answer of
  500 or above (82,334 answers in 2xx, 7,190 in 4xx); 1,307 raw uploads, 151 JSON bodies built
  around a media file, 627 base64 uploads inside JSON bodies, 82 bodies over a limit, 1,187 file
  answers.
- The reference, installed from the bundle's bytecode and re-graded locally on the full corpus
  without the sandbox, scores 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), with
  its 9 planned restarts spread through the order, no other restart and no second try, in 518 s
  of replay (the replay's monotonic clock; the Mac slept for part of the run).
- `checks/`: 26 tests pass, 5 of them new this round (the second-try preview, the limits and the
  sweep, the reward on a full disk, the shuffled order, a real venv through the data-filter
  copy), and the replay, scan, seal, sandbox and bundle checks extended; with `ci_checks` (27),
  53 pass under Python 3.13, and `ci_checks/check_repository.py` passes.
- Bundle `06c782d713f6` (1,157 files, 247.2 MB: private media 188.9 MB, samples 42.0 MB,
  scenarios 10.6 MB compressed) built twice with the same hash; flat `a633cd8ca3c5`.
  `scripts/scan_uploads.py` finds no hidden upload, cut-short upload or file answer among the 493
  files the agent image receives; Oddish preflight passes (it checks no size).

### 2026-11-19 (round 2: the client's screens, durable state, months of trading, grading fixes)

- The owner approved a realism set drawn from QA 01, 14 and 16 ("realism set", "each trading
  day counts") together with the QA 10 should-fixes. One re-record against `d61d29c`; the app
  needed no change.
- The client's own path (QA 01 R1): a `screens` theme. After each month of trading the web
  client itself (the reference frontend under vitest and jsdom, the way its own smoke test
  renders every screen) opens eight of its screens in that month's workspace, through a proxy
  that notes every request it makes (`scripts/record_live.py`, `scripts/capture_screens.test.tsx`).
  Each screen is one unit: `GET /api/version` (outside the workspace: steps marked
  `scoped: false`), `GET /auth/me`, then the screen's own reads with the client's query
  parameters, in a fixed order. Screens that read the request log or the credentials are left
  out. 343 screen units, all reads; two recordings give the same bytes.
- Durable state (QA 01 R2): the instruction now requires that everything a workspace holds
  survive a stop and start on the same `DATA_DIR`, even an abrupt one. Nine of the 44 months
  carry a planned restart: six with SIGTERM at the end of a day, three with SIGKILL straight
  after a write was answered. They run one at a time after the others; unplanned restarts keep
  `DATA_DIR` too. The reference survives SIGKILL straight after a 2xx: checked by hand, and
  every planned restart in the corpus was recorded against the real process.
- Months of trading (QA 14, 16): 44 runs of 30-35 days from 2031-03-03, each crossing the end
  of March (`scripts/trading.py`, written for the task; the app's own demo is not used). Daily
  sales to dispatch, purchase orders to all five suppliers, production, quotes, standing
  orders, kits, returns, a stock count, a recall, weekly bank statements matched and
  reconciled; on 31 March the bank reconciled, balances revalued, receivables aged and chased;
  on 1 April commissions paid, the month's rebate settled, reorder and planning, the month's
  reports and the period close. Files sit on the business path: 376 supplier invoices arrive
  as PDFs made for their purchase order (`scripts/trading_media.py`: plain, object streams,
  RC4 or AES, a portal password, incremental, damaged xref, two pages, scanned; some with a
  supplier's mistake) and are read and booked, unlocked, entered by hand or disputed; shipments
  get proof-of-delivery photos and clips, returns damage photos and voice notes, read back
  through the files and media endpoints. All made from the private seed; six invoices, four
  photos, a clip and a voice note made from the visible seed were added to the samples
  (`supplier-invoices/`, `deliveries/`).
- Each trading day counts like one scenario: reward = matched units / all units; trading days
  are 35.3% of the reward, client screens 8.6% (see [Reward formula](#reward-formula)).
- QA 10 should-fixes: strict JSON comparison (E8: `true` is not `1`, `100` not `100.0`); the
  candidate's workspace id is put into the recording where the recorder wrote `{ws}` instead
  of being rewritten out of the candidate's answer (E9); a connection the server closed while
  idle is reopened and a request that never reached it is sent again (E3, E10); `reward.txt` is
  written before the diagnostics; the `NoNewPrivs` check fails closed.
- Instruction: the staff scripts are gone; "up to 8 requests at once, each answered within 30
  seconds" is stated as behaviour (no total or session time); the client's start-up calls and
  the JSON types are named; durable state replaces "may keep its state in memory".
- The private seeds are rotated and kept in `experiment/seeds.json` (never committed): the
  private media set was made again from its new seed, and none of its 32 files equals the old
  set or a sample. The agent's account is now `dev` (QA 06 note; the Goose evaluation-cue pass).
- Corpus: 2,287 scenarios, 3,999 units, 82,837 requests (scenarios.json 89.5 MB), recorded in
  8 min 51 s with no answer of 500 or above. The reference, re-graded locally on the full corpus
  without the sandbox, scores 1.0 on every unit: 3,999 of 3,999 (2,287 of 2,287 scenarios), with
  its 9 planned restarts, no other restart and no retry, in 393 s of replay (6 min 33 s with
  loading), against the 3,000 s deadline.
- `checks/`: 21 tests pass, 4 of them new this round (units and the reward, durable restarts,
  silent closes, the reward before the diagnostics), the comparison check rewritten, and the
  recording and reference checks now cover months, screens and both restarts; with
  `ci_checks`, 48 pass under Python 3.13, and `ci_checks/check_repository.py` passes.
- Bundle `0ffbed822f74` (1,115 files, 85 MB; scenarios 9.4 MB compressed) built twice with the
  same hash; `scripts/scan_uploads.py` finds no hidden upload, cut-short upload or file answer
  among the 481 files the agent image receives; Oddish preflight passes.

### 2026-11-19 (adversarial QA: verifier, leaked samples, sealed-server link)

- An adversarial QA wave (lenses 04, 06 and 10; the reports are kept outside the task) found two
  failures and one concern, fixed below. The should-fixes not taken up are under
  [Remaining work](#remaining-work).
- Leaked samples (QA 06, fail): the 19 Stockwell test fixtures shipped in `/app/samples` are the
  files the hidden `files` scenarios upload (267 base64 uploads, 20 more cut short, and 21 file
  answers, in 78 of 2,483 scenarios), so their answers could be collected from the sealed server
  in advance. They no longer ship; the generated visible media set stays as the samples.
  `scripts/scan_uploads.py` compares every hidden upload (base64 in a JSON body, long text, or a
  raw `body_file`), every upload of 64 bytes or more that is the start of a shipped file, and
  every file answer with what the agent image receives. On the previous bundle it reports exactly
  that leak; on the new one, nothing. The bundle check runs it and also checks that no Stockwell
  fixture ships under any name.
- Verifier (QA 10, fail):
  - A set-user-id file in `/app/server` could arrive root-owned with its mode kept and run as
    root, which could read the private answers. The server now starts through `setpriv ...
    --no-new-privs`, set-id bits are cleared from the delivered files first, and every evaluation
    checks the drop in `/proc/self/status` before any submitted code runs.
  - The replay had no time limit of its own, so a hanging or slow server outlasted the step and
    left no reward. It now has a 3,000-second deadline and 30 seconds of wall clock per request
    (a watcher cuts a server that drips bytes); scenarios not played to the end count as not
    matched, with a note.
  - A health reply that is not HTTP, or JSON nested too deeply, raised an evaluation error. Any
    reply is now a not-healthy server or an answer that matches nothing, and a failed restart is a
    server that did not start.
  - A cap of 25 restarts for the whole run let a server that crashes in one theme lose every later
    scenario. There is no cap now: a scenario that got no answer is played once more on its own
    after the others, and a dead or unresponsive server is restarted while the deadline holds.
  - Two more defects turned up while writing the checks for these. An answer cut short of its
    `Content-Length` was compared as a wrong answer, because `http.client` returns the short body
    without raising; it is now no answer, which gets the retry. And a failed attempt kept its
    connection open while waiting for the server's health check, which deadlocks a server that
    serves one connection at a time; it now closes first.
- Sealed-server link (QA 04, concern): the candidate owned `/app`, so it could replace
  `/app/server` with a link to `/opt/stockwell/app`, and Harbor's collector, running as root,
  would copy the sealed bytecode into the trial artifacts (no reward gain: the copy has no `run`).
  `/app` is now root's with the sticky bit and `/app/server` root's and writable by everyone, so
  the candidate works inside `/app/server` but cannot remove, rename or replace it. See
  hackability row 7.
- README corrections: Workload follows the current rules (one session per run, no chained
  sessions, no time budget in the instruction); sizes are measured at `d61d29c`; the MirrorCode
  figures were checked against Epoch AI's results page and a report on its full results; row 4
  gives the current corpus.
- QA 10's own experiments, rerun against the new verifier: E1 (garbage health reply) 0.0 with a
  note instead of an evaluation error; E2 (deep JSON) a mismatch; E3 (early 413, closed without
  announcing it) 1 of 1, was 0; E4 (a crash in every 26th scenario) 577 of 600, as deserved, was
  208; E5 (a single-threaded server busy past the request limit) 7 of 8 with no restart, was 2
  restarts of a live server; E6 (no answer to workspace creation) still 0 of 16, but at full
  scale the deadline now ends the replay at 3,000 s, where QA estimated 28,300 s. Unchanged: E7,
  E8, E9 and E10, which are should-fixes left open.
- The instruction and the scenarios are unchanged. The limits the replay enforces (eight
  requests at a time, 30 seconds per request, 3,000 seconds in all) are not stated in the
  instruction; see Remaining work.
- `checks/`: 17 tests pass, 7 of them new; with `ci_checks`, 44 pass under Python 3.13, and
  `ci_checks/check_repository.py` passes. Bundle `2a602a3f17e6` (705 files) built twice with the
  same hash; Oddish preflight passes. The reference, re-graded locally on the full corpus
  without the sandbox, still scores 1.0 (2,483 of 2,483) in 264 s with no restarts.

### 2026-11-18 (real-world media)

- The owner asked for messy PDFs and big media before anything else runs. Stockwell gained,
  each with its own tests: a PDF reader for real files (xref streams and object streams,
  incremental updates, repair of broken files, RC4 and AES-128, passwords, CID fonts, scanned
  pages; 453 real PDFs open with poppler's page counts), image decoders (JPEG baseline and
  progressive, byte-identical to libjpeg-turbo; PNG of every kind; animated GIF; EXIF with GPS
  and embedded thumbnails), and a probe for MP4/MOV, Matroska/WebM, AVI, WAV, MP3 and Ogg.
  The files API takes raw uploads of up to 64 MiB, reads them on upload, and answers
  `/media`, `/pdf`, `/pages/{n}`, `/image`, `/unlock` and thumbnails; supplier invoices are
  read with the new reader and scanned ones are flagged. Pinned commit `d61d29c`.
- `scripts/make_media.py` makes two sets of 32 files (scanned multi-page invoices, encrypted,
  password, incremental, broken and truncated PDFs, a 150-page price list, 12-24 MP photos with
  EXIF, a CMYK JPEG, a large PNG, an animated GIF, 45-75 s videos in six containers, voice
  notes): `visible` (seed 20261121) ships as `/app/samples`, `private` (seed 20261122) only to
  the verifier, so no private upload is a file the candidate has seen. (Not so at the time:
  Stockwell's own test fixtures also shipped as samples, and the hidden `files` scenarios upload
  them. Corrected on 2026-11-19.)
- Corpus: 2,483 scenarios (83 in the new `media` theme), 63,033 requests, 749 raw uploads,
  558 file answers, no server error. A raw upload is a step with `body_file` (a file of the
  media set) or `body_size` (zero bytes, for the over-limit case); the replay sends it raw,
  reads a 413 sent before an oversized body is read, and allows 30 s per request.
- The instruction now names the uploads (scanned, encrypted, password-protected, damaged,
  large) and the 64 MiB upload limit beside the 6 MB JSON limit; the audit's should-fix is
  covered by uploads up to 64 MiB and one just over.

### 2026-11-18 (after the version 2 audit)

- Oddish source audit of version 2: one must-fix. The verifier wrote `{ws}` for the
  candidate's workspace id by replacing it across the serialized JSON, so a valid server
  whose ids are short (`1`, `a`) would have its answers corrupted, or crash the evaluation on
  invalid JSON. Now only a string that is exactly the id, or the `/ws/<id>` segment of a
  path, is rewritten (`normalise` in `verifier/replay.py`); a new check covers a one-character
  id. One should-fix: no recorded request body is near the stated 6 MB limit; the media work
  below adds large uploads and one just over the limit.
- Next, before any further run (owner's rule: build it real first): real-world media in the
  application (messy multi-page PDFs, large photos, long videos), new scenarios that upload
  and inspect them, a re-recorded corpus.

### 2026-11-18 (re-cut uploaded)

- The owner asked for no time budget in instructions: the completion section now keeps only
  "keep `/app/server/run` working at all times"; a check rejects "hours" in the instruction.
- Uploaded on the owner's word as version 2 of `...backoffice-server-rebuild-a7ccd915`, one
  row in experiment `backoffice-server-rebuild-recut-20261118`: reference 1.0 twice, no-op
  0.0 twice.

### 2026-11-18 (leak fixes before the first upload of the re-cut)

- Oddish QA rejected the sibling `markdown-linter-rebuild` (version 2) on information leaks
  alone. The classes that also apply here are fixed before this task is uploaded: the
  instruction no longer describes the session lifecycle and asks that `/app/server/run` keep
  working (it still named a 48-hour budget, removed at the next upload; the instruction now
  states no time budget); `task.toml` and the two Dockerfiles keep no authoring
  comments, and neither does `start-sealed-server`; both build contexts have a
  `.dockerignore` (`**/.git`). This task never had a reference helper in the agent image:
  the solution ships the reference package itself.
- New check: nothing the agent can read (outside the bytecode-only sealed server and the
  minified client build) names an oracle, a verifier, grading, scenarios, parity, Harbor,
  Oddish or a reward; the instruction holds no reference, hidden, grading or session text.
  `checks/`: 7 tests pass. Oddish preflight passes. Bundle `a691f329ea71` (574 files).

### 2026-11-18 (re-cut from Stockwell 2.0)

- The reference is now the Stockwell repository (github.com/abundant-ai/stockwell, private) at
  the commit in `common/STOCKWELL_COMMIT`: the same API rebuilt as a production service
  (FastAPI, Pydantic, SQLAlchemy; 232 endpoints; 15,954 lines at `722a647`, the commit pinned
  then, and 22,988 at `d61d29c` after the media work) with a React and
  TypeScript client (85 screens). It answers every scenario recorded from the earlier
  standard-library server the same way (1,080 of 1,080 in its own parity check), except that
  a body with the wrong shape is reported on its shape alone.
- The sealed server runs from bytecode as user `stockwell` on a SQLite file, with proxy
  sign-in (`X-User`). Its third-party packages are installed, pinned with hashes, in
  `/opt/py`, which `python3` points to in both images, so a candidate may build on them and
  the verifier can run what they build.
- The candidate gets the client's source and its build (`/app/client`, without tests), the
  sample files, and the API description the server publishes at `/api/openapi.json`. The
  client's source names 226 of the 232 endpoints; the description lists all of them.
- Scenarios now come from the reference repository's `backend/tools/record_corpus.py`: the
  earlier recorder's request streams (26 themes), answered by the new server, plus a
  `trading` theme of seeded busy days that end with reads of the stock ledger, the journal,
  the trial balance, receivables, stock and the integrity checks.
- The instruction names the answers that cannot be reproduced (request log, sign-in,
  sessions, API keys, `/metrics`); none of them is in the scenarios.

### 2026-11-18

- Chose a purpose-built application over a recent open-source one. Recent real back ends
  that were looked at were either far too large to rebuild (two Go servers of about 250,000
  lines) or too small (about 3,000 lines), and a real server's random ids and wall-clock
  times would have needed fuzzy comparison. An original application is not in any model's
  training data and can be made exactly reproducible.
- Wrote the reference server (`common/stockwell/`, Python standard library, about 2,400
  lines, 56 routes): users and roles, catalogue, price lists, promotions, customers and
  credit, stock lots, orders, shipments, invoices, payments, late fees, returns, reports, a
  per-workspace calendar, idempotent posts and versioned updates.
- Wrote the web client (`common/client/`), which has one form per route. A check keeps the
  client and the server's routes equal, so everything graded can be found from the client.
- Wrote the scenario generator (`scripts/record_scenarios.py`) and recorded 1,400 scenarios,
  21,083 requests, seed 20261118. Two recordings of the same seed are byte-identical; no
  request gets a 5xx answer.
- Wrote the verifier (`steps/01-rebuild-server/tests/`). First local run of the reference
  through it gave 0.72: the verifier opened one connection per request and ran out of local
  ports, and a restart race marked the server as down. Fixed both (one connection per
  scenario; a restart only when the health check fails). The reference then scored
  1,400 of 1,400 twice, in 6 seconds.
- `checks/`: 4 tests pass locally. Repository checks pass.
- Oddish results are recorded under [Validation](#validation).
- Not done: `harbor check`, ratings, any model trial, any attack on the sandbox.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-rebuild-server` | Implemented: instruction, agent image with the sealed server, separate verifier image, reference solution. |
| Further steps | Not designed. Candidates: a follow-up change request on the rebuilt server; importing a year of legacy data. The work's end is counted from the trial's set-up, which is right for one step only: a second one needs its start recorded per step first (Remaining work). Since round 15 the task is uploaded flat. |
| Private inputs | `steps/01-rebuild-server/tests/private/scenarios.json` and the private files they upload (`experiment/media/private`, made with `--big`), Git-ignored, produced by `scripts/record_scenarios.py --count 2160 --runs 44 --term 6 --kill 3 --screens 8` from the private seeds in `experiment/seeds.json` (never committed; rotated in round 3). The corpus holds `scenarios` alone; how it was recorded (the seed, the legacy commit, the themes left out, the media set's digest, the live recorder's settings) is in `experiment/recording.json` with the corpus's SHA-256, never committed or packaged (round 11). |
| Oracle | The reference server, shipped as Python 3.12 bytecode in the solution's data, installed as the delivered server and run on the packages in `/opt/py`. |
| Ratings (`harbor check`) | Not run. |

## Design dimensions

### Novelty

The candidate must discover a specification by experiment and then build to it. Nothing
states the rules: price resolution, promotion stacking, tax rounding per region, stock
allocation, credit holds, due dates, late fees and return credits are only visible in what
the sealed server answers.

Closest comparisons:

- MirrorCode (Epoch AI and METR, https://epoch.ai/benchmarks/mirrorcode): rebuild a
  command-line program from an execute-only copy, graded on held-out tests. Same family.
  Differences: MirrorCode gives the agent documentation of the program and visible tests, and
  this task gives neither (only the running server, the client's source, the API description
  the server publishes, without rules, and sample files); a stateful multi-user service instead
  of a filter program, so behaviour depends on sequences of requests; and the target is
  original, where MirrorCode's own report notes its open-source targets are probably in
  pre-training.
- SWE-Marathon v1 product clones (`slack-clone`, `stripe-clone`, `mastodon-clone`, `s3-clone`,
  `excel-clone`): build a product from a written specification of a well-known service.
  Here there is no written specification and no public product to remember.
- Tasks in this repository: no overlap with `knowledge-work-assistant`, `titans-training`,
  `battle-royale` or `sympy-restoration`.
- Deep SWE, Frontier SWE, Multi-Step SWE: not compared. Unverified.

### Verifiability

Every answer of the reference is a pure function of the requests made in a workspace: ids
are sequential, the calendar is simulated, and nothing reads the wall clock. Recorded
answers can therefore be compared exactly, types included. Partial progress is the share of
units that match in full: a scenario of the legacy and media themes, a trading day, or a
client screen opened after a month of trading. Uncertainty: a legacy scenario fails on its
first difference, so one wrong rule in a common path hides later correct behaviour there; a
month of trading goes on after a wrong answer and judges each day on its own, though a wrong
day can make later days differ too. The per-theme breakdown in `metrics.json` shows where.

### Realism

Replacing a system whose vendor has gone, with only a running copy and its client, is real
work. What a real requester checks is graded: the client opening its screens on the new
server (its start-up calls and each screen's reads), a ledger that survives a restart or a
crash, and a month of trading that runs into the month's close with supplier PDFs and
delivery photos on the way. Contrived parts: the application is small compared with a real
back office, and the sealed server gives unlimited fresh copies of the demo company, which a
production system would not.

### Difficulty

Expected sources, not yet measured by any trial:

- Rules that interact: a line's price depends on price lists, quantity breaks, tier, and
  promotions that may or may not stack; the invoice then prorates and re-taxes it.
- State and time: allocation changes when stock arrives or expires, fees accrue as the
  calendar moves, holds appear and lift.
- Exactness: messages, field order in lists, error precedence and rounding all count.
- Breadth of the surface: 232 endpoints, 5 roles, 82 tables behind them; files, PDFs and
  barcodes generated byte for byte.
- A month in one workspace: a trading day's answers depend on every earlier day, the month's
  end and the period close depend on the whole month, and supplier PDFs (encrypted, damaged,
  scanned) decide what is booked, so the PDF reader sits on the path to payables and the bank.
- Durability: a month must come through SIGTERM and SIGKILL restarts on the same data, which
  rules out a server that keeps its state in memory.
- The client's view: its screens read lists with its own paging, sorting and filters.

### Initial feasibility

Solved by construction: the reference source passes every scenario. For an agent the rules
are all observable through the API and the client; whether one session suffices is unknown.

## Workload

One agent session per run, of at most 34,560 s (9.6 hours), the agent's limit in `task.toml`
(`timeout_sec = 34560`; since round 15 nothing of the task's own ends the session earlier, and
what changes after the limit does not count). There are no chained sessions or continuation
tasks, and the instruction states no time budget. v2 asks
for about five days of agent work, which one session does not reach. Follow-up steps remain open
options for the owner: a change request on the rebuilt server, or a data migration (importing a
year of legacy data).

Size, measured at `d61d29c`: the reference server is 22,988 lines of Python in 192 files, 18,742
of them code (without blank lines and comments), 6,672 of those in the media package. The client
to read is 41,158 lines of TypeScript without tests, 22,282 of them the generated API types in
`schema.d.ts`.

For scale: gotree, the most complex target solved in MirrorCode's preliminary results, is 16,905
lines of Go. Claude Opus 4.7 rebuilt it in 14 hours for $251, with the program's documentation
and visible tests (Opus 4.6's Rust rebuild is 7,644 lines, so lines in different languages do
not compare directly). Pkl, at 61,461 lines, was not solved, and no model solved any of
MirrorCode's large targets. This task gives neither documentation nor visible tests. Sources:
Epoch AI's preliminary results
(https://epoch.ai/blog/mirrorcode-preliminary-results/) for the line counts, and a report on the
full results
(https://the-decoder.com/an-ai-model-programmed-nonstop-for-19-days-on-a-single-mirrorcode-task-that-cost-2600-to-run/)
for the hours, the cost and the large targets.

## Verification

The verifier runs in a separate image that holds the private scenarios and no copy of the
reference server. The sealed server the agent studies, the recorders and the solution all take
their settings from one file, `environment/stockwell.env` (the legacy recorder builds the same
app in-process), so the server the agent learns from answers as the grader expects (QA 12 F1).

**Run condition: the platform's limit and the work's end** (round 15; the judges' third decision,
harbor-lh `ops/swe-marathon-v2/decisions/2026-11-24-timer-round3-flat-bundles-DECISION.md`).
Nothing of the task's own ends the agent's session. Rounds 8 to 14 had a root timer
(`fsmaint-timer`) end it before the limit, because a steps bundle's turn that ran into the cap was
never graded (harbor-lh `ops/swe-marathon-v2/PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`); the
platform's verdicts on BasedPL's versions 2 and 4 rejected that stop as premature whatever the gap
(660 s, then 60 s), and the timer is gone. The limit is `timeout_sec = 34560` in both places in
`task.toml`, with no comment, and the task goes up as a flat single-step bundle under its own name
(`scripts/package_step.py --flat --keep-name`), as SymPy's does, the only setup whose capped runs
were graded (3 of 3); the repository keeps its steps layout. A turn that reaches the limit is not
ended: harbor stops waiting for it and leaves the agent's commands running, with the network back
once the turn is over (harbor-lh `ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md`), until the
collect hook ends them, and a killed claude-code run would be classified by its transcript and its
score discarded. So the work's end is its start, recorded when the set-up hands over
(`/var/lib/fsmaint/work-started`, written by `start-sealed-server` at each successful exit; the
set-up fails if it cannot write it), plus 34,560 s, and what changed in `/app/server` after that end
does not count: the collect hook removes every entry other than a directory whose change time falls
between the end and the moment it had ended the agent's processes and done everything else that
could touch the tree (the fence, `/var/lib/fsmaint/fence`), with every other name of the same file
and a note each, adds `sweep: N entries that changed after the work's end were removed` to the
manifest, and copies in no outside file or directory a link points to in which a file or link
changed after the end. Before it ends the agent's processes, the hook stops them and, as `dev`,
lists the files they map shared and writable or hold open for writing, which can be written after
the end without their change time moving; once the end has passed those count as changed after
it, and a tree whose list cannot be made is refused (BasedPL's re-check R1). A turn that ends by
itself ends before the end, so nothing is removed for it. The agent is not told; the instruction states no budget either way, and nothing the agent can
see of the hooks (the names in `/usr/local/sbin` and `/var/lib`) says what they are for. The
sealed server and its supervisor run as other users and are untouched. **This holds for one step
only**: the start is recorded at the trial's set-up, not at a step's start. See
[Remaining work](#remaining-work) before a second step is added.

1. Delivery: before `/app/server` leaves the agent's machine, a `[[verifier.collect]]` hook runs
   `environment/fsmaint-sweep` (root, mode 0700; `prepare-delivery` until round 9), so that
   nothing the agent leaves can make the copy fail (QA 07e M4, 07f M4). (From round 9 to round 14
   it first stopped the maintenance timer.) Since round 15 it first stops every process of `dev`
   (`kill -STOP -1` as `dev`, while any still runs) and, as `dev`, lists from `/proc` the regular
   files they map shared and writable or hold open for writing, within 60 s and 100,000 files (see
   the run condition above). It then ends every process of `dev` with
   `kill -9 -1` as `dev`, one system call that a forking process cannot outrun, until none is
   left (since round 12 an ended process nobody has reaped does not count, where procps's `pgrep`
   can tell its state: under Docker this image's first process, `sleep infinity`, reaps nothing,
   so every sweep made all 100 passes, and a crowd of such entries could hold the hook past its
   600 s; QA 23 N1 of the Carve task); gives back 64 MiB and 64 spare inodes set
   aside in `/var/lib/fsmaint` when the session began (`start-sealed-server`, which also records
   the free blocks and inodes then; the room cannot live outside the agent's container under
   Harbor, where both hooks run inside it, so it is root-only system state under a housekeeping
   name); replaces anything at `/app/server` that is not a directory (the agent cannot, but
   until round 12 the sweep then exited with no manifest, and the copy followed a link or found
   nothing) by an empty directory with a manifest that refuses it, after moving it aside, never
   followed; and moves aside, never following, whatever was left under the manifest's name, or
   removes it where it cannot (until round 12 it exited there and the agent's own manifest
   arrived, QA 22 F6 of the Carve task). Since round 15 it then writes the fence (see the run
   condition above): nothing before it may change the tree after it. Then, as `dev` and within two
   minutes, it makes links
   inside the directory relative, replaces links that leave it with copies of the files or
   directories they point to (within the delivery's limits, and since round 12 only while 64 MiB
   and 64 inodes stay free for the manifest and a refusal, QA 07g F2; devices, pipes and sockets
   are left out; since round 15 only where no file or link in them changed after the work's end,
   and a link that itself changed between the end and the fence is left to the walk) and removes
   dangling links, links to devices, pipes, sockets and device nodes:
   Harbor's copy (tarfile's `data` filter) refuses absolute links and links that leave the
   directory, so without this a venv's interpreter link made a correct delivery vanish (QA 07
   F3); as `dev` it copies nothing `dev` could not read. Last, as root, it walks the delivery by
   directory descriptor, so no depth hides anything, counts every name it lists against the
   100,000 entries (pipes and sockets too since round 12), removes (since round 15) every entry
   other than a directory that changed between the work's end and the fence, and every file listed
   as held once the end had passed, each with every other name of the same file, removes what the
   copy would refuse (a
   device, a pipe, a socket, a link with an absolute target, or one the kernel cannot follow, at
   most 40 links on the way, to a file or directory inside: one the walk saw or, failing that, one
   `realpath` finds there), keeps a link only as the
   relative path straight to what it reaches, writing it again so where it is not, or removing it
   where the disk has no room left for that, and counts entries and bytes (each file once), all
   within 240 s. Until round 12 it kept any relative link that resolved inside here, so one that
   climbs above `/` and back in made the copy's extraction stop part way (an evaluation error, QA
   22 F5 of the Carve task), and it resolved each link with `realpath`, which chains and long
   targets made quadratic past the hook's 600 s (QA 07g F1, QA 22 F3). It refuses the delivery on
   any step it cannot complete or that overruns those 240 s, past 100,000 entries, 1 GB (a sparse
   file counts its full size), a path of 1,000 bytes or (since round 13) a file with more than
   1,000 hard links, the limits the instruction states; then it
   packs the delivery once the way the copy does (`tar -czf` into `/tmp`) within 100 s, below the
   copy's own limits (120 s on Archil, 600 s on Modal), and refuses it if that pack fails or
   overruns, unless it failed for want of room or inodes the machine did not have when the session
   began. A refused delivery is moved aside whole and replaced by an empty directory; where the
   directory cannot be renamed (an overlay without `redirect_dir` answers a rename of a directory
   of the image's own with EXDEV, which the stage did not catch until round 12), what it holds is
   moved aside instead. The manifest, `/app/server/.fsmaint-manifest` (`.delivered` until round
   9), says `complete`, the entries and the bytes, or `refused` and why, with a line for each of
   the first 40 changes (since round 12 each one line of at most 200 characters, unprintable
   characters escaped, then how many more there were), and ends with the sweep's own lines
   (`sweep:` lines, kept apart from the hook's notes and reported whole as `sweep_log` in
   `metrics.json`: the process limit, what became of `/logs/artifacts`, how many entries changed
   after the work's end; until round 15 the timer's log as `timer:` lines and `timer_log`). The
   hook's longest run is now about 535 s: the stop and the kill loop in seconds, the list of held
   files' 60 s, the fixer's 120 s, the walk's 240 s, the pack's 100 s. `verify.py` scores what arrived, with a note when the manifest is missing or says
   `refused`, and reads at most its first 64 KiB (round 12); fewer entries or bytes arriving than
   the manifest counts (a copy the platform cut short) and an `/app/server` of which nothing
   arrived are evaluation errors, while more (hard links a copy could not keep, which arrive as
   copies) is scored with a note since round 13, and no path the agent's tree controls is known to
   lead to either error (see hackability row 14 for what is left). Since round 13 a `su` session
   of `dev`, which is how harbor's Modal backend starts every command of the agent's user, the
   agent's own session included, is capped at 16,384 processes and threads
   (`/etc/security/limits.d/90-nproc.conf`, through `pam_limits`, made optional in `/etc/pam.d/su`
   so that a limit it cannot set never stops a session), so that a fork bomb left at the end of
   the session cannot keep root's hooks or the copy from starting; the set-up records the hard
   limit such a session gets, and the sweep carries it into `sweep_log`.
2. Sandbox: set-user-id and set-group-id bits are cleared, the submission is made root's and
   read-only, and `/app/server/run` is started as user `nobody` through
   `setpriv --no-new-privs`, under `prlimit` (4,096 threads for the user, files of at most
   4 GiB, 6 GiB of address space per process), in a cgroup capping the whole group's memory and
   processes where the machine lets the verifier make one, with `oom_score_adj` 1000 set before
   the drop and raised again every 50 ms (without CAP_SYS_RESOURCE the server could lower it;
   the probe notes when it can), with `PORT` and `DATA_DIR` set, in its own process group, with
   no network. The server's memory is read every 10 ms from what the kernel charges, each page
   once whatever holds it (a process, a SysV segment no one attaches, a memfd, a file in
   `/dev/shm`, socket buffers): the server's own cgroup where one can be made, else this
   container's memory cgroup (v2: `memory.current` less reclaimable page cache and slab; v1: rss
   and shmem), else a virtual machine's or gVisor sandbox's `/proc/meminfo` (up to 16 GiB), less
   the grader's own anonymous memory and what was in use before the server started; only where
   none of these can be read, from the server's processes (proportional set size), its
   unattached SysV segments and its unmapped files in memory-backed places, every 50 ms. Above
   6 GiB the server is stopped for good, its remaining scenarios failed with a note (QA 07d M3,
   07e M3; the instruction states the cap, shared memory included). An honest server that
   shares memory among workers or keeps SQLite or multiprocessing files in `/dev/shm` counts at
   its real size (QA 07e S-a). Every stop and halt runs `ipcrm --all` as `nobody` and removes
   its files in memory-backed directories, so memory parked there never outlives the server, and
   state kept there does not survive a restart. The grader asks for a low OOM
   priority for itself (Docker's defaults lack CAP_SYS_RESOURCE, so it stays at 0 there;
   `metrics.json` records it) and holds each scenario as compact JSON, decoded when played, and
   its uploads in a bounded cache. Before the server
   starts, a process started the same way must show the unprivileged ids, no capabilities,
   no_new_privs (status file or prctl) and those limits; otherwise the evaluation stops with an
   evaluation error. The server's output goes into a pipe the grader drains, keeping its first
   and last MiB, so no file of the grader's is ever the server's to fill, read or hold open.
3. The server has 60 seconds to answer `GET /api/health`.
4. Each scenario creates a workspace and replays its requests on one connection, eight
   scenarios at a time, in a fixed shuffled order, so a server too slow to finish loses
   scenarios of every kind. A scenario with a planned restart, or one that uploads a PDF of
   1 MiB or more or any file of 16 MiB or more (the reference holds SQLite's write lock while it
   reads or stores such a file, and a request queued behind it for 15 s would fail; QA 11 S1),
   runs with nothing beside it, at a fixed place spread through the order. A step marked
   `scoped: false` names its full path (the client's `GET /api/version`); the others are under
   `/api/ws/{workspace}`. A body is JSON, a media file sent raw (`body_file`), JSON with a media
   file put into one field as base64 or text (`body_insert`, for bodies near the 6 MB limit), or
   that many zero bytes (`body_size`, for bodies over a limit). An answer matches when the status
   code is equal and the JSON body is identical, types included, to the recorded one with the
   candidate's workspace id put where the recorder wrote `{ws}`; a file matches on its type,
   length and SHA-256, hashed as it arrives. Every byte of an answer, headers, chunk sizes and
   trailers included, counts against 80 MiB plus 8 MiB of headers, and a chunk size that is not
   plain hexadecimal (`-1`, `+1a`, `0x10`) is a broken answer (QA 07c F1). A reply that is not
   HTTP, not JSON, larger than 4 MB of JSON or 80 MiB in all, or nested too deeply matches
   nothing. An answer cut short of its `Content-Length` is no answer. A connection the server
   closed while idle is reopened, and a request that never reached the server is sent once more.
5. Units: a scenario of the legacy, media, counts and kits themes is one unit and stops at its
   first difference. A month of trading lists its units, one per trading day and one per
   client screen opened after it, goes on after a difference and judges each unit on its own
   answers.
6. Time: each request has 30 seconds of wall clock and the whole replay 5,400 seconds (the step
   allows 6,000; the reference takes about 520 here). A watcher cuts any request still running
   past either, and every read of an answer, the health check's included, is given only the time
   left, so no drip outlasts it whatever the answer's framing (`Connection: close`, HTTP/1.0, no
   length; QA 07d M1). Scenarios not played to the end by the deadline count as not matched, with
   a note and a count in `metrics.json`. `verify.py` runs the evaluation in a thread and, 5,640 s
   after it starts, publishes the reward from what was decided, with a note, whatever the
   evaluation is doing then; the step's 6,000 s also covers Harbor's upload of the tests and its
   collection of the results.
7. Restarts: a server that has died, or has not answered its health check for 30 seconds, is
   restarted before the next attempt, with no cap while the deadline holds, and given up after
   three starts in a row that never answer. Every start uses the same `DATA_DIR`. A stop ends
   the process group, then stops and kills every process of `nobody` read from `/proc`,
   including a process whose main thread has exited while others run (it shows as a zombie;
   QA 07c F2), runs `kill -9 -1` as `nobody` and kills the cgroup where there is one, until none
   is left: a stopped process cannot fork, so nothing outruns it. Orphans are reaped.
8. Second tries: a scenario in flight when the server stopped (it died, or hung and was
   stopped) is played once more on its own after all the others, so the scenarios beside a crash
   still count; a wrong answer, or a request a live server left unanswered, is final. Second
   tries decide at most 2% of all units, so they rescue a server that stops now and then, not
   one that fails under load (QA 20). Before the first, the slate is cleaned: the server
   stopped; `DATA_DIR` and every directory `nobody` owns moved into a directory only root can
   enter (constant time, nothing deleted; QA 07d M2); its other files on the root filesystem and
   in `/tmp`, `/var/tmp`, `/dev/shm`, `/dev/mqueue` and `/run/lock` removed, with any hard link
   there; the search stopped after two minutes and kept out of the evaluation's own folders; SysV
   IPC removed as `nobody`; and a fresh server started. None of this starts with less than five
   minutes left. A second try decides only the units the first try left unanswered (QA 07 F1), and
   a scenario with nothing left to decide gets none (QA 07d N7).
9. Durable state: after a step marked `restart` the server is stopped (SIGTERM at the end of a
   trading day, with 30 seconds to exit, or SIGKILL straight after a write drawn at random was
   answered), started again on the same `DATA_DIR`, and the month goes on in the same workspace;
   the day after, files uploaded before the restart are read again.
10. Disk: a 256 MiB ballast is set aside before the server starts and given back for the
    results (also when `verify.py`'s hard stop publishes; QA 07e S-b), and once a second a guard
    stops the server for good when free space falls under 512 MiB on a disk the grader uses that
    the server can write, that reports its size and that had room when the server started, its
    remaining scenarios failed with a note (QA 07c F3, 07d S1, 07e S-d). `/work` or `/logs/verifier`
    without 512 MiB before the start is an evaluation error; `metrics.json` records each disk's
    free space at the start and the end. Nothing is deleted, before the reward or after: the
    container is discarded (QA 07d M2). `verify.py` writes a placeholder of the reward's size
    before the server starts; the reward goes over it in place and is renamed, which needs no
    free space, then `metrics.json` (with the slowest requests, answers of 500 or above by theme
    and the server's peak memory), then the per-scenario results. A failure writing the last two
    costs only those files, a published reward is never taken back, and no cleanup step can
    raise. If the grader itself dies, only the placeholder and a summary saying the evaluation
    did not finish remain: Harbor finds no reward, so the result is an evaluation error, never a
    0 (QA 07d M3).

### Reward formula

```
reward = (matched scenarios + matched trading days + matched screens)
         / (2,218 scenarios + 1,432 trading days + 352 screens)
       = matched units / 4,002
```

| Units | Count | Share of the reward |
| --- | --- | --- |
| Scenarios of the 26 legacy themes (refusal-only ones left out; counts and kits only where they post a count or build a kit) | 2,005 | 50.1% |
| Counts and kits made start to finish by the live recorder, filling those two themes back to 83 each | 130 | 3.2% |
| Scenarios of the media theme | 83 | 2.1% |
| Trading days (44 months of 30-35 days from four start dates, 11 each, each crossing a month's end) | 1,432 | 35.8% |
| Client screens opened after a month (8 per month, each changed by the month) | 352 | 8.8% |

- Continuous. A unit matches only if every one of its answers matches; a trading day or a
  screen is judged on its own answers, so a wrong day does not cost the month's other days.
- The denominator is fixed. No `run` file, a server that never becomes healthy, one that
  cannot be restarted, or one too slow or stuck to finish within the time limit: the
  scenarios it did not answer count as not matched.
- An evaluation error (verifier not root, privileges or limits cannot be set or do not hold,
  scenarios unreadable, an upload the scenarios name is missing) leaves no reward file;
  `metrics.json` has `status: evaluation_error`, and `verifier_error.txt` the traceback. No
  reply from the submitted server can cause one, and neither can a server that fills the
  process table, memory or the disk: its user's limits keep the table usable, the cleanup never
  forks or raises and finds every process, an answer is bounded in every transfer encoding, the
  server's output never reaches a file of the grader's, the reward goes over a placeholder made
  before it ran, and a ballast keeps room for the results and their retrieval (round 4).
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verifier/replay.py`. Tests: `checks/test_backoffice.py` (reference
  1.0; a one-character rounding defect scores between 0 and 1; a crashing or missing server
  scores 0 with the full denominator; tiny fake servers that hang, drip bytes, send a garbage
  health reply, deep or non-JSON answers, or crash in every tenth scenario, which scores 72 of
  80 with room for second tries and decides no more than 2% of units without it; a live server
  that drops a request gets no second try, and heavy uploads run alone; set-id bits are cleared
  and the drop sets `--no-new-privs` and the limits; the QA 07 preview server gains nothing from
  a second try, and the within-try echo is pinned at 0.67; the sweep never follows a link, and a
  zombie leader with live threads is found and killed; a `-1` chunk and its relatives are broken
  answers that cost the grader no memory; the server's output keeps its first and last MiB, the
  ballast is given back and a low disk stops the server; the reward is written when every new
  write fails; a real venv survives the data-filter copy and a link to `/dev/zero` is removed;
  the order is a fixed shuffle with the restarting months spread; files of 40 MiB are hashed as
  they arrive and JSON bodies are built around media files; one configuration and the
  instruction's numbers; the deadline leaves at least 300 s of the step's limit, 600 s now).

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW (14 narrowed in round 12, its residuals accepted under the run policy; findings 1 and 2
unassessed; 5, 7, 8, 9 and 11 mitigated but not yet exercised in a container; 10 keeps a residual the owner decides).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read the sealed server's code and copy it | File permissions in the agent image; what the bundle and its layers hold | Inspected by adversarial QA 04 and 08 (2026-11-19): as the agent's user, the bytecode, the database and `/proc/<pid>/{mem,environ}` of the sealed server are not readable. Not executed in a container | Server files are owned by user `stockwell`, mode 0700, and the agent runs as `dev`. Round 3 (QA 08): the bundle carries the reference as Python 3.12 bytecode only, for the sealed server and the solution, so no layer of either image holds its source (the build fails on a `.py`); every start of the sealed server first checks as `dev` that `/opt/stockwell` cannot be read or entered and fails the setup hook, which stops the trial, if it can. `/opt/py` holds only public third-party packages | A way to become root or `stockwell` inside the container; bytecode can be decompiled by anyone who has the bundle | Probe as `dev`: read `/opt/stockwell`, `/proc/<pid>/mem`, ptrace | 🟡 YELLOW / UNASSESSED |
| 2 | Agent harness starts as root and hands the model a root shell | Harness and `[agent] user` on Oddish | Not tested on Oddish | `user = "dev"` in `task.toml` | Depends on each harness honouring it | Short model trial that prints `id` | 🟡 YELLOW / UNASSESSED |
| 3 | Deliver a proxy to the sealed server | Separate verifier image | By design | The verifier image has no reference server and no network | None found | Keep | 🟢 GREEN / LOW |
| 4 | Replay a table of recorded answers, including answers collected for inputs the agent already holds | Private scenarios; what the agent image holds | QA 06 (2026-11-19): the 19 Stockwell test fixtures shipped in `/app/samples` were uploaded byte for byte by the hidden `files` scenarios; fixed in round 1, and `scripts/scan_uploads.py` checks every bundle. QA 05 (2026-11-19): a crawl of a fresh workspace, a day counter and cheap rules cover 2.2 to 3.5% of round 2's units, through screens the month never changed (67 of 343) and legacy scenarios whose every write is refused (53); left out in round 3 | Scenarios come from a private seed, rotated in round 3 and kept out of the repository and, since round 11, out of the bundle (the corpus carried it in a `recorded_with` record until then): 89,524 requests in 2,262 scenarios (4,002 units), 44 of them months of trading from four start dates whose supplier invoices are made for each purchase order. No screen that answers as a fresh workspace on the same day and no legacy scenario that changes nothing is kept, and every count and kit scenario does its work. The private media share no file and no name with the samples, and the bundle check fails on any hidden upload, cut-short upload or file answer the agent image holds | A table cannot cover them; the generators' shape could be guessed only in outline | Measure a lookup-table submission on the round 3 corpus | 🟢 GREEN / LOW |
| 5 | Submitted server attacks the verifier process or its files, or exhausts processes, memory or disk so that the evaluation publishes no reward | Verifier sandbox | QA 10: a set-user-id binary could run as root; fixed. QA 07 F2: a full process table or disk lost the reward; fixed in round 3. QA 07c F1 and F3 (round 3 re-check): a chunked answer with size `-1` made http.client read the whole stream (300 MiB grew the verifier by 848 MiB); the server could lower its own OOM priority without CAP_SYS_RESOURCE; on providers that pack `/logs/verifier` before reading the reward, a full disk, a 4 GiB `server.log` or appends to it during the pack lost the reward. F1(a), F2 and F3 fixed in round 4, the `-1` case a check. QA 07d M3: the priority raised once a second is a race a server can win on purpose where no cgroup can be made (Docker's defaults, Archil), and the grader, the largest process at 0, then dies with no reward; narrowed in round 5. QA 07e M3: round 5's guard summed only memory the server's processes map, so SysV segments, memfds and `/dev/shm` files no process maps were invisible: a server could park the container's memory under its limit and have the grader killed within a millisecond (round 5's "1.5 GB within 50 ms" was wrong); S-a: the per-process sum could also count shared pages and a fork's pages more than once. Fixed in round 6, with checks that fail against round 5 | Runs as `nobody` through `setpriv --no-new-privs` under `prlimit` (4,096 threads, 4 GiB files, 6 GiB address space per process) and a cgroup where one can be made. The server's memory is read every 10 ms from what the kernel charges (the container's memory cgroup, or a virtual machine's own meminfo, never gVisor's, whose MemAvailable is MemFree; QA 07f S2), less the grader's own and what was in use before it started, so every page counts once whatever holds it; above 6 GiB, as the instruction states with shared memory included, the server is stopped for good. Every stop and halt removes its user's SysV objects and memory-backed files. Every 50 ms its processes are put back at OOM priority 1000; the grader asks for a low priority (it stays at 0 without CAP_SYS_RESOURCE) and keeps the corpus as compact text and uploads in a bounded cache. Every byte of an answer counts against the limit and chunk sizes are strict. The server's output goes to a pipe the grader drains (first and last MiB kept), so it holds no file of the grader's. A 256 MiB ballast is given back for the results, and a guard stops the server for good under 512 MiB free on a disk it can write that had room when it started. The cleanup never forks, never raises and finds what hides (9); the reward goes over a placeholder and is never taken back once published, and a grader that dies leaves no reward file, so the result is an evaluation error, never a 0 | Not exercised in a container. Where the cgroup or meminfo can be read, the race needs the rest of the machine (about 1.4 GB on 8 GiB) filled within one 10 ms tick after the server lowers its priority. Where neither can be read, the per-process fallback does not see a memfd no process maps. Either way a grader killed for memory leaves an evaluation error, not a 0. A disk burst within the guard's one-second disk check can still fill the disk, which costs the diagnostics but not the reward or its retrieval (the ballast) | QA 07e's red-team item 1 (park 7.5 GiB in SysV segments, lower the priority after the guard's raise, allocate 20 MB) and S-a's 3.5 GiB server that spawns a child per request; 07d's item 3 and 07c's OOM floor, `-1` chunk with 3 GB, full disk and big output on each provider | 🟡 YELLOW / MEDIUM |
| 6 | Tamper with reward files | Separate verifier container | By design | Verifier starts fresh with only `/app/server`; the server cannot become root (5) and cannot reach `/logs/verifier` | None found | Keep | 🟢 GREEN / LOW |
| 7 | Replace `/app/server` with a link to `/opt/stockwell/app`, so that Harbor's collector, running as root, copies the sealed bytecode into the trial artifacts and the verifier. Leaks the private reference; no reward (the copy has no `run`) | Ownership of `/app` in the agent image; Harbor's collector; the delivery hook | QA 04 (2026-11-19), traced in Harbor 0.20: `tar -czf ... -C /app/server .` as root follows the top-level link, and GNU tar stores links below it as links. Not executed | `/app` is root's with the sticky bit and `/app/server` root's and writable by everyone: the agent creates and changes anything inside it but cannot remove, rename or replace it. The delivery hook (11) copies what links point to only as `dev`, who cannot read `/opt/stockwell`, so such a link is removed as dangling | A provider whose collector follows links below the top; not executed in a container | In the next container run, as `dev`: `rm -rf /app/server` and `mv /app/server x` fail, and a link to `/opt/stockwell` is removed by the hook | 🟡 YELLOW / MEDIUM |
| 8 | Submission makes the evaluation end without a reward (hangs past the step limit, a reply that is not HTTP, deep JSON, a crash storm, an answer that never ends, a `DATA_DIR` too big to delete in time); a run that errors may also be retried, which gives a bad run a second draw | Verifier | QA 10 E1, E2, E4 and E6, rerun after the fix; checks with fake servers that hang, drip, send garbage or crash; QA 07c E1 (`-1` chunk), fixed in round 4. QA 07d M1: an answer with `Connection: close`, HTTP/1.0 or no length took its socket out of the watcher's reach, and a drip held `evaluate()` at the server's pace (81 s for a 5 s deadline), the health check too; M2: an unbounded `rmtree` of `DATA_DIR` ran before the reward was published. Fixed in round 5; each new check fails against round 4 | A deadline and 30 s of wall clock per request; every read of an answer, the health check's included, is given only the time left, whatever its framing; `verify.py` publishes the reward 5,640 s after it starts from what was decided, whatever the evaluation is doing; nothing is deleted before the reward, and the clean slate moves what it takes away in constant time; any reply is a not-healthy server or an answer that matches nothing; an answer is bounded in every transfer encoding; no restart cap; resource exhaustion handled as in 5; the clean slate's search stops after two minutes and is skipped with less than five minutes left | A connect the kernel leaves hanging can outlast the deadline by its own 30 s, within the hard stop's margin | Exercise 5's container red team and QA 07d's items 1 and 2 (a drip after `HTTP/1.0 200 OK` on the health check; 50 million hard links in `DATA_DIR`) | 🟡 YELLOW / MEDIUM |
| 9 | Pass the durable-state units without durable state: keep a workspace in a process that outlives the planned stop, or in memory written out only on SIGTERM | Verifier's planned restarts | Checks with fake servers that keep state on disk, in memory, or save only on SIGTERM. QA 07 F4: a helper that forks fast enough survived `pkill`; fixed in round 3. QA 07c F2: a process whose main thread exits while other threads run shows as a zombie, and the sweep skipped zombies, so it survived every stop and kept the log open; fixed in round 4, with a fake-/proc check | A planned stop kills the process group, then stops every process of `nobody` read from `/proc` (a zombie leader with live threads included) until a listing finds no new one, kills them all, runs `kill -9 -1` as `nobody` and kills the cgroup where there is one; SIGKILL comes straight after an answered write drawn at random; files uploaded before a restart are read again after it | State kept in `/tmp` (on disk) instead of `DATA_DIR` also survives a planned restart, but it is durable state all the same; state in SysV shared memory or `/dev/shm` does not, since every stop removes it (QA 07e M3) | Run QA 07c's zombie-leader repro sandboxed in a container | 🟡 YELLOW / MEDIUM |
| 10 | Preview a month and answer from what later requests reveal: a month goes on after a wrong answer, and the client sends what it was shown, so later requests echo earlier answers (payments, bank statements) | Verifier's second tries; the corpus | QA 07 F1: a server with a one-cent bug scored 1.0 instead of 0.33 by previewing a month and replaying it on a second try; fixed in round 3 (`test_a_second_try_cannot_replay_what_the_first_try_revealed`). QA 07c F4: within one try, a server that adopts the amount the client then pays as the order's total earns 0.67 for the same bug, with no second try; 1,293 of 1,784 trading-day and screen units (72.5%) carry such an echo (upper bound) | A second try only after the server stopped, within 2% of units, on a clean slate, deciding only units the first try left unanswered: the preview no longer pays (0.33 with either defence). The within-try echo is pinned by the same check at 0.67 | The within-try echo: answer-fitting that can turn a cascading bug into a one-day loss | The owner's call: template echoed request fields from the candidate's own answers, or credit a day only when every earlier day of its month matched | 🟡 YELLOW / LOW |
| 11 | A correct server scores 0: an absolute link in `/app/server` (a venv's interpreter) makes Harbor's copy refuse the whole delivery | Harbor's artifact copy (tarfile `data` filter) | QA 07 F3, confirmed: `AbsoluteLinkError` on the venv link; reproduced in `checks/` with a real venv; fixed in round 3. QA 07c N2: a link to `/dev/zero` was copied until the disk filled; fixed in round 4. QA 07d S2: a copy that failed arrived as an empty `/app/server` and scored 0; fixed in round 5. QA 07e M4: round 5 made a missing mark an evaluation error, and a submission could make its own copy fail (a 1 TiB sparse file, a full disk, a process the hook missed), turning its 0 into a re-run; fixed in round 6. QA 07f M4: round 6's bound walked by path name and missed what lay below PATH_MAX, where a 4 TiB sparse file made the copy's pack overrun; exhausted inodes did the same; fixed in round 7, with a check past macOS's PATH_MAX | `[[verifier.collect]]` runs `fsmaint-sweep` (`prepare-delivery` until round 9) before the copy: links inside become relative, links out become copies of files or directories (as `dev`, within the delivery's limits and two minutes; devices, pipes and sockets left out), dangling links, links to devices and special files go; the instruction says such links are replaced by copies; the hook ends the agent's processes with `kill -9 -1` as their user, gives back room and inodes set aside at the start, walks the delivery by directory descriptor, removes what the copy would refuse (since round 12 a link is followed by the kernel to a file or directory the walk saw and kept only as the relative path straight to it), refuses (moving aside, leaving an empty marked directory) a delivery it cannot measure within 240 s, over 100,000 entries (every name listed), 1 GB or a 1,000-byte path, or that the copy's own pack, tried first within 100 s, cannot make, and marks it with its entries and bytes; the verifier scores what arrived, with a note for a missing mark or a refusal, and a copy cut short or of which nothing arrived is an evaluation error | A link to more than the delivery's limits is removed rather than copied; the hook is best-effort in Harbor (a failure is logged, the copy goes on): a delivery copied without it is scored with a note. A machine whose `/tmp` never had room for a large delivery is left to the copy, which then fails as an evaluation error. A pack that takes the trial 100 s on a slow machine is refused though Modal's 600 s would have taken it | Run the hook in a container on a venv and a Go module cache | 🟡 YELLOW / LOW |
| 12 | The server the agent studies answers differently from the grader, so doing exactly what the instruction asks loses units | The sealed server's configuration against the recorders' and the solution's | QA 12 F1 (2026-11-19): the sealed server served the web client, so `DELETE /nowhere` answered 405 `allowed: []` there and 404 `unknown_path` in the corpus; a perfect clone lost 6 units. Fixed in round 4 | One settings file, `environment/stockwell.env`, for the sealed server, the live recorder and the solution, with no client directory (the legacy recorder builds the same app in-process); a check ties every file to it and the instruction's numbers to the code; the regrade of the solution with that file is 1.0 on every unit | The Mac recording and the Ubuntu images run different Python, SQLite and zlib builds; reading the code found no dependence (QA 11, 12) | The Linux baselines: 4,002 of 4,002 for the solution | 🟢 GREEN / LOW |
| 13 | A server that fails under concurrent load earns its units back on second tries played one at a time | Verifier's second tries | QA 20 (2026-11-19): second tries were uncapped and alone, and a sequential pass fits the deadline, so a server that crashes whenever requests overlap recovered most of its units. Fixed in round 4 | A second try only for a scenario in flight when the server stopped, never for a wrong answer or a request a live server left unanswered, and only while the units they decide stay within 2% of all units; the check pins the share and that a dropped request gets none | A server that crashes under load keeps 2% of the units at most | None | 🟢 GREEN / LOW |
| 14 | A deliberately hostile submission makes the evaluation end in an error instead of 0, with no reward. Closed in round 12, each with a check that fails on round 11 (`375b570`): about 99,000 crafted links outlast the delivery hook's 600 s (QA 07g F1), and chains do the same (QA 22 F3 of the Carve task: 4,000 links took round 11's stage 22.6 s here, four times as long at each doubling); the link fixer uses up the spare inodes, so a refusal dies after `/app/server` is moved aside (07g F2); a link that resolves inside only through another link, or climbs above `/` and back in, hidden from the fixer, makes Harbor's extraction refuse the copy (07g F3, QA 22 F5: round 11 kept it, `LinkOutsideDestinationError`, "The copy arrived incomplete: 2 of 3 entries"); pipes left out of the entry count let tens of millions of them hold the hook; zombies kept the kill loop at 100 passes where the first process reaps nothing; the sweep exited without a manifest for a non-directory at `/app/server` and where the manifest's name could not be moved aside (QA 22 F6); the manifest's changes were unbounded and the verifier read it whole (QA 22 F1); a refusal's rename of `/app/server` was not guarded against EXDEV. Closed in round 13 (re-check 08), each with a check that fails on `cd98856`: a file with more names than a copy's file system allows links (65,000 on ext4) arrived as copies, whose extra bytes failed the count check and, for a large file, could fill the host's disk (now a file with more than 1,000 hard links refuses the tree, a stated limit, and more arriving than counted is scored with a note); a fork bomb left running past the session could keep the hook, and the copy, from starting (now a `su` session of `dev`, harbor's way of starting the agent's commands, is capped at 16,384 processes and threads, and the cap the platform gives is recorded in `sweep_log`). Left: where neither a memory cgroup nor a VM's own meminfo can be read, a memfd that no process maps is not counted (07f); where `/app/server` cannot be renamed, a refused tree with millions of entries at its top is moved aside one entry at a time; the process cap holds only where the kernel enforces RLIMIT_NPROC and the sandbox's own process limit is higher than the cap (both unmeasured; the baselines' `sweep_log` shows the cap a session got) | Delivery hooks; Harbor's artifact copy; the verifier's memory guard | QA 07e, 07f and 07g (2026-11-19); 07g F3 run through Harbor's own extraction code, F1 timed on macOS; round 12 against the catalogue of QA 22 and 23 of the Carve task, which shares this hook's family, each case run on `375b570` and on round 12 | None of these gives reward, reads answers or touches honest work: an honest delivery holds no crafted link chains, no tens of thousands of links and does not exhaust inodes. Round 12 makes each closed path a scored 0 with a note, or a tree copied as the agent left it, links straightened. Accepted on 2026-11-19 under a run policy for what is left: one attempt per trial; every errored trial is read; it scores 0 when its own files show the submission caused it, and is otherwise re-run as an infrastructure fault | A hostile run costs one trial and a read | The container red team repeats 07f's deep sparse file and full inodes, 07g's link chains and a file with 70,000 hard links | 🟡 YELLOW / LOW |
| 15 | Outlast the session: go on working, writing or fetching after the agent's limit, while the platform leaves a capped turn's commands running, with the network back, until the collect hook (rounds 8 to 14: outlast or stop the maintenance timer that ended the session before the limit) | The platform's handling of a turn that reaches its limit; the collect hook; file change times | Round 15: the platform's verdicts on BasedPL's versions 2 and 4 rejected a task-side stop before the limit, and the judges dropped the timer (harbor-lh `ops/swe-marathon-v2/decisions/2026-11-24-timer-round3-flat-bundles-DECISION.md`: harbor stops waiting at the limit but never ends the agent's commands, and the network comes back once the turn is over, `PLATFORM_EGRESS_WINDOW.md`). `test_a_capped_session_keeps_nothing_written_or_fetched_after_its_end` and `test_a_late_file_cannot_keep_its_content_through_another_name` fail on round 14 (`1a6b87b`), which keeps everything; `test_an_honest_capped_tree_with_hard_links_loses_no_name` (Carve's re-check: a sweep that moves a name before judging makes another name of the same file read as late) loses nothing here and three names without the fence's upper bound; `test_a_file_a_process_could_still_write_after_the_end_is_left_out` (R1, a stand-in `/proc`) fails on `bbae97b`, where the held files arrive | The work's end is the start the set-up records plus 34,560 s. The collect hook ends the agent's processes, writes its fence once nothing else can touch the tree, removes every entry of `/app/server` other than a directory whose change time falls between the end and the fence, with every other name of the same file and a note each, and copies in no outside file or directory a link points to in which a file or link changed after the end; nothing it changes after the fence is judged, so none of its own moves makes an honest name read as late. Before it ends the processes it stops them and, as the user, lists the files they map shared and writable or hold open for writing, which can be written without their change time moving; once the end has passed those count as changed after it, and a tree whose list cannot be made is refused (BasedPL's re-check R1). The change time is the kernel's: the agent can neither set it nor keep a write from moving it | The end comes from the set-up's last moment, a little before harbor starts the agent's clock, so a capped session's writes in its last moments are removed too; a late file's earlier content goes with it; a directory moved in after the end keeps the files in it written before the end; writes through a shared memory map within one dirty-page window may not move a change time; a session that ends by itself has no end yet, so what its detached processes write before the collect hook counts (Stockwell's code is private, so the network has nothing of it to fetch); a pause of the trial queue stops the agent's clock but not the wall clock, so on a backend that can pause a sandbox (not Modal) the end comes early by the pause; a file hard-linked into the tree from the agent's own file under the manifest's name, or from `/logs/artifacts` where that cannot be renamed, reads as late in a capped session; a mapping written after the end and unmapped, or made read-only, before the collect hook leaves no trace, and a process of the user made undumpable refuses the tree once the end has passed | The first capped model trials: a reward about 15 minutes after the cap, no `step_results` in `result.json`, and the sweep's note and `sweep:` line for every entry removed | 🟢 GREEN / LOW |

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| Files a stopped process could still write (BasedPL's re-check R1) | round 15 against `bbae97b`, on a stand-in `/proc` | `bbae97b` keeps the held files (`complete 16 1716`); now, once the end has passed, `mapped.bin` with its second name and `written.log` are removed with a note each, the held file outside is not copied in, `sweep_log` reads `sweep: 3 files were open for writing or mapped writable ...`; before the end everything stays; an unreadable `/proc` and an undumpable process refuse the tree |
| Late writes of a capped session | round 15 against round 14 (`1a6b87b`) | round 14 keeps everything a detached process writes and fetches after the end (`complete 11 10479`: the fetched file, the appended source, the new link and a copy of the file fetched outside); round 15: `complete 5 1035`, `app/main.py`, `late.txt`, `late-link` and `fetched.bin` removed with a note each and `sweep: 4 entries that changed after the work's end were removed`, the link to the file fetched outside not copied, the writer ended by the sweep's own loop before the fence; a session that ended before its limit keeps everything. Without the set of late files two of a late file's three names survive (`complete 12 1666`) |
| An honest capped tree with hard links (Carve's re-check) | round 15; round 14 (`1a6b87b`); round 15's sweep without the fence's upper bound | round 15: no name lost, no note about the work's end (`complete 14 2658`); round 14 the same (no rule on late writes); without the upper bound, every change after the end judged (Carve's shape): `complete 11 658`, three names lost |
| Flat bundle against the steps bundle | round 15: flat `9c6f8371270f`, steps `8725378e9033` (and `bbae97b`'s `4079a1748e67` and `7b68392e5eb4`, the same way) | the same 1,160 names once `steps/01-rebuild-server/` is dropped, the same bytes and executable bits in all but `task.toml`, which lacks `multi_step_reward_strategy = "final"` and the `[[steps]]` table (limits 34,560 s and 6,000 s, the top-level values); the same task name |
| Reference and empty server through the verifier, local, no sandbox | round 15: everything from the flat bundle `9c6f8371270f` (the regrade reading the bundle's root), its solution installed from an isolated copy (only the interpreter path swapped for this Mac) | reference 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, nothing unfinished, no note; 509.3 s of replay against the 5,400 s deadline. Empty server 0.0, 0 of 4,002, "/app/server/run is missing or not executable". `bbae97b`'s `4079a1748e67` the same (514.4 s, and 0.0), and the first build `77c04a446699` (519.5 s) |
| `checks/` (62 tests) with `ci_checks` (27) | round 15 | 89 pass under Python 3.13; `ci_checks/check_repository.py` passes; the sweep's three scripts and `verify.py` compile under Python 3.12.13; the sweep and the set-up pass `dash -n`. One timing check (a hanging and a dripping server against a 4 s deadline) failed once under load in the first full run and passed alone and in every full run since |
| Bundle | round 15: flat `9c6f8371270f` (the upload), steps `8725378e9033`, 1,160 files and 247.3 MB each | each built twice with the same hash and `diff -r`-identical files; Oddish preflight on the flat bundle passes; `compute_task_content_hash` of the flat bundle `7f631001774d...` against version 10's (`7a92d0bd02fe`) `2c5d937b30d5...`; no hidden upload among 495 agent-image files. `bbae97b`'s `4079a1748e67` (content hash `2160b86bc5b9...`) differs in the sweep alone |
| Reference through the verifier, local, no sandbox | round 13: everything from bundle `500c1a290b4e`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 493.4 s of replay against the 5,400 s deadline. An empty server from the same bundle: 0.0, 0 of 4,002 |
| Re-check 08's findings | round 13 against round 12 (`cd98856`) | M1: the build removes `/opt/py/requirements.txt` after the install, and no other file the agent image receives states the sealed server's stack. S1: a file with more than 1,000 hard links refuses the tree, stated in the instruction; more arriving than counted is a note (round 12: "The copy arrived incomplete: 2 of 2 entries and 20 of 10 bytes"). S2: a su session of `dev` capped at 16,384 (the Dockerfile's PAM edit run on two stand-in files with GNU sed; the image's own su file and the platform's enforcement not verified; the baselines' `timer_log` records the cap). S3: no "compare" in the instruction. The five checks fail on `cd98856` |
| `checks/` (61 tests) with `ci_checks` (27) | round 13 | 88 pass under Python 3.13; `ci_checks/check_repository.py` passes; the hook's scripts and `verify.py` compile under Python 3.12.13; the sweep and the set-up pass `dash -n` |
| Bundle | round 13: `500c1a290b4e`, 1,161 files, 247.3 MB; flat `6dc8f86a05ba` | built twice with the same hash and `diff -r`-identical files (the flat one too); Oddish preflight passes; no hidden upload among 496 agent-image files; differs from round 12's `7bcb797ee1be` in the Dockerfile, `fsmaint-sweep`, `start-sealed-server`, the instruction and `tests/verify.py` only |
| Re-check 08 | round 12: `375b570..cd98856`, bundle `7bcb797ee1be` | FAIL: M1 (`/opt/py/requirements.txt` in the agent image), should-fixes S1-S3, notes N1-N5; the rest of round 12 held (84 passed; its eleven checks fail on `375b570`) |
| Reference through the verifier, local, no sandbox | round 12: everything from bundle `7bcb797ee1be`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 458.7 s of replay against the 5,400 s deadline. The first build, `e16eb2141c6f`, the same in 478.9 s |
| Empty server through the verifier, local | round 12: bundle `7bcb797ee1be`'s corpus and media | 0.0, 0 of 4,002, "/app/server/run is missing or not executable" |
| Agent-caused evaluation errors | round 12 against round 11 (`375b570`), the Carve task's QA 22/23 and QA 07g | round 11: a link that climbs above `/` and back in made the copy stop (`LinkOutsideDestinationError`) and the verifier raise "The copy arrived incomplete: 2 of 3 entries and 10 of 10 bytes"; chains of 1,000, 2,000 and 4,000 links took its stage 1.62, 5.86 and 22.64 s, 1,000 long targets 1.01 s. Round 12: the copy takes the tree; 0.12-0.18 s and 0.08 s. The ten path checks fail on `375b570` and pass here |
| Evaluation cues | round 12: the instruction, the client (source, built files, README, `package.json`, `openapi.json`), the sealed server's OpenAPI document, the sealed bytecode's strings, the samples' strings and PDF text | the instruction holds none of the listed words and no framework name; everything else found is the application's own (revaluation, `overflow: hidden`, a blind count's hidden quantity, a route's score, `verify_password`) |
| `checks/` (57 tests) with `ci_checks` (27) | round 12 | 84 pass under Python 3.13; `ci_checks/check_repository.py` passes; the hook's scripts compile under Python 3.12.13 and both hooks pass `dash -n` |
| Bundle | round 12: `7bcb797ee1be`, 1,161 files, 247.3 MB; flat `ddff792eafb5` | built twice with the same hash and `diff -r`-identical files (the flat one too); Oddish preflight passes; no hidden upload among 496 agent-image files; differs from round 11's `7a92d0bd02fe` in the two hooks, the instruction, `tests/verify.py` and `task.toml` only |
| Oddish verdict | round 11: bundle `7a92d0bd02fe`, version 10 | reject: evaluation awareness in trials 99 and 100 (the completion sentence; the harness's command line in `ps`), and `info_leakage` (the instruction's framework list, used in all three trials); baselines correct, the three model trials good failures (0.209, 0.171, 0.072) |
| Reference through the verifier, local, no sandbox | round 11: everything from bundle `7a92d0bd02fe`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 530.6 s of replay against the 5,400 s deadline; 573 MiB peak resident |
| The shipped corpus | round 11: `scenarios.json.gz` of `7a92d0bd02fe` against that of `43cf2c2534a4` | the new one decompressed is the old one without its 432-byte `"recorded_with":{...},` segment; the `scenarios` arrays are the same 97,916,830 bytes (SHA-256 `9f5ebb02...`); the verifier's reader yields the same 2,262 scenarios in the same order from both; neither private seed anywhere in the new bundle; gzip header without a name or a time |
| Pre-audit sweep | round 11: every file of `7a92d0bd02fe` (text, the corpus record by record, bytecode strings, binary strings, media metadata) | fixed: the corpus's record, the probe in `solve.sh`, the laptop timing and two recorder mentions in `replay.py`; what remains is listed in the development log |
| `checks/` (46 tests) with `ci_checks` (27) | round 11 | 73 pass under Python 3.13; `ci_checks/check_repository.py` passes. The new packager check has a corpus with `recorded_with`, `source` or `zz` beside its scenarios refused (round 10's packager packs it); the bundle check pins the packaged corpus's one key, no record or seeds file and a `solve.sh` that only runs `oracle.py` |
| Bundle | round 11: `7a92d0bd02fe`, 1,161 files, 247.3 MB; flat `c857be171e8c` | built twice with the same hash (the flat one too); Oddish preflight passes; no hidden upload among 496 agent-image files; differs from round 10's `43cf2c2534a4` in the corpus, `solve.sh` and `replay.py` only |
| Oddish baselines and source audit | round 10: bundle `43cf2c2534a4`, version 9, `--no-archil` | reference 1.0 twice, no-op 0.0 twice (reported by the coordinator); source audit: one must-fix, the corpus's `recorded_with` record (round 11) |
| Reference through the verifier, local, no sandbox | round 10: everything from bundle `43cf2c2534a4`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 552.1 s of replay against the 5,400 s deadline; 625 MiB peak resident. The first build of this round, `3d0f83058ddb` (one function name apart, in the sweep), the same: 4,002 of 4,002 in 567.7 s, 556 MiB |
| `checks/` (45 tests) with `ci_checks` (27) | round 10 | 72 pass under Python 3.13; `ci_checks/check_repository.py` passes. The five timer and sweep checks run the scripts under dash; each fails on the broken copy made for it (20 of them) and passes on two unchanged copies. The bundle check's word list for the task's own files in the image fails on the first build's sweep (`trial_pack`) |
| Bundle | round 10: `43cf2c2534a4`, 1,161 files, 247.3 MB; flat `d533cc11049f` | built twice with the same hash (the flat one too); Oddish preflight passes; no hidden upload among 496 agent-image files; differs from round 9's `e129cb7c2b1b` in `environment/fsmaint-timer` and `environment/fsmaint-sweep` only, and from this round's first build `3d0f83058ddb` (flat `dc452cfabb43`, never uploaded) in the sweep's one function name; no word of the list in either hook |
| Not run (QA 07h F2) | round 10 | The two hooks as root in the image, with the real `setpriv`, `pkill`, `pgrep -r`, `setsid`, `ps` and paths; the sweep's lines that end the user's processes, which the stand-ins never reach; the timer's 9.4 hours. The guard against a refused fork under Ubuntu's dash (measured under macOS's, `dash-16`); the `/proc` scan on a real `/proc` (run on a stand-in folder). The version 9 baselines show the arming and the stop; a canary trial with `FSMAINT_TIMER_END_SECONDS=600` would show the firing |
| Reference through the verifier, local, no sandbox | round 9: everything from bundle `e129cb7c2b1b`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 500.7 s of replay against the 5,400 s deadline; 452 MiB peak resident |
| `checks/` (41 tests) with `ci_checks` (27) | round 9 | 68 pass under Python 3.13; `ci_checks/check_repository.py` passes |
| Bundle | round 9: `e129cb7c2b1b`, 1,161 files, 247.3 MB; flat `679240b989a1` | built twice with the same hash; Oddish preflight passes; no hidden upload among 496 agent-image files; no word of the audits' list in the files the task puts into the agent image, in `task.toml` or in the solution |
| Reference through the verifier, local, no sandbox | round 8: everything from bundle `54f0913384e4`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 466.5 s of replay against the 5,400 s deadline; 707 MB peak resident |
| `checks/` (41 tests) with `ci_checks` (27) | round 8 | 68 pass under Python 3.13; `ci_checks/check_repository.py` passes |
| Bundle | round 8: `54f0913384e4`, 1,161 files, 247.3 MB; flat `54767f9d067e` | built twice with the same hash; Oddish preflight passes; no hidden upload among 496 agent-image files |
| Oddish baselines | round 7: bundle `cdde8d8e6e42`, version 7, `--no-archil` | reference 1.0 twice (4,002 of 4,002), no-op 0.0 twice (reported by the coordinator) |
| Narrow adversarial re-check (QA 07g) | round 7: `e8a8cc9`, bundle `cdde8d8e6e42` | CONCERN: no finding that gives reward, reads answers or harms honest work; three paths by which only a hostile submission ends the run in an error (hackability row 14) and two minor notes. Bundle `cdde8d8e6e42` is version 7 as checked |
| Reference through the verifier, local, no sandbox | round 7: everything from bundle `cdde8d8e6e42`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 499.2 s of replay against the 5,400 s deadline; 571 MB peak resident |
| `checks/` (40 tests) with `ci_checks` (27) | round 7 | 67 pass under Python 3.13; `ci_checks/check_repository.py` passes; round 6's hook marks the deep sparse tree `delivered`, round 7's refuses it |
| Bundle | round 7: `cdde8d8e6e42`, 1,160 files, 247.3 MB; flat `d54a6abee021` | built twice with the same hash; Oddish preflight passes; no hidden upload among 495 agent-image files |
| Reference through the verifier, local, no sandbox | round 6: everything from bundle `2362781131b0`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 497.5 s of replay against the 5,400 s deadline; 551 MB peak resident |
| `checks/` (40 tests) with `ci_checks` (27) | round 6 | 67 pass under Python 3.13; `ci_checks/check_repository.py` passes; each new or rewritten check fails against round 5's verifier |
| Bundle | round 6: `2362781131b0`, 1,160 files, 247.3 MB; flat `99111f0bafee` | built twice with the same hash; Oddish preflight passes; no hidden upload among 495 agent-image files |
| Oddish baselines | round 5: bundle `7436a4aac616`, version 6, `--no-archil` | reference 1.0 twice (4,002 of 4,002), no-op 0.0 twice (reported by the coordinator); model trials (claude-code, three) started on version 6 |
| Reference through the verifier, local, no sandbox | round 5: everything from bundle `7436a4aac616`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above, no note; 500.8 s of replay against the 5,400 s deadline; 587 MB peak resident |
| `checks/` (37 tests) with `ci_checks` (27) | round 5 | 64 pass under Python 3.13; `ci_checks/check_repository.py` passes; each of the 5 new checks fails against round 4's verifier |
| Bundle | round 5: `7436a4aac616`, 1,160 files, 247.3 MB; flat `c98d148ef8f3` | built twice with the same hash; Oddish preflight passes; no hidden upload among 495 agent-image files |
| Oddish baselines | round 4 fix: bundle `87db5085aa97`, version 5 | running when round 5 started; not read here |
| Oddish baselines | round 4: bundle `d38fb62325c8`, version 4 | reference 0.0 twice (0 of 4,002): `oracle.py` raised `IndexError` looking for its settings above `/solution`, so no `run` was installed; no-op 0.0. Fixed in `87db5085aa97` (version 5) |
| Reference through the verifier, local, no sandbox | round 4 fix: everything from bundle `87db5085aa97`, its solution installed from an isolated copy (only the interpreter path swapped for this Mac), its corpus and its media | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try, no answer of 500 or above; 454.2 s of replay against the 5,400 s deadline |
| `checks/` (32 tests) with `ci_checks` (27) | round 4 fix | 59 pass under Python 3.13; `ci_checks/check_repository.py` passes |
| Bundle | round 4 fix: `87db5085aa97`, 1,160 files, 247.2 MB; flat `956c53c456fa` | built twice with the same hash; Oddish preflight passes; no hidden upload among 495 agent-image files |
| Reference through the verifier, local, no sandbox | round 4: the round 3 corpus; the solution from the bundle's bytecode with `environment/stockwell.env`, the sealed server's settings | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try; 472.5 s of replay against the 5,400 s deadline; 52 scenarios run alone; the corpus held in 98 MB |
| `checks/` (32 tests) with `ci_checks` (27) | round 4 | 59 pass under Python 3.13; `ci_checks/check_repository.py` passes |
| Bundle | round 4: `d38fb62325c8`, 1,160 files, 247.2 MB; flat `fb9bb0a0f2f4` | built twice with the same hash; Oddish preflight passes |
| Hidden uploads against the agent image (`scripts/scan_uploads.py`) | round 4: the round 3 corpus, 495 agent-image files | nothing found |
| Recording | round 3: Stockwell `d61d29c`, new private seeds | 2,262 scenarios (2,005 legacy, 130 counts and kits made live, 83 media, 44 months), 4,002 units (1,432 trading days, 352 screens), 89,524 requests, no answer of 500 or above; 10 min 52 s locally |
| Reference through the verifier, local, no sandbox | round 3 corpus and private media, the oracle from the bundle's bytecode | 1.0 on every unit: 4,002 of 4,002 (2,262 of 2,262 scenarios), 9 planned restarts, no other restart, no second try; 518 s of replay against the 5,400 s deadline |
| `checks/` (26 tests) with `ci_checks` (27) | round 3 | 53 pass under Python 3.13; `ci_checks/check_repository.py` passes |
| Bundle | round 3: `06c782d713f6`, 1,157 files, 247.2 MB (scenarios 10.6 MB compressed, private media 188.9 MB, samples 42.0 MB); flat `a633cd8ca3c5` | built twice with the same hash; Oddish preflight passes |
| Hidden uploads against the agent image (`scripts/scan_uploads.py`) | round 3: 2,262 scenarios, 89,524 requests, 627 base64 and 1,307 raw uploads, 151 bodies built around a media file, 1,187 file answers, 493 agent-image files | nothing found |
| Recording | round 2: Stockwell `d61d29c`, new private seeds | 2,287 scenarios (2,160 legacy, 83 media, 44 months), 3,999 units (1,413 trading days, 343 screens), 82,837 requests, no answer of 500 or above; 8 min 51 s locally |
| Reference through the verifier, local, no sandbox | round 2 corpus and private media | 1.0 on every unit: 3,999 of 3,999 (2,287 of 2,287 scenarios), 9 planned restarts, no other restart, no retry; 393 s of replay, 6 min 33 s with loading |
| `checks/` (21 tests) with `ci_checks` (27) | round 2 | 48 pass under Python 3.13; `ci_checks/check_repository.py` passes |
| Bundle | round 2: `0ffbed822f74`, 1,115 files, 85 MB (scenarios 9.4 MB compressed, private media 42 MB, samples 28 MB) | built twice with the same hash; Oddish preflight passes |
| Hidden uploads against the agent image (`scripts/scan_uploads.py`) | round 2: 2,287 scenarios, 82,837 requests, 655 base64 and 1,721 raw uploads, 1,195 file answers, 481 agent-image files | nothing found |
| `checks/` (17 tests) with `ci_checks` (27) | adversarial QA fixes, 2026-11-19 | 44 pass under Python 3.13; `ci_checks/check_repository.py` passes; Oddish preflight passes |
| Bundle | adversarial QA fixes: `2a602a3f17e6`, 705 files (the 19 fixtures gone) | built twice with the same hash |
| Hidden uploads against the agent image (`scripts/scan_uploads.py`) | adversarial QA fixes: 2,483 scenarios, 63,033 requests, 636 base64 and 712 raw uploads, 558 file answers, 469 agent-image files | nothing found; on the previous bundle `c4746eb643c6`, 308 (267 uploads, 20 cut short, 21 file answers), the QA 06 leak |
| Reference through the verifier, local, no sandbox | adversarial QA fixes: Stockwell `d61d29c`, same corpus and private media | 1.0 (2,483 of 2,483), 264 s, no restarts, no notes |
| QA 10's experiments E1 to E10, local, fake servers | adversarial QA fixes | see the development log, 2026-11-19 |
| `checks/` (7 tests) | re-cut with leak fixes, 2026-11-18 | pass; Oddish preflight passes |
| Bundle | re-cut with leak fixes: `a691f329ea71`, 574 files | built twice with the same hash |
| `checks/` (6 tests) | re-cut, pinned to Stockwell 722a647, 2026-11-18 | pass |
| Reference through the verifier, local, no sandbox | real-world media: Stockwell `d61d29c`, 2,483 scenarios (83 media), 63,033 requests, private media set seed 20261122 | 1.0 (2,483 of 2,483), 261 s, no restarts |
| Reference through the verifier, local, no sandbox | re-cut: 2,400 scenarios, 60,929 requests, seed 20261120 | 1.0 (2,400 of 2,400), 310 s, no restarts |
| Bundle | re-cut: `fdf9b7e70edf`, 572 files, 13 MB (scenarios gzipped) | built twice with the same hash |
| Oddish baselines | re-cut with leak fixes and no stated time budget: bundle `e51fb417380f`, task `...backoffice-server-rebuild-a7ccd915` version 2, experiment `backoffice-server-rebuild-recut-20261118` (https://www.oddish.app/experiments/d244f7d6), one row | reference 1.0 twice (trials 13, 14), no-op 0.0 twice (15, 16): the first build of both images. Ran on Archil with no verifier fault. No model trials yet |
| `checks/` (4 tests) | v1 (standard-library reference, 56 routes), 2026-11-18 | pass |
| Reference through the verifier, local, no sandbox | v1: 1,400 scenarios | 1.0 twice, 6 s each |
| Oddish baselines | v1: bundle `96bc24f242e5`, task `...backoffice-server-rebuild-a7ccd915` version 1, experiment `backoffice-server-rebuild-20261118` (https://www.oddish.app/experiments/bd81d811) | reference 1.0 twice (trials 1, 2), no-op 0.0 twice (trials 3, 4: no `run` file) |
| Model trial on Oddish | v1, same version and experiment | trial 8 (claude-code, relace/deepseek-v4.1-flash) is not a result: the agent command failed in 3 seconds on shell quoting, because the appended system prompt held an apostrophe and a non-root agent user makes the harness pass it through a shell. Trial 11, same agent and model without the apostrophe, started 2026-11-17 21:12 UTC and was cancelled at 22:40 UTC on the owner's instruction (no trials until the application is large); no result |
| `harbor check` | none | not run |

## Build and deliver

```bash
cd tasks/swe-m2-software-engineer/backoffice-server-rebuild
# STOCKWELL_REPO: the Stockwell checkout (default ../stockwell next to swe-marathon-2); STOCKWELL_PYTHON: a Python with its packages
# MEDIA_PYTHON (or the first python3 on PATH that has them): PyMuPDF, Pillow, numpy; ffmpeg and node are also needed
rm -rf experiment/media/visible experiment/media/private                                # names are drawn from the seed: start empty
python3 scripts/make_media.py --out experiment/media/visible --seed 20261121           # the samples
python3 scripts/trading_media.py --examples experiment/media/visible --seed 20261121    # supplier invoices and delivery files among them
python3 scripts/make_media.py --out experiment/media/private --seed "$(python3 scripts/seeds.py media)" --big   # full-size large files
python3 scripts/record_scenarios.py --count 2160 --runs 44 --term 6 --kill 3 --screens 8   # seeds from experiment/seeds.json; the record of the recording goes to experiment/recording.json
uv run --no-project --python 3.13 python scripts/package_step.py         # compiles the reference with Python 3.12; experiment/dist/bundles/<hash>/<task slug>/
uv run --no-project --python 3.13 python scripts/package_step.py --flat  # same content without the steps wrapper, named <task>-single
uv run --no-project --python 3.13 python scripts/package_step.py --flat --keep-name  # the upload since round 15: flat, under the task's own name; experiment/dist/flat/<hash>/
python3 scripts/scan_uploads.py experiment/dist/bundles/<hash>/<task slug>   # hidden uploads or file answers the agent image also holds
```

## Remaining work

- Upload the flat bundle `9c6f8371270f` (247.3 MB, `package_step.py --flat --keep-name`) under
  the task's own name as version 11 (version 10, bundle `7a92d0bd02fe`, passed its baselines and
  its source audit; its verdict rejected it on evaluation awareness and the instruction's
  framework list, rounds 12-15; round 15 replaces the never-uploaded `f1293aa9de6f`), after an
  independent re-check of round 15, run its baselines with `--no-archil` (reference twice, no-op
  twice), and have its Oddish source audit pass before any model trial (the owner's gate since
  version 8). Pass criteria for
  the reference: 4,002 of 4,002, `planned_restarts` 9,
  `restarts` 0, `retried` 0, `unfinished` 0, no answer of 500 or above in
  `server_errors_by_theme`, no note of the hard stop, of a stop for disk or memory, or from the
  collect hook, and `3.5 x elapsed_sec + 300 <= 5,400`. For both baselines: a `sweep_log` of one
  line, `sweep: a su session of the user had a process limit of 16384` (round 13), and no note of
  an entry changed after the work's end (both end long before it); `result.json` with no
  `step_results`, which shows the flat bundle ran. A limit of
  `unlimited`, or no such line, means the cap on the agent's processes did not apply on the
  platform; a number below 16384 means a lower one was already in place.
- In the first model trials that reach the limit (the judges' watch list): about 15 minutes after
  the cap the trial should end with a reward and a `result.json` without `step_results`, and the
  manifest's notes and `sweep_log` say what the sweep removed for changing after the work's end. A
  capped trial that ends with "Agent execution timed out" and no reward: read attempt 1's
  `oddish-mon.log` for a `docker.compose_build` RuntimeError or `startup_retry phase=build`, report
  the trial as lost, never as 0, and start nothing more until the judges' cap probe (D) reports.
  Record `memory_measure`, `server_peak_held_mib`,
  `free_space_mib`, `grader_oom_score_adj`, any note of an unwatched disk and the environment,
  hook, collect and verifier-build times against the 12-hour lease (QA 07c F7, QA 13 S3). For the
  no-op: 0.0 with `status: completed` and a manifest of `complete 0 0`.
- Before a second step is added: task-level collect hooks run at every step's collection, and the
  work's start is recorded at the trial's set-up, so every step's end would count from it. Record
  the start where each step begins and give the sweep that step's limit, then go back to the steps
  layout for the upload (the flat bundle has one step by construction).
- What the rule on late writes leaves (round 15, hackability row 15): the end is taken from the
  set-up's last moment, a little before harbor starts the agent's clock (one hook's return and the
  agent phase's own start, not measured), so a capped session's writes in its last moments are
  removed too; removing a late file removes its earlier content as well (nothing keeps an earlier
  copy); a directory moved into the tree after the end keeps the files in it that were written
  before the end; writes through a shared memory map within one dirty-page window may leave a
  file's change time where it was; a session that ends by itself has no end yet, so what its
  detached processes write before the collect hook counts (Stockwell's code is private, so the
  network has nothing of it to fetch); and a pause of the trial queue (harbor 0.20's trial control,
  which Oddish's quota pause uses) stops the agent's clock but not the wall clock, so on a backend
  that can pause a sandbox (not Modal, which the `--no-archil` runs use) the end would come before
  the platform's by the pause's length.
- What the list of held files leaves (R1): a process that maps a file writable before the end,
  writes it after the end and unmaps it, or makes the mapping read-only with `mprotect`, before the
  collect hook leaves no trace, and on a file kept in memory the change time never moves; only a
  copy taken at the end would close that. A process of the user made undumpable, which the list
  cannot read, refuses the tree once the end has passed, honest or not (this task needs none).
- What rounds 12 and 13 left of the agent-caused evaluation errors (hackability row 14): a refused
  tree with millions of top-level entries where `/app/server` cannot be renamed (create
  `/app/server` at set-up as a directory of the upper layer, so that it renames whole), the memfd
  the memory guard does not see where it has no cgroup or meminfo, and the process cap's two
  conditions (the kernel enforces RLIMIT_NPROC; the sandbox allows more processes than 16,384):
  the baselines' `sweep_log` shows the first in part. Re-check 08's notes N2 (the room checks'
  inode figures are not recorded) and N3 (a refused tree is still replayed, as an empty one) are
  open.
- The run configuration's appended system prompt (harbor-lh `ops/swe-marathon-v2/agents-*.yaml`,
  shared by the five tasks) tells the agent it runs "unattended" until "the completion criteria
  of the task are met or its time budget is used up": the platform's evaluation-awareness check
  may weigh that too, and the instruction states no time budget.
- Not run anywhere yet (QA 07h F2; see Validation): the two hooks as root in the image, with the
  real `setpriv`, `pkill`, `ps` and paths, and a turn that reaches the 34,560 s limit, the only
  place the rule on late writes acts on the platform. The checks run both scripts whole under dash
  on the author's Mac with stand-ins.
  Round 12 adds three things only a container shows: procps's `pgrep -r` state filter (Ubuntu
  24.04's procps has it; where the probe fails the loop falls back to round 11's), that a link's
  `stat` and the walk's `lstat` give the same device and inode on the platform's overlay (they do
  on any one file system), and the EXDEV fallback of a refusal.
- The privilege and limits checks fail closed: a provider whose sandbox cannot set or report
  them ends every evaluation with an evaluation error. The baselines will show it, and whether
  the server's user can lower its OOM priority there (a note in `metrics.json`).
- The within-try echo (hackability row 10): a server that adopts amounts the client echoes earns
  some units back from a cascading bug. The owner decides between templating echoed request
  fields from the candidate's own answers and crediting a day only when every earlier day of its
  month matched.
- A disk burst faster than the one-second guard can still fill the disk; the ballast keeps the
  reward and its retrieval safe, the diagnostics may be lost.
- The memory race (hackability row 5): where the grader lacks CAP_SYS_RESOURCE, a server that
  lowers its OOM priority must fill the rest of the machine (about 1.4 GB on 8 GiB) within one
  10 ms reading of the cgroup or meminfo to have the grader killed; where neither can be read,
  the per-process fallback misses a memfd no process maps. Either way the result is an
  evaluation error, not a 0. QA 07e's red-team item 1 measures it; `memory_measure` in the
  baselines shows which source each provider gives. The clean slate's set-aside data stays on
  disk until the container goes, so second tries start with less free space (QA 07d N5).
- The delivery's room rule refuses a delivery only when the disk had room for it when the
  session began; a platform whose `/tmp` is too small from the start is left to fail as before.
  The trial pack's 100 s, below Archil's 120 s, could refuse on a very slow machine a large
  delivery that Modal's 600 s would have taken.
- Memory sources by provider (QA 07f S2): `--no-archil` runs use Modal VMs, where the meter reads
  a memory cgroup or the VM's own meminfo. gVisor's meminfo misreads (its MemAvailable is
  MemFree, and its status has no `RssAnon`), so the meter does not use it there and falls back
  to the server's processes, where a memfd no process maps is not seen. Version 7's baselines
  should record `memory_measure`, `server_peak_held_mib` and the reference's own RSS on each
  provider before trusting it.
- The app answers 500 for `GET /files/{id}/content` when a file's name has a letter outside
  Latin-1 (the name goes into a `Content-Disposition` header). The corpus does not exercise it;
  report it to the app's owner rather than change the pinned app.
- QA 10 should-fixes still open: a JSON document that describes a file matches the file (E7);
  private media are not checked against the set the answers were recorded with; unpinned base
  images. QA 07c N1: `RLIMIT_NPROC` is counted per uid across a shared kernel.
- QA 01 R3 and R4 (a data takeover, a change request) remain the candidates for further steps.
- Exercise findings 5, 7, 8, 9 and 11 in a container (QA 07c's and 07d's red-team lists); probe
  findings 1 and 2.
- `harbor check` and ratings.
- Decide how to reach the workload target: more modules or follow-up steps.
