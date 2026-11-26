# Bring our HarfBuzz 14.3.0 up to upstream's fixes, through 15.0.0

## Goal

Our document typesetting product lays out reports, books and forms in about forty scripts, on desktops and on our
servers. It embeds HarfBuzz 14.3.0 as a static library, and we have frozen that version: the build is certified for
the regulated customers we serve, and a new major version would have to be certified again, which we cannot do this
year. Upstream's 15.0 also turned on the 24-bit glyph tables and formats by default and reworked the layout code
around them, so its changes do not apply to our tree.

We still need the fixes upstream has shipped since 14.3.0 in the parts of HarfBuzz we use. Upstream describes them in
its release notes, and we take each one into our 14.3.0 code as a change of our own. This request covers the releases
from 14.3.1 to 15.0.0; I will send the later ones as they come out.

## Context

- `/app/harfbuzz` is our tree: HarfBuzz 14.3.0 as we ship it, without upstream's speed-measurement programs and CI
  files. It is a git repository with a single commit, so `git diff` shows your changes.
- `test/` in the tree holds upstream's own expectations for 14.3.0, and `util/` builds `hb-shape` and the other
  command-line tools when you configure a build of your own with them. Where a note below changes behaviour, an
  expectation under `test/` may change with it.
- `/app/docs/specs/` has the OpenType specification, Microsoft's script development documents, Apple's documentation
  of the AAT tables and Unicode's text segmentation annex. `/app/docs/unicode/` has the Unicode 18.0 data files that
  upstream's table generators read (`src/update-unicode-tables.make` lists them), Microsoft's Universal Shaping
  Engine override files for Unicode 18, the IANA language subtag registry and the OpenType language tag list.
  `/app/docs/notes/` has the notes below as a text file.
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

- Every note below must hold for every font and text it applies to, not only for the case that prompted it.
- Anything the notes do not change must come out as it does from our 14.3.0 build today: the same glyphs, clusters,
  positions, flags, extents, metrics and function results, for every font, text and setting.

## The notes, 14.3.1 to 15.0.0

These are the parts of upstream's release notes that concern what our product uses. We left out the rest: subsetting,
the raster, vector and GPU libraries, the platform and third-party integrations, the 24-bit glyph tables and the other
new table formats, and speed work.

**14.3.1**

- Fix AAT insertion at the end of the text.

**14.4.0**

- Glyph positions and extents now saturate instead of overflowing.
- Arabic Windows-1256 fallback shaping is now enabled on all platforms.
- Fix `avar` axis value mapping in fonts that repeat the boundary entries.

**14.5.0**

- Update the Unicode data and script support to Unicode 18.0, including script values for Jurchen, Proto-Cuneiform
  and Seal, and the corresponding shaping support. New API: `HB_SCRIPT_JURCHEN` (`Jurc`), `HB_SCRIPT_PROTO_CUNEIFORM`
  (`Pcun`) and `HB_SCRIPT_SEAL` (`Seal`).

**14.5.1**

- Map the `fonupa` (Uralic Phonetic Alphabet) BCP 47 variant to the `UPPH` OpenType language system tag.
- Fix signed integer overflows when scaling glyph extents and when applying synthetic slant and emboldening.

**14.6.0**

- Fix shaping failures caused by out-of-range glyph IDs, a regression from 11.4.0.

**15.0.0**

- Fix a possible use-after-free in `hb_font_set_face()`, which now resets the font functions to the defaults for the
  new face. The function is now deprecated; use `hb_font_create()` instead.

## What to deliver

The changed tree, in place in `/app/harfbuzz`. Keep it building with the commands above at all times.

## Switching over

When the tree does all of the above, we rebuild our product from it and ship it to our customers in our next update.
