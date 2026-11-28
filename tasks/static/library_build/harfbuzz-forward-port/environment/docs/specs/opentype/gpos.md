# GPOS - Glyph Positioning Table
Source: GPOS - Glyph Positioning Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/gpos
These notes restate the source's structures and rules; where they differ, the source governs.

## What GPOS does

GPOS holds positioning data organised by script and language system. With it a font can:

- shift a glyph's placement and change its advance, in X and in Y;
- adjust two glyphs relative to each other (kerning and similar pair adjustments);
- attach glyphs to each other by aligning anchor points: cursive joins, marks on base
  glyphs, marks on ligature components, and marks on other marks;
- apply any of these only inside a matched glyph context (with optional backtrack and
  lookahead context).

Other font tables give a glyph only a placement (left side bearing) and an advance along the
layout direction. GPOS adds adjustments in both directions and anchor-based attachment. In
non-variable fonts any GPOS placement or advance value can also be refined per ppem size by a
Device table.

## Coordinate conventions

- Every GPOS value is in font design units.
- Placement is the glyph's offset from the current pen point; advance is how far the pen
  moves before the next glyph. For horizontal text these correspond to the left side bearing
  and the advance width.
- X and Y placement values always use the ordinary Cartesian axes (x to the right, y upward,
  origin on the baseline at the left side), whatever the writing direction.
- The meaning of an advance depends on direction. Left-to-right: a first glyph with advance
  100 puts the next glyph at (100, 0). Right-to-left: the next glyph starts at (-100, 0).
- Vertical (top-to-bottom) layout: enlarging a glyph's advance height by 100 units is
  YAdvance = 100.
- Lowering a mark by 10 units is YPlacement = -10 in every writing direction.
- A glyph may offer several attachment points; which one is used depends on the glyph being
  attached. Marks are grouped into mark classes so that one base anchor serves every mark of
  a class (for example one anchor above the base and one below).

## Variable fonts

- In a variable font, the X and Y values in GPOS describe the default instance and may need
  adjusting for the current instance.
- The variation deltas are stored in the ItemVariationStore inside GDEF (see gdef.md and
  otvarcommonformats.md). The same store also serves GDEF and JSTF values.
- Each value that varies references a VariationIndex table holding its delta-set index. A
  VariationIndex table is a Device table variant with its own format value (see chapter2.md
  (Device and VariationIndex tables)). Both use the same offset fields, so a variable font
  cannot use Device tables, and Device tables appear only in non-variable fonts.
- Applications without font-variation support, and fonts that are not variable, ignore
  VariationIndex tables.
- A value with no VariationIndex table has the same value in every instance.
- Several values may point at one VariationIndex table, and several VariationIndex tables
  may reference the same deltas; still, every varying value needs its own reference.
- A position given by an outline contour point (AnchorFormat2) would force the client to run
  the outline variation through the rasterizer before positioning could finish, which is
  slow. In a variable font, positions that vary are therefore meant to be given directly as
  X and Y values (AnchorFormat3 with VariationIndex tables).

## Table organization and lookup selection

The header points to a ScriptList, a FeatureList, a LookupList and, in version 1.1, an
optional FeatureVariations table. All four are described in chapter2.md. FeatureVariations
can substitute alternate feature tables under stated conditions; at present only variable
fonts use it.

To choose the lookups to run:

1. Find the current script in the ScriptList.
2. Take the LangSys table of the language system when it is known; otherwise take the
   script's default LangSys.
3. The LangSys supplies FeatureList indices: a required feature plus further features.
4. Select the features to apply by their featureTag.
5. If a FeatureVariations table is present, check its conditions; a match may replace
   some selected feature tables with alternate ones.
6. Collect the LookupList indices of all selected feature tables and run those lookups in
   LookupList order.

## Lookup processing rules

- A Lookup table (see chapter2.md (Lookup table)) holds one or more subtables. All of them
  have the lookup's type, but their formats may differ, so one lookup can mix (for instance)
  a glyph-list format for some glyphs and a range format for others.
- Each separate positioning action needs its own lookup. Lookups run in LookupList order,
  and each one works on the result of the lookups before it.
- Adjustments stated as X or Y placement or advance values add up from lookup to lookup.
  Positioning by attachment (anchors) can instead override what earlier lookups did.
- A lookup is run over every glyph of the string before the next lookup begins.
- At a given position the subtables are tried in order; the first one that matches is
  applied and the remaining subtables are not tried at that position (chapter2.md).
- After an action, processing resumes after every glyph that took part: the glyphs that were
  positioned and the other glyphs of the matched input sequence. In chained contexts the
  lookahead glyphs are not passed over.
