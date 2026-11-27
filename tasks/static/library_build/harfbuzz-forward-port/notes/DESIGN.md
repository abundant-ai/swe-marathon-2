# HarfBuzz forward-port, 14.3.0 → 15.2.0: design (Phase A)

Author notes, never shipped to the agent. Phase A is design only: nothing in this file has been built, run or
measured unless it says so. Facts marked **(m)** were read on 2026-11-26 from the research clone of
`harfbuzz/harfbuzz` (blobless, HEAD `197a6b9`) with lazy fetching disabled, so only objects already on disk were
read. Claims about upstream are checked one by one in [CLAIMS.md](CLAIMS.md); the pre-upload gate and QA lenses
are in [QA-PLAN.md](QA-PLAN.md); the spike and the download list are in [SPIKE.md](SPIKE.md).

**Single step since 2026-11-26.** The owner parked multi-turn ("we dont have to promote multi-turn as well so make
stuff likewise"). The task is one instruction and one 34,560 s session from 14.3.0 to 15.2.0, graded once against
15.2.0. That is the grading of the old step 3. The three-step plan is kept in [STEPS.md](STEPS.md) as history. On
2026-11-27 the owner added: "if its hard enough in single turn make sure to have it difficult enough". The sizing
that follows from it is section 13.

## 1. The task in one paragraph

A company ships HarfBuzz 14.3.0 inside its product and has frozen that build. Upstream has since shipped eight
releases (14.3.1 to 15.2.0, 2026-08-13 to 2026-11-19 **(m)**) whose shaping, layout, metrics and API fixes the
product needs, but 15.0.0 also turned on the 24-bit "beyond-64k" table formats by default and the code it
builds on was restructured, so the product cannot take 15.x wholesale. The agent gets the 14.3.0 tree, the
relevant release notes, the specifications those notes rely on, and a toolchain, and lands the listed changes
in the tree in one session. A separate verifier compiles the delivered tree from source and
compares integer outputs on private fonts and strings with outputs recorded from the upstream releases. Only
behaviour that the listed notes changed is credited; behaviour they did not change must stay as it was.

The upstream commits identified so far for the graded items are dated 2026-08-09 to 2026-11-19 UTC **(m)**, after
the June 2026 training cutoff of the current Claude models and after the 2026-05-18 to 2026-06-01 OpenAI cutoffs
the research note cites (CLAIMS.md, C5; the full per-item commit list is confirmed at the spike). Recall of
14.3.0's code helps the agent find its way and is never graded.

## 2. What the agent gets

| Path or item | Contents | Notes |
| --- | --- | --- |
| `/app/harfbuzz` | HarfBuzz 14.3.0, tag commit `4c2aa804671d7276e8a0eb95da07202ead05c843` **(m)** | Fresh repository with one commit, so history stops at the base. Pruned by `environment/prune_tree.sh`: `perf/`, `.github/`, `.ci/`, `.codecov.yml`, `CODE_OF_AI_CONDUCT.md`, `CLAUDE.md`, `AGENTS.md`, `README.mingw.md`, `TESTING.md`'s profiling pointer, `test/vector/README.md`, `subprojects/google-benchmark.wrap` and the `benchmark` option with its meson wiring. Kept: `src/`, `test/` (upstream's own tests and fonts for 14.3.0 behaviour), `util/`, `docs/`, build files. |
| `/app/docs/notes.md` | The instruction's notes, 14.3.1 to 15.2.0 | The instruction's notes section under its own heading and one introductory sentence (packaging checks that the bodies agree). |
| `/app/docs/specs/` | 51 notes in our own words: 34 OpenType table and registry pages, UAX #29, 8 Apple AAT pages, 8 Microsoft script-development pages, and `NOTICE.md` | The source pages carry no redistribution licence (CLAIMS.md C18), so nothing is copied beyond names, identifier tables and formal rules; material the pages cite without defining is not restated (section "Scope decisions of Phase C"). |
| `/app/docs/unicode/` | The data files upstream's table generators read, as upstream used them for 15.x: Unicode 18.0 `UnicodeData.txt`, `Scripts.txt`, `Blocks.txt`, `ArabicShaping.txt`, `IndicSyllabicCategory.txt`, `IndicPositionalCategory.txt`, `emoji-data.txt`, `emoji-test.txt`, `ucd.nounihan.grouped.zip`, and `DerivedCoreProperties.txt` from Unicode 17.0.0; Microsoft's USE override files under `ms-use/`; the Unicode licence | Fetched by the image build with sha256 checks. The two sources of the language tag table (the IANA registry and Microsoft's tag list) are not shipped; the instruction says so. |
| Toolchain | gcc/g++ 13, meson, ninja, pkg-config, ragel 6.10, Python 3, fontTools, packTab, GLib development files (for `util/hb-shape`), git | `src/meson.build` regenerates the ragel machines when ragel 6.10 is found **(m, 15.2.0)**, so agent and verifier must both have it. packTab is what `gen-ucd-table.py` and `gen-use-table.py` import **(m)**. |
| Absent on purpose | Any 15.x source or binary; any package that bundles HarfBuzz (uharfbuzz, skia-python and the like); HarfRust crates; network | The leak scan (QA item 11) checks the image for every `libharfbuzz*`, `hb-version.h` and HarfBuzz version string. |

## 3. What the agent delivers

The tree at `/app/harfbuzz`, declared as the task artifact. The instruction states the product's build exactly,
because the verifier uses it:

```
meson setup build --buildtype=release -Ddefault_library=static \
  -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dchafa=disabled -Dicu=disabled \
  -Dfreetype=disabled -Dpng=disabled -Dzlib=disabled -Dgraphite2=disabled \
  -Draster=disabled -Dvector=disabled -Dgpu=disabled -Dsubset=disabled \
  -Dtests=disabled -Dintrospection=disabled -Ddocs=disabled -Dutilities=disabled
ninja -C build
```

`meson_options.txt` is identical at 14.3.0 and 15.2.0 **(m)**, so one command builds every tree. With ICU, GLib and
FreeType off, the library uses its own Unicode tables and its own OpenType font functions, which is what makes
the Unicode 18 items observable. The spike times this build (SPIKE.md S2).

## 4. The hidden reference and how it stays invisible

- **The reference** is upstream's source at 15.0.0 (`35f656a1…`), 15.1.0 (`3df40d9b…`) and 15.2.0 (`ed51d202…`),
  with 14.3.0 as the base; full hashes in [SPIKE.md](SPIKE.md). The reverted mutants R_k (section 5) are built
  from the same tags.
- **Where outputs come from.** A build host (Linux x86_64, the verifier's own pinned base image and apt
  snapshot) builds every tree with the command above, runs the sweep, attributes cases and records gold.
  The verifier image holds only the selected cases, our fonts, the gold outputs, the drivers' source and the
  toolchain. It compiles no reference, which keeps its build light: a heavy image rebuilt after a capped run is
  the platform's one known way to lose a trial (`PLATFORM_VERIFIER_BUILD_AFTER_LONG_RUN.md`). The oracle at 1.0
  on the platform, twice, is the check that host and image agree.
- **Agent container.** No 15.x code, no gold, no private fonts, no case lists. The oracle's `solution/` (the
  14.3.0 → 15.2.0 upstream patch, generated, git-ignored) is uploaded only for oracle runs.
