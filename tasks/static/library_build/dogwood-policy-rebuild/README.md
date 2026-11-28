# Dogwood policy tool rebuild (single step)

Rebuild `dogwood` 1.2.0, the command-line tool of Dogwood, clean-room. Dogwood is the temporal
agent-policy language that AWS published in August 2026 (Apache-2.0, built on Cedar). Bedrock
AgentCore writes its temporal policies in it.

**What the agent gets and delivers.** In one session it works from the trimmed guide and an
execute-only build it can run but not read, and cannot read Dogwood's source. It delivers
`format`, `check-parse`, `validate`, `lower`, `replay`, `explain` and `schema`, with their human
and JSON output.

**Why single step.** The Phase A panel chose a two-step chain (1.1.2, then the 1.2.0 upgrade). On
2026-11-26 the owner set multi-turn aside ("we dont have to promote multi-turn"), so the task is
the single-step fallback that plan kept: the 1.2.0 rebuild, graded by the same verifier and
families. The two-step plan stays in `notes/` as history.

**Status (2026-11-27, Phase C done: ready for the independent QA):**
- The working machine ships the trimmed guide in `/app/docs`. The brief states the run conditions
  and no session budget.
- The private case set has 4,282 cases (2,304 units). Every documented feature and stated
  restriction has its cases, and all 33 mutants are killed.
- Locally: the oracle scores 1.0 twice and the empty submission 0 twice; the stub zoo, the
  probes and the determinism, leak and wording checks pass. The 12-item gate table is in
  `notes/PHASE-C-REPORT.md`.
- No trial has run, and nothing has been uploaded. The platform's oracle and nop runs come with the
  first upload.

The rest of this README and the `notes/` folder are author notes. Nothing here is shipped to the
agent.

| Document | What it holds |
| --- | --- |
| [instruction.md](instruction.md) | The brief |
| [NOTICE](NOTICE) | The Dogwood (and Cedar) material this folder carries, and its licence |
| [notes/DESIGN.md](notes/DESIGN.md) | What the agent gets and delivers, the hidden reference, grading families and weights, stub filters, determinism, score bands, effort, risks |
| [notes/CLAIMS.md](notes/CLAIMS.md) | Every claim used to justify the task, re-checked against primary evidence; the failure sentence and its proof plan |
| [notes/QA-PLAN.md](notes/QA-PLAN.md) | The 12-item pre-upload gate, coverage inventory, stub zoo, wording sweep, QA lenses and post-run checks |
| [notes/SPIKE-PLAN.md](notes/SPIKE-PLAN.md) | The spike and the exact download list |
| [notes/PHASE-A-REPORT.md](notes/PHASE-A-REPORT.md), [notes/PHASE-B-REPORT.md](notes/PHASE-B-REPORT.md), [notes/PHASE-C-REPORT.md](notes/PHASE-C-REPORT.md) | Phase summaries; the Phase C report holds the 12-item gate table |
| [notes/STEPS.md](notes/STEPS.md), [notes/parked-two-step/](notes/parked-two-step/) | The two-step plan and its briefs, parked by the owner on 2026-11-26 |

**Where things are:**
- `environment/` builds the working machine.
- `tests/` is the separate grading image: the grader, and the private cases in Git-ignored
  `tests/private/`.
- `solution/solve.sh` delivers upstream's own 1.2.0 source. It is staged into Git-ignored
  `solution/upstream/` by `scripts/stage_oracle.py`.
- `scripts/` holds the development tools, and `checks/` the gate checks, the inventory, the
  mutants and the stub zoo. Neither is shipped.

## Task design dimensions

**Novelty.**
- **Argument:** no public benchmark we found rebuilds a policy engine or a temporal monitor. The
  only internal neighbour shares the topic, not the task shape: Forge's `cedar-typeof-soundness`, a
  Lean proof-hole task about Cedar.
- **Same family as ours:** the closest tasks in this repository are the black-box language rebuilds
  (Goose, BasedPL). This one adds stateful decision streams over event traces and validation
  verdicts.
- **Unverified:** benchmarks outside the lists in `notes/CLAIMS.md` were not searched.

**Verifiability.**
- **Method:** every output is deterministic text or JSON from a pinned, frozen build:
  - replay verdict streams;
  - `validate` reports and exit codes;
  - lowered Cedar;
  - `explain`, `format` and `schema`.
  A separate verifier with no reference compares the submission's outputs with recorded gold on
  generated cases.
