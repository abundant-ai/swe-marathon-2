# OpenType Font Variations Common Table Formats
Source: OpenType Font Variations Common Table Formats (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/otvarcommonformats
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope

A variable font stores delta adjustment values. Each delta is keyed by two things: the
target data item it changes (one outline point coordinate, one CVT entry, OS/2.sTypoAscender,
and so on) and the region of the normalized variation space in which it acts. This chapter
defines the two shared containers for deltas:

- **Tuple variation store**: deltas grouped by region, each group covering many targets.
  Used by 'gvar' (one store per glyph, the GlyphVariationData table; see gvar.md) and by
  'cvar' (the whole table is one store). Built for decoding every target of a store in one
  pass.
- **Item variation store** (ItemVariationStore): deltas grouped by target, each row holding
  one delta per region. Used by MVAR, HVAR, VVAR, BASE, GDEF (which also serves GPOS and
  JSTF) and COLR; CFF2 uses one for its region definitions. Built for random access to
  single items.

Where each family of deltas lives:

| Target data | Container |
|---|---|
| 'glyf' outline point positions | 'gvar', one tuple variation store per glyph ID |
| CFF2 outline points | inside the CFF2 outline data; the regions come from an ItemVariationStore held in CFF2 |
| 'cvt ' values | 'cvar', a single tuple variation store |
| 'hmtx' glyph metrics | HVAR (hvar.md) |
| 'vmtx' and VORG glyph metrics | VVAR |
| GPOS anchors and other GDEF, GPOS or JSTF values | the ItemVariationStore in GDEF (gdef.md) |
| font-wide values from OS/2, 'hhea', 'gasp', 'post', 'vhea' | MVAR (mvar.md) |
| BASE baseline metrics, COLR values | an ItemVariationStore inside BASE or COLR itself |

## Coordinate normalization and region scalars

The source defers both to the Font Variations Overview chapter, which is not among these notes; they are not
restated here.



## Tuple variation store

### Overall shape

A GlyphVariationData table ('gvar') or a 'cvar' table starts with a header that holds an
array of TupleVariationHeader records, followed by a block of serialized data. Logically the
store is a list of tuple variation tables, one per region; physically each one is split into
its header (in the header array) and its data (in the serialized block). The 'cvar' header
adds major and minor version fields; otherwise the two layouts match.

### Tuple record

| Type | Name | Description |
|---|---|---|
| F2DOT14 | coordinates[axisCount] | One normalized coordinate per axis; the element count equals axisCount in 'fvar'. |

The UserTuple record of 'fvar' (fvar.md) is a different structure: it holds Fixed
user-scale values, while a Tuple record holds F2DOT14 normalized values.

### Store headers

GlyphVariationData header:

| Type | Name | Description |
|---|---|---|
| uint16 | tupleVariationCount | Packed field: flags in the top 4 bits, number of tuple variation tables for the glyph in the low 12 bits (1 to 4095). |
| Offset16 | dataOffset | Byte offset of the serialized data, measured from the start of this GlyphVariationData table. |
| TupleVariationHeader | tupleVariationHeaders[tupleVariationCount] | One variable-size header per tuple variation table; the count is the low 12 bits of tupleVariationCount. |

'cvar' table header:

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version of 'cvar'; 1. |
| uint16 | minorVersion | Minor version of 'cvar'; 0. |
| uint16 | tupleVariationCount | Same packing as above; low 12 bits count the tuple variation tables (1 to 4095). |
| Offset16 | dataOffset | Byte offset of the serialized data, measured from the start of the 'cvar' table. |
| TupleVariationHeader | tupleVariationHeaders[tupleVariationCount] | One variable-size header per tuple variation table. |

tupleVariationCount bit fields:

| Mask | Name | Description |
|---|---|---|
| 0x8000 | SHARED_POINT_NUMBERS | The serialized data opens with a packed point-number list that tables without private numbers use. |
| 0x7000 | Reserved | Reserved; must be 0. |
| 0x0FFF | COUNT_MASK | Low 12 bits: number of tuple variation tables, which is also the number of headers. |

In 'gvar' the shared numbers are outline point numbers (component indices for a composite
glyph); in 'cvar' they are CVT indices.

### TupleVariationHeader

| Type | Name | Description |
|---|---|---|
| uint16 | variationDataSize | Byte length of this table's block in the serialized data; the header itself is not counted. |
| uint16 | tupleIndex | Packed field: flags in the top 4 bits, index into the shared tuple array in the low 12 bits. |
| Tuple | peakTuple | Present only when EMBEDDED_PEAK_TUPLE is set; 'cvar' always has it. |
| Tuple | intermediateStartTuple | Present only when INTERMEDIATE_REGION is set; follows the embedded peak, if there is one. |
| Tuple | intermediateEndTuple | Present only when INTERMEDIATE_REGION is set; follows the start tuple. |

tupleIndex bit fields:

| Mask | Name | Description |
|---|---|---|
| 0x8000 | EMBEDDED_PEAK_TUPLE | A peak Tuple follows tupleIndex directly; the low 12 bits are then ignored. Must be set in every 'cvar' header. |
| 0x4000 | INTERMEDIATE_REGION | The region is intermediate: a start Tuple and an end Tuple follow, after the embedded peak when present. |
| 0x2000 | PRIVATE_POINT_NUMBERS | This table's block begins with its own packed point numbers, used in place of the shared list. |
| 0x1000 | Reserved | Reserved flag; must be 0. |
| 0x0FFF | TUPLE_INDEX_MASK | Low 12 bits: shared tuple index ('gvar' only). |

Rules:

- Header size in bytes is 4, plus 2 x axisCount when EMBEDDED_PEAK_TUPLE is set, plus
  4 x axisCount when INTERMEDIATE_REGION is set. Headers sit back to back, so walking the
  array means adding that size each time.
- Every tuple variation table has a peak: an embedded Tuple, or (in 'gvar' only) the shared
  tuple selected by TUPLE_INDEX_MASK. Shared tuples live outside the store, in the 'gvar'
  header area (gvar.md); 'cvar' neither needs nor supports them.
- Start and end tuples of an intermediate region are always embedded. INTERMEDIATE_REGION is
  independent of how the peak is given.
- PRIVATE_POINT_NUMBERS is independent of SHARED_POINT_NUMBERS. A table with private numbers
  uses them and ignores the shared list; a table without private numbers uses the shared
  list. This page gives no rule for a table that has neither.

### Serialized data

The block at dataOffset is laid out as:

1. Shared packed point numbers, present only when SHARED_POINT_NUMBERS is set.
2. Then one block per tuple variation table, in header order, each exactly variationDataSize
   bytes long:
   - private packed point numbers, present only when that header has PRIVATE_POINT_NUMBERS;
   - packed deltas. In 'gvar': the X deltas of all listed points, then the Y deltas. In
     'cvar': a single set, one delta per listed CVT.

Block i therefore starts at dataOffset + (length of the shared point list) + the sum of
variationDataSize over headers 0 to i-1, so a reader can skip the block of any table whose
scalar is zero.

### Packed point numbers

A packed point list is a count followed by runs. The count takes one or two bytes:

| First byte b0 | Count bytes | Meaning |
|---|---|---|
| 0 | 1 | No runs follow. The table covers every target: all of the glyph's point numbers including the phantom points ('gvar'), or every CVT ('cvar'). |
| 1 to 127 | 1 | Count = b0. |
| 128 to 255 (high bit set) | 2 | Count = ((b0 & 0x7F) << 8) \| b1, that is the big-endian uint16 with its top bit cleared (15-bit count). |

For instance 0x32 means 50 numbers, and 0x81 0x22 means 0x0122 = 290 numbers.

Each run starts with a control byte:

| Mask | Name | Description |
|---|---|---|
| 0x80 | POINTS_ARE_WORDS | Set: the run's elements are uint16; clear: uint8. |
| 0x7F | POINT_RUN_COUNT_MASK | Low 7 bits: number of elements in the run minus 1 (runs hold 1 to 128 elements). |

Decoding rule: elements are unsigned increments. A running total starts at 0 for the whole
list; each element, in every run, is added to it and the new total is the next point number.
So the first element of the first run is an absolute number, and every later element,
including the first one of each later run, is a difference from the previous number. Runs are
read until the count is reached.

```
decode_point_list(cur):
    b0 = u8(cur)
    if b0 == 0:
        return ALL_TARGETS
    n = b0
    if b0 & 0x80:
        n = ((b0 & 0x7F) << 8) | u8(cur)
    numbers = []
    total = 0
    while length(numbers) < n:
        ctl = u8(cur)
        repeat (ctl & 0x7F) + 1 times:
            step = (ctl & 0x80) ? u16be(cur) : u8(cur)
            total = total + step
            append total to numbers
    return numbers
```

The page does not say what to do when a run would run past the count.

Consequences: the list never decreases. A zero increment repeats a point number; each repeat
has its own delta and all of them are added to that point.

### Packed deltas

The packed delta data stores no count. The number of logical deltas equals the number of
listed points (or of all targets when the list is "all"), doubled in 'gvar' because the X
deltas come first and the Y deltas follow. Runs are read until that many deltas exist.

Each run starts with a control byte:

| Mask | Name | Description |
|---|---|---|
| 0x80 | DELTAS_ARE_ZERO | The run stores no bytes; it stands for (count) deltas of value 0. |
| 0x40 | DELTAS_ARE_WORDS | Set: the run's values are int16; clear: int8. |
| 0x3F | DELTA_RUN_COUNT_MASK | Low 6 bits: number of deltas in the run minus 1 (runs hold 1 to 64 deltas). |

```
decode_deltas(cur, wanted):
    out = []
    while length(out) < wanted:
        ctl = u8(cur)
        k = (ctl & 0x3F) + 1
        if ctl & 0x80:
            append k zeros to out                      # nothing stored
        else if ctl & 0x40:
            repeat k times: append i16be(cur) to out
        else:
            repeat k times: append i8(cur) to out
    return out
```

For instance a control byte of 0x94 stands for 0x14 + 1 = 21 zero deltas with no data bytes,
and 0x40 announces a single int16. This page assigns no combined meaning to a control byte
with both 0x80 and 0x40 set.

### Applying a tuple variation store

1. For each TupleVariationHeader, build the region (peak, plus start and end when
   intermediate) and compute its scalar for the current instance (see Region scalars). The
   headers can be scanned first to drop tables whose scalar is 0.
2. For each table that applies, decode its point list (private, else shared) and its deltas.
3. 'gvar' only: for a simple glyph whose list names some but not all points of a contour,
   infer deltas for the unnamed points of that contour (gvar.md). 'cvar': CVTs that are not
   listed get nothing from this table.
4. Multiply each delta by the table's scalar and add it to its target (in 'gvar', X deltas to
   X coordinates and Y deltas to Y coordinates).
