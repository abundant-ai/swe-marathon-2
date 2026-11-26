"""Build the synthetic fonts the AAT and `kern` units need, including `kerx`, which fontTools cannot write.

Runs inside the pipeline image (`/opt/py/bin/python -I /pipe/synth_fonts.py OUT_DIR`). Every font here is ours:
box outlines, Latin letters, and the one table feature a unit needs. Development tooling, never shipped.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import _k_e_r_n, _t_r_a_k
from fontTools.ttLib.tables.DefaultTable import DefaultTable

UPEM = 1000
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def box(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((50, height))
    pen.lineTo((width - 50, height))
    pen.lineTo((width - 50, 0))
    pen.closePath()
    return pen.glyph()


def base_font(family: str, vertical: bool = True) -> FontBuilder:
    """A TrueType font with .notdef, space and A-Z as boxes of different widths, with vertical metrics."""
    names = [".notdef", "space", *LETTERS]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({0x20: "space", **{ord(c): c for c in LETTERS}})
    glyphs = {".notdef": box(500, 700), "space": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (500, 50), "space": (250, 0)}
    for i, c in enumerate(LETTERS):
        width = 500 + 20 * i
        glyphs[c] = box(width, 700)
        metrics[c] = (width, 50)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    if vertical:
        fb.setupVerticalMetrics({n: (1000, 100) for n in names})
        fb.setupVerticalHeader(ascent=500, descent=-500)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    return fb


def gid(fb: FontBuilder, name: str) -> int:
    return fb.font.getGlyphOrder().index(name)


def kerx_format0(pairs: dict[tuple[int, int], int], coverage_flags: int = 0) -> bytes:
    """One `kerx` table holding one format 0 subtable (Apple TrueType Reference Manual, `kerx`)."""
    items = sorted(pairs.items())
    n = len(items)
    unit = 6
    search = unit * (1 << (n.bit_length() - 1)) if n else 0
    selector = (n.bit_length() - 1) if n else 0
    body = struct.pack(">IIII", n, search, selector, unit * n - search)
    body += b"".join(
        struct.pack(">HHh", left, right, value) for (left, right), value in items
    )
    sub = struct.pack(">III", 12 + len(body), coverage_flags | 0, 0) + body
    return struct.pack(">HHI", 2, 0, 1) + sub


def add_raw_table(fb: FontBuilder, tag: str, data: bytes) -> None:
    table = DefaultTable(tag)
    table.data = data
    fb.font[tag] = table


def kerx_fonts(out: Path) -> None:
    """Unit 23: `kerx` pair kerning with a `GPOS` that has no kerning feature (and its neighbours)."""
    variants = {
        "kerx-gpos-nokern": "feature ss01 { pos A 30; } ss01;",
        "kerx-gpos-kern": "feature kern { pos A V -40; pos T O -40; } kern;",
        "kerx-nogpos": None,
    }
    for name, fea in variants.items():
        fb = base_font(name)
        pairs = {
            (gid(fb, "A"), gid(fb, "V")): -120,
            (gid(fb, "T"), gid(fb, "O")): -90,
            (gid(fb, "L"), gid(fb, "Y")): -150,
            (gid(fb, "W"), gid(fb, "A")): -60,
        }
        add_raw_table(fb, "kerx", kerx_format0(pairs))
        if fea:
            addOpenTypeFeaturesFromString(fb.font, fea)
        fb.save(str(out / f"{name}.ttf"))


def trak_font(out: Path) -> None:
    """Unit 22: `trak` tracking, horizontal and vertical, positive and negative tracks."""
    fb = base_font("trak-font")
    trak = newTable("trak")
    trak.version = 1.0
    trak.format = 0
    for attr, values in (("horizData", (40, 80, 120)), ("vertData", (60, 100, 140))):
        data = _t_r_a_k.TrackData()
        data[0.0] = _t_r_a_k.TrackTableEntry(
            {8.0: values[0], 12.0: values[1], 24.0: values[2]}, nameIndex=256
        )
        data[-1.0] = _t_r_a_k.TrackTableEntry(
            {8.0: -values[0], 12.0: -values[1], 24.0: -values[2]}, nameIndex=257
        )
        setattr(trak, attr, data)
    fb.font["trak"] = trak
    fb.save(str(out / "trak-font.ttf"))


def kern_vertical_fonts(out: Path) -> None:
    """Unit 21: an OpenType `kern` table, with and without `vkrn` in `GPOS`."""
    variants = {
        "kern-gpos-novkrn": "feature ss01 { pos A 30; } ss01;",
        "kern-gpos-vkrn": "feature vkrn { pos A V -40; } vkrn;",
        "kern-nogpos": None,
    }
    for name, fea in variants.items():
        for coverage, suffix in ((1, "h"), (0, "v")):
            fb = base_font(name)
            kern = newTable("kern")
            kern.version = 0
            sub = _k_e_r_n.KernTable_format_0()
            sub.version = 0
            sub.coverage = coverage
            sub.format = 0
            sub.kernTable = {
                ("A", "V"): -120,
                ("T", "O"): -90,
                ("L", "Y"): -150,
                ("W", "A"): -60,
            }
            kern.kernTables = [sub]
            fb.font["kern"] = kern
            if fea:
                addOpenTypeFeaturesFromString(fb.font, fea)
            fb.save(str(out / f"{name}-{suffix}.ttf"))


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    kerx_fonts(out)
    trak_font(out)
    kern_vertical_fonts(out)
    for path in sorted(out.glob("*.ttf")):
        print(path.name, path.stat().st_size)


if __name__ == "__main__":
    main()
