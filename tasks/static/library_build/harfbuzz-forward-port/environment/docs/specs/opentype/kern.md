# kern - Kerning Table
Source: kern - Kerning (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/kern
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope

- 'kern' stores inter-glyph spacing adjustments. It does not apply to fonts with CFF
  outlines; those must kern through GPOS (see gpos.md).
- This is the OpenType form of the table (version 0 header). Apple defines a larger 'kern'
  table with more features; those extensions are not part of OpenType.
- A table has one or more subtables. Each subtable holds data for horizontal or vertical
  text, and holds either kerning values (adjustments) or minimum values (limits on how far the
  combined kerning and tracking may move glyphs).
- Kerning values from several subtables add up, so their order does not matter, except that
  subtables of minimum values are normally placed last so they can cap the accumulated total.

## KernHeader

KernHeader

| Type | Field | Description |
|---|---|---|
| uint16 | version | Table version, 0. |
| uint16 | nTables | Number of subtables that follow. |

## Subtable header

Subtables follow the KernHeader directly, one after another. Every subtable starts with:

| Type | Field | Description |
|---|---|---|
| uint16 | version | Subtable version, 0. |
| uint16 | length | Byte length of the subtable, this header included. |
| uint16 | coverage | Kind of data and subtable format (bit fields below). |

Coverage bit fields:

| Sub-field | Bit(s) | Description |
|---|---|---|
| horizontal | 0 | 1 = data for horizontal text, 0 = vertical text. |
| minimum | 1 | 1 = the subtable holds minimum values, 0 = kerning values. |
| cross-stream | 2 | 1 = the adjustment is perpendicular to the text direction (see below). |
| override | 3 | 1 = this subtable's value replaces the value accumulated so far instead of adding to it. |
| reserved1 | 4-7 | Must be 0. |
| format | 8-15 | Subtable format. Only 0 and 2 are defined; 1 and 3 to 255 are reserved. |

As masks: horizontal 0x0001, minimum 0x0002, cross-stream 0x0004, override 0x0008,
reserved1 0x00F0, format 0xFF00 (format = coverage >> 8).

Cross-stream kerning: in horizontal text it moves glyphs vertically (positive values up,
negative down); in vertical text it moves glyphs horizontally (positive right, negative
left). A kerning value of 0x8000 puts the cross-stream adjustment back to 0.

The format-specific data follows the subtable header; length covers both, so the next
subtable starts length bytes after the start of this one.

## Format 0: ordered list of pairs

Windows supports only this format.

KernSubtableFormat0

| Type | Field | Description |
|---|---|---|
| uint16 | nPairs | Number of kerning pairs. |
| uint16 | searchRange | (Largest power of 2 <= nPairs) * size of one pair record (6 bytes). |
| uint16 | entrySelector | log2(largest power of 2 <= nPairs): number of binary-search iterations. |
| uint16 | rangeShift | (nPairs - largest power of 2 <= nPairs) * size of one pair record. |
| KernPair | kernPairs[nPairs] | The pairs. |

KernPair record

| Type | Field | Description |
|---|---|---|
| uint16 | left | Glyph ID of the left glyph of the pair. |
| uint16 | right | Glyph ID of the right glyph of the pair. |
| FWORD | value | Adjustment in design units: positive moves the glyphs apart, negative moves them closer. |

Rules:

- Records are sorted by the unsigned 32-bit key (left << 16) | right, in increasing order.
- To kern a pair, form that key and binary-search kernPairs for it; a missing key means no
  adjustment from this subtable. searchRange, entrySelector and rangeShift are only aids for
  a power-of-two binary search (rangeShift counts the records that searchRange leaves out).

## Format 2: class-based two-dimensional array

Left glyphs and right glyphs are each mapped to classes (separate mappings), and a
two-dimensional array gives the value for each (left class, right class) pair.

- Each row is one left class, each column one right class. Row 0 and column 0 are for
  glyphs that do not kern and contain only zeros.
- Class values are stored premultiplied: right class values are multiplied by the size of
  one value (2 bytes), and left class values by the size of one row (rowWidth). A value is
  located by adding the two class values to the address of the array; no multiplication is
  needed at run time.

KernSubtableFormat2

| Type | Field | Description |
|---|---|---|
| uint16 | rowWidth | Byte width of one row of the array. |
| Offset16 | leftClassOffset | Offset from the start of this subtable to the left-hand class table. |
| Offset16 | rightClassOffset | Offset from the start of this subtable to the right-hand class table. |
| Offset16 | kerningArrayOffset | Offset from the start of this subtable to the kerning array. |

Class table header (used for both class tables):

| Type | Field | Description |
|---|---|---|
| uint16 | firstGlyph | First glyph ID covered by the class table. |
| uint16 | nGlyphs | Number of consecutive glyph IDs covered. |

The header is followed by nGlyphs uint16 class values, one for each glyph from firstGlyph
on. Glyphs that do not kern must map to row or column 0.

The kerning array holds FWORD values for (number of left classes) x (number of right
classes) cells, stored row by row.

Looking up a pair (own pseudo-code):

```
lv = left class value of the left glyph   (0 if outside firstGlyph .. firstGlyph+nGlyphs-1)
rv = right class value of the right glyph (0 if outside its range)
value = FWORD stored at (start of kerning array) + lv + rv
```

This format is the fastest to look up, at the cost of size: the array has a cell for every
combination of left and right class, kerning or not.
