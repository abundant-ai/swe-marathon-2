# Universal Shaping Engine (digest)
Source: Creating and supporting OpenType fonts for the Universal Shaping Engine - Typography | Microsoft Learn, https://learn.microsoft.com/en-us/typography/script-development/use
These notes restate the source's structures and rules; where they differ, the source governs.

Scope: the page (revision dated October 2026) covers the complex scripts of
Unicode 18.0 that have no dedicated shaping engine of their own. The scripts are
listed in section 11.

## Contents

1. Processing stages
2. Character classification
3. Split vowel handling
4. Cluster validation
5. OpenType feature application I: basic cluster formation (GSUB)
6. Glyph reordering
7. OpenType feature application II
8. Feature groups at a glance
9. Invalid combining marks
10. Recommended glyphs
11. Writing system and language tags

## 1. Processing stages

USE processes text in this order:

1. Character classification
   1. Overrides to Unicode categories
2. Split vowel handling
3. Cluster validation
4. OpenType feature application I
   1. Basic cluster formation, GSUB
5. Glyph reordering
6. OpenType feature application II
   1. Topographical features, GSUB
   2. Standard typographical features, GSUB
   3. Custom substitution features requested by the application, GSUB
   4. Positional features, GPOS

## 2. Character classification

Itemization hands USE runs that hold one script each, possibly mixed with
SCRIPT_COMMON characters. USE splits a run into clusters and gives each
character a USE class, plus a positional subclass for some classes. The classes
drive cluster parsing, special handling and reordering. They are computed from
Unicode character data through a fixed mapping, shown below.

### 2.1 Source properties

| Abbreviation | Property |
|---|---|
| AJT | Unicode Joining_Type ("Arabic Joining Type") |
| UISC | Unicode Indic_Syllabic_Category |
| UGC | Unicode General_Category |
| UIPC | Unicode Indic_Positional_Category; called Indic_Matra_Category before Unicode 8.0 |
| ESC | USE Extended Syllabic Category (a USE-defined extension) |

Unicode's UISC and UIPC data cover Indic scripts only. For other complex
scripts, USE ships the values it needs in supplementary data files in its
GitHub archive (microsoft/font-tools, folder USE). Hieroglyphic scripts need
syllabic categories that UISC does not have; these are the ESC values used
below, defined in the IndicSyllabicCategory-Additional.txt data file.

### 2.2 Classes

In the Derivation column, a semicolon separates alternative conditions (any
one of them assigns the class) and "&" joins conditions that must all hold.

