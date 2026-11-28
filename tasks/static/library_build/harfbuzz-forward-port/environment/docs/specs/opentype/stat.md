# STAT - Style Attributes Table
Source: STAT - Style Attributes Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/stat
These notes restate the source's structures and rules; where they differ, the source governs.

## Purpose

- STAT lists the design attributes (axes, and values on them) by which the fonts of a family differ, and links each attribute value to a name element that user interfaces can show.
- It is required in every variable font (see fvar.md). It is recommended for new non-variable fonts, above all when styles differ on axes other than weight, width or slope.
- It describes a font in relation to its whole family. For example, a "Bold" font can state that the family also has an italic axis and that this font sits at the non-italic value on it.
- Its labels (for example "Bold" and "Condensed" inside "Condensed Bold") may be shown in menus, but they do not replace the subfamily names in 'name' or in the named instances of 'fvar'.
- Typical uses: presenting rich families in applications built on limited family models; alternative font-selection interfaces; choosing styles from their relationships (such as bold linking).

## Family models and name projection

- Three name ID pairs serve three family models:
  - name IDs 16 and 17 (Typographic Family and Subfamily): no restriction on styles;
  - name IDs 1 and 2 (Font Family and Subfamily): the R/B/I/BI model (only regular, bold, italic and bold italic in a family);
  - name IDs 21 and 22 (WWS Family and Subfamily): the WWS model (only weight, width and slope may vary inside a family).
- An application on a limited model treats every style difference its model cannot express as a separate family. Under R/B/I/BI, for instance, a Light font becomes the "Regular" member of a family named "<family> Light", and a static font stores exactly that in name IDs 1 and 2.
- A variable font cannot do this with name IDs. It has IDs 16 and 17 (17 for the default instance), and 'fvar' gives each named instance a subfamily string equivalent to ID 17, but nothing equivalent to IDs 1/2 or 21/22.
- STAT closes the gap with axis value tables. Each one labels a value on one axis (format 4 labels a combination of values on several axes). Software combines these labels with the typographic family name (ID 16) to build alternate family and subfamily names for any model, so every named instance can be offered to older applications.
- Projection rules for generated names:
  - R/B/I/BI: every subfamily element other than "Regular", "Bold", "Italic" or "Oblique" moves into the family name. Family "Selawik" with subfamily "Condensed Bold" becomes family "Selawik Condensed", subfamily "Bold".
  - WWS: every subfamily element that is not a weight, a width, or italic/oblique moves into the family name.
  - For this reason the source advises putting width, weight and italic/oblique labels at the end of subfamily names.
- The axisOrdering value of each axis record steers the order of labels when several are joined into one generated name (see "AxisRecord").

## Header

Three header versions exist:

| Version | Header size | Difference |
|---|---|---|
| 1.0 | 18 bytes | No elidedFallbackNameID field. Deprecated. |
| 1.1 | 20 bytes | Adds elidedFallbackNameID. |
| 1.2 | 20 bytes | Same header as 1.1; adds axis value table format 4. |

The source's table spells the last field elidedFallbackNameID; its prose writes elidedFallbackNameId. Both mean the same field.

### Style attributes header, version 1.2

This is the layout the source gives. Offset is the byte offset from the start of the STAT table.

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | majorVersion | Major version; 1. |
| 2 | uint16 | minorVersion | Minor version; 2. |
| 4 | uint16 | designAxisSize | Byte size of one axis record. |
| 6 | uint16 | designAxisCount | Number of axis records. When the font has 'fvar', must be >= the 'fvar' axisCount. In any font, must be > 0 if axisValueCount > 0. |
| 8 | Offset32 | designAxesOffset | Start of the design axes array, counted from the start of the STAT table. 0 when designAxisCount is 0; otherwise must be non-zero. |
| 12 | uint16 | axisValueCount | Number of axis value tables. |
| 14 | Offset32 | offsetToAxisValueOffsets | Start of the axis value offsets array, counted from the start of the STAT table. 0 when axisValueCount is 0; otherwise must be non-zero. |
| 18 | uint16 | elidedFallbackNameID | Name ID used instead when projecting names into some family model leaves a subfamily name made only of elidable elements. |

### Style attributes header, version 1.1

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | majorVersion | 1. |
| 2 | uint16 | minorVersion | 1. |
| 4 | uint16 | designAxisSize | As in version 1.2. |
| 6 | uint16 | designAxisCount | As in version 1.2. |
| 8 | Offset32 | designAxesOffset | As in version 1.2. |
| 12 | uint16 | axisValueCount | As in version 1.2. |
| 14 | Offset32 | offsetToAxisValueOffsets | As in version 1.2. |
| 18 | uint16 | elidedFallbackNameID | As in version 1.2. |

Axis value tables in a version 1.1 table use formats 1 to 3 only.

