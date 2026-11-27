# gvar - Glyph Variations Table
Source: gvar - Glyph Variations Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/gvar
These notes restate the source's structures and rules; where they differ, the source governs.

## Role

- 'gvar' carries every variation of TrueType outlines stored in 'glyf': for each glyph,
  deltas for its outline points (or, in a composite glyph, its component offsets) and for its
  four phantom points.
- It is usable only together with 'glyf' outlines, an 'fvar' table and the other tables a
  variable font needs.
- The data for each glyph is a GlyphVariationData table, which is one variant of the tuple
  variation store. Its header flags, TupleVariationHeader records, serialized data, packed
  point numbers and packed deltas are defined in otvarcommonformats.md, which also lists the
  differences from 'cvar'.
- Metrics can be read from the varied phantom points, but that requires processing the whole
  outline. HVAR (hvar.md), and VVAR when the font has 'vhea' and 'vmtx', give per-glyph metric
  variations without outline work and are recommended for that reason.

## Table layout

The table holds a header, then an array of shared tuple records, then the array of
GlyphVariationData tables. The header ends with an offset array that has one entry per glyph
ID plus one extra entry; consecutive entries bound each glyph's data, as 'loca' does for
'glyf'.

### 'gvar' header

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; 1. |
| uint16 | minorVersion | Minor version; 0. |
| uint16 | axisCount | Number of axes; must equal axisCount in 'fvar'. |
| uint16 | sharedTupleCount | Number of Tuple records in the shared array; any glyph's data may point at them. |
| Offset32 | sharedTuplesOffset | From the start of 'gvar' to the shared tuple array. |
| uint16 | glyphCount | Number of glyphs; must agree with the glyph count recorded elsewhere in the font. |
| uint16 | flags | Bit 0 chooses the element size of the offset array below. |
| Offset32 | glyphVariationDataArrayOffset | From the start of 'gvar' to the first GlyphVariationData table (start of the array). |
| Offset16 or Offset32 | glyphVariationDataOffsets[glyphCount + 1] | For each glyph ID, where its GlyphVariationData begins, relative to the start of the GlyphVariationData array; the extra last entry closes the final table. |

flags field:

| Bit (mask) | State | Offset array encoding |
|---|---|---|
| 0 (0x0001) | clear | Offset16 elements that store the real offset divided by 2; multiply each stored value by 2. |
| 0 (0x0001) | set | Offset32 elements that store the real offset unchanged. |

No other flag bit is defined on this page. With short offsets every GlyphVariationData must
begin at an even distance from the start of the array, since only halved values are stored.

Finding the data of glyph g:

1. base = start of 'gvar' + glyphVariationDataArrayOffset.
2. Read elements g and g + 1 of glyphVariationDataOffsets: uint16 values times 2 when bit 0 of
   flags is clear, uint32 values as they are when it is set.
3. The glyph's GlyphVariationData occupies bytes base + element g up to (not including)
   base + element g+1.
4. A zero-length range means the glyph has no variation data (see Glyphs without data).

### Shared tuples

| Type | Name | Description |
|---|---|---|
| Tuple | sharedTuples[sharedTupleCount] | Peak positions that the data of any glyph may reference; each record is axisCount F2DOT14 values. |

- The array starts at sharedTuplesOffset; the page places it right after the offset array.
- A TupleVariationHeader whose EMBEDDED_PEAK_TUPLE flag is clear takes its peak from
  sharedTuples[tupleIndex & 0x0FFF] (TUPLE_INDEX_MASK).
- Shared and embedded tuples alike hold normalized coordinates as F2DOT14 (2.14) values.
- Shared tuples supply peaks only; the start and end tuples of an intermediate region are
  always embedded in the header.

### GlyphVariationData

