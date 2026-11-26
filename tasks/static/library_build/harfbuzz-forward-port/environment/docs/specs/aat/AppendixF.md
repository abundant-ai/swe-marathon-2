# Font Feature Registry (digest)
Source: Font Feature Registry - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM09/AppendixF.html
These notes restate the source's structures and rules; where they differ, the source governs.

## The feature/selector model

- An AAT typographic effect is named by two 16-bit numbers: a feature type
  (the general kind of effect, for example ligatures) and a selector, also
  called a setting (the particular effect, for example rare ligatures).
  'morx' feature table entries and 'feat' records use exactly these numbers
  (see Chap6morx.md and Chap6feat.md).
- Exclusive features allow one selector at a time (a fraction cannot be both
  vertical and diagonal). Non-exclusive features allow several at once
  (common and rare ligatures together).
- Non-exclusive selectors come in pairs: an even value turns the setting on
  and the next odd value turns it explicitly off. The tables below give the
  even value; the off value is even + 1.
  Example: Ligatures (1) selector 2 = common ligatures on, 3 = off. The pair
  1/3 can display the compatibility character U+FB01 (fi ligature) as
  separate f and i.
- Feature types above 255 are reserved for font-specific custom features.
  Custom pairs show up in user interfaces when 'feat', 'morx' and 'name' are
  set up properly. The lists below are therefore not exhaustive.
- Pairs that only imitate a change of the underlying characters (for
  example showing U+002A asterisk as U+00D7 multiplication sign) are
  discouraged now that all text is Unicode, because users cannot tell a
  display change from a text change. The exception is characters that exist
  in Unicode only for compatibility, such as U+FB01.

Notation in the selector tables:

- D = the page displays the selector in its "discouraged or deprecated"
  style.
- Constant names are taken from the C interface printed at the end of the
  page (the header SFNTTypes.h). The page's own selector tables print several
  Off constants without the leading k (for example RubyKanaOffSelector,
  CJKItalicRomanOffSelector, CaseSensitiveLayoutOffSelector,
  AlternateHorizKanaOffSelector, StylisticAltOneOffSelector,
  ContextualAlternatesOffSelector); the values are identical.
- Feature type constants: the feature tables use names such as
  kAllTypographicFeatures, the C interface uses kAllTypographicFeaturesType;
  the C enumeration also ends with kLastFeatureType = -1.
- Feature types 7 and 12 do not appear in the registry.

## Feature types

| Type | Feature | Feature constant (table) | C enum constant | Kind |
|---|---|---|---|---|
| 0 | All Typographic Features | kAllTypographicFeatures | kAllTypographicFeaturesType | Nonexclusive |
| 1 | Ligatures | kLigatures | kLigaturesType | Nonexclusive |
| 2 | Cursive Connection | kCursiveConnection | kCursiveConnectionType | Exclusive |
| 3 | Letter Case | kLetterCase | kLetterCaseType | Exclusive |
| 4 | Vertical Substitution | kVerticalSubstitution | kVerticalSubstitutionType | Nonexclusive |
| 5 | Linguistic Rearrangement | kLinguisticRearrangement | kLinguisticRearrangementType | Nonexclusive |
| 6 | Number Spacing | kNumberSpacing | kNumberSpacingType | Exclusive |
| 8 | Smart Swash | kSmartSwash | kSmartSwashType | Nonexclusive |
| 9 | Diacritics | kDiacritics | kDiacriticsType | Exclusive |
| 10 | Vertical Position | kVerticalPosition | kVerticalPositionType | Exclusive |
| 11 | Fractions | kFractions | kFractionsType | Exclusive |
| 13 | Overlapping Characters | kOverlappingCharacters | kOverlappingCharactersType | Nonexclusive |
| 14 | Typographic Extras | kTypographicExtras | kTypographicExtrasType | Nonexclusive |
| 15 | Mathematical Extras | kMathematicalExtras | kMathematicalExtrasType | Nonexclusive |
| 16 | Ornament Sets | kOrnamentSets | kOrnamentSetsType | Exclusive |
| 17 | Character Alternatives | kCharacterAlternatives | kCharacterAlternativesType | Exclusive |
| 18 | Design Complexity | kDesignComplexity | kDesignComplexityType | Exclusive |
| 19 | Style Options | kStyleOptions | kStyleOptionsType | Exclusive |
| 20 | Character Shape | kCharacterShape | kCharacterShapeType | Exclusive |
| 21 | Number Case | kNumberCase | kNumberCaseType | Exclusive |
| 22 | Text Spacing | kTextSpacing | kTextSpacingType | Exclusive |
| 23 | Transliteration | kTransliteration | kTransliterationType | Exclusive |
| 24 | Annotation | kAnnotation | kAnnotationType | Exclusive |
| 25 | Kana Spacing | kKanaSpacing | kKanaSpacingType | Exclusive |
| 26 | Ideographic Spacing | kIdeographicSpacing | kIdeographicSpacingType | Exclusive |
| 27 | Unicode Decomposition | kUnicodeDecomposition | kUnicodeDecompositionType | Nonexclusive |
| 28 | Ruby Kana | kRubyKana | kRubyKanaType | Nonexclusive |
| 29 | CJK Symbol Alternatives | kCJKSymbolAlternatives | kCJKSymbolAlternativesType | Exclusive |
| 30 | Ideographic Alternatives | kIdeographicAlternatives | kIdeographicAlternativesType | Exclusive |
| 31 | CJK Vertical Roman Placement | kCJKVerticalRomanPlacement | kCJKVerticalRomanPlacementType | Exclusive |
| 32 | Italic CJK Roman | kItalicCJKRoman | kItalicCJKRomanType | Nonexclusive |
| 33 | Case Sensitive Layout | kCaseSensitiveLayout | kCaseSensitiveLayoutType | Nonexclusive |
| 34 | Alternate Kana | kAlternateKana | kAlternateKanaType | Nonexclusive |
| 35 | Stylistic Alternatives | kStylisticAlternatives | kStylisticAlternativesType | Nonexclusive |
| 36 | Contextual Alternates | kContextualAlternates | kContextualAlternatesType | Nonexclusive |
| 37 | Lower Case | kLowerCase | kLowerCaseType | Exclusive |
| 38 | Upper Case | kUpperCase | kUpperCaseType | Exclusive |
| 39 | Language Tag | kLanguageTag | kLanguageTagType | Exclusive |
| 103 | CJK Roman Spacing | kCJKRomanSpacing | kCJKRomanSpacingType | Exclusive |