| Sigla | USE class | Derivation |
|---|---|---|
| B | BASE | AJT = C, D, L, or R; UISC = Number; UISC = Avagraha & UGC = Lo; UISC = Bindu & UGC = Lo; UISC = Consonant; UISC = Consonant_Final & UGC = Lo; UISC = Consonant_Head_Letter; UISC = Consonant_Medial & UGC = Lo; UISC = Consonant_Subjoined & UGC = Lo; UISC = Tone_Letter; UISC = Vowel & UGC = Lo; UISC = Vowel_Independent; UISC = Vowel_Dependent & UGC = Lo |
| CGJ | CGJ | U+034F |
| CM | CONS_MOD | UISC = Nukta; UISC = Gemination_Mark; UISC = Consonant_Killer; UISC = Symbol_Modifier |
| CS | CONS_WITH_STACKER | UISC = Consonant_With_Stacker |
| F | CONS_FINAL | UISC = Consonant_Final & UGC != Lo; UISC = Consonant_Succeeding_Repha |
| FM | CONS_FINAL_MOD | UISC = Syllable_Modifier |
| G | HIEROGLYPH | ESC = Hieroglyph |
| GB | BASE_OTHER | UISC = Consonant_Placeholder; U+2015, U+2022, U+25FB..U+25FE |
| H | HALANT | UISC = Virama; UISC = Invisible_Stacker |
| HM | HIEROGLYPH_MOD | ESC = Hieroglyph_Modifier |
| HN | HALANT_NUM | UISC = Number_Joiner |
| HR | HIEROGLYPH_MIRROR | ESC = Hieroglyph_Mirror |
| IND | BASE_IND | UISC = Consonant_Dead; UISC = Modifying_Letter; UISC = Other; UGC = Po (Punctuation signs), except U+104E, U+2022 |
| J | HIEROGLYPH_JOINER | ESC = Hieroglyph_Joiner |
| M | CONS_MED | UISC = Consonant_Medial & UGC != Lo |
| N | BASE_NUM | UISC = Brahmi_Joining_Number |
| O | OTHER | Any other SCRIPT_COMMON characters; White space characters, UGC=Zs |
| R | REPHA | UISC = Consonant_Preceding_Repha; UISC = Consonant_Prefixed |
| RK | Reordering Killer | UISC = Reordering_Killer |
| Rsv | Reserved characters | Any character not currently assigned or otherwise reserved in Unicode |
| S | SYM | UGC = So except U+25CC; UGC = Sc |
| SB | HIEROGLYPH_SEGMENT_BEGIN | ESC = Hieroglyph_Mark_Begin; ESC = Hieroglyph_Segment_Begin |
| SE | HIEROGLYPH_SEGMENT_END | ESC = Hieroglyph_Mark_End; ESC = Hieroglyph_Segment_End |
| SUB | CONS_SUB | UISC = Consonant_Subjoined & UGC != Lo |
| V | VOWEL | UISC = Vowel & UGC != Lo; UISC = Vowel_Dependent & UGC != Lo; UISC = Pure_Killer |
| VM | VOWEL_MOD | UISC = Bindu & UGC != Lo; UISC = Tone_Mark; UISC = Cantillation_Mark; UISC = Register_Shifter; UISC = Visarga |
| VS | VARIATION_SELECTOR | U+FE00..U+FE0F |
| WJ | Word joiner | U+2060 |
| ZWJ | Zero width joiner | UISC = Joiner |
| ZWNJ | Zero width non-joiner | UISC = Non_Joiner |

Observations that follow from the table:

- Several UISC values are split by General_Category: a character with UGC =
  Lo (other letter) becomes a base, anything else a dependent class. Bindu -> B or VM;
  Consonant_Final -> B or F; Consonant_Medial -> B or M; Consonant_Subjoined ->
  B or SUB; Vowel and Vowel_Dependent -> B or V.
- U+25CC DOTTED CIRCLE is excluded from S; the page treats an explicit U+25CC
  as a generic base (GB), see section 4.3.
- U+2022 is excluded from IND (punctuation) and listed under GB instead;
  U+104E is also excluded from IND.

### 2.3 Positional subclasses

Classes whose members can sit in different positions are refined by UIPC. Each
subclass belongs to the class its name starts with (CM, F, M, V or VM).

| Sigla | USE subclass | Derivation |
|---|---|---|
| CMAbv | CONS_MOD_ABOVE | UIPC = Top |
| CMBlw | CONS_MOD_BELOW | UIPC = Bottom |
| FAbv | CONS_FINAL_ABOVE | UIPC = Top |
| FBlw | CONS_FINAL_BELOW | UIPC = Bottom |
| FPst | CONS_FINAL_POST | UIPC = Right |
| MAbv | CONS_MED_ABOVE | UIPC = Top |
| MBlw | CONS_MED_BELOW | UIPC = Bottom |
| MPre | CONS_MED_PRE | UIPC = Left |
| MPst | CONS_MED_POST | UIPC = Right |
| VAbv | VOWEL_ABOVE | UIPC = Top |
| (blank, under VAbv) | VOWEL_ABOVE_BELOW | UIPC = Top_And_Bottom |
| (blank, under VAbv) | VOWEL_ABOVE_BELOW_POST | UIPC = Top_And_Bottom_And_Right |
| (blank, under VAbv) | VOWEL_ABOVE_POST | UIPC = Top_And_Right |
| VBlw | VOWEL_BELOW | UIPC = Bottom; UIPC = Overstruck |
| (blank, under VBlw) | VOWEL_BELOW_POST | UIPC = Bottom_And_Right |
| VPre | VOWEL_PRE | UIPC = Left |
| (blank, under VPre) | VOWEL_PRE_ABOVE | UIPC = Top_And_Left |
| (blank, under VPre) | VOWEL_PRE_ABOVE_POST | UIPC = Top_And_Left_And_Right |
| (blank, under VPre) | VOWEL_PRE_POST | UIPC = Left_And_Right |
| VPst | VOWEL_POST | UIPC = Right |
| VMAbv | VOWEL_MOD_ABOVE | UIPC = Top |
| VMBlw | VOWEL_MOD_BELOW | UIPC = Bottom; UIPC = Overstruck |
| VMPre | VOWEL_MOD_PRE | UIPC = Left |
| VMPst | VOWEL_MOD_POST | UIPC = Right |