5. Tables may be processed in any order; their contributions add up.

Packed point and delta data must be decoded from the start of a block, so random access to
one target is not possible. That is acceptable for outlines, which are processed whole, but
not for glyph metrics needed without outlines; HVAR and VVAR exist for that case.

### 'gvar' versus 'cvar'

| Aspect | 'gvar' | 'cvar' |
|---|---|---|
| Store | one GlyphVariationData per glyph ID, no version fields | the whole table, with major and minor version |
| Shared data across stores | shared tuple records | none |
| Peak tuple | embedded, or a shared tuple index | always embedded |
| Point numbers refer to | outline points, or component indices for a composite glyph, followed by four phantom points | CVT indices |
| Deltas per point number | two (all X values, then all Y values) | one |
| Targets missing from the list | deltas may be inferred (simple glyphs only) | not adjusted |

In 'gvar', the last four point numbers of every glyph, simple or composite, are the phantom
points that carry horizontal and vertical advances and side bearings (gvar.md).

## Item variation store

The ItemVariationStore groups deltas by target. Each parent table holds an offset to one
store; the store contains a region list plus one or more ItemVariationData subtables. Each
subtable is a matrix with one row (delta set) per item and one column per region it uses.

### Linking target items to delta sets

A delta set is addressed by a two-part delta-set index: an outer index that selects an
ItemVariationData subtable, and an inner index that selects a row in it. Parent tables
supply that index in different ways:

