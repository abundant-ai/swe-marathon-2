# Registered Features p-t
Source: Registered features, p-t (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/features_pt
These notes restate the source's structures and rules; where they differ, the source governs.

This file covers the registered feature tags from 'palt' to 'twid', in the source's order.
featuretags.md lists every registered tag; the other ranges are in features_ae.md,
features_fj.md, features_ko.md and features_uz.md. Lookup types are written "GSUB n" or
"GPOS n" (see gsub.md and gpos.md). "Discretionary", "script-required" and "default on/off"
are used as defined in features_ae.md.

## 'palt' - Proportional Alternate Widths

- Registered by: Adobe
- Function: re-spaces glyphs designed for full-em widths onto individual, roughly
  proportional widths. Unlike 'pwid' it substitutes no glyphs (GPOS, not GSUB), so the glyphs
  keep their identity (for example they are not rotated in vertical setting as proportional
  Latin glyphs would be).
- Lookups: GPOS 1 (alternate metrics for the full-width glyphs). If the font also kerns, the
  glyphs affected by 'palt' should be kerned through 'apkn', not 'kern' ('kern' remains for
  glyphs that are proportional by default).
- Application: discretionary. Default off.
- Script/language sensitivity: mostly CJKV fonts.
- Interactions: mutually exclusive with the other horizontal width features ('chws',
  'fwid', 'halt', 'hwid', 'pwid', 'qwid', 'twid'), which are turned off. When 'palt' is on,
  kerning features may be on for the run (by default or preference); when it is off, 'apkn'
  and 'kern' must not act on the glyphs covered by 'palt' lookups, since those glyphs are
  then fixed width. Vertical counterpart: 'vpal'.

## 'pcap' - Petite Capitals

- Registered by: Tiro Typeworks / Emigre
- Function: turns lowercase glyphs into petite capitals (capitals smaller than small caps,
  common in designs with a small x-height); related forms such as matching figures may be
  included.
- Lookups: GSUB 1. Language-specific case mappings may need separate language systems. Fonts
  that implement 'pcap' should also implement 'c2pc'.
- Application: discretionary. For correct language-specific case mapping an application can
  uppercase the text in a temporary buffer and apply 'c2pc' instead (see 'smcp'). Default off.
- Script/language sensitivity: scripts with upper and lower case (Latin, Cyrillic, Greek and
  others). Interactions: may be combined with other GSUB features and may override them.

## 'pkna' - Proportional Kana

- Registered by: Adobe
- Function: swaps fixed-width (half or full) kana and related glyphs for proportionally
  spaced versions.
- Lookups: GSUB 1. If the font kerns, only the substituted proportional glyphs should be
  kerned, never the fixed-width defaults.
- Application: discretionary. Default off.
- Script/language sensitivity: generally Japanese fonts only.
- Interactions: mutually exclusive with the other horizontal width features ('chws', 'fwid',
  'halt', 'hwid', 'palt', 'pwid', 'qwid', 'twid'), which are turned off. 'kern' may be on for
  runs where 'pkna' is on (by default or preference, but users must be able to turn it off).
  Because the defaults are not kerned, 'kern' without 'pkna' has no unwanted effect on these
  characters, although an application may still switch 'kern' off when 'pkna' is off.

## 'pnum' - Proportional Figures

- Registered by: Microsoft/Adobe
- Function: replaces tabular (uniform-width) figures with proportional figures. Tabular is
  usually, but not always, the default. Not used in monospaced designs.
- Lookups: GSUB 1 (tabular lining or oldstyle figures to new proportional glyphs), not GPOS
  re-spacing, to simplify kerning and allow the best design for each width.
- Application: discretionary. Default off; when the user switches figure style ('onum' or
  'lnum'), an application may ask whether to apply it as well.
- Script/language sensitivity: none. Interactions: overrides the results of 'tnum'.

## 'pref' - Pre-base Forms

- Registered by: Microsoft
- Function: gives a consonant its pre-base conjoining shape. In Khmer some conjoined consonants
  are always pre-base; in some South Indian scripts a conjoined Ra may be written pre-base,
  below-base or post-base depending on convention, and a font made for the pre-base
  convention uses 'pref'.
- Lookups: GSUB 4 (the sequence that turns a consonant into its pre-base form).
- Application: script-required; applied in the contexts the script's processing defines.
  Whether the lookups fired may be used by the application to decide the later reordering
  of the conjoined consonant glyph. Not exposed to users.
- Script/language sensitivity: Khmer, Myanmar and other Brahmi-derived scripts that may show
  a pre-base Ra.
- Interactions: for Indic scripts the basic-form features are applied in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features run
  after them.

## 'pres' - Pre-base Substitutions

- Registered by: Microsoft
- Function: produces pre-base conjunct forms in Indic scripts; can also select the right
  variant of a pre-base vowel sign.
- Lookups: GSUB 4 (consonants joined by virama to the conjunct ligature); GSUB 5 for
  contextual pre-base matra selection.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts. Interactions: its
  result overrides all other features.

## 'pstf' - Post-base Forms

- Registered by: Microsoft
- Function: gives a consonant its post-base conjoining shape.
- Lookups: GSUB 4.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: South and Southeast Asian scripts with post-base consonant
  forms, such as Gurmukhi, Malayalam and Khmer.
- Interactions: for Indic scripts the basic-form features are applied in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features run
  after them.

## 'psts' - Post-base Substitutions

- Registered by: Microsoft
- Function: replaces a base glyph followed by a post-base glyph with their ligature.
- Lookups: GSUB 4.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts. Interactions: its
  result overrides all other features.

## 'pwid' - Proportional Widths

- Registered by: Adobe
- Function: swaps uniform-width glyphs (usually a full or half em wide) for proportionally
  spaced ones; often used for Latin in CJKV fonts, also for kana in Japanese fonts.
- Lookups: GSUB 1. If the font kerns, only the substituted proportional glyphs are kerned.
- Application: discretionary; default on or off according to the application's market.
- Script/language sensitivity: mostly CJKV fonts, possibly European scripts.
- Interactions: mutually exclusive with the other horizontal width features ('chws', 'fwid',
  'halt', 'hwid', 'palt', 'pkna', 'qwid', 'twid', 'pnum', 'tnum'), which are turned off.
  'kern' may be on with it (by default or preference, user can turn it off); as with 'pkna',
  'kern' without 'pwid' has no unwanted effect on the fixed-width defaults, though an
  application may turn 'kern' off when 'pwid' is off.

## 'qwid' - Quarter Widths

- Registered by: Adobe
- Function: replaces glyphs of other widths with quarter-em-wide glyphs (normally figures and
  some punctuation).
- Lookups: GSUB 1 (quarter-em glyphs) or GPOS 1 (metrics fitted to a quarter em).
- Application: discretionary. Default off.
- Script/language sensitivity: generally CJKV fonts only.
- Interactions: mutually exclusive with the other horizontal width features ('chws',
  'fwid', 'halt', 'hwid', 'palt', 'pkna', 'pwid', 'twid', 'pnum', 'tnum'), which are turned
  off; 'apkn' and 'kern' are disabled on runs where it is applied.

## 'rand' - Randomize

- Registered by: Adobe
- Function: uses several alternate forms to imitate the irregularity of handwriting.
- Lookups: GSUB 3.
- Application: discretionary. The application picks one of the alternates itself, either
  pseudo-randomly or by cycling through the returned alternates each time the character
  occurs; it does not ask the user. Default on when the font supports it.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'rclt' - Required Contextual Alternates

- Registered by: Microsoft
- Function: in given contexts, replaces default glyphs with alternates for better joining or
  other glyph relationships (including spacing). Like 'calt', except that it must not be
  possible to turn 'rclt' off: its substitutions are essential to the font.
- Lookups: GSUB 6.
- Application: script-required; applied in the contexts the script's processing defines,
  taking context before and after into account. Not exposed to users.
- Script/language sensitivity: any script, especially many styles of Arabic.
- Interactions: may be combined with other GSUB features and may override them. In complex
  scripts its lookups come after the basic script and language shaping features.

## 'rkrf' - Rakar Forms

- Registered by: Microsoft
- Function: produces conjoined forms of consonant plus Ra (rakar) in Devanagari and Gujarati,
  where a Ra following a consonant is shown as an alternate form attached to that consonant
  (full or half form).
- Lookups: GSUB 4 (nominal consonant, virama, nominal Ra to the conjoined form).
- Application: script-required; applied in the contexts the script's processing defines,
  before 'half', so that a half form of a consonant-plus-Ra combination can then be derived
  by 'half'. Not exposed to users.
- Script/language sensitivity: Devanagari, Gujarati and other Brahmi-derived scripts.
- Interactions: one of the Indic basic-form features, processed in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features
  run after them.

## 'rlig' - Required Ligatures

- Registered by: Microsoft
- Function: ligatures required for correct display of a script.
- Lookups: GSUB 4; when several sequences share a beginning, the longer ones are stored first.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Arabic and Syriac; possibly other scripts. Interactions: may
  be combined with other GSUB features and may override them; see also 'liga'.

## 'rphf' - Reph Form

- Registered by: Microsoft
- Function: replaces a Ra + halant sequence with the reph form.
- Lookups: GSUB 4 (default Ra plus virama to the reph glyph).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts.
- Interactions: one of the Indic basic-form features, processed in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features
  run after them.

## 'rtbd' - Right Bounds

- Registered by: Adobe
- Function: aligns glyphs at the right end of horizontal lines by their visual right edge
  instead of their origin.
- Lookups: GPOS 1.
- Application: discretionary; applied to the character at the right end of a line in right
  aligned or justified paragraphs. Default off; may be exposed together with 'lfbd' or turned
  on automatically from paragraph settings.
- Script/language sensitivity: none. Interactions: not applied to runs that use fixed-width
  features (such as 'fwid', 'halt', 'hwid', 'qwid', 'twid') or vertical features (such as
  'vert', 'vrt2', 'vpal', 'valt', 'vhal').

## 'rtla' - Right-to-left Alternates

- Registered by: Adobe
- Function: applies glyph variants suited to right-to-left text, other than mirrored forms
  (those are 'rtlm').
- Lookups: must be substitutions; one-to-one GSUB 1 is recommended.
- Application: as described under left-to-right and right-to-left text in the Advanced
  Typographic Extensions chapter. Not exposed to users.
- Script/language sensitivity: right-to-left runs. Interactions: applied in the same pass as
  'ccmp', 'locl' and the other pre-shaping features.

## 'rtlm' - Right-to-left Mirrored Forms

- Registered by: Adobe
- Function: applies mirrored forms for right-to-left text, for characters that the layout
  engine's character-level mirroring step does not already handle (other right-to-left
  variants are 'rtla').
