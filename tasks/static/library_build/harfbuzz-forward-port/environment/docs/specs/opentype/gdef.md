# GDEF - Glyph Definition Table
Source: GDEF - Glyph Definition Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/gdef
These notes restate the source's structures and rules; where they differ, the source governs.

## Role of the table

GDEF carries glyph properties that OpenType Layout processing consults. It is made of six
independent parts, each reached through its own header offset. Any part may be missing
(NULL offset), and a client may use any subset of them.

| Part | Header field | What it provides |
|---|---|---|
| Glyph class definition (GlyphClassDef) | glyphClassDefOffset | Type of each glyph: base, ligature, mark or component. GSUB and GPOS use it to tell glyph kinds apart and to apply lookup flags. |
| Attachment point list (AttachList) | attachListOffset | For each glyph, the contour points that GPOS uses as attachment points, so a client can cache them with rendered glyphs instead of decoding GPOS. |
| Ligature caret list (LigCaretList) | ligCaretListOffset | Caret positions inside ligature glyphs, used to select and highlight individual components. |
| Mark attachment class definition (MarkAttachClassDef) | markAttachClassDefOffset | Groups mark glyphs into mark attachment classes, used as a lookup filter. |
| Mark glyph sets (MarkGlyphSets) | markGlyphSetsDefOffset | Any number of mark sets (they may overlap), used as a lookup filter. |
| Item variation store (ItemVariationStore) | itemVarStoreOffset | Variation deltas, in variable fonts, for values in GDEF, GPOS and JSTF. |

GSUB, GPOS and JSTF lookups read GDEF information while they run (see chapter2.md (Lookup
table) for the LookupFlag bits). In a variable font, GDEF, GPOS and JSTF all take their
variation deltas from the single item variation store that lives in GDEF.

## Header

Three versions are defined: 1.0, 1.2 and 1.3 (there is no 1.1). Each later version appends
one field to the previous layout. Every offset is measured from the start of the GDEF table
and may be NULL (0), which means that part is absent.

- Version 1.0 has four offsets (12-byte header).
- Version 1.2 adds markGlyphSetsDefOffset (14-byte header).
- Version 1.3 adds itemVarStoreOffset, a 32-bit offset (18-byte header).

The appended fields exist only when minorVersion is at least 2 (mark glyph sets) or at least
3 (item variation store); a version 1.0 header ends after markAttachClassDefOffset.

### GDEF header, version 1.0

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Always 1. |
| uint16 | minorVersion | 0 for this layout. |
| Offset16 | glyphClassDefOffset | ClassDef giving each glyph's type class; from GDEF start; NULL if absent. |
| Offset16 | attachListOffset | AttachList table; from GDEF start; NULL if absent. |
| Offset16 | ligCaretListOffset | LigCaretList table; from GDEF start; NULL if absent. |
| Offset16 | markAttachClassDefOffset | ClassDef assigning mark attachment classes; from GDEF start; NULL if absent. |

### GDEF header, version 1.2

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Always 1. |
| uint16 | minorVersion | 2 for this layout. |
| Offset16 | glyphClassDefOffset | ClassDef giving each glyph's type class; from GDEF start; NULL if absent. |
| Offset16 | attachListOffset | AttachList table; from GDEF start; NULL if absent. |
| Offset16 | ligCaretListOffset | LigCaretList table; from GDEF start; NULL if absent. |
| Offset16 | markAttachClassDefOffset | ClassDef assigning mark attachment classes; from GDEF start; NULL if absent. |
| Offset16 | markGlyphSetsDefOffset | MarkGlyphSets table; from GDEF start; NULL if absent. |

### GDEF header, version 1.3

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Always 1. |
| uint16 | minorVersion | 3 for this layout. |
| Offset16 | glyphClassDefOffset | ClassDef giving each glyph's type class; from GDEF start; NULL if absent. |
| Offset16 | attachListOffset | AttachList table; from GDEF start; NULL if absent. |
| Offset16 | ligCaretListOffset | LigCaretList table; from GDEF start; NULL if absent. |
| Offset16 | markAttachClassDefOffset | ClassDef assigning mark attachment classes; from GDEF start; NULL if absent. |
| Offset16 | markGlyphSetsDefOffset | MarkGlyphSets table; from GDEF start; NULL if absent. |
| Offset32 | itemVarStoreOffset | ItemVariationStore table (32-bit offset); from GDEF start; NULL if absent. |

## Glyph class definition table (GlyphClassDef)

