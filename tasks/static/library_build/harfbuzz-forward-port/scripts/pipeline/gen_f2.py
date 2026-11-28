"""Candidate generators for units 12-18, 27, 29 and 31: syllable matching, normalization, feature ranges, not-found
glyphs, glyph caches, mark attachment, fallback mark positioning, glyph flags and `gvar` variations.

Runs inside the pipeline image only (it builds fonts with fontTools and reads the downloaded fonts). Development
tooling, never shipped. Every synthetic font here is ours: box outlines and the one table feature a unit needs.

Each generator labels its candidates with `nb`: `in` inside the unit's stated condition (`in:<part>` where the
generator knows which part of it), or the boundary neighbour (one stated condition negated) a candidate sits on.
Inputs that 15.2.0 changes beyond what a note says are not generated, or are generated with an `x:` label and never
graded; each generator's docstring names them.

Units 28 and 30 have no generator: no shaping output shows their change. At the graphemes cluster level every
syllabic shaper flags each syllable before it reorders it, so the flags 15.2.0 adds are already set; and the `avar`
fix changes a branch that only a normalized coordinate below -1 reaches, while the library clamps coordinates to
[-1, +1] before the segment maps.
"""

from __future__ import annotations

import random
import struct
import unicodedata
from collections.abc import Iterator
from pathlib import Path

from casekit import Font, case
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import _k_e_r_n
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from synth_fonts import add_raw_table, kerx_format0

UPEM = 1000
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Outline boxes (x0, y0, x1, y1) by shape; marks have no advance and sit left of their origin, as in most fonts.
SHAPES = {
    "base": lambda w: (50, 0, w - 50, 700),
    "above": lambda w: (-250, 760, -50, 900),
    "below": lambda w: (-250, -240, -50, -100),
    "overlay": lambda w: (-300, 300, -20, 400),
    "attached-below": lambda w: (-200, -150, -80, 0),
    "above-right": lambda w: (-120, 600, -20, 720),
    "wide-above": lambda w: (-600, 760, 100, 860),
    "wide-below": lambda w: (-600, -200, 100, -100),
}


def _outline(shape: str, width: int):
    pen = TTGlyphPen(None)
    if shape in SHAPES:
        x0, y0, x1, y1 = SHAPES[shape](width)
        pen.moveTo((x0, y0))
        pen.lineTo((x0, y1))
        pen.lineTo((x1, y1))
        pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def _builder(
    family: str,
    glyphs: list[tuple[str, int, str]],
    cmap: dict[int, str],
    vertical: bool = False,
) -> FontBuilder:
    """A TrueType font from (name, advance, shape) triples in glyph order; shape "empty" has no outline."""
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder([g[0] for g in glyphs])
    fb.setupCharacterMap(cmap)
    fb.setupGlyf({name: _outline(shape, adv) for name, adv, shape in glyphs})
    fb.setupHorizontalMetrics(
        {
            name: (adv, SHAPES[shape](adv)[0] if shape in SHAPES else 0)
            for name, adv, shape in glyphs
        }
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    if vertical:
        fb.setupVerticalMetrics({g[0]: (1000, 100) for g in glyphs})
        fb.setupVerticalHeader(ascent=500, descent=-500)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    return fb


def _latin(
    family: str, extra: list[tuple[str, int, str, int | None]] = (), vertical=False
) -> FontBuilder:
    """.notdef, space, A-Z (boxes of different widths) and extra (name, advance, shape, code point) glyphs."""
    glyphs = [(".notdef", 500, "base"), ("space", 250, "empty")]
    glyphs += [(c, 500 + 20 * i, "base") for i, c in enumerate(LETTERS)]
    cmap = {0x20: "space", **{ord(c): c for c in LETTERS}}
    for name, adv, shape, cp in extra:
        glyphs.append((name, adv, shape))
        if cp is not None:
            cmap[cp] = name
    return _builder(family, glyphs, cmap, vertical)


def _gdef(bases, ligatures, marks) -> str:
    def cls(names) -> str:
        return f"[{' '.join(names)}]" if names else ""

    return f"table GDEF {{ GlyphClassDef {cls(bases)}, {cls(ligatures)}, {cls(marks)}, ; }} GDEF;\n"


# ---------------------------------------------------------------------------------------------------------------
# Unit 12: per-syllable GSUB lookups no longer match a glyph 15 syllables later.

U12_MY_CONS = list(range(0x1000, 0x1021))
U12_MY = {"bt": (0x102D, 0x102F), "la": (0x102E, 0x1030), "lig": (0x1036, 0x1037)}
U12_MY_NEUTRAL = (0x1032, 0x103D)
U12_DV_CONS = [cp for cp in range(0x0915, 0x093A) if cp not in (0x0929, 0x0931, 0x0934)]
U12_DV = {"bt": (0x0947, 0x0902), "la": (0x0941, 0x0903), "lig": (0x0948, 0x0901)}
U12_DV_NEUTRAL = (0x0942, 0x0943)


def _u12_font(
    out: Path,
    name: str,
    script: str,
    cons: list[int],
    pairs: dict[str, tuple[int, int]],
    neutral: tuple[int, ...],
    features: dict[str, str],
) -> None:
    """Three lookups that skip bases and every mark outside their pair (a mark filtering set):
    `bt` substitutes B after an earlier A (backtrack), `la` substitutes A before a later B (lookahead), `lig`
    ligates A and B. A per-syllable feature limits them to one syllable."""
    glyphs = [(".notdef", 500, "base"), ("space", 250, "empty")]
    glyphs.append(("dottedcircle", 600, "base"))
    cmap = {0x20: "space", 0x25CC: "dottedcircle"}
    bases = ["dottedcircle"]
    for i, cp in enumerate(cons):
        g = f"c{cp:04X}"
        glyphs.append((g, 500 + 10 * (i % 20), "base"))
        cmap[cp] = g
        bases.append(g)
    marks = []
    for cp in sorted({cp for p in pairs.values() for cp in p} | set(neutral)):
        g = f"m{cp:04X}"
        glyphs.append((g, 0, "above"))
        cmap[cp] = g
        marks.append(g)
    (a_bt, b_bt), (a_la, b_la), (a_lg, b_lg) = pairs["bt"], pairs["la"], pairs["lig"]
    alt_bt, alt_la, lig = (
        f"m{b_bt:04X}.alt",
        f"m{a_la:04X}.alt",
        f"m{a_lg:04X}_{b_lg:04X}",
    )
    for g in (alt_bt, alt_la, lig):
        glyphs.append((g, 0, "below"))
        marks.append(g)
    m = lambda cp: f"m{cp:04X}"
    fea = f"languagesystem DFLT dflt;\nlanguagesystem {script} dflt;\n"
    fea += _gdef(bases, [], marks)
    fea += f"@F_BT = [{m(a_bt)} {m(b_bt)}];\n@F_LA = [{m(a_la)} {m(b_la)}];\n@F_LG = [{m(a_lg)} {m(b_lg)}];\n"
    fea += f"lookup SUB_BT {{ sub {m(b_bt)} by {alt_bt}; }} SUB_BT;\n"
    fea += f"lookup SUB_LA {{ sub {m(a_la)} by {alt_la}; }} SUB_LA;\n"
    fea += (
        "lookup BT { lookupflag IgnoreBaseGlyphs UseMarkFilteringSet @F_BT; "
        f"sub {m(a_bt)} {m(b_bt)}' lookup SUB_BT; }} BT;\n"
        "lookup LA { lookupflag IgnoreBaseGlyphs UseMarkFilteringSet @F_LA; "
        f"sub {m(a_la)}' lookup SUB_LA {m(b_la)}; }} LA;\n"
        "lookup LG { lookupflag IgnoreBaseGlyphs UseMarkFilteringSet @F_LG; "
        f"sub {m(a_lg)} {m(b_lg)} by {lig}; }} LG;\n"
    )
    by_tag: dict[str, list[str]] = {}
    for key, lookup in (("bt", "BT"), ("la", "LA"), ("lig", "LG")):
        by_tag.setdefault(features[key], []).append(lookup)
    for tag, lookups in by_tag.items():
        fea += (
            f"feature {tag} {{ "
            + " ".join(f"lookup {lk};" for lk in lookups)
            + f" }} {tag};\n"
        )
    fb = _builder(name, glyphs, cmap)
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(out / f"{name}.ttf"))


