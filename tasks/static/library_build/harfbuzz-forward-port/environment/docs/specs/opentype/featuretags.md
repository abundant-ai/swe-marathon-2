# Feature Tags
Source: Feature tags (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/featuretags
These notes restate the source's structures and rules; where they differ, the source governs.

## What a feature tag is

- An OpenType Layout feature is identified by a 4-byte feature tag stored in a FeatureRecord
  (see chapter2.md, FeatureList table). The tag names the feature's typographic function.
  The feature's data is a list of lookups in GSUB, in GPOS, or in both.
- Tags use the restricted ASCII character set of the Tag data type (see otff.md, Data types).
  Registered feature tags are, by convention, four lowercase letters.
- Tags of four uppercase letters A-Z (no digits, spaces or punctuation) form a reserved
  vendor space for private features. A private feature has no interoperability guarantee.
- A layout client decides from the tag whether, and where, to use a feature. The lookups
  alone often cannot say where a feature applies: for example the client must run Arabic
  joining analysis to know which glyphs receive 'init', 'medi', 'fina' or 'isol'. The client
  is responsible for applying, combining and arbitrating between features and for the
  final rendering.
- The lookup types named in feature descriptions are recommendations only; fonts and
  platforms may implement a feature with other lookup types.
- General lookup processing is in gsub.md, gpos.md and chapter2.md.

## Registration

Font developers may register new features. A registered feature must perform one clearly
identified function, defined at the lowest useful level and distinct from every existing
feature; no implementation details are required. Microsoft assigns the official tags.
Registration does not mean that Microsoft fonts implement the feature.

## Complete list of registered feature tags

The source page links to the per-feature descriptions, which are digested in
features_ae.md, features_fj.md, features_ko.md, features_pt.md and features_uz.md. The
table below lists every registered feature described on those pages, in their order. The
two range entries stand for 99 tags ('cv01', 'cv02', ... 'cv99') and 20 tags ('ss01',
'ss02', ... 'ss20'). The source flags two entries, 'hngl' and 'opbd', as DEPRECATED in their
headings.

| Tag | Friendly name | Registered by | Described in |
|---|---|---|---|
| 'aalt' | Access All Alternates | Adobe | features_ae.md |
| 'abvf' | Above-base Forms | Microsoft | features_ae.md |
| 'abvm' | Above-base Mark Positioning | Microsoft | features_ae.md |
| 'abvs' | Above-base Substitutions | Microsoft | features_ae.md |
| 'afrc' | Alternative Fractions | Microsoft | features_ae.md |
| 'akhn' | Akhand | Microsoft | features_ae.md |
| 'apkn' | Kerning for Alternate Proportional Widths | Adobe/Microsoft | features_ae.md |
| 'blwf' | Below-base Forms | Microsoft | features_ae.md |
| 'blwm' | Below-base Mark Positioning | Microsoft | features_ae.md |
| 'blws' | Below-base Substitutions | Microsoft | features_ae.md |
| 'calt' | Contextual Alternates | Adobe | features_ae.md |
| 'case' | Case-sensitive Forms | Adobe | features_ae.md |
| 'ccmp' | Glyph Composition / Decomposition | Microsoft | features_ae.md |
| 'cfar' | Conjunct Form After Ro | Microsoft | features_ae.md |
| 'chws' | Contextual Half-width Spacing | Adobe/W3C | features_ae.md |
| 'cjct' | Conjunct Forms | Microsoft | features_ae.md |
| 'clig' | Contextual Ligatures | Adobe | features_ae.md |
| 'cpct' | Centered CJK Punctuation | Adobe | features_ae.md |
| 'cpsp' | Capital Spacing | Adobe | features_ae.md |
| 'cswh' | Contextual Swash | Adobe | features_ae.md |
| 'curs' | Cursive Positioning | Microsoft | features_ae.md |
| 'cv01' - 'cv99' | Character Variant 1 - Character Variant 99 | Microsoft | features_ae.md |
| 'c2pc' | Petite Capitals From Capitals | Tiro Typeworks / Emigre | features_ae.md |
| 'c2sc' | Small Capitals From Capitals | Adobe | features_ae.md |
| 'dist' | Distances | Microsoft | features_ae.md |
| 'dlig' | Discretionary Ligatures | Adobe | features_ae.md |
| 'dnom' | Denominators | Adobe | features_ae.md |
| 'dtls' | Dotless Forms | Microsoft | features_ae.md |
| 'expt' | Expert Forms | Adobe | features_ae.md |
| 'falt' | Final Glyph on Line Alternates | Microsoft | features_fj.md |
| 'fin2' | Terminal Forms #2 | Microsoft | features_fj.md |
| 'fin3' | Terminal Forms #3 | Microsoft | features_fj.md |
| 'fina' | Terminal Forms | Microsoft/Adobe | features_fj.md |
| 'flac' | Flattened Accent Forms | Microsoft | features_fj.md |
| 'frac' | Fractions | Microsoft/Adobe | features_fj.md |
| 'fwid' | Full Widths | Adobe | features_fj.md |
| 'half' | Half Forms | Microsoft | features_fj.md |
| 'haln' | Halant Forms | Microsoft | features_fj.md |
| 'halt' | Alternate Half Widths | Adobe | features_fj.md |
| 'hist' | Historical Forms | Microsoft/Adobe | features_fj.md |
| 'hkna' | Horizontal Kana Alternates | Adobe | features_fj.md |
| 'hlig' | Historical Ligatures | Microsoft | features_fj.md |
| 'hngl' (DEPRECATED) | Hangul | Adobe | features_fj.md |
| 'hojo' | Hojo Kanji Forms (JIS X 0212-1990 Kanji Forms) | Adobe | features_fj.md |
| 'hwid' | Half Widths | Adobe | features_fj.md |
| 'init' | Initial Forms | Microsoft/Adobe | features_fj.md |
| 'isol' | Isolated Forms | Microsoft | features_fj.md |
| 'ital' | Italics | Adobe | features_fj.md |
| 'jalt' | Justification Alternates | Microsoft | features_fj.md |
| 'jp78' | JIS78 Forms | Adobe | features_fj.md |
| 'jp83' | JIS83 Forms | Adobe | features_fj.md |
| 'jp90' | JIS90 Forms | Adobe | features_fj.md |
| 'jp04' | JIS2004 Forms | Adobe | features_fj.md |
| 'kern' | Kerning | Microsoft/Adobe | features_ko.md |
| 'lfbd' | Left Bounds | Adobe | features_ko.md |
| 'liga' | Standard Ligatures | Microsoft/Adobe | features_ko.md |
| 'ljmo' | Leading Jamo Forms | Microsoft | features_ko.md |
| 'lnum' | Lining Figures | Adobe | features_ko.md |
| 'locl' | Localized Forms | Tiro Typeworks/Adobe | features_ko.md |
| 'ltra' | Left-to-right Alternates | Adobe | features_ko.md |
| 'ltrm' | Left-to-right Mirrored Forms | Adobe | features_ko.md |
| 'mark' | Mark Positioning | Microsoft | features_ko.md |
| 'med2' | Medial Forms #2 | Microsoft | features_ko.md |
| 'medi' | Medial Forms | Microsoft/Adobe | features_ko.md |
| 'mgrk' | Mathematical Greek | Adobe | features_ko.md |
| 'mkmk' | Mark to Mark Positioning | Microsoft | features_ko.md |
| 'mset' | Mark Positioning via Substitution | Microsoft | features_ko.md |
| 'nalt' | Alternate Annotation Forms | Adobe | features_ko.md |
| 'nlck' | NLC Kanji Forms | Adobe Systems Inc. | features_ko.md |
| 'nukt' | Nukta Forms | Microsoft | features_ko.md |
| 'numr' | Numerators | Adobe | features_ko.md |
| 'onum' | Oldstyle Figures | Microsoft/Adobe | features_ko.md |
| 'opbd' (DEPRECATED) | Optical Bounds | Adobe | features_ko.md |
| 'ordn' | Ordinals | Adobe | features_ko.md |
| 'ornm' | Ornaments | Adobe | features_ko.md |
| 'palt' | Proportional Alternate Widths | Adobe | features_pt.md |
| 'pcap' | Petite Capitals | Tiro Typeworks / Emigre | features_pt.md |
| 'pkna' | Proportional Kana | Adobe | features_pt.md |
| 'pnum' | Proportional Figures | Microsoft/Adobe | features_pt.md |
| 'pref' | Pre-base Forms | Microsoft | features_pt.md |
| 'pres' | Pre-base Substitutions | Microsoft | features_pt.md |
| 'pstf' | Post-base Forms | Microsoft | features_pt.md |
| 'psts' | Post-base Substitutions | Microsoft | features_pt.md |
| 'pwid' | Proportional Widths | Adobe | features_pt.md |
| 'qwid' | Quarter Widths | Adobe | features_pt.md |
| 'rand' | Randomize | Adobe | features_pt.md |
| 'rclt' | Required Contextual Alternates | Microsoft | features_pt.md |
| 'rkrf' | Rakar Forms | Microsoft | features_pt.md |
| 'rlig' | Required Ligatures | Microsoft | features_pt.md |
| 'rphf' | Reph Form | Microsoft | features_pt.md |
| 'rtbd' | Right Bounds | Adobe | features_pt.md |
| 'rtla' | Right-to-left Alternates | Adobe | features_pt.md |
| 'rtlm' | Right-to-left Mirrored Forms | Adobe | features_pt.md |
| 'ruby' | Ruby Notation Forms | Adobe | features_pt.md |
| 'rvrn' | Required Variation Alternates | Microsoft | features_pt.md |
| 'salt' | Stylistic Alternates | Adobe | features_pt.md |
| 'sinf' | Scientific Inferiors | Microsoft/Adobe | features_pt.md |
| 'size' | Optical size | Adobe | features_pt.md |
| 'smcp' | Small Capitals | Microsoft/Adobe | features_pt.md |
| 'smpl' | Simplified Forms | Adobe | features_pt.md |
| 'ss01' - 'ss20' | Stylistic Set 1 - Stylistic Set 20 | Tiro Typeworks | features_pt.md |
| 'ssty' | Math Script-style Alternates | Microsoft | features_pt.md |
| 'stch' | Stretching Glyph Decomposition | Microsoft | features_pt.md |
| 'subs' | Subscript | Microsoft/Adobe | features_pt.md |
| 'sups' | Superscript | Microsoft/Adobe | features_pt.md |
| 'swsh' | Swash | Microsoft/Adobe | features_pt.md |
| 'titl' | Titling | Adobe | features_pt.md |
| 'tjmo' | Trailing Jamo Forms | Microsoft | features_pt.md |
| 'tnam' | Traditional Name Forms | Adobe | features_pt.md |
| 'tnum' | Tabular Figures | Adobe | features_pt.md |
| 'trad' | Traditional Forms | Adobe | features_pt.md |
| 'twid' | Third Widths | Adobe | features_pt.md |
| 'unic' | Unicase | Tiro Typeworks / Emigre | features_uz.md |
| 'valt' | Alternate Vertical Metrics | Adobe | features_uz.md |
| 'vapk' | Kerning for Alternate Proportional Vertical Metrics | Adobe/Microsoft | features_uz.md |
| 'vatu' | Vattu Variants | Microsoft | features_uz.md |
| 'vchw' | Vertical Contextual Half-width Spacing | Adobe/W3C | features_uz.md |
| 'vert' | Vertical Alternates | Microsoft/Adobe | features_uz.md |
| 'vhal' | Alternate Vertical Half Metrics | Adobe | features_uz.md |
| 'vjmo' | Vowel Jamo Forms | Microsoft | features_uz.md |
| 'vkna' | Vertical Kana Alternates | Adobe | features_uz.md |
| 'vkrn' | Vertical Kerning | Adobe | features_uz.md |
| 'vpal' | Proportional Alternate Vertical Metrics | Adobe | features_uz.md |
| 'vrt2' | Vertical Alternates and Rotation | Adobe | features_uz.md |
| 'vrtr' | Vertical Alternates for Rotation | Adobe/Microsoft/W3C | features_uz.md |
| 'zero' | Slashed Zero | Adobe | features_uz.md |

Totals: 126 entries, which stand for 243 distinct tags once the two ranges are expanded.
