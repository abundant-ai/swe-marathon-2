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
| Private inputs | `steps/01-rebuild-server/tests/private/scenarios.json` and the private files they upload (`experiment/media/private`), Git-ignored, produced by `scripts/record_scenarios.py --count 2160 --runs 44 --term 6 --kill 3 --screens 8` from the private seeds in `experiment/seeds.json` (never committed). |
| Oracle | The reference server's own source, installed as the delivered server and run on the packages in `/opt/py`. |
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
reference server.

1. `/app/server` arrives as the declared artifact. Set-user-id and set-group-id bits are
   cleared from its files, and `/app/server/run` is started as user `nobody` through
   `setpriv --no-new-privs`, so no set-id bit or file capability can raise it, with `PORT` and
   `DATA_DIR` set, in its own process group, with no network. Before that, a process started
   the same way must show the unprivileged ids, no capabilities and `NoNewPrivs` in
   `/proc/self/status`; otherwise the evaluation stops with an evaluation error.
2. The server has 60 seconds to answer `GET /api/health`.
3. Each scenario creates a workspace and replays its requests on one connection, eight
   scenarios at a time. A step marked `scoped: false` names its full path (the client's
   `GET /api/version`); the others are under `/api/ws/{workspace}`. An answer matches when the
   status code is equal and the JSON body is identical, types included, to the recorded one
   with the candidate's workspace id put where the recorder wrote `{ws}`; a file matches on
   its type, length and SHA-256. A reply that is not HTTP, not JSON, larger than 4 MB of JSON
   or 16 MB in all, or nested too deeply matches nothing. An answer cut short of its
   `Content-Length` is no answer. A connection the server closed while idle is reopened, and a
   request that never reached the server is sent once more.
4. Units: a scenario of the legacy and media themes is one unit and stops at its first
   difference. A month of trading lists its units, one per trading day and one per client
   screen opened after it, goes on after a difference and judges each unit on its own answers.
5. Time: each request has 30 seconds of wall clock and the whole replay 3,000 seconds (the
   step allows 3,600). A watcher cuts any request still running past either, even one whose
   bytes keep arriving. Scenarios not played to the end by the deadline count as not matched,
   with a note and a count in `metrics.json`.
6. Restarts: every scenario is played once; each one that got no answer (the server died,
   dropped the connection or ran out of time) is played once more on its own after all the
   others, so the scenarios in flight beside a crash still count. A server that has died, or
   has not answered its health check for 30 seconds, is restarted before the next attempt,
   with no cap while the deadline holds, and given up after three starts in a row that never
   answer. A failed attempt closes its connection before waiting on the server. Every start
   uses the same `DATA_DIR`.
7. Durable state: the months with a step marked `restart` run one at a time after the others.
   After that step the server is stopped (SIGTERM at the end of a trading day, with 30 seconds
   to exit, or SIGKILL straight after a write was answered), started again on the same
   `DATA_DIR`, and the month goes on in the same workspace.
8. `verify.py` writes `reward.txt` first, then `metrics.json`, then the per-scenario results;
   a failure writing the last two costs only those files.

### Reward formula

```
reward = (matched scenarios + matched trading days + matched screens)
         / (2,243 scenarios + 1,413 trading days + 343 screens)
       = matched units / 3,999
```

| Units | Count | Share of the reward |
| --- | --- | --- |
| Scenarios of the 26 legacy themes | 2,160 | 54.0% |
| Scenarios of the media theme | 83 | 2.1% |
| Trading days (44 months of 30-35 days, each crossing the end of March) | 1,413 | 35.3% |
| Client screens opened after a month (8 per month, 343 kept) | 343 | 8.6% |

- Continuous. A unit matches only if every one of its answers matches; a trading day or a
  screen is judged on its own answers, so a wrong day does not cost the month's other days.
- The denominator is fixed. No `run` file, a server that never becomes healthy, one that
  cannot be restarted, or one too slow or stuck to finish within the time limit: the
  scenarios it did not answer count as not matched.
