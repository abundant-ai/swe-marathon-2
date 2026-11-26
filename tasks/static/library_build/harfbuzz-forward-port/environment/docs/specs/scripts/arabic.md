# Arabic script shaping (digest)
Source: Developing OpenType Fonts for Arabic Script - Typography | Microsoft Learn, https://learn.microsoft.com/en-us/typography/script-development/arabic
These notes restate the source's structures and rules; where they differ, the source governs.

## Terms used below

- Base glyph: a glyph able to hold marks. Rules are stated per glyph rather than per character, since a ligature can be the base.
- Character versus glyph: one character has several glyph shapes. For lam (U+0644) the presentation-form code points U+FEDE (final), U+FEDF (initial) and U+FEE0 (medial) are all shapes of the one character.
- Kashida: U+0640 ARABIC TATWEEL. It lengthens the connection between two joined letters and is the means of justification.
- Ligatures come in two kinds: mandatory ones (lam + alef) and optional ones (for example lam + meem in initial position).

## 1. Character analysis and contextual forms

### How the form of a letter is chosen

The engine (not the font) works out the contextual form of every character from its neighbours: the character before it and the character after it. The outcome is one of four forms, and each form selects one GSUB feature for that glyph:

| Contextual form | Feature the engine applies to that glyph |
|---|---|
| isolated | `isol` |
| initial | `init` |
| medial | `medi` |
| final | `fina` |

- The page gives no joining-class table: it does not assign joining types to code points and does not list transparent characters (ones skipped when deciding joins). It only says the form follows from the preceding and following characters. Per-character joining behaviour lives in the Unicode Character Database (ArabicShaping.txt), which the page does not reproduce.
- During the same pass the engine validates combining-mark sequences (section 5).

### Control and helper characters named by the page

| Code point | Character | Role stated by the page |
|---|---|---|
| U+200C | ZERO WIDTH NON-JOINER (ZWNJ) | Placed between two letters, it prevents the cursive join between them. |
| U+200D | ZERO WIDTH JOINER (ZWJ) | Placed between a space and a following mark, it lets the two combine so the mark shows as a standalone sign (section 5). |
| U+200E | LEFT-TO-RIGHT MARK (written "LTR" on the page) | Recommended for every Arabic font; no shaping rule attached. |
| U+200F | RIGHT-TO-LEFT MARK (written "RTL" on the page) | Recommended for every Arabic font; no shaping rule attached. |
| U+25CC | DOTTED CIRCLE | Carrier for invalid marks; every Arabic font needs a glyph for it. |

## 2. Shaping stages

1. Character analysis: assign each character its contextual form (section 1) and check mark combinations, inserting dotted circles where required (section 5).
2. Substitution with GSUB: first map every character to its nominal glyph (for example the default glyph of U+0627), then apply the GSUB features of section 3, one feature at a time, in the listed order.
3. Positioning with GPOS: apply the GPOS features of section 3, one feature at a time, in the listed order.

The engine issues a separate OpenType Layout call for each feature; that is how the feature order is enforced. Within a feature the font's lookup order also matters. Some features are irrelevant for some of the languages written in Arabic script.

## 3. Feature order

Standard order, from the page's feature table (the Status column merges the page's three columns "Always applied", "On by default" and "Off by default"):

| # | Feature | Feature function (page label) | Layout operation | Status | Glyphs affected; who decides |
|---|---|---|---|---|---|
| 1 | `ccmp` | Character composition/decomposition substitution | GSUB | always applied | whole run; the font's lookups decide what changes |
| 2 | `isol` | Isolated character form substitution | GSUB | always applied | only glyphs the engine classed as isolated |
| 3 | `fina` | Final character form substitution | GSUB | always applied | only glyphs the engine classed as final |
| 4 | `medi` | Medial character form substitution | GSUB | always applied | only glyphs the engine classed as medial |
| 5 | `init` | Initial character form substitution | GSUB | always applied | only glyphs the engine classed as initial |
| 6 | `rlig` | Required ligature substitution | GSUB | always applied | whole run; font decides |
| 7 | `rclt` | Required contextual alternates substitution | GSUB | always applied | whole run; font decides |
| 8 | `calt` | Contextual alternates substitution | GSUB | always applied | whole run; font decides |
| 9 | `liga` | Standard ligature substitution | GSUB | on by default | whole run; font decides; the user may turn it off |
| 10 | `dlig` | Discretionary ligature substitution | GSUB | off by default | whole run, only if the user turns it on |
| 11 | `cswh` | Contextual swashes | GSUB | off by default | whole run, only if the user turns it on |
| 12 | `mset` | Mark positioning via substitution | GSUB | always applied | whole run; font decides |
| 13 | `curs` | Cursive positioning | GPOS | always applied | whole run; the font's entry/exit anchors decide |
| 14 | `kern` | Pair kerning | GPOS | always applied | whole run; font decides |
| 15 | `mark` | Mark to base positioning | GPOS | always applied | marks on bases and ligatures; font anchors decide |
| 16 | `mkmk` | Mark to mark positioning | GPOS | always applied | marks on other marks; font anchors decide |

