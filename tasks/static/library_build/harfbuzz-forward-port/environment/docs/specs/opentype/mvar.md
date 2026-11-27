# MVAR - Metrics Variations Table
Source: MVAR - Metrics Variations Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/mvar
These notes restate the source's structures and rules; where they differ, the source governs.

## Role

- MVAR varies font-wide metric values kept in OS/2, 'hhea', 'vhea', 'gasp' and 'post'.
- Its deltas live in an ItemVariationStore (otvarcommonformats.md), the structure HVAR and GDEF
  also use; it is unrelated to the tuple variation store of 'gvar' and 'cvar'.
- An array of value records names each varying target with a four-byte tag (for example
  'hasc' for OS/2.sTypoAscender) and gives the two-part delta-set index of its deltas: the
  outer index selects an ItemVariationData subtable, the inner index a row in it.
- MVAR requires 'fvar' and the other tables variable fonts need.
- Apple's 'fmtx' table (font-wide metrics taken from point coordinates of a designated glyph)
  plays no part in OpenType Font Variations.

## Table

Metrics variations table:

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; 1. |
| uint16 | minorVersion | Minor version; 0. |
| uint16 | (reserved) | Unused; 0. |
| uint16 | valueRecordSize | Byte size of one ValueRecord; must be greater than 0. |
| uint16 | valueRecordCount | Number of ValueRecord entries; 0 is allowed. |
| Offset16 | itemVariationStoreOffset | From the start of MVAR to its ItemVariationStore. Must be 0 when valueRecordCount is 0 and non-zero when valueRecordCount is above 0. |
| ValueRecord | valueRecords[valueRecordCount] | Records pairing a target tag with its delta-set index, sorted by valueTag in binary order. |

Layout notes:

- The header is 12 bytes, so the value records start at byte 12 and record i starts at
  12 + i x valueRecordSize.
- Always step by valueRecordSize: later minor versions may append compatible fields to
  ValueRecord.
- itemVariationStoreOffset is a 16-bit offset, unlike the 32-bit offsets of HVAR.

ValueRecord:

| Type | Name | Description |
|---|---|---|
| Tag | valueTag | Tag naming the font-wide value that varies. |
| uint16 | deltaSetOuterIndex | Outer delta-set index: which ItemVariationData subtable of the store. |
| uint16 | deltaSetInnerIndex | Inner delta-set index: which delta-set row of that subtable. |

A ValueRecord is 8 bytes in this version.

## Looking up a value

To get, say, OS/2.sCapHeight for the current instance:

1. Take the tag for the target from the tables below ('cpht' here).
2. Search valueRecords for that tag. The records are sorted by tag in binary order (compare
   tags as big-endian uint32 values), so a binary search works; step by valueRecordSize.
3. Tag not found: the value is the same everywhere in the variation space; use the stored
   value.
4. Tag found: evaluate delta set (deltaSetOuterIndex, deltaSetInnerIndex) in the
   ItemVariationStore for the current instance (otvarcommonformats.md, Applying an item
   variation store) and add the result to the value stored in the target table.
5. Records whose tag the reader does not recognize, such as private tags, are ignored.

## Tag rules

- Tags are case-sensitive. Every tag defined here uses only lowercase letters and digits.
- A font should use the tags documented here. Private tags, whose meaning rests on private
  agreement, are also allowed; their first character must be an uppercase letter,
  and every character must be an uppercase letter or a digit. An application that does not know a private tag ignores it.
- MVAR cannot vary OS/2.usWeightClass, OS/2.usWidthClass or post.italicAngle: those values
  correspond directly to the input values of the 'wght', 'wdth' and 'slnt' axes (fvar.md; the
  axis definitions are in the Design-Variation Axis Tag Registry).
- 'gsp0' to 'gsp9' vary the rangeMaxPPEM field of 'gasp' range records 0 to 9. The final
  'gasp' record always has rangeMaxPPEM 0xFFFF and is never varied, so a font may have at
  most (number of 'gasp' ranges - 1) value records for 'gasp' entries.

## Value tags by logical group

