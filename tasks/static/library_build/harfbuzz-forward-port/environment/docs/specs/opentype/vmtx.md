# vmtx - Vertical Metrics Table
Source: vmtx - Vertical metrics table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/vmtx
These notes restate the source's structures and rules; where they differ, the source governs.

## Overview

- 'vmtx' gives per-glyph vertical metrics: an advance height and a top side bearing for every glyph, stored in one or two arrays.
- A vertical OpenType font needs both 'vhea' (font-wide values; see vhea.md) and 'vmtx'. The pair mirrors 'hhea' and 'hmtx' (see hhea.md, hmtx.md).
- The source's OpenType CJK Font Guidelines section (not digested) covers building CJK fonts.

## Vertical origin and advance height

- Origin y: a glyph's vertical-origin y equals its top side bearing (from 'vmtx') plus the top of its bounding box (its maximum y): `originY = topSideBearing + yMax`.
- With TrueType outlines the bounding box is in 'glyf'. CFF-based fonts have no stored bounding boxes, so the top of the box must be computed from the CharStrings in 'CFF ' or CFF2. Such fonts may carry the optional VORG table, which records each glyph's vertical-origin y directly and so avoids computing boxes.
- Origin x: 'vmtx' does not define it. Vertical layout code may use the baselines of the BASE table (see base.md), when present, to place glyphs in x for the chosen vertical baseline.
- The advance height starts at the glyph's vertical-origin y and runs downward. By default it ends at the vertical-origin y of the following glyph in the run. Metric-adjusting layout features such as Vertical Kerning ('vkrn') can change vertical advances, much as kerning does horizontally.

## Table layout

The table has no header. The vMetrics array comes first and an optional array of top side bearings follows it. Together the two arrays must cover exactly the number of glyphs in the font. The top side bearing is measured from the top of the glyph's origin, for vertical setting of ideographic glyphs.

Overall order (summary of the two arrays the source describes):

| Type | Name | Description |
|---|---|---|
| (entry below) | vMetrics[numOfLongVerMetrics] | One full entry per glyph for the first numOfLongVerMetrics glyph IDs. |
| FWORD | topSideBearing[numGlyphs - numOfLongVerMetrics] | Top side bearings of the remaining glyphs; may be absent (zero entries). |

numOfLongVerMetrics comes from 'vhea' (see vhea.md). The glyph count is the font's total number of glyphs (numGlyphs in 'maxp').

Entry of the vMetrics array (4 bytes), as given in the source:

| Type | Name | Description |
|---|---|---|
| UFWORD | advanceHeight | Vertical advance of the glyph (design units). |
| FWORD | topSideBearing | The glyph's top side bearing (design units). |

Top side bearing array, as given in the source:

| Type | Name | Description |
|---|---|---|
| FWORD | topSideBearing[] | Top side bearing of one glyph not covered by vMetrics (design units). |

## Rules

- Each vMetrics entry holds two values for its glyph: advance height and top side bearing. The array must hold at least one entry, even in a monospaced font (for example Courier, or a Kanji font) where a single entry is enough because every glyph shares one advance height.
- The second array is optional. It serves one run of monospaced glyphs, which must sit at the end of the font; only one such run is allowed. Its glyphs all have the advance height of the last vMetrics entry, so the array stores only their top side bearings.
- Its length is the number of glyphs in the font minus numOfLongVerMetrics, so the two arrays together account for every glyph.

## Metrics for a glyph ID

1. Let n = numOfLongVerMetrics and g = the glyph ID.
2. If g < n: the advance height is vMetrics[g].advanceHeight and the top side bearing is vMetrics[g].topSideBearing.
3. Otherwise: the advance height is vMetrics[n - 1].advanceHeight, and the top side bearing is element g - n of the second array.
