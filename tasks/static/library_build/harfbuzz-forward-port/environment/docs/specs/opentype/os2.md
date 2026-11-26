# OS/2 - OS/2 and Windows Metrics Table
Source: OS/2 - OS/2 and Windows metrics table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/os2
These notes restate the source's structures and rules; where they differ, the source governs.

The OS/2 table is required in OpenType fonts. It carries font-wide metrics and classification data.

## Versions and sizes

Versions 0 to 5 are defined and all of them remain supported; the source strongly advises version 4 or later for fonts. The sizes below are computed from the field sizes (the source does not list them).

| Version | Defined in | Fields | Size in bytes |
|---|---|---|---|
| 0 | TrueType revision 1.5 | version through usWinDescent | 78 (68 when cut short after usLastCharIndex) |
| 1 | TrueType revision 1.66 | version 0 fields + ulCodePageRange1, ulCodePageRange2 (two more than version 0) | 86 |
| 2 | OpenType 1.1 | version 1 fields + sxHeight, sCapHeight, usDefaultChar, usBreakChar, usMaxContext (five more than version 1) | 96 |
| 3 | OpenType 1.4 | same fields as version 2; some definitions revised for Unicode 3.2 | 96 |
| 4 | OpenType 1.5 | same fields as version 3; some definitions revised | 96 |
| 5 | not stated in this chapter | version 4 fields + usLowerOpticalPointSize, usUpperOpticalPointSize (two more than version 4) | 100 |

Reading rules:

- The version field decides which fields exist.
- Apple's TrueType Reference Manual documents version 0 only up to usLastCharIndex and leaves out the last five fields of Microsoft's version 0 (sTypoAscender, sTypoDescender, sTypoLineGap, usWinAscent, usWinDescent). Some legacy TrueType fonts therefore carry a shortened version 0 table. Check the table length before reading those five fields of a version 0 table.
- Bytes beyond the last field of the table's version are to be ignored: after usWinDescent for version 0, after ulCodePageRange2 for version 1, after usMaxContext for versions 2 to 4.

## Field layouts

In every layout the Offset column is the byte offset from the start of the table, derived from the field sizes.

### Version 5

| Offset | Type | Name | Comments |
|---|---|---|---|
| 0 | uint16 | version | 0x0005 |
| 2 | FWORD | xAvgCharWidth | |
| 4 | uint16 | usWeightClass | |
| 6 | uint16 | usWidthClass | |
| 8 | uint16 | fsType | |
| 10 | FWORD | ySubscriptXSize | |
| 12 | FWORD | ySubscriptYSize | |
| 14 | FWORD | ySubscriptXOffset | |
| 16 | FWORD | ySubscriptYOffset | |
| 18 | FWORD | ySuperscriptXSize | |
| 20 | FWORD | ySuperscriptYSize | |
| 22 | FWORD | ySuperscriptXOffset | |
| 24 | FWORD | ySuperscriptYOffset | |
| 26 | FWORD | yStrikeoutSize | |
| 28 | FWORD | yStrikeoutPosition | |
| 30 | int16 | sFamilyClass | |
| 32 | uint8 | panose[10] | |
| 42 | uint32 | ulUnicodeRange1 | Bits 0-31 |
| 46 | uint32 | ulUnicodeRange2 | Bits 32-63 |
| 50 | uint32 | ulUnicodeRange3 | Bits 64-95 |
| 54 | uint32 | ulUnicodeRange4 | Bits 96-127 |
| 58 | Tag | achVendID | |
| 62 | uint16 | fsSelection | |
| 64 | uint16 | usFirstCharIndex | |
| 66 | uint16 | usLastCharIndex | |
| 68 | FWORD | sTypoAscender | |
| 70 | FWORD | sTypoDescender | |
| 72 | FWORD | sTypoLineGap | |
| 74 | UFWORD | usWinAscent | |
| 76 | UFWORD | usWinDescent | |
| 78 | uint32 | ulCodePageRange1 | Bits 0-31 |
| 82 | uint32 | ulCodePageRange2 | Bits 32-63 |
| 86 | FWORD | sxHeight | |
| 88 | FWORD | sCapHeight | |
| 90 | uint16 | usDefaultChar | |
| 92 | uint16 | usBreakChar | |
| 94 | uint16 | usMaxContext | |
| 96 | uint16 | usLowerOpticalPointSize | |
| 98 | uint16 | usUpperOpticalPointSize | |

### Version 4

Two fields fewer than version 5 and the same fields as version 3; definitions of some fields were revised.

| Offset | Type | Name |
|---|---|---|
| 0 | uint16 | version |
| 2 | FWORD | xAvgCharWidth |
| 4 | uint16 | usWeightClass |
| 6 | uint16 | usWidthClass |
| 8 | uint16 | fsType |
| 10 | FWORD | ySubscriptXSize |
| 12 | FWORD | ySubscriptYSize |
| 14 | FWORD | ySubscriptXOffset |
| 16 | FWORD | ySubscriptYOffset |
| 18 | FWORD | ySuperscriptXSize |
| 20 | FWORD | ySuperscriptYSize |
| 22 | FWORD | ySuperscriptXOffset |
| 24 | FWORD | ySuperscriptYOffset |
| 26 | FWORD | yStrikeoutSize |
| 28 | FWORD | yStrikeoutPosition |
| 30 | int16 | sFamilyClass |
| 32 | uint8 | panose[10] |
| 42 | uint32 | ulUnicodeRange1 |
| 46 | uint32 | ulUnicodeRange2 |
| 50 | uint32 | ulUnicodeRange3 |
| 54 | uint32 | ulUnicodeRange4 |
| 58 | Tag | achVendID |
| 62 | uint16 | fsSelection |
| 64 | uint16 | usFirstCharIndex |
| 66 | uint16 | usLastCharIndex |
| 68 | FWORD | sTypoAscender |
| 70 | FWORD | sTypoDescender |
| 72 | FWORD | sTypoLineGap |
| 74 | UFWORD | usWinAscent |
| 76 | UFWORD | usWinDescent |
| 78 | uint32 | ulCodePageRange1 |
| 82 | uint32 | ulCodePageRange2 |
| 86 | FWORD | sxHeight |
| 88 | FWORD | sCapHeight |
| 90 | uint16 | usDefaultChar |
| 92 | uint16 | usBreakChar |
| 94 | uint16 | usMaxContext |

### Version 3

The source states that the version 3 format is identical to version 4 (and to version 2); only some field definitions were revised, for Unicode 3.2. Written out:

| Offset | Type | Name |
|---|---|---|
| 0 | uint16 | version |
| 2 | FWORD | xAvgCharWidth |
| 4 | uint16 | usWeightClass |
| 6 | uint16 | usWidthClass |
| 8 | uint16 | fsType |
| 10 | FWORD | ySubscriptXSize |
| 12 | FWORD | ySubscriptYSize |
| 14 | FWORD | ySubscriptXOffset |
| 16 | FWORD | ySubscriptYOffset |
| 18 | FWORD | ySuperscriptXSize |
| 20 | FWORD | ySuperscriptYSize |
| 22 | FWORD | ySuperscriptXOffset |
| 24 | FWORD | ySuperscriptYOffset |
| 26 | FWORD | yStrikeoutSize |
| 28 | FWORD | yStrikeoutPosition |
| 30 | int16 | sFamilyClass |
| 32 | uint8 | panose[10] |
| 42 | uint32 | ulUnicodeRange1 |
| 46 | uint32 | ulUnicodeRange2 |
| 50 | uint32 | ulUnicodeRange3 |
| 54 | uint32 | ulUnicodeRange4 |
| 58 | Tag | achVendID |
| 62 | uint16 | fsSelection |
| 64 | uint16 | usFirstCharIndex |
| 66 | uint16 | usLastCharIndex |
| 68 | FWORD | sTypoAscender |
| 70 | FWORD | sTypoDescender |
| 72 | FWORD | sTypoLineGap |
| 74 | UFWORD | usWinAscent |
| 76 | UFWORD | usWinDescent |
| 78 | uint32 | ulCodePageRange1 |
| 82 | uint32 | ulCodePageRange2 |
| 86 | FWORD | sxHeight |
| 88 | FWORD | sCapHeight |
| 90 | uint16 | usDefaultChar |
| 92 | uint16 | usBreakChar |
| 94 | uint16 | usMaxContext |

