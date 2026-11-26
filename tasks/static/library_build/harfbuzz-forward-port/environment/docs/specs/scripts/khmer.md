# Khmer script shaping (digest)
Source: Developing OpenType Fonts for Khmer Script - Typography | Microsoft Learn, https://learn.microsoft.com/en-us/typography/script-development/khmer
These notes restate the source's structures and rules; where they differ, the source governs.

## Contents

1. Terms used by the rules
2. Character classes
3. Notation and syllable structure
4. Shaping stages
5. Stage 1: syllable analysis and reordering
6. Stage 2: substitution features (GSUB)
7. Stage 3: positioning features (GPOS)
8. Feature order table
9. Feature notes
10. Base elements and mark classes
11. Invalid combinations and the dotted circle
12. Recommended extra code points
13. Writing system tags

## 1. Terms used by the rules

- **Base glyph**: the single consonant, independent vowel or number of a
  syllable that keeps its full (nominal) shape. In practice it is normally the
  syllable's leading consonant or independent vowel. Rules are phrased in terms of
  the base glyph, not a base character, because shaping outputs glyphs.
- **COENG** (U+17D2 KHMER SIGN COENG): an invisible control written before a
  consonant or independent vowel to ask for that letter's subscript form. COENG
  and the letter after it are always processed together as one unit. COENG has
  no visible shape of its own (whatever glyph the font gives it is never shown),
  and input methods should not let it be entered on its own.
- **Register shifters** (consonant shifters): U+17C9 KHMER SIGN MUUSIKATOAN and
  U+17CA KHMER SIGN TRIISAP. They move the base consonant into the other
  register. The notation calls either one RegShift.
- **Syllable**: the orthographic unit that shaping works on. Characters are
  stored in phonetic order, which can differ from display order. A shaped
  syllable is atomic: the caret is never placed inside it, and characters are
  deleted from its end. None of the rules below cross a syllable boundary.
- **ROBAT** (U+17CC KHMER SIGN ROBAT): the above-base combining form of RO,
  used when RO is the first consonant of the syllable but not its base. It is
  stored in writing order, after the base: the word KARMA is stored as KA + MA +
  ROBAT (U+1780 U+1798 U+17CC; Unicode names U+1798 KHMER LETTER MO).
- **Subscript glyph**: the form produced by COENG followed by a consonant or an
  independent vowel, for example COENG KA (U+17D2 U+1780).
- **Vowel**: a syllable may contain at most one dependent vowel character. Five
  vowels are drawn in two pieces but stored as one character: U+17BE, U+17BF,
  U+17C0, U+17C4, U+17C5. For these the engine supplies the left-hand piece, a
  glyph shaped like U+17C1, at the front of the syllable.

### Subscript types

| Type | Shape | Members |
|---|---|---|
| Type 1 | Drawn under the base glyph | consonants and independent vowels with subclass SubscriptType1 (section 2) |
| Type 2 | Has an "arm" that takes up room on the left side of the base glyph; at present only COENG RO | U+179A |
| Type 3 | Has an arm that takes up room on the right side of the base glyph | the second consonant subscript row in section 2 (see note 1 there) |

Subscript count and order:

- One base glyph carries at most two subscripts, which may be of different
  types.
- Subscripts must come in type order: Type 1 (allowed twice), then Type 2, then
  Type 3 (allowed twice).
- Taken literally, the valid two-subscript sequences are therefore 1+1, 1+2,
  1+3, 2+3 and 3+3.
- Any other order is invalid. The engine then starts a new cluster whose base
  glyph is a dotted circle (section 11).

## 2. Character classes

Ranges are inclusive. Where the page leaves the Class cell empty, the row
continues the class above it; the class name is repeated here.

