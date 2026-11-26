# CBLC - Color Bitmap Location Table
Source: CBLC - Color Bitmap Location Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/cblc
These notes restate the source's structures and rules; where they differ, the source governs.

## Role

CBLC tells a reader where each glyph's color bitmap lives inside the CBDT table (see
cbdt.md) for each bitmap strike (one strike per pixel size). CBLC/CBDT are a compatible
extension of EBLC/EBDT, the tables for monochrome and grayscale embedded bitmaps: a CBLC
table is laid out exactly like an EBLC table, except for its version number and one extra
bitDepth value. Everything the source does not restate is inherited from EBLC; the
EBLC layouts that a reader needs are summarized at the end of this file.

## CblcHeader

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | 3 for CBLC. |
| uint16 | minorVersion | 0. |
| uint32 | numSizes | Count of BitmapSize records (strikes). |
| BitmapSize | bitmapSizes[numSizes] | One record per strike. |

Version 3.0 is the first CBLC version (EBLC tables use major version 2).

## BitmapSize record

One BitmapSize record describes one strike.

| Type | Name | Description |
|---|---|---|
| Offset32 | indexSubtableListOffset | Offset from the start of the CBLC table to this strike's IndexSubtableList. |
| uint32 | indexSubtableListSize | Byte length of the IndexSubtableList together with all index subtables it refers to. |
| uint32 | numberOfIndexSubtables | Number of index subtables (one per glyph range or change of format). |
| uint32 | colorRef | Unused; 0. |
| SbitLineMetrics | hori | Line metrics used for horizontal text. |
| SbitLineMetrics | vert | Line metrics used for vertical text. |
| uint16 | startGlyphIndex | Smallest glyph ID present in this strike. |
| uint16 | endGlyphIndex | Largest glyph ID present in this strike. |
| uint8 | ppemX | Horizontal size of the strike, in pixels per em. |
| uint8 | ppemY | Vertical size of the strike, in pixels per em. |
| uint8 | bitDepth | 1, 2, 4 or 8 as in EBLC (monochrome and grayscale), or 32 for color bitmaps whose pixels are BGRA with 8 bits per channel. |
| int8 | flags | Bitmap flags saying whether the strike's metrics are horizontal or vertical (EBLC bitmap flags, listed below). |

Rules:

- Each strike has its own IndexSubtableList, found at indexSubtableListOffset from the
  start of CBLC; indexSubtableListSize covers the list plus every index subtable.
- A strike is split into several index subtables when its glyphs fall into separate ranges
  or need different index or image formats.
- Each index subtable locates, inside CBDT, the image data of one or more glyphs, and can
  also hold metrics shared by those glyphs.
- bitDepth 32 marks a color strike; the pixel encoding is described in cbdt.md.

## Structures inherited from EBLC

The source defines these by reference to the EBLC table: the line metrics records, the bitmap flags, the
index subtable list and records, and the index subtable formats. The EBLC page is not among these notes, so those
structures are not restated here.