- Lookups: must be substitutions; one-to-one GSUB 1 is recommended.
- Application: as described under left-to-right and right-to-left text in the Advanced
  Typographic Extensions chapter. Not exposed to users.
- Script/language sensitivity: right-to-left runs. Interactions: applied at the same stage as
  'ccmp' and 'locl'.

## 'ruby' - Ruby Notation Forms

- Registered by: Adobe
- Function: substitutes kana glyphs designed for ruby (small annotation glyphs set beside
  kanji to show their reading).
- Lookups: GSUB 1 (default kana to ruby forms).
- Application: discretionary; after the lookups, the application may scale or reposition the
  glyphs from other settings (users may choose scaling and baseline shift). Default off.
- Script/language sensitivity: Japanese. Interactions: overrides any other feature for the
  affected characters.

## 'rvrn' - Required Variation Alternates

- Registered by: Microsoft
- Function: in variable fonts, selects different glyph IDs for particular regions of the
  design space (for example simplified shapes at heavy weights or narrow widths), instead of
  forcing all instances to share one outline. It works together with the FeatureVariations
  table of GSUB.
- Lookups: GSUB 1 only, always combined with a FeatureVariations table. Typically the
  default Feature table for 'rvrn' has no lookups (lookupIndexCount 0), so the default
  instance keeps its default glyphs; FeatureVariations substitutes an alternate Feature table,
  with the needed lookups, under condition sets on axis ranges. Condition boundaries are
  normally placed midway between named-instance values to avoid inconsistent results from
  small numeric differences.
