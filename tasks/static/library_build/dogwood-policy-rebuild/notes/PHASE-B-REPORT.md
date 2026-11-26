# Dogwood rebuild: Phase B report (2026-11-27)

Author notes, never shipped. The brief is harbor-lh
`ops/swe-marathon-v2/next-tasks/library-picks-phaseB-BRIEF.md`; the plan it follows is
[SPIKE-PLAN.md](SPIKE-PLAN.md). Everything ran in local Docker Desktop (linux/arm64, natively),
under the shared heavy lock. Nothing touched Oddish.

## 1. Verdict: GO

| Check | Result |
| --- | --- |
| The 1.2.0 release from its published lock, offline | Builds in 179 s (cgroup peak 2.82 GB). It reproduces all 93 shipped example bundles byte for byte: 93 `validate` runs accept, 93 `explain.out` and 56 replay `expected.out` match |
| Determinism, 3 + 1 | 3,758 private cases × 3 runs: every case has one answer after normalisation. 3,733 are byte-identical; the other 25 differ only in the order of a rule list. A fourth run with 1 CPU, a long `TMPDIR` and `umask 077` matches all 3,758 |
| 10 repeats of multi-permit bundles | 40 cases × 10 runs: 40 of 40 stable after normalisation. 10 of the 40 give a different byte stream on every run, only in rule-list order, so rule lists must compare as sets (they do) |
| M-dedup and M-scope from patched source, with family signatures | M-dedup **0.83** (only B-dedup drops), M-scope **0.95** (only B-scope), M-naive **0.78** (both B families), M-global **0.85** (only K). Each signature is single-family |
| Milestone: oracle 1.0, empty 0 | Through the grading image: upstream's source **1.0** (3,758 of 3,758; an 83 s build, 101 s in all), the empty submission **0**, the M-dedup source **0.83** |

**What changed from the Phase A plan:**
1. **One step** (the owner, 2026-11-26; section 2).
2. **A glibc build, not static musl.** The musl build compiled (119 s, 3.02 GB peak), but it gave
   36 of 56 shipped replay streams wrong, at random: Cedar evaluations failed with "recursion
   limit reached". Cedar guards its recursion with `stacker`, and under musl `stacker` misjudges
   the main thread's stack. The glibc build gives none wrong. SPIKE-PLAN S2 named exactly this
   fallback: "a glibc build with mode 2711". The setgid bit makes the loader run in secure mode,
   so `LD_PRELOAD` is ignored; the unreadable file makes the process non-dumpable.
3. **No 1.1.2 build.** It was started, then stopped when the single-step change arrived. Its lock
   is vendored in the cache, should the chain come back.
4. **The generator needed Python 3.12.** Upstream's conformance generator uses backslashes inside
   f-string expressions. A copy adapted for Debian's Python 3.11 (expressions hoisted, same order,
   same output) is backed up privately with its licence and a note of every change.

## 2. The single-step switch (the owner, 2026-11-26)

"we dont have to promote multi-turn as well so make stuff likewise". The task is now the single
1.2.0 rebuild that the chain kept as its fallback:
- one session of 34,560 s;
- the flat layout (`instruction.md`, `environment/`, `tests/`, `solution/` at the task root);
- step 2's verifier and families, unchanged.

The two-step plan and its briefs stay in [STEPS.md](STEPS.md) and
[parked-two-step/](parked-two-step/), marked "parked by the owner, 2026-11-26". The 1.1.2 anchor
check (0.55-0.80) went with it. Commit `7cb59e1`.

## 3. Difficulty (the owner: "difficult enough")

Target: frontier at about 0.6 or less, mid-tier 0.1-0.4, with fair levers only. Every graded rule
is stated in the shipped guide. The levers ([DESIGN.md](DESIGN.md) section 3a):
- a second counter-intuitive family, K (key-local slicing), at 0.15 with its own mutant;
- aggregation plus `validate` at 0.40 of the weight;
- R (the easy replay core) down to 0.20;
- dual pairs in B-dedup, B-scope, K and V.

The estimate is frontier near 0.52 and mid-tier near 0.25. The mutant proofs still land where
planned after the reweighting (section 4.4).

## 4. Spike results

### 4.1 Downloads

All under `~/Documents/github/Abundant/lib-tasks-cache/dogwood-policy-rebuild/`, with
`downloads/SHA256SUMS`.