| Type | Name | Description |
|---|---|---|
| uint16 | tupleVariationCount | Packed field: flags in the top 4 bits, number of tuple variation tables for this glyph in the low 12 bits (1 to 4095). |
| Offset16 | dataOffset | From the start of this GlyphVariationData table to its serialized data. |
| TupleVariationHeader | tupleVariationHeaders[tupleCount] | The tuple variation headers; tupleCount is the low 12 bits of tupleVariationCount. |

This page names the array size tupleCount; otvarcommonformats.md names it
tupleVariationCount. Both mean tupleVariationCount & COUNT_MASK.

The serialized data holds the packed point numbers and the deltas. A shared point list may
open it (used by every tuple variation table without private numbers), and each table may
carry private point numbers ahead of its deltas. In a composite glyph the numbers name
components instead of outline points.

## Processing a glyph

1. Take the default outline from 'glyf' and set up its phantom points (Point numbering).
2. Find the glyph's GlyphVariationData. If it is empty, the glyph has no deltas of its own.
3. For each TupleVariationHeader, assemble the region (peak from the embedded or shared
   tuple, plus start and end when INTERMEDIATE_REGION is set) and compute its scalar from the
   normalized instance coordinates (otvarcommonformats.md, Region scalars). Skip tables whose
   scalar is 0.
4. For each remaining table, decode its point numbers (private, else shared) and its 2 x n
   deltas: n X deltas, then n Y deltas.
5. Simple glyph: for contours that the list covers only partly, infer the missing deltas
   (Inferred deltas). Composite glyph: no inference; follow Composite glyphs.
6. Add scalar x X delta to the point's X coordinate and scalar x Y delta to its Y coordinate.
7. The tables may be applied in any order; their effects add up.

## Point numbering

Simple glyph with N outline points (numbered across all contours as in glyf.md):

| Point number | Meaning |
|---|---|
| 0 to N-1 | outline points |
| N | left side bearing point (horizontal origin, pp1) |
| N+1 | right side bearing point (advance width point, pp2) |
| N+2 | top side bearing point (vertical origin) |
| N+3 | bottom side bearing point (advance height point) |

Composite glyph with C components: numbers 0 to C-1 are pseudo-points, one per component, in
the order the components appear in the composite description; numbers C to C+3 are the same
four phantom points in the same order. For a composite made of a base letter followed by an
accent (the page uses U+00E9 LATIN SMALL LETTER E WITH ACUTE):

| Point number | Element |
|---|---|
| 0 | Base glyph |
| 1 | Accent glyph |
| 2 | Left side bearing point |
| 3 | Right side bearing point |
| 4 | Top side bearing point |
| 5 | Bottom side bearing point |

The packed point list of a tuple variation table may name any subset of these numbers.

Phantom points:

- The last four numbers of every glyph, simple or composite, are the phantom points that the
  TrueType rasterizer adds to stand for the side bearings and advances.
- Horizontal start positions: pp1.x = xMin - lsb and pp2.x = pp1.x + advance width, both on
  y = 0 (hmtx.md, head.md). A variable font with TrueType outlines must set bit 1 of the 'head'
  flags (lsb = xMin), so pp1 starts at x = 0. In the page's example, advance 1358
  and lsb = xMin = 16 put the two points at (0, 0) and (1358, 0).
- Vertical start positions are not given on this page.
- After variation: advance width = pp2.x - pp1.x, left side bearing = xMin - pp1.x (xMin of the
  varied outline), advance height = top y - bottom y.
- In a simple glyph, deltas for phantom points are applied like those of any other point.
  Phantom points belong to no contour, so they never receive inferred deltas: a table whose
  list omits them leaves them in place.
- In a composite glyph, the X delta applies only to the left side bearing and advance width
  points and the Y delta only to the top side bearing and advance height points (step 2
  below).

## Composite glyphs

Rules:

- A delta pair for component index p moves that component's placement. A component missing
  from a table's point list is not moved by that table.
