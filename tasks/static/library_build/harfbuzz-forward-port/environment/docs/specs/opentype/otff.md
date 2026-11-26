# OpenType Font File - Data Types, Table Directory and Collections
Source: OpenType font file (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/otff
These notes restate the source's structures and rules; where they differ, the source governs.

## Overview

- A font file is a set of tables. A table directory at the start of the file (or, in a collection, a TTC header that points to one directory per font) locates every top-level table.
- Tables carry layout data (glyph selection and placement), glyph descriptions (TrueType or CFF outlines, monochrome or color bitmaps, SVG documents, binary 2D vector graphics compositions) and metadata such as name strings.
- File name extensions: .OTF, .TTF, .OTC or .TTC, in upper or lower case. .OTC and .TTC are for collection files only: .TTC for collections with TrueType outlines, .OTC for collections with CFF or CFF2 outlines.
- Every multi-byte value in an OpenType font is big-endian (network byte order).

## Data types

| Data Type | Description |
|---|---|
| uint8 | Range 0 to 255; an 8-bit unsigned integer. |
| int8 | Two's complement, range -128 to 127; an 8-bit signed integer. |
| uint16 | Range 0 to 65535; a 16-bit unsigned integer. |
| int16 | Two's complement, range -32768 to 32767; a 16-bit signed integer. |
| uint24 | Three bytes, range 0 to 16777215; a 24-bit unsigned integer. |
| uint32 | Range 0 to 4294967295; a 32-bit unsigned integer. |
| int32 | Two's complement, range -2147483648 to 2147483647; a 32-bit signed integer. |
| Fixed | A 32-bit signed fixed-point number (16.16): high 16 bits signed integer part, low 16 bits fraction, value = int32 / 65536. |
| FWORD | Signed distance or coordinate; an int16 that describes a quantity in font design units. |
| UFWORD | Unsigned distance; a uint16 that describes a quantity in font design units. |
| F2DOT14 | Signed 2.14 fixed-point in 16 bits: value = int16 / 16384, range -2.0 to 1.99993896484375. |
| LONGDATETIME | Signed 64-bit count of seconds since 1904-01-01 00:00:00 UTC. |
| Tag | Four uint8 values (32 bits) that name a table, variation axis, script, language system, feature or baseline. |
| Offset8 | Offset to a table stored like a uint8 (one byte); NULL is 0x00. |
| Offset16 | Offset to a table stored like a uint16 ("short" offset); NULL is 0x0000. |
| Offset24 | Offset to a table stored like a uint24 (three bytes); NULL is 0x000000. |
| Offset32 | Offset to a table stored like a uint32 ("long" offset); NULL is 0x00000000. |
| Version16Dot16 | Packed 32-bit major/minor version (see Table version numbers). |

### F2DOT14

The 16 bits are a two's-complement integer part in the top 2 bits plus an unsigned 14-bit fraction; the value is the integer part plus fraction / 16384, which equals the int16 reading divided by 16384. Reference points:

| Bits | Value | Integer part | Fraction part |
|---|---|---|---|
| 0x7FFF | 1.999939 | 1 | 16383/16384 |
| 0x7000 | 1.75 | 1 | 12288/16384 |
| 0x0001 | 0.000061 | 0 | 1/16384 |
| 0x0000 | 0.0 | 0 | 0/16384 |
| 0xFFFF | -0.000061 | -1 | 16383/16384 |
| 0x8000 | -2.0 | -2 | 0/16384 |

### Tag syntax

- A Tag is formally a 4-byte array, conventionally written as four characters.
- Every byte must be in 0x20 to 0x7E (printable ASCII, identical to Basic Latin in UTF-8).
- Tags are case-sensitive.
- A tag has one to four non-space characters followed by space (0x20) padding to four bytes. A space may never be followed by a non-space, so leading and embedded spaces are not allowed.
- Examples with padding: 'cvt ' is 0x63767420, 'CFF ' is 0x43464620, 'SVG ' is 0x53564720; 'OS/2' (0x4F532F32) has no padding.

### Records, tables and offsets

- Tables are reached through offsets. An offset stored in a table is normally counted from the start of that table.
- Records sit inline, one after another, either as a run of fields or as an array of same-type records. An offset stored in a record is normally counted from the start of the parent table that contains the record, because the target is a subtable of that parent.
- A NULL offset (0) is allowed only where a format says the subtable is optional; it always means the subtable is absent and must never be followed as a real offset.
- Where a format does not allow NULL, font tools must write a subtable of the required format, even an empty stub such as a Coverage table with no glyphs. Parsers should still be prepared for non-conforming fonts that store NULL in such fields.

## Table version numbers

| Version field form | Where it is used |
|---|---|
| One uint16 | Many tables; versions usually start at 0. |
| Separate uint16 major and uint16 minor fields | Many tables; versions usually start at 1.0. |
| uint32 holding enumerated values | Some tables. The table directory's sfntVersion is also a uint32 with enumerated values, some of which are tags. |
| uint32 holding a plain number | Only the DSIG and 'meta' tables. |
| Version16Dot16 | Only the 'maxp', 'post' and 'vhea' tables; no other table will use it. |

Version16Dot16: the upper 16 bits are the major version and the lower 16 bits the minor version, with the minor digits stored in the high-order nibbles of the low half. 'maxp' version 0.5 is 0x00005000 and 'vhea' version 1.1 is 0x00011000. The type exists for backward compatibility only: these fields were once documented as Fixed, but their minor parts never followed Fixed arithmetic, so 0x00005000 must be read as 0.5, not as 0x5000 / 65536.

Reader rules:

1. Always check a table's version before parsing it.
2. A minor version increase only adds compatible extensions. If the major version is understood, the table can be read; fields added by a newer minor version are simply not seen.
3. Versions stored as a single uint16 or uint32 behave like minor versions: every change is a compatible extension.
4. Reserved or unassigned fields, bits and values may gain meaning in later minor versions. Readers must not rely on their contents and may ignore them; writers store zero; validators warn about non-zero values not defined for the version being checked.
5. If the major version is not recognized, do not parse the table at all; treat it as missing.

## Table directory

The table directory is the first structure of a single-font file and starts at byte 0. In a collection, each font's directory is located through the TTC header.

### TableDirectory

| Type | Name | Description |
|---|---|---|
| uint32 | sfntVersion | Outline-flavour marker: 0x00010000 or 0x4F54544F ('OTTO'); see the value table below. |
| uint16 | numTables | How many table records follow. |
| uint16 | searchRange | 16 * 2^floor(log2(numTables)): the largest power of two not above numTables, times 16. |
| uint16 | entrySelector | floor(log2(numTables)), which equals log2(searchRange / 16). |
| uint16 | rangeShift | numTables * 16 - searchRange. |
| TableRecord | tableRecords[numTables] | One record per top-level table, sorted by tag. |

sfntVersion values:

| Value | Meaning |
|---|---|
| 0x00010000 | Font with TrueType outlines. |
| 0x4F54544F ('OTTO') | Font with CFF data (CFF version 1 or CFF2). |
| 'true' (0x74727565), 'typ1' (0x74797031) | Allowed by Apple's TrueType Reference Manual; should not be used for OpenType fonts. |

Binary-search helper fields: searchRange, entrySelector and rangeShift exist so that early implementations could binary-search the 16-byte records quickly. Because wrong stored values can be used to attack parsers, readers should compute them from numTables and not rely on the stored values. Fonts should still store correct values for compatibility.

### TableRecord

| Type | Name | Description |
|---|---|---|
| Tag | tableTag | Tag naming the table. |
| uint32 | checksum | Checksum of the table's contents (see Checksums). |
| Offset32 | offset | Start of the table, counted from the first byte of the font file. |
| uint32 | length | Size of the table in bytes, padding excluded. |

Rules readers depend on:

- numTables varies: a font contains only the tables it needs.
- tableRecords must be sorted in ascending tag order. Comparing tags as big-endian uint32 values (byte by byte) gives that order, so the array can be binary-searched.
- For any tag defined by OpenType, a font should have at most one table record. If it has several, results are unpredictable: an implementation may pick any one of them or reject the font. Specifications of custom tables defined elsewhere may allow several tables with the same tag.
- Platform vendors and tools may add their own tables and tags (Apple's TrueType Reference Manual defines several that OpenType does not); a font that contains them can still be a valid OpenType font. Apple reserves tags made only of lowercase letters for its own use.
- Each top-level table starts on a 4-byte boundary, and gaps between tables are filled with zero bytes. length records the real data length, not the padded length.
- The 4-byte alignment applies only to top-level tables; subtable offsets, records and fields inside a table carry no such requirement.
- Tables should be stored contiguously without overlapping each other. Even if data of different tables is interleaved, each table's length must cover one contiguous byte range that contains all of that table's data, subtables included.
- In a collection file, offset counts from the start of the collection file (see Font collections).

## Checksums

A table checksum is the sum, modulo 2^32, of the table read as consecutive big-endian uint32 values. When the length is not a multiple of 4, the data is treated as if zero bytes padded it to the next multiple of 4 (the recorded length itself excludes padding).

```
table_checksum(data, length):
    total = 0                                   # unsigned 32-bit, wraps on overflow
    for start in 0, 4, 8, ... while start < length:
        word = 0
        for k in 0 .. 3:
            b = data[start + k] if start + k < length else 0     # implicit zero padding
            word = (word << 8) | b
        total = (total + word) mod 2^32
    return total
```

The 'head' table needs special treatment because its checksumAdjustment field (a uint32 at byte offset 8 of 'head'; see head.md) is written after the directory checksums have been computed.

Writing a font:

1. Store 0 in head.checksumAdjustment.
2. Compute the checksum of every table, 'head' included, and store each in its TableRecord.
3. Compute the same kind of checksum over the entire font file.
4. Store (0xB1B0AFBA - that whole-font sum) mod 2^32 in head.checksumAdjustment.

Checking 'head': compute its checksum with the four checksumAdjustment bytes taken as zero, whatever they actually contain, and compare that with the checksum in the 'head' TableRecord.

Collections: table checksums describe the tables exactly as they are stored in the collection file. checksumAdjustment is not used in collections and may be 0.

## Font collections

- A collection (TTC or OTC, historically "TrueType Collection") stores several font resources in one file so that tables with identical data can be shared, typically glyph data common to several fonts.
- Any outline type may be used, mixed if wanted, with or without layout tables. A collection may include one or more variable fonts, alone or together with non-variable fonts; a variable font does not need a collection.
- The file holds one TTC header, one complete table directory per font (in the same TableDirectory format as a single-font file), and the tables.
- The TTC header is at offset 0 of the file.
- Table offsets in every table directory of the collection are counted from the beginning of the collection file.
- A table is used by a font when that font's directory points to it. Some tables appear once per font; others are shared by several fonts.
- Tables that identify a font and its character mapping, including 'cmap', 'name' and OS/2, should have a separate copy per font. Tables holding glyph or instruction data, or indexed by glyph ID, should be shared: 'glyf', 'loca', 'maxp', 'hmtx', 'hdmx', 'cvt ', 'fpgm', 'prep', LTSH, EBDT, EBLC, EBSC and similar. In general any table whose data is identical across fonts may be shared.
- When fonts are merged into a collection, glyph renumbering affects 'cmap' and other glyph-indexed data, and the fonts' TrueType instructions (pre-programs, function definitions, control values) must not conflict.

### TTC header

- Version 1.0 is for collections without a digital signature. Version 2.0 may be used with or without one; when there is no signature its last three fields are 0.
- When a signature is present, the DSIG table must be the last table in the file, after all other font tables, and it is expected to use signature format 1.
- The header identifies the file as a collection, gives its version and the number of fonts, and lists the offset of each font's table directory.

#### TTCHeader Version 1.0

| Type | Name | Description |
|---|---|---|
| Tag | ttcTag | Collection signature 'ttcf' (0x74746366), used whatever the outline format. |
| uint16 | majorVersion | 1 for this header version. |
| uint16 | minorVersion | 0 for this header version. |
| uint32 | numFonts | How many fonts the collection holds. |
| Offset32 | tableDirectoryOffsets[numFonts] | Start of each font's TableDirectory, counted from the beginning of the file. |

#### TTCHeader Version 2.0

| Type | Name | Description |
|---|---|---|
| Tag | ttcTag | Collection signature 'ttcf' (0x74746366). |
| uint16 | majorVersion | 2 for this header version. |
| uint16 | minorVersion | 0 for this header version. |
| uint32 | numFonts | How many fonts the collection holds. |
| Offset32 | tableDirectoryOffsets[numFonts] | Start of each font's TableDirectory, counted from the beginning of the file. |
| uint32 | dsigTag | 0x44534947 ('DSIG') when the file is signed, otherwise 0. |
| uint32 | dsigLength | Byte length of the DSIG table, or 0 when unsigned. |
| uint32 | dsigOffset | Start of the DSIG table counted from the beginning of the file, or 0 when unsigned. |

Reading a font file:

1. Read the first uint32. If it is 'ttcf', the file is a collection: read majorVersion, minorVersion, numFonts and the directory offsets; with majorVersion 2, three DSIG fields follow the offsets.
2. Otherwise the file holds one font whose TableDirectory starts at byte 0 (sfntVersion 0x00010000 or 'OTTO').
3. For each font, read its TableDirectory; every TableRecord offset is counted from byte 0 of the file in both cases.

## Font tables

The tag lists below follow the source's grouping; some tags appear in more than one group. Tags are given as the source writes them (quotes around lowercase tags; note the trailing space in 'cvt ', 'CFF ' and 'SVG ').

### Required tables

All eight are required for a working font, whether it uses TrueType or CFF outlines.

| Tag | Name | Digest |
|---|---|---|
| 'cmap' | Character to glyph mapping | cmap.md |
| 'head' | Font header | head.md |
| 'hhea' | Horizontal header | hhea.md |
| 'hmtx' | Horizontal metrics | hmtx.md |
| 'maxp' | Maximum profile | - |
| 'name' | Naming table | - |
| OS/2 | OS/2 and Windows specific metrics | os2.md |
| 'post' | PostScript information | - |

### Tables related to TrueType outlines

| Tag | Name | Digest |
|---|---|---|
| 'cvt ' | Control Value Table (optional table) | - |
| 'fpgm' | Font program (optional table) | - |
| 'glyf' | Glyph data | glyf.md |
| 'loca' | Index to location | - |
| 'prep' | Control Value Program (optional table) | - |
| 'gasp' | Grid-fitting/Scan-conversion (optional table) | - |

### Tables related to CFF outlines

| Tag | Name | Digest |
|---|---|---|
| 'CFF ' | Compact Font Format 1.0 | - |
| CFF2 | Compact Font Format 2.0 | - |
| VORG | Vertical Origin (optional table) | - |

CFF fonts meant for vertical writing are strongly advised to include VORG.

### Table related to SVG outlines

| Tag | Name | Digest |
|---|---|---|
| 'SVG ' | The SVG (Scalable Vector Graphics) table | - |

### Tables related to bitmap glyphs

| Tag | Name | Digest |
|---|---|---|
| EBDT | Embedded bitmap data | - |
| EBLC | Embedded bitmap location data | - |
| EBSC | Embedded bitmap scaling data | - |
| CBDT | Color bitmap data | cbdt.md |
| CBLC | Color bitmap location data | cblc.md |
| 'sbix' | Standard bitmap graphics | - |

Bitmaps may accompany outlines. When the font has a bitmap for a glyph at the size being rendered, the system draws the bitmap instead of the outline.

### Advanced typographic tables

All optional.

| Tag | Name | Digest |
|---|---|---|
| BASE | Baseline data | base.md |
| GDEF | Glyph definition data | gdef.md |
| GPOS | Glyph positioning data | gpos.md |
| GSUB | Glyph substitution data | gsub.md |
| JSTF | Justification data | jstf.md |
| MATH | Math layout data | - |

Their shared formats are described in chapter2.md.

### Tables used for OpenType Font Variations

| Tag | Name | Digest |
|---|---|---|
| 'avar' | Axis variations | avar.md |
| 'cvar' | CVT variations (TrueType outlines only) | - |
| 'fvar' | Font variations | fvar.md |
| 'gvar' | Glyph variations (TrueType outlines only) | gvar.md |
| HVAR | Horizontal metrics variations | hvar.md |
| MVAR | Metrics variations | mvar.md |
| STAT | Style attributes (required for variable fonts, optional for non-variable fonts) | stat.md |
| VVAR | Vertical metrics variations | - |

Shared variation formats are described in otvarcommonformats.md; which tables a variable font must or may contain is set out in the Font Variations overview chapter. Variation data can also live outside these tables: GDEF, BASE and COLR in a variable font may carry it using the common variation formats, and a CFF2 table may carry it in formats of its own.

### Tables related to color fonts

| Tag | Name | Digest |
|---|---|---|
| COLR | Color table | colr.md |
| CPAL | Color palette table | cpal.md |
| CBDT | Color bitmap data | cbdt.md |
| CBLC | Color bitmap location data | cblc.md |
| 'sbix' | Standard bitmap graphics | - |
| 'SVG ' | The SVG (Scalable Vector Graphics) table | - |

CBDT, CBLC, 'sbix' and 'SVG ' also appear in the SVG and bitmap groups above.

### Other OpenType tables

| Tag | Name | Digest |
|---|---|---|
| DSIG | Digital signature | - |
| 'hdmx' | Horizontal device metrics | - |
| 'kern' | Kerning | kern.md |
| LTSH | Linear threshold data | - |
| MERG | Merge | - |
| 'meta' | Metadata | - |
| STAT | Style attributes | stat.md |
| PCLT | PCL 5 data | - |
| VDMX | Vertical device metrics | - |
| 'vhea' | Vertical Metrics header | vhea.md |
| 'vmtx' | Vertical Metrics | vmtx.md |

STAT is required in variable fonts. 'hdmx' and VDMX are not used in variable fonts.
