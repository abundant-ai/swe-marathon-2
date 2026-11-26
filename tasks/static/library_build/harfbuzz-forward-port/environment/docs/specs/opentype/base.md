# BASE - Baseline Table
Source: BASE - Baseline table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/base
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope

For each layout direction and each script, BASE supplies:

- baseline positions, so that glyphs of different scripts and sizes, from one font or from
  several fonts, can be aligned on one line;
- minimum and maximum extents (min/max) for the script, which a language system or a feature can
  override, to help set line spacing without clipping marks, math symbols, superscripts or
  subscripts.

These extents are separate from the font-wide extents in 'head', 'hhea', 'vhea' and 'OS/2'
(see head.md, hhea.md, vhea.md, os2.md). Data types (uint16, int16, Offset16, Offset32, Tag)
are defined in otff.md.

## Model

- One script at one size is the dominant run of a line; every other baseline is placed
  relative to it.
- Baseline types are named by baseline tags (see Registered baseline tags at the end). Each
  script gives its own coordinate for each baseline; the coordinates used for the line are
  those of the dominant run's script.
- Each script names one default baseline in its BaseValues table. Its glyphs are aligned on
  that baseline, and when scaled they grow or shrink about it.
- Example: with Latin as the dominant run, Latin glyphs of every size sit on the roman
  baseline, and Kanji glyphs sit on the ideographic baseline at the position that the Latin
  data gives for it.
- BASE positions are recommendations; a client may use other positions.
- The same tags may be used on both axes. On the vertical axis, for example, 'romn' denotes the
  baseline of rotated Latin text.

Within one font, the scripts' coordinates must be set relative to one another so that their
glyphs align, and each script lists a coordinate for every baseline of its direction. The
source's Example 3B shows two equally valid numberings for a font with Han, Latin, Cyrillic and
Devanagari at 2048 units per em: either all scripts share one coordinate system, or each
script's glyphs are drawn with that script's default baseline at 0.

| Baseline | Shared coordinates (all four scripts) | Default at 0: Han | Default at 0: Latin and Cyrillic | Default at 0: Devanagari |
|---|---|---|---|---|
| hanging | 1500 | 1788 | 1500 | 0 |
| roman | 0 | 288 | 0 | -1500 |
| ideographic | -288 | 0 | -288 | -1788 |

In both numberings the distances between baselines agree (hanging 1500 above roman,
ideographic 288 below roman); only the zero point differs.

## Organization

```
BASE header
  HorizAxis (Y values)            VertAxis (X values)        either offset may be NULL
    BaseTagList                   baseline tags of this direction, sorted
    BaseScriptList                BaseScriptRecord[], sorted by baseScriptTag
      BaseScript
        BaseValues                default baseline index + one BaseCoord per tag
        default MinMax            min/max BaseCoord + FeatMinMax[] (script-wide features)
        BaseLangSys[]             sorted; tag -> MinMax: min/max BaseCoord + FeatMinMax[]
  ItemVariationStore              version 1.1, variable fonts
```

A script appears in the BaseScriptList of each direction it is written in. For instance, a
Japanese font lists Kanji, Kana and Latin under HorizAxis, and Kanji and Kana again under
VertAxis.

## BASE header

### BASE Header, version 1.0

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; set to 1 |
| uint16 | minorVersion | Minor version; set to 0 |
| Offset16 | horizAxisOffset | Horizontal Axis table, counted from the start of the BASE table; may be NULL |
| Offset16 | vertAxisOffset | Vertical Axis table, counted from the start of the BASE table; may be NULL |

### BASE Header, version 1.1

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; set to 1 |
| uint16 | minorVersion | Minor version; set to 1 |
| Offset16 | horizAxisOffset | Horizontal Axis table, counted from the start of the BASE table; may be NULL |
| Offset16 | vertAxisOffset | Vertical Axis table, counted from the start of the BASE table; may be NULL |
| Offset32 | itemVarStoreOffset | ItemVariationStore table, counted from the start of the BASE table; may be NULL |

- HorizAxis holds the data for horizontal layout; all its baseline and extent values are Y
  values. VertAxis holds the data for vertical layout; all its values are X values.
- A font with data for one direction only sets the other axis offset to NULL.
- Version 1.1 adds the optional ItemVariationStore that variable fonts use to vary BASE values.