def _u12_fonts(out: Path) -> None:
    _u12_font(
        out, "u12-mymr", "mym2", U12_MY_CONS, U12_MY, U12_MY_NEUTRAL,
        {"bt": "blwf", "la": "pstf", "lig": "ccmp"},
    )  # fmt: skip
    _u12_font(
        out, "u12-deva-ps", "dev2", U12_DV_CONS, U12_DV, U12_DV_NEUTRAL,
        {"bt": "abvs", "la": "blws", "lig": "abvs"},
    )  # fmt: skip
    _u12_font(
        out, "u12-deva-calt", "dev2", U12_DV_CONS, U12_DV, U12_DV_NEUTRAL,
        {"bt": "calt", "la": "calt", "lig": "calt"},
    )  # fmt: skip


def _u12_text(
    rng: random.Random,
    cons: list[int],
    pair: tuple[int, int],
    neutral: tuple[int, ...],
    distance: int,
) -> list[int]:
    """Syllables of one consonant (sometimes with a mark outside every pair); A opens the matching syllable and B
    sits `distance` syllables later (0: both in one syllable)."""

    def syllable() -> list[int]:
        s = [rng.choice(cons)]
        if rng.random() < 0.3:
            s.append(rng.choice(neutral))
        return s

    a, b = pair
    text: list[int] = []
    for _ in range(rng.randrange(0, 4)):
        text += syllable()
    if distance == 0:
        text += [rng.choice(cons), a, b]
    else:
        text += [rng.choice(cons), a]
        for _ in range(distance - 1):
            text += syllable()
        text += [rng.choice(cons), b]
    for _ in range(rng.randrange(0, 3)):
        text += syllable()
    return text


