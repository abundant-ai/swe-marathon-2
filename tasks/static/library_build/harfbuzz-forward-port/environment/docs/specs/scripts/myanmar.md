# Myanmar script shaping (digest)
Source: Creating and Supporting OpenType Fonts for Myanmar Script - Typography | Microsoft Learn, https://learn.microsoft.com/en-us/typography/script-development/myanmar
These notes restate the source's structures and rules; where they differ, the source governs.

Scope: the page covers the Myanmar script as encoded in Unicode 6.0, used for
Burmese (the Myanmar language) and also for Pali, Sanskrit and other languages.

## Contents

1. Terms
2. Shaping stages and where features apply
3. Character classes
4. Grammar notation
5. Well-formed clusters
6. Reordering
7. GSUB stage
8. GPOS stage
9. Feature order table
10. Feature notes
11. Invalid combining marks
12. Recommended glyphs
13. Writing system and language tags

## 1. Terms

- **Base glyph**: any glyph that a diacritic can attach to. The rules talk
  about base glyphs, not base characters, since a ligature can serve as a base.
- **Cluster**: a group of characters that behaves as one indivisible unit in a
  Brahmi-derived script; it usually matches a syllable.
- **Consonant**: a letter with an inherent short /a/ vowel (so "Ka", not "K").
- **Consonant conjunct** (conjunct): several consonants fused into one
  ligature glyph.
- **Format controls**: ZWNJ (U+200C) and ZWJ (U+200D). They are invisible,
  except where an application opts to render zero-width glyphs.
- **Kinzi**: a reduced form of certain consonants that is written as a mark
  above the following base. It plays the role that reph plays in other
  Brahmi-derived scripts. In text it is the three-character sequence K
  (section 3).
- **Matra**: a dependent vowel sign. It always appears with a single consonant
  or a consonant cluster.
- **OTLS**: OpenType Layout Services, the library in the Microsoft text stack
  that runs the OpenType features of a font.
- **OpenType tag**: a 4-byte identifier of a script, language system or
  feature.

## 2. Shaping stages and where features apply

The Myanmar shaper (Uniscribe) runs these stages in order:

1. Analyzing the characters
2. Well-formed clusters
3. Reordering characters
4. Apply OpenType GSUB features
5. Apply OpenType GPOS features

The analysis stage splits the run into syllable clusters and gives every
character a class (section 3). The classes are used to parse syllables, to
identify their parts and to decide what must be reordered. The engine also
checks that every cluster is valid and, where a combining mark has no valid
base to attach to, adds a U+25CC placeholder glyph.

What the page says about the scope of feature application:

- In outline there are two passes: first a GSUB pass over each logical
  cluster, then a pass of GSUB and GPOS features across the whole run.
- In the GSUB stage, the engine makes one OTLS call per feature (each applied
  across the run), which fixes the order of features.
- The presentation-form features (pres, abvs, blws, psts) are applied all at
  once over the cluster. They therefore behave like one feature; having four of
  them only helps font developers organize lookups, and the lookup order in the
  font decides the result.
- All GPOS features are applied at the same time over the cluster.

## 3. Character classes

Ranges are inclusive. The page writes code points without the "U+" prefix.

