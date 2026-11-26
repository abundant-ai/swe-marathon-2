# Are the reasons valid? Claims re-checked, and the failure sentence's proof plan (2026-11-26)

Author notes, never shipped. The research behind this task re-checked here:
- **The report:** `SWE Marathon 2 library reproduction picks`, section 2.
- **The deep dive:** `deep_dogwood.md`.

Both are in the private ops repository. Every claim they use to justify the task is marked
**verified**, **corrected** or **unverified**.

## How I checked (2026-11-26)

- **The clone:** a read-only depth-1 clone of upstream `main` at `c7124710` (2026-11-19). Read with
  `grep`/`wc` and a small Python script run from outside the clone; nothing in it was built or
  executed.
  - GitHub's compare `v1.2.0...c7124710` shows 5 commits after the tag. They touch only CI,
    `AGENTS.md`, one line of `CHANGELOG.md`, 17 lines of `RELEASE_NOTES.md` and Lean files: no
    Rust, guide chapter or example.
  - So every code, guide and example count below holds for the 1.2.0 tag. The deep dive called
    these "CI-only commits"; one of them is a docs sync.
- **The GitHub API** (read-only):
  - the repository record;
  - releases and tags;
  - the 28 commits;
  - contributors;
  - directory listings at `v1.0`, `v1.0.2`, `v1.1` and `v1.2.0`;
  - five files at `v1.0.2`/`v1.1.2`: `dogwood-cli/src/main.rs`, both `Cargo.toml`s, and guide
    chapters 03, 04 and 12.
- **crates.io's API:** version, date, size, licence and `rust-version` metadata only; no `.crate`
  file was downloaded.
- **AWS's AgentCore page:** "Temporal policies".
- **Counting conventions:**
  - "Raw lines" means `wc -l`.
  - "Code lines" means non-blank, non-comment lines outside `#[cfg(test)]` blocks. It is a
    heuristic, and two heuristics disagree by up to 15% (row 13).

## 1. Validity table

### Identity, dates and novelty

| # | Claim | Evidence | Status | Note |
| --- | --- | --- | --- | --- |
| 1 | Apache-2.0 | `LICENSE`, `NOTICE` (Copyright Amazon.com), `Cargo.toml` `license = "Apache-2.0"`, API `spdx_id` | Verified | |
| 2 | Public since 2026-08-06 | First commit `ad915270` 2026-08-06T14:15Z "Dogwood: history-aware authorization policy language"; repo `created_at` 2026-07-27 | Verified | Whether the repo was public between 07-27 and 08-06 is unknown, but nothing was committed then |
| 3 | 28 commits, development squashed ("Sync … source") | Commit list via the API: 28 | Verified | |
| 4 | v1.0 on 2026-10-13, v1.1 on 2026-10-14, v1.0.1/v1.1.1 2026-11-06, v1.0.2/v1.1.2 2026-11-12, v1.2.0 2026-11-18 | Releases API: these are *published* dates | Corrected | The `v1.0` tag points at `996d756d`, committed **2026-09-17**, the day `dogwood-language` 1.0.0 reached crates.io. "v1.0" is the September state, published as a GitHub release a month later. Patch releases carry three dates: CHANGELOG 10-29 and 11-11, GitHub 11-06 and 11-12, crates.io 11-09 and 11-12 |
| 5 | v1.2.0 since 18 November, 39 breaking changes "eight days" before the research | `CHANGELOG.md` and tag commit 2026-11-18; research on 2026-11-26 | Verified | |
| 6 | About 62 changelog entries in 1.2.0, 39 breaking | Bullet count in the 1.2.0 section: 62 bullets, 39 marked "(breaking)" | Verified | About 15 of the 62 are Rust-API or build-only and not visible through the CLI (my reading of each bullet) |
| 7 | 1.1.2/1.0.2: about 8 entries (6 breaking); 1.1.1/1.0.1: about 10 (8 breaking) | Bullet count | Verified | |
| 8 | 531 stars, 36 forks, 12 open issues; four contributors | Repository and contributors API | Verified | |
| 9 | All crates published; `dogwood-language` first published 2026-09-17; `dogwood-cli` 2026-10-14 | crates.io API | Verified, with an addition | `dogwood-cli` exists only from 1.1.0: there is **no 1.0.x CLI crate**. Download counts have moved since (28,451 / 36,758 / 395 today) |
| 10 | Every graded behaviour is after every frontier cutoff (Claude June 2026; OpenAI mid-May to 1 June) | Dates above; the oldest graded release, 1.1.2's line, starts at v1.1 (2026-10-14) | Verified for Dogwood's own code | Cedar 4.11.0 is from 2026-05-18, before the cutoff. It is a vendored dependency, not graded behaviour. Its share of the weight is kept under 10% (DESIGN section 4) |
| 11 | No public benchmark rebuilds a policy engine or temporal monitor; the only Forge neighbour is `cedar-typeof-soundness` (a Lean proof-hole task) | `ls harbor-lh/tasks \| grep -iE 'policy\|cedar\|rego\|temporal\|ltl\|authz'` → `cedar-typeof-soundness` only | Verified for Forge; unverified for public lists | ProgramBench, FrontierSWE v2, TB2 and MirrorCode were not re-listed in Phase A |