- **Verifier container.** Separate (`environment_mode = "separate"`), no network at grade time. Gold and case
  files are owned by root, mode 0700. The delivered tree is built, and the driver runs, as an unprivileged
  `builder` user that cannot read them: the tree's own `meson.build` can run arbitrary commands at configure
  time, and the library's code runs inside the driver, so either could otherwise read the answers. The driver
  writes outputs to a scratch directory; a root process compares them after the driver exits.
- **Public repository.** This folder holds no case, seed, gold output or private font. They live in git-ignored
  `private/` working copies (see `.gitignore`), backed up as a git bundle in harbor-lh
  (`ops/swe-marathon-v2/next-tasks/harfbuzz-forward-port-private/`).

## 5. Cases, attribution and the families

**The sweep space.** Fonts × strings × options.

- *Fonts.* Noto fonts (OFL-1.1) for the script items: Khmer, Myanmar, Devanagari, Bengali, Balinese, Javanese, Tai
  Tham, Korean, Hebrew, Syriac, Arabic. Fonts we build for the rest with fontTools: `feaLib` for GSUB, GPOS and
  GDEF variants (no GDEF, `mark` only under `DFLT`), `varLib` for `avar` and `gvar` edge cases, `colorLib` for
  COLR, plus `morx`, `mort` and `trak`, which fontTools compiles **(m, fontTools 4.60.2 source)**. fontTools has no
  `kerx` module and keeps `kern` formats other than 0 as raw bytes **(m)**, so `kerx` and the AAT `kern`
  state tables come from a small table assembler of ours (SPIKE.md S4). Upstream's in-house test fonts are
  never used: no licence files exist for them **(m)**, and with the public `.tests` lines they are an answer key.