The rows with an empty Sigla cell are the multi-part (split) vowel subclasses.
On the page each sits directly below the sigla named in parentheses here, and
the cluster formulas never refer to them by name. Split vowels are decomposed
before validation (section 3), so the formulas only use the four cardinal
vowel positions VPre, VAbv, VBlw and VPst.

### 2.4 Overrides to Unicode categories

Where a Unicode value does not match what shaping needs, or Unicode gives no
value, USE overrides the category. The page does not list the overrides; they
are published as data files:

- IndicSyllabicCategory-Additional.txt
- IndicPositionalCategory-Additional.txt

## 3. Split vowel handling

USE decomposes split vowels whose UISC is Vowel_Dependent by the character
decomposition mappings of UnicodeData.txt. The page's example records:

```
0DCF;SINHALA VOWEL SIGN AELA-PILLA;Mc;0;L;;;;;N;;;;;
0DD9;SINHALA VOWEL SIGN KOMBUVA;Mc;0;L;;;;;N;;;;;
0DDC;SINHALA VOWEL SIGN KOMBUVA HAA AELA-PILLA;Mc;0;L;0DD9 0DCF;;;;N;;;;;
```

So U+0DDC is handled as U+0DD9 (a pre-base piece) followed by U+0DCF (a
post-base piece).

Rules:

1. Decompose recursively, so that every split vowel is fully broken down
   before shaping starts.
2. If UnicodeData.txt has no decomposition for a split vowel, any
   decomposition it needs is the font's job, done in GSUB.
3. Clusters are validated on the decomposed sequence. The cluster formulas
   know only the cardinal positions Pre, Above, Below and Post, and each piece
   fills exactly one of them, so a split vowel must fit the formula as its
   sequence of pieces. This can be stricter than the rule for a vowel with a
   single position.
4. If a character of a split-vowel class that includes a Pre part has no
   canonical decomposition, the font developer must define the decomposition.
   The logically first glyph of that decomposition is then taken as the VPre;
   the glyphs after it do not reorder. No such character exists in the scripts
   currently supported.
5. Fonts must contain glyphs for every piece that the required decompositions
   produce.

## 4. Cluster validation

Validation groups characters into clusters according to class and subclass.
Limiting which sequences may form a cluster keeps one visual cluster from
having several different encodings, which would hurt data interchange
stability and security. The USE model is deliberately generic and permissive:
it accepts whatever is graphically coherent for a script and does not enforce
spelling or linguistic rules; those belong in other layers, such as spell
checkers.

### 4.1 Notation

The category abbreviations are the sigla of section 2. The extra symbols are:

| Notation | Meaning |
|---|---|
| X* | zero or more X |
| X+ | one or more X |
| <X \| Y> | X or Y |
| [X] | X is optional: zero or one occurrence |
| ( ... ) | grouping |
| # | a boundary occurs here |
| multiplication sign | no boundary allowed at this position |
| division sign | a boundary is allowed at this position |
| ^ | except |

### 4.2 Cluster types

The page introduces the list as "four options" but defines seven cluster
types.

#### 1. Independent cluster

```
< IND | O | Rsv | WJ > [VS]
```

- Normally a single character. The only class that can join it is a variation
  selector.
- BASE_IND, OTHER, reserved characters and WJ each form a cluster of exactly
  one code point.
- A variation selector that does not directly follow a valid base (IND, O,
  Rsv, WJ, B, GB, N or S) becomes an independent cluster of its own.

#### 2. Standard cluster

```
[< R | CS >] < B | GB > [VS] (CMAbv)* (CMBlw)* (< H B [VS] | SUB > (CMAbv)* (CMBlw)*)*
    [MPre] [MAbv] [MBlw] [MPst]
    (VPre)* (VAbv)* (VBlw)* (VPst)*
    (VMPre)* (VMAbv)* (VMBlw)* (VMPst)*
    (FAbv)* (FBlw)* (FPst)* [FM]
```

