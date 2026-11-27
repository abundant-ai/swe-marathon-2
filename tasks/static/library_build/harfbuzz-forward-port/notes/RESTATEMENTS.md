# Restated notes

Author notes, never shipped. **Shipped in fix round 1 (2026-11-27):** QA pass 04 found that none of the Phase B
drafts had reached the instruction and that several were unfaithful. Each example-dependent note now carries, in
`instruction.md` (and `environment/docs/notes.md`), the rule its graded cases follow; the texts below are what
shipped, each with the generator labels it matches. Where a note's text does not determine 15.2.0's output, the
cases were narrowed (labels `x:`, or classify.py's `beyond-note` for 25a) rather than the rule widened. The
Phase B draft table is kept at the end as the record.

One entry per example-dependent note that QA pass 04 lists (its per-unit table: 3, 6, 9, 10a, 10b, 16, 17, 19,
25a, 25b, 25c, 26, 27, 29, 37, 44a, 44b; 28 is cut). Format: `unit: current note line -> proposed note text`.
Each proposed text keeps upstream's sentence (29 narrows it, 37 drops a clause no case checks) and adds what the
graded cases need, in the voice of the instruction's own API notes, and claims nothing the cases do not check. Apply each to `instruction.md` and
`environment/docs/notes.md` together (the packager compares them). Where one bullet covers several units, one
replacement covers them all. No proposed text uses the cue words of pass 21's sweep; "exactly" and "identical"
are avoided on purpose.

The "Labels" line says which generator labels the text matches. Labels changed in this round: 27
(`x:before-pair`), 29 (`x:after-lvt`), 25a (classify.py's `beyond-note`, from build `rk-25a-hist`), and 39
(`x:degenerate`, M10, no note change). The others already matched.

## 15.2.0: script-specific shaping

3: The USE shaper now ends a word at spaces and symbols when it selects `isol`, `init`, `medi` and `fina` forms. ->
The USE shaper now ends a word at spaces and symbols when it selects `isol`, `init`, `medi` and `fina` forms: a
symbol in the text (Unicode categories Sm, Sc, Sk and So, such as the multiplication sign U+00D7 and the Balinese musical symbols, with any marks
on them) or a NO-BREAK SPACE ends the word before it, and the next letter starts a new word. The script's own
digits still join, and characters in the context around the text do not end a word.
Labels: in = symbol or NBSP boundary in the text; b:adjacent, b:digit, b:context, b:no-forms. Ordinary spaces,
punctuation, ZWNJ and flags stay ungenerated.

6: Dotted circles for Hangul tone marks and prohibited vowel sequences now keep their advance in fonts without
`GDEF`. ->
Dotted circles for Hangul tone marks and prohibited vowel sequences now keep their advance in fonts without `GDEF`.
A dotted circle the shaper inserts now has the properties of U+25CC itself, a base, as one typed in the text has,
and no longer those of the mark it stands for: it keeps its advance, it is not shifted as zeroed marks are, and a
zero-width tone mark after it is placed on it.
Labels: in (Hangul tone mark after a non-syllable, spacing and zero-width marks; USE prohibited pair with a
non-spacing second vowel; fonts without GDEF); b:gdef, b:gdef-dc-mark, b:mc-second, b:typed-dc, b:nodc-flag,
b:after-syllable, b:text-start. Covers the 32 Hangul cases pass 04 found undetermined.

29: An archaic trailing jamo after a Hangul syllable now gets the unsafe-to-break flag at the character cluster
levels. ->
An archaic trailing jamo after a Hangul syllable that has no final consonant now gets the unsafe-to-break flag at
the character cluster levels (`HB_BUFFER_CLUSTER_LEVEL_MONOTONE_CHARACTERS` and `HB_BUFFER_CLUSTER_LEVEL_CHARACTERS`):
the shaper splits such a syllable into its jamo to set the trailing jamo with them, so a break before that jamo
changes the syllable.
Labels: in = LV + archaic T at levels 1 and 2; b:grapheme-level, b:modern-trailing, b:jamo-sequence;
x:after-lvt (M9). Under this text LVT + archaic T is one stated condition away and could come back as a boundary.

9: The Arabic shaper now centers `stch` tiles on short words and exact fits. ->
The Arabic shaper now centers `stch` tiles on short words and exact fits: when the fixed tiles plus one copy of
each repeating tile are at least as wide as the part of the word they stretch over, that group is centered over
it, overhanging both ends by the same amount; when the fixed tiles and whole copies of the repeating tiles fill
that part with nothing left over, they cover it with no shift.
Labels: in (both conditions, scales 1, 2, 1/2 and -1; widths are multiples of 20, so no halving rounds and no
rounding rule is stated); b:long-word, b:stch-off, b:no-stch.

## 15.1.0

10a, 10b: Fix Arabic fallback shaping: wrong ligatures when a component is missing from the font, and disappearing
marks in legacy fonts. ->
Fix Arabic fallback shaping: wrong ligatures when a component is missing from the font, and disappearing marks in
legacy fonts. A ligature that the font lacks a component of is skipped and no longer shifts how the next ligature
matches; before, that next ligature could form from letters that do not spell it. In legacy fonts, whose `cmap`
holds the private-use code points of a legacy Arabic code page, the marks those code pages do not encode
(U+0653 to U+065E) no longer map to the private-use glyph that stands for unencoded characters; like any other
character the font lacks, they get the not-found glyph.
Labels: 10a in (font without GSUB lacking HEH final; LAM, LAM, MEEM text); b:complete, b:two-part-missing,
b:no-ligature-glyph, b:first-missing, b:gsub, b:earlier-ligature. 10b in (U+0653..U+065E in legacy fonts with the
catch-all glyph); b:encoded-mark, b:direct-mark, b:no-catch-all, b:not-legacy; U+063B..U+063F stay ungenerated.

19: Fix `COLR` glyph extents and mark positioning in fonts with empty layers. ->
Fix `COLR` glyph extents and mark positioning in fonts with empty layers: a layer that draws nothing no longer
adds a box at the glyph's origin to the extents of a colour glyph, so the extents cover the layers that draw, and
marks that fallback positioning places on the glyph follow those extents. A `COLRv1` glyph with a `ClipBox` keeps
the `ClipBox` as its extents.
Labels: in (COLRv0 and COLRv1, horizontal); b:no-empty-layer, b:clipbox, b:plain. All-empty glyphs (unit 39) and
vertical text stay ungenerated.

25a, 25b, 25c: Fix AAT shaping: wrong `kerx` kerning (formats 1 and 2) and mark positioning (format 4, a 14.3.0
regression), and ignored `kern` and `mort` tables with a non-first initial state. ->
Fix AAT shaping: wrong `kerx` kerning (formats 1 and 2) and mark positioning (format 4, a 14.3.0 regression), and
ignored `kern` and `mort` tables with a non-first initial state. In `kerx` format 2, the sum of a glyph pair's two
class values is a byte offset from the start of the kerning array. In `kerx` format 1, an entry's value index
counts values, not bytes, and a value list ends at the word 0xFFFF, not at an odd value: every value before
0xFFFF, odd or even, is applied. The `kern` table keeps its own rules for both formats. A glyph that a `kerx`
format 4 action attaches to another glyph now also takes that glyph's cross-stream offset, including the offset
that glyph has from its own attachment, as `GPOS` mark attachment does. A `kern` or `mort` state machine whose
entries move to a state stored before its initial state is now applied, together with the table's other
subtables; before, HarfBuzz ignored the whole table.
Labels: 25a in (kerx f1, f2) minus `beyond-note` (rk-25a-hist moves it); b:kern-format1, b:kern-format2,
b:other-format. 25b in (mark on a mark, mark on a cross-stream-kerned base); b:unshifted-base, b:in-stream-shift.
25c in; b:first-initial, b:unreached-rows. The format 2 sentence also settles the digest's two readings
(`Chap6kerx.md`, "also carry the array's offset"; pass 04 finding 6). Nothing here states CoreText's history:
the remaining format 1 cases do not depend on it (76 of 166 candidates; each follows `Chap6kerx.md` step by
step, with no list read past the glyphs on the stack and no ninth push).

44a, 44b: Fix wrong fallback metrics: the vertical descender in fonts without `vhea`, and the hanging baseline for
some scripts. ->
Fix wrong fallback metrics: the vertical descender in fonts without `vhea`, and the hanging baseline for some
scripts. For a font without `vhea`, `hb_ot_metrics_get_position_with_fallback()` now gives as the vertical
descender the descender that `hb_font_get_extents_for_direction()` reports for vertical text, not the ascender.
The hanging baseline that HarfBuzz measures from a letter of the script, in horizontal text when the font has no
`BASE` value for it (Devanagari, Bengali, Tibetan and the other scripts it lists, when the font has that letter),
is now measured whether the script comes as either of its OpenType tags, old or new (`beng` or `bng2`), or as an
`hb_script_t`; before, none of them matched.
Labels: 44a in; b:vhea, b:v-ascender, b:v-line-gap, b:h-descender. 44b in; b:vertical, b:other-script, b:no-glyph,
b:other-baseline, b:base.

## 14.3.1 to 14.6.0

26: Fix AAT insertion at the end of the text. ->
Fix AAT insertion at the end of the text: glyphs that a `morx` insertion adds in the end-of-text transition now get
their own properties, as glyphs inserted after a glyph do: their own `GDEF` class (before, they took the class of
the glyph before them), and a deleted-glyph value 0xFFFF in the inserted list leaves no glyph behind.
Labels: in (0xFFFF sentinel; mark after a base, base after a mark with GDEF); b:mid-before (a known 14.3.0 defect
every release keeps; pass 05 finding 5), b:mid-after.

37: Fix signed integer overflows when scaling glyph extents and when applying synthetic slant and emboldening. ->
Fix signed integer overflows when applying synthetic slant and emboldening to glyph extents: the slanted and
emboldened bearings, width and height are now computed in full and then clamped to the range of a 32-bit
position, instead of wrapping.
Labels: in (slant and emboldening of extents a client's font functions report); b:no-overflow. The clause "when
scaling glyph extents" is dropped: no candidate isolates 873dbc1e3 (gen_f8a.py, gen_37), so it would stay a stated
clause with no case (pass 03 finding 5). If it must stay, keep the old first clause and add the second sentence.

16: Fix shaping failures caused by out-of-range glyph IDs, a regression from 11.4.0. ->
Fix shaping failures caused by out-of-range glyph IDs, a regression from 11.4.0: a glyph ID of 65536 or more, such
as a not-found glyph our layout engine sets on the buffer, no longer makes `GSUB` and `GPOS` lookups treat the glyph
whose ID has the same low 16 bits as one they do not cover.
Labels: in (not-found glyph G + k * 65536 before G's pairs); b:in-range-nf, b:no-alias, b:oor-covered (IDs 32 and 33
are out of the font's range but below 65536, so the stated range keeps them outside; pass 05 finding 3).

## 15.2.0: shaping

17: Fix `GPOS` marks that attached to an earlier base when a ranged feature did not apply to the nearest base, a
regression from 7.0.0. ->
Fix `GPOS` marks that attached to an earlier base when a ranged feature did not apply to the nearest base, a
regression from 7.0.0: a mark-to-base or mark-to-ligature lookup considers only the nearest base or ligature
before the mark that its lookup flags do not skip, and when a ranged request switches the feature off for that
base, the mark stays unattached.
Labels: in; b:global, b:nearest-in-range, b:mark-excluded, b:no-earlier-base, b:skipped-mark.

27: Fix missing unsafe-to-break flags in text with cross-stream kerning from `kern` or `kerx`. ->
Fix missing unsafe-to-break flags in text with cross-stream kerning from `kern` or `kerx`. A cross-stream offset
moves the kerned glyph and every glyph after it in visual order, so every break from the first cross-stream kerned
pair on, in visual order, is now unsafe.
Labels: in = text that opens, in visual order, with a kerned pair; x:before-pair (S11: 15.2.0 also flags breaks
before the first pair, which this text and a careful port leave alone; 275 of the 442 changed candidates);
b:in-stream, b:no-pair.

## Cut

28: Fix missing unsafe-to-break flags with `HB_BUFFER_CLUSTER_LEVEL_GRAPHEMES`. -> no restatement; the unit is cut
and M3 removes the bullet.


## Phase B drafts (superseded)


Author notes, never shipped as they stand. The 16 example-dependent notes (rating R in CLAIMS.md) are too loose to
grade exactly, and the owner's sizing keeps them in scope (DESIGN.md section 13), so each gets a precise
behaviour rule, written from the upstream commit that made the change (commit messages and diffs, read in the
history clone). A rule goes into the instruction only after the sweep shows it determines 15.2.0's output on every
case of its unit (QA lens 4); otherwise it is rewritten, and the unit is cut only as a last resort. The wording
below is a draft in the requester's voice: no grading words, and it describes behaviour, never code.

| Unit | Note (as upstream wrote it) | Draft rule for the instruction | Source |
| --- | --- | --- | --- |
| 3 | The USE shaper now ends a word at spaces and symbols when it selects `isol`, `init`, `medi` and `fina` | When it selects those forms, the USE shaper ends a word at every symbol cluster (spaces, punctuation, currency and other symbols, letters of other scripts), at a generic base such as NO-BREAK SPACE (which still takes its own marks), and after a syllable containing ZERO WIDTH NON-JOINER; a dotted circle does not end a word. Syllables joined by these forms are unsafe to break, and the boundaries between them unsafe to concatenate | `20b05e0d` (#6764) |
| 6 | Dotted circles for Hangul tone marks and prohibited vowel sequences keep their advance in fonts without `GDEF` | A dotted circle the shaper inserts, for a Hangul tone mark or a prohibited vowel sequence, has the Unicode properties of U+25CC itself, not those of the mark next to it, so in a font without `GDEF` it keeps its advance like any base | `74fc8c86`, `2831a8a4` (#6710, #6711) |
| 9 | The Arabic shaper now centers `stch` tiles on short words and exact fits | When the fixed `stch` tiles plus one repeat are at least as wide as the stretch, the tiles are centred over it: the overhang is split in two (truncated toward zero), the group starting that far beyond the stretch on its start side; when the repeats fill the stretch exactly, nothing is left over to spread | `3df546b9`, `3aa3e2db` (#6733, #6763) |
| 10a | Arabic fallback shaping: wrong ligatures when a component is missing from the font | In fallback shaping, a ligature whose components are not all in the font is skipped completely; it never changes how later ligatures match | `d0b38a79` (#6474) |
| 10b | Arabic fallback shaping: disappearing marks in legacy fonts | Characters without an encoding in the legacy Arabic code pages map to no private-use glyph, so they keep their normal glyphs in legacy fonts | `31e89218` (#6454), to confirm |
| 16 | Shaping failures caused by out-of-range glyph IDs, a regression from 11.4.0 | Glyph IDs at or above the font's glyph count, as substitution lookups can produce, shape like any other glyph that the font's tables do not cover | `2994c4d0` (#6321), to confirm |
| 17 | `GPOS` marks no longer attach to an earlier base when a ranged feature did not apply to the nearest base | A mark-to-base or mark-to-ligature lookup looks only at the nearest preceding base (or ligature) its lookup flags do not skip; if the lookup is not enabled for that base, for example because a ranged feature request does not cover it, the mark is not attached | `1e055f1e` (#6736) |
| 25b | `kerx` format 4 mark positioning (a 14.3.0 regression) | A `kerx` format 4 action's cross-stream mark offset applies as soon as the action runs | `436f067b` (#6537) |
| 25c | `kern` and `mort` with a non-first initial state | `kern` and `mort` state tables whose initial state is not the first row are read and applied | `ec4a38c4` |
| 26 | AAT insertion at the end of the text | A `morx` insertion action triggered at the end of the text inserts its glyphs after the last glyph | `c14ad7c6` (#6142) |
| 27 | Missing unsafe-to-break flags with cross-stream kerning | When cross-stream kerning from `kern` or `kerx` attaches glyphs to each other, every glyph of that attachment chain is unsafe to break | `e079f056` (#6747) |
| 28 | Missing unsafe-to-break flags with `HB_BUFFER_CLUSTER_LEVEL_GRAPHEMES` | At `HB_BUFFER_CLUSTER_LEVEL_GRAPHEMES`, a range flagged unsafe to break or to concatenate covers every glyph whose cluster lies in it, even when clusters are reordered | `7f0fe356` (#6706) |
| 29 | An archaic trailing jamo after a Hangul syllable gets unsafe-to-break at character cluster levels | At the character cluster levels, a trailing jamo shaped together with the syllable before it is unsafe to break | `8e6c16ee` (#6709) |
| 37 | Overflow fixes in extents scaling, synthetic slant and emboldening | Scaling glyph extents and applying synthetic slant and emboldening saturate at the limits of a 32-bit position instead of wrapping | `873dbc1e`, `3c8a65ed` |
| 44a | Fallback vertical descender without `vhea` | Without `vhea`, the fallback vertical descender is the descender of the synthesized vertical extents, not the ascender | `879be16f` (#6466) |
| 44b | Hanging baseline for some scripts | The hanging-baseline fallback recognizes scripts by their OpenType tags, old and new (for example both Bengali tags) | `f030bd21` (#6467) |
| 19 | `COLR` glyph extents and mark positioning in fonts with empty layers | Pending: the commit is not identified yet | – |
| 25a | `kerx` formats 1 and 2 | Pending: three commits (`88e5077a`, `a92e0996`, `90417543`); format 2 class values are byte offsets, format 1 value indices and terminators follow Apple's documentation, and format 1 keeps CoreText's history behaviour | – |
