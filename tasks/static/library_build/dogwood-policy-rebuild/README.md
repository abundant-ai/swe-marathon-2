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

**Status (2026-11-27, Phase B done, GO):**
- The task image builds the release from pinned sources, and the grading image records gold from
  the same build.
- The grader, the first case set (3,758 cases, private) and the oracle exist. Locally the oracle
  scores 1.0, the empty submission 0 and the M-dedup source 0.83.
- See the development log and `notes/PHASE-B-REPORT.md` for what has been run.
- No trial has run.
- The guide is not in the working machine yet: its trim and scrub are the next work item.
- V's near-miss pairs, wider K and F cases, the stub zoo and the coverage inventory are still to
  do.

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
- **Weakest point:** a clean-room rule for an Apache-2.0 project is a business choice, not a legal
  necessity. Goose's accepted brief uses the same framing.

**Difficulty.**
- **Size:** about 23-30k in-scope code lines upstream (two heuristics) and an estimated 250-400
  documented features.
- **The hard part:** correct decisions need a relational evaluator for past-time first-order
  temporal logic with deduplicating aggregation and key-local slicing. Validation has dozens of
  stated rules.
- **Two families cut against a model's prior,** both stated in the guide:
  - aggregation over a deduplicated projection (B);
  - `previous` and `since` read over the deciding principal's own events (K).
- **Sizing:** frontier at about 0.6 or less, mid-tier 0.1-0.4 (`notes/DESIGN.md` section 3a).

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
- Delivered files that copy Dogwood's own source are listed in the metrics
  (`dogwood_source_files`) for the clean-room review; the list does not change the score.
- An evaluation error writes no reward. Nothing a submission prints, builds or leaves running
  causes one: those fail its own cases.

| Family | Weight |
| --- | --- |
| R core replay | 0.20 |
| B-dedup aggregation, deduplication | 0.17 |
| B-scope aggregation, decision point | 0.05 |
| K key-local slicing, pins, mirror rule | 0.15 |
| V validate accept/reject and exit status | 0.13 |
| V-msg validate finding text (JSON) | 0.05 |
| L lowered Cedar and augmented schema | 0.10 |
| M macros | 0.05 |
| P providers | 0.05 |
| X `explain` | 0.03 |
| F `format`, `check-parse`, `schema` | 0.02 |

## Verification coverage

**The inventory** (`checks/features.json`) gives every documented feature and stated restriction
of the shipped guide an id: 417 ids (256 features, 151 restrictions, 10 out of scope). Each id
records the guide sentence it comes from, its family, the routes that observe it, and detectors
for the inputs that exercise it.

**The rule:**
- each feature needs at least 3 cases that fail when it is missing;
- each restriction needs at least 1 case that shows it enforced;
- out-of-scope ids need no case.

`checks/coverage.py` counts three kinds of evidence:
- a mutant kill: a patched release build answers the case in a way the release never did;
- a refusal of a breaking input, shown by its message or its exit status;
- a successful answer on inputs that use the feature.

The version flag is the only id that needs fewer than 3 cases (it needs 2: one per spelling),
and its reason is recorded.

**Where the cases come from:**
- upstream's own bundle generator, run with a kept private seed;
- 96 restriction templates and 29 feature templates (`scripts/restrictions.py`), each breaking
  or using one stated rule, two instances each;
- K's eight dual shapes and the B pairs (`scripts/pairs.py`);
- the command-line cases.

The kill matrix is 33 one-change mutants of the release source (`checks/mutants/`).

**Result on the final case set:** RESULT-PENDING.

## Hackability assessment

Assessed on the local arm64 images (Phase B, then Phase C on the final case set). Everything is
re-checked on the platform's image before upload.

| Boundary | Attack | Mitigation | Severity |
| --- | --- | --- | --- |
| The installed build | Read, copy, trace, preload or dump the binary | Mode 2711, `root:dogwood-run`: unreadable, and setgid makes the loader ignore `LD_PRELOAD` and the process non-dumpable. A multi-stage image holds no source or cargo cache. Probe as `dev`: reading, copying, `dd`, `/proc/<pid>/{exe,mem,maps}` and `PTRACE_ATTACH` are refused; `LD_PRELOAD` is ignored while the same library runs in `/bin/true`; a traced read of its memory fails with `EIO`; no core dump is written; there is no `sudo`; no `dogwood-*` crate or source is on disk | GREEN-PENDING |
| Wrapper | Ship a submission that calls `dogwood` | The grading image holds no build (no file named `dogwood*`, no `dogwood-*` crate); the `wrapper` stub scores 0 | GREEN-PENDING |
| Stubs | Credit from help text, constant exit codes, all-DENY streams, `cat` as `format`, no-op bodies | Selection keeps no unit a trivial program passes, and pairs every weak case with one whose answer is its own. The zoo (23 projects, `checks/stubs.py`) is built and graded by the real grader | GREEN-PENDING |
| Lookup tables | Hard-code the shipped examples' outputs | The `lookup` stub scores 0; the leak scan finds no hidden case that equals or near-copies a shipped example or a public upstream case | GREEN-PENDING |
| Reward forging | The build (`builder`) or the program (`nobody`) writes `reward.json` or `reward.txt` into the output folder, which the platform may make writable by every user, or plants links there to redirect the grader's writes | The grader ends every process of both users first, removes whatever stands under its output names (files, links, folders), then creates each output fresh with `O_EXCL` and `O_NOFOLLOW` relative to the folder's descriptor, and writes the reward last; an evaluation error also clears the reward files. The `forge` stub tries all of this against a world-writable output folder | GREEN-PENDING |
| Grader files and gold | Read the private cases or the grader | `/tests` is root-only (0700); the build runs as `builder`, the cases as `nobody`; the `buildrs` stub tries to read gold and the grader | GREEN-PENDING |
| Build-time code | The submission's `build.rs` or proc macros run while the grader builds it: loop, read gold, leave processes, point the program path elsewhere | The build runs as `builder` with no network and no read access to gold or the grader, under 20 minutes and a 16 MB log cap; afterwards every `builder` process is ended and its files removed; the program must be a regular file inside the build folder, copied from an `O_NOFOLLOW` descriptor | GREEN-PENDING |
| Hostile programs and output | Hang, flood, fork-bomb, daemonise, print what crashes the comparison, or deliver a program that cannot start | Each run is bounded (1 s, 2 GB, 512 processes, 256 MB files, 8 MB of output); every process of `nobody` is ended after each run, the grader adopts orphans, and a run's leftover files are removed. Comparison never raises, and an unstartable program fails its own cases. The `hang`, `flood`, `forkbomb`, `daemon`, `garbage` and `badexec` stubs score 0 with no evaluation error | GREEN-PENDING |
| Shared state between runs | Leave state in `/tmp` for a later run | Removed after every run (the runs-share-nothing probe on the grader's own runner). The Rust image leaves `/usr/local/cargo` and `/usr/local/rustup` writable by every user; nothing there reaches an answer or the score | GREEN-PENDING |
| Copying upstream source | Paste Dogwood's own source into the project | The clean-room rule is the requester's; the grader lists delivered files whose digest (exact, or with whitespace removed) matches a Dogwood source file, for review. It does not change the score, so the trajectory audit is the remaining check | YELLOW (report-only by design) |

Highest unresolved severity: YELLOW (the clean-room review is a report, not a score).

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