- The default language system of the DFLT script can reference an 'rvrn' feature record whose
  table is substituted for language-independent substitutions; it should be the first 'rvrn'
  feature record. Applications that process 'rvrn' without the rest of OpenType Layout or the
  script and language hierarchy should use the first 'rvrn' feature record.
- Application: mandatory whenever a variable font is used by an implementation that supports
  font variations, even one that does no other OpenType Layout processing. GSUB only (not
  GPOS). Processing: find the ConditionSet in FeatureVariations that matches the current
  instance, use its FeatureTableSubstitution to find the alternate Feature table (details in
  chapter2.md), then run only its GSUB 1 lookups (other lookup types are ignored), replacing
  each covered glyph ID with the lookup's result. Default on and not exposed to users.
- Script/language sensitivity: none.
- Interactions: processed early, right after character-to-glyph mapping and before 'locl',
  complex-script shaping features and discretionary features.

## 'salt' - Stylistic Alternates

- Registered by: Adobe
- Function: replaces default forms with purely aesthetic alternates that fit no clearer
  category; there may be several per glyph.
- Lookups: GSUB 1 and/or GSUB 3 (one lookup of each type, or one GSUB 3 lookup for all);
  alternates shared by several faces are ordered consistently across a family.
- Application: discretionary; with GSUB 3 the application picks an alternate from user choice
  or other criteria (first alternate preferred). Default off.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'sinf' - Scientific Inferiors