- Every component glyph has its own glyph entry and its own GlyphVariationData. Build
  components from the bottom up: the most deeply nested simple glyphs first.
- Deltas take effect only for components placed by offsets, that is with ARGS_ARE_XY_VALUES
  (bit 1, mask 0x0002; glyf.md) set. For components placed by matching points (flag clear),
  deltas have no effect and fonts should not provide any.
- Deltas never alter a component's scale or 2x2 transformation; they move its offset only.
  When the offset itself is scaled, the delta-adjusted offset is the one that gets scaled.
- USE_MY_METRICS (bit 9, mask 0x0200; glyf.md): the composite's phantom points are set to the component's
  phantom points after that component's variations and hinting, and the composite's own
  phantom-point deltas are not used. If several components carry the flag, the last one wins.
- With USE_MY_METRICS, the composite's 'hmtx' and HVAR entries are still read as they would be
  in a non-variable font and should hold fitting values; the hinted phantom points may not
  match the linearly varied 'hmtx' plus HVAR metrics exactly.

Steps:

1. Process the composite's own variation data with the normal algorithm, giving net (dx, dy)
   for each component index 0 to C-1 and each phantom point C to C+3.
2. Phantom points: add dx to the left side bearing and advance width points and ignore their
   dy; add dy to the top side bearing and advance height points and ignore their dx. Step
   3.5 may later replace these.
3. For each component p from 0 to C-1:
   1. Build the component glyph completely: apply its own variation data (recursively for
      nested composites) and run its hinting program.
   2. ARGS_ARE_XY_VALUES set: the placement offset becomes (argument1 + dx[p],
      argument2 + dy[p]).
   3. ARGS_ARE_XY_VALUES clear: ignore dx[p] and dy[p].
   4. Apply the component's scale or matrix as usual, using the adjusted offset wherever the
      offset is scaled.
   5. USE_MY_METRICS set: copy the component's varied, hinted phantom points over the
      composite's.

### Worked example from the page

Glyph 128 of the Skia font (U+00C4 LATIN CAPITAL LETTER A WITH DIAERESIS) has two components,
both placed with ARGS_ARE_XY_VALUES: component 0 is glyph 65 at offset (0, 0) and component 1
is glyph 315 at offset (286, 0). Its advance is 1358 and lsb = xMin = 16, so point 2 (left side
bearing) starts at (0, 0) and point 3 (right side bearing) at (1358, 0). Three of its regions,
as (weight, width) peaks, and their scalars at the instance (0.2, 0.7):

| Region | Peak | Scalar at (0.2, 0.7) | X deltas for points 0, 1, 2, 3 |
|---|---|---|---|
| R1 | (1,0) | 0.2 | 0, 69, 58, 145 |
| R2 | (0,1) | 0.7 | 0, 53, 38, 351 |
| R3 | (1,1) | 0.14 | 0, -8, -30, none (point 3 is not listed) |

Every Y delta is 0, so no Y coordinate moves. R3 lists no delta for point 3 and a composite
gets no inferred deltas, so R3 adds nothing there.

| Item | Net X adjustment as printed | Resulting position |
|---|---|---|
| Component 1 X offset | 0.2 x 69 + 0.7 x 53 + 0.14 x -8 = 49.78 | Component 1 (X, Y) offset: (286 + 49.78, 0) = (335.78, 0) |
| Left side bearing point X coordinate | 0.2 x 58 + 0.7 x 38 + 0.14 x 30 = 42.4 | Left side bearing phantom point: (0 + 42.4, 0) = (42.4, 0) |
| Right side bearing point X coordinate | 0.2 x 145 + 0.7 x 351 + 0.14 x 0 = 274.7 | Right side bearing phantom point: (1358 + 274.7, 0) = (1632.7, 0) |

Component 0 keeps offset (0, 0). The page's left side bearing sum uses +30 for R3 although
its R3 delta for point 2 is -30; with -30 the sum is 34.0 and the point ends at (34.0, 0).

