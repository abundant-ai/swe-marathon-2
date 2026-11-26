# Dogwood rebuild: design (Phase A, 2026-11-26)

Author notes, never shipped. Nothing here has been built or run; every number is a plan or an
estimate unless a source is cited. Checked facts are in [CLAIMS.md](CLAIMS.md), the step plan in
[STEPS.md](STEPS.md), the QA plan in [QA-PLAN.md](QA-PLAN.md) and the spike in
[SPIKE-PLAN.md](SPIKE-PLAN.md).

## 1. What the agent gets and what it delivers

The task is a two-step chain in one sandbox, decided by a three-judge panel ([STEPS.md](STEPS.md)):
1. **Step `01-rebuild`:** rebuild `dogwood` 1.1.2.
2. **Step `02-upgrade`:** bring the same code to 1.2.0.

### Step 1 sandbox (built into the agent image)

| Path | What it is |
| --- | --- |
| `/usr/local/bin/dogwood` | Upstream 1.1.2 (tag `v1.1.2`, commit `929f49e7`) built with `--features experimental-arithmetic` for `x86_64-unknown-linux-musl`, static, stripped. Mode 2711, root-owned, setgid to an empty group. |
| `/app/docs/1.1.2/guide/` | 1.1.2's guide, trimmed and scrubbed (section 1.3) |
| `/app/docs/1.1.2/examples/` | 1.1.2's 93 example bundles (`policy.dw`, schemas, `providers.json`/`macros.dw`/`.dwschema` where present, `explain.out`, and `trace.log` + `expected.out` where present), READMEs scrubbed; `regenerate-explain.sh` not shipped |
| Rust toolchain | One pinned stable release, at least 1.89 (Cedar 4.11/4.14 and `rustc-literal-escaper` 0.0.8 declare `rust-version` 1.89), at least 14 days old when the spike pins it |
| `/opt/cargo-registry` + `~/.cargo/config.toml` | Vendored directory source that `cargo` uses offline; `net.offline = true` |
| `/app/dogwood-rebuild/` | Empty directory owned by the agent user `dev` |

The registry holds an explicit allow-list of crates, matched to 1.1.2's dependency graph:
- **Included:** `cedar-policy` and `cedar-policy-core` 4.11.0, `pest`, `pest_derive`, `rhai`
  (`decimal`, `sync`), `regex`, `rust_decimal`, `miette` (`fancy`), `clap`, `serde`,
  `serde_json`, `smol_str`, `nonempty`, `sha2`, `thiserror`, `rustc-literal-escaper` 0.0.7, and
  their transitive closure.
- **Left out:** every `dogwood-*` crate; the MCP generator, which serves only `schema mcp`, out of
  scope; and `vstd`, which 1.1.2 does not use.

The agent runs as `dev` with no network and no `sudo`.

### Step 2 additions (installed by `steps/02-upgrade/workdir/setup.sh`, which runs as root before the agent starts)

- **The builds:** the 1.2.0 build (tag `v1.2.0`, commit `8ffd2106`, same build flags) moves from a
  root-only staging directory to `/usr/local/bin/dogwood`. 1.1.2 stays as
  `/usr/local/bin/dogwood-1.1.2`.
- **The docs:** `/app/docs/1.2.0/` gets 1.2.0's trimmed and scrubbed guide, its 93 bundles, and
  `RELEASE_NOTES.md`. The release notes are cut to the items a command-line user can see, plus the
  upgrade notes.
- **The registry:** it gains `cedar-policy` and `cedar-policy-core` 4.14.0, `rustc-literal-escaper`
  0.0.8 and their new transitive crates.
- **What persists:** the agent's code in `/app/dogwood-rebuild` and anything else it wrote.
- **Session:** step 2 starts a fresh agent session, so its brief stands alone.

### The deliverable (both steps)

- **Shape:** `/app/dogwood-rebuild`, a Cargo project whose `cargo build --release --offline`
  builds a binary named `dogwood`.
