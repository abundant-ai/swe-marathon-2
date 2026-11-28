# Pre-registration: what a frontier agent is expected to score, and what would prove it wrong

Author notes, never shipped. **Amended 2026-11-28 (fix round 2) and committed before any model run; it replaces the
2026-11-27 version** (kept in the git history). Decisions: harbor-lh `ops/swe-marathon-v2/decisions/`
`2026-11-28-harfbuzz-tiers-difficulty-DECISION.md` (the tier rule, V, the difficulty lever, the horizon) and
`2026-11-28b-harfbuzz-sentence-after-tiering-DECISION.md` (the sentence and the registered tests), applying QA pass
R2-17's amendment (N2).

## The sentence

> With no 15.x code or tests to check against, agents land most fixes whose note names the change, fewer where they
> must work the change out or diagnose a symptom the shipped fonts reproduce, and fewest where no shipped font shows
> the behaviour: a bug they must first reproduce on a font they build, or AAT `kerx` and `kern` tables they must
> assemble by hand.

## Population and freeze

- The tests count the **first three accepted claude-code sessions with an Opus-class model at 34,560 s**, on the
  bundle version that passed the platform's QA. Other runs (other models, harnesses or versions) are reported against
  the same tables and count toward nothing. With fewer than three such sessions every test reads "untested".
- **`scripts/pipeline/tiers.tsv` is frozen** at sha256 `0301c5864604908727418f04afdc79d16cb8c4e6406271ffe2d7442158a6b82c` for these runs. No unit changes tier after a
  run, and nothing is re-tiered to rescue a test.
- Tier means are the mean per-unit pass (linear p_k) of each tier's units, pooled over the three sessions.

## Tiers (the 2026-11-28 rule, applied to all 53 units)