| Class | Subclass | Member characters |
|---|---|---|
| Consonant | SubscriptType1 | U+1780..U+1782, U+1784..U+1787, U+1789..U+178C, U+178E..U+1793, U+1795..U+1798, U+179B..U+179D, U+17A0, U+17A2 |
| Consonant | SubscriptType2 | U+179A |
| Consonant | SubscriptType2 (as printed; see note 1) | U+1783, U+1788, U+178D, U+1794, U+1799, U+179E..U+179F, U+17A1 |
| Independent Vowel | (No Subscript) | U+17B4..U+17B5 |
| Independent Vowel | SubscriptType1 | U+17A3..U+17B3 |
| Coeng | | U+17D2 |
| Dependent Vowel | Above-base | U+17B7..U+17BA, U+17BE (split) |
| Dependent Vowel | Below-base | U+17BB..U+17BD |
| Dependent Vowel | Pre-base | U+17C1..U+17C3 |
| Dependent Vowel | Post-base | U+17B6, U+17BF..U+17C0 (split), U+17C4..U+17C5 (split) |
| Register Shifter | | U+17C9..U+17CA |
| Robat | | U+17CC |
| Sign | Above-base | U+17C6, U+17CB, U+17CD..U+17D1, U+17DD |
| Sign | Post-base | U+17C7..U+17C8 |
| Sign | Above numbers | U+17D3 |
| Punctuation | | U+17D4..U+17DA, U+17DC, U+19E0..U+19FF |
| Currency | | U+17DB |
| Number | | U+17E0..U+17E9, U+17F0..U+17F9 |
| Reserved | | U+17DE..U+17DF, U+17EA..U+17EF, U+17FA..U+17FF |

Notes:

1. The page gives the subclass "SubscriptType2" to both consonant rows that
   follow the Type 1 row. Its own definitions say Type 2 is only COENG RO
   (U+179A) and describe a Type 3 that otherwise has no row, so the second
   "SubscriptType2" row (U+1783, U+1788, U+178D, U+1794, U+1799,
   U+179E..U+179F, U+17A1) is the Type 3 set: COENG plus one of these letters
   gets 'pstf' and is not moved.
2. "(split)" marks the two-piece vowels. U+17BE is the only split above-base
   vowel; it is the vowel the analysis step calls KHF_ABVSPLIT. U+17BF, U+17C0,
   U+17C4 and U+17C5 are the split post-base vowels, called KHF_PSTSPLIT.
3. How the notation maps onto this table: Cons = Consonant; IndV = Independent
   Vowel; PreV, BlwV, AbvV, PstV = Dependent Vowel Pre-base, Below-base,
   Above-base, Post-base; RegShift = Register Shifter; AbvS = Sign Above-base
   (includes NIKAHIT, U+17C6); PstS = Sign Post-base (includes REAHMUK,
   U+17C7); Robat = U+17CC; COENG = U+17D2.

## 3. Notation and syllable structure

### Symbols

| Symbol | Meaning |
|---|---|
| Cons | consonant character |
| IndV | independent vowel character |
| COENG | U+17D2 |
| PreV | dependent vowel drawn before the base glyph |
| BlwV | dependent vowel drawn below the base glyph |
| RegShift | register shifter, U+17C9 (MUUSIKATOAN) or U+17CA (TRIISAP) |
| AbvV | dependent vowel drawn above the base glyph |
| AbvS | sign placed over the base glyph |
| Robat | the glyph of ROBAT, U+17CC |
| PstV | dependent vowel drawn after the base glyph |
| PstS | sign drawn after the base glyph |
| Nikahit | sign that forms a compound vowel alone or with a vowel, adding an m or n sound; counted as AbvS |
| Reahmuk | sign that forms a compound vowel alone or with a vowel, adding aspiration (h); counted as PstS |
| { } | the enclosed item occurs 0, 1 or 2 times |
| [ ] | the enclosed item occurs 0 or 1 times |
| \| | exclusive or: exactly one of the alternatives |
| + | and, in sequence |
| ( ) | grouping (used in the formula but not defined separately on the page) |

### Co-occurrence limits

- PreV and PstV never occur in the same syllable. The pre-plus-post two-piece
  vowels (U+17BF, U+17C0, U+17C4, U+17C5) are classed as PstV; the engine adds
  their U+17C1-shaped left piece itself, which is why a PreV cannot accompany
  them.
- A base glyph cannot take both a BlwV and an AbvV. The pair U+17BB + U+17C6 is
  allowed because U+17C6 is a sign (AbvS), not a vowel.
- U+17BE (left piece plus above piece) counts as an AbvV; here too the engine
  puts a U+17C1 piece at the start of the syllable.
- A RegShift normally sits right above the base glyph, but takes a lowered,
  ambiguous shape at the very bottom of the syllable when an above-base vowel
  or vowel piece is present (section 5.2).

### Syllable formula

Every syllable starts with a consonant, an independent vowel or a number. The
page gives a formula for consonant-initial syllables only. The same sequence is
the canonical storage order, which sorting and searching rely on:

```
Cons + {COENG + (Cons | IndV)} + [PreV | BlwV] + [RegShift] + [AbvV] + {AbvS} + [PstV] + [PstS]
```

Reading it left to right: one consonant; up to two subscripts, each COENG
followed by a consonant or an independent vowel; at most one of PreV or BlwV;
an optional register shifter; an optional above-base vowel; up to two
above-base signs; an optional post-base vowel; an optional post-base sign.
Robat, ZWJ and ZWNJ do not appear in the formula.

Canonical order defines text identity. For example, U+17C1 followed by U+17B6
can look like U+17C4 but is a different spelling; it also breaks the
one-vowel-per-syllable rule, so it is invalid.

## 4. Shaping stages

The Khmer shaper (Uniscribe) runs three stages, in this order:

1. Analyze syllables and reorder characters (section 5).
2. Shape (substitute) glyphs with OTLS (OpenType Library Services, the
   layout library) (section 6).
3. Position glyphs with OTLS (section 7).

Two further topics apply across the stages: base elements (section 10) and
invalid combining marks (section 11).

## 5. Stage 1: syllable analysis and reordering

### 5.1 Steps

In the order the page lists them:

1. Expect every syllable to start with a Cons, an IndV or a Number.
2. For each COENG + (Cons | IndV) pair met while the syllable has fewer than
   two subscripts so far, act according to the subscript type of the letter
   after COENG:
   1. Type 1: tag the COENG + (Cons | IndV) pair for 'blwf'.
   2. Type 2: move the COENG + RO pair so that it sits immediately before the
      base glyph, then tag it for 'pref'.
   3. Type 3: tag the COENG + Cons pair for 'pstf'.
3. If a RegShift is followed by an AbvV, tag the RegShift for 'blwf'; this
   selects its below-base shape, which resembles U+17BB.
4. If an AbvV is a KHF_ABVSPLIT vowel (U+17BE): put the pre-base piece
   (U+17C1) at the beginning of the cluster, and tag the AbvV for 'abvf' so its
   glyph turns into the above-base piece alone (which resembles U+17B8).
5. If a PstV is a KHF_PSTSPLIT vowel (U+17BF, U+17C0, U+17C4, U+17C5): put the
   pre-base piece (U+17C1) at the beginning of the cluster, and tag the PstV
   for 'pstf' so its glyph turns into the second (right-hand) piece.

Front-of-syllable order when both moves happen: the inserted U+17C1 piece, then
COENG + RO, then the base glyph. The step list has no separate step that moves a
plain PreV (U+17C1..U+17C3); the page only defines PreV as a vowel drawn before
the base glyph.

### 5.2 RegShift handling

- By default the register shifter is drawn just above the base glyph; its
  position follows from the vowel above it.
- When it stands before an AbvV it is normally drawn instead as a vertical
  stroke at the lowest point of the syllable (the 'blwf' tag of step 3).
- To keep the above-base shape even though an AbvV follows, ZWNJ (U+200C) is
  inserted so that the engine's context rule does not fire. The page's prose
  puts the ZWNJ between the RegShift and the AbvV.

Examples given on the page:

| Sequence | Behaviour |
|---|---|
| U+179F U+17CA U+17B8 | TRIISAP takes its below-base form because AbvV U+17B8 follows it. |
| U+1784 U+17C9 U+17B7 U+1780 U+1784 U+17C9 U+1780 U+17CB | The first MUUSIKATOAN is lowered (AbvV U+17B7 follows it); the second keeps its above-base form (no AbvV follows it). The page prints the second code point as "17C9", without the "U+". |
| U+17A2 U+200C U+17CA U+17B7 U+17A2 U+17BB U+17CA U+17C7 | The first TRIISAP is held above by the ZWNJ. The second needs no ZWNJ: its syllable has a below-base vowel (U+17BB), so no AbvV can follow it. In this example the ZWNJ stands before the register shifter, not between it and the AbvV as the prose describes. |

## 6. Stage 2: substitution features (GSUB)

The engine calls the layout library once per feature, one feature after
another in the fixed order below, and each call acts on the relevant glyphs of
the current syllable. One call per feature is what guarantees the order.