### Style attributes header, version 1.0 (deprecated)

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | majorVersion | 1. |
| 2 | uint16 | minorVersion | 0. |
| 4 | uint16 | designAxisSize | As in version 1.2. |
| 6 | uint16 | designAxisCount | As in version 1.2. |
| 8 | Offset32 | designAxesOffset | As in version 1.2. |
| 12 | uint16 | axisValueCount | As in version 1.2. |
| 14 | Offset32 | offsetToAxisValueOffsets | As in version 1.2. |

There is no elidedFallbackNameID, so no fallback name is available when all labels are elided.

### Arrays reached from the header

| Type | Name | Description |
|---|---|---|
| AxisRecord | designAxes[designAxisCount] | The design axes array, at designAxesOffset. |
| Offset16 | axisValueOffsets[axisValueCount] | Offsets of the axis value tables, counted in bytes from the start of this offsets array (not from the start of STAT). |

- The two arrays may lie next to each other in a font, but a parser must still find each one through its header offset.
- Step through axis records using designAxisSize, not a fixed record size: a later minor version may append compatible fields to the axis record.

## elidedFallbackNameID

- If every axis-value name of a style is elidable (for example a "Normal" weight and a "Roman" slant, both flagged elidable), the composed subfamily name would be empty. The string of this name ID, such as "Regular", is used instead.
- Fonts often point it at name ID 17 or name ID 2.

## AxisRecord

AxisRecord (8 bytes in the current format; always step by designAxisSize):

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | Tag | axisTag | Tag of the design axis. |
| 4 | uint16 | axisNameID | Name ID of the 'name' strings that display this axis. |
| 6 | uint16 | axisOrdering | Ordering key: primary sort order for face names, and order of labels when building family or face names. |

Rules:

- axisTag must obey the axis-tag rules given in the Design-Variation Axis Tag Registry. A tag should appear in at most one axis record.
- axisNameID may reuse a predefined name ID if its strings suit an axis name. Otherwise it must lie in the range 256 to 32767.
- In a variable font every 'fvar' axis needs an axis record, and the record must use the same name ID as 'fvar'. Record order is free and need not follow 'fvar'.
- A variable font whose family also varies along axes that this font does not vary dynamically (for example a separate italic font) should include records for those axes as well.
- A non-variable font should include records for the axes relevant to it or to its family, in particular any axis besides weight, width and slope.
- Each declared axis should be either a variation axis in 'fvar' or named in the font's subfamily string (ID 17 or ID 2). The exception is a font that sits at the axis's "normal" value when that value is omitted from its subfamily string.
- axisOrdering orders labels from several axes when they are joined into alternate family or subfamily names. Applications may also use it to sort or group the styles of a family in menus (for example by weight first, then by width).
- axisOrdering should be the same in every font of the family and should match the label order in name ID 17 strings and, for a variable font, in the 'fvar' named-instance strings.
- All fonts of a family should carry matching axis records. When a family gains a new axis later, the older fonts need not be updated: axis records describe the family, so the newer fonts' records cover the extended family. When newer and older fonts coexist, the ordering from the newer fonts' more complete axis records is the one used.

## Axis value tables

### General rules

- An axis value table describes one style-attribute value on one axis (formats 1, 2, 3) or a combination of values on several axes (format 4), and links it to a name element.
- Analytic names: a label tied to one value on one axis, freely combinable with labels of other axes ("Bold" + "Condensed" -> "Bold Condensed"). Formats 1, 2 and 3 serve these.
- Non-analytic names: a label for a combination of values on several axes that cannot be split into independent parts (for example "Florid" for a set of stroke and terminal axis values). Format 4 serves these. Such a label can still be joined with analytic labels, as in "Florid Bold".
- Readers first read the format field. A table with an unknown format may be ignored. Future formats can be added in a minor version update.
- valueNameID may be a predefined name ID such as 2, 17 or 22 when its string suits the value; otherwise it must lie in the range 256 to 32767.
- All numeric axis values use the same scale as that axis uses in 'fvar'.
- A variable font is strongly advised to have axis value tables for every element of the typographic subfamily names of all its 'fvar' named instances. Some applications build instance subfamily names from these tables, and an incomplete set can cause odd interface behaviour.
- Extra tables for name elements used by no named instance are allowed; legacy-model compatibility does not need them. Axes whose values are only ever chosen numerically need no names and no tables.
- Static distinctions of a variable font that matter within its family (for example a weight-variable font paired with an italic weight-variable font) should also get axis records and axis value tables.
- In non-variable families, the table for a given value should be identical in every font that has that value (both Bold Condensed and Bold SemiCondensed should carry the same "Bold" table); otherwise menus, fallback and other font selection can behave unexpectedly.
- Formats 1, 2 and 3 are especially advised for 'wght' and 'wdth' values and for "Italic" (value 1.0 on 'ital') or "Oblique" (any non-zero 'slnt' value). Format 4 is especially advised for non-analytic subfamily names: their axis-value combinations in static families, or in variable fonts that also use 'wght', 'wdth', Italic or Oblique.
- When a family later adds an axis that the earlier fonts never anticipated (for example width variants added after Regular, Bold and Italic shipped), the newer fonts should contain tables that place the earlier fonts on the new axis (typically at its "Normal" value). Such tables carry OLDER_SIBLING_FONT_ATTRIBUTE (see "Flags").

