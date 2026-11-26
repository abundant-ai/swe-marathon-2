# cmap - Character to Glyph Index Mapping Table
Source: cmap - Character To Glyph Index Mapping Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/cmap
These notes restate the source's structures and rules; where they differ, the source governs.

## Overview

- 'cmap' maps character codes to default glyph IDs. It holds one or more subtables, each for
  one character encoding; the header lists which encodings are present.
- In every encoding, a code with no glyph in the font maps to glyph ID 0. Glyph 0 must be
  the missing-character glyph (.notdef).
- Every subtable starts with a uint16 format field. Defined formats: 0, 2, 4, 6 (8-bit,
  mixed 8/16-bit and 16-bit codes), 8, 10, 12 (32-bit codes), 13 (many-to-one ranges) and
  14 (Unicode variation sequences).
- Current practice: format 4 (BMP-only fonts) or format 12 (fonts with supplementary-plane
  characters); format 14 for variation sequences; format 13 for last-resort fonts on some
  platforms. Readers must still be prepared to meet any format.
- The table version stays 0 even when newer subtable formats are used.

## 'cmap' header

| Type | Name | Description |
|---|---|---|
| uint16 | version | Table version, 0. |
| uint16 | numTables | Number of encoding records. |
| EncodingRecord | encodingRecords[numTables] | The encoding records. |

## EncodingRecord

| Type | Name | Description |
|---|---|---|
| uint16 | platformID | Platform ID. |
| uint16 | encodingID | Encoding ID, specific to the platform. |
| Offset32 | subtableOffset | Offset from the start of the 'cmap' table to the subtable. |

Rules for encoding records and subtable choice:

- platformID plus encodingID identify the encoding. For the Macintosh platform the
  subtable's language field is part of the identification as well.
- Records are sorted by platformID, then encodingID, then the language field of the
  subtable they point to. Each (platformID, encodingID, language) triple occurs at most once.
- Except for a format 14 subtable, subtables are alternatives: an application picks one and
  ignores the rest. When the chosen subtable is a Unicode one (platform 0, or platform 3
  with encoding 1 or 10), a format 14 subtable under platform 0 / encoding 5 may be used in
  addition, for variation sequences.
- If a font has both a 16-bit Unicode subtable (normally format 4) and a 32-bit one
  (format 10 or 12), the 32-bit one should cover a superset of the 16-bit one, and
  applications should use the 32-bit one.
- Fonts should not carry both format 4 and format 6 Unicode BMP subtables (format 4 is the
  one to use), nor both format 10 and format 12 (format 12 is the one to use).
- When Unicode subtables of the same format exist under different platform IDs, an
  application may use either, but should choose the same one every time it uses the font.

### Platform IDs

| Platform ID | Platform name | Platform-specific encoding IDs |
|---|---|---|
| 0 | Unicode | Various |
| 1 | Macintosh | Script manager code |
| 2 | ISO [deprecated] | ISO encoding [deprecated] |
| 3 | Windows | Windows encoding |
| 4 | Custom | Custom |

Platform IDs 240 to 255 are reserved for user-defined platforms and are never assigned to
a registered platform.

### Unicode platform (platform ID 0) encoding IDs

| Encoding ID | Description |
|---|---|
| 0 | Unicode 1.0 semantics (deprecated). |
| 1 | Unicode 1.1 semantics (deprecated). |
| 2 | ISO/IEC 10646 semantics (deprecated). |
| 3 | Unicode 2.0 and later semantics, BMP only. |
| 4 | Unicode 2.0 and later semantics, full repertoire. |
| 5 | Unicode variation sequences; for subtable format 14. |
| 6 | Unicode full repertoire; for subtable format 13. |

- Encoding IDs 0, 1 and 2 are deprecated.
- Encoding 3 goes with formats 4 or 6; encoding 4 goes with formats 10 or 12.
- A format 14 subtable is allowed only under platform 0, encoding 5, and encoding 5 should
  be used only for format 14.
- Encoding 6 should be used only with format 13, and format 13 only under platform 0,
  encoding 6.

### Macintosh platform (platform ID 1)

Needed by older Macintosh systems, discouraged on current Apple platforms. Its encoding IDs
are the Macintosh script codes listed in the 'name' table chapter.