- The one exception is pair positioning: when the second glyph's ValueRecord is empty
  (valueFormat2 is 0), that second glyph becomes the next glyph to process.

### Lookup flags as they affect GPOS

The LookupFlag bits are defined in chapter2.md (Lookup table); this summary covers what GPOS
processing depends on. Glyph classes, mark attachment classes and mark glyph sets come from
GDEF (see gdef.md).

| Mask | Name | Effect |
|---|---|---|
| 0x0001 | RIGHT_TO_LEFT | Read only by type 3 (cursive) lookups: picks which glyph moves in the cross-stream direction. Ignored by every other type and never a text-direction signal. |
| 0x0002 | IGNORE_BASE_GLYPHS | Skip glyphs of GDEF class 1. |
| 0x0004 | IGNORE_LIGATURES | Skip glyphs of GDEF class 2. |
| 0x0008 | IGNORE_MARKS | Skip glyphs of GDEF class 3. |
| 0x0010 | USE_MARK_FILTERING_SET | Skip marks outside the GDEF mark glyph set chosen by the Lookup table's markFilteringSet field (present only when this bit is set). |
| 0x00E0 | reserved | Unused; set to zero. |
| 0xFF00 | MARK_ATTACHMENT_CLASS_FILTER | If non-zero, skip marks whose GDEF mark attachment class is different. |

- A skipped glyph is treated as absent; matching of the other positions continues past it.
- The current glyph is always compared against the first position of the pattern without
  regard to the flags. The flags govern the remaining input positions and, in chained
  lookups, the backtrack and lookahead positions. In pair positioning they decide which glyph
  counts as the second glyph; in mark-to-mark positioning, which glyph counts as the
  preceding mark.
- IGNORE_MARKS overrides both mark filters; a mark filtering set overrides a mark attachment
  class.
- For types 7 and 8, the flags of the containing lookup govern pattern matching
  (RIGHT_TO_LEFT is never used there). Each nested lookup is then applied under its own
  flags, which can filter the matched sequence further.

## GposLookupType enumeration

All subtables of one Lookup table share its type.

| Value | Type | Action |
|---|---|---|
| 1 | Single adjustment | Moves one glyph. |
| 2 | Pair adjustment | Moves the two glyphs of a pair relative to each other. |
| 3 | Cursive attachment | Joins consecutive cursive glyphs through exit and entry anchors. |
| 4 | Mark-to-base attachment | Attaches a combining mark to a base glyph. |
| 5 | Mark-to-ligature attachment | Attaches a combining mark to one component of a ligature. |
| 6 | Mark-to-mark attachment | Attaches a combining mark to a preceding mark. |
| 7 | Contextual positioning | Runs nested positioning lookups inside a matched input sequence. |
| 8 | Chained contexts positioning | As type 7, with backtrack and lookahead context added. |
| 9 | Positioning extension | Wrapper that reaches a subtable of another type through a 32-bit offset; adds no new action. |

Shared building blocks:

- Every subtable except type 9 references a Coverage table (see chapter2.md (Coverage
  table)). A glyph's Coverage Index (its 0-based position in the Coverage table) selects
  that glyph's record in the parallel arrays described below.
- Types 1 and 2 use ValueRecords described by ValueFormat flags.
- Types 3 to 6 use Anchor tables; types 4 to 6 also use a MarkArray.

## GPOS header

Two versions exist. Version 1.0 has three offsets (10-byte header); version 1.1 appends a
32-bit FeatureVariations offset (14-byte header). All offsets are from the start of the GPOS
table.

GPOS header, version 1.0

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Always 1. |
| uint16 | minorVersion | 0 for this layout. |
| Offset16 | scriptListOffset | ScriptList, from start of GPOS. |
| Offset16 | featureListOffset | FeatureList, from start of GPOS. |
| Offset16 | lookupListOffset | LookupList, from start of GPOS. |

GPOS header, version 1.1

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Always 1. |
| uint16 | minorVersion | 1 for this layout. |
| Offset16 | scriptListOffset | ScriptList, from start of GPOS. |
| Offset16 | featureListOffset | FeatureList, from start of GPOS. |
| Offset16 | lookupListOffset | LookupList, from start of GPOS. |
| Offset32 | featureVariationsOffset | FeatureVariations table, from start of GPOS; NULL when absent. |

## Shared formats

### ValueRecord

A ValueRecord holds X and Y adjustments in design units. Positive values add to, and
negative values subtract from, the placement and advance the font otherwise gives. It may
also hold, per value, an offset to a Device table (non-variable fonts) or a VariationIndex
table (variable fonts).

Layout rules:

- Every field is optional. A ValueFormat field that accompanies the record says which fields
  exist; the record itself has no flags.
