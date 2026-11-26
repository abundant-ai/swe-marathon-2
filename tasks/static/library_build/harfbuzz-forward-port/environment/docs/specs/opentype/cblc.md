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

The source page defines only the two structures above and states that every other detail
is the same as in the EBLC chapter. The EBLC chapter is not one of these digests; this
section summarizes its layouts so that a CBLC table can be read end to end.

### SbitLineMetrics record (12 bytes)

| Type | Name | Description |
|---|---|---|
| int8 | ascender | Distance from baseline to top of line, pixels. |
| int8 | descender | Distance from baseline to bottom of line, pixels (negative below the baseline). |
| uint8 | widthMax | Largest glyph width in the strike. |
| int8 | caretSlopeNumerator | Rise of the caret slope. |
| int8 | caretSlopeDenominator | Run of the caret slope. |
| int8 | caretOffset | Caret offset, pixels. |
| int8 | minOriginSB | Smallest origin-side bearing. |
| int8 | minAdvanceSB | Smallest advance-side bearing. |
| int8 | maxBeforeBL | Largest extent before the baseline. |
| int8 | minAfterBL | Smallest extent after the baseline. |
| int8 | pad1 | Padding. |
| int8 | pad2 | Padding. |

### Bitmap flags (BitmapSize.flags)

| Mask | Name | Meaning |
|---|---|---|
| 0x01 | HORIZONTAL_METRICS | Small metrics in this strike are horizontal. |
| 0x02 | VERTICAL_METRICS | Small metrics in this strike are vertical. |
| 0xFC | Reserved | Set to 0. |

### IndexSubtableList and IndexSubtableRecord

The IndexSubtableList is an array of numberOfIndexSubtables IndexSubtableRecords.

| Type | Name | Description |
|---|---|---|
| uint16 | firstGlyphIndex | First glyph ID of the range. |
| uint16 | lastGlyphIndex | Last glyph ID of the range (inclusive). |
| Offset32 | indexSubtableOffset | Offset from the start of the IndexSubtableList to the index subtable for this range. |

### IndexSubHeader (start of every index subtable)

| Type | Name | Description |
|---|---|---|
| uint16 | indexFormat | Index subtable format, 1 to 5. |
| uint16 | imageFormat | Format of the glyph image data in CBDT (EBDT formats, or 17, 18, 19). |
| Offset32 | imageDataOffset | Offset from the start of the CBDT table to the image data of this range. |

### Index subtable formats

| indexFormat | Layout after the IndexSubHeader | Use |
|---|---|---|
| 1 | Offset32 sbitOffsets[lastGlyphIndex - firstGlyphIndex + 2] | Every glyph in the range; per-glyph offsets, 4 bytes. |
| 2 | uint32 imageSize; BigGlyphMetrics bigMetrics | Every glyph in the range; all images the same size and all glyphs share these metrics. |
| 3 | Offset16 sbitOffsets[lastGlyphIndex - firstGlyphIndex + 2] | Like format 1 with 2-byte offsets. |
| 4 | uint32 numGlyphs; GlyphIdOffsetPair glyphArray[numGlyphs + 1] | Sparse glyph IDs with per-glyph offsets. |
| 5 | uint32 imageSize; BigGlyphMetrics bigMetrics; uint32 numGlyphs; uint16 glyphIdArray[numGlyphs] | Sparse glyph IDs (sorted), same size and shared metrics. |

GlyphIdOffsetPair record:

| Type | Name | Description |
|---|---|---|
| uint16 | glyphID | Glyph ID. |
| Offset16 | sbitOffset | Offset of the glyph's data, relative to imageDataOffset. |

BigGlyphMetrics is defined in cbdt.md.

### Locating one glyph's image

1. Choose a strike (BitmapSize) by pixel size; glyph IDs outside
   startGlyphIndex..endGlyphIndex are not in the strike.
2. In that strike's IndexSubtableList, find the IndexSubtableRecord whose
   firstGlyphIndex..lastGlyphIndex range contains the glyph, and read the IndexSubHeader at
   IndexSubtableList start + indexSubtableOffset.
3. Compute the start and length of the glyph's data:
   - format 1 or 3: i = glyph - firstGlyphIndex; start = imageDataOffset + sbitOffsets[i];
     length = sbitOffsets[i + 1] - sbitOffsets[i]. A length of 0 means the glyph has no image.
   - format 2: start = imageDataOffset + i * imageSize; length = imageSize; metrics come from
     bigMetrics.
   - format 4: find k with glyphArray[k].glyphID == glyph (the extra last pair only closes
     the final length); start = imageDataOffset + glyphArray[k].sbitOffset;
     length = glyphArray[k + 1].sbitOffset - glyphArray[k].sbitOffset.
   - format 5: find k with glyphIdArray[k] == glyph; start = imageDataOffset + k * imageSize;
     length = imageSize; metrics come from bigMetrics.
4. Decode the bytes at that position in CBDT according to imageFormat (see cbdt.md).