- **Determinism exceptions:** two outputs vary in the reference and are normalised: replay's rule
  list comes from a hash set, and human-mode fatal errors go to standard error.
- **Measured in Phase B:** 3,758 cases × 3 runs plus a perturbed fourth all give one answer after
  normalisation. The 25 cases whose bytes moved differ only in rule-list order; on multi-permit
  bundles that order changes on every run.

**Realism.**
- **Who needs it:** teams that gate agents' tool calls with Dogwood. Upstream calls its interpreter
  a reference "NOT intended for production use", so such teams need an implementation they own.
- **Weakest point:** an Apache-2.0 tool could simply be forked. The brief's reason is provenance:
  the requester's security review lets only code it wrote into the authorization path, and its
  reviewers want every line accounted for, so the authors work from the guide and the running
  build only, and the build is execute-only for the same reason (fix round 1, QA 01 and 03).
- **Inputs:** the private inputs are generated conformance inputs, not real agent traffic: 61% come
  from upstream's generator (grammar-shaped, a small vocabulary), the rest from the task's own
  templates in a Ledger world. They test structure, not names, and carry no information about
  verdicts (QA 02).

**Difficulty.**
- **Size:** about 23-30k in-scope code lines upstream (two heuristics) and an estimated 250-400
  documented features.
- **The hard part:** correct decisions need a relational evaluator for past-time first-order
  temporal logic with deduplicating aggregation and key-local slicing. Validation has dozens of
  stated rules.
- **Two families cut against a model's prior,** both stated in the guide:
  - aggregation over a deduplicated projection (B);
  - `previous` and `since` read over the deciding principal's own events (K).
- **Sizing:** the target is frontier at about 0.6 or less and mid-tier 0.1-0.4. The 2026-11-28
  panel had QA 17's F2 and F5 applied before the first run:
  - more documented combinations per B rule and K shape;
  - R units at window edges, the `since` boundary and `previous`.
- **Re-size** (QA 17's model; `notes/DESIGN.md` section 3a, `notes/FIX1-REPORT.md` section 4): the
  frontier at a median of about 0.58 (0.40-0.73), a strong session at about 0.71, mid-tier at
  about 0.24.
- **Pre-registered response** (DESIGN section 6), on the median of the first three accepted
  Opus-class sessions:
  - 0.60 or less: accept;
  - 0.60-0.70: report to the owner;
  - above 0.70: report to the owner, and re-version only with his word (an accepted version is
    frozen);
  - below 0.30: check fairness.

  A first session at 0.80 or more triggers at once.
- **Horizon:** a strong engineer new to Dogwood needs about 39-50 working days to a solid core and
  65-95 to byte-exact output (QA 14). That is above the owner's 2-7 day target. The 2026-11-28
  owner-questions panel kept the scope, with the horizon stated here. An agent needs about 7-12 hours and 2,000-4,500 steps, so
  the 9.6-hour session may bind (QA 15): a run that ends at the cap with a project that does not
  build is a harness loss. The evaluator (R, B, K, P, M: 0.67 of the weight) is the critical path;
  validation, lowering and the command surface can be farmed out once the parser exists (QA 16).

**Initial feasibility.**
- **Plausible path:** parse with pest from the guide's grammar, evaluate Cedar parts with the
  vendored `cedar-policy`, and replay with a relational, key-local monitor.
- **Shown in Phase B:** the release builds offline from its published lock (for the image's glibc
  target; a static musl build fails Cedar evaluations at random) and reproduces every shipped
  example. Upstream's own source, built by the grader as a submission, scores 1.0 on all 3,758
  cases (an 83 s build, 101 s in all).

## Reward

`S = Σ_f w_f · g_f`, where:
- `g_f = max(0, (pass_f − b_f) / (1 − b_f))`;
- `pass_f` is the family's pass fraction over units (a single case, or a pair that counts only
  when both members pass);
- `b_f` is the best stub's pass fraction in that family. Selection keeps no unit a stub passes,
  so `b_f` is 0 for every family and no baseline file ships.

**What else decides the score:**
- The grading image holds no `dogwood` build, so a submission that calls one fails its cases.
- The grader's files are out of reach of the build (run as `builder`) and of the runs (run as
  `nobody`).