| Step | Group | Feature | Applied to, and purpose |
|---|---|---|---|
| 1 | Language forms | pref | The reordered COENG + RO pair: forms the pre-base ligature. |
| 2 | Language forms | blwf | Type 1 subscript pairs (below-base ligatures), and a RegShift tagged for its lowered shape. |
| 3 | Language forms | abvf | RO with the COENG that follows it, to give the Robat glyph (as the page words it); and a KHF_ABVSPLIT vowel, to give its above-base piece. |
| 4 | Language forms | pstf | Type 3 subscript pairs and KHF_PSTSPLIT vowels: post-base ligatures and second pieces. |
| 5 | Conjuncts and typographical forms | pres | Acts on the COENG RO glyph, giving pre-base variants, if the syllable also carries a Type 1 subscript. |
| 6 | Conjuncts and typographical forms | blws | Optional below-base refinements for typographic quality. |
| 7 | Conjuncts and typographical forms | abvs | Optional above-base refinements for typographic quality. |
| 8 | Conjuncts and typographical forms | psts | Optional post-base refinements; example: a Type 3 subscript variant with a smaller descent when a Type 1 subscript is also present. |
| 9 | Conjuncts and typographical forms | clig | Contextual ligatures for typographic quality; example: a Type 3 subscript followed by the second piece of OO (U+17C4). |

## 7. Stage 3: positioning features (GPOS)

Positioning comes after all substitution, again one feature at a time:

| Step | Group | Feature | Purpose |
|---|---|---|---|
| 1 | Distances | dist | Remaining spacing adjustments, for instance kerning between pre-base or post-base elements and the base glyph. |
| 2 | Below-base marks | blwm | Attaches below-base forms, vowel modifiers and stress or tone marks to the base glyph. |
| 3 | Above-base marks | abvm | Attaches above-base forms, vowel modifiers and stress or tone marks to the base glyph. |
| 4 | Mark to mark | mkmk | Places AbvS glyphs over AbvV glyphs, and BlwV glyphs under subscript glyphs. |

## 8. Feature order table

The standard order in which Khmer features are executed, one by one:

| Group | Feature | Feature function | Layout operation | Required |
|---|---|---|---|---|
| Language based forms | pref | Pre-base forms | GSUB | X |
| Language based forms | blwf | Below-base forms | GSUB | X |
| Language based forms | abvf | Above-base forms | GSUB | X |
| Language based forms | pstf | Post-base forms | GSUB | X |
| Conjuncts & typographical forms | pres | Pre-base substitution | GSUB | X |
| Conjuncts & typographical forms | blws | Below-base substitution | GSUB | X |
| Conjuncts & typographical forms | abvs | Above-base substitution | GSUB | X |
| Conjuncts & typographical forms | psts | Post-base substitution | GSUB | X |
| Conjuncts & typographical forms | clig | Contextual ligature substitution | GSUB | X |
| Positioning features | dist | Distances | GPOS | |
| Positioning features | blwm | Below-base mark positioning | GPOS | |
| Positioning features | abvm | Above-base mark positioning | GPOS | |
| Positioning features | mkmk | Mark to mark positioning | GPOS | |

GSUB = glyph substitution, GPOS = glyph positioning. The order of lookups
inside each feature matters as well (section 9). The table puts an X under
Required for pres, blws, abvs, psts and clig, while the page's feature notes
describe pres, blws, abvs and psts as optional typographic features whose
content varies from font to font; either way the engine runs them in this
order.

## 9. Feature notes

- **pref** (Pre-base forms; GSUB LookupType 4, ligature): replaces the COENG +
  consonant pair with the pre-base subscript glyph; in Khmer this is COENG RO.
- **blwf** (Below-base forms; GSUB LookupType 4): replaces COENG + consonant
  (for example COENG KA) with the below-base subscript glyph, and gives a
  tagged register shifter its lowered glyph.
- **abvf** (Above-base forms; GSUB LookupType 1, single): swaps a split vowel's
  nominal glyph for a glyph showing only the part above the base. This works
  because the engine has already put the left piece in front of the base glyph.
- **pstf** (Post-base forms; GSUB LookupType 4): replaces a post-base sequence
  with a post-base ligature glyph.
