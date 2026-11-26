# fvar - Font Variations Table
Source: fvar - Font Variations Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/fvar
These notes restate the source's structures and rules; where they differ, the source governs.

## Role

- 'fvar' is the global description of a variable font: which design axes exist, the
  user-scale range of each, and a list of named instances (designer-chosen positions with
  names that act like subfamily names, offered to users as ready-made choices).
- Every variable font must contain 'fvar', together with the other tables variable fonts
  need.
- STAT (stat.md) must mirror it: each 'fvar' axis needs a matching STAT axis record, and each
  named instance needs matching STAT axis value tables.
- Axis values here are user-scale values. Other variation tables work in normalized
  coordinates; otvarcommonformats.md (Coordinate normalization) and avar.md cover the
  conversion.

## Table layout

A header, then the array of VariationAxisRecord entries at axesArrayOffset, then directly
after it the array of InstanceRecord entries.

### 'fvar' header

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; 1. |
| uint16 | minorVersion | Minor version; 0. |
| Offset16 | axesArrayOffset | From the start of 'fvar' to the first VariationAxisRecord. |
| uint16 | (reserved) | Permanently reserved; holds 2. |
| uint16 | axisCount | Number of axes, equal to the number of VariationAxisRecord entries. |
| uint16 | axisSize | Byte size of one VariationAxisRecord; 20 (0x0014) in this version. |
| uint16 | instanceCount | Number of InstanceRecord entries (named instances listed). |
| uint16 | instanceSize | Byte size of one InstanceRecord: axisCount * sizeof(Fixed) + 4 without postScriptNameID, axisCount * sizeof(Fixed) + 6 with it. |

The two arrays:

| Type | Name | Description |
|---|---|---|
| VariationAxisRecord | axes[axisCount] | The axis records, starting at axesArrayOffset. |
| InstanceRecord | instances[instanceCount] | The named-instance records, starting right after the last axis record. |

Rules:

- Axis record i starts at axesArrayOffset + i x axisSize. Instance record j starts at
  axesArrayOffset + axisCount x axisSize + j x instanceSize.
- Always step by axisSize and instanceSize rather than by fixed structure sizes: later minor
  versions may append compatible fields to either record.
- The page's own byte example labels the reserved field countSizePairs (two count and size
  pairs, value 2).
- A working variable font has axisCount greater than 0. With axisCount 0 the font must be
  handled as a non-variable font, and every variation-specific table or datum is ignored.

## VariationAxisRecord

| Type | Name | Description |
|---|---|---|
| Tag | axisTag | Tag of the design axis, for example 'wght'. |
| Fixed | minValue | Lowest user-scale value this font supports on the axis. |
| Fixed | defaultValue | User-scale value of the default instance on the axis. |
| Fixed | maxValue | Highest user-scale value this font supports on the axis. |
| uint16 | flags | Axis qualifier bits (below). |
| uint16 | axisNameID | 'name' table ID of the axis display name. |

The record is 20 bytes (4 + 3 x 4 + 2 + 2).

Axis flags:

| Mask | Name | Description |
|---|---|---|
| 0x0001 | HIDDEN_AXIS | Hint that the axis should not be offered directly in user interfaces. |
| 0xFFFE | Reserved | Reserved; must be 0. |

Rules:

- Coordinates are in the user scale defined for the axis tag. A registered tag defines a valid
  range that applies to every font; a font's minValue and maxValue may cover only part of it.
- Tags must satisfy the general Tag rules (otff.md, Data Types) and the further rules of the
  OpenType Design-Variation Axis Tag Registry. The registry keeps the patterns for registered
  tags and for foundry-defined tags disjoint, so a private tag can never clash with a tag
  registered later.
- Default instance: every axis at its defaultValue. It uses the 'glyf' outlines as stored,
  with no 'gvar' deltas applied.
- No flag set: assume nothing beyond the registered definition of the axis.
- HIDDEN_AXIS set: the axis should stay out of ordinary user interfaces (specialized tools,
  such as font inspectors, may still show it). The flag does not affect named instances, which
  should always be offered in text-formatting interfaces. Flag clear: an application may show
  the axis in its default interface or, depending on the axis, in an advanced one.