- A delivery holding Dogwood's own source files, or its 1.2.0 build, scores 0, and the metrics
  list the files (`dogwood_source_files`). The oracle's files carry one added comment line each.
- A delivery that did not arrive as the hand-off listed it is a lost run (an evaluation error, no
  reward), never a 0. Nothing a submission prints, builds or leaves running causes an evaluation
  error: those fail its own cases (the hostile stubs check it).

| Family | Weight |
| --- | --- |
| R core replay | 0.20 |
| B-dedup aggregation, deduplication | 0.17 |
| B-scope aggregation, decision point | 0.05 |
| K key-local slicing, pins, mirror rule | 0.15 |
| V validate report: exit status and every finding line | 0.13 |
| V-msg validate finding text (JSON) | 0.05 |
| L lowered Cedar and augmented schema | 0.10 |
| M macros | 0.05 |
| P providers | 0.05 |
| X `explain` | 0.03 |
| F `format`, `check-parse`, `schema` | 0.02 |

## Verification coverage

**The inventory** (`checks/features.json`) gives every documented feature and stated restriction
of the shipped guide an id: 459 ids (281 features, 168 restrictions, 10 out of scope). Each id
records the guide sentence it comes from, its family, the routes that observe it, and detectors
for the inputs that exercise it.

**The rule:**
- each feature needs at least 3 cases that fail when it is missing;
- each restriction needs at least 1 case that shows it enforced;
- out-of-scope ids need no case, and any case that uses one is an error.

`checks/coverage.py` counts three kinds of evidence:
- a mutant kill: a patched release build answers the case in a way the release never did;
- a refusal of a breaking input, shown by its message or its exit status;
- a successful answer on inputs that use the feature.

It also checks the other direction (fix round 1):
- every graded case is claimed by a stated id, with no catch-all detector;
- every error, warning and fail-closed message in a graded answer holds a stated id's message;
- every graded JSON key is named in the guide.

Two ids need fewer than 3 cases, with their reasons recorded: the version flag (one per spelling)
and signed timestamps.

**Where the cases come from:**
- upstream's own bundle generator, run with a kept private seed;
- 104 restriction templates and 42 feature templates (`scripts/restrictions.py`), each breaking
  or using one stated rule, two instances each;
- history anchors for R, P and M, whose streams need the history (`scripts/restrictions.py`);
- the B pairs, now 9 B-dedup and 8 B-scope templates, and K's eight dual shapes, two templates
  each (`scripts/pairs.py`, `scripts/combos.py`);
- R's window-edge, `since`-boundary and `previous` templates (`scripts/combos.py`);
- standard input for every command, and the command-line cases (`scripts/make_cases.py`).

Each combination template of `scripts/combos.py` records the verdicts the guide's sentences
give. `checks/combos_check.py` finds the release build agreeing on all 306 of them. Selection
(`scripts/select_cases.py`) keeps no unit that one trivial program passes, an engine with no
history included (section 4 of `notes/DESIGN.md`). The 40 candidates that read only public files
are left out.

The kill matrix is 33 one-change mutants of the release source (`checks/mutants/`).

**Result on the final case set** (4,662 cases in 2,321 units over 1,508 bundles): 0 gaps.
- 253 features are evidenced by use, 157 restrictions by refusals, and 37 ids by mutant kills.
- 2 restrictions are unchecked, with their reasons recorded: the out-of-contract timestamp rule,
  and a failure the built-in engine cannot reach.
- The 10 out-of-scope ids have no cases.
- Every id's quote is in the shipped guide. Every case is claimed, every message named, and every
  JSON key documented.
- All 33 mutants are killed. Window edges (`checks/window_edges.py`, QA 02): every K trace ends
  past its window, and every generated temporal bundle left holds a decision at a window's edge.

## Hackability assessment

Assessed on the local arm64 images (Phase B, Phase C, then fix round 1 through the delivery
path; the results are in `notes/PHASE-C-REPORT.md` section 11 and `notes/FIX1-REPORT.md`).
Everything is re-checked on the platform's image before upload.