### Version 2

The source states that the version 2 format is identical to version 4: the same fields as version 3, and five more than version 1. Written out:

| Offset | Type | Name |
|---|---|---|
| 0 | uint16 | version |
| 2 | FWORD | xAvgCharWidth |
| 4 | uint16 | usWeightClass |
| 6 | uint16 | usWidthClass |
| 8 | uint16 | fsType |
| 10 | FWORD | ySubscriptXSize |
| 12 | FWORD | ySubscriptYSize |
| 14 | FWORD | ySubscriptXOffset |
| 16 | FWORD | ySubscriptYOffset |
| 18 | FWORD | ySuperscriptXSize |
| 20 | FWORD | ySuperscriptYSize |
| 22 | FWORD | ySuperscriptXOffset |
| 24 | FWORD | ySuperscriptYOffset |
| 26 | FWORD | yStrikeoutSize |
| 28 | FWORD | yStrikeoutPosition |
| 30 | int16 | sFamilyClass |
| 32 | uint8 | panose[10] |
| 42 | uint32 | ulUnicodeRange1 |
| 46 | uint32 | ulUnicodeRange2 |
| 50 | uint32 | ulUnicodeRange3 |
| 54 | uint32 | ulUnicodeRange4 |
| 58 | Tag | achVendID |
| 62 | uint16 | fsSelection |
| 64 | uint16 | usFirstCharIndex |
| 66 | uint16 | usLastCharIndex |
| 68 | FWORD | sTypoAscender |
| 70 | FWORD | sTypoDescender |
| 72 | FWORD | sTypoLineGap |
| 74 | UFWORD | usWinAscent |
| 76 | UFWORD | usWinDescent |
| 78 | uint32 | ulCodePageRange1 |
| 82 | uint32 | ulCodePageRange2 |
| 86 | FWORD | sxHeight |
| 88 | FWORD | sCapHeight |
| 90 | uint16 | usDefaultChar |
| 92 | uint16 | usBreakChar |
| 94 | uint16 | usMaxContext |

### Version 1

Five fields fewer than version 2 and two more than version 0.

| Offset | Type | Name |
|---|---|---|
| 0 | uint16 | version |
| 2 | FWORD | xAvgCharWidth |
| 4 | uint16 | usWeightClass |
| 6 | uint16 | usWidthClass |
| 8 | uint16 | fsType |
| 10 | FWORD | ySubscriptXSize |
| 12 | FWORD | ySubscriptYSize |
| 14 | FWORD | ySubscriptXOffset |
| 16 | FWORD | ySubscriptYOffset |
| 18 | FWORD | ySuperscriptXSize |
| 20 | FWORD | ySuperscriptYSize |
| 22 | FWORD | ySuperscriptXOffset |
| 24 | FWORD | ySuperscriptYOffset |
| 26 | FWORD | yStrikeoutSize |
| 28 | FWORD | yStrikeoutPosition |
| 30 | int16 | sFamilyClass |
| 32 | uint8 | panose[10] |
| 42 | uint32 | ulUnicodeRange1 |
| 46 | uint32 | ulUnicodeRange2 |
| 50 | uint32 | ulUnicodeRange3 |
| 54 | uint32 | ulUnicodeRange4 |
| 58 | Tag | achVendID |
| 62 | uint16 | fsSelection |
| 64 | uint16 | usFirstCharIndex |
| 66 | uint16 | usLastCharIndex |
| 68 | FWORD | sTypoAscender |
| 70 | FWORD | sTypoDescender |
| 72 | FWORD | sTypoLineGap |
| 74 | UFWORD | usWinAscent |
| 76 | UFWORD | usWinDescent |
| 78 | uint32 | ulCodePageRange1 |
| 82 | uint32 | ulCodePageRange2 |

### Version 0

| Offset | Type | Name |
|---|---|---|
| 0 | uint16 | version |
| 2 | FWORD | xAvgCharWidth |
| 4 | uint16 | usWeightClass |
| 6 | uint16 | usWidthClass |
| 8 | uint16 | fsType |
| 10 | FWORD | ySubscriptXSize |
| 12 | FWORD | ySubscriptYSize |
| 14 | FWORD | ySubscriptXOffset |
| 16 | FWORD | ySubscriptYOffset |
| 18 | FWORD | ySuperscriptXSize |
| 20 | FWORD | ySuperscriptYSize |
| 22 | FWORD | ySuperscriptXOffset |
| 24 | FWORD | ySuperscriptYOffset |
| 26 | FWORD | yStrikeoutSize |
| 28 | FWORD | yStrikeoutPosition |
| 30 | int16 | sFamilyClass |
| 32 | uint8 | panose[10] |
| 42 | uint32 | ulUnicodeRange1 |
| 46 | uint32 | ulUnicodeRange2 |
| 50 | uint32 | ulUnicodeRange3 |
| 54 | uint32 | ulUnicodeRange4 |
| 58 | Tag | achVendID |
| 62 | uint16 | fsSelection |
| 64 | uint16 | usFirstCharIndex |
| 66 | uint16 | usLastCharIndex |
| 68 | FWORD | sTypoAscender |
| 70 | FWORD | sTypoDescender |
| 72 | FWORD | sTypoLineGap |
| 74 | UFWORD | usWinAscent |
| 76 | UFWORD | usWinDescent |

A version 0 table may end at offset 68, after usLastCharIndex (see "Reading rules" above).

## Field details

These details cover all versions. Each entry gives the source's format, units and title, then the rules in short form.

### version

**Format:** uint16. **Units:** n/a. **Title:** OS/2 table version number.

- **Description:** One of the values 0x0000 to 0x0005; it tells exactly which fields the table contains and how they are laid out.

### xAvgCharWidth

**Format:** FWORD. **Units:** Font design units. **Title:** Average weighted escapement.

- **Description:** Arithmetic mean of the advance widths (escapements) of every glyph in the font whose width is not zero.
- **Comments:** Do not rely on it for laying out lines of text, especially with complex scripts, and never use it for real glyph advances. Some fonts do not follow the current definition: a font first built with a version 0 to 2 table may have been upgraded to a newer table version while keeping the old value, and in some CJK fonts the value is close to half of what the current definition gives.
- **Version differences:** Versions 0 to 2 used a formula biased toward Basic Latin, meant to estimate average line length: multiply the width of each letter in the table below by its weight factor, add up the products, and divide the total by 1000. Version 3 replaced this method; it is deprecated.

`xAvgCharWidth (versions 0-2) = sum(width(letter) * factor(letter)) / 1000`

| Letter | Weight factor | Letter | Weight factor |
|---|---|---|---|
| a | 64 | o | 56 |
| b | 14 | p | 17 |
| c | 27 | q | 4 |
| d | 35 | r | 49 |
| e | 100 | s | 56 |
| f | 20 | t | 71 |
| g | 14 | u | 31 |
| h | 42 | v | 10 |
| i | 63 | w | 18 |
| j | 3 | x | 3 |
| k | 6 | y | 18 |
| l | 35 | z | 2 |
| m | 20 | space | 166 |
| n | 56 | | |

### usWeightClass

**Format:** uint16. **Title:** Weight class.

- **Description:** Visual weight of the glyphs (how dark they are, how thick the strokes). Every value from 1 to 1000 is valid.
- **Comments:** The scale is the one used by the 'wght' axis in 'fvar' and STAT (see fvar.md, stat.md). Integers 1 to 1000 are supported, although some legacy platforms accept only some of them. Commonly used values:

| Value | Description | C definition (windows.h) |
|---|---|---|
| 100 | Thin | FW_THIN |
| 200 | Extra-light (Ultra-light) | FW_EXTRALIGHT |
| 300 | Light | FW_LIGHT |
| 400 | Normal (Regular) | FW_NORMAL |
| 500 | Medium | FW_MEDIUM |
| 600 | Semi-bold (Demi-bold) | FW_SEMIBOLD |
| 700 | Bold | FW_BOLD |
| 800 | Extra-bold (Ultra-bold) | FW_EXTRABOLD |
| 900 | Black (Heavy) | FW_BLACK |

### usWidthClass

**Format:** uint16. **Title:** Width class.

