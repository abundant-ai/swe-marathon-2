# Bengali script shaping (digest)
Source: Developing OpenType Fonts for Bengali Script - Typography | Microsoft Learn, https://learn.microsoft.com/en-us/typography/script-development/bengali
These notes restate the source's structures and rules; where they differ, the source governs.

## Conventions

- Code points are written U+XXXX and ranges U+XXXX..U+YYYY. Where the source writes bare hexadecimal (its reorder table has cells such as `09C1-09C4`), only the notation changes here; every value is kept.
- Feature tags are written in single quotes ('rphf'). Script and language system tags are written in double quotes, exactly as registered, including trailing spaces.
- Anything labelled "Reference (Unicode)" is a Unicode Character Database fact added to make a character concrete. The source names that character but does not give the code point or name.
- Anything labelled "Reading note" is an interpretation added to these notes, not a statement of the source.
- The source describes the revised Indic model, whose script tag is "bng2". Its remarks about the earlier model (tag "beng") are collected in section 10.
- The source covers the Bengali script as used for Bengali (Bangla), Assamese and Manipuri.

## 1. Terms

| Term | Meaning for Bengali shaping |
|---|---|
| Syllable (cluster) | The unit that shaping works on. Text stores its characters in phonetic order, which can differ from the visual order. Once shaped, a syllable cannot be split (the caret cannot stop inside it), and no rule in these notes reaches across a syllable boundary. |
| Base glyph | The syllable's single consonant or conjunct drawn in full (nominal) shape. Normally the final consonant is the base, unless the syllable ends with Ra. A syllable without any vowel (typically word-final) takes its final consonant, shown in halant form, as the base. Since the base frequently ends up as a ligature, layout rules refer to the base glyph rather than to one base character. |
| Main consonant | A consonant for which the font supplies no pre-base, half, below-base or post-base form. One syllable may hold several (section 3.5). |
| Halant (virama) | Cancels the inherent vowel of the consonant it follows. Inside a syllable each consonant but the last carries one; the last one does too when the syllable has no vowel. After shaping, halants are often invisible because conjoining forms or conjuncts absorb them. |
| Halant form | The nominal consonant shape with a visible virama. It is used when the syllable has no vowel, and stands in for the half form of a consonant that has no distinct half shape. |
| Half form (pre-base form) | The shape a consonant takes to the left of the base when it does not join a ligature. Half forms come before the consonant(s) making up the base. The source states that most Bengali consonants have a distinctive half shape; a consonant lacking one, and not forming a ligature, is drawn with an explicit virama (its halant form). |
| Reph | The above-base form of Ra, used when Ra opens the syllable without being its base. Ra is the only Bengali consonant with an above-base form; the reorder table lists two reph-forming letters, U+09B0 and U+09F0 (2.3). |
| Below-base form (vattu) | Consonant shape placed under the base. It is a non-spacing mark glyph, and in the glyph sequence it follows the base consonant(s). In Bengali, below-base forms exist for Ra and Ba; the below-base Ra is the ra-phala. |
| Post-base form | Consonant shape placed right of the base, normally as a spacing glyph. In the text, such a consonant appears after the base consonant(s) and a halant. In Bengali, Ya takes a post-base form when it is the last consonant of the syllable. |
| Pre-base reordering form | In some scripts, a consonant (Ra) that comes after the base in the text, and in pronunciation, yet is drawn in front of it. The engine finds such cases from the font's 'pref' feature and moves the glyph. Ordinary half forms, by contrast, precede the base both logically and visually. |
| Akhand ligature | A conjunct that must always be formed. Its place in the syllable is unrestricted and it need not involve the base. It outranks all other conjuncts and is built first (some languages count such ligatures as letters). Both half and full shapes exist. |
| Matra | A dependent vowel sign. It never stands alone: it is always drawn together with one consonant or with a conjunct. |
| Split matra | A matra drawn as two or more parts that land in different places around the base, e.g. one part leading the cluster and another trailing it. |
| Nukta | A combining sign that alters the sound of the consonant (or matra) before it. |

## 2. Characters and character classes

### 2.1 Code points that the source assigns

The source gives code points in three places only: the reorder-class table (2.3), the grammar legend (A = U+0952), and the section on invalid marks (U+25CC, U+200D, U+200C, U+200B). It does not list, by code point, which characters belong to C, V, N, H, M, SM or VD.