| Boundary | Attack | Mitigation | Severity |
| --- | --- | --- | --- |
| The installed build | Read, copy, trace, preload or dump the binary | Mode 2711, `root:dogwood-run`: unreadable and non-dumpable, and linked statically (fix round 1), so no loader runs a preload library even on a self-traced exec that drops the setgid bit. `checks/protection_probe.py` tries every route as `dev` and fails closed: read, `/proc/<pid>/{exe,mem,maps}`, `PTRACE_ATTACH`, a self-traced exec read at the stack pointer, `LD_PRELOAD` on a normal and a traced exec, a core dump. A hard link to the build inside the delivery is removed by the hand-off, and a delivered copy of it scores 0 | 🟢 GREEN (local; gVisor on the first platform run) |
| Root's PATH | Plant `tar`, `su` or `setpriv` where root finds them by name: Harbor packs the grader's output folder, the logs and the project with `tar` as root, and runs the collect hook through `su` | Both images close what the Rust image leaves writable by everyone on root's PATH (`/usr/local/cargo`, its `bin` directory and the `rustup` program its entries link to), and each image build fails if any directory on root's PATH, anything in one, or a parent is writable by another user; the grader re-checks at start. The `hostile-build`, `hostile-run` and `devplant` checks plant in every PATH directory, and Harbor's own `tar` is run after grading: no planted marker | 🟢 GREEN (local) |
| Wrapper | Ship a submission that calls `dogwood`, or embeds it | The grading image holds no build (no file named `dogwood*`, no `dogwood-*` crate); the `wrapper` stub scores 0; root can no longer be reached to copy the build out (previous row) | 🟢 GREEN (local) |
| Stubs | Credit from help text, constant exit codes, all-DENY or last-ALLOW streams, an engine with no history, `cat` as `format`, no-op bodies | Selection keeps no unit that one trivial program passes whole: each case carries the set of programs that pass it (`empty`, `table`, `cli-shell`, `uniform`, `last-allow`, two history-free readings replayed by the release build, `cat`). The zoo (`checks/stubs.py`), a Cedar-only history-free engine included, is graded through the delivery path | 🟢 GREEN (local) |
| Lookup tables | Hard-code the shipped examples' outputs | The `lookup` stub scores 0; the leak scan matches any mix of visible files and guide blocks and finds no hidden case reading only visible inputs | 🟢 GREEN (local) |
| Reward forging | The build (`builder`) or the program (`nobody`) writes `reward.json` or `reward.txt` into the output folder (world-writable on the platform), plants links there, or leaves a process (one whose first thread has exited included) to write after the grader | Before anything of the submission runs, the grader makes the folder root's and 0755 and never reopens it. Before writing, it stops and kills every task of both users from root and by uid across `/proc/*/task` in every state, checks none is left (else an evaluation error), removes what they left anywhere (System V objects included), removes whatever stands under its output names, and creates each output fresh with `O_EXCL` and `O_NOFOLLOW`, the reward last. The `forge`, `hostile-build` and `hostile-run` stubs try all of it against a world-writable folder; a grading killed mid-run leaves no reward | 🟢 GREEN (local) |
| Grader files and gold | Read the private cases or the grader | `/tests` is root-only (0700); the build runs as `builder`, the cases as `nobody`, with no supplementary groups; standard input is fed from the private store, never opened in a run's folder | 🟢 GREEN (local) |
| Build-time code | The submission's `build.rs` or proc macros loop, read gold, leave processes, fill the disk or memory, fork without end, point the program path elsewhere | As `builder` with no network, 20 minutes, a 16 MB log cap, 4,096 processes, 4 GB files, no core dumps, and the kernel's first choice on memory pressure (the grader is its last). Afterwards every task of `builder` is ended and its files and System V objects removed; the program must be a regular file inside the build folder, copied from an `O_NOFOLLOW` descriptor | 🟢 GREEN (local) |
| Hostile programs and output | Hang, flood, fork-bomb, daemonise, rename a process to bytes that are not UTF-8, nest 2,000 directories, print what crashes the comparison, or deliver a program that cannot start | Each run is bounded (1 s, 2 GB, 512 processes, 256 MB files, 8 MB of output); /proc is read as bytes; trees are walked without recursion and removed with GNU `rm`; comparison never raises; an unstartable program fails its own cases. The `hang`, `flood`, `forkbomb`, `daemon`, `garbage`, `badexec` and `hostile-run` stubs score 0 with no evaluation error | 🟢 GREEN (local) |
| Shared state between runs | Leave files, processes or shared memory for a later run | After every run: every task of `nobody` ended, its files in every shared directory and its System V objects removed, the run's folder removed; at the end the grader searches the whole filesystem for anything either user owns | 🟢 GREEN (local) |
| The delivery transfer | One FIFO, socket, device, or absolute or outward link anywhere in the project makes Harbor's `extractall(filter="data")` stop, and the rest is lost | The hand-off applies the brief's copy rules before the transfer and writes a manifest; the grader checks the arrived tree against it, and a mismatch or a missing manifest is a lost run, never a 0. Tested through a copy of Harbor's own transfer (`work/spike/deliver.py`) with clutter, with no hand-off and with a pipe added after it | 🟢 GREEN (local) |
| The egress window | A process left running fetches Dogwood's crates once the turn ends, before collection | `wait-uplink` (root, from the setup hooks) stops and ends `dev` as soon as a public host answers; the hand-off records the processes, egress and every entry's times; entries changed after the end of the work are listed in the metrics for the per-trial audit; a verbatim drop-in scores 0. A modified drop-in fetched in the remaining fraction of a second is not refused: the audit is the last check | 🟡 YELLOW (recorded and bounded; audit decides) |
| Provider-side web tools | A harness web tool reads docs.rs, which serves Dogwood's source, during the turn | Every Dogwood run config lists `WebSearch` and `WebFetch` in `disallowed_tools` (QA-PLAN section 6); codex keeps web search disabled | 🟡 YELLOW (run-config discipline) |
| Evaluation cues | `ps` shows the harness's launcher line; `/logs/verifier` exists in the working machine | The working image has no `ps` (procps is not installed: keep it so). `/logs/verifier` is the platform's and cannot be renamed by the task | 🟢 GREEN (task); platform residue noted |