GlyphClassDef is an ordinary class definition table, format 1 or 2 (see chapter2.md (Class
definition table)). Its class values have fixed meanings:

GlyphClassDef enumeration

| Class | Name | Notes |
|---|---|---|
| 1 | Base glyph (single character, spacing glyph) | Skipped by lookups that set IGNORE_BASE_GLYPHS. |
| 2 | Ligature glyph (multiple character, spacing glyph) | Skipped by lookups that set IGNORE_LIGATURES. |
| 3 | Mark glyph (non-spacing combining glyph) | Skipped by IGNORE_MARKS; subject to the mark attachment class and mark filtering set filters. |
| 4 | Component glyph (part of single character, spacing glyph) | Not referenced by any GSUB or GPOS format. |

Rules:

- A font need not classify every glyph. A glyph with no assigned class is class 0 (the
  ClassDef default).
- Component glyphs are pieces that a ligature can be built from, either by a glyph that
  references them or by emitting the pieces in sequence. No GSUB or GPOS subtable format uses
  class 4.
- GSUB and GPOS rely on these classes to distinguish glyph kinds (for example a base from
  the mark that follows it) and to apply lookup flags correctly.
- When the font has no GlyphClassDef, the client has to determine and maintain the glyph
  classes itself for GSUB and GPOS processing.

## How lookup flags use GDEF data

The LookupFlag bits and the Lookup table's markFilteringSet field are defined in chapter2.md
(Lookup table). The parts that consult GDEF are:

| Mask | Name | GDEF data consulted | Effect during matching |
|---|---|---|---|
| 0x0002 | IGNORE_BASE_GLYPHS | GlyphClassDef, class 1 | Base glyphs are skipped. |
| 0x0004 | IGNORE_LIGATURES | GlyphClassDef, class 2 | Ligature glyphs are skipped. |
| 0x0008 | IGNORE_MARKS | GlyphClassDef, class 3 | Every mark glyph is skipped. |
| 0x0010 | USE_MARK_FILTERING_SET | MarkGlyphSets, set number markFilteringSet | Marks that are not in that set's Coverage are skipped. |
| 0xFF00 | MARK_ATTACHMENT_CLASS_FILTER | MarkAttachClassDef | When this high byte is non-zero, marks whose mark attachment class differs from it are skipped. |

Processing rules:

1. A skipped glyph is handled as if it were absent from the glyph sequence: matching of the
   other pattern positions continues past it.
2. The current glyph (first position of the input pattern) is always compared directly; the
   flags affect the remaining input positions and, in chained lookups, the backtrack and
   lookahead positions.
3. Precedence: IGNORE_MARKS overrides both mark filters, and a mark filtering set overrides
   a mark attachment class given in the high byte.
4. The IGNORE bits name only classes 1, 2 and 3, so glyphs of class 0 or class 4 are never
   skipped by them.
5. A font that sets an IGNORE bit must have a GlyphClassDef; a non-zero attachment class
   filter needs a MarkAttachClassDef; USE_MARK_FILTERING_SET needs a MarkGlyphSets table
   (GDEF 1.2 or later) and a markFilteringSet field in the Lookup table.

## Attachment point list table (AttachList)

AttachList lets a client cache the coordinates of attachment points together with glyph
bitmaps. It lists every glyph that has attachment points defined in GPOS and, for each, the
contour points involved. GPOS processing does not need it; without it a client would have to
decode the GPOS lookups to find the points.

AttachList table

| Type | Name | Description |
|---|---|---|
| Offset16 | coverageOffset | Coverage of the glyphs that have attachment points; from AttachList start. |
| uint16 | glyphCount | Count of glyphs with attachment points (entries in attachPointOffsets). |
| Offset16 | attachPointOffsets[glyphCount] | One AttachPoint offset per covered glyph, in Coverage Index order; from AttachList start. |

AttachPoint table (one glyph)

| Type | Name | Description |
|---|---|---|
| uint16 | pointCount | How many attachment points the glyph has. |
| uint16 | pointIndices[pointCount] | Contour point index of each attachment point, sorted ascending. |

## Ligature caret list table (LigCaretList)

LigCaretList gives caret positions for ligature glyphs so a client can select and highlight
the components of a ligature. Without it, a client must place carets with no knowledge of
where the components lie.

LigCaretList table

| Type | Name | Description |
|---|---|---|
| Offset16 | coverageOffset | Coverage of the ligature glyphs that have carets; from LigCaretList start. |
| uint16 | ligGlyphCount | Number of ligature glyphs (entries in ligGlyphOffsets). |
| Offset16 | ligGlyphOffsets[ligGlyphCount] | One LigGlyph offset per covered ligature, in Coverage Index order; from LigCaretList start. |