### Production use and press

| # | Claim | Evidence | Status | Note |
| --- | --- | --- | --- | --- |
| 12 | AgentCore writes temporal policies in Dogwood ("compatible with Cedar and supports all existing Cedar policies"); quotas 20 per engine, 3 operators per policy, 24 h window; operators named `formerly within`, `since within`, `count`, `sum`; 16 regions | AWS page "Temporal policies" | Verified | The page also says counting conditions include the current request, consistent with closed windows |
| 13 | InfoQ (2026-08-16): standard-library macros over an MFOTL subset, "evaluation time can depend on the length of the event log", AWS not accepting contributions | `CONTRIBUTING.md`: "not accepting external contributions"; the four macros are in chapter 06's `DEFAULT_MACROS` | Partly verified | The article itself was not re-read; the facts it reports that matter are confirmed upstream |
| 14 | A 132k-line Lean model proves "Validation is sound" and "Dogwood conservatively extends Cedar", with no `sorry` or `native_decide` | `dogwood-lean`: 132,167 lines of `.lean`; README theorem table and axiom statement | Verified | The spec covers 1.2 with `experimental-arithmetic` on, over cedar-lean v4.14.0 |
| 15 | Upstream calls its interpreter a reference "**NOT** intended for production use" | `README.md` lines 16-20 and 150 | Verified | This is the brief's reason for an owned implementation |

### Size and scope