## Selectors by feature type

### 0 All Typographic Features (kAllTypographicFeatures, nonexclusive)

Master switch for all other features: when it is off, every other request is ignored. Meant for debugging only; hiding it from ordinary users is advised because turning it off can disable shaping that legibility depends on.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | All Typographic Features | kAllTypeFeaturesOnSelector = 0, kAllTypeFeaturesOffSelector = 1 |  | turns every other feature on (0) or off (1); required pair that Apple's ftxenhancer adds to 'morx' automatically |

### 1 Ligatures (kLigatures, nonexclusive)

Families of ligatures that may be combined freely.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Required Ligatures | kRequiredLigaturesOnSelector = 0, kRequiredLigaturesOffSelector = 1 |  | ligatures the writing system requires (for example Arabic, Hindi); usually hidden from users |
| 2 | Common Ligatures | kCommonLigaturesOnSelector = 2, kCommonLigaturesOffSelector = 3 |  | ligatures normally used in well-set text, such as fi and fl |
| 4 | Rare Ligatures | kRareLigaturesOnSelector = 4, kRareLigaturesOffSelector = 5 |  | less frequent ligatures, such as fj |
| 6 | Logos | kLogosOnSelector = 6, kLogosOffSelector = 7 | D | words turned into logo glyphs; should not be used (insert graphics instead) |
| 8 | Rebus Pictures | kRebusPicturesOnSelector = 8, kRebusPicturesOffSelector = 9 |  | pictures standing for words or syllables |
| 10 | Diphthong Ligatures | kDiphthongLigaturesOnSelector = 10, kDiphthongLigaturesOffSelector = 11 |  | AE/ae style ligatures; strongly discouraged |
| 12 | Squared Ligatures | kSquaredLigaturesOnSelector = 12, kSquaredLigaturesOffSelector = 13 |  | letters packed into one square cell (compare U+3300..U+3357 and U+337B..U+337F) |
| 14 | Squared Ligatures, Abbreviated | kAbbrevSquaredLigaturesOnSelector = 14, kAbbrevSquaredLigaturesOffSelector = 15 |  | abbreviated variants of the squared ligatures |
| 16 | Symbol Ligatures | kSymbolLigaturesOnSelector = 16, kSymbolLigaturesOffSelector = 17 |  | ligatures drawn as graphics, for example emoji |
| 18 | Contextual Ligatures | kContextualLigaturesOnSelector = 18, kContextualLigaturesOffSelector = 19 |  | ligatures that occur only in certain contexts |
| 20 | Historical Ligatures | kHistoricalLigaturesOnSelector = 20, kHistoricalLigaturesOffSelector = 21 |  | ligatures no longer in general use |

### 2 Cursive Connection (kCursiveConnection, exclusive)

Cursive joining; required for Arabic, usable for other scripts.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Unconnected | kUnconnectedSelector = 0 |  | no cursive joining at all; wrong for scripts that require joining |
| 1 | Partially Connected | kPartiallyConnectedSelector = 1 |  | pre-drawn forms that join without looking at context |
| 2 | Cursive | kCursiveSelector = 2 |  | full contextual joining; required as the default where the script depends on joining |

### 3 Letter Case (kLetterCase, exclusive)