Highest unresolved severity: 🟡 YELLOW (the egress window is recorded and bounded, not closed; the per-trial audit decides).

## Development log

### 2026-11-26

Phase A, design only. No downloads, builds, runs, Docker or Oddish.
- **Claims re-checked.** I re-checked the research report's and the deep dive's claims against a
  read-only clone of upstream `main` at `c7124710` (v1.2.0 plus CI commits), the GitHub API
  (releases, tags, commits, trees at each tag), crates.io's API, and AWS's AgentCore page. Results
  are in `notes/CLAIMS.md`.
- **Main corrections:**
  - v1.0 is the 2026-09-17 state.
  - `format` and `explain` arrived in 1.1.0.
  - Upstream commits no `Cargo.lock`, so the deep dive's `--locked` build cannot work as written.
  - 1.1.2's validation diagnostics are not yet stable in order; 1.2.0 fixed that.
  - The predicted M-dedup band straddled 0.85, so B is weighted 0.25.
- **Panel:** opus, sonnet and haiku unanimously chose the two-step chain (1.1.2, then the 1.2.0
  upgrade) with `final` reward, plain capability families, and step 1 told that newer releases
  follow.
  - Budgets are 21,600 + 12,600 s (2 to 1), with 2,700 s per verifier.
  - Told afterwards that the itemised cost is +8 to +9 person-days rather than +3-5, none changed
    its vote. Opus asked that S's assets (step 2's) be built first.
  - Votes: `harbor-lh` `ops/swe-marathon-v2/decisions/2026-11-26-dogwood-policy-rebuild-steps-*.md`.
- **Drafts:** both step briefs are drafted in the requester's voice. An independent reviewer
  (sonnet) found no must-fix wording. Its four should-fixes are applied:
  - "decision streams" instead of "verdict streams";
  - a reason given for following the build when the guide differs;
  - why the 1.1.2 build stays in step 2;
  - a pointer for the events `replay` does not take into the history.

  The mechanical sweep now finds no banned word in either brief.
- **Next:** the spike in `notes/SPIKE-PLAN.md`, after the owner approves the download list.

### 2026-11-27

Phase B: downloads, the spike and the first build milestone, in local Docker (arm64). Details are
in `notes/PHASE-B-REPORT.md`.
- **Single step.** The owner set multi-turn aside, so the task became the 1.2.0 rebuild in one
  34,560 s session, graded by what was step 2's verifier. The two-step plan is parked in `notes/`.