The page groups rows 1-8 as "Language based forms", rows 9-12 as "Typographical forms" and rows 13-16 as "Positioning features".

Notes:

- The four form features run in the order `isol`, `fina`, `medi`, `init` (not initial-first).
- The step list in the page's shaping section names `ccmp`, `isol`, `fina`, `medi`, `init`, `rlig`, `calt` and then `liga`, `dlig`, `cswh`, `mset`; it omits `rclt`. The feature table (above) places `rclt` between `rlig` and `calt`.
- Optional features are toggled for an entire run: a caller-supplied feature list that marks `liga` off disables it, and one that marks `dlig` or `cswh` on enables them.

## 4. Reordering

The page defines no reordering of characters or marks for Arabic.

## 5. Invalid combining marks

### Mechanism

- A combining mark or sign that is not attached to a valid base is invalid. The engine renders it with the Unicode fallback for non-spacing marks (the page cites section 5.12 of Unicode 3.1): the mark is shown on U+25CC DOTTED CIRCLE.
- The dotted circle exists only in the glyph array that the shaping call returns. The engine never writes it into the application's stored text.
- If the font lacks a U+25CC glyph, the invalid mark is drawn on the missing-glyph shape (an empty box) instead.
- Motivation given by the page: on the engine's path for non-OpenType fonts, invalid mark combinations are overstruck (drawn on top of each other); inserting the dotted circle avoids that and makes the error visible.
- To show a mark on its own on purpose, put it on a space (U+0020), as Unicode 3.1 section 2.5 describes, with U+200D ZWJ between the space and the mark. The engine combines the space and the mark only when that ZWJ is present.

### Mark classes used by the validity check

| Class | Description (page label) | Code points |
|---|---|---|
| DIAC1 | Arabic above diacritics | U+064B, U+064C, U+064E, U+064F, U+0652, U+0657, U+0658, U+06E1 |
| DIAC2 | Arabic below diacritics | U+064D, U+0650, U+0656 |
| DIAC3 | Arabic seat shadda | U+0651 |
| DIAC4 | Arabic Qur'anic marks above | U+0610..U+0614, U+0659, U+06D6..U+06DC, U+06DF, U+06E0, U+06E2, U+06E4, U+06E7, U+06E8, U+06EB, U+06EC |
| DIAC5 | Arabic Qur'anic marks below | U+06E3, U+06EA, U+06ED |
| DIAC6 | Arabic superscript alef | U+0670 |
| DIAC7 | Arabic madda | U+0653 |
| DIAC8 | Arabic madda | U+0654, U+0655 |

DIAC8 repeats the DIAC7 label on the page; by Unicode name its members are U+0654 ARABIC HAMZA ABOVE and U+0655 ARABIC HAMZA BELOW.

### Rules

1. A single base may hold no more than one mark from any one class.
2. A DIAC1 mark and a DIAC2 mark may not share a base.
3. When a sequence breaks rule 1 or 2, the mark responsible for the conflict (in logical order, the one that arrives second) is put on a dotted circle rather than on the base.

Example given by the page: two fathas on one letter, such as U+0628 U+064E U+064E. The second U+064E is displayed on a dotted circle.

## 6. What each feature does in Arabic

