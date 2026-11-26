# 'kern' table: AAT kerning (digest)
Source: Kern Table - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6kern.html
These notes restate the source's structures and rules; where they differ, the source governs.

## Purpose and scope

'kern' stores inter-glyph spacing adjustments in one or more subtables. A
subtable may serve horizontal or vertical text and may act along the line or
across it (cross-stream). Results of all applicable subtables are summed, so
subtable order does not matter. Four formats are defined, 0 through 3;
formats 4..255 are reserved. The 32-bit successor table is 'kerx' (see
Chap6kerx.md).

| Format | Kind |
|---|---|
| 0 | sorted list of glyph pairs with values |
| 1 | state machine that kerns as many as eight glyphs by context |
| 2 | two-dimensional array of values with left/right class tables |
| 3 | compact variant of format 2 using byte-sized classes and indices |

## Table versions

There are two header layouts:

| Header | version field | nTables field | Where used |
|---|---|---|---|
| Current Apple layout | fixed32, 0x00010000 | uint32 | the layout described on this page |
| Older layout | uint16 | uint16 | the layout Microsoft Windows recognises; Windows does not recognise the newer one |

Notes from the page:

- Apple's layout engine can detect an old-style table and still use it
  correctly, but using the old layout on OS X is discouraged.
- Recommended choice: the new layout for Apple-only fonts, the old layout for
  fonts that must also work on Windows.
- The page gives no further detail of the old layout (its subtable header is
  defined by the OpenType 'kern' specification, not here). Since the new
  version value is 0x00010000, its first 16 bits read as 1.

Current header:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | fixed32 | version | 0x00010000 |
| 4 | uint32 | nTables | number of subtables |

## Subtable header (8 bytes)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | length | subtable size in bytes, this header included |
| 4 | uint16 | coverage | flag bits and format, see next table |
| 6 | uint16 | tupleIndex | for variation fonts: which tuple this subtable covers |

### coverage field (uint16)

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | kernVertical | set when the subtable holds vertical kerning values |
| 0x4000 | kernCrossStream | set when the subtable holds cross-stream kerning values |
| 0x2000 | kernVariation | set when the subtable holds variation kerning values |
| 0x1F00 | kernUnusedBits | must be 0 |
| 0x00FF | kernFormatMask | subtable format, 0..3 |

Cross-stream signs: in horizontal text the shift is vertical (positive up,
negative down); in vertical text it is horizontal (positive right, negative
left).

## Format 0: ordered list of kerning pairs

Body (follows the 8-byte subtable header):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | nPairs | number of pair records |
| 2 | uint16 | searchRange | (largest power of two <= nPairs) x (record size in bytes) |
| 4 | uint16 | entrySelector | log2 of (largest power of two <= nPairs); binary-search iteration count |
| 6 | uint16 | rangeShift | (nPairs - largest power of two <= nPairs) x (record size in bytes) |
| 8 | record[nPairs] | pairs | sorted pair records |