- **Artifact:** `task.toml` declares `artifacts = ["/app/dogwood-rebuild"]` at the root level.
- **What the verifier does with it:** copies it without `target/` or outside links, builds it in
  the verifier image (same toolchain, same registry as that step), then runs the cases.

### 1.3 The shipped docs: trim, move, scrub, fix (per version)

| Action | What |
| --- | --- |
| Keep | Chapters 00-06, 08-10, 12 |
| Cut | Chapter 07 (Rust API, 927 lines in 1.2.0) except its "Trace replay" section, which moves into chapter 12; chapter 11 (MCP); Rust-API, LSP, Lean-frontend and `net` passages elsewhere |
| Check before cutting | Chapter 07's "Event kinds, decisions, and failure handling" and "Retries and event ids" sections: whatever is observable through `replay` moves into chapter 12 too |
| Scrub | Every agent-visible use of the banned classes ([QA-PLAN.md](QA-PLAN.md) section 4): "corpus case …" citations (24 in the guide), "test"/"testing" in the authoring sense, "reference interpreter", "harness", "oracle", "conformance" in the Lean sense, links to upstream's repository and crates.io, and chapter 08's "source of record" annotations that name upstream source files. Domain senses stay: "evaluate a policy", "the event conforms to its schema" |
| Fix | Chapter 04's "Simple sum of a bound value column — total transferred exceeds 200" (same text in 1.0.2, 1.1.2 and 1.2.0). Rewrite it to say what the bundle shows: a body without a past operator sees only the event being decided, so that `Alert` permit never fires. Keep every statement of the deduplication rule |
| Reword | The timestamp contract: "out of contract; behaviour unspecified" instead of a promise the build does not check |
| Verify | Every shipped `expected.out` and `explain.out` is reproduced byte for byte by our pinned build of that version. Otherwise it is regenerated from our build and the dev log says so |

## 2. The hidden reference and how it stays invisible

- **Where gold comes from:** gold is recorded from our pinned builds at authoring time and stored
  per step in `steps/<N>/tests/private/`. It is Git-ignored and backed up as a bundle in the
  private store. The verifier image holds the gold, the case files and the grader, and never a
  `dogwood` build. A submission that wraps a build therefore has nothing to call.
- **Agent image:** multi-stage.
  - The builder stage downloads the two pinned source tarballs and the locked crates (checksums
    verified), builds both binaries and strips them.
  - The final stage copies the two binaries, the toolchain, the vendored registry (allow-list
    only) and the trimmed docs.
  - No upstream source, `target/` or `~/.cargo/registry` cache from the reference build reaches it.
- **Execute-only builds:** mode 2711, so the binary is unreadable, and setgid gives `AT_SECURE`.
  The musl-static binary has no dynamic loader, so `LD_PRELOAD` has nothing to hook. Executing an
  unreadable file makes the process non-dumpable, which blocks `ptrace` and `/proc/<pid>/mem` and
  `exe` reads.
- **Probe:** the QA protection probe checks all of this as `dev` in the real sandbox.
- **Future material:** the 1.2.0 build, docs and crates wait in `/root/.staging/` (0700; `/root` is
  0700) until step 2's `setup.sh` installs them. Nothing in step 1 names 1.2.0.
- **Clean-room wording:** the brief forbids reading Dogwood's source and disassembling or tracing
  the build. The prompt rule is not the defence, though. The defence is the file modes and the
  absence of any source, and the brief only explains them.
- **Leak scan:** no hidden case equals or near-copies a shipped example or a public upstream corpus
  case (578 temporal, 155 macros, 262 expected-failure, 80 probe directories, 93 examples). See
  [QA-PLAN.md](QA-PLAN.md) gate 11.

## 3. Grading families and weights

**A case** is a bundle:
- **Inputs:** a policy, the action schema, and optional event schema, `providers.json`, macro
  library and trace.
- **Run:** one command line in one format.
- **Expected:** the gold standard output and exit status.

**How a case is run and compared:**
- Each case runs in its own process with a fresh working directory, `HOME` and `TMPDIR`, a 5 s
  limit and 2 GB of memory, as `nobody`.