### ISO platform (platform ID 2), deprecated

| Code | ISO encoding |
|---|---|
| 0 | 7-bit ASCII |
| 1 | ISO 10646 |
| 2 | ISO 8859-1 |

### Windows platform (platform ID 3) encoding IDs

| Platform ID | Encoding ID | Description |
|---|---|---|
| 3 | 0 | Symbol |
| 3 | 1 | Unicode BMP |
| 3 | 2 | ShiftJIS |
| 3 | 3 | PRC |
| 3 | 4 | Big5 |
| 3 | 5 | Wansung |
| 3 | 6 | Johab |
| 3 | 7 | Reserved |
| 3 | 8 | Reserved |
| 3 | 9 | Reserved |
| 3 | 10 | Unicode full repertoire |

- Fonts for Windows should always provide a Unicode subtable: (3, 1) or (3, 10).
- A font limited to the BMP (U+0000 to U+FFFF) uses encoding 1 with a format 4 subtable;
  encoding 1 must not be used for supplementary-plane characters.
- A font with supplementary-plane characters (U+10000 to U+10FFFF) uses encoding 10 with a
  format 12 subtable.
- Symbol encoding (3, 0): a format 4 subtable, normally with up to 224 symbols at codes
  starting at 0xF020 (a part of the Private Use Area, although this is not a Unicode
  encoding). Legacy software sent single-byte codes and mapped byte 0x20 to the font's
  OS/2.usFirstCharIndex. New fonts should instead put non-Unicode symbols at PUA code points
  in a Unicode subtable.

### Custom platform (platform ID 4) and the OTF Windows NT compatibility mapping

| ID | Custom encoding |
|---|---|
| 0-255 | OTF Windows NT compatibility mapping |

- A legacy platform for OpenType fonts converted from Type 1 fonts whose encoding is not
  StandardEncoding, so that non-Unicode applications can treat them as Windows ANSI fonts.
  Not for new fonts.
- The encoding ID equals the Windows charset value (0 to 255) from the original font's .PFM
  file.
- The subtable must be format 0 or 6 and must match the CFF encoding.
- For a CFF-outline font with such a subtable, the Windows NT OTF driver (a) overlays the
  glyphs at codes 0-255 onto the matching Windows ANSI (code page 1252) Unicode values of the
  Unicode mapping it reports, (b) adds charset 0 (Windows ANSI) to the font's supported
  charsets, and (c) also adds the encoding ID, read as a charset value, to that list.

## The language field

The source says every subtable format has a language field; in the layouts it gives, formats
0 to 13 have one and format 14 does not.

- For any platform other than Macintosh (1), language must be 0.
- For Macintosh subtables, language is the Macintosh language ID plus 1, or 0 when the
  subtable is not language-specific (so Turkish, Mac language ID 17, is stored as 18, and
  Mac OS Roman is stored as 0).

## Format 0: byte encoding table

'cmap' Subtable Format 0:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 0. |
| uint16 | length | Byte length of the subtable. |
| uint16 | language | See "The language field". |
| uint8 | glyphIdArray[256] | Glyph ID for each code 0-255. |

Direct one-to-one lookup: glyph = glyphIdArray[code]. Only glyph IDs 0 to 255 can be
reached.

## Format 2: high-byte mapping through table

For mixed 8/16-bit East Asian encodings (now rare). Some byte values introduce a 2-byte
code (those values may also occur as second bytes); the mapping of 2-byte codes depends
mostly on the first byte.

'cmap' Subtable Format 2:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 2. |
| uint16 | length | Byte length of the subtable. |
| uint16 | language | See "The language field". |
| uint16 | subHeaderKeys[256] | For each high byte, the index of its SubHeader multiplied by 8. |
| SubHeader | subHeaders[ ] | Variable number of SubHeader records. |
| uint16 | glyphIdArray[ ] | Variable-length pool of sub-arrays used to map the low byte. |

SubHeader Record:

| Type | Name | Description |
|---|---|---|
| uint16 | firstCode | First low-byte value covered. |
| uint16 | entryCount | Number of low-byte values covered. |
| int16 | idDelta | Value added to non-zero glyph IDs from the sub-array. |
| uint16 | idRangeOffset | Byte distance from this field to the glyphIdArray element for firstCode. |