- Registered by: Microsoft/Adobe
- Function: swaps lining or oldstyle figures for inferior figures (small, below the
  baseline, for chemical or mathematical notation); may also give inferior letters.
- Lookups: GSUB 1.
- Application: discretionary. Default off.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'size' - Optical size

- Registered by: Adobe. Superseded by the STAT table for optical-size families (see
  stat.md and the OS/2 optical size fields in os2.md).
- Function: records the font's design size (the size it is optimized for), its recommended
  size range, a subfamily identifier grouping fonts that differ only in size range, and a
  name for that subfamily. Sizes are nominal output sizes, independent of magnification or
  resolution.
- Required implementation: a GPOS feature whose Feature table references no lookups. Its
  featureParamsOffset is an offset from the start of the Feature table to five uint16 values.
  If any font of a family uses 'size', every font of the family must implement it (family =
  fonts sharing the Typographic Family name, name ID 16, or the Font Family name, name ID 1,
  when ID 16 is absent).

Parameter array (five uint16 values; the source names them by position):

| Position | Type | Meaning |
|---|---|---|
| 1 | uint16 | Design size in decipoints (720 per inch). Must be non-zero. If there is no recommended range, the remaining four values are 0. |
| 2 | uint16 | Subfamily identifier: fonts sharing a Typographic or Font Family name that differ only in size range share this value; fonts differing in weight or style never share it. 0 means the remaining values are ignored. |
| 3 | uint16 | 'name' ID of the subfamily's menu name; when value 2 is non-zero it must be in 256 to 32767 inclusive. The name entry must have English strings in Windows Unicode and Macintosh Roman encodings and may have localized ones. |
| 4 | uint16 | Smallest size of the recommended range, exclusive, in decipoints. |
| 5 | uint16 | Largest size of the recommended range, inclusive, in decipoints. |

Ranges of a subfamily must not overlap and should generally be contiguous. Example from the
source: design size 18 points, subfamily 3 named by name ID 257, range above 13.9 points up
to and including 24 points.

- Application: when the user sets a size, the application looks for 'size' in the active
  font; without it, default behaviour applies. With it:
  - Design size: an application with size-based tracking applies its tracking curve so that
    there is no adjustment at the design size.
  - Size ranges (when value 2 is non-zero): collect all fonts with the same subfamily value and
    Typographic Family name. If the requested size lies in the current font's range, keep the
    current font; otherwise use the font whose range contains it; if none does, use the font
    whose range is closest; if the size lies exactly between two ranges, use the range with
    the larger values. Adding or removing fonts of a subfamily can reflow text, so applications
    should record which font was used for which text.
- Default on. Script/language sensitivity: none. Interactions: none.

## 'smcp' - Small Capitals

- Registered by: Microsoft/Adobe
- Function: turns lowercase glyphs into small capitals (for "caps and small caps" settings);
  related forms such as oldstyle figures may be included.
- Lookups: GSUB 1. Language-specific case mappings may need separate language systems (for
  example a 'TRK ' language system for Turkish dotted and dotless i, directly or with
  'locl'). Fonts with 'smcp' should also implement 'c2sc'.
- Application: discretionary. For correct language-specific case mapping an application can
  uppercase the text in a temporary buffer (using Unicode special casing data,
  SpecialCasing.txt) and apply 'c2sc'; 'smcp' still applies to characters that have no
  uppercase mapping and to uppercased characters the font's 'c2sc' does not cover. Default
  off.