- **Description:** How far the designer has changed the glyphs' aspect ratio (width relative to height) from the normal width.
- **Comments:** Whatever its actual proportions, each glyph of a normal-width font counts as having relative aspect ratio 1. A style in another width class (made by a designer or automatically) has glyphs some percentage wider or narrower than their normal-width counterparts; this field records that class. The values relate to, but are not the same scale as, the 'wdth' axis in 'fvar' and STAT. The "% of normal" column maps classes 1 to 9 onto 'wdth' values.

| Value | Description | C Definition | % of normal |
|---|---|---|---|
| 1 | Ultra-condensed | FWIDTH_ULTRA_CONDENSED | 50 |
| 2 | Extra-condensed | FWIDTH_EXTRA_CONDENSED | 62.5 |
| 3 | Condensed | FWIDTH_CONDENSED | 75 |
| 4 | Semi-condensed | FWIDTH_SEMI_CONDENSED | 87.5 |
| 5 | Medium (normal) | FWIDTH_NORMAL | 100 |
| 6 | Semi-expanded | FWIDTH_SEMI_EXPANDED | 112.5 |
| 7 | Expanded | FWIDTH_EXPANDED | 125 |
| 8 | Extra-expanded | FWIDTH_EXTRA_EXPANDED | 150 |
| 9 | Ultra-expanded | FWIDTH_ULTRA_EXPANDED | 200 |

In a variable font a 'wdth' value above 200 maps to class 9 (see "OS/2 and font variations").

### fsType

**Format:** uint16. **Title:** Type flags.

- **Description:** The font's embedding licensing rights, encoded as follows.

| Bits | Mask | Description |
|---|---|---|
| 0-3 | 0x000F | Usage-permissions sub-field. A valid font sets at most one of bits 1, 2 and 3; bit 0 is permanently reserved and must be 0. The only valid sub-field values are 0, 2, 4 and 8 (next table). |
| 4-7 | 0x00F0 | Reserved; must be 0. |
| 8 | 0x0100 | No subsetting: the font must not be subset before it is embedded. The restrictions of bits 0-3 and bit 9 still apply. |
| 9 | 0x0200 | Bitmap embedding only: only bitmaps in the font may be embedded, never outline data. A font with no bitmaps is then not embeddable and embedding fails. The restrictions of bits 0-3 and bit 8 still apply. |
| 10-15 | 0xFC00 | Reserved; must be 0. |

| Sub-field value | Permission | Meaning |
|---|---|---|
| 0 | Installable embedding | May be embedded, and may be installed permanently on the remote system or used by other users. The remote user gets the same rights, obligations and licences for the font as the original purchaser, under the same licence agreement, copyright, design patent and trademark terms. |
| 2 | Restricted License embedding | No modifying, embedding or exchanging of the font in any way without first getting explicit permission from its legal owner. |
| 4 | Preview & Print embedding | May be embedded and loaded temporarily on other systems to view or print the document. Documents holding such fonts open read-only; no edits are allowed. |
| 8 | Editable embedding | May be embedded and loaded temporarily on other systems. Documents holding such fonts may be opened, edited (including formatting new text in the embedded font) and saved. |

- **Comments:**
  - An embeddable font can be stored inside a document. On a system that lacks it, an embedding-aware application may load it for temporary (sometimes permanent) use. The font vendor grants the embedding rights.
  - Applications must not embed a font whose licence does not permit it, must not change these permission bits when embedding, and must delete temporarily loaded fonts (Preview & Print or Editable) when the document that carried them is closed.
  - Bits 0-3 are mutually exclusive; a font should never set more than one. If several are set anyway, some applications take the least restrictive permission among them.
  - Restricted License embedding is in force only when the sub-field equals 2, that is, bit 1 alone.
  - Bit 0 stays reserved for good, and setting it is deprecated. Early fonts that wrongly used the value 1 caused interoperability problems, so the final version 0 specification reserved it. Apple's TrueType Reference Manual gives a meaning to bit 1 only, a leftover of a pre-release draft; the final version 0 definition covers bits 0-3.
- **Version differences:**
  - Versions 0 and 1: only bits 0-3 were assigned; readers must ignore bits 4-15 of a version 0 or 1 table.
  - Versions 0 to 2: bits 0-3 were not declared exclusive; when more than one was set, the least restrictive permission won. Some fonts with such tables set both bit 2 and bit 3 to grant preview/print and editing. Applications may keep this interpretation for version 0 to 2 tables.
  - Version 3 and later (from OpenType 1.4): bits 0-3 must be mutually exclusive.

### ySubscriptXSize

**Format:** FWORD. **Units:** Font design units. **Title:** Subscript horizontal font size.

- **Description:** Suggested horizontal size of subscripts, in design units; should be > 0.
- **Comments:** The value is an em size for the subscript. An application that has to fake subscripts (by scaling glyphs, or by borrowing glyphs from another font) uses it as the nominal subscript width: the horizontal scale is ySubscriptXSize / unitsPerEm, so 205 in a 2048-unit em gives one tenth of normal size. When a font has two suggested subscript sizes (numerals and others), the numeral size is the one to give. The field was implemented as signed on the OS/2 platform even though only positive values make sense.

### ySubscriptYSize

**Format:** FWORD. **Units:** Font design units. **Title:** Subscript vertical font size.

- **Description:** Suggested vertical size of subscripts, in design units; should be > 0.
- **Comments:** As for ySubscriptXSize, but vertical: the nominal height for faked subscripts, with vertical scale ySubscriptYSize / unitsPerEm. Numeral sizes take priority when there are two, and the field is signed although only positive values make sense.

### ySubscriptXOffset

**Format:** FWORD. **Units:** Font design units. **Title:** Subscript x offset.

- **Description:** Suggested horizontal offset of subscripts, in design units.
- **Comments:** Measured from the origin of the base glyph to the origin of the subscript glyph. For faked subscripts, it is the horizontal distance from the advance (escapement) point of the glyph that precedes the first subscript glyph. Usually 0 for upright designs; italic or slanted designs usually shift it to allow for the slant.

### ySubscriptYOffset

**Format:** FWORD. **Units:** Font design units. **Title:** Subscript y offset.

- **Description:** Suggested vertical offset of subscripts from the baseline, in design units.
- **Comments:** Distance from the glyph baseline down to the subscript baseline, stored as a positive number for a position below the baseline. Applications that supply their own subscript glyphs place them this far below the baseline.

### ySuperscriptXSize

**Format:** FWORD. **Units:** Font design units. **Title:** Superscript horizontal font size.

- **Description:** Suggested horizontal size of superscripts, in design units; should be > 0.
- **Comments:** An em size for the superscript: the nominal width for faked superscripts, with horizontal scale ySuperscriptXSize / unitsPerEm (205 in a 2048-unit em gives one tenth). Numeral sizes take priority when there are two, and the field is signed although only positive values make sense.

### ySuperscriptYSize

**Format:** FWORD. **Units:** Font design units. **Title:** Superscript vertical font size.

- **Description:** Suggested vertical size of superscripts, in design units; should be > 0.
- **Comments:** The nominal height for faked superscripts, with vertical scale ySuperscriptYSize / unitsPerEm. Numeral sizes take priority when there are two, and the field is signed although only positive values make sense.

### ySuperscriptXOffset

**Format:** FWORD. **Units:** Font design units. **Title:** Superscript x offset.

- **Description:** Suggested horizontal offset of superscripts, in design units.
- **Comments:** Runs from the origin of the base glyph to the origin of the superscript glyph. For faked superscripts, it is measured horizontally starting at the advance (escapement) point of the glyph that precedes the first superscript glyph. Usually 0 for upright designs; slanted designs usually adjust it for the slant.

### ySuperscriptYOffset

**Format:** FWORD. **Units:** Font design units. **Title:** Superscript y offset.

- **Description:** Suggested vertical offset of superscripts from the baseline, in design units.
- **Comments:** Distance from the glyph baseline up to the superscript baseline, stored as a positive number for a position above the baseline. Applications that supply their own superscript glyphs place them this far above the baseline.

### yStrikeoutSize

**Format:** FWORD. **Units:** Font design units. **Title:** Strikeout size.

- **Description:** Thickness of the strikeout stroke, in design units; should be > 0.
- **Comments:** Normally equal to the thickness of the font's em dash and to the underline thickness given in the 'post' table. Signed on the OS/2 platform although only positive values make sense.

### yStrikeoutPosition