| # | Item | How | Size | SHA-256 or digest |
| --- | --- | --- | --- | --- |
| D1 | Dogwood 1.2.0 source, tag commit `8ffd2106` | curl, codeload.github.com | 6,734,991 B | `5e207e35431fcd4dd6045c5029663e18cb667c40be92a883dfc6adea69a3c82a` |
| D2 | Dogwood 1.1.2 source, tag commit `929f49e7` | curl, codeload.github.com | 4,689,825 B | `79d3b1263a2448c1a552707ae47ab0699e0769692e648e820b5a54a819e44680` |
| D3 | `dogwood-cli-1.2.0.crate` (its `Cargo.lock` is the published one; vcs sha1 `8ffd2106`) | curl, static.crates.io | 26,868 B | `2390e687a9101ba29a7a949bef711c5d6ae5926dcdecd427d71d9424f3c211b0` |
| D4 | `dogwood-cli-1.1.2.crate` (published lock; vcs sha1 `929f49e7`) | curl, static.crates.io | 31,981 B | `306ef7e702d15ca8dd8d2fceb5bfb084838328032b5c78a67290680d594413ff` |
| D5 | `rust:1.100.0-slim-bookworm` (rustc and cargo 1.100.0) | docker pull | 1.13 GB | index `sha256:bb875b0f8ce726053e259034848c471840e96bfe591fd52556178ae9a05e6126` |
| D6 | `rust-std` for the musl targets | rustup in the spike's toolchain image (hash-checked) | in that image | rustup manifest |
| D7/D8 | 305 crates, the union of both published locks (`cargo vendor --locked --versioned-dirs`) | cargo, checked against the locks | 284 MB unpacked | per-crate `.cargo-checksum.json` |
| D9 | `debian:bookworm-slim` | not needed: the Rust image is the base everywhere | 0 | n/a |
| D10 | Debian bookworm `python3` 3.11.2 and `musl-tools` 1.2.3 | apt in the toolchain image | in that image | apt signatures |

**S1 check.** The 1.2.0 tag and the Phase A clone of `main` (`c7124710`) differ only in CI
workflows, `AGENTS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md` and Lean files. The clone also holds
Cedar's fuzz corpus, which the tag's tarball leaves out. The crates, the guide and the examples are
identical, so the Phase A measurements hold for the tag.

### 4.2 Builds

| Build | Time | Peak memory (cgroup) | SHA-256 |
| --- | --- | --- | --- |
| 1.2.0 release, glibc, `--locked`, 6 jobs | 179 s | 2.82 GB | `f0a00b1e501b65f0be9772f2dd8e2fabb8e1b8f0f3dd62b26816e4939ab792b6` |
| 1.2.0 release, static musl (dropped) | 119 s | 3.02 GB | `e54cf715…` |
| M-dedup, M-scope, M-naive, M-global (incremental, patched `dogwood-language` through `[patch.crates-io]`) | 23-27 s each | 1.08-1.14 GB | `a4069a6e…`, `f0893a16…`, `c2521660…`, `60533527…` |

Mutant patches are in the cache (`work/spike/patches/`):
- **M-dedup:** aggregation keeps every matching row (a bag) instead of projecting onto the `for`
  domain.
- **M-scope:** an aggregate body with no past operator reads the whole history.
- **M-naive:** both.
- **M-global:** upstream's relativisation pass is skipped, so `previous` and the left of `since`
  read the global trace while predicates stay pinned.

### 4.3 The first case set

Generated into Git-ignored `tests/private/` and backed up (section 5).
- **Sources:** upstream's generator (temporal, traces, events, providers, macros; adapted for
  Python 3.11) plus 40 dual pairs each for B-dedup, B-scope and K from `scripts/pairs.py`.
- **Size:** 418 bundles, 3,758 cases, 6.4 MB. 102 generated bundles were dropped because their
  traces repeat or reverse a timestamp, which the brief puts out of contract.
- **Commands:** `replay` (human and JSON, per trace), `validate` (human, and JSON as V-msg),
  `explain` (both), `lower --emit` (both) and `check-parse`.
- **Speed:** the slowest case takes 0.157 s. The grader runs all 3,758 cases in under 20 s, after
  an 83 s build of the submission.

| Family | R | B-dedup | B-scope | K | V | V-msg | L | M | P | X | F |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cases | 300 | 160 | 160 | 160 | 418 | 418 | 836 | 24 | 28 | 836 | 418 |

**Tagging is checked by the mutants** (`scripts/retag.py`). `make_cases.py` tags a case by what its
policy and trace contain. That over-counted: none of the unpaired cases it put in B-dedup (60),
B-scope (6) or K (122) changed under the matching mutant. They still check core replay, so they
move to R. B-dedup, B-scope and K are now made only of dual pairs. Before the retagging, M-dedup
scored 0.932 and M-global 0.963, because uninformative cases diluted their families.