| Code point | Unicode name | Role in the source |
|---|---|---|
| U+09B0 | BENGALI LETTER RA | Reph-forming Ra; listed as "09B0, 09F0 (reph)" in the reorder table |
| U+09F0 | BENGALI LETTER RA WITH MIDDLE DIAGONAL | Second reph-forming letter in the same table row |
| U+09BF, U+09C7, U+09C8 | see 2.3 | Pre-base matras, class BeforeHalf (U+09BF is the "I-matra" of the examples) |
| U+09C1..U+09C4, U+09E2, U+09E3 | see 2.3 | Matras with class AfterSubscript |
| U+09BE, U+09C0, U+09D7 | see 2.3 | Characters with class AfterPostscript |
| U+0981 | BENGALI SIGN CANDRABINDU | Class AfterPostscript |
| U+0952 | DEVANAGARI STRESS SIGN ANUDATTA | Grammar symbol A; the Bengali page uses this Devanagari-block code point |
| U+25CC | DOTTED CIRCLE | Default base for an invalid mark; fonts should contain this glyph |
| U+200D | ZERO WIDTH JOINER | ZWJ; fonts should contain this glyph |
| U+200C | ZERO WIDTH NON-JOINER | ZWNJ; fonts should contain this glyph |
| U+200B | ZERO WIDTH SPACE | ZWSP; fonts should contain this glyph |

Note on the joiners: the source's sentence recommending these glyphs swaps the two abbreviations. It pairs "ZWJ" with "zero width non-joiner; U+200C" and "ZWNJ" with "zero width joiner; U+200D". The names and code points it gives agree with Unicode: ZWJ is U+200D ZERO WIDTH JOINER and ZWNJ is U+200C ZERO WIDTH NON-JOINER, as used everywhere else in these notes.

Reference (Unicode): characters that the source names without a code point.

| Name in the source | Code point | Unicode name |
|---|---|---|
| halant / virama (H) | U+09CD | BENGALI SIGN VIRAMA |
| nukta (N) | U+09BC | BENGALI SIGN NUKTA |
| NBSP | U+00A0 | NO-BREAK SPACE |
| Ba (below-base form) | U+09AC | BENGALI LETTER BA |
| Ya (post-base form) | U+09AF | BENGALI LETTER YA |
| Danda, Double Danda | U+0964, U+0965 | DEVANAGARI DANDA, DEVANAGARI DOUBLE DANDA (the Bengali block has no danda of its own) |
| pre-composed nukta characters | U+09DC, U+09DD, U+09DF | BENGALI LETTER RRA, BENGALI LETTER RHA, BENGALI LETTER YYA |
| two-part matras | U+09CB, U+09CC | BENGALI VOWEL SIGN O = U+09C7 U+09BE; BENGALI VOWEL SIGN AU = U+09C7 U+09D7 (canonical decompositions) |

### 2.2 Static and dynamic properties

- Static properties belong to the script and are the same in every font; a font cannot change them. They are the character type (consonant, matra, vedic sign and so on) and the kind of reordering a matra undergoes (table 2.3).
- Dynamic properties come from the font: the engine reads them when it loads the font, and they affect both shaping and reordering. In the revised model the conjoining behaviour of consonants is dynamic (2.4).
- In the earlier model every consonant property was static: the engine assumed each consonant had particular conjoining forms.

### 2.3 Reordering classes (exact)

Column headings as in the source: Characters, Reorder Class. Rows are in source order; the last column is an addition.

| Row | Characters | Reorder Class | Reference (Unicode) names |
|---|---|---|---|
| 1 | U+09B0, U+09F0 (reph) | AfterSubscript | BENGALI LETTER RA; BENGALI LETTER RA WITH MIDDLE DIAGONAL; both in their reph role |
| 2 | U+09BF, U+09C7, U+09C8 | BeforeHalf | BENGALI VOWEL SIGN I, E, AI |
| 3 | U+09C1..U+09C4, U+09E2, U+09E3 | AfterSubscript | BENGALI VOWEL SIGN U, UU, VOCALIC R, VOCALIC RR, VOCALIC L, VOCALIC LL |
| 4 | U+09BE, U+09C0, U+09D7 | AfterPostscript | BENGALI VOWEL SIGN AA, BENGALI VOWEL SIGN II, BENGALI AU LENGTH MARK |
| 5 | U+0981 | AfterPostscript | BENGALI SIGN CANDRABINDU |

Notes:
- U+0981 (candrabindu) is the only syllable modifier sign the table classifies; it gives no class for vedic signs.
- The two-part matras U+09CB and U+09CC are not in the table. Reading note: initial reordering splits multi-part matras before moving them (5.1), and by their Unicode decompositions the parts fall under row 2 (U+09C7, BeforeHalf) and row 4 (U+09BE or U+09D7, AfterPostscript).
- Reading note: the source never defines the class names. They match the target slots used in reordering (section 5): BeforeHalf = before the first half form; AfterSubscript = after the subjoined (below-base) consonants; AfterPostscript = after the post-base consonant forms; BeforePostscript (not used in this table) = before the post-base consonant forms.
- Reading note: the reph steps in 5.2 name three reph positions (after the main consonant, before the post-base consonant forms, after the post-base consonant forms), and AfterSubscript is not literally one of them. Read by its name, the class puts reph after the below-base consonants, which in the syllable order of 3.5 come before any post-base consonants.

### 2.4 Consonant types read from the font