LigGlyph table (one ligature)

| Type | Name | Description |
|---|---|---|
| uint16 | caretCount | Number of carets; equals the ligature's component count minus 1. |
| Offset16 | caretValueOffsets[caretCount] | CaretValue table offsets, from LigGlyph start, sorted by increasing coordinate. |

### Caret value tables

Three formats exist. The first two bytes of each are the format number.

CaretValueFormat1 table: design units only

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| int16 | coordinate | Caret position (X or Y) in design units. |

CaretValueFormat2 table: contour point

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 2. |
| uint16 | caretValuePointIndex | Index of the glyph contour point whose position gives the caret. |

CaretValueFormat3 table: design units plus Device or VariationIndex table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 3. |
| int16 | coordinate | Caret position (X or Y) in design units. |
| Offset16 | deviceOffset | Device table (non-variable font) or VariationIndex table (variable font) adjusting coordinate; from the start of this CaretValue table. |

### Interpreting caret values

1. A ligature with N components has N - 1 carets, one at each boundary between adjacent
   components. LigGlyph lists them in increasing coordinate order.
2. Each caret is one coordinate on the baseline: an X value for horizontal text, a Y value
   for vertical text, as set by the writing direction of the script or language system in use.
3. Format 1: the coordinate in design units is the caret position. It cannot be adjusted for
   particular device resolutions.
4. Format 2: the caret is located by contour point caretValuePointIndex on the glyph outline.
   Hinting may move that point; its final, hinted position gives the caret value for the
   size being rendered. This format stores no design-unit coordinate, and the source gives no
   fallback for when the outline point cannot be obtained.
5. Format 3, non-variable font: deviceOffset points to a Device table whose per-ppem pixel
   corrections adjust the scaled coordinate at particular sizes and resolutions (see
   chapter2.md (Device and VariationIndex tables)).
6. Format 3, variable font: deviceOffset points to a VariationIndex table. Its delta-set
   index selects deltas in the GDEF item variation store; the delta for the current instance
   is added to coordinate. Format 3 is the only caret format that can carry variation data.
7. A caret value that does not reference a VariationIndex table keeps the same value in every
   variation instance.
8. Several caret values may share one VariationIndex table, and several VariationIndex
   tables may reference the same variation deltas; still, each varying value needs its own
   reference.

## Mark attachment class definition table (MarkAttachClassDef)

MarkAttachClassDef is an ordinary class definition table (see chapter2.md (Class definition
table)) that sorts mark glyphs into mark attachment classes. A lookup selects one of these
classes through the high byte of its LookupFlag (MARK_ATTACHMENT_CLASS_FILTER); marks of
other classes are then skipped by that lookup. Each glyph has exactly one mark attachment
class, so these classes cannot overlap, and a lookup can name only one of them.

## Mark glyph sets table (MarkGlyphSets)

Mark glyph sets serve the same filtering purpose as mark attachment classes but, unlike
classes, the sets may intersect. Each set is an ordinary Coverage table (see chapter2.md
(Coverage table)). A lookup references at most one set, through the markFilteringSet field of
its Lookup table, whose value is an index into coverageOffsets.

MarkGlyphSets table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| uint16 | markGlyphSetCount | Number of mark glyph sets. |
| Offset32 | coverageOffsets[markGlyphSetCount] | 32-bit offsets, from MarkGlyphSets start, to one Coverage table per set; the array index is the set number. |

Note that these offsets are Offset32, not Offset16.

## Item variation store and VariationIndex tables

- The item variation store is defined in otvarcommonformats.md (ItemVariationStore and its
  subtables), which also points to the interpolation rules.
- It holds adjustment deltas arranged in delta sets addressed by delta-set indices. Data
  outside the store supplies the delta-set index for each value that varies.
- Within GDEF, GPOS and JSTF, delta-set indices are carried by VariationIndex tables, one
  referenced for each value that needs adjustment. In GDEF they appear only in
  CaretValueFormat3.
- The GDEF store serves GDEF caret values and also varying values in GPOS and JSTF; deltas
  for the different tables may be interleaved and organised in any way.
- A VariationIndex table is a Device table variant with its own format value (see
  chapter2.md (Device and VariationIndex tables)). Because the same offset fields serve both,
  a variable font cannot use Device tables.
- Applications that do not support font variations, and fonts that are not variable, ignore
  VariationIndex tables.
