# Registered Features f-j
Source: Registered features, f-j (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/features_fj
These notes restate the source's structures and rules; where they differ, the source governs.

This file covers the registered feature tags from 'falt' to 'jp04', in the source's order.
featuretags.md lists every registered tag; the other ranges are in features_ae.md,
features_ko.md, features_pt.md and features_uz.md. Lookup types are written "GSUB n" or
"GPOS n" (see gsub.md and gpos.md). "Discretionary", "script-required" and "default on/off"
are used as defined in features_ae.md.

## 'falt' - Final Glyph on Line Alternates

- Registered by: Microsoft
- Function: replaces the last glyph of a line with an alternate of different width designed
  to help justification.
- Lookups: GSUB 1 (line-final glyphs, in isolated or final form, to alternates). May be
  combined with JSTF extension or shrinkage modifications (see jstf.md).
- Application: applied to line-final glyphs of justified text, as a justification algorithm
  or the user decides. It can change line length, which line breaking and justification
  must account for. Default on or off per user preference.
- Script/language sensitivity: any cursive script. Interactions: applied last, after all
  other features have been applied to the run.

## 'fin2' - Terminal Forms #2

- Registered by: Microsoft
- Function: Syriac only: selects the form of Alaph at the end of a word when the preceding
  base character does not join to it and is not Dalath, Rish or dotless Dalath-Rish.
- Lookups: GSUB 1 (default form to final form).
- Application: script-required for Syriac; always applied to Alaph when the preceding base is
  non-joining and is not Dalath, Rish or dotless Dalath-Rish. Not exposed to users.
- Script/language sensitivity: Syriac only. Interactions: may be combined with other GSUB
  features and may override them; see 'init' and 'fina'.

## 'fin3' - Terminal Forms #3

- Registered by: Microsoft
- Function: Syriac only: selects the form of word-final Alaph when the preceding base
  character is Dalath, Rish or dotless Dalath-Rish.
- Lookups: GSUB 5 (as the source states).
- Application: script-required for Syriac; always applied to word-final Alaph after Dalath,
  Rish or dotless Dalath-Rish. Not exposed to users.
- Script/language sensitivity: Syriac only. Interactions: may be combined with other GSUB
  features and may override them; see 'init' and 'fina'.

## 'fina' - Terminal Forms

- Registered by: Microsoft/Adobe (description revised in 2016)
- Function: replaces the glyph of a joining character with its final form when it occurs in
  a final context. It applies to characters whose Unicode Joining_Type is:
  - Right_Joining, in a right-to-left script;
  - Left_Joining, in a left-to-right script;
  - Dual_Joining.
  Joining_Type values come from the UCD file ArabicShaping.txt.
- Lookups: usually GSUB 1 (default form to final form); contextual GSUB 5, 6 or 8 may also be
  used.
- Application: script-required for cursively connected scripts. The application analyses
  the character string, using Joining_Type and other factors such as control characters, and
  decides which glyphs get 'init', 'medi', 'fina' or 'isol'. Not exposed to users.
- Script/language sensitivity: any script with joining behaviour, that is, any script whose
  characters have Joining_Type values given explicitly in ArabicShaping.txt.
- Interactions: may be combined with other GSUB features and may override them; see 'init',
  'isol', 'medi'.

## 'flac' - Flattened Accent Forms

- Registered by: Microsoft
- Function: flattened accent shapes for math accents over tall bases such as capitals. It
  changes only the accent's shape, never its position; the math engine positions it. The math
  engine uses the flattened form when the base is taller than
  MathConstants.flattenedAccentBaseHeight in the MATH table.
- Lookups: GSUB 1 (accent glyph to flattened form).
- Application: required for math layout; applied to individual glyphs as the math layout
  handler decides. Not exposed to users.
- Script/language sensitivity: math formula layout. Interactions: none.

## 'frac' - Fractions

- Registered by: Microsoft/Adobe
- Function: turns figures separated by a slash (U+002F SOLIDUS or U+2044 FRACTION SLASH) into
  diagonal fractions.
- Lookups: GSUB 1 (or contextual lookups calling GSUB 1 lookups) mapping figures to numerator
  or denominator variants, or GSUB 4 mapping whole sequences to fraction ligatures.
- Application: discretionary. An application may apply it automatically to sequences such as
  one or more digits, U+2044 FRACTION SLASH, one or more digits, and may apply 'numr' to the
  part before the slash and 'dnom' to the part after it, by its own analysis or as part of
  applying 'frac'. Default off.
- Script/language sensitivity: none. Interactions: used together with 'numr' and 'dnom'; may
  be combined with other GSUB features and may override them.

## 'fwid' - Full Widths

- Registered by: Adobe
- Function: replaces glyphs set on other widths with full-width (usually one em) glyphs; in
  CJKV fonts this can include ASCII Latin and symbols. In European fonts it selects
  fixed-width glyphs (typically 0.6 em) instead of proportional ones.
- Lookups: GSUB 1 (full-width glyphs) or GPOS 1 (xPlacement and xAdvance giving full-width
  metrics).
- Application: discretionary. Default off.
- Script/language sensitivity: any script that can use fixed-width forms.
- Interactions: mutually exclusive with the other horizontal width features ('chws',
  'halt', 'hwid', 'palt', 'pkna', 'pwid', 'qwid', 'twid', 'pnum', 'tnum'), which are turned
  off; 'apkn' and 'kern' are disabled on runs where it is applied.

## 'half' - Half Forms

- Registered by: Microsoft
- Function: gives Indic consonants their half (pre-base, conjoining) shapes.
- Lookups: GSUB 4 (consonant plus virama (halant) to half form).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Devanagari and other Indic or Brahmi-derived scripts with
  pre-base half forms.
- Interactions: one of the Indic basic-form features, processed in the order 'nukt',
  'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'half', 'pstf', 'cjct'; discretionary features
  run after them.

## 'haln' - Halant Forms

- Registered by: Microsoft
- Function: produces halant forms of consonants (precomposed consonant with visible halant).
- Lookups: GSUB 4 (consonant plus virama to halant form).
- Application: script-required; applied in the contexts the script's processing defines.
  Not exposed to users.
- Script/language sensitivity: Indic and other Brahmi-derived scripts. Interactions: its
  result overrides all other features.

## 'halt' - Alternate Half Widths

- Registered by: Adobe
- Function: re-spaces full-width glyphs onto fixed half-em widths, approximating CJK layouts
  such as JLREQ. Unlike 'hwid' it substitutes no glyphs; unlike 'chws' it is not contextual.
- Lookups: GPOS 1 (xPlacement, xAdvance, yPlacement, yAdvance).
- Application: not used when the layout engine itself implements CLREQ, JLREQ or KLREQ.
  Otherwise used for every CJKV glyph in horizontal layout, or only for characters that need
  special handling (brackets, punctuation, quotation marks); default on for horizontal
  CJK text in applications without such advanced layout.
- Script/language sensitivity: CJKV fonts only.
- Interactions: mutually exclusive with the other horizontal width features ('chws',
  'fwid', 'hwid', 'palt', 'pkna', 'pwid', 'qwid', 'twid', 'pnum', 'tnum'), which are turned
  off; 'apkn' and 'kern' are disabled. Vertical counterpart: 'vhal'.

## 'hist' - Historical Forms

- Registered by: Microsoft/Adobe
- Function: replaces current letterforms with historical alternates (such as long s) for a
  period effect. Single characters only; historical ligatures are 'hlig'.
- Lookups: GSUB 1.
- Application: discretionary. Default off.
- Script/language sensitivity: none. Interactions: may be combined with other GSUB features
  and may override them.

## 'hkna' - Horizontal Kana Alternates

- Registered by: Adobe
- Function: replaces standard kana with forms designed only for horizontal writing (better
  fit and colour). With 'vkna' it lets fonts for both directions pick kana variants per
  direction. Advance widths are not changed.
- Lookups: GSUB 1 (standard full-width forms to horizontal forms).
- Application: discretionary. Default off.
- Script/language sensitivity: fonts with kana (hiragana and katakana).
- Interactions: may be used with 'kern'. Vertical features ('vkna', 'vert', 'vrt2', 'vkrn')
  do not apply together with it.

## 'hlig' - Historical Ligatures

- Registered by: Microsoft
- Function: replaces current forms with historical ligatures for a period effect.
- Lookups: GSUB 4.
- Application: discretionary. Default off.
- Script/language sensitivity: none. Interactions: its result overrides all other features.

## 'hngl' (DEPRECATED) - Hangul

- Registered by: Adobe
- Function: converts hanja (Korean text written with Chinese characters) back to hangul
  syllables, the reverse of the usual input method.
- Lookups: GSUB 1 for one-to-one cases, GSUB 3 when the user must choose among several
  hangul; alternate order should be consistent across a family.
- Application: discretionary. With GSUB 3 the user picks the alternate; the application may
  remember the choice for the same hanja next time, otherwise treat the first alternate as
  preferred. The effect is equivalent to changing character codes, so the application should
  store the codes of the new glyphs besides the original hanja codes. Default off.
- Script/language sensitivity: Korean only.
- Interactions: mutually exclusive with most features, which are turned off; 'palt', 'vert'
  and 'vrt2' may still be applied.

## 'hojo' - Hojo Kanji Forms (JIS X 0212-1990 Kanji Forms)

- Registered by: Adobe
- Function: where JIS X 0212-1990 (Hojo Kanji) and JIS X 0213:2004 prototype glyphs differ and
  the font encodes the JIS X 0213:2004 form (recommended for fonts supporting both, such as
  Adobe-Japan1-6 fonts), gives access to the JIS X 0212-1990 form.
- Lookups: GSUB 1 (JIS X 0213:2004 glyph to JIS X 0212-1990 glyph).
- Application: discretionary. Default off.
- Script/language sensitivity: kanji in Japanese only.
- Interactions: mutually exclusive with 'jp78', 'jp83', 'jp90', 'nlck' and similar
  features; combinable with 'palt', 'vpal', 'vert' and 'vrt2'.

## 'hwid' - Half Widths

- Registered by: Adobe
- Function: replaces proportional glyphs, or fixed-width glyphs of other widths, with glyphs
  on half-em widths (selects the half-width variants in CJKV fonts; useful for compatibility
  with older documents).
- Lookups: GSUB 1 (half-width glyphs) or GPOS 1 (xPlacement and xAdvance fitting the glyphs
  to half an em).
- Application: discretionary. Default off.
- Script/language sensitivity: generally CJKV fonts only.
- Interactions: mutually exclusive with the other horizontal width features ('chws',
  'fwid', 'halt', 'palt', 'pkna', 'pwid', 'qwid', 'twid', 'pnum', 'tnum'), which are turned
  off; 'apkn' and 'kern' are disabled on runs where it is applied.

## 'init' - Initial Forms

- Registered by: Microsoft/Adobe (description revised in 2016)
- Function: replaces the glyph of a joining character with its initial form when it occurs
  in an initial context. It applies to characters whose Unicode Joining_Type is:
  - Right_Joining, in a left-to-right script;
  - Left_Joining, in a right-to-left script;
  - Dual_Joining.
  Joining_Type values come from ArabicShaping.txt.
- Lookups: usually GSUB 1; contextual GSUB 5, 6 or 8 may also be used.
- Application: script-required for cursively connected scripts; the application's joining
  analysis (Joining_Type plus factors such as control characters) decides which glyphs get
  'init', 'medi', 'fina' or 'isol'. Not exposed to users.
- Script/language sensitivity: any script whose Joining_Type values are listed explicitly in
  ArabicShaping.txt. Interactions: may be combined with other GSUB features and may override
  them; see 'fina', 'isol', 'medi'.

## 'isol' - Isolated Forms

- Registered by: Microsoft (description revised in 2016)
- Function: replaces the glyph of a joining character with its isolated (non-joining) form
  when it occurs in an isolated context. It applies to characters whose Unicode Joining_Type
  is Right_Joining, Left_Joining or Dual_Joining, and to Non_Joining characters of scripts
  with joining behaviour (scripts listed explicitly in ArabicShaping.txt).
- Many fonts do not implement it because their default glyphs are already the isolated
  forms; some implement it contextually.
- Lookups: GSUB 1, or often contextual GSUB 5, 6 or 8.
- Application: script-required for cursively connected scripts; chosen by the application's
  joining analysis as for 'init'. Not exposed to users.
- Script/language sensitivity: scripts with joining behaviour. Interactions: may be combined
  with other GSUB features and may override them; see 'fina', 'init', 'medi'.

## 'ital' - Italics

- Registered by: Adobe
- Function: in fonts that contain both roman and italic forms of some characters (for
  example Japanese fonts with Latin italics), replaces roman glyphs with italic ones.
- Lookups: GSUB 1.
- Application: applied automatically when the text is formatted italic by markup, user
  action or other means; when the user applies an italic style, the application should
  check for the feature and use it if present.
- Script/language sensitivity: mostly Latin, especially in fonts made mainly for CJKV or other
  scripts without italics.
- Interactions: may be combined with other GSUB features and may override them. In CJKV fonts
  it should also turn on 'kern' (normally on already for other scripts).

## 'jalt' - Justification Alternates

- Registered by: Microsoft
- Function: replaces glyphs with wider or narrower alternates designed to improve
  justification.
- Lookups: GSUB 1 (initial, medial, final or isolated forms to alternates). May be combined
  with JSTF extension or shrinkage modifications.
- Application: applied to glyphs of justified text as a justification algorithm or the user
  decides; may change line length, which line breaking and justification must account for.
  Default on or off per user preference.
- Script/language sensitivity: any cursive script. Interactions: if the font has 'init',
  'medi', 'fina' and 'isol', those must be applied before 'jalt'.

## 'jp78' - JIS78 Forms

- Registered by: Adobe
- Function: replaces default (JIS90) Japanese glyphs with JIS C 6226-1978 (JIS78) forms.
- Lookups: GSUB 1 for one-to-one cases and GSUB 3 where a choice is needed; a font may use two
  lookups (one of each type) or one GSUB 3 lookup for everything.
- Application: discretionary; with GSUB 3 the user selects the alternate, and the first is the
  preferred one. The effect equals a change of character code, so the application should
  store the new glyph's code as well as the original. Default off.
- Script/language sensitivity: Japanese only.
- Interactions: mutually exclusive with most features, which are turned off; 'palt', 'vpal',
  'vert' and 'vrt2' may still be applied.

## 'jp83' - JIS83 Forms

- Registered by: Adobe
- Function: replaces default (JIS90) Japanese glyphs with JIS X 0208-1983 (JIS83) forms.
- Lookups: GSUB 1.
- Application: discretionary; if implemented with an alternate (GSUB 3) lookup, the user
  selects the alternate. Default off.
- Script/language sensitivity: Japanese only.
- Interactions: mutually exclusive with most features, which are turned off; 'palt', 'vpal',
  'vert' and 'vrt2' may still be applied.

## 'jp90' - JIS90 Forms

- Registered by: Adobe
- Function: replaces JIS78 or JIS83 forms with JIS X 0208-1990 (JIS90) forms.
- Lookups: GSUB 1 (each JIS78 and JIS83 form to its JIS90 form).
- Application: discretionary. The application keeps a record of glyphs produced by 'jp78' or
  'jp83'; applying 'jp90' to those undoes the earlier substitution, and where no record
  exists the 'jp90' lookup returns the default form. The effect equals a change of character
  code, so the new code should be stored with the original. Default off.
- Script/language sensitivity: Japanese only.
- Interactions: mutually exclusive with most features, which are turned off; 'palt', 'vpal',
  'vert' and 'vrt2' may still be applied.

## 'jp04' - JIS2004 Forms

- Registered by: Adobe
- Function: gives access to the prototype glyphs that Japan's National Language Council
  defined and JIS X 0213:2004 adopted. It is a subset of 'nlck' that keeps to JIS X
  0213:2004.
- Lookups: GSUB 1 (non-JIS X 0213:2004 glyph to the JIS X 0213:2004 glyph).
- Application: discretionary. Default off.
- Script/language sensitivity: Japanese only.
- Interactions: mutually exclusive with 'jp78', 'jp83', 'jp90', 'nlck' and similar
  features; combinable with 'palt', 'vpal', 'vert' and 'vrt2'.