- **pres, blws, abvs, psts** (conjuncts and typographical forms): optional,
  font-specific refinements; fonts may cover different sets of conjuncts, and
  almost none are strictly needed. Guidance that applies to all four:
  - They act within one orthographic syllable only.
  - The engine hands the whole syllable to the layout library and does not
    dictate lookup formats or inputs, so lookups may use any context.
  - The library runs the font's lookups left to right in the font's order:
    pre-base first, then below-base, above-base and post-base. Fonts should
    order their lookups the same way.
  - For every newly added element, check three things in sequence: does it
    ligate with the base glyph; does it ligate with elements that come before
    it in canonical order; does it need a contextual form. Each step must
    allow for forms that earlier steps produced.
  - **pres** produces pre-base conjunct forms; **blws**, **abvs** and **psts**
    make below-, above- and post-base adjustments (psts example: a Type 3
    subscript with a smaller descent next to a Type 1 subscript).
- **clig** (Contextual ligatures): ligatures used only in a stated context,
  built as chained-context ligature substitution. The page cites GSUB lookup
  type 8 for it (in the OpenType GSUB table, chained context substitution is
  type 6 and type 8 is reverse chaining single substitution). A ligature with
  more components must come before one with fewer, or it will never match.
- **dist** (Distances; GPOS LookupType 2, pair adjustment): moves glyphs toward
  or away from one another; covers any spacing lookup not handled elsewhere,
  such as kerning pre- and post-base elements against the base. The page notes
  that no usage examples were available.
- **blwm** (Below-base mark positioning; GPOS LookupTypes 4 and 5): attaches
  below-base marks to bases. Suggested encoding: a chaining contextual
  positioning lookup that calls mark-to-base and mark-to-mark attachment.
- **abvm** (Above-base mark positioning; GPOS LookupTypes 4 and 5): the same
  for above-base marks, with the same suggested encoding.
- **mkmk** (Mark to mark positioning; GPOS LookupType 6, MarkToMark): positions
  one mark glyph relative to another.

## 10. Base elements and mark classes

Many lookups must relate the base glyph to one pre-base, post-base or
above-base element, but reordering cannot make every such element adjacent to
the base, so lookups have to skip whatever lies between them. The page's
method:

- Give the mark glyph class to glyphs whose characters Unicode treats as marks,
  and also to below-base and above-base consonant forms.
- Give each kind of syllable element and positional form its own mark
  attachment class, chosen by its position relative to the base.
- Let each lookup handle a single mark type; for example, an above-base
  substitution lookup normally needs to see only above-base elements.

## 11. Invalid combinations and the dotted circle

- A combining mark or sign that is not attached to a valid consonant base is
  invalid. The engine shows it using Unicode's fallback rendering for
  non-spacing marks, that is, on a dotted circle (U+25CC).
- To display a sign deliberately on its own, put it on a space character.
- Fonts should therefore include a glyph for U+25CC; if it is missing, the
  invalid sign is drawn on the missing-glyph (white box) glyph.
- These are invalid and make the engine begin a new cluster with a dotted
  circle as its base glyph:
  - a second vowel character within one syllable;
  - a third subscript on the same base;
  - subscripts out of type order (section 1).
- The dotted circle exists only in the glyph array returned by shaping
  (ScriptShape); it is never inserted into the stored text.
- Reason: without this, a non-OpenType renderer would overprint invalid mark
  combinations; a dotted-circle base keeps them legible.

## 12. Recommended extra code points

Besides the Khmer characters, fonts should cover:

| Code point | Name | Use |
|---|---|---|
| U+25CC | DOTTED CIRCLE | base for invalid marks |
| U+200D | ZERO WIDTH JOINER (ZWJ) | |
| U+200C | ZERO WIDTH NON-JOINER (ZWNJ) | also keeps a register shifter above the base (section 5.2) |
| U+200B | ZERO WIDTH SPACE (ZWSP) | marks word boundaries |

## 13. Writing system tags

| Script tag | Script | Language system tag | Language |
|---|---|---|---|
| 'khmr' | Khmer | 'dflt' | default script handling |
| | | 'KHM ' (KHM followed by a space) | Khmer |

- Features are looked up by script tag and language system tag together.
- Uniscribe uses only the default language system of each script; fonts may
  still add language-specific features for other software.
- Always include 'dflt'. It holds the basic script behaviour and is the
  fallback when no language system matches or the application does not
  support the language; a font without it may not work in some applications.
- Tags are case-sensitive and exactly four characters long: script tags in
  lower case, language tags in upper case, with a space appended to
  three-letter language tags.
