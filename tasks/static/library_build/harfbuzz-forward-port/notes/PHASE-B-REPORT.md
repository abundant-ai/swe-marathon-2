# Phase B report: HarfBuzz forward-port

Author notes, never shipped. Phase B: the downloads, the spike and the first build milestone, under the shared-machine
rules (heavy lock, at least 30% memory free, containers at 4 GB, 5 GB of disk).

## Summary

**Go.** Every must-pass check passed: S2 (the product build of the four releases in 15-31 s on 4 CPUs, identical
outputs with and without ragel), S3 (the driver reproduces all 16 of upstream's new Khmer expectations, and 8 differ
on the base, as upstream's commit says), S6 (49 of 56 units revert cleanly alone), S8 (the verifier builds a tree and
runs 1,802 cases in 27 s) and S10 (three runs and a perturbed fourth are byte-identical on 18,898 candidates, on both
15.2.0 and 14.3.0; 15.2.0 without FMA contraction gives the same outputs; an emulated amd64 verifier scores the
arm64-recorded outputs 1.0). Item by item: S4 passes for `trak` and `kerx`, S5 passes (every measured unit yields
51-855 attributable changed cases; the four of S5's six named items that were measured yield 717-855 each), S7
passes (the Unicode 18 regeneration matches 15.0.0 on all 1,114,112 code points), S9 passes, and S11 is partial (the
over-broad mutant fails every dual on the boundary it widens, but the dual mix dilutes that to about 20% per unit).
No unit is cut.

**Milestone reached.** The pipeline image builds every release, revert and mutant; the verifier skeleton runs in
its own image; the first families (F1 units 1, 2, 4, 5, 7; F2 units 13, 14, 15; F4 units 21, 22, 23) generate into
the git-ignored `tests/private/`; upstream 15.2.0 scores **1.0**, the 14.3.0 release tree **0.0**, and the pruned
tree the agent starts from **0.0**.

## Plan changes from the owner

- **Single step (2026-11-26).** "we dont have to promote multi-turn as well so make stuff likewise": one instruction,
  one 34,560 s session, graded as the old step 3 (all 56 units against 15.2.0, with the held-fixed duals gate). The
  `steps/` layout is gone (commit `47b8f47`); notes/STEPS.md is kept as history, marked parked. The spike's per-step
  chain measurements were dropped; nothing else in the spike depended on steps.
- **Difficulty (2026-11-27).** "if its hard enough in single turn make sure to have it difficult enough": target
  frontier at most about 0.6, the dual gate at full strength (w_d at least 0.25), the AAT and `kern` families kept,
  no hard but fair note dropped. notes/DESIGN.md section 13 holds the sizing: frontier ≈ 0.48 (range 0.36-0.60),
  mid-tier ≈ 0.12-0.30.
- **What the spike's yield does to that estimate.** Nothing yet: no measured unit fell below the 3-case floor, and
  the three font-dependent F4 units measured (21, 22, 23) all yield on our own fonts, so the scope stays at 56 units
  and the estimate stands. If later units are cut, section 13's arithmetic applies: five cuts at an expected 0.30
  move frontier D up by about 0.02; losing all of F4 and F5 would move it to about 0.59.

## Downloads

Fetched with `scripts/fetch_inputs.sh` into `~/Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port/`; the
cache's `MANIFEST.tsv` lists every file with its source URL, size and SHA-256. One URL had moved (the emoji test file
is now under `/Public/18.0.0/emoji/`); the script tries both. The history clone (blobless, 17 MB) fetches blobs on
demand. Nothing beyond the approved list was downloaded into the cache; the one addition is Ubuntu's `python3-lxml`
package, installed by the image builds from the Ubuntu archive like the rest of the toolchain (S7 explains why).

