# Korean Hangul script shaping (digest)
Source: Developing OpenType Fonts for Korean Hangul Script - Typography | Microsoft Learn, https://learn.microsoft.com/en-us/typography/script-development/hangul
These notes restate the source's structures and rules; where they differ, the source governs.

## Terms and notation

- Jamo: a single Hangul letter, consonant or vowel; the smallest unit of a syllable.
- Consonants come in two roles: leading (choseong, starts the syllable) and trailing (jongseong, ends it). Vowels are jungseong.
- A syllable is drawn as one square cell, the syllable block, into which its jamo are shaped and positioned.
- Modern Hangul: syllables that have their own precomposed code point. Old Hangul: syllables assembled from individual jamo code points.

Notation used by the page and in these notes:

| Symbol | Meaning |
|---|---|
| L | leading consonant jamo |
| V | vowel jamo |
| T | trailing consonant jamo |
| S | syllable |
| X | a character that is not a jamo |
| Lf, Vf | leading consonant filler, vowel filler |
| `{ }` | zero, one or more occurrences |
| `[ ]` | zero or one occurrence |
| `( )` | one or more occurrences |

## 1. Character classes and ranges

| Class | Meaning | Code points |
|---|---|---|
| Precomposed syllables | Modern Hangul, 11,172 syllables with one code point each | U+AC00..U+D7AF (range as given by the page; 11,172 code points counted from U+AC00 end at U+D7A3) |
| Hangul Jamo block | building blocks of Old Hangul syllables | U+1100..U+11FF |
| L | leading consonants, filler included | U+1100..U+1159, U+115F |
| V | vowels, filler included | U+1160..U+11A2 |
| T | trailing consonants | U+11A8..U+11F9 |
| Lf | leading consonant filler | U+115F |
| Vf | vowel filler | U+1160 |

- The L, V and T ranges come from Appendix B (section 10): each of its three tables contains every code point of its range exactly once as a one-code-point row, and the L and V tables start with their filler. Within U+1100..U+11FF, the code points U+115A..U+115E, U+11A3..U+11A7 and U+11FA..U+11FF appear nowhere in Appendix B.
- The page does not split the precomposed syllables into LV and LVT types, and it says nothing about tone marks.

## 2. Shaping stages

The page lists four stages, in this order:

1. Compose Old Hangul jamo combinations (section 3).
2. Identify syllable boundaries with OpenType Layout services (no further detail is given for this stage).
3. Analyze the syllables (section 4).
4. Shape glyphs with OpenType Layout services: map every character to its nominal glyph, then apply the features of section 5 one feature per call, which keeps them in order. The order of lookups inside each feature matters too.

## 3. Composing Old Hangul jamo (stage 1)

The engine receives a character run that has already been divided into runs of leading (L), vowel (V) and trailing (T) jamo.

1. In each run it looks for the longest stretch of jamo that matches an Appendix B entry and swaps that stretch for the single registered Old Hangul jamo the entry stands for.
2. It repeats this with the next longest match, and keeps going until all runs have been handled.
3. What comes out is a sequence in which every element is a registered Old Hangul jamo.

Only sequences listed in Appendix B produce Old Hangul jamo and syllables. A sequence of Hangul Jamo block characters that matches no Appendix B pattern is treated as a series of separate characters that are not Old Hangul.

The page's abstract example (indices only distinguish the input jamo):

    input:   V1 L1 L2 L3 V2 V3 T1 T2 T3 L4 L5 V4 T4 V5 V6 L6 V7
    matches: L2 L3 / T1 T2 T3 / V5 V6 are Appendix B entries
    output:  V1 L1 L23 V2 V3 T123 L4 L5 V4 T4 V56 L6 V7

## 4. Syllable analysis (stage 3)

