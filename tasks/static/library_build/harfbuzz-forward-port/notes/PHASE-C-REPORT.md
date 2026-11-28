# Phase C report: HarfBuzz forward-port

Author notes, never shipped. Phase C took the task from the first three families to every unit, with the
failure-sentence proof, the gold recorded through the verifier image, the agent image, the reference solution and
the gate. It ran under the shared-machine rules (heavy lock, at least 30% memory free, containers at 4 GB, no
Oddish) and, from 2026-11-27, a 3 GB disk allowance.

## Summary

**QA-ready.** 53 of the 57 units are graded on 5,256 private cases; the other four are cut with their reasons on
record. Through the amd64 verifier image built from a pinned Ubuntu snapshot: the reference solution scores **1.0**,
the untouched shipped tree **0.0**, every stub **0.0**, and the failure-sentence mutant W **0.672**, inside the
0.60-0.85 band with the loss in the gate. The expected outputs were recorded through that image and agree with the
pipeline's arm64 builds on all 5,256 cases; three more recordings and one on a single CPU are byte-identical. Local
preflight passes on the flat bundle (hash and result below). An independent 20-pass QA is next.

## Scope

| | Units |
| --- | --- |
| Graded | 53: F1 12, F2 5, F3 3, F4 9, F5 2, F6 1, F7 3, F8 18 |
| Cut | 47a, 28, 30, 50 (scripts/pipeline/cuts.tsv, notes/DESIGN.md "Scope decisions of Phase C") |

- **47a** superseded: in 15.2.0 `hb_font_set_face()` is 47b's no-op; only a deprecation attribute remains.
- **28** unobservable: the syllabic shapers already set the flags 15.2.0 adds at the graphemes level (0 differences
  in 6,109 probed texts on 7 fonts).
- **30** unreachable: the changed branch needs a normalized coordinate below -1; every public way to set variations
  clamps to [-1, 1] first.
- **50** rule not in the materials (audit class c/d): format 19 takes its metrics from CBLC index formats 2 and 5,
  which only the EBLC chapter defines; that chapter is not among the shipped notes and 14.3.0 implements neither.
- **Left-out inputs** (never graded either way): unit 36's values that overflowed 14.3.0's 16-bit scaler arguments
  (`x:16bit`; confirmed by the coordinator), and in every unit what 15.2.0 changes beyond its note (each generator's
  docstring lists them).
- **Unit 19** (the 15.1.0 `COLR` note) was found in Phase C: commit e8a7f183f.

## Specification notes