| Consonant type | Feature | Two-character probe input |
|---|---|---|
| Reph | 'rphf' | Consonant + Halant |
| Half form | 'half' | Consonant + Halant |
| Pre-base-reordering form of Ra/Rra | 'pref' | Halant + Consonant |
| Below-base form | 'blwf' | Halant + Consonant |
| Post-base form | 'pstf' | Halant + Consonant |

Procedure:
1. For each consonant, apply each of the five features, together with 'locl', to the two-character input shown.
2. A consonant has a given form exactly when the probe collapses the pair into a single glyph, using no surrounding glyphs as context. Example: if 'half' with 'locl' substitutes U+09A6 U+09CD (Da, virama), Da counts as a consonant with a half form.
3. All classifications come from these context-free probes. A font may move Ra to the pre-base position in some syllables and draw it below or after the base in others, so the pre-base-reordering class can coexist with the below-base or post-base class.
4. The font decides only the consonant types. Each character class keeps fixed reordering positions.
5. Fonts built for the earlier model are probed with Consonant + Halant for all five features.

## 3. Syllable structure

### 3.1 Processing loop

While input remains, find the next syllable by matching one of the three patterns in 3.2, then shape that syllable by itself; nothing outside it takes part.

### 3.2 Syllable patterns (exact, source notation)

The source prints the consonant-syllable pattern as two list items, the first ending in "} +"; they are joined into one line here.

```
Consonant syllable
{C+[N]+<H+[<ZWNJ|ZWJ>]|<ZWNJ|ZWJ>+H>} + C+[N]+[A] + [< H+[<ZWNJ|ZWJ>] | {M}+[N]+[H]>]+[SM]+[(VD)]

Vowel-based syllable:
[Ra+H]+V+[N]+[<[<ZWJ|ZWNJ>]+H+C|ZWJ+C>]+[{M}+[N]+[H]]+[SM]+[(VD)]

Stand Alone cluster (at the start of the word only):
[Ra+H]+NBSP+[N]+[<[<ZWJ|ZWNJ>]+H+C>]+[{M}+[N]+[H]]+[SM]+[(VD)]
```

### 3.3 Symbols

- `{ }` zero or more occurrences
- `[ ]` optional occurrence
- `<|>` "one of": the alternatives inside `<` and `>` are separated by `|`
- `( )` one or two occurrences
- `+` followed by (implied by the patterns; not part of the source legend)
- `C` consonant
- `V` independent vowel
- `N` nukta
- `H` halant/virama
- `ZWNJ` zero width non-joiner
- `ZWJ` zero width joiner
- `M` matra; at most one of each type (pre-base, above-base, below-base, post-base)
- `SM` syllable modifier sign
- `VD` vedic
- `A` anudatta (U+0952)
- `NBSP` NO-BREAK SPACE
- `Ra` the letter Ra (Reference (Unicode): U+09B0)

### 3.4 Reading the patterns

Consonant syllable, from left to right:
1. `{C+[N]+<H+[<ZWNJ|ZWJ>]|<ZWNJ|ZWJ>+H>}`: any number of leading units. Each unit is a consonant with an optional nukta, closed either by a halant that may carry one joiner after it, or by one joiner placed before a halant.
2. `C+[N]+[A]`: the last consonant, then an optional nukta and an optional anudatta.
3. `[< H+[<ZWNJ|ZWJ>] | {M}+[N]+[H]>]`: optionally one of two endings: a final halant (a joiner may follow it), or a run of matras followed by an optional nukta and an optional halant.
4. `[SM]+[(VD)]`: an optional syllable modifier sign, then zero, one or two vedic signs.

Vowel-based syllable: an optional Ra + halant (a reph candidate); the independent vowel with an optional nukta; optionally either an (optional joiner, halant, consonant) tail or a (ZWJ, consonant) tail; an optional group of matras with optional nukta and halant; an optional syllable modifier; zero to two vedic signs.

Stand Alone cluster: valid only at the start of a word. NBSP replaces the vowel, and the only consonant tail it accepts is (optional joiner, halant, consonant). This is the pattern behind showing marks and conjoining forms on their own (section 7).

### 3.5 Parts of a syllable

```
Reph + HalfConsonant(s) + MainConsonant(s) + BelowBaseConsonant(s) + PostBaseConsonant(s) + PreBaseReorderingRa + MatrasAndSigns
```

- Halants and nuktas count as part of the consonant part they belong to; a BelowBaseConsonant, say, is the pair Halant + below-base-forming consonant.
- The main consonant is the only required part.
- The order above holds except for PreBaseReorderingRa, whose place is font-dependent: ahead of every BelowBaseConsonant, between the below-base and post-base groups, or after the last PostBaseConsonant.
- Since a font can restrict pre-base reordering of Ra to some syllables, the engine cannot settle a given Ra's status until that syllable has been through 'pref'.
- A syllable has more than one main consonant whenever two or more of its consonants lack all four conjoining forms (pre-base, half, below-base, post-base). If the first consonant has no half form, the engine records it as the first full-form consonant and goes on to look for a second one. The result guides where reph, matras, vowel modifiers and stress marks are moved.
- Everything else in the syllable gets a position class with respect to the base: pre-base (covering half forms and a pre-base reordering Ra), below-base, above-base or post-base.