- Each Hangul syllable is handled in the canonical shape L V T. When a syllable lacks its leading consonant or its vowel, the engine inserts the corresponding filler (Lf U+115F or Vf U+1160) into the registered jamo sequence so the syllable reaches that shape. The page names no trailing filler, and a syllable may stop after its vowel (see the L V example in section 7).
- Next the engine tags every jamo with the feature that is to process it, then calls OpenType Layout for one syllable after another.
- The feature follows from the jamo's slot in the syllable: leading slot -> `ljmo`, vowel slot -> `vjmo`, trailing slot -> `tjmo`. The page does not say whether an inserted filler itself receives a feature.
- Modern syllables are left alone: when a jamo sequence under analysis is able to form a Modern Hangul syllable, the engine applies no OpenType features to it. Such syllables are expected to be encoded with the precomposed code points (U+AC00..U+D7AF), as the Unicode Standard describes.
- The page gives no composition or decomposition arithmetic for modern syllables and does not define which jamo sequences count as modern; it defers to the Unicode Standard for both.

## 5. Feature order (stage 4)

| # | Feature | Feature function (page label) | Layout operation | Required | Glyphs affected; who decides |
|---|---|---|---|---|---|
| 1 | `ccmp` | Character composition/decomposition substitution | GSUB | no | L, V and T jamo sequences; the font's ligatures carry out the Appendix B compositions |
| 2 | `ljmo` | Leading consonant Jamo | GSUB | yes | jamo the engine tagged as leading; the font chooses the shape from context |
| 3 | `vjmo` | Vowel Jamo | GSUB | yes | jamo the engine tagged as vowels; the font chooses the shape from context |
| 4 | `tjmo` | Trailing consonant Jamo | GSUB | yes | jamo the engine tagged as trailing; the font chooses the shape from context |

All four sit in the page's "Language based forms" group. No GPOS features are listed for Hangul.

## 6. What each feature does

- `ccmp`: ligature substitution (GSUB type 4) that turns a multi-jamo Appendix B sequence into one jamo glyph. It runs ahead of every other feature so these compositions take priority, and it serves leading, vowel and trailing sequences alike. The composed glyph is afterwards reshaped by `ljmo`, `vjmo` or `tjmo`. Example: the leading sequence U+1107 + U+1109 + U+1110 becomes one glyph.
- `ljmo`: chooses the shape of the leading consonant for its syllable. The choice depends on what comes after it: a vowel only, or a vowel and then a trailing consonant. Example: U+1113 is replaced by its leading form when only a vowel follows.
- `vjmo`: chooses the shape of the vowel. The choice depends on whether only a leading jamo precedes it, or a leading jamo precedes it and a trailing jamo follows. Example: U+1162 (JUNGSEONG AE) is replaced by its form for a syllable with just a leading jamo before it.
- `tjmo`: chooses the shape of the trailing consonant. The choice depends on whether it comes after a leading filler plus vowel, or after a real leading jamo plus vowel. Example: U+11C7 is replaced by its form for a syllable with a leading jamo and a vowel.

## 7. Worked examples from the page (with code points)

| Input | What happens |
|---|---|
| U+1107 U+1109 U+1110 U+1169 U+1163 U+1175 U+11AF U+11B7 U+11C2 (choseong pieup, sios, thieuth; jungseong o, ya, i; jongseong rieul, mieum, hieuh) | `ccmp` merges each three-jamo run into a single glyph (Appendix B rows L53, V26, T46); `ljmo`, `vjmo` and `tjmo` then give each glyph the size and position it needs in an L V T syllable. |
| U+1101 U+1161 U+11C7 (choseong ssangkiyeok, jungseong a, jongseong nieun-sios) | nothing to compose; `ljmo`, `vjmo` and `tjmo` select the L V T variants. |
| U+1113 U+1162 (choseong nieun-kiyeok, jungseong ae) | an L V syllable without a trailing consonant; `ljmo` and `vjmo` select the variants. |

## 8. Invalid combinations and helper characters

