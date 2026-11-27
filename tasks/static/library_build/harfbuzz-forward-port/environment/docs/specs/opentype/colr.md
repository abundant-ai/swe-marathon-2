# COLR - Color Table
Source: COLR - Color Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/colr
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope

- COLR attaches a color presentation (informally a "color glyph") to a glyph ID (the "base glyph"). The color glyph is a composition built from other glyphs' outlines and from CPAL colors.
- COLR is applied to the glyph IDs produced by text layout (after substitution and positioning), just before the glyphs are drawn. It does not change shaping.
- Version 0: for each base glyph, a bottom-to-top stack of layers. Each layer is one glyph outline (from 'glyf', 'CFF ' or CFF2) filled with one solid palette color. Layers combine by plain alpha blending only.
- Version 1: adds a graph of Paint tables: solid fills, linear, radial and sweep gradients, glyph-outline clipping, affine transforms, reusable layer slices, reusable color glyphs, and other compositing and blend modes.
- Variable fonts: with version 0 data only the outlines vary. With version 1 data the outlines vary and so can alpha values, color stop offsets, gradient geometry, transform parameters (matrix elements, angles, scale factors, centers) and clip boxes.
- Every color comes from a CPAL palette (see cpal.md). If a font has COLR but no CPAL, ignore COLR.
- Applications should not apply synthetic bold or synthetic italic/oblique emulation (meant for ordinary, non-color glyphs) to color glyphs; it can badly distort them.

## Data types

| Type | Bytes | Encoding |
|---|---|---|
| uint8, uint16, uint32 | 1, 2, 4 | Unsigned big-endian integers |
| Offset24, Offset32 | 3, 4 | Unsigned byte offsets; 0 is NULL (no table) |
| FWORD | 2 | int16 in font design units |
| UFWORD | 2 | uint16 in font design units |
| F2DOT14 | 2 | Signed 2.14 fixed point: value = (int16) raw / 16384; range -2.0 to 1.99993896484375 |
| Fixed | 4 | Signed 16.16 fixed point: value = (int32) raw / 65536 |

See otff.md (data types) for the general definitions.

## COLR header

Every header offset counts from the first byte of the COLR table. NULL (0) means the structure is absent.

### Version 0 header (14 bytes)

| Type | Name | Description |
|---|---|---|
| uint16 | version | Header version: 0 |
| uint16 | numBaseGlyphRecords | Count of BaseGlyph records |
| Offset32 | baseGlyphRecordsOffset | Start of the BaseGlyph record array, from start of COLR |
| Offset32 | layerRecordsOffset | Start of the Layer record array, from start of COLR |
| uint16 | numLayerRecords | Count of Layer records |

### Version 1 header (34 bytes)

| Type | Name | Description |
|---|---|---|
| uint16 | version | Header version: 1 |
| uint16 | numBaseGlyphRecords | Count of BaseGlyph records; 0 allowed |
| Offset32 | baseGlyphRecordsOffset | BaseGlyph record array, from start of COLR; NULL allowed |
| Offset32 | layerRecordsOffset | Layer record array, from start of COLR; NULL allowed |
| uint16 | numLayerRecords | Count of Layer records; 0 allowed |
| Offset32 | baseGlyphListOffset | BaseGlyphList table, from start of COLR |
| Offset32 | layerListOffset | LayerList table, from start of COLR; NULL allowed |
| Offset32 | clipListOffset | ClipList table, from start of COLR; NULL allowed |
| Offset32 | varIndexMapOffset | DeltaSetIndexMap table, from start of COLR; NULL allowed |
| Offset32 | itemVariationStoreOffset | ItemVariationStore table, from start of COLR; NULL allowed |

Header rules:

- The first five fields have the same layout in both versions, so a reader that knows only version 0 can still use the version 0 records of a version 1 table.
- The BaseGlyphList and everything reached from it exist only in version 1. Unlike the other version 1 offsets, baseGlyphListOffset is not described as nullable in the source.
- layerListOffset is NULL when no glyph uses a PaintColrLayers table; the LayerList serves only PaintColrLayers.
- clipListOffset is NULL when no clip boxes are given; the ClipList applies only to BaseGlyphList color glyphs.
- itemVariationStoreOffset is non-NULL only in variable fonts; the store serves the BaseGlyphList and its subtables.
- The DeltaSetIndexMap may use format 0 or format 1 (see otvarcommonformats.md, DeltaSetIndexMap). It is optional even when an ItemVariationStore exists; without it an implicit mapping applies (see "Variation data").
- Later minor versions may add new Paint formats; see "Error recovery" for unknown formats.

### Choosing version 0 or version 1 data for a glyph

1. A version 1 table may also carry version 0 BaseGlyph and Layer records, so applications limited to version 0 still get color glyphs.
2. Within one font, some base glyphs may be described only by version 0 records and others only by the BaseGlyphList. One glyph may even have a version 0 definition and a different version 1 definition.
3. An application that supports version 1 searches the BaseGlyphList first. Only if the glyph is not found there does it search the version 0 BaseGlyph records (when present). The version 1 definition therefore wins.
4. An application limited to version 0 reads only the BaseGlyph and Layer records.

## Version 0 records

BaseGlyph record (6 bytes; numBaseGlyphRecords of them at baseGlyphRecordsOffset):

| Type | Name | Description |
|---|---|---|
| uint16 | glyphID | The base glyph this record describes |
| uint16 | firstLayerIndex | Zero-based index of its first Layer record |
| uint16 | numLayers | How many consecutive Layer records form the color glyph |

Layer record (4 bytes; numLayerRecords of them at layerRecordsOffset):

| Type | Name | Description |
|---|---|---|
| uint16 | glyphID | Glyph whose outline is the shape of this layer |
| uint16 | paletteIndex | Zero-based CPAL palette entry used as the fill; 0xFFFF selects the foreground color |

Rules:

- Every glyphID (in either record) is less than numGlyphs in 'maxp'. A Layer record's glyph must have outline data in 'glyf', 'CFF ' or CFF2.
- BaseGlyph records are in ascending glyphID order; locate a glyph by binary search.
- The color glyph uses Layer records firstLayerIndex through firstLayerIndex + numLayers - 1. The first of them is the lowest layer; each later one is drawn above those before it.
- Different base glyphs may use overlapping runs of Layer records.
- paletteIndex is below CPAL numPaletteEntries, or is 0xFFFF, meaning the text foreground color chosen by the application.

### Rendering a version 0 color glyph

1. Find the base glyph by binary search over the BaseGlyph records (a version 1 reader does this only after the BaseGlyphList lookup fails).
2. For each Layer record of the run, from the first (bottom) to the last (top):
   1. Resolve the color: 0xFFFF gives the application's foreground color; any other value gives entry paletteIndex of the active CPAL palette (see cpal.md), including that entry's alpha.
   2. Fill the layer glyph's outline with that color at the base glyph's position and blend it over what is already drawn with ordinary source-over alpha compositing.