Deprecated as a whole; use Lower Case (37) and Upper Case (38) instead. Case changes here are visual only; the stored text is unchanged.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Upper & Lower Case | kUpperAndLowerCaseSelector = 0 | D | default; letters keep the case that was typed |
| 1 | All Caps | kAllCapsSelector = 1 | D | every letter shown as a capital (non-contextual; text itself unchanged) |
| 2 | All Lower Case | kAllLowerCaseSelector = 2 | D | every letter shown in lower case (non-contextual) |
| 3 | Small Caps | kSmallCapsSelector = 3 | D | lower-case letters shown as true small capitals (non-contextual) |
| 4 | Initial Caps | kInitialCapsSelector = 4 | D | first letter of a word capital, the rest lower case (contextual) |
| 5 | Initial Caps and Small Caps | kInitialCapsAndSmallCapsSelector = 5 | D | first letter of a word capital, the rest small capitals (contextual) |

### 4 Vertical Substitution (kVerticalSubstitution, nonexclusive)

Glyph changes needed in vertical runs. Single on/off pair.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Vertical Substitution | kSubstituteVerticalFormsOnSelector = 0, kSubstituteVerticalFormsOffSelector = 1 |  | vertical-text forms on (0) / off (1) |

### 5 Linguistic Rearrangement (kLinguisticRearrangement, nonexclusive)

Linguistic glyph rearrangement as needed by South Asian scripts; on by default in such fonts and normally hidden from users. Not the same thing as bidirectional reordering. Single on/off pair.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Linguistic Rearrangement | kLinguisticRearrangementOnSelector = 0, kLinguisticRearrangementOffSelector = 1 |  | linguistic rearrangement on (0) / off (1) |

### 6 Number Spacing (kNumberSpacing, exclusive)

Choice of digit widths.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Monospaced Numbers | kMonospacedNumbersSelector = 0 |  | equal-width digits for columns |
| 1 | Proportional Numbers | kProportionalNumbersSelector = 1 |  | digits of varying width |
| 2 | Third-width Numerals | kThirdWidthNumbersSelector = 2 |  | third-width (thin) digits |
| 3 | Quarter-width Numerals | kQuarterWidthNumbersSelector = 3 |  | quarter-width (very thin) digits |

### 8 Smart Swash (kSmartSwash, nonexclusive)

Swashes chosen by context analysis rather than by plain substitution.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Word Initial Swashes | kWordInitialSwashesOnSelector = 0, kWordInitialSwashesOffSelector = 1 |  | forms for the start of a word (or line) |
| 2 | Word Final Swashes | kWordFinalSwashesOnSelector = 2, kWordFinalSwashesOffSelector = 3 |  | forms for the end of a word (or line) |
| 4 | Line Initial Swashes | kLineInitialSwashesOnSelector = 4, kLineInitialSwashesOffSelector = 5 | D | forms for line starts only; not supported by CoreText |
| 6 | Line Final Swashes | kLineFinalSwashesOnSelector = 6, kLineFinalSwashesOffSelector = 7 | D | forms for line ends only; not supported by CoreText |
| 8 | Non-Final Swashes | kNonFinalSwashesOnSelector = 8, kNonFinalSwashesOffSelector = 9 |  | forms for word-initial or word-medial positions (for example long s) |

### 9 Diacritics (kDiacritics, exclusive)

How marks (accents, vowel signs) are displayed.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Show Diacritics | kShowDiacriticsSelector = 0 |  | default; marks attached to their bases |
| 1 | Hide Diacritics | kHideDiacriticsSelector = 1 |  | marks not displayed (for example unvowelled Arabic) |
| 2 | Decompose Diacritics | kDecomposeDiacriticsSelector = 2 |  | marks displayed in line instead of attached |

### 10 Vertical Position (kVerticalPosition, exclusive)

Superscript/subscript style positioning.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Vertical Position | kNormalPositionSelector = 0 |  | default; no vertical shift |
| 1 | Superiors | kSuperiorsSelector = 1 |  | superior forms where the font has them |
| 2 | Inferiors | kInferiorsSelector = 2 |  | inferior forms where the font has them |
| 3 | Ordinals | kOrdinalsSelector = 3 |  | contextual superior forms for ordinals (as in Spanish 1a) |
| 4 | Scientific Inferiors | kScientificInferiorsSelector = 4 |  | inferiors designed for scientific notation (as in H2O) |

### 11 Fractions (kFractions, exclusive)

Selection or synthesis of fractions.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Fractions | kNoFractionsSelector = 0 |  | no automatic fractions |
| 1 | Vertical Fractions | kVerticalFractionsSelector = 1 |  | use the font's pre-drawn (vertical) fractions |
| 2 | Diagonal Fractions | kDiagonalFractionsSelector = 2 |  | build fractions from superiors and inferiors (or numerator/denominator forms if present) |

### 13 Overlapping Characters (kOverlappingCharacters, nonexclusive)

Keeps long tails of some glyphs from colliding with neighbours. Single on/off pair.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Overlap Prevention | kPreventOverlapOnSelector = 0, kPreventOverlapOffSelector = 1 |  | overlap prevention on (0) / off (1) |

### 14 Typographic Extras (kTypographicExtras, nonexclusive)

