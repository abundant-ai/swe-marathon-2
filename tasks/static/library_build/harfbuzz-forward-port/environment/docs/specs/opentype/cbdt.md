# CBDT - Color Bitmap Data Table
Source: CBDT - Color Bitmap Data Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/cbdt
These notes restate the source's structures and rules; where they differ, the source governs.

## Role

CBDT holds the image data of color bitmap glyphs. It is always used with CBLC (see
cblc.md), which says where each glyph's data starts, how long it is, and which image format
it uses. CBDT/CBLC extend the EBDT/EBLC tables for monochrome and grayscale bitmaps in a
backward compatible way.

## CbdtHeader

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | 3 for CBDT. |
| uint16 | minorVersion | 0. |

Version 3.0 is the first CBDT version.

After the header the table is a pool of glyph image records. Nothing in CBDT says which
format a record has: the imageFormat field of the CBLC index subtable that covers the glyph
does. Some formats begin with glyph metrics and others contain only image data (their
metrics are in CBLC). Records need only byte alignment; 4-byte alignment is not required.

## Uncompressed color bitmaps (bitDepth 32)

- A BitmapSize record in CBLC with bitDepth 32 marks a color strike whose pixels are four
  bytes each, stored in the order blue, green, red, alpha (8 bits per channel).
- The color channels are premultiplied by alpha and are in the sRGB color space
  (IEC 61966-2-1:1999/Amd 1:2003). For instance a pure green pixel at 50% alpha is stored
  as the bytes 0x00 0x80 0x00 0x80, not 0x00 0xFF 0x00 0x80.
- Every bitmap image format defined for EBDT/EBLC may also be used in CBDT/CBLC.

## Compressed color bitmaps (PNG)

- A glyph image may be a complete PNG stream (ISO/IEC 15948), carried by formats 17, 18
  and 19 below.
- Only these PNG chunks are permitted: IHDR, PLTE, tRNS, sRGB, IDAT, IEND. Any other chunk
  makes the behaviour undefined.
- The image is to be treated as sRGB whatever color information other chunks may carry.
- The PNG's pixel width and height must equal the width and height given in the glyph's
  metrics.

## Glyph metrics records

Big metrics carry both horizontal and vertical layout metrics (needed by fonts used in both
directions, such as CJK fonts). Small metrics carry one direction only; which one is chosen
by the flags field of the strike's BitmapSize record in CBLC (HORIZONTAL_METRICS or
VERTICAL_METRICS).

BigGlyphMetrics record (8 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | height | Bitmap height in rows. |
| uint8 | width | Bitmap width in columns. |
| int8 | horiBearingX | Horizontal layout: x distance from the origin to the bitmap's left edge, pixels. |
| int8 | horiBearingY | Horizontal layout: y distance from the origin to the bitmap's top edge, pixels. |
| uint8 | horiAdvance | Horizontal advance, pixels. |
| int8 | vertBearingX | Vertical layout: x distance from the vertical origin to the bitmap's left edge, pixels. |
| int8 | vertBearingY | Vertical layout: y distance from the vertical origin to the bitmap's top edge, pixels. |
| uint8 | vertAdvance | Vertical advance, pixels. |

SmallGlyphMetrics record (5 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | height | Bitmap height in rows. |
| uint8 | width | Bitmap width in columns. |
| int8 | bearingX | Horizontal strike: origin to left edge. Vertical strike: vertical origin to top edge. Pixels. |
| int8 | bearingY | Horizontal strike: origin to top edge. Vertical strike: vertical origin to left edge. Pixels. |
| uint8 | advance | Advance in the strike's direction, pixels. |

## Glyph bitmap data formats

EBDT defines nine glyph image formats (summarized at the end of this file); CBDT accepts
all of them and adds three PNG formats. The type names smallGlyphMetrics and
bigGlyphMetrics below refer to the SmallGlyphMetrics and BigGlyphMetrics records.

### Format 17: small metrics, PNG image data

GlyphBitmapFormat17 table:

| Type | Name | Description |
|---|---|---|
| smallGlyphMetrics | glyphMetrics | The glyph's metrics (one direction). |
| uint32 | dataLen | Byte length of the PNG data. |
| uint8 | data[dataLen] | The PNG stream. |

### Format 18: big metrics, PNG image data

GlyphBitmapFormat18 table:

| Type | Name | Description |
|---|---|---|
| bigGlyphMetrics | glyphMetrics | The glyph's metrics (both directions). |
| uint32 | dataLen | Byte length of the PNG data. |
| uint8 | data[dataLen] | The PNG stream. |

### Format 19: metrics in CBLC table, PNG image data

GlyphBitmapFormat19 table:

| Type | Name | Description |
|---|---|---|
| uint32 | dataLen | Byte length of the PNG data. |
| uint8 | data[dataLen] | The PNG stream. |

Format 19 records have no metrics of their own; the metrics come from the CBLC index
subtable that covers the glyph (index formats 2 and 5 carry a shared BigGlyphMetrics).

## Scaling

Strikes exist only at the sizes stored. When a different size is requested, how the image
is scaled is up to the application; the source prefers scaling down from the nearest strike
that is larger than the target size.

## Image formats inherited from EBDT

The source keeps the EBDT image formats by reference; the EBDT page is not among these notes, so they are not
restated here.
