# JSTF - Justification Table
Source: JSTF - Justification Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/jstf
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope

JSTF gives a client that justifies text font-specific ways to make a line longer or shorter
besides changing word and letter spacing. Per script and language system it holds ranked
suggestions. A suggestion can switch GSUB and GPOS lookups on or off, and can supply
JSTF-local positioning lookups that state the largest adjustment allowed. Per script it can
also list extender glyphs (such as Arabic kashidas) that the client may insert. Suggestions
apply to both horizontal and vertical text.

Data types (uint16, Offset16, Tag) are defined in otff.md.

## Organization

```
JSTF header
  jstfScriptRecords[]: tag + offset          (sorted by jstfScriptTag)
    JstfScript
      ExtenderGlyph                           (optional)
      default JstfLangSys                     (optional; no record of its own)
      jstfLangSysRecords[]: tag + offset      (sorted by jstfLangSysTag)
        JstfLangSys
          jstfPriorityOffsets[]               (priority 0 first)
            JstfPriority
              shrink: GSUB enable, GSUB disable, GPOS enable, GPOS disable  -> JstfModList
                      shrinkage limit                                        -> JstfMax
              extend: GSUB enable, GSUB disable, GPOS enable, GPOS disable  -> JstfModList
                      extension limit                                        -> JstfMax
```

- A JstfModList holds indices into the LookupList of GSUB or of GPOS.
- A JstfMax holds offsets to GPOS-format lookups that are stored inside JSTF itself.

Naming notes:

- The source's overview mentions a "JstfDataRecord" next to the JstfPriority table but defines
  no structure of that name; the JstfPriority layout below is complete without it.
- One JstfModList layout serves both GSUB and GPOS lists. Earlier editions of the
  specification called the two uses JstfGSUBModList and JstfGPOSModList; their layout is the
  same (a uint16 count followed by that many uint16 lookup indices).

## Processing rules

Selecting the data:

1. Justification starts only after every selected GSUB and GPOS feature has been applied to
   the string.
2. Find the JstfScriptRecord whose jstfScriptTag is the script's tag. JSTF script tags must
   correspond to the script tags used in GSUB and GPOS.
3. In that JstfScript, use the JstfLangSys named by the JstfLangSysRecord of the text's
   language system. Without language-specific data, use the default JstfLangSys, which holds
   the data for the whole script.

Applying suggestions:

4. Suggestions are ranked by priority. Priority 0 is the least objectionable choice; higher
   numbers are progressively more visible. The font defines how many levels there are and what
   each one means.
5. Begin with priority 0. Enable and disable the lookups that this level's JstfModList tables
   name, put the resulting set of lookups back into LookupList order, and apply it to each glyph
   of the string in turn. Use the shrinkage entries when the line must get shorter and the
   extension entries when it must get longer.
6. If the line length still does not meet the requirement, go to the next priority (ascending)
   and repeat. Stop as soon as the length is acceptable.
7. Each level stands alone: its suggestions are not added on top of those of earlier levels.
8. If a suggestion, at any level, changes a GSUB or GPOS lookup that was already applied to the
   glyph string, the client must apply that suggestion to an unmodified copy of the glyph
   string rather than to the already processed one.
9. When GSUB or GPOS has a FeatureVariations table, the lookups that actually ran for a feature
   may differ from the feature's default lookups. Rule 8 is checked against the lookups that
   actually ran, with feature variations in effect. Fonts are advised to include such
   alternate lookups in their lists of lookups to disable. Lookups stored inside JSTF (in
   JstfMax tables) have no feature-variation mechanism.
10. JstfMax lookups state maximum adjustments. The client may move a glyph by any amount from 0
    up to that maximum.
11. The client may also insert the script's extender glyphs, in addition to using the
    suggestions.

Variable fonts:

- Justification runs the same way for every instance; only the metrics differ, so the text
  that ends up on a line may differ between instances.
- The X and Y values in GPOS-format lookups, whether those lookups live in GPOS or in JSTF,
  apply to the default instance. Their adjustments for other instances come through
  VariationIndex tables that refer to the ItemVariationStore inside the GDEF table, the same
  store used for GDEF and GPOS values. JSTF has no variation store of its own. See gdef.md
  (Item variation store table), chapter2.md (Device and VariationIndex tables) and gpos.md.

## JSTF header

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; set to 1 |
| uint16 | minorVersion | Minor version; set to 0 |
| uint16 | jstfScriptCount | Number of entries in jstfScriptRecords |
| JstfScriptRecord | jstfScriptRecords[jstfScriptCount] | Script records, sorted alphabetically by jstfScriptTag |

### JstfScriptRecord

| Type | Name | Description |
|---|---|---|
| Tag | jstfScriptTag | Script tag (4 bytes) identifying the JstfScript |
| Offset16 | jstfScriptOffset | Where the JstfScript table starts, counted from the start of the JSTF header |