51 digests in `environment/docs/specs/` (34 OpenType pages, UAX #29, 8 AAT pages, 8 script pages), written in our
own words because the source pages carry no redistribution licence. Material the pages cite without defining was
cut instead of shipped unverified: the EBLC/EBDT formats, the baseline tag and axis tag registries, the Variations
Overview's normalization and region scalars, the W3C compositing formulas, `gvar`'s vertical phantom points, the AAT
lookup formats, the inferred Hebrew glyph list, the added USE position table and the Devanagari and Bengali reading
notes. Each cut leaves a sentence naming what is not restated. Only unit 50 depended on cut material; units 31, 40b,
44b and the AAT units keep their rules through 14.3.0's own code and public headers.

## Sweep (c2) and selection

- Five unit authors wrote the generators and fonts (`gen_f1`, `gen_f2`, `gen_f4`, `gen_f8a`, `gen_f8b`), the API
  drivers (`hbapi`, `hbmeta`, and the probes `hbapi48/49/51`, each compiling only against a tree that declares its
  function) and one widening patch per conditional unit (45 in `mutants/W/`). Hand-resolved reverts for 27, 29, 36,
  48, 49 and 51; unit 33 is attributed by adding Unicode 18 to the base (`regen-14.3.0`).
- 50,299 candidates in 402 s under the lock: 23,836 changed and attributed, 25,460 held, 988 broad, 15
  unattributed, no flapping base output in three base runs (two under `MALLOC_PERTURB_`). Every build compiled,
  mutant W with all 45 patches.
- Selection: 3,156 changed cases (36-60 per unit), 1,500 duals (30 per unit, spread evenly over its boundaries, 50
  units; 48, 49 and 51 are pure additions without a condition), 600 broad: **5,256 cases**.

Per unit (attributable = changed cases attributed to the unit in the sweep; "W keeps" = the share of the unit's
duals mutant W leaves as they were):

| Unit | Family | Window | Candidates | Attributable | Graded changed | Duals (boundaries) | W keeps of the duals |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | F1 | C | 2000 | 770 | 60 | 30 (5) | 0.467 |
| 2 | F1 | C | 2000 | 1109 | 60 | 30 (4) | 0.733 |
| 3 | F1 | C | 800 | 461 | 60 | 30 (4) | 0.767 |
| 4 | F1 | C | 2000 | 1007 | 60 | 30 (5) | 0.8 |
| 5 | F1 | C | 2000 | 668 | 60 | 30 (5) | 0.8 |
| 6 | F1 | C | 800 | 361 | 60 | 30 (7) | 0.667 |
| 7 | F1 | C | 2000 | 250 | 60 | 30 (6) | 0.733 |
| 8 | F1 | C | 700 | 287 | 60 | 30 (5) | 0.6 |
| 9 | F1 | C | 800 | 419 | 60 | 30 (3) | 0.667 |
| 10a | F1 | B | 600 | 205 | 60 | 30 (6) | 0.867 |
| 10b | F1 | B | 600 | 344 | 60 | 30 (4) | 0.733 |
| 11 | F1 | A | 600 | 259 | 60 | 30 (4) | 0.8 |
| 12 | F2 | C | 1200 | 443 | 60 | 30 (3) | 0.667 |
| 13 | F2 | C | 1500 | 767 | 60 | 30 (3) | 0.667 |
| 14 | F2 | C | 2000 | 1003 | 60 | 30 (3) | 0.667 |
| 15 | F2 | C | 2000 | 838 | 60 | 30 (3) | 0.667 |
| 16 | F2 | A | 900 | 398 | 60 | 30 (3) | 0.667 |
| 17 | F3 | C | 900 | 410 | 60 | 30 (5) | 0.8 |
| 18 | F3 | C | 900 | 479 | 60 | 30 (2) | 0.5 |
| 19 | F3 | B | 600 | 320 | 60 | 30 (3) | 1.0 |
| 20 | F4 | C | 779 | 399 | 60 | 30 (2) | 0.5 |
| 21 | F4 | C | 700 | 232 | 60 | 30 (4) | 0.533 |
| 22 | F4 | C | 500 | 251 | 60 | 30 (2) | 0.5 |
| 23 | F4 | C | 600 | 258 | 60 | 30 (3) | 0.667 |
| 24 | F4 | C | 1000 | 313 | 60 | 30 (4) | 0.767 |
| 25a | F4 | B | 900 | 331 | 60 | 30 (3) | 0.933 |
| 25b | F4 | B | 789 | 424 | 60 | 30 (2) | 0.533 |
| 25c | F4 | B | 700 | 277 | 60 | 30 (2) | 1.0 |
| 26 | F4 | A | 800 | 270 | 60 | 30 (2) | 0.667 |
| 27 | F5 | C | 900 | 442 | 60 | 30 (2) | 0.5 |
| 28 | F5 | C | 0 | 0 | cut | - | - |
| 29 | F5 | C | 900 | 388 | 60 | 30 (4) | 0.733 |
| 30 | F6 | A | 0 | 0 | cut | - | - |
| 31 | F6 | B | 900 | 449 | 60 | 30 (4) | 1.0 |
| 33 | F7 | A | 1200 | 835 | 60 | 30 (3) | 0.833 |
| 34 | F7 | B | 1200 | 674 | 60 | 30 (2) | 0.5 |
| 35 | F7 | A | 600 | 279 | 60 | 30 (5) | 0.867 |
| 36 | F8 | A | 2000 | 1475 | 60 | 30 (1) | 0.0 |
| 37 | F8 | A | 800 | 515 | 60 | 30 (1) | 0.033 |
| 38 | F8 | C | 800 | 453 | 60 | 30 (2) | 0.5 |
| 39 | F8 | C | 600 | 280 | 60 | 30 (3) | 0.733 |
| 40a | F8 | C | 600 | 205 | 60 | 30 (7) | 0.533 |
| 40b | F8 | C | 600 | 302 | 60 | 30 (3) | 0.633 |
| 40c | F8 | C | 500 | 212 | 60 | 30 (4) | 0.8 |
| 41 | F8 | C | 71 | 36 | 36 | 30 (5) | 0.8 |
| 42 | F8 | C | 500 | 227 | 60 | 30 (3) | 1.0 |
| 43 | F8 | C | 570 | 346 | 60 | 30 (2) | 0.5 |
| 44a | F8 | B | 600 | 254 | 60 | 30 (4) | 0.733 |
| 44b | F8 | B | 800 | 309 | 60 | 30 (5) | 0.8 |
| 45 | F8 | B | 500 | 257 | 60 | 30 (3) | 0.667 |
| 46 | F8 | B | 500 | 248 | 60 | 30 (3) | 0.667 |
| 47a | F8 | A | 0 | 0 | cut | - | - |
| 47b | F8 | C | 500 | 300 | 60 | 30 (2) | 1.0 |
| 48 | F8 | C | 300 | 300 | 60 | 0 (0) | - |
| 49 | F8 | C | 400 | 400 | 60 | 0 (0) | - |
| 50 | F8 | C | 500 | 297 | cut | - | - |
| 51 | F8 | B | 800 | 800 | 60 | 0 (0) | - |

## The failure sentence (band check)

Reward = D x h_d x (1 - 0.10 (1 - h_b)): the dual gate is a full factor (notes/DESIGN.md section 6). Mutant W is
15.2.0 with every conditional unit's condition widened the way an over-eager port would widen it.

| | D | h_d | h_b | Gate | Reward |
| --- | --- | --- | --- | --- | --- |
| Pipeline (arm64) | 0.986 | 0.684 | 0.965 | 0.682 | 0.672 |
| Verifier (amd64, recorded gold) | 0.985849 | 0.684 | 0.965 | 0.681606 | **0.671961** |

W loses 0.318 of its reward to the gate and 0.014 to D. Three widenings are not perfectly clean: W passes 0.617 of
unit 7's changed cases, 0.717 of unit 9's and 0.917 of unit 40c's, because the widened code path also reaches some
inside inputs (unit 7: spaces made transparent also move circles in texts that hold a space elsewhere; unit 9:
centring every word also moves the long word sharing a run with a short one; unit 40c: skipping every flagged STAT
value also skips flagged values 15.2.0 keeps). D stays above 0.98 because the three shortfalls sum to 0.75 of a
unit over 53 units (0.014). Cleaner widenings would move W from 0.672 to about 0.682, inside the band either way,
and the proof already rests on the gate; not worth another build cycle before QA, noted for later.

## Gold, determinism and the verifier passes

- Expected outputs recorded through the verifier image (amd64, toolchain from snapshot.ubuntu.com 20261126T000000Z,
  gcc 13.3.0-6ubuntu2~24.04.1) on the 15.2.0 release tree: 5,256 cases, **0** differ from the arm64 pipeline.
- 3+1: two more recordings and one on 1 CPU are byte-identical to the first.
- Verifier runs (amd64; about 60-135 s each, of which the build is 45-62 s):

| Tree | Reward | Wall time |
| --- | --- | --- |
| Reference solution: the shipped tree after `solution/solve.sh` | **1.0** | 74 s |
| Shipped tree plus the reference change | **1.0** | 81 s |
| Untouched shipped 14.3.0 tree | **0.0** | 68 s |
| Stub: comment and whitespace edits | 0.0 | 62 s |
| Stub: a neutral refactor (a helper nothing calls) | 0.0 | 62 s |
| Stub: a tree that does not build | 0.0 (a valid reward) | 16 s |
| Stub: `hb_shape_full()` returns an empty buffer | 0.0 | 60 s |
| Stub: the library aborts on its first shaping call | 0.0 | 61 s |
| Mutant W | **0.671961** | 73 s |
| The reference tree with a pipe, a 600 MB sparse file, 100,000 files and links out of the tree | 1.0 | 113 s |
| A bogus release (the verifier's own fault path) | no reward, exit 1 | 1 s |

These are the final pass (2026-11-27, 17:10-17:21 UTC), on the final drivers. An earlier pass found the
empty-`hb_shape` stub at 0.002: it passed 25 of unit 43's 60 cases, because with no shaping the positions left in
the buffer's memory are zero anyway. The positions probe now answers `!err:noshape` when the text it shapes first
has no glyph that moves the pen; real shaping always moves it on these fonts, so no recorded output changed (the
reference solution and W score as before). A first attempt at the stub trees with hard links failed across Docker
Desktop's file sharing; the stubs are now plain copies without `test/`, which the product build never reads.

## Images and probes

- **Agent image** (`environment/Dockerfile`): pinned base, toolchain from the snapshot on amd64, fontTools, packTab,
  meson and Ubuntu's `python3-lxml` (upstream's UCD generator needs it); the Unicode 18 generator inputs with
  sha256 checks; the 51 specification notes and `notes.md`; HarfBuzz 14.3.0 pruned (no `perf/`, `.github`,
  `.ci`, `CLAUDE.md`, `AGENTS.md`, `CODE_OF_AI_CONDUCT.md`), one git commit, user `dev`.
- **Protection probe** (amd64 agent image, no network): uid 1001; no HarfBuzz library or version header outside
  the tree; no 15.x version string in the tree outside `NEWS`; none of the pruned agent files; no `/solution` or
  `/tests`; network unreachable; the tree clean at its one commit.
- **Verifier protection** (amd64 verifier image): as `builder`, reading the expected outputs, listing
  `/tests/private` and writing the reward all fail.
- **Reference solution**: the 358 source files the change touches, as they read in 15.2.0, and 3 deleted paths;
  `solve.sh` copies and removes. The tree `solve.sh` produces scores 1.0.

## Packaging and preflight

`scripts/package_task.py` builds the flat bundle from task.toml, instruction.md, environment/, tests/ (with the staged
private cases, fonts and the meson wheel) and solution/ (the reference sources). It checks the notes file against the
instruction and every agent-visible file for private case ids and font names, and refuses patch files.

- **Bundle** `0462de9dc7cbd3631c923814fe0593a26eeb981c7d5e8eb2a91961ad3acc1e04`: 654 files, 24.4 MB.
- **Local preflight** (`oddish preflight`, no upload): **passed**. The first bundle failed it because the solution
  applied a patch; the solution now ships source files, and `environment/.dockerignore` keeps any `.git` out.

## Gate (QA-PLAN.md section 1)

| # | Gate | Result |
| --- | --- | --- |
| 1 | Inventory | **Pass.** All 51 notes map to graded units or recorded cuts (scripts/pipeline/notes_map.tsv, cuts.tsv) |
| 2 | Kill matrix | **Pass.** 53 units with 36-60 cases each; each unit's own revert fails all its cases; no other unit's revert changes any of them |
| 3 | Stub zoo | **Pass.** Untouched tree, comment edits, neutral refactor, no build, empty `hb_shape`, abort: 0.0 each. R_all scores 0 on all 43 units it reverts (its total 0.179 comes only from the 10 units it cannot revert, each covered by its own revert) |
| 4 | Oracle and nop | **Pass.** The tree `solve.sh` produces scores 1.0; the untouched tree 0.0 |
| 5 | Determinism | **Pass.** 3+1 recordings through the verifier image byte-identical on 5,256 cases; three base runs (two under `MALLOC_PERTURB_`) agree |
| 6 | Cue-word sweep | **Pass.** Instruction, notes and Dockerfile clean. Justified hits: "evaluation" in its technical sense in 7 lines of the specification notes, "upgraded" in one, and the name of upstream's `benchmark` build option in `prune_tree.sh`, which removes it and is itself deleted from the image. One phrase ("behave exactly like") reworded in the COLR notes |
| 7 | Protection probe | **Pass** (amd64 agent image): non-root, no network, no 15.x material, no pruned agent files, no solution or tests |
| 8 | Verifier robustness | **Pass.** The cluttered tree scores 1.0 like the reference; a tree that does not build scores 0 with a clean exit; a verifier fault leaves no reward; the build user cannot read the expected outputs or write the reward |
| 9 | Isolation and timeouts | **Implemented, not attacked.** One process per driver and font under `prlimit`, 300 s per batch, 1,200 s for all batches, outputs above 256 MB discarded |
| 10 | No early stops | **Pass.** Only `timeout_sec` (34,560 s); no hooks, timers or kills in the task |
| 11 | Leak scan | **Pass.** No private case id or font name in any agent-visible file (packager); no 15.x material in the agent image (probe) |
| 12 | Band check | **Pass.** W 0.671961 (D 0.986, h_d 0.684, h_b 0.965), with 0.318 of its loss in the gate |

## Resource use

- Lock holds in Phase C: revert builds 1,115 s; sweep 402 s; first verifier pass 1,867 s (818 s of it the
  snapshot's slow package downloads); second pass 699 s; final pass 678 s. Every start had at least 30% of
  memory free; the gate kept jobs waiting for up to about 70 minutes at a time.
- Disk after clean-up: **about 0.53 GB**: the cache 474 MB (downloads 124 MB, the c2 sweep's outputs 327 MB,
  candidates, patches and logs), and in the task folder the bundle (25 MB) and the git-ignored staged inputs, reference
  sources and private store (27 MB). No image of ours remains (`hbfp-verifier:phaseB-amd64` and
  `hbfp-pipeline:phaseB` deleted by name, the agent image earlier); every work tree and the unit authors' scratch
  folders are deleted; the heavy lock is free. The worktree's development environment (`.venv`, 718 MB) is the
  repository's tooling, not task data.

## Commits (branch `neel/harfbuzz-forward-port`, all pushed)

24f82900, 9127d0ff, 7a14405a, 47d7466d, 636b77f4, e508ff1a, e5f0b55c, ccae9ef8, 19290cca (specification notes),
08996019 (F4 units), 5d720894 (F1 and F8 units), fd5260b0, d5275ead (F2 units), de36572a (specification cuts, unit
50), d72ee18e, 6591d64b, ae662895, 0e1e9c36, 8430fd59 (the c2 sweep), 2e4ca9cb, c4f3d693 (the solution as source
files), 38ffabf9 (the positions probe guard), and the commit holding this report.

## Open items for QA

- The 12-hour session question (owner): the length lives only in `task.toml` (`timeout_sec` 34,560); the
  instruction states none, so a switch is one value and one sentence.
- Hang and fork attacks on the verifier are bounded by limits but were not run.
- The three imperfect widenings above.
