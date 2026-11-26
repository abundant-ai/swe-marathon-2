# Hebrew script shaping (digest)
Source: Developing OpenType Fonts for Hebrew Script - Typography | Microsoft Learn, https://learn.microsoft.com/en-us/typography/script-development/hebrew
These notes restate the source's structures and rules; where they differ, the source governs.

## Terms used below

- Base glyph: a glyph that takes one or more combining marks, placed above it, below it, or (for dagesh) inside its outline. A ligature can serve as a base, so rules are expressed per glyph.
- Nikud: pronunciation marks added to a base letter. Most are vowel points, and every vowel point except one sits below the base. There are also three consonant modifiers: dagesh, shin dot and sin dot. One letter may carry a consonant modifier plus a vowel point, and in biblical text a cantillation mark as well. Nikud are optional and missing from most running text, but must be placed correctly when present; biblical and modern Hebrew differ slightly in their conventions.
- Cantillation marks (teamim): Masoretic marks above or below the base that guide liturgical chanting. Their correct position often depends on the other marks on the same base, so the font should place them contextually.
- Character example: alef is U+05D0.

## 1. Character analysis

For Hebrew the analysis step does one thing: it checks that combining marks form valid combinations (section 5). The page describes no contextual form selection for Hebrew letters.

## 2. Shaping stages

The page names two stages, which follow the mark check of section 1:

1. Substitution with GSUB: map every character to its nominal glyph, then apply `ccmp` and then `dlig`, one feature per call.
2. Positioning with GPOS: apply `kern`, then `mark`.

Each feature gets its own OpenType Layout call, which is what fixes the order; the order of lookups inside a feature matters as well. Some features are irrelevant for some of the languages written in Hebrew script.

## 3. Feature order

| # | Feature | Feature function (page label) | Layout operation | Required | Glyphs affected; who decides |
|---|---|---|---|---|---|
| 1 | `ccmp` | Character composition/decomposition substitution | GSUB | no | whole run; the font's lookups decide |
| 2 | `dlig` | Discretionary ligature substitution | GSUB | no | whole run; font decides; the user controls whether it runs |
| 3 | `kern` | Pair kerning | GPOS | no | pairs of base glyphs; font decides |
| 4 | `mark` | Mark to base positioning | GPOS | yes | marks on bases and ligatures; font anchors decide |

The page groups `ccmp` under "Language based forms", `dlig` under "Typographical forms", and `kern` and `mark` under "Positioning features". `mark` is the only feature flagged as required, and no mark-to-mark (`mkmk`) feature is listed for Hebrew.

## 4. Reordering

The page defines no reordering of characters or marks for Hebrew.

## 5. Invalid combining marks

### Mechanism

- A combining mark or sign that is not attached to a valid base is invalid. It is rendered with the Unicode fallback for non-spacing marks (the page cites section 5.12 of Unicode 3.1): the mark is shown on U+25CC DOTTED CIRCLE.
- The dotted circle is inserted at run time into the returned glyph array only; the text the application stores is not changed.
- Motivation given by the page: on the engine's path for non-OpenType fonts, invalid mark combinations are overstruck (drawn on top of each other); inserting the dotted circle avoids that and makes the error visible.
- If the font has no glyph for U+25CC, the mark appears on the missing-glyph shape (an empty box).
- Besides U+25CC, the page recommends that Hebrew fonts contain U+200E LEFT-TO-RIGHT MARK and U+200F RIGHT-TO-LEFT MARK (written "LTR" and "RTL" on the page).

### Specific invalid cases

1. Shin dot (U+05C1) and sin dot (U+05C2) belong only on SHIN (U+05E9). When their base is any other letter, a dotted circle is inserted and the dot is placed on it. The page gives this as its example for the `ccmp` step.
2. A base may not carry two marks of the same class (table below). The page's example is two nikud on one base. The mark that creates the conflict goes onto a dotted circle.

### Mark classes used by the validity check