### No duplicate descriptions

No two tables should describe the same combination of axis values:

1. A format 1 table and a separate format 3 table should not have both the same axisIndex and the same value.
2. A format 1 table and a format 2 table with the same axisIndex should not coexist if the format 1 value is strictly between the format 2 rangeMinValue and rangeMaxValue. The format 1 value may equal the range minimum or maximum, but then the format 2 nominalValue should be a different value.
3. Tables of formats 2 and 3 may share an axisIndex with the format 2 nominalValue equal to the format 3 value, because each adds different information. Their flags and valueNameID must then be identical.
4. A format 4 table may give an axis value that another table also gives, but only if the two tables' combinations differ in some other way.
5. Format 4 is meant for multi-axis combinations, so no format 4 table should hold a single axis value equal to the value or nominal value of another table.

### Axis value table, format 1

AxisValueFormat1 (12 bytes):

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | format | Format identifier; 1. |
| 2 | uint16 | axisIndex | Zero-based index into the axis record array, naming the axis this table describes. Must be < designAxisCount. |
| 4 | uint16 | flags | Flag bits; see "Flags". |
| 6 | uint16 | valueNameID | Name ID of the display string for this attribute value. |
| 8 | Fixed | value | The axis value being labelled. |

Format 1 just ties one axis value to a name.

### Axis value table, format 2

AxisValueFormat2 (20 bytes):

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | format | Format identifier; 2. |
| 2 | uint16 | axisIndex | Zero-based index into the axis record array, naming the axis this table describes. Must be < designAxisCount. |
| 4 | uint16 | flags | Flag bits; see "Flags". |
| 6 | uint16 | valueNameID | Name ID of the display string for this attribute value. |
| 8 | Fixed | nominalValue | The single value that the name stands for. |
| 12 | Fixed | rangeMinValue | Low end of the range of axis values that also carry this name. |
| 16 | Fixed | rangeMaxValue | High end of that range. |

- Use format 2 when a name belongs to one particular value but also to a span of values (for example "Subhead" for a span of optical sizes). nominalValue can match the coordinate of a named instance in 'fvar'; the range lets the same name cover nearby values.
- Open-ended axes: rangeMinValue = 0x80000000 stands for negative infinity, and rangeMaxValue = 0x7FFFFFFF stands for positive infinity.
- Ranges are inclusive at both ends.
- Two format 2 tables on one axis may touch (the rangeMaxValue of one equals the rangeMinValue of the other) but should overlap no further.

Ranges that touch at value T, with L the lower range and H the higher one:

1. At most one of L and H should have its nominalValue equal to T.
2. For a requested value equal to T, use H, unless L.nominalValue == T and H.nominalValue > T; in that case use L.

A format 1 or format 3 value V that touches a format 2 range R:

1. V == R.rangeMaxValue: use the format 1 or 3 table.
2. V == R.rangeMinValue: use the format 1 or 3 table, unless R.nominalValue also equals R.rangeMinValue, in which case R is used.

Two format 2 tables for one axis whose ranges overlap by more than a point (advice to applications):

1. Identical ranges: keep one, chosen consistently by the application's own criterion, and ignore the other.
2. One range lies entirely inside the other: ignore the table with the smaller range.
3. Otherwise, for axis values inside the overlap, use the table whose range is higher (both its rangeMinValue and its rangeMaxValue are higher).

### Axis value table, format 3

AxisValueFormat3 (16 bytes):

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | format | Format identifier; 3. |
| 2 | uint16 | axisIndex | Zero-based index into the axis record array, naming the axis this table describes. Must be < designAxisCount. |
| 4 | uint16 | flags | Flag bits; see "Flags". |
| 6 | uint16 | valueNameID | Name ID of the display string for this attribute value. |
| 8 | Fixed | value | The axis value being labelled. |
| 12 | Fixed | linkedValue | The value on the same axis that is the style-linked counterpart of value. |

- linkedValue names the value to switch to for style linking, chiefly "bold" linking on the weight axis: it maps a non-bold weight to its bold partner, so an application can pick the right style when the user turns on Bold.
- Not every weight needs a mapping. Lighter weights should have one; heavier weights (usually semibold and up) already count as bold and need none.
- Applications are free not to use these mappings. An application that does not apply style linking on the axis ignores linkedValue.

