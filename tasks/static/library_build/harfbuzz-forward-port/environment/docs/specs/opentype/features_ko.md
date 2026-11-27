# Registered Features k-o
Source: Registered features, k-o (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/features_ko
These notes restate the source's structures and rules; where they differ, the source governs.

This file covers the registered feature tags from 'kern' to 'ornm', in the source's order.
featuretags.md lists every registered tag; the other ranges are in features_ae.md,
features_fj.md, features_pt.md and features_uz.md. Lookup types are written "GSUB n" or
"GPOS n" (see gsub.md and gpos.md). "Discretionary", "script-required" and "default on/off"
are used as defined in features_ae.md.

## 'kern' - Kerning

- Registered by: Microsoft/Adobe
- Function: adjusts the space between particular glyph combinations in horizontal layout for
  optically even spacing. Besides horizontal adjustment it can provide cross-stream (y)
  kerning, placement changes independent of the advance, and size-specific values through
  device tables. Its lookups may act on runs of more than two glyphs.
- Not for vertical layout ('vkrn' is the vertical feature). It is for spacing the user may
  override; spacing a script requires and users must not control belongs in 'dist'.
- Lookups: GPOS 2 or GPOS 8 (xPlacement, xAdvance, yPlacement, yAdvance), as class-pair tables
  or individual pairs; longer sequences (triplets and more) may be ordered to take
  precedence over pair values. With GPOS 2, valueFormat2 should be 0 so that matching
  resumes at the second glyph and every glyph can be the first of a pair; otherwise only
  every other pair is kerned.
- Font data: fixed-width glyphs should not be kerned unless another feature makes them
  proportional; in new fonts, kerning of glyphs made proportional by 'palt' belongs in 'apkn'.
- Application (defaults): discretionary, and default on in most horizontal layout; users must
  be able to turn it off for a run, and may add manual adjustments. CJK exception: for a
  font that implements 'palt', 'kern' is not enabled by default on glyphs covered by 'palt'
  lookups unless 'palt' is on. An application can find those glyphs from the coverage of
  the 'palt' lookups, or treat characters with East_Asian_Width Wide or Fullwidth (UAX #11)
  as fixed width. If the font implements both 'palt' and 'apkn', 'kern' can be on by
  default for all horizontal text; if it implements 'kern' and not 'palt', 'kern' is on by
  default for all horizontal text.
- Script/language sensitivity: none.
- Interactions: not combined with fixed-width features ('chws', 'fwid', 'halt', 'hwid',
  'qwid', 'twid', 'tnum'); when any of those is on for a run, 'kern' is off. It may be on,
  by default or by preference, with 'pkna' and 'pwid', and with 'palt' as described above.
  When it is turned on automatically because a proportional-width feature is on, users must
  still be able to turn it off.

## 'lfbd' - Left Bounds

- Registered by: Adobe
- Function: aligns glyphs at the left end of horizontal lines by their visual left edge
  instead of their origin.
- Lookups: GPOS 1 (placement and advance changes).
- Application: discretionary; applied to the character at the left end of a line in left
  aligned or justified paragraphs. Default off; may be exposed together with 'rtbd' or
  turned on automatically from paragraph settings.
- Script/language sensitivity: none. Interactions: not applied to glyphs affected by
  fixed-width features (such as 'fwid', 'halt', 'hwid', 'qwid', 'twid') or vertical
  features (such as 'vert', 'vrt2', 'vpal', 'valt', 'vhal').

## 'liga' - Standard Ligatures

- Registered by: Microsoft/Adobe
- Function: replaces glyph sequences with the ligatures the designer intends for normal use.
- Lookups: GSUB 4; ligatures with more components must come before those with fewer.
- Application: discretionary, but default on (it is critical in some contexts).
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'ljmo' - Leading Jamo Forms

- Registered by: Microsoft
- Function: substitutes the form of a Hangul leading consonant jamo used inside a jamo
  cluster.
- Lookups: GSUB 1, or a contextual lookup that calls a GSUB 1 lookup.
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Hangul, especially when Unicode conjoining jamo are used.
  Interactions: its result overrides all other features.

## 'lnum' - Lining Figures

- Registered by: Adobe (newer, revised description)
- Function: changes non-lining figures to lining figures.
- Lookups: GSUB 1 (digits and number separators to lining forms, including the default figures
  when they are non-lining).
- Application: discretionary. Default off; the user toggles between lining and oldstyle sets.
  It is separate from the width features 'pnum' and 'tnum' (an application may ask whether a
  width change is also wanted).
- Script/language sensitivity: none. Interactions: mutually exclusive with 'onum'.

## 'locl' - Localized Forms

- Registered by: Tiro Typeworks/Adobe
- Function: substitutes language-specific variants of letters for the default forms (for
  example Bulgarian and Serbian Cyrillic forms that differ from Russian ones).
- Lookups: GSUB 1, one-to-one; each language system may have its own lookups.
- Application: always applied. The language of the text (from language tags or similar
  metadata) selects the language system in GSUB and GPOS, which in turn selects the
  appropriate lookups. Users control it only through language settings or a choice of the
  font's language systems.
- Script/language sensitivity: none (the language system choice does the work).
  Interactions: may be combined with any feature.

## 'ltra' - Left-to-right Alternates

- Registered by: Adobe
- Function: applies glyph variants suited to left-to-right text, other than mirrored forms
  (those are 'ltrm').
- Lookups: must be substitutions; one-to-one GSUB 1 is recommended.
- Application: as described under left-to-right and right-to-left text in the Advanced
  Typographic Extensions chapter. Not exposed to users.
- Script/language sensitivity: left-to-right runs. Interactions: applied in the same pass as
  'ccmp', 'locl' and the other pre-shaping features.

## 'ltrm' - Left-to-right Mirrored Forms

- Registered by: Adobe
- Function: applies mirrored forms suited to left-to-right text (other left-to-right variants
  are 'ltra').
- Lookups: must be substitutions; one-to-one GSUB 1 is recommended.
- Application: as described under left-to-right and right-to-left text in the Advanced
  Typographic Extensions chapter. Not exposed to users.
- Script/language sensitivity: left-to-right runs. Interactions: applied at the same stage as
  'ccmp' and 'locl'.

## 'mark' - Mark Positioning

- Registered by: Microsoft
- Function: positions mark glyphs relative to base glyphs.
- Lookups: GPOS 4 (mark-to-base) or GPOS 5 (mark-to-ligature).
- Application: required for correct layout; always applied. Not exposed to users.
- Script/language sensitivity: none. Interactions: none.

## 'med2' - Medial Forms #2

- Registered by: Microsoft
- Function: Syriac only: selects the form of Alaph inside a word when the preceding base
  character joins to it.
- Lookups: GSUB 1.
- Application: script-required for Syriac; always applied to Alaph when the preceding base is
  a joining character. Not exposed to users.
- Script/language sensitivity: Syriac only. Interactions: may be combined with other GSUB
  features and may override them; see 'init' and 'fina'.

## 'medi' - Medial Forms

- Registered by: Microsoft/Adobe (description revised in 2016)
- Function: replaces the glyph of a joining character with its medial form in a medial
  context. Applies to characters whose Unicode Joining_Type is Dual_Joining (values from
  ArabicShaping.txt).
- Lookups: usually GSUB 1; contextual GSUB 5, 6 or 8 may also be used.
- Application: script-required for cursively connected scripts; the application's joining
  analysis (Joining_Type plus factors such as control characters) decides which glyphs get
  'init', 'medi', 'fina' or 'isol'. Not exposed to users.
- Script/language sensitivity: any script whose Joining_Type values are listed explicitly in
  ArabicShaping.txt. Interactions: may be combined with other GSUB features and may override
  them; see 'fina', 'init', 'isol'.

## 'mgrk' - Mathematical Greek

- Registered by: Adobe
- Function: replaces typographic Greek forms with the forms used in mathematical notation.
- Lookups: GSUB 1.
- Application: discretionary. The effect equals a change of character codes; the application
  should store the new codes besides the original ones. Default off in most applications,
  possibly on in math-oriented ones.
- Script/language sensitivity: Greek characters. Interactions: may be combined with other
  GSUB features and may override them.

## 'mkmk' - Mark to Mark Positioning

- Registered by: Microsoft
- Function: positions marks relative to other marks; needed in many non-Latin scripts such as
  Arabic.
- Lookups: GPOS 6 (mark-to-mark).
- Application: required for correct layout; always applied. Not exposed to users.
- Script/language sensitivity: none. Interactions: none.

## 'mset' - Mark Positioning via Substitution

- Registered by: Microsoft
- Function: legacy: positions Arabic marks in Windows 95-era fonts by substituting a mark
  glyph whose outline is already drawn at the right position. Not recommended for new fonts.
- Lookups: those legacy fonts used GSUB 5.
- Application: in legacy fonts that have it, it is required for correct display and is
  applied to the whole run. Not exposed to users.
- Script/language sensitivity: legacy Arabic fonts only. Interactions: may be combined with
  other GSUB features and may override them.

## 'nalt' - Alternate Annotation Forms

- Registered by: Adobe
- Function: replaces default glyphs with notational forms (glyphs in circles, squares,
  parentheses, diamonds, rounded boxes and so on), or one such form with another.
- Lookups: GSUB 1 for one-to-one cases, GSUB 3 where a choice is needed (one lookup of each
  type, or one GSUB 3 lookup for all). Alternate order should be consistent within the font
  and across the family.
- Application: discretionary; with GSUB 3 the application selects an alternate from user
  choice or other criteria, may remember the chosen position for next time, and otherwise
  treats the first alternate as preferred. Default off.
- Script/language sensitivity: mostly CJKV fonts, also European scripts.
- Interactions: mutually exclusive with most features, which are turned off; 'vert' and
  'vrt2' may still be applied.

## 'nlck' - NLC Kanji Forms

- Registered by: Adobe Systems Inc.
- Function: gives access to the glyph shapes defined in 2000 by Japan's National Language
  Council for a number of JIS characters.
- Lookups: GSUB 1 (non-NLC glyph to NLC glyph).
- Application: discretionary. Default off.
- Script/language sensitivity: kanji in Japanese only.
- Interactions: mutually exclusive with 'jp78', 'jp83', 'jp90' and similar features;
  combinable with 'palt', 'vpal', 'vert' and 'vrt2'.

## 'nukt' - Nukta Forms

- Registered by: Microsoft
- Function: yields the nukta forms used in Indic scripts.
- Lookups: GSUB 4 (consonant plus nukta to the nukta form).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts.
- Interactions: one of the Indic basic-form features, processed in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features
  run after them.

## 'numr' - Numerators

- Registered by: Adobe
- Function: replaces figures before a slash with numerator figures, and the slash with the
  fraction slash.
- Lookups: GSUB 1 (digits and number separators to numerator glyphs; U+002F SOLIDUS glyph to
  the U+2044 FRACTION SLASH glyph).
- Application: applied automatically by the application as part of 'frac' (see
  features_fj.md, 'frac'); no direct user control needed.
- Script/language sensitivity: none. Interactions: supports 'frac'; may be combined with
  other GSUB features and may override them.

## 'onum' - Oldstyle Figures

- Registered by: Microsoft/Adobe
- Function: changes default or lining figures to oldstyle figures.
- Lookups: GSUB 1 (digits and number separators to oldstyle forms, including the default
  figures when they are non-lining).
- Application: discretionary. Default off; separate from the width features 'pnum' and
  'tnum'.
- Script/language sensitivity: none. Interactions: overrides the results of 'lnum'.

## 'opbd' (DEPRECATED) - Optical Bounds

- Registered by: Adobe
- Function: aligns glyphs by their visual edges (left and right in horizontal setting, top
  and bottom in vertical setting) instead of their origins.
- Lookups: GPOS 1, in separate lookups for the features of each line edge.
- Application: discretionary. An implementation uses 'lfbd' automatically for glyphs at the
  left end of horizontal lines and 'rtbd' for glyphs at the right end. It changes line
  length, which line breaking and justification must account for. Default on.
- Script/language sensitivity: none. Interactions: not applied to glyphs using fixed-width
  features (such as 'fwid', 'halt', 'hwid', 'qwid', 'twid') or vertical features (such as
  'vert', 'vrt2', 'vpal', 'valt', 'vhal'); uses 'lfbd' and 'rtbd'.

## 'ordn' - Ordinals

- Registered by: Adobe
- Function: replaces letters after figures with ordinal forms. The numero sign (U+2116) is
  also reached through this feature, as a ligature, without the figure context.
- Lookups: GSUB 6 (lowercase letters to ordinal forms in context) and GSUB 4 ("No" to the
  numero ligature).
- Application: discretionary; surrounding context is considered when the lookups are
  processed. The effect can amount to a change of character codes; the application should
  store the new codes besides the original ones. Default off.
- Script/language sensitivity: mostly Latin. Interactions: may be combined with other GSUB
  features and may override them.

## 'ornm' - Ornaments

- Registered by: Adobe
- Function: gives access to ornament glyphs (fleurons, dingbats, border elements) in two ways:
  the bullet character can be replaced by any ornament, or specific ASCII characters can be
  replaced by the ornaments assigned to them.
- Lookups: GSUB 3 (all ornaments as alternates of the U+2022 BULLET glyph) and/or GSUB 1
  (alphanumeric glyphs to assigned ornaments); a font may use one lookup of each type or a
  single GSUB 3 lookup. Alternates shared by several faces should be ordered consistently
  across the family.
- Application: discretionary. The application checks whether the selected text is U+2022
  BULLET or alphanumeric characters: for the bullet it offers the alternates for selection
  (remembering the last choice as the next default, else taking the first as preferred);
  for alphanumerics it applies the substitution directly. Default off.
- Script/language sensitivity: none. Interactions: mutually exclusive with all other GSUB
  features, which are turned off when it is on.