- Present fields appear in the order of the table below. An absent field takes no space: the
  next present field follows directly after the previous present one.
- Each of the eight defined ValueFormat bits adds one 2-byte field, so a record occupies
  2 * popcount(valueFormat & 0x00FF) bytes. ValueFormat 0x0000 is an empty record: no
  adjustment.
- The size and content of ValueRecords therefore differ from subtable to subtable. Within
  one subtable, every ValueRecord for a given glyph position uses the same ValueFormat.
- The four device offsets are measured from the start of the record's immediate parent
  table: the SinglePos subtable (format 1 or 2), the PairPosFormat2 subtable, or, for
  PairPosFormat1, the PairSet table that holds the record.

ValueRecord

| Type | Name | Description |
|---|---|---|
| int16 | xPlacement | Change to horizontal placement, design units. |
| int16 | yPlacement | Change to vertical placement, design units. |
| int16 | xAdvance | Change to horizontal advance, design units; horizontal layout only. |
| int16 | yAdvance | Change to vertical advance, design units; vertical layout only. |
| Offset16 | xPlaDeviceOffset | Device (non-variable) or VariationIndex (variable) table for xPlacement; from the immediate parent table; may be NULL. |
| Offset16 | yPlaDeviceOffset | Device (non-variable) or VariationIndex (variable) table for yPlacement; from the immediate parent table; may be NULL. |
| Offset16 | xAdvDeviceOffset | Device (non-variable) or VariationIndex (variable) table for xAdvance; from the immediate parent table; may be NULL. |
| Offset16 | yAdvDeviceOffset | Device (non-variable) or VariationIndex (variable) table for yAdvance; from the immediate parent table; may be NULL. |

ValueFormat flags (combine with bitwise OR)

| Mask | Name | Description |
|---|---|---|
| 0x0001 | X_PLACEMENT | xPlacement field present. |
| 0x0002 | Y_PLACEMENT | yPlacement field present. |
| 0x0004 | X_ADVANCE | xAdvance field present. |
| 0x0008 | Y_ADVANCE | yAdvance field present. |
| 0x0010 | X_PLACEMENT_DEVICE | xPlaDeviceOffset field present. |
| 0x0020 | Y_PLACEMENT_DEVICE | yPlaDeviceOffset field present. |
| 0x0040 | X_ADVANCE_DEVICE | xAdvDeviceOffset field present. |
| 0x0080 | Y_ADVANCE_DEVICE | yAdvDeviceOffset field present. |
| 0xFF00 | Reserved | Not defined; must be zero. |

For instance 0x0001 means the record is just xPlacement, 0x0004 just xAdvance, and 0x0005
both (xPlacement first).

Applying a ValueRecord to a glyph:

1. Work out from the governing ValueFormat which fields are present.
2. Add xPlacement and yPlacement to the glyph's horizontal and vertical placement offsets.
3. Add xAdvance to the glyph's advance in horizontal layout, or yAdvance in vertical layout;
   the advance field of the other direction is not used.
4. For each device offset that is present and not NULL, correct the matching value
   (xPlaDeviceOffset -> xPlacement, yPlaDeviceOffset -> yPlacement, xAdvDeviceOffset ->
   xAdvance, yAdvDeviceOffset -> yAdvance):
   - non-variable font: the Device table lists pixel corrections for each ppem size from its
     startSize to its endSize; the correction for the current size is applied to the scaled
     value;
   - variable font: the VariationIndex table gives a delta-set index; the delta for the
     current instance, taken from the GDEF item variation store, is added to the value.
5. The resulting changes add to whatever earlier lookups did to the same glyph.

### Anchor tables

An anchor is a point on a glyph. To attach two glyphs, each provides an anchor and the client
moves one glyph so that the two anchors coincide. The coordinates are design units relative
to the glyph's own outline coordinates. Three formats exist; the first uint16 is the format.

AnchorFormat1 table: design units

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| int16 | xCoordinate | X of the anchor, design units. |
| int16 | yCoordinate | Y of the anchor, design units. |

AnchorFormat2 table: design units plus contour point

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 2. |
| int16 | xCoordinate | X of the anchor, design units. |
| int16 | yCoordinate | Y of the anchor, design units. |
| uint16 | anchorPoint | Index of a contour point on the glyph outline that refines the anchor. |

AnchorFormat3 table: design units plus Device or VariationIndex tables

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 3. |
| int16 | xCoordinate | X of the anchor, design units. |
| int16 | yCoordinate | Y of the anchor, design units. |
| Offset16 | xDeviceOffset | Device (non-variable) or VariationIndex (variable) table adjusting xCoordinate; from start of this Anchor table; may be NULL. |
| Offset16 | yDeviceOffset | Device (non-variable) or VariationIndex (variable) table adjusting yCoordinate; from start of this Anchor table; may be NULL. |

