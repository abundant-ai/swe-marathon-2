"""Candidates for the metrics, extents, positions, Unicode data and language-tag units (19, 33, 35-39, 42, 43, 50).

Runs inside the pipeline image (imported by cases.py and synth_fonts.py). Fonts are ours: box outlines built with
fontTools, units per em 1024 where scaled values must stay exact (x_scale / 1024 then has few significant bits, so
every product of a small integer and the scale is exact in single precision and no rounding, fused or not, can
differ between machines). Development tooling, never shipped.

API candidates run through tests/driver/hbapi.c (drv "api"); shaping candidates through hbdrv; unit 33's script
constants through hbapi33.c (drv "api33") and its dominant baselines through hbmeta.c (drv "meta").
"""

from __future__ import annotations

import math
import random
import struct
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path

from casekit import Font, api_case, case
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import _k_e_r_n
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables.TupleVariation import TupleVariation

I32_MAX = 2**31 - 1
I32_MIN = -(2**31)
UCD = Path("/dl/unicode/UCD-18.0.0.zip")

# --------------------------------------------------------------------------------------------------------------
# Font helpers
# --------------------------------------------------------------------------------------------------------------


def rect(
    x0: int, y0: int, x1: int, y1: int, pen: TTGlyphPen | None = None
) -> TTGlyphPen:
    """A rectangle contour; points 0-3 are (x0,y0), (x0,y1), (x1,y1), (x1,y0)."""
    pen = pen or TTGlyphPen(None)
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()
    return pen