**Format:** FWORD. **Units:** Font design units. **Title:** Strikeout position.

- **Description:** Height of the top edge of the strikeout stroke above the baseline, in design units.
- **Comments:** Positive values lie above the baseline and negative values below it. Lining it up with the em dash is suggested, but it should not coincide with crossbars, so that letters stay recognizable.

### sFamilyClass

**Format:** int16. **Title:** Font-family class and subclass.

- **Description:** Classifies the design of the font family.
- **Comments:** High byte = family class, low byte = subclass; the meaning of a subclass depends on its class. The registered values come from IBM (see "IBM Font Family Classifications", referenced by the source but not digested). The field is meant for choosing a substitute family when the requested one is missing.

### panose

PANOSE array layout (10 bytes, at offset 32 of the OS/2 table). The field names apply when the family kind is Latin Text:

| Byte | Type | Name |
|---|---|---|
| 0 | uint8 | bFamilyType |
| 1 | uint8 | bSerifStyle |
| 2 | uint8 | bWeight |
| 3 | uint8 | bProportion |
| 4 | uint8 | bContrast |
| 5 | uint8 | bStrokeVariation |
| 6 | uint8 | bArmStyle |
| 7 | uint8 | bLetterform |
| 8 | uint8 | bMidline |
| 9 | uint8 | bXHeight |

**Format:** uint8[10]. **Title:** PANOSE classification number. **International:** classifying non-Latin character sets with PANOSE needs further specifications.

- **Description:** Ten numbers that describe the visual character of the typeface, so that fonts of similar appearance but different names can be matched.
- **Comments:**
  - Each byte has several possible values; the external PANOSE Classification Metrics Guide defines them fully and is the normative source.
  - Byte 0 (bFamilyType, "Family Kind") is the top-level class, and the meaning of the other nine bytes depends on it. With Family Kind 2 (Latin Text) byte 1 is "Serif Style"; with Family Kind 3 (Latin Hand Written) byte 1 is "Tool Kind". Some applications support only some Family Kind values.
  - No usage is required of applications. Examples of use: the Proportion byte (Latin Text) to detect monospaced fonts; Serif Style to sort fonts into serif and sans serif; Family Kind 5 (Latin Symbol) to spot symbol fonts, which can affect font selection and fallback.
  - A variable font can hold only one set of PANOSE values, which cannot vary by instance; they may describe the default instance.
- **Version differences:** Older editions of the specification described PANOSE values in more detail; the external specification is the normative reference for those details.

### ulUnicodeRange1-4 (ulUnicodeRange*)

- ulUnicodeRange1 holds bits 0-31, ulUnicodeRange2 bits 32-63, ulUnicodeRange3 bits 64-95 and ulUnicodeRange4 bits 96-127. Each uint32 is stored big-endian; bit k of the 128-bit set is bit (k mod 32) of field (k div 32) + 1.

**Format:** uint32[4] (128 bits total). **Title:** Unicode Character Range.

- **Description:** States which Unicode blocks or ranges the font covers through its 'cmap' subtables for platform 3 encoding 1 (Windows, Unicode BMP) and platform 3 encoding 10 (Windows, full Unicode repertoire); see cmap.md.
  - A set bit means the ranges of that bit are considered functional; a clear bit means they are not.
  - Every bit is an independent flag and any combination may be set.
  - The font designer decides what counts as "functional", but should aim to make coverage functional range by range where possible.
  - All reserved bits must be 0.

In the table, a row with an empty Bit cell is a further range of the bit in the row above it. In the Notes column "OT" means OpenType and "vN" means OS/2 table version N.

