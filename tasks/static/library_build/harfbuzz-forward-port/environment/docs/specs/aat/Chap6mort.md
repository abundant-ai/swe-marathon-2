# 'mort' table: glyph metamorphosis, the older format (digest)
Source: Glyph Metamorphosis Table - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6mort.html
These notes restate the source's structures and rules; where they differ, the source governs.

## Status

- Deprecated. Supported on OS X, never on iOS; Apple's tools no longer
  generate it; new fonts should use 'morx' (see Chap6morx.md).
- If a font carries both 'mort' and 'morx', 'mort' is ignored.
- The concepts (chains, feature table, sub-feature flags, the five subtable
  kinds) are the same as in 'morx'; the differences are in field widths,
  state table encoding and how actions address their data.

## Differences from 'morx' at a glance

| Aspect | 'mort' | 'morx' |
|---|---|---|
| Table version | fixed32 0x00010000 | uint16 2 or 3, then uint16 unused |
| nFeatureEntries, nSubtables in chain header | uint16 each | uint32 each |
| Subtable header | uint16 length, uint16 coverage, uint32 subFeatureFlags (8 bytes) | uint32 length, uint32 coverage, uint32 subFeatureFlags (12 bytes) |
| Coverage bits | 0x8000 vertical, 0x4000 descending, 0x2000 both orientations, type in 0x0007 | 0x80000000, 0x40000000, 0x20000000, plus 0x10000000 logical order; type in 0x000000FF |
| State table header | StateHeader, uint16 fields | STXHeader, uint32 fields |
| Class table | firstGlyph, nGlyphs, uint8 class array | lookup table, uint16 classes |
| State array cell | uint8 | uint16 |
| newState in entries | byte offset from the start of the state table to the state's row | zero-based row index |
| Contextual substitution targets | markOffset / currentOffset: word offsets to per-glyph substitution tables | markIndex / currentIndex into an offset array of lookup tables (0xFFFF = none) |
| Ligature action trigger | low 14 bits of the entry flags hold the action list offset (non-zero = act) | performAction flag 0x2000 plus a separate ligActionIndex |
| Ligature action offset field | word offset from the state table to a per-glyph component offset table | 30-bit signed value added to the glyph ID to index the component table |
| Component values | byte offsets, summed into an offset to the ligature glyph | uint16 values, summed into an index into the ligature list |
| Insertion subtable | state table only; glyph lists addressed by byte offset (0 = none) | STXHeader plus insertionActionOffset; lists addressed by index (0xFFFF = none) |
| Glyph coverage bitfields | none | version 3 |
| Lengths | subtables padded to multiples of 4; chains start on 4-byte boundaries | chainLength a multiple of 4 |

## Table header

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | fixed32 | version | 0x00010000 |
| 4 | uint32 | nChains | number of chains |

Each chain starts on a 4-byte boundary; padding is inserted between chains as
needed.

## Chain header

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | defaultFlags | default sub-feature flags of the chain |
| 4 | uint32 | chainLength | chain length in bytes, header included |
| 8 | uint16 | nFeatureEntries | entries in the feature table |
| 10 | uint16 | nSubtables | subtables in the chain |

One chain normally suffices unless the font needs more than 32 sub-features.
The feature table follows the chain header, then the subtables.

## Feature table

Same 12-byte entry and the same resolution procedure as 'morx':

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | featureType | feature type |
| 2 | uint16 | featureSetting | setting |
| 4 | uint32 | enableFlags | flags this setting turns on |
| 8 | uint32 | disableFlags | complement of the flags this setting turns off |

    flags = defaultFlags
    for each entry in table order:
        if its feature/setting was requested: flags = (flags AND disableFlags) OR enableFlags
    a subtable runs when (subFeatureFlags AND flags) != 0

Later entries win over earlier ones. The table must end with the
glyph-effects-off entry (enable 0x00000000, disable 0x00000000), which clears
all flags when requested.

Worked flag examples from the page:

Vertical parentheses font (one chain, defaultFlags 1, one noncontextual
subtable with subFeatureFlags 0x00000001):

| featureType | featureSetting | enableFlags | disableFlags |
|---|---|---|---|
| 4 (vertical substitution) | 0 (on) | 0x00000001 | 0xFFFFFFFF |
| 4 (vertical substitution) | 1 (off) | 0x00000000 | 0xFFFFFFFE |
| 0 (glyph effects) | 1 (off) | 0x00000000 | 0x00000000 |

Ligature settings, hierarchical design (subtables with subFeatureFlags 0x1
mandatory, 0x2 normal-only, 0x4 optional-only; choosing a level also runs the
lower levels):

