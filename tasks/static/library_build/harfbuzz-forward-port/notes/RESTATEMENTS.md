# Restated notes (Phase B drafts)

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