| # | Claim | Evidence | Status | Note |
| --- | --- | --- | --- | --- |
| 16 | `dogwood-language` about 61k raw lines in `src` and 48.7k in tests | `.rs` under `src`: 61,729; under `tests/`: 45,936 | Corrected (tests) | The 48.7k figure probably counts test modules inside `src` too |
| 17 | Code lines: `dogwood-language` 27.5k; in-scope about 23-26k | Same-area counts match within 5% for interpreter (1,612 vs 1,609), macros, `informalize` (1,998 vs 1,998), `cedarify` and the parser. My filter gives 32.3k for all of `src` (temporal 6,703 vs 5,638; API glue 3.6k vs 2.3k) | Verified within heuristic spread | In scope is about 26-30k by my filter, including all API glue, and 23-26k by the deep dive's. Both are inside the 10-40k target. A real SLOC tool comes in the spike |
| 18 | `dogwood-cli` 457 code lines, ops 1.8k raw, formatter 0.5k raw, syntax 0.8k raw, LSP 11.9k + 15.2k tests | 457 / 1,825 / 483 / 793 / 11,862 + 15,212 | Verified | |
| 19 | Pest grammars 947 raw lines (368 + 429 + 150) | Same | Verified | |
| 20 | 250-400 documented features | 79 distinct bold rule names in chapter 08 (85 occurrences: TEMP 19, L 18, A 17, FailClosed 9, WF 8, PROV 6, V 4, EVENT 4); 207 H2/H3 headings in chapters 02-06, 08-10, 12 | Unverified (estimate); inputs corrected | The deep dive said 75 distinct names and 208 headings; my counts are 79 and 207. Its per-prefix occurrence counts match exactly. Only `features.yaml` can settle the total |
| 21 | Every in-scope feature is observable through the CLI | `main.rs`: `format`, `check-parse`, `validate`, `lower --emit cedar-policies\|cedar-schema\|cedar-json\|both`, `replay --trace`, `explain`, `schema action\|event\|providers` (`mcp` only with the feature); `--format human\|json`; exit 0/1/2 | Verified for the command surface | Feature by feature, this is the kill matrix's job |
| 22 | Chapter 07 (927 lines) is the Rust API, unobservable through the CLI, but holds the only trace-format specification | Chapter 07 "Trace replay" (lines 748-785): envelope order, strict parsing, `TraceParse`; `entities(...)` appears only there and in one bundle README | Verified | Its "Event kinds, decisions, and failure handling" section may hold replay-visible rules; check it before cutting (DESIGN 1.3) |
| 23 | Guide: 13 chapters, 7,702 lines plus a 101-line README; per-chapter counts | `wc -l` | Verified | |
| 24 | 93 example bundles plus one script; all have `explain.out`; 56 have `trace.log` and `expected.out`; 14 `providers.json`; 8 `macros.dw`; 4 marked `requires-experimental-arithmetic` | Directory scan | Verified | At v1.0.2 there were 86 bundles and none had `explain.out`; v1.1 and v1.2.0 have 93 |
| 25 | Public corpora: 578 temporal, 155 macros, 262 expected failures, 80 probes, 84 integration-test files; `TESTING.md` stale (475, 144, 164) and Lean README stale (68 probes) | Directory counts; `TESTING.md` lines 12-17; Lean README line 87 | Verified | |
| 26 | About 167 distinct pinned error messages; the most common (43 cases) is the removed `let` binder | First-60-character groups: 165; `let` message: 43 | Corrected (minor) | |
| 27 | No `once` operator: exactly three operators `formerly`, `previous`, `since`, each with a mandatory `within`; `once` is only a macro example; README's "(`since`, `formerly`, `once`, aggregations)" is loose | Chapter 04 line 116; `def temporal once` in the guide; README line 5 | Verified | |
| 28 | Four units `s m h d`; closed windows stated twice | Chapter 04 lines 124-129 and 723 | Verified | Round 1's window-edge sentence stays refuted |
| 29 | Over the CLI, `scriptFile` is never resolved, so `replay` fails with "rhai implementation has no script" | Chapter 12 lines 97-110 | Verified | |
| 30 | `explain` has four rewrite rules and a first line stating the event schema's pins; `format` changes whitespace only and leaves a statement with an inner comment unchanged | Chapter 12 lines 52-64 and 207-238 | Verified | |

### Build, determinism and the generator