Fine-typography effects. Everything except the slashed-zero pair is discouraged, because these effects imitate changes of the underlying text.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Hyphens to Em Dash | kHyphensToEmDashOnSelector = 0, kHyphensToEmDashOffSelector = 1 | D | two hyphens become an em dash; discouraged |
| 2 | Hyphen to En Dash | kHyphenToEnDashOnSelector = 2, kHyphenToEnDashOffSelector = 3 | D | hyphen between spaces or digits becomes an en dash; discouraged |
| 4 | Unslashed Zero | kSlashedZeroOnSelector = 4, kSlashedZeroOffSelector = 5 |  | always use the unslashed zero, even if the slashed zero is the font default (named slashed zero in the constants) |
| 6 | Form Interrobang | kFormInterrobangOnSelector = 6, kFormInterrobangOffSelector = 7 | D | ?! or !? becomes an interrobang if the font has one; discouraged |
| 8 | Smart Quotes | kSmartQuotesOnSelector = 8, kSmartQuotesOffSelector = 9 | D | straight quotes become curly quotes by context; discouraged |
| 10 | Periods to Ellipsis | kPeriodsToEllipsisOnSelector = 10, kPeriodsToEllipsisOffSelector = 11 | D | three periods become an ellipsis; discouraged |

### 15 Mathematical Extras (kMathematicalExtras, nonexclusive)

Effects for mathematics and figures.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Hyphen To Minus | kHyphenToMinusOnSelector = 0, kHyphenToMinusOffSelector = 1 | D | hyphen between spaces or digits becomes a minus; discouraged |
| 2 | Asterisk to Multiply | kAsteriskToMultiplyOnSelector = 2, kAsteriskToMultiplyOffSelector = 3 | D | asterisk between spaces becomes a multiplication sign; discouraged |
| 4 | Slash to Divide | kSlashToDivideOnSelector = 4, kSlashToDivideOffSelector = 5 | D | slash between spaces becomes a division sign; discouraged |
| 6 | Inequality Ligatures | kInequalityLigaturesOnSelector = 6, kInequalityLigaturesOffSelector = 7 | D | >= and <= become single relation glyphs; discouraged |
| 8 | Exponents | kExponentsOnSelector = 8, kExponentsOffSelector = 9 | D | digits after ^ become superiors; discouraged |
| 10 | Mathematical Greek | kMathematicalGreekOnSelector = 10, kMathematicalGreekOffSelector = 11 |  | Greek glyphs designed for mathematics rather than for Greek text |

### 16 Ornament Sets (kOrnamentSets, exclusive)

Non-letter ornament sets; lets one pi font stand in for several. Intended for characters in Unicode private use areas.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | None | kNoOrnamentsSelector = 0 |  | no ornaments |
| 1 | Dingbats | kDingbatsSelector = 1 |  | miscellaneous display symbols (arrows, stars, pointing hands) |
| 2 | Pi Characters | kPiCharactersSelector = 2 |  | symbol sets for a particular purpose that are not an alphabet (maps, music) |
| 3 | Fleurons | kFleuronsSelector = 3 |  | floral and leaf ornaments |
| 4 | Decorative Borders | kDecorativeBordersSelector = 4 |  | pieces for interlocking or repeating borders |
| 5 | International Symbols | kInternationalSymbolsSelector = 5 |  | internationally recognised icons |
| 6 | Math Symbols | kMathSymbolsSelector = 6 |  | mathematical and logic symbols that Unicode does not already encode |

### 17 Character Alternatives (kCharacterAlternatives, exclusive)

Selectors simply pick alternative glyph sets (for example one of many ampersands); they are not enumerated by the registry. Selector 0 should be the "No Alternates" setting. Style Options (19) is preferred where it fits.

No selector table on the page; the C interface defines only kNoAlternatesSelector = 0.

### 18 Design Complexity (kDesignComplexity, exclusive)

Overall design level of the font (plain, italic, chancery and so on). Level 1 should exist in every font using this feature and is normally the default; higher levels are progressively more elaborate.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Design Level 1 | kDesignLevel1Selector = 0 |  | first (normal) design level |
| 1 | Design Level 2 | kDesignLevel2Selector = 1 |  | second design level |
| 2 | Design Level 3 | kDesignLevel3Selector = 2 |  | third design level |
| 3 | Design Level 4 | kDesignLevel4Selector = 3 |  | fourth design level |
| 4 | Design Level 5 | kDesignLevel5Selector = 4 |  | fifth design level |

### 19 Style Options (kStyleOptions, exclusive)

Named sets of non-contextual substitutions.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Style Options | kNoStyleOptionsSelector = 0 |  | plain text |
| 1 | Display Text | kDisplayTextSelector = 1 |  | designs for display sizes, typically above 24 points |
| 2 | Engraved Text | kEngravedTextSelector = 2 |  | engraved look with strokes paralleling the main strokes |
| 3 | Illuminated Caps | kIlluminatedCapsSelector = 3 |  | decorated capitals that fill their surrounding space, in medieval manner |
| 4 | Titling Caps | kTitlingCapsSelector = 4 |  | special titling capitals |
| 5 | Tall Caps | kTallCapsSelector = 5 |  | taller versions of certain capitals |

### 20 Character Shape (kCharacterShape, exclusive)