- Standard output is compared exactly after two normalisations:
  - JSON is parsed and compared with object key order ignored;
  - rule lists (`[rules: …]` in human replay output, `determining_rules` in JSON) are compared as
    sets.
- The exit status must match.
- Standard error is never read.

| Family | Weight | What its cases exercise | Cases, step 1 / step 2 (target) |
| --- | --- | --- | --- |
| R core replay | 0.25 | `formerly`, `previous`, `since`, windows and units, `exists`, `tp`, `&&`/`!`, comparisons and the `==` binder, arithmetic, fail-closed decisions, Cedar conditions next to temporal ones; verdict streams with at least one ALLOW and one DENY | 300 / 320 |
| B aggregation semantics | 0.25 (B-dedup 0.18, B-scope 0.07) | `count`/`sum` over the deduplicated projection onto the `for` domain; repeated equal values; `for` lists with and without the timepoint; bodies with and without a past operator; built as dual pairs | 160 / 160 (80 / 80 pairs) |
| K key-local and event schemas | 0.10 | Universal symmetric pins, `previous` and `since` on the key's slice, non-universal pins, the mirror rule (1.2.0), decision kinds, custom `.dwschema`, `max_window`/`max_horizon` | 120 / 140 |
| V validate verdict | 0.10 | Accept/reject and exit status of `validate`, as accept/near-miss pairs, one near-miss per stated rule | 240 / 280 |
| V-msg validate text | 0.05 | The `--format json` findings (message, severity, labels with byte spans) of the V cases that reject; human `error:` lines | (same cases as V) |
| L lowering | 0.10 | `lower --emit cedar-policies / cedar-schema / cedar-json / both`: hoisted leaf names, the balanced `&&` fold, desugaring, schema augmentation, the stderr note's absence or presence via exit status | 140 / 160 |
| M macros | 0.05 | `def cedar` / `def temporal`, `?p` and `$t`, hygiene, the standard library, `--macros`, the rejection classes | 80 / 80 |
| P providers | 0.05 | Rhai providers, `paramType` variants, enums (1.1+), methods, `guardrails`, fail-closed outputs, `scriptFile` over the CLI | 80 / 90 |
| X `explain` | 0.03 | Text and JSON phrase trees with spans; the four rewrites; the pins line | 60 / 70 |
| F `format`, `check-parse`, `schema` | 0.02 | `format` cases whose output differs from the input (plus the comment rule, paired); `check-parse` counts and undeclared providers; `schema action/event/providers` accept/reject | 60 / 60 |

**Step 2 case mix:**
- The step-2 set mixes cases whose output is the same in 1.1.2 and 1.2.0 with cases whose output
  changed.
- At least 30% are changed cases, with at least 3 (target 10) per CLI-observable 1.2.0 item,
  spread over the families where the behaviour lives.
- The changed partition is reported as a metric per release-note item; it carries no separate
  weight (panel, Q4).

**Scoring (per step):**
- Per family: `g_f = max(0, (pass_f − b_f)/(1 − b_f))`, where `b_f` is the best stub's pass
  fraction in that family.
- A paired case counts only if both members pass.
- Step score: `S = Σ w_f g_f`.
- **Integrity gates** set `S` to 0:
  - the submission contains or invokes a `dogwood` build (a byte match on the shipped binaries'
    hashes and an exec trace in the verifier);
  - the build step writes outside its directory;
  - the grader's files are touched.
- **Evaluation errors** leave no reward file.
- **`metrics.json`** holds:
  - per family: the pass fraction, `g_f` and the case count;
  - per feature id: kills;
  - per release item: the step-2 changed partition;
  - threshold flags: all cases, ≥99% and ≥95%.

**Why these weights:**
- B is 0.25, not the report's 0.20 (section 6 of [CLAIMS.md](CLAIMS.md)). At 0.20 the predicted
  B-mutant score straddled the top of the 0.60-0.85 band. At 0.25, with B-dedup at 0.18, M-dedup
  lands near 0.82.