| Group | Files | Bytes |
| --- | --- | --- |
| HarfBuzz release tarballs | 4 | 81,493,016 |
| Fonts (Noto, licence files) | 17 | 9,892,742 |
| Python wheels | 3 | 2,454,532 |
| Unicode and language data | 10 | 9,464,863 |
| Specification pages | 51 | 5,318,215 |
| All | 85 | 108,623,368 |

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `harfbuzz-14.3.0.tar.xz` | 19,819,024 | `16070d77cfc4ba1f1e7327e83bf9b3f55898081cabdb94e56a33e04fc8874eae` |
| `harfbuzz-15.0.0.tar.xz` | 20,396,372 | `968536e9abd782f07f7954044c0c4020199fcdd39b41d221ec42d2a3be4a44df` |
| `harfbuzz-15.1.0.tar.xz` | 20,515,628 | `0fc7c565443a5f4be7da65ac5ee5bd737d9b158dc908708b7689a0a5796b0c8d` |
| `harfbuzz-15.2.0.tar.xz` | 20,761,992 | `e2ec49090744383cdbe7df808c1cedaafba06a97be8dc4211fe546ba585f12cb` |
| `fonttools-4.69.1-py3-none-any.whl` | 1,301,769 | `20e9dfac71694d9eeae48bb53c877bdf43b914794d69a769940728a1929cc835` |
| `packtab-1.9.0-py3-none-any.whl` | 44,095 | `5641d7505ea726c21501101af32f21908180db84eae0f04e3b70a5cb40fd10a1` |
| `meson-1.12.1-py3-none-any.whl` | 1,108,668 | `930bc7542cbd9f57009e182fd014eba48cf1a0180a7b9006d2d32d8f168d8b02` |
| `UCD-18.0.0.zip` | 5,657,953 | `7b3e555514060b92290d154f53655c5eb0fa62b16eb04c03434ff72d1a66a0d8` |
| `DerivedCoreProperties-17.0.0.txt` | 1,134,783 | `24c7fed1195c482faaefd5c1e7eb821c5ee1fb6de07ecdbaa64b56a99da22c08` |
| `ucd.nounihan.grouped-18.0.0.zip` | 1,037,692 | `552bef87e5bf69d0047048d1e5762d352ab817aecc1a35b955628e8f1a4707ee` |

Fonts (Noto at `notofonts.github.io@d14cc173`, Korean at `noto-cjk@f8d15753`), the remaining Unicode files and the 51
specification pages are in the manifest with their hashes.

## Spike results

Everything ran in bounded containers (`--memory=4g --cpus` 1-6) of our own images, arm64-native except the one amd64
sample. Candidates: 18,898 per sweep (seed 20261127): 2,000 per Noto-font unit, 666 per synthetic-font unit, 900
broad.