3. Advances and metrics come from the base glyph (see "Glyph metrics").

## Version 1 lists

### BaseGlyphList

| Type | Name | Description |
|---|---|---|
| uint32 | numBaseGlyphPaintRecords | Count of records that follow |
| BaseGlyphPaintRecord | baseGlyphPaintRecords[numBaseGlyphPaintRecords] | One record per base glyph, in ascending glyphID order |

BaseGlyphPaintRecord (6 bytes):

| Type | Name | Description |
|---|---|---|
| uint16 | glyphID | The base glyph |
| Offset32 | paintOffset | Root Paint table of its color glyph, counted from the start of the BaseGlyphList (not from the record) |

Rules:

- glyphID is below numGlyphs in 'maxp'. Records are sorted by ascending glyphID so that binary search works.
- The referenced Paint table is the root of the glyph's paint graph. It is often a PaintColrLayers table, but any format may be the root.

### LayerList

| Type | Name | Description |
|---|---|---|
| uint32 | numLayers | Count of paint offsets |
| Offset32 | paintOffsets[numLayers] | Paint tables, each offset counted from the start of the LayerList |

Rules:

- A single LayerList serves every PaintColrLayers table; each PaintColrLayers selects a contiguous run (slice) of it.
- Inside a slice the order is bottom to top: the first entry's sub-graph is lowest and each later entry is drawn above. When an entry's sub-graph itself holds several layers, all of them sit above the earlier entries and below the later ones.
- Paints that no PaintColrLayers reaches should not be listed.

### ClipList and clip boxes

ClipList:

| Type | Name | Description |
|---|---|---|
| uint8 | format | ClipList format: 1 |
| uint32 | numClips | Count of Clip records |
| Clip | clips[numClips] | Clip records, ordered by startGlyphID |

Clip record (7 bytes):

| Type | Name | Description |
|---|---|---|
| uint16 | startGlyphID | Lowest glyph ID of the range (inclusive) |
| uint16 | endGlyphID | Highest glyph ID of the range (inclusive) |
| Offset24 | clipBoxOffset | ClipBox table for every glyph of the range, counted from the start of the ClipList |

