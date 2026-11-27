# GSUB - Glyph Substitution Table
Source: GSUB - Glyph Substitution Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/gsub
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope

GSUB rewrites a string of glyph IDs. The 'cmap' table (see cmap.md) gives each character one
default glyph; GSUB lookups then turn one glyph into another glyph, one glyph into several,
one glyph into a client-chosen alternate, or several glyphs into one, and any of these can be
made to depend on the surrounding glyphs. Lookup type 7 adds no new action: it only lets a
lookup reach its subtables through 32-bit offsets.

Data types (uint16, int16, Offset16, Offset32, Tag) are defined in otff.md. Every offset is
counted in bytes from the structure named in its row.

## Variable fonts

A GSUB table may contain a FeatureVariations table (header version 1.1). In a variable font it
swaps the lookup lists of selected features for alternate ones in chosen regions of the design
space (for example, simplified glyphs where counters get small). Its layout and processing are
in chapter2.md (FeatureVariations table). The related feature is 'rvrn', Required Variation
Alternates; see features_pt.md.

## Organization and lookup selection

The header points to four common structures, all described in chapter2.md:

- ScriptList: the scripts and language systems that use substitutions.
- FeatureList: the substitution features those scripts and language systems need.
- LookupList: the lookups that carry out those features.
- FeatureVariations (version 1.1 only, optional): conditions under which alternate feature
  tables replace the default ones. At present only variable fonts use it.

To decide which lookups to run:

1. Find the script of the text in the ScriptList.
2. If the language system is known, find its LangSys table under that script; otherwise use
   the script's default LangSys table.
3. The LangSys table gives FeatureList indices: one required feature and any number of other
   features.
4. Choose which of those features to apply, by their featureTag.
5. If a FeatureVariations table exists, evaluate its conditions; a match may replace some of
   the chosen feature tables with alternate feature tables.
6. Gather the LookupList indices of all chosen feature tables into one set and run those
   lookups in LookupList order.

## Rules shared by all lookup types

- Lookup and subtable layout, subtable order and the lookupFlag bits are defined in
  chapter2.md (Lookup table). All subtables of one Lookup table must have the same lookup type.
  A lookup may still hold several subtables of that type, so that each group of glyphs can use
  whichever format stores it most compactly.
- Each separate substitution step on the same glyphs needs its own lookup. Lookups run in
  LookupList order, each one on the output of the lookups before it. The order therefore
  matters: an earlier lookup can create a glyph sequence that a later lookup then matches, or
  break a sequence that the later lookup would otherwise have matched.
- A lookup is run over every glyph of the string before the next lookup starts.
- The glyph at the position being processed is the current glyph. For types 1 to 4 and 8 it
  is the glyph looked up in the subtable's Coverage table (for a ligature, the first
  component); for a nested lookup started by a contextual record it is the glyph at that
  record's sequenceIndex. Types 1 to 6 visit positions from the start of the string forward;
  type 8 visits them from the end backwards; a type 7 lookup behaves as the type it wraps. How
  lookup flags filter the glyphs matched after the current glyph is explained in chapter2.md
  (Lookup table).
- At a given position, the lookup is done once the client has found the target glyph or
  context and performed the substitution (if any).
- The client then moves past all glyphs that took part: the glyphs that were replaced and the
  other glyphs of the matched input sequence. Only input-sequence glyphs are passed over; for
  a chained context lookup the lookahead glyphs are not, so the next position is the glyph
  right after the input sequence.

## GsubLookupType enumeration

| Value | Type | Description |
|---|---|---|
| 1 | Single | One glyph becomes one other glyph |
| 2 | Multiple | One glyph becomes a sequence of glyphs |
| 3 | Alternate | One glyph becomes one of a set of alternates |
| 4 | Ligature | A sequence of glyphs becomes one glyph |
| 5 | Contextual substitution | Substitutions on glyphs that match an input pattern |
| 6 | Chained contexts substitution | As type 5, plus backtrack and lookahead patterns |
| 7 | Substitution extension | 32-bit indirection to a subtable of another type |
| 8 | Reverse chaining context single | One-for-one substitution in chained context, scanned from the end backwards |

