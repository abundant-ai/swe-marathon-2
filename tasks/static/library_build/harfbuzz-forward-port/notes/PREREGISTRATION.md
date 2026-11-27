# Pre-registration: what a frontier agent is expected to score, and what would prove it wrong

Author notes, never shipped. Written and committed on 2026-11-27, before any model run (decision 2026-11-27,
`ops/swe-marathon-v2/decisions/2026-11-27-harfbuzz-failure-sentence-DECISION.md` in harbor-lh). The tiers and the
failure sentence are in notes/DESIGN.md section 10. Predictions are for one claude-code session with a frontier
model (Opus class) at 34,560 s; the per-tier figures are QA pass 16's estimates (tier A 0.89, tier B 0.68, tier C
0.46), with units 33 and 34 set at 0.60 and 0.50 (mechanical regeneration, but new characters no shipped font
covers).

## Per unit

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
| 20 | cross-stream kern: reset value and axis scale | F4 | 15.2.0 | A | the note names the fix | 0.89 |
| 21 | kern in vertical text when vkrn is requested | F4 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 22 | trak in vertical text | F4 | 15.2.0 | A | the note names the fix | 0.89 |
| 23 | kerx with GPOS lacking a kerning feature | F4 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 24 | AAT: later feature request wins | F4 | 15.2.0 | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
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

## Per family

| Family | Units | Predicted pass |
| --- | --- | --- |
| F1 | 12 | 0.68 |
| F2 | 5 | 0.63 |
| F3 | 3 | 0.60 |
| F4 | 9 | 0.63 |
| F5 | 2 | 0.46 |
| F6 | 1 | 0.46 |
| F7 | 3 | 0.66 |
| F8 | 18 | 0.75 |

Predicted frontier D: 0.672; with h_d and h_b near 0.97 each, the predicted reward is about
0.64 (QA pass 16: 0.54-0.75 across harnesses). Mid-tier models: about 0.28.

## Kill conditions (checked on the first three frontier runs, before any change to cases or weights)

1. **Difficulty.** The median frontier reward above 0.75, or below 0.30: the difficulty claim fails. Stop, report,
   and decide with the owner before changing anything; no weight is changed after seeing runs without a new
   pre-registration.
2. **The failure sentence.** The mean pass of tier-C units is not at least 0.10 below the mean of tiers A and B
   (over the three runs): the verification-gap sentence fails.
3. **Over-breadth (the earlier sentence returns).** Units an agent implemented fail their duals at 15% or more, and
   at least three times the rate of units it left untouched.
4. **Per family.** A family of three or more units lands more than 0.25 from its prediction (median of the runs):
   re-examine that family's cases and tiers.
5. **Per unit.** A tier-C unit passes 0.9 or more in two of three runs, or a tier-A unit 0.3 or less in two of
   three runs: re-examine that unit's note, cases and tier.

Per-case results are in each run's `metrics.json` (per unit and kind), so every condition can be computed from the
runs alone.
