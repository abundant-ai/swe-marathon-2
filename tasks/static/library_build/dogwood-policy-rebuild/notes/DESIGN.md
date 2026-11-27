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
- what Phase B ran and measured: [PHASE-B-REPORT.md](PHASE-B-REPORT.md);
- what Phase C ran and measured: [PHASE-C-REPORT.md](PHASE-C-REPORT.md).

## 1. What the agent gets and what it delivers

**The working machine** (`environment/Dockerfile`, one session, `timeout_sec` 34,560):

| Path | What it is |
| --- | --- |
| `/usr/local/bin/dogwood` | Dogwood 1.2.0 as released. It is built at image build time from the published `dogwood-cli-1.2.0.crate`, which was published from tag commit `8ffd2106`. The build uses its published `Cargo.lock`, every dependency is vendored from crates.io and checked against that lock, and `experimental-arithmetic` is on. It is built for the image's own glibc target, because a static musl build failed Cedar evaluations at random ("recursion limit reached"; see the Phase B report). Mode 2711, root-owned, setgid to an empty group |
| `/app/docs/guide/`, `/app/docs/examples/` | 1.2.0's guide and its 93 example bundles, trimmed and scrubbed (section 1.2). `scripts/build_docs.py` makes them from the pinned source and the edit list `scripts/docs_edits.json`; the result is committed as `environment/docs/` |
| Rust 1.100.0 | The pinned `rust:1.100.0-slim-bookworm` image (index digest `sha256:bb875b0f…`) |
| `/opt/cargo-registry` with `~/.cargo/config.toml` | The vendored crates of the published lock, without the four `dogwood-*` crates. `cargo` uses it offline |
| `/app/dogwood-rebuild/` | Empty, owned by the agent user `dev` |
| Python 3.11 | Debian's, for the agent's own scripts (the brief says so) |
| `/usr/local/sbin/stop-user-processes` | Root-only (0700). Harbor runs it as `[[verifier.collect]]` after the session: it stops and then ends every process of `dev`, so nothing left running changes the deliverable while it is copied |

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
  scores. No answer holds a float or a libm result either: Cedar decimals are fixed-point, and
  every provider decimal in the cases comes from `parse_decimal` of a string literal.
- The program it records from is a file named `dogwood`, as a delivered build is installed:
  the usage text names the file a program was started as.
- A case without one answer over the three runs stops the image build. Selection keeps only
  cases with one answer over six recorded runs, and drops every answer that names one member of
  a cycle, which the build picks by hash order.

**Private cases.**
- The bundles and their command lines are in Git-ignored `tests/private/`.
- They are backed up in the private ops repository.
- Their seeds are in `tests/private/manifest.json`.

**The working machine.**
- It is multi-stage: no upstream source, `target/` or crate cache from the release build reaches
  the final stage.
- The build is mode 2711. It cannot be read, and setgid gives `AT_SECURE`, so the dynamic loader
  ignores `LD_PRELOAD` and `LD_LIBRARY_PATH`. An unreadable executable also makes a non-dumpable
  process.
- The registry holds no `dogwood-*` crate.

**Leak scan** (`checks/leaks.py`). The agent can run the build on anything it sees, so no private
case may read only files it can see: every file a case reads (policy, schemas, providers, macros,
trace) equal, up to comments and whitespace, to the files of one shipped example or of one
directory of upstream's public repository fails the scan. Policies equal to a public one, and
near copies (word 5-grams, Jaccard 0.9 or more), are counted.

**The grader's own hardening** (`tests/verifier/`):
- output is read with a cap (8 MB a run, 16 MB for the build log), so a flood cannot exhaust
  the grader;
- after the build and after every run, every process of `builder` or `nobody` still alive is
  ended (a process that left its group included) and counted in the metrics;
- runs are in a fixed order hashed from the case ids, and the global deadline gives every case
  its full per-run limit, so it binds only a run that overruns;
- the grader adopts orphans (`PR_SET_CHILD_SUBREAPER`), sweeps a user's processes until none is
  left, and removes what a run or the build left in the shared writable folders, so runs share
  nothing;
- each run's folder stays root's; the built program must be a regular file inside the build
  folder and is copied from an `O_NOFOLLOW` descriptor;