### 3.6 Finding the base consonant

1. Begin at the end of the syllable and step backwards over its consonants.
2. Step past any consonant that has a below-base form or a post-base form, or that is a pre-base reordering Ra. The source adds, in parentheses, an ordering condition: in the syllable, post-base forms come after below-base forms.
3. The scan stops at the first consonant that is none of these, or when it reaches the first consonant of the syllable. The consonant where it stops is the base.
4. Exception: a syllable-initial Ra + Halant can never be chosen as the base when the syllable has other consonants (the rule applies to scripts with reph, Bengali among them).

### 3.7 Cluster constraints

- At most one reph per syllable.
- At most one pre-base reordering Ra per syllable.
- A nukta may attach to a consonant, a matra or an independent vowel, but not to a character that already includes a nukta (Reference (Unicode): U+09DC, U+09DD, U+09DF).
- Per positioning class a syllable may carry one matra (Kannada is the stated exception); a composite matra occupies every class its components occupy.
- At most one syllable modifier sign per cluster.
- Vedic signs, the combining marks needed for Sanskrit, belong in every Indic script.
- Every Indic script is expected to include the Danda and Double Danda punctuation marks (Reference (Unicode): U+0964, U+0965).

## 4. Shaping stages and features

### 4.1 Stages

1. Analyse: split the text into syllables (3.2) and work out each character's properties (2.2 to 2.4).
2. Initial reordering (5.1), before any feature has run.
3. Substitution (GSUB): map each character to its nominal glyph through the cmap table; apply 'locl' and the basic shaping forms; run final reordering (5.2); apply the presentation forms.
4. Positioning (GPOS): apply the positioning features.

### 4.2 Feature order (exact)

Feature, Feature function and Layout operation are the source's columns; Order and Group restate its row grouping. GSUB = glyph substitution, GPOS = glyph positioning. The final-reordering row marks where that step runs; it is not a row of the source table.

| Order | Group | Feature | Feature function | Layout operation |
|---|---|---|---|---|
| 1 | Localized forms | locl | Localization form substitution | GSUB |
| 2 | Basic shaping forms | nukt | Nukta form substitution | GSUB |
| 3 | Basic shaping forms | akhn | Akhand ligature substitution | GSUB |
| 4 | Basic shaping forms | rphf | Reph form substitution | GSUB |
| 5 | Basic shaping forms | blwf | Below-base form substitution | GSUB |
| 6 | Basic shaping forms | half | Half-form substitution | GSUB |
| 7 | Basic shaping forms | pstf | Post-base form substitution | GSUB |
| 8 | Basic shaping forms | vatu | Vattu variants | GSUB |
| 9 | Basic shaping forms | cjct | Conjunct form substitution | GSUB |
| - | final reordering (5.2) | - | - | - |
| 10 | Mandatory presentation forms | init | Initial form | GSUB |
| 11 | Mandatory presentation forms | pres | Pre-base substitution | GSUB |
| 12 | Mandatory presentation forms | abvs | Above-base substitution | GSUB |
| 13 | Mandatory presentation forms | blws | Below-base substitution | GSUB |
| 14 | Mandatory presentation forms | psts | Post-base substitution | GSUB |
| 15 | Mandatory presentation forms | haln | Halant form substitution | GSUB |
| 16 | Discretionary presentation forms | calt | Contextual alternates | GSUB |
| 17 | Positioning features | kern | Kerning | GPOS |
| 18 | Positioning features | dist | Distances | GPOS |
| 19 | Positioning features | abvm | Above-base mark positioning | GPOS |
| 20 | Positioning features | blwm | Below-base mark positioning | GPOS |

### 4.3 How each group is applied

- Orders 1 to 9 run one feature at a time, each over the cluster or over the part of it that the feature concerns. Their output decides two things: whether any Ra is finally treated as pre-base reordering, and the final positions of reph and matras.
- Final reordering (5.2) runs after order 9 and before order 10.
- Orders 10 to 16 are applied together, in one pass over the entire cluster; inside each feature, lookups run in the order the font lists them. Because of this joint application the mandatory presentation features act as one: a font may spread its lookups across them or put them all under one tag with the same result, and the separate tags exist only to help font makers organise lookups. None of them may ever be treated as optional.
- 'init' sits in the table's mandatory presentation group and is listed first among the presentation features, but the source's paragraph on mandatory presentation features names only 'pres', 'abvs', 'blws', 'psts' and 'haln'.
- Mandatory features are always applied. 'calt' is discretionary: applied by default, but a client may suppress it (normally when the user asks), so a font must not depend on it for required forms.
- Orders 17 to 20 are applied together over the entire cluster, to glyphs in the order the presentation forms left them.
- Inside every feature, the order of the lookups matters.
- Each feature sees the output of the features applied before it.
- 'pref' does not appear in the ordered list, although the probe (2.4) uses it and final reordering (5.2) relies on it. The source says only that a Ra's pre-base status is final once 'pref' has been applied to the syllable.

