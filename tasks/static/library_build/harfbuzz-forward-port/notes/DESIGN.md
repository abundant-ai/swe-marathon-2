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
| `/app/harfbuzz` | HarfBuzz 14.3.0, tag commit `4c2aa804671d7276e8a0eb95da07202ead05c843` **(m)** | Fresh repository with one commit, so history stops at the base. Pruned: `perf/` (25 files **(m)**), `subprojects/google-benchmark.wrap` **(m)**, the `benchmark` option in `meson_options.txt` **(m)** and its `subdir` line, `.github/`, `.ci/`, `.codecov.yml`. Kept: `src/`, `test/` (upstream's own tests and fonts for 14.3.0 behaviour), `util/`, `docs/`, build files. |
| Upstream agent files | `AGENTS.md`, `CLAUDE.md`, `CODE_OF_AI_CONDUCT.md` exist at the 14.3.0 root **(m)** | Not read yet (blobs not on disk). claude-code loads `CLAUDE.md` as project instructions, so these files are part of the instruction surface. QA lens 19 decides keep or remove after the download. |
| `/app/docs/notes.md` | The release-note items, 14.3.1 to 15.2.0 | The same text as the instruction's list, so the agent can grep it. |
| `/app/docs/specs/` | OpenType tables, Microsoft's script development specs (Khmer, Myanmar, Indic, USE, Hangul, Hebrew, Arabic), Apple's AAT table pages (`morx`, `mort`, `kerx`, `kern`, `trak`, `ankr`, `feat`), UAX #29 | Redistribution licences unverified (CLAIMS.md C18). Fallback: our own digests of the sections the notes rely on. |
| `/app/docs/unicode/` | The Unicode 18.0.0 files the table generators read: `UnicodeData.txt`, `Scripts.txt`, `Blocks.txt`, `ArabicShaping.txt`, `DerivedCoreProperties.txt`, `IndicSyllabicCategory.txt`, `IndicPositionalCategory.txt`, `emoji-data.txt`, `emoji-test.txt`, `ucd.nounihan.grouped.zip`; the IANA `language-subtag-registry`; Microsoft's `languagetags` page | The list comes from `src/update-unicode-tables.make` at 15.2.0 **(m)**. Upstream's generated tables record which file versions it used, some of them pre-release (CLAIMS.md C33); the shipped files must be those versions, or affected code points are cut. |
| `/app/docs/examples/` | One small font of ours per note that we restate as a precise behaviour (see section 6), with one input and the 14.3.0 output | Never the new output. |
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

## 6. Reward

One verifier run at the end of the session, over the 56 units I, against 15.2.0:

- p_k = passed_k / n_k for each unit k, with a fixed denominator: a crash, timeout or missing output fails its cases.
- D = mean of p_k over I (every unit counts the same; family scores are reported, not weighted).
- h_d = pass fraction of the duals; h_b = pass fraction of the broad held-fixed cases.
- G = max(0, 1 − w_d·(1 − h_d) − 0.10·(1 − h_b)), with w_d = 0.25 at least.
- **reward = D · G.**

A tree that does not build under the stated command scores 0, a candidate failure; a verifier fault (toolchain
missing, gold unreadable, driver crash on the oracle) leaves no reward file. The held-fixed sets only ever
multiply, so the unmodified base scores exactly 0: it fails every changed case by construction. The dual weight
w_d is the B family's share. Per the owner's sizing (section 13) it stays at full strength: 0.25 is the floor,
and the band check (QA gate item 12) may raise it, up to 0.35, so that mutant W lands in 0.60-0.85. It is never
lowered.

`metrics.json`: per family and per unit the pass fraction and case count, per release tag the pass fraction,
h_d, h_b, G, D, the build result and the build time.

**Why every unit counts the same and not every family.** The requester asked for a list of changes, and "how
much of the list works" is the plain measure. Family-equal weights would make one `gvar` fix worth as much as
eleven script fixes. The cost: F8 (metrics and API, 19 units) carries 34% of D, and its units are the easiest.
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
| Mutant W (section 10) | 0.60-0.85 |
| Frontier agents | about 0.36-0.60 (target: at most about 0.6) |
| Mid-tier agents | about 0.12-0.30 |

A healthy profile: no full solve; F8, F2 and the simpler F1 notes high; F4 (AAT and `kern`) and F5 (flags) low; the
dual gate below 0.95. Below 0.10 for mid-tier models the task risks reading as unfair or broken (difficulty note
§7), so the first trials must check that F8 and the P-rated F1 notes are reachable.

## 10. The failure mode, in one sentence

"Agents reproduce each release note's new behaviour on the sequences it describes but apply the rule beyond its
stated condition, so neighbouring sequences that upstream left unchanged regress." The B family is H_dual; the
proving mutant is W (each conditional item's guard widened to its unconditional form). The full proof plan,
with the learnability argument and the evidence that agents plausibly miss it, is in
[CLAIMS.md](CLAIMS.md#failure-sentence-and-its-proof-plan).

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
| 3 | Example-dependent notes (16 E items) are not pinned exactly | "Grader rejects valid work" | Restate each as a precise behaviour rule checked against the release on every case; drop it if the rule does not determine the output | Open |
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
no full solve. The sizing keeps four levers:

1. **The dual gate at full strength.** It is multiplicative, and w_d never drops below 0.25. An agent that implements
   notes broadly loses up to a quarter of its reward. The band check may raise w_d toward 0.35, never lower it.
2. **The AAT and `kern` families stay in scope** (F4, 9 units; F5, 3 units), with cases on fonts we build, including
   `kerx` through our own writer. Agents must build such fonts to see these notes work at all.
3. **No hard but fair note is dropped.** The 16 example-dependent notes are restated as precise rules rather than
   cut. A unit is cut only when the sweep cannot produce 3 attributable cases for it, and then the report says so.
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

D (frontier) ≈ (19·0.70 + 12·0.50 + 5·0.50 + 3·0.45 + 9·0.30 + 3·0.20 + 2·0.40 + 3·0.60) / 56 ≈ **0.52**. With an
expected dual failure of 10-30% and a few broad slips, G ≈ 0.92-0.97, so the frontier reward is **≈ 0.48, range
0.36-0.60**. The mid-tier D is about 0.27; with G ≈ 0.88-0.95, the mid-tier reward is **≈ 0.12-0.30**, above the
0.10 floor below which a task reads as broken.

**Where the estimate could go above 0.6, and the answer.** F8 is a third of D and the easiest family. If frontier
agents reach 0.9 on F8 and 0.7 on F1, D rises to about 0.62. The answers, in order:
- raise w_d within the band check (an agent that broadens rules loses more);
- widen each F8 unit's cases (more scales, fonts and edge values per unit, so half-right fixes earn half);
- add no new obligations: the scope is the notes.

**How a smaller scope moves the estimate.** Every unit cut for low yield moves D toward the mean of the units left.
Cuts fall mostly on hard, font-dependent units. Cutting five units at an expected pass of 0.30 raises frontier D by
about (0.52 − 0.30) × 5 / 51 ≈ +0.02. Losing all of F4 and F5 (12 units) would raise it by about +0.07, to ≈ 0.59
before the gate, which is the target's edge. So F4 and F5 are worth our own fonts, and the Phase B report states the
yield-driven cuts and their effect.