Lookup:

1. Take the first byte b of the code; k = subHeaderKeys[b] / 8.
2. If k == 0, the code is a single byte: SubHeader 0 maps the byte b itself and no second
   byte is consumed. Otherwise the code is two bytes and SubHeader k maps the second byte.
3. With the byte v being mapped and SubHeader s: if v < s.firstCode or
   v >= s.firstCode + s.entryCount, the result is glyph 0. (The covered range always lies
   inside 0-255.)
4. Otherwise read g from the sub-array: the element for firstCode sits s.idRangeOffset bytes
   after the position of the idRangeOffset field itself, and the element for v is
   (v - firstCode) entries after that. The sub-array has entryCount entries.
5. If g == 0 the result is glyph 0. Otherwise the glyph is (g + idDelta) modulo 65536 (add
   65536 to a negative sum). idDelta lets several SubHeaders share one sub-array.

## Format 4: segment mapping to delta values

The standard subtable for BMP-only fonts (U+0000 to U+FFFF); supplementary-plane support
uses format 12. Codes are grouped into contiguous segments, which may have holes. The data
is, in this order: a search header, four parallel per-segment arrays, and a glyph ID array.

'cmap' Subtable Format 4:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 4. |
| uint16 | length | Byte length of the subtable. |
| uint16 | language | See "The language field". |
| uint16 | segCountX2 | segCount * 2. |
| uint16 | searchRange | 2 * (largest power of 2 <= segCount), that is (2**floor(log2(segCount))) * 2. |
| uint16 | entrySelector | log2(searchRange / 2), equal to floor(log2(segCount)). |
| uint16 | rangeShift | segCount * 2 - searchRange. |
| uint16 | endCode[segCount] | Last code of each segment; the final one is 0xFFFF. |
| uint16 | reservedPad | 0. |
| uint16 | startCode[segCount] | First code of each segment. |
| int16 | idDelta[segCount] | Delta applied to codes of each segment. |
| uint16 | idRangeOffset[segCount] | 0, or a byte offset into glyphIdArray (see below). |
| uint16 | glyphIdArray[ ] | Glyph ID pool, any length. |

Rules:

- segCount = segCountX2 / 2. searchRange, entrySelector and rangeShift are derived from it
  (for segCount 39: segCountX2 78, searchRange 64, entrySelector 5, rangeShift 14). They
  only help a binary search. Wrong values have been used to attack parsers, so readers
  should compute them from segCountX2 rather than trust the stored values; fonts should
  still store correct values.
- Segments are sorted by increasing endCode. The last segment must have startCode and
  endCode 0xFFFF so that the search always ends; it need not map anything useful (it may
  just map 0xFFFF to glyph 0), but it must exist.

Lookup of code c:

1. Find the first segment i with endCode[i] >= c. If startCode[i] > c, return glyph 0.
2. If idRangeOffset[i] == 0: glyph = (idDelta[i] + c) modulo 65536 (add 65536 to a negative
   sum).
3. Otherwise read the uint16 g located at
   address(idRangeOffset[i]) + idRangeOffset[i] + 2 * (c - startCode[i]),
   that is, idRangeOffset[i] / 2 + (c - startCode[i]) uint16 entries past the
   idRangeOffset[i] slot itself. This works because glyphIdArray follows idRangeOffset
   directly. If g == 0 return glyph 0; otherwise glyph = (g + idDelta[i]) modulo 65536.

## Format 6: trimmed table mapping

For 16-bit codes that fall in one contiguous range.

'cmap' Subtable Format 6:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 6. |
| uint16 | length | Byte length of the subtable. |
| uint16 | language | See "The language field". |
| uint16 | firstCode | First code of the range. |
| uint16 | entryCount | Number of codes in the range. |
| uint16 | glyphIdArray[entryCount] | Glyph ID for each code in the range. |

Codes outside firstCode .. firstCode + entryCount - 1 map to glyph 0; otherwise
glyph = glyphIdArray[code - firstCode].

## Format 8: mixed 16-bit and 32-bit coverage