Interpreting an anchor:

- Format 1: the anchor is exactly (xCoordinate, yCoordinate). It is small and simple but
  cannot follow hinting.
- Format 2: the coordinates locate the anchor, and anchorPoint names an outline point used to
  fine-tune it. Hinting may move that point; in rendered output the point's final position
  at the current ppem gives the anchor.
- Format 3: the coordinates locate the anchor, and each coordinate may have its own
  adjustment table; set the offset for a coordinate that needs none to NULL. Non-variable
  font: Device tables adjust the position for particular sizes and resolutions. Variable
  font: VariationIndex tables supply per-instance deltas, and a coordinate without one is
  the same in every instance. Several coordinates may share a VariationIndex table.

### MarkArray table and MarkRecord

Mark-to-base, mark-to-ligature and mark-to-mark subtables describe their marks with a
MarkArray: one MarkRecord per mark, giving the mark's class and its anchor.

- A MarkRecord must state its class explicitly, even class 0. (In a ClassDef table, by
  contrast, unlisted glyphs fall into class 0 automatically.)
- Mark class values index the zero-based per-class anchor arrays (BaseRecord,
  ComponentRecord, Mark2Record), which have markClassCount entries.

MarkArray table

| Type | Name | Description |
|---|---|---|
| uint16 | markCount | Number of MarkRecords. |
| MarkRecord | markRecords[markCount] | One per mark, in the order of the associated mark Coverage table. |

MarkRecord

| Type | Name | Description |
|---|---|---|
| uint16 | markClass | Mark class of this mark (0 allowed, but always stated). |
| Offset16 | markAnchorOffset | This mark's Anchor table, from start of the MarkArray table. |

## Lookup type 1: single adjustment (SinglePos)

Adjusts the placement and/or advance of one glyph (for example a superscript or subscript).
Format 1 gives every covered glyph the same adjustment; format 2 gives each covered glyph its
own ValueRecord. SinglePos lookups are also the usual nested lookups of contextual
positioning.

SinglePosFormat1 subtable: one value for all covered glyphs

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| Offset16 | coverageOffset | Coverage of the glyphs to adjust; from start of the SinglePos subtable. |
| uint16 | valueFormat | ValueFormat flags describing valueRecord. |
| ValueRecord | valueRecord | The adjustment applied to every covered glyph. |

SinglePosFormat2 subtable: one value per covered glyph

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 2. |
| Offset16 | coverageOffset | Coverage of the glyphs to adjust; from start of the SinglePos subtable. |
| uint16 | valueFormat | ValueFormat flags shared by every entry of valueRecords. |
| uint16 | valueCount | Number of ValueRecords; must equal the Coverage glyph count. |
| ValueRecord | valueRecords[valueCount] | One record per covered glyph, in Coverage Index order. |

Processing:

1. If the current glyph is not in the Coverage table, the subtable does not apply.
2. Format 1: apply valueRecord. Format 2: apply valueRecords[i], where i is the glyph's
   Coverage Index. Records are 2 * popcount(valueFormat & 0x00FF) bytes each and start at
   byte 8 of a format 2 subtable (byte 6 for the single record of format 1).
3. Only the current glyph changes. Device offsets in the records are measured from the start
   of the SinglePos subtable.

## Lookup type 2: pair adjustment (PairPos)

Adjusts two glyphs relative to each other, independently in X and Y and for each glyph of the
pair. Pairs are written in logical order: the first glyph of a pair is the left-most one in
left-to-right text and the right-most one in right-to-left text. Format 1 names pairs by glyph
ID; format 2 names them by glyph class.

Both formats carry two ValueFormat fields:

- valueFormat1 describes the record for the first glyph of every pair. If it is 0, the first
  glyph has no record and is not moved.
- valueFormat2 describes the record for the second glyph of every pair. If it is 0, the
  second glyph has no record, is not moved, and becomes the next glyph at which the lookup
  is tried.

### Pair adjustment format 1: glyph pairs

The Coverage table lists each first glyph once, however many pairs it starts. For every
covered glyph there is one PairSet listing the pairs that begin with it.

PairPosFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| Offset16 | coverageOffset | Coverage of the first glyphs; from start of the PairPos subtable. |
| uint16 | valueFormat1 | Fields of valueRecord1 (first glyph); 0 is allowed. |
| uint16 | valueFormat2 | Fields of valueRecord2 (second glyph); 0 is allowed. |
| uint16 | pairSetCount | Number of PairSet tables (one per covered glyph). |
| Offset16 | pairSetOffsets[pairSetCount] | PairSet offsets from start of the PairPos subtable, in Coverage Index order. |