### 4.4 Mutant signatures (after the retagging)

| Mutant | Score | Families below 1.0 | Predicted |
| --- | --- | --- | --- |
| M-dedup | 0.83 | B-dedup: 0 of 40 pairs | 0.83, within S5's 0.70-0.85 |
| M-scope | 0.95 | B-scope: 0 of 40 pairs | 0.95 |
| M-naive | 0.78 | B-dedup and B-scope: 0 of 40 pairs each | 0.78 |
| M-global | 0.85 | K: 0 of 40 pairs | 1 − 0.15 × the share it fails |

Over upstream's 56 shipped replay bundles, no mutant changes any stream, as S5 predicted for
M-dedup and M-scope; M-naive and M-global change none either. So the shipped examples never show
the two rules at work. The guide states both, and the agent can run the build on bundles of its
own, so they stay discoverable. Copying the examples' behaviour is not enough, which is the point
of the failure sentence.

### 4.5 First stub estimate (analytic, from the recorded results)

How often a stub's output would equal the recorded result, per family, counting a pair only when
both members match. No stub was built; these are computed from the recorded results.

| Stub | Raw score | Families it reaches |
| --- | --- | --- |
| Z2 prints nothing, exits 0 | 0.007 | R 0.027, M 0.042 |
| Z4 `validate` always prints the accept line | 0.143 | **V 0.797, V-msg 0.797** |
| Z6 `replay` prints DENY for every event | 0.069 | R 0.247, M 0.25, P 0.143 |
| Z7 `replay` prints ALLOW `[rules: 0]` for every event | 0.045 | R 0.207, P 0.071 |
| Z9 `check-parse` counts policies | 0.000 | F 0.017 |

B-dedup, B-scope, K, L and X are at 0 for every stub. **V and V-msg are not yet usable:** 80% of
the generated bundles are valid, so a stub that always accepts passes 80% of them. They need the
planned accept/near-miss pairs (one near-miss per stated rule) before any QA pass. R, M and P need
fewer single-verdict streams, or pairing. Until then the baseline subtraction would squash honest
credit in these families.

## 5. The first build milestone

| Item | Status |
| --- | --- |
| The task image builds the release from pinned source | Done. `environment/Dockerfile` and `tests/Dockerfile` share one release stage: the published crate (checksum-pinned `ADD`), `cargo vendor --locked`, an offline `--locked` build with `experimental-arithmetic`, the four `dogwood-*` crates removed from the registry. First image builds: working machine 133 s, grading image 69 s (the release stage is shared) |
| The working machine as the agent sees it | `dev` (uid 1000); `/usr/local/bin/dogwood` is mode 2711, `root:dogwood-run`, and prints `dogwood 1.2.0`; reading it is refused; the registry has 275 crates and no `dogwood-*` crate. Probe as `dev`: reading, copying, `dd`, `/proc/<pid>/{exe,mem,maps}` and `PTRACE_ATTACH` are refused; a `PTRACE_TRACEME` read of its memory fails with `EIO` (the same read of `/bin/true` works); `LD_PRELOAD` is ignored (the same library runs in `/bin/true`); the running process holds egid `dogwood-run`; no `sudo`; `/root` cannot be listed; no `dogwood-*` crate or source anywhere on disk. The grading image has no file named `dogwood*` |
| The verifier skeleton runs | Done. It builds the submission offline as `builder`, runs each case as `nobody` in a fresh directory with 5 s and 2 GB, and scores families |
| The generator emits the first families into `tests/private/` | Done (section 4.3) |
| Upstream scores 1.0, the empty submission 0 | Done: 1.0 (all 3,758 cases) and 0 (no `Cargo.toml`, so nothing builds). The M-dedup source, built the same way, scores 0.83 |
| Public parts committed, private parts backed up | Public parts: section 7. Private parts: `dogwood-tests-private.bundle` (cases and seeds) and `dogwood-generator-adapted.bundle` in harbor-lh `ops/swe-marathon-v2/next-tasks/dogwood-policy-rebuild-private/` |

**A grader bug the milestone caught.** The first grading run scored everything 0, the oracle too.
The grading image keeps its private files readable by root only. The runner copied each bundle
with those modes, so `nobody` could not read the policy, and every run printed nothing. The runner
now gives the run's own copy to the user it runs as. The spike had not caught this because it ran
cases from a host mount with ordinary modes.