ClipBoxFormat1, fixed box (9 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | ClipBox format: 1 |
| FWORD | xMin | Left edge |
| FWORD | yMin | Bottom edge |
| FWORD | xMax | Right edge |
| FWORD | yMax | Top edge |

ClipBoxFormat2, variable box (13 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | ClipBox format: 2 |
| FWORD | xMin | Left edge (var +0) |
| FWORD | yMin | Bottom edge (var +1) |
| FWORD | xMax | Right edge (var +2) |
| FWORD | yMax | Top edge (var +3) |
| uint32 | varIndexBase | First variation index of this box (see "Variation data") |

In any description, "var +k" means the field's variation index is varIndexBase + k.

Rules:

- Glyph ranges of Clip records never overlap; with the records sorted by startGlyphID, binary search finds the range that holds a glyph.
- Clip boxes are optional; any color glyph may lack one.
- Nothing outside the clip box may be drawn.
- The box need not be tight, but implementations may size drawing buffers from it, so it should not be oversized.
- For a format 2 box, compute the varied edges in floating point, then round outward: xMin and yMin toward negative infinity, xMax and yMax toward positive infinity.
- In a variable font the box is meant to enclose the glyph at every instance, either by being large enough for all of them or by varying with them.

## Color references, color stops and color lines

Color references in version 1 (PaintSolid, PaintVarSolid, ColorStop, VarColorStop):

- paletteIndex is a zero-based entry of the palette the application selected. 0xFFFF means the application's text foreground color and is never used as an index into the CPAL color records.
- alpha is an F2DOT14 multiplier that is always present. Clamp it to [0.0, 1.0] (values outside are reserved), after applying any variation delta. 0 is fully transparent, 1 fully opaque.
- Effective alpha = clamped COLR alpha * (CPAL alpha / 255). For 0xFFFF it is the clamped COLR alpha times the foreground color's alpha.
- Keeping alpha separate from the palette entry lets transparency be defined independently of which palette is chosen, lets several elements share one entry at different opacities, and lets alpha vary in a variable font. Version 0 Layer records have no such field; their opacity is the CPAL entry's alpha alone.
- Any opacity the application applies at a higher level is combined with this result; it is not replaced by it.

ColorStop record (6 bytes):

| Type | Name | Description |
|---|---|---|
| F2DOT14 | stopOffset | Position of this stop on the color line |
| uint16 | paletteIndex | CPAL entry (0xFFFF = foreground color) |
| F2DOT14 | alpha | Alpha multiplier for this stop |

VarColorStop record (10 bytes):

| Type | Name | Description |
|---|---|---|
| F2DOT14 | stopOffset | Position of this stop on the color line (var +0) |
| uint16 | paletteIndex | CPAL entry (0xFFFF = foreground color); not variable |
| F2DOT14 | alpha | Alpha multiplier for this stop (var +1) |
| uint32 | varIndexBase | First variation index of this stop |

ColorLine table (3 + 6 * numStops bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | extend | Extend mode, a value of the Extend enumeration |
| uint16 | numStops | Count of stops |
| ColorStop | colorStops[numStops] | The stops, in any order |

VarColorLine table (3 + 10 * numStops bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | extend | Extend mode, a value of the Extend enumeration |
| uint16 | numStops | Count of stops |
| VarColorStop | colorStops[numStops] | The stops, each carrying its own varIndexBase |

The VarColorLine itself has no varIndexBase; only its stops vary.

Extend enumeration (the same mode applies in both directions along the line):

| Value | Name | Description |
|---|---|---|
| 0 | EXTEND_PAD | Outside the stops, keep the color of the closest end stop |
| 1 | EXTEND_REPEAT | Tile the stop interval end to end |
| 2 | EXTEND_REFLECT | Tile the stop interval, mirroring every second copy |

Treat an unrecognized extend value as EXTEND_PAD. The color line evaluation rules are under "Processing rules".

## Paint tables

Every Paint table begins with a uint8 format (1 to 32); read it first and dispatch on it. Every Offset24 inside a Paint table (child paints, color lines, transforms) counts from the first byte of that Paint table. These are unsigned forward offsets, so a shared child always lies later in the table than every Paint that points to it.

The Var formats (3, 5, 7, 9, 13, 15, 17, 19, 21, 23, 25, 27, 29 and 31) are variable twins of the format numbered one lower. They must not be used in a non-variable font, nor in a COLR table without an ItemVariationStore.

Summary (Size is the fixed size in bytes; variable fields are listed in index order, base+0 first):

| Format | Table | Size | Children | Variable fields |
|---|---|---|---|---|
| 1 | PaintColrLayers | 6 | numLayers LayerList entries | none |
| 2 | PaintSolid | 5 | none (leaf) | none |
| 3 | PaintVarSolid | 9 | none (leaf) | alpha |
| 4 | PaintLinearGradient | 16 | none (leaf); has a ColorLine | none |
| 5 | PaintVarLinearGradient | 20 | none (leaf); has a VarColorLine | x0, y0, x1, y1, x2, y2 |
| 6 | PaintRadialGradient | 16 | none (leaf); has a ColorLine | none |
| 7 | PaintVarRadialGradient | 20 | none (leaf); has a VarColorLine | x0, y0, radius0, x1, y1, radius1 |
| 8 | PaintSweepGradient | 12 | none (leaf); has a ColorLine | none |
| 9 | PaintVarSweepGradient | 16 | none (leaf); has a VarColorLine | centerX, centerY, startAngle, endAngle |
| 10 | PaintGlyph | 6 | 1 (paintOffset) | none |
| 11 | PaintColrGlyph | 3 | 1 (root paint of another base glyph) | none |
| 12 | PaintTransform | 7 | 1 (paintOffset); has an Affine2x3 | none |
| 13 | PaintVarTransform | 7 | 1 (paintOffset); has a VarAffine2x3 | xx, yx, xy, yy, dx, dy (in the VarAffine2x3) |
| 14 | PaintTranslate | 8 | 1 | none |
| 15 | PaintVarTranslate | 12 | 1 | dx, dy |
| 16 | PaintScale | 8 | 1 | none |
| 17 | PaintVarScale | 12 | 1 | scaleX, scaleY |
| 18 | PaintScaleAroundCenter | 12 | 1 | none |
| 19 | PaintVarScaleAroundCenter | 16 | 1 | scaleX, scaleY, centerX, centerY |
| 20 | PaintScaleUniform | 6 | 1 | none |
| 21 | PaintVarScaleUniform | 10 | 1 | scale |
| 22 | PaintScaleUniformAroundCenter | 10 | 1 | none |
| 23 | PaintVarScaleUniformAroundCenter | 14 | 1 | scale, centerX, centerY |
| 24 | PaintRotate | 6 | 1 | none |
| 25 | PaintVarRotate | 10 | 1 | angle |
| 26 | PaintRotateAroundCenter | 10 | 1 | none |
| 27 | PaintVarRotateAroundCenter | 14 | 1 | angle, centerX, centerY |
| 28 | PaintSkew | 8 | 1 | none |
| 29 | PaintVarSkew | 12 | 1 | xSkewAngle, ySkewAngle |
| 30 | PaintSkewAroundCenter | 12 | 1 | none |
| 31 | PaintVarSkewAroundCenter | 16 | 1 | xSkewAngle, ySkewAngle, centerX, centerY |
| 32 | PaintComposite | 8 | 2 (source, backdrop) | none |

### Format 1: PaintColrLayers

PaintColrLayers table (format 1, 6 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 1 |
| uint8 | numLayers | Length of the LayerList slice |
| uint32 | firstLayerIndex | Zero-based LayerList index of the slice's first (bottom) entry |

- The layers are LayerList entries firstLayerIndex to firstLayerIndex + numLayers - 1, drawn bottom to top; each one is composited onto the result so far with COMPOSITE_SRC_OVER.
- A LayerList must exist and the slice must lie inside it; otherwise this node is not well-formed.
- numLayers has only 8 bits; bigger stacks are built by combining several PaintColrLayers under another PaintColrLayers or a PaintComposite.
- A PaintColrLayers may be a glyph's root or may sit anywhere deeper in a graph, which lets one run of LayerList entries be shared by many glyphs.

### Formats 2 and 3: PaintSolid, PaintVarSolid

PaintSolid table (format 2, 5 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 2 |
| uint16 | paletteIndex | CPAL entry (0xFFFF = foreground color) |
| F2DOT14 | alpha | Alpha multiplier |

PaintVarSolid table (format 3, 9 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 3 |
| uint16 | paletteIndex | CPAL entry (0xFFFF = foreground color) |
| F2DOT14 | alpha | Alpha multiplier (var +0) |
| uint32 | varIndexBase | First variation index |

A solid paint covers everything inside the current clip with one color; on its own it is unbounded.

### Formats 4 and 5: PaintLinearGradient, PaintVarLinearGradient

PaintLinearGradient table (format 4, 16 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 4 |
| Offset24 | colorLineOffset | ColorLine, from start of this Paint table |
| FWORD | x0 | p0 x; stop offset 0 lies at p0 |
| FWORD | y0 | p0 y |
| FWORD | x1 | p1 x; stop offset 1 lies at p1 |
| FWORD | y1 | p1 y |
| FWORD | x2 | p2 x; p2 is the rotation point |
| FWORD | y2 | p2 y |

PaintVarLinearGradient table (format 5, 20 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 5 |
| Offset24 | colorLineOffset | VarColorLine, from start of this Paint table |
| FWORD | x0 | p0 x (var +0) |
| FWORD | y0 | p0 y (var +1) |
| FWORD | x1 | p1 x (var +2) |
| FWORD | y1 | p1 y (var +3) |
| FWORD | x2 | p2 x (var +4) |
| FWORD | y2 | p2 y (var +5) |
| uint32 | varIndexBase | First variation index |

Geometry rules: see "Linear gradients" under "Processing rules".

### Formats 6 and 7: PaintRadialGradient, PaintVarRadialGradient

PaintRadialGradient table (format 6, 16 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 6 |
| Offset24 | colorLineOffset | ColorLine, from start of this Paint table |
| FWORD | x0 | Circle 0 center x; stop offset 0 lies on circle 0 |
| FWORD | y0 | Circle 0 center y |
| UFWORD | radius0 | Circle 0 radius |
| FWORD | x1 | Circle 1 center x; stop offset 1 lies on circle 1 |
| FWORD | y1 | Circle 1 center y |
| UFWORD | radius1 | Circle 1 radius |

PaintVarRadialGradient table (format 7, 20 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 7 |
| Offset24 | colorLineOffset | VarColorLine, from start of this Paint table |
| FWORD | x0 | Circle 0 center x (var +0) |
| FWORD | y0 | Circle 0 center y (var +1) |
| UFWORD | radius0 | Circle 0 radius (var +2) |
| FWORD | x1 | Circle 1 center x (var +3) |
| FWORD | y1 | Circle 1 center y (var +4) |
| UFWORD | radius1 | Circle 1 radius (var +5) |
| uint32 | varIndexBase | First variation index |

Radii are stored unsigned, but variation deltas can make them negative; see "Radial gradients".

### Formats 8 and 9: PaintSweepGradient, PaintVarSweepGradient

PaintSweepGradient table (format 8, 12 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 8 |
| Offset24 | colorLineOffset | ColorLine, from start of this Paint table |
| FWORD | centerX | Sweep center x |
| FWORD | centerY | Sweep center y |
| F2DOT14 | startAngle | Angle of stop offset 0: degrees = (value + 1.0) * 180, counter-clockwise |
| F2DOT14 | endAngle | Angle of stop offset 1: degrees = (value + 1.0) * 180, counter-clockwise |

PaintVarSweepGradient table (format 9, 16 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 9 |
| Offset24 | colorLineOffset | VarColorLine, from start of this Paint table |
| FWORD | centerX | Sweep center x (var +0) |
| FWORD | centerY | Sweep center y (var +1) |
| F2DOT14 | startAngle | Angle of stop offset 0, biased as in format 8 (var +2) |
| F2DOT14 | endAngle | Angle of stop offset 1, biased as in format 8 (var +3) |
| uint32 | varIndexBase | First variation index |

Angles count counter-clockwise from the positive x axis of the design grid. The bias of 1.0 exists so that +360 degrees is representable: raw 0x8000 (-2.0) is -180 degrees, 0x0000 (0.0) is 180, 0x1000 (0.25) is 225 and 0x4000 (1.0) is 360. Unvaried values thus span [-180, 540) degrees. Only sweep gradient angles carry this bias; rotation and skew angles do not.

### Format 10: PaintGlyph

PaintGlyph table (format 10, 6 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 10 |
| Offset24 | paintOffset | Child Paint (the fill), from start of this Paint table |
| uint16 | glyphID | Glyph whose outline is the shape (clip region) |

- glyphID is below numGlyphs in 'maxp' and must have an outline in 'glyf', 'CFF ' or CFF2. Only that outline is used. If the same glyph ID also has COLR data (a BaseGlyph record or a BaseGlyphList entry), that data plays no part here.
- The outline itself is never drawn. It restricts the painting of the child sub-graph to the inside of the outline; nested PaintGlyph tables intersect their clip regions.
- A PaintGlyph must have a child; without one the graph is not well-formed.

### Format 11: PaintColrGlyph

PaintColrGlyph table (format 11, 3 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 11 |
| uint16 | glyphID | Base glyph whose BaseGlyphList color glyph is reused |

- glyphID must have a BaseGlyphPaintRecord in the BaseGlyphList (version 0 records do not count). If there is none, the graph is not well-formed.
- The root Paint of that record, with its whole graph, becomes the child sub-graph of this table and continues the current graph (current transform and clip apply).
- An implementation may process a base glyph's graph once, cache the outcome, and reuse it for every PaintColrGlyph that names that glyph.

### Formats 12 and 13: PaintTransform, PaintVarTransform

PaintTransform table (format 12, 7 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 12 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| Offset24 | transformOffset | Affine2x3 table, from start of this Paint table |

PaintVarTransform table (format 13, 7 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 13 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| Offset24 | transformOffset | VarAffine2x3 table, from start of this Paint table |

Affine2x3 table (24 bytes):

| Type | Name | Description |
|---|---|---|
| Fixed | xx | x of the image of the x unit vector |
| Fixed | yx | y of the image of the x unit vector |
| Fixed | xy | x of the image of the y unit vector |
| Fixed | yy | y of the image of the y unit vector |
| Fixed | dx | Shift along x |
| Fixed | dy | Shift along y |

VarAffine2x3 table (28 bytes):

| Type | Name | Description |
|---|---|---|
| Fixed | xx | x of the image of the x unit vector (var +0) |
| Fixed | yx | y of the image of the x unit vector (var +1) |
| Fixed | xy | x of the image of the y unit vector (var +2) |
| Fixed | yy | y of the image of the y unit vector (var +3) |
| Fixed | dx | Shift along x (var +4) |
| Fixed | dy | Shift along y (var +5) |
| uint32 | varIndexBase | First variation index |

- A child point (x, y) maps to x' = xx * x + xy * y + dx and y' = yx * x + yy * y + dy. So (1, 0) maps to the vector (xx, yx), (0, 1) maps to (xy, yy), and the origin moves to (dx, dy). The fields are in the same order as a PostScript or PDF matrix [a b c d e f].
- The matrix can express any combination of scale, skew, mirroring, rotation and translation.
- After the transform, the child's coordinate origin (the post-transform (0, 0)) is placed on the parent's origin; the matrix simply maps child coordinates into the parent's coordinate system.

### Formats 14 and 15: PaintTranslate, PaintVarTranslate

PaintTranslate table (format 14, 8 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 14 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| FWORD | dx | Shift along x |
| FWORD | dy | Shift along y |

PaintVarTranslate table (format 15, 12 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 15 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| FWORD | dx | Shift along x (var +0) |
| FWORD | dy | Shift along y (var +1) |
| uint32 | varIndexBase | First variation index |

Equivalent matrix (xx, yx, xy, yy, dx, dy) = (1, 0, 0, 1, dx, dy). The translate, scale, rotate and skew formats trade precision for size; Affine2x3 is the high-precision alternative.

### Formats 16 to 23: PaintScale and its variants

Formats 16 and 17 scale x and y separately about the origin; 18 and 19 separately about a given center; 20 and 21 uniformly about the origin; 22 and 23 uniformly about a given center. The odd formats are the variable twins.

PaintScale table (format 16, 8 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 16 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scaleX | Horizontal factor |
| F2DOT14 | scaleY | Vertical factor |

PaintVarScale table (format 17, 12 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 17 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scaleX | Horizontal factor (var +0) |
| F2DOT14 | scaleY | Vertical factor (var +1) |
| uint32 | varIndexBase | First variation index |

PaintScaleAroundCenter table (format 18, 12 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 18 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scaleX | Horizontal factor |
| F2DOT14 | scaleY | Vertical factor |
| FWORD | centerX | Point that stays fixed while scaling, x |
| FWORD | centerY | Point that stays fixed while scaling, y |

PaintVarScaleAroundCenter table (format 19, 16 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 19 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scaleX | Horizontal factor (var +0) |
| F2DOT14 | scaleY | Vertical factor (var +1) |
| FWORD | centerX | Fixed point of the scaling, x (var +2) |
| FWORD | centerY | Fixed point of the scaling, y (var +3) |
| uint32 | varIndexBase | First variation index |

PaintScaleUniform table (format 20, 6 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 20 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scale | One factor for both axes |

PaintVarScaleUniform table (format 21, 10 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 21 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scale | One factor for both axes (var +0) |
| uint32 | varIndexBase | First variation index |

PaintScaleUniformAroundCenter table (format 22, 10 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 22 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scale | One factor for both axes |
| FWORD | centerX | Fixed point of the scaling, x |
| FWORD | centerY | Fixed point of the scaling, y |

PaintVarScaleUniformAroundCenter table (format 23, 14 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 23 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | scale | One factor for both axes (var +0) |
| FWORD | centerX | Fixed point of the scaling, x (var +1) |
| FWORD | centerY | Fixed point of the scaling, y (var +2) |
| uint32 | varIndexBase | First variation index |

Equivalent matrices: about the origin, (sx, 0, 0, sy, 0, 0), with sx = sy = scale for the uniform formats. About a center (cx, cy): translate by (-cx, -cy), scale, translate back by (cx, cy), which gives (sx, 0, 0, sy, cx - sx * cx, cy - sy * cy). A factor of -1 mirrors along that axis (x for horizontal mirroring, y for vertical).

### Formats 24 to 27: PaintRotate, PaintVarRotate, PaintRotateAroundCenter, PaintVarRotateAroundCenter

PaintRotate table (format 24, 6 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 24 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | angle | Rotation: value * 180 degrees, counter-clockwise |

PaintVarRotate table (format 25, 10 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 25 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | angle | Rotation: value * 180 degrees, counter-clockwise (var +0) |
| uint32 | varIndexBase | First variation index |

PaintRotateAroundCenter table (format 26, 10 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 26 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | angle | Rotation: value * 180 degrees, counter-clockwise |
| FWORD | centerX | Pivot of the rotation, x |
| FWORD | centerY | Pivot of the rotation, y |

PaintVarRotateAroundCenter table (format 27, 14 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 27 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | angle | Rotation: value * 180 degrees, counter-clockwise (var +0) |
| FWORD | centerX | Pivot of the rotation, x (var +1) |
| FWORD | centerY | Pivot of the rotation, y (var +2) |
| uint32 | varIndexBase | First variation index |

- Angle in degrees = stored value * 180 (no bias). Unvaried values span [-360, 360) degrees; varied values may go beyond.
- Equivalent matrix for angle a about the origin: (xx, yx, xy, yy, dx, dy) = (cos a, sin a, -sin a, cos a, 0, 0).
- About a center (cx, cy): translate by (-cx, -cy), rotate, translate back, so dx = cx - cx * cos a + cy * sin a and dy = cy - cx * sin a - cy * cos a.
- Combining a rotation with other transforms must give exactly what the equivalent matrix (or sequence of matrices) gives.

### Formats 28 to 31: PaintSkew, PaintVarSkew, PaintSkewAroundCenter, PaintVarSkewAroundCenter

PaintSkew table (format 28, 8 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 28 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | xSkewAngle | Skew toward the x axis: value * 180 degrees, counter-clockwise |
| F2DOT14 | ySkewAngle | Skew toward the y axis: value * 180 degrees, counter-clockwise |

PaintVarSkew table (format 29, 12 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 29 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | xSkewAngle | Skew toward the x axis, as in format 28 (var +0) |
| F2DOT14 | ySkewAngle | Skew toward the y axis, as in format 28 (var +1) |
| uint32 | varIndexBase | First variation index |

PaintSkewAroundCenter table (format 30, 12 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 30 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | xSkewAngle | Skew toward the x axis, as in format 28 |
| F2DOT14 | ySkewAngle | Skew toward the y axis, as in format 28 |
| FWORD | centerX | Pivot of the skew, x |
| FWORD | centerY | Pivot of the skew, y |

PaintVarSkewAroundCenter table (format 31, 16 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 31 |
| Offset24 | paintOffset | Child Paint, from start of this Paint table |
| F2DOT14 | xSkewAngle | Skew toward the x axis, as in format 28 (var +0) |
| F2DOT14 | ySkewAngle | Skew toward the y axis, as in format 28 (var +1) |
| FWORD | centerX | Pivot of the skew, x (var +2) |
| FWORD | centerY | Pivot of the skew, y (var +3) |
| uint32 | varIndexBase | First variation index |

- Angles in degrees = stored value * 180 (no bias). Unvaried values span [-360, 360) degrees; varied values may go beyond.
- Equivalent matrix about the origin, for x skew angle ax and y skew angle ay: (xx, yx, xy, yy, dx, dy) = (1, tan(ay), -tan(ax), 1, 0, 0). Note the minus sign on xy: x' = x - tan(ax) * y and y' = tan(ay) * x + y.
- About a center (cx, cy): translate by (-cx, -cy), skew, translate back, so dx = cy * tan(ax) and dy = -cx * tan(ay).
- Combining a skew with other transforms must give exactly what the equivalent matrix (or sequence of matrices) gives.

### Format 32: PaintComposite

PaintComposite table (format 32, 8 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | format | 32 |
| Offset24 | sourcePaintOffset | Root of the source sub-graph, from start of this Paint table |
| uint8 | compositeMode | How source and backdrop combine (CompositeMode enumeration) |
| Offset24 | backdropPaintOffset | Root of the backdrop sub-graph, from start of this Paint table |

The backdrop is also called the destination. The modes are those of the W3C Compositing and Blending Level 1 specification, which defines their arithmetic. Treat an unrecognized compositeMode as COMPOSITE_CLEAR.

CompositeMode enumeration (the rows without a value are group headings, as in the source):

| Value | Name | Description |
|---|---|---|
|  | Porter-Duff modes |  |
| 0 | COMPOSITE_CLEAR | Clear: nothing kept |
| 1 | COMPOSITE_SRC | Source only; W3C name: copy |
| 2 | COMPOSITE_DEST | Backdrop only |
| 3 | COMPOSITE_SRC_OVER | Source on top of backdrop |
| 4 | COMPOSITE_DEST_OVER | Backdrop on top of source |
| 5 | COMPOSITE_SRC_IN | Source kept where the backdrop has coverage |
| 6 | COMPOSITE_DEST_IN | Backdrop kept where the source has coverage |
| 7 | COMPOSITE_SRC_OUT | Source kept where the backdrop lacks coverage |
| 8 | COMPOSITE_DEST_OUT | Backdrop kept where the source lacks coverage |
| 9 | COMPOSITE_SRC_ATOP | Source over backdrop, limited to the backdrop |
| 10 | COMPOSITE_DEST_ATOP | Backdrop over source, limited to the source |
| 11 | COMPOSITE_XOR | Only the parts that do not overlap |
| 12 | COMPOSITE_PLUS | Sum of both; W3C name: lighter |
|  | Separable color blend modes: |  |
| 13 | COMPOSITE_SCREEN | B = Cb + Cs - Cb * Cs |
| 14 | COMPOSITE_OVERLAY | Hard-light with backdrop and source swapped |
| 15 | COMPOSITE_DARKEN | B = min(Cb, Cs) |
| 16 | COMPOSITE_LIGHTEN | B = max(Cb, Cs) |
| 17 | COMPOSITE_COLOR_DODGE | B = min(1, Cb / (1 - Cs)); but 0 when Cb = 0, else 1 when Cs = 1 |
| 18 | COMPOSITE_COLOR_BURN | B = 1 - min(1, (1 - Cb) / Cs); but 1 when Cb = 1, else 0 when Cs = 0 |
| 19 | COMPOSITE_HARD_LIGHT | Multiply(Cb, 2 * Cs) if Cs <= 0.5, else Screen(Cb, 2 * Cs - 1) |
| 20 | COMPOSITE_SOFT_LIGHT | W3C soft-light |
| 21 | COMPOSITE_DIFFERENCE | B = abs(Cb - Cs) |
| 22 | COMPOSITE_EXCLUSION | B = Cb + Cs - 2 * Cb * Cs |
| 23 | COMPOSITE_MULTIPLY | B = Cb * Cs |
|  | Non-separable color blend modes: |  |
| 24 | COMPOSITE_HSL_HUE | Hue from source; saturation and luminosity from backdrop |
| 25 | COMPOSITE_HSL_SATURATION | Saturation from source; hue and luminosity from backdrop |
| 26 | COMPOSITE_HSL_COLOR | Hue and saturation from source; luminosity from backdrop |
| 27 | COMPOSITE_HSL_LUMINOSITY | Luminosity from source; hue and saturation from backdrop |

Boundedness of a PaintComposite sub-graph, by mode:

| compositeMode | The PaintComposite is bounded when |
|---|---|
| COMPOSITE_CLEAR | Always |
| COMPOSITE_SRC, COMPOSITE_SRC_OUT | The source is bounded |
| COMPOSITE_DEST, COMPOSITE_DEST_OUT | The backdrop is bounded |
| COMPOSITE_SRC_IN, COMPOSITE_DEST_IN | At least one of source and backdrop is bounded |
| Any other mode | Both source and backdrop are bounded |

## Number encodings

| Field | Type | Meaning (v = raw / 16384 for F2DOT14, raw / 65536 for Fixed) |
|---|---|---|
| stopOffset | F2DOT14 | Position v on the color line; unvaried range [-2, 2), varied values may leave it |
| alpha | F2DOT14 | Opacity multiplier v, clamped to [0, 1] |
| scaleX, scaleY, scale | F2DOT14 | Scale factor v; 1.0 (raw 0x4000) leaves size unchanged, negative values mirror |
| angle, xSkewAngle, ySkewAngle | F2DOT14 | v * 180 degrees, counter-clockwise, no bias; unvaried range [-360, 360) |
| startAngle, endAngle | F2DOT14 | (v + 1) * 180 degrees, counter-clockwise; unvaried range [-180, 540) |
| xx, yx, xy, yy, dx, dy | Fixed | Affine2x3 matrix elements; dx and dy are in design units |
| coordinates, centers, radii, translations, clip box edges | FWORD or UFWORD | Design units |

Variation deltas are integers added to the stored raw value before conversion: for an F2DOT14 the raw int16 counts units of 1/16384, for a Fixed the raw int32 counts units of 1/65536, and FWORD or UFWORD values count design units. When the meaning restricts the range (alpha to [0, 1]), clamp after adding the delta (see otvarcommonformats.md, deltas applied to F2DOT14 and Fixed values).

## Variation data

How each field of a Var table or record gets its delta:

1. If the COLR table has no ItemVariationStore (itemVariationStoreOffset is NULL), ignore every varIndexBase (fonts should store 0 there) and use the stored values.
2. If varIndexBase is 0xFFFFFFFF, the table or record has no variation data; use the stored values.
3. The k-th variable field (k = 0, 1, ... in field order; shown as "var +k" in the tables) uses variation index varIndexBase + k. The sum never wraps around and must not exceed 0xFFFFFFFF.
4. With a DeltaSetIndexMap (varIndexMapOffset not NULL), read the map entry at that index; an index at or beyond the map's mapCount uses the map's last entry. The entry yields an outer and an inner delta-set index (see otvarcommonformats.md for entryFormat unpacking).
5. Without a map (store present, varIndexMapOffset NULL), the mapping is implicit: the variation index itself is the delta-set index, with outer = index >> 16 (high 16 bits) and inner = index & 0xFFFF (low 16 bits).
6. A delta-set index of 0xFFFF/0xFFFF (outer and inner both 0xFFFF) means that field has no variation data.
7. Otherwise compute the scaled delta for the current instance from the ItemVariationStore (see otvarcommonformats.md) and add it to the stored raw value (see "Number encodings").

Variable fields by structure, in index order:

| Structure | +0 | +1 | +2 | +3 | +4 | +5 |
|---|---|---|---|---|---|---|
| ClipBoxFormat2 | xMin | yMin | xMax | yMax |  |  |
| VarColorStop | stopOffset | alpha |  |  |  |  |
| PaintVarSolid (3) | alpha |  |  |  |  |  |
| PaintVarLinearGradient (5) | x0 | y0 | x1 | y1 | x2 | y2 |
| PaintVarRadialGradient (7) | x0 | y0 | radius0 | x1 | y1 | radius1 |
| PaintVarSweepGradient (9) | centerX | centerY | startAngle | endAngle |  |  |
| VarAffine2x3 (from format 13) | xx | yx | xy | yy | dx | dy |
| PaintVarTranslate (15) | dx | dy |  |  |  |  |
| PaintVarScale (17) | scaleX | scaleY |  |  |  |  |
| PaintVarScaleAroundCenter (19) | scaleX | scaleY | centerX | centerY |  |  |
| PaintVarScaleUniform (21) | scale |  |  |  |  |  |
| PaintVarScaleUniformAroundCenter (23) | scale | centerX | centerY |  |  |  |
| PaintVarRotate (25) | angle |  |  |  |  |  |
| PaintVarRotateAroundCenter (27) | angle | centerX | centerY |  |  |  |
| PaintVarSkew (29) | xSkewAngle | ySkewAngle |  |  |  |  |
| PaintVarSkewAroundCenter (31) | xSkewAngle | ySkewAngle | centerX | centerY |  |  |

paletteIndex fields never vary. PaintVarTransform has no varIndexBase of its own (its VarAffine2x3 has one), and neither does VarColorLine (each VarColorStop has one).

## Processing rules

### The paint graph

- The Paint referenced by a BaseGlyphPaintRecord is the root of a directed graph; the color glyph consists of every Paint reachable from that root.
- Direct links are forward offsets: BaseGlyphPaintRecord.paintOffset, the paintOffset of PaintGlyph and of every transform format, and sourcePaintOffset and backdropPaintOffset of PaintComposite.
- Indirect links: a PaintColrLayers links to the Paints of its LayerList slice; a PaintColrGlyph links to the root Paint of the named base glyph, whose whole graph then continues the current one.
- colorLineOffset and transformOffset lead to data tables, not to Paints; they are not graph edges.
- Paints and whole sub-graphs may be shared by several parents, so the structure is a DAG rather than a tree. Depth is limited only by what the formats can express.
- Reuse comes in three forms: shared child tables reached by forward offsets, nested PaintColrLayers over a shared LayerList slice, and PaintColrGlyph.

### Well-formedness and validity

A color glyph graph is well-formed and valid when all of these hold:

1. Every forward offset lands inside the COLR table.
2. Each PaintColrLayers has a LayerList and its slice ends within that LayerList's numLayers.
3. Each PaintColrGlyph names a glyph that has a BaseGlyphPaintRecord.
4. Each PaintGlyph has a child.
5. No Paint can reach itself (the graph is acyclic).
6. The glyph is bounded (see "Boundedness and clip boxes").

It follows that in a well-formed graph every leaf is one of formats 2 to 9. These checks may be folded into the rendering pass rather than run separately.

### Detecting cycles

Forward offsets cannot form a loop, so only PaintColrLayers and PaintColrGlyph (indirect links) can introduce one. Detect it during the depth-first walk:

1. Keep the set of Paints on the path from the root to the current node (a Paint can be identified by its position within the table).
2. Before entering a Paint, look it up in that set. If it is already there, this link closes a cycle: do not enter it, and handle the error as below.
3. Insert a Paint into the set on entry and remove it on exit, so a sub-graph shared by two siblings is not mistaken for a cycle.

### Error recovery

1. When a node is broken (a cycle closes there, an offset leaves the table, a LayerList slice is out of range, a PaintColrGlyph target is missing, or another rule above fails), skip that Paint together with its sub-graph, count the node as bounded, and go on rendering the rest of the graph if the rest is valid.
2. Treat a Paint with an unrecognized format (for example one added by a later minor version) the same way: skip it and its sub-graph, count it as bounded, render the remainder.
3. An application that cannot recover may drop the whole color glyph; it may then draw the base glyph's own outline, if it has one, as an ordinary non-color glyph.

### Rendering a version 1 color glyph

Implementations may use any method that produces the same result as this procedure.

1. Prepare a drawing surface. Its size can come from the glyph's clip box, if any, or from a walk of the graph.
2. Starting at the root Paint, with the identity transform, process each Paint according to its format:

| Format | Action |
|---|---|
| 1 | Process each Paint of the LayerList slice from bottom to top; composite each result onto the surface with plain alpha (source-over) blending |
| 2, 3 | Paint the resolved solid color over the current clip region |
| 4 to 9 | Paint the gradient (rules below) over the current clip region, with its geometry under the current transform |
| 10 | Intersect the current clip with the glyph outline (under the current transform), process the child, then restore the previous clip |
| 11 | Process the root Paint of the named base glyph |
| 12 to 31 | Combine the table's transform with the current transform, process the child, then restore the previous transform |
| 32 | Process the backdrop sub-graph into a separate result, then the source sub-graph into another; merge source into backdrop with compositeMode; composite the merged result onto the surface with source-over |

### Transform composition

- A transform Paint affects its whole sub-graph: glyph outlines used as clips, gradient geometry, and transforms nested further down.
- Nested transforms accumulate. If an outer table has matrix A and a table inside its sub-graph has matrix B, a point p of B's child is drawn at A(B(p)). Keep a current matrix M; on entering a transform table with matrix T set M = M * T (T acts on child coordinates first), and restore M on leaving.
- The translate, scale, rotate and skew formats give the same result as their equivalent matrices. Each "around center" variant equals translate(center) * operation * translate(-center).
- These specialized formats store F2DOT14 and FWORD values; Affine2x3 uses 16.16 Fixed values for higher precision.

### Color lines

To find the color at position t of a color line (gradient geometry supplies t):

1. Resolve each stop: its offset (after deltas) and its color, namely the CPAL entry or the foreground color, with alpha = clamped stop alpha * color alpha.
2. Sort the stops by offset, ascending. File order matters only among stops with equal offsets, which keep their file order (a stable sort). In a variable font, sort after applying deltas; the order can therefore change between instances.
3. No stops: the whole line is transparent black. One stop: its color everywhere.
4. Let omin and omax be the smallest and largest offsets. If they are equal: with EXTEND_PAD, use the first stop's color for t < omin and the last stop's color for t >= omin; with EXTEND_REPEAT or EXTEND_REFLECT the line is ill-formed and nothing is drawn.
5. Otherwise let L = omax - omin and bring t into [omin, omax] by the extend mode:
   - EXTEND_PAD: below omin use the first stop's color, above omax the last stop's color.
   - EXTEND_REPEAT: shift t by a whole multiple of L. Copies above the interval are (omax, omax + L], (omax + L, omax + 2L], and so on; copies below are [omin - L, omin), [omin - 2L, omin - L), and so on. Each copy restarts from the color at the far end of the interval.
   - EXTEND_REFLECT: tile the same way, but run every second copy backward, so the pattern goes forward, backward, forward (period 2L).
6. Between two neighboring stops, interpolate linearly, using premultiplied linear-light values (see cpal.md, "Interpolation of colors").
7. Several stops on the same offset: below that offset use the first of them in file order, at and above it use the last, and ignore the others. This also applies when stops with different default offsets reach the same offset at some instance.

The three extend modes match the SVG 1.1 spreadMethod values pad, repeat and reflect.

Normalizing a color line to [0, 1], for graphics back ends that require it: map offset o to (o - omin) / (omax - omin), then move the gradient geometry so the new 0 and 1 positions fall where omin and omax were (formulas under each gradient type below).

### Linear gradients

- p0 = (x0, y0) carries stop offset 0 and p1 = (x1, y1) carries offset 1. Colors are laid out along the line through p0 and p1; each color then extends across the plane along lines parallel to the line through p0 and p2 = (x2, y2).
- Only the direction of the line p0p2 matters; neither the length of p2 - p0 nor its sign has any effect.
- Do not draw the gradient if p1 equals p0, if p2 equals p0, or if line p0p2 is parallel to line p0p1 (or nearly parallel, by an implementation-chosen tolerance).
- Position of a point P on the color line (follows from the definition): with v = p1 - p0, d = p2 - p0 and n = (-d.y, d.x) perpendicular to d, t(P) = ((P - p0) . n) / (v . n). The denominator is zero exactly in the parallel case.
- Two-point equivalent: p3 = p0 + n * (v . n) / (n . n) is the projection of p1 onto the line through p0 perpendicular to p0p2. A gradient from p0 (offset 0) to p3 (offset 1) with bands perpendicular to p0p3 looks identical.
- Under a transform, the result is the same as transforming p0, p1 and p2 first.
- Normalization to [0, 1] with v = p1 - p0: p0' = p0 + omin * v, p1' = p0 + omax * v, p2' = p2 + omin * v. In the two-point form, with w = p3 - p0: p0' = p0 + omin * w and p3' = p0 + omax * w.

### Radial gradients

- Circle 0 (center c0 = (x0, y0), radius r0) carries offset 0; circle 1 (center c1 = (x1, y1), radius r1) carries offset 1. This is the two-point conical gradient model of HTML Canvas createRadialGradient(), extended with the COLR extend modes and unrestricted stop offsets. Rendering must match these steps:
  1. If c0 equals c1 and r0 equals r1, draw nothing.
  2. For a real number t, define center c(t) = c0 + t * (c1 - c0), radius r(t) = r0 + t * (r1 - r0), and color(t) = the color line at t.
  3. Visit every t with r(t) > 0, going from the largest t (toward positive infinity) to the smallest (toward negative infinity). For each, draw the circle of radius r(t) around c(t) in color(t), touching only pixels that this step has not already painted for a larger t.
- What results:
  - Identical circles, or both radii 0: nothing is drawn.
  - Different centers and radii, neither circle inside the other: a cone open on one side; the area outside the cone stays unpainted.
  - Different centers, equal radii, neither circle inside the other: a strip (a flattened cylinder); the area outside it stays unpainted.
  - Different radii with one circle entirely inside the other: the whole plane is painted; colors inside the inner circle and outside the outer one come from the extend mode, and the bands of constant color are full circles.
  - Inner circle touching the outer one at a single point: exactly half the plane is painted. A variable font can flip abruptly between this and the other cases.
- Swapping the two circles changes the picture, because larger t wins, unless one circle contains the other. When the circles do not overlap, the bands of constant color curve the same way as the near side of circle 1.
- Negative radii (reachable only through variation deltas) need no special case; the same steps apply. With r0 = r1, a positive radius gives a cylinder and a negative one gives nothing.
- When r0 != r1 the cone's tip is at t_tip = r0 / (r0 - r1). If r1 > r0 then r(t) > 0 exactly for t > t_tip; if r1 < r0 then exactly for t < t_tip.
- Under a transform, the result equals transforming both circles and interpolating between the transformed shapes; the r(t) > 0 condition may be evaluated with the untransformed radii.
- If a transform flattens the circles into a single line (or nearly, by an implementation tolerance) with both centers on that line, the gradient is degenerate and must not be drawn. Flattening that leaves the centers apart gives a strip, or a cone that looks like a linear gradient.
- Repeat or reflect with nearly identical circles produces very fine bands and possible moire; the appearance then depends on the renderer.
- Back ends that need non-negative radii or stops in [0, 1] may rewrite the gradient, keeping the extend behavior:
  - If r0 = r1 > 0, plain normalization of the color line suffices.
  - If every stop offset t has r(t) >= 0, plain normalization with non-negative circles suffices.
  - With EXTEND_PAD, replace all stops whose r(t) < 0 by one stop at t_tip carrying the color interpolated there.
  - When the extension is periodic, any one-period slice of the extended line gives the same picture; pick a slice where r(t) >= 0, normalize it to [0, 1] and recompute the circles. The source states this item for the pad and repeat modes; a periodic extension exists for EXTEND_REPEAT (period omax - omin) and EXTEND_REFLECT (period 2 * (omax - omin)).

### Sweep gradients

- A sweep gradient has a center, a start angle a0, an end angle a1 (degrees counter-clockwise from the positive x axis, bias removed) and a color line.
- The color line is wrapped onto an endless spiral arc around the center: offset 0 sits at a0 and offset 1 at a1, whichever is larger. The ray at angle a therefore takes the color at t = (a - a0) / (a1 - a0); offsets outside the stop range follow the extend mode.
- Rays are drawn only for angles from 0 up to but excluding 360 degrees; positions below 0 or at or above 360 are never sampled. At most one full turn is drawn, with no overlap, although a0, a1 and the stops may lie outside that range and still shape the colors inside it.
- If a0 <= a1, offsets grow counter-clockwise. If a0 > a1, the color line is reversed and grows clockwise.
- If a0 equals a1 and the extend mode is EXTEND_REPEAT or EXTEND_REFLECT, draw nothing.
- The gradient is unbounded and covers the whole plane. A hard edge can appear at 0 degrees.
- Under a transform: imagine a circle of any non-zero radius around the center, with points marked at a0 and a1; transform the center, the circle and both points; put offset 0 at the transformed a0 point and offset 1 at the transformed a1 point; cast rays from the transformed center. A transform such as a mirror can therefore reverse the sweep direction.

### Compositing and blending

- Unless a PaintComposite says otherwise, overlapping content combines with plain source-over alpha compositing (W3C Compositing and Blending Level 1). That is how version 0 layers, PaintColrLayers layers and the output of PaintComposite are laid over what is below them.
- PaintComposite produces the backdrop first, then the source, and merges them with compositeMode. Porter-Duff modes decide how much each side contributes; blend modes decide how the two colors mix.
- Compositing and blending arithmetic runs on linear-light RGB: apply the inverse sRGB transfer function to CPAL colors first (see cpal.md).
- Typical uses: COMPOSITE_SRC_IN with an alpha ramp in the source acts as a mask; COMPOSITE_SRC_OUT punches the source shape out of the backdrop, where only the source's coverage matters, not its color.

### Glyph metrics

- Version 0: every layer glyph has the same advance width as the base glyph; when the font has vertical metrics, also the same advance height and vertical origin.
- Version 1: the color glyph takes the base glyph's advance width (and, with vertical metrics, its advance height and vertical origin). Advances of glyphs named by PaintGlyph are irrelevant and ignored.

### Boundedness and clip boxes

- A valid color glyph paints only inside some finite box.
- A glyph with a clip box is bounded by definition; its graph need not be inspected.
- For a glyph without a clip box the application must check the graph, and must not render the glyph if the graph is unbounded. Per format:
  - PaintGlyph (10): always bounded.
  - Fills (formats 2 to 9): unbounded.
  - PaintColrLayers (1): bounded only if every layer is bounded.
  - PaintColrGlyph (11): bounded only if the named glyph's graph is bounded.
  - Transforms (formats 12 to 31): bounded only if the child is bounded.
  - PaintComposite (32): by mode, per the table under Format 32.
  - A node skipped as broken or unknown counts as bounded.
- The clip box lets an implementation size its drawing surface without walking the graph. Without a clip box, a bounding box can be computed by walking the graph.