| Class | Description (page label) | Code points |
|---|---|---|
| DIAC | Hebrew diacritic | U+05B0..U+05B6, U+05BB |
| CANT1 | Hebrew cantilation - above left | U+0599, U+05A1, U+05A9, U+05AE |
| CANT2 | Hebrew cantilation - above center left | U+0597, U+05A8, U+05AC |
| CANT3 | Hebrew cantilation - above center | U+0592..U+0595, U+05A7, U+05AB |
| CANT4 | Hebrew cantilation - above center right | U+0598, U+059C, U+059E, U+059F |
| CANT5 | Hebrew cantilation - above right | U+059D, U+05A0 |
| CANT6 | Hebrew cantilation - below left | U+059B, U+05A5 |
| CANT7 | Hebrew cantilation - below center left | U+0591, U+05A3, U+05A6 |
| CANT8 | Hebrew cantilation - below center right | U+0596, U+05A4, U+05AA |
| CANT9 | Hebrew cantilation - below right | U+059A, U+05AD |
| CANT10 | Hebrew cantilation - Masora Circle | U+05AF |
| DAGESH | Hebrew dagesh/mapiq | U+05BC |
| DOTABV | Hebrew upper dot | U+05C4 |
| HOLAM | Hebrew holam | U+05B9 |
| METEG | Hebrew Meteg/sof pasuq | U+05BD |
| PATAH | Hebrew patah | U+05B7 |
| QAMATS | Hebrew shin/sin dot | U+05B8 |
| RAFE | Hebrew Rafe | U+05BF |
| SHINSIN | Hebrew shin/sin dot | U+05C1, U+05C2 |

Notes on the table:

- The QAMATS row carries the same label as SHINSIN on the page; its only member, U+05B8, is HEBREW POINT QAMATS.
- "cantilation" is the page's spelling. In the CANT4 row the page writes the second code point in lower case ("u+059C").

## 6. What each feature does in Hebrew

- `ccmp`: applied first so the font can merge a glyph sequence into one glyph (GSUB type 4) or split a glyph into several (GSUB type 2). Example from the page: the Yiddish ligature yod yod patah, U+05F2 + U+05B7 -> U+FB1F. The meteg ligatures of section 8 are also formed here.
- `dlig`: optional ligatures that the user can control (GSUB type 4); sequences with more components must be listed before shorter ones. The page notes that the engine has a flag for switching this feature off. Example: alef + lamed (U+05D0 U+05DC) replaced by an alef-lamed ligature glyph.
- `kern`: pair adjustments (GPOS type 2, or chained context positioning, type 8), with the same conventions as elsewhere: individual pairs before class pairs, longer glyph runs before pairs, not used in monospaced fonts. Seldom needed in Hebrew; possible uses are extra room for bases that carry nikud or teamim, and spacing in handwriting-style designs.
- `mark`: the one required feature; attaches marks to a base glyph (MarkToBase, GPOS type 4) or to a component of a ligature (MarkToLigature, GPOS type 5).

## 7. Script and language system tags

Script tag: `hebr` (Hebrew).

| Language system tag | Language |
|---|---|
| `dflt` | default script handling |
| `"IWR "` | Hebrew |
| `"JUD "` | Ladino |
| `"JII "` | Yiddish |

- Tags are case-sensitive and exactly four characters long: script tags are lower case, language system tags upper case, and a three-letter language tag is padded with one trailing space (shown inside quotes above).
- Every font should carry a `dflt` language system under the script. It is the fallback when no language-specific system matches or when the application does not support the language; some applications fail on fonts without it.
- The Microsoft engine described by the page uses only the default language system; language-specific features serve other applications.

## 8. Suggested extra glyphs (Appendix C)

- In three cases a meteg (U+05BD, the page's "METEG/SOF PASUQ") is written between the two parts of a single nikud. For correct display the page suggests adding three extra glyphs for these combinations to the font, produced by a `ccmp` ligature lookup (GSUB type 4). The glyphs need no Unicode code points of their own.
- The page also refers to the Unicode Standard for further guidance on meteg combined with hataf vowels.
- The page presents the three glyphs only as a picture and names no code points in its text, so the exact list cannot be transcribed here. Inference (not page text): the only two-part points are the hataf vowels, so the three cases are most likely U+05B1 HEBREW POINT HATAF SEGOL, U+05B2 HEBREW POINT HATAF PATAH and U+05B3 HEBREW POINT HATAF QAMATS, each combined with U+05BD.
