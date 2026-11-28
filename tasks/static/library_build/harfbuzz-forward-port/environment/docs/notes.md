# HarfBuzz release notes, 14.3.1 to 15.2.0

The changes our product needs, by release, as in the work order.

These are the parts of upstream's release notes that concern what our product uses. We left out the rest: subsetting,
the raster, vector and GPU libraries, the platform and third-party integrations, the 24-bit glyph tables and the other
new table formats (color bitmap format 19 among them), the work limits, speed work, and two fixes that change nothing
our product can observe.

**14.3.1**

- Fix AAT insertion at the end of the text.

**14.4.0**

- Glyph positions now saturate instead of overflowing.
- Arabic Windows-1256 fallback shaping is now enabled on all platforms.

**14.5.0**

- Update the Unicode data and script support to Unicode 18.0, including script values for Jurchen, Proto-Cuneiform and
  Seal, and the corresponding shaping support: the three scripts go through the Universal Shaping Engine, as the other
  scripts it shapes do, and Jurchen and Seal take the ideographic baseline. New API: `HB_SCRIPT_JURCHEN` (`Jurc`),
  `HB_SCRIPT_PROTO_CUNEIFORM` (`Pcun`) and `HB_SCRIPT_SEAL` (`Seal`).

**14.5.1**

- Map the `fonupa` (Uralic Phonetic Alphabet) BCP 47 variant to the `UPPH` OpenType language system tag, and `UPPH`
  back to `und-fonupa`.
- Fix signed integer overflows when applying synthetic slant and emboldening to glyph extents: the slanted and
  emboldened bearings, width and height are now computed in full and then clamped to the range of a 32-bit position,
  instead of wrapping.

**14.6.0**

- Fix shaping failures caused by out-of-range glyph IDs, a regression from 11.4.0.

**15.0.0**

- `hb_font_set_face()` is deprecated; use `hb_font_create()` instead. What the function does now is the 15.2.0 note
  below.

**15.1.0**

- Add buffer deserialization functions that report their progress as a byte offset, declared in `hb-buffer.h`:

  ```c
  HB_EXTERN hb_bool_t
  hb_buffer_deserialize_glyphs2 (hb_buffer_t *buffer,
                                 const char *buf,
                                 int buf_len,
                                 unsigned int *buf_consumed,
                                 hb_font_t *font,
                                 hb_buffer_serialize_format_t format);

  HB_EXTERN hb_bool_t
  hb_buffer_deserialize_unicode2 (hb_buffer_t *buffer,
                                  const char *buf,
                                  int buf_len,
                                  unsigned int *buf_consumed,
                                  hb_buffer_serialize_format_t format);
  ```

  Each does what `hb_buffer_deserialize_glyphs()` or `hb_buffer_deserialize_unicode()` does, with the same return
  value and the same partial buffer contents when parsing fails. Instead of a pointer into `buf`, it stores in
  `*buf_consumed` the byte offset from `buf` of the character after the last one consumed, on success or failure,
  and 0 when nothing is consumed. `buf_consumed` may be `NULL`. `buf_len` is the size of `buf` in bytes, or -1 if it
  is `NULL`-terminated.
- Fix Indic shaping of the Unicode 18 Devanagari and Bengali additions.
- Fix Arabic fallback shaping: wrong ligatures when a component is missing from the font, and disappearing marks in
  legacy fonts.
- Fix `COLR` glyph extents and mark positioning in fonts with empty layers.
- Fix AAT shaping: wrong `kerx` kerning (formats 1 and 2) and mark positioning (format 4, a 14.3.0 regression), and
  ignored `kern` and `mort` tables with a non-first initial state.
- Fix wrong outlines in `gvar` fonts with intermediate tuples.
- Fix `hb_face_create_or_fail()` rejecting face indices with named-instance bits set. An index whose face is not in
  the blob is still rejected.
- Fix wrong fallback metrics: the vertical descender in fonts without `vhea`, and the hanging baseline for some
  scripts.
- Fix `hb_ot_layout_lookup_collect_glyph_alternates()` collecting garbage from `AlternateSubst` and `SingleSubst`
  format 1 lookups.

**15.2.0: new features**

- A font constructor that does not install default font functions, for clients that install their own, declared in
  `hb-font.h`:

  ```c
  HB_EXTERN hb_font_t *
  hb_font_create_without_funcs_or_fail (hb_face_t *face);
  ```

  It makes a new font object with the same initial properties as `hb_font_create()`, but without setting up default
  font functions. The font keeps the face alive and makes it immutable, and its scale and variation coordinates start
  as in `hb_font_create()`. The `HB_FONT_FUNCS` environment variable is not consulted. It returns the new font, or
  `NULL` if allocation fails.