| # | Check | Result | Pass? |
| --- | --- | --- | --- |
| S1 | Fetch, hashes, licences, upstream agent files | All 85 files hashed. Fonts: all 15 Noto fonts carry the SIL Open Font License in their `name` table (read in a container); Unicode data: Unicode License V3; Microsoft and Apple pages: no licence grant found, so they ship as our own digests. `CLAUDE.md` is a symlink to `AGENTS.md`, whose rules (narrow changes, preserve behaviour) fit the work order: kept, minus its `perf/` line. Pruned besides `perf/`: `CODE_OF_AI_CONDUCT.md`, `test/vector/README.md`, the speed-measurement meson wiring. The pruned tree builds with the product command | Pass |
| S2 | Product build of the four releases, ragel on and off, time on 4 CPUs | Native arm64, `ninja -j4`: 14.3.0 15 s, 15.0.0 22 s, 15.1.0 24 s, 15.2.0 31 s (wall 19-36 s); peak memory 1.65-2.14 GB per build container. ragel 6.10 regenerates four shaper machines; hidden, none; outputs with and without ragel identical on all 18,898 candidates | Pass |
| S3 | Driver against upstream's 16 new Khmer lines (upstream's test font, spike only) | 15.2.0 matches upstream's expectation on 16 of 16; the base differs on 8, as the commit says. Rechecked after the driver fix below | Pass |
| S4 | Our own AAT fonts | (a) `trak`: HarfBuzz applies `trak` only to fonts that also have `STAT`; with one, vertical text changes (358 cases), horizontal text and the same font without `STAT` stay fixed. (b) `kerx` format 0 from our writer (fontTools 4.69.1 still has no `kerx` module): HarfBuzz prefers `GPOS` over `kerx` only when `GSUB` is present too, so the changed font has all three tables (194 cases); neighbours without `GSUB`, without `GPOS`, with a `kern` feature, or with a cross-stream subtable stay fixed. (c) The AAT `kern` format 1 cross-stream font (unit 20) is not built yet | Pass for (a), (b) |
| S5 | Attributable changed cases per unit | Table below: 11 units measured, 51-855 each. Of S5's six named items, 1, 2, 4 and 7 yield 717-855 (unit 1: 368 on Noto Sans Bengali, whose `init` covers the E and AI signs, and 349 on our Bengali font); 3 and 12 have no generator yet | Pass |
| S6 | Revert cleanliness | Patches cover the library's build inputs only. Strict `git apply`: 48 of 56 units clean alone (85.7%); `patch` with default fuzz on the tarballs, in a container: 49 of 56 (87.5%). Not clean: 36 (the 76-commit saturation stack), 33 (Unicode 18), 47a, 51, 27, 48, 49; they need merged stacks | Pass |
| S7 | Unicode fidelity | The final 18.0.0 files carry the dates upstream recorded (Phase A's "pre-release" corrected); `DerivedCoreProperties` 17.0.0 is the one exception, and we have it. A 14.3.0 tree regenerated with its own generators from the shipped files (plus the three script values the notes name) matches 15.0.0's Unicode properties on all 1,114,112 code points (category, combining class, script, mirroring, decomposition, composition); 14.3.0 itself differs on 13,008. Every remaining table difference against 15.2.0 is a generator change that is a unit of its own (`fonupa` tag, the USE space category, the Indic and vowel-constraint fixes, an ASCII fast path). The newer IANA registry changes only the table's date line. Upstream's `gen-ucd-table.py` needs `lxml` (through packtab's UCD XML reader), which the agent image lacked: both images now install Ubuntu's `python3-lxml` | Pass |
| S8 | Verifier dry run on 4 CPUs | Separate verifier image; builds the tree as an unprivileged user (setup 1 s, build 21 s) and runs 1,802 cases: 27 s in all | Pass |
| S9 | Spec availability | `CBDT` format 19 is in the public `CBDT` page (unit 50 stays); `FeatureVariations` 1.1 and `DMAP` are not public (stay out) | Pass |
| S10 | 3+1 determinism, FMA, an emulated amd64 sample | 3 runs and a perturbed fourth (1 CPU, `MALLOC_PERTURB_`, a longer path, `LC_ALL=C`) byte-identical on all 18,898 candidates, for 15.2.0 and for 14.3.0. 15.2.0 built with `-ffp-contract=off`: identical outputs. The verifier image built for linux/amd64 and run emulated on the 15.2.0 tree scores 1.0 against outputs recorded on arm64 (1,802 of 1,802) | Pass |
| S11 | Mutant W (over-broad application of stated conditions) | W passes all 60 changed cases of units 21 and 23, and fails every dual on the boundary it widens (21: 11 of 11, vertical text with `vkrn` not requested or in `GPOS`; 23: 10 of 10, `GPOS` with a kerning feature). Across all 50 duals of each unit it fails 22% and 20%, because the duals cover every neighbour, not only the widened one; W's total is 0.960. Unit 4's mutation is no pure widening (it passes 43 of 60 changed cases) | Partial |

### Yield per unit (S5)

Attributable: the base and 15.1.0 differ from 15.2.0, the unit's revert gives 15.1.0's output, and the eleven other
reverts give 15.2.0's.

| Unit | Family | Note | Candidates | Changed, attributable | Fonts |
| --- | --- | --- | --- | --- | --- |
| 1 | F1 | No Indic `init` after a letter or mark in the pre-context | 2,000 | 717 | Noto Sans Bengali, our Bengali font |
| 2 | F1 | USE: a space is no base for a dependent vowel | 2,000 | 849 | Noto Balinese, Javanese, Tai Tham |
| 4 | F1 | Khmer: one Coeng Ro, first or second coeng only | 2,000 | 855 | Noto Sans and Serif Khmer |
| 5 | F1 | A Hangul tone mark at the start of the text gets one dotted circle | 2,000 | 679 | Noto Sans KR |
| 7 | F1 | Vowel constraints across default ignorables | 2,000 | 788 | Noto Indic and USE fonts |
| 13 | F2 | Precomposed characters in text with no marks | 2,000 | 51 | Noto Indic, Khmer, USE, Myanmar |
| 14 | F2 | A global feature request overrides earlier ranged ones | 2,000 | 128 | Noto Sans and Serif (variable) |
| 15 | F2 | A missing character with a variation selector gets the not-found glyph | 2,000 | 821 | Noto Sans Hebrew, Noto Sans |
| 21 | F4 | `kern` in vertical text when `vkrn` is requested | 666 | 94 | our `kern` fonts |
| 22 | F4 | `trak` in vertical text | 666 | 358 | our `trak` font with `STAT` |
| 23 | F4 | `kerx` together with a `GPOS` that has no kerning feature | 666 | 194 | our `kerx` font with `GSUB` and `GPOS` |
| broad | - | Text near no note, every Noto font | 900 | 897 held fixed | all |

### What the spike found and fixed

- **The candidates, not the units, explained every zero.** In the first sweep units 1, 5, 22 and 23 had no changed
  case. Each condition was narrower than its first generator: Noto Sans Bengali's `init` covers the E and AI signs,
  not I (the generator now reads each font's `init` coverage); HarfBuzz applies `trak` only with `STAT`; it prefers
  `GPOS` over `kerx` only when `GSUB` is present too; and unit 5's note is about the beginning-of-text flag (with it,
  14.3.0 gives a tone mark that opens the text two dotted circles, the generic one for a broken cluster at the start
  and the Hangul shaper's own; 15.2.0 gives one).
- **What 15.2.0 changes beyond a note stays out of both case kinds.** Format characters such as ZWJ as Indic
  pre-context (15.2.0 treats them like letters there), and a dotted circle already in the text before a tone mark,
  change in 15.2.0 although no note says so; generators leave them out rather than score them either way.
- **The driver** merged two tabs and lost an empty options field (388 candidates came back as bad lines); it now
  splits on every tab, and `relink.sh` relinks it into saved builds.
- **Mutant W** failed to compile at first (an unused variable under HarfBuzz's `-Werror` flags); fixed.
- **The instruction** now says the product passes the text around each run as context, which the Indic note's
  "pre-context" assumes.

## Milestone status

| Item | Status |
| --- | --- |
| The image builds the releases | Done: `hbfp-pipeline:phaseB` builds 14.3.0, 15.0.0, 15.1.0, 15.2.0 (ragel on and off, FMA off), 12 single-unit reverts, mutant W and the regenerated Unicode tree, each in 20-36 s |
| The verifier skeleton runs | Done: `tests/Dockerfile`, `tests/test.sh`, `tests/verify.py`; separate image, network off, private cases root-only, candidate built as an unprivileged user under `prlimit`, one driver process per font; writes `reward.txt` and `metrics.json`, or no reward on an evaluation error |
| First families generate into `tests/private/` | Done: 1,802 cases (652 changed in 11 units of F1, F2 and F4, 550 duals, 600 broad), opaque ids from a private salt; fonts staged into `tests/inputs/`; all git-ignored |
| Upstream scores 1.0, the base 0 | Done: 15.2.0 → 1.0 (arm64, and amd64 emulated); 14.3.0 release tree → 0.0; the pruned tree the agent starts from → 0.0 |
| Public parts committed, private parts backed up | Done: commits below; the private store (salt, selection with recorded outputs, catalogue) is in the bundle at `harbor-lh/ops/swe-marathon-v2/next-tasks/harfbuzz-forward-port-private/` |

## Resource use

- **Memory.** Every heavy job started with at least 30% free (30-33% at each start; the gate held batches for up to
  about 45 minutes). Each build container peaked at 1.65-2.14 GB of its 4 GB bound (cgroup `memory.peak`); runs and
  the verifier stayed within the same bound.
- **Lock.** Six holds, 1,064 s in all: image 80 s, batch 1 157 s, batch 2 354 s, batch 5 115 s, milestone 236 s,
  amd64 sample 123 s. One incident: my first run crashed (host Python 3.9) right after creating the lock directory,
  leaving it empty for a few minutes at 19:54 UTC on 2026-11-26; I removed that directory by its literal path. No
  other task's lock was taken over.
- **Disk.** Cache 846 MB (downloads 124 MB; trees, builds, outputs 722 MB); images `hbfp-pipeline:phaseB` 787 MB,
  `hbfp-verifier:phaseB` 691 MB, `hbfp-verifier:phaseB-amd64` 687 MB (sizes count shared base layers each time);
  the worktree's development `.venv` 718 MB. About 3.7 GB at the peak, under 5 GB. The three images are removed by
  name at the end of Phase B; they rebuild in about a minute each.

## Commits (branch `neel/harfbuzz-forward-port`, all pushed)

`2cce559`, `47b8f47` (single step and the difficulty sizing), `d7deb05`, `47640c9`, `70c4f30`, `3f3fee7`, `c2cbbce`,
`dbbb512`, `799dbf1`, `f4c36da`, `bb0268c`, `7a119c5`, `a513b51`, `ea0d1d0`, `54316b8`, `95ff140`, `1ecf4a7`,
`f01de85`, `c8df2d9`, `257dac9`, `1fc8a1d`, and the commit holding this report.

## Next steps (Phase C)

1. Generators for the other 45 units, windows A and B included (their changed cases compare 14.3.0 with 15.0.0 or
   15.1.0); merged-stack reverts for 36, 33, 47a, 51, 27, 48 and 49; the AAT `kern` format 1 font for unit 20; a
   USE font with positional forms for unit 3; long-syllable text for unit 12; Unicode 18 text for units 33 and 34.
2. Duals drawn per boundary neighbour, with a floor for each, so an over-broad port loses what the gate promises;
   unit 4's W rebuilt as a pure widening; then the band check on w_d.
3. Record the outputs through the verifier image itself (the exact-source build), with apt pinned to a snapshot of
   the Ubuntu archive: the verifier build upgraded `perl-base` over the base image's, so package versions follow
   the build date until pinned. All three images record their package versions now.
4. Build the agent image (now with `python3-lxml`) and the oracle patch (pruned 14.3.0 to 15.2.0's library), and run
   the oracle through `solve.sh`.
5. Restatements for the example-dependent notes, then 20+ independent QA passes; no Oddish run before the owner says
   so.