PairSet table: all pairs starting with one covered glyph

| Type | Name | Description |
|---|---|---|
| uint16 | pairValueCount | Number of PairValue records in this set. |
| PairValue | pairValueRecords[pairValueCount] | The pairs, sorted by the glyph ID in secondGlyph. |

PairValue record

| Type | Name | Description |
|---|---|---|
| uint16 | secondGlyph | Glyph ID of the second glyph (the first glyph is the covered one). |
| ValueRecord | valueRecord1 | Adjustment for the first glyph; absent (zero bytes) when valueFormat1 is 0. |
| ValueRecord | valueRecord2 | Adjustment for the second glyph; absent (zero bytes) when valueFormat2 is 0. |

A PairValue record is 2 + 2 * popcount(valueFormat1 & 0x00FF) + 2 * popcount(valueFormat2 &
0x00FF) bytes. Device offsets inside these records are measured from the start of the PairSet
table, not from the subtable.

### Pair adjustment format 2: class pairs

Every glyph of every pair is assigned a class value through a ClassDef table (see
chapter2.md (Class definition table)): classDef1 for first glyphs, classDef2 for second
glyphs. The two offsets may point to the same ClassDef but need not. A glyph not listed in a
ClassDef has class 0. The Coverage table still lists every glyph that may come first, each
once.

The adjustments form a two-dimensional array: class1Records indexed by the first glyph's
class, each holding class2Records indexed by the second glyph's class. Neither record type
carries a class number; the array index is the class value. Both counts include class 0, and
each Class1 record holds a Class2 record for every class of classDef2, class 0 included.

PairPosFormat2 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 2. |
| Offset16 | coverageOffset | Coverage of glyphs that may be first in a pair; from start of the PairPos subtable. |
| uint16 | valueFormat1 | Fields of valueRecord1 (first glyph); 0 is allowed. |
| uint16 | valueFormat2 | Fields of valueRecord2 (second glyph); 0 is allowed. |
| Offset16 | classDef1Offset | ClassDef for first glyphs; from start of the PairPos subtable. |
| Offset16 | classDef2Offset | ClassDef for second glyphs; from start of the PairPos subtable. |
| uint16 | class1Count | Count of first-glyph classes, class 0 included. |
| uint16 | class2Count | Count of second-glyph classes, class 0 included. |
| Class1 | class1Records[class1Count] | One entry per first-glyph class, indexed by class value. |

Class1 record

| Type | Name | Description |
|---|---|---|
| Class2 | class2Records[class2Count] | One entry per second-glyph class, indexed by class value. |

Class2 record

| Type | Name | Description |
|---|---|---|
| ValueRecord | valueRecord1 | Adjustment for the first glyph; omitted when valueFormat1 = 0. |
| ValueRecord | valueRecord2 | Adjustment for the second glyph; omitted when valueFormat2 = 0. |

Class2 records are variable in size; a client must compute their size from the two
ValueFormats. With s = 2 * popcount(valueFormat1 & 0x00FF) + 2 * popcount(valueFormat2 &
0x00FF), the record for classes (c1, c2) starts (c1 * class2Count + c2) * s bytes after the
start of class1Records (byte 16 of the subtable). If valueFormat1 is 0 a Class2 record is just
valueRecord2. Device offsets inside these records are measured from the start of the
PairPosFormat2 subtable.

### Pair positioning procedure (both formats)

1. The current glyph is the first glyph. If it is not in the Coverage table, the subtable
   does not apply.
2. The second glyph is the next glyph in logical order, passing over glyphs that the lookup
   flags skip.
3. Format 1: take the PairSet at pairSetOffsets[i] (i = Coverage Index of the first glyph)
   and search its records for secondGlyph equal to the second glyph's ID; the records are
   sorted, so a binary search works. If no record matches, the subtable defines nothing for
   this pair.
4. Format 2: c1 = class of the first glyph in classDef1, c2 = class of the second glyph in
   classDef2; use class1Records[c1].class2Records[c2].
5. Apply valueRecord1 to the first glyph and valueRecord2 to the second glyph. An empty
   record changes nothing.
6. Next position: if valueFormat2 is 0, processing resumes at the second glyph, which may
   itself start a new pair. If valueFormat2 is non-zero, the second glyph was part of the
   action and processing resumes after it.

## Lookup type 3: cursive attachment (CursivePos)

Joins glyphs of a cursive script by aligning the exit anchor of one glyph with the entry
anchor of the glyph that follows it. Only one format exists.

CursivePosFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| Offset16 | coverageOffset | Coverage of the glyphs that have cursive data; from start of the CursivePos subtable. |
| uint16 | entryExitCount | Number of EntryExit records. |
| EntryExit | entryExitRecords[entryExitCount] | One per covered glyph, in Coverage Index order. |