Meant for UTF-16 text containing supplementary-plane characters; rarely used, not widely
supported, and discouraged. It assumes no 32-bit code shares its high 16 bits with a 16-bit
code (in Unicode this could only clash for U+0000 to U+0010, which are control
characters), so a 16-bit unit alone tells whether it starts a 32-bit code.

'cmap' Subtable Format 8:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 8. |
| uint16 | reserved | 0. |
| uint32 | length | Byte length of the subtable, header included. |
| uint32 | language | See "The language field". |
| uint8 | is32[8192] | Bit array, one bit per 16-bit value: set when that value is the first half of a 32-bit code. |
| uint32 | numGroups | Number of groups. |
| SequentialMapGroup | groups[numGroups] | The groups. |

SequentialMapGroup Record (format 8):

| Type | Name | Description |
|---|---|---|
| uint32 | startCharCode | First code of the group; for 16-bit codes (per is32) the high 16 bits are 0. |
| uint32 | endCharCode | Last code of the group; same convention. |
| uint32 | startGlyphID | Glyph ID of startCharCode; later codes map to consecutive glyph IDs. |

Rules:

- The bit for 16-bit value cp is is32[cp / 8] & (1 << (7 - (cp % 8))); non-zero means cp is
  the first half of a 32-bit code.
- A high half of 0 is not special. A font must not have a glyph for code 0x0000 and also
  glyphs for 32-bit codes whose high half is 0x0000.
- is32 is meaningful even for values with no glyphs, because text processing needs to know
  how many bytes the current character occupies.
- Groups are sorted by increasing startCharCode, and each group's endCharCode is less than
  the next group's startCharCode.
- A code c inside group g maps to g.startGlyphID + (c - g.startCharCode).

## Format 10: trimmed array

The 32-bit analogue of format 6. Rarely used and not supported on Windows.

'cmap' Subtable Format 10:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 10. |
| uint16 | reserved | 0. |
| uint32 | length | Byte length of the subtable, header included. |
| uint32 | language | See "The language field". |
| uint32 | startCharCode | First code covered. |
| uint32 | numChars | Number of codes covered. |
| uint16 | glyphIdArray[] | Glyph ID for each covered code. |

glyph = glyphIdArray[c - startCharCode] for startCharCode <= c < startCharCode + numChars;
other codes map to glyph 0.

## Format 12: segmented coverage

The standard subtable for repertoires that include supplementary-plane characters
(U+10000 to U+10FFFF). A format 4 subtable may also be present for older applications but
is not required. Like format 4, but with 32-bit codes and sequential groups.

'cmap' Subtable Format 12:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 12. |
| uint16 | reserved | 0. |
| uint32 | length | Byte length of the subtable, header included. |
| uint32 | language | See "The language field". |
| uint32 | numGroups | Number of groups. |
| SequentialMapGroup | groups[numGroups] | The groups. |

SequentialMapGroup Record (format 12; same layout as format 8, but every code is a plain
32-bit value):

| Type | Name | Description |
|---|---|---|
| uint32 | startCharCode | First code of the group. |
| uint32 | endCharCode | Last code of the group. |
| uint32 | startGlyphID | Glyph ID of startCharCode. |

Groups are sorted by increasing startCharCode, with each endCharCode below the next
group's startCharCode. Code c in group g maps to g.startGlyphID + (c - g.startCharCode);
codes in no group map to glyph 0.

## Format 13: many-to-one range mappings

Maps whole ranges of codes to one glyph each, for example in last-resort fonts (see also
bit 14 of the 'head' flags, head.md). Same layout as format 12; only the meaning of the
glyph field differs.

'cmap' Subtable Format 13:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 13. |
| uint16 | reserved | 0. |
| uint32 | length | Byte length of the subtable, header included. |
| uint32 | language | See "The language field". |
| uint32 | numGroups | Number of groups. |
| ConstantMapGroup | groups[numGroups] | The groups. |

ConstantMapGroup Record:

| Type | Name | Description |
|---|---|---|
| uint32 | startCharCode | First code of the group. |
| uint32 | endCharCode | Last code of the group. |
| uint32 | glyphID | The one glyph ID used for every code in the group. |

