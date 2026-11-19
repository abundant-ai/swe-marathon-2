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
| Further steps | Not designed. Candidates: a follow-up change request on the rebuilt server; importing a year of legacy data. |
| Private inputs | `steps/01-rebuild-server/tests/private/scenarios.json` and the private files they upload (`experiment/media/private`, made with `--big`), Git-ignored, produced by `scripts/record_scenarios.py --count 2160 --runs 44 --term 6 --kill 3 --screens 8` from the private seeds in `experiment/seeds.json` (never committed; rotated in round 3). |
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

One agent session of up to 9.6 hours per run (`timeout_sec = 34560` in `task.toml`). There are
no chained sessions or continuation tasks, and the instruction states no time budget. v2 asks
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

1. Delivery: before `/app/server` leaves the agent's machine, a `[[verifier.collect]]` hook runs
   `environment/prepare-delivery` (root, mode 0700). It ends the agent's leftover processes,
   then, as `dev`, makes links inside the directory relative, replaces links that leave it with
   copies of the files or directories they point to (at most 2 GiB in all; devices, pipes and
   sockets are left out) and removes dangling links, links to devices, pipes, sockets and device
   nodes. Harbor's copy (tarfile's `data` filter) refuses absolute links and links that leave
   the directory, so without this a venv's interpreter link made a correct delivery vanish (QA 07
   F3). It runs as `dev`, so it copies nothing `dev` could not read. An `/app/server` that never
   arrives is a note in `metrics.json`.
2. Sandbox: set-user-id and set-group-id bits are cleared, the submission is made root's and
   read-only, and `/app/server/run` is started as user `nobody` through
   `setpriv --no-new-privs`, under `prlimit` (4,096 threads for the user, files of at most
   4 GiB, 6 GiB of address space per process), in a cgroup capping the whole group's memory and
   processes where the machine lets the verifier make one, with `oom_score_adj` 1000 set before
   the drop and raised again every second (without CAP_SYS_RESOURCE the server could lower it;
   the probe notes when it can), with `PORT` and `DATA_DIR` set, in its own process group, with
   no network. The grader asks for a low OOM priority for itself and holds each scenario as
   compact JSON, decoded when played, and its uploads in a bounded cache. Before the server
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
   past either, even one whose bytes keep arriving. Scenarios not played to the end by the
   deadline count as not matched, with a note and a count in `metrics.json`.
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
   stopped, `DATA_DIR` moved into a directory only root can enter, every file `nobody` owns on
   the root filesystem and in `/tmp`, `/var/tmp`, `/dev/shm`, `/dev/mqueue` and `/run/lock`
   removed (with any hard link there) within two minutes, SysV IPC removed as `nobody`, and a
   fresh server started; none of this starts with less than five minutes left. A second try
   decides only the units the first try left unanswered (QA 07 F1).
9. Durable state: after a step marked `restart` the server is stopped (SIGTERM at the end of a
   trading day, with 30 seconds to exit, or SIGKILL straight after a write drawn at random was
   answered), started again on the same `DATA_DIR`, and the month goes on in the same workspace;
   the day after, files uploaded before the restart are read again.