| Bit | Unicode Range | Block range | Notes |
|---|---|---|---|
| 0 | Basic Latin | 0000-007F | |
| 1 | Latin-1 Supplement | 0080-00FF | |
| 2 | Latin Extended-A | 0100-017F | |
| 3 | Latin Extended-B | 0180-024F | |
| 4 | IPA Extensions | 0250-02AF | |
| | Phonetic Extensions | 1D00-1D7F | Added in OT 1.5 (v4). |
| | Phonetic Extensions Supplement | 1D80-1DBF | Added in OT 1.5 (v4). |
| 5 | Spacing Modifier Letters | 02B0-02FF | |
| | Modifier Tone Letters | A700-A71F | Added in OT 1.5 (v4). |
| 6 | Combining Diacritical Marks | 0300-036F | |
| | Combining Diacritical Marks Supplement | 1DC0-1DFF | Added in OT 1.5 (v4). |
| 7 | Greek and Coptic | 0370-03FF | |
| 8 | Coptic | 2C80-2CFF | Added in OT 1.5 (v4); older meaning under "Version differences". |
| 9 | Cyrillic | 0400-04FF | |
| | Cyrillic Supplement | 0500-052F | Added in OT 1.4 (v3). |
| | Cyrillic Extended-A | 2DE0-2DFF | Added in OT 1.5 (v4). |
| | Cyrillic Extended-B | A640-A69F | Added in OT 1.5 (v4). |
| 10 | Armenian | 0530-058F | |
| 11 | Hebrew | 0590-05FF | |
| 12 | Vai | A500-A63F | Added in OT 1.5 (v4); older meaning under "Version differences". |
| 13 | Arabic | 0600-06FF | |
| | Arabic Supplement | 0750-077F | Added in OT 1.5 (v4). |
| 14 | NKo | 07C0-07FF | Added in OT 1.5 (v4); older meaning under "Version differences". |
| 15 | Devanagari | 0900-097F | |
| 16 | Bangla | 0980-09FF | |
| 17 | Gurmukhi | 0A00-0A7F | |
| 18 | Gujarati | 0A80-0AFF | |
| 19 | Odia | 0B00-0B7F | |
| 20 | Tamil | 0B80-0BFF | |
| 21 | Telugu | 0C00-0C7F | |
| 22 | Kannada | 0C80-0CFF | |
| 23 | Malayalam | 0D00-0D7F | |
| 24 | Thai | 0E00-0E7F | |
| 25 | Lao | 0E80-0EFF | |
| 26 | Georgian | 10A0-10FF | |
| | Georgian Supplement | 2D00-2D2F | Added in OT 1.5 (v4). |
| 27 | Balinese | 1B00-1B7F | Added in OT 1.5 (v4); older meaning under "Version differences". |
| 28 | Hangul Jamo | 1100-11FF | |
| 29 | Latin Extended Additional | 1E00-1EFF | |
| | Latin Extended-C | 2C60-2C7F | Added in OT 1.5 (v4). |
| | Latin Extended-D | A720-A7FF | Added in OT 1.5 (v4). |
| 30 | Greek Extended | 1F00-1FFF | |
| 31 | General Punctuation | 2000-206F | |
| | Supplemental Punctuation | 2E00-2E7F | Added in OT 1.5 (v4). |
| 32 | Superscripts And Subscripts | 2070-209F | |
| 33 | Currency Symbols | 20A0-20CF | |
| 34 | Combining Diacritical Marks For Symbols | 20D0-20FF | |
| 35 | Letterlike Symbols | 2100-214F | |
| 36 | Number Forms | 2150-218F | |
| 37 | Arrows | 2190-21FF | |
| | Supplemental Arrows-A | 27F0-27FF | Added in OT 1.4 (v3). |
| | Supplemental Arrows-B | 2900-297F | Added in OT 1.4 (v3). |
| | Miscellaneous Symbols and Arrows | 2B00-2BFF | Added in OT 1.5 (v4). |
| 38 | Mathematical Operators | 2200-22FF | |
| | Supplemental Mathematical Operators | 2A00-2AFF | Added in OT 1.4 (v3). |
| | Miscellaneous Mathematical Symbols-A | 27C0-27EF | Added in OT 1.4 (v3). |
| | Miscellaneous Mathematical Symbols-B | 2980-29FF | Added in OT 1.4 (v3). |
| 39 | Miscellaneous Technical | 2300-23FF | |
| 40 | Control Pictures | 2400-243F | |
| 41 | Optical Character Recognition | 2440-245F | |
| 42 | Enclosed Alphanumerics | 2460-24FF | |
| 43 | Box Drawing | 2500-257F | |
| 44 | Block Elements | 2580-259F | |
| 45 | Geometric Shapes | 25A0-25FF | |
| 46 | Miscellaneous Symbols | 2600-26FF | |
| 47 | Dingbats | 2700-27BF | |
| 48 | CJK Symbols And Punctuation | 3000-303F | |
| 49 | Hiragana | 3040-309F | |
| 50 | Katakana | 30A0-30FF | |
| | Katakana Phonetic Extensions | 31F0-31FF | Added in OT 1.4 (v3). |
| 51 | Bopomofo | 3100-312F | |
| | Bopomofo Extended | 31A0-31BF | Added in OT 1.3 (update of v2). |
| 52 | Hangul Compatibility Jamo | 3130-318F | |
| 53 | Phags-pa | A840-A87F | Added in OT 1.5 (v4); older meaning under "Version differences". |
| 54 | Enclosed CJK Letters And Months | 3200-32FF | |
| 55 | CJK Compatibility | 3300-33FF | |
| 56 | Hangul Syllables | AC00-D7AF | |
| 57 | Non-Plane 0 | 10000-10FFFF | A set bit means the font supports at least one character outside the BMP. Bit first assigned in OT 1.3 (v2). |
| 58 | Phoenician | 10900-1091F | Bit first assigned in OT 1.5 (v4). |
| 59 | CJK Unified Ideographs | 4E00-9FFF | |
| | CJK Radicals Supplement | 2E80-2EFF | Added in OT 1.3 (v2). |
| | Kangxi Radicals | 2F00-2FDF | Added in OT 1.3 (v2). |
| | Ideographic Description Characters | 2FF0-2FFF | Added in OT 1.3 (v2). |
| | CJK Unified Ideographs Extension A | 3400-4DBF | Added in OT 1.3 (v2). |
| | CJK Unified Ideographs Extension B | 20000-2A6DF | Added in OT 1.4 (v3). |
| | Kanbun | 3190-319F | Added in OT 1.4 (v3). |
| 60 | Private Use Area (plane 0) | E000-F8FF | |
| 61 | CJK Strokes | 31C0-31EF | Added in OT 1.5 (v4). |
| | CJK Compatibility Ideographs | F900-FAFF | |
| | CJK Compatibility Ideographs Supplement | 2F800-2FA1F | Added in OT 1.4 (v3). |
| 62 | Alphabetic Presentation Forms | FB00-FB4F | |
| 63 | Arabic Presentation Forms-A | FB50-FDFF | |
| 64 | Combining Half Marks | FE20-FE2F | |
| 65 | Vertical Forms | FE10-FE1F | Added in OT 1.5 (v4). |
| | CJK Compatibility Forms | FE30-FE4F | |
| 66 | Small Form Variants | FE50-FE6F | |
| 67 | Arabic Presentation Forms-B | FE70-FEFF | |
| 68 | Halfwidth And Fullwidth Forms | FF00-FFEF | |
| 69 | Specials | FFF0-FFFF | |
| 70 | Tibetan | 0F00-0FFF | Bit first assigned in OT 1.3 (update of v2). |
| 71 | Syriac | 0700-074F | Bit first assigned in OT 1.3 (update of v2). |
| 72 | Thaana | 0780-07BF | Bit first assigned in OT 1.3 (update of v2). |
| 73 | Sinhala | 0D80-0DFF | Bit first assigned in OT 1.3 (update of v2). |
| 74 | Myanmar | 1000-109F | Bit first assigned in OT 1.3 (update of v2). |
| 75 | Ethiopic | 1200-137F | Bit first assigned in OT 1.3 (update of v2). |
| | Ethiopic Supplement | 1380-139F | Added in OT 1.5 (v4). |
| | Ethiopic Extended | 2D80-2DDF | Added in OT 1.5 (v4). |
| 76 | Cherokee | 13A0-13FF | Bit first assigned in OT 1.3 (update of v2). |
| 77 | Unified Canadian Aboriginal Syllabics | 1400-167F | Bit first assigned in OT 1.3 (update of v2). |
| 78 | Ogham | 1680-169F | Bit first assigned in OT 1.3 (update of v2). |
| 79 | Runic | 16A0-16FF | Bit first assigned in OT 1.3 (update of v2). |
| 80 | Khmer | 1780-17FF | Bit first assigned in OT 1.3 (update of v2). |
| | Khmer Symbols | 19E0-19FF | Added in OT 1.5 (v4). |
| 81 | Mongolian | 1800-18AF | Bit first assigned in OT 1.3 (update of v2). |
| 82 | Braille Patterns | 2800-28FF | Bit first assigned in OT 1.3 (update of v2). |
| 83 | Yi Syllables | A000-A48F | Bit first assigned in OT 1.3 (update of v2). |
| | Yi Radicals | A490-A4CF | Added in OT 1.3 (update of v2). |
| 84 | Tagalog | 1700-171F | Bit first assigned in OT 1.4 (v3). |
| | Hanunoo | 1720-173F | Added in OT 1.4 (v3). |
| | Buhid | 1740-175F | Added in OT 1.4 (v3). |
| | Tagbanwa | 1760-177F | Added in OT 1.4 (v3). |
| 85 | Old Italic | 10300-1032F | Bit first assigned in OT 1.4 (v3). |
| 86 | Gothic | 10330-1034F | Bit first assigned in OT 1.4 (v3). |
| 87 | Deseret | 10400-1044F | Bit first assigned in OT 1.4 (v3). |
| 88 | Byzantine Musical Symbols | 1D000-1D0FF | Bit first assigned in OT 1.4 (v3). |
| | Musical Symbols | 1D100-1D1FF | Added in OT 1.4 (v3). |
| | Ancient Greek Musical Notation | 1D200-1D24F | Added in OT 1.5 (v4). |
| 89 | Mathematical Alphanumeric Symbols | 1D400-1D7FF | Bit first assigned in OT 1.4 (v3). |
| 90 | Private Use (plane 15) | F0000-FFFFD | Bit first assigned in OT 1.4 (v3). |
| | Private Use (plane 16) | 100000-10FFFD | Added in OT 1.4 (v3). |
| 91 | Variation Selectors | FE00-FE0F | Bit first assigned in OT 1.4 (v3). |
| | Variation Selectors Supplement | E0100-E01EF | Added in OT 1.4 (v3). |
| 92 | Tags | E0000-E007F | Bit first assigned in OT 1.4 (v3). |
| 93 | Limbu | 1900-194F | Bit first assigned in OT 1.5 (v4). |
| 94 | Tai Le | 1950-197F | Bit first assigned in OT 1.5 (v4). |
| 95 | New Tai Lue | 1980-19DF | Bit first assigned in OT 1.5 (v4). |
| 96 | Buginese | 1A00-1A1F | Bit first assigned in OT 1.5 (v4). |
| 97 | Glagolitic | 2C00-2C5F | Bit first assigned in OT 1.5 (v4). |
| 98 | Tifinagh | 2D30-2D7F | Bit first assigned in OT 1.5 (v4). |
| 99 | Yijing Hexagram Symbols | 4DC0-4DFF | Bit first assigned in OT 1.5 (v4). |
| 100 | Syloti Nagri | A800-A82F | Bit first assigned in OT 1.5 (v4). |
| 101 | Linear B Syllabary | 10000-1007F | Bit first assigned in OT 1.5 (v4). |
| | Linear B Ideograms | 10080-100FF | Added in OT 1.5 (v4). |
| | Aegean Numbers | 10100-1013F | Added in OT 1.5 (v4). |
| 102 | Ancient Greek Numbers | 10140-1018F | Bit first assigned in OT 1.5 (v4). |
| 103 | Ugaritic | 10380-1039F | Bit first assigned in OT 1.5 (v4). |
| 104 | Old Persian | 103A0-103DF | Bit first assigned in OT 1.5 (v4). |
| 105 | Shavian | 10450-1047F | Bit first assigned in OT 1.5 (v4). |
| 106 | Osmanya | 10480-104AF | Bit first assigned in OT 1.5 (v4). |
| 107 | Cypriot Syllabary | 10800-1083F | Bit first assigned in OT 1.5 (v4). |
| 108 | Kharoshthi | 10A00-10A5F | Bit first assigned in OT 1.5 (v4). |
| 109 | Tai Xuan Jing Symbols | 1D300-1D35F | Bit first assigned in OT 1.5 (v4). |
| 110 | Cuneiform | 12000-123FF | Bit first assigned in OT 1.5 (v4). |
| | Cuneiform Numbers and Punctuation | 12400-1247F | Added in OT 1.5 (v4). |
| 111 | Counting Rod Numerals | 1D360-1D37F | Bit first assigned in OT 1.5 (v4). |
| 112 | Sundanese | 1B80-1BBF | Bit first assigned in OT 1.5 (v4). |
| 113 | Lepcha | 1C00-1C4F | Bit first assigned in OT 1.5 (v4). |
| 114 | Ol Chiki | 1C50-1C7F | Bit first assigned in OT 1.5 (v4). |
| 115 | Saurashtra | A880-A8DF | Bit first assigned in OT 1.5 (v4). |
| 116 | Kayah Li | A900-A92F | Bit first assigned in OT 1.5 (v4). |
| 117 | Rejang | A930-A95F | Bit first assigned in OT 1.5 (v4). |
| 118 | Cham | AA00-AA5F | Bit first assigned in OT 1.5 (v4). |
| 119 | Ancient Symbols | 10190-101CF | Bit first assigned in OT 1.5 (v4). |
| 120 | Phaistos Disc | 101D0-101FF | Bit first assigned in OT 1.5 (v4). |
| 121 | Carian | 102A0-102DF | Bit first assigned in OT 1.5 (v4). |
| | Lycian | 10280-1029F | Added in OT 1.5 (v4). |
| | Lydian | 10920-1093F | Added in OT 1.5 (v4). |
| 122 | Domino Tiles | 1F030-1F09F | Bit first assigned in OT 1.5 (v4). |
| | Mahjong Tiles | 1F000-1F02F | First assigned in OT 1.5 (v4). |
| 123-127 | Reserved | | Must be 0. |

