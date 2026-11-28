# Registered Features a-e
Source: Registered features, a-e (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/features_ae
These notes restate the source's structures and rules; where they differ, the source governs.

This file covers the registered feature tags from 'aalt' to 'expt', in the source's order.
featuretags.md lists every registered tag; the other ranges are in features_fj.md,
features_ko.md, features_pt.md and features_uz.md. Lookup types are written "GSUB n" or
"GPOS n" (see gsub.md and gpos.md).

Terms used below:

- Discretionary: the application applies the feature to runs as markup, the user or its own
  logic decides.
- Script-required: needed to display a script correctly; the script's shaping logic applies it
  in the contexts its processing rules define, and users normally do not control it.
- Default on / Default off: the source's suggested initial state in an application.

## 'aalt' - Access All Alternates

- Registered by: Adobe
- Function: makes every variant of a selected character reachable, for cases where the
  normal feature is unsupported, the needed context is absent, or the user does not know
  which feature gives the glyph.
- Lookups: normally GSUB 3; GSUB 1 is acceptable when a glyph has one alternate; one lookup
  may mix type 3 and type 1 subtables. Other types are not recommended.
- Application: discretionary. Take the character's default glyph from 'cmap' with no
  features applied; if it is in the coverage of an 'aalt' lookup, offer the alternates that
  lookup maps it to and substitute the one chosen. The first alternate may be treated as the
  preferred form; with a single alternate the feature can toggle between the two forms.
- Font data: the default glyph may appear in its own alternate set, as the first entry.
  Ligatures are not listed as alternates of a component glyph (an fi ligature is not an
  alternate of f), but a ligature may be an alternate of another ligature. Alternate order
  should match across fonts of a family.
- Script/language sensitivity: none. Interactions: may be combined with other features.

## 'abvf' - Above-base Forms

- Registered by: Microsoft
- Function: substitutes the above-base part of a split vowel, for Khmer and other
  Brahmi-derived scripts where a vowel has pre-base and above-base parts but no Unicode
  decomposition into two characters.
- Lookups: GSUB 1 (default vowel glyph to its above-base component glyph).
- Application: script-required for Khmer. In a cluster containing such a split vowel, the
  application first inserts the pre-base glyph at the correct position, then applies
  'abvf' to the split vowel. Not exposed to users.
- Script/language sensitivity: Khmer; possibly other Brahmi-derived scripts.
  Interactions: its result overrides all other features.

## 'abvm' - Above-base Mark Positioning

- Registered by: Microsoft
- Function: places marks over base glyphs.
- Lookups: GPOS 4 and GPOS 5 (x, y anchors).
- Application: script-required positioning; applied in the contexts the script's processing
  defines. Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts.
  Interactions: positions default marks or marks chosen contextually by a feature such as
  'abvs'.

## 'abvs' - Above-base Substitutions

- Registered by: Microsoft
- Function: replaces a base glyph and the mark above it with a ligature.
- Lookups: GSUB 4 (consonant plus vowel sequences to ligatures).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts. Interactions: none.

## 'afrc' - Alternative Fractions

- Registered by: Microsoft
- Function: turns a digit sequence, slash and digit sequence into an alternative style of
  fraction glyph.
- Lookups: GSUB 4 (digits plus U+002F SOLIDUS or U+2044 FRACTION SLASH plus digits to one
  fraction ligature).
- Application: discretionary; the application applies it to the whole sequence of figures
  and slash or fraction slash. Default off.
- Script/language sensitivity: none. Interactions: its result overrides all other
  features.

## 'akhn' - Akhand

- Registered by: Microsoft
- Function: replaces a character sequence that forms an akhand with its ligature, preferring
  it regardless of the surrounding characters.
- Lookups: GSUB 4.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts.
- Interactions: one of the Indic basic-form features, which the application processes in
  this order: 'nukt', 'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'.
  Lookups of discretionary typographic features run after these.

## 'apkn' - Kerning for Alternate Proportional Widths

- Registered by: Adobe/Microsoft (the source misspells the label)
- Function: kerns glyphs that are fixed-width by default but have been given proportional
  widths by 'palt'.
- Lookups: GPOS, normally GPOS 2. Single and pair adjustments add up, so the order of these
  lookups relative to GPOS 1 or 2 lookups of 'palt' and similar features does not matter.
- Application: default off. It may be turned on for a run only when 'palt' is on for that
  run (it may then be switched on automatically, but users must be able to turn it off while
  'palt' stays on). When 'palt' is turned off for a run, 'apkn' must be turned off too,
  because the kerning is wrong for fixed-width glyphs. Since it acts only on glyphs that
  'palt' makes proportional, it can be disabled on any run without 'palt' without
  inspecting its lookups.
- Font data: glyphs that 'palt' can make proportional should be kerned only through 'apkn',
  not through 'kern'. A font implementing 'apkn' should also implement 'palt'.
- Script/language sensitivity: mainly CJK, but usable for any script whose glyphs are
  fixed-width by default.

## 'blwf' - Below-base Forms

- Registered by: Microsoft
- Function: gives a consonant inside a conjunct its below-base shape.
- Lookups: GSUB 4 (virama (halant) plus consonant to the below-base form).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: many Indic and other Brahmi-derived scripts.
- Interactions: one of the Indic basic-form features, processed in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features
  run after them.

## 'blwm' - Below-base Mark Positioning

- Registered by: Microsoft
- Function: places marks under base glyphs.
- Lookups: GPOS 4 and GPOS 5.
- Application: script-required positioning; applied in the contexts the script's processing
  defines. Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts.
  Interactions: positions default marks or marks chosen contextually by a feature such as
  'blws'.

## 'blws' - Below-base Substitutions

- Registered by: Microsoft
- Function: forms ligatures of a base glyph with below-base forms.
- Lookups: GSUB 4 (consonant conjunct or consonant plus vowel sequences to ligatures).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts. Interactions: its
  result overrides all other features.

## 'calt' - Contextual Alternates

- Registered by: Adobe
- Function: in given contexts, replaces default glyphs with alternates that join better;
  meant for script typefaces whose glyphs join.
- Lookups: GSUB 6 (context plus replacement of one or more glyphs).
- Application: discretionary. Default on.
- Script/language sensitivity: scripts with optional cursive styles. Interactions: may be
  combined with other GSUB features and may override their results.

## 'case' - Case-sensitive Forms

- Registered by: Adobe
- Function: raises punctuation and similar marks to suit all-capital text and lining
  figures, and replaces oldstyle figures with lining figures.
- Lookups: GSUB 1 (substitute glyphs) or GPOS 1 (xPlacement and yPlacement).
- Application: discretionary. The source suggests applying or removing it automatically
  when the user changes the case of more than one character, or for words detected as all
  capitals, according to user preference.
- Script/language sensitivity: European scripts only (notably Spanish setting).
  Interactions: overrides other figure features such as 'onum' and 'tnum'.

## 'ccmp' - Glyph Composition / Decomposition

- Registered by: Microsoft
- Function: composes the default glyphs of several characters into one glyph, or decomposes
  one character's default glyph into several glyphs, to simplify later glyph processing.
- Lookups: GSUB 4 (compose) and GSUB 2 (decompose).
- Application: always applied, and processed first of all features (the source also says it
  is processed only when called). Not exposed to users.
- Script/language sensitivity: none. Interactions: must be applied before any other feature.

## 'cfar' - Conjunct Form After Ro

- Registered by: Microsoft
- Function: Khmer only: picks alternate shapes for below-base or post-base conjoining forms
  when a conjoined Ro (Coeng Ra) precedes them in the syllable.
- Background a shaper needs: the conjoined Ro is reordered before the base consonant but
  wraps under it, so after reordering it is no longer adjacent to the below-base and
  post-base forms it can collide with. The application detects this and applies 'cfar' over
  the range of the below-base and post-base conjoining forms.
- Lookups: GSUB 1 (conjoining form to alternate form).
- Application: script-required for Khmer; expected for any syllable in which Coeng Ra
  is followed by further conjoining consonants or vowels. Not exposed to users.
- Script/language sensitivity: Khmer. Interactions: works with the other Khmer
  required-form features; discretionary features run after it.

## 'chws' - Contextual Half-width Spacing

- Registered by: Adobe/W3C
- Function: contextually narrows full-em glyphs (mostly punctuation and symbols) to half-em
  widths, approximating layouts such as JLREQ, CLREQ or KLREQ without breaking monospaced
  alignment. Unlike 'halt', the adjustment depends on context.
- Lookups: GPOS 2 or GPOS 8 (xPlacement, xAdvance, yPlacement, yAdvance), for class pairs or
  glyph pairs, optionally longer sequences ordered to take precedence over pair adjustments.
  With GPOS 2, valueFormat2 should be 0 (no adjustment of the second glyph), so that matching
  resumes at the second glyph and every glyph can be the first of a pair; adjusting the
  second glyph would make only every other pair adjustable.
- Application: not used when the layout engine itself implements CLREQ, JLREQ or KLREQ
  spacing; otherwise always supported, and default on, for horizontal CJK layout.
- Script/language sensitivity: mostly CJKV fonts.
- Interactions: mutually exclusive with the other horizontal width features ('fwid',
  'halt', 'hwid', 'palt', 'pkna', 'pwid', 'qwid', 'twid', 'pnum', 'tnum'), which are turned
  off when it is on; 'apkn' and 'kern' are disabled on runs where it is applied. Vertical
  counterpart: 'vchw'.

## 'cjct' - Conjunct Forms

- Registered by: Microsoft
- Function: produces consonant conjunct forms in Indic scripts. Like 'akhn', but applied at a
  later point of syllable shaping, just before final reordering, so that the shaper can see
  whether consonants conjoined before it places reordering vowel marks or reph.
- Lookups: GSUB 4 (consonant, virama, consonant sequences, possibly longer, or sequences of
  earlier conjunct or conjoining forms, to a conjunct glyph).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Devanagari and other Indic or Brahmi-derived scripts.
- Interactions: one of the Indic basic-form features, processed in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features
  run after them.

## 'clig' - Contextual Ligatures

- Registered by: Adobe
- Function: replaces a glyph sequence with a preferred ligature only in a specified context
  (useful in some scripts and for swash ligatures).
- Lookups: ligatures in a chained context. The source cites "GSUB lookup type 8" here; note
  that in gsub.md type 8 is reverse chaining single substitution and chained context
  substitution is type 6. Ligatures with more components must come before those with fewer
  so they can match.
- Application: discretionary; context before and after the sequence is taken into account.
  Default on.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them; see also 'dlig'.

## 'cpct' - Centered CJK Punctuation

- Registered by: Adobe
- Function: centers certain punctuation marks in fonts that lack separate centered forms.
- Lookups: GPOS 1 (xPlacement, xAdvance, yPlacement, yAdvance) for a few full-width glyphs.
- Application: discretionary. Default off.
- Script/language sensitivity: mainly Chinese fonts. Interactions: mutually exclusive with
  the other glyph-width features (for example 'tnum', 'fwid', 'hwid', 'halt', 'palt',
  'twid'), which are turned off when it is on.

## 'cpsp' - Capital Spacing

- Registered by: Adobe
- Function: adds spacing between glyphs for all-capital text (not for monospaced designs).
- Lookups: GPOS 1 (xPlacement and xAdvance), usually a uniform percentage increase for the
  capitals.
- Application: discretionary; the user may trigger it (for example by setting text in all
  caps) or the application may detect capital-only words. Default on; applications may let
  users change the amount.
- Script/language sensitivity: not for connecting scripts such as most Arabic.
  Interactions: combinable with any feature; its adjustments add to those of 'kern' and
  similar features.

## 'cswh' - Contextual Swash

- Registered by: Adobe
- Function: replaces default glyphs with swash forms in a given context; a character may
  have several swash alternates.
- Lookups: swash forms in a chained context (the source again cites GSUB type 8; see the
  note under 'clig'); with several alternates the nested lookup is GSUB 3. Alternate order
  should be consistent across the font.
- Application: discretionary; with a GSUB 3 implementation the application lets the user
  pick the alternate (the first is the preferred form). Default off.
- Script/language sensitivity: not used for ideographic scripts. Interactions: may be
  combined with other GSUB features and may override them; see also 'swsh' and 'init'.

## 'curs' - Cursive Positioning

- Registered by: Microsoft
- Function: positions adjacent glyphs so that cursive connections meet.
- Lookups: GPOS 3 (entry and exit anchors).
- Application: required positioning for fonts with cursive joining; always applied. Not
  normally exposed to users.
- Script/language sensitivity: mainly Arabic and other cursively connected scripts, and any
  script with optional cursive styles. Interactions: none.

## 'cv01' - 'cv99' - Character Variant 1 - Character Variant 99

- Registered by: Microsoft
- Function: each feature selects variants for one character, or for a small set of closely
  related characters (its case pair, precomposed characters containing it), when the
  variation does not apply across many characters. Compared with 'salt' they give per
  character control; compared with 'ss01'-'ss20' they are narrow rather than broad; they
  can also serve language preferences that 'locl' cannot cover.
- Lookups: GSUB 3 (GSUB 1 is acceptable for a single variant). Within one 'cvXX' feature
  every covered glyph should have the same number of variants, and the n-th variant of each
  glyph should correspond.
- Feature parameters: featureParamsOffset of the GSUB Feature table is either 0 or the
  offset of this table:

| Type | Name | Description |
|---|---|---|
| uint16 | format | 0. |
| uint16 | featUiLabelNameId | 'name' ID of the feature's UI label; may be NULL (0). |
| uint16 | featUiTooltipTextNameId | 'name' ID of tooltip text for the feature; may be NULL (0). |
| uint16 | sampleTextNameId | 'name' ID of sample text showing the feature; may be NULL (0). |
| uint16 | numNamedParameters | Number of named parameters; may be 0. |
| uint16 | firstParamUiLabelNameId | First 'name' ID of the parameter UI labels; must be 0 when there are no named parameters. |
| uint16 | charCount | Number of characters for which the feature has variants; may be 0. |
| uint24 | character[charCount] | Unicode scalar values of those characters. |

- Parameter rules:
  - Named parameters use the consecutive name IDs firstParamUiLabelNameId to
    firstParamUiLabelNameId + numNamedParameters - 1. Parameter value p (1-based) selects
    alternate p of a GSUB 3 lookup, and its label is name ID
    p + firstParamUiLabelNameId - 1.
  - numNamedParameters should not exceed the number of alternates in the feature's lookups,
    but may be smaller; readers must not assume the alternate array has exactly that many
    entries.
  - The name IDs are expected (not required) to lie in the font-specific range 256 to
    32767; firstParamUiLabelNameId + numNamedParameters - 1 should not exceed 32767.
  - A NULL name ID means no string. English strings should be present as a fallback for
    localized labels.
  - The character list is informational (exhaustive, partial or empty) and does not change
    what the feature does; with charCount 0 there is no array.
  - Fonts with several 'cvXX' features should use parameter tables consistently. Whether and
    how applications use any of this data is up to them.
- Application: discretionary. The application enumerates the 'cv01'-'cv99' features present,
  offers a selection UI, interprets parameter tables if it wishes, and with a GSUB 3
  implementation may pass an index into the alternate array. Default off.
- Script/language sensitivity: none.
- Interactions: may be combined with other GSUB features and may override them. Lookup order
  is the font's responsibility (for example when 'smcp' is applied afterwards). With
  complex scripts that need obligatory ligatures or contextual forms, 'cvXX' should be
  applied before the obligatory script features.

## 'c2pc' - Petite Capitals From Capitals

- Registered by: Tiro Typeworks / Emigre
- Function: turns capitals into petite capitals (for acronyms and similar words otherwise set
  in capitals).
- Lookups: GSUB 1.
- Application: discretionary; applications may use it to implement petite-cap formatting
  with language-specific case mapping (see 'pcap', 'smcp'). Default off.
- Script/language sensitivity: bicameral scripts such as Latin, Greek, Cyrillic and
  Armenian. Interactions: may be combined with other GSUB features and may override them;
  see 'pcap'.

## 'c2sc' - Small Capitals From Capitals

- Registered by: Adobe
- Function: turns capitals into small capitals.
- Lookups: GSUB 1.
- Application: discretionary; applications may use it to implement small-cap formatting with
  language-specific case mapping (see 'smcp'). Default off.
- Script/language sensitivity: bicameral scripts such as Latin, Greek, Cyrillic and
  Armenian. Interactions: may be combined with other GSUB features and may override them;
  see 'smcp'.

## 'dist' - Distances

- Registered by: Microsoft
- Function: required adjustments of the distance between glyphs. It is not a second kerning
  feature; user-controllable spacing belongs in 'kern'.
- Lookups: GPOS 1, GPOS 2, or contextual lookups that call GPOS 1 or 2 lookups.
- Application: script-required positioning; applied in the contexts the script's processing
  defines. Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts.
- Interactions: its adjustments add to those of features such as 'kern'; fonts should keep
  the glyphs affected by 'dist' and 'kern' separate unless combined effects are intended.

## 'dlig' - Discretionary Ligatures

- Registered by: Adobe
- Function: ligatures used for special effect at the user's choice.
- Lookups: GSUB 4; ligatures with more components must come first.
- Application: discretionary. Default off.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them; see also 'clig'.

## 'dnom' - Denominators

- Registered by: Adobe
- Function: replaces figures after a slash with denominator forms.
- Lookups: GSUB 1 (figures and related separators to denominator glyphs).
- Application: applied automatically by the application as part of its 'frac'
  implementation (see features_fj.md, 'frac'); no direct user control needed.
- Script/language sensitivity: none. Interactions: supports 'frac'; may be combined with
  other GSUB features and may override them.

## 'dtls' - Dotless Forms

- Registered by: Microsoft
- Function: provides dotless forms of mathematical alphanumeric characters (for example
  U+1D422 MATHEMATICAL BOLD SMALL I, U+1D423 MATHEMATICAL BOLD SMALL J, U+1D456 MATHEMATICAL
  ITALIC SMALL I, U+1D457 MATHEMATICAL ITALIC SMALL J) to carry math accents.
- Lookups: GSUB 1 for every dotted glyph.
- Application: required for math layout; a math layout handler applies it to the individual
  glyphs it selects (see the MATH table). Not exposed to users.
- Script/language sensitivity: math formula layout. Interactions: none.

## 'expt' - Expert Forms

- Registered by: Adobe
- Function: replaces standard Japanese forms with forms preferred by typographers; covers
  most 'jp78' substitutions and many more characters.
- Lookups: GSUB 1 (many default JIS90 glyphs to alternates).
- Application: discretionary. The effect amounts to a change of character code, so the
  application should store the code of the new glyph as well as the original code. Default
  on or off according to the application's market.
- Script/language sensitivity: Japanese only.
- Interactions: mutually exclusive with most features, which are turned off when it is on;
  'palt', 'vpal', 'vert' and 'vrt2' may still be applied.
