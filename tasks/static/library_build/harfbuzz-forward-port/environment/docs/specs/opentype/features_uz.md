# Registered Features u-z
Source: Registered features, u-z (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/features_uz
These notes restate the source's structures and rules; where they differ, the source governs.

This file covers the registered feature tags from 'unic' to 'zero', in the source's order.
featuretags.md lists every registered tag; the other ranges are in features_ae.md,
features_fj.md, features_ko.md and features_pt.md. Lookup types are written "GSUB n" or
"GPOS n" (see gsub.md and gpos.md). "Discretionary", "script-required" and "default on/off"
are used as defined in features_ae.md.

## 'unic' - Unicase

- Registered by: Tiro Typeworks / Emigre
- Function: maps both uppercase and lowercase letters to one mixed set of lowercase and
  small-capital (or purpose-made unicase) forms, giving a single-case alphabet; may include
  special figures. Which letters change depends on the design.
- Lookups: GSUB 1.
- Application: discretionary. Default off.
- Script/language sensitivity: bicameral scripts such as Latin, Greek, Cyrillic and Armenian.
  Interactions: may be combined with other GSUB features and may override them.

## 'valt' - Alternate Vertical Metrics

- Registered by: Adobe
- Function: in vertical setting, shifts full-width Latin, Greek or Cyrillic glyphs of East
  Asian fonts (upright, on a common horizontal baseline) so they are visually centred in
  full-height metrics.
- Lookups: GPOS 1 (yPlacement). The same result is better obtained through vertical origins:
  topSideBearing values in 'vmtx' and, for CFF or CFF2 fonts, vertOriginY in VORG. Fonts that
  have 'vmtx' or VORG tables should not implement 'valt'.
- Application: applied to runs of the relevant scripts in vertical layout; default on in
  vertical setting.
- Script/language sensitivity: scripts with vertical writing modes.
- Interactions: mutually exclusive with the other glyph-height features (such as 'vhal' and
  'vpal'), which are turned off; 'vapk' and 'vkrn' are disabled on runs where it is applied.

## 'vapk' - Kerning for Alternate Proportional Vertical Metrics

- Registered by: Adobe/Microsoft
- Function: in vertical layout, kerns glyphs whose advance heights are fixed by default but
  that 'vpal' has made proportional.
- Lookups: GPOS, normally GPOS 2. Single and pair adjustments add up, so the order of these
  lookups relative to GPOS 1 or 2 lookups of 'vpal' and similar features does not matter.
- Font data: glyphs that 'vpal' can make proportional should be kerned only through 'vapk',
  not 'vkrn'. A font implementing 'vapk' should also implement 'vpal'.
- Application: default off. It may be on for a run only if 'vpal' is on for that run (it may
  then be switched on automatically, with a way for users to turn it off while 'vpal' stays
  on). When 'vpal' is turned off for a run, 'vapk' must be turned off as well. Because it
  only acts on glyphs that 'vpal' makes proportional, it can be disabled on runs without
  'vpal' without inspecting its lookups.
- Script/language sensitivity: mainly CJK fonts.

## 'vatu' - Vattu Variants

- Registered by: Microsoft
- Function: inside an Indic conjunct, replaces two glyphs with one ligature: either a base
  consonant plus the vattu (below-base) form of the consonant that conjoins with it, or a
  consonant half form plus such a vattu form.
- Lookups: GSUB 4. They act on glyphs produced by 'blwf' (which derives the nominal vattu
  form) and, for half-form plus vattu ligatures, by 'half'; 'vatu' only replaces the nominal
  vattu form plus base or half form with a ligature. Fonts that use 'rkrf' do not need
  'vatu'.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Devanagari and other Indic or Brahmi-derived scripts.
- Interactions: used together with 'nukt', 'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half',
  'pstf' and 'cjct' to derive the required forms; the application orders them suitably, and
  discretionary features run after them.

## 'vchw' - Vertical Contextual Half-width Spacing

- Registered by: Adobe/W3C
- Function: contextually narrows glyphs with full-em heights onto half-em vertical heights,
  approximating layouts such as JLREQ while keeping monospaced alignment; unlike 'vhal', the
  adjustment depends on context.
- Lookups: GPOS 2 or GPOS 8 (xPlacement, xAdvance, yPlacement, yAdvance), as class-pair tables
  or individual pairs, optionally longer sequences ordered to take precedence. With GPOS 2,
  valueFormat2 should be 0 so that matching resumes at the second glyph and every glyph can
  be the first of a pair.
- Application: not used when the layout engine itself implements CLREQ, JLREQ or KLREQ;
  otherwise always applied, and default on, in vertical CJK layout.
- Script/language sensitivity: mostly CJKV fonts.
- Interactions: mutually exclusive with the other glyph-height features (such as 'valt',
  'vhal', 'vpal'), which are turned off; 'vapk' and 'vkrn' are disabled on runs where it is
  applied. Horizontal counterpart: 'chws'.

## 'vert' - Vertical Alternates

- Registered by: Microsoft/Adobe
- Function: replaces default glyphs with forms for upright presentation in vertical writing
  (rotated, shifted or with reordered components), for the minority of East Asian characters
  whose upright glyph must change in vertical text. For example the glyph of U+3041
  HIRAGANA LETTER SMALL A moves up and right, and U+3343 SQUARE MAIKURO gets its katakana
  components reordered top to bottom, then right to left.
- Lookups: GSUB 1.
- Application: applied to runs of the relevant scripts in vertical layout; default on in
  vertical writing mode.
- Script/language sensitivity: scripts with vertical writing modes.
- Interactions: 'vert' (glyphs shown upright) and 'vrtr' (glyphs shown sideways) work as a
  pair for engines that rotate sideways runs themselves, as in UTR #50; they never apply to
  the same glyph, so they do not interact. Engines that rely on the font for pre-rotated
  sideways glyphs use 'vrt2' instead of 'vert' and 'vrtr'; 'vert' must never be combined with
  'vrt2' but may be combined with any other feature.

## 'vhal' - Alternate Vertical Half Metrics

- Registered by: Adobe
- Function: re-spaces glyphs with full-em heights onto half-em heights. Unlike 'valt', it
  changes the advance, not only the position.
- Lookups: GPOS 1 (xPlacement, xAdvance, yPlacement, yAdvance).
- Application: discretionary. Generally default off; applications following JLREQ or similar
  CJK layout rules either turn it on by default or apply it selectively to brackets, punctuation,
  quotation marks and similar characters.
- Script/language sensitivity: CJKV fonts only.
- Interactions: mutually exclusive with the other glyph-height features (such as 'valt' and
  'vpal'), which are turned off; 'vapk' and 'vkrn' are turned off on runs where it is applied.
  Horizontal counterpart: 'halt'.

## 'vjmo' - Vowel Jamo Forms

- Registered by: Microsoft
- Function: substitutes the form of a Hangul vowel jamo used inside a jamo cluster.
- Lookups: GSUB 1, or a contextual lookup calling a GSUB 1 lookup.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Hangul, especially with Unicode conjoining jamo.
  Interactions: its result overrides all other features.

## 'vkna' - Vertical Kana Alternates

- Registered by: Adobe
- Function: swaps standard kana for forms designed only for vertical writing (better fit
  and colour). With 'hkna' it lets fonts for both directions pick kana variants per direction;
  advance widths do not change.
- Lookups: GSUB 1 (standard full-width kana to vertical forms).
- Application: discretionary. Default off.
- Script/language sensitivity: hiragana and katakana only. Interactions: horizontal features
  (such as 'kern') do not apply together with it.

## 'vkrn' - Vertical Kerning

- Registered by: Adobe
- Function: adjusts the space between particular glyph combinations in vertical layout. It can
  also provide cross-stream (x) kerning, placement changes independent of the advance, and
  size-specific values through device tables; its lookups may act on runs of more than two
  glyphs. For spacing the user may override; not for horizontal layout ('kern' is the
  horizontal feature).
- Lookups: GPOS 2 or GPOS 8, as class-pair tables or individual pairs; longer sequences may be
  ordered to take precedence. With GPOS 2, valueFormat2 should be 0 so that every glyph can
  be the first of a pair.
- Font data: fixed-height glyphs should not be kerned unless another feature makes their
  vertical metrics proportional; in new fonts, kerning of glyphs made proportional by 'vpal'
  belongs in 'vapk'.
- Application (defaults): discretionary, and default on in most vertical layout; users must
  be able to turn it off for a run, and may add manual adjustments. CJK exception: for a font
  that implements 'vpal', 'vkrn' is not enabled by default on glyphs covered by 'vpal' lookups
  unless 'vpal' is on; those glyphs can be found from the coverage of the 'vpal' lookups, or
  approximated by East_Asian_Width Wide or Fullwidth characters (UAX #11). If the font
  implements both 'vpal' and 'vapk', 'vkrn' can be on by default for all vertical text; if it
  implements 'vkrn' but not 'vpal', 'vkrn' is on by default for all vertical text.
- Script/language sensitivity: none.
- Interactions: not combined with fixed-height features ('valt', 'vchw', 'vhal'); when any of
  those is on for a run, 'vkrn' is off. May be used with 'vpal' as described above. When it is
  turned on automatically because a proportional feature is on, users must still be able to
  turn it off.

## 'vpal' - Proportional Alternate Vertical Metrics

- Registered by: Adobe
- Function: re-spaces glyphs with full-em heights onto individual, roughly proportional
  heights. Unlike 'valt', it changes the advance.
- Lookups: GPOS 1 (xPlacement, xAdvance, yPlacement, yAdvance). If the font also kerns
  vertically, glyphs affected by 'vpal' should be kerned through 'vapk', not 'vkrn' ('vkrn'
  remains for glyphs that are proportional by default).
- Application: discretionary. Default off.
- Script/language sensitivity: mostly CJKV fonts.
- Interactions: mutually exclusive with the other glyph-height features ('valt', 'vchw',
  'vhal'), which are turned off. When 'vpal' is on, kerning features may be on for the run;
  when it is off, 'vapk' and 'vkrn' must not act on glyphs covered by 'vpal' lookups.
  Horizontal counterpart: 'palt'.

## 'vrt2' - Vertical Alternates and Rotation

- Registered by: Adobe
- Function: swaps some fixed-width (half, third or quarter width) or proportional glyphs,
  mostly Latin or katakana, for forms rotated 90 degrees clockwise for vertical writing. It
  covers a superset of the glyphs covered by 'vert'.
- Lookups: GSUB 1 (horizontal forms to rotated forms); it should be the last substitution in
  the font. Some implementations require, for CFF-outline fonts used vertically, that 'vrt2'
  exist in GSUB as exactly one GSUB 1 lookup with lookupFlag 0 and a single subtable; such
  implementations ignore 'vert'.
- Font data: a rotated glyph's top side bearing and vertical advance in 'vmtx' equal the left
  side bearing and horizontal advance of the upright glyph in 'hmtx'; its horizontal advance
  is arbitrary (head.unitsPerEm is one choice). For kerning to match, 'vkrn' values between
  rotated glyphs should equal the 'kern' values between their upright counterparts.
- Application: discretionary for vertical runs; default on in vertical writing mode, with a
  user override.
- Script/language sensitivity: scripts with vertical writing modes.
- Interactions: overrides 'vert', which it includes; may be combined with any other feature.

## 'vrtr' - Vertical Alternates for Rotation

- Registered by: Adobe/Microsoft/W3C
- Function: replaces default glyphs with forms meant to be shown sideways in vertical writing
  (glyphs of other scripts, some Western punctuation). The substitutes differ from the
  defaults, for example by shift or shape, once the layout engine rotates them 90 degrees
  clockwise.
- Lookups: GSUB 1.
- Application: applied to the relevant characters in vertical layout; always default on for
  runs set sideways in vertical writing mode.
- Script/language sensitivity: any script set in vertical writing mode.
- Interactions: paired with 'vert' for engines that rotate sideways runs themselves (UTR #50);
  the two never apply to the same glyph. Engines relying on pre-rotated glyphs use 'vrt2'
  instead of 'vrtr' and 'vert'; 'vrtr' must never be combined with 'vrt2' but may be combined
  with any other feature.

## 'zero' - Slashed Zero

- Registered by: Adobe
- Function: replaces the default zero with a slashed zero, to tell 0 from O apart (especially
  in condensed designs).
- Lookups: GSUB 1 (lining zero to slashed zero).
- Application: discretionary; best kept as a user preference that toggles between the two
  forms. Default off in most applications.
- Script/language sensitivity: the digit zero only. Interactions: applies only to lining
  figures, so it is mutually exclusive with oldstyle figure features such as 'onum'.