- **Comments:** Every available bit was used up by Unicode 5.1; the assignments were last revised for OS/2 version 4 in OpenType 1.5. Many ranges of current Unicode have no bit here. The 'dlng' and 'slng' tags of the 'meta' table are the alternative way to declare which scripts or languages a font supports or is designed for.
- **Version differences:**
  - Each table version was defined while a particular Unicode version was current, and earlier table versions defined fewer bits. Applications may not honour every assignment in fonts with older table versions.
  - Every assignment in the table above is valid for every table version. However, versions 1 and 2 defined a few bits with meanings that matched no well-defined Unicode range and that clash with the later assignments (table below). A font with a version 1 or 2 table that sets one of these bits may mean the obsolete assignment, whose character coverage is unclear.
  - Version 0: no bit assignments were defined when it was first specified; some applications may ignore these fields in a version 0 table.
  - Version 1: specified alongside Unicode 1.1, with assignments for bits 0 to 69 only; some applications may recognize only bits 0-69 in fonts with a version 1 table. The bits 8, 12, 14 and 27 obsolete meanings were dropped as of version 2.
  - Version 2: defined in OpenType 1.1 (Unicode 2.1 era) with bits 0-69. OpenType 1.3 then added bits 70-83 for blocks new in Unicode 2.0 and Unicode 3.0. Some applications may recognize only the bits assigned in OpenType 1.2 or OpenType 1.3 for version 2 fonts. Bit 53 kept its obsolete meaning in version 2; it was dropped as of version 3.
  - Version 3: defined in OpenType 1.4, adding bits 84-92 for ranges of Unicode 3.2 and extending some existing bits to related ranges (see the Notes column).
  - Version 4: defined in OpenType 1.5, adding bit 58 and bits 93-122 for ranges of Unicode 5.1, reassigning bits 8, 12, 14, 27 and 53, and extending more existing bits to related ranges (see the Notes column).

Obsolete assignments of versions 1 and 2:

| Bit | Obsolete name | Tables that used it | Neighbouring assignment at that time |
|---|---|---|---|
| 8 | Greek Symbols and Coptic | version 1 | bit 7 = Basic Greek |
| 12 | Hebrew Extended | version 1 | bit 11 = Basic Hebrew |
| 14 | Arabic Extended | version 1 | bit 13 = Basic Arabic |
| 27 | Georgian Extended | version 1 | bit 26 = Basic Georgian |
| 53 | CJK Miscellaneous | versions 1 and 2 | none |

### achVendID

**Format:** Tag. **Title:** Font Vendor Identification.

- **Description:** Four-character identifier of the typeface's vendor, stored as a Tag (4 bytes at offset 58; see otff.md for the Tag data type, a four-character string drawn from a limited set of ASCII characters).
- **Comments:**
  - It names the company that markets and distributes the typeface, not the owner of royalties on the original design. It lets software prefer one vendor's version of a typeface (for example one with more kerning pairs or hand hinting) over another vendor's.
  - Microsoft keeps a registry of vendor IDs; a registered ID belongs to a single vendor. Unregistered IDs are allowed but discouraged, since they can clash and give customers no contact details.
  - The field may be blank: all zero bytes (null) or four space characters.
  - By convention only registered tags consist entirely of uppercase letters (or spaces).

### fsSelection

**Format:** uint16. **Title:** Font selection flags.

- **Description:** Flags that describe the nature of the font's glyph patterns. The masks follow from the bit numbers.

| Bit # | macStyle bit | C definition | Mask | Description |
|---|---|---|---|---|
| 0 | bit 1 | ITALIC | 0x0001 | Italic or oblique glyphs; when clear, the glyphs are upright. |
| 1 | | UNDERSCORE | 0x0002 | Glyphs carry an underscore. |
| 2 | | NEGATIVE | 0x0004 | Glyph foreground and background are swapped. |
| 3 | | OUTLINED | 0x0008 | Hollow outline glyphs; when clear, the glyphs are solid. |
| 4 | | STRIKEOUT | 0x0010 | Glyphs are struck through. |
| 5 | bit 0 | BOLD | 0x0020 | Glyphs are bold (emboldened). |
| 6 | | REGULAR | 0x0040 | Glyphs use the family's standard weight and style. |
| 7 | | USE_TYPO_METRICS | 0x0080 | Applications are strongly advised to take sTypoAscender - sTypoDescender + sTypoLineGap as the font's default line spacing. |
| 8 | | WWS | 0x0100 | The font's 'name' strings already fit a weight/width/slope family, without name IDs 21 and 22 (details below). |
| 9 | | OBLIQUE | 0x0200 | The font has oblique glyphs. |
| 10-15 | | Reserved | 0xFC00 | Reserved; 0. |

- **Comments:**
  - All undefined bits must be 0. The field began as an OS/2-platform compatibility feature; modern applications use some style bits (such as bit 0) and ignore others.
  - Bit 0 must have the same setting as bit 1 (Italic) of macStyle in 'head' (see head.md).
  - Bits 1-4 are rarely used; they mark a font mainly meant for decorative or special purposes.
  - Bit 5 must have the same setting as bit 0 (Bold) of macStyle in 'head'.
  - Bit 6 is not widely used by modern applications. If bit 6 is set, bits 0 and 5 must be clear; otherwise behaviour is undefined. Bits 0 and 5 both clear do not imply bit 6 is set: a Light style that is not the family's regular style has all three clear. In extended families, styles other than the regular one do not need bit 6 even if their name ID 2 is "Regular".
  - Bit 7 (defined in version 4) is used by many modern applications. Fonts are encouraged to use a version 4 or later table with bit 7 set. Turning bit 7 on in an updated older font can reflow existing documents, so it should be turned on in that case only when the usWin metrics give clearly worse line heights than the sTypo metrics.
  - Bit 8: when set, the family and subfamily strings (name IDs 1 and 2, or 16 and 17) are already consistent with a weight/width/slope (WWS) family model, so name IDs 21 and 22 are never needed and should be absent. Applications that assume a WWS model can then use those names as they are, without looking for IDs 21 and 22. When clear, such applications should look for name IDs 21 and 22 or treat the names in some other way.
  - Bit 8 should be set when a face differs from the rest of its family only in weight, width or slope, even inside a large family whose other faces differ in other ways. It should be clear, and name IDs 21 and 22 should be present, when a face differs from Regular in some other attribute (for example "handwriting", "caption", "display" or optical size), because WWS applications need that attribute in the family name (ID 1 or ID 16) whereas the font may keep it in the typographic subfamily (ID 17).
  - The STAT table (see stat.md) arrived later and solves the same problem more generally; it can help WWS applications when name IDs 21 and 22 are missing. Even when STAT is present (it is required in variable fonts), the bit 8 and name ID 21/22 rules above still apply.
  - Definitions for bit 8: "typographic family" is the Microsoft Unicode string of name ID 16 if present, otherwise of name ID 1; "weight" is usWeightClass; "width" is usWidthClass; "slope" is fsSelection bit 0 (ITALIC) together with bit 9 (OBLIQUE).
  - Bit 9: when set, processes that distinguish oblique from italic (such as CSS font matching) should treat the font as an oblique style; a font made by slanting an upright design algorithmically sets it. With a version 4 or later table, a clear bit 9 means the font is not oblique (a classic italic design leaves it clear). Bit 9 plays no part in the four-member regular/italic/bold/bold-italic style linking that bit 0 serves, and can be set independently of bit 0. Usually ITALIC is also set when OBLIQUE is set, but that is not required.
  - Bit 15 is permanently reserved. Some legacy implementations used it, and it may trigger special behaviour in some implementations; its use is deprecated.