## Axis table

| Type | Name | Description |
|---|---|---|
| Offset16 | baseTagListOffset | BaseTagList table, counted from the start of this Axis table; may be NULL |
| Offset16 | baseScriptListOffset | BaseScriptList table, counted from the start of this Axis table |

- When a direction has no baseline data, baseTagListOffset may be NULL.

## BaseTagList table

| Type | Name | Description |
|---|---|---|
| uint16 | baseTagCount | Number of baseline tags for this direction; may be 0 |
| Tag | baselineTags[baseTagCount] | Baseline tags (4 bytes each), required to be in alphabetical order |

- Names the baselines used by the scripts of this direction. A baseline that several scripts
  use as their default is listed once; usually there is a tag for each distinct default
  baseline.
- May hold any number of tags, including tags for scripts that other fonts support.
- Each script in the BaseScriptList must pick one of these tags as its default.

## BaseScriptList table

| Type | Name | Description |
|---|---|---|
| uint16 | baseScriptCount | Number of entries in baseScriptRecords |
| BaseScriptRecord | baseScriptRecords[baseScriptCount] | Script records, sorted alphabetically by baseScriptTag |

- Lists every script of the font that is written in this direction, with one record each.
- A script that is not listed is laid out using the layout information of the font as a whole.

### BaseScriptRecord

| Type | Name | Description |
|---|---|---|
| Tag | baseScriptTag | Script tag (4 bytes); must be identical to the tag of that script in the GSUB or GPOS ScriptList |
| Offset16 | baseScriptOffset | BaseScript table, counted from the start of the BaseScriptList |

## BaseScript table

Baseline and extent data for one script.

| Type | Name | Description |
|---|---|---|
| Offset16 | baseValuesOffset | BaseValues table, counted from the start of this BaseScript table; may be NULL |
| Offset16 | defaultMinMaxOffset | The script's default MinMax table, counted from the start of this BaseScript table; may be NULL |
| uint16 | baseLangSysCount | Number of BaseLangSys records; may be 0 |
| BaseLangSys | baseLangSysRecords[baseLangSysCount] | Language system records, sorted alphabetically by baseLangSysTag |

- baseValuesOffset may be NULL when the script has no baseline data or when the BaseTagList
  offset of the Axis is NULL.
- defaultMinMaxOffset may be NULL when the script has no default extents.
- baseLangSysCount may be 0 when no language system and no language-specific feature has its
  own extents.
- Feature extents that hold for the whole script go in FeatMinMax records of the default
  MinMax table. Extents for one language system, including its feature-specific ones, need a
  BaseLangSys record and a MinMax table of their own.

### BaseLangSys record

| Type | Name | Description |
|---|---|---|
| Tag | baseLangSysTag | Language system tag (4 bytes) |
| Offset16 | minMaxOffset | MinMax table for this language system, counted from the start of the BaseScript table (not from the record) |

## BaseValues table

The baseline positions of one script and the choice of its default baseline.

| Type | Name | Description |
|---|---|---|
| uint16 | defaultBaselineIndex | Position in the BaseTagList's baselineTags array of this script's default baseline |
| uint16 | baseCoordCount | Number of entries in baseCoordOffsets; equal to baseTagCount of the BaseTagList |
| Offset16 | baseCoordOffsets[baseCoordCount] | One BaseCoord table per baseline, in the order of baselineTags; each counted from the start of this BaseValues table |

- Not needed when the BaseTagList offset is NULL. Otherwise each script must give a coordinate
  for every baseline named in the BaseTagList, the default baseline included.
- The source's prose says baseCoordCount must equal the number of tags; its table says should.
- baseCoordOffsets[k] gives the coordinate of baselineTags[k].
- Each coordinate is one design-unit value measured from 0 on the axis (Y under HorizAxis, X
  under VertAxis). Values may be negative, and each script may place each baseline
  differently.
- Several scripts may share a default baseline. With the tags 'ideo' (index 0) and 'romn'
  (index 1), Latin and Cyrillic both use defaultBaselineIndex 1 and Han uses 0.

## MinMax table and FeatMinMax record

### MinMax table

Extents of a script (default table) or of a language system.