**Separate-verifier format** (forge `TBS_VERIFIER_FORMAT.md`):
- **Declared artifact:** `/app/dogwood-rebuild` only (root-level `artifacts`). The grader reads
  nothing else under `/app`, and writes only `/logs/verifier`.
- **Baked into the grading image:**
  - `test.sh`, `verify.py` and `verifier/`;
  - the private cases and bundles;
  - gold, recorded at image build from the release build, which itself stays out of the final
    stage;
  - the vendored registry (275 crates, no `dogwood-*`) and its cargo config;
  - the `builder` user (`nobody` exists already).
- **Network:** `[verifier] network_mode = "no-network"` is the grading phase's override. Harbor
  0.25 treats `[verifier.environment] network_mode` as the baseline, which stays `public` because
  the image build fetches the crate and vendors from crates.io.
- **Baselines:** locally, the oracle scores 1.0 and the nop 0 in this separate setup. The four
  Oddish trials (oracle ×2, nop ×2) wait for the owner's go.

## 6. Resource use

- **Heavy jobs:** 9, one at a time, each under the shared lock and started at 30% or more free
  memory. They took 37 minutes of machine time in all. Waits before a job were 0-24 minutes, mostly
  for memory below 30% free; twice the lock was held by the HarfBuzz or the Weave author. No stale
  lock was taken over.
- **Containers:**
  - every container ran with `--memory=4g` and `--cpus=6` or less;
  - each private case runs under `RLIMIT_AS` of 2 GB;
  - the image builds (BuildKit) cannot take `--memory`, so their release compile is held to 4 jobs
    (`CARGO_BUILD_JOBS=4`). The same compile peaked at 2.82 GB with 6 jobs.
- **Peak memory:**
  - 3.02 GB for the musl release build;
  - 2.82 GB for the glibc release build;
  - at most 1.14 GB for each mutant build.
- **Disk:**
  - the cache folder: 680 MB (downloads 11 MB, sources 69 MB, vendored crates 284 MB, binaries
    135 MB, runs 34 MB, work 118 MB, milestone 29 MB);
  - Docker at its peak, about 21:05 UTC: the Rust image (1.13 GB), the toolchain and both task
    images (2.11 GB of their own), and 1.6 GB of build-cache records left by superseded builds.
    With the cache folder that is about 5.5 GB, over the 5 GB budget for about half an hour.
    During the spike, the build volume (up to 1.28 GB) took the space the task images took later;
  - after cleanup: **1.81 GB**: the cache folder and the pinned Rust image, kept as the next build's
    base.
- **Cleanup** (about 21:30 UTC):
  - no container of ours was left;
  - the build volume was removed by name in the milestone job;
  - the three images (`dogwood-spike-toolchain:2`, `dogwood-env:milestone`,
    `dogwood-verifier:milestone`) were listed, then removed by exact name;
  - 46 BuildKit cache records from our Dockerfiles were removed one exact ID at a time. Each step
    checked that the record count fell by at most one and that another campaign's 656 MB record
    was still there. Nothing else was pruned.

## 7. Commits

On `neel/dogwood-policy-rebuild`, each pushed:
- `7cb59e1`: the single-step switch and the grader skeleton;
- `43441f0`: the glibc release build, the runner fix, the mutant-checked family tags, and the
  measured mutant proofs in DESIGN.md;
- the commit that adds this report, the README's development log and its hackability table.

## 8. Next steps

1. **Docs:** trim, scrub and fix the 1.2.0 guide and examples into `/app/docs`
   ([DESIGN.md](DESIGN.md) section 1.2). Then the "every rule stated" audit. The working machine
   has no docs yet, so the brief's `/app/docs` does not exist.
2. **Cases:**
   - V accept/near-miss pairs;
   - K beyond its one shape: the left of `since`, a pin that is not universal, the mirror rule,
     rejected events;
   - `format` and `schema` cases (F has only `check-parse` so far);
   - fewer single-verdict replay streams.
3. **Coverage:** `features.yaml` from the trimmed guide, the kill matrix, the stub zoo built for
   real, and `baselines.json`.
4. **Leak scan** against the shipped examples and upstream's public corpus.
5. **Timing:** an upstream-sized submission builds and runs all cases in 101 s. Size the
   verifier's timeout (now 4,500 s) once the case set is final.
6. **x86_64:** no emulated amd64 sample was run. The platform's own image build records gold on
   x86_64, and the oracle and nop baselines there are the proof.
7. **The 20 QA passes,** with forge's `TBS_VERIFIER_FORMAT.md` and `TASK_HYGIENE.md` given to the
   author and an independent reviewer of the final bytes. Then the Oddish gate with the owner's
   go.