| Class | Description | Code points |
|---|---|---|
| A | Anusvara class | U+1032, U+1036 |
| As | Asat | U+103A |
| C | Consonants and Independent vowels | U+1000..U+1020, U+103F, U+104E, U+1050, U+1051, U+105A..U+105D, U+1061, U+1065, U+1066, U+106E..U+1070, U+1075..U+1081, U+108E, U+AA60..U+AA6F, U+AA71..U+AA76, U+AA7A |
| D | Myanmar digits except zero | U+1041..U+1049, U+1090..U+1099 |
| D0 | Myanmar digit zero | U+1040 |
| DB | Dot below | U+1037 |
| GB | Generic base characters | U+00A0, U+00D7, U+2012..U+2015, U+2022, U+25CC, U+25FB..U+25FE |
| H | Halant/virama | U+1039 |
| IV | Independent vowel | U+1021..U+102A, U+1052..U+1055 |
| J | Joiners | U+200C, U+200D |
| K | A special sequence of three characters (kinzi) | one of U+1004, U+101B, U+105A; then U+103A; then U+1039 |
| MH | Medial consonants Ha, Mon La | U+103E, U+1060 |
| MR | Medial consonants Ra | U+103C |
| MW | Medial consonants Wa, Shan Wa | U+103D, U+1082 |
| MY | Medial consonants Ya, Mon Na, Mon Ma | U+103B, U+105E, U+105F |
| O | SCRIPT_COMMON characters in a Myanmar run | by script property, no list |
| P | Punctuation | U+104A, U+104B |
| PT | Pwo and other tones | U+1063, U+1064, U+1069..U+106D, U+AA7B |
| R | Reserved characters from the Myanmar Extended-A block | U+AA7C..U+AA7F |
| S | Symbols | U+104C, U+104D, U+104F, U+109E, U+109F, U+AA70, U+AA77..U+AA79 |
| V | Visarga and Shan tones | U+1038, U+1087..U+108D, U+108F, U+109A..U+109C |
| VAbv | Above base dependent vowel | U+102D, U+102E, U+1033..U+1035, U+1071..U+1074, U+1085, U+1086, U+109D |
| VBlw | Below base dependent vowel | U+102F, U+1030, U+1058, U+1059 |
| VPre | Pre base dependent vowel | U+1031, U+1084 |
| VPst | Post base dependent vowel | U+102B, U+102C, U+1056, U+1057, U+1062, U+1067, U+1068, U+1083 |
| VS | Variation selectors | U+FE00..U+FE0F |
| WJ | Word joiner | U+2060 |
| WS | White space | all white space characters; ZWSP (U+200B) counts as one |

In the page's own notation, K is `<1004 | 101B | 105A>, 103A, 1039`: MYANMAR
LETTER NGA, MYANMAR LETTER RA or MYANMAR LETTER MON NGA, followed by MYANMAR
SIGN ASAT and MYANMAR SIGN VIRAMA.

## 4. Grammar notation

| Notation | Meaning |
|---|---|
| X* | zero or more X. Because this could make a cluster arbitrarily long, the page applies an arbitrary cap of 31 characters to such a sequence. |
| X+ | one or more X |
| <X \| Y> | X or Y (alternatives) |
| [X] | X is optional: zero or one occurrence |
| (X) | grouping |
| # | a boundary occurs here |
| multiplication sign | no boundary allowed at this position |
| division sign | a boundary is allowed at this position |
| ^ | except |

## 5. Well-formed clusters

The page defines three kinds of cluster.

### 5.1 Simple non-compounding cluster

```
<P | S | R | WJ| WS | O | D0 >
```

Each of these characters is a cluster by itself: punctuation (P), symbols (S),
reserved Extended-A characters (R), word joiner (WJ), white space (WS), other
SCRIPT_COMMON characters (O) and, according to the formula, digit zero (D0,
U+1040). D0 is not in the base set of the other two cluster types, so under
these formulas digit zero cannot take dependent marks.

### 5.2 Cluster terminating in Halant

```
[K] <C | IV | D | GB>[VS] (H <C | IV> [VS])* H
```

An optional kinzi; one required base (consonant, independent vowel, non-zero
digit or generic base) with an optional variation selector; any number of
stacked letters, each a halant followed by a consonant or independent vowel and
an optional variation selector; and a final halant that closes the cluster.

### 5.3 Complex cluster

Formula with its repetition marks restored (see the note that follows):

```
[K] <C | IV | D | GB>[VS] (H <C | IV> [VS])* (As)* [MY [As]] [MR] [<MW [As] | [MW] MH [As]>] (VPre)* (VAbv)* (VBlw)* (A)* [DB [As]] (VPst [MH] (As)* (VAbv)* (A)* [DB [As]])* (PT < [A] [DB] [As] | [As] [A] > )* (V)* [J]
```

Note: the published page shows no "*" after seven items that its own
description calls repeatable; the page source has empty emphasis markup at
those points, so the marks were evidently consumed by text formatting. The line
as displayed reads:

```
[K] <C | IV | D | GB>[VS] (H <C | IV> [VS]) (As) [MY [As]] [MR] [<MW [As] | [MW] MH [As]>] (VPre) (VAbv)* (VBlw) (A) [DB [As]] (VPst [MH] (As)* (VAbv)* (A)* [DB [As]]) (PT < [A] [DB] [As] | [As] [A] > ) (V)* [J]
```

The page's slot-by-slot description states "zero or more" for the stacked
letters, the asats that follow them, pre-base vowels, below-base vowels,
anusvara, the post-base vowel groups and the tone groups; that is where the
restored marks go.

Slots, in order:

1. `[K]`: optional kinzi.
2. `<C | IV | D | GB>` then `[VS]`: the required base, with an optional
   variation selector.
3. `(H <C | IV> [VS])*`: any number of stacked consonants or independent
   vowels, each introduced by a halant and optionally followed by a variation
   selector.
4. `(As)*`: any number of asats.
5. Medials, each at most once: `[MY [As]]` (a single asat may follow MY), then
   `[MR]`, then `[<MW [As] | [MW] MH [As]>]`, meaning MW alone, MH alone, or
   MW followed by MH, with one optional asat after the last of them.
6. `(VPre)* (VAbv)*`: any number of pre-base vowels, then any number of
   above-base vowels.
7. `(VBlw)*`: any number of below-base vowels.
8. `(A)* [DB [As]]`: any number of anusvara-class signs, then an optional dot
   below, which may itself take one asat.
9. `(VPst [MH] (As)* (VAbv)* (A)* [DB [As]])*`: any number of post-base vowel
   groups. Each is a post-base vowel, an optional medial Ha, any asats, any
   above-base vowels, any anusvara-class signs and an optional dot below (with
   an optional asat). The page's prose for this slot leaves out the `(A)*`
   item, but the formula includes it.
10. `(PT < [A] [DB] [As] | [As] [A] > )*`: any number of tone groups. Each is a
    Pwo or other tone mark followed either by optional anusvara, optional dot
    below and optional asat (in that order), or by optional asat and then
    optional anusvara.
11. `(V)*`: any number of visarga or Shan tone signs.
12. `[J]`: an optional ZWNJ or ZWJ. A joiner is always the last character of
    the cluster that contains it.

The page also shows a deliberately overloaded cluster that fills many slots at
once (ordinary text rarely uses more than a few of them together):

U+1004 U+103A U+1039 U+1000 U+1039 U+1000 U+103B U+103C U+103D U+103E U+1031
U+102D U+102F U+1037 U+103A U+102C U+103E U+102E U+1037 U+1064 U+1032 U+1036
U+1037 U+1038 U+108D

Mapped onto the slots: kinzi U+1004 U+103A U+1039; base U+1000; stacked U+1039
U+1000; medials U+103B U+103C U+103D U+103E; vowels U+1031, U+102D, U+102F; dot
below and asat U+1037 U+103A; post-base group U+102C U+103E U+102E U+1037; tone
group U+1064 U+1032 ...; visarga and Shan tone U+1038 U+108D. Under the
restored formula a tone group admits only one anusvara-class sign, so the
second one (U+1036, after U+1032) does not fit a slot; the formula and the
sample disagree at that point.

## 6. Reordering

