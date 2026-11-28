# Residual-case audit (fix round 2, 2026-11-28)

Author notes, never shipped. The 2026-11-28 panel (harbor-lh `ops/swe-marathon-v2/decisions/
2026-11-28-harfbuzz-tiers-difficulty-DECISION.md`, item 4) asked for a static audit, before any run, of every unit's
graded cases: which of them does the note, together with the shipped specification notes and the 14.3.0 code, not
determine? Per-unit evidence, with case ids and examples, is in the private store (`private/fix2/residual-audit.md`);
this is the public summary. Method: five independent auditors over all 53 units under one brief, sampling each
unit's changed cases and duals from the c3 selection against the note and upstream's diff, with simulators where
cheap; their key claims were checked again.

**Result.** One unit had cases its note did not determine, and fix round 2 fixes it in the note:

| Unit | Residual | Fix |
| --- | --- | --- |
| 7 | All 60 changed cases: the note did not say where the dotted circle goes when a default ignorable sits between the vowels | The note now says it goes right before the second vowel, after the default ignorables |

Known residuals that QA round 2 had already found are fixed in this round: unit 35's reverse mapping (stated), unit
2's NO-BREAK SPACE (stated), unit 6's circle in fonts whose `GDEF` classes it (stated), units 13 and 16's strata
(left out and redrawn), unit 40a's rounding and the float bits of 40a-40c and 48 (rounded output, exact bounds), and
the clause coverage of 13, 23, 33, 36 and 48 (cases added, or the clause dropped).

**Watch items**, determined today only through 14.3.0's own behaviour or a documented contract; each note now says
it in one sentence, so an honest port cannot read them otherwise:
- 5: the single dotted circle is set as it is without the beginning-of-text flag;
- 17: the mark is left unattached;
- 21: vertical `kern` values apply as HarfBuzz already applies them;
- 41: code points mapped to a missing glyph are still left out;
- 46: an index with no face in the blob is still rejected;
- 14: the pattern ranged, global, ranged on one tag has no case and is kept out of every draw (15.2.0 still applies
  the first range there).

After these, no unit is left with graded cases its note does not determine (the panel's reopen threshold is more
than three).

**Determined readings an honest port can still get wrong** (not residual; for the post-run reading): 38's rounding
of the first commit only, 36's symmetric clamp or float sums, 24's sort-only flip, 44a's negated ascender and 44b's
conversion of old tags only.