| Tag | Mnemonic | Value represented |
|---|---|---|
| 'hasc' | horizontal ascender | OS/2.sTypoAscender |
| 'hdsc' | horizontal descender | OS/2.sTypoDescender |
| 'hlgp' | horizontal line gap | OS/2.sTypoLineGap |
| 'hcla' | horizontal clipping ascent | OS/2.usWinAscent |
| 'hcld' | horizontal clipping descent | OS/2.usWinDescent |
| 'vasc' | vertical ascender | vhea.ascent |
| 'vdsc' | vertical descender | vhea.descent |
| 'vlgp' | vertical line gap | vhea.lineGap |
| 'hcrs' | horizontal caret rise | hhea.caretSlopeRise |
| 'hcrn' | horizontal caret run | hhea.caretSlopeRun |
| 'hcof' | horizontal caret offset | hhea.caretOffset |
| 'vcrs' | vertical caret rise | vhea.caretSlopeRise |
| 'vcrn' | vertical caret run | vhea.caretSlopeRun |
| 'vcof' | vertical caret offset | vhea.caretOffset |
| 'xhgt' | x height | OS/2.sxHeight |
| 'cpht' | cap height | OS/2.sCapHeight |
| 'sbxs' | subscript em x size | OS/2.ySubscriptXSize |
| 'sbys' | subscript em y size | OS/2.ySubscriptYSize |
| 'sbxo' | subscript em x offset | OS/2.ySubscriptXOffset |
| 'sbyo' | subscript em y offset | OS/2.ySubscriptYOffset |
| 'spxs' | superscript em x size | OS/2.ySuperscriptXSize |
| 'spys' | superscript em y size | OS/2.ySuperscriptYSize |
| 'spxo' | superscript em x offset | OS/2.ySuperscriptXOffset |
| 'spyo' | superscript em y offset | OS/2.ySuperscriptYOffset |
| 'strs' | strikeout size | OS/2.yStrikeoutSize |
| 'stro' | strikeout offset | OS/2.yStrikeoutPosition |
| 'unds' | underline size | post.underlineThickness |
| 'undo' | underline offset | post.underlinePosition |
| 'gsp0' | gaspRange[0] | gasp.gaspRange[0].rangeMaxPPEM |
| 'gsp1' | gaspRange[1] | gasp.gaspRange[1].rangeMaxPPEM |
| 'gsp2' | gaspRange[2] | gasp.gaspRange[2].rangeMaxPPEM |
| 'gsp3' | gaspRange[3] | gasp.gaspRange[3].rangeMaxPPEM |
| 'gsp4' | gaspRange[4] | gasp.gaspRange[4].rangeMaxPPEM |
| 'gsp5' | gaspRange[5] | gasp.gaspRange[5].rangeMaxPPEM |
| 'gsp6' | gaspRange[6] | gasp.gaspRange[6].rangeMaxPPEM |
| 'gsp7' | gaspRange[7] | gasp.gaspRange[7].rangeMaxPPEM |
| 'gsp8' | gaspRange[8] | gasp.gaspRange[8].rangeMaxPPEM |
| 'gsp9' | gaspRange[9] | gasp.gaspRange[9].rangeMaxPPEM |

## Value tags in alphabetical order

This is also the binary order in which value records must be stored.

| Tag | Mnemonic | Value represented |
|---|---|---|
| 'cpht' | cap height | OS/2.sCapHeight |
| 'gsp0' | gaspRange[0] | gasp.gaspRange[0].rangeMaxPPEM |
| 'gsp1' | gaspRange[1] | gasp.gaspRange[1].rangeMaxPPEM |
| 'gsp2' | gaspRange[2] | gasp.gaspRange[2].rangeMaxPPEM |
| 'gsp3' | gaspRange[3] | gasp.gaspRange[3].rangeMaxPPEM |
| 'gsp4' | gaspRange[4] | gasp.gaspRange[4].rangeMaxPPEM |
| 'gsp5' | gaspRange[5] | gasp.gaspRange[5].rangeMaxPPEM |
| 'gsp6' | gaspRange[6] | gasp.gaspRange[6].rangeMaxPPEM |
| 'gsp7' | gaspRange[7] | gasp.gaspRange[7].rangeMaxPPEM |
| 'gsp8' | gaspRange[8] | gasp.gaspRange[8].rangeMaxPPEM |
| 'gsp9' | gaspRange[9] | gasp.gaspRange[9].rangeMaxPPEM |
| 'hasc' | horizontal ascender | OS/2.sTypoAscender |
| 'hcla' | horizontal clipping ascent | OS/2.usWinAscent |
| 'hcld' | horizontal clipping descent | OS/2.usWinDescent |
| 'hcof' | horizontal caret offset | hhea.caretOffset |
| 'hcrn' | horizontal caret run | hhea.caretSlopeRun |
| 'hcrs' | horizontal caret rise | hhea.caretSlopeRise |
| 'hdsc' | horizontal descender | OS/2.sTypoDescender |
| 'hlgp' | horizontal line gap | OS/2.sTypoLineGap |
| 'sbxo' | subscript em x offset | OS/2.ySubscriptXOffset |
| 'sbxs' | subscript em x size | OS/2.ySubscriptXSize |
| 'sbyo' | subscript em y offset | OS/2.ySubscriptYOffset |
| 'sbys' | subscript em y size | OS/2.ySubscriptYSize |
| 'spxo' | superscript em x offset | OS/2.ySuperscriptXOffset |
| 'spxs' | superscript em x size | OS/2.ySuperscriptXSize |
| 'spyo' | superscript em y offset | OS/2.ySuperscriptYOffset |
| 'spys' | superscript em y size | OS/2.ySuperscriptYSize |
| 'stro' | strikeout offset | OS/2.yStrikeoutPosition |
| 'strs' | strikeout size | OS/2.yStrikeoutSize |
| 'undo' | underline offset | post.underlinePosition |
| 'unds' | underline size | post.underlineThickness |
| 'vasc' | vertical ascender | vhea.ascent |
| 'vcof' | vertical caret offset | vhea.caretOffset |
| 'vcrn' | vertical caret run | vhea.caretSlopeRun |
| 'vcrs' | vertical caret rise | vhea.caretSlopeRise |
| 'vdsc' | vertical descender | vhea.descent |
| 'vlgp' | vertical line gap | vhea.lineGap |
| 'xhgt' | x height | OS/2.sxHeight |
