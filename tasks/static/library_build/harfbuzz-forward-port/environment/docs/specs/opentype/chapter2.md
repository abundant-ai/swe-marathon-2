# OpenType Layout Common Table Formats
Source: OpenType layout common table formats (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/chapter2
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope and conventions

- The structures here are shared by the OpenType Layout tables GSUB, GPOS, BASE, JSTF and GDEF, and are also used by MATH. Each of those tables has its own digest (gsub.md, gpos.md, base.md, jstf.md, gdef.md).
- All values are big-endian. Primitive types (uint16, Tag, Offset16, Offset32, F2DOT14, ...) are defined in otff.md (Data types). An offset of 0 is NULL and means "no subtable here".
- GSUB and GPOS each hold four of these structures: a ScriptList, a FeatureList, a LookupList and, optionally, a FeatureVariations table. GSUB data describes substitutions, GPOS data describes positioning.
- BASE and JSTF are also keyed by script and language system, but use their own record formats and have no FeatureList or LookupList (base.md, jstf.md).
- Chain of references in GSUB and GPOS: ScriptList -> Script table -> LangSys table (one default plus zero or more language-specific ones) -> indices into the FeatureList -> Feature table -> indices into the LookupList -> Lookup table -> lookup subtables.
- GSUB defines eight lookup types and GPOS defines nine (gsub.md, gpos.md). Each subtable carries one kind of operation. Every lookup subtable except an Extension subtable references a Coverage table naming the glyphs it can act on.
- Glyph classes for lookups come from Class Definition (ClassDef) tables.
- Device tables (non-variable fonts only) correct scaled values at particular ppem sizes. They appear in GPOS subtables and, for baseline coordinates and caret positions, in BASE and GDEF; JSTF and MATH use them too. In variable fonts the same offset fields lead to VariationIndex tables instead (GPOS subtables, BaseCoord tables, CaretValue tables).
- Variable fonts: font-unit values in GPOS, BASE, JSTF and GDEF are those of the default instance. Deltas for GPOS, JSTF and GDEF values are kept in the ItemVariationStore owned by GDEF; deltas for BASE values are kept in an ItemVariationStore inside BASE (otvarcommonformats.md). VariationIndex tables point at those deltas.
- A FeatureVariations table (in GSUB or GPOS) swaps whole Feature tables when runtime conditions hold, for example to use simplified glyphs in heavy or narrow instances. At present its only condition type is a range on a variation axis.

## Scripts and language systems

### ScriptList table

| Type | Name | Description |
|---|---|---|
| uint16 | scriptCount | How many entries scriptRecords has. |
| ScriptRecord | scriptRecords[scriptCount] | One entry per script, in alphabetical order of scriptTag. |

### ScriptRecord

| Type | Name | Description |
|---|---|---|
| Tag | scriptTag | Script tag (see scripttags.md). |
| Offset16 | scriptOffset | Where the Script table starts, counted from the start of the ScriptList. |

Rules:

- A record is needed only for scripts that have script-specific features; a script without them may be absent.
- Records are sorted by tag, so readers may binary-search them.
- The tag 'DFLT' names a Script table for features that are not tied to any particular script.

### Script table

| Type | Name | Description |
|---|---|---|
| Offset16 | defaultLangSysOffset | Default LangSys table, counted from the start of this Script table; NULL is allowed. |
| uint16 | langSysCount | How many entries langSysRecords has; 0 when there are no language-specific systems. |
| LangSysRecord | langSysRecords[langSysCount] | Language-specific systems, sorted alphabetically by langSysTag. |

### LangSysRecord

| Type | Name | Description |
|---|---|---|
| Tag | langSysTag | Language system tag. |
| Offset16 | langSysOffset | LangSys table, counted from the start of the Script table that holds this record. |

Rules:

- A 'DFLT' Script table must have a non-NULL defaultLangSysOffset.
- A 'DFLT' Script table normally carries only its default LangSys, because language-specific behaviour is expected to sit under a real script. Fonts may nevertheless give it language-specific LangSys records (see selection below).

### LangSys table

| Type | Name | Description |
|---|---|---|
| Offset16 | lookupOrderOffset | Reserved for future use; written as NULL. |
| uint16 | requiredFeatureIndex | FeatureList index of the single required feature, or 0xFFFF for none. |
| uint16 | featureIndexCount | How many entries featureIndices has. |
| uint16 | featureIndices[featureIndexCount] | Zero-based indices into the FeatureList's featureRecords, in any order. |

Rules:

- requiredFeatureIndex = 0xFFFF means the language system has no required feature. At most one feature can be marked required; that is no real limit, since one Feature table may reference many lookups.
- Every feature reached through featureIndices is optional from this table's point of view. A client may still treat some features as mandatory for some scripts or characters; such policies are outside the table format.
- lookupOrderOffset has no defined meaning; writers store NULL and readers ignore it.
- Nothing is inherited from the default LangSys. A language-specific LangSys must itself list every feature that applies to that language, including the script-wide ones, and a language-specific Feature table must list every lookup it needs. (The source's examples repeat the default 'init', 'medi' and 'fina' features inside an Urdu LangSys, and repeat shared ligature lookups inside a language-specific 'liga' Feature table.)

### Choosing the Script table and LangSys

1. Determine the script of the text run (the client's own segmentation) and look for a ScriptRecord with that tag.
2. If no record matches, or the run belongs to no particular script (say, it is made up of symbols or punctuation alone), use the font's 'DFLT' Script table when it has one.
3. Characters whose Unicode Script property is Common may be shaped together with the script-specific characters next to them. The client then uses the neighbouring script's Script table for them, and fonts may put features for those characters under that script. 'DFLT' still applies to text made only of such neutral characters.
4. In the chosen Script table, if the client wants a specific language system and a LangSysRecord with that tag exists, use that LangSys; otherwise use the default LangSys. The criteria for picking a language system are the client's own.
5. A run uses the features of exactly one LangSys: the language-specific one or the default one, never both combined.
6. When the 'DFLT' Script table is in use (step 2) and the requested language has a LangSysRecord inside it, clients should honour that LangSys.

## Features

### FeatureList table

| Type | Name | Description |
|---|---|---|
| uint16 | featureCount | How many entries featureRecords has. |
| FeatureRecord | featureRecords[featureCount] | Tag/table pairs; LangSys indices select entries of this array. |

### FeatureRecord

| Type | Name | Description |
|---|---|---|
| Tag | featureTag | Feature tag (see featuretags.md). |
| Offset16 | featureOffset | Where the Feature table starts, counted from the start of the FeatureList. |

Rules:

- One FeatureList per GSUB or GPOS table covers every script and language system in the font; features are not tied to a single script.
- The same tag may appear in several records, because a feature is usually built differently for different scripts or language systems. Features are therefore found through a LangSys's indices, not by searching the list for a tag.
- Records should be in alphabetical tag order; records that share a tag may be in any order relative to each other.

### Feature table

| Type | Name | Description |
|---|---|---|
| Offset16 | featureParamsOffset | Feature parameters table, counted from the start of this Feature table; NULL when the feature defines no such table or the font does not supply one. |
| uint16 | lookupIndexCount | How many entries lookupListIndices has. |
| uint16 | lookupListIndices[lookupIndexCount] | Zero-based LookupList indices, in any order. |

Rules:

- A Feature table in GSUB refers only to GSUB lookups, and one in GPOS only to GPOS lookups. A feature that needs both substitution and positioning gets a Feature table under the same tag in each of the two tables.
- Feature parameters tables exist only for 'cv01' to 'cv99', 'size', and 'ss01' to 'ss20'. Each layout is given with that feature's registry entry (features_ae.md for 'cv01' to 'cv99', features_pt.md for 'size' and 'ss01' to 'ss20'). Whether one is required depends on the feature. The parameters table must state or imply its own length.
- For any other feature, and whenever a defined parameters table is not supplied, featureParamsOffset must be NULL.

### Enabling features and collecting lookups

1. From the selected LangSys take the required feature (when requiredFeatureIndex != 0xFFFF) and every entry of featureIndices. Each index selects a FeatureRecord whose tag tells the client what the feature does.
2. The client decides which of those features to apply; the required feature is always applied. Fonts may also define custom feature tags.
3. If the table has a FeatureVariations table and the client supports it, replace Feature tables as described under "Feature variations" below.
4. Merge the lookupListIndices of every applied Feature table, drop duplicates and sort ascending. Lookups run in that LookupList order, so lookups belonging to different features may interleave; the font designer is responsible for a sensible order.
5. A client may apply GSUB features in successive stages and may reorder glyphs before or between stages (script-specific shaping, outside this format). Within one stage, the lookups of that stage's features still run in LookupList order.
6. When features cover different parts of the glyph string, a lookup acts only on the glyphs covered by a feature that references it.

Typographic knowledge that would be identical in every font of a script or language belongs in the client's shaping logic, not in the font's features and lookups.

## Lookups

### LookupList table

| Type | Name | Description |
|---|---|---|
| uint16 | lookupCount | How many entries lookupOffsets has. |
| Offset16 | lookupOffsets[lookupCount] | Lookup tables, each counted from the start of the LookupList; the position in this array is the lookup index and fixes processing order. |

### Lookup table

| Type | Name | Description |
|---|---|---|
| uint16 | lookupType | Kind of operation; GSUB and GPOS number their types separately. |
| uint16 | lookupFlag | Bit flags that control which glyphs are skipped (see below). |
| uint16 | subTableCount | How many entries subtableOffsets has. |
| Offset16 | subtableOffsets[subTableCount] | Subtables, each counted from the start of this Lookup table; tried in array order. |
| uint16 | markFilteringSet | Zero-based index of a mark glyph set in GDEF. The field exists only when lookupFlag has USE_MARK_FILTERING_SET (0x0010); otherwise the table ends after subtableOffsets. |

Rules:

- A lookup performs one kind of operation, so all its subtables have the lookup's lookupType. Different subtable formats of that type may be mixed in one lookup, for example a list-based subtable for some glyphs and a range-based one for others.
- The order of subtableOffsets is the order in which subtables are tried.

### LookupFlag bit enumeration

| Mask | Name | Description |
|---|---|---|
| 0x0001 | RIGHT_TO_LEFT | Only for cursive attachment (GPOS type 3): the last glyph of the matched sequence is the one that stays on the baseline. |
| 0x0002 | IGNORE_BASE_GLYPHS | Skip glyphs whose GDEF class is base. |
| 0x0004 | IGNORE_LIGATURES | Skip glyphs whose GDEF class is ligature. |
| 0x0008 | IGNORE_MARKS | Skip every mark glyph. |
| 0x0010 | USE_MARK_FILTERING_SET | The markFilteringSet field is present; marks outside that GDEF mark glyph set are skipped. |
| 0x00E0 | reserved | Unassigned; write as 0. |
| 0xFF00 | MARK_ATTACHMENT_CLASS_FILTER | High byte; when non-zero, marks whose GDEF mark attachment class differs from this value are skipped. |

Bit layout: bits 0-3 are the four processing options above, bit 4 announces the markFilteringSet field, bits 5-7 are reserved, and bits 8-15 hold a mark attachment class number (0 means no class filter).

Rules:

- RIGHT_TO_LEFT is meaningful only for GPOS lookup type 3 and is ignored for all other lookups. It is not a text-direction indicator, and it is never used on the main lookup of a contextual lookup.
- "Base", "ligature" and "mark" are the glyph classes from GDEF's GlyphClassDef (gdef.md). Setting any of IGNORE_BASE_GLYPHS, IGNORE_LIGATURES or IGNORE_MARKS requires the font to have that GDEF class definition. A skipped glyph is treated exactly as if it were absent from the glyph string.
- A non-zero MARK_ATTACHMENT_CLASS_FILTER requires GDEF's MarkAttachClassDef; only marks of the named class take part and all other marks are skipped.
- USE_MARK_FILTERING_SET requires the markFilteringSet field and a GDEF MarkGlyphSets table; only marks belonging to that set take part.
- Precedence: IGNORE_MARKS wins over a mark filtering set and over a mark attachment class; a mark filtering set wins over a mark attachment class.
- The flags do not apply to the current glyph (the glyph at the position being processed); it is always compared with the first element of the input pattern. They decide which following glyphs are passed over while the rest of the input sequence is matched and, for chained lookups, while backtrack and lookahead glyphs are matched.

Skip decision for a glyph other than the current one (GDEF glyph class values: 1 base, 2 ligature, 3 mark; see gdef.md):

```
skipped(g, flags, setIndex):
    k = gdef_glyph_class(g)
    if k == 1: return (flags & 0x0002) != 0
    if k == 2: return (flags & 0x0004) != 0
    if k != 3: return false
    if (flags & 0x0008) != 0: return true                      # IGNORE_MARKS first
    if (flags & 0x0010) != 0: return not in_mark_glyph_set(setIndex, g)
    cls = flags >> 8                                            # attachment class filter last
    return cls != 0 and gdef_mark_attach_class(g) != cls
```

### Running a lookup over the glyph string

Each selected lookup is run over the whole string before the next lookup starts, so every lookup sees the glyphs and positions produced by the lookups before it.

1. Start at the first glyph of the string; only glyphs covered by a feature that references this lookup are candidate start positions.
2. At the current position, try the subtables in subtableOffsets order. A subtable whose first-glyph Coverage does not contain the current glyph cannot match and can be passed over at once.
3. Apply the first subtable whose pattern matches; no later subtable is tried at this position. The lookup's work at this position ends as soon as one action has been performed. If no subtable matches, nothing happens here.
4. Advance. With no match, move one glyph forward. After a match, move past every glyph that took part in the matched input sequence, whether or not it was changed. Exceptions: a pair positioning lookup (GPOS type 2) may continue at the second glyph of the pair (gpos.md); contextual and chained lookups continue right after the last input glyph, so a lookahead sequence is not consumed.
5. Repeat until the end of the string.

```
run_lookup(L, buf, active):              # active[i]: a feature using L covers glyph i
    i = 0
    while i < len(buf):
        resume = none
        if active[i]:
            for st in L.subtables:                       # array order
                if not first_glyph_covered(st, buf[i]): continue
                resume = try_apply(st, buf, i)           # resume point, or none if no match
                if resume != none: break                 # first matching subtable only
        i = resume if resume != none else i + 1
```

Chained lookups (GSUB type 6, GPOS type 8) also require backtrack and lookahead sequences to match around the input. Input glyphs must lie where the feature applies; backtrack and lookahead glyphs need not. Actions may target only input glyphs.

### Main lookups and nested lookups

- Contextual lookup types keep their actions in separate "nested" lookups of the same LookupList, so a main lookup and each nested lookup each have their own lookupFlag. The source puts GSUB types 5, 6 and 8 and GPOS types 7 and 8 in this group: the main lookup decides which glyph sequences qualify rather than changing glyphs itself.
- The main lookup's flags govern the initial pattern match; for example IGNORE_MARKS lets the pattern match across intervening marks.
- While a nested lookup runs, only the nested lookup's flags count; the main lookup's flags are not consulted. The nested flags can therefore filter the matched sequence a second time.

## Coverage table

- A Coverage table lists the glyphs that a lookup subtable can act on (all subtables except Extension subtables have one; GDEF uses Coverage tables too). If the current glyph is not covered, the subtable does not apply and the client goes on to the next subtable.
- Each covered glyph has a Coverage Index from 0 to (number of covered glyphs - 1), assigned in glyph ID order. Subtables use it to index their per-glyph data.
- format 1 lists individual glyph IDs; format 2 lists ranges of consecutive glyph IDs.

### CoverageFormat1 table: Individual glyph indices

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 1. |
| uint16 | glyphCount | How many entries glyphArray has. |
| uint16 | glyphArray[glyphCount] | Covered glyph IDs in ascending numeric order, so they can be binary-searched. |

The Coverage Index of a glyph is its position in glyphArray: 0 for the first entry, glyphCount - 1 for the last.

### CoverageFormat2 table: Range of glyphs

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 2. |
| uint16 | rangeCount | How many entries rangeRecords has. |
| RangeRecord | rangeRecords[rangeCount] | Ranges sorted by startGlyphID. |

### RangeRecord

| Type | Name | Description |
|---|---|---|
| uint16 | startGlyphID | Lowest glyph ID of the range. |
| uint16 | endGlyphID | Highest glyph ID of the range, inclusive. |
| uint16 | startCoverageIndex | Coverage Index given to startGlyphID. |

Rules:

- Ranges are ordered by startGlyphID, are distinct and must not overlap.
- The first range starts at Coverage Index 0. Each later range continues without a gap: its startCoverageIndex = previous startCoverageIndex + (previous endGlyphID - previous startGlyphID + 1).
- For a glyph inside a range: Coverage Index = startCoverageIndex + glyphID - startGlyphID.

```
coverage_index(cov, g):                  # -1 means "not covered"
    if cov.format == 1:
        k = binary search for g in cov.glyphArray
        return k if found else -1
    if cov.format == 2:
        r = binary search for the record with r.startGlyphID <= g <= r.endGlyphID
        return r.startCoverageIndex + (g - r.startGlyphID) if found else -1
```

## Class definition table

- A ClassDef table puts glyphs into numbered classes. Assigned classes start at 1; every glyph the table does not assign belongs to class 0. Within one ClassDef each glyph is in exactly one class.
- GSUB and GPOS subtables use classes, for example to describe contexts or sets of marks to process or skip.
- format 1 gives one class value per glyph over a single run of consecutive glyph IDs; format 2 gives one class value per range of consecutive glyph IDs.

### ClassDefFormat1 table: Class array

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 1. |
| uint16 | startGlyphID | Glyph ID that receives classValues[0]. |
| uint16 | glyphCount | How many entries classValues has. |
| uint16 | classValues[glyphCount] | Class of glyph startGlyphID + i, stored at index i. |

Glyphs below startGlyphID, or at or above startGlyphID + glyphCount, are in class 0.

### ClassDefFormat2 table: Class ranges

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 2. |
| uint16 | classRangeCount | How many entries classRangeRecords has. |
| ClassRange | classRangeRecords[classRangeCount] | Ranges sorted by startGlyphID. |

### ClassRange record

| Type | Name | Description |
|---|---|---|
| uint16 | startGlyphID | Lowest glyph ID of the range. |
| uint16 | endGlyphID | Highest glyph ID of the range, inclusive. |
| uint16 | class | Class value shared by every glyph of the range. |

Ranges must not overlap and are sorted by startGlyphID. A glyph that lies in no range is in class 0.

```
class_of(cd, g):
    if cd.format == 1:
        i = g - cd.startGlyphID
        return cd.classValues[i] if 0 <= i < cd.glyphCount else 0
    if cd.format == 2:
        r = binary search for the record with r.startGlyphID <= g <= r.endGlyphID
        return r.class if found else 0
```

Class 0 consequences: class 0 is a real class. In class-based contexts a pattern element with value 0 matches any glyph that the relevant ClassDef leaves unassigned (or assigns 0 explicitly), and rule-set arrays indexed by class have an entry for class 0.

## Contextual and chained contextual subtables

### Common rules

- Contextual lookups: GSUB type 5 (contextual substitution) and GPOS type 7 (contextual positioning). Chained contextual lookups: GSUB type 6 and GPOS type 8. Each comes in three formats: format 1 matches specific glyph IDs, format 2 matches glyph classes from ClassDef tables, format 3 matches sets given by Coverage tables.
- The binary layouts below are the same in GSUB and GPOS. The difference lies only in the nested lookups: a contextual lookup in GSUB calls GSUB lookups, one in GPOS calls GPOS lookups.
- Sequences are in logical order: for right-to-left text the first glyph is the rightmost one.
- The input sequence is where actions happen; it must match completely, and actions are given per input position through SequenceLookup records. Chained lookups add a backtrack sequence before the input and a lookahead sequence after it. All three must match, but actions can target input glyphs only.
- The whole pattern is matched against the glyph string as it is before any action runs. Substitutions made by nested lookups change the string afterwards; they do not alter the match already made.
- After the actions, processing resumes at the glyph right after the matched input sequence (never after the lookahead), with special handling when a nested lookup is a GPOS type 2 pair adjustment.

### SequenceLookup record

Also known as SequenceLookupRecord.

| Type | Name | Description |
|---|---|---|
| uint16 | sequenceIndex | Zero-based position inside the matched input sequence. |
| uint16 | lookupListIndex | Zero-based LookupList index of the nested lookup to apply at that position. |

### Applying the SequenceLookup records

1. Match first. The backtrack, input and lookahead parts are matched before anything is changed. Glyphs skipped under the main lookup's flags do not count as input positions: input position k is the k-th glyph actually matched, and position 0 is the current glyph.
2. Process the records in array order. They need not be sorted by sequenceIndex; their order is chosen by the font for the intended result.
3. For each record, apply the lookup at lookupListIndex once, at the glyph at input position sequenceIndex, using that nested lookup's own flags. Its subtables are tried in order as for any lookup; if none matches there, the record has no effect.
4. Each record works on the result left by the records before it, so sequenceIndex refers to the input sequence as already changed by earlier records (for example after a nested substitution replaced or merged glyphs). The source states no further index arithmetic.
5. Resume after the matched input sequence (see Common rules).

```
apply_context(buf, i, rule, L):                       # L = main lookup
    inp = match_forward(buf, i, rule.input, L)         # list of buffer positions, inp[0] == i
    if inp == fail: return none
    if rule is chained:
        if not match_backward(buf, i, rule.backtrack, L): return none
        if not match_forward_after(buf, last(inp), rule.lookahead, L): return none
    for rec in rule.seqLookupRecords:                  # stored order
        p = position of input element rec.sequenceIndex, as the buffer now stands
        apply lookup rec.lookupListIndex once at p     # nested lookup's own flags
    return position just after the last input glyph

match_forward(buf, i, pattern, L):
    pos = [i]                                          # element 0 checked by coverage, flags not used
    j = i
    for k in 1 .. len(pattern) - 1:
        j = next index after j whose glyph is not skipped(..., L.lookupFlag, L.markFilteringSet)
        if no such j, or pattern element k rejects buf[j]: return fail
        pos.append(j)
    return pos
```

Backtrack matching walks from the glyph before position i towards the start of the string, applying the same skip rule; backtrack element 0 is compared with the nearest non-skipped glyph before i, element 1 with the next one further back, and so on. Lookahead matching walks forward from the glyph after the last input glyph.

### Sequence context format 1: simple glyph contexts

GSUB type 5 format 1 and GPOS type 7 format 1. Each input sequence is spelled out with glyph IDs. The Coverage table lists the first glyph of every sequence (each glyph once); the other glyphs of a sequence are in a SequenceRule. All rules whose sequence starts with the same glyph are grouped in one SequenceRuleSet.

#### SequenceContextFormat1 table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 1. |
| Offset16 | coverageOffset | Coverage of first glyphs, counted from the start of this subtable. |
| uint16 | seqRuleSetCount | How many entries seqRuleSetOffsets has. |
| Offset16 | seqRuleSetOffsets[seqRuleSetCount] | SequenceRuleSet tables in Coverage Index order, counted from the start of this subtable; entries may be NULL. |

#### SequenceRuleSet table

| Type | Name | Description |
|---|---|---|
| uint16 | seqRuleCount | How many entries seqRuleOffsets has. |
| Offset16 | seqRuleOffsets[seqRuleCount] | SequenceRule tables, counted from the start of this SequenceRuleSet; tried in this order. |

#### SequenceRule table

| Type | Name | Description |
|---|---|---|
| uint16 | glyphCount | Length of the input sequence, first glyph included. |
| uint16 | seqLookupCount | How many SequenceLookup records follow. |
| uint16 | inputSequence[glyphCount - 1] | Glyph IDs for input positions 1 onwards. |
| SequenceLookup | seqLookupRecords[seqLookupCount] | Actions for this rule. |

Rules:

- Processing: find the current glyph in the Coverage table; take the SequenceRuleSet at its Coverage Index; try its SequenceRules in order; the first rule whose sequence matches is applied and the rest are ignored.
- seqRuleSetCount should equal the number of covered glyphs. If they differ, covered glyphs without a rule set, and rule sets without a covered glyph, are ignored.
- inputSequence[0] is compared with input position 1, inputSequence[1] with position 2, and so on.
- First match wins, not longest match. A rule whose sequence is a prefix of a later rule's sequence hides the later rule completely, which is why fonts list longer rules first.

### Sequence context format 2: class-based glyph contexts

GSUB type 5 format 2 and GPOS type 7 format 2. Patterns are sequences of class values taken from one ClassDef; for example the pattern 1, 4, 3 matches any three glyphs whose classes are 1, 4 and 3 in that order. Patterns are grouped by the class of their first position.

#### SequenceContextFormat2 table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 2. |
| Offset16 | coverageOffset | Coverage of every glyph that can start a pattern, counted from the start of this subtable. |
| Offset16 | classDefOffset | ClassDef used for all positions, counted from the start of this subtable. |
| uint16 | classSeqRuleSetCount | How many entries classSeqRuleSetOffsets has. |
| Offset16 | classSeqRuleSetOffsets[classSeqRuleSetCount] | ClassSequenceRuleSet tables indexed by class value, counted from the start of this subtable; entries may be NULL. |

#### ClassSequenceRuleSet table

| Type | Name | Description |
|---|---|---|
| uint16 | classSeqRuleCount | How many entries classSeqRuleOffsets has. |
| Offset16 | classSeqRuleOffsets[classSeqRuleCount] | ClassSequenceRule tables, counted from the start of this ClassSequenceRuleSet; tried in this order. |

#### ClassSequenceRule table

| Type | Name | Description |
|---|---|---|
| uint16 | glyphCount | Length of the pattern, first position included. |
| uint16 | seqLookupCount | How many SequenceLookup records follow. |
| uint16 | inputSequence[glyphCount - 1] | Class values for input positions 1 onwards. |
| SequenceLookup | seqLookupRecords[seqLookupCount] | Actions for this rule. |

Rules:

- The Coverage table holds, once each, all glyphs of every class that begins some pattern (for example all glyphs of classes 1 and 2 if patterns begin only with those classes).
- Processing: if the current glyph is covered, get its class from the ClassDef and use the class value directly as the index into classSeqRuleSetOffsets; try the rules of that set in order; the first match wins.
- The array has one entry per class of the ClassDef, in class value order, starting with class 0. An entry is NULL when no pattern begins with that class. (The source gives no rule for a class value beyond the end of the array; such a glyph has no rule set to try.)
- ClassSequenceRuleSet and ClassSequenceRule are laid out like SequenceRuleSet and SequenceRule; the difference is that the sequence holds class values, not glyph IDs.

### Sequence context format 3: coverage-based glyph contexts

GSUB type 5 format 3 and GPOS type 7 format 3. The subtable holds exactly one pattern, given as one Coverage table per input position.

#### SequenceContextFormat3 table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 3. |
| uint16 | glyphCount | Length of the input sequence. |
| uint16 | seqLookupCount | How many SequenceLookup records follow. |
| Offset16 | coverageOffsets[glyphCount] | One Coverage per input position, in position order, counted from the start of this subtable. |
| SequenceLookup | seqLookupRecords[seqLookupCount] | Actions for the pattern. |

The current glyph must be in coverageOffsets[0]; glyph k of the input must be in coverageOffsets[k].

### Chained sequence context format 1: simple glyph contexts

GSUB type 6 format 1 and GPOS type 8 format 1. Like sequence context format 1, but each rule also lists a backtrack and a lookahead sequence of glyph IDs. The Coverage table lists the first input glyph of every rule (each glyph once); rules sharing a first input glyph are grouped in one ChainedSequenceRuleSet.

Ordering of the three sequences (shown for a string whose input match begins at index i and is three glyphs long):

| Logical order: | p | q | r | s | t | u | v | w |
|---|---|---|---|---|---|---|---|---|
| Sequence index: | i - 3 | i - 2 | i - 1 | i | i + 1 | i + 2 | i + 3 | i + 4 |
| Input sequence index: |  |  |  | 0 | 1 | 2 |  |  |
| Backtrack sequence index: | 2 | 1 | 0 |  |  |  |  |  |
| Lookahead sequence index: |  |  |  |  |  |  | 0 | 1 |

Here the backtrack array is stored as r, q, p (nearest glyph first, moving away from the input), inputSequence holds t, u (s comes from the Coverage table), and the lookahead array is v, w in logical order. Only s, t and u can be targets of SequenceLookup records.

#### ChainedSequenceContextFormat1 table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 1. |
| Offset16 | coverageOffset | Coverage of first input glyphs, counted from the start of this subtable. |
| uint16 | chainedSeqRuleSetCount | How many entries chainedSeqRuleSetOffsets has. |
| Offset16 | chainedSeqRuleSetOffsets[chainedSeqRuleSetCount] | ChainedSequenceRuleSet tables in Coverage Index order, counted from the start of this subtable; entries may be NULL. |

#### ChainedSequenceRuleSet table

| Type | Name | Description |
|---|---|---|
| uint16 | chainedSeqRuleCount | How many entries chainedSeqRuleOffsets has. |
| Offset16 | chainedSeqRuleOffsets[chainedSeqRuleCount] | ChainedSequenceRule tables, counted from the start of this ChainedSequenceRuleSet; tried in this order. |

#### ChainedSequenceRule table

| Type | Name | Description |
|---|---|---|
| uint16 | backtrackGlyphCount | Length of the backtrack sequence. |
| uint16 | backtrackSequence[backtrackGlyphCount] | Backtrack glyph IDs, nearest to the input first. |
| uint16 | inputGlyphCount | Length of the input sequence, first glyph included. |
| uint16 | inputSequence[inputGlyphCount - 1] | Glyph IDs for input positions 1 onwards. |
| uint16 | lookaheadGlyphCount | Length of the lookahead sequence. |
| uint16 | lookaheadSequence[lookaheadGlyphCount] | Lookahead glyph IDs in logical order, starting right after the input. |
| uint16 | seqLookupCount | How many SequenceLookup records follow. |
| SequenceLookup | seqLookupRecords[seqLookupCount] | Actions for this rule (input positions only). |

Rules:

- Processing: find the current glyph in the Coverage table, take the ChainedSequenceRuleSet at its Coverage Index, try its rules in order, and apply the first one whose backtrack, input and lookahead sequences all match.
- The lookup flags apply while matching all three sequences.
- chainedSeqRuleSetCount should equal the number of covered glyphs; when they differ, the surplus on either side is ignored.

### Chained sequence context format 2: class-based glyph contexts

GSUB type 6 format 2 and GPOS type 8 format 2. Backtrack, input and lookahead sequences are given as class values, each part using its own ClassDef. Rules whose input begins with the same class are grouped in one ChainedClassSequenceRuleSet.

#### ChainedSequenceContextFormat2 table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 2. |
| Offset16 | coverageOffset | Coverage of every glyph that can start an input pattern, counted from the start of this subtable. |
| Offset16 | backtrackClassDefOffset | ClassDef for backtrack positions, counted from the start of this subtable. |
| Offset16 | inputClassDefOffset | ClassDef for input positions, counted from the start of this subtable. |
| Offset16 | lookaheadClassDefOffset | ClassDef for lookahead positions, counted from the start of this subtable. |
| uint16 | chainedClassSeqRuleSetCount | How many entries chainedClassSeqRuleSetOffsets has. |
| Offset16 | chainedClassSeqRuleSetOffsets[chainedClassSeqRuleSetCount] | ChainedClassSequenceRuleSet tables indexed by input class value, counted from the start of this subtable; entries may be NULL. |

#### ChainedClassSequenceRuleSet table

| Type | Name | Description |
|---|---|---|
| uint16 | chainedClassSeqRuleCount | How many entries chainedClassSeqRuleOffsets has. |
| Offset16 | chainedClassSeqRuleOffsets[chainedClassSeqRuleCount] | ChainedClassSequenceRule tables, counted from the start of this ChainedClassSequenceRuleSet; tried in this order. |

#### ChainedClassSequenceRule table

| Type | Name | Description |
|---|---|---|
| uint16 | backtrackGlyphCount | Length of the backtrack pattern. |
| uint16 | backtrackSequence[backtrackGlyphCount] | Backtrack class values (backtrack ClassDef), nearest to the input first. |
| uint16 | inputGlyphCount | Length of the input pattern, first position included. |
| uint16 | inputSequence[inputGlyphCount - 1] | Input class values (input ClassDef) for positions 1 onwards. |
| uint16 | lookaheadGlyphCount | Length of the lookahead pattern. |
| uint16 | lookaheadSequence[lookaheadGlyphCount] | Lookahead class values (lookahead ClassDef) in logical order. |
| uint16 | seqLookupCount | How many SequenceLookup records follow. |
| SequenceLookup | seqLookupRecords[seqLookupCount] | Actions for this rule (input positions only). |

Rules:

- Processing: if the current glyph is covered, look up its class in the input ClassDef and use that value as the index into chainedClassSeqRuleSetOffsets; try that set's rules in order; the first rule whose three patterns all match is applied.
- The rule-set array has one entry per class of the input ClassDef, in class value order starting with class 0; an entry is NULL when no input pattern begins with that class.
- Each backtrack glyph is classified with the backtrack ClassDef, each input glyph with the input ClassDef and each lookahead glyph with the lookahead ClassDef. Ordering of the three sequences is as in chained format 1, and the lookup flags apply to all three.

### Chained sequence context format 3: coverage-based glyph contexts

GSUB type 6 format 3 and GPOS type 8 format 3. One pattern only, given as Coverage tables for every backtrack, input and lookahead position.

#### ChainedSequenceContextFormat3 table

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 3. |
| uint16 | backtrackGlyphCount | Length of the backtrack sequence. |
| Offset16 | backtrackCoverageOffsets[backtrackGlyphCount] | One Coverage per backtrack position, nearest to the input first. |
| uint16 | inputGlyphCount | Length of the input sequence. |
| Offset16 | inputCoverageOffsets[inputGlyphCount] | One Coverage per input position, first position included. |
| uint16 | lookaheadGlyphCount | Length of the lookahead sequence. |
| Offset16 | lookaheadCoverageOffsets[lookaheadGlyphCount] | One Coverage per lookahead position, in logical order. |
| uint16 | seqLookupCount | How many SequenceLookup records follow. |
| SequenceLookup | seqLookupRecords[seqLookupCount] | Actions for the pattern (input positions only). |

Every offset in this subtable is counted from the start of the ChainedSequenceContextFormat3 table. The current glyph must be in inputCoverageOffsets[0].

## Device and VariationIndex tables

- Both kinds adjust a font-unit value (for example the x or y coordinate of an attachment anchor) in GPOS, JSTF, GDEF or BASE. A table that holds such a value also holds an offset to its adjustment table.
- Device tables appear only in fonts without variations, VariationIndex tables only in variable fonts. They are reached through the same offset fields, so one value never has both.
- A Device table gives pixel corrections for the scaled, rounded value at each ppem size from startSize to endSize.
- A VariationIndex table gives a delta-set index into an ItemVariationStore: the one in GDEF for GPOS, JSTF and GDEF values, the one in BASE for BASE values (otvarcommonformats.md). A delta-set index has two parts: the outer index picks an ItemVariationData subtable, the inner index picks a delta-set row within it.

### DeltaFormat values

| Mask | Name | Description |
|---|---|---|
| 0x0001 | LOCAL_2_BIT_DELTAS | Device table; signed 2-bit deltas, eight per uint16 (range -2 to 1). |
| 0x0002 | LOCAL_4_BIT_DELTAS | Device table; signed 4-bit deltas, four per uint16 (range -8 to 7). |
| 0x0003 | LOCAL_8_BIT_DELTAS | Device table; signed 8-bit deltas, two per uint16 (range -128 to 127). |
| 0x8000 | VARIATION_INDEX | VariationIndex table; the first two fields form an outer/inner delta-set index. |
| 0x7FFC | Reserved | Unassigned bits; write as 0. |

Values 1 to 3 are an enumeration for Device tables; 0x8000 marks a VariationIndex table.

### Device table

| Type | Name | Description |
|---|---|---|
| uint16 | startSize | Smallest ppem size that gets a correction. |
| uint16 | endSize | Largest ppem size that gets a correction. |
| uint16 | deltaFormat | Packing of deltaValue: 0x0001, 0x0002 or 0x0003. |
| uint16 | deltaValue[ ] | Packed corrections; length follows from the size range and the format. |

Packing rules:

- One delta per ppem size from startSize to endSize inclusive, so count = endSize - startSize + 1. The first delta belongs to startSize, the next to startSize + 1, and so on.
- Each delta is a signed two's-complement field of 2, 4 or 8 bits (deltaFormat 1, 2, 3). Fields fill each uint16 starting at the most significant bits.
- The array holds ceil(count * bits / 16) uint16 values; unused low-order bits of the last value are 0.
- A delta is the number of pixels added to (if negative, removed from) the scaled value at that ppem.
- Sample encodings: the 4-bit deltas 1, 2, 3, -1 pack into the single value 0x123F; a 2-bit table for 11 to 15 ppem with a delta of +1 at every size has deltaValue = { 0x5540 }.

```
device_delta(dev, ppem):                 # returns a pixel adjustment
    if dev.deltaFormat not in (1, 2, 3): not a Device table (0x8000 = VariationIndex)
    if ppem < dev.startSize or ppem > dev.endSize: return 0
    bits  = 1 << dev.deltaFormat         # 2, 4 or 8
    per   = 16 / bits                    # fields per uint16
    n     = ppem - dev.startSize
    word  = dev.deltaValue[n / per]      # integer division
    shift = 16 - bits * (n % per + 1)
    v     = (word >> shift) & ((1 << bits) - 1)
    if v >= (1 << (bits - 1)): v = v - (1 << bits)
    return v
```

### VariationIndex table

| Type | Name | Description |
|---|---|---|
| uint16 | deltaSetOuterIndex | Outer half of the delta-set index: which ItemVariationData subtable. |
| uint16 | deltaSetInnerIndex | Inner half: which delta-set row inside that subtable. |
| uint16 | deltaFormat | Always 0x8000. |

Reading rule: an offset that may lead to either table is read the same way at first. Read three uint16 values and look at the third (deltaFormat). For 0x0001 to 0x0003 it is a Device table: the first two values are startSize and endSize, and packed deltas follow. For 0x8000 it is a VariationIndex table: the first two values are the outer and inner indices and nothing follows. A VariationIndex table is in effect a Device table with an empty delta array, which is why it is shorter.

## Feature variations

### FeatureVariations table

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Equals 1. |
| uint16 | minorVersion | Equals 0. |
| uint32 | featureVariationRecordCount | How many entries featureVariationRecords has. |
| FeatureVariationRecord | featureVariationRecords[featureVariationRecordCount] | Condition/substitution pairs in order of precedence. |

### FeatureVariationRecord

| Type | Name | Description |
|---|---|---|
| Offset32 | conditionSetOffset | ConditionSet, counted from the start of the FeatureVariations table; 0 means no ConditionSet, which matches every context. |
| Offset32 | featureTableSubstitutionOffset | FeatureTableSubstitution, counted from the start of the FeatureVariations table; 0 means no table and no substitution. |

Rules:

- The Feature tables reached from the LangSys are the defaults. They are used when no record matches, and always by implementations that do not support FeatureVariations.
- Replacement Feature tables are placed at the end of the FeatureVariations table, not in the FeatureList. They have no FeatureRecord, keep the tag of the default feature they replace, and are reached through 32-bit offsets, unlike the 16-bit offsets of the FeatureList.
- Records are stored in order of precedence and are examined in that order.
- General version handling (an unrecognized major version means the structure is not read) is described in otff.md (Table version numbers).

### ConditionSet table

| Type | Name | Description |
|---|---|---|
| uint16 | conditionCount | How many entries conditionOffsets has. |
| Offset32 | conditionOffsets[conditionCount] | Condition tables, each counted from the start of this ConditionSet. |

Rules:

- All conditions of a set must hold (logical AND).
- A factor with no condition in the set does not restrict the match; for example an axis without a condition may have any value.
- A set with conditionCount = 0 matches every context; it is still overridden by an earlier record that matches.
- The only factor currently defined is the variation instance of a variable font.

### Condition table

The source defines a single condition format, format 1 (an axis range). Other formats may be added later. A condition table whose format the engine does not recognize makes its condition set fail to match; matching then goes on with the following records, so fonts using new formats still work in older engines.

#### ConditionFormat1 table

Font variation axis range.

| Type | Name | Description |
|---|---|---|
| uint16 | format | Equals 1. |
| uint16 | axisIndex | Zero-based position of the axis in the 'fvar' axis array. |
| F2DOT14 | filterRangeMinValue | Lowest normalized axis value that satisfies the condition. |
| F2DOT14 | filterRangeMaxValue | Highest normalized axis value that satisfies the condition. |

Rules:

- Using format 1 requires an 'fvar' table, and axisIndex must be less than its axisCount (fvar.md). If axisIndex is invalid, the FeatureVariationRecord containing the condition is ignored.
- Bounds are normalized coordinates in the range -1 to 1, i.e. after the user value has been mapped through the normalization defined for variable fonts (fvar.md, avar.md).
- The condition holds when filterRangeMinValue <= current normalized value <= filterRangeMaxValue; both ends are inclusive.

### FeatureTableSubstitution table

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Equals 1. |
| uint16 | minorVersion | Equals 0. |
| uint16 | substitutionCount | How many entries substitutions has. |
| FeatureTableSubstitutionRecord | substitutions[substitutionCount] | Replacement records sorted by featureIndex. |

### FeatureTableSubstitutionRecord

| Type | Name | Description |
|---|---|---|
| uint16 | featureIndex | FeatureList index whose Feature table is replaced. |
| Offset32 | alternateFeatureOffset | Replacement Feature table, counted from the start of this FeatureTableSubstitution table. |

Rules:

- Records are in strictly increasing featureIndex order; one featureIndex never appears twice.
- When looking for a feature index, the first record with that index is the match; the search stops early at a record with a higher index.

### Evaluating feature variations

1. Obtain the default feature indices (required plus optional) from the selected LangSys.
2. Take the normalized coordinate of every axis for the current instance.
3. Walk featureVariationRecords in array order:
   1. A record with conditionSetOffset = 0 matches. Otherwise check each condition of its ConditionSet: format 1 holds when the axis value lies within [filterRangeMinValue, filterRangeMaxValue]; a condition with an unknown format fails, which fails the set. Any failing condition means no match.
   2. A record containing a format 1 condition with an invalid axisIndex is ignored.
   3. On a match, look at the record's FeatureTableSubstitution. If its version is supported, select this record and stop searching. If the version is not supported, reject the record and continue with the next one. A record with featureTableSubstitutionOffset = 0 substitutes nothing (the source does not say separately whether such a record ends the search).
4. If no record was selected, keep the defaults.
5. If a record was selected, then for each feature index in use, scan its substitution records in order: an equal featureIndex gives the replacement Feature table (same tag as before), and stop; a higher featureIndex, or the end of the array, leaves the default Feature table in place.
6. Continue with "Enabling features and collecting lookups" step 4 using the resulting Feature tables.

```
pick_record(fv, coords):
    for rec in fv.featureVariationRecords:               # precedence order
        if rec.conditionSetOffset != 0:
            ok = true
            for c in conditions(rec):
                if c.format != 1: ok = false; break
                if c.axisIndex >= fvar_axis_count(): ok = false; break      # record ignored
                v = coords[c.axisIndex]
                if v < c.filterRangeMinValue or v > c.filterRangeMaxValue: ok = false; break
            if not ok: continue
        if rec.featureTableSubstitutionOffset != 0 and not version_supported(fts(rec)): continue
        return rec                      # a NULL substitution offset is taken as selected here; it changes nothing
    return none

feature_table_for(index, rec):
    if rec != none and rec.featureTableSubstitutionOffset != 0:
        for s in fts(rec).substitutions:                 # ascending featureIndex
            if s.featureIndex == index: return table_at(fts(rec), s.alternateFeatureOffset)
            if s.featureIndex > index: break
    return default_feature_table(index)
```