- *Strings.* Generated per script from the syllable grammars in the Microsoft specs (valid and broken syllables,
  dotted-circle triggers), with pre- and post-context, plus boundary sequences around each note's condition.
- *Options.* Global and ranged features, direction (including vertical), script and language, cluster levels 0 to 3,
  buffer flags, the not-found glyph, variations, scale and ppem, synthetic slant and bold.
- *Observables.* Shaping: glyph ids, clusters, advances, offsets, and glyph flags where the case asks for them.
  API: glyph extents, font and fallback metrics, baselines, `hb_style_get_value()`, collected sets (printed
  sorted), face creation results, deserialization progress, extender glyphs. Every value is an integer.

**Builds.** Base B = 14.3.0; targets T1 = 15.0.0, T2 = 15.1.0, T3 = 15.2.0; for every graded item k in window s, a
mutant R_k = T_s with item k's commits reverted. Candidate commits per item are listed in
[CLAIMS.md](CLAIMS.md) (section "Item inventory"); the spike confirms each revert applies (SPIKE.md S6).

**Attribution** (per release window s, T0 = B; the windows remain the unit of attribution even though the task
is graded once, against T3):
1. A case *changes in window s* when out(T_{s−1}) ≠ out(T_s); it is graded only if out(B) ≠ out(T3) as well, so
   the base fails every graded case.
2. It belongs to item k when out(R_k) = out(T_{s−1}) and no other item's revert also explains it. Anything else is
   dropped: the "Various …" notes, the number-parser rewrite, raised work limits and the unlisted behaviour
   commits the window contains (for example `489157f8` "[ot] Ignore y hinting devices when hinting is disabled"
   and `22e7463b` "[GPOS] Keep anchor variation adjustments fractional" **(m)**).
3. A case attributed in an earlier window whose output a later item changes again moves to that item; its gold is
   always T3's output (this is how `hb_font_set_face()`'s cases move from item 47a to 47b).
4. *Held fixed*: out(B) = out(T1) = out(T2) = out(T3), and every R_k agrees. **Duals** are held-fixed cases built
   as neighbours of a note's stated condition with one condition negated (a third coeng, a space or punctuation
   pre-context, a ranged request after a global one, `GPOS` with a kerning feature, horizontal instead of
   vertical text). **Broad** held-fixed cases are sampled from text and options near no note.
5. Base outputs that vary from run to run (uninitialized memory in items 43 and 45) are classified over three
   runs; a case counts as changed only if every base run differs from the target, and flapping cases are dropped.

**Sizing** (estimates, checked by the spike): at least 20 changed cases per item where the sweep yields them,
at most 60; items with fewer than 3 are cut or merged with a neighbour. At least 50 duals for each family the
failure mode touches; about 1,000 broad held-fixed cases. In all about 1,000-2,500 changed and 2,000-4,000
held-fixed cases. Every case is tagged with its family, its item and its upstream release, so contamination
would show up as a rise on the oldest releases first.

**Families** (reporting groups; items weigh equally, see section 6):

| Family | Items (ids from CLAIMS.md) | Units |
| --- | --- | --- |
| F1 script shapers | 1-11 | 12 (10 has two parts) |
| F2 shaping plan and normalisation | 12-16 | 5 |
| F3 mark and GPOS positioning | 17-19 | 3 |
| F4 legacy `kern` and AAT | 20-26 | 9 (25 has three parts) |
| F5 unsafe-to-break flags and clusters | 27-29 | 3 |
| F6 variations | 30-31 (32 cut unless a public spec exists) | 2 |
| F7 Unicode 18 and tags | 33-35 | 3 |
| F8 metrics and API | 36-51 (40 and 44 have parts; 47b supersedes 47a) | 19 |
| H_dual (the B family) | duals of every conditional item | gate |
| H_broad | broad held-fixed | gate |

In all 56 graded units, by release window 8 (A, 14.3.1 to 15.0.0, 47a superseded), 13 (B, 15.1.0) and 35 (C,
15.2.0). The windows survive as release tags on the cases. The spike may cut some units.

### Scope decisions of Phase C (2026-11-27)

**Units cut** (scripts/pipeline/cuts.tsv; their notes stay in the instruction, ungraded):