- **Version differences:**
  - Versions 0 to 3: only bits 0 (ITALIC) to 6 (REGULAR) are assigned; bits 7-15 are reserved and must be 0. Applications should ignore bits 7-15 in a version 0 to 3 table.
  - Versions 4 and 5: bits 7-9 were added in version 4 (OpenType 1.5); bits 10-15 are reserved and must be 0. Applications should ignore bits 10-15 in a version 4 or 5 table.

### usFirstCharIndex

**Format:** uint16.

- **Description:** Lowest Unicode code point in the font, as mapped by its platform 3 'cmap' subtable with encoding ID 0 or 1 (see cmap.md). Typically 0x0020 in fonts covering Win-ANSI or similar character sets.
- Code points above 0xFFFF cannot be stored. If the lowest code point is a supplementary character, the field should be 0xFFFF.

### usLastCharIndex

**Format:** uint16.

- **Description:** Highest Unicode code point in the font, as mapped by its platform 3 'cmap' subtable with encoding ID 0 or 1. The value depends on the character sets the font covers.
- Code points above 0xFFFF cannot be stored. A font that supports any supplementary character should store 0xFFFF.

### sTypoAscender

**Format:** FWORD. **Units:** Font design units.

- **Description:** The typographic ascender. Combined with sTypoDescender and sTypoLineGap it gives the default line spacing (see "Line metrics" below).
- It resembles the 'hhea' ascender and usWinAscent, but legacy platforms gave those fields platform-specific behaviour, so they are tied to backward compatibility and do not produce the same layout everywhere. The three sTypo fields exist so that applications can lay out documents correctly and portably.
- sTypoAscender - sTypoDescender need not equal unitsPerEm; the values should suit the primary languages of the font.
- CJK fonts meant for vertical as well as horizontal layout must set sTypoAscender to the top of the ideographic em box. With an em box from (0,-120) to (1000,880), a 1000 x 1000 box sitting 120 units below the Latin baseline, the value must be 880. Other values lead to wrong vertical layout.
- The source's Recommendations chapter (not digested) has more on this field.

### sTypoDescender

**Format:** FWORD. **Units:** Font design units.

- **Description:** The typographic descender, combined with sTypoAscender and sTypoLineGap for the default line spacing. It resembles the 'hhea' descender and usWinDescent, which carry legacy platform behaviour.
- sTypoAscender - sTypoDescender need not equal unitsPerEm.
- CJK fonts meant for vertical layout must set sTypoDescender to the bottom of the ideographic em box: -120 for the em box (0,-120) to (1000,880). Other values lead to wrong vertical layout.
- The source's Recommendations chapter (not digested) has more on this field.

### sTypoLineGap

**Format:** FWORD. **Units:** Font design units.

- **Description:** The typographic line gap, combined with sTypoAscender and sTypoDescender for the default line spacing. It resembles the 'hhea' lineGap, which legacy platforms handle in platform-specific ways and which therefore does not give consistent layout.

### usWinAscent

**Format:** UFWORD. **Units:** Font design units.

- **Description:** The "Windows ascender": the height above the baseline of a clipping region. It resembles sTypoAscender and the 'hhea' ascender, with important differences:
  - Windows GDI sizes the TrueType rasterizer's bitmap surface from usWinAscent and usWinDescent and clips any part of an outline above usWinAscent. To avoid clipping, the value should be >= yMax. This concerns glyphs at their default position, not after GPOS or 'kern' adjustments.
  - When a VDMX table is present and holds data matching the device's aspect ratio and the size being rasterized, that VDMX data takes precedence over usWinAscent and usWinDescent.
  - Some legacy applications compute default line spacing from usWinAscent and usWinDescent; this is strongly discouraged in favour of the sTypo fields. Some applications pick the usWin or the sTypo values according to fsSelection bit 7 (USE_TYPO_METRICS), which keeps old documents stable while newer fonts get better, portable layout.
  - Applications that space lines with the sTypo fields can use the usWin values as a clipping region, for example to decide what to repaint after an edit or how tall to draw a selection.
  - Older editions of the specification suggested the yMax over the Windows "ANSI" character set. New fonts should base the value on their primary languages and allow room for tall glyphs and positioned marks.

### usWinDescent

**Format:** UFWORD. **Units:** Font design units.

- **Description:** The "Windows descender": the extent below the baseline of a clipping region. It resembles sTypoDescender and the 'hhea' descender, but:
  - It counts distances below the baseline as positive, so it is usually positive, while sTypoDescender and the 'hhea' descender are usually negative.
  - Windows GDI clips any part of an outline below -1 x usWinDescent. To avoid clipping, the value should be >= -yMin (default glyph position, before GPOS or 'kern').
  - VDMX data, when present for the current aspect ratio and size, overrides usWinAscent and usWinDescent.
  - The line-spacing and clipping-region remarks of usWinAscent apply here too.
  - Older editions suggested -yMin over the Windows "ANSI" character set. New fonts should base the value on their primary languages and allow room for low descenders and positioned marks.

### ulCodePageRange1-2 (ulCodePageRange*)

- ulCodePageRange1 holds bits 0-31 and ulCodePageRange2 bits 32-63. Each uint32 is stored big-endian.

**Format:** uint32[2] (64 bits total). **Title:** Code Page Character Range.

- **Description:** States which code pages the font covers through its 'cmap' subtable for platform 3 encoding 1 (Windows, Unicode BMP).
  - A font whose 'cmap' uses encoding ID 0 should set the Symbol Character Set bit (bit 31).
  - A set bit means the code page is considered functional; a clear bit means it is not. Bits are independent and may be combined freely. The designer decides what is functional, aiming for whole code pages where possible.
  - Symbol character sets are special. If bit 31 is set and the font has a 'cmap' subtable for platform 3 encoding 1, every character in U+F000 to U+F0FF (inclusive) is used to enumerate the symbol character set. If bit 31 is clear, characters in that range are not enumerated as a symbol character set.
  - All reserved bits must be 0.

| Bit | Code Page | Description |
|---|---|---|
| 0 | 1252 | Latin 1 |
| 1 | 1250 | Latin 2: Eastern Europe |
| 2 | 1251 | Cyrillic |
| 3 | 1253 | Greek |
| 4 | 1254 | Turkish |
| 5 | 1255 | Hebrew |
| 6 | 1256 | Arabic |
| 7 | 1257 | Windows Baltic |
| 8 | 1258 | Vietnamese |
| 9-15 | | Reserved (alternate ANSI) |
| 16 | 874 | Thai |
| 17 | 932 | JIS/Japan |
| 18 | 936 | Simplified Chinese (PRC, Singapore) |
| 19 | 949 | Korean Wansung |
| 20 | 950 | Traditional Chinese (Taiwan, Hong Kong SAR) |
| 21 | 1361 | Korean Johab |
| 22-28 | | Reserved (alternate ANSI or OEM) |
| 29 | | Macintosh (US Roman) character set |
| 30 | | OEM Character Set |
| 31 | | Symbol Character Set |
| 32-47 | | Reserved for OEM |
| 48 | 869 | IBM Greek |
| 49 | 866 | MS-DOS Russian |
| 50 | 865 | MS-DOS Nordic |
| 51 | 864 | Arabic |
| 52 | 863 | MS-DOS Canadian French |
| 53 | 862 | Hebrew |
| 54 | 861 | MS-DOS Icelandic |
| 55 | 860 | MS-DOS Portuguese |
| 56 | 857 | IBM Turkish |
| 57 | 855 | IBM Cyrillic (mainly Russian) |
| 58 | 852 | Latin 2 |
| 59 | 775 | MS-DOS Baltic |
| 60 | 737 | Greek (formerly 437 G) |
| 61 | 708 | Arabic (ASMO 708) |
| 62 | 850 | WE/Latin 1 |
| 63 | 437 | US |