Code c with startCharCode <= c <= endCharCode maps to glyphID (not glyphID plus an
offset). Format 13 is used only under platform 0, encoding 6.

## Format 14: Unicode variation sequences

A Unicode variation sequence (UVS) is a base character followed by a variation selector,
for example <U+82A6, U+E0101>. Format 14 lists the UVSes the font supports and is used only
under platform 0, encoding 5, alongside the font's regular Unicode subtable (BMP or full
repertoire).

Each supported UVS is either:

- default: the glyph for the sequence is the glyph the regular Unicode subtable gives for the
  base character alone; or
- non-default: the glyph for the sequence is stored in the format 14 subtable.

'cmap' Subtable Format 14:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 14. |
| uint32 | length | Byte length of the subtable, header included. |
| uint32 | numVarSelectorRecords | Number of VariationSelector records. |
| VariationSelector | varSelector[numVarSelectorRecords] | The records. |

Note: format 14 has no language field.

VariationSelector Record:

| Type | Name | Description |
|---|---|---|
| uint24 | varSelector | The variation selector code point. |
| Offset32 | defaultUVSOffset | Offset from the start of the format 14 subtable to a DefaultUVS table; 0 if none. |
| Offset32 | nonDefaultUVSOffset | Offset from the start of the format 14 subtable to a NonDefaultUVS table; 0 if none. |

Records are sorted by increasing varSelector, with no duplicates. One record, with the
tables it points to, lists every supported UVS that uses its selector: the base characters
are in the two tables, split into default and non-default ones, and the NonDefaultUVS table
supplies the glyph IDs of the non-default ones.

### DefaultUVS table

A range-compressed list of the base characters of default UVSes for this selector.

DefaultUVS Table:

| Type | Name | Description |
|---|---|---|
| uint32 | numUnicodeValueRanges | Number of ranges. |
| UnicodeRange | ranges[numUnicodeValueRanges] | The ranges. |

UnicodeRange Record:

| Type | Name | Description |
|---|---|---|
| uint24 | startUnicodeValue | First code point of the range. |
| uint8 | additionalCount | Number of code points in the range after the first (0 for a single code point). |

- A range covers startUnicodeValue .. startUnicodeValue + additionalCount inclusive (for
  U+4E4D to U+4E4F: start 0x004E4D, additionalCount 2).
- startUnicodeValue + additionalCount must not exceed 0xFFFFFF.
- Ranges are sorted by increasing startUnicodeValue and do not overlap: the end of a range
  is less than the start of the next one.
- The listed code points should also be mapped in a Unicode subtable, but readers can meet
  fonts where they are not.

### NonDefaultUVS table

Pairs of base character and glyph ID for the non-default UVSes of this selector.

NonDefaultUVS Table:

| Type | Name | Description |
|---|---|---|
| uint32 | numUVSMappings | Number of mappings. |
| UVSMapping | uvsMappings[numUVSMappings] | The mappings. |

UVSMapping Record:

| Type | Name | Description |
|---|---|---|
| uint24 | unicodeValue | Base character of the sequence. |
| uint16 | glyphID | Glyph to use for the sequence. |

Mappings are sorted by increasing unicodeValue, with no duplicates. A base character listed
here usually, but not necessarily, also has a mapping in the regular Unicode subtable (it may
be meant to appear only inside variation sequences).

### Resolving a base character plus selector

1. Binary-search the VariationSelector records for varSelector == selector. If there is
   none, the font does not support any sequence with this selector.
2. If nonDefaultUVSOffset != 0 and base is found among that table's unicodeValue entries,
   the glyph is that entry's glyphID.
3. Else if defaultUVSOffset != 0 and base lies in one of that table's ranges, the sequence is
   supported and its glyph is whatever the regular Unicode subtable maps base to.
4. Otherwise the font does not support this sequence. The source leaves the fallback (for
   example, using the base character's ordinary glyph) to the application.

Usage pattern given by the source: a font that wants JIS2004 shapes by default maps U+82A6
to the JIS2004 glyph in its Unicode subtable, lists U+82A6 in the DefaultUVS table of
selector U+E0101, and maps U+82A6 to the JIS90 glyph in the NonDefaultUVS table of selector
U+E0100; a font defaulting to JIS90 shapes does the reverse.