- A combining mark or sign that is not attached to a valid base is invalid. For Hangul, when the engine meets an invalid combination of letters it just begins a new syllable (cluster); the page describes no dotted-circle insertion for this script.
- To display a mark on its own, place it on a space (U+0020), as Unicode 3.1 section 2.5 describes, with U+200D ZWJ between the space and the mark; the engine combines the two only when that ZWJ is present.
- Recommended, though not needed for OpenType processing: ZERO WIDTH JOINER, ZERO WIDTH NON-JOINER and ZERO WIDTH SPACE (U+200B) in Hangul fonts. The page's sentence pairs ZWJ with U+200C and ZWNJ with U+200D; by Unicode, ZWNJ is U+200C and ZWJ is U+200D.

## 9. Script and language system tags

Script tag: `hang` (Korean Hangul).

| Language system tag | Language |
|---|---|
| `dflt` | default script handling |
| `"KOR "` | Korean |

- Tags are case-sensitive and exactly four characters long: script tags are lower case, language system tags upper case, and a three-letter language tag is padded with one trailing space (shown inside quotes above).
- Every font should carry a `dflt` language system under the script. It is the fallback when no language-specific system matches or when the application does not support the language; some applications fail on fonts without it.
- The Microsoft engine described by the page uses only the default language system; language-specific features serve other applications.

## 10. Appendix B: standard composition of Old Hangul jamo

How to read these tables:

- There is one table per class (leading consonants, vowels, trailing consonants), with the rows in the page's order. The # column counts each page table's rows from the top; the numbering is added here for reference.
- A one-code-point row is a registered jamo that already has its own code point: no composition takes place, but the row marks a valid member of the class.
- A row of two or three code points is a sequence that stage 1 replaces with one registered Old Hangul jamo, and that the font's `ccmp` ligates into a single glyph. The page shows the composed jamo only as a glyph picture and assigns it no code point, so the result column describes it rather than naming a code point.
- Matching is longest-first (section 3). Some three-jamo rows start with a two-jamo row of the same table: L21 (U+1105 U+1100) inside L22 (U+1105 U+1100 U+1100); L24 (U+1105 U+1103) inside L25 (U+1105 U+1103 U+1103); L28 (U+1105 U+1107) inside L29 (U+1105 U+1107 U+1107); V25 (U+1169 U+1163) inside V26 (U+1169 U+1163 U+1175); V36 (U+116D U+1161) inside V37 (U+116D U+1161 U+1175); V67 (U+1173 U+1165) inside V68 (U+1173 U+1165 U+1175); V79 (U+1175 U+1167) inside V80 (U+1175 U+1167 U+1175); T24 (U+11AE U+11AE) inside T25 (U+11AE U+11AE U+11B8); T28 (U+11AE U+11BA) inside T29 (U+11AE U+11BA U+11A8); T66 (U+11B7 U+11AB) inside T67 (U+11B7 U+11AB U+11AB); T125 (U+11BD U+11B8) inside T126 (U+11BD U+11B8 U+11B8).

Row counts:

| Class | Rows | One code point | Two code points | Three code points |
|---|---|---|---|---|
| Leading consonants (L) | 124 | 91 | 27 | 6 |
| Vowels (V) | 95 | 67 | 17 | 11 |
| Trailing consonants (T) | 141 | 82 | 43 | 16 |
| All | 360 | 240 | 87 | 33 |

### Leading consonants (L)