### 4.4 Where each feature applies

| Feature | Glyphs or part of the syllable it acts on, per the source |
|---|---|
| locl | Glyphs that need a language-specific variant; used with language system tags other than the default ("dflt") |
| nukt | A full-form consonant followed by a nukta |
| akhn | Full-form consonants joined by a halant; applied across the entire cluster |
| rphf | Full-form Ra + Halant when it is the first consonant of the cluster |
| blwf | Halant + Ra and Halant + Ba (the stage list calls this "ba + ra phala"), when the consonant before them forms no ligature with them |
| half | Every consonant that comes before the main consonant (consonant + halant) |
| pstf | Halant + Ya, when Ya is the last consonant of the syllable |
| vatu | The below-base mark (vattu, i.e. ra-phala) together with the consonant or conjunct glyph before it, whether that glyph is full or half |
| cjct | A consonant pair whose first consonant has no half form |
| init | The vowels E and AI; the source requires the input context of every initial form to be the full forms of consonants |
| pres | Consonant and matra conjuncts on the left of the base |
| abvs | Conjuncts with above-base matras or with reph; vowel modifiers above the base; stress and tone marks above the base |
| blws | Conjuncts with below-base consonants or matras; vowel modifiers below the base; stress and tone marks below the base |
| psts | Conjuncts with post-base consonants or matras; vowel modifiers after the base |
| haln | The base (or conjunct base) glyph when the syllable ends with a halant; also a non-final consonant that has no half form and makes no conjunct with the next consonant |
| calt | Consonants that have contextual alternates |
| kern, dist | Spacing between glyphs, for example between a pre-base or post-base element and the base |
| abvm | Matras, vowel modifiers, stress or tone marks and consonant forms that sit above the base; each is attached to a base glyph or to a post-base matra |
| blwm | Matras, vowel modifiers, stress or tone marks and consonant forms that sit below the base; each is attached to a base glyph or to a post-base matra |

## 5. Reordering

### 5.1 Initial reordering (before any feature)

For each cluster the engine builds a buffer of glyph elements in reordered sequence. Font lookups are written against that reordered sequence. A font should not try to perform the reordering through substitutions: covering the engine's general rules that way would take an enormous number of many-to-many mappings.

Steps, in order:
1. Find the base consonant (3.6).
2. Decompose and reorder matras. First break every two-part or three-part matra into its components (in Bengali, Reference (Unicode): U+09CB -> U+09C7 U+09BE and U+09CC -> U+09C7 U+09D7). Then move every matra, and any syllable modifier sign, to its slot relative to the consonants. The slot depends on which consonant of a conjunct the matra has affinity for (its reorder class, 2.3). The slots are:
   - before the first half form of the syllable;
   - after the subjoined (below-base) consonants;
   - after the post-base consonant;
   - after the main consonant (for above-base marks).
3. Canonical mark order: a nukta must precede an adjacent halant or vedic sign; swap the two when the text has them the other way round.

Reph is not moved in this phase. It stays at the very start of the syllable until final reordering.

### 5.2 Final reordering (after 'locl' and the basic shaping forms, before the presentation forms)

Three operations, in this order.

**A. Pre-base matras.** This concerns a pre-base matra that initial reordering placed in front of the half forms (in Bengali the BeforeHalf characters U+09BF, U+09C7, U+09C8). Depending on which half forms actually came out of the basic shaping features, its glyph may now move nearer to the main consonant. The target slot lies:
- after the last halant glyph that still stands on its own;
- no earlier than the slot that initial reordering gave the matra;
- before the main consonant.

If that halant is directly followed by ZWJ or ZWNJ, the slot moves to after the joiner.

**B. Reph.** Reph has been at the start of the syllable up to now; where it goes depends on the basic-forms results. The three possible reph positions are: after the main consonant; before the post-base consonant forms; after the post-base consonant forms. Bengali reph (U+09B0, U+09F0) has class AfterSubscript (2.3). The source's sub-steps, numbered 1 to 6:

1. If reph belongs after the post-base consonant forms, go to step 5.
2. Otherwise, look for the first explicit halant glyph that lies between the first consonant after the reph and the last main consonant. If one exists, the target is right after it (or after a ZWJ or ZWNJ that immediately follows it), and the search ends. If none exists, continue with step 3. For fonts built for the earlier model, this step never finds a position.
3. If reph belongs after the main consonant: the source words this step elliptically. As the reference point it names the earliest consonant not ligated with the main consonant, or else the earliest consonant that could not act as a pre-base reordering Ra. It gives no further detail of the slot.
4. If reph belongs before the post-base consonants: find the first consonant classed as post-base that is not ligated with the main consonant; reph goes in front of it. If there is no such consonant, the target is in front of whichever matra, syllable modifier sign or vedic sign comes first.
5. If step 3 or step 4 found no consonant: place reph directly before the earliest post-base matra, syllable modifier or vedic sign whose reorder class lies beyond the intended reph position. The source's example: with a post-main reph position, an above-base matra whose position is also post-main is skipped.
6. Failing all of the above, reph goes to the end of the syllable.

**C. Pre-base reordering consonants.** If the syllable contains one:
1. Eligibility: the glyph must be the output of a 'pref' substitution. Fonts can enable 'pref' for Ra broadly and still block it in chosen contexts; a Ra left unsubstituted stays where it is.
2. Locate a slot with the pre-base matra rules of (A); when one exists, the glyph moves there.
3. With no such slot, the glyph goes directly before the main consonant.

### 5.3 Example: half forms decide where reph and the pre-base matra go

Input U+09B0 U+09CD U+09A6 U+09CD U+0995 U+09BF (Ra, virama, Da, virama, Ka, vowel sign I). Ra + virama becomes the reph.
- When Da + virama forms a half form (the case the source shows for Bengali), reph goes onto the first main consonant, Ka, and the I matra is placed directly in front of the half-form Da.
- If Da had no half form and the font did not list it under 'half', the halant form would show, Da would become the first main consonant and carry the reph, and the I matra would be placed directly in front of Ka.

The source's 'rphf' example makes the same point: reph is moved onto the first main consonant, not onto a half form.

## 6. Invalid combining marks and the dotted circle

- Invalid means: a combining mark or sign that has no valid base to go with.
- Engines are free to choose how they treat invalid marks, and their notions of validity can differ at the edges (the example given is a cap of a single above-base vowel mark, applied by some engines and not by others).
- The strategy the source describes: make the invalid mark a cluster of its own and draw it on a default base glyph such as the dotted circle U+25CC. The source points to "Fallback Rendering" in the Unicode Standard 4.0 (its section 5.13) and does not prescribe a more exact insertion rule.
- Reading note: a mark that none of the three patterns in 3.2 can absorb is the case that has no valid base.
- Fonts should contain a glyph for U+25CC. Without it, engines following this strategy draw the mark on the missing-glyph shape (a white box).
- Fonts should also contain glyphs for ZWJ (U+200D), ZWNJ (U+200C) and ZWSP (U+200B); see the note in 2.1 about the swapped labels in the source.
- To show a mark by itself without a dotted circle, text puts NBSP in front of it (section 7).

## 7. ZWJ, ZWNJ and NBSP

The Indic behaviour keeps the general Unicode meaning: ZWJ asks for neighbouring elements to connect, ZWNJ asks for them to stay apart.

| Use | Effect requested | What the engine must do |
|---|---|---|
| ZWJ inside a consonant cluster | Prevent a ligature conjunct. The source's sentence (worded as on the Devanagari page) adds that in Devanagari and Gujarati it asks for a half, below-base or post-base form instead. | Nothing special. The joiner sits between the glyphs, so substitution lookups no longer match. If the first consonant has no half form, the overt halant form results by itself. |
| Cluster starting RA + H + ZWJ | Prevent the reph | 'rphf' must be skipped for this Ra and no reph reordering may happen. The same holds with ZWNJ in place of ZWJ. |
| Consonant + Halant + ZWNJ | Prevent conjunct ligatures and half forms; show an explicit halant form | Must actively stop a half form from being made out of this Consonant + Halant. |
| NBSP + mark, for example U+00A0 U+09BF | Show a matra or other mark alone, without a dotted circle | NBSP acts as the base. |
| NBSP with ZWJ | Show the below-base form of Ra alone | NBSP acts as the base; ZWJ requests the conjoining form. |

Notes:
- A half form can be shown alone with ZWJ and no NBSP. Marks and below-base or post-base forms need a leading NBSP instead; the source's reason is that such glyphs are zero-width, so they need the NBSP to sit on.
- The Bengali page has no counterpart of the Devanagari eyelash-RA use of RA + H + ZWJ.
- Reading note: the Stand Alone pattern (3.2) accepts NBSP followed by an optional joiner, a halant and a consonant, for example U+00A0 U+200D U+09CD U+09B0. The source shows the below-base Ra sequence only as an illustration, not in text.

## 8. Base elements and mark classes

