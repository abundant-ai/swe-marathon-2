# Dogwood rebuild: design (single step, 2026-11-27)

Author notes, never shipped.

**History.**
- Phase A (2026-11-26) designed a two-step chain (1.1.2, then the 1.2.0 upgrade).
- The owner then set multi-turn aside ("we dont have to promote multi-turn as well so make stuff
  likewise"), and asked that a single-turn task be "difficult enough". So this is the single-step
  rebuild of 1.2.0 that the chain kept as its fallback, with the same grader.
- The chain's plan is parked in [STEPS.md](STEPS.md) and [parked-two-step/](parked-two-step/).

**Where the rest is:**
- checked facts: [CLAIMS.md](CLAIMS.md);
- the QA plan: [QA-PLAN.md](QA-PLAN.md);
- the spike: [SPIKE-PLAN.md](SPIKE-PLAN.md);
- what Phase B ran and measured: [PHASE-B-REPORT.md](PHASE-B-REPORT.md).

## 1. What the agent gets and what it delivers

**The working machine** (`environment/Dockerfile`, one session, `timeout_sec` 34,560):

| Path | What it is |
| --- | --- |
| `/usr/local/bin/dogwood` | Dogwood 1.2.0 as released. It is built at image build time from the published `dogwood-cli-1.2.0.crate`, which was published from tag commit `8ffd2106`. The build uses its published `Cargo.lock`, every dependency is vendored from crates.io and checked against that lock, `experimental-arithmetic` is on, and the target is the architecture's `*-unknown-linux-musl`, static. Mode 2711, root-owned, setgid to an empty group |
| `/app/docs/guide/`, `/app/docs/examples/` | 1.2.0's guide and its 93 example bundles, trimmed and scrubbed (section 1.2). **Not in the image yet**: the trim and scrub is the next work item |
| Rust 1.100.0 | The pinned `rust:1.100.0-slim-bookworm` image (index digest `sha256:bb875b0f…`) |
| `/opt/cargo-registry` with `~/.cargo/config.toml` | The vendored crates of the published lock, without the four `dogwood-*` crates. `cargo` uses it offline |
| `/app/dogwood-rebuild/` | Empty, owned by the agent user `dev` |

The agent runs as `dev`, with no network and no `sudo`.

**The deliverable:**
- `/app/dogwood-rebuild`, a Cargo project whose `cargo build --release --offline` builds a binary
  named `dogwood`.
- `task.toml` declares it as the root-level artifact.
- The grader copies it, without `target/` or outside links, and builds it as an unprivileged
  user with the same toolchain and registry. Then it runs the cases.

### 1.2 The shipped docs: trim, move, scrub, fix

| Action | What |
| --- | --- |
| Keep | Chapters 00-06, 08-10, 12 |
| Cut | Chapter 07 (Rust API), except its "Trace replay" section, which moves into chapter 12; chapter 11 (MCP); the Rust-API, LSP, Lean-frontend and `net` passages elsewhere |
| Check before cutting | Chapter 07's "Event kinds, decisions, and failure handling" and "Retries and event ids" sections: whatever `replay` can observe moves into chapter 12 |
| State every rule | The difficulty must come from rules that cut against a model's prior, never from anything hidden. The trim keeps every statement of the two counter-intuitive rules (section 3a), and an audit lists each graded rule with its sentence in the shipped guide ([QA-PLAN.md](QA-PLAN.md) section 2) |
| Scrub | Every agent-visible use of the banned classes ([QA-PLAN.md](QA-PLAN.md) section 4): "corpus case …" citations, "test" and "testing" in the authoring sense, "reference interpreter", "harness", "oracle", "conformance" in the Lean sense, links to upstream's repository and crates.io, and chapter 08's "source of record" annotations naming upstream files. Domain senses stay ("evaluate a policy", "the event conforms to its schema") |
| Fix | Chapter 04's "Simple sum of a bound value column — total transferred exceeds 200", which contradicts its own bundle. The rewrite says what the bundle shows; every statement of the deduplication rule stays |
| Reword | The timestamp contract becomes "out of contract; behaviour unspecified" |
| Verify | Our pinned build reproduces every shipped `expected.out` and `explain.out` byte for byte ([PHASE-B-REPORT.md](PHASE-B-REPORT.md)) |

## 2. The hidden reference and how it stays invisible

**Gold.**
- The grading image records the expected result of every private case while it is built. It runs
  each case three times through the same release build, the way the grader runs a submission;
  `tests/record.py` does this.
- Only the recorded results reach the final stage, so the grading image never holds a `dogwood`
  build. A submission that wraps the build has nothing to call.
- Because gold is recorded on the platform's own architecture, no arm64/x86_64 drift reaches the
  scores.

**Private cases.**
- The bundles and their command lines are in Git-ignored `tests/private/`.
- They are backed up in the private ops repository.
- Their seeds are in `tests/private/manifest.json`.

**The working machine.**
- It is multi-stage: no upstream source, `target/` or crate cache from the release build reaches
  the final stage.
- The build is mode 2711. It cannot be read, setgid gives `AT_SECURE`, a static binary has no
  loader for `LD_PRELOAD`, and an unreadable executable makes a non-dumpable process.
- The registry holds no `dogwood-*` crate.

**Leak scan.** No private case equals or near-copies a shipped example or a public upstream corpus
case.

## 3. Grading families and weights

**A case and how it is judged:**
- A case is a bundle (policy, schemas, and optionally providers, macros and a trace) plus one
  command line in one format.
- It runs in its own process with a fresh working directory, `HOME` and `TMPDIR`, as `nobody`,
  with 5 s and 2 GB.
- Standard output is compared exactly, with two exceptions: JSON is compared parsed with object
  key order ignored, and rule lists compare as sets. The exit status must match too.
- Standard error is never read.

**Scoring:**
- `S = Σ w_f g_f`, with `g_f = max(0, (pass_f − b_f)/(1 − b_f))`, where `b_f` is the best stub's
  pass fraction in that family.
- A paired case counts only if both members pass.
- Integrity failures (a submission that holds or calls a `dogwood` build, or touches the grader's
  files) give 0.
- An evaluation error writes no reward.

| Family | Weight | What its cases exercise |
| --- | --- | --- |
| R core replay | 0.20 | `formerly`, `previous`, `since` on single-principal traces; windows and units; `exists`; `tp`; `&&`/`!`; comparisons and the `==` binder; arithmetic; fail-closed decisions; Cedar conditions next to temporal ones |
| B-dedup aggregation, deduplication | 0.17 | `count`/`sum` over the deduplicated projection onto the `for` domain: repeated equal values, `for` lists without the timepoint (dual pairs) |
| B-scope aggregation, decision point | 0.05 | Aggregates whose body has no past operator read only the decision event (dual pairs) |
| K key-local slicing | 0.15 | Universal symmetric pins: `previous` is the key's previous event, the left of `since` ranges over the key's positions, the 1.2.0 rule that any universal pin is key-local, non-universal pins staying global, the strict mirror rule, and non-conforming events rejected (`REJECTED, not ingested`). Traces interleave principals; key-local pairs are duals |
| V validate verdict | 0.13 | Accept/reject and exit status of `validate`, as accept/near-miss pairs, one near-miss per stated rule |
| V-msg validate text | 0.05 | The `--format json` findings (message, severity, byte spans) |
| L lowering | 0.10 | `lower --emit …`: hoisted names, the balanced `&&` fold, desugaring, schema augmentation |
| M macros | 0.05 | `def cedar` / `def temporal`, sigils, hygiene, the standard library, `--macros`, the rejection classes |
| P providers | 0.05 | Rhai providers, `paramType` variants, enums, methods, fail-closed outputs, `scriptFile` over the CLI |
| X `explain` | 0.03 | Text and JSON phrase trees; the four rewrites; the pins line |
| F `format`, `check-parse`, `schema` | 0.02 | `format` cases whose output differs from the input; `check-parse` counts; `schema …` accept/reject |

### 3a. Difficulty sizing and the levers chosen (2026-11-27)

**Target.** The owner asked for a single turn that is "difficult enough", and the coordinator's
target is frontier at about 0.6 or less and mid-tier at 0.1-0.4. Phase A's estimate for the
single-step design was frontier 0.45-0.70, which is too high at the top. Only fair levers are
used: nothing hidden, every graded rule stated in the shipped guide.

| Lever | What changed | Why it is fair |
| --- | --- | --- |
| A second counter-intuitive family | K rises from 0.10 to 0.15 and gets paired cases and its own mutant (M-global). The deep dive flagged key-local slicing as possibly the stronger trap | The rule is stated in chapter 03 (universal symmetric pins) and chapter 04 ("`previous` means 'this key's previous event'"; the left of `since` "quantifies over this key's positions only"); the default event schema applies it to every policy |
| Aggregation plus `validate` at least 35% | B 0.22 plus V 0.13 plus V-msg 0.05 = 0.40 | Both are stated rule by rule (aggregation at least four times in chapter 04; every validation rule in chapters 04 and 08) |
| Replay's easy core shrinks | R falls from 0.25 to 0.20 | Weight follows the rules that need a relational, key-local evaluator, not the parts any recursive checker gets right |
| Pairs | B-dedup, B-scope, K and V are dual pairs; a pair counts only if both members pass | Both members are documented behaviour; a half-right implementation gets half the pairs wrong rather than half the credit |
| Case mix toward the documented corners | Traces interleave principals; aggregates repeat equal values; validate pairs sit on each stated rule's boundary | Every case traces to a feature id with its sentence in the shipped guide |

**Not levers:** undocumented behaviour, hidden rules, timing pressure, and exact error wording
beyond the 5% V-msg share.

**Mutant proofs after the reweighting** (all in the 0.60-0.85 band or below the top family drop):

| Mutant | Family drop | Overall if the family fails fully |
| --- | --- | --- |
| M-dedup (no projection or deduplication) | B-dedup | 1 − 0.17 = **0.83** |
| M-scope (bodies without a past operator read the whole history) | B-scope | 0.95 |
| M-naive (both) | B | 0.78 |
| M-global (no key-local rewrite: `previous` and the left of `since` read the whole trace) | K | 1 − 0.15 × (share of K that M-global fails) |

The Phase B spike measured these on the first case set ([PHASE-B-REPORT.md](PHASE-B-REPORT.md)).

**Sizing (estimates, to check against the first trials):**
- **A frontier agent at the cap:** R 0.85, B 0.30, K 0.40, V 0.60, V-msg 0.30, L 0.70, M 0.60,
  P 0.40, X 0.30, F 0.80 lands near **0.52**.
- **A mid-tier agent:** R 0.50, B 0.10, K 0.15, V 0.30, V-msg 0.10, L 0.30, M 0.20, P 0.10, X 0.05,
  F 0.50 lands near **0.25**.
- **Bands:** frontier 0.40-0.60, mid-tier 0.10-0.35.

## 4. Stub filters

The stub zoo runs at every build and must score 0.000 after pairing and baseline subtraction
([QA-PLAN.md](QA-PLAN.md) section 3).

| Stub | What it would pass | What zeroes it |
| --- | --- | --- |
| nop (empty directory) | nothing | the build fails |
| prints nothing | nothing | every case has stdout |
| exit status only | validate rejects | stdout compared too |
| "OK: validation passed…" | accepted validate cases | accept/near-miss pairs |
| all-DENY / all-ALLOW replayer | single-verdict streams | R, B and K streams are mixed or paired |
| `format` as `cat` | already-formatted input | `format` cases differ from their input; the comment rule is paired |
| `check-parse` counter | clean parses | paired with syntax errors |
| `schema` "OK" | valid schemas | paired with invalid ones |
| lookup table of shipped examples | shipped examples | leak scan |
| wrapper around `dogwood` | everything in the sandbox | no build in the grading image |
| Cedar-only implementation | cases with no temporal or provider leaf | legitimate partial credit, held under 10% of the weight |

## 5. Determinism controls

**Inputs:**
- Strictly increasing timestamps; bundles whose traces repeat or reverse a timestamp are dropped
  at generation.
- Traces of 200 events or fewer.
- Cases avoid the regions where upstream's Lean model and the crate disagree.

**Outputs:**
- Rule lists compare as sets, because Cedar reports determining policies from a hash set.
- JSON compares parsed.
- Standard error is never compared.
- A fixed environment (`TERM=dumb`, `NO_COLOR=1`, `LANG=C.UTF-8`, no TTY).

**Recording.** A case without one answer over three runs stops the grading image's build. The
spike's 3+1 and 10-repeat recordings are in the Phase B report.

**Builds:**
- The published lock with `--locked`.
- The pinned toolchain image.
- C dependencies built with `musl-gcc` from Debian's `musl-tools` (cedar's `stacker` pulls in
  `psm`).