| # | Input sequence | Result after composition |
|---|---|---|
| L1 | U+115F | itself (leading consonant filler, Lf) |
| L2 | U+1100 | itself (no composition) |
| L3 | U+1101 | itself (no composition) |
| L4 | U+1102 | itself (no composition) |
| L5 | U+1113 | itself (no composition) |
| L6 | U+1114 | itself (no composition) |
| L7 | U+1115 | itself (no composition) |
| L8 | U+1116 | itself (no composition) |
| L9 | U+1102 + U+1109 | one composed L jamo |
| L10 | U+1102 + U+110C | one composed L jamo |
| L11 | U+1102 + U+1112 | one composed L jamo |
| L12 | U+1103 | itself (no composition) |
| L13 | U+1117 | itself (no composition) |
| L14 | U+1104 | itself (no composition) |
| L15 | U+1103 + U+1105 | one composed L jamo |
| L16 | U+1103 + U+1106 | one composed L jamo |
| L17 | U+1103 + U+1107 | one composed L jamo |
| L18 | U+1103 + U+1109 | one composed L jamo |
| L19 | U+1103 + U+110C | one composed L jamo |
| L20 | U+1105 | itself (no composition) |
| L21 | U+1105 + U+1100 | one composed L jamo |
| L22 | U+1105 + U+1100 + U+1100 | one composed L jamo |
| L23 | U+1118 | itself (no composition) |
| L24 | U+1105 + U+1103 | one composed L jamo |
| L25 | U+1105 + U+1103 + U+1103 | one composed L jamo |
| L26 | U+1119 | itself (no composition) |
| L27 | U+1105 + U+1106 | one composed L jamo |
| L28 | U+1105 + U+1107 | one composed L jamo |
| L29 | U+1105 + U+1107 + U+1107 | one composed L jamo |
| L30 | U+1105 + U+112B | one composed L jamo |
| L31 | U+1105 + U+1109 | one composed L jamo |
| L32 | U+1105 + U+110C | one composed L jamo |
| L33 | U+1105 + U+110F | one composed L jamo |
| L34 | U+111A | itself (no composition) |
| L35 | U+111B | itself (no composition) |
| L36 | U+1106 | itself (no composition) |
| L37 | U+1106 + U+1100 | one composed L jamo |
| L38 | U+1106 + U+1103 | one composed L jamo |
| L39 | U+111C | itself (no composition) |
| L40 | U+1106 + U+1109 | one composed L jamo |
| L41 | U+111D | itself (no composition) |
| L42 | U+1107 | itself (no composition) |
| L43 | U+111E | itself (no composition) |
| L44 | U+111F | itself (no composition) |
| L45 | U+1120 | itself (no composition) |
| L46 | U+1108 | itself (no composition) |
| L47 | U+1121 | itself (no composition) |
| L48 | U+1122 | itself (no composition) |
| L49 | U+1123 | itself (no composition) |
| L50 | U+1124 | itself (no composition) |
| L51 | U+1125 | itself (no composition) |
| L52 | U+1126 | itself (no composition) |
| L53 | U+1107 + U+1109 + U+1110 | one composed L jamo |
| L54 | U+1127 | itself (no composition) |
| L55 | U+1128 | itself (no composition) |
| L56 | U+1107 + U+110F | one composed L jamo |
| L57 | U+1129 | itself (no composition) |
| L58 | U+112A | itself (no composition) |
| L59 | U+1107 + U+1112 | one composed L jamo |
| L60 | U+112B | itself (no composition) |
| L61 | U+112C | itself (no composition) |
| L62 | U+1109 | itself (no composition) |
| L63 | U+112D | itself (no composition) |
| L64 | U+112E | itself (no composition) |
| L65 | U+112F | itself (no composition) |
| L66 | U+1130 | itself (no composition) |
| L67 | U+1131 | itself (no composition) |
| L68 | U+1132 | itself (no composition) |
| L69 | U+1133 | itself (no composition) |
| L70 | U+110A | itself (no composition) |
| L71 | U+1109 + U+1109 + U+1107 | one composed L jamo |
| L72 | U+1134 | itself (no composition) |
| L73 | U+1135 | itself (no composition) |
| L74 | U+1136 | itself (no composition) |
| L75 | U+1137 | itself (no composition) |
| L76 | U+1138 | itself (no composition) |
| L77 | U+1139 | itself (no composition) |
| L78 | U+113A | itself (no composition) |
| L79 | U+113B | itself (no composition) |
| L80 | U+113C | itself (no composition) |
| L81 | U+113D | itself (no composition) |
| L82 | U+113E | itself (no composition) |
| L83 | U+113F | itself (no composition) |
| L84 | U+1140 | itself (no composition) |
| L85 | U+110B | itself (no composition) |
| L86 | U+1141 | itself (no composition) |
| L87 | U+1142 | itself (no composition) |
| L88 | U+110B + U+1105 | one composed L jamo |
| L89 | U+1143 | itself (no composition) |
| L90 | U+1144 | itself (no composition) |
| L91 | U+1145 | itself (no composition) |
| L92 | U+1146 | itself (no composition) |
| L93 | U+1147 | itself (no composition) |
| L94 | U+1148 | itself (no composition) |
| L95 | U+1149 | itself (no composition) |
| L96 | U+114A | itself (no composition) |
| L97 | U+114B | itself (no composition) |
| L98 | U+110B + U+1112 | one composed L jamo |
| L99 | U+114C | itself (no composition) |
| L100 | U+110C | itself (no composition) |
| L101 | U+114D | itself (no composition) |
| L102 | U+110D | itself (no composition) |
| L103 | U+110C + U+110C + U+1112 | one composed L jamo |
| L104 | U+114E | itself (no composition) |
| L105 | U+114F | itself (no composition) |
| L106 | U+1150 | itself (no composition) |
| L107 | U+1151 | itself (no composition) |
| L108 | U+110E | itself (no composition) |
| L109 | U+1152 | itself (no composition) |
| L110 | U+1153 | itself (no composition) |
| L111 | U+1154 | itself (no composition) |
| L112 | U+1155 | itself (no composition) |
| L113 | U+110F | itself (no composition) |
| L114 | U+1110 | itself (no composition) |
| L115 | U+1110 + U+1110 | one composed L jamo |
| L116 | U+1111 | itself (no composition) |
| L117 | U+1156 | itself (no composition) |
| L118 | U+1111 + U+1112 | one composed L jamo |
| L119 | U+1157 | itself (no composition) |
| L120 | U+1112 | itself (no composition) |
| L121 | U+1112 + U+1109 | one composed L jamo |
| L122 | U+1158 | itself (no composition) |
| L123 | U+1159 | itself (no composition) |
| L124 | U+1159 + U+1159 | one composed L jamo |

