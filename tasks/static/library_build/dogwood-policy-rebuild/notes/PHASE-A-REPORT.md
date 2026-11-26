# Phase A report: Dogwood rebuild (2026-11-26)

## Summary

Design only.

**What was not done:** no downloads, no builds or runs of upstream code, no Docker, no Oddish.

**What was read:**
- a read-only clone of upstream `main` that already existed (`c7124710`, the 1.2.0 tag plus five
  non-code commits);
- GitHub API metadata (releases, tags, commits, directory listings, and five doc and source files
  at the `v1.0.2` and `v1.1.2` tags);
- crates.io API metadata;
- AWS's AgentCore "Temporal policies" page.

**Deliverables** (all in `notes/` unless named):

| Deliverable | Where |
| --- | --- |
| Design | [DESIGN.md](DESIGN.md) |
| Multi-step plan, per-step acceptance criteria, panel decision | [STEPS.md](STEPS.md); votes and record in `harbor-lh` `ops/swe-marathon-v2/decisions/2026-11-26-dogwood-policy-rebuild-steps-{BRIEF,opus,sonnet,haiku,DECISION}.md` |
| Claim validity table, failure sentence and proof plan | [CLAIMS.md](CLAIMS.md) |
| QA plan | [QA-PLAN.md](QA-PLAN.md) |
| Spike plan and exact download list | [SPIKE-PLAN.md](SPIKE-PLAN.md) |
| Task skeleton | `README.md` (dev log), `task.toml` (draft), `steps/01-rebuild/` and `steps/02-upgrade/` (draft briefs, empty `tests/` and `solution/` with `.gitignore`), task `.gitignore` |
| Private store | `harbor-lh` `ops/swe-marathon-v2/next-tasks/dogwood-policy-rebuild-private/` (Phase A evidence; Phase B's hidden material will be backed up there as git bundles); the same evidence is in the task's Git-ignored `experiment/phaseA/` |

## 1. Panel decision

**M2a, unanimous (opus, sonnet, haiku).** Step 1 rebuilds `dogwood` 1.1.2; step 2 carries the
same code to 1.2.0.

| Question | Result |
| --- | --- |
| Reward | `final`, unanimous |
| Agent budgets | 21,600 + 12,600 s (2 to 1); 20,700 s for step 1 if measured overheads exceed 2,400 s |
| Verifiers | 2,700 s each |
| Step-2 reward | Plain capability families on 1.2.0 gold, unanimous; the changed-in-1.2.0 cases are a reported metric |
| Step 1 told that releases follow | Yes, unanimous |
| Cost follow-up | Told the extra cost is +8 to +9 person-days, not +3-5: all three unchanged |

Opus's build order: build S's assets first (they are step 2's) and commit step 1's extra work only
after a long-chain probe grades step 2 reliably; otherwise ship S. The single-step fallback S
reuses step 2's verifier unchanged.

## 2. Steps and acceptance criteria

| | Step 1 `01-rebuild` (1.1.2) | Step 2 `02-upgrade` (1.2.0) |
| --- | --- | --- |
| Agent / verifier timeout | 21,600 s / 2,700 s | 12,600 s / 2,700 s |
| Graded families | all ten on 1.1.2 gold | all ten on 1.2.0 gold; changed partition at least 30% of cases, reported per release item |
| Counts toward reward | no (reported) | yes (`final`) |
| Reference | 1.000 (2 local + 2 platform) | 1.000 (2 local + 2 platform) |
| nop | 0.000 (2 + 2) | 0.000 (2 + 2) |
| Regression on earlier step | n/a | the unchanged partition. The no-upgrade anchor (1.1.2's source at step 2) builds against the post-setup registry and scores 1.000 unchanged, 0.000 changed, 0.55-0.80 overall |
| Band mutant | M-dedup 0.70-0.85 (about 0.82), B-dedup only | same, on 1.2.0 |
| Other gates | stub zoo 0.000; kill matrix (at least 3 per feature, at least 1 per restriction); 3+1 determinism and a 10-run stability filter for 1.1.2's unordered diagnostics | same, plus at least 3 changed cases per CLI-observable 1.2.0 item with an unchanged dual; idle full-length chain graded twice, total at most about 42,000 s |

**Families (both steps):**
- R core replay 0.25
- B aggregation 0.25 (B-dedup 0.18, B-scope 0.07)
- K key-local and event schemas 0.10
- V validate verdict 0.10
- V-msg finding text 0.05
- L lowering 0.10
- M macros 0.05
- P providers 0.05
- X `explain` 0.03
- F `format`/`check-parse`/`schema` 0.02

## 3. Validity of the reasons (55 claims; full table in CLAIMS.md)

**Verified:**
- Apache-2.0; first public commit 2026-08-06; 28 commits; 531 stars; four contributors.
- 1.2.0 on 2026-11-18 with 62 changelog entries, 39 breaking.
- AgentCore writes temporal policies in Dogwood (quotas 20 / 3 / 24 h; 16 regions).
- 132k Lean lines with the claimed theorems, no `sorry`.
- Upstream calls its interpreter "NOT intended for production use".
- Three operators, no `once`.
- 93 bundles (93 `explain.out`, 56 `expected.out`, 14 providers, 8 macros, 4 arithmetic).
- Corpora 578 / 155 / 262 / 80 / 84.
- The generator: 4,087 lines, family weights, near-miss family, seed-determined.
- Exact Cedar 4.14.0 pin and the dated `vstd` pin.
- The CLI surface and exit codes; the hash-set rule order; human errors through miette.
- Every quote behind the failure sentence, in every version.
- Cue-word counts: "evaluat…" 177, "corpus" 45, "reference interpreter" 5.

**Corrected:**
- **"v1.0 on 2026-10-13":** the tag is the 2026-09-17 state. 1.0.x has no `format` or `explain`,
  there is no 1.0.x CLI crate, and the 39 breaking changes are counted against 1.1.2.
- **The `--locked` build:** it cannot work. Upstream commits no `Cargo.lock`, dependencies float
  (pest 2.9.7 and Cedar 4.15.0 exist), and CI uses floating stable.
- **The M-dedup band arithmetic:** 0.80-0.86 straddles the band's 0.85 top, so B is set to 0.25.
- **Effort:** 11-16 becomes 13-18 single-step and 21.5-27 two-step, counting the spike and QA.
- **Minor counts:**
  - tests 45.9k raw lines, not 48.7k;
  - 79 distinct rule names, not 75;
  - 207 headings, not 208;
  - 165 distinct pinned messages, not about 167;
  - "test" 34 by word start, not 38;
  - `HashMap` appears beyond `api.rs`.
- **The clone's later commits** include a docs sync, not only CI.
- **New finding:** 1.1.2's validation diagnostics are unordered; 1.2.0 fixed that.

**Unverified:**
- 250-400 features (estimate, settled by `features.yaml`);
- score bands and readiness (judgements);
- the durability argument (inference);
- probe-ability of B through the binary (no runs);
- public-benchmark novelty beyond the Forge check;
- the InfoQ article itself.

**Reason found partly invalid:** "the shipped examples' naive probes pass".
- It holds outright for M-dedup.
- For M-scope it holds only for an agent whose key-local slicing is right, because both
  un-windowed bundles aggregate other principals' events.
- The sentence stands; the evidence is restated.

## 4. Failure sentence and its proof plan

> Agents implement `count`/`sum` as tallies of matching past events, but Dogwood aggregates the
> deduplicated projection of the body's satisfying rows onto the `for` domain, and at the decision
> point only unless a past operator widens it, so they miscount every aggregate where equal values
> repeat across timepoints, the `for` list leaves out the timepoint, or the body has no past
> operator.

**Documented:**
- At least four statements in chapter 04 of every version, plus `count_distinct_within` in
  chapter 06.
- Chapter 12's "counting only this request itself" (1.1.2 and 1.2.0).
- The `alert_total_transfer_over_200` `explain.out`.
- A one-line probe derivation.

**Plausibly missed:**
- bag-semantics prior;
- no shipped example tells the readings apart (12 of 13 `for` lists include the timepoint);
- an early relational-evaluator choice;
- the guide's "simple sum" prose, which we fix for fairness.

**Proof, from patched source, per version:**
- **M-dedup**, the band mutant: B-dedup only, overall about 0.82.
- **M-scope:** B-scope only, about 0.93.
- **M-naive:** about 0.75.
- **M-global:** K only, for the difficulty ordering against the deep dive's alternative trap.

**Rules that make it a real check:**
- Tags come from generator intent, not mutant output, so the single-family check tests tagging
  hygiene and is not tautological.
- B cases are dual pairs (at least 80 pairs per step; at least 25 without the timepoint).
- Solvability from visible material only is written down before upload.
- Difficulty-ordering proxies are recorded per family.
- After trials, the sentence is kept only if B-dedup is the lowest family in most trials;
  otherwise it is rewritten from data.

## 5. Exact download list (for the owner's approval; details in SPIKE-PLAN.md)

| # | Item | Size |
| --- | --- | --- |
| D1 | Dogwood 1.2.0 source tarball, commit `8ffd2106…` (codeload.github.com) | about 15-25 MB |
| D2 | Dogwood 1.1.2 source tarball, commit `929f49e7…` | about 15-20 MB |
| D3 | `dogwood-cli-1.2.0.crate` (static.crates.io) | 26,868 B |
| D4 | `dogwood-cli-1.1.2.crate` | 31,981 B |
| D5 | Rust 1.100.0 (2026-11-12) minimal toolchain, pinned image `rust:1.100.0-slim-bookworm` or rustup; fallback 1.99.1 | about 250-300 MB image, or about 120 MB download |
| D6 | `rust-std` for `x86_64-unknown-linux-musl` 1.100.0 | about 30-40 MB |
| D7 | crates.io sparse index entries | a few MB |
| D8 | Every `.crate` in the two frozen locks: Cedar 4.11.0 and 4.14.0 with `-core`, `rhai`, `pest`, `vstd` 2026-09-20, `rustc-literal-escaper` 0.0.7/0.0.8, `miette`, `clap`, `regex`, `rust_decimal`, `serde`, `sha2` and the rest | about 150-250 crates, 30-60 MB |
| D9 | `debian:bookworm-slim`, pinned by digest | about 28 MB |
| D10 | Debian `python3`, `ca-certificates` (and `musl-tools` only if needed) | about 30-60 MB |

**Not downloaded:** meson, ninja, fontTools, Lean/elan, Node, pip packages, LSP, wasm, python
bindings.

**Where things are built:**
- Reference binaries: inside the agent image's builder stage (Linux x86_64).
- Mutants and generator batches: on a Linux x86_64 build machine.
- The shared laptop: light items only, under the memory guard.

## 6. Deviations and decisions for the owner

1. **Base version.** The brief's natural candidate "rebuild v1.0" became "rebuild 1.1.2", on the
   evidence (CLAIMS rows 4, 9, 42, 55) and the panel.
2. **The brief skill's modularity requirement is left out.** The instruction-writing skill asks
   the brief to require modular code. Both briefs leave it out, because no case can check it and
   the audit must-fixes unchecked promises; BasedPL v8 dropped its modular-source requirement for
   that reason.
3. **The 1.1.2 build stays in step 2** as `dogwood-1.1.2`. A migrating team would keep it, and it
   makes the upgrade fairer to probe. QA lens 19 should judge whether it makes step 2 too easy.
4. **Needs the owner's word:**
   - the download list;
   - the task name (drafted as `abundant/swe-m2_software-engineering_dogwood-policy-rebuild`, in
     line with the other rebuilds; the research used `library-reproduction`);
   - the optional off-platform pilot in CLAIMS section 4.
5. **Wording review.** An independent wording review of both briefs (sonnet, read-only) found no
   must-fix. Its should-fixes are applied:
   - "decision streams" instead of "verdict streams";
   - a requester's reason for following the build;
   - why `dogwood-1.1.2` stays;
   - a pointer for events that are not taken into the history.

   The mechanical sweep now finds no banned word.
6. **Untouched:** no PR was opened or edited, and the ops folder was not pushed (`push_ops.sh` not
   run).

## 7. Commits (branch `neel/dogwood-policy-rebuild`, pushed after each)

- `8c9faac` task skeleton
- `06da630` DESIGN.md
- `ed3ef3e` STEPS.md
- `efd7bd3` CLAIMS.md
- `a8e4d86` QA-PLAN.md
- `0a71743` SPIKE-PLAN.md (and the CLAIMS clone note)
- this report, the brief wording fixes and the README dev log: the next commit