- MVAR: value records name a target by tag and give its outer and inner index (mvar.md).
- HVAR and VVAR: DeltaSetIndexMap subtables map glyph IDs to indices, or glyph IDs serve as
  implicit indices (hvar.md).
- COLR: a DeltaSetIndexMap as well; a variable structure gives a base index and uses that
  many consecutive map entries from there.
- BASE, GDEF, GPOS and JSTF: a VariationIndex table in the same subtable as the target item
  (chapter2.md, Device and VariationIndex tables).

### DeltaSetIndexMap

DeltaSetIndexMap format 0:

| Type | Name | Description |
|---|---|---|
| uint8 | format | 0 for this format. |
| uint8 | entryFormat | Packed description of how each map entry is stored (masks below). |
| uint16 | mapCount | Number of map entries (at most 65,535). |
| uint8 | mapData[variable] | The packed map entries. |

DeltaSetIndexMap format 1:

| Type | Name | Description |
|---|---|---|
| uint8 | format | 1 for this format. |
| uint8 | entryFormat | Packed description of how each map entry is stored (masks below). |
| uint32 | mapCount | Number of map entries, as a 32-bit count. |
| uint8 | mapData[variable] | The packed map entries. |

Older editions defined a single uint16 entryFormat field whose high byte was reserved and
zero. Splitting it into format and entryFormat keeps those maps valid: they read as format 0.