- the output folder may be writable by every user, and `reward.json` there is read first: the
  grader closes the folder to everyone but its owner before any build or run (so a planted
  reward cannot outlive a grader that dies mid-run), ends every process of `builder` and
  `nobody`, removes whatever stands under its output names, creates each output fresh
  (`O_EXCL`, `O_NOFOLLOW`, relative to the folder's descriptor), writes the reward last, and
  gives the folder its mode back; an evaluation error clears the reward files too;
- nothing a submission prints, builds or leaves running raises: output comparison falls back to
  the printed text, a link loop is left out of the copy, and an unstartable program fails its
  own cases;
- the metrics list any delivered `.rs`/`.pest` file that is a copy of Dogwood's own source (by
  digests made in the release stage, as written and with whitespace removed). This is for
  review against the clean-room rule and does not change the reward: the oracle is upstream's
  own source, and any edit to a copied file would evade a hard check anyway.

**After the session.** Harbor runs `/usr/local/sbin/stop-user-processes` as root
(`[[verifier.collect]]`) before it copies `/app/dogwood-rebuild`: it stops, then kills, every
process of `dev`. The platform restores public egress when the agent's turn ends, before
collection (harbor-lh `PLATFORM_EGRESS_WINDOW.md`); a process the agent left behind could fetch
Dogwood's crates in that window. The hook shortens the window but cannot close it, the clean-room
report flags a verbatim drop-in, and the trajectory audit is the remaining check.

## 3. Grading families and weights

**A case and how it is judged:**
- A case is a bundle (policy, schemas, and optionally providers, macros and a trace) plus one
  command line in one format.
- It runs in its own process with a fresh working directory, `HOME` and `TMPDIR`, as `nobody`,
  with the limits the brief states: 1 s, 2 GB of memory, 512 processes and threads, files of at
  most 256 MB, 8 MB of standard output.
- Standard output is compared exactly, with two exceptions: JSON is compared parsed with object
  key order ignored, and rule lists compare as sets. The exit status must match too.
- Standard error is never read.

**Scoring:**
- `S = Σ w_f g_f`, with `g_f = max(0, (pass_f − b_f)/(1 − b_f))`, where `b_f` is the best stub's
  pass fraction in that family.
- A paired case counts only if both members pass.
- A submission that calls `dogwood` finds no build in the grading image, and the grader's files
  are out of reach of the build (`builder`) and the runs (`nobody`). Delivered files that are
  copies of Dogwood's own source are listed in the metrics (`dogwood_source_files`) for the
  clean-room review; that list does not change the score.