## GSUB header

### GSUB Header, version 1.0

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; set to 1 |
| uint16 | minorVersion | Minor version; set to 0 |
| Offset16 | scriptListOffset | Where the ScriptList starts, counted from the start of the GSUB table |
| Offset16 | featureListOffset | Where the FeatureList starts, counted from the start of the GSUB table |
| Offset16 | lookupListOffset | Where the LookupList starts, counted from the start of the GSUB table |

### GSUB Header, version 1.1

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; set to 1 |
| uint16 | minorVersion | Minor version; set to 1 |
| Offset16 | scriptListOffset | Where the ScriptList starts, counted from the start of the GSUB table |
| Offset16 | featureListOffset | Where the FeatureList starts, counted from the start of the GSUB table |
| Offset16 | lookupListOffset | Where the LookupList starts, counted from the start of the GSUB table |
| Offset32 | featureVariationsOffset | Where the FeatureVariations table starts, counted from the start of the GSUB table; may be NULL |

The two versions differ only in the trailing 32-bit featureVariationsOffset, which exists in
version 1.1 alone.

## Lookup type 1: single substitution (SingleSubst)

Both formats name their input glyphs in a Coverage table (see chapter2.md (Coverage table)).
A subtable applies only when the current glyph is covered. Format 1 is smaller; format 2 is
more flexible.

### SingleSubstFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 1 |
| Offset16 | coverageOffset | Coverage table of input glyphs, counted from the start of this subtable |
| int16 | deltaGlyphID | Signed amount added to a covered glyph ID to obtain its replacement |

- The replacement glyph is computed, not stored:
  `substitute = (inputGlyphID + deltaGlyphID) modulo 65536`.
  A negative sum is made valid by adding 65536, and a sum above 65535 has 65536 taken off;
  computed in integers this is `(inputGlyphID + deltaGlyphID) & 0xFFFF` with deltaGlyphID
  sign-extended.
- The Coverage index is not used by this format.
- The covered glyphs need not form a continuous ID range, but all of them shift by the same
  delta.

### SingleSubstFormat2 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 2 |
| Offset16 | coverageOffset | Coverage table of input glyphs, counted from the start of this subtable |
| uint16 | glyphCount | Number of entries in substituteGlyphIDs |
| uint16 | substituteGlyphIDs[glyphCount] | Replacement glyph for each Coverage index |

- glyphCount must equal the number of glyphs in the Coverage table, and the array is in
  Coverage index order.
- If the current glyph has Coverage index i, it is replaced by substituteGlyphIDs[i].

## Lookup type 2: multiple substitution (MultipleSubst)

Replaces one glyph with a sequence of glyphs (for example, splitting a ligature back into its
parts). One format.

### MultipleSubstFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 1 |
| Offset16 | coverageOffset | Coverage table of input glyphs, counted from the start of this subtable |
| uint16 | sequenceCount | Number of entries in sequenceOffsets |
| Offset16 | sequenceOffsets[sequenceCount] | One Sequence table per Coverage index, in Coverage index order; each counted from the start of this subtable |

### Sequence table

| Type | Name | Description |
|---|---|---|
| uint16 | glyphCount | Number of output glyphs; never 0 |
| uint16 | substituteGlyphIDs[glyphCount] | The glyphs that take the place of the input glyph |

- If the current glyph has Coverage index i, it is replaced by all glyphs of Sequence table i,
  in array order.
- The array is in logical order: for left-to-right text the left-most output glyph is first,
  for right-to-left text the right-most one is first.
- Empty sequence: a multiple substitution may not be used to delete its input glyph, so
  glyphCount must be greater than 0. The source states this only as a requirement on fonts; it
  does not say how a reader should treat a Sequence table whose glyphCount is 0.