Alternative appearances of the same character that are not swashes. For simplified-to-traditional Chinese mappings with several candidates, use the traditional alternative sets.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Traditional Glyphs | kTraditionalCharactersSelector = 0 |  | traditional character forms |
| 1 | Simplified Glyphs | kSimplifiedCharactersSelector = 1 |  | simplified character forms (the page adds a caution, left incomplete, about simplified characters that Unicode encodes separately) |
| 2 | JIS 1978 Glyphs | kJIS1978CharactersSelector = 2 |  | Japanese shapes as in JIS C 6226-1978 |
| 3 | JIS 1983 Glyphs | kJIS1983CharactersSelector = 3 |  | Japanese shapes as in JIS X 0208-1983 |
| 4 | JIS 1990 Glyphs | kJIS1990CharactersSelector = 4 |  | Japanese shapes as in JIS X 0208-1990 |
| 5 | Traditional Glyphs, Alternative Set 1 | kTraditionalAltOneSelector = 5 |  | traditional forms, alternative set 1 |
| 6 | Traditional Glyphs, Alternative Set 2 | kTraditionalAltTwoSelector = 6 |  | traditional forms, alternative set 2 |
| 7 | Traditional Glyphs, Alternative Set 3 | kTraditionalAltThreeSelector = 7 |  | traditional forms, alternative set 3 |
| 8 | Traditional Glyphs, Alternative Set 4 | kTraditionalAltFourSelector = 8 |  | traditional forms, alternative set 4 |
| 9 | Traditional Glyphs, Alternative Set 5 | kTraditionalAltFiveSelector = 9 |  | traditional forms, alternative set 5 |
| 10 | Expert Glyphs | kExpertCharactersSelector = 10 |  | expert ideograph forms (as in the Fujitsu FMR character set) |
| 11 | JIS 2004 Glyphs | kJIS2004CharactersSelector = 11 |  | Japanese shapes as in JIS X 0208-2004 |
| 12 | Hojo Glyphs | kHojoCharactersSelector = 12 |  | JIS X 0212-1990 (Hojo kanji) shapes where they differ from the JIS X 0213:2004 forms, which are preferred as the encoded forms in fonts supporting both |
| 13 | NLC Glyphs | kNLCCharactersSelector = 13 |  | glyph shapes defined in 2000 by Japan's National Language Council |
| 14 | Traditional Names | kTraditionalNamesCharactersSelector = 14 |  | maps simplified forms to traditional forms usable in personal names |

### 21 Number Case (kNumberCase, exclusive)

Digit style, independent of Letter Case.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Lower Case Numbers | kLowerCaseNumbersSelector = 0 |  | old-style digits that may descend below the baseline |
| 1 | Upper Case Numbers | kUpperCaseNumbersSelector = 1 |  | lining digits that stay on the baseline |

### 22 Text Spacing (kTextSpacing, exclusive)

Proportional, monospaced or reduced-width letter forms. Optional; Kana Spacing (25) and Ideographic Spacing (26) give finer control.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Proportional | kProportionalTextSelector = 0 |  | proportional letter forms |
| 1 | Monospace | kMonospacedTextSelector = 1 |  | monospaced letter forms |
| 2 | Half-width | kHalfWidthTextSelector = 2 |  | half-width letter forms |
| 3 | Third-width | kThirdWidthTextSelector = 3 |  | third-width letter forms |
| 4 | Quarter-width | kQuarterWidthTextSelector = 4 |  | quarter-width letter forms |
| 5 | Alternate Proportional | kAltProportionalTextSelector = 5 |  | alternate proportional letter forms |
| 6 | Alternate Half-width | kAltHalfWidthTextSelector = 6 |  | alternate half-width letter forms |

### 23 Transliteration (kTransliteration, exclusive)

Displays text of one writing system in another. Strongly discouraged, since transliteration belongs in character space.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Transliteration | kNoTransliterationSelector = 0 |  | no transliteration |
| 1 | Hanja to Hangul | kHanjaToHangulSelector = 1 | D | hanja shown as hangul |
| 2 | Hiragana To Katakana | kHiraganaToKatakanaSelector = 2 | D | hiragana shown as katakana |
| 3 | Katakana To Hiragana | kKatakanaToHiraganaSelector = 3 | D | katakana shown as hiragana |
| 4 | Kana To Romanization | kKanaToRomanizationSelector = 4 | D | kana shown as romaji |
| 5 | Romanization To Hiragana | kRomanizationToHiraganaSelector = 5 | D | romaji shown as hiragana |
| 6 | Romanization To Katakana | kRomanizationToKatakanaSelector = 6 | D | romaji shown as katakana |
| 7 | Hanja To Hangul Alt One | kHanjaToHangulAltOneSelector = 7 | D | hanja with several readings shown as hangul for the second reading |
| 8 | Hanja To Hangul Alt Two | kHanjaToHangulAltTwoSelector = 8 | D | the same for the third reading |
| 9 | Hanja To Hangul Alt Three | kHanjaToHangulAltThreeSelector = 9 | D | the same for the fourth reading |

### 24 Annotation (kAnnotation, exclusive)