- The only compulsory element is a BASE or BASE_OTHER.
- It may be preceded by a REPHA or a CONS_WITH_STACKER.
- The base may be followed at once by a variation selector, then any number of
  consonant modifiers, all CMAbv before any CMBlw.
- Then any number of further base units, each either HALANT + BASE (optionally
  with a variation selector) or one CONS_SUB, each followed by its own optional
  CMAbv and CMBlw modifiers.
- Then at most one medial consonant per position, in the order Pre, Above,
  Below, Post.
- Then any number of vowels per position, in the order Pre, Above, Below,
  Post.
- Then any number of vowel modifiers per position, in the same order.
- Then any number of final consonants per position, in the order Above,
  Below, Post.
- Last, an optional CONS_FINAL_MOD.

#### 3. Virama terminated cluster

```
[< R | CS >] < B | GB > [VS] (CMAbv)* (CMBlw)* (< H B [VS] | SUB > (CMAbv)* (CMBlw)*)* < H | RK >
```

- Same opening as the standard cluster, but it ends with a HALANT or a
  Reordering Killer (RK).
- A HALANT or RK after a BASE or BASE_OTHER makes up a cluster. If what
  follows the virama or RK is not a base, the cluster breaks right after the
  virama or RK.
- HALANT + BASE units (with optional variation selector or consonant
  modifiers) may repeat; a CONS_SUB counts the same as HALANT + BASE.

#### 4. Number-joiner terminated cluster

```
N [VS] (HN N [VS])* HN
```

- A HALANT_NUM after a BASE_NUM makes up a cluster; if the character after the
  HALANT_NUM is not a BASE_NUM, the cluster breaks after the HALANT_NUM.
- Each BASE_NUM may take a variation selector directly after it, and HALANT_NUM
  + BASE_NUM units may repeat.

#### 5. Numeral cluster

```
N [VS] (HN N [VS])*
```

- BASE_NUM characters chained by HALANT_NUM, as many times as needed; any
  BASE_NUM may take a variation selector.

#### 6. Symbol cluster

```
< S | GB > [VS] (CMAbv)* (CMBlw)*
```

- A symbol (the formula also allows a BASE_OTHER) with an optional variation
  selector, then any number of CONS_MOD_ABOVE, then any number of
  CONS_MOD_BELOW.

#### 7. Hieroglyph cluster

```
SB* G [VS] [HR] [HM] SE* ( J SB* G [VS] [HR] [HM] SE* )*
```

- The core unit is one HIEROGLYPH, optionally followed by, in this order and
  at most once each: VARIATION_SELECTOR (picks a specific graphic variant),
  HIEROGLYPH_MIRROR (picks a horizontally mirrored alternate),
  HIEROGLYPH_MODIFIER (varies the sign graphically).
- Any number of HIEROGLYPH_SEGMENT_BEGIN may precede the hieroglyph and any
  number of HIEROGLYPH_SEGMENT_END may follow it.
- Units are chained with HIEROGLYPH_JOINER.
- Segments can nest; three levels of nesting are attested, so two SB, or two
  SE, can occur back to back. An implementation that bounds these repeats
  must allow at least SB{0,2} and SE{0,2}.
- So that text can be entered one character at a time, implementations should
  also accept a hieroglyph cluster that ends with a joiner, which keeps the
  cluster valid until the next hieroglyph is typed.
- The model does not check whether nesting is minimal. Unnecessary nesting can
  defeat text matching in collation; flagging it is left to a higher level,
  such as orthography checking.

### 4.3 Further cluster rules

- **Independent vowel plus dependent vowel**: the Unicode core specification
  forbids spelling certain independent vowels as another base plus a dependent
  vowel (the page cites TUS Table 13-0 as an example). These bans concern
  specific pairs, not whole classes, so USE keeps a list of the prohibited
  sequences that the cluster model would otherwise accept, in the data file
  IndicShapingInvalidCluster.txt.