- **Difficulty.** The owner asked for a single turn that is "difficult enough":
  - K (key-local slicing) is a second counter-intuitive family at 0.15, with its own mutant;
  - aggregation plus `validate` hold 0.40 of the weight;
  - the estimate is frontier near 0.52 and mid-tier near 0.25.
- **Downloads:** D1-D8 and D10 as approved, checksummed in the cache. D9 was not needed.
- **The release build is glibc, not static musl.** Under musl, Cedar's stack check failed
  evaluations at random (36 of 56 shipped replay streams wrong). The glibc build reproduces all 93
  shipped bundles. The binary is mode 2711, as SPIKE-PLAN S2's fallback named.
- **Determinism:** 3,758 cases × 3 runs plus a perturbed fourth give one answer each after
  normalisation. Multi-permit rule lists change order on every run, so they compare as sets.
- **Mutants:** M-dedup 0.83, M-scope 0.95, M-naive 0.78, M-global 0.85, each touching only its own
  family. That holds once family tagging is checked by the mutants: the generator's own cases
  never exercised the two rules, so B-dedup, B-scope and K are made of dual pairs.
- **Stub estimate:** a `validate` that always accepts passes 80% of V, because most generated
  bundles are valid. V needs its near-miss pairs before any QA pass.
- **Milestone:** both images build. The first grading run scored even the oracle 0: the runner
  copied root-only private files that `nobody` could not read. Fixed. After the fix the oracle
  scores 1.0, the empty submission 0 and the M-dedup source 0.83.
- **Protection probe as `dev`:** reading, copying, `/proc/<pid>/{exe,mem,maps}`, `PTRACE_ATTACH`
  and a traced read of the build's memory are refused, and `LD_PRELOAD` is ignored. The grading
  image holds no `dogwood` build.
- **Resources:** 9 heavy jobs (37 minutes), peak memory 3.02 GB per container. Disk peaked at about
  5.5 GB for half an hour (superseded build-cache records), and is 1.81 GB after cleanup by exact
  name and ID.
- **Next:** the docs trim and scrub into `/app/docs`, V near-miss pairs, wider K and F cases, the
  coverage inventory, the stub zoo and the leak scan.

### 2026-11-27 (Phase C)

Phase C took the task to QA-ready, in local Docker (arm64). Details and the 12-item gate table are
in `notes/PHASE-C-REPORT.md`.

- **The agent's material:**
  - The guide ships in `/app/docs`, built from the pinned source by 319 scripted edits.
  - Seven statements that contradicted the build were corrected.
  - The help and version flags are now stated in the guide.
  - An independent review judged the material clean.
  - The brief states the run conditions in the requester's voice, says what our tools read (not
    "the same output as the build"), and gives no session budget.
- **Cases:**
  - The final set is 4,282 cases in 2,304 units over 1,150 bundles, selected so that no unit
    can be passed by a trivial program.
  - V uses near-miss pairs, and K has eight dual shapes.
  - 96 restriction templates and 29 feature templates each break or use one stated rule.
  - The generator seed is kept.
  - Answers that hash order picks were found and removed.
- **Coverage:** 0 gaps over 417 ids, and all 33 mutants are killed. The band check: M-dedup 0.830,
  M-scope 0.950 and M-global 0.900, each moving only its own family.
- **Grader:**
  - Output comparison never raises, and runs share nothing.
  - The grader adopts orphans.
  - The built program is copied from an `O_NOFOLLOW` descriptor.
  - The output folder is closed to the submission's users while they can act, and outputs are
    created fresh, the reward last.
  - Gold is recorded from a file named `dogwood`.
- **Checks:**
  - Determinism: 3 runs plus 1 perturbed run, all 4,282 cases identical after normalisation.
  - Leak scan and wording sweep: clean.
  - Shipped examples: 93 of 93 match.
  - Oracle: 1.0 twice (about 2 minutes). Empty submission: 0 twice.
  - Stubs, probes and stop hook: as the report's gate table lists.
- **Close-out:**
  - The flat bundle's content hash is `30413844e28b…`, the same when packaged twice, and
    `oddish preflight` passes.
  - The private set is backed up to the private store (`dogwood-tests-private-phaseC.bundle`).
- **Next:** the independent 20-pass QA, then the first upload.
