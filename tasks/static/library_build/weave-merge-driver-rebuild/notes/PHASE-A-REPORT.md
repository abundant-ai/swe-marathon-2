# Weave merge-driver rebuild: Phase A report (2026-11-26)

Phase A (design only) is complete. Nothing was downloaded, built or run; no Oddish, no Docker. The
deep dive's clones were read only. Dates, tags, histories and sizes came from the GitHub, crates.io
and Hacker News APIs and Cursor's page text.

## Outcome

Weave stays a credible third pick on paper, with three corrections. The suggested step split was
built on a misread history (the gate shipped in 0.6.0, not 0.7.1). The specification must be
written from the `v0.7.1` tag, not from the later commit the deep dive read. The gate family needs
paired accept-duals, because the gate's fallback output is partly reproducible by trivial stubs.
None of these sinks the task; all three are now in the design. Probation still turns on the
three-day spike, which now has two more gates: the oracle must build from the agent's own crates,
and the owner must approve vendoring `sem-core`.

## Panel decision (steps)

Opus voted C (0.5.4, then the 0.6.0-0.7.1 releases, built in stages with A first), sonnet B (0.6.2,
then 0.7.1) and haiku A (one step now). With no majority, the tie rule picks the more conservative
option: **build the single step (A) first.** The chain is decided on spike days 4-5 by each judge's
own measurable condition. All three agreed on `final` for any chain, on A as the base of every
option (Proximus refuses `[[steps]]`), and on one idle full-length chain before any model trial.
Record: harbor-lh `ops/swe-marathon-v2/decisions/2026-11-26-weave-merge-driver-rebuild-steps-DECISION.md`
(brief and votes beside it).

## Steps and acceptance criteria (`STEPS.md`)

| Plan | Steps and budgets | Families graded | Original's score | Acceptance before upload or adoption |
| --- | --- | --- | --- | --- |
| **A (adopted)** | one step, 34,560 s | F1-F10, about 1,200 cases, F8 gate 20% | 1.0 | oracle 1.0 x2 and nop 0 x2; stub zoo 0.000; at least 3 kills per feature and 1 per restriction; M-gate 0.80 with F8 alone moving; 3+1 identical; verifier within 30 min; clean cue sweep and protection probe; a graded full-length flat canary |
| C (designed) | 01 rebuild 0.5.4, 14,400 s; 02 follow 0.6.0-0.7.1, 20,160 s; `final` | step 1: F1-F5, F7, F10 plus the statement fold, about 400 cases (diagnostic); step 2: A's cases | 1.0 per step | 0.5.4 build 3+1 identical; a 0.5.4 build scores 0.25-0.70 on A's cases with F8 at 0; the step-1 set survives the filter; `sem-core` 0.23 vs 0.29 differences known; independent spec review; step-2 material invisible in step 1; oracle chain 1.0/1.0, nop 0/0; idle chain graded in both steps within 43,200 s |
| B (designed) | 01 rebuild 0.6.2, 26,000 s; 02 follow 0.7.0-0.7.1, 8,000 s; `final` | step 1: F1-F10 at 0.6.2 (diagnostic); step 2: A's cases plus at least about 100 step-2-only layout cases | 1.0 per step | at least about 100 step-2-only cases; a 0.6.2 build scores at most 0.85 of 0.7.1 on A's cases; a steps-layout heavy-verifier canary graded at the cap 2 of 2 |

Author's prediction (unmeasured): B fails its own condition (0.6.2 and 0.7.1 differ by about 120
merge-path lines); C may qualify.

## Validity of the reasons (`VALIDITY.md`)

43 claims: **21 verified, 14 verified with a correction, 1 invalid, 7 unverified here.**

- **Invalid:** the suggested split, "0.6 engine, then 0.7.1's gate and changes" (C34). The gate,
  region rules and element union shipped in 0.6.0 on 2026-10-19; within scope, 0.6.x to 0.7.1 is
  `region.rs` +79/-40 and `binding.rs` +29/-13 in 0.7.0 and nothing in 0.7.1. Fix: the panel
  above.
- **Corrections that change the design:**
  - the deep dive's clone is nine commits past the tag, and two of them change `verify.rs`
    (TypeScript definition keys; `.qmd`), so the specification comes from `527ccb3` (C33);
  - 0.7.1 changed no merge-path file, so the graded engine is 0.7.0's, which crates.io and docs.rs
    have shown since 2026-10-30 (C32);
  - the oracle needs a small patch to build with the agent's crates (no `git2`, `rayon`, `memmap2`)
    (C20);
  - a sixth undocumented constant, `REHOME_MIN_OVERLAP = 0.6` (C24);
  - the hint line carries the `-p` path even with standard markers (C23);
  - non-UTF-8 input also exits 2 (C22).
- **Other corrections:**
  - Cursor's 70,000 conflicts accrued "before we paused it", not within the two hours (C11);
  - the incident was "two features", not "two agents" (C12);
  - the 344-of-4,971 replay used the pre-gate 0.5.3 engine and `diffy` as the line baseline (C30);
  - 0.4.0 was never tagged or released (C9);
  - the composition ladder is richer than "diffy, then git" (C36);
  - M-gate lands at exactly 1 - w (0.80 at 20%) (C35).