Adorned forms (boxed, circled, parenthesized numerals and so on); many exist in Unicode only for compatibility, and the feature reaches a larger set.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Annotation | kNoAnnotationSelector = 0 |  | no annotation |
| 1 | Box Annotation | kBoxAnnotationSelector = 1 |  | characters inside a box |
| 2 | Rounded Box Annotation | kRoundedBoxAnnotationSelector = 2 |  | characters inside a box with rounded corners |
| 3 | Circle Annotation | kCircleAnnotationSelector = 3 |  | characters inside a circle (compare U+3260..U+326F) |
| 4 | Inverted Circle Annotation | kInvertedCircleAnnotationSelector = 4 |  | circled with black and white swapped (compare U+2776..U+277F) |
| 5 | Parenthesis Annotation | kParenthesisAnnotationSelector = 5 |  | characters in parentheses (compare U+2474..U+2487) |
| 6 | Period Annotation | kPeriodAnnotationSelector = 6 |  | characters followed by a period (compare U+2488..U+249B) |
| 7 | Roman Numeral Annotation | kRomanNumeralAnnotationSelector = 7 |  | Roman numeral forms |
| 8 | Diamond Annotation | kDiamondAnnotationSelector = 8 |  | characters inside a diamond |
| 9 | Inverted Box Annotation | kInvertedBoxAnnotationSelector = 9 |  | boxed with black and white swapped |
| 10 | Inverted Rounded Box Annotation | kInvertedRoundedBoxAnnotationSelector = 10 |  | rounded box with black and white swapped |

### 25 Kana Spacing (kKanaSpacing, exclusive)

Widths for hiragana and katakana.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Full Width | kFullWidthKanaSelector = 0 |  | full-width kana |
| 1 | Proportional | kProportionalKanaSelector = 1 |  | proportional kana |

### 26 Ideographic Spacing (kIdeographicSpacing, exclusive)

Widths for ideographs.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Full Width | kFullWidthIdeographsSelector = 0 |  | full-width ideographs |
| 1 | Proportional | kProportionalIdeographsSelector = 1 |  | proportional ideographs |
| 2 | Half Width | kHalfWidthIdeographsSelector = 2 |  | half-width ideographs |

### 27 Unicode Decomposition (kUnicodeDecomposition, nonexclusive)

Shows composition/decomposition effects to the user.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Canonical Composition | kCanonicalCompositionOnSelector = 0, kCanonicalCompositionOffSelector = 1 |  | show canonically decomposed text as composed; normally hidden from users |
| 2 | Compatibility Composition | kCompatibilityCompositionOnSelector = 2, kCompatibilityCompositionOffSelector = 3 |  | show compatibility-decomposed text as composed; normally hidden from users |
| 4 | Transcoding Composition | kTranscodingCompositionOnSelector = 4, kTranscodingCompositionOffSelector = 5 |  | controls whether Apple's private-use transcoding control characters (kept for round trips with old Macintosh encodings) take effect |

### 28 Ruby Kana (kRubyKana, nonexclusive)

Small kana (ruby) designed to annotate kanji. The layout engine still has to scale and position ruby; the feature only substitutes the designs.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Ruby Kana | kNoRubyKanaSelector = 0 | D | no ruby forms (deprecated; use the off selector 3) |
| 1 | Ruby Kana | kRubyKanaSelector = 1 | D | ruby forms (deprecated; use the on selector 2) |
| 2 | Ruby Kana | kRubyKanaOnSelector = 2, kRubyKanaOffSelector = 3 |  | ruby forms on (2) / off (3) |

### 29 CJK Symbol Alternatives (kCJKSymbolAlternatives, exclusive)

Alternate forms of East Asian symbols.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No CJK Symbol Alternatives | kNoCJKSymbolAlternativesSelector = 0 |  | standard forms (the ones 'cmap' maps to) |
| 1 | CJK Symbol Alt One | kCJKSymbolAltOneSelector = 1 |  | first set of alternates |
| 2 | CJK Symbol Alt Two | kCJKSymbolAltTwoSelector = 2 |  | second set of alternates |
| 3 | CJK Symbol Alt Three | kCJKSymbolAltThreeSelector = 3 |  | third set of alternates |
| 4 | CJK Symbol Alt Four | kCJKSymbolAltFourSelector = 4 |  | fourth set of alternates |
| 5 | CJK Symbol Alt Five | kCJKSymbolAltFiveSelector = 5 |  | fifth set of alternates |

### 30 Ideographic Alternatives (kIdeographicAlternatives, exclusive)

Alternate forms of East Asian ideographs.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Ideographic Alternatives | kNoIdeographicAlternativesSelector = 0 |  | standard forms (the ones 'cmap' maps to) |
| 1 | Ideographic Alt One | kIdeographicAltOneSelector = 1 |  | first set of alternates |
| 2 | Ideographic Alt Two | kIdeographicAltTwoSelector = 2 |  | second set of alternates |
| 3 | Ideographic Alt Three | kIdeographicAltThreeSelector = 3 |  | third set of alternates |
| 4 | Ideographic Alt Four | kIdeographicAltFourSelector = 4 |  | fourth set of alternates |
| 5 | Ideographic Alt Five | kIdeographicAltFiveSelector = 5 |  | fifth set of alternates |

