"""Family F1 (script shapers): candidate generators and the synthetic fonts they shape with.

New generators: units 3 (USE word ends for positional forms), 6 (inserted dotted circles keep their advance without
`GDEF`), 8 (Hebrew presentation forms with `mark` only under `DFLT`), 9 (Arabic `stch` tiles on short words and exact
fits), 10a (Arabic fallback ligatures with a missing component), 10b (Arabic fallback: marks without a legacy encoding
in legacy fonts), 11 (Arabic Windows-1256 fallback) and 34 (Indic shaping of the Unicode 18 Devanagari and Bengali
additions). Labelled replacements of the spike generators: units 2 (no space as the base of a dependent vowel), 4 (one
Coeng Ro, first or second coeng only) and 7 (vowel constraints across default ignorables).

Every candidate carries `nb`: `in` inside the unit's stated condition, or `b:<boundary>` for a neighbour one stated
condition away. Inputs that 15.2.0 changes although the note does not say so are not generated (see each generator).

Runs inside the pipeline image only (fontTools, the downloaded fonts). Development tooling, never shipped.
"""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Iterator
from pathlib import Path

from casekit import CGJ, DOTTED, NBSP, SHY, WJ, ZWJ, ZWNJ, Font, case
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

UPEM = 1000


def _hex(cps: list[int]) -> str:
    return ",".join(f"{cp:X}" for cp in cps)


def _gc(cp: int) -> str:
    try:
        return unicodedata.category(chr(cp))
    except ValueError:
        return "Cn"


# ---------------------------------------------------------------------------------------------------------------
# Font building
# ---------------------------------------------------------------------------------------------------------------


def _outline(adv: int):
    """A box for a spacing glyph; a small box left of the origin for a zero-advance mark."""
    pen = TTGlyphPen(None)
    if adv > 60:
        x0, x1 = 20, adv - 20
        y0, y1 = 0, 600
    elif adv > 0:
        x0, x1, y0, y1 = 0, adv, 0, 600
    else:
        x0, x1, y0, y1 = -220, -60, 650, 760
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()
    return pen.glyph(), x0


def _font(
    family: str,
    glyphs: list[tuple[str, int]],
    cmap: dict[int, str],
    os2: dict | None = None,
    symbol: bool = False,
) -> FontBuilder:
    """A TrueType font with box outlines; `glyphs` lists (name, advance) in glyph order, `.notdef` first. With
    `symbol`, the `cmap` is a single Microsoft symbol (3,0) subtable, as legacy fonts have."""
    names = [g for g, _ in glyphs]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(names)
    if symbol:
        _symbol_cmap(fb, cmap)
    else:
        fb.setupCharacterMap(cmap)
    outlines, metrics = {}, {}
    for name, adv in glyphs:
        glyph, lsb = _outline(adv)
        outlines[name] = glyph
        metrics[name] = (adv, lsb)
    fb.setupGlyf(outlines)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
        **(os2 or {}),
    )
    fb.setupPost()
    return fb


def _gdef(fb: FontBuilder, classes: dict[str, int]) -> None:
    """A `GDEF` table holding only glyph classes (1 base, 2 ligature, 3 mark)."""
    table = newTable("GDEF")
    table.table = ot.GDEF()
    table.table.Version = 0x00010000
    cd = ot.GlyphClassDef()
    cd.classDefs = dict(classes)
    table.table.GlyphClassDef = cd
    table.table.AttachList = None
    table.table.LigCaretList = None
    table.table.MarkAttachClassDef = None
    fb.font["GDEF"] = table


def _no_gdef(fb: FontBuilder) -> None:
    if "GDEF" in fb.font:
        del fb.font["GDEF"]


def _symbol_cmap(fb: FontBuilder, mapping: dict[int, str]) -> None:
    """A `cmap` with a single Microsoft symbol (3,0) format 4 subtable."""
    table = newTable("cmap")
    table.tableVersion = 0
    sub = CmapSubtable.newSubtable(4)
    sub.platformID, sub.platEncID, sub.language = 3, 0, 0
    sub.cmap = dict(mapping)
    table.tables = [sub]
    fb.font["cmap"] = table


FIXED_TIME = 0xE6D4_8000  # seconds since 1904, a fixed date, so that every build writes the same bytes


def _save(fb: FontBuilder, path: Path) -> None:
    head = fb.font["head"]
    head.created = head.modified = FIXED_TIME
    fb.font.recalcTimestamp = False
    fb.save(str(path))


def _name(cp: int) -> str:
    return f"u{cp:04X}"


# ---------------------------------------------------------------------------------------------------------------
# Unit 3: the USE shaper ends a word at spaces and symbols when it selects isol, init, medi and fina forms
# ---------------------------------------------------------------------------------------------------------------

BALI_CONS = list(range(0x1B13, 0x1B34))
BALI_VOWELS = (
    0x1B35,
    0x1B36,
    0x1B38,
    0x1B3E,
)  # TEDUNG (post), ULU (above), SUKU (below), TALING (pre)
BALI_ADEG = 0x1B44
BALI_DIGITS = list(range(0x1B50, 0x1B5A))
BALI_MUSIC = list(range(0x1B61, 0x1B6B)) + list(
    range(0x1B74, 0x1B7D)
)  # So, symbol bases
BALI_MUSIC_MARKS = list(range(0x1B6B, 0x1B74))  # symbol modifiers
# Symbols (Unicode Sm, Sc, Sk, So) that USE classes OTHER: each is a symbol cluster of its own.
U3_SYMBOLS = (
    0x2B, 0x3C, 0x3D, 0x3E, 0x7C, 0x7E, 0x24, 0x5E, 0x60,
    0xA2, 0xA3, 0xA5, 0xA9, 0xAC, 0xAE, 0xB0, 0xB1, 0xF7, 0x20AC,
)  # fmt: skip
# Symbols that USE classes as generic bases (BASE_OTHER).
U3_GB_SYMBOLS = (0xD7, 0x25FB, 0x25FC, 0x25FD, 0x25FE)
U3_FORMS = ("isol", "init", "medi", "fina")


def _u3_font(out: Path) -> None:
    """A Balinese font whose `GSUB` has `isol`, `init`, `medi` and `fina` forms of every consonant and digit.

    No downloaded USE font has positional forms. The symbols, spaces and generic bases have no forms, so only the
    letters on either side of a boundary show which form the shaper selected.
    """
    glyphs = [(".notdef", 500), ("space", 260), ("nbsp", 260), ("dottedcircle", 520)]
    cmap = {0x20: "space", NBSP: "nbsp", DOTTED: "dottedcircle"}
    lines = []
    for group, base in (("cons", BALI_CONS), ("dig", BALI_DIGITS)):
        for i, cp in enumerate(base):
            name = _name(cp)
            width = (560 if group == "cons" else 440) + 8 * i
            glyphs.append((name, width))
            cmap[cp] = name
            for k, form in enumerate(U3_FORMS):
                glyphs.append((f"{name}.{form}", width + 2 + k))
        lines.append((group, [_name(cp) for cp in base]))
    for cp in BALI_VOWELS:
        glyphs.append((_name(cp), 0 if _gc(cp) == "Mn" else 210))
        cmap[cp] = _name(cp)
    glyphs.append((_name(BALI_ADEG), 190))
    cmap[BALI_ADEG] = _name(BALI_ADEG)
    for i, cp in enumerate(BALI_MUSIC):
        glyphs.append((_name(cp), 480 + 4 * i))
        cmap[cp] = _name(cp)
    for cp in BALI_MUSIC_MARKS:
        glyphs.append((_name(cp), 0))
        cmap[cp] = _name(cp)
    for i, cp in enumerate(U3_SYMBOLS + U3_GB_SYMBOLS):
        glyphs.append((_name(cp), 380 + 6 * i))
        cmap[cp] = _name(cp)
    fb = _font("u3-bali-topo", glyphs, cmap)
    fea = ["languagesystem DFLT dflt;", "languagesystem bali dflt;"]
    for group, names in lines:
        fea.append(f"@{group} = [{' '.join(names)}];")
        for form in U3_FORMS:
            fea.append(f"@{group}_{form} = [{' '.join(f'{n}.{form}' for n in names)}];")
    for form in U3_FORMS:
        fea.append(
            f"feature {form} {{ sub @cons by @cons_{form}; sub @dig by @dig_{form}; }} {form};"
        )
    addOpenTypeFeaturesFromString(fb.font, "\n".join(fea))
    _no_gdef(fb)
    _save(fb, out / "u3-bali-topo.ttf")


def _u3_syllable(rng: random.Random) -> list[int]:
    syl = [rng.choice(BALI_CONS)]
    if rng.random() < 0.15:
        syl += [BALI_ADEG, rng.choice(BALI_CONS)]
    if rng.random() < 0.45:
        syl.append(rng.choice(BALI_VOWELS))
    return syl


def _u3_word(rng: random.Random, lo: int = 1, hi: int = 4) -> list[int]:
    return [cp for _ in range(rng.randint(lo, hi)) for cp in _u3_syllable(rng)]


def _u3_boundary(rng: random.Random) -> list[int]:
    kind = rng.choice(("sym", "sym", "sym", "gb", "nbsp", "music", "music-mod", "two"))
    if kind == "sym":
        return [rng.choice(U3_SYMBOLS)]
    if kind == "gb":
        return [rng.choice(U3_GB_SYMBOLS)]
    if kind == "nbsp":
        return [NBSP]
    if kind == "music":
        return [rng.choice(BALI_MUSIC)]
    if kind == "music-mod":
        return [rng.choice(BALI_MUSIC[:10]), rng.choice(BALI_MUSIC_MARKS)]
    return [rng.choice(U3_SYMBOLS), rng.choice(U3_SYMBOLS + (NBSP,))]


