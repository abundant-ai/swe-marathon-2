# vhea - Vertical Header Table
Source: vhea - Vertical header table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/vhea
These notes restate the source's structures and rules; where they differ, the source governs.

## Overview

- 'vhea' holds font-wide values for vertical layout, as used by Chinese, Japanese, Korean and other ideographic scripts set top-to-bottom or bottom-to-top. Per-glyph values live in 'vmtx' (see vmtx.md). The pair mirrors 'hhea' and 'hmtx' (see hhea.md, hmtx.md).
- The two tables must agree: the source requires the advance heights and top sidebearings in 'vmtx' to correspond with the maximum advance height and the minimum bottom sidebearing given here, and each of advanceHeightMax, minTopSideBearing and minBottomSideBearing must be consistent with the 'vmtx' entries.
- The source's OpenType CJK Font Guidelines section (not digested) covers building CJK fonts.

## Versions

Two versions exist. Both are 36 bytes long and share one layout; only the meaning and names of the three fields at offsets 4, 6 and 8 differ.

| Version | version field value |
|---|---|
| 1.0 | 0x00010000 |
| 1.1 | 0x00011000 (minor half 0x1000, not 0x0001) |

| Offset | Version 1.0 name | Version 1.1 name |
|---|---|---|
| 4 | ascent | vertTypoAscender |
| 6 | descent | vertTypoDescender |
| 8 | lineGap | vertTypoLineGap |

The source's summary list calls the two version 1.0 fields "ascender" and "descender", while its version 1.0 table names them ascent and descent.

The source's layout tables print three names broken over two lines (minTop SideBearing, minBottom SideBearing, numOf LongVerMetrics). The names are minTopSideBearing, minBottomSideBearing and numOfLongVerMetrics, as the source's example table spells them.

### VheaHeader, version 1.0

The Offset column is the byte offset from the start of the table, derived from the field sizes.

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | Version16Dot16 | version | 0x00010000 for version 1.0. |
| 4 | FWORD | ascent | Distance, in design units, from the centerline to the descent of the previous line. |
| 6 | FWORD | descent | Distance, in design units, from the centerline to the ascent of the next line. |
| 8 | FWORD | lineGap | Reserved; 0. |
| 10 | UFWORD | advanceHeightMax | Largest advance height in the font, design units; must agree with 'vmtx'. |
| 12 | FWORD | minTopSideBearing | Smallest top sidebearing in the font, design units; must agree with 'vmtx'. |
| 14 | FWORD | minBottomSideBearing | Smallest bottom sidebearing in the font, design units; must agree with 'vmtx'. |
| 16 | FWORD | yMaxExtent | `yMaxExtent = max(tsb + (yMax - yMin))`. |
| 18 | int16 | caretSlopeRise | Numerator of the caret slope; see "Caret". |
| 20 | int16 | caretSlopeRun | Denominator of the caret slope; 1 for vertical fonts that are not slanted. |
| 22 | int16 | caretOffset | How far the highlight on slanted glyphs is moved away from the glyph for best appearance; 0 for fonts that are not slanted. |
| 24 | int16 | reserved | 0. |
| 26 | int16 | reserved | 0. |
| 28 | int16 | reserved | 0. |
| 30 | int16 | reserved | 0. |
| 32 | int16 | metricDataFormat | 0. |
| 34 | uint16 | numOfLongVerMetrics | Count of advance heights (full entries) in 'vmtx'. |

### VheaHeader, version 1.1

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | Version16Dot16 | version | 0x00011000 for version 1.1. |
| 4 | FWORD | vertTypoAscender | Vertical typographic ascender: how far the right edge of the ideographic em box (the design space of CJK and other ideographic glyphs) lies from the vertical center baseline, in design units. Normally unitsPerEm / 2 (500 for a 1000-unit em). |
| 6 | FWORD | vertTypoDescender | Vertical typographic descender: offset of the left edge of that em box from the vertical center baseline. Normally -(unitsPerEm / 2) (-500 for a 1000-unit em). |
| 8 | FWORD | vertTypoLineGap | Vertical typographic line gap. Default single-spaced vertical line spacing = ideographic em box width + vertTypoLineGap. |
| 10 | UFWORD | advanceHeightMax | Largest advance height in the font, design units; must agree with 'vmtx'. |
| 12 | FWORD | minTopSideBearing | Smallest top sidebearing in the font, design units; must agree with 'vmtx'. |
| 14 | FWORD | minBottomSideBearing | Smallest bottom sidebearing in the font, design units; must agree with 'vmtx'. |
| 16 | FWORD | yMaxExtent | `yMaxExtent = max(tsb + (yMax - yMin))`. |
| 18 | int16 | caretSlopeRise | Numerator of the caret slope; see "Caret". |
| 20 | int16 | caretSlopeRun | Denominator of the caret slope; 1 for vertical fonts that are not slanted. |
| 22 | int16 | caretOffset | How far the highlight on slanted glyphs is moved away from the glyph for best appearance; 0 for fonts that are not slanted. |
| 24 | int16 | reserved | 0. |
| 26 | int16 | reserved | 0. |
| 28 | int16 | reserved | 0. |
| 30 | int16 | reserved | 0. |
| 32 | int16 | metricDataFormat | 0. |
| 34 | uint16 | numOfLongVerMetrics | Count of advance heights (full entries) in 'vmtx'. |

In yMaxExtent, tsb is a glyph's top side bearing and yMin/yMax its vertical bounds. The ideographic em box is described in the baseline tags section of the OpenType Layout Tag Registry (not digested).

## Caret

- Slope = caretSlopeRise / caretSlopeRun.
- Rise 0 with run 1 gives a horizontal caret; rise 1 with run 0 gives a vertical caret. Oblique or italic designs use values in between.
- For a vertical font a horizontal caret works best, hence rise 0 and run 1 when the glyphs are not slanted.
- caretOffset shifts the highlight drawn on slanted glyphs away from them; non-slanted fonts store 0.

## Variable fonts

Instance-specific values come from the metrics variations table (see mvar.md), keyed by these value tags:

| 'vhea' entry | Tag |
|---|---|
| ascent, vertTypoAscender | 'vasc' |
| caretOffset | 'vcof' |
| caretSlopeRun | 'vcrn' |
| caretSlopeRise | 'vcrs' |
| descent, vertTypoDescender | 'vdsc' |
| lineGap, vertTypoLineGap | 'vlgp' |

## Example in the source

The source closes with a sample version 1.1 header (2048-unit em: vertTypoAscender 1024, vertTypoDescender -1024, numOfLongVerMetrics 258), not repeated here. Its offset/length column gives the first reserved field as 24/4; the field is an int16, so it is 2 bytes long, which matches the next field starting at 26.