10. Disk: a 256 MiB ballast is set aside before the server starts and given back for the
    results, and a guard stops the server for good when free space on the grader's disks falls
    under 512 MiB, its remaining scenarios failed with a note (QA 07c F3). After the final stop
    `DATA_DIR` is removed within a minute. `verify.py` writes a placeholder of the reward's size
    before the server starts; the reward goes over it in place and is renamed, which needs no
    free space, then `metrics.json` (with the slowest requests, answers of 500 or above by theme
    and the server's peak memory), then the per-scenario results. A failure writing the last two
    costs only those files, a published reward is never taken back, and no cleanup step can
    raise.

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

Highest unresolved severity: 🟡 YELLOW (findings 1 and 2 unassessed; 5, 7, 8, 9 and 11 mitigated but
not yet exercised in a container; 10 keeps a residual the owner decides).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read the sealed server's code and copy it | File permissions in the agent image; what the bundle and its layers hold | Inspected by adversarial QA 04 and 08 (2026-11-19): as the agent's user, the bytecode, the database and `/proc/<pid>/{mem,environ}` of the sealed server are not readable. Not executed in a container | Server files are owned by user `stockwell`, mode 0700, and the agent runs as `dev`. Round 3 (QA 08): the bundle carries the reference as Python 3.12 bytecode only, for the sealed server and the solution, so no layer of either image holds its source (the build fails on a `.py`); every start of the sealed server first checks as `dev` that `/opt/stockwell` cannot be read or entered and fails the setup hook, which stops the trial, if it can. `/opt/py` holds only public third-party packages | A way to become root or `stockwell` inside the container; bytecode can be decompiled by anyone who has the bundle | Probe as `dev`: read `/opt/stockwell`, `/proc/<pid>/mem`, ptrace | 🟡 YELLOW / UNASSESSED |
| 2 | Agent harness starts as root and hands the model a root shell | Harness and `[agent] user` on Oddish | Not tested on Oddish | `user = "dev"` in `task.toml` | Depends on each harness honouring it | Short model trial that prints `id` | 🟡 YELLOW / UNASSESSED |
| 3 | Deliver a proxy to the sealed server | Separate verifier image | By design | The verifier image has no reference server and no network | None found | Keep | 🟢 GREEN / LOW |
| 4 | Replay a table of recorded answers, including answers collected for inputs the agent already holds | Private scenarios; what the agent image holds | QA 06 (2026-11-19): the 19 Stockwell test fixtures shipped in `/app/samples` were uploaded byte for byte by the hidden `files` scenarios; fixed in round 1, and `scripts/scan_uploads.py` checks every bundle. QA 05 (2026-11-19): a crawl of a fresh workspace, a day counter and cheap rules cover 2.2 to 3.5% of round 2's units, through screens the month never changed (67 of 343) and legacy scenarios whose every write is refused (53); left out in round 3 | Scenarios come from a private seed, rotated in round 3 and kept out of the repository: 89,524 requests in 2,262 scenarios (4,002 units), 44 of them months of trading from four start dates whose supplier invoices are made for each purchase order. No screen that answers as a fresh workspace on the same day and no legacy scenario that changes nothing is kept, and every count and kit scenario does its work. The private media share no file and no name with the samples, and the bundle check fails on any hidden upload, cut-short upload or file answer the agent image holds | A table cannot cover them; the generators' shape could be guessed only in outline | Measure a lookup-table submission on the round 3 corpus | 🟢 GREEN / LOW |
| 5 | Submitted server attacks the verifier process or its files, or exhausts processes, memory or disk so that the evaluation publishes no reward | Verifier sandbox | QA 10: a set-user-id binary could run as root; fixed. QA 07 F2: a full process table or disk lost the reward; fixed in round 3. QA 07c F1 and F3 (round 3 re-check): a chunked answer with size `-1` made http.client read the whole stream (300 MiB grew the verifier by 848 MiB); the server could lower its own OOM priority without CAP_SYS_RESOURCE; on providers that pack `/logs/verifier` before reading the reward, a full disk, a 4 GiB `server.log` or appends to it during the pack lost the reward. Fixed in round 4; the `-1` case is a check | Runs as `nobody` through `setpriv --no-new-privs` under `prlimit` (4,096 threads, 4 GiB files, 6 GiB address space per process) and a cgroup where one can be made; `oom_score_adj` 1000 set before the drop and raised again every second; the grader asks for a low one and keeps the corpus as compact text and uploads in a bounded cache. Every byte of an answer counts against the limit and chunk sizes are strict. The server's output goes to a pipe the grader drains (first and last MiB kept), so it holds no file of the grader's. A 256 MiB ballast is given back for the results, and a guard stops the server for good under 512 MiB free. The cleanup never forks, never raises and finds what hides (9); the reward goes over a placeholder and is never taken back once published | Not exercised in a container. A burst faster than the one-second guard can still fill the disk, which costs the diagnostics but not the reward or its retrieval (the ballast) | QA 07c's container red team: OOM floor, `-1` chunk with 3 GB, full disk and big output on each provider | 🟡 YELLOW / MEDIUM |
| 6 | Tamper with reward files | Separate verifier container | By design | Verifier starts fresh with only `/app/server`; the server cannot become root (5) and cannot reach `/logs/verifier` | None found | Keep | 🟢 GREEN / LOW |
| 7 | Replace `/app/server` with a link to `/opt/stockwell/app`, so that Harbor's collector, running as root, copies the sealed bytecode into the trial artifacts and the verifier. Leaks the private reference; no reward (the copy has no `run`) | Ownership of `/app` in the agent image; Harbor's collector; the delivery hook | QA 04 (2026-11-19), traced in Harbor 0.20: `tar -czf ... -C /app/server .` as root follows the top-level link, and GNU tar stores links below it as links. Not executed | `/app` is root's with the sticky bit and `/app/server` root's and writable by everyone: the agent creates and changes anything inside it but cannot remove, rename or replace it. The delivery hook (11) copies what links point to only as `dev`, who cannot read `/opt/stockwell`, so such a link is removed as dangling | A provider whose collector follows links below the top; not executed in a container | In the next container run, as `dev`: `rm -rf /app/server` and `mv /app/server x` fail, and a link to `/opt/stockwell` is removed by the hook | 🟡 YELLOW / MEDIUM |
| 8 | Submission makes the evaluation end without a reward (hangs past the step limit, a reply that is not HTTP, deep JSON, a crash storm, an answer that never ends); a run that errors may also be retried, which gives a bad run a second draw | Verifier | QA 10 E1, E2, E4 and E6, rerun after the fix; checks with fake servers that hang, drip, send garbage or crash; QA 07c E1 (`-1` chunk), fixed in round 4 | A deadline and 30 s of wall clock per request; any reply is a not-healthy server or an answer that matches nothing; an answer is bounded in every transfer encoding; no restart cap; resource exhaustion handled as in 5; the clean slate is bounded in time and skipped with less than five minutes left | None found beyond 5 | Exercise 5's container red team | 🟡 YELLOW / MEDIUM |
| 9 | Pass the durable-state units without durable state: keep a workspace in a process that outlives the planned stop, or in memory written out only on SIGTERM | Verifier's planned restarts | Checks with fake servers that keep state on disk, in memory, or save only on SIGTERM. QA 07 F4: a helper that forks fast enough survived `pkill`; fixed in round 3. QA 07c F2: a process whose main thread exits while other threads run shows as a zombie, and the sweep skipped zombies, so it survived every stop and kept the log open; fixed in round 4, with a fake-/proc check | A planned stop kills the process group, then stops every process of `nobody` read from `/proc` (a zombie leader with live threads included) until a listing finds no new one, kills them all, runs `kill -9 -1` as `nobody` and kills the cgroup where there is one; SIGKILL comes straight after an answered write drawn at random; files uploaded before a restart are read again after it | State kept in `/tmp` instead of `DATA_DIR` also survives a planned restart, but it is durable state all the same | Run QA 07c's zombie-leader repro sandboxed in a container | 🟡 YELLOW / MEDIUM |
| 10 | Preview a month and answer from what later requests reveal: a month goes on after a wrong answer, and the client sends what it was shown, so later requests echo earlier answers (payments, bank statements) | Verifier's second tries; the corpus | QA 07 F1: a server with a one-cent bug scored 1.0 instead of 0.33 by previewing a month and replaying it on a second try; fixed in round 3 (`test_a_second_try_cannot_replay_what_the_first_try_revealed`). QA 07c F4: within one try, a server that adopts the amount the client then pays as the order's total earns 0.67 for the same bug, with no second try; 1,293 of 1,784 trading-day and screen units (72.5%) carry such an echo (upper bound) | A second try only after the server stopped, within 2% of units, on a clean slate, deciding only units the first try left unanswered: the preview no longer pays (0.33 with either defence). The within-try echo is pinned by the same check at 0.67 | The within-try echo: answer-fitting that can turn a cascading bug into a one-day loss | The owner's call: template echoed request fields from the candidate's own answers, or credit a day only when every earlier day of its month matched | 🟡 YELLOW / LOW |
| 11 | A correct server scores 0: an absolute link in `/app/server` (a venv's interpreter) makes Harbor's copy refuse the whole delivery | Harbor's artifact copy (tarfile `data` filter) | QA 07 F3, confirmed: `AbsoluteLinkError` on the venv link; reproduced in `checks/` with a real venv; fixed in round 3. QA 07c N2: a link to `/dev/zero` was copied until the disk filled; fixed in round 4 | `[[verifier.collect]]` runs `prepare-delivery` before the copy: links inside become relative, links out become copies of files or directories (as `dev`, at most 2 GiB; devices, pipes and sockets left out), dangling links, links to devices and special files go; the instruction says such links are replaced by copies; a delivery that never arrives is a note | A link to more than 2 GiB is removed rather than copied; the hook is best-effort in Harbor (a failure is logged, the copy goes on) | Run the hook in a container on a venv and a Go module cache | 🟡 YELLOW / LOW |
| 12 | The server the agent studies answers differently from the grader, so doing exactly what the instruction asks loses units | The sealed server's configuration against the recorders' and the solution's | QA 12 F1 (2026-11-19): the sealed server served the web client, so `DELETE /nowhere` answered 405 `allowed: []` there and 404 `unknown_path` in the corpus; a perfect clone lost 6 units. Fixed in round 4 | One settings file, `environment/stockwell.env`, for the sealed server, the live recorder and the solution, with no client directory (the legacy recorder builds the same app in-process); a check ties every file to it and the instruction's numbers to the code; the regrade of the solution with that file is 1.0 on every unit | The Mac recording and the Ubuntu images run different Python, SQLite and zlib builds; reading the code found no dependence (QA 11, 12) | The Linux baselines: 4,002 of 4,002 for the solution | 🟢 GREEN / LOW |
| 13 | A server that fails under concurrent load earns its units back on second tries played one at a time | Verifier's second tries | QA 20 (2026-11-19): second tries were uncapped and alone, and a sequential pass fits the deadline, so a server that crashes whenever requests overlap recovered most of its units. Fixed in round 4 | A second try only for a scenario in flight when the server stopped, never for a wrong answer or a request a live server left unanswered, and only while the units they decide stay within 2% of all units; the check pins the share and that a dropped request gets none | A server that crashes under load keeps 2% of the units at most | None | 🟢 GREEN / LOW |

## Validation

| Check | Revision | Result |
| --- | --- | --- |
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
python3 scripts/record_scenarios.py --count 2160 --runs 44 --term 6 --kill 3 --screens 8   # seeds from experiment/seeds.json
uv run --no-project --python 3.13 python scripts/package_step.py         # compiles the reference with Python 3.12; experiment/dist/bundles/<hash>/<task slug>/
uv run --no-project --python 3.13 python scripts/package_step.py --flat  # same content without the steps wrapper
python3 scripts/scan_uploads.py experiment/dist/bundles/<hash>/<task slug>   # hidden uploads or file answers the agent image also holds
```

## Remaining work

- Upload bundle `87db5085aa97` (247.2 MB) as version 5 on its own first: Oddish preflight
  checks no size, and Oddish once refused a 138 MB task (QA 20). Then run its baselines with
  `--no-archil` (reference twice, no-op twice). Pass criteria for the reference: 4,002 of 4,002,
  `planned_restarts` 9, `restarts` 0, `retried` 0, `unfinished` 0, no answer of 500 or above in
  `server_errors_by_theme`, and `3.5 x elapsed_sec + 300 <= 5,400` (otherwise raise the deadline
  and the verifier limit and shorten the agent's); record the environment, hook, collect and
  verifier-build times against the 12-hour lease (QA 07c F7, QA 13 S3). For the no-op: 0.0 with
  `status: completed`. Model trials wait for the owner.
- The privilege and limits checks fail closed: a provider whose sandbox cannot set or report
  them ends every evaluation with an evaluation error. The baselines will show it, and whether
  the server's user can lower its OOM priority there (a note in `metrics.json`).
- The within-try echo (hackability row 10): a server that adopts amounts the client echoes earns
  some units back from a cascading bug. The owner decides between templating echoed request
  fields from the candidate's own answers and crediting a day only when every earlier day of its
  month matched.
- A disk burst faster than the one-second guard can still fill the disk; the ballast keeps the
  reward and its retrieval safe, the diagnostics may be lost.
- The app answers 500 for `GET /files/{id}/content` when a file's name has a letter outside
  Latin-1 (the name goes into a `Content-Disposition` header). The corpus does not exercise it;
  report it to the app's owner rather than change the pinned app.
- QA 10 should-fixes still open: a JSON document that describes a file matches the file (E7);
  private media are not checked against the set the answers were recorded with; unpinned base
  images. QA 07c N1: `RLIMIT_NPROC` is counted per uid across a shared kernel.
- QA 01 R3 and R4 (a data takeover, a change request) remain the candidates for further steps.
- Exercise findings 5, 7, 8, 9 and 11 in a container (QA 07c's red-team list); probe findings 1
  and 2.
- `harbor check` and ratings.
- Decide how to reach the workload target: more modules or follow-up steps.
