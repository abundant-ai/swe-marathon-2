"""Build the synthetic fonts the AAT and `kern` units need, including `kerx`, which fontTools cannot write.

Runs inside the pipeline image (`/opt/py/bin/python -I /pipe/synth_fonts.py OUT_DIR`). Every font here is ours:
box outlines, Latin letters, and the one table feature a unit needs. Development tooling, never shipped.
"""

from __future__ import annotations

import importlib
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


CROSS_STREAM = 0x40000000  # `kerx` subtable coverage bit


def kerx_fonts(out: Path) -> None:
    """Unit 23: `kerx` pair kerning beside a `GSUB` and a `GPOS` that has no kerning feature, and its neighbours.

    HarfBuzz prefers `GPOS` over `kerx` only when a font has both `GSUB` and `GPOS`, so the changed font needs all
    three tables. Neighbours: `GPOS` with `kern` (`kerx` stays off), no `GSUB` or no `GPOS` (`kerx` alone, before and
    after), and a cross-stream `kerx` subtable, which is not simple kerning and stays off beside `GPOS`.
    """
    gsub = "feature ss02 { sub A by B; } ss02;"
    nokern = "feature ss01 { pos A 30; } ss01;"
    kern = "feature kern { pos A V -40; pos T O -40; } kern;"
    variants = {
        "kerx-gsub-gpos-nokern": (gsub + nokern, 0),
        "kerx-gsub-gpos-kern": (gsub + kern, 0),
        "kerx-gsub-gpos-nokern-cross": (gsub + nokern, CROSS_STREAM),
        "kerx-gpos-nokern": (nokern, 0),
        "kerx-gpos-kern": (kern, 0),
        "kerx-gsub-nogpos": (gsub, 0),
        "kerx-nogpos": (None, 0),
    }
    for name, (fea, coverage) in variants.items():
        fb = base_font(name)
        pairs = {
            (gid(fb, "A"), gid(fb, "V")): -120,
            (gid(fb, "T"), gid(fb, "O")): -90,
            (gid(fb, "L"), gid(fb, "Y")): -150,
            (gid(fb, "W"), gid(fb, "A")): -60,
        }
        add_raw_table(fb, "kerx", kerx_format0(pairs, coverage))
        if fea:
            addOpenTypeFeaturesFromString(fb.font, fea)
        fb.save(str(out / f"{name}.ttf"))


def trak_fonts(out: Path) -> None:
    """Unit 22: `trak` tracking, horizontal and vertical, positive and negative tracks.

    HarfBuzz applies `trak` only to fonts that also have a `STAT` table, so the font that shows the change has one;
    the same font without `STAT` is a neighbour that no release tracks.
    """
    for name, stat in (("trak-stat", True), ("trak-nostat", False)):
        fb = base_font(name)
        trak = newTable("trak")
        trak.version = 1.0
        trak.format = 0
        for attr, values in (
            ("horizData", (40, 80, 120)),
            ("vertData", (60, 100, 140)),
        ):
            data = _t_r_a_k.TrackData()
            data[0.0] = _t_r_a_k.TrackTableEntry(
                {8.0: values[0], 12.0: values[1], 24.0: values[2]}, nameIndex=256
            )
            data[-1.0] = _t_r_a_k.TrackTableEntry(
                {8.0: -values[0], 12.0: -values[1], 24.0: -values[2]}, nameIndex=257
            )
            setattr(trak, attr, data)
        fb.font["trak"] = trak
        if stat:
            fb.setupStat(
                [
                    {
                        "tag": "wght",
                        "name": "Weight",
                        "values": [{"value": 400, "name": "Regular", "flags": 0x2}],
                    }
                ]
            )
        fb.save(str(out / f"{name}.ttf"))


BENGALI = {
    0x0995: "ka",
    0x0996: "kha",
    0x0997: "ga",
    0x099A: "ca",
    0x099C: "ja",
    0x099F: "tta",
    0x09A4: "ta",
    0x09A6: "da",
    0x09A8: "na",
    0x09AA: "pa",
    0x09AC: "ba",
    0x09AE: "ma",
    0x09AF: "ya",
    0x09B0: "ra",
    0x09B2: "la",
    0x09B8: "sa",
    0x09B9: "ha",
    0x0985: "aIndep",
    0x0987: "iIndep",
    0x09BE: "aaSign",
    0x09BF: "iSign",
    0x09C0: "iiSign",
    0x09C1: "uSign",
    0x09C7: "eSign",
    0x09C8: "aiSign",
    0x09CD: "virama",
    0x0981: "candrabindu",
    0x0982: "anusvara",
    0x09E7: "beng1",
    0x0964: "danda",
    0x0020: "space",
    0x002C: "comma",
    0x002D: "hyphen",
    0x002E: "period",
    0x0031: "one",
    0x0061: "a",
    0x25CC: "dottedCircle",
}
BENGALI_MARKS = {"uSign", "virama", "candrabindu", "anusvara"}
BENGALI_INIT = ("iSign", "eSign", "aiSign")


def bengali_init_font(out: Path) -> None:
    """Unit 1: a Bengali font whose `init` feature has word-initial forms of the pre-base vowel signs I, E and AI.

    No downloaded Bengali font has such forms (Noto Sans Bengali's `init` does not cover them), so this one is ours.
    """
    names = [".notdef", *BENGALI.values(), *(f"{g}.init" for g in BENGALI_INIT)]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({cp: name for cp, name in BENGALI.items()})
    glyphs, metrics = {}, {}
    for i, name in enumerate(names):
        width = 0 if name in BENGALI_MARKS else 400 + 10 * i
        glyphs[name] = box(max(width, 120), 600) if width else TTGlyphPen(None).glyph()
        metrics[name] = (width, 50 if width else 0)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "beng-init", "styleName": "Regular"})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    subs = " ".join(f"sub {g} by {g}.init;" for g in BENGALI_INIT)
    # No GDEF: HarfBuzz then classes the glyphs from their Unicode properties, marks included.
    fea = (
        "languagesystem DFLT dflt; languagesystem bng2 dflt; languagesystem beng dflt;\n"
        f"feature init {{ {subs} }} init;\n"
    )
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(out / "beng-init.ttf"))


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
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    for path in sorted(here.glob("gen_*.py")):
        build = getattr(importlib.import_module(path.stem), "build_fonts", None)
        if build:
            build(out)
    kerx_fonts(out)
    trak_fonts(out)
    bengali_init_font(out)
    kern_vertical_fonts(out)
    for path in sorted(out.glob("*.ttf")):
        print(path.name, path.stat().st_size)


if __name__ == "__main__":
    main()