- B and the two validate families together hold 0.40. The report asked for at least 0.35, so
  replay-heavy work cannot carry a frontier model past 0.8.
- `explain` and `format` stay small, because their exact text is specified mostly by example.
- Weights are by documented importance, never by case count. They are re-fitted once, after the
  spike measures per-feature yields, and then frozen before the first QA pass.

## 4. Stub filters

The stub zoo runs at every build and must score 0.000 after the baseline subtraction and pairing
([QA-PLAN.md](QA-PLAN.md) section 3). The members, and the rule that zeroes each:

| Stub | What it would pass | Rule that zeroes it |
| --- | --- | --- |
| nop (empty directory) | nothing | build fails, every case fails |
| Prints nothing, exits 0 | nothing | every case has non-empty stdout |
| Exit-status-only per command | validate rejects | stdout must match too |
| "OK: validation passed…" printer | accepted validate cases | accept/reject pairs |
| All-DENY / all-ALLOW replayer that parses trace lines | single-verdict streams | R and B streams must be mixed, or be paired with a mixed dual |
| `format` as `cat` | already-formatted input, the comment rule | `format` cases whose output differs from the input; comment-rule cases paired |
| `check-parse` counter ("OK: parsed N policies.") | clean parses | paired with syntax-error cases |
| `schema … ` "OK" printer | valid schemas | paired with invalid ones |
| Lookup table of every shipped example | shipped examples | no hidden case equals or near-copies one (leak scan) |
| Wrapper around `dogwood` | everything, in the sandbox | the verifier has no build; integrity gate |
| Cedar-only implementation (vendored `cedar-policy`, no temporal leaves) | cases without temporal or provider leaves | not a stub but legitimate partial credit; such cases are kept under 10% of the weight |

## 5. Determinism controls

**Inputs:**
- Every trace has strictly increasing timestamps.
- Events conform to their declared kinds, except where non-conformance is the point of a 1.2.0 case.
- Traces have 200 events or fewer.
- Cases avoid the regions where upstream's own Lean specification and the crate disagree:
  caller-stamped and decreasing timestamps, missing scope entities, cascading findings for
  undeclared providers, the optional `datetime` validation, and reading a policy's own hoisted
  name.

**Outputs:**
- Rule lists are compared as sets.
- JSON is compared parsed.
- Standard error is never compared, which covers human-mode fatal errors (miette's graphical
  renderer).
- Every run sees the same environment: `TERM=dumb`, `NO_COLOR=1`, `LANG=C.UTF-8`, no TTY.

**Two orders that may move between runs:**
- **Replay's `[rules: …]`:** Cedar reports determining policies from a hash set, and 1.2.0's
  `dogwood-ops` collects `reason()` unsorted. The set comparison covers it.
- **1.1.2's validation diagnostics:** they list entity types and request environments in an
  unfixed order. 1.2.0's changelog fixes this ("Validation diagnostics list entity types and
  request environments in name order, so they are the same on every run"). Step 1's V-msg cases
  keep only messages that are identical over at least 10 repeated runs, and the spike measures
  how many multi-environment messages that drops.

**Recording:**
- Three identical runs plus one perturbed run must give byte-identical per-case verdict files,
  and the verdict-file hashes must match. The perturbed run uses 1 CPU, a longer working-directory
  path, another `HOME` and another umask.
- Multi-permit replay cases and multi-environment validate cases run at least 10 times.
- Cedar's schema printer order (`lower --emit cedar-schema/cedar-json`) is recorded across 10 runs.
- A case that varies is dropped, not normalised away, unless the variation is one of the two
  documented orders above.

**Builds:**
- One frozen `Cargo.lock` per release. Upstream commits none, and its dependencies float: pest 2.9.7
  came out on 2026-11-24, after 1.2.0.
- One pinned toolchain.
- The build must reproduce every shipped `expected.out`/`explain.out` of its own tag before any
  gold is recorded.

## 6. Expected score bands (estimates, untested)