| Type | Name | Description |
|---|---|---|
| Offset16 | minCoordOffset | BaseCoord table of the minimum extent, counted from the start of this MinMax table; may be NULL |
| Offset16 | maxCoordOffset | BaseCoord table of the maximum extent, counted from the start of this MinMax table; may be NULL |
| uint16 | featMinMaxCount | Number of FeatMinMax records; may be 0 |
| FeatMinMax | featMinMaxRecords[featMinMaxCount] | Feature records, sorted alphabetically by featureTag |

### FeatMinMax record

Extents that apply while one feature is in use.

| Type | Name | Description |
|---|---|---|
| Tag | featureTag | Feature tag (4 bytes); must match a feature tag in the GSUB or GPOS FeatureList |
| Offset16 | minCoordOffset | BaseCoord table of the feature's minimum extent, counted from the start of the enclosing MinMax table (not from the record); may be NULL |
| Offset16 | maxCoordOffset | BaseCoord table of the feature's maximum extent, counted from the start of the enclosing MinMax table (not from the record); may be NULL |

- Each extent is one X or Y value, depending on the direction, in design units; negative
  values are allowed.
- Where each kind of extent lives:
  - script default: the MinMax table at BaseScript.defaultMinMaxOffset;
  - features that apply to the whole script: FeatMinMax records of that default MinMax table;
  - a language system: the MinMax table at BaseLangSys.minMaxOffset;
  - features within that language system: FeatMinMax records of the language's MinMax table.
- Every feature whose glyphs exceed the default extents should have a FeatMinMax record.
- A language system whose own extents equal the script defaults, but which has a feature that
  needs other extents, gets a MinMax table with both coordinate offsets NULL and a FeatMinMax
  record for that feature (source Example 4B). The NULL offsets there mean that the language
  system has no extents of its own and the script default applies.

## BaseCoord tables

Shared rules:

- A BaseCoord gives one value: a baseline position, a minimum extent or a maximum extent. Under
  HorizAxis it is a Y value; under VertAxis it is an X value.
- Values are in design units and may be negative. They are typically scaled with the glyphs
  and rounded to the nearest integer.
- The leading uint16 format field selects one of three formats. All three carry the
  design-unit coordinate; formats 2 and 3 add a way to adjust it.

### BaseCoordFormat1 table: Design units only

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 1 |
| int16 | coordinate | The value, in design units (a Y position under HorizAxis, an X position under VertAxis) |

Compact and simple, but the value cannot be adjusted for size or device resolution.

### BaseCoordFormat2 table: Design units plus contour point

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 2 |
| int16 | coordinate | The value, in design units (a Y position under HorizAxis, an X position under VertAxis) |
| uint16 | referenceGlyph | Glyph ID of the glyph that carries the reference point |
| uint16 | baseCoordPoint | Contour point index on referenceGlyph |

- Hinting may move the point; its final position after hinting supplies the value used when
  rendering at that size.
- GPOS positioning operations do not change that final position.

### BaseCoordFormat3 table: Design units plus Device or VariationIndex table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 3 |
| int16 | coordinate | The value, in design units (a Y position under HorizAxis, an X position under VertAxis) |
| Offset16 | deviceOffset | Device table (non-variable font) or VariationIndex table (variable font) for this value, counted from the start of this BaseCoord table; may be NULL |

- Non-variable font: the Device table refines the value for each size and resolution (see
  chapter2.md (Device and VariationIndex tables)).
- Variable font: a value that needs to vary must use format 3, with deviceOffset pointing to a
  VariationIndex table.

## ItemVariationStore table and variable fonts

- BASE values are those of the default instance. For other instances they are adjusted with
  deltas from the ItemVariationStore held in BASE itself (itemVarStoreOffset, version 1.1),
  unlike GPOS and JSTF values, whose store lives in GDEF. The store's format is in
  otvarcommonformats.md (Item Variation Store); the interpolation is described in the
  OpenType Font Variations Overview chapter. GDEF, MVAR and other tables use the same store
  format, which is not the format used by 'gvar' and 'cvar'.
- A delta-set index has two parts: an outer index that picks an ItemVariationData subtable and
  an inner index that picks a delta-set row in it. A VariationIndex table carries both. In
  BASE, VariationIndex tables are reached only through BaseCoordFormat3, one reference per
  value that varies.