### 31 CJK Vertical Roman Placement (kCJKVerticalRomanPlacement, exclusive)

Placement of Roman text set among kanji in vertical lines (the same result is reachable through baseline settings).

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | CJK Vertical Roman Centered | kCJKVerticalRomanCenteredSelector = 0 |  | Roman glyphs centred vertically on the ideographs' centre |
| 1 | CJK Vertical Roman H Baseline | kCJKVerticalRomanHBaselineSelector = 1 |  | Roman glyphs on a normal Roman baseline |

### 32 Italic CJK Roman (kItalicCJKRoman, nonexclusive)

Italic glyphs for romaji mixed with kanji.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No CJK Italic Roman | kNoCJKItalicRomanSelector = 0 | D | no italic romaji (deprecated; use the off selector 3) |
| 1 | CJK Italic Roman | kCJKItalicRomanSelector = 1 | D | italic romaji (deprecated; use the on selector 2) |
| 2 | CJK Italic Roman | kCJKItalicRomanOnSelector = 2, kCJKItalicRomanOffSelector = 3 |  | italic romaji on (2) / off (3) |

### 33 Case Sensitive Layout (kCaseSensitiveLayout, nonexclusive)

Alternate punctuation forms or spacing for text that is all lower case (for example a lower em dash between lower-case letters).

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Case Sensitive Layout | kCaseSensitiveLayoutOnSelector = 0, kCaseSensitiveLayoutOffSelector = 1 |  | case-sensitive forms on (0) / off (1) |
| 2 | Case Sensitive Spacing | kCaseSensitiveSpacingOnSelector = 2, kCaseSensitiveSpacingOffSelector = 3 |  | case-sensitive spacing on (2) / off (3) |

### 34 Alternate Kana (kAlternateKana, nonexclusive)

Different kana forms for horizontal or vertical text.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Alternate Horiz Kana | kAlternateHorizKanaOnSelector = 0, kAlternateHorizKanaOffSelector = 1 |  | alternate kana for horizontal text |
| 2 | Alternate Vert Kana | kAlternateVertKanaOnSelector = 2, kAlternateVertKanaOffSelector = 3 |  | alternate kana for vertical text |

### 35 Stylistic Alternatives (kStylisticAlternatives, nonexclusive)

Stylistic alternate sets; roughly a non-exclusive form of Character Alternatives, and the AAT counterpart of OpenType ss01..ss20 (selector 2n turns on set n, n = 1..20).

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | No Stylistic Alternates | kNoStylisticAlternatesSelector = 0 |  | standard forms (the ones 'cmap' maps to) |
| 2 | Stylistic Alt One | kStylisticAltOneOnSelector = 2, kStylisticAltOneOffSelector = 3 |  | first alternate set (OpenType ss01 counterpart) on (2) / off (3) |
| 4 | Stylistic Alt Two | kStylisticAltTwoOnSelector = 4, kStylisticAltTwoOffSelector = 5 |  | second alternate set (OpenType ss02 counterpart) on (4) / off (5) |
| 6 | Stylistic Alt Three | kStylisticAltThreeOnSelector = 6, kStylisticAltThreeOffSelector = 7 |  | third alternate set (OpenType ss03 counterpart) on (6) / off (7) |
| 8 | Stylistic Alt Four | kStylisticAltFourOnSelector = 8, kStylisticAltFourOffSelector = 9 |  | fourth alternate set (OpenType ss04 counterpart) on (8) / off (9) |
| 10 | Stylistic Alt Five | kStylisticAltFiveOnSelector = 10, kStylisticAltFiveOffSelector = 11 |  | fifth alternate set (OpenType ss05 counterpart) on (10) / off (11) |
| 12 | Stylistic Alt Six | kStylisticAltSixOnSelector = 12, kStylisticAltSixOffSelector = 13 |  | sixth alternate set (OpenType ss06 counterpart) on (12) / off (13) |
| 14 | Stylistic Alt Seven | kStylisticAltSevenOnSelector = 14, kStylisticAltSevenOffSelector = 15 |  | seventh alternate set (OpenType ss07 counterpart) on (14) / off (15) |
| 16 | Stylistic Alt Eight | kStylisticAltEightOnSelector = 16, kStylisticAltEightOffSelector = 17 |  | eighth alternate set (OpenType ss08 counterpart) on (16) / off (17) |
| 18 | Stylistic Alt Nine | kStylisticAltNineOnSelector = 18, kStylisticAltNineOffSelector = 19 |  | ninth alternate set (OpenType ss09 counterpart) on (18) / off (19) |
| 20 | Stylistic Alt Ten | kStylisticAltTenOnSelector = 20, kStylisticAltTenOffSelector = 21 |  | tenth alternate set (OpenType ss10 counterpart) on (20) / off (21) |
| 22 | Stylistic Alt Eleven | kStylisticAltElevenOnSelector = 22, kStylisticAltElevenOffSelector = 23 |  | eleventh alternate set (OpenType ss11 counterpart) on (22) / off (23) |
| 24 | Stylistic Alt Twelve | kStylisticAltTwelveOnSelector = 24, kStylisticAltTwelveOffSelector = 25 |  | twelfth alternate set (OpenType ss12 counterpart) on (24) / off (25) |
| 26 | Stylistic Alt Thirteen | kStylisticAltThirteenOnSelector = 26, kStylisticAltThirteenOffSelector = 27 |  | thirteenth alternate set (OpenType ss13 counterpart) on (26) / off (27) |
| 28 | Stylistic Alt Fourteen | kStylisticAltFourteenOnSelector = 28, kStylisticAltFourteenOffSelector = 29 |  | fourteenth alternate set (OpenType ss14 counterpart) on (28) / off (29) |
| 30 | Stylistic Alt Fifteen | kStylisticAltFifteenOnSelector = 30, kStylisticAltFifteenOffSelector = 31 |  | fifteenth alternate set (OpenType ss15 counterpart) on (30) / off (31) |
| 32 | Stylistic Alt Sixteen | kStylisticAltSixteenOnSelector = 32, kStylisticAltSixteenOffSelector = 33 |  | sixteenth alternate set (OpenType ss16 counterpart) on (32) / off (33) |
| 34 | Stylistic Alt Seventeen | kStylisticAltSeventeenOnSelector = 34, kStylisticAltSeventeenOffSelector = 35 |  | seventeenth alternate set (OpenType ss17 counterpart) on (34) / off (35) |
| 36 | Stylistic Alt Eighteen | kStylisticAltEighteenOnSelector = 36, kStylisticAltEighteenOffSelector = 37 |  | eighteenth alternate set (OpenType ss18 counterpart) on (36) / off (37) |
| 38 | Stylistic Alt Nineteen | kStylisticAltNineteenOnSelector = 38, kStylisticAltNineteenOffSelector = 39 |  | nineteenth alternate set (OpenType ss19 counterpart) on (38) / off (39) |
| 40 | Stylistic Alt Twenty | kStylisticAltTwentyOnSelector = 40, kStylisticAltTwentyOffSelector = 41 |  | twentieth alternate set (OpenType ss20 counterpart) on (40) / off (41) |