- A function that gets the `JSTF` extender glyphs of a script, declared in `hb-ot-layout.h`:

  ```c
  HB_EXTERN unsigned
  hb_ot_layout_get_extender_glyphs (hb_face_t      *face,
                                    hb_script_t     script,
                                    hb_language_t   language,
                                    unsigned        start_offset,
                                    unsigned       *glyphs_count /* IN/OUT.  May be NULL */,
                                    hb_codepoint_t *glyphs       /* OUT.     May be NULL */);
  ```

  Extender glyphs lengthen a word for justification in some scripts, such as variants of tatweel (U+0640) in Arabic.
  It returns only glyphs the `JSTF` table lists for the script, starting at `start_offset`; `language` is currently
  unused. On input `*glyphs_count` is the most glyphs to return, on output the number returned (possibly zero). The
  return value is the total number of extender glyphs for the script.

**15.2.0: shaping**

- Fix per-syllable `GSUB` lookups that matched a glyph 15 syllables later, for example in long Myanmar text.
- Fix `GPOS` marks that attached to an earlier base when a ranged feature did not apply to the nearest base, a
  regression from 7.0.0. The mark is now left unattached.
- Fix precomposed characters that stayed decomposed in text with no marks, in the Indic, Khmer, Myanmar and USE
  shapers.
- A global feature request now overrides earlier ranged requests for the same feature. Before, the ranged request
  kept its value and could disable unrelated features.
- An unsupported character followed by a variation selector now gets the not-found glyph set on the buffer, instead
  of always getting glyph 0.
- Fix fallback mark positioning to use the x offset of the base.
- Fix cross-stream kerning from the `kern` table. The reset value caused a large shift. The offset used the scale of
  the wrong axis.
- Fix missing unsafe-to-break flags in text with cross-stream kerning from `kern` or `kerx`.
- Apply the `kern` table in vertical text when the client requests `vkrn` and `GPOS` does not have it. The values
  apply as HarfBuzz already applies vertical `kern` values.

**15.2.0: script-specific shaping**

- The Indic shaper no longer applies `init` to a first syllable that follows a letter or mark in the pre-context.
- The USE shaper no longer uses a space (other than U+00A0 NO-BREAK SPACE, which stays a base) as the base of a
  dependent vowel. The vowel now gets a dotted circle.
- The USE shaper now ends a word at spaces and symbols when it selects `isol`, `init`, `medi` and `fina` forms.
- The Khmer shaper now moves only one Coeng Ro before the base, and only when it is the first or second coeng of the
  syllable.
- A Hangul tone mark at the start of the text now gets only one dotted circle, set as it is when the beginning-of-text
  flag is not set.
- An archaic trailing jamo after a Hangul syllable that has no final consonant now gets the unsafe-to-break flag at
  the character cluster levels (`HB_BUFFER_CLUSTER_LEVEL_MONOTONE_CHARACTERS` and
  `HB_BUFFER_CLUSTER_LEVEL_CHARACTERS`): the shaper splits such a syllable into its jamo to set the trailing jamo with
  them, so a break before that jamo changes the syllable.
- Dotted circles for Hangul tone marks and prohibited vowel sequences now keep their advance in fonts without `GDEF`.
  A dotted circle the shaper inserts now has the properties of a U+25CC typed in the text, and no longer those of the
  mark it stands for: where that makes it a base (in fonts without `GDEF`, or whose `GDEF` classes it as a base), it
  keeps its advance, it is not shifted as zeroed marks are, and a zero-width tone mark after it is placed on it.
- Prohibited vowel sequences now get a dotted circle also when a default ignorable, such as ZWJ, is between the
  vowels. The dotted circle goes right before the second vowel, after the default ignorables.
- The Hebrew shaper now composes presentation forms in fonts that have `mark` only under the `DFLT` script.
- The Arabic shaper now centers `stch` tiles on short words and exact fits.

**15.2.0: AAT shaping**

- Fix `trak` tracking in vertical text, where positive tracking decreased the spacing.
- Apply the pair and class kerning of `kerx` together with `GPOS` when `GPOS` has no kerning feature. Before, HarfBuzz
  did not apply `kerx` in such fonts.
- A later request for a feature now overrides earlier requests, as in OpenType shaping.

**15.2.0: core library**

- The deprecated `hb_font_set_face()` now does nothing. To use another face, create a new font with `hb_font_create()`.
- Fix scaled glyph extents, which could be smaller than the glyph. The extents now round outward on both axes, after
  scaling. The extents of fractional outlines can grow by one unit.
- Empty glyphs now have zero extents. Before, they could have a negative width and a positive height.
- Fix `hb_style_get_value()`: the `OS/2` optical size is now in points, not in twentieths of a point; the slant angle
  from `fvar` or `STAT` now includes the synthetic slant; and the function now skips `STAT` values that are for older
  sibling fonts.
- Fix `hb_face_collect_unicodes()`, which missed most code points of `cmap` format 13 subtables. Code points mapped to
  a glyph the font does not have are still left out.
- Fix the position of nested `glyf` components that use anchor points.
- `hb_buffer_get_glyph_positions()` now returns zero positions for items that the client added after the first call.
  Before, those positions could be uninitialized or old.