- Script/language sensitivity: bicameral scripts such as Latin, Greek, Cyrillic and Armenian.
  Interactions: may be combined with other GSUB features and may override them; see 'c2sc'.

## 'smpl' - Simplified Forms

- Registered by: Adobe
- Function: swaps traditional Chinese or Japanese forms for simplified forms.
- Lookups: GSUB 1 (several traditional forms may map to one simplified form).
- Application: discretionary. The effect equals a change of character codes; the application
  should store the new codes besides the original ones. Default off (a user preference may
  make it the default).
- Script/language sensitivity: Chinese and Japanese only.
- Interactions: mutually exclusive with most features, which are turned off; 'palt', 'vert'
  and 'vrt2' may still be applied. 'trad' and 'tnam' are mutually exclusive with 'smpl' and
  override its results.

## 'ss01' - 'ss20' - Stylistic Set 1 - Stylistic Set 20

- Registered by: Tiro Typeworks
- Function: each feature selects a set of stylistic alternatives covering part of the
  character set (for example a full alternate lowercase), designed to work together. Not
  limited to GSUB: a stylistic set may also supply alternate mark positioning or kerning.
- Lookups: GSUB 1 per 'ssXX' feature, from default forms to the set's variants; a font may
  also map variants of other sets to this set's variants (for example 'ss03' mapping 'ss01'
  and 'ss02' variants as well as defaults).
- Feature parameters: featureParamsOffset of the Feature table is 0 or the offset of this
  table:

| Type | Name | Description |
|---|---|---|
| uint16 | Version | 0. A minor version: more fields may be appended later. |
| uint16 | uiLabelNameID | 'name' ID of the UI label for the stylistic set; expected (not required) in 256 to 32767; English should be present as a fallback for localized strings. |

- Application: discretionary. The application enumerates the 'ss01'-'ss20' features present
  and offers a selection UI; any combination may be on at once. Default off.
- Script/language sensitivity: none.
- Interactions: may be combined with other GSUB or GPOS features and may override them; sets
  are not mutually exclusive (they may affect different glyphs or combine). Lookup order is
  the font's responsibility when users apply glyph-level features such as 'salt' afterwards.

## 'ssty' - Math Script-style Alternates

- Registered by: Microsoft
- Function: glyph variants better suited to math subscripts and superscripts. They are not
  scaled or moved in the font; the math engine scales and positions them, and the font may
  assume MathConstants.scriptPercentScaleDown and scriptScriptPercentScaleDown as the scale
  factors.
- Parameter: the script level, 1 for first-level scripts and 2 for scripts on scripts (only the
  first two alternates are currently used). Glyphs the feature does not cover keep their
  original form in scripts.
- Lookups: GSUB 3 with alternate 1 or 2 per level; GSUB 1 when no second-level alternates
  exist. Glyphs without script forms may be left out.
- Application: required for math layout; applied to individual glyphs under the math layout
  handler, choosing the first or second alternate by nesting level. Not exposed to users.
- Script/language sensitivity: math formula layout. Interactions: none.

## 'stch' - Stretching Glyph Decomposition

- Registered by: Microsoft
- Function: lets an enclosing character such as U+070F SYRIAC ABBREVIATION MARK stretch over
  the text it encloses. The character's glyph is decomposed into an odd number of glyphs:
  those at odd positions are fixed points, spaced equally from the beginning of the
  enclosed text to its end, and those at even positions repeat to fill the gaps. The first and last
  glyphs may be ordinary glyphs with width at the baseline or marks; all the others must be
  mark glyphs (with width).
- Lookups: GSUB 2 (default glyph to an odd-length sequence).
- Application: applied to characters that need stretching. If the glyph is covered, the
  application takes the substituted sequence, moves its last glyph after the end of the
  glyphs to be enclosed, inserts the remaining glyphs before them, spreads the odd-numbered
  glyphs evenly over the enclosed width and repeats the even-numbered glyphs to fill the
  space between them. Not exposed to users.
- Script/language sensitivity: none. Interactions: none.

## 'subs' - Subscript

- Registered by: Microsoft/Adobe
- Function: presents subscript forms.
- Lookups: GSUB 1 (single or contextual) for the subscript glyph, then if needed GPOS 1 or
  GPOS 2, or a contextual lookup calling them, to move it.