EntryExit record

| Type | Name | Description |
|---|---|---|
| Offset16 | entryAnchorOffset | Anchor of the entry point; from start of the CursivePos subtable; NULL if the glyph has none. |
| Offset16 | exitAnchorOffset | Anchor of the exit point; from start of the CursivePos subtable; NULL if the glyph has none. |

Processing, for two glyphs G1 and G2 that follow each other in logical order (G2 being the
next glyph after lookup-flag skipping):

1. Both glyphs need EntryExit records in this subtable. The anchors used are the exit anchor
   of G1 and the entry anchor of G2. If either offset is NULL, no adjustment is made.
2. Along the line-layout direction (X in horizontal layout), the advance of G1, the first
   glyph in logical order, is changed. This moves G2 relative to G1 until the two anchors
   line up along that axis.
3. Across the line (Y in horizontal layout), the placement of one glyph is changed so the
   anchors line up:
   - RIGHT_TO_LEFT lookup flag clear: G2 is moved to meet G1.
   - RIGHT_TO_LEFT lookup flag set: G1 is moved to meet G2.
4. Chains: when several glyphs join in a row, each alignment uses its neighbour's adjusted
   position, so cross-stream shifts accumulate along the run. With RIGHT_TO_LEFT set, the
   last glyph of the connected run keeps its original cross-stream position relative to the
   baseline and every preceding connected glyph is shifted. With the flag clear, the
   dependency runs the other way: each glyph follows its predecessor and the first glyph of
   the run keeps its position.

## Lookup type 4: mark-to-base attachment (MarkBasePos)

Positions combining marks on base glyphs. Each mark has an anchor and a mark class. Each base
glyph has one anchor per mark class. Only the mark's placement changes; the base's placement
and the advances of both glyphs stay as they were. Only one format exists.

MarkBasePosFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| Offset16 | markCoverageOffset | Coverage of the marks; from start of the MarkBasePos subtable. |
| Offset16 | baseCoverageOffset | Coverage of the base glyphs; from start of the MarkBasePos subtable. |
| uint16 | markClassCount | Number of distinct mark classes used by the MarkRecords; length of every BaseRecord. |
| Offset16 | markArrayOffset | MarkArray (class and anchor per mark); from start of the MarkBasePos subtable. |
| Offset16 | baseArrayOffset | BaseArray; from start of the MarkBasePos subtable. |

BaseArray table

| Type | Name | Description |
|---|---|---|
| uint16 | baseCount | Number of BaseRecords. |
| BaseRecord | baseRecords[baseCount] | One per base glyph, in baseCoverage Index order. |

BaseRecord

| Type | Name | Description |
|---|---|---|
| Offset16 | baseAnchorOffsets[markClassCount] | Base anchor for each mark class, indexed by class value; from start of the BaseArray table (not the record); entries may be NULL. |

Anchor tables carry no class number; position in the array is the class. Every class used in
the MarkRecords, class 0 included, has a slot.

Processing:

1. The input is the mark being positioned (the current glyph). If it is not in markCoverage,
   the subtable does not apply. Its MarkRecord (markRecords[mark Coverage Index]) gives the
   mark class c and the mark anchor.
2. Walk back from the mark until reaching the closest earlier base glyph, stepping over
   intervening marks (for example earlier marks on the same base).
3. That base must be in baseCoverage; its BaseRecord is baseRecords[base Coverage Index]. The
   base anchor is baseAnchorOffsets[c]. A NULL entry means the base has no attachment point
   for class c.
4. Change the mark's placement so the mark anchor lands on the base anchor. The alignment is
   made relative to the base glyph's final pen (advance) position.
5. Each mark is its own input: with several marks in a row the lookup acts once per mark.

## Lookup type 5: mark-to-ligature attachment (MarkLigPos)

Positions combining marks on ligature glyphs. A ligature is treated as several components
(virtual parts, not separate glyphs), each with its own anchor per mark class, so one
ligature can offer several anchors for the same class. Only the mark's placement changes;
the ligature's placement and both advances stay as they were. Only one format exists.

MarkLigPosFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| Offset16 | markCoverageOffset | Coverage of the marks; from start of the MarkLigPos subtable. |
| Offset16 | ligatureCoverageOffset | Coverage of the ligature glyphs; from start of the MarkLigPos subtable. |
| uint16 | markClassCount | Number of mark classes in use; length of every ComponentRecord. |
| Offset16 | markArrayOffset | MarkArray (class and anchor per mark); from start of the MarkLigPos subtable. |
| Offset16 | ligatureArrayOffset | LigatureArray; from start of the MarkLigPos subtable. |

LigatureArray table