In order: **C** if (i) the behaviour shows only on tables no shipped font has and fontTools cannot write, or (ii) the
note gives only a symptom, the cause is neither stated nor pointed to by the note (judged on upstream's diff), and no
shipped material shows the behaviour; otherwise **A** if the note names the edit; otherwise **B**. fontTools 4.69.1
(the agent image's) writes `morx` and `mort` state tables, `trak`, `JSTF`, `STAT` and `kern` format 0 with any coverage
bits; it has no `kerx` support, and AAT `kern` formats 1-3 stay raw bytes. Confirmed in the agent image before the
freeze (`scripts/pipeline/fonttools_aat_check.py` over our fonts and the shipped test fonts, 104 tables): `kerx` 17 of
17 raw (DefaultTable); `kern` 30 structured, every subtable of format 0 (coverage 0, 1, 5 and 64) structured and
round-tripping through TTX unchanged, formats 1-3 raw; `morx` 45 structured; `trak` 5 and `JSTF` 4 structured; `mort`
2 structured, and the third, a state table entered at a non-first initial state (unit 25c's construct), does not
even decompile. **A 23, B 22, C 8**; tier C is 10a, 23,
25a, 25b, 25c, 26, 31 and 42. Per-unit evidence (the note's words, the material that shows the behaviour, the
hand-written upstream lines) is in `tiers.tsv` and the private audit; the public summary is notes/RESIDUAL-AUDIT.md.

**Frozen sensitivity, never adopted after the runs:** read strictly, "pointed to" would also put 12 and 27 in C
(|C| = 10). The tests are reported under that reading too, as a sensitivity only.

## Per unit

Predictions are QA pass 16's per-unit estimates (round 2, `estimate2.py`: frontier and mid-tier), for one claude-code
session at 34,560 s. Fix round 2's wording changes (units 5, 7, 17, 21, 33, 35, 41, 46) make notes more determinate
and are not re-estimated.

| Unit | Note | Family | Note's release | Tier | Predicted (frontier, mid) | Why this tier |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Indic init after a letter or mark in the pre-context | F1 | 15.2.0 | A | 0.80, 0.35 | names the edit at one existing decision (word-start test for init); shown on shipped material; was B |
| 2 | USE: no space as the base of a dependent vowel (candidate) | F1 | 15.2.0 | B | 0.65, 0.25 | states the behaviour; the change (a new USE category and machine rule) must be designed; upstream lines exclude 968 regenerated table and machine lines |
| 3 | USE word boundaries for positional forms | F1 | 15.2.0 | B | 0.55, 0.20 | states the behaviour; several decisions (symbol clusters, NBSP as a generic base) must be designed |
| 4 | Khmer: one Coeng Ro, first or second coeng only | F1 | 15.2.0 | A | 0.95, 0.80 | names the edit (one existing bound); shown on shipped material |
| 5 | Hangul tone mark at text start | F1 | 15.2.0 | B | 0.60, 0.25 | states the corrected output, not the change (treat an existing circle as the base) |
| 6 | dotted circles keep their advance without GDEF | F1 | 15.2.0 | A | 0.78, 0.40 | names the edit (the inserted circle takes U+25CC's properties); panel expected A; was B |
| 7 | vowel constraints across default ignorables | F1 | 15.2.0 | B | 0.60, 0.20 | states the behaviour; the vowel-constraint matcher must be reworked; upstream changed only the generated matcher (337 lines), so 0 hand-written lines |
| 8 | Hebrew composes with mark only under DFLT | F1 | 15.2.0 | B | 0.55, 0.20 | states when composition happens; the agent must find why it does not (has_gpos_mark) |
| 9 | Arabic stch tiles centred on short words and exact fits | F1 | 15.2.0 | B | 0.45, 0.10 | states the behaviour; the centring arithmetic must be designed; was C [predicted 0.45: pass 16 rates the stch centring hard (0.45)] |
| 10a | Arabic fallback: ligatures with a missing component | F1 | 15.1.0 | C | 0.65, 0.25 | C(ii): symptom only; the cause (partial component lists stay counted) is not stated; no shipped font shows it; was B |
| 10b | Arabic fallback: marks in legacy fonts (candidate) | F1 | 15.1.0 | B | 0.45, 0.10 | symptom only, but shipped legacy fonts show it, so not C(ii); was C [predicted 0.45: pass 16 0.45: legacy-font PUA diagnosis] |
| 11 | Arabic Windows-1256 fallback on all platforms | F1 | 14.4.0 | A | 0.95, 0.80 | names the edit (a platform switch) |
| 12 | per-syllable lookups 15 syllables later (alternative fd5702517) | F2 | 15.2.0 | B | 0.50, 0.10 | symptom only, but the note points to the cause (matching across syllables after the serial wraps), so not C(ii); was C [predicted 0.50: pass 16 0.50: diagnosis of the syllable walk] |
| 13 | precomposed characters in text with no marks | F2 | 15.2.0 | B | 0.60, 0.20 | symptom only, but shipped material shows it, so not C(ii) |
| 14 | a global request overrides earlier ranged requests | F2 | 15.2.0 | B | 0.70, 0.30 | states the precedence rule; the map/mask change must be designed (3 files) |
| 15 | missing character + variation selector: not-found glyph | F2 | 15.2.0 | A | 0.80, 0.45 | names the edit (use the buffer's not-found glyph) |
| 16 | out-of-range glyph ids (candidate) | F2 | 14.6.0 | B | 0.40, 0.10 | symptom only and the cause (coverage-cache aliasing) is not pointed to, but shipped fonts show it, so not C(ii); was C [predicted 0.40: pass 16 0.40: cache aliasing has to be diagnosed] |
| 17 | GPOS marks and an earlier base | F3 | 15.2.0 | B | 0.55, 0.15 | symptom only, but shipped material shows it, so not C(ii); was C |
| 18 | fallback mark positioning uses the base x offset | F3 | 15.2.0 | A | 0.90, 0.60 | names the edit |
| 19 | COLR extents and marks with empty layers | F3 | 15.1.0 | B | 0.50, 0.15 | symptom only, but a shipped COLR font shows it, so not C(ii); was C [predicted 0.50: pass 16 0.50: paint-extents diagnosis] |
| 20 | cross-stream kern: reset value and axis scale | F4 | 15.2.0 | A | 0.85, 0.45 | names both edits; format 0 is fontTools-writable, so not C(i) |
| 21 | kern in vertical text when vkrn is requested | F4 | 15.2.0 | A | 0.65, 0.25 | names the edit; fontTools-writable, so not C(i); panel expected A; was C [predicted 0.65: pass 16 0.65: needs a vertical kern font of its own] |
| 22 | trak in vertical text | F4 | 15.2.0 | A | 0.90, 0.55 | names the edit (apply tracking in the advance direction); fontTools-writable |
| 23 | kerx with GPOS lacking a kerning feature | F4 | 15.2.0 | C | 0.60, 0.20 | C(i): kerx only, though the note names the edit |
| 24 | AAT: later feature request wins | F4 | 15.2.0 | A | 0.55, 0.20 | names the edit (request precedence in the AAT map); shipped and fontTools material; was C [predicted 0.55: pass 16 0.55: AAT request merging, morx fonts of its own] |
| 25a | kerx formats 1 and 2 | F4 | 15.1.0 | C | 0.58, 0.18 | C(i): kerx only |
| 25b | kerx format 4 mark positioning | F4 | 15.1.0 | C | 0.30, 0.05 | C(i): kerx only [predicted 0.30: pass 16 0.30: kerx format 4 attachment chains] |
| 25c | kern and mort with a non-first initial state | F4 | 15.1.0 | C | 0.50, 0.15 | C(ii): symptom only; the cause (negative-state arithmetic in StateTable) is not stated; no shipped font |
| 26 | AAT insertion at the end of the text | F4 | 14.3.1 | C | 0.40, 0.10 | C(ii): symptom only; the cause (metadata applied to cur() at end of text) is not stated; no shipped font |
| 27 | unsafe-to-break with cross-stream kerning | F5 | 15.2.0 | B | 0.55, 0.15 | the note states what is missing (the flags), so not C(ii); fontTools-writable, so not C(i); was C |
| 29 | archaic trailing jamo flags (candidate) | F5 | 15.2.0 | B | 0.62, 0.25 | states the behaviour and the mechanism, not the edit; panel expected B; was C |
| 31 | gvar intermediate tuples | F6 | 15.1.0 | C | 0.50, 0.10 | C(ii): symptom only; the cause (the shared-peak scalar cache) is not stated; no shipped font shows it |
| 33 | Unicode 18.0 data and scripts | F7 | 14.5.0 | A | 0.85, 0.40 | names the edit (regenerate, add three script values); panel expected A; was C |
| 34 | Indic shaping of the Unicode 18 additions | F7 | 15.1.0 | B | 0.60, 0.20 | symptom only (the block filter is not named), but shipped material shows it, so not C(ii); upstream changed only the generated table (179 lines; the block filter is 2 generator lines); was C |
| 35 | fonupa maps to UPPH | F7 | 14.5.1 | A | 0.90, 0.55 | names the edit; 0 hand-written lines because the 9-line edit is in the generated tag table, which the agent edits by hand (its sources are withheld) |
| 36 | saturating positions and extents (the 2026-08-12 stack) | F8 | 14.4.0 | B | 0.70, 0.30 | names the arithmetic, but the sites (76 upstream commits) must be found; GPOS shows it, so not C(i) |
| 37 | overflow fixes in extents scaling, slant and emboldening | F8 | 14.5.1 | A | 0.78, 0.40 | names the edit; panel expected A; was B |
| 38 | extents round outward after scaling | F8 | 15.2.0 | B | 0.50, 0.15 | states the rounding rule; the unrounded extents must be produced in glyf, CFF1 and CFF2; panel expected B; was C [predicted 0.50: pass 16 0.50: three outline back ends] |
| 39 | empty glyphs have zero extents | F8 | 15.2.0 | A | 0.90, 0.55 | names the edit |
| 40a | OS/2 optical size in points | F8 | 15.2.0 | A | 0.90, 0.60 | names the edit |
| 40b | slant includes synthetic slant | F8 | 15.2.0 | A | 0.85, 0.40 | names the edit |
| 40c | STAT values of older sibling fonts skipped | F8 | 15.2.0 | A | 0.70, 0.30 | names the edit; STAT is fontTools-writable, so not C(i); was B [predicted 0.70: pass 16 0.70: STAT fonts of its own] |
| 41 | collect_unicodes and cmap format 13 | F8 | 15.2.0 | B | 0.75, 0.35 | symptom only, but shipped material shows it, so not C(ii) |
| 42 | nested glyf components with anchor points | F8 | 15.2.0 | C | 0.70, 0.25 | C(ii): symptom only; the cause (anchor index not offset by the composite's start point) is not stated; no shipped font; was B [predicted 0.70: pass 16 0.70: the digest states the point-matching rule] |
| 43 | zero positions for items added after the first call | F8 | 15.2.0 | A | 0.75, 0.35 | names the edit (zero the positions of items added later); was B |
| 44a | fallback vertical descender without vhea | F8 | 15.1.0 | B | 0.95, 0.75 | symptom only (the one-token edit is not stated); shipped material shows it, so B, not A; was A [predicted 0.95: pass 16 0.95: a one-token edit] |
| 44b | hanging baseline fallback | F8 | 15.1.0 | B | 0.80, 0.40 | symptom only (the tag conversion is not stated); shipped material shows it, so B, not A; was A |
| 45 | collect_glyph_alternates garbage | F8 | 15.1.0 | B | 0.65, 0.25 | symptom only, but shipped material shows it, so not C(ii) |
| 46 | hb_face_create_or_fail() named-instance bits | F8 | 15.1.0 | A | 0.95, 0.75 | the stated defect gives the edit (ignore the named-instance bits) |
| 47b | hb_font_set_face() does nothing | F8 | 15.2.0 | A | 0.90, 0.60 | names the edit |
| 48 | hb_font_create_without_funcs_or_fail() | F8 | 15.2.0 | A | 0.80, 0.40 | the note gives the complete contract of a new function; was B |
| 49 | hb_ot_layout_get_extender_glyphs() | F8 | 15.2.0 | A | 0.70, 0.30 | the note gives the complete contract; JSTF is fontTools-writable, so not C(i); was B [predicted 0.70: pass 16 0.70: JSTF reading of its own] |
| 51 | deserialize2 functions | F8 | 15.1.0 | A | 0.85, 0.45 | the note gives the complete contract; was B |

## Per family

| Family | Units | Predicted frontier | Predicted mid |
| --- | --- | --- | --- |
| F1 | 12 | 0.67 | 0.33 |
| F2 | 5 | 0.60 | 0.23 |
| F3 | 3 | 0.65 | 0.30 |
| F4 | 9 | 0.59 | 0.24 |
| F5 | 2 | 0.58 | 0.20 |
| F6 | 1 | 0.50 | 0.10 |
| F7 | 3 | 0.78 | 0.38 |
| F8 | 18 | 0.78 | 0.42 |

## Predicted

- **D** frontier 0.687; with h_d about 0.95 and h_b about 0.99 (pass 16) the reward is about 0.65. Mid-tier D
  0.326, reward about 0.29.
- **Tier means** (frontier): A 0.824, B 0.601, C 0.529. Mid-tier: A 0.474, B 0.232, C 0.160.
- **Shares of the D loss:** A 24%, B 53%, C 23%.

## Registered tests (the 2026-11-28b decision)

They replace the 2026-11-27 conditions on tier C. Pass rates are simulated over three sessions: "all-or-nothing"
draws each unit landing or not with its predicted probability (the worst case for noise), "fractional" draws a pass
fraction around it (sd 0.15). "Chance" puts every unit at the predicted mean D, so no tier structure; "wording only"
is QA R2-17's main rival, where notes that name the edit land at 0.80 and symptom-only notes at 0.40 whatever the
material.

| Test | Predicted | Passes if the predictions hold (all-or-nothing, fractional) | By chance | If only wording matters | If it fails |
| --- | --- | --- | --- | --- | --- |
| A - C >= 0.15 | 0.29 | 0.91, 1.00 | 0.09 | 0.96 | the sentence fails |
| A - B >= 0.10 | 0.22 | 0.96, 1.00 | 0.12 | 0.95 | the A/B distinction is dropped from the sentence |
| B - C >= 0.05 | 0.07 | 0.57, 0.73 | 0.32 | 0.76 | the B/C distinction is dropped from the sentence |
| B >= 0.55 | 0.60 | 0.80, 1.00 | 0.99 | 0.70 | agents do not land the fixes they can work out; the sentence fails |
| B carries at least 40% of the D loss (reported for every tier) | 53% | 0.99, 1.00 | 0.60 | 0.98 | the sentence fails |
| All of them | | 0.48, 0.73 | 0.014 | 0.55 | |

A failed step is reported and its distinction dropped from the sentence; nothing is re-tiered. The ranking tests do
not separate the sentence from the wording-only rival, since tier A is defined by the note's wording; the mechanism
contrast below does.

## Reported contrasts (not kill conditions)

- **The mechanism contrast** (R2-17 N2, point 4). Units whose note names the edit but whose behaviour no shipped
  material shows (20, 21, 22, 24, 40c, 49) against named-edit units whose behaviour shipped material shows (1, 3, 4, 5,
  14, 15, 18, 35, 37, 38, 39, 40a, 40b, 43, 46, 47b, 48, 51). The sentence predicts no real gap: named edits land
  whether or not the agent can see them work. If the first group falls 0.15 or more below the second, seeing a fix
  work matters, and the sentence says so (a reported revision; nothing is re-tiered).
- **Fix size** (the panel's diagnostic). Among units with at most 15 hand-written upstream lines, A - C, so a gap
  explained by fix size alone shows.
- **Per family:** the median family mean of F1, F4 and F8 more than 0.25 from its prediction (chance, all-or-nothing:
  F1 0.005, F4 0.030, F8 0.000); the smaller families are reported only.

## Per-unit conditions, calibrated against chance

Each fires by chance in under 5% of draws when every prediction is exactly right (all-or-nothing outcomes):
- more than 6 of the 8 tier-C units at 0.9 or more in two of three sessions (chance 0.044);
- more than 5 of the 23 tier-A units at 0.3 or less in two of three sessions (chance 0.016);
- more than 11 of the 22 tier-B units at 0.3 or less in two of three sessions (chance 0.049).

A firing means those units' tiers or cases are wrong for the next registration; it never re-tiers the counted runs.

## Over-breadth, defined (the earlier sentence's test)

- Implemented: p_k is 0.5 or more. Untouched: the session's delivered tree changes none of the files that the unit's
  upstream commits change.
- The rate is the mean of (1 - h_k) over the unit set, per session.
- It fires when the implemented units' rate is at least 15% and at least three times the untouched units', in two of
  the three sessions. The Phase A over-breadth sentence then comes back as the headline.
- Read first, before calling a failed dual over-breadth: the strata a literal reading of a note fails (unit 26
  `b:mid-before`, which keeps a 14.3.0 behaviour every release keeps).

## Difficulty (kill condition 1)

- The owner's target of at most about 0.6 governs; the 2026-11-28 decision accepts about 0.65 as "about 0.6" (the
  owner's word on this is asked for).
- A median reward of 0.60-0.70 over the three sessions is reported as "above target".
- **A median above 0.70 triggers the contingent lever:** per-unit completeness (D over p_k squared), applied under a
  new registration, never retroactively; pass 16 puts it at about 0.59 frontier and 0.25 mid-tier.
- A median below 0.30: stop and check fairness. A median below 0.45 means agents do not land the checkable fixes
  either; the headline then becomes the largest component of the loss.

## V, a consistency check

V (15.2.0 with every tier-C unit's commits reverted) must land in 0.60-0.85, lose D only on tier C, and keep h_d
and h_b at 0.99 or more; the band never moves. Expected 1 - 8/53 = 0.849 complete, about 0.87 as built (25a's and
25b's later commits do not revert on 15.2.0). Measured: see notes/FIX2-REPORT.md.

Per-case results are in each run's `case_pass.json`, and per-unit and per-family figures in `metrics.json`, so every
test can be computed from the runs alone.