def wide_rect(x0: int, y0: int, x1: int, y1: int) -> TTGlyphPen:
    """A rectangle with a midpoint on each horizontal edge, so no stored point delta exceeds 16 bits."""
    mid = (x0 + x1) // 2
    pen = TTGlyphPen(None)
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((mid, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.lineTo((mid, y0))
    pen.closePath()
    return pen


def empty_glyph():
    return TTGlyphPen(None).glyph()


def ttf(
    family: str,
    order: list[str],
    cmap: dict[int, str],
    glyphs: dict,
    metrics: dict[str, tuple[int, int]],
    upem: int = 1024,
    vmetrics: dict[str, tuple[int, int]] | None = None,
    asc: int = 800,
    desc: int = -224,
) -> FontBuilder:
    """A TrueType font. `metrics` maps glyph name to (advance, left side bearing)."""
    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=asc, descent=desc)
    fb.setupVerticalMetrics(vmetrics or {n: (upem, 100) for n in order})
    fb.setupVerticalHeader(ascent=upem // 2, descent=-(upem // 2))
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(
        sTypoAscender=asc,
        sTypoDescender=desc,
        usWinAscent=asc,
        usWinDescent=-desc,
    )
    fb.setupPost()
    return fb


def add_raw_table(fb: FontBuilder, tag: str, data: bytes) -> None:
    table = DefaultTable(tag)
    table.data = data
    fb.font[tag] = table


def kerx_format0(pairs: dict[tuple[int, int], int]) -> bytes:
    """One `kerx` table with one format 0 subtable (Apple TrueType Reference Manual, `kerx`)."""
    items = sorted(pairs.items())
    n = len(items)
    unit = 6
    search = unit * (1 << (n.bit_length() - 1)) if n else 0
    selector = (n.bit_length() - 1) if n else 0
    body = struct.pack(">IIII", n, search, selector, unit * n - search)
    body += b"".join(struct.pack(">HHh", a, b, v) for (a, b), v in items)
    sub = struct.pack(">III", 12 + len(body), 0, 0) + body
    return struct.pack(">HHI", 2, 0, 1) + sub


def png(width: int, height: int, seed: int) -> bytes:
    """A small valid truecolour PNG whose pixels depend on `seed`."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    rows = b"".join(
        b"\x00" + bytes((seed * 37 + x * 11 + y * 5) & 0xFF for x in range(width * 3))
        for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------------------------------------------
# Unit 36: positions and extents saturate
# --------------------------------------------------------------------------------------------------------------

U36_LETTERS = "ABCDEFGHIJKLMN"
# Advances in font units (units per em 1024); all at most 32767, so the 16-bit scaler arguments of 14.3.0 hold them.
U36_ADV = dict(
    zip(
        U36_LETTERS,
        (
            30000,
            26000,
            22000,
            18000,
            30000,
            26000,
            30000,
            24000,
            30000,
            20000,
            1000,
            20000,
            30000,
            12000,
        ),
    )
)
# SinglePos xAdvance (kern feature): A B C D; PairPos format 1: E F; PairPos format 2: G H with I J.
U36_SINGLE = {"A": 30000, "B": 25000, "C": 20000, "D": 15000}
U36_PAIR1 = {("E", "F"): 28000, ("F", "E"): 21000, ("E", "E"): 32000}
U36_PAIR2 = 26000  # [G H] followed by [I J]
U36_MARK_BASE_X, U36_MARK_X = (
    -15000,
    15000,
)  # anchors: the mark lands 30000 units left of the base origin
U36_WIDE_ADV = {"P": 40000, "Q": 50000, "R": 65535, "S": 33000}


def u36_pos_font(out: Path) -> None:
    """GPOS single and pair adjustments, mark attachment and placements with values near the 16-bit limit."""
    names = [".notdef", "space", *U36_LETTERS, "acutecomb", "gravecomb"]
    cmap = {0x20: "space", 0x301: "acutecomb", 0x300: "gravecomb"}
    cmap.update({ord(c): c for c in U36_LETTERS})
    glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
    metrics = {".notdef": (500, 50), "space": (512, 0)}
    for i, c in enumerate(U36_LETTERS):
        glyphs[c] = rect(100, 0, 900 + 10 * i, 700).glyph()
        metrics[c] = (U36_ADV[c], 100)
    for m in ("acutecomb", "gravecomb"):
        glyphs[m] = rect(-300, 800, -100, 1000).glyph()
        metrics[m] = (0, -300)
    fb = ttf("u36-pos", names, cmap, glyphs, metrics)
    single = " ".join(f"pos {g} <0 0 {v} 0>;" for g, v in U36_SINGLE.items())
    pair1 = " ".join(f"pos {a} {b} {v};" for (a, b), v in U36_PAIR1.items())
    fea = f"""
languagesystem DFLT dflt; languagesystem latn dflt;
markClass [acutecomb gravecomb] <anchor {U36_MARK_X} 0> @TOP;
feature kern {{
  lookup SINGLE_ADV {{ {single} }} SINGLE_ADV;
  lookup PAIR_ONE {{ {pair1} }} PAIR_ONE;
  lookup PAIR_TWO {{ pos [G H] [I J] {U36_PAIR2}; }} PAIR_TWO;
}} kern;
feature dist {{
  lookup PLACE_ONE {{ pos K <30000 30000 0 0>; pos N <20000 20000 0 0>; }} PLACE_ONE;
  lookup PLACE_TWO {{ pos K <30000 30000 0 0>; pos N <20000 20000 0 0>; }} PLACE_TWO;
}} dist;
feature mark {{
  pos base [{" ".join(U36_LETTERS)}] <anchor {U36_MARK_BASE_X} 30000> mark @TOP;
}} mark;
"""
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(out / "u36-pos.ttf"))


def u36_kern_font(out: Path, tag: str) -> None:
    """Pair kerning near the 16-bit limit from an OpenType `kern` table or an AAT `kerx` table, without GPOS."""
    names = [".notdef", "space", *U36_LETTERS]
    cmap = {0x20: "space", **{ord(c): c for c in U36_LETTERS}}
    glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
    metrics = {".notdef": (500, 50), "space": (512, 0)}
    for i, c in enumerate(U36_LETTERS):
        glyphs[c] = rect(100, 0, 900 + 10 * i, 700).glyph()
        metrics[c] = (U36_ADV[c], 100)
    fb = ttf(f"u36-{tag}", names, cmap, glyphs, metrics)
    pairs = {
        ("A", "B"): 30000,
        ("B", "A"): 28000,
        ("C", "D"): 24000,
        ("E", "E"): 32000,
        ("G", "H"): 20000,
    }
    if tag == "kern":
        kern = newTable("kern")
        kern.version = 0
        sub = _k_e_r_n.KernTable_format_0()
        sub.version = 0
        sub.coverage = 1
        sub.format = 0
        sub.kernTable = dict(pairs)
        kern.kernTables = [sub]
        fb.font["kern"] = kern
    else:
        order = fb.font.getGlyphOrder()
        add_raw_table(
            fb,
            "kerx",
            kerx_format0(
                {(order.index(a), order.index(b)): v for (a, b), v in pairs.items()}
            ),
        )
    fb.save(str(out / f"u36-{tag}.ttf"))


def u36_wide_font(out: Path) -> None:
    """Advances above 32767 units, and glyphs wider than 32767 units whose left side bearing is not xMin."""
    names = [".notdef", "space", *U36_WIDE_ADV, "W1", "W2", "W3", "W4", "V1"]
    cmap = {0x20: "space", **{ord(c): c for c in U36_WIDE_ADV}}
    cmap.update({0x57: "W1", 0x58: "W2", 0x59: "W3", 0x5A: "W4", 0x56: "V1"})
    glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
    metrics = {".notdef": (500, 50), "space": (512, 0)}
    vmetrics = {n: (1024, 100) for n in names}
    for c, adv in U36_WIDE_ADV.items():
        glyphs[c] = rect(100, 0, 900, 700).glyph()
        metrics[c] = (adv, 100)
    # (xMin, xMax, hmtx lsb): width = xMax - xMin above 32767, lsb + width above 32767.
    wide = {
        "W1": (-20000, 20000, 0),
        "W2": (-16000, 17000, 1000),
        "W3": (-30000, 30000, 5000),
        "W4": (-1000, 32000, 200),
    }
    for n, (x0, x1, lsb) in wide.items():
        glyphs[n] = wide_rect(x0, -100, x1, 700).glyph()
        metrics[n] = (1000, lsb)
    glyphs["V1"] = rect(100, 0, 900, 700).glyph()
    metrics["V1"] = (1000, 100)
    vmetrics["V1"] = (45000, 100)
    for c, advance in U36_WIDE_ADV.items():
        vmetrics[c] = (advance, 100)
    fb = ttf("u36-wide", names, cmap, glyphs, metrics, vmetrics=vmetrics)
    # The horizontal header's 16-bit summary fields cannot describe these glyphs: compute the glyph boxes here,
    # keep the given side bearings, and fill the summaries by hand (HarfBuzz does not read them for extents).
    font = fb.font
    glyf = font["glyf"]
    for nme in names:
        glyf[nme].recalcBounds(glyf)
    font.recalcBBoxes = False
    boxes = [glyf[nme] for nme in names if glyf[nme].numberOfContours]
    head = font["head"]
    head.xMin, head.yMin = min(g.xMin for g in boxes), min(g.yMin for g in boxes)
    head.xMax, head.yMax = max(g.xMax for g in boxes), max(g.yMax for g in boxes)
    hhea = font["hhea"]
    hhea.advanceWidthMax = max(a for a, _ in metrics.values())
    hhea.minLeftSideBearing = min(lsb for _, lsb in metrics.values())
    hhea.minRightSideBearing = -32768
    hhea.xMaxExtent = 32767
    vhea = font["vhea"]
    vhea.advanceHeightMax = max(a for a, _ in vmetrics.values())
    vhea.minTopSideBearing, vhea.minBottomSideBearing, vhea.yMaxExtent = (
        0,
        -32768,
        32767,
    )
    font["maxp"].recalc(font)
    fb.save(str(out / "u36-wide.ttf"))


def em(v: int, s: int) -> int:
    """HarfBuzz's fixed-point font-unit scaler for units per em 1024 (both releases agree for |s| < 2**31)."""
    mult = s * 64  # (int64) s * 0x10000 / 1024, exact
    return (v * mult + 32768) >> 16


def sat(v: int) -> int:
    return max(I32_MIN, min(I32_MAX, v))


U36_KERN_PAIRS = {"AB": 30000, "BA": 28000, "CD": 24000, "EE": 32000, "GH": 20000}


def u36_positions(kind: str, glyphs: str, s: int) -> list[list[int]] | None:
    """The scaled terms summed into each position the case changes, in the order they are added; None when a term
    alone leaves the 32-bit range."""
    if kind == "single":
        g = glyphs[0]
        sums = [[em(U36_ADV[g], s), em(U36_SINGLE[g], s)]]
    elif kind == "pair1":
        sums = [[em(U36_ADV[glyphs[0]], s), em(U36_PAIR1[(glyphs[0], glyphs[1])], s)]]
    elif kind == "pair2":
        sums = [[em(U36_ADV[glyphs[0]], s), em(U36_PAIR2, s)]]
    elif kind == "place":
        v = em(30000 if glyphs[0] == "K" else 20000, s)
        sums = [[v, v], [v, v]]
    elif kind == "mark":
        if s % 1024:
            return None
        sums = [
            [(U36_MARK_BASE_X - U36_MARK_X) * s // 1024, -em(U36_ADV[glyphs[0]], s)]
        ]
    else:
        k = em(U36_KERN_PAIRS[glyphs], s)
        if k > I32_MAX or k < I32_MIN:
            return None
        k1 = k >> 1
        sums = [
            [em(U36_ADV[glyphs[0]], s), k1],
            [em(U36_ADV[glyphs[1]], s), k - k1],
            [k - k1],
        ]
    # Every glyph's own scaled advance must fit too: a scaled value that overflows alone wraps in every release.
    advances = [em(U36_ADV[g], s) for g in glyphs]
    if any(t > I32_MAX or t < I32_MIN for terms in [*sums, advances] for t in terms):
        return None
    return sums


def u36_classify(sums: list[list[int]]) -> str:
    totals = [sum(t) for t in sums]
    if any(t > I32_MAX or t < I32_MIN for t in totals):
        return "in"
    top = max(totals, key=abs)
    if abs(top) >= I32_MAX - 2**16 and top % 128:
        return "near"
    return "plain"


def gen_36(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 36: glyph positions and extents saturate instead of overflowing.

    Inside: a position whose 14.3.0 sum overflows 32 bits (GPOS single and pair adjustments added to the advance,
    a mark offset minus the base advance, two placements on one glyph, `kern` and `kerx` pairs), every scaled term
    fitting on its own, so only the sum overflows. Values that overflowed the 16-bit scaler arguments of 14.3.0
    (advances above 32767 units, stored extents whose bearing plus width passes 32767) are generated but marked
    `x:16bit` and never graded: 15.0.0 gives their exact values, the note only says that values saturate.
    All terms of a sum share one sign, so saturating each step equals clamping the exact sum. Boundary
    `b:near-limit`: the same positions at scales that bring the largest within 2**16 of the limit without
    overflowing, at values single precision cannot hold. Left out: scaled values that overflow on their own (every
    release still wraps them, which the note does not describe), slant and emboldening and vertical origins (more
    saturation sites changed in 15.2.0), and buffer normalization (its intermediate sum makes the result depend on
    how intermediates are clamped). Inside cases that leave a large position below the limit (marks, placements,
    pairs) use scales that are multiples of 2**20, so anchors and every scaled value are exact in single precision.
    """
    pos, kern, kerx, wide = (
        synth / f"u36-{t}.ttf" for t in ("pos", "kern", "kerx", "wide")
    )
    kinds = ("single", "pair1", "pair2", "place", "mark", "kern", "kerx")
    for i in range(n):
        kind = kinds[i % len(kinds)]
        if kind == "single":
            glyphs = rng.choice(list(U36_SINGLE))
        elif kind == "pair1":
            glyphs = "".join(rng.choice(list(U36_PAIR1)))
        elif kind == "pair2":
            glyphs = rng.choice("GH") + rng.choice("IJ")
        elif kind == "place":
            glyphs = rng.choice("KN")
        elif kind == "mark":
            glyphs = rng.choice("EFGHILM")
        else:
            glyphs = rng.choice(list(U36_KERN_PAIRS))
        want = "in" if kind == "mark" or rng.random() < 0.6 else "near"
        sign = rng.choice((1, -1))
        found = None
        for _ in range(60):
            if kind in ("mark", "place", "kern", "kerx") and want == "in":
                # Multiples of 2**20: every scaled value is then a multiple of 1024, exact in single precision,
                # so the positions these cases leave below the limit carry no rounding of any kind.
                s = rng.randint(30, 96) * 2**20 * sign
            else:
                sums = u36_positions(kind, glyphs, 1024 * sign)
                unit_total = max(abs(sum(t)) for t in sums) / 1024
                if want == "in":
                    s = (
                        int(rng.uniform(2**31 / unit_total, 2**31 / unit_total * 1.9))
                        * sign
                    )
                else:
                    s = int((I32_MAX - rng.randint(1, 2**16)) / unit_total) * sign
            sums = u36_positions(kind, glyphs, s)
            if sums is not None and u36_classify(sums) == want:
                found = s
                break
        if found is None:
            continue
        text = [ord(c) for c in glyphs]
        if kind == "mark":
            text.append(rng.choice((0x301, 0x300)))
        font = {"kern": kern, "kerx": kerx}.get(kind, pos)
        yield case(
            "36",
            "cand",
            font,
            text,
            nb="in" if want == "in" else "b:near-limit",
            scale=found,
            cl=rng.choice((0, 1)),
        )
        # Values that overflow the 16-bit scaler arguments of 14.3.0, at the default scale. Left out of the
        # cases (nb x:): 15.0.0 gives their exact values, while the note says only that values saturate, so a
        # port that saturates at 16 bits would be as faithful to the note.
        if i % 3 == 0:
            r = rng.random()
            if r < 0.4:
                text = [
                    rng.choice([ord(c) for c in U36_WIDE_ADV])
                    for _ in range(rng.randint(1, 3))
                ]
                yield case(
                    "36", "cand", wide, text, nb="x:16bit", cl=rng.choice((0, 1))
                )
            elif r < 0.6:
                text = [
                    rng.choice((0x56, *[ord(c) for c in U36_WIDE_ADV]))
                    for _ in range(rng.randint(1, 3))
                ]
                yield case("36", "cand", wide, text, nb="x:16bit", dir="ttb")
            else:
                gids = rng.sample(range(6, 10), rng.randint(1, 3))
                yield api_case("36", wide, "ext", gids, nb="x:16bit")


# --------------------------------------------------------------------------------------------------------------
# Unit 37: overflow fixes in synthetic slant and emboldening of glyph extents
# --------------------------------------------------------------------------------------------------------------


def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def wrap(v: int) -> int:
    return (v + 2**31) % 2**32 - 2**31


def floor_f(x: float) -> int:
    return math.floor(x)


def ceil_f(x: float) -> int:
    return math.ceil(x)


def syn_old(e, slant, xs, ys, scale, inplace):
    """14.3.0's synthetic_glyph_extents on 32-bit integers; None when a float result leaves the int range."""
    xb, yb, w, h = e
    if slant:
        x1, y1, x2, y2 = xb, yb, wrap(xb + w), wrap(yb + h)
        a, b = f32(f32(float(y1)) * slant), f32(f32(float(y2)) * slant)
        fx1 = f32(f32(float(x1)) + floor_f(min(a, b)))
        fx2 = f32(f32(float(x2)) + ceil_f(max(a, b)))
        if not (I32_MIN <= fx1 <= I32_MAX and I32_MIN <= fx2 <= I32_MAX):
            return None
        x1, x2 = int(fx1), int(fx2)
        xb, w = x1, wrap(x2 - x1)
    if xs or ys:
        ysh = -ys if scale < 0 else ys
        yb, h = wrap(yb + ysh), wrap(h - ysh)
        xsh = -xs if scale < 0 else xs
        if inplace:
            xb = wrap(xb - int(xsh / 2))
        w = wrap(w + xsh)
    return xb, yb, w, h


def syn_new(e, slant, xs, ys, scale, inplace):
    """15.0.0's synthetic_glyph_extents: 64-bit sums clamped to 32 bits."""
    xb, yb, w, h = e
    if slant:
        y1, y2 = yb, yb + h
        a, b = f32(f32(float(y1)) * slant), f32(f32(float(y2)) * slant)
        x1 = xb + floor_f(min(a, b))
        x2 = xb + w + ceil_f(max(a, b))
        xb, w = sat(x1), sat(x2 - x1)
    if xs or ys:
        ysh = -ys if scale < 0 else ys
        yb, h = sat(yb + ysh), sat(h - ysh)
        xsh = -xs if scale < 0 else xs
        if inplace:
            xb = sat(xb - int(xsh / 2))
        w = sat(w + xsh)
    return xb, yb, w, h


def u32(v: int) -> int:
    return v & 0xFFFFFFFF


def gen_37(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 37: synthetic slant and emboldening of glyph extents no longer overflow.

    HarfBuzz's own OpenType font functions take synthetic extents from the drawn outline, so the arithmetic the note
    fixes runs for extents a client's font functions report (public API since 14.3.0): the probe installs a
    glyph-extents callback that reports the case's four values. Inside: values whose 14.3.0 sums overflow 32 bits
    (bearing plus size under slant, bearing and size plus the emboldening shift). With slant, all values are
    multiples of 512 and the slant a short binary fraction, so 14.3.0's single-precision steps are exact and the only
    difference is the overflow. Boundary `b:no-overflow`: emboldening of large odd values that do not overflow (exact
    in every release). Left out: slant with values 14.3.0 rounds through single precision (a precision change, not an
    overflow), and the scaling fix of 873dbc1e3, whose overflow needs extents beyond 16 bits, where 14.3.0's 16-bit
    scaler arguments (unit 36) already change the result, so no candidate isolates it.
    """
    plain = synth / "u37-plain.ttf"
    made = tries = 0
    while made < n and tries < 60 * n:
        tries += 1
        want = "in" if rng.random() < 0.7 else "no"
        site = (
            rng.choice(("slant-x", "slant-y", "bold-y", "bold-h", "bold-x", "bold-w"))
            if want == "in"
            else "none"
        )
        slant = (
            rng.choice((0.5, -0.5, 0.25, -0.25)) if site.startswith("slant") else 0.0
        )
        bold = rng.choice(
            ((0.5, 0.5), (0.25, 0.75), (1.0, 0.0), (0.0, 0.5), (0.0, 0.0))
        )
        if site == "bold-y" or site == "bold-h":
            bold = rng.choice(((0.5, 0.5), (0.0, 0.5), (0.25, 0.75)))
        if site == "bold-x" or site == "bold-w":
            bold = rng.choice(((0.5, 0.5), (1.0, 0.0), (0.25, 0.75)))
        if site == "none" and bold == (0.0, 0.0):
            bold = (0.5, 0.5)
        scale = rng.choice((1024, 1024, 2048, -1024))
        inplace = site == "bold-x" or (rng.random() < 0.4 and bold != (0.0, 0.0))
        xs, ys = round(abs(scale) * bold[0]), round(abs(scale) * bold[1])
        unit = 512 if slant else 1

        def near_limit(sign: int, margin: int, unit: int = unit) -> int:
            v = (
                (I32_MAX - rng.randint(0, margin))
                if sign > 0
                else (I32_MIN + rng.randint(0, margin))
            )
            return (v // unit) * unit if sign > 0 else -((-v) // unit) * unit

        def mid(unit: int = unit) -> int:
            return (
                (rng.randint(-(2**12), 2**12) // unit) * unit
                if unit > 1
                else rng.randint(-5000, 5000)
            )

        e = [mid(), mid(), abs(mid()), -abs(mid())]
        sign = rng.choice((1, -1))
        if site == "slant-x":
            half = (2**30 + rng.randint(0, 2**29)) // unit * unit
            e[0], e[2] = half, (2**31 - half + rng.randint(512, 2**28)) // unit * unit
        elif site == "slant-y":
            half = (2**30 + rng.randint(0, 2**29)) // unit * unit
            e[1] = sign * half
            e[3] = sign * ((2**31 - half + rng.randint(512, 2**28)) // unit * unit)
        elif site == "bold-y":
            e[1] = near_limit(1 if scale > 0 else -1, max(ys - 1, 0))
        elif site == "bold-h":
            e[3] = near_limit(-1 if scale > 0 else 1, max(ys - 1, 0))
        elif site == "bold-x":
            e[0] = near_limit(-1 if scale > 0 else 1, max(xs // 2 - 1, 0))
        elif site == "bold-w":
            e[2] = near_limit(1 if scale > 0 else -1, max(xs - 1, 0))
        else:
            # Large odd values that every release keeps exact: no slant, no overflow.
            for k in range(4):
                if rng.random() < 0.7:
                    e[k] = rng.choice((1, -1)) * (rng.randint(2**24, 2**31 - 2**13) | 1)
        old = syn_old(tuple(e), slant, xs, ys, scale, inplace)
        new = syn_new(tuple(e), slant, xs, ys, scale, inplace)
        if old is None:
            continue
        if want == "in" and old == new:
            continue
        if want == "no" and old != new:
            continue
        params = {
            "scale": scale if scale != 1024 else None,
            "slant": slant or None,
            "bold": f"{bold[0]},{bold[1]}" if bold != (0.0, 0.0) else None,
            "boldin": 1 if inplace and bold != (0.0, 0.0) else None,
        }
        made += 1
        yield api_case(
            "37",
            plain,
            "syn",
            [u32(v) for v in e],
            nb="in" if want == "in" else "b:no-overflow",
            **{k: v for k, v in params.items() if v is not None},
        )


def u37_font(out: Path) -> None:
    names = [".notdef", "space", "A"]
    glyphs = {
        ".notdef": rect(50, 0, 450, 700).glyph(),
        "space": empty_glyph(),
        "A": rect(100, 0, 600, 700).glyph(),
    }
    fb = ttf(
        "u37-plain",
        names,
        {0x20: "space", 0x41: "A"},
        glyphs,
        {".notdef": (500, 50), "space": (512, 0), "A": (700, 100)},
    )
    fb.save(str(out / "u37-plain.ttf"))


# --------------------------------------------------------------------------------------------------------------
# Unit 38: scaled extents round outward on both axes, after scaling
# --------------------------------------------------------------------------------------------------------------

U38_BOXES = {
    "A": (37, -113, 517, 701),
    "B": (-61, 3, 449, 655),
    "C": (13, -201, 397, 333),
    "D": (101, 99, 901, 777),
    "E": (-211, -37, 311, 517),
    "F": (5, 0, 1001, 23),
}


def u38_fonts(out: Path) -> None:
    """Static boxes with odd edges, a variable font whose deltas make quarter-unit outlines, and a CFF font with
    fractional outlines. Units per em 1024."""
    names = [".notdef", "space", *U38_BOXES]
    cmap = {0x20: "space", **{ord(c): c for c in U38_BOXES}}
    glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
    metrics = {".notdef": (500, 50), "space": (512, 0)}
    for c, (x0, y0, x1, y1) in U38_BOXES.items():
        glyphs[c] = rect(x0, y0, x1, y1).glyph()
        metrics[c] = (x1 + 50, x0)
    fb = ttf("u38-box", names, cmap, glyphs, metrics, asc=801, desc=-223)
    fb.save(str(out / "u38-box.ttf"))

    fb = ttf("u38-var", names, cmap, dict(glyphs), dict(metrics), asc=801, desc=-223)
    fb.setupFvar([("wght", 400, 400, 800, "Weight")], [])
    variations = {}
    for k, c in enumerate(U38_BOXES):
        # Odd deltas on every corner: a quarter of the axis range gives quarter-unit coordinates.
        d = [(3 + 2 * k, 5), (-7, 9 + 2 * k), (11, -13), (-(15 + 2 * k), 17)] + [
            (0, 0)
        ] * 4
        variations[c] = [TupleVariation({"wght": (0.0, 1.0, 1.0)}, d)]
    fb.setupGvar(variations)
    fb.save(str(out / "u38-var.ttf"))

    cff_names = [".notdef", "space", *U38_BOXES]
    fbc = FontBuilder(1024, isTTF=False)
    fbc.setupGlyphOrder(cff_names)
    fbc.setupCharacterMap(cmap)
    charstrings = {}
    advances = {".notdef": 500, "space": 512}
    fracs = (0.25, 0.75, 0.125, 0.375)
    for k, n in enumerate(cff_names):
        pen = T2CharStringPen(advances.get(n, 0), None)
        if n in U38_BOXES:
            x0, y0, x1, y1 = U38_BOXES[n]
            f = fracs[k % 4]
            x0, y0, x1, y1 = (
                x0 + f,
                y0 - f,
                x1 + fracs[(k + 1) % 4],
                y1 + fracs[(k + 2) % 4],
            )
            pen = T2CharStringPen(int(U38_BOXES[n][2]) + 50, None, roundTolerance=0)
            pen.moveTo((x0, y0))
            pen.lineTo((x0, y1))
            pen.lineTo((x1, y1))
            pen.lineTo((x1, y0))
            pen.closePath()
            advances[n] = U38_BOXES[n][2] + 50
        elif n == ".notdef":
            pen.moveTo((50, 0))
            pen.lineTo((50, 700))
            pen.lineTo((450, 700))
            pen.lineTo((450, 0))
            pen.closePath()
        charstrings[n] = pen.getCharString()
    fbc.setupCFF("u38-cff", {"FullName": "u38-cff"}, charstrings, {})
    fbc.setupHorizontalMetrics({n: (advances[n], 0) for n in cff_names})
    fbc.setupHorizontalHeader(ascent=801, descent=-223)
    fbc.setupNameTable({"familyName": "u38-cff", "styleName": "Regular"})
    fbc.setupOS2(
        sTypoAscender=801, sTypoDescender=-223, usWinAscent=801, usWinDescent=223
    )
    fbc.setupPost()
    fbc.save(str(out / "u38-cff.otf"))


def gen_38(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 38: scaled glyph extents round outward on both axes, after scaling.

    Inside (`ext` through the font's own functions): static glyf boxes at scales whose scaled edges are fractional
    (the vertical bearing, and both axes of reversed scales, rounded the wrong way before), and fractional outlines
    (quarter-unit variable instances, CFF) at any scale. Scales are multiples of 1/1024 of the em with few
    significant bits, so every product is exact. Boundaries: `b:integral` (scales that keep every edge whole) and
    `b:font-extents` (font ascender, descender and line gap at the same fractional scales, still rounded to nearest).
    Left out: extents under synthetic slant or emboldening and colour-glyph extents, which 15.2.0 still rounds to
    nearest through the drawn or painted outline, so the note's statement does not hold for them.
    """
    box, var, cff = synth / "u38-box.ttf", synth / "u38-var.ttf", synth / "u38-cff.otf"
    gids = list(range(2, 2 + len(U38_BOXES)))
    frac_scales = [1100, 1300, 1700, 900, 700, 1536, 1280, 2600, 3300, 520, 1170, 1940]
    for i in range(n):
        r = rng.random()
        g = rng.sample(gids, rng.randint(1, 3))
        if r < 0.35:
            # 15.1.0 already rounded outward on a reversed vertical axis and a forward horizontal one, so a case
            # needs a forward vertical axis (positive y scale) or a reversed horizontal one.
            sx = rng.choice(frac_scales) * rng.choice((1, 1, -1))
            sy = rng.choice(frac_scales) * (1 if sx > 0 else rng.choice((1, -1)))
            yield api_case("38", box, "ext", g, nb="in", scale=f"{sx},{sy}")
        elif r < 0.55:
            font, extra = (
                (var, {"var": f"wght={rng.choice((500, 700))}"})
                if rng.random() < 0.5
                else (cff, {})
            )
            s = rng.choice((1024, 1024, 2048, *frac_scales)) * rng.choice((1, 1, -1))
            if s != 1024:
                extra["scale"] = (
                    f"{s},{abs(s) if s > 0 else rng.choice((abs(s), -abs(s), 1024))}"
                )
            yield api_case("38", font, "ext", g, nb="in", **extra)
        elif r < 0.75:
            k = rng.choice((1, 2, 3, -1, -2))
            k2 = rng.choice((1, 2, -1, 3))
            yield api_case(
                "38", box, "ext", g, nb="b:integral", scale=f"{1024 * k},{1024 * k2}"
            )
        else:
            font = rng.choice((box, box, cff))
            sx = rng.choice(frac_scales)
            sy = rng.choice(frac_scales) * rng.choice((1, -1))
            yield api_case(
                "38", font, "fext", [], nb="b:font-extents", scale=f"{sx},{sy}"
            )


# --------------------------------------------------------------------------------------------------------------
# Unit 39: empty glyphs have zero extents
# --------------------------------------------------------------------------------------------------------------


def u39_fonts(out: Path) -> None:
    """Empty glyphs (space, a glyph with no data, a composite of an empty glyph), degenerate outlines (one point,
    zero-height and zero-width contours), boxes and a composite of boxes; glyf and CFF."""
    names = [
        ".notdef",
        "space",
        "nothing",
        "compempty",
        "dot1",
        "hline",
        "vline",
        "boxA",
        "boxB",
        "compbox",
    ]
    cmap = {
        0x20: "space",
        0xE000: "nothing",
        0xE001: "compempty",
        0xE002: "dot1",
        0xE003: "hline",
        0xE004: "vline",
        0x41: "boxA",
        0x42: "boxB",
        0xE005: "compbox",
    }
    pen = TTGlyphPen(None)
    pen.moveTo((300, 400))
    pen.closePath()
    dot1 = pen.glyph()
    pen = TTGlyphPen(None)
    pen.moveTo((100, 250))
    pen.lineTo((700, 250))
    pen.closePath()
    hline = pen.glyph()
    pen = TTGlyphPen(None)
    pen.moveTo((333, -100))
    pen.lineTo((333, 600))
    pen.closePath()
    vline = pen.glyph()
    glyphs = {
        ".notdef": rect(50, 0, 450, 700).glyph(),
        "space": empty_glyph(),
        "nothing": empty_glyph(),
        "dot1": dot1,
        "hline": hline,
        "vline": vline,
        "boxA": rect(64, -128, 576, 704).glyph(),
        "boxB": rect(-96, 32, 416, 512).glyph(),
    }
    c = Glyph()
    c.numberOfContours = -1
    comp = GlyphComponent()
    comp.glyphName, comp.x, comp.y, comp.flags = "nothing", 128, 64, 0
    c.components = [comp]
    glyphs["compempty"] = c
    c = Glyph()
    c.numberOfContours = -1
    comps = []
    for gname, x, y in (("boxA", 0, 0), ("boxB", 640, 256)):
        comp = GlyphComponent()
        comp.glyphName, comp.x, comp.y, comp.flags = gname, x, y, 0
        comps.append(comp)
    c.components = comps
    glyphs["compbox"] = c
    metrics = {n: (640, 0) for n in names}
    metrics.update(
        {
            ".notdef": (500, 50),
            "boxA": (640, 64),
            "boxB": (512, -96),
            "dot1": (600, 300),
            "hline": (800, 100),
            "vline": (666, 333),
            "compbox": (1100, 0),
        }
    )
    fb = ttf("u39-empty", names, cmap, glyphs, metrics)
    fb.save(str(out / "u39-empty.ttf"))

    fbc = FontBuilder(1024, isTTF=False)
    cnames = [".notdef", "space", "nothing", "boxA", "boxB", "hline"]
    fbc.setupGlyphOrder(cnames)
    fbc.setupCharacterMap(
        {0x20: "space", 0xE000: "nothing", 0x41: "boxA", 0x42: "boxB", 0xE003: "hline"}
    )
    cs = {}
    for nme in cnames:
        p = T2CharStringPen(640, None)
        if nme in ("boxA", "boxB", ".notdef"):
            x0, y0, x1, y1 = {
                "boxA": (64, -128, 576, 704),
                "boxB": (-96, 32, 416, 512),
                ".notdef": (50, 0, 450, 700),
            }[nme]
            p.moveTo((x0, y0))
            p.lineTo((x0, y1))
            p.lineTo((x1, y1))
            p.lineTo((x1, y0))
            p.closePath()
        elif nme == "hline":
            p.moveTo((100, 250))
            p.lineTo((700, 250))
            p.closePath()
        cs[nme] = p.getCharString()
    fbc.setupCFF("u39-cff", {"FullName": "u39-cff"}, cs, {})
    fbc.setupHorizontalMetrics({nme: (640, 0) for nme in cnames})
    fbc.setupHorizontalHeader(ascent=800, descent=-224)
    fbc.setupNameTable({"familyName": "u39-cff", "styleName": "Regular"})
    fbc.setupOS2(
        sTypoAscender=800, sTypoDescender=-224, usWinAscent=800, usWinDescent=224
    )
    fbc.setupPost()
    fbc.save(str(out / "u39-cff.otf"))


def gen_39(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 39: empty glyphs have zero extents.

    With synthetic slant or emboldening, HarfBuzz takes extents from the drawn outline; a glyph that draws nothing
    used to come out with a width of -1 and a height of 1. Inside: empty glyphs (space, a glyph with no data, a
    composite of an empty glyph; glyf and CFF) under slant, emboldening or both, any scale. Boundaries:
    `b:unsynthetic` (the same glyphs without synthetic settings, already zero) and `b:outline` (boxes and a composite
    of boxes under slant). Every `b:outline` edge stays whole: the box corners are multiples of 32, the slants
    multiples of 1/8 and the scales multiples of 1/2 of the em, so note 38's outward rounding, applied to slanted
    extents too, moves none of them. Left out: a glyph whose only contour is one point (it draws nothing, so 15.2.0
    zeroes it too, but whether such a glyph is empty is not something the note decides), and zero-height and
    zero-width outlines under slant (`x:degenerate`): a zero-height outline has zero area, which "empty" can be read
    to cover, and most of their slanted edges are fractional, where note 38's outward rounding, read as covering
    slanted extents, would move them. Emboldening is used on empty glyphs only, where it moves no point; slants are
    short binary fractions, so every drawn coordinate is exact.
    """
    ttf_, cff = synth / "u39-empty.ttf", synth / "u39-cff.otf"
    empty_t, empty_c = [1, 2, 3], [1, 2]
    for i in range(n):
        r = rng.random()
        scale = rng.choice((None, None, 2048, 1536, 512, -1024))
        params = {} if scale is None else {"scale": scale}
        if r < 0.45:
            font, gl = (ttf_, empty_t) if rng.random() < 0.7 else (cff, empty_c)
            kind = rng.choice(("slant", "bold", "both"))
            if kind in ("slant", "both"):
                params["slant"] = rng.choice((0.25, 0.5, -0.25, 0.125))
            if kind in ("bold", "both"):
                params["bold"] = rng.choice(
                    ("0.0625,0.0625", "0.125,0", "0,0.03125", "0.25,0.25")
                )
                if rng.random() < 0.3:
                    params["boldin"] = 1
            yield api_case(
                "39",
                font,
                "ext",
                rng.sample(gl, rng.randint(1, len(gl))),
                nb="in",
                **params,
            )
        elif r < 0.6:
            font, gl = (ttf_, empty_t) if rng.random() < 0.7 else (cff, empty_c)
            yield api_case(
                "39",
                font,
                "ext",
                rng.sample(gl, rng.randint(1, len(gl))),
                nb="b:unsynthetic",
                **params,
            )
        elif r < 0.8:
            font, gl = (ttf_, [7, 8, 9]) if rng.random() < 0.7 else (cff, [3, 4])
            params["slant"] = rng.choice((0.25, 0.5, -0.25, 0.125))
            yield api_case(
                "39",
                font,
                "ext",
                rng.sample(gl, rng.randint(1, len(gl))),
                nb="b:outline",
                **params,
            )
        else:
            font, gl = (ttf_, [5, 6]) if rng.random() < 0.8 else (cff, [5])
            params["slant"] = rng.choice((0.25, 0.5, -0.25, 0.125))
            yield api_case(
                "39",
                font,
                "ext",
                rng.sample(gl, rng.randint(1, len(gl))),
                nb="x:degenerate",
                **params,
            )


# --------------------------------------------------------------------------------------------------------------
# Unit 42: nested glyf components with anchor points
# --------------------------------------------------------------------------------------------------------------


def component(
    name: str, x: int = 0, y: int = 0, anchor: tuple[int, int] | None = None
) -> GlyphComponent:
    c = GlyphComponent()
    c.glyphName = name
    c.flags = 0
    if anchor:
        c.firstPt, c.secondPt = anchor
    else:
        c.x, c.y = x, y
    return c


def composite(*comps: GlyphComponent) -> Glyph:
    g = Glyph()
    g.numberOfContours = -1
    g.components = list(comps)
    return g


U42_GLYPHS = {
    # name: (code point, label)
    "O1": (0x41, "in"),
    "O2": (0x42, "in"),
    "O4": (0x43, "in"),
    "O5": (0x44, "in"),
    "F1": (0x45, "b:flat"),
    "F2": (0x46, "b:flat"),
    "N1": (0x47, "b:offsets"),
    "N2": (0x48, "b:offsets"),
    "OA": (0x49, "b:outer-anchor"),
}


def u42_font(out: Path) -> None:
    """Composites two and three levels deep whose inner composites place components by anchor points, and their
    neighbours. Variable (one axis, no deltas), so non-default coordinates take extents from the outline."""
    simple = {
        "bar": rect(0, 0, 600, 100),
        "dot": rect(0, 0, 100, 100),
        "ring": rect(0, 0, 200, 50),
        "tall": rect(0, 0, 80, 400),
    }
    glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
    glyphs.update({k: v.glyph() for k, v in simple.items()})
    # Inner composites: anchor point p1 of the composite so far, p2 of the component.
    glyphs["inA"] = composite(component("bar"), component("dot", anchor=(2, 0)))
    glyphs["inB"] = composite(
        component("ring", 50, 300), component("dot", anchor=(1, 3))
    )
    glyphs["inT"] = composite(
        component("tall", 20, 0),
        component("ring", anchor=(2, 0)),
        component("dot", anchor=(6, 1)),
    )
    glyphs["inC"] = composite(component("bar"), component("dot", 600, 100))
    # Outer composites.
    glyphs["O1"] = composite(component("dot", 0, 500), component("inA", 100, 0))
    glyphs["O2"] = composite(
        component("ring"), component("tall", 700, 0), component("inB", 300, 0)
    )
    glyphs["O4"] = composite(component("dot"), component("O1", 0, 1000))
    glyphs["O5"] = composite(component("bar", 0, 800), component("inT", 200, 0))
    glyphs["F1"] = composite(component("bar"), component("dot", anchor=(2, 0)))
    glyphs["F2"] = composite(
        component("ring", 50, 300),
        component("tall", 300, 0),
        component("dot", anchor=(5, 3)),
    )
    glyphs["N1"] = composite(component("dot", 0, 500), component("inC", 100, 0))
    glyphs["N2"] = composite(component("ring"), component("inC", 300, 200))
    glyphs["OA"] = composite(component("bar"), component("inC", anchor=(2, 0)))
    names = [".notdef", "space", *simple, "inA", "inB", "inT", "inC", *U42_GLYPHS]
    cmap = {0x20: "space", **{cp: name for name, (cp, _) in U42_GLYPHS.items()}}
    metrics = {nme: (1200, 0) for nme in names}
    metrics[".notdef"] = (500, 50)
    fb = ttf("u42-nest", names, cmap, glyphs, metrics)
    fb.setupFvar([("wght", 400, 400, 800, "Weight")], [])
    fb.setupGvar({})
    fb.save(str(out / "u42-nest.ttf"))


def gen_42(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 42: nested glyf components placed by anchor points.

    Inside: composites nested two or three levels deep whose inner composite places a component by anchor points
    and does not start the outer glyph (its anchor indices used to count from the start of the whole glyph).
    Observed through the drawn outline at whole scales, through extents at non-default variation coordinates, and
    through extents under a slant of a short binary fraction (both computed from the outline; every coordinate
    exact). Boundaries: `b:flat` (one level of anchor points), `b:offsets` (nested composites placed by offsets),
    `b:outer-anchor` (an outer anchor placing an inner composite that uses offsets). Extents at default coordinates
    without slant come from the stored bounding box and show nothing, so they are not generated.
    """
    font = synth / "u42-nest.ttf"
    order = [
        ".notdef",
        "space",
        "bar",
        "dot",
        "ring",
        "tall",
        "inA",
        "inB",
        "inT",
        "inC",
        *U42_GLYPHS,
    ]
    for i in range(n):
        name = rng.choice(list(U42_GLYPHS))
        nb = U42_GLYPHS[name][1]
        gid = order.index(name)
        r = rng.random()
        if r < 0.4:
            params = (
                {"scale": rng.choice((2048, 3072, -1024, 4096))}
                if rng.random() < 0.4
                else {}
            )
            yield api_case("42", font, "draw", [gid], nb=nb, **params)
        elif r < 0.7:
            params = {"var": f"wght={rng.choice((500, 600, 800))}"}
            if rng.random() < 0.4:
                # Whole multiples of the em only: a fractional scaled edge would also show unit 38's rounding.
                params["scale"] = rng.choice((2048, -1024, 3072))
            yield api_case("42", font, "ext", [gid], nb=nb, **params)
        else:
            yield api_case(
                "42", font, "ext", [gid], nb=nb, slant=rng.choice((0.25, 0.5, -0.5))
            )


# --------------------------------------------------------------------------------------------------------------
# Unit 43: zero positions for items added after the first call to hb_buffer_get_glyph_positions
# --------------------------------------------------------------------------------------------------------------


def u43_font(out: Path) -> None:
    names = [".notdef", "space", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    cmap = {0x20: "space", **{ord(c): c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}}
    glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
    metrics = {".notdef": (500, 50), "space": (256, 0)}
    for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        glyphs[c] = rect(40, 0, 500 + 7 * i, 700).glyph()
        metrics[c] = (540 + 7 * i + 3 * (i % 5), 40)
    fb = ttf("u43-plain", names, cmap, glyphs, metrics)
    fb.save(str(out / "u43-plain.ttf"))


def gen_43(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 43: items added after the first hb_buffer_get_glyph_positions() call get zero positions.

    Determinism: the buffer first holds an earlier text, shaped (its positions are the font's advances) and then
    removed with hb_buffer_clear_contents() or hb_buffer_reset(); the current text is added and read; then more items
    are added with one of the adding functions. The earlier text is at least as long as everything added later, and
    the buffer never grows after it, so the memory read for the new items is the earlier text's positions, the same
    on every run (never uninitialized). The probe prints only the new items' positions. Boundaries: `b:old` (the same
    flow, printing the items that were there at the first call: zero, or shaped positions when the current text was
    shaped first) and `b:before-call` (every item added before the first call). The font and text are plain Latin
    boxes without layout tables, so the earlier positions are the same in every release.
    """
    font = synth / "u43-plain.ttf"
    letters = [ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    for i in range(n):
        a = rng.randint(0, 5)
        b = rng.randint(1, 6)
        pre = a + b + rng.randint(0, 6)
        text = [rng.choice(letters) for _ in range(pre + a + b)]
        params = {
            "pre": pre,
            "a": a,
            "clr": rng.choice(("clear", "reset")),
            "how": rng.choice(("add", "cps", "utf8", "utf16", "utf32", "latin1")),
        }
        if rng.random() < 0.5:
            params["shp"] = 1
        r = rng.random()
        if r < 0.6:
            yield api_case("43", font, "pos", text, nb="in", show="new", **params)
        elif r < 0.85:
            if a == 0:
                continue
            params["shp"] = 1
            yield api_case("43", font, "pos", text, nb="b:old", show="old", **params)
        else:
            params["a"] = a + b
            yield api_case(
                "43", font, "pos", text, nb="b:before-call", show="all", **params
            )


# --------------------------------------------------------------------------------------------------------------
# Unit 50: CBDT format 19
# --------------------------------------------------------------------------------------------------------------

U50_GLYPHS = ["g17a", "g17b", "g18a", "g18b", "g19a", "g19b", "g19c", "g19d", "g19e"]


def u50_fonts(out: Path) -> None:
    """Colour bitmaps: image format 17 (index format 1), 18 (index format 3) and 19 (index formats 2 and 5), in a
    font whose glyf glyphs are empty, and in one whose glyf glyphs are boxes."""
    from fontTools.ttLib.tables import C_B_D_T_, E_B_L_C_, BitmapGlyphMetrics

    for variant in ("empty", "box"):
        names = [".notdef", "space", *U50_GLYPHS]
        cmap = {0x20: "space", **{0xE100 + k: g for k, g in enumerate(U50_GLYPHS)}}
        glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
        for k, g in enumerate(U50_GLYPHS):
            glyphs[g] = (
                rect(64 + 8 * k, -64, 900, 832).glyph()
                if variant == "box"
                else empty_glyph()
            )
        metrics = {nme: (1024, 0) for nme in names}
        metrics[".notdef"] = (500, 50)
        fb = ttf(f"u50-cbdt-{variant}", names, cmap, glyphs, metrics)
        font = fb.font
        order = font.getGlyphOrder()

        def small(w, h, bx, by, adv):
            m = BitmapGlyphMetrics.SmallGlyphMetrics()
            m.width, m.height, m.BearingX, m.BearingY, m.Advance = w, h, bx, by, adv
            return m

        def big(w, h, bx, by, adv):
            m = BitmapGlyphMetrics.BigGlyphMetrics()
            m.width, m.height = w, h
            m.horiBearingX, m.horiBearingY, m.horiAdvance = bx, by, adv
            m.vertBearingX, m.vertBearingY, m.vertAdvance = -(w // 2), 4, h + 8
            return m

        strike_glyphs = {}
        for k, g in enumerate(("g17a", "g17b")):
            bm = C_B_D_T_.cbdt_bitmap_format_17(None, font)
            bm.metrics = small(20 + 4 * k, 24, 2 + k, 22 - k, 28)
            bm.imageData = png(20 + 4 * k, 24, k)
            strike_glyphs[g] = bm
        for k, g in enumerate(("g18a", "g18b")):
            bm = C_B_D_T_.cbdt_bitmap_format_18(None, font)
            bm.metrics = big(26 - 2 * k, 30, -1 + k, 26, 30)
            bm.imageData = png(26 - 2 * k, 30, 10 + k)
            strike_glyphs[g] = bm
        same_png = png(18, 21, 40)
        for g in ("g19a", "g19b", "g19c", "g19d", "g19e"):
            bm = C_B_D_T_.cbdt_bitmap_format_19(None, font)
            bm.imageData = same_png
            strike_glyphs[g] = bm
        cbdt = newTable("CBDT")
        cbdt.version = 3.0
        cbdt.strikeData = [strike_glyphs]
        font["CBDT"] = cbdt

        def index(fmt, img_fmt, glyph_names, metrics=None, size=None, font=font):
            cls = getattr(E_B_L_C_, f"eblc_index_sub_table_{fmt}")
            t = cls(None, font)
            t.indexFormat, t.imageFormat = fmt, img_fmt
            t.names = list(glyph_names)
            if metrics is not None:
                t.metrics = metrics
                t.imageSize = size
            return t

        ist = [
            index(1, 17, ["g17a", "g17b"]),
            index(3, 18, ["g18a", "g18b"]),
            index(
                2,
                19,
                ["g19a", "g19b", "g19c"],
                big(18, 21, 3, 19, 24),
                len(same_png) + 4,
            ),
            index(5, 19, ["g19d", "g19e"], big(18, 21, -2, 25, 22), len(same_png) + 4),
        ]
        strike = E_B_L_C_.Strike()
        bst = E_B_L_C_.BitmapSizeTable()
        line = E_B_L_C_.SbitLineMetrics()
        for attr, v in (
            ("ascender", 26),
            ("descender", -6),
            ("widthMax", 30),
            ("caretSlopeNumerator", 0),
            ("caretSlopeDenominator", 0),
            ("caretOffset", 0),
            ("minOriginSB", 0),
            ("minAdvanceSB", 0),
            ("maxBeforeBL", 26),
            ("minAfterBL", -6),
            ("pad1", 0),
            ("pad2", 0),
        ):
            setattr(line, attr, v)
        bst.hori, bst.vert = line, line
        bst.colorRef, bst.ppemX, bst.ppemY, bst.bitDepth, bst.flags = 0, 32, 32, 32, 1
        bst.startGlyphIndex = min(order.index(g) for g in U50_GLYPHS)
        bst.endGlyphIndex = max(order.index(g) for g in U50_GLYPHS)
        strike.bitmapSizeTable = bst
        strike.indexSubTables = ist
        cblc = newTable("CBLC")
        cblc.version = 3.0
        cblc.strikes = [strike]
        font["CBLC"] = cblc
        fb.save(str(out / f"u50-cbdt-{variant}.ttf"))


def gen_50(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 50: bitmap glyphs in CBDT image format 19 (metrics in CBLC index formats 2 and 5).

    Inside: format 19 glyphs, their extents at various scales and pixel sizes and their PNG data. Boundaries:
    `b:format17` and `b:format18` (glyphs in the formats supported before, through index formats 1 and 3). Left
    out: format 17 and 18 images reached through index formats 2 and 5, which 15.2.0 also starts to read although
    the note names only format 19.
    """
    fonts = [synth / "u50-cbdt-empty.ttf", synth / "u50-cbdt-box.ttf"]
    gid = {g: 2 + k for k, g in enumerate(U50_GLYPHS)}
    groups = {
        "in": [g for g in U50_GLYPHS if g.startswith("g19")],
        "b:format17": ["g17a", "g17b"],
        "b:format18": ["g18a", "g18b"],
    }
    for i in range(n):
        nb = rng.choice(("in", "in", "in", "b:format17", "b:format18"))
        gl = [
            gid[g]
            for g in rng.sample(groups[nb], rng.randint(1, min(3, len(groups[nb]))))
        ]
        font = rng.choice(fonts)
        params = {}
        if rng.random() < 0.5:
            params["scale"] = rng.choice((2048, 4096, 3072))
        if rng.random() < 0.3:
            params["ppem"] = rng.choice((16, 32, 64))
        cmd = "png" if rng.random() < 0.25 else "ext"
        yield api_case("50", font, cmd, gl, nb=nb, **params)


# --------------------------------------------------------------------------------------------------------------
# Unit 19: COLR glyph extents and mark positioning with empty layers
# --------------------------------------------------------------------------------------------------------------

U19_BASES = {
    # name: (code point, COLR version, layers, label); "nil" is a glyph with no outline.
    "A": (0x41, 0, ["L1", "nil"], "in"),
    "B": (0x42, 0, ["nil", "L2", "L3"], "in"),
    "C": (0x43, 0, ["L1", "L3"], "b:no-empty-layer"),
    "D": (0x44, 1, ["L2", "nil"], "in"),
    "E": (0x45, 1, ["nil", "L1"], "in"),
    "F": (0x46, 1, ["L2", "L3"], "b:no-empty-layer"),
    "G": (0x47, 1, ["L1", "nil"], "b:clipbox"),
    "P": (0x50, None, None, "b:plain"),
}


def u19_fonts(out: Path) -> None:
    """Colour glyphs whose layers include a glyph with no outline (COLRv0 layers, COLRv1 PaintGlyph), neighbours
    without such a layer, one with a ClipBox, a plain glyph, and combining marks; no GPOS, so marks are placed from
    glyph extents."""
    from fontTools.colorLib.builder import buildCOLR, buildCPAL

    layers = {
        "L1": rect(128, 96, 512, 704),
        "L2": rect(224, 320, 416, 896),
        "L3": rect(160, 128, 448, 288),
    }
    marks = {
        "acutecomb": (0x301, rect(-260, 760, -60, 960)),
        "gravecomb": (0x300, rect(-240, 740, -40, 900)),
        "dotbelowcomb": (0x323, rect(-180, 40, -80, 140)),
        "cedillacomb": (0x327, rect(-200, 60, -40, 200)),
        "ringbelowcomb": (0x325, rect(-220, 20, -80, 160)),
        "macronbelowcomb": (0x331, rect(-300, 90, -20, 150)),
        "ringcomb": (0x30A, rect(-220, 780, -80, 920)),
    }
    names = [".notdef", "space", *U19_BASES, *layers, "nil", *marks]
    cmap = {0x20: "space", **{cp: nme for nme, (cp, *_r) in U19_BASES.items()}}
    cmap.update({cp: nme for nme, (cp, _) in marks.items()})
    glyphs = {
        ".notdef": rect(50, 0, 450, 700).glyph(),
        "space": empty_glyph(),
        "nil": empty_glyph(),
    }
    for nme, (_cp, ver, _lay, _lab) in U19_BASES.items():
        glyphs[nme] = (
            rect(150, 100, 500, 650).glyph()
            if ver is None
            else rect(0, 0, 1, 1).glyph()
        )
    for nme, pen in layers.items():
        glyphs[nme] = pen.glyph()
    for nme, (_cp, pen) in marks.items():
        glyphs[nme] = pen.glyph()
    metrics = {nme: (640, 0) for nme in names}
    metrics.update({nme: (0, 0) for nme in marks})
    metrics[".notdef"] = (500, 50)
    for nme in U19_BASES:
        metrics[nme] = (704, 0)
    fb = ttf("u19-colr", names, cmap, glyphs, metrics)
    v0 = {}
    v1 = {}
    clips = {}
    for nme, (_cp, ver, lay, label) in U19_BASES.items():
        if ver == 0:
            v0[nme] = [(layer, k % 2) for k, layer in enumerate(lay)]
        elif ver == 1:
            v1[nme] = {
                "Format": 1,  # PaintColrLayers
                "Layers": [
                    {
                        "Format": 10,
                        "Paint": {"Format": 2, "PaletteIndex": k % 2, "Alpha": 1.0},
                        "Glyph": layer,
                    }
                    for k, layer in enumerate(lay)
                ],
            }
            if label == "b:clipbox":
                clips[nme] = (96, 64, 544, 736)
    glyph_map = {nme: k for k, nme in enumerate(names)}
    colr = buildCOLR({**v0, **v1}, glyphMap=glyph_map, clipBoxes=clips or None)
    fb.font["COLR"] = colr
    fb.font["CPAL"] = buildCPAL([[(0.8, 0.1, 0.1, 1.0), (0.1, 0.1, 0.8, 1.0)]])
    fb.save(str(out / "u19-colr.ttf"))


def gen_19(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 19: COLR glyph extents and mark positioning with empty layers.

    A layer that draws nothing used to add a box from the origin to (-1,-1), scaled, to the colour glyph's ink
    bounds. Inside: COLRv0 and COLRv1 glyphs with such a layer and other layers away from the origin: their extents,
    and combining marks placed on them by fallback positioning (the font has no GPOS). Boundaries:
    `b:no-empty-layer` (colour glyphs without an empty layer), `b:clipbox` (a COLRv1 glyph with an empty layer whose
    extents come from its ClipBox), `b:plain` (an outline glyph). Left out: colour glyphs whose layers are all
    empty (15.2.0 changes their extents again, unit 39) and vertical text (its origins also follow the extents, which
    the note does not name).
    """
    font = synth / "u19-colr.ttf"
    order_bases = list(U19_BASES)
    gid = {nme: 2 + k for k, nme in enumerate(order_bases)}
    below, above = [0x323, 0x327, 0x325, 0x331], [0x301, 0x300, 0x30A]
    for i in range(n):
        nme = rng.choice(order_bases)
        label = U19_BASES[nme][3]
        params = {}
        if rng.random() < 0.4:
            params["scale"] = rng.choice((2048, 3072, 512, 1536))
        if rng.random() < 0.5:
            yield api_case("19", font, "ext", [gid[nme]], nb=label, **params)
        else:
            # The empty layer's box reaches down to the origin, so marks below the base show it; marks above
            # cannot (the box never reaches the top of the ink), and come only after a mark below.
            text = [U19_BASES[nme][0], *rng.sample(below, rng.randint(1, 2))]
            if rng.random() < 0.4:
                text.append(rng.choice(above))
            if rng.random() < 0.3:
                text = (
                    [rng.choice((0x41, 0x50)), *text]
                    if rng.random() < 0.5
                    else [*text, 0x20]
                )
            yield case(
                "19", "cand", font, text, nb=label, cl=rng.choice((0, 1)), **params
            )


# --------------------------------------------------------------------------------------------------------------
# Unit 33: Unicode 18.0 data
# --------------------------------------------------------------------------------------------------------------

U33_CHANGED_OLD = [
    0x221D
]  # assigned before 18.0; its mirroring partner is new (U+1DB10)
# Scripts (Scripts.txt names) whose new characters are shaped: no Indic, Khmer, Myanmar or USE script.
U33_SHAPED_SCRIPTS = {
    "Inherited",
    "Common",
    "Arabic",
    "Hebrew",
    "Latin",
    "Greek",
    "Armenian",
}


def ucd18() -> tuple[
    dict[int, tuple[str, str, int]], dict[int, float], list[tuple[int, int, str]]
]:
    """Unicode 18 data: code point -> (category, bidi class, combining class); age; blocks."""
    props: dict[int, tuple[str, str, int]] = {}
    age: dict[int, float] = {}
    blocks: list[tuple[int, int, str]] = []
    with zipfile.ZipFile(UCD) as z:
        names = set(z.namelist())
        first = None
        for line in z.read("UnicodeData.txt").decode().splitlines():
            f = line.split(";")
            cp = int(f[0], 16)
            if f[1].endswith(", First>"):
                first = cp
                continue
            rng_ = (
                range(first, cp + 1)
                if f[1].endswith(", Last>") and first is not None
                else (cp,)
            )
            for c in rng_:
                props[c] = (f[2], f[4], int(f[3]))
            first = None
        for line in z.read("DerivedAge.txt").decode().splitlines():
            body = line.split("#", 1)[0].strip()
            if not body:
                continue
            cps, ver = (s.strip() for s in body.split(";"))
            lo, _, hi = cps.partition("..")
            for c in range(int(lo, 16), int(hi or lo, 16) + 1):
                age[c] = float(ver)
        if "Blocks.txt" in names:
            for line in z.read("Blocks.txt").decode().splitlines():
                body = line.split("#", 1)[0].strip()
                if not body:
                    continue
                cps, nme = (s.strip() for s in body.split(";"))
                lo, _, hi = cps.partition("..")
                blocks.append((int(lo, 16), int(hi, 16), nme))
    return props, age, blocks


def scripts18() -> dict[int, str]:
    out: dict[int, str] = {}
    with zipfile.ZipFile(UCD) as z:
        for line in z.read("Scripts.txt").decode().splitlines():
            body = line.split("#", 1)[0].strip()
            if not body:
                continue
            cps, sc = (s.strip() for s in body.split(";"))
            lo, _, hi = cps.partition("..")
            for c in range(int(lo, 16), int(hi or lo, 16) + 1):
                out[c] = sc
    return out


def u33_sets() -> dict[str, list[int]]:
    props, age, blocks = ucd18()
    sc = scripts18()
    new = sorted(c for c, a in age.items() if a == 18.0 and c < 0xF0000)
    new_set = set(new)
    old_near: set[int] = set()
    for c in new:
        for d in (-3, -2, -1, 1, 2, 3):
            o = c + d
            if (
                o in age
                and age[o] < 18.0
                and props.get(o, ("Cn",))[0] not in ("Cs", "Co")
            ):
                old_near.add(o)
    new_blocks = [
        (lo, hi)
        for lo, hi, _n in blocks
        if all(age.get(c, 18.0) >= 18.0 for c in range(lo, hi + 1))
    ]
    reserved_new = sorted(
        c for lo, hi in new_blocks for c in range(lo, hi + 1) if c not in age
    )
    unassigned_near = sorted(
        {
            c + d
            for c in new
            for d in range(-8, 9)
            if (c + d) not in age and 0 <= c + d < 0xF0000
        }
        - set(reserved_new)
    )
    marks = [
        c
        for c in new
        if props[c][0] in ("Mn", "Mc") and sc.get(c, "") in U33_SHAPED_SCRIPTS
    ]
    rtl = [
        c
        for c in new
        if props[c][1] in ("R", "AL")
        and props[c][0].startswith("L")
        and sc.get(c, "") in U33_SHAPED_SCRIPTS
    ]
    letters = [c for c in new if props[c][0].startswith("L")]
    old_marks = [c for c in range(0x300, 0x370)] + [
        c for c in range(0x1AB0, 0x1ADE) if age.get(c, 99) < 18.0
    ]
    old_rtl = [c for c in range(0x5D0, 0x5EB)] + [c for c in range(0x628, 0x64B)]
    return {
        "new": new,
        "old": sorted(old_near - new_set),
        "reserved_new": reserved_new,
        "unassigned": unassigned_near,
        "marks": marks,
        "rtl": rtl,
        "letters": letters,
        "old_marks": old_marks,
        "old_rtl": old_rtl,
    }


def u33_font(out: Path) -> None:
    """Glyphs for a sample of characters new in Unicode 18 (marks, right-to-left letters, letters), the mirroring
    pair U+221D/U+1DB10, and old neighbours; boxes of distinct widths, no layout tables."""
    sets = u33_sets()
    rng = random.Random("u33-font")
    chars = sorted(
        set(sets["marks"])
        | set(rng.sample(sets["rtl"], min(40, len(sets["rtl"]))))
        | set(rng.sample(sets["letters"], min(60, len(sets["letters"]))))
        | set(sets["old_marks"])
        | set(sets["old_rtl"])
        | {0x221D, 0x1DB10, 0x41, 0x42, 0x43, 0x61, 0x62}
        | set(range(0x28, 0x2A))
        | {0x5B, 0x5D, 0x3C, 0x3E}
    )
    names = [".notdef", "space"] + [f"u{c:04X}" for c in chars]
    cmap = {0x20: "space", **{c: f"u{c:04X}" for c in chars}}
    glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
    metrics = {".notdef": (500, 50), "space": (256, 0)}
    for k, c in enumerate(chars):
        w = 300 + (k * 37) % 500
        glyphs[f"u{c:04X}"] = rect(30, 0, w, 600 + (k % 7) * 20).glyph()
        metrics[f"u{c:04X}"] = (w + 30, 30)
    fb = ttf("u33-new", names, cmap, glyphs, metrics)
    fb.save(str(out / "u33-new.ttf"))


# The three script values of Unicode 18.0, and code points of each (Scripts.txt 18.0: Jurchen U+18E00..U+19191 and
# U+191A0..U+191D2, Proto_Cuneiform U+125A8..U+1264B, Seal U+3D000..U+3FC3F). The Cuneiform numerals around the
# Proto-Cuneiform range (U+12550..U+125A7 and U+1264C..U+12686) are new in 18.0 too, but of the old Cuneiform script.
U33_NEW_SCRIPTS = {"Jurc": 0x18E00, "Pcun": 0x125A8, "Seal": 0x3D000}
U33_PCUN = range(0x125A8, 0x1264C)
U33_XSUX_NEW = [*range(0x12550, 0x125A8), *range(0x1264C, 0x12687)]
U33_PCUN_UNASSIGNED = range(
    0x12544, 0x12550
)  # unassigned, before the block (Early Dynastic Cuneiform)
U33_PCUN_RESERVED = range(
    0x12687, 0x12690
)  # unassigned, inside the new Archaic Cuneiform Numerals block
# Shaping with the new script values: a few characters of each, and of old scripts the default shaper keeps
# (Cuneiform, including its numerals new in 18.0, and Tangut); `pres` substitutes every one of them, and only the
# Universal Shaping Engine applies `pres`.
U33_USE_TEXT = {
    "Jurc": list(range(0x18E00, 0x18E08)),
    "Pcun": list(range(0x125A8, 0x125B0)),
    "Seal": list(range(0x3D000, 0x3D008)),
}
U33_USE_OLD = {
    "Xsux": [*range(0x12000, 0x12008), *range(0x12550, 0x12558)],
    "Tang": list(range(0x17000, 0x17008)),
}
# Script names for the constants probe (hbapi33): the three new ones in any case, old ones, and look-alikes.
U33_NAMES = ["Jurc", "jurc", "JURC", "Pcun", "pcun", "PCUN", "Seal", "seal", "SEAL"]
U33_OTHER_NAMES = [
    "Xsux",
    "Hani",
    "Kits",
    "Tang",
    "Latn",
    "Nshu",
    "Zzzz",
    "Jurx",
    "Pcuu",
    "Seel",
    "Seil",
]
# Scripts for the dominant baseline: the two new ideographic ones, and old ones of every kind (ideographic,
# hanging, roman), with Proto-Cuneiform, which is not ideographic.
U33_IDEO_NEW = ["Jurc", "jurc", "JURC", "Seal", "seal", "SEAL"]
U33_BASE_OTHER = [
    "Pcun",
    "pcun",
    "Hani",
    "Hang",
    "Kana",
    "Tang",
    "Nshu",
    "Kits",
    "Latn",
    "Deva",
    "Xsux",
    "Arab",
]


def u33_use_fonts(out: Path) -> None:
    """For the routing of the new scripts: u33-use, whose `GSUB` has `pres` under DFLT and under the OpenType tags
    of the three new scripts and of Cuneiform and Tangut (each character goes to a glyph of its own), and
    u33-use-dflt, the same with `pres` under DFLT only: HarfBuzz keeps the default shaper for a font designed for
    DFLT. Boxes of distinct widths; the substitutes are narrower."""
    chars = sorted(
        {c for cps in (*U33_USE_TEXT.values(), *U33_USE_OLD.values()) for c in cps}
    )
    for name, systems in (
        ("u33-use", ["DFLT", "jurc", "pcun", "seal", "xsux", "tang"]),
        ("u33-use-dflt", ["DFLT"]),
    ):
        order = [".notdef", "space"]
        order += [g for c in chars for g in (f"u{c:04X}", f"u{c:04X}.alt")]
        cmap = {0x20: "space", **{c: f"u{c:04X}" for c in chars}}
        glyphs = {".notdef": rect(50, 0, 450, 700).glyph(), "space": empty_glyph()}
        metrics = {".notdef": (500, 50), "space": (256, 0)}
        for k, c in enumerate(chars):
            w = 400 + (k * 29) % 400
            glyphs[f"u{c:04X}"] = rect(30, 0, w, 700).glyph()
            metrics[f"u{c:04X}"] = (w + 30, 30)
            glyphs[f"u{c:04X}.alt"] = rect(30, 0, w - 100, 600).glyph()
            metrics[f"u{c:04X}.alt"] = (w - 70, 30)
        fb = ttf(name, order, cmap, glyphs, metrics)
        fea = "".join(f"languagesystem {s} dflt;\n" for s in systems)
        fea += "feature pres {\n"
        fea += "".join(f"  sub u{c:04X} by u{c:04X}.alt;\n" for c in chars)
        fea += "} pres;\n"
        addOpenTypeFeaturesFromString(fb.font, fea)
        fb.save(str(out / f"{name}.ttf"))


def _name_int(name: str) -> int:
    """A script name's first four characters as HB_TAG packs them (spaces after a shorter one)."""
    return tag_int(name[:4])


def gen_33(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 33: Unicode 18.0 data and script values, and the shaping support of the three new scripts (attributed
    through fwd-33: the base with its Unicode tables regenerated from the Unicode 18 files and the code half of
    bf93d8671 added).

    Inside: `ucd` on code points new in 18.0 and on U+221D (its mirroring partner is new) (`in:ucd`); shaping of
    text with new combining marks after a base (category, combining class, cluster and mark advance, `in:marks`),
    new right-to-left letters (guessed direction, `in:rtl`), and U+221D in right-to-left text with a font that has
    U+1DB10 (`in:mirror`). Boundaries: `b:old` (code points assigned before 18.0 next to new ones; shaping with old
    marks and old right-to-left letters), `b:unassigned` (still unassigned next to new ones),
    `b:reserved-in-new-block` (unassigned code points inside blocks new in 18.0). New characters of the Indic and
    USE scripts are left out of shaping (unit 34 changes their shaping in 15.1.0), and so are variation selectors
    (unit 15).

    After the main loop (so its candidates are as before):
    - `in:ucd-pcun`: `ucd` on Proto-Cuneiform code points, often with the new Cuneiform numerals around them
      (U+125A7, U+1264C and the rest: new in 18.0 too, of the Cuneiform script); the unassigned code points before
      the block and the reserved ones at its end join `b:unassigned` and `b:reserved-in-new-block`.
    - `in:consts` (probe hbapi33, drv "api33"): the constants HB_SCRIPT_JURCHEN, HB_SCRIPT_PROTO_CUNEIFORM and
      HB_SCRIPT_SEAL against hb_script_from_string() of script names. A tree without the constants cannot compile
      the probe and fails these cases only.
    - `in:use`: text in one of the three scripts (script set, or guessed from the text) in u33-use, which has `pres`
      under their tags: they now go through the Universal Shaping Engine, which applies `pres`. Neighbours:
      `b:use-dflt-font`, the same in u33-use-dflt (a font designed for DFLT keeps the default shaper);
      `b:use-old-script`, Cuneiform (its old signs and its numerals new in 18.0) and Tangut in u33-use, which keep
      the default shaper.
    - `in:baseline` (hbmeta `scriptbase`): the dominant horizontal baseline of lists of scripts holding Jurchen or
      Seal, now ideographic (`icfb`). Neighbour `b:baseline-other`: lists of Proto-Cuneiform and old scripts only.
    """
    sets = u33_sets()
    font = synth / "u33-new.ttf"
    have = Font(font).cmap
    marks = [c for c in sets["marks"] if c in have]
    rtl = [c for c in sets["rtl"] if c in have]
    old_marks = [c for c in sets["old_marks"] if c in have]
    old_rtl = [c for c in sets["old_rtl"] if c in have]
    bases = [0x41, 0x42, 0x43, 0x61, 0x62]
    for i in range(n):
        r = rng.random()
        if r < 0.3:
            cps = rng.sample(sets["new"], rng.randint(1, 6))
            if rng.random() < 0.1:
                cps.append(0x221D)
            yield api_case("33", font, "ucd", cps, nb="in:ucd")
        elif r < 0.45:
            pool, nb = rng.choice(
                (
                    (sets["old"], "b:old"),
                    (sets["unassigned"], "b:unassigned"),
                    (sets["reserved_new"], "b:reserved-in-new-block"),
                )
            )
            if not pool:
                continue
            yield api_case(
                "33",
                font,
                "ucd",
                rng.sample(pool, min(len(pool), rng.randint(1, 6))),
                nb=nb,
            )
        elif r < 0.65 and marks:
            text = [rng.choice(bases)] + rng.sample(
                marks, min(len(marks), rng.randint(1, 3))
            )
            if rng.random() < 0.4:
                text.insert(2, rng.choice(old_marks))
            yield case(
                "33", "cand", font, text, nb="in:marks", cl=rng.choice((0, 1, 2))
            )
        elif r < 0.75 and rtl:
            text = rng.sample(rtl, min(len(rtl), rng.randint(2, 5)))
            if rng.random() < 0.3:
                text.append(rng.choice((0x28, 0x29, 0x5B)))
            yield case("33", "cand", font, text, nb="in:rtl", cl=rng.choice((0, 1)))
        elif r < 0.82:
            text = [rng.choice(old_rtl), 0x221D, rng.choice(old_rtl)]
            yield case("33", "cand", font, text, nb="in:mirror", dir="rtl")
        else:
            if rng.random() < 0.5:
                text = [rng.choice(bases)] + rng.sample(old_marks, rng.randint(1, 3))
            else:
                text = rng.sample(old_rtl, rng.randint(2, 5))
            yield case("33", "cand", font, text, nb="b:old", cl=rng.choice((0, 1)))
    # Proto-Cuneiform in `ucd`, and the unassigned code points around its block.
    for _ in range(80):
        cps = rng.sample(U33_PCUN, rng.randint(1, 6))
        if rng.random() < 0.4:
            cps.insert(
                rng.randrange(len(cps) + 1),
                rng.choice((0x125A7, 0x1264C) if rng.random() < 0.6 else U33_XSUX_NEW),
            )
        yield api_case("33", font, "ucd", cps, nb="in:ucd-pcun")
    for pool, nb in (
        (U33_PCUN_UNASSIGNED, "b:unassigned"),
        (U33_PCUN_RESERVED, "b:reserved-in-new-block"),
    ):
        for _ in range(20):
            yield api_case(
                "33", font, "ucd", rng.sample(pool, rng.randint(1, 4)), nb=nb
            )
    # The constants.
    for _ in range(60):
        names = [rng.choice(U33_NAMES)] + [
            rng.choice(U33_NAMES + U33_OTHER_NAMES) for _ in range(rng.randrange(0, 4))
        ]
        rng.shuffle(names)
        yield api_case(
            "33",
            font,
            "scripts",
            [_name_int(s) for s in names],
            nb="in:consts",
            drv="api33",
        )
    # Routing through the Universal Shaping Engine.
    use, dflt = synth / "u33-use.ttf", synth / "u33-use-dflt.ttf"
    for kind in (
        ("in:use",) * 80 + ("b:use-dflt-font",) * 40 + ("b:use-old-script",) * 40
    ):
        texts = U33_USE_OLD if kind == "b:use-old-script" else U33_USE_TEXT
        script = rng.choice(sorted(texts))
        text = [rng.choice(texts[script]) for _ in range(rng.randint(1, 4))]
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        # The script is guessed from the text in a third of the cases (only for text the old data can guess too,
        # among the neighbours: the Cuneiform numerals are new in 18.0).
        guessed = rng.random() < 0.33 and not (
            kind == "b:use-old-script" and any(c in U33_XSUX_NEW for c in text)
        )
        if not guessed:
            opts["script"] = script
        yield case(
            "33",
            "cand",
            dflt if kind == "b:use-dflt-font" else use,
            text,
            nb=kind,
            **opts,
        )
    # The dominant baseline.
    for kind in ("in:baseline",) * 80 + ("b:baseline-other",) * 40:
        names = [rng.choice(U33_BASE_OTHER) for _ in range(rng.randrange(0, 4))]
        if kind == "in:baseline":
            names.insert(rng.randrange(len(names) + 1), rng.choice(U33_IDEO_NEW))
        elif not names:
            names = [rng.choice(U33_BASE_OTHER)]
        yield api_case(
            "33", font, "scriptbase", [_name_int(s) for s in names], nb=kind, drv="meta"
        )


# --------------------------------------------------------------------------------------------------------------
# Unit 35: fonupa maps to UPPH
# --------------------------------------------------------------------------------------------------------------

U35_LANGS = [
    "und",
    "fi",
    "et",
    "hu",
    "sme",
    "smn",
    "kv",
    "udm",
    "myv",
    "mdf",
    "mhr",
    "krl",
    "vep",
    "ru",
    "en",
    "se",
    "fit",
    "vro",
    "liv",
    "sms",
]
U35_SCRIPTS = ["Latn", "Cyrl", None]


def lang_bytes(s: str) -> list[int]:
    return [ord(c) for c in s]


def tag_int(t: str) -> int:
    t = (t + "    ")[:4]
    return (ord(t[0]) << 24) | (ord(t[1]) << 16) | (ord(t[2]) << 8) | ord(t[3])


def gen_35(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 35: the BCP 47 variant `fonupa` maps to the OpenType language system tag UPPH, and UPPH back to
    `und-fonupa`.

    Inside: tags with the `-fonupa` variant (with or without script and region subtags, any case) through
    hb_ot_tags_from_script_and_language (`in:forward`), and UPPH through hb_ot_tag_to_language and
    hb_ot_tags_to_script_and_language (`in:reverse`). Boundaries: `b:other-variant` (the other phonetic variants and
    look-alike subtags), `b:plain` (the same languages without the variant), `b:private-use` (`fonupa` after `-x-`
    or another singleton), `b:other-tag` (nearby OpenType language tags converted back). The main loop gives few
    distinct reverse inputs (UPPH alone, with three script tags); more follow it, UPPH among other language tags and
    with other script tags (the selection takes each input once).
    """
    font = synth / "u37-plain.ttf"
    for i in range(n):
        r = rng.random()
        lang = rng.choice(U35_LANGS)
        mid = rng.choice(("", "", "-Latn", "-Cyrl", "-FI", "-Latn-EE", "-RU"))
        script = rng.choice(U35_SCRIPTS)
        params = {"script": script} if script else {}
        if r < 0.35:
            s = f"{lang}{mid}-fonupa" + rng.choice(
                ("", "", "", "-u-co-phonebk", "-x-hbsc")
            )
            if rng.random() < 0.3:
                s = s.upper() if rng.random() < 0.5 else s.title()
            yield api_case("35", font, "tags", lang_bytes(s), nb="in:forward", **params)
        elif r < 0.45:
            if rng.random() < 0.5:
                yield api_case("35", font, "t2l", [tag_int("UPPH")], nb="in:reverse")
            else:
                yield api_case(
                    "35",
                    font,
                    "t2sl",
                    [tag_int(rng.choice(("latn", "cyrl", "DFLT"))), tag_int("UPPH")],
                    nb="in:reverse",
                )
        elif r < 0.6:
            var = rng.choice(
                (
                    "fonipa",
                    "fonnapa",
                    "fonxsamp",
                    "fonkirsh",
                    "fonupaa",
                    "fonup",
                    "xfonupa",
                    "fonupa1",
                    "afonupa",
                )
            )
            nb = "b:look-alike" if "fonup" in var else "b:other-variant"
            yield api_case(
                "35", font, "tags", lang_bytes(f"{lang}{mid}-{var}"), nb=nb, **params
            )
        elif r < 0.72:
            yield api_case(
                "35", font, "tags", lang_bytes(f"{lang}{mid}"), nb="b:plain", **params
            )
        elif r < 0.85:
            s = rng.choice(
                (
                    f"{lang}{mid}-x-fonupa",
                    f"{lang}-u-fonupa",
                    "x-fonupa",
                    f"{lang}-t-fonupa",
                )
            )
            yield api_case(
                "35", font, "tags", lang_bytes(s), nb="b:private-use", **params
            )
        else:
            tags = rng.sample(
                [
                    "IPPH",
                    "APPH",
                    "UPP ",
                    "UPPE",
                    "UPPG",
                    "URD ",
                    "UIG ",
                    "UKR ",
                    "UMB ",
                    "FIN ",
                    "SKS ",
                    "UDM ",
                    "KOM ",
                ],
                rng.randint(1, 3),
            )
            if rng.random() < 0.5:
                yield api_case(
                    "35", font, "t2l", [tag_int(t) for t in tags], nb="b:other-tag"
                )
            else:
                yield api_case(
                    "35",
                    font,
                    "t2sl",
                    [tag_int("latn"), tag_int(tags[0])],
                    nb="b:other-tag",
                )
    # More reverse inputs: UPPH among other language tags (t2l), and with other script tags (t2sl), the ones that
    # are not a script's primary tag giving the language an -x-hbsc- subtag.
    others = ["IPPH", "APPH", "FIN ", "SKS ", "UDM ", "KOM ", "URD ", "UKR ", "UPPE"]
    scripts = ["grek", "arab", "deva", "dev2", "hani", "kana", "math", "copt", "zyyy"]
    for k in range(50):
        if k % 5 < 3:
            tags = rng.sample(others, rng.randint(1, 2))
            tags.insert(rng.randrange(len(tags) + 1), "UPPH")
            yield api_case(
                "35", font, "t2l", [tag_int(t) for t in tags], nb="in:reverse"
            )
        else:
            yield api_case(
                "35",
                font,
                "t2sl",
                [tag_int(rng.choice(scripts)), tag_int("UPPH")],
                nb="in:reverse",
            )


# --------------------------------------------------------------------------------------------------------------
# Module contract
# --------------------------------------------------------------------------------------------------------------


def build_fonts(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    u36_pos_font(out)
    u36_kern_font(out, "kern")
    u36_kern_font(out, "kerx")
    u36_wide_font(out)
    u37_font(out)
    u38_fonts(out)
    u39_fonts(out)
    u42_font(out)
    u43_font(out)
    u50_fonts(out)
    u19_fonts(out)
    u33_font(out)
    u33_use_fonts(out)


UNITS = {
    "19": gen_19,
    "33": gen_33,
    "35": gen_35,
    "36": gen_36,
    "37": gen_37,
    "38": gen_38,
    "39": gen_39,
    "42": gen_42,
    "43": gen_43,
    "50": gen_50,
}

PER_UNIT = {
    "19": 600,
    "33": 1200,
    "35": 600,
    "36": 1500,
    "37": 800,
    "38": 800,
    "39": 600,
    "42": 500,
    "43": 600,
    "50": 500,
}

W_TARGETS = {
    "36": ["b:near-limit"],
    "37": ["b:no-overflow"],
    "38": ["b:font-extents"],
    "39": [],  # W39 (is_empty for is_void) moved only b:degenerate, now x:degenerate
    "43": ["b:old"],
    "33": ["b:reserved-in-new-block"],
    "35": ["b:look-alike"],
}
