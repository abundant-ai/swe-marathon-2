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

## Re-run on the shipped c4 set (2026-11-28, the owner-questions panel)

The audit above read the c3 selection; the adversarial review of the owner-questions panel (harbor-lh
`ops/swe-marathon-v2/decisions/2026-11-28c-owner-questions-DECISION.md`) asked for it again on the set that ships,
c4 (5,245 cases). Per-stratum evidence is in `private/fix2/residual-audit-c4.md`.

- **Carry-over, checked mechanically.** Every c4 case's unit, kind, stratum and driver was compared with c3's. 43
  units have the same strata from the same generators (their cases redrawn, repeats dropped), so the audit above
  holds for them; units 1, 5 and 25a only gained inside-stratum labels. Unit 40a, a watch item above, now holds on
  every changed case: 15.2.0's value is 14.3.0's divided by 20, printed to 3 decimals, so every reading of "in
  points" prints the same.
- **New or changed strata, read case by case** against their notes, the specification notes and the 14.3.0 code:
  - 13, Khmer: a precomposed letter in Khmer-shaped text with no marks stays whole, as the note says;
  - 23, class kerning (`kerx` format 6, alone and after format 0, beside `GSUB` and a `GPOS` without a kerning
    feature): the values are the fonts' class arrays applied through 14.3.0's own `kerx` code, which no 15.x commit
    changes for format 6; no graded font has a state-machine or cross-stream subtable; the neighbours stay as 14.3.0;
  - 29, the restored `b:after-lvt` neighbours: checked mechanically, every one has its archaic trailing jamo after
    a syllable with a final consonant, which the note's "that has no final consonant" leaves out, and every changed
    case has it after a syllable without one, at a character cluster level;
  - 33, every stratum: all 60 changed cases match the note-derived build (14.3.0's generators on the shipped
    Unicode 18 files, the three named script values, and the two code changes the note states: the scripts go
    through the USE, and Jurchen and Seal take the ideographic baseline); 48 already match the regenerated tables
    alone; all 30 neighbours stay as 14.3.0 under it;
  - 35, the reverse mapping, which the note states; 48, the probe under `HB_FONT_FUNCS=ot`, which the note says
    is not consulted; 49, a face with no `JSTF` table returns nothing, as "only glyphs the `JSTF` table lists" says;
  - 13's composition exclusions and 16's covered out-of-range glyphs are no longer graded.
- **Task-wide, on c4:** every changed case is moved by its own unit's revert and by no other, and no revert moves a
  neighbour (gate row 2); of the 600 broad cases only W and W_literal move any (18 each: 12 Hebrew, 4 Khmer and 2
  Devanagari), each a widening that drops a condition its note states.

**Result on c4:** no case its note does not determine; nothing to fix or drop.
