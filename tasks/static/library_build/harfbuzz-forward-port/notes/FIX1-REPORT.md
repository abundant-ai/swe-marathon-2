# HarfBuzz forward-port: QA fix round 1

Author notes, never shipped. 2026-11-27/28. The independent QA round (21 passes: 12 FAIL, 5 CONCERN, 4 PASS;
harbor-lh `ops/swe-marathon-v2/qa/harfbuzz/SUMMARY.md`) gave ten must-fix and seven should-fix items, and the
three-judge panel on the failure sentence (`ops/swe-marathon-v2/decisions/2026-11-27-harfbuzz-failure-sentence-DECISION.md`)
added M11. Each report a finding cites was read before its fix. Three subagents did part of the work under the
author's review: the case fixes (M2, M4, M9, M10, S11 and draft restatements), the verifier hardening (M5-M8, S1,
per-case logging) and the specification paraphrase (S2). Rules held throughout: the shared heavy-job lock and the
memory gate, `--memory=4g` containers, no Oddish upload or run, no PR edits, push after every commit, the session
left at 34,560 s with no stated budget.

What did not change: the reward formula and its weights (reward = D x h_d x (1 - 0.10 (1 - h_b))), the 53 graded
units, the case counts per kind, and the session length.

## Items

| Item | QA finding (pass) | What changed | Evidence | Commit |
| --- | --- | --- | --- | --- |
| M1 | `instruction.md:58-60` framed the work as matching the 14.3.0 build "for every font, text and setting" (02) | The two bullets now say it in the requester's terms: each fix works wherever its note applies, in whatever fonts and texts customers bring; apply it there and nowhere else, and whatever the notes do not change stays as the 14.3.0 build has it, in everything the layout engine reads | Cue sweep over `instruction.md` and `environment/`: 0 hits (`prune_tree.sh` is deleted by the image build after use; gate item 6 skips it) | de387860 |
| M2 | 16 of unit 25a's 60 changed cases expected CoreText's undocumented `kerx` format 1 history (commit 90417543f), which the shipped digest contradicts (03, 04, 06, 16, 17, 21) | A partial revert `rk-25a-hist` (15.1.0 without 90417543f alone) is built and run; `classify.py` marks a 25a case `beyond-note`, never graded, when that build moves it. `Chap6kerx.md` now states format 2 addressing one way (pass 04 finding 6) | c3 sweep: 90 candidates of unit 25a are `beyond-note` (all `kerx` format 1, as the format 1 simulator predicted: 90 of 166 depend on that history); 241 changed remain (76 format 1, 165 format 2) and 60 are graded; `rk-25a-hist` reverts that one commit on 15.1.0 | 3779de18, b1b4a2f1 |
| M3 | The notes of cut units 28, 30 and 50 stayed in the instruction with no case (03, 21) | Removed from `instruction.md` and `notes.md`; the list of what was left out names color bitmap format 19 and "two fixes that change nothing our product can observe". Unit 37's clause on scaling glyph extents, which no case checks, is gone too | Gate item 1: each of the 48 notes in `notes_map.tsv` has graded units with at least 36 changed cases each | de387860, d7ddf4b0 |
| M4 | No-op bodies of the new functions 48, 49 and 51 earned credit (09) | `hbapi49` ends each case with a call that finds glyphs (`also=`), `hbapi51` with a second call that consumes well-formed input (`then=`); `hbapi48` already failed a no-op everywhere. Unit 49's cases on a font without `JSTF` are left out (`x:no-jstf`). New stub `noop-api`: the four declarations copied from the notes into the headers they name, with bodies that return NULL, 0 or false | `stub-noop-api` through the verifier: all four probes compile and run, 0 of 60 graded cases pass on each of 48, 49 and 51, D 0, reward 0.0 | 3779de18 |
| M5 | The delivered tree could forge or keep a reward (07, 11, 21) | Root-only `/var/lib/hbv` and root-owned 0755 `/logs/verifier`, opened through folder descriptors with `O_NOFOLLOW|O_EXCL`; case programs get input and output only as files root opened; every `builder` process killed after each step and batch and at the end; existing reward files removed; `metrics.json`, then `reward.txt`, written last into reserved space; fixed uid, no new privileges, `verify.py` root-only | Hostile tree (the 14.3.0 tree whose build and library attack every route): reward 0.0 in a regular file written by root, no `reward.json`; the notes show builder processes left after setup and after the build, killed; about 900 links it planted in the logs folder (Docker Desktop's file sharing let it) moved nothing | f86259ea |
| M6 | Timeouts covered only the drivers, not the build; no global bound (11, 13) | One 1,800 s deadline covers the copy, the build and every batch; each step gets what is left; what has not run fails and a reward is still written; a last-resort alarm at 2,100 s, inside the 2,400 s verifier timeout | Slow tree (setup sleeps 600 s, the build 1,500 s more): setup exit 0 in 607 s, the build stopped at what was left of the deadline (1,192 s), every case failed, reward 0.0 written 1,800 s after the start. Hanging tree (the library spins in its first shaping call): batches that shape stopped at 125 s (14), 227 batches (4,392 cases) not run once the time was up, reward 0.018 written at 1,806 s | f86259ea |
| M7 | Output reads were capped by file size, not by bytes read (11) | At most 16 MiB + 1 byte of a batch's output is read (more fails that batch only); 64 MiB file-size and 4 GiB address-space limits on case programs; step logs keep their last 4,000 bytes | Flood tree (each shaping call writes 4 GiB): the 141 batches that shape failed with "output over 16 MiB", the other 261 scored as the reference (reward 0.074); the run took 79 s and left 148 KB of logs | f86259ea |
| M8 | No stop of `dev`'s processes before collection; no defence against a whole-release drop-in (08) | A root `[[verifier.collect]]` hook kills every `dev` process (`kill -9 -1` as `dev`, `pkill -u/-U`, until none is left; gives up after 60 s). Tripwire: a 15.x version in `meson.build`, `src/hb-version.h` or `NEWS`, or any of the 15 unit-test sources only 15.x has (sha256), and the tree is not built and scores 0. The reference keeps the tree's version and leaves those tests out; `make_solution.py` refuses a tree that trips it; the instruction now says the tree stays version 14.3.0 | Drop-in tree (the 15.2.0 release itself): not built, reward 0.0 in under a second, all 18 markers listed; the oracle, the `solve.sh` tree, V and W: none. The hook, run as root in the agent image against 22 `dev` processes (a stopped one, one in its own session, a forking loop, a `nohup` one): 0 left after 139 ms, exit 0 | f86259ea |
| M9 | 8 of unit 29's duals sat inside the note's literal wording (05; 04 finding 4) | `b:after-lvt` is now `x:after-lvt` (never graded); the 30 duals come 10 each from the other three boundaries; the note is tightened to a syllable without a final consonant (S6) | c3: unit 29 has 60 changed cases and 30 duals, 10 each on `b:grapheme-level`, `b:jamo-sequence`, `b:modern-trailing` | 3779de18, d7ddf4b0 |
| M10 | Unit 39's `b:degenerate` duals were mislabelled (05) | `x:degenerate`; `b:outline` and `b:unsynthetic` checked: every edge a whole number, so note 38 cannot move them; duals 15 and 15 | c3: unit 39 has 60 changed cases and 30 duals, 15 on `b:outline` and 15 on `b:unsynthetic`; W's h_d rises from 0.684 to 0.691 | 3779de18 |
| M11 | Failure sentence (17; 20, 09), decided by the panel on 2026-11-27 | The verification-gap sentence; tiers (14 A, 20 B, 19 C, `tiers.tsv`, DESIGN.md section 10); proof mutant V; R_unbuilt and W_literal; pre-registration with five kill conditions (`notes/PREREGISTRATION.md`, committed before any run); W relabelled a secondary bound; D, h_d and h_b reported separately; per-case verdicts in `metrics.json` only; README failure-mode, difficulty and hackability text | V through the verifier 0.684591: D 0.6846, h_d 1.000, h_b 1.000; tier means A 1.00, B 1.00, C 0.12; D lost only on tier-C units. See "The verification-gap proof" | c43080a0, 23f51390, 749fe231, 3d79861c, f8b81b3d, 02e97477, 2a69bd25, f86259ea |
| S1 | `hbmeta` and `hbapi48` print raw float bits; FMA paths on real amd64 untested (10) | Case programs run with `GLIBC_TUNABLES=glibc.cpu.hwcaps=-AVX2,-FMA,-FMA4` (glibc 2.33+ spelling; libm takes its SSE2 paths) | The expected outputs, recorded through the amd64 verifier under the pin, equal the pipeline's on all 5,256 cases; the 3+1 recordings are byte-identical | f86259ea |
| S2 | Verbatim runs of 128-263 words in five spec notes; no licence notice; fonts shipped without their OFL (15) | 30 notes paraphrased (no 9-word prose run left against their own page or all 51 pages); `specs/NOTICE.md` (sources, titles, URLs, the sources govern, what is carried over, copyrights, the Unicode License V3); the verifier's Noto fonts ship with the OFL 1.1 text and a notice of each font's copyright (all 15 are OFL per name ID 13; the notofonts site licence is Apache-2.0 and no longer shipped) | 30 files changed; longest remaining runs are tables (mvar 262, use 219, scripttags 215, hebrew 171, tr29 127) | f997351a |
| S5 | Requester wording (01) | Why only release notes (an air-gapped build network); why a freeze takes the Unicode update and new functions (customer documents, the layout engine's calls); change control and delta certification; no regression set is given | Instruction diff in de387860 | de387860 |
| S6 | Restatements never shipped; units 6 and 29 under-specified (04) | Decision recorded: narrow the cases, not the notes. Pass 04 found every other unit determined by upstream's wording, the specs and the 14.3.0 code; units 6, 29 and 37 now state their rule. The fuller texts for ten more notes stay unshipped in `notes/RESTATEMENTS.md`; DESIGN.md risk 3 closed | Instruction diff in d7ddf4b0 | d7ddf4b0 |
| S9 | No recorded offline run of upstream's suite; dangling perf/.ci references; offline build (19) | `--wrap-mode=nodownload` in the product's, pipeline's and verifier's setup; `README.mingw.md` removed and `TESTING.md`'s profiling section cut by `prune_tree.sh`; the `util/` hint names its options | Offline in the agent image (native arm64, `--network=none`, 4 CPUs): setup 1 s, compile 85 s (419 targets), `meson test` 3 s: 244 of 245 passed; `shape_threads` aborted because its inputs are in `perf/`, so the prune now drops that test (6f9ea68f). The new prune lines, run with GNU sed and grep on a copy of 14.3.0's `test/threads`, remove the test cleanly and leave a valid `meson.build`; the re-run on the rebuilt image is pending (see "Left open") | de387860, f86259ea |
| S10 | `DESIGN.md` lines 37-40 stale against what ships (12) | DESIGN.md section 2 matches what ships; sections 4, 6-10 and 13 and the QA plan follow fix round 1 | | fb7f3765, 749fe231, 58ee9d6d |
| S11 | Unit 27 relied on whole-text flags the instruction never states (21) | Inside texts that do not open, in visual order, with a kerned pair are left out (`x:before-pair`, 275 of 442 changed candidates); on the 167 left, "flag from the first pair on" matches 15.2.0 on every one | c3: unit 27 has 60 changed cases drawn from the 167 that remain, and 30 duals (15 `b:in-stream`, 15 `b:no-pair`) | 3779de18 |

## The verification-gap proof (M11)

**Tiers** (`scripts/pipeline/tiers.tsv`, notes/DESIGN.md section 10): 14 units tier A (the note names the fix),
20 tier B (checkable on the agent's own 14.3.0 build with the shipped fonts and tools), 19 tier C: pass 16's 14
(9, 10b, 12, 16, 17, 19, 25a, 25b, 25c, 26, 27, 29, 31, 38), the AAT units 21, 23 and 24 (no shipped 14.3.0 font has
`kerx`, a vertical `kern` header or a repeated AAT feature request; upstream built new fonts to test 21 and 24), and
the Unicode 18 units 33 and 34. Units 20 and 22 are AAT units too, but their notes name the edit, so they stay in A.

**V** is 15.2.0 with every tier-C unit's commits reverted (`scripts/pipeline/assemble_reverts.py` into
`patches-lib/ALLV`, 22 upstream patches plus the hand-resolved reverts of 27 and 29; the same patches build the
pipeline's `mut-V` and, through `make_mutant.sh`, the verifier's V tree over the reference). Four commits no longer
revert on 15.2.0, because later 15.x commits rework the same lines: 25a's a92e0996d and 90417543f, 25b's 436f067b2
and 33's bf93d8671. So V keeps 25b and 33 whole and 25a at 0.283; the other 16 tier-C units are fully out.

| Run | Reward | D | h_d | h_b | Where D is lost |
| --- | --- | --- | --- | --- | --- |
| **V, through the amd64 verifier** | **0.684591** | 0.6846 | 1.000 | 1.000 | only tier C: 16 units at 0.0, 25a 0.283; tier means A 1.00, B 1.00, C 0.12 |
| V, pipeline (arm64) | 0.6846 | 0.6846 | 1.000 | 1.000 | the same units |
| V_full, all 19 tier-C units failing (estimate: 25a, 25b and 33's changed cases counted as failed, their duals and the broad set as measured) | 0.623 | 0.623 | 1.000 | 1.000 | tier C only |
| R_unbuilt, every F4 and F5 unit out (pipeline; the panel's starting point) | 0.8167 | 0.8167 | 1.000 | 1.000 | 20, 21, 22, 23, 24, 25c, 26, 27, 29 at 0.0, 25a 0.283 (25b's commit does not revert) |
| W, every conditional note widened (secondary bound), through the verifier | 0.678438 | 0.9846 | 0.6907 | 0.9767 | 9 (0.617), 7 (0.700), 40c (0.867); 44 units lose neighbours |
| W_literal, without pass 17's eight non-literal widenings (pipeline) | 0.7511 | 0.9846 | 0.7647 | 0.9767 | as W |

Per family, V: F1 0.83, F2 0.60, F3 0.33, F4 0.37, F5 0.00, F6 0.00, F7 0.67, F8 0.94. **V lands in the band
(0.60-0.85) as built and in the full estimate, loses D only on tier-C units, and leaves h_d and h_b at 1.000**, so
no re-tiering is proposed. Making V exact would take hand-resolved reverts of the four commits against 15.2.0.

**Pre-registration** (`notes/PREREGISTRATION.md`, c43080a0, tiers revised in f8b81b3d, both before any run): per
unit and per family, frontier D 0.660 and reward about 0.64 (QA pass 16: 0.54-0.75), mid-tier about 0.28, and five
kill conditions (difficulty outside 0.30-0.75; tier C not at least 0.10 below tiers A and B; implemented units
failing duals at 15% or more and three times untouched units; a family 0.25 off; a tier-C unit at 0.9 or a tier-A
unit at 0.3 in two of three runs).

**Per-case logging**: `metrics.json` (the verifier's own file) has `case_pass` {kind -> unit -> opaque id -> 0/1},
the per-unit and per-family figures, `release_markers`, `step_logs` and `batches`; stdout is still one summary line.
D, h_d and h_b are reported separately in every table here and in the README.

## The final verifier pass

c3 selection (5,256 cases: 3,156 changed over 53 units, 36-60 each; 1,500 duals over 50 units; 600 broad), expected
outputs recorded through the amd64 verifier image under the glibc pin: 0 differences from the pipeline; the 3+1
recordings (two more, one on 1 CPU) byte-identical. All runs in one hold of the shared lock (88 min, 20:50-22:18
UTC on 2026-11-27); the slow tree ran in the background beside the others.

| Tree | Reward | D | h_d | h_b | Wall s |
| --- | --- | --- | --- | --- | --- |
| oracle (shipped tree + reference change) | 1.0 | 1.0 | 1.0 | 1.0 | 76 |
| solved (`solution/solve.sh` on the shipped tree) | 1.0 | 1.0 | 1.0 | 1.0 | 76 |
| nop (the shipped 14.3.0 tree) | 0.0 | 0.0 | 1.0 | 1.0 | 67 |
| V | 0.684591 | 0.684591 | 1.0 | 1.0 | 75 |
| W | 0.678438 | 0.984591 | 0.690667 | 0.976667 | 75 |
| stub-comments | 0.0 | 0.0 | 1.0 | 1.0 | 63 |
| stub-refactor | 0.0 | 0.0 | 1.0 | 1.0 | 64 |
| stub-nobuild | 0.0 | 0.0 | 0.0 | 0.0 | 15 |
| stub-empty | 0.0 | 0.0 | 0.289 | 0.0 | 61 |
| stub-abort | 0.0 | 0.0 | 0.279 | 0.0 | 66 |
| stub-noop-api (new) | 0.0 | 0.0 | 1.0 | 1.0 | 71 |
| robust (pipe, 600 MB sparse file, 100,000 files, links out) | 1.0 | 1.0 | 1.0 | 1.0 | 98 |
| hostile (new) | 0.0 | 0.0 | 1.0 | 1.0 | 137 |
| drop-in, the 15.2.0 release (new) | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| flood (new) | 0.074215 | 0.296 | 0.279 | 0.0 | 79 |
| slow (new) | 0.0 | 0.0 | 0.0 | 0.0 | reward at 1,800 |
| hang (new) | 0.018331 | 0.159 | 0.128 | 0.0 | 1,806 |
| fault (unknown release) | exit 1, no reward | | | | 1 |

## Gate (QA-PLAN.md section 1), `scripts/gate_checks.py`

| # | Gate | Result |
| --- | --- | --- |
| 1 | Inventory | **Pass.** 48 notes, every one with graded units (53, at least 36 changed cases each) |
| 2 | Kill matrix | **Pass.** 53 units, no unit below 3, no cross-kill, every own revert kills all its unit's cases |
| 3 | Stub zoo | **Pass.** nop and all six stubs 0.0; R_all (pipeline) 0.175 because it reverts only single-commit units, 0 on those (as in Phase C) |
| 4 | Oracle and nop | **Pass.** oracle 1.0, `solve.sh` tree 1.0, nop 0.0 |
| 5 | Determinism | **Pass.** 3+1 recordings identical |
| 6 | Cue words | **Pass.** 0 hits on `instruction.md` and `environment/` (`prune_tree.sh` is deleted by the image build) |
| 8-10 | Robustness, isolation, no early stops | **Pass.** The trees above; nothing stops the session before 34,560 s |
| 12 | Band | **Pass.** V 0.685 in band, D lost only on tier C, h_d and h_b 1.000; W 0.678 and W_literal 0.751 as bounds |

Items 7 and 11 (protection probe, leak scan) are unchanged from Phase C; the packager's leak scan passes.

## Bundle and preflight

- Bundle `de0962c420fedacb364282e71e5ff33c95c3984ac2f0a024af23f62cc0062d15`: 653 files, 24.4 MB
  (`scripts/package_task.py`; the notes file matches the instruction; no patch files).
- Local `oddish preflight` (no upload): **passed**.
- The private store has `fix1/` (the c3 selection, the recorded outputs, the gate and band data, every verifier
  run's metrics), backed up as a bundle in harbor-lh `ops/swe-marathon-v2/next-tasks/harfbuzz-forward-port-private/`.

## Left open

- V keeps 25b and 33 whole and 25a in part (four commits do not revert on 15.2.0); the full estimate is 0.623.
- The reference tree's `src/meson.build` still names the 15 test programs it leaves out, so a `-Dtests=enabled`
  build of the reference would fail; the product build and the verifier never enable tests.
- Seven synthetic fonts the c2 selection used stay in `tests/inputs/fonts/synth/`; no case reads them.
- The collect hook was tested in the agent image locally; its platform run shows on the first oracle trial.
- The re-run of upstream's suite on the agent image rebuilt with the fixed prune could not start: for 90 minutes
  the shared lock was held by the game and Dogwood campaigns, or memory sat at 25-29% free, below the gate. It is
  one short job (`spike.py batch CACHE/work/plans/fix1-s9b.json`: build the agent image, run the suite offline,
  remove the image). The fix removes the only failing test, no other file in the shipped tree refers to `perf/`
  or `.ci/`, and the prune lines work under GNU sed and grep on a copy of the threads tests.
- No Oddish upload or run; QA re-check passes come next.

## Resource use

One hold of the shared lock, 88 min, after about two hours of waiting for the lock (the game, Dogwood and Weave
campaigns) and the memory gate. Containers at `--memory=4g`, two at once only while the slow tree slept (35-40 MiB
each). Afterwards the trees, the pipeline builds, the c2 outputs and all three of this task's images were deleted by
name or ID; the work folder is 376 MB.

## Commits (branch `neel/harfbuzz-forward-port`, all pushed)

| Commit | What |
| --- | --- |
| de387860 | Requester wording (M1, S5), cut notes removed (M3), offline build (S9) |
| fb7f3765 | DESIGN.md section 2 matches what ships (S10) |
| c43080a0 | The verification-gap sentence, the tiers, the pre-registration (M11) |
| 23f51390 | Tier tables name each unit's note and release |
| 749fe231 | W relabelled as a secondary bound; estimates point at the pre-registration |
| 3d79861c | CLAIMS.md records the replaced failure sentence |
| f997351a | Spec notes paraphrased, NOTICE, font licence (S2) |
| f8b81b3d | Tier C gains the AAT units no shipped font can check (M11) |
| 02e97477 | Gate checks for V, the new stub and the hostile trees |
| 2a69bd25 | README states the verification-gap sentence, tiers and V (M11) |
| b1b4a2f1 | `kerx` format 2 addressing stated one way (pass 04 finding 6) |
| 3779de18 | Cases follow the notes (M2, M4, M9, M10, S6, S11) |
| d7ddf4b0 | Narrow the cases, not the notes (S6) |
| f86259ea | Verifier hardening (M5, M6, M7, M8, S1) |
| 58ee9d6d | QA plan and design notes describe the hardened verifier |
| 6f9ea68f | Drop the threaded shaping test that reads the pruned speed fonts (S9) |
| c1deb879 | README status, hackability and development log with the measured results |
| (this report) | notes/FIX1-REPORT.md |