- **CGJ** (U+034F COMBINING GRAPHEME JOINER): left out of the formulas for
  simplicity. It may appear anywhere inside a cluster and has no effect. Its
  role is to block normalization from reordering a mark sequence; its handling
  would need revisiting if USE ever adds normalization.
- **ZWNJ** (zero width non-joiner, prevents two characters from fusing): it
  attaches to the cluster before it. A cluster break follows it unless the
  next character is a mark (General_Category Mn or Mc). It does not reset the
  cluster model.
- **ZWJ** (zero width joiner, makes two characters fuse): it attaches to the
  cluster before it and links that cluster to the next character, except when
  the next character is another ZWJ; then the cluster breaks between the two
  ZWJs. It does not reset the cluster model.
- **Standalone characters**: BASE_IND characters stand alone and never form a
  cluster with what follows. A VS or WJ found outside any cluster (at the
  start of a run, or after a standalone character) is standalone as well.
- **Defective clusters**: if a cluster would begin with a character whose
  General_Category is Mc or Mn, USE inserts a dotted circle (U+25CC) to show
  that the cluster is broken. A defective cluster does not grow into an
  extended cluster; a run of marks with no valid base becomes one separate
  cluster per mark. An explicit U+25CC in the text, by contrast, counts as a
  generic base (GB, BASE_OTHER), so it can head a full cluster.
- **Cluster length**: about 31 characters is a practical upper limit. Past
  that length the engine may cut the cluster and start another one. During
  GSUB a cluster may grow far beyond 31 glyphs.

## 5. OpenType feature application I: basic cluster formation (GSUB)

Three groups run in this order, each one cluster at a time. Descriptions marked
"(general)" give the usual meaning of a tag that the page lists by name only.

### 5.1 Default glyph pre-processing group

The features are applied together, cluster by cluster. Their lookups fire in
the font's lookup order and may be interleaved across features. Recommended
feature order:

| Feature | Name | Purpose |
|---|---|---|
| locl | Localized forms | Starting point for language-specific forms; USE uses whatever language system tag the edit control supplies. |
| ccmp | Glyph composition/decomposition | (general) Composes or splits glyphs before the rest of shaping. |
| nukt | Nukta forms | Substitutions involving a combining nukta, a consonant modifier that usually signals a different sound, often one borrowed from another language. |
| akhn | Akhands | Traditional ligatures formed from character sequences. |

### 5.2 Reordering group

These two features are applied separately, rphf first and then pref. Glyphs
they produce are moved later, in the reordering stage (section 6); nothing is
moved until all basic-formation features have run.

| Feature | Name | Purpose and scope |
|---|---|---|
| rphf | Reph form | Classically the combining form of a pre-consonantal r, which moves after the following base; may be used for any component that reorders the way reph does. Only the first three glyphs of a cluster are in scope. |
| pref | Pre-base forms | Marks a component that follows the base but must move like a pre-base medial consonant. Applied to the whole cluster. |

### 5.3 Orthographic unit shaping group

Applied together, cluster by cluster, like section 5.1; the font's lookup order
decides. Recommended (not required) order:

| Feature | Name | Purpose |
|---|---|---|
| rkrf | Rakar forms | (general) Ligatures of a consonant with a following ra (rakar). |
| abvf | Above-base forms | Substitutions for above-base components. |
| blwf | Below-base forms | Substitutions for below-base components. |
| half | Half forms | Half forms, in scripts that have them. |
| pstf | Post-base forms | Substitutions for post-base components. |
| vatu | Vattu variants | Ligatures that include a below-base form. |
| cjct | Conjunct forms | Completes basic conjuncts that no other feature formed. |

## 6. Glyph reordering

### 6.1 Principles

- Reordering, like mark anchoring, is relative to the base consonant.
- USE reorders once, late: after basic cluster formation (section 5) and
  before the topographical features (section 7.1). Any reordering depends on
  which glyph ends up as the base, and basic cluster formation can change it.
- USE neither checks nor looks ahead into a font's lookups, so lookups of the
  basic features must be written for logical (not yet reordered) glyph order.
- There are two kinds of reordering glyph: feature-based (rphf, pref) and
  property-based (R, VPre, VMPre).
- They are handled in logical order: rphf, then pref, then VPre, then VMPre.

Effect on a plain cluster (numbers give the processing order):

