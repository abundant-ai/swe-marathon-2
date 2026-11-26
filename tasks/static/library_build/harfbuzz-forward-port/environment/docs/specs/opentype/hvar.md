# HVAR - Horizontal Metrics Variations Table
Source: HVAR - Horizontal Metrics Variations Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/hvar
These notes restate the source's structures and rules; where they differ, the source governs.

## Role

- HVAR supplies variation data for horizontal glyph metrics: advance widths from 'hmtx' and,
  in fonts with TrueType outlines, left and right side bearings (derived from 'hmtx' and the
  glyph bounding boxes).
- It appears only in variable fonts and must be accompanied by 'hmtx', 'fvar' and the other
  tables variable fonts need.
- TrueType outlines: the 'gvar' phantom points already vary the metrics (gvar.md), so HVAR is
  optional. It is still recommended, because layout can then get varied metrics without
  varying any outline.
- CFF2 outlines: there are no phantom points, so HVAR is required whenever any advance width
  changes across the variation space.
- In a variable font with TrueType outlines, each glyph's left side bearing must equal its
  xMin and bit 1 of the 'head' flags must be set (head.md, hmtx.md).
- 'hdmx' is not used in variable fonts.
- The deltas live in an ItemVariationStore (otvarcommonformats.md), the same structure VVAR
  and GDEF use; it is unrelated to the tuple variation store of 'gvar' and 'cvar'. VVAR plays
  the same role for vertical metrics.

## Table

Horizontal metrics variations table:

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; 1. |
| uint16 | minorVersion | Minor version; 0. |
| Offset32 | itemVariationStoreOffset | From the start of HVAR to its ItemVariationStore. |
| Offset32 | advanceWidthMappingOffset | From the start of HVAR to the DeltaSetIndexMap for advance widths; NULL when there is none. |
| Offset32 | lsbMappingOffset | From the start of HVAR to the DeltaSetIndexMap for left side bearings; NULL when there is none. |
| Offset32 | rsbMappingOffset | From the start of HVAR to the DeltaSetIndexMap for right side bearings; NULL when there is none. |

The header is 20 bytes. All four offsets count from the first byte of the HVAR table.

## Mapping subtables

- A mapping subtable is a DeltaSetIndexMap (otvarcommonformats.md, DeltaSetIndexMap). HVAR
  uses format 0 only.
- Each mapping subtable is optional; a missing one has a NULL (zero) offset.
- Advance widths: variation data must exist, but its mapping subtable is optional. Without
  it, glyph IDs act as implicit delta-set indices: outer index 0, inner index = glyph ID, so
  ItemVariationData subtable 0 is addressed directly by glyph ID.
- With an advance map, glyphs whose advances vary identically can share one delta set, which
  shrinks the store; including the map is generally recommended.
- Side bearings: variation data is optional. When it is present, mapping subtables are
  required; side bearings have no implicit glyph-ID mapping. Side-bearing data should cover
  both left and right side bearings, and then both lsbMappingOffset and rsbMappingOffset must
  be non-NULL.

## Finding a glyph's deltas

Advance width of glyph g:

1. If advanceWidthMappingOffset is NULL, the delta-set index is outer 0, inner g.
2. Otherwise read entry g of the advance map (an index at or past mapCount uses the last
   entry) and split it into outer and inner indices with the map's entryFormat
   (otvarcommonformats.md).
3. Evaluate that delta set in the ItemVariationStore for the current instance
   (otvarcommonformats.md, Applying an item variation store). An index of (0xFFFF, 0xFFFF), or
   one that selects a NULL subtable, means no variation.
4. Varied advance = default advance from 'hmtx' + the result.

Left or right side bearing of glyph g:

1. If the matching map offset (lsbMappingOffset or rsbMappingOffset) is NULL, HVAR holds no
   variation data for that metric.
2. Otherwise look up entry g of that map as in step 2 above and evaluate the delta set as in
   step 3.
3. Add the result to the default value. Defaults come from 'hmtx' and 'glyf': the left side
   bearing from 'hmtx', and the right side bearing as advance - (lsb + xMax - xMin)
   (hmtx.md).

The delta-set index only addresses a row of the store; each row holds one delta per region,
and the region scalars for the current instance decide how much of each delta applies
(otvarcommonformats.md, Region scalars).