| Type | Name | Description |
|---|---|---|
| uint16 | ligatureCount | Number of LigatureAttach offsets. |
| Offset16 | ligatureAttachOffsets[ligatureCount] | One LigatureAttach offset per ligature, in ligatureCoverage Index order; from start of the LigatureArray table. |

LigatureAttach table (one ligature glyph)

| Type | Name | Description |
|---|---|---|
| uint16 | componentCount | Number of ComponentRecords (components of the ligature). |
| ComponentRecord | componentRecords[componentCount] | One per component, in logical (writing-direction) order. |

ComponentRecord

| Type | Name | Description |
|---|---|---|
| Offset16 | ligatureAnchorOffsets[markClassCount] | Anchor for each mark class on this component, indexed by class value; from start of the LigatureAttach table; NULL when the component has no point for that class. |

Component order is logical: in left-to-right text component 0 is the left-most part of the
ligature; in right-to-left text it is the right-most part.

Processing:

1. The input is the mark (the current glyph); it must be in markCoverage. Its MarkRecord
   gives the class c and the mark anchor.
2. Walk back from the mark until reaching the closest earlier ligature glyph, stepping over
   intervening marks. It must be in ligatureCoverage; its LigatureAttach table is found through
   ligatureAttachOffsets[ligature Coverage Index].
3. Choose the component k that the mark belongs to. The font data cannot tell this: it
   depends on the original character string and on the character and glyph processing done
   since. The client must therefore record, during any character-level preprocessing and
   every GSUB substitution (in particular when it forms ligatures), which ligature component
   each mark is associated with.
4. The ligature anchor is componentRecords[k].ligatureAnchorOffsets[c]. NULL means component
   k defines no attachment point for class c.
5. Change the mark's placement so the anchors coincide.

## Lookup type 6: mark-to-mark attachment (MarkMarkPos)

Positions one mark relative to another (for example a tone mark on a vowel mark). The layout
matches MarkBasePos; mark1 is the attaching mark and mark2 plays the role of the base. Each
mark1 has an anchor and a class (via a MarkArray); each mark2 has one anchor per mark1 class.
Only one format exists.

MarkMarkPosFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| Offset16 | mark1CoverageOffset | Coverage of the attaching marks (mark1); from start of the MarkMarkPos subtable. |
| Offset16 | mark2CoverageOffset | Coverage of the base marks (mark2); from start of the MarkMarkPos subtable. |
| uint16 | markClassCount | Number of mark1 classes; length of every Mark2 record. |
| Offset16 | mark1ArrayOffset | MarkArray for the mark1 glyphs; from start of the MarkMarkPos subtable. |
| Offset16 | mark2ArrayOffset | Mark2Array for the mark2 glyphs; from start of the MarkMarkPos subtable. |

Mark2Array table

| Type | Name | Description |
|---|---|---|
| uint16 | mark2Count | Number of Mark2 records. |
| Mark2 | mark2Records[mark2Count] | One per mark2 glyph, in mark2Coverage Index order. |

Mark2 record

| Type | Name | Description |
|---|---|---|
| Offset16 | mark2AnchorOffsets[markClassCount] | Anchor for each mark1 class, indexed by class value; from start of the Mark2Array table; entries may be NULL. |

Processing:

1. The input is mark1, the mark being positioned (the current glyph); it must be in
   mark1Coverage. Its MarkRecord in the mark1 MarkArray gives class c and the mark1 anchor.
2. mark2 is the glyph immediately before mark1 in glyph-string order, after passing over the
   glyphs that the lookup flags skip. No other skipping is done.
3. The subtable applies exactly when that glyph is in mark2Coverage. Its Mark2 record is
   mark2Records[mark2 Coverage Index] and the anchor is mark2AnchorOffsets[c]; a NULL entry
   means no attachment point for class c.
4. Change mark1's placement so the anchors coincide; advances are unchanged.
5. As with types 4 and 5, a sequence of several marks is handled by applying the lookup once
   per mark.

## Lookup type 7: contextual positioning

Matches an input sequence pattern and then applies nested positioning lookups at chosen
positions inside it. The three formats use the structures shared with GSUB type 5; see
chapter2.md for their complete layouts and matching rules.

| Format | Pattern given as | Shared structure (chapter2.md) |
|---|---|---|
| 1 | Specific glyph IDs | SequenceContextFormat1 (Sequence context format 1: simple glyph contexts) |
| 2 | Glyph classes from one ClassDef | SequenceContextFormat2 (Sequence context format 2: class-based glyph contexts) |
| 3 | One Coverage table per position | SequenceContextFormat3 (Sequence context format 3: coverage-based glyph contexts) |