- An evaluation error (verifier not root, privileges cannot be dropped or the drop does not
  hold, scenarios unreadable, an upload the scenarios name is missing) leaves no reward file;
  `metrics.json` has `status: evaluation_error`, and `verifier_error.txt` the traceback. No
  reply from the submitted server can cause one; exhausting the container's memory, disk or
  process table still can (see Remaining work).
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verifier/replay.py`. Tests: `checks/test_backoffice.py` (reference
  1.0; a one-character rounding defect scores between 0 and 1; a crashing or missing server
  scores 0 with the full denominator; tiny fake servers that hang, drip bytes, send a garbage
  health reply, deep or non-JSON answers, or crash in every tenth scenario, which scores 72 of
  80, as deserved; set-id bits are cleared and the drop sets `--no-new-privs`; the deadline
  leaves at least 300 s of the step's limit, 600 s now).

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW (findings 1 and 2 unassessed; 5, 7 and 8 mitigated but
not yet exercised in a container).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read the sealed server's code and copy it | File permissions in the agent image | Inspected by adversarial QA 04 (2026-11-19): as the agent's user, the bytecode, the database and `/proc/<pid>/{mem,environ}` of the sealed server are not readable. Not executed in a container | Server files are owned by user `stockwell`, mode 0700, shipped as bytecode only; the agent runs as `dev`. `/opt/py` holds only public third-party packages, not the server | A way to become root or `stockwell` inside the container. Anyone who can pull the image finds the plain source in the layer that copies it (QA 06 note) | Probe as `dev`: read `/opt/stockwell`, `/proc/<pid>/mem`, ptrace | 🟡 YELLOW / UNASSESSED |
| 2 | Agent harness starts as root and hands the model a root shell | Harness and `[agent] user` on Oddish | Not tested on Oddish | `user = "dev"` in `task.toml` | Depends on each harness honouring it | Short model trial that prints `id` | 🟡 YELLOW / UNASSESSED |
| 3 | Deliver a proxy to the sealed server | Separate verifier image | By design | The verifier image has no reference server and no network | None found | Keep | 🟢 GREEN / LOW |
| 4 | Replay a table of recorded answers, including answers collected for inputs the agent already holds | Private scenarios; what the agent image holds | QA 06 (2026-11-19): the 19 Stockwell test fixtures shipped in `/app/samples` were uploaded byte for byte by the hidden `files` scenarios (267 uploads, 20 more cut short, 21 file answers; 78 scenarios). Fixed. `scripts/scan_uploads.py` reports that leak on the old bundle `c4746eb643c6` and nothing on `2a602a3f17e6` | Scenarios come from a private seed, rotated on 2026-11-19 and kept out of the repository, and vary quantities, customers, dates and order of operations; 82,837 requests in 2,287 scenarios (3,999 units), 44 of them months of trading whose supplier invoices are made for each purchase order. The fixtures no longer ship, and the bundle check fails on any hidden upload, cut-short upload or file answer the agent image holds | A table cannot cover them; the generators' shape could be guessed only in outline. Private media of the media theme reuse the sample names, and a few header-level facts do not depend on the seed (QA 06 note) | Measure a lookup-table submission | 🟢 GREEN / LOW |
| 5 | Submitted server attacks the verifier process or its files | Verifier sandbox | QA 10 (2026-11-19) traced, without running it, a set-user-id binary in `/app/server` that arrives root-owned with its mode kept on Docker and, under the old drop, runs as root and can read `/tests/private`. Fixed | Runs as `nobody` through `setpriv --no-new-privs`; set-id bits cleared from the delivered files first; the drop is checked in `/proc/self/status` at every evaluation; `/tests` and the output directory are mode 0700; the server's user is killed at each restart and at the end | Not exercised in a container. Exhausting the container's memory, disk or process table (QA 10 should-fix) | Red-team the verifier image in a container | 🟡 YELLOW / MEDIUM |
| 6 | Tamper with reward files | Separate verifier container | By design | Verifier starts fresh with only `/app/server`; the server can no longer become root (5) | None found | Keep | 🟢 GREEN / LOW |
| 7 | Replace `/app/server` with a link to `/opt/stockwell/app`, so that Harbor's collector, running as root, copies the sealed bytecode into the trial artifacts and the verifier. Leaks the private reference; no reward (the copy has no `run`) | Ownership of `/app` in the agent image; Harbor's collector | QA 04 (2026-11-19), traced in Harbor 0.20: `tar -czf ... -C /app/server .` as root follows the top-level link, and GNU tar stores links below it as links. Not executed | `/app` is root's with the sticky bit and `/app/server` root's and writable by everyone: the agent creates and changes anything inside it but cannot remove, rename or replace it. A link inside it is archived as a link and dangles in the verifier | A provider whose collector follows links below the top (Harbor 0.20's `tar` and `docker compose cp` do not); not executed in a container | In the next container run, as `dev`: `rm -rf /app/server` and `mv /app/server x` fail, and an inner link is archived as a link | 🟡 YELLOW / MEDIUM |
| 8 | Submission makes the evaluation end without a reward (hangs past the step limit, a reply that is not HTTP, deep JSON, a crash storm); a run that errors may also be retried, which gives a bad run a second draw | Verifier | QA 10 E1, E2, E4 and E6 (2026-11-19), rerun after the fix; checks with fake servers that hang, drip, send garbage or crash | 3,000 s deadline and 30 s of wall clock per request; any reply is a not-healthy server or an answer that matches nothing; no restart cap, and one solo retry for a scenario that got no answer; the reward is written before the diagnostics | Exhausting memory, disk or processes can still end the evaluation (QA 10 should-fix) | Run the server under `prlimit` and `choom`, bound its log | 🟡 YELLOW / MEDIUM |
| 9 | Pass the durable-state units without durable state: keep a workspace in a process that outlives the planned stop, or in memory written out only on SIGTERM | Verifier's planned restarts | Checks with fake servers that keep state on disk, in memory, or save only on SIGTERM: they pass both restarts, neither, and only SIGTERM's (2026-11-19). Not exercised in a container | A planned stop kills the server's whole process group and, sandboxed, every process of its user before the start; SIGKILL comes straight after an answered write, with no chance to save | None found: state kept in `/tmp` instead of `DATA_DIR` also survives, but it is durable state all the same | Run the restart checks in a container, sandboxed | 🟡 YELLOW / MEDIUM |

## Validation

| Check | Revision | Result |
| --- | --- | --- |
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
python3 scripts/make_media.py --out experiment/media/visible --seed 20261121           # the samples
python3 scripts/trading_media.py --examples experiment/media/visible --seed 20261121    # supplier invoices and delivery files among them
python3 scripts/make_media.py --out experiment/media/private --seed "$(python3 scripts/seeds.py media)"
python3 scripts/record_scenarios.py --count 2160 --runs 44 --term 6 --kill 3 --screens 8   # seeds from experiment/seeds.json
python scripts/package_step.py            # experiment/dist/bundles/<hash>/<task slug>/
python scripts/package_step.py --flat     # same content without the steps wrapper
python scripts/scan_uploads.py experiment/dist/bundles/<hash>/<task slug>   # hidden uploads or file answers the agent image also holds
```

## Remaining work

- Upload bundle `0ffbed822f74` as a new version and run its baselines (reference twice, no-op twice):
  the verifier, the corpus, the samples, the agent image and the instruction all changed. Model
  trials wait for the owner.
- The privilege check now fails closed when `/proc/self/status` has no `NoNewPrivs` line; a
  provider whose kernel or sandbox (some gVisor versions) does not report it would end every
  evaluation with an evaluation error. The baselines on each provider will show it.
- QA 10 should-fixes still open: a JSON document that describes a file matches the file (E7);
  memory, disk and process exhaustion of the shared container; a missing artifact directory
  scores 0.0 instead of an evaluation error; private media are not checked against the set the
  answers were recorded with; unpinned base images.
- QA 06 notes: private media of the media theme reuse the sample names; the image layer that
  copies the sealed server holds its plain source (a multi-stage build would not).
- QA 01 R3 and R4 (a data takeover, a change request) remain the candidates for further steps.
- Exercise findings 5, 7, 8 and 9 in a container; probe findings 1 and 2.
- Record the first model trial and run more.
- `harbor check` and ratings.
- Decide how to reach the workload target: more modules or follow-up steps.