- **Version differences:**
  - Version 0: the fields do not exist. If a version 0 table continues past usWinDescent, ignore the extra data.
  - Version 1: bit 8 was not yet assigned; every other bit now assigned was already defined.
  - Version 2 and later: all bits now assigned were defined.

### sxHeight

**Format:** FWORD. **Units:** Font design units.

- **Description:** Distance from the baseline to the approximate height of lowercase letters without ascenders. Normally chosen by the designer. When that is impossible (for example when converting a legacy font), it may be set to the top of the unscaled, unhinted bounding box of the glyph mapped from U+0078 LATIN SMALL LETTER X; when the font maps nothing to that code point, store 0.
- Possible use: font substitution, scaling one font so that its x-height matches the apparent size of another.
- **Version differences:** Not defined in versions 0 and 1; data past usWinDescent (version 0) or past the code page fields (version 1) is to be ignored. Defined from version 2.

### sCapHeight

**Format:** FWORD. **Units:** Font design units.

- **Description:** Distance from the baseline to the approximate height of uppercase letters. Normally chosen by the designer; failing that (for example when converting a legacy font) it may be set to the top of the unscaled, unhinted bounding box of the glyph mapped from U+0048 LATIN CAPITAL LETTER H, or 0 if there is no such glyph.
- Possible uses: systems that specify type size by cap height in millimetres; alignment, such as aligning the top of a drop capital with the cap height of the first line.
- **Version differences:** Not defined in versions 0 and 1 (extra data after the last field of those versions is ignored). Defined from version 2.

### usDefaultChar

**Format:** uint16.

- **Description:** UTF-16 code point of a character whose glyph can stand in when a requested character is missing from the font. 0 means glyph ID 0 serves as the default glyph.
- It cannot express code points above 0xFFFF, so applications are strongly discouraged from using it.
- **Version differences:** Not defined in versions 0 and 1 (extra data after the last field of those versions is ignored). Defined from version 2.

### usBreakChar

**Format:** uint16.

- **Description:** UTF-16 code point of the default break character, which separates words and is used in justification. Most fonts use U+0020 SPACE.
- It cannot express code points above 0xFFFF, so applications are strongly discouraged from using it.
- **Version differences:** Not defined in versions 0 and 1 (extra data after the last field of those versions is ignored). Defined from version 2.

### usMaxContext

**Format:** uint16.

- **Description:** Length of the longest glyph context that any feature of the font acts on. A font whose only feature is pair kerning stores 2; adding a ligature that turns "f f i" into "ffi" raises it to 3. Line-breaking engines can use it to know how far ahead to look when checking whether a change could alter a line break.
- For chaining contextual lookups, the context length counts the covered glyph, the input sequence and the lookahead sequence together.
- **Version differences:** Not defined in versions 0 and 1 (extra data after the last field of those versions is ignored). Defined from version 2.

### usLowerOpticalPointSize

**Format:** uint16. **Units:** TWIPs.

- **Description:** For fonts that come in several optical-size styles: the lower end of the size range the font was designed for.
- Unit: TWIPs, one twentieth of a point (1440 per inch).
- The bound is inclusive: the font is meant for sizes from this value up to, but not including, usUpperOpticalPointSize.
- Within an optical-size set of fonts in one typographic family, the ranges should leave no intended gaps or overlaps: some other font's usUpperOpticalPointSize equals this value, unless this font covers the lowest range. The smallest-size font of the set stores 0.
- Must be less than usUpperOpticalPointSize. Largest valid value: 0xFFFE.
- A font not designed as one of several optical-size variants stores 0 here and 0xFFFF in usUpperOpticalPointSize.
- The STAT table (see stat.md) supersedes this field; the source's Recommendations chapter (not digested) discusses it.
- **Version differences:** Not defined in versions 0 to 4; data past the last field of a table's version is to be ignored. Defined in version 5.

### usUpperOpticalPointSize

**Format:** uint16. **Units:** TWIPs.

- **Description:** For fonts that come in several optical-size styles: the upper end of the size range the font was designed for, in TWIPs (one twentieth of a point, 1440 per inch).
- The bound is exclusive: the font is meant for sizes below this value, down to usLowerOpticalPointSize.
- Within an optical-size set, some other font's usLowerOpticalPointSize equals this value, unless this font covers the highest range; ranges should leave no intended gaps or overlaps. The largest-size font of the set stores 0xFFFF, which means infinity.
- Must be greater than usLowerOpticalPointSize. Smallest valid value: 2.
- The largest inclusive point size this field can express is 3276.65 points; anything larger has to be written as infinity (0xFFFF).
- A font not designed as one of several optical-size variants stores 0xFFFF here and 0 in usLowerOpticalPointSize.
- The STAT table supersedes this field.
- **Version differences:** Not defined in versions 0 to 4; data past the last field of a table's version is to be ignored. Defined in version 5.

## Line metrics

- Default line spacing from the typographic fields: `sTypoAscender - sTypoDescender + sTypoLineGap`. The source strongly advises applications to use this when fsSelection bit 7 (USE_TYPO_METRICS) is set.
- Some applications choose between the sTypo values and the usWin values according to bit 7; legacy applications that space lines with usWinAscent and usWinDescent do so against the source's advice.
- usWinAscent and usWinDescent are clipping extents (Windows GDI clips outlines outside them, and VDMX data overrides them when present). usWinDescent is positive below the baseline; sTypoDescender is negative below it.
- The 'hhea' ascender, descender and lineGap fields are the Apple-platform counterparts (see hhea.md).

## OS/2 and font variations

- Variable fonts should always define default line metrics through sTypoAscender, sTypoDescender and sTypoLineGap and should set USE_TYPO_METRICS. The 'hhea' ascender, descender and lineGap fields should hold the same values as the three sTypo fields. usWinAscent and usWinDescent should describe a suggested clipping rectangle.
- Per-instance values for some OS/2 fields come from the metrics variations table (see mvar.md), keyed by these value tags:

| OS/2 entry | Tag |
|---|---|
| sCapHeight | 'cpht' |
| sTypoAscender | 'hasc' |
| sTypoDescender | 'hdsc' |
| sTypoLineGap | 'hlgp' |
| sxHeight | 'xhgt' |
| usWinAscent | 'hcla' |
| usWinDescent | 'hcld' |
| yStrikeoutPosition | 'stro' |
| yStrikeoutSize | 'strs' |
| ySubscriptXOffset | 'sbxo' |
| ySubScriptXSize | 'sbxs' |
| ySubscriptYOffset | 'sbyo' |
| ySubscriptYSize | 'sbys' |
| ySuperscriptXOffset | 'spxo' |
| ySuperscriptXSize | 'spxs' |
| ySuperscriptYOffset | 'spyo' |
| ySuperscriptYSize | 'spys' |

The source spells the 'sbxs' entry ySubScriptXSize; it is the ySubscriptXSize field.

- Variable line metrics: the 'hasc', 'hdsc' and 'hlgp' tags vary the ascender, descender and line gap starting from sTypoAscender, sTypoDescender and sTypoLineGap. 'hcla' and 'hcld' may additionally vary the clipping region starting from the usWinAscent and usWinDescent defaults. The other listed tags vary the other metrics.
- usWeightClass and usWidthClass have no variation data, because they correspond to the 'wght' and 'wdth' axes that define the variation space. For an instance, derive them from the 'wght' and 'wdth' user coordinates used to select it; for 'wdth' values above 200, usWidthClass is clamped to 9. The OpenType Design-Variation Axis Tag Registry (not digested) describes how these fields relate to the axes.
- usLowerOpticalPointSize and usUpperOpticalPointSize have no variation data either. They are superseded by STAT, and size-targeted variation is expected to use the 'opsz' axis. If a variable font has an 'opsz' axis, the two fields can be set to match the minValue and maxValue of that axis in 'fvar' (see fvar.md).