entryFormat masks:

| Mask | Name | Description |
|---|---|---|
| 0x0F | INNER_INDEX_BIT_COUNT_MASK | Low 4 bits: number of bits used for the inner index, minus 1. |
| 0x30 | MAP_ENTRY_SIZE_MASK | Bits 4-5: byte size of each entry, minus 1. |
| 0xC0 | Reserved | Reserved; must be 0. |

Logically both indices are 16-bit unsigned values. The packing lets the inner part use 1 to
16 bits and the outer part 0 to 31 bits, within an entry of 1 to 4 bytes. Size facts:
entrySize = ((entryFormat & MAP_ENTRY_SIZE_MASK) >> 4) + 1, and mapData occupies
entrySize * mapCount bytes.

Looking up map index i:

1. If i >= mapCount, use the last entry instead (i = mapCount - 1). The page does not cover
   an empty map.
2. innerBits = (entryFormat & 0x0F) + 1.
3. entrySize = ((entryFormat & 0x30) >> 4) + 1.
4. Read entry as a big-endian unsigned integer of entrySize bytes starting at
   mapData + i * entrySize.
5. outer index = entry >> innerBits.
6. inner index = entry & ((1 << innerBits) - 1).

### ItemVariationStore

| Type | Name | Description |
|---|---|---|
| uint16 | format | Store format; 1. |
| Offset32 | variationRegionListOffset | From the start of this ItemVariationStore to its VariationRegionList. |
| uint16 | itemVariationDataCount | Number of ItemVariationData subtables (entries in the offset array). |
| Offset32 | itemVariationDataOffsets[itemVariationDataCount] | From the start of this ItemVariationStore to each ItemVariationData subtable; NULL means no subtable at that position. |

Rules:

- The position in itemVariationDataOffsets is the outer index. When that offset is NULL, any
  inner index paired with it is invalid and can be ignored: the item does not vary.
- The delta-set index with outer = 0xFFFF and inner = 0xFFFF means "no variation data"; it
  behaves like a delta set of zeros for every region.
- One subtable suffices unless the number of distinct delta sets exceeds 65,536; further
  subtables are otherwise only a size optimization (dropping regions whose deltas are all
  zero for a group of rows, or grouping rows by which columns need wide deltas).

### VariationRegionList

| Type | Name | Description |
|---|---|---|
| uint16 | axisCount | Number of axes; must equal axisCount in 'fvar'. |
| uint16 | regionCount | Number of regions; must be below 32,768 (the top bit is reserved and must be clear). |
| VariationRegion | variationRegions[regionCount] | The regions, in any order. |

VariationRegion record:

