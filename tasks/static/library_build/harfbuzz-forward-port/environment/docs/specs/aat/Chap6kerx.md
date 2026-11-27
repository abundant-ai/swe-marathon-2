# 'kerx' table: extended kerning (digest)
Source: Kerx Table - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6kerx.html
These notes restate the source's structures and rules; where they differ, the source governs.

## Purpose and scope

'kerx' is the 32-bit successor of the AAT 'kern' table (see Chap6kern.md). It
holds glyph positioning adjustments organised as a sequence of subtables. A
subtable can target horizontal or vertical text and can shift glyphs along the
line (with-stream) or across it (cross-stream). Adjustments from all applicable
subtables are added together, so subtable order carries no meaning.

Defined subtable formats: 0, 1, 2, 4 and 6. The values 3, 5 and 7..255 are
reserved. (The page's prose calls this "four" formats while listing five.)

| Format | Kind |
|---|---|
| 0 | sorted list of glyph pairs with values |
| 1 | state machine that kerns as many as eight glyphs by context |
| 2 | two-dimensional array addressed by byte offsets from class lookups |
| 4 | state table that aligns control points or anchor points |
| 6 | two-dimensional array addressed by indices from class lookups |

All offsets in this note are byte offsets unless stated otherwise. Field
offsets in the tables below are derived from the field sizes.

## Table header

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | version | 2, 3 or 4 |
| 2 | uint16 | padding | unused, 0 |
| 4 | uint32 | nTables | number of subtables that follow |

Version-dependent additions:

- version >= 3: after the last subtable comes a subtable glyph coverage array
  (see "Subtable glyph coverage" below).
- version >= 4: a kerning value can be either one number or, in variation
  fonts, a vector of numbers (see "Variation fonts" below).

## Subtable header (12 bytes, starts every subtable)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | length | size of the whole subtable in bytes, this header included |
| 4 | uint32 | coverage | flag bits and format number, see next table |
| 8 | uint32 | tupleCount | 0 except in variation fonts; ignored when the table version is below 4 |

When tupleCount > 0, the subtable no longer stores single kerning values; each
value becomes a vector of tupleCount FUnit values tied to the global tuples of
the font's 'gvar' table. How a format stores such vectors is given per format.

### coverage field (uint32)

| Mask | Name | Meaning |
|---|---|---|
| 0x80000000 | vertical | set when the subtable holds vertical kerning values |
| 0x40000000 | crossStream | set when the values act perpendicular to the text flow |
| 0x20000000 | variation | set when the subtable holds variation kerning values |
| 0x10000000 | processDirection | clear: walk the glyphs from first to last; set: from last to first. Only meaningful for the state-table formats 1 and 4 |
| 0x0FFFFF00 | unusedBits | must be 0 |
| 0x000000FF | formatMask | subtable format (0, 1, 2, 4 or 6) |

Cross-stream sign conventions: in horizontal text a cross-stream value moves
the glyph vertically (positive up, negative down); in vertical text it moves
the glyph horizontally (positive right, negative left).

With-stream sign convention (formats 0, 2 and 6 with tupleCount 0): a
positive value pushes the two glyphs apart, a negative value pulls them
together.

## Format 0: ordered list of kerning pairs

Body (follows the 12-byte subtable header):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | nPairs | number of pair records |
| 4 | uint32 | searchRange | (largest power of two <= nPairs) x (size of one record in bytes) |
| 8 | uint32 | entrySelector | log2 of (largest power of two <= nPairs); number of binary-search iterations |
| 12 | uint32 | rangeShift | (nPairs - largest power of two <= nPairs) x (size of one record in bytes) |
| 16 | record[nPairs] | pairs | sorted pair records |

Pair record (6 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | left | glyph index of the left-hand glyph |
| 2 | uint16 | right | glyph index of the right-hand glyph |
| 4 | int16 | value | tupleCount 0: kerning value in FUnits. tupleCount >= 1: offset from the start of the subtable to a vector of tupleCount FUnit values |

Rules:

- Records are sorted by the unsigned 32-bit key (left << 16) | right.
- The list may finish with a sentinel record left = 0xFFFF, right = 0xFFFF,
  value = 0 (optional in 'kerx'; mandatory in 'kern').
- Binary search: first check whether the wanted key falls inside the
  searchRange part of the list. If it does, search from the first record;
  otherwise begin rangeShift bytes into the list (always a record boundary).
  The loop then runs entrySelector times.

## Format 1: contextual kerning state table

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | STXHeader (16 bytes) | stHeader | extended state table header |
| 16 | uint32 | valueTable | offset from the start of the state table (the STXHeader) to the kerning value array |

STXHeader layout (defined with 'morx'; see Chap6morx.md):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | nClasses | number of glyph classes, fixed classes included |
| 4 | uint32 | classTableOffset | offset to the class lookup table |
| 8 | uint32 | stateArrayOffset | offset to the state array (uint16 cells) |
| 12 | uint32 | entryTableOffset | offset to the entry table |

All four offsets are measured from the start of the STXHeader.

Entry (three 16-bit words):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | newState | index of the next state (state array row) |
| 2 | uint16 | flags | see next table |
| 4 | uint16 | valueIndex | index into the kerning value array of the first value to apply; 0xFFFF means no kerning |

Entry flags:

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | push | push the current glyph's position onto the kerning stack |
| 0x4000 | dontAdvance | keep the same glyph position when moving to the new state |
| 0x2000 | reset | reset the kerning data, that is, empty the kerning stack |
| 0x1FFF | (unused) | must be 0 |

Operation:

- The kerning stack holds the positions of up to eight glyphs, which is why
  the format can kern up to eight glyphs at once.
- An entry whose valueIndex is not 0xFFFF starts reading the value array at
  that index. Each value read pops one glyph position from the stack and
  applies that value to the popped glyph. Reading stops at the end-of-list
  marker, the 16-bit value 0xFFFF.
- tupleCount 0: each value is one FUnit kerning value.
- tupleCount >= 1: each value is a tupleCount-long vector of FUnit values,
  applied to the popped glyph; the list still ends with a single 0xFFFF word.
- The page does not fix the order in which push, value application and reset
  are carried out inside one entry.

## Format 2: offset-based class array

Each glyph is mapped to a left-hand class and a right-hand class through two
separate lookups; rows of the array are left-hand classes, columns are
right-hand classes, and each cell is a kerning value. Class 0 (row 0 and
column 0) stands for glyphs that do not kern; all its cells must be 0.

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | rowWidth | bytes in one row of the kerning array |
| 4 | uint32 | leftOffsetTable | offset from the start of the subtable to the left-hand class lookup table |
| 8 | uint32 | rightOffsetTable | offset from the start of the subtable to the right-hand class lookup table |
| 12 | uint32 | array | offset from the start of the subtable to the kerning array |

Class lookups:

- Both class tables are AAT lookup tables whose values are unsigned 16-bit
  offsets; a glyph absent from a lookup gets 0.
- Right-hand values are already multiplied by the size of one kerning value
  (2 bytes).
- Left-hand values are already multiplied by the row size in bytes and also
  carry the array's offset (the page phrases this as offset "from the start
  of the kerning array"). Because the products are pre-computed, no
  multiplication is needed at run time.
- To read a pair's value, look up the left-hand (or top) glyph and the
  right-hand (or bottom) glyph, add the two values, and fetch the value at
  that position; the page describes adding them to the address of the
  kerning array. (The 'kern' format 2 text measures the same sum from the
  start of the subtable.)

Values: tupleCount 0 gives FUnit values (positive apart, negative together);
tupleCount >= 1 gives offsets from the start of the subtable to
tupleCount-long FUnit vectors.

## Format 4: control point / anchor point positioning state table

The current glyph is moved so that one of its points lands exactly on a point
of an earlier, marked glyph.

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | STXHeader (16 bytes) | stHeader | extended state table header (layout as in format 1) |
| 16 | uint32 | flags | action type and action table offset, see next table |

Format 4 flags (uint32):

| Mask | Meaning |
|---|---|
| 0xC0000000 | action type (2-bit field): 0 = control point numbers, 1 = anchor point numbers, 2 = coordinates |
| 0x3F000000 | unused, must be 0 |
| 0x00FFFFFF | offset from the start of the state table to the control point (action) table |

Entry (three 16-bit words):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | newState | index of the next state |
| 2 | uint16 | flags | see next table |
| 4 | uint16 | actionIndex | 0xFFFF = no action; otherwise index of the action record to perform |

Entry flags:

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | mark | remember the current glyph's position; that glyph becomes the marked glyph |
| 0x4000 | dontAdvance | keep the same glyph position when moving to the new state |

Action records (all records in one subtable share the subtable's action type):

Action type 0, control point numbers (4 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | markControlPoint | point number in the marked glyph |
| 2 | uint16 | currControlPoint | point number in the current glyph |

Action type 1, anchor point numbers (4 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | markAnchorPoint | anchor index in the marked glyph |
| 2 | uint16 | currAnchorPoint | anchor index in the current glyph |

Action type 2, coordinates (8 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | FWord | markX | x of the marked glyph's point |
| 2 | FWord | markY | y of the marked glyph's point |
| 4 | FWord | currX | x of the current glyph's point |
| 6 | FWord | currY | y of the current glyph's point |

Rules:

- Performing an action positions the current glyph so that the two named
  points coincide.
- Anchor points come from the font's 'ankr' table when it exists (see
  Chap6ankr.md); otherwise the "anchor points" are the outline points of the
  'glyf' table.
- tupleCount has no effect on format 4. For variation-aware attachment use
  action type 0 (control point numbers) and let 'gvar' move those points.

## Format 6: index-based class array

Same row/column model as format 2 (class 0 means "no kerning" and its row and
column must be all zeros), but the class lookups deliver array indices
instead of byte offsets.

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | flags | bit 0 (0x00000001) = valuesAreLong; no other flag is defined |
| 4 | uint16 | rowCount | rows in the kerning array |
| 6 | uint16 | columnCount | columns in the kerning array |
| 8 | uint32 | rowIndexTableOffset | offset from the start of the subtable to the row index lookup table |
| 12 | uint32 | columnIndexTableOffset | offset from the start of the subtable to the column index lookup table |
| 16 | uint32 | kerningArrayOffset | offset from the start of the subtable to the kerning array |
| 20 | uint32 | kerningVectorOffset | offset from the start of the subtable to the kerning vectors; present only when tupleCount >= 1 |

Rules:

- valuesAreLong set: the values in both index lookups and in the kerning
  array are 4 bytes; clear: 2 bytes. It must be set when
  rowCount x columnCount > 65535; it may be set otherwise, but that only
  makes the table bigger and is discouraged.
- Both index tables are lookup tables. Row values are already multiplied by
  columnCount. Glyphs not covered by a lookup get 0.
- Index of a pair's value = row value of the first glyph + column value of
  the second glyph.
- tupleCount 0: array elements are FUnit values (positive apart, negative
  together). tupleCount >= 1: array elements are offsets, measured from the
  start of the kerning vector area, to tupleCount-long FUnit vectors; those
  offsets are 4 bytes when valuesAreLong is set, otherwise 2 bytes.

## Subtable glyph coverage (table version >= 3)

Placed after the last subtable.

| Type | Field | Meaning |
|---|---|---|
| uint32[nTables] | subtableOffsets | one per subtable: offset from the start of this coverage structure to that subtable's bitfield; 0xFFFFFFFF = the subtable has no bitfield |
| uint8[] | coverageBitfields | the bitfields |

- Bitfields are used only for format 1 and format 4 subtables.
- Size of one bitfield: (numGlyphs + 7) / 8 bytes (CHAR_BIT = 8), rounded up
  to a multiple of four bytes.
- Glyph g is covered when bitfield[g / 8] & (1 << (g & 7)) is non-zero.
- Intended use: build a bitfield of the glyphs present in the run, AND it
  with a subtable's bitfield, and skip the subtable when the result is zero.
  Bitfields that contain only glyphs which actually trigger kerning actions
  let the most subtables be skipped.

## Variation fonts (table version >= 4)

- With tupleCount = 0 a pair carries one 16-bit FUnit value.
- With tupleCount >= 1 a pair carries a vector of tupleCount 16-bit FUnit
  values: element 0 is the default kerning value and each following element
  is a delta for one of the global tuples of 'gvar', in order. Deltas not
  present count as 0. (A font with eight global tuples can therefore use
  tupleCount 0 or 2..9.)
- The current instance's normalized axis values give a scalar for each
  global tuple, computed exactly as 'gvar' computes tuple scalars. Applied
  value = default + sum over tuples of (scalar x delta).
- Illustration from the page: axes wght and wdth; tuples, in order, (1,0),
  (-1,0), (0,1), (0,-1), (-1,-1), (1,-1), (1,1), (-1,1); vector
  [100, 5, -10, -15, 20, 0, 0, -25, 30]; instance wght = 0.4, wdth = -0.25.
  Only tuples whose non-zero coordinates all have the instance value between
  0 and that coordinate contribute: (1,0) adds 0.4 x 5 = 2, (0,-1) adds
  0.25 x -15 = -3.75, and (1,-1) qualifies but its delta is 0. Result: 98.25.

## Dependencies and availability

- Glyph indices must stay below the glyph count in 'maxp'.
- Anchor points: 'ankr' if present, else 'glyf' points.
- Per the page: 'kerx' works from OS X 10.7 and iOS 7; format 2 subtables do
  not work before iOS 7 / OS X 10.9; the processDirection bit and version 3
  tables need iOS 9 / OS X 10.11; tupleCount >= 1 and format 6 are described
  as planned for later releases.