### Axis value table, format 4

AxisValueFormat4 (8 + 6 * axisCount bytes):

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | format | Format identifier; 4. |
| 2 | uint16 | axisCount | Number of axes that take part in this combination. |
| 4 | uint16 | flags | Flag bits; see "Flags". |
| 6 | uint16 | valueNameID | Name ID of the display string for this combination of values. |
| 8 | AxisValue | axisValues[axisCount] | One AxisValue record per contributing axis, together giving the combination. |

AxisValue record (6 bytes; the record type the source calls AxisValue):

| Offset | Type | Name | Description |
|---|---|---|---|
| 0 | uint16 | axisIndex | Zero-based index into the axis record array for the axis this value is on. Must be < designAxisCount. |
| 2 | Fixed | value | The value on that axis. |

- axisCount should be greater than 1.
- Every AxisValue record in one table must have a different axisIndex. The records may appear in any order.
- Matching: when looking for the table that fits a combination of axis values, and two format 4 tables each match part of it, use the one that matches more values (the most specific). If both match the same number of values (on different sets of axes), use the first matching table.
- If a format 1, 2 or 3 table's value (or nominal value) also appears in a format 4 table that adds values for other axes, the format 4 table is the more specific match and is used.
- Ordering: wherever axisOrdering matters for a format 4 table (for example when its label is joined with others), take the lowest axisOrdering among the axes it references.

## Flags

Axis value table flags:

| Mask | Name | Description |
|---|---|---|
| 0x0001 | OLDER_SIBLING_FONT_ATTRIBUTE | The table describes other fonts of the same family that shipped earlier without data for some axis. Ignored when newer versions of those fonts, which carry the data themselves, are present. |
| 0x0002 | ELIDABLE_AXIS_VALUE_NAME | The value is the "normal" value of its axis, and its name may be dropped when composing names. |
| 0xFFFC | Reserved | Kept for future use; must be 0. |

OLDER_SIBLING_FONT_ATTRIBUTE:

- Implementations may use such a table to decide behaviour for a different font of the same family.
- When a released family is extended with fonts on a new design axis, every new font should include an OLDER_SIBLING_FONT_ATTRIBUTE table giving the new axis's "normal" value, which is the value that holds for the earlier fonts (for example 'wdth' 100, "Normal"). These tables should agree across fonts; if they do not, application behaviour may be unpredictable.
- The table gives default information about other fonts of the family, never about the font that contains it. The font describes itself with separate tables that do not have this flag.
- Because it usually describes the "normal" value of a new axis, ELIDABLE_AXIS_VALUE_NAME may be set on it too. For the earlier fonts, which had no label for the new axis, elidable behaviour is implied anyway.

ELIDABLE_AXIS_VALUE_NAME:

- Marks a "normal" value whose label normally stays out of face names (for example "Normal" width or "Regular" weight). Applications may omit the label, but may also show it in some situations.
- Fonts should still include axis value tables for normal values, even though their labels are usually hidden.
- If every axis value of the selected font or variable-font instance is elidable, an application may keep the weight axis label, when there is one, as the constructed subfamily name and omit all other labels. The elidedFallbackNameID string is the other fallback for this case.

Several tables with the same axisIndex should occur only when one of these holds:

- the font is variable and that axis is a variation axis in 'fvar';
- one of the tables has OLDER_SIBLING_FONT_ATTRIBUTE set.

## Applying the rules (summary)

The source gives the rules above but no single algorithm. Taken together, composing a style name for a font or a named instance goes like this:

1. Find the axis value tables that describe the style's coordinates. Format 1 and format 3 tables match on value; a format 2 table matches when the coordinate lies in its inclusive range, with the tie rules above at touching ends; a format 4 table matches on its combination, and a more specific (more values matched) format 4 table beats a less specific one and beats single-axis tables.
2. Tables flagged OLDER_SIBLING_FONT_ATTRIBUTE describe sibling fonts, not the containing font, and are ignored once newer versions of those siblings carrying their own data are present.
3. Order the labels by the axisOrdering of their axes; a format 4 table takes the lowest ordering among its axes.
4. Labels from tables flagged ELIDABLE_AXIS_VALUE_NAME may be dropped.
5. If nothing is left, use the string of elidedFallbackNameID (version 1.1 and later), or keep the weight label.
6. For a legacy family model, move every label that the model cannot express from the subfamily name into the family name, starting from the typographic family name (name ID 16).

## Examples in the source

The source ends with six example data sets (a weight-only static family, weight plus italic, a family later extended with width variants, a weight/width variable font, a non-italic plus italic variable font pair, and a variable font with format 4 names "Florid" and "Jagged"). They only illustrate the rules above and are not repeated here.