| | Glyph order |
|---|---|
| Before reordering | rphf(1), Base, pref(2), VPre(3), VMPre(4) |
| After reordering | VMPre(4), VPre(3), pref(2), Base, rphf(1) |

### 6.2 Explicit virama

If the cluster still contains an explicit virama, that is one that basic
cluster formation did not substitute away, no reordering glyph moves across
it:

| | Glyph order |
|---|---|
| Before reordering | rphf(1), Base A, Halant, Base B, pref(2), VPre(3), VMPre(4) |
| After reordering | Base A, rphf(1), Halant, VMPre(4), VPre(3), pref(2), Base B |

The reph stops after Base A, and the pre-base glyphs collect in front of Base
B, the first spacing glyph after the virama. A font that does not want the
virama to block reordering can replace it with an alternate glyph during basic
cluster formation; USE then treats the cluster as continuous, without an
explicit virama.

### 6.3 Feature-based reordering

| Sigla | Name | Rule |
|---|---|---|
| rphf | Reph form | Many abugidas draw a pre-consonantal r as a sign over the consonant that follows it; this sign is reph. In OpenType it is normally a mark glyph, so it has to come after its base. Any context that yields the reph glyph must use 'rphf'. The glyph output by rphf moves to after the following full base, but never past an explicit virama. An rphf lookup should output at most one glyph per cluster. |
| pref | Pre-base form | Some scripts (Javanese, for example) move a medial consonant to the front of the cluster depending on context. The font encodes that context and uses 'pref' to identify the glyph or glyphs to move. One or more glyphs may be replaced by a single feature glyph, which moves to before the first spacing glyph of the cluster or, when an explicit virama is present, before the first spacing glyph that comes after it. Only one glyph per cluster is moved. |

Pre-base medial consonants (CONS_MED_PRE, MPre) are not moved by USE on its
own: the font applies 'pref' to such a glyph to have it moved, and only one
glyph per cluster can be moved this way.

### 6.4 Property-based reordering

| Sigla | Name | Rule |
|---|---|---|
| R | REPHA | A pre-base REPHA is moved after the following full base as if 'rphf' had been applied to it; the font does not need to apply 'rphf' itself. |
| VPre | VOWEL_PRE | Pre-base vowels, including pre-base pieces of split vowels, move before the base glyph and also before any glyph moved by 'pref'. |
| VMPre | VOWEL_MOD_PRE | Pre-base vowel modifiers move before the base glyph, and also before any pre-base vowel and any glyph moved by 'pref'. |

- The page also states that USE does not currently support the REPHA
  category.
- VOWEL_PRE_ABOVE, VOWEL_PRE_ABOVE_POST and VOWEL_PRE_POST each have a
  pre-base part. Because decomposition comes before reordering, only one glyph
  from such a vowel ends up with class VOWEL_PRE, so VPre is the only vowel
  class that needs handling at this point.

## 7. OpenType feature application II

### 7.1 Topographical features (GSUB)

For scripts like Arabic, whose glyphs change shape with their position in a
word, USE applies four positional features:

| Feature | Name |
|---|---|
| isol | Isolated forms |
| init | Initial forms |
| medi | Medial forms |
| fina | Final forms |

How a position is decided:

- They are required features and are applied per cluster: all glyphs of a
  cluster get the same one of the four.
- The form depends on where the cluster stands relative to non-joining
  boundaries and white-space boundaries.
- A non-joining boundary separates two glyphs of a joining script if either
  character (or both) is non-joining on the side that faces the other.
- ZWJ can be used to force a join and ZWNJ to block one.
- Joining properties are the Unicode Joining_Type values from
  ArabicShaping.txt.
- USE does not implement topographical features for non-joining scripts; the
  page says further specification is needed.

Which feature each position receives:

| Boundary before the cluster | Boundary after the cluster | Feature |
|---|---|---|
| yes | yes | isol |
| yes | no | init |
| no | no | medi |
| no | yes | fina |

The page gives the boundary rule but no table; the rows above apply the
standard meaning of the four tags to a cluster lying between boundaries,
reading the start and end of the run as boundaries.

### 7.2 Standard typographic presentation (GSUB)