- An evaluation error writes no reward. Nothing a submission prints, builds or leaves running can
  cause one: those fail its own cases (section 4's probes check it).

| Family | Weight | What its cases exercise |
| --- | --- | --- |
| R core replay | 0.20 | `formerly`, `previous`, `since` on single-principal traces; windows and units; `exists`; `tp`; `&&`/`!`; comparisons and the `==` binder; arithmetic; fail-closed decisions; Cedar conditions next to temporal ones |
| B-dedup aggregation, deduplication | 0.17 | `count`/`sum` over the deduplicated projection onto the `for` domain: repeated equal values, `for` lists without the timepoint (dual pairs) |
| B-scope aggregation, decision point | 0.05 | Aggregates whose body has no past operator read only the decision event (dual pairs) |
| K key-local slicing | 0.15 | Dual pairs in eight shapes (`scripts/pairs.py`): `previous` is the key's previous event; the positive left of `since` ranges over the key's positions, and the key's own non-matching event still breaks it; a pin on some kinds only keeps global semantics; a universal pin to `context.session` keys on the session; the mirror rule rejects a history event that logs a caller it does not carry, fails a decision event that does, and rejects a history event with no principal under the default pin. Traces interleave principals |
| V validate verdict | 0.13 | `validate` in human form: the generator's near misses (64 kinds, each breaking one stated rule) and accepted bundles; an accepted bundle counts only paired with a rejected one |
| V-msg validate text | 0.05 | The same in `--format json` (message, severity, byte spans), paired the same way |
| L lowering | 0.10 | `lower` with `--emit both` (human and JSON), `cedar-policies`, `cedar-schema` and `cedar-json`: hoisted names, the balanced `&&` fold, desugaring, schema augmentation; `lower` on near misses, which it does not validate |
| M macros | 0.05 | `def cedar` / `def temporal`, sigils, hygiene, the standard library, `--macros`, the rejection classes |
| P providers | 0.05 | Rhai providers, `paramType` variants, enums, methods, fail-closed outputs, `scriptFile` over the CLI |
| X `explain` | 0.03 | Text and JSON phrase trees, with and without `--policy-schema`; the four rewrites; the pins line |
| F `format`, `check-parse`, `schema`, the command line | 0.02 | `format` on a copy of each policy with its layout disturbed; `check-parse` (human and JSON) on each policy and on a copy with one token broken; `schema action`, `schema event`, `schema providers`; `--help`, `--version`, usage and I/O errors |

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

**The second sentence (K).**
> Agents pin each predicate to the request's principal but read `previous` and the left of `since`
> over the whole trace, so a decision flips whenever another principal's event sits between two
> of this principal's events.

Where 1.2.0's guide states it, so the trim must keep it:
- **Chapter 03, "The mirror rule" and "Universal symmetric pins: key-local semantics and the
  partition guarantee"** (lines 95-163):
  - "`previous` means 'this key's previous event.'";
  - "The positive left of `since` quantifies over this key's positions";
  - the default schema's `callerPrincipal` pin;
  - "A pin that is not universal silently keeps global semantics".
- **Chapter 04, line 721:** the key-local reading under universal pins.
- **Chapter 12, lines 134-139:** non-conforming history events are "rejected, and not ingested".

The mutant is M-global: upstream's relativisation pass is skipped, so predicates stay pinned but
`previous` and `since` read the global trace.

**Mutant proofs after the reweighting** (all in the 0.60-0.85 band or below the top family drop):

| Mutant | Family drop | Predicted | Measured, Phase B first case set |
| --- | --- | --- | --- |
| M-dedup (no projection or deduplication) | B-dedup | 1 − 0.17 = **0.83** | **0.83**: B-dedup 0 of 40 pairs, every other family 1.0 |
| M-scope (bodies without a past operator read the whole history) | B-scope | 0.95 | **0.95**: B-scope 0 of 40 pairs, every other family 1.0 |
| M-naive (both) | B | 0.78 | **0.78**: B-dedup and B-scope 0 of 40 pairs each |
| M-global (no key-local rewrite: `previous` and the left of `since` read the whole trace) | K | 1 − 0.15 × (share of K it fails) | **0.85**: K 0 of 40 pairs, every other family 1.0 |

Each mutant moves only its own family, so every signature is single-family.

**Family tagging is checked by the mutants** (`scripts/retag.py`). `make_cases.py` tags a case by
what its policy and trace contain. On the first case set that intent tagging over-counted: no
unpaired case it put in B-dedup (60), B-scope (6) or K (122) changed under the matching mutant.
Those cases still check core replay, so they move to R. The three counter-intuitive families are
therefore made only of the dual pairs from `scripts/pairs.py` (40 per family). Before the
retagging, M-dedup scored 0.932 and M-global 0.963, because uninformative cases diluted their
families.

**K's shapes (Phase C).** Phase B's K was one shape (`previous` with another principal's event in
between). Phase C adds the other stated K rules as dual shapes, so a reading that gets one rule
right and another wrong fails pairs: the positive left of `since` over another principal's event
and over the key's own non-matching event, a pin on `request` only (global, no slicing), a
universal pin to `context.session` (slicing by session, not principal), and the three mirror-rule
cases. M-global breaks the slicing shapes; the mirror-rule shapes need their own mutants (section
3a's table and the Phase C report).

**Sizing (estimates, to check against the first trials).** Phase B's estimate was 0.52 for the
frontier and 0.25 for mid-tier. Phase C's case set is harder in four ways the estimate now counts:
- selection keeps no unit a trivial program passes, and pairs every weak case with a case whose
  answer is its own, so a unit needs both answers right;
- V is accept/reject pairs on 64 near-miss kinds and the restriction templates;
- K has eight dual shapes, not one, so getting slicing right but the mirror rule wrong fails
  pairs;
- V-msg compares error messages and spans exactly, and many of the template errors are not
  quoted in the guide.

The weights stay as section 3 lists them. Per family, as unit pass rates:

| Agent | R | B-dedup | B-scope | K | V | V-msg | L | M | P | X | F | Weighted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Frontier at the cap | 0.75 | 0.35 | 0.40 | 0.35 | 0.50 | 0.15 | 0.50 | 0.50 | 0.40 | 0.25 | 0.50 | **0.47** |
| Mid-tier | 0.40 | 0.05 | 0.15 | 0.10 | 0.25 | 0.03 | 0.20 | 0.15 | 0.10 | 0.05 | 0.30 | **0.19** |

- **Bands:** frontier 0.35-0.60, mid-tier 0.08-0.30, inside the owner's "difficult enough" target
  (frontier at about 0.6 or less, mid-tier 0.1-0.4).
- **What would move it:** the first trials' per-family rates. If the frontier tops 0.6, the fair
  levers are the weights inside the stated rules (section 3a's table), never hidden rules.

## 4. Stub filters

**Selection makes every stub score 0 by construction** (`scripts/select_cases.py`, from the
release build's recorded answers). A unit is a single case, or a pair that counts only when both
members pass. A case is weak when a trivial program could print its answer:
- its standard output is empty;
- its answer is the one its command gives most often, or one given more than once for its
  command (commands are keyed as the table-driven stubs key them: subcommand, `--emit` form or
  schema part, and `--format` value);
- it is a replay whose stream is DENY, or ALLOW with one rule list, for every event;
- it is a `format` whose output is its input.

A weak case is paired with a case of the same family and command whose answer is its own, or
dropped. A declared B or K pair one program passes whole is dropped. After the family caps, a unit
whose every answer is also given elsewhere is dropped. `checks/stub_estimate.py` predicts the
zoo from the recorded answers.

**The zoo itself** (`checks/stubs.py`): std-only Cargo projects, built and run by the real grader
the way a submission is. They must all score 0.

| Stub | What it does |
| --- | --- |
| nop | an empty directory (the build fails) |
| silent, usual-status | print nothing; exit 0, or each command's most common status |
| exit1, exit2 | print nothing and fail every command with 1 (or 2) |
| accept, reject | `validate` prints the accept line, or a generic error |
| deny, allow | `replay` prints DENY, or ALLOW with rule 0, for every request line |
| cat | `format` prints its input |
| count | `check-parse` prints "OK: parsed N policies." from a count of rules |
| most-common | every command prints its most common recorded answer (one given at least twice) |
| echo | `lower` prints the policy without its temporal and provider blocks, then the schema |
| lookup | prints a shipped example's recorded output when the policy (and trace) is that example's |
| wrapper | runs `dogwood` from `PATH` (the grading image has none) |

**Robustness probes**, in the same zoo: `hang` (sleeps past the per-run limit on two command
lines), `flood` (prints without end on `--help`), `forkbomb` (forks without end on
`--version`), `daemon` (leaves a detached process on `format`), `garbage` (prints JSON nested past
a parser's depth, a rule list of mixed values, and empty or overlong rule numbers), `buildrs` (a
build script that tries to read the private cases and the grader, write the reward, and leave a
process behind), `forge` (a build script and a program that write `reward.json` and `reward.txt`
into the output folder, plant links under the other output names and leave a process rewriting
the reward; graded with a world-writable output folder, as the platform may provide) and
`badexec` (a build that leaves an unrunnable file where the program belongs).
Each must leave the grader working: no evaluation error, a reward of 0, and its leftovers ended.
Next to the zoo, the oracle is graded with odd files around it (a 5 GB sparse file in `target/`,
20,000 small files, link loops, links outside and to a directory, a pipe, a socket; it must score
1.0), and over the 1 GB copy limit (it must score 0, without an evaluation error).

A Cedar-only implementation earns legitimate partial credit on the cases without temporal or
provider leaves; that is held well under the weight of R, B and K.

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
- The image's glibc target. The static musl build was dropped: under musl, Cedar's stack check
  (via `stacker`) misjudges the main thread's stack and fails evaluations at random.

## 6. Expected score bands (estimates)

| Who | Single step (1.2.0), Phase C estimate |
| --- | --- |
| Frontier (Opus 5.5 / Fable 5.2 / GPT-6 Astra class) | about 0.47 (0.35-0.60) |
| Mid-tier (DeepSeek v4.1 Flash, GLM 5.3) | about 0.19 (0.08-0.30) |

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
| A documented feature or stated restriction left with zero cases | Audit must-fix | `checks/features.json` from the shipped docs, two-way trace, kill matrix |
| Evaluation-aware wording in the brief, the docs or `--help` | Verdict reject | Requester voice, mechanical sweep, 3 wording lenses |
| The guide trim drops a rule a case grades | Unfair case | The "every rule stated" audit (section 1.2) |
| The failure sentence is wrong: K or V-msg dominates instead of B | Weaker story | Two counter-intuitive families with mutants; trial labels decide |
| The frontier lands above 0.6 anyway | Saturation | Re-weight within the fair levers after the first trials; never hide rules |
| The heavy grading image (release build plus recording) at upload | Upload time | Build time measured in Phase B; the release stage is shared with the working machine's image |
| Third language toolchain after Goose and BasedPL | Diversity criticism | New domain and new outputs |