| # | Claim | Evidence | Status | Note |
| --- | --- | --- | --- | --- |
| 31 | Exact pins: `cedar-policy =4.14.0`, `cedar-policy-core =4.14.0`, `rustc-literal-escaper =0.0.8`, `vstd =0.0.0-2026-09-20-0158`; `rhai 1` (`decimal`, `sync`), `pest 2`, `regex`, `rust_decimal`, `sha2`, `miette 7`; off-by-default `corpus`, `mcp-schema`, `net`, `experimental-arithmetic`, `frontend-export`, `lean-frontend` | `dogwood-language/Cargo.toml` | Verified | Also `links = "dogwood_lean"`. `vstd` is a dated pre-release on crates.io (MIT, 328 KB, 2026-09-20) |
| 32 | Build with `cargo build --release --locked -p dogwood-cli --features experimental-arithmetic --target x86_64-unknown-linux-musl` | No `Cargo.lock` anywhere in the clone or at `v1.0.2`; `.gitignore` does not list it, it is simply not committed. CI runs `rustup update stable` | **Corrected: cannot work as written** | `--locked` fails without a lock, and every caret dependency floats: pest 2.9.7 (2026-11-24) and Cedar 4.15.0 already exist. 1.1.2's `cedar-policy = "4.11"` is held at 4.11.x only through its MCP generator's exact pin. Fix: freeze one lock per release, or take the lock packaged in the `dogwood-cli` `.crate` if it has one (spike item), then reproduce every shipped expected output |
| 33 | Default build needs no Lean (`build.rs` prints `cargo:lean=0` without `lean-frontend`); binary named `dogwood` | `build.rs` lines 4-7, 124; `dogwood-cli/Cargo.toml` `[[bin]] name = "dogwood"` | Verified | |
| 34 | Replay's `[rules: …]` comes unsorted from Cedar's hash set | `api.rs` lines 2020-2022 ("Cedar reports determining policies from a hash set … `reason` keeps the engine's order"); `dogwood-ops/src/ops.rs` 332-336 collects `reason()` unsorted; `render.rs` 147-150 prints it | Verified by reading | No run, so the order changing between processes is inferred, not observed. None of the 56 `expected.out` lists more than one rule |
| 35 | Human-mode fatal errors use miette's graphical, terminal-sensitive renderer; `validate` findings print as plain `error:` lines; JSON is the stable machine shape | `render.rs` 27-36, 64-88; CLI `miette` with `fancy`; chapter 12 line 34 | Verified | Fatal human errors go to standard error, which is never compared |
| 36 | No `SystemTime`, `Instant`, `thread::spawn`, `rand` or `RandomState` outside Lean-frontend tests; BTree collections almost everywhere; `HashMap` only in `api.rs` lookups | `SystemTime` 0, `Instant` 0, `rand::` 0, `RandomState` 0; `thread::spawn` 2, both in `lean_frontend/tests.rs`; BTreeMap 234, BTreeSet 156 | Corrected (minor) | `HashMap`/`HashSet` also appear in `leaf_map.rs` (keyed lookups whose values are BTreeSets), `field_path.rs` (test module) and `lean_frontend/decode.rs` |
| 37 | (Not in the research) 1.1.2's validation diagnostics may come in a different order on each run | 1.2.0 CHANGELOG, Fixed: "diagnostics list entity types and request environments in name order, so they are the same on every run" | New finding | Step 1's V-msg cases need a 10-run stability filter |
| 38 | Rhai providers have no CPU or memory limits by default; `net` is off because it makes providers non-deterministic | `README.md` lines 213-217; `Cargo.toml` comment | Verified | One process per case with a timeout |
| 39 | The interpreter does not validate timestamps; the Lean baseline lists `decreasing_timestamp_read` | `README.md` 158-162; `baseline.txt` | Verified | The baseline's other disagreements are also as stated: 2 stamping probes, 3 missing-scope-entity cases, 2 undeclared-provider cascades, 1 optional `datetime`, 1 own-leaf-name read |
| 40 | The generator is 4,087 lines of Python with a typed, weighted grammar, a `nearmiss` family aimed at every validity rule, each bundle "a function of the seed and its index alone"; family weights temporal 30, nearmiss 26, providers 11, macros 10, events 9, schema 8, traces 6; `probegen.py` 682 lines | `wc -l` over 11 files = 4,087; `families.py` line 27; conformance README line 47 | Verified | It writes `meta.json` with family and features per bundle, which is useful for tagging. It targets 1.2 (the Lean spec), so step 1 must filter out 1.2-only constructs. Its trace knobs (`equal_ts`, `decreasing_ts`, `extreme_timestamps`, `nonconforming`) are set to 0 for our cases, except `nonconforming` in step 2. The files carry no per-file header; the repository's Apache-2.0 `LICENSE` and `NOTICE` cover them |

### The failure sentence's premises