| Setting | enableFlags | disableFlags |
|---|---|---|
| Mandatory | 0x00000001 | 0xFFFFFFF9 (complement of 0x00000006) |
| Normal | 0x00000003 | 0xFFFFFFFB (complement of 0x00000004) |
| Optional | 0x00000007 | 0xFFFFFFFF (complement of 0x00000000) |
| Suppress | 0x00000000 | 0xFFFFFFF8 (complement of 0x00000007) |

Ligature settings, stand-alone design (each setting selects exactly one
subtable, which duplicates the lower levels' ligatures; faster because one
subtable runs):

| Setting | enableFlags | disableFlags |
|---|---|---|
| Mandatory | 0x00000001 | 0xFFFFFFF9 (complement of 0x00000006) |
| Normal | 0x00000002 | 0xFFFFFFFA (complement of 0x00000005) |
| Optional | 0x00000004 | 0xFFFFFFFC (complement of 0x00000003) |
| Suppress | 0x00000000 | 0xFFFFFFF8 (complement of 0x00000007) |

The stand-alone feature entries can also drive the hierarchical subtables if
those subtables' subFeatureFlags become 0x7, 0x6 and 0x4.

## Subtables

### MorphSubtableHeader (8 bytes)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | length | subtable length in bytes, header included; must be a multiple of 4 (pad at the end) |
| 2 | uint16 | coverage | flags and subtable type |
| 4 | uint32 | subFeatureFlags | sub-feature bits served by this subtable |

### coverage field (uint16)

| Mask | Meaning |
|---|---|
| 0x8000 | 1: apply only to vertical text; 0: only to horizontal text (bit 0x2000 can override) |
| 0x4000 | 1: process the glyph array in descending order; 0: ascending |
| 0x2000 | 1: apply regardless of bit 0x8000, i.e. to both orientations (available from GX 1.1; older software ignores it) |
| 0x1FF8 | reserved, 0 |
| 0x0007 | subtable type |

### Subtable types

| Type | Subtable |
|---|---|
| 0 | Indic-style rearrangement |
| 1 | contextual glyph substitution |
| 2 | ligature substitution |
| 3 | reserved |
| 4 | noncontextual glyph substitution |
| 5 | contextual glyph insertion |

## Classic state tables

Every state-machine subtable starts with a StateHeader. The page links to the
manual's state-table chapter for its definition; the 'kern' page's worked
example shows this layout (offsets from the start of the StateHeader):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | stateSize | number of classes (= bytes per state array row) |
| 2 | uint16 | classTable | offset to the class subtable |
| 4 | uint16 | stateArray | offset to the state array |
| 6 | uint16 | entryTable | offset to the entry table |

- Class subtable: uint16 firstGlyph, uint16 nGlyphs, uint8 classArray[nGlyphs];
  glyphs outside the range are class 1 (out of bounds).