- `ccmp`: runs before every other feature so the font can merge several glyphs into one (ligature substitution, GSUB lookup type 4) or split one glyph into several (multiple substitution, GSUB lookup type 2). Example: alef U+0627 followed by hamza above U+0654 can be merged into the alef-with-hamza-above glyph (the glyph of U+0623). The page also shows a decomposition case, motivated by applications that colour diacritics separately from letters.
- `isol`: single substitution (GSUB type 1) to the isolated shape. Often that is the nominal glyph itself; the font's cmap may map both the base character and its isolated presentation-form code point to one glyph.
- `fina`, `medi`, `init`: single substitutions (GSUB type 1) to the final, medial and initial shapes.
- `rlig`: ligatures that must always form, lam + alef (U+0644 U+0627) being the standard case; GSUB type 4. In any ligature lookup, sequences with more components must be listed before shorter ones, or the longer ones can never match. Ligatures the user should be able to refuse belong in `liga`, not here.
- `rclt`: contextual alternates required for correct rendering of the script (chaining context substitution, GSUB type 6).
- `calt`: contextual alternates that give better joins or a more calligraphic result (GSUB type 6). For Arabic the engine always applies `calt`, so documents set with older fonts keep working; fonts that must also serve systems unaware of `rclt` repeat their `rclt` rules inside `calt`.
- `liga`: optional ligatures that are active unless the user disables them (GSUB type 4, longest sequences first). Examples: lam + meem (U+0644 U+0645); yeh + noon (U+064A U+0646) when the yeh is medial and the noon final.
- `dlig`: further optional ligatures that stay inactive unless the user enables them (GSUB type 4, longest sequences first).
- `cswh`: replaces glyphs with swash variants according to the surrounding glyphs, for example a wide swash noon (U+0646) when the glyphs after it stay above the baseline. One-to-one cases use single substitution (GSUB type 1) and choices among several variants use alternate substitution (GSUB type 3); a font may also put everything in type 3 lookups. When the font has several swash styles, each character's variants should be listed in a consistent order.
- `mset`: an older way to place marks by swapping in a mark glyph drawn at the right height for the base, used in Microsoft's Windows 95 Arabic fonts through contextual substitution (GSUB type 5). Examples: fatha (U+064E) swapped for a lower variant over beh (U+0628); hamza above (U+0654) needing a different position over yeh barree (U+06D2) than over alef (U+0627). GPOS `mark` gives better results.
- `curs`: cursive attachment (GPOS type 3), aligning each glyph's exit point with the entry point of the next glyph. This can shift glyphs vertically: in a Nastaliq-style font an initial sheen (U+0634) is raised so that it meets a following final meem (U+0645).
- `kern`: spacing adjustments between pairs of base glyphs (GPOS type 2, or chained context positioning, type 8); can also carry device-table size tweaks, cross-stream (vertical) shifts and placement changes that leave the advance alone. Individual pairs come before class-based pairs so they can override them; rules for three or four glyphs come before the pairs. Not intended for monospaced fonts.
- `mark`: attaches a mark to a base glyph (MarkToBase, GPOS type 4) or to a component of a ligature glyph (MarkToLigature, GPOS type 5).
- `mkmk`: attaches a mark to another mark (MarkToMark, GPOS type 6).

## 7. Script and language system tags

Script tag: `arab` (Arabic).

| Language system tag | Language |
|---|---|
| `dflt` | default script handling |
| `"ARA "` | Arabic |
| `"BLI "` | Baluchi |
| `"BLT "` | Balti |
| `"BBR "` | Berber |
| `"BRH "` | Brahui |
| `"FAR "` | Persian |
| `"FUL "` | Fulah |
| `"HAU "` | Hausa |
| `"HND "` | Hindko |
| `"KNR "` | Kanuri |
| `"KSH "` | Kashmiri |
| `"KHW "` | Khowar |
| `"KUR "` | Kurdish |
| `"LDK "` | Ladakhi |
| `"MLY "` | Malay |
| `"MND "` | Mandinka |
| `"PAS "` | Pashto |
| `"PAN "` | Punjabi |
| `"SRK "` | Saraiki |
| `"SND "` | Sindhi |
| `"SML "` | Somali |
| `"SWK "` | Swahili |
| `"URD "` | Urdu |
| `"UYG "` | Uyghur |

- Tags are case-sensitive and exactly four characters long: script tags are lower case, language system tags upper case, and a three-letter language tag is padded with one trailing space (shown inside quotes above).
- Every font should carry a `dflt` language system under the script. It is the fallback when no language-specific system matches or when the application does not support the language; some applications fail on fonts without it.
- The Microsoft engine described by the page uses only the default language system; language-specific features serve other applications.