- A lookup often has to relate the base glyph to a single element of another position; the source names post-base, pre-base and above-base elements. Not all of these elements can be reordered to sit next to the base, so lookups must be able to skip the elements lying between.
- The source's remedy: give each kind of syllable element and positional form its own mark attachment class, so that a lookup can use its lookup flag to see one kind of mark and ignore the rest. Above-base substitutions, for example, mostly need to see only above-base elements.
- Glyphs that Unicode treats as marks, together with the below-base and above-base consonant forms, should be classed as marks, each with an attachment class chosen by its position relative to the base.
- Example from the source: after reordering, a matra always comes before a syllable modifier such as candrabindu, yet another mark (a nukta, say) may sit between them. A positioning lookup limited to above-base marks still matches in that case; a lookup processing all marks would fail.
- Consequence for an engine: lookup flags and mark attachment classes must be honoured during matching.

## 9. Feature descriptions

Each feature sees the glyph sequence after reordering and after the features applied before it.

### Localized forms

- 'locl': Selects glyph variants that follow the conventions of a particular language, triggered through language system tags. Fonts should attach it to specific language systems only, not to the default one (tags in section 11).

### Basic shaping forms

- 'nukt': Replaces a full-form consonant plus nukta with a precomposed nukta glyph; the source's example is Ya + nukta (U+09AF U+09BC) becoming the Yya glyph. Fonts may instead place the nukta as a below-base mark with 'blwm'. Half forms of nukta consonants come later, from 'half'. Every consonant and akhand form is expected to have a nukta variant.
- 'akhn': Builds the obligatory akhand ligatures from full-form consonants. The source's examples are KaSsa from U+0995 U+09CD U+09B7 and JaNya from U+099C U+09CD U+099E; unlike the Devanagari page it gives no count. Half forms of akhand ligatures come later, from 'half'. Since it runs early and over the whole cluster, a font can also use it for forms that must win over what later features would make.
- 'rphf': Turns a cluster-initial full-form Ra + Halant (U+09B0 U+09CD) into the reph, a combining-mark glyph. Final reordering then moves it onto the first main consonant (not onto a half form), and 'abvm' adjusts its position.
- 'blwf': Gives Ra and Ba their below-base shapes, starting from Halant + Ra and Halant + Ba, in cases where the consonant before them does not ligate with them.
- 'half': Replaces consonant + halant with the half form for every consonant before the main consonant; a consonant without a distinct half shape and without a ligature shows its halant form. Listing a consonant here, even when its "half form" is only the halant-form shape, changes where reph and pre-base matras go (example 5.3).
- 'pstf': Produces post-base consonant forms; the Bengali case is Ya. When Ya is the final consonant of a syllable, Halant + Ya is replaced by the post-base Ya.
- 'vatu': Ligates a consonant, in full or half form, with the below-base vattu glyph after it (the Bengali ra-phala). Source examples: Ka with below-base Ra and Tta with below-base Ra. Fonts may put these ligatures under 'blws' instead.
- 'cjct': Forms conjunct ligatures when the first consonant of a pair has no half form, which gives the font control over reph and pre-base matra placement for such consonants. Source example: Gha + halant + Na (U+0998 U+09CD U+09A8).

### Presentation forms

'init', 'pres', 'abvs', 'blws', 'psts' and 'haln' form the table's mandatory group; 'calt' is discretionary. The source sets no rule on which lookups go under which of 'pres', 'abvs', 'blws', 'psts' and 'haln'; the descriptions below are typical uses.

- 'init': Swaps vowel E or vowel AI for an initial-form variant, a glyph that lacks the joining bar on its leading edge. The source requires the input context of all such lookups to be consonant full forms, and gives no further rule for deciding which glyphs count as initial. Reference (Unicode): the vowel signs E and AI are U+09C7 and U+09C8, both BeforeHalf in table 2.3.
- 'pres': Makes pre-base conjuncts from half forms, Bengali's usual conjunct type; the result may be a full or a half form (examples include half Ka + half Ssa + Nna giving one KaSsaNna ligature). It also picks the right shape of the I-matra (U+09BF) for the consonant or cluster it precedes, and may hold precomposed ligatures of the I-matra with particular bases (the source shows I-matra followed by Tta, U+099F, and by Ttha, U+09A0, each becoming one ligature).
- 'abvs': Substitutions involving above-base marks: contextual shapes of marks, mark-to-mark ligatures and mark-to-base ligatures. Source examples: reph with an I-type matra, and reph with candrabindu, each becoming one ligature glyph. The source also lists specific context-dependent forms and below-base consonants under this feature.
- 'blws': Works on below-base marks and consonants: conjuncts of a base with a below-base consonant, ligatures of below-base marks, ligatures of a below-base mark with its base, and other context-dependent forms. In the source's examples a below-base U matra changes shape inside such a ligature, and a conjunct base merges with a following U matra.
- 'psts': Substitutions involving post-base consonants or matras: conjuncts of a base with a post-base consonant, post-base matra ligatures (the source shows Ttha with vowel sign II, and a Sha plus below-base Ra conjunct with vowel sign II), and contextual alternates of post-base forms.
- 'haln': Substitutes a precomposed halant form of the base or conjunct base in a syllable that ends with a halant. A font may instead position the halant as a below-base mark with 'blwm'.
- 'calt': Optional discretionary contextual alternates. Users may be able to turn it off, so it must not carry any form that correct Bengali typography requires.