- A VariationIndex table is a Device table variant with its own format value (DeltaFormat
  0x8000; see chapter2.md (Device and VariationIndex tables)). This keeps the default instance
  usable by applications without variation support, and it means a variable font cannot use
  Device tables. Applications without variation support ignore VariationIndex tables, as does
  any reader when the font is not variable.
- Several values that need the same variation may point to one VariationIndex table, and
  several VariationIndex tables may refer to the same delta data.
- A value with no VariationIndex table (deviceOffset 0, or format 1 or 2) is the same in every
  instance.
- Recommendation: in a variable font, give varying values directly as X or Y values (format 3)
  rather than through a glyph point (format 2). A point reference would require applying the
  outline variations and running the rasterizer before the value is known, which slows layout.

## Processing rules

### Default baseline and alignment

1. Choose the Axis of the layout direction: HorizAxis for horizontal text, VertAxis for
   vertical text.
2. Find the script's BaseScriptRecord by tag. If the script is not listed, use the layout
   information of the font as a whole.
3. In the script's BaseValues table, defaultBaselineIndex selects the default baseline tag in
   the BaseTagList's baselineTags; baseCoordOffsets[k] gives the coordinate of baselineTags[k].
4. On a line, take the coordinates from the dominant run's script. Glyphs of every script sit
   on their own script's default baseline, placed where the dominant script's BaseValues puts
   that baseline.

Derived from these rules (the source states no formula): let script S have default tag T, let
D be the dominant run's script, let c_X(T) be the coordinate script X gives for T, and let s_X
be the scale of run X (ppem / unitsPerEm). Then S's glyphs are shifted along the cross axis by
c_D(T) * s_D - c_S(T) * s_S relative to the dominant run's origin, so that S's default baseline
lands on the dominant run's position for T and S scales about that baseline.

### Choosing min/max extents

1. Start from the script's extents for the text: the default MinMax table of the script.
2. Take language-specific extents for the language system in use, if its BaseLangSys record
   exists.
3. Let the application or user decide whether to use feature-specific extents (FeatMinMax) for
   the features in effect: from the language's MinMax table for language-specific features, or
   from the default MinMax table for features that apply to the whole script.
4. Wherever no extents are defined for the language system or for its features, use the
   script's default min/max values. In particular, if no language system or feature of the
   script affects the default extents, the defaults are used.

### Which value a BaseCoord yields

- Format 1: the coordinate.
- Format 2: the coordinate in design units; when the glyphs are hinted, the hinted position of
  point baseCoordPoint of referenceGlyph supplies the value at that size.
- Format 3: the coordinate plus an adjustment: Device-table deltas for the current size in a
  non-variable font, or VariationIndex deltas for the current instance in a variable font. A
  NULL deviceOffset means no adjustment.
- In a variable font only format 3 with a VariationIndex table varies a value; every other value
  stays fixed across instances.

## Registered baseline tags

The baseline tags are registered in the OpenType Layout tag registry, on its own page
(Baseline tags, https://learn.microsoft.com/en-us/typography/opentype/spec/baselinetags),
not on the BASE page; the BASE page's examples use 'hang', 'ideo' and 'romn'. The registry, in
alphabetical order:

| Tag | Baseline |
|---|---|
| 'hang' | Hanging baseline: the line from which syllables appear to hang in Tibetan and similar scripts (several Indic scripts align glyph tops on a high hanging baseline) |
| 'icfb' | Ideographic character face, bottom edge in horizontal layout (left edge in vertical layout) |
| 'icft' | Ideographic character face, top edge in horizontal layout (right edge in vertical layout) |
| 'ideo' | Ideographic em-box, bottom edge in horizontal layout (left edge in vertical layout) |
| 'idtp' | Ideographic em-box, top edge in horizontal layout (right edge in vertical layout) |
| 'math' | Baseline about which mathematical characters are centered; in vertical layout, about which math characters rotated 90 degrees clockwise are centered |
| 'romn' | Baseline of simple alphabetic scripts such as Latin, Cyrillic and Greek; in vertical layout, the baseline of such text rotated 90 degrees clockwise (not of characters that stay upright) |

The ideographic em-box is the design square of the ideographs; the ideographic character face
is the usually smaller area inside it that their shapes occupy.