- Application: discretionary. For some characters the effect equals a change of character
  code; then the application should store the new code besides the original. Default off.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'sups' - Superscript

- Registered by: Microsoft/Adobe
- Function: replaces figures with superior figures (footnote references) and lowercase letters
  with superior letters (abbreviated French titles).
- Lookups: GSUB 1.
- Application: discretionary. For some characters the effect equals a change of character
  code; then the application should store the new code besides the original. Default off.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'swsh' - Swash

- Registered by: Microsoft/Adobe
- Function: replaces default glyphs with swash forms; a character may have several.
- Lookups: GSUB 1 and/or GSUB 3 (one of each, or one GSUB 3 lookup for all); with several
  swash styles the forms of each character are ordered consistently.
- Application: discretionary; with GSUB 3 the application picks an alternate from user choice
  or other criteria (first alternate preferred). Default off.
- Script/language sensitivity: not used for ideographic scripts. Interactions: may be
  combined with other GSUB features and may override them.

## 'titl' - Titling

- Registered by: Adobe
- Function: replaces default glyphs with forms designed for titles (possibly all capitals,
  larger on the body, tuned for large sizes).
- Lookups: GSUB 1.
- Application: discretionary. Default off.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'tjmo' - Trailing Jamo Forms

- Registered by: Microsoft
- Function: substitutes the form of a Hangul trailing consonant jamo used inside a jamo
  cluster.
- Lookups: GSUB 1, or a contextual lookup calling a GSUB 1 lookup.
- Application: script-required for Hangul; applied in the contexts the script's processing
  defines. Not exposed to users.
- Script/language sensitivity: Hangul, especially with Unicode conjoining jamo.
  Interactions: its result overrides all other features.

## 'tnam' - Traditional Name Forms

- Registered by: Adobe
- Function: replaces simplified Japanese kanji with traditional forms, limited to those
  proper in personal names (up to about 205 glyphs in some fonts); otherwise like 'trad'.
- Lookups: GSUB 1. The application records simplified forms produced by 'smpl'; for those,
  applying 'tnam' undoes the earlier substitution.
- Application: discretionary. The effect equals a change of character codes; the application
  should store the new code besides the original. Default off.
- Script/language sensitivity: Japanese only.
- Interactions: some affected characters may also be affected by 'palt'. 'trad' and 'tnam'
  are mutually exclusive with 'smpl' and override its results.

## 'tnum' - Tabular Figures

- Registered by: Adobe
- Function: replaces proportional figures with tabular (uniform-width) figures. Tabular is
  usually, but not always, the default. Not used in monospaced designs.
- Lookups: GSUB 1 (proportional lining or oldstyle figures to new tabular glyphs), not GPOS
  re-spacing.
- Application: discretionary. Default off; when the user switches figure style ('onum' or
  'lnum'), an application may ask whether to apply it as well.
- Script/language sensitivity: none. Interactions: overrides the results of 'pnum'.

## 'trad' - Traditional Forms

- Registered by: Adobe
- Function: swaps simplified Chinese hanzi or Japanese kanji for traditional forms.
- Lookups: GSUB 1 and/or GSUB 3 (one of each, or one GSUB 3 lookup for all); alternates
  shared by several faces are ordered consistently across a family.
- Application: discretionary. The application records simplified forms produced by 'smpl'
  and, for those, undoes the substitution; otherwise it offers the alternates (remembering
  the user's last choice for that character, else taking the first as preferred). The effect
  equals a change of character codes; the application should store the new code besides the
  original. Default off.
- Script/language sensitivity: Chinese and Japanese only.
- Interactions: some affected characters may also be affected by 'palt'. 'trad' and 'tnam'
  are mutually exclusive with 'smpl' and override its results.

## 'twid' - Third Widths

- Registered by: Adobe
- Function: replaces glyphs of other widths with third-em-wide glyphs (normally figures and
  some punctuation).
- Lookups: GSUB 1 (third-em glyphs) or GPOS 1 (metrics fitted to a third of an em).
- Application: discretionary. Default off.
- Script/language sensitivity: generally CJKV fonts only.
- Interactions: mutually exclusive with the other horizontal width features ('chws', 'fwid',
  'halt', 'hwid', 'palt', 'pkna', 'pwid', 'qwid', 'pnum', 'tnum'), which are turned off;
  'apkn' and 'kern' are disabled on runs where it is applied.