def gen_u12(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 12: a per-syllable GSUB lookup that skips glyphs no longer matches a glyph 15 syllables later.

    Inside: a lookup of a per-syllable feature (Myanmar `blwf`, `pstf`, `ccmp`; Devanagari `abvs`, `blws`) whose
    context, lookahead or ligature skips 14 whole syllables to a glyph in the 15th syllable after its own, which
    carries the same 4-bit syllable serial. Neighbours: the same text 13, 14, 16 or 17 syllables apart
    (`b:other-distance`), both glyphs in one syllable (`b:same-syllable`), and the same lookups under `calt`, which
    is not per-syllable and crosses syllables in every release (`b:not-per-syllable`). Matches 30 or more
    syllables apart are left out: the note speaks of 15. Texts stay far below the maximum syllable length.
    """
    fonts = {
        "mymr": (synth / "u12-mymr.ttf", U12_MY_CONS, U12_MY, U12_MY_NEUTRAL),
        "ps": (synth / "u12-deva-ps.ttf", U12_DV_CONS, U12_DV, U12_DV_NEUTRAL),
        "calt": (synth / "u12-deva-calt.ttf", U12_DV_CONS, U12_DV, U12_DV_NEUTRAL),
    }
    for _ in range(n):
        kind = rng.choice(("mymr", "mymr", "ps", "calt"))
        path, cons, pairs, neutral = fonts[kind]
        pair = pairs[rng.choice(("bt", "la", "lig"))]
        if kind == "calt":
            distance = rng.choice((15, 15, 15, 14, 16, 13, 17))
            nb = "b:not-per-syllable"
        else:
            shape = rng.choice(("in",) * 5 + ("near",) * 3 + ("same",) * 2)
            distance = {"in": 15, "near": rng.choice((13, 14, 16, 17)), "same": 0}[
                shape
            ]
            nb = {"in": "in", "near": "b:other-distance", "same": "b:same-syllable"}[
                shape
            ]
        text = _u12_text(rng, cons, pair, neutral, distance)
        yield case("12", "cand", path, text, nb=nb, cl=rng.choice((0, 1, 2)))


# ---------------------------------------------------------------------------------------------------------------
# Unit 13: precomposed characters in text with no marks (Indic, Khmer, Myanmar, USE).

# Per script: letters, letters whose canonical decomposition the shaper recomposes (Devanagari NNNA and LLLA,
# Bengali YYA through the Indic shaper's own exception, Myanmar UU, Balinese letters with the tedung), composition
# exclusions it decomposes and never recomposes, and marks without a decomposition or a combining class.
U13_SCRIPTS = {
    "deva": (
        [cp for cp in range(0x0915, 0x093A) if cp not in (0x0929, 0x0931, 0x0934)],
        [0x0929, 0x0934],
        list(range(0x0958, 0x0960)),
        [0x0902, 0x093E, 0x0940, 0x0941, 0x0947],
        [0x093C, 0x094D],
    ),
    "beng": (
        [cp for cp in range(0x0995, 0x09BA) if unicodedata.category(chr(cp)) == "Lo"],
        [0x09DF],
        [],
        [0x0981, 0x0982, 0x09BE, 0x09C0, 0x09C1],
        [0x09BC, 0x09CD],
    ),
    "mymr": (
        list(range(0x1000, 0x1026)),
        [0x1026],
        [],
        [0x102B, 0x102C, 0x102D, 0x1036],
        [0x102E],
    ),
    "bali": (
        [
            cp
            for cp in range(0x1B05, 0x1B34)
            if cp not in (0x1B06, 0x1B08, 0x1B0A, 0x1B0C, 0x1B0E, 0x1B12)
        ],
        [0x1B06, 0x1B08, 0x1B0A, 0x1B0C, 0x1B0E, 0x1B12],
        [],
        [0x1B00, 0x1B01, 0x1B34, 0x1B36, 0x1B38],
        [0x1B35],
    ),
}


# Khmer: consonants, vowel signs and other signs that have no decomposition and are not split vowels (the Khmer
# shaper splits U+17BE..U+17C0, U+17C4 and U+17C5 itself and never recomposes them), and the Latin letters whose
# canonical decomposition is one base letter and one combining mark, with their parts.
U13_KHMER_CONS = list(range(0x1780, 0x17A3))
U13_KHMER_MARKS = [0x17B6, *range(0x17B7, 0x17BE), 0x17C6, 0x17C7, 0x17C8, 0x17C9]


def _u13_latin() -> dict[int, tuple[int, int]]:
    """Latin-1 and Latin Extended-A letters whose canonical decomposition is a basic Latin letter and a mark."""
    out = {}
    for cp in range(0xC0, 0x180):
        d = unicodedata.decomposition(chr(cp))
        if not d or d.startswith("<"):
            continue
        parts = [int(x, 16) for x in d.split()]
        if (
            len(parts) == 2
            and chr(parts[0]).isascii()
            and chr(parts[0]).isalpha()
            and 0x300 <= parts[1] < 0x370
        ):
            out[cp] = (parts[0], parts[1])
    return out


def _u13_fonts(out: Path) -> None:
    """Devanagari, Bengali, Myanmar and Balinese letters, their precomposed letters and the parts of those, and no
    layout tables: a decomposed letter shows as two glyphs, a recomposed one as one. u13-khmer: Khmer letters and
    signs, and Latin precomposed letters with their parts, also without layout tables."""
    glyphs = [(".notdef", 500, "base"), ("space", 250, "empty")]
    cmap = {0x20: "space"}
    for letters, recomposed, excluded, marks, parts in U13_SCRIPTS.values():
        for i, cp in enumerate(letters + recomposed + excluded):
            glyphs.append((f"u{cp:04X}", 500 + 10 * (i % 25), "base"))
            cmap[cp] = f"u{cp:04X}"
        for cp in marks + parts:
            glyphs.append((f"u{cp:04X}", 0, "above"))
            cmap[cp] = f"u{cp:04X}"
    _builder("u13-indic", glyphs, cmap).save(str(out / "u13-indic.ttf"))
    latin = _u13_latin()
    bases = sorted(
        {b for b, _ in latin.values()} | {*range(0x41, 0x5B), *range(0x61, 0x7B)}
    )
    marks = sorted({m for _, m in latin.values()})
    glyphs = [(".notdef", 500, "base"), ("space", 250, "empty")]
    cmap = {0x20: "space"}
    for i, cp in enumerate(U13_KHMER_CONS + bases + sorted(latin)):
        glyphs.append((f"u{cp:04X}", 500 + 10 * (i % 25), "base"))
        cmap[cp] = f"u{cp:04X}"
    for cp in U13_KHMER_MARKS + marks:
        glyphs.append((f"u{cp:04X}", 0, "above"))
        cmap[cp] = f"u{cp:04X}"
    _builder("u13-khmer", glyphs, cmap).save(str(out / "u13-khmer.ttf"))


def _decomposes(f: Font, cp: int) -> bool:
    d = unicodedata.decomposition(chr(cp))
    if not d or d.startswith("<"):
        return False
    parts = [int(x, 16) for x in d.split()]
    return f.has(cp, *parts)


def gen_u13(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 13: precomposed characters no longer stay decomposed in text with no marks.

    Inside (`in:<script>`): a precomposed letter the shaper decomposes and recomposes (Devanagari U+0929, U+0934,
    Bengali U+09DF, Myanmar U+1026, Balinese letters with the tedung), in a font with glyphs for it and its parts,
    in text whose input has no marks. Our font has no layout tables, so the decomposed letter shows as two glyphs;
    Noto Sans Myanmar shows U+1026 the same way (the other Noto fonts compose the parts back with `GSUB`, so they
    show nothing). Neighbours: the same text with a mark elsewhere, which recomposes in every release
    (`b:has-mark`); and Latin precomposed letters the font has, which the default shaper never decomposes
    (`b:other-shaper`). Devanagari composition exclusions (U+0958..U+095F), which stay decomposed in every release,
    are left out (`x:exclusion`): read literally, "precomposed characters that stayed decomposed" covers them too.
    Latin letters the font lacks are left out: their partial recomposition is a 15.2.0 change outside the four
    shapers the note names.

    Khmer has no precomposed letter that is not itself a mark (its split vowels are marks, and the Khmer shaper
    never recomposes them), so its cases are those of upstream's own test for this fix: a Latin precomposed letter
    in text the Khmer shaper shapes (`script=Khmr`, or Khmer text before it), in u13-khmer (`in:khmr`); the same
    text with a Khmer vowel sign after a consonant (`b:has-mark`); the letter in Latin text in the same font
    (`b:other-shaper`). They follow the main loop, so the other candidates are as before.
    """
    ours = Font(synth / "u13-indic.ttf")
    pools = [
        (
            ours.path,
            [cp for cp in rec if _decomposes(ours, cp)],
            [cp for cp in exc if _decomposes(ours, cp)],
            cons,
            marks,
            f"in:{script}",
        )
        for script, (cons, rec, exc, marks, _) in U13_SCRIPTS.items()
    ]
    myanmar = noto["NotoSansMyanmar-Regular"]
    if _decomposes(myanmar, 0x1026):
        cons, _, _, marks, _ = U13_SCRIPTS["mymr"]
        pools.append(
            (
                myanmar.path,
                [0x1026],
                [],
                [cp for cp in cons if myanmar.has(cp)],
                [cp for cp in marks if myanmar.has(cp)],
                "in:mymr-noto",
            )
        )
    latin = noto["NotoSans-VF"]
    latin_pre = [
        cp for cp in range(0xC0, 0x180) if _decomposes(latin, cp) and latin.has(cp)
    ]
    latin_plain = [cp for cp in range(0x61, 0x7B)]
    for i in range(n):
        if i % 10 == 9:
            words = [rng.choice(latin_plain) for _ in range(rng.randrange(0, 4))]
            words.insert(rng.randrange(0, len(words) + 1), rng.choice(latin_pre))
            yield case(
                "13",
                "cand",
                latin,
                words,
                nb="b:other-shaper",
                cl=rng.choice((0, 1, 2)),
            )
            continue
        path, inside, excluded, cons, marks, label = pools[i % len(pools)]
        shape = rng.choice(
            ("in", "in", "in", "mark", "mark") + (("excl", "excl") if excluded else ())
        )
        letter = rng.choice(excluded if shape == "excl" else inside)
        text = [rng.choice(cons) for _ in range(rng.randrange(0, 4))]
        text.insert(rng.randrange(0, len(text) + 1), letter)
        if rng.random() < 0.3:
            text.insert(rng.randrange(1, len(text) + 1), 0x20)
            if text[-1] == 0x20:
                text.append(rng.choice(cons))
        if shape == "mark":
            # A mark after a consonant or after the letter itself: the input then has a mark.
            spots = [k + 1 for k, cp in enumerate(text) if cp != 0x20]
            text.insert(rng.choice(spots), rng.choice(marks))
        nb = {"in": label, "mark": "b:has-mark", "excl": "x:exclusion"}[shape]
        yield case("13", "cand", path, text, nb=nb, cl=rng.choice((0, 1, 2)))
    khmer = synth / "u13-khmer.ttf"
    letters = sorted(_u13_latin())
    shapes = ("in",) * 30 + ("mark",) * 40 + ("latin",) * 30
    for shape in shapes:
        cons = [rng.choice(U13_KHMER_CONS) for _ in range(rng.randrange(0, 4))]
        text = list(cons)
        text.insert(rng.randrange(1 if cons else 0, len(text) + 1), rng.choice(letters))
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        if shape == "latin":
            # The same letter in Latin text: the default shaper keeps the precomposed glyph.
            text = [rng.choice(range(0x61, 0x7B)) for _ in range(rng.randrange(0, 3))]
            text.insert(rng.randrange(0, len(text) + 1), rng.choice(letters))
            if rng.random() < 0.5:
                opts["script"] = "Latn"
            yield case("13", "cand", khmer, text, nb="b:other-shaper", **opts)
            continue
        if not cons or rng.random() < 0.5:
            opts["script"] = "Khmr"
        if shape == "mark":
            if not cons:
                text.insert(0, rng.choice(U13_KHMER_CONS))
            spots = [k + 1 for k, cp in enumerate(text) if cp in U13_KHMER_CONS]
            text.insert(rng.choice(spots), rng.choice(U13_KHMER_MARKS))
        nb = "in:khmr" if shape == "in" else "b:has-mark"
        yield case("13", "cand", khmer, text, nb=nb, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 14: a global feature request overrides earlier ranged requests for the same feature.

U14_WORDS = ["AVATAR office 1/20", "Toyota WAVE fifty 3/4 10", "LYNX affluent 1/2 AWAY 2024",
             "Type ff fl ffi 0 To", "WAVY fjord 1/8 LT 905"]  # fmt: skip
# What each tag changes in Noto Sans and Noto Serif, as substrings: kerning pairs, ligatures, letters, digits.
U14_KERN = [
    "AV",
    "VA",
    "AT",
    "TA",
    "To",
    "Wa",
    "WA",
    "AW",
    "AY",
    "YA",
    "LT",
    "LY",
    "Yo",
    "Te",
    "VY",
]
U14_TARGETS = {
    "kern": U14_KERN,
    "liga": ["ffi", "ff", "fi", "fl"],
    "smcp": list("abcdefghijklmnopqrstuvwxyz"),
    "c2sc": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    "onum": list("123456789"),
    "sups": list("0123456789"),
    "zero": ["0"],
    "frac": ["1/20", "3/4", "1/2", "1/8"],
}


def _u14_span(
    rng: random.Random, word: str, targets: list[str]
) -> tuple[int, int] | None:
    """A range of cluster indices that covers one occurrence of a target, widened by up to two characters."""
    spots = [
        (i, i + len(t))
        for t in targets
        for i in range(len(word))
        if word.startswith(t, i)
    ]
    if not spots:
        return None
    s, e = rng.choice(spots)
    return max(0, s - rng.randrange(0, 3)), min(len(word), e + rng.randrange(0, 3))


def gen_u14(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 14: a later global request for a feature overrides its earlier ranged requests.

    Inside: one or two ranged requests for a tag, then a global request for the same tag with another value: a
    range value of 0 or 2 before a global 1 (14.3.0 then switches off every global feature over the range), or a
    range value of 0 before a global 2 (14.3.0 keeps the range's value). Every range covers text the request acts
    on: a kerning pair or ligature for a global 1, the tag's own target for a global 2. Neighbours: the global
    request first and the ranged one after it, which keeps its range in every release (`b:global-first`, its range
    over the tag's own target); a ranged request for one tag and a global request for another (`b:other-tag`); two
    ranged requests for one tag (`b:two-ranged`).
    """
    fonts = [noto["NotoSans-VF"], noto["NotoSerif-VF"]]
    shared = U14_KERN + U14_TARGETS["liga"]
    for i in range(n):
        f = fonts[i % len(fonts)]
        tags = sorted(t for t in U14_TARGETS if t in f.features)
        shape = rng.choice(("in", "in", "in", "in", "first", "first", "other", "two"))
        if shape == "first":
            # One request switches the feature on, the other off, over text the feature changes.
            tag = rng.choice([t for t in tags if t != "frac"])
            v_range, v_global = rng.choice(((0, 1), (1, 0)))
        else:
            tag = rng.choice(tags)
            if shape == "in":
                v_range, v_global = rng.choice(((0, 1), (0, 1), (2, 1), (0, 2)))
            else:
                v_range, v_global = rng.choice(((0, 1), (1, 0), (1, 0), (2, 1), (0, 2)))
        other = rng.choice([t for t in tags if t != tag])
        targets = shared if (shape, v_global) == ("in", 1) else U14_TARGETS[tag]
        word = rng.choice(
            [w for w in U14_WORDS if any(t in w for t in targets)] or U14_WORDS
        )
        start, end = _u14_span(rng, word, targets) or _u14_span(rng, word, shared)
        if shape == "in":
            pre = f"{tag}={v_range}@{start}:{end}"
            if rng.random() < 0.3:
                s2, e2 = _u14_span(rng, word, shared)
                pre += f",{tag}={v_range}@{s2}:{e2}"
            feat = f"{pre},{tag}={v_global}"
        elif shape == "first":
            feat = f"{tag}={v_global},{tag}={v_range}@{start}:{end}"
        elif shape == "other":
            feat = f"{tag}={v_range}@{start}:{end},{other}={v_global}"
        else:
            s2, e2 = _u14_span(rng, word, shared)
            feat = f"{tag}={v_range}@{start}:{end},{tag}={v_global}@{s2}:{e2}"
        opts: dict[str, object] = {"feat": feat}
        if rng.random() < 0.3:
            opts["var"] = f"wght={rng.choice((300, 700))}"
        nb = {
            "in": "in",
            "first": "b:global-first",
            "other": "b:other-tag",
            "two": "b:two-ranged",
        }[shape]
        yield case("14", "cand", f, [ord(c) for c in word], nb=nb, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 15: an unsupported character followed by a variation selector gets the buffer's not-found glyph.

U15_SELECTORS = [*range(0xFE00, 0xFE10), *range(0xE0100, 0xE0105)]


def _glyph_ids(path: Path) -> dict[int, int]:
    font = TTFont(str(path), lazy=True)
    order = {name: i for i, name in enumerate(font.getGlyphOrder())}
    return {cp: order[name] for cp, name in (font.getBestCmap() or {}).items()}


def _uvs_bases(path: Path) -> set[int]:
    """Characters with at least one variation sequence in a `cmap` format 14 subtable."""
    font = TTFont(str(path), lazy=True)
    out: set[int] = set()
    for sub in font["cmap"].tables:
        if sub.format == 14:
            for seqs in sub.uvsDict.values():
                out |= {base for base, _ in seqs}
    return out


def gen_u15(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 15: an unsupported character followed by a variation selector gets the not-found glyph set on the buffer.

    Inside: a character the font lacks, then a selector, with a non-zero not-found glyph set. Neighbours: the
    same character without a selector (`b:no-selector`), a supported character with a selector the font has no
    sequence for, which keeps its own glyph (`b:supported-base`), and the not-found glyph left at 0 (`b:no-nf`).
    Supported characters that have any variation sequence in the font are left out.
    """
    fonts = [noto["NotoSansHebrew-Regular"], noto["NotoSans-VF"]]
    gids = {f.path: _glyph_ids(f.path) for f in fonts}
    uvs = {f.path: _uvs_bases(f.path) for f in fonts}
    for i in range(n):
        f = fonts[i % len(fonts)]
        nf = rng.choice((1, 2, 3, 7))
        present = sorted(
            cp
            for cp in f.cmap
            if cp > 0x20 and cp not in uvs[f.path] and gids[f.path][cp] not in (0, nf)
        )
        missing = next(
            cp
            for cp in (rng.randrange(0x4E00, 0x9FFF) for _ in range(50))
            if cp not in f.cmap
        )
        shape = rng.choice(
            ("in", "in", "in", "nosel", "supported", "supported", "nonf")
        )
        text = {
            "in": [missing, rng.choice(U15_SELECTORS)],
            "nosel": [missing],
            "supported": [rng.choice(present), rng.choice(U15_SELECTORS)],
            "nonf": [missing, rng.choice(U15_SELECTORS)],
        }[shape]
        if rng.random() < 0.4:
            text = [rng.choice(present), *text]
        opts = {} if shape == "nonf" else {"nf": nf}
        nb = {
            "in": "in",
            "nosel": "b:no-selector",
            "supported": "b:supported-base",
            "nonf": "b:no-nf",
        }[shape]
        yield case("15", "cand", f, text, nb=nb, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 16: out-of-range glyph IDs no longer break the layout coverage caches.

U16_KERN = {("A", "Y"): -90, ("A", "O"): -40, ("T", "O"): -70, ("T", "J"): -50, ("L", "Y"): -110,
            ("L", "O"): -30, ("P", "J"): -60, ("P", "Q"): -20}  # fmt: skip
U16_LIGA = {("F", "I"): "f_i", ("F", "H"): "f_h", ("S", "K"): "s_k", ("S", "H"): "s_h"}
U16_FIRSTS = "ATLPFS"
U16_OTHER = "BCDEGMNRUVWXZ"
U16_NUM_GLYPHS = (
    32  # .notdef, space, A-Z, four ligatures; oor1 (32) and oor2 (33) lie beyond it
)


def _set_num_glyphs(path: Path, count: int) -> None:
    """Rewrite `maxp.numGlyphs` in place, so the glyphs after `count` exist in the other tables but are out of range."""
    data = bytearray(path.read_bytes())
    num_tables = struct.unpack(">H", data[4:6])[0]
    for k in range(num_tables):
        tag, _, offset, _ = struct.unpack(">4sIII", data[12 + 16 * k : 28 + 16 * k])
        if tag == b"maxp":
            data[offset + 4 : offset + 6] = struct.pack(">H", count)
    path.write_bytes(bytes(data))


def _u16_fonts(out: Path) -> None:
    """Pair kerning (`GPOS` PairPos) and ligatures (`GSUB`), whose coverage lookups 14.3.0 caches by glyph ID, plus
    two glyphs beyond `maxp.numGlyphs` that a single substitution (oor1 -> Q) and a kerning pair (oor2 Y) cover.
    The changed cases run on u16-in, the neighbours on u16-held, an identical copy: a glyph ID that aliases a
    covered glyph in 14.3.0's cache leaves the cache wrong for later text in the same font object."""
    fb = _latin(
        "u16",
        [(g, 900, "base", None) for g in U16_LIGA.values()]
        + [("oor1", 600, "base", None), ("oor2", 600, "base", None)],
    )
    fea = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n"
    fea += (
        "feature liga { "
        + " ".join(f"sub {a} {b} by {g};" for (a, b), g in U16_LIGA.items())
        + " } liga;\n"
    )
    fea += "feature liga { sub oor1 by Q; } liga;\n"
    fea += "feature kern { " + " ".join(
        f"pos {a} {b} {v};" for (a, b), v in U16_KERN.items()
    )
    fea += " pos oor2 Y -77; } kern;\n"
    addOpenTypeFeaturesFromString(fb.font, fea)
    path = out / "u16-in.ttf"
    fb.save(str(path))
    _set_num_glyphs(path, U16_NUM_GLYPHS)
    (out / "u16-held.ttf").write_bytes(path.read_bytes())


def _u16_gid(letter: str) -> int:
    return 2 + LETTERS.index(letter)


def _u16_tokens(first: str) -> list[str]:
    return [b for (a, b) in U16_KERN if a == first] + [
        b for (a, b) in U16_LIGA if a == first
    ]


def gen_u16(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 16: out-of-range glyph IDs no longer make lookups skip glyphs they cover.

    14.3.0 stored the coverage of a glyph ID at or above 65536 in a cache slot it shares with a glyph below
    65536 whose ID has the same low 16 bits, so that glyph then counted as not covered. The out-of-range glyph
    comes from the buffer's not-found glyph (`nf`), given to the lowercase letters the font lacks.

    Inside (font u16-in): a not-found glyph G + k * 65536 before every use of a kerning or ligature first glyph
    G, followed by its partner. Neighbours (font u16-held): an in-range not-found glyph (`b:in-range-nf`) and an
    out-of-range one that aliases no covered glyph (`b:no-alias`). An out-of-range glyph that the font's own lookups
    cover (IDs 32 and 33, beyond `maxp.numGlyphs`) is left out (`x:oor-covered`): every release keeps applying those
    lookups, while "out-of-range glyph IDs" can be read as IDs at or above the font's glyph count. An out-of-range
    glyph after its aliased glyph is left out too: 14.3.0's result then depends on the text shaped before it.
    """
    in_font, held = synth / "u16-in.ttf", synth / "u16-held.ttf"
    lower = [ord(c) for c in "abcdeghkmnrsuvwxz"]
    for _ in range(n):
        shape = rng.choice(
            ("in",) * 4 + ("inrange", "noalias", "noalias", "oor", "oor")
        )
        first = rng.choice(U16_FIRSTS)
        if shape == "in":
            text = [ord(rng.choice(U16_OTHER)) for _ in range(rng.randrange(0, 3))]
            text += [rng.choice(lower) for _ in range(rng.randrange(1, 3))]
            for _ in range(rng.randrange(1, 4)):
                text += [ord(rng.choice(U16_OTHER)) for _ in range(rng.randrange(0, 2))]
                text += [ord(first), ord(rng.choice(_u16_tokens(first)))]
            text += [ord(rng.choice(U16_OTHER)) for _ in range(rng.randrange(0, 3))]
            nf = _u16_gid(first) + 65536 * rng.randrange(1, 256)
            yield case("16", "cand", in_font, text, nb="in", nf=nf)
            continue
        text = []
        for _ in range(rng.randrange(2, 6)):
            r = rng.random()
            if r < 0.3:
                text.append(rng.choice(lower))
            elif r < 0.7:
                f2 = rng.choice(U16_FIRSTS)
                text += [ord(f2), ord(rng.choice(_u16_tokens(f2)))]
            else:
                text.append(ord(rng.choice(U16_OTHER + "YOJQIHK")))
        if not any(cp in lower for cp in text):
            text.insert(rng.randrange(0, len(text) + 1), rng.choice(lower))
        if shape == "inrange":
            nf = rng.randrange(0, U16_NUM_GLYPHS)
            nb = "b:in-range-nf"
        elif shape == "noalias":
            if rng.random() < 0.5:
                nf = _u16_gid(
                    rng.choice(U16_OTHER + "YOJQIHK")
                ) + 65536 * rng.randrange(1, 256)
            else:
                nf = rng.randrange(U16_NUM_GLYPHS + 2, 32768)
            nb = "b:no-alias"
        else:
            nf = rng.choice((32, 33))
            if nf == 33:
                k = next(k for k, cp in enumerate(text) if cp in lower)
                text.insert(k + 1, ord("Y"))
            nb = "x:oor-covered"
        yield case("16", "cand", held, text, nb=nb, nf=nf)


# ---------------------------------------------------------------------------------------------------------------
# Unit 17: GPOS marks no longer attach to an earlier base when a ranged feature skips the nearest base.

U17_ABOVE = [0x0300, 0x0301, 0x0302, 0x0303, 0x0304, 0x0306, 0x0307, 0x0308]
U17_BELOW = [0x0323, 0x0324, 0x0325]
U17_LIGS = {
    0xFB00: ("ff", 2),
    0xFB01: ("fi", 2),
    0xFB02: ("fl", 2),
    0xFB03: ("ffi", 3),
    0xFB04: ("ffl", 3),
}


def _u17_fonts(out: Path) -> None:
    """Mark-to-base and mark-to-ligature attachment under `mark`, with anchors at the middle of each base and of
    each ligature component."""
    extra = [(f"lig_{name}", 400 * k, "base", cp) for cp, (name, k) in U17_LIGS.items()]
    extra += [(f"m{cp:04X}", 0, "above", cp) for cp in U17_ABOVE]
    extra += [(f"m{cp:04X}", 0, "below", cp) for cp in U17_BELOW]
    fb = _latin("u17", extra)
    widths = {c: 500 + 20 * i for i, c in enumerate(LETTERS)}
    ligs = [f"lig_{name}" for name, _ in U17_LIGS.values()]
    marks = [f"m{cp:04X}" for cp in U17_ABOVE + U17_BELOW]
    fea = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n"
    fea += _gdef(["space", *LETTERS], ligs, marks)
    fea += f"markClass [{' '.join(f'm{cp:04X}' for cp in U17_ABOVE)}] <anchor -150 760> @TOP;\n"
    fea += f"markClass [{' '.join(f'm{cp:04X}' for cp in U17_BELOW)}] <anchor -150 -100> @BOT;\n"
    fea += "lookup MB {\n"
    for c, w in widths.items():
        fea += f"  pos base {c} <anchor {w // 2} 700> mark @TOP <anchor {w // 2} 0> mark @BOT;\n"
    fea += "} MB;\nlookup ML {\n"
    for name, k in U17_LIGS.values():
        comps = " ligComponent ".join(
            f"<anchor {400 * j + 200} 700> mark @TOP <anchor {400 * j + 200} 0> mark @BOT"
            for j in range(k)
        )
        fea += f"  pos ligature lig_{name} {comps};\n"
    fea += "} ML;\nfeature mark { lookup MB; lookup ML; } mark;\n"
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(out / "u17.ttf"))


def gen_u17(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 17: a GPOS mark does not attach to an earlier base when a ranged feature request leaves out the nearest
    base.

    Text: tokens of a base (a letter, or a ligature code point U+FB00..U+FB04) and its marks; cluster levels 1
    and 2, where each mark keeps a cluster of its own, so a range can cover a base without its marks. The ranges
    switch `mark` off (`mark=0@start:end`). Inside: the range covers the nearest base Q of a mark (and maybe the
    bases between Q and an earlier base P) but neither the mark nor P. Neighbours: no range (`b:global`); a range
    over P only (`b:nearest-in-range`); a range over the mark (`b:mark-excluded`); a range over Q and every earlier
    base (`b:no-earlier-base`); a range over a mark between Q and the mark, which the lookup skips
    (`b:skipped-mark`).
    """
    path = synth / "u17.ttf"
    bases = [ord(c) for c in LETTERS] + list(U17_LIGS)

    def token(marks: int) -> list[int]:
        out = [rng.choice(bases)]
        if marks:
            out += [rng.choice(U17_BELOW)] if rng.random() < 0.3 else []
            out += [rng.choice(U17_ABOVE) for _ in range(marks)]
        return out

    for _ in range(n):
        shape = rng.choice(
            ("in",) * 5
            + ("global", "nearest", "markx", "noearlier", "skipped", "skipped")
        )
        text: list[int] = []
        for _ in range(rng.randrange(0, 3)):
            text += token(rng.choice((0, 0, 1)))
        p = len(text)
        # A base the range switches off carries no marks of its own (they would be inside cases).
        text += token(0 if shape == "nearest" else rng.choice((0, 0, 1)))
        middle = len(text)
        for _ in range(rng.choice((0, 0, 1, 2))):
            text += token(0)
        q = len(text)
        q_marks = 2 if shape == "skipped" else rng.choice((1, 1, 2))
        text += [rng.choice(bases)] + [rng.choice(U17_ABOVE) for _ in range(q_marks)]
        mark_end = len(text)
        for _ in range(rng.randrange(0, 3)):
            text += token(rng.choice((0, 1)))
        feat = {
            "in": f"mark=0@{rng.choice((middle, q))}:{q + 1}",
            "global": None,
            "nearest": f"mark=0@{p}:{p + 1}",
            "markx": f"mark=0@{rng.choice((q, q + 1))}:{mark_end}",
            "noearlier": f"mark=0@0:{q + 1}",
            "skipped": f"mark=0@{q + 1}:{q + 2}",
        }[shape]
        opts: dict[str, object] = {"cl": rng.choice((1, 2))}
        if feat:
            opts["feat"] = feat
        nb = {
            "in": "in",
            "global": "b:global",
            "nearest": "b:nearest-in-range",
            "markx": "b:mark-excluded",
            "noearlier": "b:no-earlier-base",
            "skipped": "b:skipped-mark",
        }[shape]
        yield case("17", "cand", path, text, nb=nb, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 18: fallback mark positioning uses the x offset of the base.

U18_MARKS = {
    0x0301: "above", 0x0308: "above", 0x0323: "below", 0x0331: "below", 0x0327: "attached-below",
    0x031B: "above-right", 0x0315: "above-right", 0x035D: "wide-above", 0x035C: "wide-below",
    0x0334: "overlay", 0x0345: "below",
}  # fmt: skip
U18_KERN = {("A", "V"): -80, ("T", "O"): -60, ("L", "Y"): -100, ("W", "A"): -40, ("V", "A"): -70,
            ("P", "A"): -50, ("F", "O"): 30, ("K", "O"): 24, ("R", "T"): -36}  # fmt: skip
U18_SECONDS = sorted({b for _, b in U18_KERN})


def _u18_fonts(out: Path) -> None:
    """The same letters and combining marks three times: with a `kern` table and no `GPOS` (fallback positioning
    of marks), with vertical metrics and no kerning (fallback positioning in vertical text), and with a `GPOS`
    that kerns and moves bases but has no `mark` feature (no fallback positioning)."""
    extra = [(f"m{cp:04X}", 0, shape, cp) for cp, shape in U18_MARKS.items()]
    marks = [f"m{cp:04X}" for cp in U18_MARKS]
    fb = _latin("u18-kern", extra)
    kern = newTable("kern")
    kern.version = 0
    sub = _k_e_r_n.KernTable_format_0()
    sub.version, sub.coverage, sub.format = 0, 1, 0
    sub.kernTable = dict(U18_KERN)
    kern.kernTables = [sub]
    fb.font["kern"] = kern
    fb.save(str(out / "u18-kern.ttf"))
    _latin("u18-vert", extra, vertical=True).save(str(out / "u18-vert.ttf"))
    fb = _latin("u18-gpos", extra)
    fea = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n"
    fea += _gdef(["space", *LETTERS], [], marks)
    fea += (
        "feature kern { "
        + " ".join(f"pos {a} {b} {v};" for (a, b), v in U18_KERN.items())
        + " } kern;\n"
    )
    fea += "feature kern { " + " ".join(
        f"pos {b} <{-25 - 5 * i} 0 0 0>;" for i, b in enumerate(U18_SECONDS)
    )
    fea += " } kern;\n"
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(out / "u18-gpos.ttf"))


def gen_u18(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 18: fallback mark positioning places marks relative to the base's x offset.

    Fallback positioning runs for fonts without `GPOS` (and without `kerx`). Inside: a mark on a base with a
    non-zero x offset, which comes from `kern` table kerning (the second glyph of a kerned pair gets half the
    kerning as its x offset) or, in vertical text, from the vertical origin. Neighbours: marks only on bases
    without an x offset in horizontal text (`b:no-x-offset`), and the same kerned text in the `GPOS` font, where
    no release positions marks by fallback (`b:gpos`). Vertical text with a `kern` table is left out (units 21 and
    22 change vertical kerning and tracking).
    """
    fonts = {k: synth / f"u18-{k}.ttf" for k in ("kern", "vert", "gpos")}
    marks = list(U18_MARKS)
    pairs = list(U18_KERN)
    plain = "BCDEGHIJMNQSUXZ"  # no pair starts or ends with these
    for _ in range(n):
        shape = rng.choice(
            ("in-kern",) * 3 + ("in-vert", "in-vert", "zero", "zero", "gpos", "gpos")
        )
        text: list[int] = []
        if shape in ("in-kern", "gpos"):
            # `kern` subtables run in visual order, so in right-to-left text a pair (a, b) kerns the logical
            # sequence b, a and gives b the offset. The marks go on the glyph that gets the offset.
            direction = rng.choice(("ltr", "ltr", "ltr", "rtl"))
            for _ in range(rng.randrange(0, 2)):
                text.append(ord(rng.choice(plain)))
            for _ in range(rng.randrange(1, 3)):
                a, b = rng.choice(pairs)
                kerned = [ord(b)] + [
                    rng.choice(marks) for _ in range(rng.choice((1, 1, 2)))
                ]
                if direction == "ltr":
                    text += (
                        [ord(a)]
                        + ([rng.choice(marks)] if rng.random() < 0.2 else [])
                        + kerned
                    )
                else:
                    text += kerned + [ord(a)]
                text.append(ord(rng.choice(plain)))
            opts = {"dir": direction}
            font, nb = (
                (fonts["kern"], "in")
                if shape == "in-kern"
                else (fonts["gpos"], "b:gpos")
            )
        elif shape == "in-vert":
            for _ in range(rng.randrange(1, 4)):
                text += [ord(rng.choice(LETTERS))] + [
                    rng.choice(marks) for _ in range(rng.choice((0, 1, 1, 2)))
                ]
            if not any(cp in U18_MARKS for cp in text):
                text.append(rng.choice(marks))
            opts = {"dir": rng.choice(("ttb", "ttb", "btt"))}
            font, nb = fonts["vert"], "in"
        else:
            # Marks only on bases that no pair touches; other letters around them may kern each other.
            for _ in range(rng.randrange(1, 3)):
                text += [ord(rng.choice(plain))] + [
                    rng.choice(marks) for _ in range(rng.choice((1, 2)))
                ]
                a, b = rng.choice(pairs)
                text += [ord(a), ord(b)] if rng.random() < 0.5 else []
            opts = {"dir": rng.choice(("ltr", "ltr", "rtl"))}
            font, nb = fonts["kern"], "b:no-x-offset"
        yield case("18", "cand", font, text, nb=nb, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 27: unsafe-to-break flags with cross-stream kerning from `kern` or `kerx`.

U27_PAIRS = {("A", "V"): 120, ("T", "O"): -80, ("L", "Y"): 150, ("W", "A"): 60, ("V", "A"): -50,
             ("P", "O"): 90, ("K", "Y"): -30}  # fmt: skip
CROSS_STREAM = 0x40000000


def _u27_fonts(out: Path) -> None:
    """Cross-stream pair kerning in a Microsoft `kern` table (coverage: horizontal and cross-stream), an Apple
    `kern` table (coverage 0x40) and a `kerx` table (format 0), and in-stream copies of the Microsoft and `kerx`
    tables. No value is the cross-stream reset value -0x8000."""
    for name, apple, cross in (
        ("u27-kern-ms", False, True),
        ("u27-kern-apple", True, True),
        ("u27-kern-ms-in", False, False),
    ):
        fb = _latin(name)
        kern = newTable("kern")
        kern.version = 1.0 if apple else 0
        sub = _k_e_r_n.KernTable_format_0(apple=apple)
        sub.version, sub.format = 0, 0
        sub.coverage = (0x40 if cross else 0) if apple else (0x05 if cross else 0x01)
        sub.tupleIndex = 0 if apple else None
        sub.kernTable = dict(U27_PAIRS)
        kern.kernTables = [sub]
        fb.font["kern"] = kern
        fb.save(str(out / f"{name}.ttf"))
    for name, cross in (("u27-kerx", True), ("u27-kerx-in", False)):
        fb = _latin(name)
        order = fb.font.getGlyphOrder()
        pairs = {(order.index(a), order.index(b)): v for (a, b), v in U27_PAIRS.items()}
        add_raw_table(fb, "kerx", kerx_format0(pairs, CROSS_STREAM if cross else 0))
        fb.save(str(out / f"{name}.ttf"))


def _u27_opens_with_pair(text: list[int], direction: str) -> bool:
    """True when the first two glyphs in visual order are a kerned pair (the tables kern in visual order)."""
    vis = text if direction == "ltr" else text[::-1]
    return (chr(vis[0]), chr(vis[1])) in U27_PAIRS


def gen_u27(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 27: in text with cross-stream kerning from `kern` or `kerx`, every break from the first kerned pair on
    is unsafe.

    Glyph flags printed (`gf=1`), every cluster level, no buffer flags. A cross-stream offset carries over to every
    glyph after the kerned one in visual order (each glyph is attached to the one before it), so breaking anywhere
    from the first kerned pair on changes the glyphs after the break. Inside: a cross-stream font and text that
    opens, in visual order, with a kerned pair and has a glyph after it. Left out (`x:before-pair`): text with
    glyphs before the first kerned pair. 15.2.0 flags the whole text, so it also flags the breaks between those
    glyphs, which the kerning moves nothing across; the note does not say that. Neighbours: the same kinds of text
    in the in-stream fonts (`b:in-stream`), and text in the cross-stream fonts that has the pairs' glyphs but no
    adjacent pair, so no cross-stream offset is applied (`b:no-pair`).
    """
    cross = [synth / f"{s}.ttf" for s in ("u27-kern-ms", "u27-kern-apple", "u27-kerx")]
    plain = [synth / f"{s}.ttf" for s in ("u27-kern-ms-in", "u27-kerx-in")]
    pairs = list(U27_PAIRS)
    filler = "BCDEFGHIJMNQRSUXZ"  # in no pair
    for _ in range(n):
        shape = rng.choice(("in",) * 4 + ("plain", "plain", "nopair", "nopair"))
        direction = rng.choice(("ltr", "ltr", "ltr", "rtl"))
        if shape == "nopair":
            a, b = rng.choice(pairs)
            text = (
                [ord(a)]
                + [ord(rng.choice(filler)) for _ in range(rng.randrange(1, 3))]
                + [ord(b)]
            )
            for _ in range(rng.randrange(0, 3)):
                text.insert(rng.randrange(0, len(text) + 1), ord(rng.choice(filler)))
            font, nb = rng.choice(cross), "b:no-pair"
        else:
            # The tables kern in visual order: in right-to-left text the pair (a, b) is the logical sequence b, a.
            text = [ord(rng.choice(filler)) for _ in range(rng.randrange(0, 3))]
            for _ in range(rng.randrange(1, 3)):
                a, b = rng.choice(pairs)
                text += [ord(a), ord(b)] if direction == "ltr" else [ord(b), ord(a)]
                text += [ord(rng.choice(filler)) for _ in range(rng.randrange(0, 2))]
            if len(text) < 4:
                text.append(ord(rng.choice(filler)))
            font, nb = (
                (rng.choice(cross), "in")
                if shape == "in"
                else (rng.choice(plain), "b:in-stream")
            )
            if nb == "in" and not _u27_opens_with_pair(text, direction):
                nb = "x:before-pair"
        opts = {"gf": 1, "cl": rng.choice((0, 1, 2, 3)), "dir": direction}
        yield case("27", "cand", font, text, nb=nb, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 29: an archaic trailing jamo after a Hangul syllable is unsafe to break at the character levels.

U29_L, U29_V = list(range(0x1100, 0x1113)), list(range(0x1161, 0x1176))
U29_MODERN_T = list(range(0x11A8, 0x11C3))
U29_ARCHAIC_T = [*range(0x11C3, 0x1200), *range(0xD7CB, 0xD7FC)]
# The syllables the font has: LV for these leading and vowel indices, and LVT for these trailing indices.
U29_LI, U29_VI, U29_TI = (
    (0, 2, 3, 5, 6, 9, 11, 12, 14, 18),
    (0, 1, 4, 5, 8, 12, 13, 17, 18, 20),
    (1, 4, 8, 16, 19, 21),
)


def _u29_lv(li: int, vi: int) -> int:
    return 0xAC00 + (li * 21 + vi) * 28


def _u29_fonts(out: Path) -> None:
    """Hangul syllables and conjoining jamo (modern and archaic), with no layout tables: only the Hangul shaper
    sets glyph flags. (Noto Sans KR's own contextual jamo lookups flag the trailing jamo in every release.)"""
    glyphs = [(".notdef", 500, "base"), ("space", 250, "empty")]
    cmap = {0x20: "space"}
    cps = [_u29_lv(li, vi) + t for li in U29_LI for vi in U29_VI for t in (0, *U29_TI)]
    for cp in cps + U29_L:
        glyphs.append((f"u{cp:04X}", 920, "base"))
        cmap[cp] = f"u{cp:04X}"
    for cp in U29_V + U29_MODERN_T + U29_ARCHAIC_T:
        glyphs.append((f"u{cp:04X}", 0, "above"))
        cmap[cp] = f"u{cp:04X}"
    _builder("u29-hangul", glyphs, cmap).save(str(out / "u29-hangul.ttf"))


def gen_u29(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 29: an archaic trailing jamo after an LV syllable gets the unsafe-to-break flag at the character levels.

    The Hangul shaper decomposes an LV syllable followed by a trailing jamo that does not combine with it (an
    archaic one) into its jamo plus the trailing one. Glyph flags printed, no buffer flags, our font without
    layout tables. Inside: LV + archaic T at cluster levels 1 and 2. Neighbours: the same text at levels 0 and 3,
    where the three jamo form one cluster (`b:grapheme-level`); LV + a modern trailing jamo, which composes or is
    flagged by its own rule (`b:modern-trailing`); a decomposed L, V and archaic T, flagged in every release
    (`b:jamo-sequence`); LVT + archaic T, which is not decomposed and stays unflagged (`b:after-lvt`: the note names
    a syllable "that has no final consonant", so this is the boundary a port that flags every archaic T after any
    Hangul syllable crosses). Tone marks and dotted circles are left out (units 5 and 6); so are Thai and Lao,
    whose SARA AM decomposition 15.2.0 flags the same way although the note speaks of Hangul only.
    """
    path = synth / "u29-hangul.ttf"

    def lv() -> int:
        return _u29_lv(rng.choice(U29_LI), rng.choice(U29_VI))

    def filler() -> list[int]:
        return [rng.choice((lv(), lv() + rng.choice(U29_TI), 0x20))]

    for _ in range(n):
        shape = rng.choice(
            ("in",) * 4 + ("grapheme", "grapheme", "modern", "lvt", "jamo")
        )
        if shape == "jamo":
            core = [rng.choice(U29_L), rng.choice(U29_V), rng.choice(U29_ARCHAIC_T)]
        elif shape == "lvt":
            core = [lv() + rng.choice(U29_TI), rng.choice(U29_ARCHAIC_T)]
        elif shape == "modern":
            core = [lv(), rng.choice(U29_MODERN_T)]
        else:
            core = [lv(), rng.choice(U29_ARCHAIC_T)]
        text = [cp for _ in range(rng.randrange(0, 3)) for cp in filler()]
        text += core + [cp for _ in range(rng.randrange(0, 3)) for cp in filler()]
        level = rng.choice((0, 3)) if shape == "grapheme" else rng.choice((1, 2))
        nb = {"in": "in", "grapheme": "b:grapheme-level", "modern": "b:modern-trailing",
              "lvt": "b:after-lvt", "jamo": "b:jamo-sequence"}[shape]  # fmt: skip
        yield case("29", "cand", path, text, nb=nb, cl=level, gf=1)


# ---------------------------------------------------------------------------------------------------------------
# Unit 31: `gvar` intermediate tuples. Glyph advances come from `gvar` phantom-point deltas (no `HVAR`).

# Glyph roles: tuples as (start, peak, end, advance delta) in tuple order; None start/end is a peak-only tuple.
U31_ROLES = {
    "A": [(None, 0.5, None, 120)], "B": [(None, 0.5, None, 90)], "C": [(None, 0.5, None, 150)],
    "D": [(0.25, 0.5, 1.0, 200)], "E": [(0.25, 0.5, 1.0, 140)], "F": [(0.0, 0.5, 1.0, 180)],
    "G": [(None, 0.5, None, 60), (0.25, 0.5, 1.0, 160)], "H": [(None, 0.5, None, 40), (0.0, 0.5, 1.0, 220)],
    "I": [(0.25, 0.5, 1.0, 160), (None, 0.5, None, 60)],
    "J": [(None, -0.5, None, 110)], "K": [(None, -0.5, None, 70)],
    "L": [(-1.0, -0.5, -0.25, 190)], "M": [(-1.0, -0.5, 0.0, 130)],
    "N": [(None, -0.5, None, 50), (-1.0, -0.5, -0.25, 170)],
    "O": [(0.3, 0.6, 1.0, 210)], "P": [(-1.0, -0.7, -0.4, 230)],
    "Q": [(None, 1.0, None, 100)], "R": [(None, 1.0, None, 80)], "S": [(None, -1.0, None, 90)],
    "T": [(None, -1.0, None, 60)],
}  # fmt: skip
U31_PLAIN_POS, U31_INTERM_POS, U31_BOTH_POS = "ABC", "DEF", "GH"
U31_PLAIN_NEG, U31_INTERM_NEG, U31_BOTH_NEG = "JK", "LM", "N"
U31_EMBEDDED, U31_NOINT, U31_STATIC = "OP", "QRST", "UVWXYZ"


def _variable_latin(family: str, roles: dict[str, list[tuple]]) -> FontBuilder:
    """A-Z with a `wght` axis 100..900 (default 400); each listed glyph's advance moves by its tuples' deltas."""
    fb = _latin(family)
    fb.setupFvar(
        [("wght", 100, 400, 900, "Weight")],
        [{"location": {"wght": 400}, "stylename": "Regular"}],
    )
    variations = {}
    for letter, tuples in roles.items():
        var = []
        for start, peak, end, delta in tuples:
            region = (
                (min(0.0, peak), peak, max(0.0, peak))
                if start is None
                else (start, peak, end)
            )
            coords = [(0, 0)] * 4 + [(0, 0), (delta, 0), (0, 0), (0, 0)]
            var.append(TupleVariation({"wght": region}, coords))
        variations[letter] = var
    fb.setupGvar(variations)
    return fb


def _u31_fonts(out: Path) -> None:
    """Peaks +0.5 and -0.5 are shared tuples (several glyphs use them); intermediate tuples use them too, after a
    peak-only tuple with the same peak in the same glyph (G, H, N), in other glyphs (D, E, F, L, M) or before one
    (I). O and P have intermediate tuples with peaks no other tuple uses (embedded)."""
    _variable_latin("u31-gvar", U31_ROLES).save(str(out / "u31-gvar.ttf"))


def gen_u31(rng: random.Random, noto, synth: Path, n: int) -> Iterator[dict]:
    """Unit 31: `gvar` intermediate tuples no longer take a scalar cached for their shared peak.

    15.0.0 cached the scalar of a peak-only tuple under its shared peak and gave that cached 0 to a later
    intermediate tuple with the same peak, even where the intermediate region is non-zero. Advances come from
    `gvar` (no `HVAR`), so the driver's advances show it. Inside: a location beyond the peak inside the
    intermediate region (wght 700-850 for +0.5, 130-220 for -0.5), and text where a peak-only tuple with the
    shared peak is evaluated before an intermediate one (in one glyph, or an earlier glyph). Neighbours: locations
    between the default and the peak, at the peak and at the default (`b:inside-peak`); intermediate glyphs before
    every peak-only one (`b:intermediate-first`); intermediate tuples with embedded peaks (`b:embedded`); fonts'
    glyphs without intermediate tuples (`b:no-intermediate`).
    """
    path = synth / "u31-gvar.ttf"
    pos_out, neg_out = (700, 750, 800, 850), (130, 175, 220)
    pos_in, neg_in = (450, 500, 550, 600, 650, 400), (250, 300, 350, 400)
    static = U31_STATIC

    def pick(s: str, k: int) -> list[int]:
        return [ord(rng.choice(s)) for _ in range(k)]

    for _ in range(n):
        side = rng.choice(("pos", "pos", "neg"))
        plain, interm, both = (
            (U31_PLAIN_POS, U31_INTERM_POS, U31_BOTH_POS)
            if side == "pos"
            else (U31_PLAIN_NEG, U31_INTERM_NEG, U31_BOTH_NEG)
        )
        out_w, in_w = (pos_out, pos_in) if side == "pos" else (neg_out, neg_in)
        shape = rng.choice(("in",) * 4 + ("peak", "first", "embedded", "noint"))
        text = pick(static, rng.randrange(0, 2))
        if shape in ("in", "peak"):
            if rng.random() < 0.5:
                text += pick(both, 1)
            else:
                text += (
                    pick(plain, 1)
                    + pick(static, rng.randrange(0, 2))
                    + pick(interm, rng.randrange(1, 3))
                )
            wght = rng.choice(out_w) if shape == "in" else rng.choice(in_w)
        elif shape == "first":
            text += (
                pick(interm, rng.randrange(1, 3))
                + pick(static, rng.randrange(0, 2))
                + pick(plain, 1)
            )
            wght = rng.choice(out_w)
        elif shape == "embedded":
            text += pick(plain, 1) + pick(U31_EMBEDDED, rng.randrange(1, 3))
            wght = rng.choice(out_w)
        else:
            text += pick(plain + U31_NOINT, rng.randrange(1, 4))
            wght = rng.choice(out_w + in_w)
        text += pick(static, rng.randrange(0, 2))
        nb = {"in": "in", "peak": "b:inside-peak", "first": "b:intermediate-first",
              "embedded": "b:embedded", "noint": "b:no-intermediate"}[shape]  # fmt: skip
        yield case("31", "cand", path, text, nb=nb, var=f"wght={wght}")


# ---------------------------------------------------------------------------------------------------------------


def build_fonts(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _u12_fonts(out)
    _u13_fonts(out)
    _u16_fonts(out)
    _u17_fonts(out)
    _u18_fonts(out)
    _u27_fonts(out)
    _u29_fonts(out)
    _u31_fonts(out)


UNITS = {
    "12": gen_u12,
    "13": gen_u13,
    "14": gen_u14,
    "15": gen_u15,
    "16": gen_u16,
    "17": gen_u17,
    "18": gen_u18,
    "27": gen_u27,
    "29": gen_u29,
    "31": gen_u31,
}

PER_UNIT = {
    "12": 1200,
    "13": 1500,
    "16": 900,
    "17": 900,
    "18": 900,
    "27": 900,
    "29": 900,
    "31": 900,
}

W_TARGETS = {
    "12": ["b:not-per-syllable"],
    "13": [],  # W13 moved b:exclusion, now x:exclusion
    "14": ["b:global-first"],
    "15": ["b:supported-base"],
    "16": [],  # W16 moved b:oor-covered, now x:oor-covered
    "17": ["b:skipped-mark"],
    "18": ["b:gpos"],
    "27": ["b:no-pair"],
    "29": ["b:grapheme-level"],
    "31": [],
}