## JstfScript table

Justification data for one script.

| Type | Name | Description |
|---|---|---|
| Offset16 | extenderGlyphOffset | ExtenderGlyph table, counted from the start of this JstfScript table; may be NULL |
| Offset16 | defJstfLangSysOffset | Default JstfLangSys table, counted from the start of this JstfScript table; may be NULL |
| uint16 | jstfLangSysCount | Number of entries in jstfLangSysRecords; may be 0 |
| JstfLangSysRecord | jstfLangSysRecords[jstfLangSysCount] | Language system records, sorted alphabetically by jstfLangSysTag |

- If every language system uses the same justification data, the font defines only the
  default JstfLangSys and sets jstfLangSysCount to 0.
- If any language system has its own suggestions, jstfLangSysCount is positive and there is one
  record for each such language system.
- The default data has no JstfLangSysRecord; it is reached only through defJstfLangSysOffset.

### JstfLangSysRecord

| Type | Name | Description |
|---|---|---|
| Tag | jstfLangSysTag | Language system tag (4 bytes) |
| Offset16 | jstfLangSysOffset | Where the JstfLangSys table starts, counted from the start of the JstfScript table (not from the record) |

## ExtenderGlyph table

| Type | Name | Description |
|---|---|---|
| uint16 | glyphCount | Number of extender glyphs for this script |
| uint16 | extenderGlyphs[glyphCount] | Glyphs the client may insert to lengthen a line, in ascending glyph ID order |

## JstfLangSys table

Holds the suggestions of one language system (or the script default), in priority order.

| Type | Name | Description |
|---|---|---|
| uint16 | jstfPriorityCount | Number of priority levels (JstfPriority tables) |
| Offset16 | jstfPriorityOffsets[jstfPriorityCount] | JstfPriority tables in priority order, entry 0 being priority 0; each counted from the start of this JstfLangSys table |

## JstfPriority table

The suggestions of one priority level. All ten offsets are counted from the start of this
JstfPriority table and may be NULL, meaning the level has no data of that kind. The first five
fields serve shrinking a line and the last five serve extending it.

| Type | Name | Description |
|---|---|---|
| Offset16 | gsubShrinkageEnableOffset | JstfModList of GSUB lookups to switch on when shrinking |
| Offset16 | gsubShrinkageDisableOffset | JstfModList of GSUB lookups to switch off when shrinking |
| Offset16 | gposShrinkageEnableOffset | JstfModList of GPOS lookups to switch on when shrinking |
| Offset16 | gposShrinkageDisableOffset | JstfModList of GPOS lookups to switch off when shrinking |
| Offset16 | shrinkageJstfMaxOffset | JstfMax table that bounds shrinkage |
| Offset16 | gsubExtensionEnableOffset | JstfModList of GSUB lookups to switch on when extending |
| Offset16 | gsubExtensionDisableOffset | JstfModList of GSUB lookups to switch off when extending |
| Offset16 | gposExtensionEnableOffset | JstfModList of GPOS lookups to switch on when extending |
| Offset16 | gposExtensionDisableOffset | JstfModList of GPOS lookups to switch off when extending |
| Offset16 | extensionJstfMaxOffset | JstfMax table that bounds extension |

## JstfModList table

Names GSUB or GPOS lookups to enable or disable at one priority level. Which LookupList the
indices refer to follows from the JstfPriority field that points here (gsub... fields: GSUB;
gpos... fields: GPOS). For example, a font may disable a GSUB ligature lookup to make a line
longer.

| Type | Name | Description |
|---|---|---|
| uint16 | lookupCount | Number of entries in lookupIndices |
| uint16 | lookupIndices[lookupCount] | Indices into the GSUB or GPOS LookupList, in ascending numeric order |

To use a level, the client enables or disables the listed lookups, reassembles the active
lookups in LookupList order, and applies them to each glyph in turn (rules 5 to 9 above).

## JstfMax table

Points to justification lookups that hold maximum adjustment values.

| Type | Name | Description |
|---|---|---|
| uint16 | lookupCount | Number of entries in lookupOffsets |
| Offset16 | lookupOffsets[lookupCount] | GPOS-format Lookup tables, in design order; each counted from the start of this JstfMax table |

- Each lookup and its subtables have the layout of a GPOS Lookup table and GPOS subtables (see
  chapter2.md (Lookup table) and gpos.md), but they are stored in JSTF and carry justification
  data only. They usually follow the JstfMax table in the font data.
- Any GPOS lookup type may be used except contextual positioning lookups.
- The values are GPOS ValueRecords and may adjust any placement or advance, horizontal or
  vertical. Each value is the largest shrinkage or extension allowed per glyph; the client may
  apply any amount from 0 up to it.
- A lookup may give one value for all glyphs of the script, or finer data such as per-glyph
  values or values for particular glyph pairs.