| Unit | Reason |
| --- | --- |
| 47a | Superseded: in 15.2.0 `hb_font_set_face()` is the no-op of 47b, so nothing of 15.0.0's behaviour remains observable except a deprecation attribute, which no output shows. Its cases belong to 47b |
| 28 | Unobservable: the syllabic shapers already set the unsafe-to-break flags that 15.2.0 adds at the graphemes level, so only removals differ, which the note does not state (0 differences in 6,109 probed texts on 7 fonts) |
| 30 | Unreachable: the changed branch needs a normalized coordinate below -1, and every public way to set variations clamps to [-1, 1] before the `avar` maps |
| 50 | Rule not in the materials: format 19 takes its metrics from `CBLC` index subtable formats 2 and 5, which only the EBLC chapter defines. That chapter is not among the shipped specification notes, and 14.3.0 implements neither format (audit class c/d) |

**Inputs left out of a unit, so no case grades them either way:**

- Unit 36: values that overflowed 14.3.0's 16-bit scaler arguments (advances above 32767 units, stored extents whose
  bearing plus width passes 32767), marked `x:16bit`. 15.0.0 gives their exact values, while the note promises only
  that values saturate, so a port that saturates them at 16 bits would be as faithful to the note. Confirmed by the
  coordinator, 2026-11-27.
