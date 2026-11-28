# head - Font Header Table
Source: head - Font header table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/head
These notes restate the source's structures and rules; where they differ, the source governs.

The 'head' table carries font-wide values. Its bounding-box fields are computed over glyphs that have contours; a glyph without contours does not contribute to them.

## Table layout

The Offset column is the byte offset from the start of the table, derived from the field sizes (54 bytes in total).

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | majorVersion | Major version of the table; 1. |
| 2 | uint16 | minorVersion | Minor version of the table; 0. |
| 4 | Fixed | fontRevision | Revision number chosen by the font maker. |
| 8 | uint32 | checksumAdjustment | Value that makes the whole-font checksum come out right; see "checksumAdjustment" below. Ignored for a font inside a collection. |
| 12 | uint32 | magicNumber | Constant 0x5F0F3CF5. |
| 16 | uint16 | flags | Font-wide flag bits; see "flags bits" below. |
| 18 | uint16 | unitsPerEm | Design units per em; every value from 16 to 16384 is valid. |
| 20 | LONGDATETIME | created | Creation time, counted in seconds from 1904-01-01 00:00:00 UTC. |
| 28 | LONGDATETIME | modified | Time of last change, same epoch and unit as created. |
| 36 | int16 | xMin | Lowest x over the bounding boxes of all glyphs. |
| 38 | int16 | yMin | Lowest y over the bounding boxes of all glyphs. |
| 40 | int16 | xMax | Highest x over the bounding boxes of all glyphs. |
| 42 | int16 | yMax | Highest y over the bounding boxes of all glyphs. |
| 44 | uint16 | macStyle | Style bits; see "macStyle bits" below. |
| 46 | uint16 | lowestRecPPEM | Smallest size, in pixels per em, at which the font is still legible. |
| 48 | int16 | fontDirectionHint ^a | Deprecated; fonts store 2. Values are listed below. |
| 50 | int16 | indexToLocFormat | Offset size used by 'loca': 0 = short (Offset16), 1 = long (Offset32). |
| 52 | int16 | glyphDataFormat | Glyph data format; 0 is the only current format. |

^a The hint was intended to help RTL support. Each character is strongly LTR, strongly RTL, or neutral. Neutral characters, such as spaces and punctuation, carry no inherent direction (neutral has nothing to do with zero width); Latin letters are strongly LTR and Arabic letters strongly RTL. A typical Latin font that includes spaces and punctuation stores 2.

## flags bits

The source numbers the bits; the masks follow from the bit numbers.

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x0001 | The font's baseline is at y = 0. |
| 1 | 0x0002 | The left sidebearing point is at x = 0 (only TrueType rasterizers care). Variable fonts have extra rules; see below. |
| 2 | 0x0004 | Instructions may behave differently depending on point size. |
| 3 | 0x0008 | All internal scaler math uses ppem rounded to an integer; when the bit is clear, fractional ppem sizes are allowed. Hinted fonts are strongly advised to set it. |
| 4 | 0x0010 | Instructions may change advance widths, so advances may not scale linearly. |
| 5 | 0x0020 | Unused in OpenType; should be clear for consistent behaviour across platforms. Some platforms change vertical layout when it is set (Apple's specification covers Apple's use). Must be clear in every variable font. |
| 6-10 | 0x07C0 | Unused in OpenType; always clear (Apple's specification covers legacy Apple use). |
| 11 | 0x0800 | Font data is "lossless": it passed through an optimizing transform and/or compression (for example ISO/IEC 14496-18, MicroType Express or WOFF 2.0) that keeps the original functionality and features but does not guarantee a byte-identical file. Such a transform can also leave the DSIG table invalid. |
| 12 | 0x1000 | Font has been converted (gives compatible metrics). |
| 13 | 0x2000 | Font is optimized for ClearType. A font that relies on embedded EBDT bitmaps for rendering does not count as ClearType-optimized and keeps this bit clear. |
| 14 | 0x4000 | Last Resort font: the glyphs that 'cmap' maps are generic stand-ins for whole code point ranges and do not mean those code points are really supported. When clear, mapped glyphs do represent real support. |
| 15 | 0x8000 | Reserved; 0. |

## macStyle bits

A set bit means the style applies.

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x0001 | Bold |
| 1 | 0x0002 | Italic |
| 2 | 0x0004 | Underline |
| 3 | 0x0008 | Outline |
| 4 | 0x0010 | Shadow |
| 5 | 0x0020 | Condensed |
| 6 | 0x0040 | Extended |
| 7-15 | 0xFF80 | Reserved; 0. |

- macStyle must agree with the fsSelection field of the OS/2 table (see os2.md): macStyle bit 0 (Bold) pairs with fsSelection bit 5 (BOLD), and macStyle bit 1 (Italic) pairs with fsSelection bit 0 (ITALIC).
- Windows decides bold and italic from fsSelection, not macStyle. PANOSE values and 'post' table values play no part in that decision.

## fontDirectionHint values

The field is deprecated and should hold 2.

| Value | Meaning |
|---|---|
| 0 | Glyphs of mixed directions. |
| 1 | Strongly left-to-right glyphs only. |
| 2 | Strongly left-to-right glyphs plus neutrals. |
| -1 | Strongly right-to-left glyphs only. |
| -2 | Strongly right-to-left glyphs plus neutrals. |

## indexToLocFormat, glyphDataFormat and magicNumber

| Field | Value | Meaning |
|---|---|---|
| indexToLocFormat | 0 | 'loca' uses short offsets (Offset16). |
| indexToLocFormat | 1 | 'loca' uses long offsets (Offset32). |
| glyphDataFormat | 0 | Current glyph data format (the only one defined). |
| magicNumber | 0x5F0F3CF5 | The field always holds this constant. |

The 'loca' chapter itself is not digested here; in its short form each entry holds the real byte offset divided by 2.

## checksumAdjustment

1. Set checksumAdjustment to 0.
2. Add up the entire font file as a sequence of uint32 values, the same way table checksums are formed (see otff.md), keeping the sum in 32 bits.
3. Store `0xB1B0AFBA - sum` (uint32 arithmetic) in checksumAdjustment.

When the font is a member of a font collection file, the file structure and table directory make the stored value meaningless; readers must ignore it in that case.

## Other rules

- unitsPerEm sets the granularity of the design grid on which outline control points and attachment anchors are placed. For TrueType outlines a power of two is advised because some rasterizers run faster with it, but any value in 16..16384 is valid.
- The bounding box of a glyph is the tightest rectangle around all of its control points (see glyf.md). xMin, yMin, xMax and yMax enclose every glyph in the font, ignoring glyphs without contours.
- Windows does not take the font's version from fontRevision; it reads the version string, name ID 5, from the 'name' table.
- The left sidebearing point of a glyph is the first phantom point, pp1 (see hmtx.md): `pp1 = xMin - lsb`.
- When flags bit 1 is set, pp1 = 0 for every glyph, so each glyph's xMin must equal its left side bearing.

## Variable fonts

- With TrueType outlines, every glyph's left side bearing must equal its xMin, and flags bit 1 must be set.
- In every variable font, flags bit 5 must be clear.
- xMin, yMin, xMax and yMax describe the default instance. In another instance a glyph's control points can move, so its tight bounds can grow or shrink; these four fields may or may not enclose the outlines of such an instance, and no variation deltas exist for them. An application that needs bounds for a non-default instance must compute them from that instance's derived outlines.
