# Pre-registration: what a frontier agent is expected to score, and what would prove it wrong

Author notes, never shipped. Written and committed on 2026-11-27, before any model run (decision 2026-11-27,
`ops/swe-marathon-v2/decisions/2026-11-27-harfbuzz-failure-sentence-DECISION.md` in harbor-lh). The tiers and the
failure sentence are in notes/DESIGN.md section 10. Predictions are for one claude-code session with a frontier
model (Opus class) at 34,560 s; the per-tier figures are QA pass 16's estimates (tier A 0.89, tier B 0.68, tier C
0.46), with units 33 and 34 set at 0.60 and 0.50 (mechanical regeneration, but new characters no shipped font
covers).

## Per unit

| Unit | Family | Window | Tier | Why | Predicted pass |
| --- | --- | --- | --- | --- | --- |
| 26 | F4 | A | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 11 | F1 | A | A | the note names the fix | 0.89 |
| 36 | F8 | A | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 33 | F7 | A | C | needs regenerated Unicode 18 data and fonts covering the new characters | 0.60 |
| 35 | F7 | A | A | the note names the fix | 0.89 |
| 37 | F8 | A | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 16 | F2 | A | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 19 | F3 | B | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 10a | F1 | B | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 10b | F1 | B | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 25a | F4 | B | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 25b | F4 | B | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 25c | F4 | B | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 31 | F6 | B | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 34 | F7 | B | C | needs regenerated Unicode 18 data and fonts covering the new characters | 0.50 |
| 44a | F8 | B | A | the note names the fix | 0.89 |
| 44b | F8 | B | A | the note names the fix | 0.89 |
| 45 | F8 | B | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 46 | F8 | B | A | the note names the fix | 0.89 |
| 51 | F8 | B | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 1 | F1 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 2 | F1 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 3 | F1 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 4 | F1 | C | A | the note names the fix | 0.89 |
| 5 | F1 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 6 | F1 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 7 | F1 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 8 | F1 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 9 | F1 | C | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 12 | F2 | C | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 13 | F2 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 14 | F2 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 15 | F2 | C | A | the note names the fix | 0.89 |
| 17 | F3 | C | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 18 | F3 | C | A | the note names the fix | 0.89 |
| 20 | F4 | C | A | the note names the fix | 0.89 |
| 21 | F4 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 22 | F4 | C | A | the note names the fix | 0.89 |
| 23 | F4 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 24 | F4 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 27 | F5 | C | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 29 | F5 | C | C | AAT/kern or flag behaviour that needs fonts the agent builds | 0.46 |
| 38 | F8 | C | C | the note gives a symptom; the cause has to be found without an oracle | 0.46 |
| 39 | F8 | C | A | the note names the fix | 0.89 |
| 40a | F8 | C | A | the note names the fix | 0.89 |
| 40b | F8 | C | A | the note names the fix | 0.89 |
| 40c | F8 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 41 | F8 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 42 | F8 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 43 | F8 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 47b | F8 | C | A | the note names the fix | 0.89 |
| 48 | F8 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |
| 49 | F8 | C | B | checkable on the agent's own 14.3.0 build with shipped fonts and tools | 0.68 |

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