def gen_u3(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 3: the USE shaper ends a word at spaces and symbols when it selects positional forms.

    Inside: Balinese words in our font with positional forms, separated by (or starting or ending with) a symbol
    (Unicode Sm, Sc, Sk, So; OTHER or generic-base symbols, Balinese musical symbols with or without their combining
    marks) or NO-BREAK SPACE. Neighbours: the same words with nothing between them (`b:adjacent`), with Balinese
    digits between them (`b:digit`; digits are bases and keep joining), the boundary only in the pre- or
    post-context (`b:context`), and the inside texts in Noto Sans Balinese, which has no positional forms
    (`b:no-forms`).

    Left out as unstated: ordinary spaces (U+0020 and the other spaces that 15.2.0 classes SPACE; unit 2's space
    class also stops their joining, so they are no evidence for this note on its own), punctuation, ASCII digits and
    letters of other scripts (15.2.0 ends words at them too; the note names only spaces and symbols), DOTTED CIRCLE
    (a symbol that still joins), ZWNJ (15.2.0 also ends a word after a syllable holding ZWNJ), a dependent vowel
    after NO-BREAK SPACE or a symbol (unit 2's territory), and glyph flags (15.2.0 adds unsafe-to-break and
    unsafe-to-concat flags that the note does not mention; flags are not printed).
    """
    topo = synth / "u3-bali-topo.ttf"
    plain = noto.get("NotoSansBalinese-Regular")
    for i in range(n):
        kind = rng.choice(
            ("in",) * 9
            + (
                "b:adjacent",
                "b:adjacent",
                "b:digit",
                "b:digit",
                "b:context",
                "b:no-forms",
            )
        )
        cl = rng.choice((0, 1, 2))
        if kind in ("in", "b:no-forms"):
            shape = rng.choice(
                ("between", "between", "between", "lead", "trail", "many")
            )
            if shape == "between":
                text = _u3_word(rng) + _u3_boundary(rng) + _u3_word(rng)
            elif shape == "lead":
                text = _u3_boundary(rng) + _u3_word(rng, 2, 4)
            elif shape == "trail":
                text = _u3_word(rng, 2, 4) + _u3_boundary(rng)
            else:
                text = _u3_word(rng, 1, 3)
                for _ in range(rng.randint(2, 3)):
                    text += _u3_boundary(rng) + _u3_word(rng, 1, 3)
            if kind == "b:no-forms" and plain is None:
                continue
            font = plain if kind == "b:no-forms" else topo
            yield case("3", "cand", font, text, nb=kind, cl=cl)
        elif kind == "b:adjacent":
            yield case("3", "cand", topo, _u3_word(rng, 2, 6), nb=kind, cl=cl)
        elif kind == "b:digit":
            digits = [rng.choice(BALI_DIGITS) for _ in range(rng.randint(1, 3))]
            shape = rng.choice(("between", "lead", "trail"))
            if shape == "between":
                text = _u3_word(rng) + digits + _u3_word(rng)
            elif shape == "lead":
                text = digits + _u3_word(rng, 1, 3)
            else:
                text = _u3_word(rng, 1, 3) + digits
            yield case("3", "cand", topo, text, nb=kind, cl=cl)
        else:
            opts: dict[str, object] = {"cl": cl}
            side = rng.choice(("pre", "post", "both"))
            if side in ("pre", "both"):
                opts["pre"] = _hex(_u3_word(rng, 1, 2) + _u3_boundary(rng))
            if side in ("post", "both"):
                opts["post"] = _hex(_u3_boundary(rng) + _u3_word(rng, 1, 2))
            yield case("3", "cand", topo, _u3_word(rng, 1, 4), nb=kind, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 6: dotted circles for Hangul tone marks and prohibited vowel sequences keep their advance without GDEF
# ---------------------------------------------------------------------------------------------------------------

HANGUL_TONES = (0x302E, 0x302F)
HANGUL_SYLS = list(range(0xAC00, 0xAC1C))
LATIN_BASES = [*range(0x41, 0x5B), *range(0x30, 0x3A)]
HANGUL_PUNCT = (0x2E, 0x2C, 0x28, 0x29, 0x21)

# Prohibited vowel sequences (Microsoft's IndicShapingInvalidCluster data) of USE-shaped scripts.
USE_VC_PAIRS = (
    (0x11005, 0x11038), (0x1100B, 0x1103E), (0x1100F, 0x11042),  # Brahmi
    (0x11680, 0x116AD), (0x11686, 0x116B2), (0x11680, 0x116B4), (0x11680, 0x116B5),  # Takri
    (0x11200, 0x1122C), (0x11240, 0x1122E), (0x11206, 0x1122C), (0x11200, 0x11231), (0x11200, 0x11233),  # Khojki
    (0x112B0, 0x112E0), (0x112B0, 0x112E5), (0x112B0, 0x112E6), (0x112B0, 0x112E7), (0x112B0, 0x112E8),  # Khudawadi
    (0x11481, 0x114B0), (0x114AA, 0x114B5), (0x114AA, 0x114B6), (0x1148B, 0x114BA), (0x1148D, 0x114BA),  # Tirhuta
    (0x11600, 0x11639), (0x11600, 0x1163A), (0x11601, 0x11639), (0x11601, 0x1163A),  # Modi
    (0x0D85, 0x0DCF), (0x0D85, 0x0DD0), (0x0D85, 0x0DD1), (0x0D8B, 0x0DDF), (0x0D8D, 0x0DD8),  # Sinhala
    (0x0D8F, 0x0DDF), (0x0D91, 0x0DCA), (0x0D91, 0x0DD9), (0x0D91, 0x0DDA), (0x0D94, 0x0DDF),
)  # fmt: skip
# A few consonants of each of those scripts, for syllables around the sequences.
USE_VC_CONS = {
    "brah": (0x11013, 0x11014, 0x11015, 0x1101A, 0x11022, 0x11027, 0x1102B, 0x1102E),
    "takr": (0x1168A, 0x1168B, 0x1168E, 0x11693, 0x11698, 0x1169D, 0x116A2),
    "khoj": (0x11208, 0x11209, 0x1120C, 0x11211, 0x11214, 0x1121A, 0x11222),
    "sind": (0x112BA, 0x112BB, 0x112BE, 0x112C3, 0x112C8, 0x112CD, 0x112D2),
    "tirh": (0x1148F, 0x11490, 0x11493, 0x11498, 0x1149D, 0x114A2, 0x114A7),
    "modi": (0x1160E, 0x1160F, 0x11612, 0x11617, 0x1161C, 0x11621, 0x11626),
    "sinh": (0x0D9A, 0x0D9B, 0x0D9C, 0x0DA0, 0x0DA7, 0x0DB4, 0x0DB8, 0x0DC3),
}


def _vc_script(cp: int) -> str:
    if 0x0D80 <= cp <= 0x0DFF:
        return "sinh"
    for tag, lo, hi in (
        ("brah", 0x11000, 0x1107F),
        ("khoj", 0x11200, 0x1124F),
        ("sind", 0x112B0, 0x112FF),
        ("tirh", 0x11480, 0x114DF),
        ("modi", 0x11600, 0x1165F),
        ("takr", 0x11680, 0x116CF),
    ):
        if lo <= cp <= hi:
            return tag
    raise ValueError(cp)


def _u6_hangul_fonts(out: Path) -> None:
    """Hangul fonts: tone marks with an advance, and with none, without `GDEF`; and a `GDEF` and `GPOS` control."""
    for name, tone_adv, tables in (
        ("u6-hangul-nogdef", 260, False),
        ("u6-hangul-zw-nogdef", 0, False),
        ("u6-hangul-gdef-gpos", 260, True),
    ):
        glyphs = [(".notdef", 500), ("space", 250), ("dottedcircle", 520)]
        cmap = {0x20: "space", DOTTED: "dottedcircle"}
        for cp in HANGUL_TONES:
            glyphs.append((_name(cp), tone_adv))
            cmap[cp] = _name(cp)
        for i, cp in enumerate(HANGUL_SYLS):
            glyphs.append((_name(cp), 900 + i))
            cmap[cp] = _name(cp)
        for i, cp in enumerate(LATIN_BASES + list(HANGUL_PUNCT)):
            glyphs.append((_name(cp), 420 + 7 * i))
            cmap[cp] = _name(cp)
        fb = _font(name, glyphs, cmap)
        if tables:
            fea = (
                "languagesystem DFLT dflt; languagesystem hang dflt;\n"
                "feature kern { pos u0041 u0056 -40; } kern;\n"
            )
            addOpenTypeFeaturesFromString(fb.font, fea)
            classes = {g: 1 for g, _ in glyphs if g != ".notdef"}
            for cp in HANGUL_TONES:
                classes[_name(cp)] = 3
            _gdef(fb, classes)
        else:
            _no_gdef(fb)
        _save(fb, out / f"{name}.ttf")


def _u6_use_fonts(out: Path) -> None:
    """Fonts for the prohibited vowel sequences of USE-shaped scripts: without `GDEF`, with one, and with one that
    classes the dotted circle as a mark. No `GSUB`, so the USE shaper takes these scripts."""
    cps = {DOTTED, 0x20, 0xA0}
    for a, b in USE_VC_PAIRS:
        cps |= {a, b}
    for cons in USE_VC_CONS.values():
        cps |= set(cons)
    ordered = sorted(cps)
    for name, gdef in (
        ("u6-use-nogdef", None),
        ("u6-use-gdef", "dc-base"),
        ("u6-use-gdef-dcmark", "dc-mark"),
    ):
        glyphs = [(".notdef", 500)]
        cmap = {}
        for i, cp in enumerate(ordered):
            gname = "dottedcircle" if cp == DOTTED else _name(cp)
            adv = 520 if cp == DOTTED else (0 if _gc(cp) == "Mn" else 300 + 5 * i)
            glyphs.append((gname, adv))
            cmap[cp] = gname
        fb = _font(name, glyphs, cmap)
        if gdef:
            classes = {}
            for cp in ordered:
                gname = "dottedcircle" if cp == DOTTED else _name(cp)
                classes[gname] = 3 if _gc(cp) == "Mn" else 1
            if gdef == "dc-mark":
                classes["dottedcircle"] = 3
            _gdef(fb, classes)
        else:
            _no_gdef(fb)
        _save(fb, out / f"{name}.ttf")


def gen_u6(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 6: dotted circles that the Hangul shaper inserts for a tone mark, and that the vowel constraints insert
    in a prohibited vowel sequence, keep their advance in fonts without `GDEF`.

    Inside: a tone mark after a base that is not a Hangul syllable (a Latin letter, digit, punctuation or space),
    shaped with the Hangul script, in our Hangul fonts without `GDEF` (spacing and zero-width tone marks); a
    prohibited vowel sequence of a USE-shaped script (Brahmi, Takri, Khojki, Khudawadi, Tirhuta, Modi, Sinhala)
    whose second vowel is non-spacing, in our font without `GDEF`. Neighbours: the same texts in fonts with
    `GDEF` (`b:gdef`; the Hangul one also has `GPOS`); fonts whose `GDEF` classes the dotted circle as a mark,
    where every release zeroes it (`b:gdef-dc-mark`); sequences whose second vowel is spacing (`b:mc-second`); a
    dotted circle typed in the text before a vowel sign (`b:typed-dc`); the do-not-insert-dotted-circle flag
    (`b:nodc-flag`); a tone mark after a Hangul syllable (`b:after-syllable`); a spacing tone mark opening the
    text or run (`b:text-start`).

    Left out as unstated: Hangul fonts with `GDEF` and without `GPOS` (15.2.0 keeps the circle's advance there
    too, through fallback mark positioning, which the note does not cover); a zero-width tone mark opening the
    text or run (15.2.0 then positions the tone mark on the inserted circle, whose advance does not change); the
    beginning-of-text flag and a typed dotted circle before a tone mark (unit 5).
    """
    hang = synth / "u6-hangul-nogdef.ttf"
    hang_zw = synth / "u6-hangul-zw-nogdef.ttf"
    hang_ctl = synth / "u6-hangul-gdef-gpos.ttf"
    use = synth / "u6-use-nogdef.ttf"
    use_gdef = synth / "u6-use-gdef.ttf"
    use_dcmark = synth / "u6-use-gdef-dcmark.ttf"
    mn_pairs = [p for p in USE_VC_PAIRS if _gc(p[1]) == "Mn"]
    mc_pairs = [p for p in USE_VC_PAIRS if _gc(p[1]) != "Mn"]

    def hangul_text() -> list[int]:
        base = rng.choice(LATIN_BASES + list(HANGUL_PUNCT) + [0x20])
        text = [base, rng.choice(HANGUL_TONES)]
        if rng.random() < 0.4:
            text = (
                rng.choice(
                    (
                        [rng.choice(HANGUL_SYLS)],
                        [rng.choice(LATIN_BASES)],
                        [rng.choice(HANGUL_SYLS), 0x20],
                    )
                )
                + text
            )
        if rng.random() < 0.4:
            text += rng.choice(
                (
                    [rng.choice(HANGUL_SYLS)],
                    [0x20, rng.choice(HANGUL_SYLS)],
                    [rng.choice(LATIN_BASES)],
                )
            )
        return text

    def vc_text(pair: tuple[int, int]) -> list[int]:
        cons = USE_VC_CONS[_vc_script(pair[0])]
        text = list(pair)
        if rng.random() < 0.4:
            text = [rng.choice(cons)] + text
        if rng.random() < 0.4:
            text += [rng.choice(cons)]
        return text

    def start_text() -> tuple[list[int], dict[str, object]]:
        """A tone mark opening the run: nothing before it, or its base in the pre-context."""
        text = [rng.choice(HANGUL_TONES)] + rng.choice(
            ([], [rng.choice(LATIN_BASES)], [rng.choice(HANGUL_SYLS)])
        )
        opts: dict[str, object] = {"script": "Hang"}
        if rng.random() < 0.5:
            opts["pre"] = _hex([rng.choice(LATIN_BASES + list(HANGUL_PUNCT))])
        return text, opts

    for i in range(n):
        kind = rng.choice(
            ("in-hangul",) * 4 + ("in-vc",) * 4
            + ("b:gdef", "b:gdef", "b:gdef-dc-mark", "b:gdef-dc-mark", "b:mc-second")
            + ("b:typed-dc", "b:nodc-flag", "b:after-syllable", "b:text-start")
        )  # fmt: skip
        cl = rng.choice((0, 1, 2))
        hangul = {"cl": cl, "script": "Hang"}
        if kind == "in-hangul":
            yield case(
                "6",
                "cand",
                rng.choice((hang, hang_zw)),
                hangul_text(),
                nb="in",
                **hangul,
            )
        elif kind == "in-vc":
            yield case("6", "cand", use, vc_text(rng.choice(mn_pairs)), nb="in", cl=cl)
        elif kind == "b:gdef":
            if rng.random() < 0.5:
                yield case("6", "cand", hang_ctl, hangul_text(), nb=kind, **hangul)
            else:
                yield case(
                    "6",
                    "cand",
                    use_gdef,
                    vc_text(rng.choice(USE_VC_PAIRS)),
                    nb=kind,
                    cl=cl,
                )
        elif kind == "b:gdef-dc-mark":
            if rng.random() < 0.75:
                text = vc_text(rng.choice(USE_VC_PAIRS))
            else:
                pair = rng.choice(mn_pairs)
                text = [DOTTED, pair[1]]
            yield case("6", "cand", use_dcmark, text, nb=kind, cl=cl)
        elif kind == "b:mc-second":
            yield case("6", "cand", use, vc_text(rng.choice(mc_pairs)), nb=kind, cl=cl)
        elif kind == "b:typed-dc":
            pair = rng.choice(mn_pairs)
            text = [DOTTED, pair[1]]
            if rng.random() < 0.5:
                text = [rng.choice(USE_VC_CONS[_vc_script(pair[0])])] + text
            yield case("6", "cand", use, text, nb=kind, cl=cl)
        elif kind == "b:nodc-flag":
            if rng.random() < 0.5:
                yield case(
                    "6",
                    "cand",
                    use,
                    vc_text(rng.choice(mn_pairs)),
                    nb=kind,
                    cl=cl,
                    flags="nodc",
                )
            else:
                font = rng.choice((hang, hang_zw))
                yield case(
                    "6", "cand", font, hangul_text(), nb=kind, flags="nodc", **hangul
                )
        elif kind == "b:after-syllable":
            text = [rng.choice(HANGUL_SYLS), rng.choice(HANGUL_TONES)]
            if rng.random() < 0.5:
                text = [rng.choice(LATIN_BASES)] + text
            yield case(
                "6", "cand", rng.choice((hang, hang_zw)), text, nb=kind, **hangul
            )
        else:
            text, opts = start_text()
            yield case("6", "cand", hang, text, nb=kind, cl=cl, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 8: the Hebrew shaper composes presentation forms in fonts that have mark only under DFLT
# ---------------------------------------------------------------------------------------------------------------

HEB_LETTERS = list(range(0x05D0, 0x05EB)) + [0x05F0, 0x05F1, 0x05F2]
HEB_POINTS = [*range(0x05B0, 0x05BE), 0x05BF, 0x05C1, 0x05C2, 0x05C4, 0x05C5, 0x05C7]
HEB_FORMS = [0xFB1D, 0xFB1F, *range(0xFB2A, 0xFB37), *range(0xFB38, 0xFB3D), 0xFB3E, 0xFB40, 0xFB41, 0xFB43,
             0xFB44, *range(0xFB46, 0xFB4F)]  # fmt: skip
# (letter, point) pairs the Hebrew shaper composes into a presentation form, and the form.
HEB_DAGESH = {
    0x05D0: 0xFB30, 0x05D1: 0xFB31, 0x05D2: 0xFB32, 0x05D3: 0xFB33, 0x05D4: 0xFB34, 0x05D5: 0xFB35, 0x05D6: 0xFB36,
    0x05D8: 0xFB38, 0x05D9: 0xFB39, 0x05DA: 0xFB3A, 0x05DB: 0xFB3B, 0x05DC: 0xFB3C, 0x05DE: 0xFB3E, 0x05E0: 0xFB40,
    0x05E1: 0xFB41, 0x05E3: 0xFB43, 0x05E4: 0xFB44, 0x05E6: 0xFB46, 0x05E7: 0xFB47, 0x05E8: 0xFB48, 0x05E9: 0xFB49,
    0x05EA: 0xFB4A,
}  # fmt: skip
HEB_PAIRS = [
    (0x05D9, 0x05B4), (0x05F2, 0x05B7), (0x05D0, 0x05B7), (0x05D0, 0x05B8), (0x05D5, 0x05B9),
    (0x05D1, 0x05BF), (0x05DB, 0x05BF), (0x05E4, 0x05BF), (0x05E9, 0x05C1), (0x05E9, 0x05C2),
    *((letter, 0x05BC) for letter in HEB_DAGESH),
]  # fmt: skip
# Points that compose with nothing in these letters.
HEB_PLAIN_POINTS = (0x05B0, 0x05B1, 0x05B2, 0x05B3, 0x05B5, 0x05B6, 0x05BB)


def _u8_fonts(out: Path) -> None:
    """Hebrew fonts: `mark` only under `DFLT` (with and without a `hebr` `GSUB`, with and without presentation
    forms), `mark` under `hebr`, `DFLT` `mark` beside a `hebr` `GPOS` with `kern` only, and no `GPOS`."""
    letters = [_name(cp) for cp in HEB_LETTERS]
    points = [_name(cp) for cp in HEB_POINTS]
    variants = {
        # name: (presentation forms?, GPOS features, GSUB features)
        "u8-dflt-mark": (True, "dflt", None),
        "u8-dflt-mark-hebr-gsub": (True, "dflt", "hebr"),
        "u8-hebr-mark": (True, "hebr", None),
        "u8-hebr-kern": (True, "dflt+hebr-kern", None),
        "u8-nogpos": (True, None, None),
        "u8-dflt-mark-noforms": (False, "dflt", None),
    }
    for name, (forms, gpos, gsub) in variants.items():
        glyphs = [(".notdef", 500), ("space", 250)]
        cmap = {0x20: "space"}
        for i, cp in enumerate(HEB_LETTERS):
            glyphs.append((_name(cp), 520 + 6 * i))
            cmap[cp] = _name(cp)
        for cp in HEB_POINTS:
            glyphs.append((_name(cp), 0))
            cmap[cp] = _name(cp)
        if forms:
            for i, cp in enumerate(HEB_FORMS):
                glyphs.append((_name(cp), 700 + 3 * i))
                cmap[cp] = _name(cp)
        fb = _font(name, glyphs, cmap)
        mark_body = (
            f"markClass [{' '.join(points)}] <anchor 0 -120> @BELOW;\n"
            f"pos base [{' '.join(letters)}] <anchor 260 -120> mark @BELOW;\n"
        )
        fea = []
        if gpos == "dflt" and gsub is None:
            fea = ["languagesystem DFLT dflt;", f"feature mark {{ {mark_body} }} mark;"]
        elif gpos == "dflt" and gsub == "hebr":
            fea = [
                "languagesystem DFLT dflt;",
                "languagesystem hebr dflt;",
                f"feature mark {{ script DFLT; language dflt; {mark_body} }} mark;",
                "feature ccmp { script hebr; language dflt; sub u05F0 by u05F1; } ccmp;",
            ]
        elif gpos == "hebr":
            fea = [
                "languagesystem DFLT dflt;",
                "languagesystem hebr dflt;",
                f"feature mark {{ {mark_body} }} mark;",
            ]
        elif gpos == "dflt+hebr-kern":
            fea = [
                "languagesystem DFLT dflt;",
                "languagesystem hebr dflt;",
                f"feature mark {{ script DFLT; language dflt; {mark_body} }} mark;",
                "feature kern { script hebr; language dflt; pos u05D0 u05D1 -30; } kern;",
            ]
        if fea:
            addOpenTypeFeaturesFromString(fb.font, "\n".join(fea))
        _save(fb, out / f"{name}.ttf")


def gen_u8(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 8: the Hebrew shaper composes presentation forms in fonts that have `mark` only under `DFLT`.

    Inside: Hebrew letters with points that compose into a presentation form (YOD with HIRIQ, ALEF with PATAH,
    letters with DAGESH, SHIN with SHIN DOT and so on), in our fonts whose `GPOS` has `mark` only under `DFLT` and
    which have the presentation forms (one of them with a `hebr` `GSUB`). Neighbours: `mark` under `hebr`
    (`b:hebr-script`, never composed); a `hebr` `GPOS` with `kern` only beside the `DFLT` `mark` (`b:hebr-no-mark`,
    always composed); no `GPOS` (`b:no-gpos`, always composed); the `DFLT` font without presentation forms
    (`b:no-form-glyph`); points that compose with nothing (`b:no-composition`, in the inside fonts).

    Left out as unstated: fonts with `mark` under another script such as `latn`, and fonts where `kerx` turns
    `GPOS` off; 15.2.0 composes there too.
    """
    inside = [synth / "u8-dflt-mark.ttf", synth / "u8-dflt-mark-hebr-gsub.ttf"]
    fonts = {
        "b:hebr-script": synth / "u8-hebr-mark.ttf",
        "b:hebr-no-mark": synth / "u8-hebr-kern.ttf",
        "b:no-gpos": synth / "u8-nogpos.ttf",
        "b:no-form-glyph": synth / "u8-dflt-mark-noforms.ttf",
    }

    def syllable(composable: bool) -> list[int]:
        if composable:
            letter, point = rng.choice(HEB_PAIRS)
            syl = [letter, point]
            if point == 0x05BC and letter == 0x05E9 and rng.random() < 0.5:
                syl.append(rng.choice((0x05C1, 0x05C2)))
            elif rng.random() < 0.3:
                syl.insert(rng.randint(1, 2), rng.choice(HEB_PLAIN_POINTS))
            return syl
        syl = [rng.choice(HEB_LETTERS[:27])]
        if rng.random() < 0.7:
            syl.append(rng.choice(HEB_PLAIN_POINTS))
        return syl

    def word(composable: bool) -> list[int]:
        text = []
        k = rng.randint(1, 4)
        hit = rng.randrange(k)
        for j in range(k):
            text += syllable(composable and (j == hit or rng.random() < 0.3))
        return text

    for i in range(n):
        kind = rng.choice(("in",) * 6 + tuple(fonts) * 2 + ("b:no-composition",))
        text = word(kind != "b:no-composition")
        if rng.random() < 0.3:
            text += [0x20] + word(kind != "b:no-composition")
        cl = rng.choice((0, 1, 2))
        if kind == "in" or kind == "b:no-composition":
            font = rng.choice(inside)
        else:
            font = fonts[kind]
        yield case("8", "cand", font, text, nb=kind, cl=cl)


# ---------------------------------------------------------------------------------------------------------------
# Unit 9: the Arabic shaper centers stch tiles on short words and exact fits
# ---------------------------------------------------------------------------------------------------------------

# Syriac letters and advances (multiples of 20, so that scales of one half and two keep every sum exact).
SYRIAC_WIDTHS = {
    0x0710: 200, 0x0712: 240, 0x0713: 160, 0x0715: 180, 0x0717: 140, 0x0718: 120, 0x0719: 100, 0x071A: 260,
    0x071B: 220, 0x071D: 80, 0x071F: 200, 0x0720: 160, 0x0721: 240, 0x0722: 140, 0x0723: 280, 0x0725: 180,
    0x0726: 220, 0x0728: 260, 0x0729: 200, 0x072A: 180, 0x072B: 300, 0x072C: 220,
}  # fmt: skip
ARABIC_DIGIT_WIDTHS = {
    0x0660 + k: w
    for k, w in enumerate((100, 60, 120, 140, 100, 80, 120, 140, 160, 120))
}
# (pieces) per stch font: (advance, is the piece repeating)
U9_TILES = {
    "u9-syrc-stch3": ((100, False), (120, True), (80, False)),
    "u9-syrc-stch5": ((60, False), (100, True), (40, False), (80, True), (60, False)),
    "u9-arab-stch3": ((80, False), (140, True), (60, False)),
}
U9_STCH_CHAR = {
    "u9-syrc-stch3": 0x070F,
    "u9-syrc-stch5": 0x070F,
    "u9-arab-stch3": 0x0601,
}


def _u9_fonts(out: Path) -> None:
    """Fonts whose `stch` feature turns SYRIAC ABBREVIATION MARK (or ARABIC SIGN SANAH) into fixed and repeating
    tiles; letters (or Arabic-Indic digits) of known advances fill the stretch."""
    for name, tiles in U9_TILES.items():
        syriac = name.startswith("u9-syrc")
        widths = SYRIAC_WIDTHS if syriac else ARABIC_DIGIT_WIDTHS
        stch_cp = U9_STCH_CHAR[name]
        glyphs = [(".notdef", 500), ("space", 240), (_name(stch_cp), 300)]
        cmap = {0x20: "space", stch_cp: _name(stch_cp)}
        for cp, w in widths.items():
            glyphs.append((_name(cp), w))
            cmap[cp] = _name(cp)
        pieces = [f"stch.{k}" for k in range(len(tiles))]
        glyphs += [(p, w) for p, (w, _) in zip(pieces, tiles)]
        fb = _font(name, glyphs, cmap)
        script = "syrc" if syriac else "arab"
        fea = (
            f"languagesystem {script} dflt;\n"
            f"feature stch {{ sub {_name(stch_cp)} by {' '.join(pieces)}; }} stch;\n"
        )
        addOpenTypeFeaturesFromString(fb.font, fea)
        _no_gdef(fb)
        _save(fb, out / f"{name}.ttf")


def _u9_kind(total: int, tiles: tuple[tuple[int, bool], ...]) -> str:
    """`in` when the fixed tiles plus one repeat reach the stretch or the repeats fill it exactly, else long."""
    fixed = sum(w for w, rep in tiles if not rep)
    repeat = sum(w for w, rep in tiles if rep)
    rest = total - fixed
    if rest <= repeat or rest % repeat == 0:
        return "in"
    return "b:long-word"


def gen_u9(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 9: the Arabic shaper centers `stch` tiles on short words and exact fits.

    Inside: a stretching mark (SYRIAC ABBREVIATION MARK, or ARABIC SIGN SANAH before Arabic-Indic digits) whose
    stretch is at most as wide as the fixed tiles plus one repeat, or exactly as wide as the fixed tiles plus whole
    repeats, at scales one, two, one half and minus one. The stretch is the rest of the word after the mark;
    Syriac set left-to-right is shaped right-to-left with its graphemes reversed, so there the stretch is the part
    of the word before the mark, and a run of digits set left-to-right is shaped left-to-right. Neighbours: longer
    stretches that are no exact fit (`b:long-word`, the overlap path every release handles alike); `stch` turned
    off (`b:stch-off`); words without a stretching mark (`b:no-stch`).

    Left out: nothing; the other releases differ only through this change on these fonts.
    """
    letters = {
        name: list(SYRIAC_WIDTHS if name.startswith("u9-syrc") else ARABIC_DIGIT_WIDTHS)
        for name in U9_TILES
    }
    widths = {**SYRIAC_WIDTHS, **ARABIC_DIGIT_WIDTHS}

    def word_for(name: str, want: str) -> list[int]:
        tiles = U9_TILES[name]
        word: list[int] = []
        for _ in range(200):
            word = [
                rng.choice(letters[name])
                for _ in range(rng.randint(1, 8 if want == "b:long-word" else 6))
            ]
            if rng.random() < 0.1 and want == "in":
                word = []
            if _u9_kind(sum(widths[c] for c in word), tiles) == want:
                return word
        return word

    for i in range(n):
        name = rng.choice(tuple(U9_TILES))
        font = synth / f"{name}.ttf"
        tiles = U9_TILES[name]
        stch = U9_STCH_CHAR[name]
        kind = rng.choice(
            ("in",) * 6 + ("b:long-word",) * 3 + ("b:stch-off", "b:no-stch")
        )
        direction = rng.choice(("rtl", "rtl", "ltr"))
        before = name.startswith("u9-syrc") and direction == "ltr"
        wants = ["b:long-word" if kind == "b:long-word" else "in"]
        if rng.random() < 0.3:
            wants.append("b:long-word")
        words = []
        for want in wants:
            word = word_for(name, want)
            if _u9_kind(sum(widths[c] for c in word), tiles) != want:
                words = []
                break
            if kind == "b:no-stch":
                words.append(word or [rng.choice(letters[name])])
            else:
                words.append(word + [stch] if before else [stch] + word)
        if not words:
            continue
        rng.shuffle(words)
        text = words[0]
        for word in words[1:]:
            text = text + [0x20] + word
        opts: dict[str, object] = {"dir": direction}
        scale = rng.choice((0, 0, 2000, 500, -1000))
        if scale:
            opts["scale"] = scale
        if kind == "b:stch-off":
            opts["feat"] = "stch=0"
        opts["cl"] = rng.choice((0, 1))
        yield case("9", "cand", font, text, nb=kind, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Units 10a, 10b, 11: Arabic fallback shaping
# ---------------------------------------------------------------------------------------------------------------

# Arabic letters, their joining (D dual, R right) and presentation forms (isolated, final, initial, medial). ALEF
# MAKSURA joins on both sides but has no initial or medial presentation form.
ARABIC_LETTERS = {
    0x0627: ("R", 0xFE8D, 0xFE8E, 0, 0), 0x0622: ("R", 0xFE81, 0xFE82, 0, 0), 0x0623: ("R", 0xFE83, 0xFE84, 0, 0),
    0x0625: ("R", 0xFE87, 0xFE88, 0, 0), 0x0628: ("D", 0xFE8F, 0xFE90, 0xFE91, 0xFE92),
    0x062A: ("D", 0xFE95, 0xFE96, 0xFE97, 0xFE98), 0x062C: ("D", 0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0),
    0x062D: ("D", 0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4), 0x062E: ("D", 0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8),
    0x062F: ("R", 0xFEA9, 0xFEAA, 0, 0), 0x0631: ("R", 0xFEAD, 0xFEAE, 0, 0),
    0x0633: ("D", 0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4), 0x0644: ("D", 0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0),
    0x0645: ("D", 0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4), 0x0646: ("D", 0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8),
    0x0647: ("D", 0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC), 0x0648: ("R", 0xFEED, 0xFEEE, 0, 0),
    0x0649: ("D", 0xFEEF, 0xFEF0, 0, 0), 0x064A: ("D", 0xFEF1, 0xFEF2, 0xFEF3, 0xFEF4),
}  # fmt: skip
ARABIC_MARKS = (0x064B, 0x064C, 0x064D, 0x064E, 0x064F, 0x0650, 0x0651, 0x0652)
# Two-part fallback ligatures whose first glyph and component are forms of the letters above (HarfBuzz's
# ligature_table), three-part ones (ligature_3_table) and the shadda ligatures (ligature_mark_table).
LIG2 = (
    0xFC08, 0xFC9F, 0xFC9C, 0xFC9D, 0xFC9E, 0xFC6A, 0xFC6D, 0xFC6F, 0xFC0E, 0xFCA4, 0xFCA1, 0xFCA2, 0xFCA3, 0xFC70,
    0xFC73, 0xFC75, 0xFCA8, 0xFCAA, 0xFCAC, 0xFCB0, 0xFC3F, 0xFCC9, 0xFC40, 0xFCCA, 0xFC41, 0xFCCB, 0xFC42, 0xFCCC,
    0xFC43, 0xFC44, 0xFCCD, 0xFEF5, 0xFEF7, 0xFEF9, 0xFEFB, 0xFC86, 0xFEF6, 0xFEF8, 0xFEFA, 0xFEFC, 0xFCCE, 0xFCCF,
    0xFCD0, 0xFCD1, 0xFC4E, 0xFCD5, 0xFCD2, 0xFCD3, 0xFC8F, 0xFCDA, 0xFCDB, 0xFCDC, 0xFCDD, 0xFC91, 0xFC94,
)  # fmt: skip
LIG3 = (0xFD88, 0xF201, 0xF211)
LIGMARK = (0xFC5E, 0xFC60, 0xFC61, 0xFC62, 0xF2EE)

# Fonts of unit 10a and what each leaves out of its `cmap`.
U10A_FONTS = {
    "u10a-p2": {0xFEEA},  # HEH final: the second component of LAM LAM HEH (U+F201)
    "u10a-p2-sparse": {0xFEEA, 0xFCCC, 0xFEFB, 0xFEFC, 0xFC9F, 0xFCD1, 0xFC5E},
    "u10a-full": set(),
    "u10a-d2": {0xFEA2},  # HAH final: the component of a two-part ligature only
    "u10a-noligglyph": {0xFD88},  # the ligature glyph of LAM MEEM HAH
    "u10a-first": {
        0xFEE4
    },  # MEEM medial: the first component of LAM MEEM HAH and LAM MEEM JEEM
}


def _arabic_glyphs(
    skip: set[int], extra: tuple[int, ...] = ()
) -> tuple[list[tuple[str, int]], dict[int, str]]:
    glyphs = [(".notdef", 500), ("space", 250)]
    cmap = {0x20: "space"}
    cps: list[int] = []
    for letter, (_, *forms) in ARABIC_LETTERS.items():
        cps += [letter, *(f for f in forms if f)]
    cps += list(ARABIC_MARKS) + list(LIG2) + list(LIG3) + list(LIGMARK) + list(extra)
    for i, cp in enumerate(cps):
        if cp in skip or cp in cmap:
            continue
        adv = 0 if _gc(cp) == "Mn" else 300 + 4 * i
        glyphs.append((_name(cp), adv))
        cmap[cp] = _name(cp)
    return glyphs, cmap


def _u10a_fonts(out: Path) -> None:
    """Fonts without `GSUB` whose `cmap` has the presentation forms and ligatures that Arabic fallback shaping
    synthesizes lookups from, each leaving out one kind of piece; and the complete set with a `GSUB`."""
    for name, skip in U10A_FONTS.items():
        glyphs, cmap = _arabic_glyphs(skip)
        fb = _font(name, glyphs, cmap)
        _no_gdef(fb)
        _save(fb, out / f"{name}.ttf")
    glyphs, cmap = _arabic_glyphs(set())
    fb = _font("u10a-gsub", glyphs, cmap)
    subs = {form: [] for form in ("isol", "fina", "init", "medi")}
    for letter, (_, *forms) in ARABIC_LETTERS.items():
        for tag, form in zip(("isol", "fina", "init", "medi"), forms):
            if form:
                subs[tag].append(f"sub {_name(letter)} by {_name(form)};")
    fea = ["languagesystem DFLT dflt;", "languagesystem arab dflt;"]
    for tag, body in subs.items():
        fea.append(f"feature {tag} {{ {' '.join(body)} }} {tag};")
    fea.append(
        f"feature rlig {{ sub {_name(0xFEDF)} {_name(0xFE8E)} by {_name(0xFEFB)}; }} rlig;"
    )
    addOpenTypeFeaturesFromString(fb.font, "\n".join(fea))
    _save(fb, out / "u10a-gsub.ttf")


LAM, MEEM, HAH, JEEM, HEH, ALEF = 0x0644, 0x0645, 0x062D, 0x062C, 0x0647, 0x0627
U10A_DUAL = list(ARABIC_LETTERS)
U10A_JOINERS = [cp for cp, v in ARABIC_LETTERS.items() if v[0] == "D"]
U10A_ENDERS = [cp for cp, v in ARABIC_LETTERS.items() if v[0] == "R"]


def gen_u10a(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 10a: Arabic fallback shaping no longer forms wrong ligatures when a component is missing from the font.

    Inside: fonts without `GSUB` that lack HEH final, the second component of the three-part ligature LAM LAM HEH;
    14.3.0 then reads LAM MEEM JEEM's components one place off and turns a word-initial LAM, medial LAM, medial
    MEEM into that ligature. Texts hold that sequence (with marks, other words and joining letters around it).
    Neighbours: the complete font (`b:complete`); a font missing a component of a two-part ligature only
    (`b:two-part-missing`); a missing ligature glyph (`b:no-ligature-glyph`); a missing first component
    (`b:first-missing`); a font with `GSUB`, which turns fallback shaping off (`b:gsub`); the three-part ligature
    listed before the incomplete one, in the inside fonts (`b:earlier-ligature`).

    Left out: LAM MEEM JEEM in the inside fonts (the valid ligature the wrong one displaced). It changes as the note
    says, but the widening mutant this unit is measured with (later ligatures of a first glyph dropped after an
    incomplete one) gets it wrong as 14.3.0 does, so it cannot serve as a changed case of that mutant.
    """
    inside = [synth / "u10a-p2.ttf", synth / "u10a-p2-sparse.ttf"]
    duals = {
        "b:complete": synth / "u10a-full.ttf",
        "b:two-part-missing": synth / "u10a-d2.ttf",
        "b:no-ligature-glyph": synth / "u10a-noligglyph.ttf",
        "b:first-missing": synth / "u10a-first.ttf",
        "b:gsub": synth / "u10a-gsub.ttf",
    }
    mark_pool = (0x064E, 0x064F, 0x0650, 0x0652, 0x0651)

    def with_marks(seq: list[int]) -> list[int]:
        out: list[int] = []
        for cp in seq:
            out.append(cp)
            if rng.random() < 0.2:
                out.append(rng.choice(mark_pool))
        return out

    def other_word() -> list[int]:
        return [rng.choice(U10A_DUAL) for _ in range(rng.randint(1, 4))]

    def wrap(core: list[int]) -> list[int]:
        """A word starting with `core` (its first letter word-initial), then a joining letter and more."""
        word = core + [rng.choice(U10A_DUAL)]
        if rng.random() < 0.4:
            word += [rng.choice(U10A_DUAL)]
        if rng.random() < 0.4:
            word = [rng.choice(U10A_ENDERS)] + word
        text = with_marks(word)
        if rng.random() < 0.4:
            text = other_word() + [0x20] + text
        if rng.random() < 0.3:
            text = text + [0x20] + other_word()
        return text

    patterns = {
        "wrong": [LAM, LAM, MEEM],
        "l1": [LAM, MEEM, HAH],
        "l2": [LAM, LAM, HEH],
        "l3": [LAM, MEEM, JEEM],
        "lam-alef": [LAM, ALEF],
        "lam-meem": [LAM, MEEM],
        "lam-yeh": [LAM, 0x064A],
        "beh-meem": [0x0628, MEEM],
    }
    for i in range(n):
        kind = rng.choice(("in",) * 6 + tuple(duals) * 2 + ("b:earlier-ligature",))
        cl = rng.choice((0, 1, 2))
        if kind == "in":
            yield case(
                "10a",
                "cand",
                rng.choice(inside),
                wrap(patterns["wrong"]),
                nb=kind,
                cl=cl,
            )
        elif kind == "b:earlier-ligature":
            yield case(
                "10a", "cand", rng.choice(inside), wrap(patterns["l1"]), nb=kind, cl=cl
            )
        elif kind == "b:two-part-missing":
            core = patterns[
                rng.choice(("lam-alef", "lam-alef", "lam-meem", "lam-meem", "l1"))
            ]
            yield case("10a", "cand", duals[kind], wrap(core), nb=kind, cl=cl)
        else:
            core = patterns[rng.choice(tuple(patterns))]
            yield case("10a", "cand", duals[kind], wrap(core), nb=kind, cl=cl)


# Legacy Arabic PUA encodings (HarfBuzz's ArabicPUASimplified.txt and ArabicPUATraditional.txt): code point ->
# (simplified PUA, traditional PUA).
LEGACY_PUA = {
    0x0020: (0xF120, 0xF220), 0x0627: (0xF141, 0xF241), 0xFE8D: (0xF141, 0xF241), 0xFE8E: (0xF142, 0xF242),
    0x0628: (0xF14A, 0xF24C), 0xFE8F: (0xF14A, 0xF24C), 0xFE90: (0xF14A, 0xF24B), 0xFE91: (0xF149, 0xF249),
    0xFE92: (0xF149, 0xF24A), 0x062A: (0xF14C, 0xF250), 0xFE95: (0xF14C, 0xF250), 0xFE96: (0xF14C, 0xF24F),
    0xFE97: (0xF14B, 0xF24D), 0xFE98: (0xF14B, 0xF24E), 0x062F: (0xF158, 0xF265), 0xFEA9: (0xF158, 0xF265),
    0xFEAA: (0xF158, 0xF266), 0x0631: (0xF15A, 0xF269), 0xFEAD: (0xF15A, 0xF269), 0xFEAE: (0xF15A, 0xF26A),
    0x0633: (0xF162, 0xF270), 0xFEB1: (0xF162, 0xF270), 0xFEB2: (0xF162, 0xF26F), 0xFEB3: (0xF161, 0xF26D),
    0xFEB4: (0xF161, 0xF26E), 0x0644: (0xF17C, 0xF2BE), 0xFEDD: (0xF17C, 0xF2BE), 0xFEDE: (0xF17C, 0xF2BD),
    0xFEDF: (0xF17B, 0xF2BB), 0xFEE0: (0xF17B, 0xF2BC), 0x0645: (0xF17E, 0xF2C2), 0xFEE1: (0xF17E, 0xF2C2),
    0xFEE2: (0xF17E, 0xF2C1), 0xFEE3: (0xF17D, 0xF2BF), 0xFEE4: (0xF17D, 0xF2C0), 0x0646: (0xF1E1, 0xF2C6),
    0xFEE5: (0xF1E1, 0xF2C6), 0xFEE6: (0xF1E1, 0xF2C5), 0xFEE7: (0xF17F, 0xF2C3), 0xFEE8: (0xF17F, 0xF2C4),
    0x0647: (0xF1A4, 0xF2CA), 0xFEE9: (0xF1A4, 0xF2CA), 0xFEEA: (0xF1A3, 0xF2C9), 0xFEEB: (0xF1A1, 0xF2C7),
    0xFEEC: (0xF1A2, 0xF2C8), 0x064A: (0xF1A8, 0xF2D0), 0xFEF1: (0xF1A8, 0xF2D0), 0xFEF2: (0xF1A7, 0xF2CF),
    0xFEF3: (0xF1A6, 0xF2CD), 0xFEF4: (0xF1A6, 0xF2CE), 0xFEFB: (0xF1BD, 0xF2DC), 0xFEFC: (0xF1BC, 0xF2DD),
    0x064E: (0xF1C4, 0xF2E4), 0x064F: (0xF1C5, 0xF2E5), 0x0652: (0xF1C6, 0xF2E6), 0x064B: (0xF1C7, 0xF2E7),
    0x064C: (0xF1C8, 0xF2E8), 0x0651: (0xF1C9, 0xF2E9), 0x0650: (0xF1CA, 0xF2EA), 0x064D: (0xF1CB, 0xF2EB),
}  # fmt: skip
LEGACY_LETTERS = (
    0x0627,
    0x0628,
    0x062A,
    0x062F,
    0x0631,
    0x0633,
    0x0644,
    0x0645,
    0x0646,
    0x0647,
    0x064A,
)
ENCODED_MARKS = ARABIC_MARKS  # marks with a legacy encoding
UNENCODED_MARKS = tuple(range(0x0653, 0x065F))  # marks the legacy code pages lack


def _u10b_fonts(out: Path) -> None:
    """Legacy Arabic fonts: a symbol `cmap` of private-use code points, `OS/2` version 0 with the simplified or
    traditional Arabic font page, the PUA glyph the unencoded marks used to map to, and controls."""
    variants = {
        # name: (column of LEGACY_PUA, OS/2 font page, glyph at U+F100/U+F200, direct mark entries, symbol cmap)
        "u10b-simp": (0, 0xB200, True, False, True),
        "u10b-trad": (1, 0xB300, True, False, True),
        "u10b-simp-direct": (0, 0xB200, True, True, True),
        "u10b-simp-nof100": (0, 0xB200, False, False, True),
        "u10b-simp-page0": (0, 0x0000, True, False, True),
        "u10b-simp-unicode": (0, 0xB200, True, False, False),
    }
    for name, (col, page, catch_all, direct, symbol) in variants.items():
        glyphs = [(".notdef", 500)]
        mapping: dict[int, str] = {}
        pua = sorted({codes[col] for codes in LEGACY_PUA.values()})
        for i, code in enumerate(pua):
            gname = f"pua{code:04X}"
            marks = {
                cp
                for cp, codes in LEGACY_PUA.items()
                if codes[col] == code and _gc(cp) == "Mn"
            }
            glyphs.append((gname, 0 if marks else 320 + 5 * i))
            mapping[code] = gname
        if catch_all:
            code = 0xF100 if col == 0 else 0xF200
            glyphs.append((f"pua{code:04X}", 0))
            mapping[code] = f"pua{code:04X}"
        if direct:
            for cp in UNENCODED_MARKS:
                glyphs.append((_name(cp), 0))
                mapping[cp] = _name(cp)
        fb = _font(
            name,
            glyphs,
            mapping,
            os2={"version": 0, "fsSelection": page | 0x40},
            symbol=symbol,
        )
        _save(fb, out / f"{name}.ttf")


def gen_u10b(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 10b: Arabic fallback shaping no longer makes marks disappear in legacy fonts.

    Inside: Arabic words with marks the legacy code pages do not encode (U+0653..U+065E) in legacy fonts (symbol
    `cmap` of private-use glyphs, simplified or traditional Arabic font page) that have the private-use glyph 14.3.0
    sent those marks to. Each text holds marks of one kind only. Neighbours: words whose marks all have a legacy
    encoding, FATHATAN to SUKUN (`b:encoded-mark`); a legacy font that maps the marks directly
    (`b:direct-mark`); a legacy font without that private-use glyph (`b:no-catch-all`); a symbol font without an
    Arabic font page and a font with a Unicode `cmap` (`b:not-legacy`).

    Left out as unstated: ARABIC LETTER KEHEH WITH TWO DOTS ABOVE and the other letters U+063B..U+063F, which 15.2.0
    also stops mapping to that glyph; the note speaks of marks.
    """
    legacy = [synth / "u10b-simp.ttf", synth / "u10b-trad.ttf"]
    duals = {
        "b:direct-mark": [synth / "u10b-simp-direct.ttf"],
        "b:no-catch-all": [synth / "u10b-simp-nof100.ttf"],
        "b:not-legacy": [
            synth / "u10b-simp-page0.ttf",
            synth / "u10b-simp-unicode.ttf",
        ],
    }

    def word(marks: tuple[int, ...], need: int) -> list[int]:
        """Letters with marks of one kind only, so that each text sits on one side of the encoding."""
        letters = [rng.choice(LEGACY_LETTERS) for _ in range(rng.randint(1, 5))]
        slots = rng.sample(range(len(letters)), min(need, len(letters)))
        text: list[int] = []
        for k, cp in enumerate(letters):
            text.append(cp)
            if k in slots:
                text.append(rng.choice(marks))
                if rng.random() < 0.3:
                    text.append(rng.choice(marks))
        return text

    for i in range(n):
        kind = rng.choice(("in",) * 6 + ("b:encoded-mark",) * 2 + tuple(duals))
        cl = rng.choice((0, 1))
        marks = ENCODED_MARKS if kind == "b:encoded-mark" else UNENCODED_MARKS
        text = word(marks, rng.randint(1, 2))
        if rng.random() < 0.3:
            text += [0x20] + word(marks, 1)
        font = rng.choice(legacy if kind in ("in", "b:encoded-mark") else duals[kind])
        opts: dict[str, object] = {"cl": cl}
        if rng.random() < 0.3:
            opts["nf"] = rng.choice((1, 2))
        yield case("10b", "cand", font, text, nb=kind, **opts)


def _cp1256() -> dict[int, int]:
    """Unicode -> byte of Windows-1256 for the bytes 0x20..0xFF."""
    out = {}
    for b in range(0x20, 0x100):
        try:
            ch = bytes([b]).decode("cp1256")
        except UnicodeDecodeError:
            continue
        out[ord(ch)] = b
    return out


U11_SIGNATURE = (
    0x0627,
    0x0644,
    0x0649,
    0x064A,
    0x0652,
)  # ALEF 199, LAM 225, ALEF MAKSURA 236, YEH 237, SUKUN 250
U11_SWAPS = {
    "lam": 0x0644,
    "maksura": 0x0649,
    "yeh": 0x064A,
    "sukun": 0x0652,
    "alef": 0x0627,
}


def _u11_fonts(out: Path) -> None:
    """Fonts laid out in Windows-1256 order (glyph id = byte), as Windows-1256 fallback detects; variants with one
    signature glyph moved, with presentation forms, and with a `GSUB`."""
    enc = _cp1256()
    names = [".notdef"] + [f"g{b:03d}" for b in range(1, 256)]

    def build(
        name: str, swap: int | None = None, presforms: bool = False, gsub: bool = False
    ) -> None:
        glyphs = [(g, 300 + 3 * k) for k, g in enumerate(names)]
        glyphs[0] = (".notdef", 500)
        cmap = {cp: f"g{b:03d}" for cp, b in enc.items()}
        if swap is not None:
            b = enc[swap]
            other = next(cp for cp, ob in enc.items() if ob == b - 1)
            cmap[swap], cmap[other] = cmap[other], cmap[swap]
        if presforms:
            for _, *forms in ARABIC_LETTERS.values():
                for form in forms:
                    if form:
                        glyphs.append((_name(form), 600))
                        cmap[form] = _name(form)
        fb = _font(name, glyphs, cmap)
        if gsub:
            fea = (
                "languagesystem arab dflt;\n"
                "feature init { sub g225 by g141; sub g227 by g142; } init;\n"
                "feature medi { sub g225 by g141; sub g227 by g143; } medi;\n"
                "feature fina { sub g199 by g001; } fina;\n"
            )
            addOpenTypeFeaturesFromString(fb.font, fea)
        _no_gdef(fb)
        _save(fb, out / f"{name}.ttf")

    build("u11-cp1256")
    for key, cp in U11_SWAPS.items():
        build(f"u11-sig-{key}", swap=cp)
    build("u11-presforms", presforms=True)
    build("u11-gsub", gsub=True)


def gen_u11(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 11: Arabic Windows-1256 fallback shaping is enabled on all platforms.

    Inside: Arabic words (letters, harakat, shadda, lam-alef) in our font laid out in Windows-1256 order, which has
    no `GSUB` and no presentation forms. Neighbours: one of LAM, ALEF MAKSURA, YEH or SUKUN at another glyph id
    (`b:sig-mismatch`) or ALEF at another glyph id (`b:sig-alef`), so the font no longer looks Windows-1256-encoded;
    presentation forms in the `cmap`, which fallback shaping prefers (`b:pres-forms`); a `GSUB` (`b:gsub`).

    Left out: nothing.
    """
    enc = _cp1256()
    letters = [cp for cp in enc if 0x0621 <= cp <= 0x064A and _gc(cp) == "Lo"]
    marks = [cp for cp in enc if 0x064B <= cp <= 0x0652]
    duals = {
        "b:sig-mismatch": [
            synth / f"u11-sig-{k}.ttf" for k in ("lam", "maksura", "yeh", "sukun")
        ],
        "b:sig-alef": [synth / "u11-sig-alef.ttf"],
        "b:pres-forms": [synth / "u11-presforms.ttf"],
        "b:gsub": [synth / "u11-gsub.ttf"],
    }

    def word() -> list[int]:
        text: list[int] = []
        for _ in range(rng.randint(2, 6)):
            r = rng.random()
            if r < 0.15:
                text += [0x0644, rng.choice((0x0627, 0x0622, 0x0623, 0x0625))]
            else:
                text.append(rng.choice(letters))
            if rng.random() < 0.25:
                if rng.random() < 0.4:
                    text += [0x0651, rng.choice((0x064E, 0x064F, 0x0650))]
                else:
                    text.append(rng.choice(marks))
        return text

    for i in range(n):
        kind = rng.choice(("in",) * 5 + ("b:sig-mismatch",) * 2 + tuple(duals))
        text = word()
        if rng.random() < 0.3:
            text += [0x20] + word()
        font = synth / "u11-cp1256.ttf" if kind == "in" else rng.choice(duals[kind])
        yield case("11", "cand", font, text, nb=kind, cl=rng.choice((0, 1)))


# ---------------------------------------------------------------------------------------------------------------
# Unit 34: Indic shaping of the Unicode 18 Devanagari and Bengali additions
# ---------------------------------------------------------------------------------------------------------------

DEVA_CONS = list(range(0x0915, 0x093A))
DEVA_MATRAS = (0x093E, 0x093F, 0x0940, 0x0941, 0x0942, 0x0947, 0x0948, 0x094B, 0x094C)
DEVA_MODS = (0x0901, 0x0902, 0x0903)
BENG_CONS = [cp for cp in range(0x0995, 0x09BA) if _gc(cp) == "Lo"]
BENG_MATRAS = (0x09BE, 0x09BF, 0x09C0, 0x09C1, 0x09C7, 0x09C8, 0x09CB, 0x09CC)
BENG_MODS = (0x0981, 0x0982, 0x0983)
NEW_DEVA = 0x11B0A  # DEVANAGARI LETTER ALTERNATE DDDA
NEW_BENG_MARK = 0x11DF0  # BENGALI SIGN COMBINING ANUSVARA ABOVE
NEW_BENG = 0x11DF1  # BENGALI LETTER ALTERNATE BARGIYA BA
EXT_A_SIGNS = list(
    range(0x11B00, 0x11B0A)
)  # Devanagari Extended-A head marks and signs (Po, since Unicode 15)


def _u34_fonts(out: Path) -> None:
    """Devanagari and Bengali fonts with glyphs at the Unicode 18 additions, `rphf`, `half` and `blwf` under `dev2`
    and `bng2`; with `GDEF`, and without."""
    cps = (
        [
            0x20,
            DOTTED,
            *range(0x0901, 0x0904),
            *range(0x0905, 0x0915),
            *DEVA_CONS,
            0x093C,
            *range(0x093E, 0x094E),
        ]
        + [
            *range(0x0981, 0x0984),
            *range(0x0985, 0x098D),
            *BENG_CONS,
            0x09BC,
            *range(0x09BE, 0x09C5),
        ]
        + [0x09C7, 0x09C8, 0x09CB, 0x09CC, 0x09CD, 0x09D7, 0x09F0, 0x09F1]
        + [NEW_DEVA, NEW_BENG_MARK, NEW_BENG, *EXT_A_SIGNS]
    )
    cps = [
        cp
        for cp in dict.fromkeys(cps)
        if cp == NEW_DEVA or cp >= 0x11B00 or _gc(cp) != "Cn"
    ]
    for name, with_gdef in (("u34-indic", True), ("u34-indic-nogdef", False)):
        glyphs = [(".notdef", 500)]
        cmap = {}
        for i, cp in enumerate(cps):
            gname = "dottedcircle" if cp == DOTTED else _name(cp)
            mark = cp == NEW_BENG_MARK or _gc(cp) == "Mn"
            glyphs.append((gname, 0 if mark else 400 + 3 * i))
            cmap[cp] = gname
        extra = [
            ("deva.reph", 0),
            ("deva.rakar", 0),
            ("beng.reph", 0),
            ("beng.raphala", 0),
            ("beng.yaphala", 220),
            *((f"{_name(cp)}.half", 300 + 2 * k) for k, cp in enumerate(DEVA_CONS)),
            (f"{_name(NEW_DEVA)}.half", 333),
            (f"{_name(NEW_BENG)}.half", 334),
        ]
        glyphs += extra
        fb = _font(name, glyphs, cmap)
        halves = " ".join(
            f"sub {_name(cp)} u094D by {_name(cp)}.half;" for cp in DEVA_CONS
        )
        fea = (
            "languagesystem dev2 dflt; languagesystem bng2 dflt;\n"
            "feature rphf { script dev2; sub u0930 u094D by deva.reph; script bng2; sub u09B0 u09CD by beng.reph; } rphf;\n"
            f"feature half {{ script dev2; {halves} sub {_name(NEW_DEVA)} u094D by {_name(NEW_DEVA)}.half;"
            f" script bng2; sub {_name(NEW_BENG)} u09CD by {_name(NEW_BENG)}.half; }} half;\n"
            "feature blwf { script dev2; sub u094D u0930 by deva.rakar; script bng2; sub u09CD u09B0 by beng.raphala; } blwf;\n"
            "feature pstf { script bng2; sub u09CD u09AF by beng.yaphala; } pstf;\n"
        )
        addOpenTypeFeaturesFromString(fb.font, fea)
        if with_gdef:
            classes = {}
            for gname, adv in glyphs:
                if gname == ".notdef":
                    continue
                classes[gname] = 3 if adv == 0 else 1
            _gdef(fb, classes)
        else:
            _no_gdef(fb)
        _save(fb, out / f"{name}.ttf")


def gen_u34(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 34: Indic shaping of the Unicode 18 Devanagari and Bengali additions.

    Inside: syllables built on DEVANAGARI LETTER ALTERNATE DDDA (U+11B0A) and BENGALI LETTER ALTERNATE BARGIYA BA
    (U+11DF1) as consonants (with matras, nukta, virama conjuncts in either position, reph), and BENGALI SIGN
    COMBINING ANUSVARA ABOVE (U+11DF0) after a syllable or alone, shaped with the Devanagari or Bengali script (set or
    guessed), in our fonts that have glyphs for them and in Noto Sans Devanagari and Bengali (`.notdef` glyphs).
    Neighbours: the same syllables with an older letter or sign in place of the addition (`b:older-letter`), and
    with a Devanagari Extended-A head mark or sign (U+11B00..U+11B09, punctuation since Unicode 15) in the
    consonant's place (`b:ext-a-sign`).

    Left out: nothing; text without a script set keeps another Devanagari or Bengali character in it.
    """
    fonts = [
        synth / "u34-indic.ttf",
        synth / "u34-indic.ttf",
        synth / "u34-indic-nogdef.ttf",
    ]
    deva_noto = noto.get("NotoSansDevanagari-Regular")
    beng_noto = noto.get("NotoSansBengali-Regular")

    def deva_syllable(base: int) -> list[int]:
        shape = rng.choice(
            ("matra", "matra", "nukta", "first", "second", "reph", "mod")
        )
        if shape == "matra":
            syl = [base, rng.choice(DEVA_MATRAS)]
        elif shape == "nukta":
            syl = [base, 0x093C] + (
                [rng.choice(DEVA_MATRAS)] if rng.random() < 0.6 else []
            )
        elif shape == "first":
            syl = [base, 0x094D, rng.choice(DEVA_CONS)] + (
                [rng.choice(DEVA_MATRAS)] if rng.random() < 0.6 else []
            )
        elif shape == "second":
            syl = [rng.choice(DEVA_CONS), 0x094D, base] + (
                [rng.choice(DEVA_MATRAS)] if rng.random() < 0.6 else []
            )
        elif shape == "reph":
            syl = [0x0930, 0x094D, base] + (
                [rng.choice(DEVA_MATRAS)] if rng.random() < 0.5 else []
            )
        else:
            syl = [base, rng.choice(DEVA_MODS)]
        if rng.random() < 0.15:
            syl.append(rng.choice(DEVA_MODS))
        return syl

    def beng_syllable(base: int, mark: int) -> list[int]:
        shape = rng.choice(
            (
                "matra",
                "matra",
                "first",
                "second",
                "reph",
                "yaphala",
                "mark",
                "lone-mark",
            )
        )
        if shape == "matra":
            syl = [base, rng.choice(BENG_MATRAS)]
        elif shape == "first":
            syl = [base, 0x09CD, rng.choice(BENG_CONS)] + (
                [rng.choice(BENG_MATRAS)] if rng.random() < 0.6 else []
            )
        elif shape == "second":
            syl = [rng.choice(BENG_CONS), 0x09CD, base] + (
                [rng.choice(BENG_MATRAS)] if rng.random() < 0.6 else []
            )
        elif shape == "reph":
            syl = [0x09B0, 0x09CD, base] + (
                [rng.choice(BENG_MATRAS)] if rng.random() < 0.5 else []
            )
        elif shape == "yaphala":
            syl = [base, 0x09CD, 0x09AF] + (
                [rng.choice(BENG_MATRAS)] if rng.random() < 0.5 else []
            )
        elif shape == "mark":
            syl = [rng.choice((base, rng.choice(BENG_CONS))), mark]
        else:
            syl = [mark]
        return syl

    for i in range(n):
        kind = rng.choice(("in",) * 6 + ("b:older-letter",) * 2 + ("b:ext-a-sign",) * 2)
        deva = rng.random() < 0.5
        if kind == "b:ext-a-sign":
            deva = True
        if deva:
            base = {
                "in": NEW_DEVA,
                "b:older-letter": rng.choice((0x0921, 0x0922, 0x0915, 0x0930)),
            }.get(kind)
            if base is None:
                base = rng.choice(EXT_A_SIGNS)
            syl = deva_syllable(base)
            ctx = [rng.choice(DEVA_CONS), rng.choice(DEVA_MATRAS)]
            script = "Deva"
        else:
            if kind == "in":
                base, mark = rng.choice(
                    (
                        (NEW_BENG, NEW_BENG_MARK),
                        (NEW_BENG, 0x0982),
                        (rng.choice(BENG_CONS), NEW_BENG_MARK),
                    )
                )
            else:
                base, mark = (
                    rng.choice((0x09AC, 0x09F0, 0x09B0)),
                    rng.choice((0x0982, 0x0981)),
                )
            syl = beng_syllable(base, mark)
            if kind == "in" and NEW_BENG not in syl and NEW_BENG_MARK not in syl:
                syl = (
                    [NEW_BENG] + syl[1:]
                    if syl and syl[0] == base
                    else [NEW_BENG, rng.choice(BENG_MATRAS)]
                )
            ctx = [rng.choice(BENG_CONS), rng.choice(BENG_MATRAS)]
            script = "Beng"
        text = list(syl)
        if rng.random() < 0.35:
            text = ctx + text
        if rng.random() < 0.35:
            text = text + rng.choice(([0x20], [])) + ctx
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        if rng.random() < 0.7 or text == syl:
            opts["script"] = script
        noto_font = deva_noto if deva else beng_noto
        font = rng.choice(fonts + ([noto_font] if noto_font else []))
        yield case("34", "cand", font, text, nb=kind, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 2 (labelled): the USE shaper no longer uses a space as the base of a dependent vowel
# ---------------------------------------------------------------------------------------------------------------

USE_SPACES = (
    0x0020,
    0x1680,
    *range(0x2000, 0x200B),
    0x202F,
    0x205F,
    0x3000,
)  # Zs except NO-BREAK SPACE
USE_DEP_VOWELS = {
    "bali": list(range(0x1B35, 0x1B44)),
    "java": list(range(0xA9B4, 0xA9BD)),
    "lana": list(range(0x1A61, 0x1A74)),
}
USE_BLOCKS = {
    "bali": (0x1B05, 0x1B4C),
    "java": (0xA984, 0xA9B2),
    "lana": (0x1A20, 0x1A54),
}
USE_NOTO = {
    "bali": "NotoSansBalinese-Regular",
    "java": "NotoSansJavanese-Regular",
    "lana": "NotoSansTaiTham-Regular",
}


def gen_u2(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 2: the USE shaper no longer uses a space as the base of a dependent vowel; the vowel gets a dotted circle.

    Inside: a space separator other than NO-BREAK SPACE followed by one or two dependent vowels, between or after
    syllables, in Noto Sans Balinese and Javanese (Noto Sans Tai Tham has no dotted circle, so nothing changes
    there). Neighbours: NO-BREAK SPACE (`b:nbsp`) or DOTTED CIRCLE (`b:dotted-circle`) as the base, which every
    release keeps; a space followed by a consonant and its vowel
    (`b:space-consonant`); the space only in the pre-context of a text that opens with the vowel
    (`b:space-in-context`, a dotted circle in every release).

    Left out as unstated: a space followed by a mark that is not a dependent vowel (vowel modifiers, finals,
    consonant modifiers); 15.2.0 gives those a dotted circle too.
    """
    usable = []
    for tag, stem in USE_NOTO.items():
        f = noto.get(stem)
        if not f or not f.has(DOTTED):
            continue  # without a dotted circle glyph no release inserts one
        vowels = [cp for cp in USE_DEP_VOWELS[tag] if f.has(cp)]
        cons = [cp for cp in f.block(*USE_BLOCKS[tag], ("Lo",))]
        if vowels and cons:
            usable.append((f, vowels, cons))
    for i in range(n):
        f, vowels, cons = usable[i % len(usable)]
        kind = rng.choice(
            ("in",) * 6
            + (
                "b:nbsp",
                "b:nbsp",
                "b:dotted-circle",
                "b:space-consonant",
                "b:space-in-context",
            )
        )
        vs = [rng.choice(vowels) for _ in range(rng.choice((1, 1, 2)))]
        before = (
            [rng.choice(cons)] + ([rng.choice(vowels)] if rng.random() < 0.3 else [])
            if rng.random() < 0.6
            else []
        )
        after = [rng.choice(cons)] if rng.random() < 0.3 else []
        opts: dict[str, object] = {"cl": rng.choice((0, 1))}
        if kind == "in":
            text = before + [rng.choice(USE_SPACES)] + vs + after
        elif kind == "b:nbsp":
            text = before + [NBSP] + vs + after
        elif kind == "b:dotted-circle":
            text = before + [DOTTED] + vs + after
        elif kind == "b:space-consonant":
            text = before + [rng.choice(USE_SPACES), rng.choice(cons)] + vs + after
        else:
            opts["pre"] = _hex(before + [rng.choice(USE_SPACES)])
            text = vs + after
        yield case("2", "cand", f, text, nb=kind, **opts)


# ---------------------------------------------------------------------------------------------------------------
# Unit 4 (labelled): the Khmer shaper moves only one Coeng Ro, and only as the first or second coeng
# ---------------------------------------------------------------------------------------------------------------

KHMER_RO, KHMER_COENG = 0x179A, 0x17D2


def gen_u4(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 4: the Khmer shaper moves only one Coeng Ro before the base, and only as the first or second coeng.

    Inside (one syllable with a Coeng Ro in the text, other syllables without): a Coeng Ro as first coeng followed
    by another Coeng Ro; a Coeng Ro as second coeng followed by another; a Coeng Ro as third coeng after two other
    coengs. Neighbours: exactly one Coeng Ro as first or second coeng (`b:single-ro`); Coeng Ro, another coeng, then
    Coeng Ro (`b:ro-gap`, the second never moves); a Coeng Ro as fourth coeng (`b:ro-fourth`); coengs without Ro
    (`b:no-ro`); two or three syllables each with one Coeng Ro as first or second coeng (`b:next-syllable`).

    Left out: nothing.
    """
    fonts = [
        f
        for f in (noto.get("NotoSansKhmer-Regular"), noto.get("NotoSerifKhmer-Regular"))
        if f
    ]
    patterns = {
        "in": (["R", "R"], ["R", "R", "X"], ["R", "R", "R"], ["X", "R", "R"], ["X", "R", "R", "X"], ["X", "X", "R"],
               ["X", "X", "R", "X"], ["X", "X", "R", "R"]),
        "b:single-ro": (["R"], ["R", "X"], ["X", "R"], ["X", "R", "X"], ["R", "X", "X"]),
        "b:ro-gap": (["R", "X", "R"], ["R", "X", "R", "X"]),
        "b:ro-fourth": (["X", "X", "X", "R"],),
        "b:no-ro": (["X"], ["X", "X"], ["X", "X", "X"]),
    }  # fmt: skip

    def syllable(f: Font, pattern: list[str]) -> list[int]:
        cons = [cp for cp in f.block(0x1780, 0x17A2, ("Lo",)) if cp != KHMER_RO]
        vowels = f.block(0x17B6, 0x17C5, ("Mn", "Mc"))
        signs = [
            cp for cp in f.block(0x17C6, 0x17D1, ("Mn", "Mc")) if cp != KHMER_COENG
        ]
        syl = [rng.choice(cons + [KHMER_RO])]
        for p in pattern:
            syl += [KHMER_COENG, KHMER_RO if p == "R" else rng.choice(cons)]
        if vowels and rng.random() < 0.5:
            syl.append(rng.choice(vowels))
        if signs and rng.random() < 0.25:
            syl.append(rng.choice(signs))
        return syl

    for i in range(n):
        f = fonts[i % len(fonts)]
        kind = rng.choice(
            ("in",) * 6
            + ("b:single-ro", "b:ro-gap", "b:ro-fourth", "b:no-ro")
            + ("b:next-syllable",) * 2
        )
        cl = rng.choice((0, 1, 2))
        if kind == "b:next-syllable":
            text = []
            for _ in range(rng.randint(2, 3)):
                text += syllable(f, rng.choice(patterns["b:single-ro"]))
        else:
            text = syllable(f, rng.choice(patterns[kind]))
            if rng.random() < 0.3:
                text = syllable(f, rng.choice(patterns["b:no-ro"])) + text
            if rng.random() < 0.3:
                text = text + syllable(f, rng.choice(patterns["b:no-ro"]))
        yield case("4", "cand", f, text, nb=kind, cl=cl)


# ---------------------------------------------------------------------------------------------------------------
# Unit 7 (labelled): prohibited vowel sequences get a dotted circle also across a default ignorable
# ---------------------------------------------------------------------------------------------------------------

INDIC_VC = (
    (0x0905, 0x0946), (0x0905, 0x093E), (0x0909, 0x0941), (0x090F, 0x0945), (0x090F, 0x0946), (0x090F, 0x0947),
    (0x0905, 0x0949), (0x0906, 0x0945), (0x0905, 0x094A), (0x0906, 0x0946), (0x0905, 0x094B), (0x0906, 0x0947),
    (0x0905, 0x094C), (0x0906, 0x0948), (0x0905, 0x0945), (0x0905, 0x093A), (0x0905, 0x093B), (0x0906, 0x093A),
    (0x0905, 0x094F), (0x0905, 0x0956), (0x0905, 0x0957), (0x0930, 0x094D, 0x0907),
    (0x0985, 0x09BE), (0x098B, 0x09C3), (0x098C, 0x09E2),
)  # fmt: skip
DEFAULT_IGNORABLES = (
    ZWJ,
    ZWNJ,
    CGJ,
    WJ,
    SHY,
    0x200E,
    0x200F,
    0xFE00,
    0xFE0F,
    0xFEFF,
    0x2061,
    0x2063,
    0x180B,
    0xE0041,
)
VC_ALLOWED = {
    0x0905: (0x0940, 0x0942, 0x0943),
    0x0985: (0x09C0, 0x09C1),
    0x0906: (0x0941, 0x093F),
}


def gen_u7(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 7: prohibited vowel sequences get a dotted circle also when a default ignorable is between the vowels.

    Inside: a prohibited sequence (Devanagari and Bengali in the Noto fonts; Brahmi, Takri, Khojki, Khudawadi,
    Tirhuta, Modi and Sinhala in our font with `GDEF`) with one or two default ignorables (ZWJ, ZWNJ, CGJ, WJ, SOFT
    HYPHEN, LRM, RLM, variation selectors, ZWNBSP, invisible operators, a Mongolian free variation selector, a tag
    character) between its elements. Neighbours: the sequence with nothing between (`b:adjacent`); a space between
    (`b:space-between`, Devanagari and Bengali only: a space before a USE dependent vowel is unit 2's change);
    NO-BREAK SPACE between (`b:nbsp-between`); a letter, sign, digit or punctuation between (`b:other-between`); a
    sequence that is not prohibited, with a default ignorable between (`b:allowed-pair`); default ignorables only
    before or after the sequence (`b:di-outside`).

    Left out: nothing. Our font without `GDEF` is not used here, so the dotted circle's advance (unit 6) stays the
    same in every release.
    """
    deva = noto.get("NotoSansDevanagari-Regular")
    beng = noto.get("NotoSansBengali-Regular")
    use_font = synth / "u6-use-gdef.ttf"
    pools: list[tuple[object, tuple[int, ...], list[int]]] = []
    for seq in INDIC_VC:
        f = deva if seq[0] < 0x0980 else beng
        if f and f.has(*seq):
            cons = (
                f.block(0x0915, 0x0939, ("Lo",))
                if seq[0] < 0x0980
                else f.block(0x0995, 0x09B9, ("Lo",))
            )
            pools.append((f, seq, cons))
    for seq in USE_VC_PAIRS:
        pools.append((use_font, seq, list(USE_VC_CONS[_vc_script(seq[0])])))
    others = (0x0964, 0x002D, 0x0031)
    for i in range(n):
        f, seq, cons = pools[i % len(pools)]
        kind = rng.choice(("in",) * 6 + ("b:adjacent", "b:space-between", "b:nbsp-between", "b:other-between")
                          + ("b:nbsp-between", "b:allowed-pair", "b:di-outside"))  # fmt: skip
        if kind == "b:space-between" and f == use_font:
            kind = "b:nbsp-between"  # a space before a USE dependent vowel is unit 2's change
        if kind == "b:allowed-pair":
            first = seq[0] if seq[0] in VC_ALLOWED else rng.choice(tuple(VC_ALLOWED))
            f = deva if first < 0x0980 else beng
            if not f:
                continue
            seq = (first, rng.choice(VC_ALLOWED[first]))
            cons = (
                f.block(0x0915, 0x0939, ("Lo",))
                if first < 0x0980
                else f.block(0x0995, 0x09B9, ("Lo",))
            )
        gaps = len(seq) - 1
        text = [seq[0]]
        for g in range(gaps):
            if kind in ("in", "b:allowed-pair"):
                take = g == gaps - 1 or rng.random() < 0.5
                if kind == "in" and g == 0 and gaps > 1:
                    take = rng.random() < 0.5
                if take:
                    text += [
                        rng.choice(DEFAULT_IGNORABLES)
                        for _ in range(rng.choice((1, 1, 2)))
                    ]
            elif kind == "b:space-between":
                text.append(0x20)
            elif kind == "b:nbsp-between":
                text.append(NBSP)
            elif kind == "b:other-between":
                text.append(rng.choice(list(others) + list(cons)))
            text.append(seq[g + 1])
        if kind == "b:di-outside":
            if rng.random() < 0.5:
                text = [rng.choice(DEFAULT_IGNORABLES)] + text
            else:
                text = text + [rng.choice(DEFAULT_IGNORABLES)]
        if rng.random() < 0.3 and cons:
            text = [rng.choice(cons)] + text
        if rng.random() < 0.3 and cons:
            text = text + [rng.choice(cons)]
        yield case("7", "cand", f, text, nb=kind, cl=rng.choice((0, 1)))


# ---------------------------------------------------------------------------------------------------------------
# Module contract
# ---------------------------------------------------------------------------------------------------------------


def build_fonts(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _u3_font(out)
    _u6_hangul_fonts(out)
    _u6_use_fonts(out)
    _u8_fonts(out)
    _u9_fonts(out)
    _u10a_fonts(out)
    _u10b_fonts(out)
    _u11_fonts(out)
    _u34_fonts(out)


UNITS = {
    "2": gen_u2,
    "3": gen_u3,
    "4": gen_u4,
    "6": gen_u6,
    "7": gen_u7,
    "8": gen_u8,
    "9": gen_u9,
    "10a": gen_u10a,
    "10b": gen_u10b,
    "11": gen_u11,
    "34": gen_u34,
}

PER_UNIT = {
    "3": 800,
    "6": 800,
    "8": 700,
    "9": 800,
    "10a": 600,
    "10b": 600,
    "11": 600,
    "34": 1200,
}

W_TARGETS = {
    "1": ["b:space", "b:punct", "b:digit"],
    "2": ["b:nbsp"],
    "3": ["b:digit"],
    "4": ["b:next-syllable"],
    "5": ["b:noflag"],
    "6": ["b:gdef-dc-mark"],
    "7": ["b:nbsp-between"],
    "8": ["b:hebr-script"],
    "9": ["b:long-word"],
    "10a": ["b:two-part-missing"],
    "10b": ["b:encoded-mark"],
    "11": ["b:sig-mismatch"],
    "34": ["b:ext-a-sign"],
}
