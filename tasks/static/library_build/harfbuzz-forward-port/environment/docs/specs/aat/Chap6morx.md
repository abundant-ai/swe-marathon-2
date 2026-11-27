# 'morx' table: extended glyph metamorphosis (digest)
Source: Extended Glyph Metamorphosis Table - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6morx.html
These notes restate the source's structures and rules; where they differ, the source governs.

## Purpose and overall structure

'morx' describes glyph transformations ("text features": ligatures, cursive
forms, contextual swashes, Indic rearrangement and so on) that the layout
engine applies to a glyph run. Features a font exposes must be registered in
Apple's Font Feature Registry (see AppendixF.md); the feature names shown to
users live in 'feat' (see Chap6feat.md).

Nesting:

    'morx' header
      chain 1 .. chain nChains, each:
        chain header
        feature table (nFeatureEntries entries)
        metamorphosis subtables (nSubtables), each: subtable header + type-specific body
        [version >= 3] subtable glyph coverage array

All offsets are byte offsets unless the text says index.

## Table header

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | version | 2 or 3 |
| 2 | uint16 | unused | 0 |
| 4 | uint32 | nChains | number of chains that follow |

## Chain header

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | defaultFlags | sub-feature flags in force when the user specifies nothing |
| 4 | uint32 | chainLength | bytes in the whole chain, header included; a multiple of 4 |
| 8 | uint32 | nFeatureEntries | number of feature table entries |
| 12 | uint32 | nSubtables | number of subtables in the chain |

In version 3 tables, the last subtable of each chain is followed by that
chain's subtable glyph coverage array.

## Feature table

