# Claims behind the HarfBuzz forward-port, checked against primary evidence (Phase A)

Author notes, never shipped. Sources checked on 2026-11-26:

- **Upstream history.** The research clone of `harfbuzz/harfbuzz` (blobless, HEAD `197a6b9`), read with
  `GIT_NO_LAZY_FETCH=1` so no object was downloaded. Tags, commits, trees and messages are all local. File contents
  were read only where their blobs were already on disk (905 blobs, for example `COPYING`, `NEWS` at 15.2.0,
  `meson_options.txt`, the shaper sources and most `.tests` files at 14.3.0 and 15.2.0).
- **NEWS.** The saved `NEWS` file is byte-identical to the 15.2.0 blob (`b2a6b23b`).
- **Other sources.** harbor-lh's Forge `tasks/` and this repository's `main` (`ff9359f`). An installed fontTools
  4.60.2 was read as source, not run.

Nothing was built or run, and no web page was fetched. A claim that needs an outside page or a file not on disk is
marked **unverified** and has a named check in [SPIKE.md](SPIKE.md) or [QA-PLAN.md](QA-PLAN.md).

**Verdicts.** **Verified**: primary evidence agrees. **Corrected**: the evidence changes the claim; the corrected
form is given. **Unverified**: not checkable in Phase A. **Estimate**: a judgement, not a fact.

## Validity table