The remaining required substitution features are applied all together to the
whole run, in whatever lookup order the font specifies. The page lists them by
name only; purposes marked "(general)" are the usual meanings of the tags.

| Feature | Name | Purpose |
|---|---|---|
| abvs | Above-base substitutions | (general) Presentation adjustments for above-base glyphs. |
| blws | Below-base substitutions | (general) Presentation adjustments for below-base glyphs. |
| calt | Contextual alternates | (general) Alternates chosen by context. |
| clig | Contextual ligature | (general) Ligatures that form only in a given context. |
| haln | Virama forms | (general) Forms for clusters that end in a visible virama. |
| liga | Standard ligatures | (general) Ordinary ligatures; used only for horizontal layout. |
| pres | Pre-base substitutions | (general) Presentation adjustments for pre-base glyphs. |
| psts | Post-base substitutions | (general) Presentation adjustments for post-base glyphs. |
| rclt | Required contextual forms | (general) Contextual alternates that must always apply. |
| rlig | Required ligatures | (general) Ligatures that must always form; used only for horizontal layout. |
| vert | Vertical writing | (general) Vertical glyph variants; supplied by the edit control. |
| vrt2 | Vertical alternates and rotation | (general) Vertical variants plus rotation; supplied by the edit control. |

When text is laid out vertically, the edit control turns on the vertical
features as a custom feature. Apply only one of vert and vrt2, never both.

### 7.3 Custom substitution features requested by the application (GSUB)

This step appears in the stage list and as a heading; the page names no
features for it.

### 7.4 Positional features (GPOS)

All of these required features run at once over the whole run. The order
below is recommended; the font defines the actual lookup order.

| Feature | Name | Purpose |
|---|---|---|
| curs | Cursive positioning | Positions bases relative to other bases. |
| dist | Distances | Required width adjustments. |
| kern | Kerning | Optimal letter spacing; edit controls can disable it. |
| mark | Mark positioning | Positions marks relative to a base. |
| abvm | Above-base mark positioning | Functionally the same as mark; lets a font keep above-mark lookups apart from below-mark lookups. |
| blwm | Below-base mark positioning | Functionally the same as mark; the below-mark counterpart. |
| mkmk | Mark to Mark Positioning | Positions marks relative to marks before them. |

### 7.5 Bases classed as marks, restored with dist

- To keep a base glyph out of contextual lookups, a font can class it as a mark
  in GDEF, since lookups can include or skip marks selectively.
- OpenType processing removes a mark's advance width (it is not clear where a
  non-spacing mark's width should go), so a base handled this way must get its
  width back through 'dist'.
- Typical case: Javanese pre-base vowels. They stay in logical position until
  reordering, where they can interrupt other contextual substitutions; classed
  as marks, they are skipped, which reduces the number of contextual rules, and
  'dist' restores their advance.
- The page's sample, written in VOLT syntax, is a single-adjustment positioning
  lookup named j.dist_preVowel (processing bases and all marks, left to right)
  that adds 1433 units of advance width to the glyphs jSignE and jSignAi.

## 8. Feature groups at a glance

| Order | Group | Features | Unit | How applied |
|---|---|---|---|---|
| 1 | Default glyph pre-processing | locl, ccmp, nukt, akhn | cluster | together; font lookup order |
| 2 | Reordering group | rphf, pref | cluster (rphf: first three glyphs) | one feature at a time, rphf then pref |
| 3 | Orthographic unit shaping | rkrf, abvf, blwf, half, pstf, vatu, cjct | cluster | together; font lookup order |
| 4 | Glyph reordering (no features) | rphf output, pref output, VPre, VMPre (and R) | cluster | engine, in that order |
| 5 | Topographical | isol, init, medi, fina | cluster | required; one form per cluster |
| 6 | Standard typographic presentation | abvs, blws, calt, clig, haln, liga, pres, psts, rclt, rlig, vert, vrt2 | run | together; font lookup order |
| 7 | Custom substitution features | as requested by the application | (not specified) | (not specified) |
| 8 | Positional (GPOS) | curs, dist, kern, mark, abvm, blwm, mkmk | run | together; font lookup order |

## 9. Invalid combining marks