### Positioning features

- 'kern': Adjusts distances between glyphs, for example between pre-base or post-base elements and the base. Whether it is applied depends on the application enabling kerning.
- 'dist': Does the same kind of distance adjustment as 'kern', but does not depend on the application enabling kerning, so it suits adjustments that must always appear.
- 'abvm': Places each mark that sits above the base (reph included) on the base glyph or on a post-base matra. Fonts do this best with a chaining contextual lookup that calls mark-to-base and mark-to-mark attachment lookups for these marks. The source also shows a contextual single adjustment that raises candrabindu over certain bases, using as preceding context an I-matra (ikaar) glyph followed by one of those bases.
- 'blwm': Places each mark that sits below the base on the base glyph. Here too a chaining contextual lookup calling mark-to-base and mark-to-mark attachment lookups is the preferred encoding.

## 10. Earlier model compared with the revised model

| Topic | Earlier model | Revised model (described by the source) |
|---|---|---|
| Script tag | "beng" | "bng2" |
| Consonant conjoining properties | Static: built into the engine | Dynamic: probed from the font (2.4) |
| Probe input for 'pref', 'blwf', 'pstf' (halant position) | Consonant + Halant | Halant + Consonant |
| Probe input for 'rphf', 'half' | Consonant + Halant | Consonant + Halant |
| Reph step 2 in 5.2 | Never yields a position | May yield a position |

Older-model fonts keep working with the newer engines; updating them is optional and mainly lifts the older model's restrictions.

## 11. Writing system tags (exact)

| Script tag | Script | Language system tag | Language |
|---|---|---|---|
| "bng2" | Bengali | "dflt" | *default script handling |
| | | "ASM " | Assamese |
| | | "BEN " | Bangla |
| | | "MNI " | Manipuri |

- "bng2" is the script tag for the revised model; engines following the earlier model used "beng".
- Tags are case-sensitive and exactly four characters long: script tags are lowercase, language tags uppercase, and three-letter language tags are padded with a trailing space.
- Include "dflt" in every font. It holds the font's basic handling of the script and is the fallback when no language-specific features are defined or the application lacks support for the requested language; some applications may not work with a font that has no "dflt" for the script.
- The source notes that most engines then supported only the default language system, while language-specific features may be used by other applications.

## 12. Where the Devanagari page differs

The syllable patterns, base-finding rule, cluster constraints and final-reordering procedure are worded the same on both pages. The differences:

| Topic | Bengali page | Devanagari page |
|---|---|---|
| Reph-forming letters and their class | U+09B0 and U+09F0, AfterSubscript | U+0930, BeforePostscript |
| BeforeHalf matras | U+09BF, U+09C7, U+09C8 | U+093F |
| AfterSubscript matras | U+09C1..U+09C4, U+09E2, U+09E3 | U+0941..U+0948, U+0962, U+0963, U+093E, U+0940, U+0949..U+094C |
| AfterPostscript characters | U+09BE, U+09C0, U+09D7, and U+0981 (candrabindu) | none |
| Below-base consonant forms | Ra and Ba | Ra only (rakaar) |
| Post-base consonant form | Ya, through 'pstf' | none named; 'pstf' appears only among the probes |
| Basic shaping features | nukt, akhn, rphf, blwf, half, pstf, vatu, cjct | nukt, akhn, rphf, rkrf, blwf, half, vatu, cjct |
| Presentation features | init, pres, abvs, blws, psts, haln, calt | pres, abvs, blws, psts, haln, calt (no 'init') |
| 'vatu' | 'blws' may make the same ligatures | Unnecessary when 'rkrf' is used |
| ZWJ uses | No eyelash RA item | Includes RA + H + ZWJ as the Marathi eyelash RA |
| NBSP explanation | Marks and below-base or post-base forms are zero-width, so they sit on the NBSP | A mark needs a base glyph to combine with |
| Akhand ligatures | Two pairs shown, no count stated | Two, stated as a count |
| Elements named under base elements | Post-, pre- and above-base | Post-, pre-, above- and below-base |
| 'locl' function name in the feature table | Localization form substitution | Localized form substitution |
| Legend entry for SM | syllable modifier sign | syllable modifier signs |
| Reph sub-step labels | 1 to 6 | (a) to (f) |
| Sentence giving ZWJ/ZWNJ code points | Swaps the two labels | Correct |
| Script tag (earlier-model tag in parentheses) | "bng2" ("beng") | "dev2" ("deva") |
| Language systems | "dflt", "ASM ", "BEN ", "MNI " | "dflt", "HIN ", "KSH ", "KOK ", "MAR ", "NEP ", "SAN ", "SND " |