## 6. Expected score bands (estimates)

| Who | Single step (1.2.0) |
| --- | --- |
| Frontier (Opus 5.5 / Fable 5.2 / GPT-6 Astra class) | 0.40-0.60 |
| Mid-tier (DeepSeek v4.1 Flash, GLM 5.3) | 0.10-0.35 |

**A working task shows:**
- no full solve;
- B or K as the lowest family in most trials;
- V-msg trailing V;
- the score still rising at the cap.

## 7. Effort (person-days)

| Item | Days |
| --- | --- |
| Spike (done in Phase B) | 1.5 |
| Images, release build, registry | 1 (done in Phase B) |
| Doc trim, scrub, fix, the "every rule stated" audit | 2-2.5 |
| Case generation, pairs, family tagging (first families done in Phase B) | 2-3 |
| Grader (skeleton done in Phase B) | 1.5 |
| Feature and restriction inventory, kill matrix (40-80 mutants on a Linux build machine) | 2-4 |
| Stub zoo, determinism, protection probe, long-run smoke | 1-2 |
| 20 QA passes and fix rounds before the Oddish gate | 1-2 |
| **Total** | **12-17** |

## 8. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| A documented feature or stated restriction left with zero cases | Audit must-fix | `features.yaml` from the shipped docs, two-way trace, kill matrix |
| Evaluation-aware wording in the brief, the docs or `--help` | Verdict reject | Requester voice, mechanical sweep, 3 wording lenses |
| The guide trim drops a rule a case grades | Unfair case | The "every rule stated" audit (section 1.2) |
| The failure sentence is wrong: K or V-msg dominates instead of B | Weaker story | Two counter-intuitive families with mutants; trial labels decide |
| The frontier lands above 0.6 anyway | Saturation | Re-weight within the fair levers after the first trials; never hide rules |
| The heavy grading image (release build plus recording) at upload | Upload time | Build time measured in Phase B; the release stage is shared with the working machine's image |
| Third language toolchain after Goose and BasedPL | Diversity criticism | New domain and new outputs |