- A combining mark or sign that does not belong to a valid base is invalid.
  USE makes such a mark a cluster of its own and displays it on a dotted circle
  (U+25CC); see "Defective clusters" in section 4.3.
- To put several marks on one dotted circle, insert an explicit U+25CC in the
  text and follow it with the marks; normal clustering then applies.
- Fonts used with USE should include a glyph for U+25CC; otherwise engines that
  place invalid marks on a dotted circle show them on the missing-glyph (white
  box) glyph.

## 10. Recommended glyphs

| Code point | Description |
|---|---|
| U+200B | Zero Width Space |
| U+200C | Zero Width Non-Joiner |
| U+200D | Zero Width Joiner |
| U+25CC | Dotted Circle |
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

## 11. Writing system and language tags

- Features are enabled per script tag and language system tag. Not every
  application supports language-specific tags.
- Always include 'dflt'. It carries the basic script behaviour and is the
  fallback when no language system matches or the application does not
  support the language; fonts lacking it may fail in some applications.
- The page lists no language system tags for USE scripts; font developers
  choose those suited to each script.
- Script tags are case-sensitive, lower case and four characters long.
- The list grows as Unicode adds complex scripts and USE is extended.

Script tags handled by USE:

| Script | Script tag |
|---|---|
| ADLaM | adlm |
| Ahom | ahom |
| Balinese | bali |
| Batak | batk |
| Beria Erfe | berf |
| Bhaiksuki | bhks |
| Brahmi | brah |
| Buginese | bugi |
| Buhid | buhd |
| Chakma | cakm |
| Cham | cham |
| Chorasmian | chrs |
| Cypro Minoan | cpmn |
| Dives Akuru | diak |
| Dogra | dogr |
| Duployan | dupl |
| Egyptian Hieroglyphs | egyp |
| Elymaic | elym |
| Garay | gara |
| Grantha | gran |
| Gunjala Gondi | gong |
| Gurung Khema | gukh |
| Hanifi Rohingya | rohg |
| Hanunoo | hano |
| Javanese | java |
| Jurchen | jurc |
| Kaithi | kthi |
| Kawi | kawi |
| Kayah Li | kali |
| Kharoshthi | khar |
| Khitan Small Script | kits |
| Khojki | khoj |
| Khudawadi | sind |
| Kirat Rai | krai |
| Lepcha | lepc |
| Limbu | limb |
| Mahajani | mahj |
| Makasar | maka |
| Mandaic | mand |
| Manichaean | mani |
| Marchen | marc |
| Masaram Gondi | gonm |
| Medefaidrin | medf |
| Meitei Mayek | mtei |
| Miao | plrd |
| Modi | modi |
| Mongolian | mong |
| Multani | mult |
| Nag Mundari | nagm |
| Nandinagari | nand |
| Newa | newa |
| N'Ko | nko |
| Nyiakeng Puachue Hmong | hmnp |
| Old Sogdian | sogo |
| Old Uyghur | ougr |
| Ol Onal | onao |
| Pahawh Hmong | hmng |
| Phags-pa | phag |
| Proto-Cuneiform | pcun |
| Psalter Pahlavi | phlp |
| Rejang | rjng |
| Saurashtra | saur |
| Seal ("Small Seal") | seal |
| Sharada | shrd |
| Siddham | sidd |
| Sidetic | sidt |
| Sinhala | sinh |
| Sogdian | sogd |
| Soyombo | soyo |
| Sunuwar | sunu |
| Sundanese | sund |
| Syloti Nagri | sylo |
| Tagalog | tglg |
| Tagbanwa | tagb |
| Tai Le | tale |
| *Tai Tham | lana |
| Tai Viet | tavt |
| Tai Yo | tayo |
| Takri | takr |
| Tangsa | tnsa |
| Tibetan | tibt |
| Tifinagh | tfng |
| Tirhuta | tirh |
| Todhri | todr |
| Tolong Siki | tols |
| Toto | toto |
| Tulu Tigalari | tutg |
| Vithkuqi | vith |
| Wancho | wcho |
| Yezidi | yezi |
| Zanabazar Square | zanb |

The tag for N'Ko is the three letters nko (a four-character tag padded with a
trailing space, 'nko '). The asterisk on Tai Tham marks limited support: more
encoding work is needed before its text can be fully represented.