| # | Claim | Evidence | Status | Note |
| --- | --- | --- | --- | --- |
| 41 | The guide states "project … onto the `for` domain, deduplicate, then count" | 1.2.0 chapter 04 lines 343, 371, 455, 734; the same four statements in 1.1.2 (339, 367, 451, 730) and 1.0.2 (338, 366, 450, 632); chapter 06's `count_distinct_within` ("repeated values across timepoints deduplicate") | Verified, and stronger than claimed | Stated at least four times in every version, plus once in the macros chapter |
| 42 | An un-windowed `count` covers "only this request itself" | Chapter 12 lines 234-238 (1.2.0), line 215 (1.1.2); the evaluation semantics (chapter 04 lines 727-734) imply it | Verified for 1.1.2 and 1.2.0 | Absent from 1.0.2, which has no `explain`. One reason M2a beats M2b |
| 43 | The guide's own prose calls one example a "simple sum" (`alert_total_transfer_over_200`) | Chapter 04 line 428 (1.2.0), 424 (1.1.2), 423 (1.0.2) | Verified | Its `explain.out` reads "the sum of a over the distinct values a for which the current event is a Transfer request"; its README says the body "scans only the *current* timepoint". To be fixed in every shipped doc set (DESIGN 1.3) |
| 44 | The `for (t: Timepoint)` idiom makes naive counting agree, so an agent's probes of the shipped examples pass | 12 of the 13 shipped `for` lists include the timepoint (`grep` over all `policy.dw` and `macros.dw`). The 13th is un-windowed with distinct amounts (100, 200, 50) | Verified by reading for M-dedup; **refined** for M-scope | Both un-windowed bundles (`alert_total_transfer_over_200`, `alert_heartbeat_and_login_rate`) aggregate other principals' events. Under the default `callerPrincipal` pin, key-local slicing already gives 0, so even a whole-history reading prints all DENY. The examples hide M-scope only if key-local slicing is right; an agent wrong on both would be caught. To prove in the spike: run both mutants over the 56 bundles |
| 45 | Key-local pins may be the stronger trap | Chapter 03 (default schema `pin callerPrincipal: principalType(A) = principal`); chapter 04 line 721 (`previous` is "this key's previous event"; the `∀`-side of `since` ranges over the key's positions) | Verified as documented; unverified as stronger | 1.2.0 widened it ("any universal pin … whatever the field is called"), so in step 2 it is also a changed behaviour |
| 46 | With B at 20% and the mutant failing at least 70% of B, the overall score is about 0.80-0.86, in band | Arithmetic: 1 − 0.2 × 0.7 = 0.86, 1 − 0.2 × 1.0 = 0.80 | **Corrected** | The band is 0.60-0.85, so 0.86 is outside it. Two further problems: if B also holds the un-windowed cases, M-dedup alone fails only the dedup share; and the "failing ≥70% by design" figure was never tied to how the cases are tagged. Fix: B at 0.25 with B-dedup 0.18 and B-scope 0.07. Cases are tagged by the generator's feature intent, not by mutant output. M-dedup then lands near 0.82 (section 4) |
| 47 | "Fair because two doc statements, one example's `explain` output and one-line probes all reveal it" | Rows 41-43 | Verified (docs, `explain.out`); unverified (probes) | Probes of the binary are a Phase B item; no binary was run |
| 48 | "Durable because correctness needs a relational evaluator chosen early and costly to retrofit" | Chapter 04's relational semantics (`&&` as join, `!` as anti-join, aggregation as projection) | Unverified (inference) | Plausible, not measurable before trials |

### Cue words, estimates and judgements

| # | Claim | Evidence | Status | Note |
| --- | --- | --- | --- | --- |
| 49 | Guide uses "evaluat…" 177 times, "corpus" 45 (27 are case citations), "test" 38, "conformance" 9, "reference interpreter" 5; example READMEs: "corpus" 24, "test" 13, "harness" 4, "oracle" 1 | Case-insensitive counts over the guide: 177 / 45 / 34 (word-start "test") / 9 / 5; corpus-case citations 24; READMEs 24 / 12 / 4 / 1 | Verified (counting conventions differ by a few) | New: "session" occurs 23 times in the guide (domain sense, user sessions), "budget" once in the guide, 3 times in READMEs, 2 in policies (domain sense, "refund budget"). Both are on the banned list in our sense, so the sweep must judge each one (QA-PLAN section 4) |
| 50 | Formal spec says "the code is authoritative" | Chapter 08: "… with its source of record — the file and function; the code is authoritative, and …" | Verified | Its "source of record" annotations name upstream source files; we scrub them |
| 51 | Frontier 0.45-0.70, mid-tier 0.15-0.35 | Proxies only | Unverified (estimate) | Two-step estimates are in DESIGN section 6 |
| 52 | Build 11-16 person-days | Item list in the deep dive | Corrected | It leaves out the spike and the 20-pass QA. Itemised: 13-18 single-step, 21.5-27 two-step (DESIGN section 7) |
| 53 | Readiness Medium (3/5), crispness 4/5, total 29/40 | Judgement | Unverified (judgement) | Readiness is lower until the build route (row 32) and the diagnostics order (row 37) are settled |
| 54 | Diversity 3: our third language toolchain after Goose and BasedPL | `tasks/static/app_clone/` | Verified | New domain and new kinds of output |
| 55 | "Rebuild v1.0, then upgrade to v1.2's 39 breaking changes" (the brief's natural candidate) | 1.0.x has no `format`, `explain` or enum providers; the 39 breaking changes are counted against 1.1.2 | Corrected | The panel chose 1.1.2 then 1.2.0, which is exactly the release the 39 changes describe |

## 2. What the corrections change

1. **The build route.** Freeze our own locks (or use the packaged ones) and a pinned toolchain.
   Reproducing every shipped `expected.out` and `explain.out` is the acceptance test of each
   reference build (rows 32, 4, 9).
2. **The step plan.** "v1.0" is a September snapshot without `format` or `explain`. The 39
   breaking changes are relative to 1.1.2. The chain is therefore 1.1.2 then 1.2.0 (row 55;
   [STEPS.md](STEPS.md)).
3. **Determinism at step 1.** Step 1 adds a stability filter for validation messages (row 37).
4. **Weights.** B goes from 0.20 to 0.25, with M-dedup as the band mutant (row 46).
5. **The sentence's evidence is refined, not overturned.** The examples hide the dedup half
   outright. They hide the scope half only from an agent whose key-local slicing is right
   (row 44).

## 3. The failure sentence

> **Agents implement `count`/`sum` as tallies of matching past events, but Dogwood aggregates the
> deduplicated projection of the body's satisfying rows onto the `for` domain, and at the decision
> point only unless a past operator widens it, so they miscount every aggregate where equal values
> repeat across timepoints, the `for` list leaves out the timepoint, or the body has no past
> operator.**

**Documented, so a careful agent can learn it:**
- The rule is stated at least four times in chapter 04 of every shipped version (row 41) and in
  chapter 06's `count_distinct_within`.
- The decision-point reading follows from chapter 04's "holds at timepoint `i`" semantics, and
  chapter 12's `explain` section says it in words (row 42).
- The `explain.out` of `alert_total_transfer_over_200` says "the distinct values a" and "the
  current event".
- One-line probes expose both halves. A trace with two `Transfer` requests of 100 under one
  principal, followed by an `Alert` whose `sum a for (a: Long). where formerly within 1h …`
  threshold is 150, prints DENY. Dropping `formerly` makes the sum read only the `Alert` itself.
  (This is the derivation path to write down and run in the spike.)

**Plausibly missed, and why:**
1. Bag semantics is the prior: SQL's `SUM`, and most monitors and rate limiters, count events.
2. No shipped example tells the readings apart: 12 of 13 `for` lists include the timepoint, and
   the remaining one is un-windowed with distinct amounts (row 44). An agent that checks its work
   against the shipped bundles gets no signal.
3. Under the default pin, the two un-windowed bundles are all-DENY for a second reason, key-local
   slicing. So they do not expose a whole-history reading either.
4. Correct results need a relational evaluator (joins, anti-joins, projection), not boolean
   recursion over events. That is an early architectural choice and expensive to change late.
5. The guide's own "Simple sum … total transferred exceeds 200" invites the naive reading. We fix
   that prose for fairness, which weakens this reason; reasons 1-4 remain.

**What could make it wrong:**
- Frontier agents that read chapter 04's "Form" section carefully may simply get it right. In
  that case B stops being the lowest family, which only trials can show.
- The deep dive's alternative, key-local slicing (family K), may dominate instead. Section 4 adds
  the difficulty-ordering proxies that test this before any run.
- After the first trials, the per-family labels decide.

## 4. The proof plan (grading guide sections 13 and 4)

**Mutants, built from patched source, once per version (1.1.2 and 1.2.0):**

| Mutant | Patch | Expected signature |
| --- | --- | --- |
| **M-dedup** (the band mutant) | In the interpreter's aggregation path (`dogwood-language/src/interpreter/`), aggregate the body's satisfying rows directly: no projection onto the `for` columns and no deduplication, so one row per satisfying occurrence (bag semantics). The function is located in the spike | B-dedup falls by at least 50 points (target: to 0-10%); B-scope, R, K, V, V-msg, L, M, P, X and F stay at 95% or more; overall ≈ 1 − 0.18 = **0.82**, inside 0.60-0.85 |
| **M-scope** (sibling) | Evaluate an aggregate whose body has no past operator over every in-window timepoint of the history instead of the decision point only | B-scope falls by at least 50 points; everything else at 95% or more; overall ≈ 1 − 0.07 = 0.93; a distinct signature from M-dedup |
| **M-naive** (both patches) | The "tally of matching past events" model the sentence describes | B falls to 0-10%; overall ≈ 0.75 |
| **M-global** (the alternative trap, for the ordering check) | Ignore universal pins at evaluation: global `previous`/`since` instead of the key's slice | Only K (and the K-tagged step-2 changes) falls; its score is compared with M-dedup's in the difficulty ordering |

**Rules that keep the check honest:**
1. **Tags come from intent, not from the mutant.** Cases are tagged with their family from the
   generator's feature intent (`meta.json` features plus our dual templates), never from mutant
   output. The check that M-dedup's failures fall only in B is then a real test of tagging
   hygiene. An R case that happens to hold an aggregate with repeated values shows up as
   cross-family leakage, and is retagged or regenerated.
2. **B cases are dual pairs.** Each B-dedup case is paired with its timepoint-in-`for` dual, where
   the two readings agree. Each B-scope case is paired with the same body under `formerly`. A pair
   counts only if both pass. At least 80 pairs per step; at least 25 B-dedup pairs have a `for`
   list without the timepoint (the shape no shipped example shows).
3. **Every other mutant gets the same treatment.** The kill matrix's 40-80 mutants per version
   ([QA-PLAN.md](QA-PLAN.md) gate 2) must not produce B's signature.
4. **What the mutant shows, and what it cannot.** It shows the grader can see the failure and
   where it lands. It cannot show that agents make it. The tagging rule above is what keeps the
   check from being tautological.

**Solvability of B from visible material alone (section 13, step 2):**
- Before upload, an author pass writes the derivation using only the shipped docs and the
  execute-only build: which paragraphs, which `explain.out` lines, which probe commands and their
  outputs.
- If any part of B needs something neither documented nor probe-discoverable, the cases that need
  it are dropped.

**Difficulty ordering without model runs (section 13, step 3):** for each family, record three
proxies from the reference source:
- the share of interpreter code behind it;
- how many documented rules interact in it;
- whether the docs state it explicitly or only by example.

B is stated explicitly, which counts against it as the hardest family. If K or V-msg ranks harder
on the proxies, the README says so and the sentence becomes "B or K" (at most two families,
section 13) until trials decide.

**Optional cheap pilot (needs the owner's OK; off-platform):** a short local session by a small
model, limited to chapter 04's aggregation section and the build, to check that B is neither
trivially solved nor impossible.

**After the first trials:**
- Auto-label every failing case by family, which is free because cases are tagged. The sentence
  holds if B, specifically B-dedup, is the lowest family in most trials.
- If K or V-msg dominates instead, first re-run its solvability derivation and the cue and leak
  checks, then rewrite the sentence from the data.
