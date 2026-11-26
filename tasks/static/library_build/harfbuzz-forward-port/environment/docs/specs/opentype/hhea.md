# hhea - Horizontal Header Table
Source: hhea - Horizontal header table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/hhea
These notes restate the source's structures and rules; where they differ, the source governs.

The 'hhea' table holds font-wide values for horizontal layout; per-glyph values are in 'hmtx' (see hmtx.md). minLeftSideBearing, minRightSideBearing and xMaxExtent are computed over glyphs that have contours only; glyphs without contours are left out. Every reserved field must be 0.

## Table layout

The Offset column is the byte offset from the start of the table, derived from the field sizes (36 bytes in total).

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | majorVersion | Major version of the table; 1. |
| 2 | uint16 | minorVersion | Minor version of the table; 0. |
| 4 | FWORD | ascender | Typographic ascent; see "Line metrics". |
| 6 | FWORD | descender | Typographic descent; see "Line metrics". |
| 8 | FWORD | lineGap | Typographic line gap. Some legacy platforms treat a negative value as 0. |
| 10 | UFWORD | advanceWidthMax | Largest advance width found in 'hmtx'. |
| 12 | FWORD | minLeftSideBearing | Smallest left side bearing in 'hmtx', over glyphs with contours. |
| 14 | FWORD | minRightSideBearing | Smallest right side bearing over glyphs with contours: `min(aw - (lsb + xMax - xMin))`. |
| 16 | FWORD | xMaxExtent | `max(lsb + (xMax - xMin))`. |
| 18 | int16 | caretSlopeRise | Rise part of the caret (cursor) slope, rise/run; 1 for an upright caret. |
| 20 | int16 | caretSlopeRun | Run part of the caret slope; 0 for an upright caret. |
| 22 | int16 | caretOffset | Shift that makes a slanted highlight look best; 0 for fonts that are not slanted. |
| 24 | int16 | (reserved) | 0 |
| 26 | int16 | (reserved) | 0 |
| 28 | int16 | (reserved) | 0 |
| 30 | int16 | (reserved) | 0 |
| 32 | int16 | metricDataFormat | 0, the current format. |
| 34 | uint16 | numberOfHMetrics | Count of hMetric (LongHorMetric) entries in 'hmtx'. |

In the formulas, aw is the advance width, lsb the left side bearing, and xMin/xMax the glyph's horizontal bounds.

## Caret

- The caret slope is caretSlopeRise / caretSlopeRun. An upright caret uses rise 1 and run 0.
- caretOffset moves the highlight drawn over slanted glyphs so that it looks right; non-slanted fonts store 0.

## Line metrics

- ascender, descender and lineGap here follow Apple's definitions; Apple's specification describes their use on Apple platforms.
- Windows uses sTypoAscender, sTypoDescender and sTypoLineGap from the OS/2 table instead, and those OS/2 fields are the ones advised for new text-layout code (see os2.md, which also says that a variable font should give these three 'hhea' fields the same values as the OS/2 sTypo fields).
- Applications differ in which table they read, so a font's line spacing can depend on the application.

## Variable fonts

Instance-specific values for some fields come from the metrics variations table (see mvar.md), keyed by these value tags:

| 'hhea' entry | Tag |
|---|---|
| caretOffset | 'hcof' |
| caretSlopeRise | 'hcrs' |
| caretSlopeRun | 'hcrn' |
