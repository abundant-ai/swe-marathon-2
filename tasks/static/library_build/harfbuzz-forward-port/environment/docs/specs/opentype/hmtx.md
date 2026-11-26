# hmtx - Horizontal Metrics Table
Source: hmtx - Horizontal metrix table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/hmtx
These notes restate the source's structures and rules; where they differ, the source governs.

## Role of the table

Horizontal glyph metrics are the advance width, the side bearings and the horizontal extent (xMin, xMax). 'hmtx' supplies advance widths and left side bearings; the extent comes from the outline data ('glyf', 'CFF ' or CFF2).

- TrueType outlines: 'glyf' records xMin and xMax per glyph but no advance or side bearing. The advance width is always read from 'hmtx'. Whether a glyph's left side bearing equals its xMin depends on bit 1 of the 'head' flags (see head.md), which is why 'hmtx' stores it. The right side bearing is always computed from the 'hmtx' advance and left side bearing plus the glyph's bounding box.
- TrueType variable fonts: the 'hmtx' left side bearing must equal xMin and 'head' flags bit 1 must be set, so the default-instance value can also be read from 'glyf'. These values hold only for the default instance. For other instances, take the side bearings from the interpolated phantom points (see gvar.md) or apply HVAR deltas (see hvar.md) to the default values from 'glyf' or 'hmtx'.
- CFF version 1 outlines: 'CFF ' stores advance widths for PostScript processors, but OpenType layout does not use them; 'hmtx' is required and its advances are the ones to use. Fonts in a collection that share one 'CFF ' table may each give a glyph ID a different advance in their own 'hmtx'.
- CFF2 stores no advance widths. Neither CFF nor CFF2 has explicit xMin/xMax values; the side bearings are implicit in the CharStrings and come from the CFF/CFF2 rasterizer. Because some layout engines read the 'hmtx' left side bearings anyway, font tools should keep them equal to the xMin implied by the CharStrings.
- CFF2 variable fonts: for a non-default instance, combine 'hmtx' with HVAR to get the advance width and left side bearing.

## Table layout

Horizontal Metrics Table:

| Type | Name | Description |
|---|---|---|
| LongHorMetric | hMetrics[numberOfHMetrics] | One advance-width/left-side-bearing pair per glyph, indexed by glyph ID. |
| FWORD | leftSideBearings[numGlyphs - numberOfHMetrics] | Left side bearings of the glyphs whose ID is numberOfHMetrics or higher. |

LongHorMetric Record (4 bytes):

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | UFWORD | advanceWidth | Horizontal advance of the glyph (design units). |
| 2 | FWORD | lsb | The glyph's left side bearing (design units). |

- numberOfHMetrics is read from the 'hhea' table (see hhea.md); numGlyphs is read from the 'maxp' table.
- The table has no header of its own; the hMetrics array starts at offset 0 and leftSideBearings follows it directly.

## Metrics for a glyph ID

The record count may be smaller than the glyph count. This saves space in monospaced fonts and in fonts where many glyphs share one advance width, provided those glyphs are placed at the end of the glyph order.

1. Let n = numberOfHMetrics and g = the glyph ID.
2. If g < n: the advance width is hMetrics[g].advanceWidth and the left side bearing is hMetrics[g].lsb.
3. Otherwise: the advance width is hMetrics[n - 1].advanceWidth (the last record's advance covers every later glyph), and the left side bearing is leftSideBearings[g - n].

The leftSideBearings array has numGlyphs - n entries. The source does not say what to do when numberOfHMetrics is 0 or larger than numGlyphs.

## Derived values

- Right side bearing: `rsb = aw - (lsb + xMax - xMin)`, where aw is the advance width and lsb the left side bearing.
- TrueType phantom points used to control the side bearings start at these x positions: `pp1 = xMin - lsb` and `pp2 = pp1 + aw`.
- With TrueType outlines, aw and lsb can come either from the phantom points computed by the rasterizer or from 'hmtx'; xMin and xMax come from 'glyf'. With CFF or CFF2 outlines, xMin (which equals the left side bearing) and xMax come from the rasterizer.
- A glyph with no contours has no defined xMin or xMax; its 'hmtx' left side bearing should be 0.