## Lookup type 3: alternate substitution (AlternateSubst)

Lists aesthetic alternates for a glyph. For example, 'cmap' maps the ampersand to one default
glyph and an AlternateSet lists the other ampersand designs. One format.

### AlternateSubstFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 1 |
| Offset16 | coverageOffset | Coverage table of glyphs that have alternates, counted from the start of this subtable |
| uint16 | alternateSetCount | Number of entries in alternateSetOffsets |
| Offset16 | alternateSetOffsets[alternateSetCount] | One AlternateSet table per Coverage index, in Coverage index order; each counted from the start of this subtable |

### AlternateSet table

| Type | Name | Description |
|---|---|---|
| uint16 | glyphCount | Number of entries in alternateGlyphIDs |
| uint16 | alternateGlyphIDs[glyphCount] | Alternate glyph IDs; their order carries no meaning |

- If the current glyph has Coverage index i, AlternateSet table i lists its alternates. The
  table does not pick one: the client (usually on the user's request) decides which
  alternate, if any, replaces the glyph.
- The alternates are treated as functionally equivalent, so they may appear in any order.

## Lookup type 4: ligature substitution (LigatureSubst)

Replaces a sequence of glyphs with one ligature glyph. One subtable can describe any number of
ligatures. One format.

### LigatureSubstFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 1 |
| Offset16 | coverageOffset | Coverage table that lists only the first component of each ligature, counted from the start of this subtable |
| uint16 | ligatureSetCount | Number of entries in ligatureSetOffsets |
| Offset16 | ligatureSetOffsets[ligatureSetCount] | One LigatureSet table per Coverage index, in Coverage index order; each counted from the start of this subtable |

### LigatureSet table

There is one LigatureSet per covered glyph; it holds every ligature that begins with that glyph
(for a covered "f": "ffl", "fl", "ffi", "fi" and "ff").

| Type | Name | Description |
|---|---|---|
| uint16 | ligatureCount | Number of entries in ligatureOffsets |
| Offset16 | ligatureOffsets[LigatureCount] | Ligature tables, most preferred first; each counted from the start of this LigatureSet table |

The source writes the array size as LigatureCount; it means the ligatureCount field. Note that
these offsets are relative to the LigatureSet table, not to the subtable.

### Ligature table

| Type | Name | Description |
|---|---|---|
| uint16 | ligatureGlyph | Glyph ID of the ligature that is substituted |
| uint16 | componentCount | Total component count, the first component included |
| uint16 | componentGlyphIDs[componentCount - 1] | Components two to componentCount, in writing (logical) order |

- The first component is not stored in the Ligature table: it is the covered glyph.
  componentGlyphIDs[0] is the second component (input sequence index 1).
- componentGlyphIDs follows logical order: left-most glyph first for left-to-right text,
  right-most glyph first for right-to-left text.
- Preference order: the order of ligatureOffsets expresses preference. A font that prefers
  "ffl" over "ff" lists the "ffl" Ligature table first.

Applying one LigatureSubstFormat1 subtable at the current glyph:

1. Look up the current glyph in the Coverage table. If it is not covered, the subtable does not
   apply.
2. Take the LigatureSet table at that Coverage index.
3. Visit its Ligature tables in array order. For each one, compare componentGlyphIDs[0] to
   componentGlyphIDs[componentCount - 2] with the glyphs that follow the current glyph,
   passing over any glyph that the lookup flags tell the lookup to ignore (see chapter2.md
   (Lookup table) for IGNORE_BASE_GLYPHS, IGNORE_LIGATURES, IGNORE_MARKS, the mark attachment
   class filter and mark filtering sets).
4. The first Ligature table whose components all match is used. If none matches, the subtable
   does not apply.
5. The current (first) glyph is replaced by ligatureGlyph, and the other matched component
   glyphs are deleted.
6. Glyphs that were passed over because of the lookup flags (for example marks between the
   components when IGNORE_MARKS is set) are not components and are not deleted; they stay in
   the glyph string.

## Lookup type 5: contextual substitution

A type 5 subtable describes input patterns and the substitutions to make inside a matching
glyph sequence. Its three formats are the sequence-context formats shared by GSUB and GPOS; the
GSUB page does not repeat their layouts.

| Format | Input pattern expressed as | Structure | Layout |
|---|---|---|---|
| 1 | Specific glyph IDs; several patterns allowed | SequenceContextFormat1 | chapter2.md (Sequence context format 1: simple glyph contexts) |
| 2 | Glyph classes from one ClassDef table; several patterns allowed | SequenceContextFormat2 | chapter2.md (Sequence context format 2: class-based glyph contexts) |
| 3 | One Coverage table per input position; one pattern only | SequenceContextFormat3 | chapter2.md (Sequence context format 3: coverage-based glyph contexts) |

- In format 2 every glyph belongs to exactly one class. In format 3 a glyph may appear in the
  Coverage tables of several positions.
- Each action is a SequenceLookupRecord (sequenceIndex plus lookupListIndex; see chapter2.md
  (Sequence lookup record)). In GSUB, lookupListIndex refers to the GSUB LookupList, so a GSUB
  contextual lookup can only cause substitutions.

Processing a matched subtable:

1. Match the input pattern against the current glyph sequence before doing anything else.
   Substitutions made afterwards never change the outcome of this match.
2. Carry out the subtable's SequenceLookupRecords one by one, in the stored order.
3. Each record runs its nested lookup at position sequenceIndex of the input sequence. The
   glyph at that position is the nested lookup's current glyph; if the nested lookup needs more
   glyphs (a ligature, for instance), it takes the input-sequence glyphs that follow.
4. Every record works on the sequence as the earlier records left it, and its sequenceIndex
   counts positions in that changed sequence, not in the sequence as first matched.

Worked case: the input is four glyphs; the first is left alone, a ligature lookup is to merge
the second and third, and a single substitution is to change the fourth. The ligature record
names position 1. Afterwards only three glyphs remain, so the single-substitution record must
name position 2, not 3.

## Lookup type 6: chained contexts substitution

Works like type 5, but each pattern may also require a backtrack sequence (glyphs before the
input) and a lookahead sequence (glyphs after it). The type 5 remarks above apply here as well.

| Format | Patterns expressed as | Structure | Layout |
|---|---|---|---|
| 1 | Specific glyph IDs for backtrack, input and lookahead | ChainedSequenceContextFormat1 | chapter2.md (Chained sequence context format 1: simple glyph contexts) |
| 2 | Glyph classes, with separate ClassDef tables for backtrack, input and lookahead | ChainedSequenceContextFormat2 | chapter2.md (Chained sequence context format 2: class-based glyph contexts) |
| 3 | Separate arrays of Coverage tables for backtrack, input and lookahead | ChainedSequenceContextFormat3 | chapter2.md (Chained sequence context format 3: coverage-based glyph contexts) |

- Substitutions may target input glyphs only; backtrack and lookahead glyphs are context.
- Backtrack sequences are stored in reverse logical order (the glyph nearest the input first);
  the details are in chapter2.md (Chained sequence context format 1: simple glyph contexts).
- As in type 5, a glyph has exactly one class in format 2 but may be in several Coverage tables
  in format 3.
- After a match, processing resumes at the glyph right after the input sequence; lookahead
  glyphs are not passed over.

## Lookup type 7: substitution extension

Lets a lookup reach a subtable through a 32-bit offset, for fonts whose subtables are too large
for the 16-bit offsets used elsewhere in GSUB. The subtable found at the 32-bit offset is
called the extension subtable. One format.

### SubstExtensionFormat1 subtable

The source's prose calls this structure ExtensionSubstFormat1.

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 1 |
| uint16 | extensionLookupType | Lookup type of the extension subtable that extensionOffset points to |
| Offset32 | extensionOffset | Where the extension subtable starts, counted from the start of this ExtensionSubstFormat1 subtable |

- extensionLookupType may be any GSUB lookup type except 7.
- When a lookup uses extension subtables, all of them must carry the same extensionLookupType.
- extensionOffset is measured in the normal way, from the start of the ExtensionSubstFormat1
  subtable that holds it.

When a layout engine meets a GSUB lookup of type 7, it must:

1. Treat the Lookup table as though its lookupType were the extensionLookupType of its
   subtables.
2. Treat every extension subtable as though it stood in the place of the type 7 subtable that
   points to it. Offsets inside the extension subtable are therefore taken from the extension
   subtable's own start.

## Lookup type 8: reverse chaining contextual single substitution

ReverseChainSingleSubst substitutes single glyphs in chained context, but processes the glyph
string from its logical end toward its start. Compared with type 6 it is restricted to:

- a coverage-based format only;
- an input sequence of exactly one glyph;
- a single substitution of that glyph, given directly in the subtable (no nested lookups).

It was designed for Arabic styles such as Nastaliq, where the form of a glyph depends on the
glyph after it, starting from the last glyph of a connected group.

### ReverseChainSingleSubstFormat1 subtable

| Type | Name | Description |
|---|---|---|
| uint16 | format | Format number; 1 |
| Offset16 | coverageOffset | Coverage table for the single input glyph, counted from the start of this subtable |
| uint16 | backtrackGlyphCount | Number of backtrack positions |
| Offset16 | backtrackCoverageOffsets[backtrackGlyphCount] | One Coverage table per backtrack position, in glyph sequence order (see below) |
| uint16 | lookaheadGlyphCount | Number of lookahead positions |
| Offset16 | lookaheadCoverageOffsets[lookaheadGlyphCount] | One Coverage table per lookahead position, in glyph sequence order |
| uint16 | glyphCount | Number of entries in substituteGlyphIDs |
| uint16 | substituteGlyphIDs[glyphCount] | Replacement for each input glyph, in Coverage index order |

- The source gives the offset base explicitly only for coverageOffset (the start of the
  subtable); the backtrack and lookahead Coverage offsets are read from the same base.
- glyphCount must equal the number of glyphs in the input Coverage table; the covered glyph
  with Coverage index k is replaced by substituteGlyphIDs[k].
- Coverage tables of different positions may share glyphs.
- The source requires the Coverage arrays to follow the writing direction even though the scan
  runs backwards, and refers to the backtrack convention of chapter2.md (Chained sequence
  context format 1: simple glyph contexts). Concretely, with the input glyph at logical
  position i: backtrackCoverageOffsets[0] is for position i - 1, [1] for i - 2, and so on
  toward the start of the string; lookaheadCoverageOffsets[0] is for position i + 1, [1] for
  i + 2, and so on toward the end.

Processing:

1. Set i to the last glyph of the string (the logical end).
2. If the glyph at i is in the input Coverage table and every backtrack and lookahead position
   matches its Coverage table, replace the glyph at i with substituteGlyphIDs at its Coverage
   index.
3. Move i one glyph toward the logical start and repeat step 2 until the first glyph has been
   handled.

Because the scan starts at the end, a glyph replaced at a later position is already in its new
form when earlier positions check their lookahead; that is how each glyph can follow the form
chosen for the glyph after it.

## Font requirements stated without a reader fallback

The source states the following as conditions on font data and does not say what a reader
must do when one is broken:

- Every subtable of one Lookup table has the same lookup type.
- SingleSubstFormat2 and ReverseChainSingleSubstFormat1: glyphCount equals the number of
  covered glyphs.
- MultipleSubstFormat1: every Sequence table has glyphCount > 0 (no deletion through multiple
  substitution).
- SubstExtensionFormat1: extensionLookupType != 7, and the same value in every subtable of the
  lookup.

The only arithmetic rule is the modulo-65536 wrap of SingleSubstFormat1, which keeps every
computed glyph ID within 0 to 65535.