- axisNameID must be greater than 255 and less than 32768. For registered tags, the
  conventional US English axis name (or a localized form of it) is the recommended interface
  label.

## UserTuple record

| Type | Name | Description |
|---|---|---|
| Fixed | coordinates[axisCount] | One user-scale value per axis, in the order of the axis records. |

A UserTuple (Fixed, user scale) is not the same structure as the Tuple record of the
variation tables (F2DOT14, normalized; otvarcommonformats.md).

## InstanceRecord

| Type | Name | Description |
|---|---|---|
| uint16 | subfamilyNameID | 'name' table ID of this instance's subfamily name. |
| uint16 | flags | Reserved; must be 0. |
| UserTuple | coordinates | User-scale position of this instance. |
| uint16 | postScriptNameID | Optional: 'name' table ID of this instance's PostScript name. |

Detecting postScriptNameID:

1. All instance records in a font have one size: either all of them carry postScriptNameID
   or none does.
2. sizeof(Fixed) is 4, so instanceSize = axisCount x 4 + 6 means the field is present and
   instanceSize = axisCount x 4 + 4 means it is absent.
3. Whatever the size, find each record by stepping instanceSize bytes.

Name ID rules:

- subfamilyNameID strings are treated like name ID 17 (typographic subfamily) for that
  instance. Allowed values: 2 or 17, or a value above 255 and below 32768. Use 2 or 17 only
  when the instance is the default instance.
- postScriptNameID strings are treated like name ID 6 (PostScript name). Allowed values: 6,
  0xFFFF, or a value above 255 and below 32768. 0xFFFF means "no PostScript name for this
  instance" and the field is ignored. Use 6 only when the instance is the default instance.
- Instance records should differ in coordinates, in subfamilyNameID and in postScriptNameID.
  When two or more records share coordinates, or share a subfamily name ID, or share a
  PostScript name ID, all but the first may be ignored.
- The default instance needs no record. When listing named instances, include the default
  instance even if no record describes it; a font with instanceCount 0 therefore still has one
  named instance.
- If a record does describe the default instance (all coordinates at the defaults), its
  subfamilyNameID should be 2 or 17, or an ID whose string equals that of 2 or 17; when
  records carry postScriptNameID, its value should be 6 or an ID whose string equals that of 6.

## Selecting an instance (validation and clamping)

1. Obtain a value for every axis, either from a named instance's coordinates or from values
   supplied by the caller.
2. An axis left without a value takes its defaultValue.
3. A value below minValue is replaced by minValue; a value above maxValue is replaced by
   maxValue.
4. Normalize the clamped values before using any variation data (otvarcommonformats.md,
   Coordinate normalization; avar.md).

## Registered axes

Registered axis tags and their ranges are defined in the OpenType Design-Variation Axis Tag Registry, which is not
among these notes.

## Example from the page (layout check)

A hypothetical family "SelawikV" with two axes:

| Axis tag | Minimum | Default | Maximum | Axis name ID |
|---|---|---|---|---|
| 'wght' | 300 | 400 | 700 | 256 |
| 'wdth' | 62.5 | 100 | 150 | 257 |

and four named instances:

| Subfamily name | Subfamily name ID | PostScript name | PostScript name ID | 'wght' | 'wdth' |
|---|---|---|---|---|---|
| Regular | 258 | SelawikV-Regular | 262 | 400 | 100 |
| Bold | 259 | SelawikV-Bold | 263 | 700 | 100 |
| Condensed | 260 | SelawikV-Condensed | 264 | 400 | 75 |
| Condensed Bold | 261 | SelawikV-CondensedBold | 265 | 700 | 75 |

Encoded: axesArrayOffset 0x0010 (16 bytes of header), reserved 2, axisSize 0x0014,
instanceSize 0x000E (2 x 4 + 6, so postScriptNameID is present), 62.5 as Fixed is 0x003E8000,
and the whole table is 16 + 2 x 20 + 4 x 14 = 112 bytes.