| # | Claim (source) | Verdict | Evidence and corrected form |
| --- | --- | --- | --- |
| C1 | HarfBuzz shapes text in Android, Chrome, ChromeOS, Firefox, Flutter, GNOME and KDE (report, README "users") | Unverified | `README.md` blob not on disk. Widely documented; read the 14.3.0 README after download (SPIKE S1) |
| C2 | Base 14.3.0 released 2026-07-31 (report) | Verified | Tag commit `4c2aa804671d` committed 2026-07-31T17:49:40+03:00; NEWS "Friday, July 31, 2026" |
| C3 | Target 15.2.0 released 2026-11-19 (report) | Verified | Tag created 2026-11-19 17:06 −06:00 (23:06 UTC); NEWS says "Friday, November 20, 2026", the release commit's author date being 2026-11-20 00:36 +02:00. Both dates are right in their time zones |
| C4 | Intermediate releases 14.3.1 (08-13), 14.4.0 (08-26), 14.5.0 (09-21), 14.5.1 (09-30), 14.6.0 (10-05), 15.0.0 (10-22), 15.1.0 (11-04) (deep dive) | Verified | Tag dates. 14.5.1 was tagged 2026-09-30 18:09 −06:00, which is 2026-10-01 UTC, matching NEWS "Thursday, October 1, 2026" |
| C5 | Every graded item's commits land between August and 19 November, "2 to 5.6 months after every stated frontier cutoff (Claude June 2026; OpenAI 18 May to 1 June 2026)" (report) | Corrected | The item commits identified so far run from `c14ad7c6` (2026-08-09, AAT insertion at end) to `d44ad4f5` (2026-11-19 20:59 UTC, zeroed positions). The gap is 2.3-5.6 months from a 1 June cutoff and 2.7-6.1 months from 18 May. Read as the end of June, Claude's cutoff gives **1.3-4.7 months**, so "2 months" holds only if "June 2026" means early June. Claude's June 2026 cutoff matches this session's own model card. OpenAI's dates are second-hand (the research note) and unverified. The per-item commit list is confirmed at the spike (S6) |
| C6 | About 55 user-visible changes: 35 P, 16 E, 3-4 V/X, "leaving about 45 gradable items" (report, deep dive) | Corrected | All 55 rows trace to NEWS lines in the right releases, and 35 P + 16 E + 1 E/X + 3 V/X = 55. "About 45" does not follow from that tally. Excluding item 32 (no confirmed public spec) and items 52-55 leaves **50 notes**. Split into their separate fixes (10, 25, 40, 44 and 47 have parts), they make **57 units**: 9 in window A, 13 in B, 35 in C. The final count depends on the spike (case yield, clean reverts, restatable E items); 45 is a plausible floor, not a count |
| C7 | 35 items are pinned precisely by the release notes plus public specs (report) | Corrected | True for the behaviour notes checked: item 4's rule is quoted from Microsoft's Khmer spec in the 14.3.0 source, right above the `<= 2` test (`hb-ot-shaper-khmer.cc` lines 227-239 at 14.3.0); item 35 names `UPPH` outright. Not true for the new-API items 48, 49 and 51: NEWS gives only their names. The instruction must carry their declarations, which exist in the 15.x headers (`hb-font.h` 1138-1139, `hb-ot-layout.h` 557-562, `hb-buffer.h` 773-785 at 15.2.0) |
| C8 | 77% of the window's commits carry AI-assistance trailers (report) | Verified | 851 of 1,101 commits from 14.3.0 to 15.2.0 (77.3%); 957 of 1,335 from 14.2.1 (71.7%); 254 of 287 from 15.1.0 (88.5%) |
| C9 | Upstream needed 795 new test lines and 97 new fonts (report) | Verified | `.tests` files from 14.3.0 to 15.2.0: +795/−5 over 39 files (14 new, 25 changed). 97 fonts added under `test/shape/data`, by release 1, 3, 2, 0, 4, 2, 34 and 51 |
| C10 | Upstream itself changed five expectation lines (report) | Corrected | Five lines were removed, but only **two are changed expectations**. One is `arabic-stch.tests` (exact-fit stretch tiles). The other is `vertical.tests`, `NotoSans-VF` at `wght=700`, where a y offset moved from −954 to −955 after the extents-rounding change. The other three are a commented-out case, a comment and a directive. The conclusion stands: never promise that existing tests keep passing |
| C11 | HarfRust tracks every release; its port of 15.2.0 is a second public copy (report) | Partly verified | NEWS records HarfRust updates to 0.14 (14.6.0), 0.15 (15.0.0) and 0.16.1 (15.2.0). HarfRust's "Matches HarfBuzz 15.2.0" is on its own README, unverified |
| C12 | SWE-EVO, SWE-Chain and RoadmapBench use pre-cutoff releases and upstream tests (report) | Unverified | Second-hand from the research note; no paper re-read |
| C13 | No Forge task shapes text (report) | Verified | harbor-lh has 664 Forge tasks. The near ones are font containers (`bdf-pcf-font`, `cff-font`, `eot`, `woff2`) and Unicode algorithms (`bidi-uax9`, `rewrite-unicode-go`). `cff-font`'s instruction excludes GSUB and GPOS outright |
| C14 | SWE-smith-cpp holds no HarfBuzz rows (report) | Unverified | External dataset |
| C15 | First C++ task, first text-and-font task and first forward-port in SWE-M2 (report) | Corrected | Text-and-font ✓ and forward-port ✓: neither exists on `main` (`ff9359f`). But `openfoam-rebuild`, also on `main`, is a from-scratch rebuild with a C++ toolchain. Corrected: **the first task that changes an existing C++ library** |
| C16 | A probe measured base recall at 0.951 on one function (report) | Unverified | Round-1 model probe; no model runs in Phase A. Not needed for the design: base code is never graded |
| C17 | Ship the 14.3.0 tree with history cut and `perf/` removed (report) | Verified, extended | `perf/` has 25 files at 14.3.0. More "benchmark" sources: `subprojects/google-benchmark.wrap`, the `benchmark` option in `meson_options.txt`, `.github/` and `.ci/`. **New finding:** the 14.3.0 root has `AGENTS.md`, `CLAUDE.md` and `CODE_OF_AI_CONDUCT.md`. claude-code loads `CLAUDE.md` as instructions, so these must be read and judged (QA lens 19) |
| C18 | Offline OpenType, Microsoft script, Apple TrueType and Unicode 18 documents can ship with the task (report) | Unverified | Redistribution licences not read. The Unicode data licence (expected to be Unicode License v3) is checked at download. Fallback for the others: our own digests (SPIKE S9) |
| C19 | HarfBuzz's in-house test fonts have no known licence and must not be hidden fonts (report) | Verified | Licence files under `test/shape/data` exist only in `aots/` and `text-rendering-tests/` (`COPYING`, `README`, `Selawik-README.md`). The 211 in-house fonts at 14.3.0 (306 at 15.2.0) have none |
| C20 | Noto fonts are OFL-1.1 (report) | Unverified | No font downloaded. Each font's licence file and `name` table are checked at download (SPIKE S5) |
| C21 | PR #6735 changed `<= 2` to `< 2`, and 8 of its 16 cases already passed before the fix (report) | Verified | 15.1.0 → 15.2.0 diff of `hb-ot-shaper-khmer.cc`: `num_coengs <= 2` → `num_coengs < 2` (plus #6558's cut recording); `khmer-misc.tests` +16 lines. Commit `e8451366` says "Eight cases fail before the fix" |
| C22 | The notes state rules as conditions ("only when it is the first or second coeng", "when `GPOS` has no kerning feature") (report) | Verified | NEWS 15.2.0 lines 38-45, 33-34 and 60-62, verbatim |
| C23 | Revert commits for R_k on 15.2.0 items: `e845136`, `20b05e0`, `3aa3e2d`, `3df546b`, `5795f86`, `59fa8f0`, `2831a8a`, `bc7dff9`, `97d8794`, `641971d`, `fd57025` (deep dive) | Verified, one correction | All 11 exist, have one parent, lie in 15.1.0..15.2.0 and are dated 2026-11-10 to 11-18; their subjects match the items. Correction: `fd57025` (#6558) records `HB_MAX_SYLLABLE_LENGTH` cuts. The likelier commit for item 12 (a match 15 syllables later) is `b35dd1d4` (#6672, "Stop skipped glyphs from crossing syllable boundaries"). The reverts decide (S6) |
| C24 | 1,101 commits (953 in `src/`), 332 in shaping scope; by committer month June 37, July 1, Aug 69, Sep 22, Oct 86, Nov 117 (deep dive) | Verified | Exact match, same path set |
| C25 | All 38 June-July shaping-scope commits come from the excluded beyond-64k branch; 5 were authored in November 2025 (deep dive) | Verified | All 38 are reachable from the second parent of merge `1c06f054` ("Merge pull request #5655 from harfbuzz/beyond-64k", 2026-10-02, so they entered in 14.6.0) and none from its first parent. Five author dates fall in 2025-11 |
| C26 | 14.3.0 contains the beyond-64k code compiled out; 15.0.0 turned it on (deep dive) | Partly verified | NEWS 14.6.0: "remains disabled by default"; NEWS 15.0.0: "now enabled by default". `hb-config.hh` at 14.3.0 not on disk |
| C27 | The 15.2.0 NEWS entry is 145 lines; 31 of 336 non-blank lines from 14.3.1 to 15.2.0 are "Various …" lines (deep dive) | Verified | Exactly 145 lines; 31 of 336 lines contain "various" (24 begin "Various", 7 "Fix various" or similar) |
| C28 | fontTools' support for `morx`, `kerx` and `trak` is unverified (report) | Corrected | From fontTools 4.60.2's source: `morx` with all five subtable types, plus `mort`, `trak`, `ankr`, `feat`, `ltag` and `bsln`, are compiled; `kern` compiles format 0 and keeps other formats as raw bytes. **There is no `kerx` module.** So `kerx` (items 23, 25a, 25b, 27) and the AAT `kern` state tables (20, 25c, 27) need our own assembler. Newer fontTools not checked (S4) |
| C29 | HarfBuzz is under the "Old MIT" licence (deep dive) | Verified | `COPYING` at 15.2.0 |
| C30 | Beyond-64k, `DMAP`, `FeatureVariations` 1.1 and `CBDT` format 19 stay out unless a public spec text exists (report) | Corrected | `CBDT` format 19 is a format of the public OpenType `CBDT` table, and fontTools writes it (`cbdt_bitmap_format_19`), so item 50 stays in as a precise note (confirm in the offline spec, S9). The other three stay out |
| C31 | The deep dive's item table matches NEWS (deep dive) | Verified | Every row checked against NEWS 15.2.0 lines 1-366 |
| C32 | 15.0.0 restructured the code a 14.x product builds on, so 15.x cannot be taken wholesale (report's work-order story) | Verified as plausible | 15.0.0 enabled 24-bit formats by default, ended support for overriding atomic operators and deprecated `hb_font_set_face()` (NEWS). Layout code was templated across table widths, for example `87454172` "[ot] Share mark attachment positioning across table widths" and `1ea14e1c` (cursive attachment). A frozen product has real reasons, and the agent ports behaviour into pre-rewrite code |
| C33 | The Unicode 18 items are "P with UCD 18" (deep dive) | Corrected | 15.2.0's generated USE table records its inputs: `IndicSyllabicCategory-18.0.0` dated 2026-07-02, `IndicPositionalCategory-18.0.0` 2026-06-24, `ArabicShaping-18.0.0` 2026-08-18, `Blocks-18.0.0` 2026-07-08, `Scripts-18.0.0` 2026-06-29, and **`DerivedCoreProperties-17.0.0`** (2025-07-30). These are pre-release 18.0 files plus a 17.0 file. Shipping the final 18.0.0 files could make a correct regeneration differ from 15.2.0. The task must ship the versions upstream used, or keep only code points where a regeneration from the shipped files matches the release (S7) |
| C34 | The table generators run offline (implied by "P with UCD 18") | Corrected | `gen-ucd-table.py` and `gen-use-table.py` import packTab, and `update-unicode-tables.make` installs it from GitHub on demand. packTab must be in the image. The full input list is in DESIGN.md section 2 |
| C35 | Outputs are integer sequences (deep dive) | Verified | `.tests` lines: `glyph=cluster@x,y+advance` and flags, for example `khmer-misc.tests` at 15.2.0. API outputs we choose are integers too |
| C36 | The verifier build after a 9.6 h session is the platform's known failure (report) | Verified | `PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md` (harbor-lh): 4 of 4 capped steps trials with heavy images lost on 2026-11-19; graded on 2026-11-20 (2 trials) and in the 2026-11-24 probe (n = 1 per layout) |
| C37 | Human horizon 1-2 weeks for an expert, 3-6 for a strong C++ engineer; frontier 0.35-0.65, mid-tier 0.10-0.30; build 9-13 person-days (report) | Estimate | Unchanged except build cost, revised to 12-17 person-days (DESIGN.md section 11) |
| C38 | `meson_options.txt` lets one minimal configuration build every tree (implied by the verifier plan) | Verified | The file is identical at 14.3.0 and 15.2.0 (same blob) |
| C39 | ragel is needed only to develop HarfBuzz itself (implied) | Corrected | 15.2.0's `src/meson.build` regenerates every `.rl` machine at build time when ragel 6.10 is found. 15.2.0 changed `hb-ot-shaper-use-machine.rl` (item 3). Agent image and verifier must both have ragel 6.10, and the instruction says the build regenerates machines |
| C40 | The Unicode 18 units can be regenerated from the UCD files (implied by "P with UCD 18") | Corrected | Upstream's Unicode 18.0 update `cdbe72ca` (14.5.0, #6242) also changed `src/ms-use/IndicSyllabicCategory-Additional.txt` (+7/−10, for example dropping a `Consonant_With_Stacker` entry for U+11A3A) and `IndicPositionalCategory-Additional.txt` (+4/−2). These are Microsoft's USE overrides and cannot be derived from the UCD. They ship as specification data (SPIKE E11), or the affected code points are dropped. Raised by the panel's opus judge, checked the same day |

**What changes for the pick.** None of the corrections removes the case for the task. Three make the build harder
than the report assumed: no `kerx` writer in fontTools (C28), the Unicode data-version trap (C33) and the API items'
declarations (C7). Two sharpen it: the in-tree spec quote makes item 4 fully learnable (C7), and the beyond-64k
rewrite means the agent cannot paste 15.x code (C32). The report's readiness score of 3 holds only if the spike
retires C28 and C33.

## Item inventory

Ratings: **P**, the note plus a public spec pins the behaviour; **R**, an example-dependent note (the deep dive's
E) that we restate as a precise behaviour rule, kept only if the rule determines the release's output on every
case; **X**, out. Commits are candidates found by subject in the clone (each exists locally). The revert
mutants decide which commits make each item (S6). Fonts: N = Noto, S = synthetic (ours), A = synthetic via our
AAT/`kern` assembler.

| Id | Rel. | Win. | Fam. | Note (condensed from NEWS) | Rating | Candidate commits | Fonts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 26 | 14.3.1 | A | F4 | AAT insertion at the end of the text | R | `c14ad7c6` (#6142) | S (`morx`) |
| 11 | 14.4.0 | A | F1 | Arabic Windows-1256 fallback shaping on all platforms | P | `03c3e45d` (#6209) | S |
| 30 | 14.4.0 | A | F6 | `avar` mapping in fonts that repeat the boundary entries | P | `efdb61f4` | S |
| 36 | 14.4.0 | A | F8 | Positions and extents saturate instead of overflowing | P | about 30 commits of 2026-08-12, for example `507b52e0`, `2a2a3792`, `d8927d1b` | S |
| 33 | 14.5.0 | A | F7 | Unicode 18.0 data and script support (Jurchen, Proto-Cuneiform, Seal) | P with data | `bf93d867`, `cdbe72ca` (#6242) | S |
| 35 | 14.5.1 | A | F7 | BCP 47 `fonupa` maps to `UPPH` | P | `d84e253c` (#6299) | S |
| 37 | 14.5.1 | A | F8 | Overflow fixes in extents scaling, synthetic slant and emboldening | R | `873dbc1e` (#6275), `3c8a65ed` (#6296) | S |
| 16 | 14.6.0 | A | F2 | Shaping failures from out-of-range glyph ids (regression from 11.4.0) | R | `2994c4d0` (#6321), to confirm | S |
| 47a | 15.0.0 | A | F8 | `hb_font_set_face()` resets font funcs (deprecated) | P | `ef64f7ea`, `5365d272` | S |
| 32 | 14.6.0 | – | F6 | `FeatureVariations` 1.1 lookup variations | X (no confirmed public spec) | `2c05df74` | – |
| 10a | 15.1.0 | B | F1 | Arabic fallback: wrong ligatures when a component is missing | R | `d0b38a79` (#6474) | S |
| 10b | 15.1.0 | B | F1 | Arabic fallback: disappearing marks in legacy fonts | R | `31e89218` (#6454), to confirm | S |
| 19 | 15.1.0 | B | F3 | `COLR` extents and mark positioning with empty layers | R | not identified yet | S |
| 25a | 15.1.0 | B | F4 | `kerx` formats 1 and 2 | R | `a92e0996` (#6538), `88e5077a` (#6494), `90417543` (#6540) | A |
| 25b | 15.1.0 | B | F4 | `kerx` format 4 mark positioning (a 14.3.0 regression) | R | PR #6537 (merge `436f067b`) | A |
| 25c | 15.1.0 | B | F4 | `kern` and `mort` with a non-first initial state | R | `ec4a38c4` | A, S (`mort`) |
| 31 | 15.1.0 | B | F6 | `gvar` intermediate tuples | P | `c2076625` (#6468) | S |
| 34 | 15.1.0 | B | F7 | Indic shaping of the Unicode 18 Devanagari and Bengali additions | P with data | `0e6a9c81` (#6544) | S |
| 44a | 15.1.0 | B | F8 | Fallback vertical descender without `vhea` | R | `879be16f` (#6466) | S |
| 44b | 15.1.0 | B | F8 | Hanging baseline fallback for some scripts | R | `f030bd21` (#6467) | S |
| 45 | 15.1.0 | B | F8 | `hb_ot_layout_lookup_collect_glyph_alternates()` no garbage | P | `041e5a31` (#6482) | S |
| 46 | 15.1.0 | B | F8 | `hb_face_create_or_fail()` accepts named-instance bits | P | `bd306afe` (#6571) | S |
| 51 | 15.1.0 | B | F8 | New `hb_buffer_deserialize_glyphs2()` / `_unicode2()` | P with declarations | `2db1b3ab` (#6552) | S |
| 1 | 15.2.0 | C | F1 | Indic: no `init` on a first syllable after a letter or mark in the pre-context | P | `5795f869` (#6713) | N |
| 2 | 15.2.0 | C | F1 | USE: a space is no base for a dependent vowel (dotted circle) | P | `0ff5835b` (#6765), to confirm | N |
| 3 | 15.2.0 | C | F1 | USE: words end at spaces and symbols for `isol`/`init`/`medi`/`fina` | R | `20b05e0d` (#6764) | N |
| 4 | 15.2.0 | C | F1 | Khmer: one Coeng Ro moves, only when it is the first or second coeng | P | `e8451366` (#6735) | N |
| 5 | 15.2.0 | C | F1 | Hangul tone mark at text start: one dotted circle | P | `59fa8f0c` (#6712) | N |
| 6 | 15.2.0 | C | F1 | Inserted dotted circles keep their advance without `GDEF` | R | `2831a8a4` (#6711), `74fc8c86` (#6710) | S |
| 7 | 15.2.0 | C | F1 | Prohibited vowel sequences: dotted circle also across default ignorables | P | `955f9751` (#6767) | N |
| 8 | 15.2.0 | C | F1 | Hebrew composes presentation forms when `mark` is only under `DFLT` | P | `7374f9c6` (#6738) | S |
| 9 | 15.2.0 | C | F1 | Arabic `stch` tiles centred on short words and exact fits | R | `3aa3e2db` (#6763), `3df546b9` (#6733) | N, S |
| 12 | 15.2.0 | C | F2 | Per-syllable `GSUB` lookups no longer match 15 syllables later | P | `b35dd1d4` (#6672) or `fd570251` (#6558) | N |
| 13 | 15.2.0 | C | F2 | Precomposed characters no longer stay decomposed in text with no marks | P | `bc7dff9a` (#6705) | N |
| 14 | 15.2.0 | C | F2 | A global feature request overrides earlier ranged requests | P | `5d9dfde2` (#6704) | N, S |
| 15 | 15.2.0 | C | F2 | Unsupported character + variation selector gets the buffer's not-found glyph | P | `97d87944` (#6699) | S |
| 17 | 15.2.0 | C | F3 | `GPOS` marks no longer attach to an earlier base (regression from 7.0.0) | R | `1e055f1e` (#6736) | S |
| 18 | 15.2.0 | C | F3 | Fallback mark positioning uses the base's x offset | P | `641971dd` (#6701) | S |
| 20 | 15.2.0 | C | F4 | Cross-stream `kern`: reset value and axis scale | P | `45c39d96` (#6732), `2701661a` (#6769) | A |
| 21 | 15.2.0 | C | F4 | `kern` in vertical text when `vkrn` is requested and `GPOS` lacks it | P | `86ea053f` (#6734) | S |
| 22 | 15.2.0 | C | F4 | `trak` in vertical text: positive tracking increases spacing | P | `45c7759a` (#6700) | S (`trak`) |
| 23 | 15.2.0 | C | F4 | `kerx` pair and class kerning with `GPOS` when `GPOS` has no kerning feature | P | `46174bb6` (#6761) | A |
| 24 | 15.2.0 | C | F4 | AAT: a later request for a feature overrides earlier ones | P | `f346ea17` (#6714) | S (`morx`) |
| 27 | 15.2.0 | C | F5 | Unsafe-to-break flags with cross-stream kerning | R | `e079f056` (#6747) | A |
| 28 | 15.2.0 | C | F5 | Unsafe-to-break flags with `HB_BUFFER_CLUSTER_LEVEL_GRAPHEMES` | R | `7f0fe356` (#6706), to confirm | N |
| 29 | 15.2.0 | C | F5 | Archaic trailing jamo after a Hangul syllable: unsafe-to-break at character levels | R | `8e6c16ee` (#6709), to confirm | N |
| 38 | 15.2.0 | C | F8 | Scaled extents round outward on both axes, after scaling | P | `f5e925cd` (#6707), `ec4f0d9d` | S |
| 39 | 15.2.0 | C | F8 | Empty glyphs have zero extents | P | `46ab0d09` (#6685) | S |
| 40a | 15.2.0 | C | F8 | `hb_style_get_value()`: `OS/2` optical size in points | P | `b14a94e5` (#6695) | S |
| 40b | 15.2.0 | C | F8 | `hb_style_get_value()`: slant includes synthetic slant | P | `4bcdffbd` (#6743) | S |
| 40c | 15.2.0 | C | F8 | `hb_style_get_value()`: skips `STAT` values for older sibling fonts | P | `2bbe878a` (#6755) | S |
| 41 | 15.2.0 | C | F8 | `hb_face_collect_unicodes()` covers `cmap` format 13 | P | `9644ff2a` (#6597) | S |
| 42 | 15.2.0 | C | F8 | Nested `glyf` components with anchor points | P | `7684854b` (#6749) | S |
| 43 | 15.2.0 | C | F8 | `hb_buffer_get_glyph_positions()` zeroes items added after the first call | P | `d44ad4f5` (#6803) | S |
| 47b | 15.2.0 | C | F8 | `hb_font_set_face()` does nothing (replaces 47a) | P | `d71578d1` (#6787) | S |
| 48 | 15.2.0 | C | F8 | New `hb_font_create_without_funcs_or_fail()` | P with declaration | `e5630586` (#6651) | S |
| 49 | 15.2.0 | C | F8 | New `hb_ot_layout_get_extender_glyphs()` (`JSTF`) | P with declaration | `aa7a824c` (#6568) | S |
| 50 | 15.2.0 | C | F8 | `CBDT` format 19 bitmaps | P (C30) | `ebb58687` (#6754) | S |
| 52-55 | 14.6.0-15.2.0 | – | – | `DMAP`, beyond-64k, the number parser, raised work limits | X | – | – |

Every "R" restatement is written in Phase B, beside its derivation path (QA gate item 1). Windows (release tags
on the cases; the task itself is single-step since 2026-11-26): A = 14.3.1 to 15.0.0, B = 15.1.0, C = 15.2.0.

## Failure sentence and its proof plan

**The sentence.** "Agents reproduce each release note's new behaviour on the sequences it describes but apply the
rule beyond its stated condition, so neighbouring sequences that upstream left unchanged regress."

The B family is H_dual: held-fixed cases built as neighbours of each conditional note, one stated condition
negated. It enters the reward only through the gate (DESIGN.md section 6). The B-mutant is **W**.

### 1. It is documented, so a careful agent can learn the rule

- The notes state the conditions in words (C22), and the instruction states the general rule as the requester's
  need: anything the notes do not change comes out as it does today.
- Unlike almost every other rule in the task, the duals have an oracle the agent can run: its own build of the
  untouched 14.3.0 tree. Building the base once, keeping it beside the work tree and diffing outputs for neighbour
  inputs is ordinary practice for a maintainer porting fixes. The base tree also ships upstream's 14.3.0 test
  suite (`test/shape/data`), which pins hundreds of unchanged behaviours.
- For each conditional note, the Phase B derivation (QA gate item 1, §13 step 2 of the grading guide) records: the
  note's sentence; the spec paragraph (for item 4, the spec quote already in the 14.3.0 source); and one probe
  command on the base build that shows a neighbour's output, which must stay the same.

### 2. It is plausibly missed, and why

- **The fixes are narrow, so a slightly broader fix looks right.** #6735 is a one-token change, and 8 of its 16
  upstream cases passed before it (C21). Stopping every coeng move after the first Coeng Ro, or suppressing `init`
  after any pre-context character, passes the note's own examples.
- **No oracle exists for the new behaviour, but one exists for the old.** Agents check the positive example they
  construct. Checking neighbours needs a second build and a diff harness, which nothing in the work asks for
  outright.
- **Later releases revise earlier fixes** (`hb_font_set_face()`, the `kern` and `kerx` fixes, Arabic fallback), so
  a later note can regress cases an earlier one got right.
- **Published pattern.** Long-horizon agents break existing functionality while adding features: the C compiler
  report, SWE-Chain's "struggle to preserve existing functionality" (second-hand via the research notes, not
  re-read).
- **The competing explanation is throughput.** Agents may simply not reach many items, F4 and F5 above all, because
  they need fonts the agent must assemble. If that dominates, the sentence is wrong for those agents; section 4
  tells the two apart.

### 3. It is provable by a named mutant that moves only its family

**Mutant W (condition-widened).** Built from 15.2.0, it removes the stated condition from every
conditional note:

| Item | W's widening |
| --- | --- |
| 1 | No `init` after any pre-context character (punctuation and space included) |
| 2 | Every space-like character (NBSP among them) refused as a base |
| 3 | Words end at every non-letter |
| 4 | Coeng handling stops after the first Coeng Ro wherever it sits |
| 7 | A dotted circle whatever stands between the two vowels |
| 8 | Presentation forms composed even when `mark` sits under `hebr` |
| 12 | Per-syllable restriction applied to every lookup |
| 14 | Any later request overrides, ranged over global included |
| 15 | The not-found glyph also when the base character is in the font |
| 17 | The base search stops at the nearest base for every mark lookup |
| 18 | The base's y offset applied too |
| 21 | `kern` in vertical text whether or not `vkrn` is requested or present in `GPOS` |
| 22 | The tracking sign flipped in horizontal text too |
| 23 | `kerx` applied even when `GPOS` has a kerning feature |
| 24 | A later request wins even across different features of one type |
| 39 | Zero extents for any glyph without contours, composites included |

Each widening is a few lines in the release's source. The list is final after the spike shows which duals exist.
The pre-run checks follow the grading guide §13 and are QA gate item 12:

1. **Signature.** W scores at least 0.98 on the changed cases (D), fails at least 50% of the duals (h_d ≤ 0.5),
   keeps h_b ≥ 0.95, and keeps every family F1-F8 at least 0.95. Its reward lands in 0.60-0.85; the dual weight
   (0.20-0.35) is set here. No R_k, and no flags revert R_flags, produces the same signature: each R_k drops one
   unit by at least 3 cases and leaves the duals whole.
2. **Learnability.** The derivation write-up above, one per conditional item, written before upload.
3. **Difficulty ordering without models.** Per family, record how many stated conditions it carries, whether the
   docs state them in words, the base-versus-target lines changed, and whether the agent must build its own font.
   The duals must rank hard on "needs a differential check against the base". If F4 ranks hardest on everything,
   expect throughput to dominate, and say so before the first run.
4. **Optional cheap pilot** (owner's OK needed, off-platform): a short local session limited to two conditional
   notes, to see that the duals are neither trivial nor impossible.

### 4. Confirmed or refuted after the first trials

Cases carry unit and family tags, so labelling is free. The sentence holds in a trial when its agent's dual failure
rate on units it implemented (p_k ≥ 0.5) is at least 15% and at least three times the rate on units it left alone.
It is confirmed if that holds in at least two of the first three accepted runs. If instead most of the lost reward
is unimplemented units, the sentence is replaced by the fallback below.

### 5. If the sentence turns out invalid

- **Fallback sentence** (throughput on self-built fonts): "Agents land the script-shaper and API notes but not the
  AAT and `kern` notes, because those need fonts they must assemble themselves and the specifications only describe
  binary tables." The B family is F4; the proving mutant is R_F4 (every F4 item reverted). F4 has 9 units, about
  16% of D, so R_F4 lands near 0.84, inside the band.
- **Secondary diagnostic** (kept either way): "fixes update glyphs and positions but not the unsafe-to-break flags
  the same stage emits" (F5, 3 units, R_flags). Too small to headline.
