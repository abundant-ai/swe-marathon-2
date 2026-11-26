# Dogwood policy tool rebuild, then the 1.2.0 upgrade (design, Phase A)

Rebuild `dogwood`, the command-line tool of Dogwood, clean-room. Dogwood is the temporal
agent-policy language that AWS published in August 2026 (Apache-2.0, built on Cedar). Bedrock
AgentCore writes its temporal policies in it.

The agent works from the guide and an execute-only build. It cannot read Dogwood's source.
The task runs in two steps in one sandbox:
1. **`01-rebuild`:** rebuild `dogwood` 1.1.2: `format`, `check-parse`, `validate`, `lower`,
   `replay`, `explain` and `schema`, with their human and JSON output.
2. **`02-upgrade`:** carry the same implementation to 1.2.0, whose release notes list 39 breaking
   changes against 1.1.2.

**Status: design only.** Nothing has been built, run or downloaded. No oracle exists, no verifier
exists, and no trial has run. The rest of this README and the `notes/` folder are author notes.
Nothing here is shipped to the agent.

| Document | What it holds |
| --- | --- |
| [notes/DESIGN.md](notes/DESIGN.md) | What the agent gets and delivers, the hidden reference, grading families and weights, stub filters, determinism, score bands, effort, risks |
| [notes/STEPS.md](notes/STEPS.md) | The multi-step plan, each step's acceptance criteria, the reward strategy and timeouts, the single-step fallback |
| [notes/CLAIMS.md](notes/CLAIMS.md) | Every claim used to justify the task, re-checked against primary evidence; the failure sentence and its proof plan |
| [notes/QA-PLAN.md](notes/QA-PLAN.md) | The 12-item pre-upload gate, coverage inventory, stub zoo, wording sweep, QA lenses and post-run checks |
| [notes/SPIKE-PLAN.md](notes/SPIKE-PLAN.md) | The spike that comes before any build, with the exact download list |
| [notes/PHASE-A-REPORT.md](notes/PHASE-A-REPORT.md) | Phase A summary |

The step briefs are [steps/01-rebuild/instruction.md](steps/01-rebuild/instruction.md) and
[steps/02-upgrade/instruction.md](steps/02-upgrade/instruction.md) (drafts).

## Task design dimensions

**Novelty.**
- **Argument:** no public benchmark we found rebuilds a policy engine or a temporal monitor. The
  only internal neighbour shares the topic, not the task shape: Forge's `cedar-typeof-soundness`, a
  Lean proof-hole task about Cedar.
- **Same family as ours:** the closest tasks in this repository are the black-box language rebuilds
  (Goose, BasedPL). This one adds three things:
  - stateful decision streams over event traces;
  - validation verdicts;
  - a version upgrade as a second step.
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
- **Pending:** the determinism recording (`notes/SPIKE-PLAN.md`).

**Realism.**
- **Who needs it:** teams that gate agents' tool calls with Dogwood. Upstream calls its interpreter
  a reference "NOT intended for production use", so such teams need an implementation they own.
- **Why two steps:** a 1.1.2 deployment that must move to 1.2.0 is the upgrade upstream's own
  release notes describe.
- **Weakest point:** a clean-room rule for an Apache-2.0 project is a business choice, not a legal
  necessity. Goose's accepted brief uses the same framing.

**Difficulty.**
- **Size:** about 23-30k in-scope code lines upstream (two heuristics) and an estimated 250-400
  documented features.
- **The hard part:** correct decisions need a relational evaluator for past-time first-order
  temporal logic with deduplicating aggregation and key-local slicing. Validation has dozens of
  stated rules.
- **Step 2:** the agent must find and apply about 45 CLI-visible changes in a codebase it already
  wrote, some of them silent verdict changes.
- **Failure sentence:** see `notes/CLAIMS.md`.

**Initial feasibility.**
- **Plausible path:** parse with pest from the guide's grammar, evaluate Cedar parts with the
  vendored `cedar-policy`, and replay with a relational monitor; then work through the release
  notes in step 2.
- **Unknowns:**
  - whether both releases build offline from a lock we freeze;
  - how stable Cedar's printer and 1.1.2's validator ordering are;
  - whether the case generator yields enough discriminating cases per feature.

## Reward

The trial reward is step 2's score (`multi_step_reward_strategy = "final"`). Step 1 is scored the
same way on 1.1.2 and reported, not counted.

Each step's score is `S = Σ_f w_f · g_f`, where:
- `g_f = max(0, (pass_f − b_f) / (1 − b_f))`;
- `pass_f` is the family's pass fraction over paired cases;
- `b_f` is the best stub's pass fraction in that family.

Integrity failures set the score to 0: the submission calls a `dogwood` build or holds one, or it
tampers with the verifier's files. An evaluation error writes no reward.

| Family | Weight |
| --- | --- |
| R core replay | 0.25 |
| B aggregation semantics (B-dedup 0.18, B-scope 0.07) | 0.25 |
| K key-local pins, mirror rule, decision kinds, custom event schemas | 0.10 |
| V validate accept/reject and exit status | 0.10 |
| V-msg validate finding text (JSON) | 0.05 |
| L lowered Cedar and augmented schema | 0.10 |
| M macros | 0.05 |
| P providers | 0.05 |
| X `explain` | 0.03 |
| F `format`, `check-parse`, `schema` | 0.02 |

These weights are provisional. Case counts, the "same in both versions" and "changed in 1.2.0"
partition, and the anchors each step must hit are in `notes/STEPS.md`.

## Verification coverage

Every documented feature and stated restriction of the shipped guide gets an id in `features.yaml`.
Each id is killed by cases in its own family: at least 3 cases per feature and at least 1 per
restriction, preferring 2. A feature with zero cases blocks upload. The procedure is in
`notes/QA-PLAN.md`.

## Hackability assessment

Nothing is built, so every boundary is unassessed.

| Boundary | Attack | Planned mitigation | Severity |
| --- | --- | --- | --- |
| The installed builds | Read, copy, trace, preload or dump the binary | musl-static, mode 2711, non-dumpable; multi-stage image with no source or cargo cache; protection probe as the agent user | 🟡 YELLOW / UNASSESSED |
| Future step material | Find the 1.2.0 build, docs or crates during step 1 | Root-only staging directory, unlistable; installed only by step 2's `setup.sh` | 🟡 YELLOW / UNASSESSED |
| Wrapper | Ship a submission that calls `dogwood` | The verifier image holds no build; integrity check on the submission | 🟡 YELLOW / UNASSESSED |
| Stubs | Credit from help text, constant exit codes, all-DENY streams, `cat` as `format` | Stub zoo at every build; paired cases; baseline subtraction | 🟡 YELLOW / UNASSESSED |
| Lookup tables | Hard-code the shipped examples' outputs | Hidden cases never equal or near-copy a shipped example (leak scan); paired duals | 🟡 YELLOW / UNASSESSED |
| Verifier and reward | Tamper with grading files or the reward | Separate verifier image; submission runs as an unprivileged user in fresh directories | 🟡 YELLOW / UNASSESSED |
| Build-time code | The submission's `build.rs` or proc macros run while the verifier builds it: read gold, write a reward, leave processes | Build as a dedicated unprivileged user with no network and no read access to gold or the grader; kill its process group after the build | 🟡 YELLOW / UNASSESSED |

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (everything).

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