| Who | Step 1 (1.1.2, reported) | Final reward (1.2.0) | Single-step fallback |
| --- | --- | --- | --- |
| Frontier (Opus 5.5 / Fable 5.2 / GPT-6 Astra class) | 0.40-0.65 | 0.40-0.65 | 0.45-0.70 |
| Mid-tier (DeepSeek v4.1 Flash, GLM 5.3) | 0.12-0.30 | 0.10-0.30 | 0.15-0.35 |

The two-step final sits a little under the single-step estimate for two reasons: about 5.75 hours
go to 1.1.2 behaviour, and the upgrade breaks some of what step 1 built. The reference scores 1.0
at both steps. The step-2 anchor is 1.1.2's own source delivered unchanged, which shows what an
upgrade that does nothing earns. That anchor should score 0.55-0.80; [STEPS.md](STEPS.md) treats
anything above 0.80 as too few changed cases.

A working task shows:
- no full solve;
- the lowest family is B in most trials;
- K and V-msg trail R;
- the step-2 changed partition lags the unchanged one;
- the score is still rising at the cap.

## 7. Effort (person-days, one author who knows Rust and our checks)

| Item | Single-step | Two-step (chosen) |
| --- | --- | --- |
| Spike (offline builds, locks, determinism, mutant signatures) | 2 | 3 |
| Reference builds and image packaging, staging for step 2 | 1 | 2 |
| Doc trim, scrub, fix, move (per version) | 2 | 3.5 |
| Generator adaptation, dual pairs, case selection, gold recording | 2-3 | 3-4 |
| Grader (separate image, offline build of the submission, per-case runner, metrics) | 2 | 2.5 |
| Feature and restriction inventory, kill matrix, 40-80 mutant builds per version on a Linux build machine | 2-4 | 3.5-6 |
| Stub zoo, determinism, protection probe, long-run smoke, idle full chain | 1-2 | 2-3 |
| 20 QA passes and fix rounds before the Oddish gate | 1-2 | 2-3 |
| **Total** | **13-18** | **21.5-27** |

The report's 11-16 days for the single-step task left out the spike and the 20-pass QA. Counting
them, the two-step chain costs about 7-9 days more than single-step.

## 8. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| A heavy per-step verifier fails after a long chain (all 4 such trials failed on 2026-11-19; one probe passed on 2026-11-24, n = 1) | A lost trial under `final` | Images prebuilt at upload; verifier work under 2,700 s per step, measured at full case count; an idle full-length reference and no-op chain before any model trial; fall back to single-step if it fails |
| A documented feature or stated restriction left with zero cases (back office v11, BasedPL v6 were rejected for this) | Audit must-fix | `features.yaml` from the shipped docs, mechanical diff against the docs, kill matrix gate |
| Evaluation-aware wording in the brief, the docs or `--help` (Carve v3, back office v10 and v13) | Verdict reject | Requester voice with consumers stated, cut-over line, mechanical sweep plus 3 wording lenses |
| Upstream's docs disagree with our pinned build because dependencies drifted | Unfair cases, audit finding | Frozen locks; reproduce every shipped expected output before recording gold |
| 1.1.2's unstable diagnostic order | Flaky V-msg cases | Ten-run stability filter for step 1 |
| The failure sentence is wrong: B is not the dominant failure, and K or V-msg is | Weak diagnostic story | Pre-run difficulty-ordering proxies; post-run family labelling; the sentence is revised from trial data, not defended |
| musl-static build fails, or `vstd`'s dated pre-release does not resolve offline | Build route change | Spike item 1; fallback is a glibc build with mode 2711 |
| Mutant builds (2 versions x 40-80) exceed laptop RAM | Machine stalls | Built on a Linux build machine or in the image builder, never on the shared laptop |
| Third language toolchain after Goose and BasedPL | Diversity criticism | New domain (authorization, runtime verification) and new outputs (decision streams, validation verdicts, lowered Cedar) |
| Churn: upstream ships 1.3 | Task drifts from upstream | Pinned tags; the task is about 1.1.2 and 1.2.0 by design |
