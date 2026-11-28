# 'ankr' table: anchor points (digest)
Source: Anchor Point Table - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6ankr.html
These notes restate the source's structures and rules; where they differ, the source governs.

## Purpose

'ankr' gives glyphs anchor points: positions in the glyph's coordinate space
that are independent of the outline's control points. They are consumed by
'kerx' format 4 subtables whose action type is 1 (anchor point numbers); see
Chap6kerx.md. Without an 'ankr' table, 'kerx' treats the 'glyf' outline
points as the anchor points.

## Header

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | version | 0 |
| 2 | uint16 | flags | unused, 0 |
| 4 | uint32 | lookupTableOffset | offset to the lookup table; currently always 0x0000000C (it follows the header) |
| 8 | uint32 | glyphDataTableOffset | offset to the glyph data table |

## Lookup table

- A standard AAT lookup table keyed by glyph ID.
- Each value is a 16-bit offset from the start of the glyph data table to
  that glyph's anchor data.
- Offset 0 is a valid value, so glyphs that have no anchor points must be
  left out of the lookup entirely.

## Glyph data table

A sequence of entries, one per glyph that has anchor points:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | numPoints | number of anchor points of this glyph |
| 4 | point[numPoints] | anchorPoints | each point is int16 x followed by int16 y (4 bytes) |

Anchor point n of a glyph is element n of its anchorPoints array; 'kerx'
format 4 anchor actions refer to these indices.

## Availability

OS X 10.9 and later; iOS 7.0 and later.