- **Unverified (spike or later):** the `sem-core` 0.29 extraction size, no clock reads, the stub
  yield, execute-only on this binary, the external benchmark lists, the root-commit count, and
  the private endorsements (not load-bearing).

## Failure sentence and proof plan

> A capable agent merges edits to different definitions correctly, but returns clean merges where
> 0.7.1 refuses, because its own composition looks valid line by line. It does not check the
> composed file for a name declared twice, a repeated key or case label, a renumbered `iota`
> constant, a name left unbound, or a file that no longer parses or loads. Nor does it fall back to
> the one whole-file conflict box 0.7.1 writes when git's line merge is clean but fails the same
> checks.

**Documented.** Specification chapter 12 covers each check per language, the line arithmetic and
the fallback. The instruction's landing-agents paragraph covers the stakes. One probe shows it:
both sides add `case 3:`, and git is clean but the build exits 1.

**Plausibly missed.** The gate is low-frequency. It is broad: six checks across three languages
and two formats, behind about 2,000-2,700 code-only lines. It runs against the prior of git,
Mergiraf and Weave before 0.6.0. Its fallback is layered.

**Proof.** M-gate is the tag's source with four call sites forced to pass: `verify::verify`,
`iota_refusal`, `duplicate_keys` (the `keys_hold` backstop), and `take_superset`'s data check. The
element union's own guards stay.

- F8 is defined as the cases where the original and M-gate disagree, plus at least as many paired
  accept-duals.
- Expected signature: F8's net credit falls from 1 to 0, every other family stays at 1.0, and the
  overall score is 0.80.
- The signature must be unique among about twelve mutants. F8 must also rank hardest on the
  code-share proxies.
- After the first trials, F8 should be the lowest net family, and most failed refusals should be
  clean exits.

## Exact download list (`SPIKE-PLAN.md`, `download-crates.tsv`)

Nothing is fetched until the owner approves.

| Group | Items | Size |
| --- | --- | --- |
| Base | `ubuntu:24.04@sha256:73b99939...` (Goose's digest) | about 29 MB |
| System (apt, one snapshot date) | `git` 2.43.0 series (one pinned package version), `build-essential`, `pkg-config`, `python3`, `ca-certificates`, `curl`, `procps`, `util-linux`; `strace` and `gdb` in the probe image only | about 300 MB installed |
| Rust | `rustup-init`; a stable toolchain of at least 1.85, minimal profile, exact version recorded | about 15 + 110 MB |
| Upstream | `weave` `v0.7.1` source (`527ccb3`); optional release binary `weave-driver-x86_64-unknown-linux-gnu.tar.gz` (8,434,507 bytes) and `checksums.txt`; days 4-5: `v0.6.2` and `v0.5.4` source | about 1.5 MB each; 8.4 MB |
| Crates | 82 for the agent's registry (14.5 MB); 140 more for the original's build (35.9 MB); every name, version, size and sha256 in `download-crates.tsv`; re-derived from the tag's lock first | 50.3 MB |
| Corpora (optional) | `pallets/flask` (BSD-3-Clause), `colinhacks/zod` (MIT), `spf13/cobra` (Apache-2.0), one pinned tag each | about 3.5 MB |

Everything is built on a Linux x86_64 host with Docker, never on the shared Mac.

## Commits

swe-marathon-2, branch `neel/weave-merge-driver-rebuild` (pushed after each; no PR opened):

| Commit | Deliverable |
| --- | --- |
| `e4a5ad5` | skeleton: instruction, `task.toml`, README with development log, ignore rules |
| `0135866` | `notes/DESIGN.md` |
| `3ab158a` | `notes/STEPS.md` and `notes/steps/` |
| `03cb1e9` | `notes/VALIDITY.md` (its message miscounts the tally by one; the table is right) |
| `5dca4a2` | `notes/QA-PLAN.md`; modularity wording aligned with Carve and BasedPL |
| `a1c992d` | `notes/SPIKE-PLAN.md` and `notes/download-crates.tsv` |
| this commit | `notes/PHASE-A-REPORT.md`, README log, the validity tally |

harbor-lh `neel/swe-m2-ops` (via `push_ops.sh`):

- `4e18102`: the panel brief, three votes and the decision.
- `e6e2f6b`: the private folder with its placeholder bundle and the Phase A analysis tools.

## Judgment calls

- **Single-step skeleton.** The skeleton is flat, and the chain drafts sit in `notes/steps/`. This
  follows the tie rule, and the repository allows only implemented steps in `task.toml`.
- **Authors field.** `task.toml` carries the owner's name and work email, as every task in the
  repository does. The repository requires it. The brief's "no emails or names" rule was read as
  covering trajectory and third-party material.
- **Placeholder folders.** `tests/` and `solution/` hold only `.gitignore` files, because Git keeps
  no empty folders.

## Next

1. The owner approves the download list and the vendoring of `sem-core`.
2. The spike (days 1-3), then the chain measurements (days 4-5).
3. Go or no-go on the third pick.