## Inferred deltas for unlisted points

Scope and properties:

- Only simple glyphs get inferred deltas; composite glyphs never do.
- Inference runs per glyph, per tuple variation table (region), per contour, from that
  table's own point list.
- One point list serves both directions: a point has explicit X and Y deltas, or both of its
  deltas are inferred. The two directions are computed separately but use the same
  neighbouring points.
- Inputs are the default 'glyf' coordinates and the table's unscaled deltas. The result does
  not depend on the instance or on the order in which tables are handled, so it can be
  computed ahead of time. The region scalar is applied afterwards, exactly as for explicit
  deltas.
- The idea resembles the TrueType IUP instruction, but IUP works from current (already moved)
  positions, while this works from default positions, and the arithmetic differs slightly.

Steps for one table and one contour:

1. If the table's point list is "all points", there is nothing to infer.
2. Let L be the listed points that belong to the contour. If L is empty, no point of the
   contour moves for this table. If L is the whole contour, there is nothing to infer.
3. For each unlisted point t of the contour:
   1. a = the listed point of the contour with the highest number below t; if there is none,
      the listed point with the highest number in the contour (wrap around).
   2. b = the listed point of the contour with the lowest number above t; if there is none,
      the listed point with the lowest number in the contour (wrap around).
   3. Compute the X delta of t from the X coordinates and X deltas of a and b, and the Y delta
      from their Y coordinates and Y deltas, using the rule below.

One-direction rule (c = coordinate in that direction, d = unscaled delta):

```
infer(ca, da, cb, db, ct):
    if ca == cb:
        if da == db: return da
        return 0
    # order the two neighbours by coordinate
    if ca < cb: (lo_c, lo_d, hi_c, hi_d) = (ca, da, cb, db)
    else:       (lo_c, lo_d, hi_c, hi_d) = (cb, db, ca, da)
    if ct <= lo_c: return lo_d          # at or beyond the low side: copy that neighbour
    if ct >= hi_c: return hi_d          # at or beyond the high side: copy that neighbour
    p = (ct - lo_c) / (hi_c - lo_c)     # strictly between: linear interpolation
    return lo_d + p * (hi_d - lo_d)
```

The page states the interpolation with either neighbour as the reference point r and the
other as the comparison point s: proportion = (targetCoord - refCoord) / (compCoord - refCoord)
and deltaTarget = (1 - proportion) x deltaRef + proportion x deltaComp. Both choices give the
same value. The interpolation branch is only reached when the two coordinates differ, so it
never divides by zero.

Consequence: when a contour has exactly one listed point, that point is both neighbours of
every other point, so the whole contour takes its X and Y deltas.

Example from the page: P1, P2 and P3 lie on one contour; P1 and P3 are listed, P2 is not. In X,
P2 lies between them; with P1 as reference, proportion = (260 - 245) / (305 - 245) = 0.25 (the
figure caption prints 246 in the denominator, but the page continues with 0.25). In Y, P2 lies
outside the span of P1 and P3, and P3 is the nearer one.

| Point | X delta | Y delta |
|---|---|---|
| P1 | +28 | -62 |
| P2 | +10.5, inferred: (1 - 0.25) x 28 + 0.25 x -42 | -57, inferred: copied from P3 |
| P3 | -42 | -57 |

## Glyphs without data

- When glyphVariationDataOffsets[g] equals glyphVariationDataOffsets[g + 1], glyph g has no
  GlyphVariationData: its own outline points, component offsets and phantom points receive no
  deltas, and a simple glyph keeps the same outline over the whole variation space.
- A composite glyph without data of its own is still assembled from components that are each
  varied through their own data (Composite glyphs, step 3.1).
- Within a glyph that does have data, an unlisted component is not moved by that table, an
  unlisted phantom point is not moved by that table, and an untouched contour (no listed
  point) is not moved by that table.
