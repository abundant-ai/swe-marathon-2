# Upstream released HarfBuzz 15.1.0: take its fixes as well

## Goal

Upstream has released HarfBuzz 15.1.0. Please take the fixes listed below into our tree too, the same way as before:
our product stays on its certified 14.3.0 base, and each note becomes a change of our own in that code. Everything
from my earlier request still holds, including its notes from 14.3.1 to 15.0.0, which are repeated at the end so that
this request stands on its own.

As a reminder of why: our document typesetting product lays out reports, books and forms in about forty scripts and
embeds HarfBuzz 14.3.0 as a static library. That build is certified for the regulated customers we serve, a new major
version would have to be certified again, and upstream's 15.0 reworked the layout code around the 24-bit glyph tables,
so its changes do not apply to our tree.

## Context

- `/app/harfbuzz` is our tree: HarfBuzz 14.3.0 as we ship it, with the changes made so far for the earlier request. It
  is a git repository, so `git diff` and `git log` show what has changed.
- `test/` in the tree holds upstream's own expectations for 14.3.0, and `util/` builds `hb-shape` and the other
  command-line tools when you configure a build of your own with them. Where a note changes behaviour, an expectation
  under `test/` may change with it.
- `/app/docs/specs/` has the OpenType specification, Microsoft's script development documents, Apple's documentation
  of the AAT tables and Unicode's text segmentation annex. `/app/docs/unicode/` has the Unicode 18.0 data files that
  upstream's table generators read, Microsoft's Universal Shaping Engine override files for Unicode 18, the IANA
  language subtag registry and the OpenType language tag list. `/app/docs/notes/` has every note so far, one file per
  request.
- There is no network access. gcc and g++ 13, meson, ninja, ragel 6.10, Python 3 with fontTools and packTab, and the
  GLib development files are installed; fontTools is there so that you can build fonts of your own.

## How our product uses HarfBuzz

Every build we ship compiles `/app/harfbuzz` with these commands, unchanged:

```
meson setup build --buildtype=release -Ddefault_library=static \
  -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dchafa=disabled -Dicu=disabled \
  -Dfreetype=disabled -Dpng=disabled -Dzlib=disabled -Dgraphite2=disabled \
  -Draster=disabled -Dvector=disabled -Dgpu=disabled -Dsubset=disabled \
  -Dtests=disabled -Dintrospection=disabled -Ddocs=disabled -Dutilities=disabled
ninja -C build
```

So the library uses its own OpenType font functions and its own Unicode data. The build regenerates the shaper state
machines from the `.rl` files with ragel and regenerates nothing else, so any other generated file you change has to
be in the tree.

Our layout engine calls HarfBuzz's public C API only. It shapes text with features turned on for the whole text or
for ranges of it, sets the direction, script and language or lets HarfBuzz guess them, chooses cluster levels and
buffer flags, sets the buffer's not-found glyph, and applies variations, synthetic slant and synthetic emboldening. It
reads glyph positions, glyph flags, glyph extents, font and fallback metrics, baselines, style values, language and
script tags, and face data. Our customers also bring Apple-format fonts with `morx`, `mort`, `kerx`, `kern` and `trak`
tables, and we lay those out with the same library.

Our customers' documents depend on every detail of what the library returns. A document a customer has approved is
laid out again each time it is opened, exported or printed, and a glyph that moves, or a line that breaks in a
different place, changes a document they have already signed off. So:

- Every note, new or earlier, must hold for every font and text it applies to, not only for the case that prompted
  it.
- Anything the notes do not change must come out as it does from our 14.3.0 build today: the same glyphs, clusters,
  positions, flags, extents, metrics and function results, for every font, text and setting.

## The notes, 15.1.0

As before, these are the parts of upstream's notes that concern what our product uses; subsetting, the rendering
libraries, the platform and third-party integrations, the 24-bit glyph tables and speed work are left out.

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
  and 0 when nothing is consumed. `buf_consumed` may be `NULL`. `buf_len` is the size of `buf` in bytes, or -1 if it is
  `NULL`-terminated.
- Fix Indic shaping of the Unicode 18 Devanagari and Bengali additions.
- Fix Arabic fallback shaping: wrong ligatures when a component is missing from the font, and disappearing marks in
  legacy fonts.
- Fix `COLR` glyph extents and mark positioning in fonts with empty layers.
- Fix AAT shaping: wrong `kerx` kerning (formats 1 and 2) and mark positioning (format 4, a 14.3.0 regression), and
  ignored `kern` and `mort` tables with a non-first initial state.
- Fix wrong outlines in `gvar` fonts with intermediate tuples.
- Fix `hb_face_create_or_fail()` rejecting face indices with named-instance bits set.
- Fix wrong fallback metrics: the vertical descender in fonts without `vhea`, and the hanging baseline for some
  scripts.
- Fix `hb_ot_layout_lookup_collect_glyph_alternates()` collecting garbage from `AlternateSubst` and `SingleSubst`
  format 1 lookups.

## Notes from the earlier request, still in force (14.3.1 to 15.0.0)

- Fix AAT insertion at the end of the text. (14.3.1)
- Glyph positions and extents now saturate instead of overflowing. (14.4.0)
- Arabic Windows-1256 fallback shaping is now enabled on all platforms. (14.4.0)
- Fix `avar` axis value mapping in fonts that repeat the boundary entries. (14.4.0)
- Update the Unicode data and script support to Unicode 18.0, including script values for Jurchen, Proto-Cuneiform
  and Seal, and the corresponding shaping support. New API: `HB_SCRIPT_JURCHEN` (`Jurc`), `HB_SCRIPT_PROTO_CUNEIFORM`
  (`Pcun`) and `HB_SCRIPT_SEAL` (`Seal`). (14.5.0)
- Map the `fonupa` (Uralic Phonetic Alphabet) BCP 47 variant to the `UPPH` OpenType language system tag. (14.5.1)
- Fix signed integer overflows when scaling glyph extents and when applying synthetic slant and emboldening.
  (14.5.1)
- Fix shaping failures caused by out-of-range glyph IDs, a regression from 11.4.0. (14.6.0)
- Fix a possible use-after-free in `hb_font_set_face()`, which now resets the font functions to the defaults for the
  new face. The function is now deprecated; use `hb_font_create()` instead. (15.0.0)

## What to deliver

The changed tree, in place in `/app/harfbuzz`. Keep it building with the commands above at all times.

## Switching over

When the tree does all of the above, we rebuild our product from it and ship it to our customers in our next update.