- Each action is a SequenceLookupRecord: sequenceIndex (0-based position in the input
  sequence) and lookupListIndex. In GPOS the index points into the GPOS LookupList, so the
  actions are always positioning lookups.
- Formats 1 and 2 may define many patterns; format 3 defines exactly one.
- In format 2 each glyph belongs to exactly one class; in format 3 a glyph may appear in
  several Coverage tables, and one Coverage table may serve several positions.
- chapter2.md also states that, for format 1, a mismatch between the rule-set count and the
  number of covered glyphs is tolerated: the surplus is ignored.

## Lookup type 8: chained contexts positioning

Like type 7, but each rule may also require a backtrack sequence before the input sequence
and a lookahead sequence after it. The formats use the structures shared with GSUB type 6;
see chapter2.md.

| Format | Pattern given as | Shared structure (chapter2.md) |
|---|---|---|
| 1 | Specific glyph IDs | ChainedSequenceContextFormat1 (Chained sequence context format 1: simple glyph contexts) |
| 2 | Glyph classes; separate ClassDefs for backtrack, input and lookahead | ChainedSequenceContextFormat2 (Chained sequence context format 2: class-based glyph contexts) |
| 3 | Coverage tables; separate arrays for backtrack, input and lookahead | ChainedSequenceContextFormat3 (Chained sequence context format 3: coverage-based glyph contexts) |

- Positioning actions may target only glyphs of the input sequence, never the backtrack or
  lookahead glyphs.
- Backtrack sequences are stored in reverse logical order: entry 0 is the glyph immediately
  before the input sequence.
- After a match, processing resumes right after the input sequence; the lookahead glyphs are
  not passed over.
- Lookup flags apply to backtrack and lookahead matching as well as to the input.
- As for type 7 format 1, chapter2.md tolerates a format 1 rule-set count that differs from
  the number of covered glyphs; the surplus is ignored.

## Lookup type 9: positioning extension (PosExtensionFormat1)

Lets a lookup reach a subtable through a 32-bit offset, needed when the subtables grow beyond
what 16-bit offsets elsewhere in GPOS can address. The subtable at the 32-bit offset is the
"extension" subtable. Only one format exists.

PosExtensionFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Set to 1. |
| uint16 | extensionLookupType | Lookup type of the extension subtable; any value except 9. |
| Offset32 | extensionOffset | 32-bit offset to the extension subtable, from start of this PosExtensionFormat1 subtable. |

Rules:

1. extensionLookupType must not be 9. Within one lookup, every extension subtable has the
   same extensionLookupType.
2. A layout engine treats a type 9 lookup as if its lookupType were the extensionLookupType
   of its subtables.
3. It also treats each extension subtable as if it stood in place of the type 9 subtable
   that points to it; offsets inside the extension subtable are relative to the extension
   subtable itself, as for any subtable.

## What each lookup type acts on

| Type | Current glyph | Other glyphs involved | What may change |
|---|---|---|---|
| 1 | A covered glyph | None | That glyph's placement and advance. |
| 2 | A covered first glyph | The next glyph after flag skipping | Placement and advance of either glyph or both. |
| 3 | Two adjacent glyphs: one with an exit anchor, the next with an entry anchor | - | Advance of the first; cross-stream placement of one of them. |
| 4 | A covered mark | Preceding base glyph | The mark's placement only. |
| 5 | A covered mark | Preceding ligature and the mark's recorded component | The mark's placement only. |
| 6 | A covered mark (mark1) | Preceding glyph after flag skipping (mark2) | mark1's placement only. |
| 7 | First glyph of the input sequence | Rest of the input sequence | Input glyphs, through nested lookups only. |
| 8 | First glyph of the input sequence | Input, backtrack and lookahead sequences | Input glyphs, through nested lookups only. |
| 9 | As for extensionLookupType | - | As for extensionLookupType. |

## Consistency requirements and invalid data

The source states these requirements but gives no recovery behaviour for data that breaks
them:

- SinglePosFormat2.valueCount equals the number of glyphs in its Coverage table.
- pairSetOffsets, entryExitRecords, baseRecords, ligatureAttachOffsets, mark2Records and
  markRecords each have one entry per glyph of the corresponding Coverage table, in Coverage
  Index order.
- class1Count and class2Count count every class including 0, and every Class1 record holds
  class2Count Class2 records.
- Each MarkRecord states its class; per-class anchor arrays have markClassCount entries.
- extensionLookupType is not 9 and is the same for all extension subtables of a lookup.
- Reserved ValueFormat bits (0xFF00) are zero.

The source gives no rule for a mark class value of markClassCount or more, for a class value
of class1Count or class2Count or more, for a ligature component number outside
0 .. componentCount - 1, or for a mark with no recorded component.