After analysis, the engine builds a glyph buffer for each cluster in which
elements are rearranged by these rules (listed in the page's order):

1. Kinzi (K) moves to directly after the cluster's base.
2. Medial Ra (MR) moves to before the base consonant.
3. Pre-base vowels (VPre) move to the start of the cluster. More than one may
   occur; a run of them moves together as one block to the front.
4. Anusvara (A) that comes right after one or more below-base vowels (VBlw)
   moves to just before those vowels.

The resulting front of a cluster is: VPre block, MR, base, kinzi, then the
remaining elements.

### Worked example from the page

The highlighted elements are kinzi, base, medial Ra, pre-base vowels and
anusvara.

Input:

```
U+1004 U+103A U+1039 U+1000 U+1039 U+1000 U+103B U+103C U+103D U+1031 U+1031 U+102D U+102F U+1036 U+102C U+1036
```

Reordered:

```
U+1031 U+1031 U+103C U+1000 U+1004 U+103A U+1039 U+1039 U+1000 U+103B U+103D U+102D U+1036 U+102F U+102C U+1036
```

What moved:

- U+1031 U+1031 (two pre-base vowels) went to the front as one block (rule 3).
- U+103C (medial Ra) went in front of the base U+1000 (rule 2).
- The kinzi U+1004 U+103A U+1039 went to right after the base U+1000, ahead
  of the stacked U+1039 U+1000 (rule 1).
- The first U+1036 (anusvara after the below-base vowel U+102F) went in front
  of U+102F (rule 4). The second U+1036 follows the post-base vowel U+102C and
  stays where it is.

Font consequences:

- GSUB and GPOS lookups must be written against the reordered glyph sequence.
- Fonts must not try to do this reordering with substitutions; covering the
  general case would need an enormous set of many-to-many glyph substitutions.

## 7. GSUB stage

Features in order (a given language need not use all of them):

| Step | Group | Feature | Role |
|---|---|---|---|
| 1 | Localized forms | locl | Language-specific forms for the current language, done before anything else. |
| 2 | Basic shaping forms | rphf | Kinzi glyph forms. |
| 3 | Basic shaping forms | pref | Pre-base glyph forms. |
| 4 | Basic shaping forms | blwf | Below-base glyph forms. |
| 5 | Basic shaping forms | pstf | Post-base forms. |
| 6 | Presentation forms | pres | Pre-base presentation substitutions. |
| 7 | Presentation forms | abvs | Above-base presentation substitutions. |
| 8 | Presentation forms | blws | Below-base presentation substitutions. |
| 9 | Presentation forms | psts | Post-base presentation substitutions. |

Steps 6 to 9 run together over the cluster (section 2), so within them the
font's lookup order is what counts.

## 8. GPOS stage

All positioning features are applied at the same time over the cluster. Font
developers must take the reordering into account when writing GPOS lookups.

| Step | Group | Feature | Role |
|---|---|---|---|
| 1 | Kerning | kern | Pair kerning for typographic quality; some applications switch it off. |
| 2 | Kerning | dist | Any distance adjustments that are needed. |
| 3 | Mark placement | mark | Places diacritic glyphs relative to the base glyph. |
| 4 | Mark placement | mkmk | Places diacritic glyphs relative to one another. |

## 9. Feature order table

The fixed order used for Myanmar features, as given on the page:

| Group | Feature | Feature function | Layout operation | Required |
|---|---|---|---|---|
| Localized forms | locl | (none given) | GSUB | |
| Basic shaping forms | rphf | Kinzi substitution | GSUB | X |
| Basic shaping forms | pref | Pre-base substitution | GSUB | X |
| Basic shaping forms | blwf | Below-base substitution | GSUB | X |
| Basic shaping forms | pstf | Post-base form substitution | GSUB | X |
| Presentation forms | pres | Pre-base substitution | GSUB | |
| Presentation forms | abvs | Above-base substitution | GSUB | |
| Presentation forms | blws | Below-base substitution | GSUB | |
| Presentation forms | psts | Post-base substitution | GSUB | |
| Kerning | kern | Pair kerning | GPOS | |
| Kerning | dist | Distance adjustments | GPOS | X |
| Mark placement | mark | Mark positioning | GPOS | |
| Mark placement | mkmk | Mark to mark positioning | GPOS | |

GSUB = glyph substitution, GPOS = glyph positioning. The table leaves mark and
mkmk unmarked in the Required column, but the feature notes (section 10) call
both of them required and say the engine always applies them. The order of
lookups inside each feature is also significant.

## 10. Feature notes

The page's examples come from the Myanmar Text font (mmrtext.ttf). Every
feature sees the glyph sequence after reordering, and its input can already
include the output of earlier features.

- **locl**: works with language system tags to pick alternate glyphs for
  language-specific conventions (the page's example swaps in Sgaw Karen
  variants). It belongs under specific language system tags only, never under
  the default language system.
- **rphf**: forms kinzi. Kinzi has already been moved after a valid base
  (section 6); if there is no valid base, the engine inserts a dotted circle to
  serve as one. The font should replace the kinzi sequence (consonant + asat +
  virama) with a mark glyph, so that after reordering it can be positioned
  over the base glyph that now precedes it. Kinzi substitution has to be done
  in rphf.
- **pref**: pre-base forms. Example: choosing a medial Ra (U+103C) glyph of
  suitable width, with the following consonant as context.
- **blwf**: below-base forms. Example: sequences of a virama and a consonant
  become that consonant's stacked (below-base) glyph.
- **pstf**: post-base forms. Example: vowel sign tall AA (U+102B) followed by
  asat (U+103A) becomes one ligature glyph.
- **pres**: presentation forms involving pre-base elements. Example: clipped
  variants of medial Ra.
- **abvs**: presentation forms for above-base elements. Example: ligatures of
  several above-base marks.
- **blws**: presentation forms for below-base elements. Example: spacing
  variants of below-base vowel marks.
- **psts**: presentation forms for post-base elements. Example: a contextual
  alternate of medial Ya (U+103B).
- **kern**: optional pair adjustment between glyphs; Myanmar Text does not use
  it.
- **dist**: required. OTLS sets the advance width of mark glyphs to zero, so a
  mark that needs width must get it back here (Myanmar Text adds advance width
  back to spacing marks such as medial Ra); dist also carries any other
  required spacing adjustment.
- **mark**: positions marks on a base glyph, above and below. Required; the
  engine always applies it. A font may also use abvm or blwm, but those are not
  required features.
- **mkmk**: positions marks relative to one another (sequences of marks).
  Required; the engine always applies it.

## 11. Invalid combining marks

- A combining mark or sign that does not belong to a valid base is invalid.
- Engines may handle such marks in different ways. One approach is to make the
  stray mark its own cluster and draw it on a default base such as a dotted
  circle (U+25CC), as in Unicode's fallback rendering guidance. Engines also
  differ on what counts as valid; for example, some limit a cluster to one
  above-base vowel and others do not.
- This shaper inserts U+25CC during analysis wherever combining marks lack a
  valid base (section 2), and also supplies a dotted-circle base for a kinzi
  that has no valid base (section 10, rphf).
- Fonts should contain a U+25CC glyph; otherwise engines that rely on it show
  the invalid sign on the missing-glyph (white box) glyph.

## 12. Recommended glyphs

Code points that every Myanmar font should include:

| Code point | Description |
|---|---|
| U+200B | Zero Width Space |
| U+200C | Zero Width Non-Joiner |
| U+200D | Zero Width Joiner |
| U+25CC | Dotted Circle |
| U+002D | Hyphen-minus |
| U+00A0 | No-break space |
| U+00D7 | Multiplication sign |
| U+2012 | Figure dash |
| U+2013 | En dash |
| U+2014 | Em dash |
| U+2015 | Horizontal bar |
| U+2022 | Bullet |
| U+25FB | White medium square |
| U+25FC | Black medium square |
| U+25FD | White medium small square |
| U+25FE | Black medium small square |

## 13. Writing system and language tags

- The script tag for this shaper is 'mym2'. Do not use 'mymr': it has only
  limited support.
- Features are looked up by script and language system. Language systems
  capture typographic conventions of individual languages (the script serves
  Burmese, Pali, Sanskrit and others). Not every application supports language
  tags.
- Always include 'dflt': it carries the basic script behaviour and is the
  fallback when no language system matches or the application does not support
  the language. Fonts lacking it may fail in some applications.

| Script tag | Script | Language system tag | Language |
|---|---|---|---|
| 'mym2' | Myanmar | 'dflt' | default script handling |
| | | ARK | Rakhine-Marma (Arakanese) |
| | | BRM | Burmese |
| | | MON | Mon |
| | | KRN | Karen |
| | | QIN | Chin |
| | | SHN | Shan |
| | | PLG | Palaung |
| | | SAN | Sanskrit |
| | | PAL | Pali |

Tags are case-sensitive and four characters long: script tags in lower case,
language tags in upper case. The three-letter language tags above therefore
carry a trailing space in a font, for example 'BRM '.