| Type | Name | Description |
|---|---|---|
| RegionAxisCoordinates | regionAxes[axisCount] | One record per axis, in 'fvar' axis order. |

RegionAxisCoordinates record:

| Type | Name | Description |
|---|---|---|
| F2DOT14 | startCoord | Lower edge of the region on this axis. |
| F2DOT14 | peakCoord | Point on this axis where the axis factor reaches 1. |
| F2DOT14 | endCoord | Upper edge of the region on this axis. |

Constraints on each triple:

- All three lie within -1.0 to +1.0, and startCoord <= peakCoord <= endCoord.
- All three are non-positive or all are non-negative, with one exception: when peakCoord is 0,
  startCoord may be negative or 0 and endCoord positive or 0.

Conventions:

- Non-intermediate region on a participating axis: start = peak < 0 and end = 0 (typically
  -1, -1, 0), or start = 0 and peak = end > 0 (typically 0, +1, +1).
- Intermediate region on a participating axis: the three values share a sign (all <= 0 or all
  >= 0).
- Axis not participating: peakCoord = 0, with start <= 0 and end >= 0; preferably all three 0,
  or -1, 0, +1.

The per-axis factors of a region multiply into the region scalar (see Region scalars above).

### ItemVariationData

| Type | Name | Description |
|---|---|---|
| uint16 | itemCount | Number of delta-set rows in this subtable. |
| uint16 | wordDeltaCount | Packed field: LONG_WORDS flag in the top bit, number of long-type columns in the low 15 bits. |
| uint16 | regionIndexCount | Number of regions (columns) this subtable refers to. |
| uint16 | regionIndexes[regionIndexCount] | For each column, the index of its region in the VariationRegionList. |
| DeltaSet | deltaSets[itemCount] | The rows, one DeltaSet per item. |

wordDeltaCount masks:

| Mask | Name | Description |
|---|---|---|
| 0x8000 | LONG_WORDS | Set: long columns are int32 and short columns int16. Clear: long columns are int16 and short columns int8. |
| 0x7FFF | WORD_DELTA_COUNT_MASK | Number of columns stored with the long type. |

DeltaSet record:

| Type | Name | Description |
|---|---|---|
| int16 and int8 or int32 and int16 | deltaData[regionIndexCount] | One delta per column; the first wordCount values use the long type, the remaining ones the short type. |

Rules:

- wordCount = wordDeltaCount & WORD_DELTA_COUNT_MASK must not exceed regionIndexCount.
- LONG_WORDS is meant only for parent tables that have variable 32-bit values; at present that
  is only COLR.
- Row length in bytes: regionIndexCount + wordCount when LONG_WORDS is clear, and twice that
  when it is set. Row r starts at deltaSets + r x row length.
- Column j of every row belongs to region regionIndexes[j]; the column order within a subtable
  carries no meaning beyond that pairing.
- Deltas are stored as plain signed integers; there is no run-length packing here.

Applying deltas to different target types:

- Deltas are normally 16-bit signed integers applied to FWORD or UFWORD values.
- COLR can apply scaled deltas to F2DOT14 targets: treat the target as an integer count of
  1/16384 units. If the context limits the valid range (for example 0 to 1), clamp the varied
  result to that range.
- COLR can also vary Fixed (16.16) targets: treat the target as an integer count of 1/65536
  units. Such targets generally need 32-bit deltas, hence LONG_WORDS.

### Applying an item variation store

1. Get the delta-set index (outer, inner) for the target from the parent table.
2. If it is (0xFFFF, 0xFFFF), the item does not vary; stop.
3. Use the outer index to pick itemVariationDataOffsets[outer]; a NULL offset means the item
   does not vary.
4. Use the inner index to pick row deltaSets[inner] of that subtable.
5. For each column j, compute the scalar of region regionIndexes[j] for the current instance
   and multiply it by the row's delta j.
6. Sum the products; the instance value is the default value plus that sum.

Region scalars depend only on the instance, so a reader can compute one scalar per entry of
the VariationRegionList once per instance and reuse the array for every item. This page gives
no rule for an outer index at or past itemVariationDataCount, an inner index at or past
itemCount, or a region index at or past regionCount.