- Fixed classes 0..3: End of text, Out of bounds, Deleted glyph, End of line.
- State array cells are uint8 entry indices.
- Entries start with uint16 newState (a byte offset from the start of the
  state table to the next state's row) and uint16 flags.

## Type 0: Indic rearrangement

Body: StateHeader only. Entry: newState, flags. Flags and the sixteen verbs
are identical to 'morx' type 0:

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | markFirst | current glyph becomes the first glyph of the range |
| 0x4000 | dontAdvance | do not advance before moving to the new state |
| 0x2000 | markLast | current glyph becomes the last glyph of the range |
| 0x1FF0 | reserved | 0 |
| 0x000F | verb | rearrangement code |

| Verb | Before => after |
|---|---|
| 0 | no change |
| 1 | Ax => xA |
| 2 | xD => Dx |
| 3 | AxD => DxA |
| 4 | ABx => xAB |
| 5 | ABx => xBA |
| 6 | xCD => CDx |
| 7 | xCD => DCx |
| 8 | AxCD => CDxA |
| 9 | AxCD => DCxA |
| 10 | ABxD => DxAB |
| 11 | ABxD => DxBA |
| 12 | ABxCD => CDxAB |
| 13 | ABxCD => CDxBA |
| 14 | ABxCD => DCxAB |
| 15 | ABxCD => DCxBA |

The marks are set before the verb of the same entry is applied.

## Type 1: contextual glyph substitution

Substitutes the current glyph and/or an earlier marked glyph; setMark makes
the current glyph the marked one after this entry's substitutions.

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | StateHeader | stHeader | state table header |
| 8 | uint16 | substitutionTable | offset from the start of the state subtable to the substitution tables |

Entry (four 16-bit words):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | newState | byte offset from the start of the state table to the next state |
| 2 | uint16 | flags | see next table |
| 4 | uint16 | markOffset | word offset from the start of the state subtable to the substitution table used for the marked glyph |
| 6 | uint16 | currentOffset | word offset from the start of the state subtable to the substitution table used for the current glyph |

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | setMark | make the current glyph the marked glyph |
| 0x4000 | dontAdvance | do not advance before moving to the new state |
| 0x3FFF | reserved | 0 |

Substitution tables are per-glyph tables (one 16-bit replacement per glyph).
Typical uses named by the page: two-glyph ligatures, odd substitutions such as
percent + zero -> per-mille, and longer ligatures built from existing
ligature glyphs (an ff ligature followed by i -> ffi).

## Type 2: ligature substitution

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | StateHeader | stHeader | state table header |
| 8 | uint16 | ligActionTable | byte offset (from the state table start) of the action lists |
| 10 | uint16 | componentTable | byte offset (from the state table start) of the per-glyph component tables |
| 12 | uint16 | ligatureTable | byte offset (from the state table start) of the ligature glyph table |

Entry: uint16 newState, uint16 flags (no per-glyph substitution fields).

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | setComponent | make the current glyph a ligature component (push it) |
| 0x4000 | dontAdvance | do not advance before moving to the new state |
| 0x3FFF | offset | byte offset from the beginning of the subtable to this entry's ligature action list; a multiple of 4; non-zero means "run the actions" |

Ligature action (uint32; the list is 4-byte aligned):

| Mask | Name | Meaning |
|---|---|---|
| 0x80000000 | last | final action of the list; implies store |
| 0x40000000 | store | put the ligature in place of the glyph just popped |
| 0x3FFFFFFF | offset | word offset from the start of the state table to the per-glyph component offset table for this component |

Processing:

- The component stack is 16 deep, so a ligature has at most 16 components;
  ligature tables are sorted by first component, then second, and so on.
- Each action pops one component (most recent first) and adds that glyph's
  value from the component offset table it names to a running sum.
- If neither store nor last is set, the popped glyph is replaced by the
  deleted glyph. If store or last is set, the running sum locates the
  ligature glyph index, which replaces the popped glyph. An n-component
  ligature thus leaves one ligature glyph plus n - 1 deleted glyphs
  (f f i -> ffi plus two deleted glyphs).
- Usually only the last action stores; setting store on intermediate actions
  forms several ligatures from one list, limited only by the stack size.
- After the list is done, the position of each ligature glyph is pushed back
  on the stack so ligatures can be components of further ligatures (ff
  feeding ffi).
- The running sum is a byte offset. Component values for one position are
  relative offsets into the ligature table; one of the component tables must
  also add the ligature table's own offset so the final sum is relative to
  the start of the state subtable.

Example values from the page (ligature table sorted a/b/c, then d/e/f, then
g/h/i, 2 bytes per glyph): a = 1000, b = 1018, c = 1036; d = 0, e = 6,
f = 12; g = 0, h = 2, i = 4. So b f h -> 1018 + 12 + 2 = 1032 and
a e i -> 1000 + 6 + 4 = 1010, both relative to the ligature table.

## Type 4: noncontextual glyph substitution

Body: one lookup table mapping each affected glyph to its replacement.

## Type 5: contextual glyph insertion (from GX 1.1)

Kashida-like insertions travel with the glyph they are attached to
(selection, justification width, caret split); split-vowel-like insertions
are attached next to one glyph but selected with another.

Body: StateHeader only. Entry (8 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | newState | byte offset from the start of the state table to the next state |
| 2 | uint16 | flags | see next table |
| 4 | uint16 | currentInsertList | byte offset from the start of the state table to the uint16 glyph list inserted at the current glyph; 0 = none |
| 6 | uint16 | markedInsertList | byte offset from the start of the state table to the uint16 glyph list inserted at the marked glyph; 0 = none |

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | setMark | mark the current glyph |
| 0x4000 | dontAdvance | do not advance before moving to the new state |
| 0x2000 | currentIsKashidaLike | with a non-zero currentInsertList: set = kashida-like, clear = split-vowel-like |
| 0x1000 | markedIsKashidaLike | with a non-zero markedInsertList: set = kashida-like, clear = split-vowel-like |
| 0x0800 | currentInsertBefore | set: insert to the left of the current glyph; clear: to its right |
| 0x0400 | markedInsertBefore | set: insert to the left of the marked glyph; clear: to its right |
| 0x03E0 | currentInsertCount | 5-bit number of glyphs inserted at the current glyph (max 31) |
| 0x001F | markedInsertCount | 5-bit number of glyphs inserted at the marked glyph (max 31) |

Split vowels work as in 'morx': mark candidate consonants and, on meeting the
vowel, insert before the marked glyph with markedIsKashidaLike clear (both
pieces then belong to the vowel's character offset); or process in reverse,
mark the vowel, and insert before the current glyph when the consonant is
reached.

## Tools note

Apple's ftxdumperfuser can dump 'mort' (not fuse it); ftxenhancer does not
produce 'mort'.