### 36 Contextual Alternates (kContextualAlternates, nonexclusive)

Alternates for context-dependent glyphs and swashes.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Contextual Alternates | kContextualAlternatesOnSelector = 0, kContextualAlternatesOffSelector = 1 |  | alternates for context-dependent glyphs |
| 2 | Swash Alternates | kSwashAlternatesOnSelector = 2, kSwashAlternatesOffSelector = 3 |  | alternates for context-dependent swashes |
| 4 | Contextual Swash Alternates | kContextualSwashAlternatesOnSelector = 4, kContextualSwashAlternatesOffSelector = 5 |  | alternates for context-dependent glyphs and swashes |

### 37 Lower Case (kLowerCase, exclusive)

Takes over part of Letter Case for lower-case text. Displaying real capitals for lower-case letters is discouraged.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Default Lower Case | kDefaultLowerCaseSelector = 0 |  | standard lower-case glyphs |
| 1 | Lower Case Small Caps | kLowerCaseSmallCapsSelector = 1 |  | lower-case letters as small capitals (the usual small-caps setting) |
| 2 | Lower Case Petite Caps | kLowerCasePetiteCapsSelector = 2 |  | lower-case letters as petite capitals |

### 38 Upper Case (kUpperCase, exclusive)

Takes over part of Letter Case for upper-case text. Displaying real lower-case glyphs for capitals is discouraged.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Default Upper Case | kDefaultUpperCaseSelector = 0 |  | standard capitals |
| 1 | Upper Case Small Caps | kUpperCaseSmallCapsSelector = 1 |  | capitals as small capitals (common for acronyms) |
| 2 | Upper Case Petite Caps | kUpperCasePetiteCapsSelector = 2 |  | capitals as petite capitals |

### 39 Language Tag (kLanguageTag, exclusive)

Language-specific glyphs. Selector 0 = no change; any other selector is 1 + an index into the 'ltag' table, which maps it to an IETF language tag. Example: if 'ltag' entry 0 is sr (Serbian), 39/1 switches to Serbian-specific shapes. Must be exclusive.

No fixed selector list (selectors follow the 'ltag' indices as described above).

### 103 CJK Roman Spacing (kCJKRomanSpacing, exclusive)

Proportional versus half-width forms of Roman letters in a CJK font.

| Selector | Name | Constant(s) from the C interface | D | Effect |
|---|---|---|---|---|
| 0 | Half-width | kHalfWidthCJKRomanSelector = 0 |  | half-width Roman letters |
| 1 | Proportional | kProportionalCJKRomanSelector = 1 |  | proportional Roman letters |
| 2 | Default Roman | kDefaultCJKRomanSelector = 2 |  | the font's default Roman letters |
| 3 | Full-width Roman | kFullWidthCJKRomanSelector = 3 |  | full-width Roman letters |