### Vowels (V)

| # | Input sequence | Result after composition |
|---|---|---|
| V1 | U+1160 | itself (vowel filler, Vf) |
| V2 | U+1161 | itself (no composition) |
| V3 | U+1176 | itself (no composition) |
| V4 | U+1177 | itself (no composition) |
| V5 | U+1161 + U+1173 | one composed V jamo |
| V6 | U+1162 | itself (no composition) |
| V7 | U+1163 | itself (no composition) |
| V8 | U+1178 | itself (no composition) |
| V9 | U+1179 | itself (no composition) |
| V10 | U+1163 + U+116E | one composed V jamo |
| V11 | U+1164 | itself (no composition) |
| V12 | U+1165 | itself (no composition) |
| V13 | U+117A | itself (no composition) |
| V14 | U+117B | itself (no composition) |
| V15 | U+117C | itself (no composition) |
| V16 | U+1166 | itself (no composition) |
| V17 | U+1167 | itself (no composition) |
| V18 | U+1167 + U+1163 | one composed V jamo |
| V19 | U+117D | itself (no composition) |
| V20 | U+117E | itself (no composition) |
| V21 | U+1168 | itself (no composition) |
| V22 | U+1169 | itself (no composition) |
| V23 | U+116A | itself (no composition) |
| V24 | U+116B | itself (no composition) |
| V25 | U+1169 + U+1163 | one composed V jamo |
| V26 | U+1169 + U+1163 + U+1175 | one composed V jamo |
| V27 | U+117F | itself (no composition) |
| V28 | U+1180 | itself (no composition) |
| V29 | U+1169 + U+1167 | one composed V jamo |
| V30 | U+1181 | itself (no composition) |
| V31 | U+1182 | itself (no composition) |
| V32 | U+1169 + U+1169 + U+1175 | one composed V jamo |
| V33 | U+1183 | itself (no composition) |
| V34 | U+116C | itself (no composition) |
| V35 | U+116D | itself (no composition) |
| V36 | U+116D + U+1161 | one composed V jamo |
| V37 | U+116D + U+1161 + U+1175 | one composed V jamo |
| V38 | U+1184 | itself (no composition) |
| V39 | U+1185 | itself (no composition) |
| V40 | U+116D + U+1165 | one composed V jamo |
| V41 | U+1186 | itself (no composition) |
| V42 | U+1187 | itself (no composition) |
| V43 | U+1188 | itself (no composition) |
| V44 | U+116E | itself (no composition) |
| V45 | U+1189 | itself (no composition) |
| V46 | U+118A | itself (no composition) |
| V47 | U+116F | itself (no composition) |
| V48 | U+118B | itself (no composition) |
| V49 | U+1170 | itself (no composition) |
| V50 | U+116E + U+1167 | one composed V jamo |
| V51 | U+118C | itself (no composition) |
| V52 | U+118D | itself (no composition) |
| V53 | U+1171 | itself (no composition) |
| V54 | U+116E + U+1175 + U+1175 | one composed V jamo |
| V55 | U+1172 | itself (no composition) |
| V56 | U+118E | itself (no composition) |
| V57 | U+1172 + U+1161 + U+1175 | one composed V jamo |
| V58 | U+118F | itself (no composition) |
| V59 | U+1190 | itself (no composition) |
| V60 | U+1191 | itself (no composition) |
| V61 | U+1192 | itself (no composition) |
| V62 | U+1172 + U+1169 | one composed V jamo |
| V63 | U+1193 | itself (no composition) |
| V64 | U+1194 | itself (no composition) |
| V65 | U+1173 | itself (no composition) |
| V66 | U+1173 + U+1161 | one composed V jamo |
| V67 | U+1173 + U+1165 | one composed V jamo |
| V68 | U+1173 + U+1165 + U+1175 | one composed V jamo |
| V69 | U+1173 + U+1169 | one composed V jamo |
| V70 | U+1195 | itself (no composition) |
| V71 | U+1196 | itself (no composition) |
| V72 | U+1174 | itself (no composition) |
| V73 | U+1197 | itself (no composition) |
| V74 | U+1175 | itself (no composition) |
| V75 | U+1198 | itself (no composition) |
| V76 | U+1199 | itself (no composition) |
| V77 | U+1175 + U+1163 + U+1169 | one composed V jamo |
| V78 | U+1175 + U+1163 + U+1175 | one composed V jamo |
| V79 | U+1175 + U+1167 | one composed V jamo |
| V80 | U+1175 + U+1167 + U+1175 | one composed V jamo |
| V81 | U+119A | itself (no composition) |
| V82 | U+1175 + U+1169 + U+1175 | one composed V jamo |
| V83 | U+1175 + U+116D | one composed V jamo |
| V84 | U+119B | itself (no composition) |
| V85 | U+1175 + U+1172 | one composed V jamo |
| V86 | U+119C | itself (no composition) |
| V87 | U+1175 + U+1175 | one composed V jamo |
| V88 | U+119D | itself (no composition) |
| V89 | U+119E | itself (no composition) |
| V90 | U+119E + U+1161 | one composed V jamo |
| V91 | U+119F | itself (no composition) |
| V92 | U+119E + U+1165 + U+1175 | one composed V jamo |
| V93 | U+11A0 | itself (no composition) |
| V94 | U+11A1 | itself (no composition) |
| V95 | U+11A2 | itself (no composition) |