- Every generator leaves out what 15.2.0 changes beyond its note (each module's docstrings list them): for example
  format characters as Indic pre-context (1), a dotted circle already in the text before a Hangul tone mark (5),
  `kerx` resets (20), vertical `kerx` (21), format 17/18 glyphs through index formats 2/5 (50), STAT format 4 (40c).

**Specification notes.** The digests in `environment/docs/specs/` restate the downloaded pages only. Material the
pages cite without defining (the EBLC/EBDT formats, the baseline tag and axis tag registries, the Variations
Overview's normalization and region scalars, W3C compositing, `gvar`'s vertical phantom points, the AAT lookup
formats, and the interpretive reading notes) was cut rather than shipped unverified. Of the graded units only 50
depended on it (above); 31's per-tuple region rule is in 14.3.0's own `gvar` code, 44b's baseline tags and 40b's
slant axis are documented in 14.3.0's public headers, and the AAT lookup formats are implemented in 14.3.0.

## 6. Reward

One verifier run at the end of the session, over the graded units I, against 15.2.0:

- p_k = passed_k / n_k for each unit k, with a fixed denominator: a crash, timeout, missing output or a driver that
  does not compile fails its cases.
- D = mean of p_k over I (every unit counts the same; family scores are reported, not weighted).
- h_k = the pass fraction of unit k's duals; h_d = mean of h_k over the units that have duals (unit-equal, like D).
- h_b = the pass fraction of the broad held-fixed cases.
- **G = h_d · (1 − 0.10 · (1 − h_b))** and **reward = D · G**.

**The gate is fully multiplicative (Phase C, 2026-11-27).** The Phase A gate, G = 1 − w_d(1 − h_d) − 0.10(1 − h_b)
with w_d between 0.25 and 0.35, could take at most a third of the reward from a port that breaks every dual, and the
Phase B prototype of the over-broad mutant W scored 0.960 with it. With h_d as a factor, a port that applies
every note one condition too broadly keeps D ≈ 1 and loses exactly the share of neighbours it breaks; the duals are
drawn evenly over each unit's boundaries (one stratum per negated condition, 30 per unit), so a unit whose widening
breaks one of three boundaries keeps about two thirds of its neighbours. The broad set keeps its light weight: it
guards against general damage, which also shows in D.

A tree that does not build under the stated command scores 0, a candidate failure; a verifier fault (toolchain
missing, private inputs unreadable, the reference tree not building in record mode) leaves no reward file. The
held-fixed sets only ever multiply, so the unmodified base scores exactly 0: it fails every changed case by
construction.

`metrics.json`: per unit the pass fraction and case count of its changed cases and of its duals, per family the pass
fraction, h_d, h_b, G, D, the drivers that compiled and the build steps with their times, and each case's opaque id
with its verdict, by unit and kind (for post-run analysis; the file is the verifier's and the agent never sees it).
Every result this task reports gives D, h_d and h_b separately, not the reward alone.

**Why every unit counts the same and not every family.** The requester asked for a list of changes, and "how
much of the list works" is the plain measure. Family-equal weights would make one `gvar` fix worth as much as
eleven script fixes. The cost: F8 (metrics and API) carries about a third of D, and its units are the easiest.
That is why the expected profile below has F8 high, and why the failure mode sits in a gate rather than in D.

## 7. Stub filters

- **Nop = 0 by construction.** Every graded changed case is one the base fails, and held-fixed cases only gate.
- **Stub zoo** (must each score exactly 0.000): the unmodified base; the base with comment and
  whitespace edits; the base with behaviour-neutral refactors; a tree that does not build; a library whose
  `hb_shape()` returns an empty buffer; a library that crashes on the first call; R_all (T3 with every graded
  item reverted, which equals the base on graded cases).
- **Over-broad probes** (expected small positive scores, recorded, not required to be 0): always insert a dotted
  circle; zero every glyph's extents; flag every glyph unsafe to break; apply `kerx` and `kern` whenever present.
  Each is the failure mode in miniature, and each must lose most of its credit to the gate.
- **No path around the gate.** A wrapper cannot call a reference (none exists in the verifier); the candidate
  cannot read gold (section 4); it never sees the private fonts, so it cannot key outputs on them.

## 8. Determinism controls

- Integer outputs only; sets printed sorted; floats never printed.
- One pinned base image digest and one apt snapshot date for the gold host and the verifier, so both compile with
  the same gcc 13 build. Flags: the meson `release` buildtype, no `-march`, no `-ffast-math`.
- `env -i` with `LC_ALL=C`; no `HB_*` variables (`HB_SHAPER_LIST`, `HB_FONT_FUNCS` and `HB_OPTIONS` change
  behaviour).
- The 3+1 recording (QA gate item 5): three identical runs and one perturbed run (one CPU, a longer scratch path,
  `MALLOC_PERTURB_`, a different environment order) must give byte-identical per-case verdicts for the oracle.
- One process per font batch, with CPU, memory, file-size and process limits and a timeout, so a hang or crash
  costs only that batch's cases.

## 9. Expected scores

All figures are estimates from proxies; none has been measured. The agent rows come from section 13.

| Tree | Reward |
| --- | --- |
| Upstream 15.2.0 (oracle) | 1.000 |
| Base 14.3.0 (nop) | 0.000 |
| Upstream 15.1.0 (every window-C unit missing) | about 21/56 ≈ 0.38 |
| Mutant V, the verification-gap proof (section 10) | 0.60-0.85 |
| Mutant W, the over-broad port (a secondary bound, section 10) | measured 0.672 in Phase C |
| Frontier agents | about 0.64 (0.54-0.75; notes/PREREGISTRATION.md, from QA pass 16; target: at most about 0.6) |
| Mid-tier agents | about 0.28 (0.15-0.40) |

A healthy profile: no full solve; F8, F2 and the simpler F1 notes high; F4 (AAT and `kern`) and F5 (flags) low; the
dual gate below 0.95. Below 0.10 for mid-tier models the task risks reading as unfair or broken (difficulty note
§7), so the first trials must check that F8 and the P-rated F1 notes are reachable.

## 10. The failure mode, in one sentence

Decided by a three-judge panel on 2026-11-27 (harbor-lh `ops/swe-marathon-v2/decisions/2026-11-27-harfbuzz-failure-sentence-DECISION.md`):

> With no 15.x code or tests to check against, agents land the fixes they can confirm on their own 14.3.0 build and
> fall short on the ones they cannot, chiefly AAT/kern behaviour that needs hand-built fonts, regenerated Unicode
> data, and bugs a note describes only by symptom.

**Tiers** (QA pass 16's tiers and CLAIMS.md's families). Tier A: the note names the fix. Tier B: the agent can
check its change on its own 14.3.0 build with the shipped fonts and tools. Tier C: it cannot without material it
builds itself: AAT/`kern` and flag behaviour that needs hand-built fonts, the Unicode 18 data and its new
characters, and bugs the note describes only by a symptom. 14 units are tier A, 20 tier B and 19 tier C: pass 16's
14 tier-C units; 21, 23 and 24, AAT units pass 16 rated moderate, for which no font shipped with 14.3.0 has the
tables the note is about (the shipped test fonts have no `kerx`, no vertical `kern` header and no repeated AAT
feature request; upstream built new fonts to test 21 and 24); and 33 and 34, the decision's "regenerated Unicode
data". Units 20 and 22 are AAT units too, but their notes name the edit, so an agent can apply it without seeing
it work; they stay in tier A.

| Unit | Note | Family | Release | Tier | Why | Predicted pass |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Indic init after a letter or mark in the pre-context | F1 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 2 | USE: no space as the base of a dependent vowel (candidate) | F1 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 3 | USE word boundaries for positional forms | F1 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 4 | Khmer: one Coeng Ro, first or second coeng only | F1 | 15.2.0 | A | the note names the fix | 0.89 |
| 5 | Hangul tone mark at text start | F1 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 6 | dotted circles keep their advance without GDEF | F1 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 7 | vowel constraints across default ignorables | F1 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 8 | Hebrew composes with mark only under DFLT | F1 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 9 | Arabic stch tiles centred on short words and exact fits | F1 | 15.2.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 10a | Arabic fallback: ligatures with a missing component | F1 | 15.1.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 10b | Arabic fallback: marks in legacy fonts (candidate) | F1 | 15.1.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 11 | Arabic Windows-1256 fallback on all platforms | F1 | 15.0.0 | A | the note names the fix | 0.89 |
| 12 | per-syllable lookups 15 syllables later (alternative fd5702517) | F2 | 15.2.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 13 | precomposed characters in text with no marks | F2 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 14 | a global request overrides earlier ranged requests | F2 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 15 | missing character + variation selector: not-found glyph | F2 | 15.2.0 | A | the note names the fix | 0.89 |
| 16 | out-of-range glyph ids (candidate) | F2 | 15.0.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 17 | GPOS marks and an earlier base | F3 | 15.2.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 18 | fallback mark positioning uses the base x offset | F3 | 15.2.0 | A | the note names the fix | 0.89 |
| 19 | COLR extents and marks with empty layers | F3 | 15.1.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 20 | cross-stream kern: reset value and axis scale | F4 | 15.2.0 | A | the note names the fix (no font is needed to apply it, though one is needed to see it) | 0.89 |
| 21 | kern in vertical text when vkrn is requested | F4 | 15.2.0 | C | no shipped font has a vertical kern header; upstream built two fonts to test the fix | 0.46 |
| 22 | trak in vertical text | F4 | 15.2.0 | A | the note names the fix (no font is needed to apply it, though one is needed to see it) | 0.89 |
| 23 | kerx with GPOS lacking a kerning feature | F4 | 15.2.0 | C | no shipped font has a kerx table, and fontTools cannot write one | 0.46 |
| 24 | AAT: later feature request wins | F4 | 15.2.0 | C | no shipped font requests one AAT feature twice; upstream built morx fonts to test the fix | 0.46 |
| 25a | kerx formats 1 and 2 | F4 | 15.1.0 | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 25b | kerx format 4 mark positioning | F4 | 15.1.0 | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 25c | kern and mort with a non-first initial state | F4 | 15.1.0 | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 26 | AAT insertion at the end of the text | F4 | 15.0.0 | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 27 | unsafe-to-break with cross-stream kerning | F5 | 15.2.0 | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 29 | archaic trailing jamo flags (candidate) | F5 | 15.2.0 | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 31 | gvar intermediate tuples | F6 | 15.1.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 33 | Unicode 18.0 data and scripts | F7 | 15.0.0 | C | needs regenerated Unicode 18 data and fonts covering the new characters | 0.60 |
| 34 | Indic shaping of the Unicode 18 additions | F7 | 15.1.0 | C | needs regenerated Unicode 18 data and fonts covering the new characters | 0.50 |
| 35 | fonupa maps to UPPH | F7 | 15.0.0 | A | the note names the fix | 0.89 |
| 36 | saturating positions and extents (the 2026-08-12 stack) | F8 | 15.0.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 37 | overflow fixes in extents scaling, slant and emboldening | F8 | 15.0.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 38 | extents round outward after scaling | F8 | 15.2.0 | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 39 | empty glyphs have zero extents | F8 | 15.2.0 | A | the note names the fix | 0.89 |
| 40a | OS/2 optical size in points | F8 | 15.2.0 | A | the note names the fix | 0.89 |
| 40b | slant includes synthetic slant | F8 | 15.2.0 | A | the note names the fix | 0.89 |
| 40c | STAT values of older sibling fonts skipped | F8 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 41 | collect_unicodes and cmap format 13 | F8 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 42 | nested glyf components with anchor points | F8 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 43 | zero positions for items added after the first call | F8 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 44a | fallback vertical descender without vhea | F8 | 15.1.0 | A | the note names the fix | 0.89 |
| 44b | hanging baseline fallback | F8 | 15.1.0 | A | the note names the fix | 0.89 |
| 45 | collect_glyph_alternates garbage | F8 | 15.1.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 46 | hb_face_create_or_fail() named-instance bits | F8 | 15.1.0 | A | the note names the fix | 0.89 |
| 47b | hb_font_set_face() does nothing | F8 | 15.2.0 | A | the note names the fix | 0.89 |
| 48 | hb_font_create_without_funcs_or_fail() | F8 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 49 | hb_ot_layout_get_extender_glyphs() | F8 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 51 | deserialize2 functions | F8 | 15.1.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |

**The proof mutant V** is 15.2.0 with every tier-C unit's change taken out: `scripts/pipeline/assemble_reverts.py`
collects the 19 units' commits (and the hand-resolved reverts of 27 and 29) into `patches-lib/ALLV`, the pipeline
builds it as `mut-V`, and `scripts/pipeline/make_mutant.sh` applies it to the reference tree for the verifier;
a commit that no longer reverts cleanly is left in and listed. V must land in 0.60-0.85, lose D only on tier-C
units, and leave h_d and h_b essentially unchanged. Two companions are measured in the pipeline: **R_unbuilt**,
the panel's starting point (every F4 and F5 unit taken out, `patches-lib/ALLRu`), and **W_literal**, W without
the eight widenings QA pass 17 found not to be, or arguably not to be, over-broad readings of their notes, or no-ops
(11, 18, 25b, 31, 33, 36, 37, 44b; `patches-lib/LITW`). The over-broad mutant W is kept as a **secondary bound**:
it shows how much the gate takes from a port that widens every condition, not how agents fail. Every result
reports D, h_d and h_b separately. What would reopen the decision is in `notes/PREREGISTRATION.md`.

## 11. Effort

The report estimated 9-13 person-days. Phase A findings add work: the `kerx` and AAT `kern` assembler (fontTools
cannot write them), the Unicode data-version check and the precise restatement of the 16 example-dependent notes.
The single-step switch removes the multi-step packaging and the capped chain. Revised estimate: **11-16
person-days**, of which the spike is 2-3 days (SPIKE.md), the item inventory, fonts and case generators 5-7, the
verifier, drivers and packaging 2-3, and QA 2-3. All builds of R_k and mutants (about 60 trees of a few minutes
each) run in bounded containers of the pipeline image, never as host processes. Phase B runs them as native
arm64 containers in local Docker Desktop, with emulated amd64 samples only where the architecture matters.

## 12. Risks

| # | Risk | Effect | Mitigation | Status |
| --- | --- | --- | --- | --- |
| 1 | Heavy verifier after a capped session: the image fails to come up and the trial is lost | Ungraded trials, biased toward agents that stop early | Light image (no reference build inside); a capped oracle run before any model run | Open; platform evidence n = 1 |
| 2 | Attribution noise: unlisted behaviour commits in every window **(m)** | Cases graded on undocumented behaviour | R_k attribution drops anything no single listed item explains; QA lens 6 audits 50 random attributed cases | Open |
| 3 | Example-dependent notes (16 E items) are not pinned exactly | "Grader rejects valid work" | Restate each as a precise behaviour rule checked against the release on every case; drop it if the rule does not determine the output | Closed in fix round 1: 13 note bullets (units 3, 6, 9, 10a, 10b, 16, 17, 19, 25a-25c, 26, 27, 29, 37, 44a, 44b) carry the rule their graded cases follow, matched label by label (notes/RESTATEMENTS.md); cases a note's text does not determine are labelled `x:` (27, 29, 39) or `beyond-note` (25a) and never graded |
| 4 | Unicode data versions differ from upstream's (pre-release files, DerivedCoreProperties 17.0.0) **(m)** | Unfair Unicode 18 cases | Ship the exact files, or keep only code points where a build regenerated from the shipped files matches the release | Open, spike S7 |
| 5 | fontTools cannot write `kerx` or AAT `kern` state tables **(m)** | F4's `kerx` units (23, 25a, 25b, 27) unbuildable | Our own table assembler, validated by base-versus-target differences | Open, spike S4 |
| 6 | Offline specs may not be redistributable | Missing documentation | Our own digests of the needed sections | Open, licence check |
| 7 | Candidate build scripts or library code read the answers in the verifier | Exploit | Unprivileged `builder` user, root-only gold, compare after exit (section 4); protection probe | Design done |
| 8 | Upstream `CLAUDE.md` and `AGENTS.md` in the tree steer the agent or carry cue words | Awareness or conflicting instructions | Read after download; keep only if clean and compatible | Open |
| 9 | Mid-tier floor near 0.10 | Reads as unfair | Expected profile check on the first trials; the E-item restatements | Open |
| 10 | Decay: models trained past November 2026 (expected spring 2027) and HarfRust's public 15.2.0 port | Recall instead of work | Per-release tags; re-cut the window per model generation | Accepted |
| 11 | Frontier above about 0.6 (too easy for the owner's target) | Saturates within a model generation | Section 13: dual gate at full strength, AAT and `kern` families kept, hard but fair notes kept, per-unit case breadth | Open, measured by the first runs |
| 12 | "Each fix is small" perception | Reads as easy | Breadth times domain depth, no oracle in the room, porting into pre-rewrite code | Accepted |
| 13 | The spike's case yield cuts units, mostly hard ones (F4, F5 need our own fonts) | Smaller, easier scope | Section 13 says how each cut moves the estimate; synthetic fonts before cutting | Open |

## 13. Difficulty sizing (owner, 2026-11-27)

The owner asked that the single-session task be "difficult enough". Target: **frontier at most about 0.6**, with
no full solve.

**Superseded estimate (2026-11-27).** QA pass 16 re-estimated the frontier at about 0.64 (0.54-0.75) by tier
rather than family, and found the gate takes only about 5% from careful work. The operative prediction, with its
kill conditions, is notes/PREREGISTRATION.md; the failure sentence is section 10's. The estimate below is kept as the
Phase A record. The sizing keeps four levers:

1. **The dual gate at full strength.** h_d multiplies the reward directly (section 6): an agent that implements
   notes broadly loses the share of neighbouring cases it breaks, with no cap.
2. **The AAT and `kern` families stay in scope** (F4, 9 units; F5, 3 units), with cases on fonts we build, including
   `kerx` through our own writer. Agents must build such fonts to see these notes work at all.
3. **No hard but fair note is dropped.** The example-dependent notes are restated as precise rules in the
   instruction (fix round 1) rather than cut. A unit is cut only when the sweep cannot produce 3 attributable cases for it, and then the report says so.
4. **Case breadth per unit.** Each unit's cases spread over several fonts, scripts, options and cluster levels. A fix
   that works only for the example in the note earns only part of its unit.

**The estimate, unit by unit.** Frontier pass rates per family are estimates for a 9.6 h session; the reasons are in
the inventory's ratings.

| Family | Units | Frontier pass (est.) | Mid-tier pass (est.) | Why |
| --- | --- | --- | --- | --- |
| F8 metrics and API | 19 | 0.70 | 0.40 | Small fixes and stated declarations; the saturation stack (76 commits) and exact rounding are the hard part |
| F1 script shapers | 12 | 0.50 | 0.25 | Khmer and Win-1256 are easy; USE word boundaries need the ragel machine; `stch` tiles and legacy Arabic are hard |
| F2 plan and normalisation | 5 | 0.50 | 0.25 | The 15-syllables-later bug needs a root cause |
| F3 positioning | 3 | 0.45 | 0.20 | Mark base search and `COLR` layers |
| F4 AAT and `kern` | 9 | 0.30 | 0.10 | Binary AAT tables, fonts the agent must assemble, state machines |
| F5 flags | 3 | 0.20 | 0.05 | Exact unsafe-to-break placement |
| F6 variations | 2 | 0.40 | 0.20 | `avar` and `gvar` edge cases need variable fonts of their own |
| F7 Unicode 18 and tags | 3 | 0.60 | 0.35 | Table regeneration is mechanical but long; `fonupa` is easy |

D (frontier) ≈ (19·0.70 + 12·0.50 + 5·0.50 + 3·0.45 + 9·0.30 + 3·0.20 + 2·0.40 + 3·0.60) / 56 ≈ **0.52**. Only
the units an agent changes can break their own duals; an agent that implements half the notes, a fifth of them too
broadly with one boundary in three crossed, keeps h_d ≈ 0.97. So G ≈ 0.90-0.97 and the frontier reward is **≈ 0.48,
range 0.36-0.60**. The mid-tier D is about 0.27; with G ≈ 0.88-0.97, the mid-tier reward is **≈ 0.12-0.30**, above
the 0.10 floor below which a task reads as broken.

**Where the estimate could go above 0.6, and the answer.** F8 is a third of D and the easiest family. If frontier
agents reach 0.9 on F8 and 0.7 on F1, D rises to about 0.62. The answers, in order:
- more duals on the boundaries a broad port crosses most (within the even per-boundary draw);
- widen each F8 unit's cases (more scales, fonts and edge values per unit, so half-right fixes earn half);
- add no new obligations: the scope is the notes.

**How a smaller scope moves the estimate.** Every unit cut for low yield moves D toward the mean of the units left.
Cuts fall mostly on hard, font-dependent units. Cutting five units at an expected pass of 0.30 raises frontier D by
about (0.52 − 0.30) × 5 / 51 ≈ +0.02. Losing all of F4 and F5 (12 units) would raise it by about +0.07, to ≈ 0.59
before the gate, which is the target's edge. So F4 and F5 are worth our own fonts, and the Phase B report states the
yield-driven cuts and their effect.