Pair record (6 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | left | left-hand glyph index |
| 2 | uint16 | right | right-hand glyph index |
| 4 | int16 | value | FUnits; positive moves the glyphs apart, negative together |

Rules:

- Sort key: unsigned 32-bit (left << 16) | right.
- The list must end with the record left = 0xFFFF, right = 0xFFFF, value = 0.
- Binary search: decide whether the key lies inside the searchRange portion;
  if so search from the first record, otherwise from rangeShift bytes into the
  list (a record boundary); iterate entrySelector times.

## Format 1: contextual kerning state table

### Subtable body

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | StateHeader (8 bytes) | stHeader | classic AAT state table header, see below |
| 8 | uint16 | valueTable | the field table defines it as the offset from the beginning of the subtable to the kerning values; the page's worked example measures it from the start of the state table header |

### StateHeader and classic state table pieces

The page does not define StateHeader itself (it belongs to the manual's
state-table chapter); its worked example shows this layout, with every offset
measured from the start of the StateHeader:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | stateSize | number of classes, which is also the byte width of one state array row |
| 2 | uint16 | classTable | offset to the class subtable |
| 4 | uint16 | stateArray | offset to the state array |
| 6 | uint16 | entryTable | offset to the entry table |

Class subtable (as shown in the example):

| Type | Field | Meaning |
|---|---|---|
| uint16 | firstGlyph | first glyph that has a class entry |
| uint16 | nGlyphs | number of class entries |
| uint8[nGlyphs] | classArray | class of glyph firstGlyph + i |

Glyphs outside firstGlyph .. firstGlyph + nGlyphs - 1 get class 1 (out of
bounds). Fixed classes (named in the example): 0 = End of text, 1 = Out of
bounds, 2 = Deleted glyph, 3 = End of line; font-defined classes start at 4.

State array: one row per state, stateSize bytes per row, each byte an entry
table index. In the example state 0 is "start of text" and state 1 is
"start of line" (identical rows there).

### Entries and flags

Entry (two 16-bit words):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | newState | byte offset from the start of the state table to the row of the next state |
| 2 | uint16 | flags | see next table |

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | push | push the current glyph's position onto the kerning stack |
| 0x4000 | dontAdvance | keep the same glyph position when moving to the new state |
| 0x3FFF | valueOffset | byte offset to the value list for the glyphs on the stack (the field table says from the beginning of the subtable; the worked example measures from the start of the state table); 0 = no values |

### Applying values

- The kerning stack holds up to eight glyph positions.
- A non-zero valueOffset points at a list of 16-bit FUnit values. Each value
  pops one glyph from the stack and applies the value to that glyph.
- The list ends at the first odd value: the low bit of a value is the
  end-of-list flag. The page says the exact interpretation of that last value
  depends on the subtable's coverage field. In the worked example the value
  0x0001 means "kern by 0, end of list" and 683 is described as a
  cross-stream step of 682 FUnits that also ends the list, which shows that
  the low bit is not part of the amount.
- Cross-stream reset value: in a cross-stream subtable a value whose
  remaining bits equal 0x8000 (stored as 0x8001 when it ends the list) does
  not move the glyph by an amount; it returns the cross-stream position to
  the baseline.

### Initial state quirk

The stateArray offset is redundant (the rows can be located without it), so
some fonts use it to name a start state other than "start of text". To detect
this, compute where the state array would normally start; if the stored
offset differs, use the state it points to as the initial state.

### Worked example (condensed)

The page's example font (2048 units per em) raises each successive letter
across the stream, keeps punctuation at the level of the preceding glyph, and
drops back to the baseline at a space.

- Classes: 4 = letter, 5 = space, 6 = punctuation (plus the four fixed classes).
- States: 0 start of text, 1 start of line (same row as 0), 2 in word.
- Value lists: [0x0001] (zero, end), [683] (682 FUnits, end), [0x8001]
  (cross-stream reset, end).
- Rows of the state array (entry index per class 0..6):
  state 0 and 1: 2,0,0,2,1,0,0; state 2: 2,3,3,2,4,5,1.

| Entry | Next state | Flags | Effect |
|---|---|---|---|
| 0 | 0 (start of text) | push, values [0x0001] | glyph kerned by 0 |
| 1 | 2 (in word) | push, values [0x0001] | glyph kerned by 0 |
| 2 | 0 (start of text) | none | nothing |
| 3 | 2 (in word) | none | nothing |
| 4 | 2 (in word) | push, values [683] | letter shifted by 682 across the stream |
| 5 | 0 (start of text) | push, values [0x8001] | space resets cross-stream kerning to the baseline |

The example implies that cross-stream shifts accumulate along the run until a
reset value is applied. (Some offset arithmetic in the page's byte-by-byte
listing is inconsistent; the structure above is what the listing encodes.)

## Format 2: simple n x m array with class tables

Rows are left-hand classes, columns are right-hand classes, cells are kerning
values. Row 0 and column 0 represent glyphs that do not kern and must be all
zeros.

Simple array header (follows the subtable header):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | rowWidth | bytes in one row of the array |
| 2 | uint16 | leftOffsetTable | offset from the start of the subtable to the left-hand class table |
| 4 | uint16 | rightOffsetTable | offset from the start of the subtable to the right-hand class table |
| 6 | uint16 | array | offset from the start of the subtable to the kerning array |

Class table (used for both sides):

| Type | Field | Meaning |
|---|---|---|
| uint16 | firstGlyph | first glyph in the range |
| uint16 | nGlyphs | number of glyphs in the range |
| uint16[nGlyphs] | offsets | value for glyph firstGlyph + i |

Rules:

- Right-hand values are pre-multiplied by 2 (bytes per value).
- Left-hand values are pre-multiplied by the row size in bytes and already
  include the array's offset from the start of the subtable; so they should
  never be smaller than the array offset.
- Default for a glyph outside the left-hand range: the array offset. Default
  for a glyph outside the right-hand range: 0.
- Value of a pair: left value + right value is the offset from the start of
  the subtable to the int16 kerning value.

## Format 3: compact class array

Header (follows the subtable header):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | glyphCount | number of glyphs in the font |
| 2 | uint8 | kernValueCount | number of kerning values |
| 3 | uint8 | leftClassCount | number of left-hand classes |
| 4 | uint8 | rightClassCount | number of right-hand classes |
| 5 | uint8 | flags | 0, reserved |

Arrays that follow immediately, in this order:

| Type | Field | Meaning |
|---|---|---|
| FWord[kernValueCount] | kernValue | the kerning values |
| uint8[glyphCount] | leftClass | left-hand class of each glyph |
| uint8[glyphCount] | rightClass | right-hand class of each glyph |
| uint8[leftClassCount x rightClassCount] | kernIndex | indices into kernValue |

Lookup for glyphs L and R:

    value = kernValue[ kernIndex[ leftClass[L] * rightClassCount + rightClass[R] ] ]

Limits: at most 256 left classes, 256 right classes and 256 distinct values;
larger needs call for format 2. Format 3 is quicker to evaluate than format 2
and may be smaller.

## Dependencies

Glyph indices must be below the glyph count recorded in 'maxp'.