### Trailing consonants (T)

| # | Input sequence | Result after composition |
|---|---|---|
| T1 | U+11A8 | itself (no composition) |
| T2 | U+11A9 | itself (no composition) |
| T3 | U+11A8 + U+11AB | one composed T jamo |
| T4 | U+11C3 | itself (no composition) |
| T5 | U+11A8 + U+11B8 | one composed T jamo |
| T6 | U+11AA | itself (no composition) |
| T7 | U+11C4 | itself (no composition) |
| T8 | U+11A8 + U+11BE | one composed T jamo |
| T9 | U+11A8 + U+11BF | one composed T jamo |
| T10 | U+11A8 + U+11C2 | one composed T jamo |
| T11 | U+11AB | itself (no composition) |
| T12 | U+11C5 | itself (no composition) |
| T13 | U+11AB + U+11AB | one composed T jamo |
| T14 | U+11C6 | itself (no composition) |
| T15 | U+11AB + U+11AF | one composed T jamo |
| T16 | U+11C7 | itself (no composition) |
| T17 | U+11C8 | itself (no composition) |
| T18 | U+11AC | itself (no composition) |
| T19 | U+11AB + U+11BE | one composed T jamo |
| T20 | U+11C9 | itself (no composition) |
| T21 | U+11AD | itself (no composition) |
| T22 | U+11AE | itself (no composition) |
| T23 | U+11CA | itself (no composition) |
| T24 | U+11AE + U+11AE | one composed T jamo |
| T25 | U+11AE + U+11AE + U+11B8 | one composed T jamo |
| T26 | U+11CB | itself (no composition) |
| T27 | U+11AE + U+11B8 | one composed T jamo |
| T28 | U+11AE + U+11BA | one composed T jamo |
| T29 | U+11AE + U+11BA + U+11A8 | one composed T jamo |
| T30 | U+11AE + U+11BD | one composed T jamo |
| T31 | U+11AE + U+11BE | one composed T jamo |
| T32 | U+11AE + U+11C0 | one composed T jamo |
| T33 | U+11AF | itself (no composition) |
| T34 | U+11B0 | itself (no composition) |
| T35 | U+11AF + U+11A8 + U+11A8 | one composed T jamo |
| T36 | U+11CC | itself (no composition) |
| T37 | U+11AF + U+11A8 + U+11C2 | one composed T jamo |
| T38 | U+11CD | itself (no composition) |
| T39 | U+11CE | itself (no composition) |
| T40 | U+11CF | itself (no composition) |
| T41 | U+11D0 | itself (no composition) |
| T42 | U+11AF + U+11AF + U+11BF | one composed T jamo |
| T43 | U+11B1 | itself (no composition) |
| T44 | U+11D1 | itself (no composition) |
| T45 | U+11D2 | itself (no composition) |
| T46 | U+11AF + U+11B7 + U+11C2 | one composed T jamo |
| T47 | U+11B2 | itself (no composition) |
| T48 | U+11AF + U+11B8 + U+11AE | one composed T jamo |
| T49 | U+11D3 | itself (no composition) |
| T50 | U+11AF + U+11B8 + U+11C1 | one composed T jamo |
| T51 | U+11D4 | itself (no composition) |
| T52 | U+11D5 | itself (no composition) |
| T53 | U+11B3 | itself (no composition) |
| T54 | U+11D6 | itself (no composition) |
| T55 | U+11D7 | itself (no composition) |
| T56 | U+11AF + U+11F0 | one composed T jamo |
| T57 | U+11D8 | itself (no composition) |
| T58 | U+11B4 | itself (no composition) |
| T59 | U+11B5 | itself (no composition) |
| T60 | U+11B6 | itself (no composition) |
| T61 | U+11D9 | itself (no composition) |
| T62 | U+11AF + U+11F9 + U+11C2 | one composed T jamo |
| T63 | U+11AF + U+11BC | one composed T jamo |
| T64 | U+11B7 | itself (no composition) |
| T65 | U+11DA | itself (no composition) |
| T66 | U+11B7 + U+11AB | one composed T jamo |
| T67 | U+11B7 + U+11AB + U+11AB | one composed T jamo |
| T68 | U+11DB | itself (no composition) |
| T69 | U+11B7 + U+11B7 | one composed T jamo |
| T70 | U+11DC | itself (no composition) |
| T71 | U+11B7 + U+11B8 + U+11BA | one composed T jamo |
| T72 | U+11DD | itself (no composition) |
| T73 | U+11DE | itself (no composition) |
| T74 | U+11DF | itself (no composition) |
| T75 | U+11B7 + U+11BD | one composed T jamo |
| T76 | U+11E0 | itself (no composition) |
| T77 | U+11E1 | itself (no composition) |
| T78 | U+11E2 | itself (no composition) |
| T79 | U+11B8 | itself (no composition) |
| T80 | U+11B8 + U+11AE | one composed T jamo |
| T81 | U+11E3 | itself (no composition) |
| T82 | U+11B8 + U+11AF + U+11C1 | one composed T jamo |
| T83 | U+11B8 + U+11B7 | one composed T jamo |
| T84 | U+11B8 + U+11B8 | one composed T jamo |
| T85 | U+11B9 | itself (no composition) |
| T86 | U+11B8 + U+11BA + U+11AE | one composed T jamo |
| T87 | U+11B8 + U+11BD | one composed T jamo |
| T88 | U+11B8 + U+11BE | one composed T jamo |
| T89 | U+11E4 | itself (no composition) |
| T90 | U+11E5 | itself (no composition) |
| T91 | U+11E6 | itself (no composition) |
| T92 | U+11BA | itself (no composition) |
| T93 | U+11E7 | itself (no composition) |
| T94 | U+11E8 | itself (no composition) |
| T95 | U+11E9 | itself (no composition) |
| T96 | U+11BA + U+11B7 | one composed T jamo |
| T97 | U+11EA | itself (no composition) |
| T98 | U+11BA + U+11E6 | one composed T jamo |
| T99 | U+11BB | itself (no composition) |
| T100 | U+11BA + U+11BA + U+11A8 | one composed T jamo |
| T101 | U+11BA + U+11BA + U+11AE | one composed T jamo |
| T102 | U+11BA + U+11EB | one composed T jamo |
| T103 | U+11BA + U+11BD | one composed T jamo |
| T104 | U+11BA + U+11BE | one composed T jamo |
| T105 | U+11BA + U+11C0 | one composed T jamo |
| T106 | U+11BA + U+11C2 | one composed T jamo |
| T107 | U+11EB | itself (no composition) |
| T108 | U+11EB + U+11B8 | one composed T jamo |
| T109 | U+11EB + U+11E6 | one composed T jamo |
| T110 | U+11BC | itself (no composition) |
| T111 | U+11EC | itself (no composition) |
| T112 | U+11ED | itself (no composition) |
| T113 | U+11BC + U+11B7 | one composed T jamo |
| T114 | U+11BC + U+11BA | one composed T jamo |
| T115 | U+11EE | itself (no composition) |
| T116 | U+11EF | itself (no composition) |
| T117 | U+11BC + U+11C2 | one composed T jamo |
| T118 | U+11F0 | itself (no composition) |
| T119 | U+11F0 + U+11A8 | one composed T jamo |
| T120 | U+11F1 | itself (no composition) |
| T121 | U+11F2 | itself (no composition) |
| T122 | U+11F0 + U+11BF | one composed T jamo |
| T123 | U+11F0 + U+11C2 | one composed T jamo |
| T124 | U+11BD | itself (no composition) |
| T125 | U+11BD + U+11B8 | one composed T jamo |
| T126 | U+11BD + U+11B8 + U+11B8 | one composed T jamo |
| T127 | U+11BD + U+11BD | one composed T jamo |
| T128 | U+11BE | itself (no composition) |
| T129 | U+11BF | itself (no composition) |
| T130 | U+11C0 | itself (no composition) |
| T131 | U+11C1 | itself (no composition) |
| T132 | U+11F3 | itself (no composition) |
| T133 | U+11C1 + U+11BA | one composed T jamo |
| T134 | U+11C1 + U+11C0 | one composed T jamo |
| T135 | U+11F4 | itself (no composition) |
| T136 | U+11C2 | itself (no composition) |
| T137 | U+11F5 | itself (no composition) |
| T138 | U+11F6 | itself (no composition) |
| T139 | U+11F7 | itself (no composition) |
| T140 | U+11F8 | itself (no composition) |
| T141 | U+11F9 | itself (no composition) |
