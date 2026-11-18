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
  instruction no longer describes the session lifecycle (it keeps the 48 hours and asks that
  `/app/server/run` keep working); `task.toml` and the two Dockerfiles keep no authoring
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
  (FastAPI, Pydantic, SQLAlchemy; 232 endpoints, about 16,000 lines) with a React and
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
| Private inputs | `steps/01-rebuild-server/tests/private/scenarios.json`, Git-ignored, produced by `scripts/record_scenarios.py --count 2160 --trading 240 --seed 20261120`. |
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
  Differences: a stateful multi-user service instead of a filter program, so behaviour
  depends on sequences of requests; and the target is original, where MirrorCode's own
  report notes its open-source targets are probably in pre-training.
- SWE-Marathon v1 product clones (`slack-clone`, `stripe-clone`, `mastodon-clone`, `s3-clone`,
  `excel-clone`): build a product from a written specification of a well-known service.
  Here there is no written specification and no public product to remember.
- Tasks in this repository: no overlap with `knowledge-work-assistant`, `titans-training`,
  `battle-royale` or `sympy-restoration`.
- Deep SWE, Frontier SWE, Multi-Step SWE: not compared. Unverified.

### Verifiability

Every answer of the reference is a pure function of the requests made in a workspace: ids
are sequential, the calendar is simulated, and nothing reads the wall clock. Recorded
answers can therefore be compared exactly. Partial progress is the share of scenarios that
match in full. Uncertainty: a scenario fails on its first difference, so one wrong rule in
a common path hides later correct behaviour; the per-theme breakdown in `metrics.json`
shows where.

### Realism

Replacing a system whose vendor has gone, with only a running copy and its client, is real
work. Contrived parts: the application is small compared with a real back office, and the
sealed server gives unlimited fresh copies of the demo company, which a production system
would not.

### Difficulty

Expected sources, not yet measured by any trial:

- Rules that interact: a line's price depends on price lists, quantity breaks, tier, and
  promotions that may or may not stack; the invoice then prorates and re-taxes it.
- State and time: allocation changes when stock arrives or expires, fees accrue as the
  calendar moves, holds appear and lift.
- Exactness: messages, field order in lists, error precedence and rounding all count.
- Breadth of the surface: 232 endpoints, 5 roles, 82 tables behind them; files, PDFs and
  barcodes generated byte for byte.

### Initial feasibility

Solved by construction: the reference source passes every scenario. For an agent the rules
are all observable through the API and the client; whether 48 hours suffice is unknown.

## Workload

The budget is 48 hours, run as five sessions of 9.6 hours because Oddish ends an attempt
after 12 hours. v2 asks for about five days. The reference server is about 16,000 lines of
Python, the size of MirrorCode's largest target, with a 20,000-line client to read. Follow-up
steps remain options: a change request on the rebuilt server, a data migration.

## Verification

The verifier runs in a separate image that holds the private scenarios and no copy of the
reference server.

1. `/app/server` arrives as the declared artifact. `/app/server/run` is started as user
   `nobody` with `PORT` and `DATA_DIR` set, in its own process group, with no network.
2. The server has 60 seconds to answer `GET /api/health`.
3. Each scenario creates a workspace and replays its requests on one connection, eight
   scenarios at a time. An answer matches when the status code is equal and the JSON body is
   equal after the workspace id is replaced by a placeholder.
4. A request with no answer within 15 seconds ends that scenario attempt. The server is
   restarted only if its health check then fails (at most 25 times), and the scenario is
   tried again, up to three attempts, each in a new workspace.

### Reward formula

```
reward = scenarios_matched / 2400
```

- Continuous. A scenario matches only if every one of its answers matches.
- The denominator is fixed. No `run` file, a server that never becomes healthy, or one that
  cannot be restarted: the unanswered scenarios count as not matched.
- An evaluation error (verifier not root, privileges cannot be dropped, scenarios
  unreadable) leaves no reward file; `metrics.json` has `status: evaluation_error`.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verifier/replay.py`. Tests: `checks/test_backoffice.py` (reference
  1.0; a one-character rounding defect scores between 0 and 1; a crashing or missing server
  scores 0 with the full denominator).

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 2, 5).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read the sealed server's code and copy it | File permissions in the agent image | Not attacked | Server files are owned by user `stockwell`, mode 0700, shipped as bytecode only; the agent runs as `candidate`. `/opt/py` holds only public third-party packages, not the server | A way to become root or `stockwell` inside the container | Probe as `candidate`: read `/opt/stockwell`, `/proc/<pid>/mem`, ptrace | 🟡 YELLOW / UNASSESSED |
| 2 | Agent harness starts as root and hands the model a root shell | Harness and `[agent] user` on Oddish | Not tested on Oddish | `user = "candidate"` in `task.toml` | Depends on each harness honouring it | Short model trial that prints `id` | 🟡 YELLOW / UNASSESSED |
| 3 | Deliver a proxy to the sealed server | Separate verifier image | By design | The verifier image has no reference server and no network | None found | Keep | 🟢 GREEN / LOW |
| 4 | Replay a table of recorded answers | Private scenarios | By design | Scenarios come from a private seed and vary quantities, customers, dates and order of operations; 60,929 requests in 2,400 scenarios | A table cannot cover them; the generator's shape could be guessed only in outline | Measure a lookup-table submission | 🟢 GREEN / LOW |
| 5 | Submitted server attacks the verifier process or its files | Verifier sandbox | Not attacked | Submission runs as `nobody`; `/tests` and the output directory are mode 0700; process group killed at the end | Unknown | Red-team the verifier image | 🟡 YELLOW / UNASSESSED |
| 6 | Tamper with reward files | Separate verifier container | By design | Verifier starts fresh with only `/app/server` | None found | Keep | 🟢 GREEN / LOW |

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (7 tests) | re-cut with leak fixes, 2026-11-18 | pass; Oddish preflight passes |
| Bundle | re-cut with leak fixes: `a691f329ea71`, 574 files | built twice with the same hash |
| `checks/` (6 tests) | re-cut, pinned to Stockwell 722a647, 2026-11-18 | pass |
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
python scripts/record_scenarios.py --count 2160 --trading 240 --seed 20261120
python scripts/package_step.py            # experiment/dist/bundles/<hash>/<task slug>/
python scripts/package_step.py --flat     # same content without the steps wrapper
```

## Remaining work

- Read the platform's source audit of version 2 and fix what it finds. Model trials wait for the owner.
- Record the first model trial and run more.
- Probe findings 1, 2 and 5.
- `harbor check` and ratings.
- Decide how to reach the workload target: more modules or follow-up steps.