Entry (12 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | featureType | registry feature type |
| 2 | uint16 | featureSetting | selector (setting) of that feature |
| 4 | uint32 | enableFlags | flags this feature/setting turns on |
| 8 | uint32 | disableFlags | complement of the flags this feature/setting turns off |

### Turning a feature request into the chain's flags

    flags = chain.defaultFlags
    for each entry, in the order stored in the feature table:
        if (entry.featureType, entry.featureSetting) is among the requested settings:
            flags = (flags AND entry.disableFlags) OR entry.enableFlags
        (an entry that was not requested changes nothing)
    -> flags is the chain's sub-feature flag set for this request

- The order of the caller's request list does not matter; the order of the
  feature table does: a later entry overrides an earlier one, which lets the
  font designer encode how features interact.
- defaultFlags therefore describe what happens for every feature the user
  leaves alone.
- Every feature table must end with the entry for the glyph-effects-off
  setting (the page names it the Enable Glyph Effects feature with
  enableEffectOffSelector; the 'mort' page's worked example encodes it as
  featureType 0, featureSetting 1, i.e. All Typographic Features off). Its
  enableFlags are 0x00000000 and its disableFlags 0x00000000 (the complement
  of 0xFFFFFFFF), so requesting it clears every sub-feature flag of the chain.
- A subtable takes part in processing when
  (subtable.subFeatureFlags AND flags) != 0. Example from the page: flags
  0x00010001 enable a subtable whose subFeatureFlags are 0x00000001.
- Selector conventions come from the registry: for non-exclusive features
  an even selector turns a setting on and the following odd selector turns
  it off; exclusive features use plain values (see AppendixF.md and
  Chap6feat.md).

### Language-specific glyphs (feature type 39)

- Feature type 39 works with the 'ltag' table and must be flagged exclusive.
- Selector 0 means "no change" (typically the language-independent forms).
- Selector n > 0 selects the glyphs for the language at 'ltag' index n - 1.
- Which glyphs count as language-specific is the font designer's choice.

## Subtable header (12 bytes)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | length | bytes in the subtable, this header included |
| 4 | uint32 | coverage | flags and subtable type, see next table |
| 8 | uint32 | subFeatureFlags | the sub-feature bits that need this subtable; it runs when they intersect the resolved flags |

### coverage field (uint32)

| Mask | Meaning |
|---|---|
| 0x80000000 | set: apply only to vertical text; clear: apply only to horizontal text |
| 0x40000000 | set: process glyphs in descending order; clear: ascending order |
| 0x20000000 | set: apply to both horizontal and vertical text (bit 0x80000000 is then ignored) |
| 0x10000000 | set: process in logical order (or reverse logical order; the page's cell says this depends on bit 0x80000000, while the order table below ties it to bit 30) |
| 0x0FFFFF00 | reserved, 0 |
| 0x000000FF | subtable type |

Processing order. Normally the bidi algorithm has already run, so the glyphs
are in layout order (left to right, or top to bottom); logical order is the
order of the backing-store characters, which is the reverse of layout order
for right-to-left text. Bit 28 (0x10000000) chooses logical versus layout
order; bit 30 (0x40000000) chooses forward versus backward within it:

| Bit 30 | Bit 28 | Order for horizontal text |
|---|---|---|
| 0 | 0 | layout order (left to right) |
| 1 | 0 | reverse layout order (right to left) |
| 0 | 1 | logical order (follows the characters; may be either direction) |
| 1 | 1 | reverse logical order |

### Subtable types

| Type | Subtable |
|---|---|
| 0 | rearrangement (Indic-style) |
| 1 | contextual glyph substitution |
| 2 | ligature |
| 3 | reserved |
| 4 | noncontextual ("swash") substitution |
| 5 | glyph insertion |

## Lookup tables inside 'morx'

- Class tables and substitution tables are AAT lookup tables.
- A lookup may list a glyph that should stay unchanged by giving it the value
  0. Parsers must treat a returned 0 as "no substitution / do nothing";
  consequently no 'morx' subtable can turn a glyph into glyph 0.
- The page's examples show the binary-search formats: a uint16 format, then
  uint16 unitSize, nUnits, searchRange, entrySelector, rangeShift, then the
  units, then a guard unit made of 0xFFFF glyph values that is not counted in
  nUnits. Format 6 units are {glyph, value}; format 2 units are
  {lastGlyph, firstGlyph, value}.
- The lookup table formats are defined in the manual's common table chapter, which is not among these notes.

## Extended state tables (types 0, 1, 2 and 5)

### STXHeader (shown by the page's examples)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint32 | nClasses | number of classes, the four fixed classes included |
| 4 | uint32 | classTableOffset | offset to the class lookup table |
| 8 | uint32 | stateArrayOffset | offset to the state array |
| 12 | uint32 | entryTableOffset | offset to the entry table |

Offsets are measured from the start of the STXHeader. Type-specific uint32
offsets follow at offset 16. The pieces may appear in any order in the file.

- Class table: a lookup table mapping glyph -> class.
- Fixed classes: 0 End of text, 1 Out of bounds, 2 Deleted glyph,
  3 End of line (names as in the 'kern' page example); font classes start
  at 4.
- State array: rows = states, columns = classes (nClasses columns); each
  cell is a uint16 index into the entry table. In the page's examples,
  row 0 is the start-of-text state and row 1 the start-of-line state.
- Entry table: every entry begins with uint16 newState and uint16 flags,
  followed by type-specific uint16 fields. In 'morx', newState is a
  zero-based state (row) index, not a byte offset as in 'mort', so even very
  large state arrays can be addressed.

### Driving the machine

General loop (state-table conventions of the manual, summarised; the page
itself only restates what changed relative to 'mort'):

1. Start in state 0 (start of text).
2. For the current glyph, take its class from the class lookup (glyphs the
   lookup does not cover are class 1, out of bounds; deleted glyphs are
   class 2).
3. Read state array[state][class] to get an entry; carry out the entry's
   actions.
4. Switch to entry.newState. Move to the next glyph unless the entry has
   dontAdvance set.
5. After the last glyph, run the end-of-text class (0) once so pending work
   can complete.

The traversal direction is the one selected by the coverage bits.

## Type 0: rearrangement subtable

The subtable body is only an STXHeader (no extra offsets, no per-glyph
tables). Entry = uint16 newState, uint16 flags.

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | markFirst | the current glyph becomes the first glyph of the range to rearrange |
| 0x4000 | dontAdvance | stay at the same glyph index for the next step (even though the glyph stored there may have changed) |
| 0x2000 | markLast | the current glyph becomes the last glyph of the range |
| 0x1FF0 | reserved | 0 |
| 0x000F | verb | rearrangement to perform, see next table |

markFirst/markLast are recorded before the verb of the same entry runs. In
the verb table A, B, C, D are single glyphs at the ends of the marked range
and x is everything between them (possibly empty).

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

## Type 1: contextual glyph substitution subtable

Replaces the current glyph and/or an earlier "marked" glyph through
per-glyph substitution lookups.

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | STXHeader | stxHeader | extended state table header |
| 16 | uint32 | substitutionTable | offset from the start of the state table to the substitution table area |

Entry (8 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | newState | zero-based index of the next state |
| 2 | uint16 | flags | see next table |
| 4 | uint16 | markIndex | substitution table to apply to the marked glyph; 0xFFFF = none |
| 6 | uint16 | currentIndex | substitution table to apply to the current glyph; 0xFFFF = none |

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | setMark | make the current glyph the marked glyph (done after this entry's substitutions) |
| 0x4000 | dontAdvance | do not advance before going to the new state |
| 0x3FFF | reserved | 0 |

Substitution table area:

- It starts with an array of uint32 offsets, measured from the start of the
  area, one per substitution lookup table.
- markIndex / currentIndex select an element of that array; the offset found
  there leads to a lookup table that maps the glyph to its replacement.
- The number of lookup tables is not stored anywhere; runtime processing does
  not need it.
- Condensed example from the page: after glyph 80, glyphs 50, 51, 201, 202
  become 600, 601, 602, 900. Classes: 50/51/201/202 -> 4, 80 -> 5. States
  0 and 1 go to state 2 on class 5; in state 2, class 4 selects an entry
  whose currentIndex is 0. The area begins with the single offset 4,
  pointing just past itself to lookup 0 (a format 6 lookup).

## Type 2: ligature subtable

Builds ligatures, or turns a base plus marks into a precomposed glyph.

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | STXHeader | stateHeader | extended state table header |
| 16 | uint32 | ligActionOffset | offset from the STXHeader to the ligature action table |
| 20 | uint32 | componentOffset | offset from the STXHeader to the component table |
| 24 | uint32 | ligatureOffset | offset from the STXHeader to the ligature list |

Entry (6 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | nextStateIndex | state array row for the next glyph |
| 2 | uint16 | entryFlags | see next table |
| 4 | uint16 | ligActionIndex | index of the first ligature action to run, used when performAction is set |

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | setComponent | record the current glyph as a component (push it on the component stack) |
| 0x4000 | dontAdvance | process the same glyph position again in the next step |
| 0x2000 | performAction | run the ligature action list starting at ligActionIndex |
| 0x3FFF | (reserved) | printed this way on the page; it overlaps 0x2000, so in effect the free bits are 0x1FFF; set to 0 |

Ligature action (uint32):

| Mask | Name | Meaning |
|---|---|---|
| 0x80000000 | last | final action of the list; also implies store |
| 0x40000000 | store | write the ligature found at the accumulated index over the glyph just popped |
| 0x3FFFFFFF | offset | 30-bit value, sign-extended to 32 bits, added to the popped glyph's ID to give an index into the component table |

Component table: array of uint16. Ligature list: array of uint16 output
glyph IDs.

Processing a ligature group (the action table is entered by index, not by
offset):

1. Glyphs flagged with setComponent were pushed on the component stack.
2. With performAction, read actions from ligActionIndex onward. Each action
   pops one component, newest first.
3. For the popped glyph g: component index = g + signextend(offset);
   accumulated index += component[component index].
4. If the action has store or last, the glyph at ligature[accumulated index]
   replaces the popped glyph.
5. Stop after the action that has last.

Rules stated on the 'mort' page and carried over (the 'morx' page only lists
changes): the stack is 16 components deep; popped components that do not
receive a ligature become deleted glyphs, so an n-part ligature leaves the
ligature glyph plus n - 1 deleted glyphs; after the list finishes, the
ligature glyphs are pushed back on the stack so that they can serve as
components of longer ligatures. See Chap6mort.md.

Worked example (condensed from the page): glyphs a..i are 20..28; ligatures
are a/b/c + d/e + f/g/h/i (24 of them, glyphs 1000..1015, 1500..1506 and
1511).

- Classes: 20..22 -> 4, 23..24 -> 5, 25..28 -> 6.
- Entries: 1 = go to state 2 + setComponent; 2 = go to state 3 +
  setComponent; 3 = go to state 0 + setComponent + performAction (0xA000)
  with ligActionIndex 0.
- Actions: 0x3FFFFFE7 (offset -25), 0x3FFFFFED (-19), 0xBFFFFFF2 (last,
  -14).
- Component table: [0, 1, 2, 3, 0, 4, 0, 8, 16].
- For b d g = 21 23 26: pop 26 -> index 1 -> +1; pop 23 -> index 4 -> +0;
  pop 21 -> index 7 -> +8; total 9 -> ligature[9] = 1009.

## Type 4: noncontextual substitution subtable

The body is a single lookup table mapping a glyph to its replacement glyph
(a returned 0 means "leave unchanged").

## Type 5: glyph insertion subtable

Inserts glyphs that have no characters of their own. Two behaviours, which
may be mixed in one subtable:

- Kashida-like: the inserted glyphs belong to the glyph they are attached
  to; they are selected together with it, justification widens that glyph by
  the inserted widths, and the caret split covers the whole group.
- Split-vowel-like: the inserted glyphs are attached next to one glyph but
  are selected together with a different glyph (for example a split vowel
  whose first part is placed before the consonant).

Body:

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | STXHeader | stateHeader | extended state table header |
| 16 | uint32 | insertionActionOffset | offset from the STXHeader to the insertion glyph table (array of uint16 glyph IDs) |

Entry (8 bytes):

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | newState | zero-based index of the next state |
| 2 | uint16 | flags | see next table |
| 4 | uint16 | currentInsertIndex | position (counting from 0) in the insertion glyph table where the glyphs for the current glyph start; how many is given by currentInsertCount; 0xFFFF = no insertion |
| 6 | uint16 | markedInsertIndex | same, for the marked glyph, with markedInsertCount; 0xFFFF = no insertion |

| Mask | Name | Meaning |
|---|---|---|
| 0x8000 | setMark | mark the current glyph |
| 0x4000 | dontAdvance | do not update the glyph index before the next step; if glyphs were just inserted right after the current glyph, the next glyph processed is the first inserted one |
| 0x2000 | currentIsKashidaLike | set: the current-glyph insertion is kashida-like; clear: split-vowel-like |
| 0x1000 | markedIsKashidaLike | set: the marked-glyph insertion is kashida-like; clear: split-vowel-like |
| 0x0800 | currentInsertBefore | set: insert to the left of (before) the current glyph; clear: to the right of (after) it |
| 0x0400 | markedInsertBefore | set: insert to the left of (before) the marked glyph; clear: to the right of (after) it |
| 0x03E0 | currentInsertCount | 5-bit count of glyphs to insert at the current glyph (0 = none, maximum 31) |
| 0x001F | markedInsertCount | 5-bit count of glyphs to insert at the marked glyph (0 = none, maximum 31) |

The kashida/split-vowel choice and the before/after choice apply only when the
corresponding insert list is present (index not 0xFFFF, count non-zero).

Split vowels. The two pieces of a split vowel are tied together through the
distance between the current glyph and the marked glyph. Two ways to put the
first piece in front of the consonant that precedes the vowel:

- Forward processing: mark every candidate consonant; when the vowel turns
  up, do a marked insertion with markedInsertBefore set and
  markedIsKashidaLike clear. Both pieces then belong to the vowel's character
  offset, so selecting one highlights both.
- Reverse processing (coverage bit 0x40000000): the vowel is seen first and
  gets marked; on reaching the consonant, insert before the current glyph.

## Subtable glyph coverage (version 3)

Follows the last subtable of each chain.

| Type | Field | Meaning |
|---|---|---|
| uint32[nSubtables] | subtableOffsets | one per subtable of the chain: offset from the start of this coverage structure to that subtable's bitfield; 0 = the subtable has no bitfield |
| uint8[] | coverageBitfields | the bitfields |

- One bitfield is (numGlyphs + 7) / 8 bytes (CHAR_BIT = 8), padded to a
  four-byte boundary.
- Glyph g is covered when bitfield[g / 8] & (1 << (g & 7)) is non-zero.
- A run's own glyph bitfield ANDed with a subtable's bitfield being zero
  means the subtable cannot affect the run and may be skipped. Keep
  bitfields minimal (for an ff/fi/fl ligature subtable, the f glyph alone is
  enough).
- Unlike 'kerx', where 0xFFFFFFFF means "no bitfield", 'morx' uses offset 0.

## Availability (per the page)

- Version 2 is supported on all OS X and iOS versions.
- A second sentence, which also says "version 2" but evidently concerns
  version 3, gives OS X 10.10 and iOS 8.0.
- Support for coverage bit 28 (logical order) is described as planned.
- When a font has both 'morx' and 'mort', 'mort' is ignored (stated on the
  'mort' page).
