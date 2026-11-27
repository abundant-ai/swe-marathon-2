"""Candidates for the style, cmap, fallback metric, glyph alternate, face and font units, and the fonts they need.

Units: 40a, 40b, 40c (hb_style_get_value), 41 (hb_face_collect_unicodes and cmap format 13), 44a, 44b (fallback
vertical descender and hanging baseline), 45 (hb_ot_layout_lookup_collect_glyph_alternates), 46
(hb_face_create_or_fail with named-instance bits), 47b (hb_font_set_face does nothing), all through
tests/driver/hbmeta.c (drv "meta"); and 48, 49, 51 through the probes hbapi48.c, hbapi49.c and hbapi51.c of the
functions 15.1.0 and 15.2.0 add. Unit 47a has no generator: 47b overwrites its behaviour in 15.2.0.

Runs inside the pipeline image (fontTools 4.69.1). Every font here is ours: box outlines and the one table a unit
needs. Each font is described by a spec computed from a fixed seed, so build_fonts() and the generators agree on
what each font holds without reading it back. Development tooling, never shipped.
"""

from __future__ import annotations

import io
import math
import random
import struct
from collections.abc import Iterator
from pathlib import Path

from casekit import Font, api_case
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.ttCollection import TTCollection


def tag(s: str) -> int:
    """A four-character tag as the integer the drivers read."""
    return struct.unpack(">I", s.ljust(4).encode("ascii"))[0]


# Style tags, metrics tags and baseline tags as hb-style.h, hb-ot-metrics.h and hb-ot-layout.h define them.
SLNT, SLNT_RATIO, WGHT, WDTH, ITAL, OPSZ = (
    tag(t) for t in ("slnt", "Slnt", "wght", "wdth", "ital", "opsz")
)
VASC, VDSC, VLGP, HDSC = (tag(t) for t in ("vasc", "vdsc", "vlgp", "hdsc"))
HANG, ROMN, IDEO, IDTP, ICFB, ICFT, MATH = (
    tag(t) for t in ("hang", "romn", "ideo", "idtp", "icfb", "icft", "math")
)


# --------------------------------------------------------------------------------------------------------------
# Font helpers
# --------------------------------------------------------------------------------------------------------------


def _box(width: int, height: int):
    pen = TTGlyphPen(None)
    if width > 100 and height > 0:
        pen.moveTo((50, 0))
        pen.lineTo((50, height))
        pen.lineTo((width - 50, height))
        pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def _builder(
    family: str,
    names: list[str],
    cmap: dict[int, str],
    upem: int = 1000,
    widths: dict[str, int] | None = None,
    heights: dict[str, int] | None = None,
    vhea: tuple[int, int] | None = None,
    os2: dict | None = None,
    italic: float = 0.0,
) -> FontBuilder:
    """A TrueType font with a box for every glyph (empty for `space`); vertical metrics only when `vhea` is given."""
    widths, heights = widths or {}, heights or {}
    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    glyphs, metrics = {}, {}
    for i, name in enumerate(names):
        width = widths.get(name, upem // 2 + upem * (i % 37) // 100)
        height = heights.get(name, upem * 7 // 10)
        glyphs[name] = _box(width, height) if name != "space" else _box(0, 0)
        metrics[name] = (width, 50 * upem // 1000 if name != "space" else 0)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=upem * 4 // 5, descent=-upem // 5)
    if vhea:
        fb.setupVerticalMetrics({n: (upem, upem // 10) for n in names})
        fb.setupVerticalHeader(ascent=vhea[0], descent=vhea[1])
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    values = {
        "version": 4,
        "sTypoAscender": upem * 4 // 5,
        "sTypoDescender": -upem // 5,
        "usWinAscent": upem * 4 // 5,
        "usWinDescent": upem // 5,
        "usWeightClass": 400,
        "usWidthClass": 5,
    }
    values.update(os2 or {})
    fb.setupOS2(**values)
    fb.setupPost(italicAngle=italic)
    fb.updateHead(
        created=0x7C259DC0,
        modified=0x7C259DC0,
        macStyle=2 if values.get("fsSelection", 0) & 1 else 0,
    )
    return fb


def _bytes(fb: FontBuilder) -> bytes:
    fb.font.recalcTimestamp = False
    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


def _save(fb: FontBuilder, path: Path) -> None:
    path.write_bytes(_bytes(fb))


def _with_raw(data: bytes, tables: dict[str, bytes]) -> TTFont:
    """The font in `data` with some tables replaced by raw bytes; the other tables are kept as they are."""
    font = TTFont(io.BytesIO(data), lazy=True)
    font.recalcTimestamp = False
    for t, raw in tables.items():
        table = DefaultTable(t)
        table.data = raw
        font[t] = table
    return font


def _save_raw(data: bytes, tables: dict[str, bytes], path: Path) -> None:
    font = _with_raw(data, tables)
    buf = io.BytesIO()
    font.save(buf)
    path.write_bytes(buf.getvalue())


def _collection(fonts: list[bytes], path: Path) -> None:
    coll = TTCollection()
    coll.fonts = [TTFont(io.BytesIO(d), lazy=True) for d in fonts]
    for f in coll.fonts:
        f.recalcTimestamp = False
    coll.save(str(path))


def _latin(n_extra: int = 0) -> tuple[list[str], dict[int, str]]:
    names = [".notdef", "space", *(chr(c) for c in range(0x41, 0x5B))]
    names += [f"x{i:03d}" for i in range(n_extra)]
    cmap = {0x20: "space", **{c: chr(c) for c in range(0x41, 0x5B)}}
    return names, cmap


def _name(fb: FontBuilder, string: str, name_id: int) -> None:
    fb.font["name"].setName(string, name_id, 3, 1, 0x409)


def _stat(fb: FontBuilder, axes: list[str], values: list[tuple]) -> None:
    """A STAT table: `axes` the design axis tags; `values` (format, axis index, flags, value, extra) in table order,
    extra being (min, max) for format 2 and the linked value for format 3."""
    t = otTables.STAT()
    t.Version = 0x00010001
    t.DesignAxisRecordSize = 8
    rec = otTables.AxisRecordArray()
    rec.Axis = []
    for i, a in enumerate(axes):
        r = otTables.AxisRecord()
        r.AxisTag = a
        r.AxisNameID = 256 + i
        r.AxisOrdering = i
        rec.Axis.append(r)
        _name(fb, f"Axis {a}", 256 + i)
    t.DesignAxisRecord = rec
    t.DesignAxisCount = len(axes)
    arr = otTables.AxisValueArray()
    arr.AxisValue = []
    for k, (fmt, axis, flags, value, extra) in enumerate(values):
        v = otTables.AxisValue()
        v.Format = fmt
        v.AxisIndex = axis
        v.Flags = flags
        v.ValueNameID = 300 + k
        _name(fb, f"Value {k}", 300 + k)
        if fmt == 2:
            v.NominalValue = value
            v.RangeMinValue, v.RangeMaxValue = extra
        else:
            v.Value = value
            if fmt == 3:
                v.LinkedValue = extra
        arr.AxisValue.append(v)
    t.AxisValueArray = arr
    t.AxisValueCount = len(values)
    t.ElidedFallbackNameID = 2
    stat = newTable("STAT")
    stat.table = t
    fb.font["STAT"] = stat


def _fvar(fb: FontBuilder, axes: list[tuple], instances: list[dict]) -> None:
    """axes: (tag, min, default, max); instances: {tag: value}, axes left out at their default."""
    defaults = {a: d for a, _, d, _ in axes}
    fb.setupFvar(
        [(a, lo, d, hi, f"Axis {a}") for a, lo, d, hi in axes],
        [
            {"location": {**defaults, **loc}, "stylename": f"Instance {i}"}
            for i, loc in enumerate(instances)
        ],
    )


# --------------------------------------------------------------------------------------------------------------
# Font specs (fixed seed: build_fonts() and the generators read the same lists)
# --------------------------------------------------------------------------------------------------------------

_R = random.Random("f8b-fonts-1")

# 40a: OS/2 version 5 optical size bounds, in twentieths of a point. Every third font also has a GPOS `size`
# feature, which the OS/2 bounds take precedence over.
OPSZ_V5 = [
    (160, 480),
    (120, 240),
    (180, 1440),
    (100, 280),
    (1, 2),
    (20, 65535),
    (240, 360),
    (333, 1001),
]
OPSZ_V5 += [
    (200, 201),
    (12, 0xFFFE),
    (480, 960),
    (60, 140),
    (7, 913),
    (1000, 3000),
    (90, 150),
    (141, 707),
]
OPSZ_SIZE = [90, 120, 180, 240, 75, 720, 105]  # GPOS `size` design sizes in decipoints
OPSZ_BAD = [
    (240, 240),
    (0, 480),
    (480, 240),
    (5, 1),
    (0, 0),
    (300, 100),
]  # rejected OS/2 bounds

# 40b: the slant angle from fvar, from STAT, and from post. Composing an angle with the synthetic slant calls the C
# library's tanf and atanf, whose last bit differs between machines (the arm64 build fuses multiply-adds). Changed
# cases and the post neighbours therefore use only angles whose ratio tanf returns unchanged (0 and angles below
# 0.007 degrees, where tanf (x) is x) and synthetic slants that make the composed ratio exactly +-0.5, 1 or 1.5,
# whose atanf every implementation returns from the same constants. The other angles serve the neighbours that
# compose nothing.
ROBUST_ANGLES = [
    0.0,
    0.0050048828125,
    -0.0050048828125,
    0.001953125,
    -0.001953125,
    0.00390625,
    -0.00390625,
]
RATIO_TARGETS = [0.5, 1.0, 1.5, -0.5, -1.0, -1.5]
SLANT_FVAR = [
    (0.0, False),
    (0.0050048828125, True),
    (-12.0, True),
    (0.001953125, False),
    (-0.00390625, True),
    (8.5, False),
]  # default, with a wght axis
SLANT_STAT = [
    (0.0, 1),
    (0.0050048828125, 2),
    (-0.001953125, 3),
    (-12.0, 1),
    (0.0, 2),
    (0.00390625, 1),
    (-0.0050048828125, 3),
]  # value, STAT format
SLANT_POST = [0.0, 0.0050048828125, -0.001953125, 0.00390625, -0.0050048828125, 0.0]
SYNTH_SLANTS = ["0.1", "0.2", "0.25", "-0.15", "0.333", "1", "-0.5", "0.05", "0.4"]


def _f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _f32_step(x: float, up: bool) -> float:
    bits = struct.unpack("<i", struct.pack("<f", x))[0]
    bits += 1 if (up == (x >= 0)) else -1
    return struct.unpack("<f", struct.pack("<i", bits))[0]


PI_F = _f32(math.pi)


def slant_for(angle: float, target: float) -> str:
    """A synthetic slant s with s + ratio (angle) == target in float arithmetic, HarfBuzz's ratio of these tiny angles
    being tanf (angle * -HB_PI / 180.f) == angle * -HB_PI / 180.f; printed so that strtof gives s back."""
    x = _f32(_f32(angle * -PI_F) / 180.0)
    assert abs(x) < 2.0**-13
    s = _f32(target - x)
    for cand in (s, _f32_step(s, True), _f32_step(s, False)):
        if _f32(cand + x) == target:
            return f"{cand:.9g}"
    raise ValueError((angle, target))


# 40c: STAT axis values with flags. Design axes in this order; per font, per axis, the values in table order as
# (flags, value). Flag 1 is OLDER_SIBLING_FONT_ATTRIBUTE, flag 2 ELIDABLE_AXIS_VALUE_NAME.
STAT_AXES = ["wght", "wdth", "ital", "opsz", "slnt"]
STAT_CHOICES = {
    "wght": [100, 200, 300, 350, 400, 500, 600, 700, 800, 900],
    "wdth": [50, 62.5, 75, 87.5, 100, 112.5, 125, 150],
    "ital": [0, 1],
    "opsz": [6, 8, 9, 10, 11, 14, 18, 24, 36, 72],
    "slnt": [-15, -12, -10, -8, 0, 5, 10],
}
STAT_SHAPES = [
    [(1, 0), (0, 1)],  # an older sibling value before the current one
    [(1, 0)],  # only an older sibling value: the polyfill answers
    [(3, 0), (0, 1)],  # older sibling and elidable
    [(1, 0), (1, 1), (0, 2)],  # two older sibling values first
    [(2, 0), (0, 1)],  # elidable first
    [(0, 0), (1, 1)],  # an older sibling value after the current one
    [(0, 0)],  # no flags
    [(2, 0)],  # elidable only
]


def _stat_font_specs() -> list[dict]:
    specs = []
    for i in range(14):
        axes = {}
        for a in STAT_AXES:
            shape = _R.choice(STAT_SHAPES)
            vals = _R.sample(STAT_CHOICES[a], k=min(len(shape), len(STAT_CHOICES[a])))
            if len(vals) < len(shape):
                shape = shape[: len(vals)]
            axes[a] = [(flags, vals[j], _R.choice((1, 1, 2, 3))) for flags, j in shape]
        specs.append(
            {
                "name": f"u40c-stat-{i}.ttf",
                "axes": axes,
                "weight": _R.choice((300, 400, 500, 700)),
                "width": _R.choice((3, 4, 5, 7)),
                "italic_bit": _R.random() < 0.3,
                "angle": _R.choice((0.0, -10.0, -12.5)),
            }
        )
    return specs


STAT_FONTS = _stat_font_specs()


def stat_label(axes: dict[str, list], a: str) -> str:
    """Unit 40c: which side of the note a query of axis `a` sits on, from the axis' values in table order."""
    vals = axes.get(a, [])
    if not vals:
        return ""
    first = vals[0][0]
    if first & 1:
        return "in"
    if first == 2:
        return "b:elidable"
    if any(f & 1 for f, _, _ in vals[1:]):
        return "b:sibling-later"
    return "b:no-sibling"


# 41: cmap faces of one collection. Each spec: (role, glyph count, subtables), a subtable being (platform,
# encoding, format, groups) and a group (first code point, last code point, glyph).
BLOCKS = [
    (0x0400, 0x04FF),
    (0x0590, 0x05FF),
    (0x0600, 0x06FF),
    (0x0900, 0x097F),
    (0x0E00, 0x0E7F),
    (0x1100, 0x11FF),
    (0x2000, 0x206F),
    (0x2190, 0x21FF),
    (0x2500, 0x257F),
    (0x3040, 0x309F),
    (0x4E00, 0x9FFF),
    (0xAC00, 0xD7A3),
    (0xE000, 0xF8FF),
    (0x10000, 0x1007F),
    (0x1F300, 0x1F5FF),
    (0x20000, 0x2A6DF),
    (0xF0000, 0xFFFFD),
]


def _groups(n_glyphs: int, count: int, fit: bool) -> list[tuple[int, int, int]]:
    """`count` disjoint block groups with glyphs in 1..n_glyphs-1; `fit` keeps glyph + last - first below the
    glyph count, otherwise at least one group runs past it."""
    blocks = sorted(_R.sample(BLOCKS, k=count))
    out = []
    for lo, hi in blocks:
        glyph = _R.randrange(1, n_glyphs)
        if fit:
            room = n_glyphs - 1 - glyph
            if room < 1:
                glyph, room = 1, n_glyphs - 2
            span = _R.randrange(0, min(room, hi - lo) + 1)
            start = _R.randrange(lo, hi - span + 1)
            out.append((start, start + span, glyph))
        else:
            out.append((lo, hi, glyph))
    if not fit and all(g + (e - s) < n_glyphs for s, e, g in out):
        s, e, _ = out[0]
        out[0] = (s, e, n_glyphs - 1)
    return out


def _cmap_specs() -> list[tuple[str, int, list]]:
    specs = []
    for i in range(36):
        n = _R.choice((12, 30, 64, 200))
        enc = _R.choice(((3, 10), (3, 10), (0, 6), (0, 4)))
        groups = _groups(n, _R.randrange(1, 6), fit=False)
        if _R.random() < 0.3:
            groups = sorted(
                groups
                + [
                    g
                    for g in _groups(n, 1, fit=True)
                    if all(g[1] < s or g[0] > e for s, e, _ in groups)
                ]
            )
        subs = [(enc[0], enc[1], 13, groups)]
        if _R.random() < 0.4:
            subs.append((3, 1, 4, None))
        specs.append(("in", n, subs))
    for i in range(7):
        n = _R.choice((64, 200))
        specs.append(
            ("b:f13-short", n, [(3, 10, 13, _groups(n, _R.randrange(1, 5), fit=True))])
        )
    for i in range(7):
        n = _R.choice((30, 64, 200))
        groups = _groups(n, _R.randrange(1, 4), fit=True)
        lo, hi = _R.choice(
            [b for b in BLOCKS if all(b[1] < s or b[0] > e for s, e, _ in groups)]
        )
        groups = sorted(groups + [(lo, hi, _R.choice((n, n + 1, n + 50, 0xFFFF)))])
        specs.append(("b:f13-glyph-past-end", n, [(3, 10, 13, groups)]))
    for i in range(7):
        n = _R.choice((30, 64, 200))
        groups = _groups(n, _R.randrange(1, 4), fit=True)
        lo, hi = _R.choice(
            [b for b in BLOCKS if all(b[1] < s or b[0] > e for s, e, _ in groups)]
        )
        groups = sorted(groups + [(lo, hi, 0)])
        specs.append(("b:f13-notdef", n, [(3, 10, 13, groups)]))
    for i in range(7):
        n = _R.choice((64, 200))
        specs.append(
            ("b:f12", n, [(3, 10, 12, _groups(n, _R.randrange(1, 5), fit=True))])
        )
    for i in range(7):
        n = _R.choice((30, 64, 200))
        specs.append(
            (
                "b:f13-not-chosen",
                n,
                [
                    (3, 10, 12, _groups(n, 2, fit=True)),
                    (0, 6, 13, _groups(n, 3, fit=False)),
                ],
            )
        )
    return specs


CMAP_FACES = _cmap_specs()
CMAP_FILE = "u41-cmap.ttc"

# 44a: synthetic fonts without vhea (units per em) and with vhea (ascender, descender).
NOVHEA_UPEM = [1000, 2048, 1024, 500, 1100, 3000]
VHEA = [(500, -500), (880, -120), (1024, -1024), (600, -400), (512, -512)]

# 44b: the scripts whose hanging baseline the fallback synthesizes from a glyph, with their OpenType tags (old,
# then new where there is one) and the character it measures.
HANGING = [
    ("Beng", ("beng", "bng2"), 0x0995),
    ("Deva", ("deva", "dev2"), 0x0915),
    ("Gujr", ("gujr", "gjr2"), 0x0A95),
    ("Guru", ("guru", "gur2"), 0x0A15),
    ("Tibt", ("tibt",), 0x0F40),
    ("Limb", ("limb",), 0x1901),
    ("Sylo", ("sylo",), 0xA807),
    ("Phag", ("phag",), 0xA840),
    ("Mtei", ("mtei",), 0xABC0),
    ("Shrd", ("shrd",), 0x11191),
    ("Takr", ("takr",), 0x1168C),
    ("Modi", ("modi",), 0x1160E),
    ("Sidd", ("sidd",), 0x11590),
    ("Tirh", ("tirh",), 0x1148F),
    ("Marc", ("marc",), 0x11C72),
    ("Newa", ("newa",), 0x1140E),
    ("Soyo", ("soyo",), 0x11A5C),
    ("Zanb", ("zanb",), 0x11A0B),
    ("Dogr", ("dogr",), 0x1180A),
    ("Gong", ("gong",), 0x11D6C),
    ("Nand", ("nand",), 0x119B0),
]
OTHER_SCRIPTS = [
    ("Latn", ("latn",)),
    ("Cyrl", ("cyrl",)),
    ("Grek", ("grek",)),
    ("Arab", ("arab",)),
    ("Hebr", ("hebr",)),
    ("Taml", ("taml", "tml2")),
    ("Telu", ("telu", "tel2")),
    ("Knda", ("knda", "knd2")),
    ("Mlym", ("mlym", "mlm2")),
    ("Orya", ("orya", "ory2")),
    ("Sinh", ("sinh",)),
    ("Thai", ("thai",)),
    ("Khmr", ("khmr",)),
    ("Armn", ("armn",)),
]


def _hang_specs() -> list[dict]:
    specs = []
    for i, upem in enumerate((1000, 2048, 1000, 1024, 1000, 500)):
        have = _R.sample(range(len(HANGING)), k=_R.randrange(14, len(HANGING) + 1))
        specs.append(
            {
                "name": f"u44b-hang-{i}.ttf",
                "upem": upem,
                "heights": {
                    HANGING[k][2]: _R.randrange(upem * 3 // 10, upem)
                    for k in sorted(have)
                },
                "base": None,
            }
        )
    for i, upem in enumerate((1000, 2048, 1000)):
        have = list(range(len(HANGING)))
        in_base = sorted(_R.sample(range(4), k=3)) + [
            4
        ]  # Bengali, Devanagari, Gujarati, Gurmukhi; Tibetan
        specs.append(
            {
                "name": f"u44b-base-{i}.ttf",
                "upem": upem,
                "heights": {
                    HANGING[k][2]: _R.randrange(upem * 3 // 10, upem) for k in have
                },
                "base": {
                    HANGING[k][1][0]: _R.randrange(upem // 2, upem) for k in in_base
                },
                "dflt": i != 1,
            }
        )
    return specs


HANG_FONTS = _hang_specs()

# 45: GSUB lookups of each kind. Per font, lookups in definition order (= lookup index): (kind, data).
N45 = 160


def _alt_lookup(n_glyphs: int, many: bool) -> dict:
    sources = _R.sample(range(1, 60), k=_R.randrange(2, 8))
    return {
        g: _R.sample(
            range(60, n_glyphs), k=_R.randrange(2 if many else 1, 7 if many else 2)
        )
        for g in sorted(sources)
    }


def _alts_specs() -> list[list[tuple]]:
    fonts = []
    for i in range(4):
        lookups = []
        for _ in range(3):
            lookups.append(("alt", _alt_lookup(N45, True)))
        lookups.append(("alt1", _alt_lookup(N45, False)))
        lookups.append(("alt-ext", _alt_lookup(N45, True)))
        first = _alt_lookup(N45, True)
        shared = next(iter(first))
        second = {shared: _R.sample(range(60, N45), k=_R.randrange(1, 4))}
        second.update(
            {g: alts for g, alts in _alt_lookup(N45, True).items() if g not in first}
        )
        lookups.append(("alt-2sub", (first, second)))
        for ext in ("sgl1", "sgl1", "sgl1-ext"):
            delta = _R.choice((1, 3, 17, 40, -5, -30))
            lo = 40 if delta < 0 else 1
            glyphs = sorted(_R.sample(range(lo, 59), k=_R.randrange(2, 9)))
            lookups.append((ext, {g: g + delta for g in glyphs}))
        sources = sorted(_R.sample(range(1, 60), k=_R.randrange(3, 9)))
        lookups.append(("sgl2", {g: _R.randrange(60, N45) for g in sources}))
        lookups.append(
            (
                "lig",
                [
                    (sorted(_R.sample(range(1, 60), k=2)), _R.randrange(60, N45))
                    for _ in range(3)
                ],
            )
        )
        sources = sorted(_R.sample(range(1, 60), k=_R.randrange(3, 7)))
        seqs = {
            g: [_R.randrange(60, N45) for _ in range(_R.choice((1, 1, 2)))]
            for g in sources
        }
        seqs[sources[0]] = [
            _R.randrange(60, N45),
            _R.randrange(60, N45),
        ]  # keeps it a MultipleSubst for feaLib
        lookups.append(("mul", seqs))
        _R.shuffle(lookups)
        fonts.append(lookups)
    return fonts


ALTS_FONTS = _alts_specs()

# 46: collections of a static face and small variable faces. Each face: named instances (0 = static).
COLLECTIONS = [[0, 4, 0], [3, 5], [0, 0, 2, 0]]

# 49: JSTF tables. Per font, per script tag (sorted): extender glyphs (None: no ExtenderGlyph table) and the
# language systems the script lists.
JSTF_FONTS = [
    {
        "arab": ([5, 6, 7, 8, 9], ["ARA ", "FAR "]),
        "latn": (None, []),
        "mong": ([20], []),
        "syrc": ([10, 11], []),
    },
    {
        "arab": (list(range(30, 42)), []),
        "hebr": ([], []),
        "thaa": ([12, 13, 14], ["DIV "]),
    },
    {
        "arab": ([3], ["URD "]),
        "copt": ([25, 26], []),
        "grek": (None, ["ELL "]),
        "syrc": ([4, 15, 16, 17], []),
    },
    {
        "armn": ([2, 4, 6, 8, 10, 12, 14, 16], []),
        "cyrl": ([40], ["RUS ", "UKR "]),
        "geor": ([7, 9], []),
    },
]
N49 = 48


# --------------------------------------------------------------------------------------------------------------
# build_fonts
# --------------------------------------------------------------------------------------------------------------


def _v5(lo: int, hi: int) -> dict:
    """OS/2 version 5 with optical size bounds given in twentieths of a point (fontTools holds them in points)."""
    return {
        "version": 5,
        "usLowerOpticalPointSize": lo / 20,
        "usUpperOpticalPointSize": hi / 20,
    }


def _size_feature(fb: FontBuilder, decipoints: int) -> None:
    addOpenTypeFeaturesFromString(
        fb.font, f"feature size {{ parameters {decipoints / 10:.1f} 0; }} size;"
    )


def _fonts_40(out: Path) -> None:
    names, cmap = _latin()
    for i, (lo, hi) in enumerate(OPSZ_V5):
        fb = _builder(f"u40a-v5-{i}", names, cmap, os2=_v5(lo, hi))
        if i % 3 == 0:
            _size_feature(fb, OPSZ_SIZE[i % len(OPSZ_SIZE)])
        if i % 4 == 1:
            _stat(fb, ["wght"], [(1, 0, 0, 400.0, None)])
        _save(fb, out / f"u40a-v5-{i}.ttf")
    for i, size in enumerate(OPSZ_SIZE):
        fb = _builder(f"u40a-v4size-{i}", names, cmap)
        _size_feature(fb, size)
        _save(fb, out / f"u40a-v4size-{i}.ttf")
    for i in range(3):
        _save(
            _builder(f"u40a-v4-{i}", names, cmap, os2={"version": (4, 3, 1)[i]}),
            out / f"u40a-v4-{i}.ttf",
        )
    for i, (lo, hi) in enumerate(OPSZ_BAD):
        fb = _builder(f"u40a-v5bad-{i}", names, cmap, os2=_v5(lo, hi))
        if i % 2:
            _size_feature(fb, OPSZ_SIZE[i])
        _save(fb, out / f"u40a-v5bad-{i}.ttf")
    fb = _builder("u40a-v5fvar", names, cmap, os2=_v5(160, 480))
    _fvar(
        fb, [("opsz", 6.0, 12.0, 72.0)], [{"opsz": 6.0}, {"opsz": 12.0}, {"opsz": 72.0}]
    )
    _save(fb, out / "u40a-v5fvar.ttf")
    for i, (fmt, value) in enumerate(((1, 11.0), (2, 14.0), (3, 9.0))):
        fb = _builder(f"u40a-v5stat-{i}", names, cmap, os2=_v5(160, 480))
        _stat(
            fb,
            ["wght", "opsz"],
            [
                (1, 0, 0, 400.0, None),
                (fmt, 1, 0, value, (6.0, 72.0) if fmt == 2 else 18.0),
            ],
        )
        _save(fb, out / f"u40a-v5stat-{i}.ttf")

    for i, (default, wght) in enumerate(SLANT_FVAR):
        fb = _builder(f"u40b-fvar-{i}", names, cmap)
        axes = [("slnt", -20.0, default, 20.0)] + (
            [("wght", 100.0, 400.0, 900.0)] if wght else []
        )
        insts = [{"slnt": default}, {"slnt": -10.0}] + (
            [{"slnt": 0.0, "wght": 700.0}] if wght else []
        )
        _fvar(fb, axes, insts)
        _save(fb, out / f"u40b-fvar-{i}.ttf")
    for i, (value, fmt) in enumerate(SLANT_STAT):
        fb = _builder(f"u40b-stat-{i}", names, cmap)
        extra = (value - 2.0, value + 2.0) if fmt == 2 else 1.0
        _stat(
            fb,
            ["wght", "slnt", "ital"],
            [(1, 0, 0, 400.0, None), (fmt, 1, 0, value, extra), (1, 2, 2, 0.0, None)],
        )
        _save(fb, out / f"u40b-stat-{i}.ttf")
    for i, angle in enumerate(SLANT_POST):
        fb = _builder(f"u40b-post-{i}", names, cmap, italic=angle)
        if i % 2:
            _stat(fb, ["wght"], [(1, 0, 0, 400.0, None)])
        _save(fb, out / f"u40b-post-{i}.ttf")

    order_rng = random.Random("f8b-stat-order-1")
    for spec in STAT_FONTS:
        fb = _builder(
            spec["name"][:-4],
            names,
            cmap,
            italic=spec["angle"],
            os2={
                "usWeightClass": spec["weight"],
                "usWidthClass": spec["width"],
                "fsSelection": 0x01 if spec["italic_bit"] else 0x40,
            },
        )
        per_axis = [
            [(STAT_AXES.index(a), f, v, fmt) for f, v, fmt in vals]
            for a, vals in spec["axes"].items()
        ]
        order = []
        while any(per_axis):
            queue = order_rng.choice([q for q in per_axis if q])
            order.append(queue.pop(0))
        values = []
        for axis, flags, value, fmt in order:
            extra = (
                (value - 1.0, value + 1.0)
                if fmt == 2
                else (value + 1.0 if fmt == 3 else None)
            )
            values.append((fmt, axis, flags, float(value), extra))
        _stat(fb, STAT_AXES, values)
        _save(fb, out / spec["name"])
    fb = _builder("u40c-fvar", names, cmap)
    _fvar(
        fb,
        [("wght", 100.0, 400.0, 900.0), ("wdth", 75.0, 100.0, 100.0)],
        [{"wght": 700.0, "wdth": 75.0}],
    )
    _stat(
        fb,
        STAT_AXES,
        [
            (1, 0, 1, 300.0, None),
            (1, 0, 0, 400.0, None),
            (1, 1, 1, 87.5, None),
            (1, 2, 1, 1.0, None),
            (1, 2, 0, 0.0, None),
        ],
    )
    _save(fb, out / "u40c-fvar.ttf")


def _cmap_raw(subtables: list[tuple], glyph_of: dict[int, int]) -> bytes:
    """A cmap table; format 4 subtables map the font's Latin letters, formats 12 and 13 their groups."""
    out = []
    for plat, enc, fmt, groups in sorted(subtables, key=lambda s: (s[0], s[1])):
        if fmt == 4:
            segs = sorted(glyph_of.items()) + [(0xFFFF, 0)]
            body = []
            seg_count = len(segs)
            ends = [cp for cp, _ in segs]
            starts = [cp for cp, _ in segs]
            deltas = [((g - cp) & 0xFFFF) if cp != 0xFFFF else 1 for cp, g in segs]
            search = 2 * (1 << (seg_count.bit_length() - 1))
            body = struct.pack(
                ">HHHH",
                seg_count * 2,
                search,
                (search // 2).bit_length() - 1,
                seg_count * 2 - search,
            )
            body += (
                struct.pack(f">{seg_count}H", *ends)
                + b"\0\0"
                + struct.pack(f">{seg_count}H", *starts)
            )
            body += struct.pack(f">{seg_count}H", *deltas) + struct.pack(
                f">{seg_count}H", *([0] * seg_count)
            )
            out.append((plat, enc, struct.pack(">HHH", 4, 6 + len(body), 0) + body))
        else:
            body = b"".join(struct.pack(">III", s, e, g) for s, e, g in groups)
            out.append(
                (
                    plat,
                    enc,
                    struct.pack(">HHIII", fmt, 0, 16 + len(body), 0, len(groups))
                    + body,
                )
            )
    head = struct.pack(">HH", 0, len(out))
    offset = 4 + 8 * len(out)
    recs, data = b"", b""
    for plat, enc, sub in out:
        recs += struct.pack(">HHI", plat, enc, offset + len(data))
        data += sub
    return head + recs + data


def _fonts_41(out: Path) -> None:
    faces = []
    for role, n, subs in CMAP_FACES:
        names = [
            ".notdef",
            "space",
            *(chr(c) for c in range(0x41, 0x41 + min(26, n - 2))),
        ]
        names += [f"x{i:03d}" for i in range(n - len(names))]
        letters = {c: names.index(chr(c)) for c in range(0x41, 0x41 + min(26, n - 2))}
        fb = _builder(f"u41-{role}", names, {})
        faces.append(
            bytes(_with_raw_bytes(_bytes(fb), {"cmap": _cmap_raw(subs, letters)}))
        )
    _collection(faces, out / CMAP_FILE)


def _with_raw_bytes(data: bytes, tables: dict[str, bytes]) -> bytes:
    font = _with_raw(data, tables)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def _fonts_44(out: Path) -> None:
    names, cmap = _latin()
    for upem in NOVHEA_UPEM:
        _save(
            _builder(f"u44a-novhea-{upem}", names, cmap, upem=upem),
            out / f"u44a-novhea-{upem}.ttf",
        )
    for i, (asc, desc) in enumerate(VHEA):
        _save(
            _builder(f"u44a-vhea-{i}", names, cmap, vhea=(asc, desc)),
            out / f"u44a-vhea-{i}.ttf",
        )
    for spec in HANG_FONTS:
        upem = spec["upem"]
        glyphs = {cp: f"u{cp:05X}" for cp in spec["heights"]}
        hnames = [".notdef", "space", "hyphen", "x", *glyphs.values()]
        hcmap = {
            0x20: "space",
            0x2D: "hyphen",
            0x78: "x",
            **{cp: n for cp, n in glyphs.items()},
        }
        heights = {glyphs[cp]: h for cp, h in spec["heights"].items()}
        heights.update({"hyphen": upem * 3 // 10, "x": upem // 2})
        fb = _builder(spec["name"][:-4], hnames, hcmap, upem=upem, heights=heights)
        if spec["base"]:
            scripts = (
                [f"DFLT romn {upem * 7 // 10} {-upem // 8} 0"] if spec["dflt"] else []
            )
            scripts += [
                f"{t} hang {v} {-upem // 8} 0" for t, v in sorted(spec["base"].items())
            ]
            addOpenTypeFeaturesFromString(
                fb.font,
                "table BASE { HorizAxis.BaseTagList hang ideo romn;\n"
                f"HorizAxis.BaseScriptList {', '.join(scripts)}; }} BASE;",
            )
        _save(fb, out / spec["name"])


def _fea_glyph(g: int) -> str:
    return f"x{g:03d}"


def _fonts_45(out: Path) -> None:
    names = [".notdef", *(f"x{g:03d}" for g in range(1, N45))]
    for i, lookups in enumerate(ALTS_FONTS):
        fea = ["languagesystem DFLT dflt;"]
        refs = []
        for k, (kind, data) in enumerate(lookups):
            name = f"L{k}"
            ext = " useExtension" if kind.endswith("-ext") else ""
            body = []
            if kind.startswith("alt") and kind != "alt-2sub":
                body = [
                    f"sub {_fea_glyph(g)} from [{' '.join(map(_fea_glyph, alts))}];"
                    for g, alts in data.items()
                ]
            elif kind == "alt-2sub":
                first, _ = (
                    data  # the second subtable is added below: feaLib refuses a glyph twice in a lookup
                )
                body = [
                    f"sub {_fea_glyph(g)} from [{' '.join(map(_fea_glyph, a))}];"
                    for g, a in first.items()
                ]
            elif kind.startswith("sgl"):
                body = [
                    f"sub {_fea_glyph(g)} by {_fea_glyph(t)};" for g, t in data.items()
                ]
            elif kind == "lig":
                body = [
                    f"sub {' '.join(map(_fea_glyph, comps))} by {_fea_glyph(t)};"
                    for comps, t in data
                ]
            elif kind == "mul":
                body = [
                    f"sub {_fea_glyph(g)} by {' '.join(map(_fea_glyph, seq))};"
                    for g, seq in data.items()
                ]
            fea.append(
                f"lookup {name}{ext} {{\n  " + "\n  ".join(body) + f"\n}} {name};"
            )
            refs.append(f"lookup {name};")
        fea.append("feature salt {\n  " + "\n  ".join(refs) + "\n} salt;")
        fb = _builder(
            f"u45-alts-{i}", names, {0x41 + k: f"x{k + 1:03d}" for k in range(26)}
        )
        addOpenTypeFeaturesFromString(fb.font, "\n".join(fea))
        table = fb.font["GSUB"].table
        for k, (kind, data) in enumerate(lookups):
            if kind == "alt-2sub":
                sub = otTables.AlternateSubst()
                sub.Format = 1
                sub.alternates = {
                    _fea_glyph(g): [_fea_glyph(a) for a in alts]
                    for g, alts in data[1].items()
                }
                lookup = table.LookupList.Lookup[k]
                lookup.SubTable.append(sub)
                lookup.SubTableCount = len(lookup.SubTable)
        _save(fb, out / f"u45-alts-{i}.ttf")


def _vf_bytes(family: str, instances: int) -> bytes:
    names, cmap = _latin()
    fb = _builder(family, names, cmap)
    if instances:
        values = [100.0, 300.0, 400.0, 600.0, 700.0, 900.0][:instances]
        _fvar(
            fb,
            [("wght", 100.0, 400.0, 900.0), ("wdth", 75.0, 100.0, 125.0)],
            [
                {"wght": v, "wdth": (75.0, 100.0, 125.0)[k % 3]}
                for k, v in enumerate(values)
            ],
        )
    return _bytes(fb)


def _fonts_46(out: Path) -> None:
    for i, members in enumerate(COLLECTIONS):
        _collection(
            [_vf_bytes(f"u46-coll-{i}-{k}", inst) for k, inst in enumerate(members)],
            out / f"u46-coll-{i}.ttc",
        )


def _fonts_47(out: Path) -> None:
    names, cmap = _latin()
    fb = _builder("u47b-a", names, cmap)
    addOpenTypeFeaturesFromString(
        fb.font, "feature kern { pos A V -80; pos T O -60; } kern;"
    )
    _save(fb, out / "u47b-a.ttf")
    rev = [".notdef", *(chr(c) for c in range(0x5A, 0x40, -1)), "space", "F_I", "T_H"]
    fb = _builder(
        "u47b-b",
        rev,
        cmap,
        upem=2048,
        widths={n: 900 + 37 * k for k, n in enumerate(rev)},
    )
    addOpenTypeFeaturesFromString(
        fb.font,
        "feature liga { sub F I by F_I; sub T H by T_H; } liga;\n"
        "feature kern { pos A W -150; pos L T -200; } kern;",
    )
    _save(fb, out / "u47b-b.ttf")
    half = [".notdef", "space", *(chr(c) for c in range(0x41, 0x4E))]
    fb = _builder(
        "u47b-c",
        half,
        {0x20: "space", **{c: chr(c) for c in range(0x41, 0x4E)}},
        widths={n: 300 + 45 * k for k, n in enumerate(half)},
    )
    addOpenTypeFeaturesFromString(
        fb.font,
        "feature ss01 { sub A by B; } ss01; feature kern { pos B A -40; } kern;",
    )
    _save(fb, out / "u47b-c.ttf")


def _jstf_raw(scripts: dict[str, tuple]) -> bytes:
    def lang_sys() -> bytes:
        return (
            struct.pack(">HH", 1, 4) + b"\0" * 20
        )  # one JstfPriority, every offset NULL

    def script(extenders: list[int] | None, langs: list[str]) -> bytes:
        head = 6 + 6 * len(langs)
        parts = b""
        ext_off = 0
        if extenders is not None:
            ext_off = head + len(parts)
            parts += struct.pack(f">H{len(extenders)}H", len(extenders), *extenders)
        def_off = head + len(parts)
        parts += lang_sys()
        recs = b""
        for t in langs:
            recs += struct.pack(">4sH", t.encode("ascii"), head + len(parts))
            parts += lang_sys()
        return struct.pack(">HHH", ext_off, def_off, len(langs)) + recs + parts

    items = sorted(scripts.items())
    head = 6 + 6 * len(items)
    recs, data = b"", b""
    for t, (ext, langs) in items:
        recs += struct.pack(">4sH", t.encode("ascii"), head + len(data))
        data += script(ext, langs)
    return struct.pack(">HHH", 1, 0, len(items)) + recs + data


def _fonts_49(out: Path) -> None:
    names = [".notdef", "space", *(f"x{g:03d}" for g in range(2, N49))]
    for i, scripts in enumerate(JSTF_FONTS):
        data = _bytes(_builder(f"u49-jstf-{i}", names, {0x20: "space", 0x640: "x002"}))
        _save_raw(data, {"JSTF": _jstf_raw(scripts)}, out / f"u49-jstf-{i}.ttf")


def _fonts_51(out: Path) -> None:
    names, cmap = _latin()
    names = names + ["A.alt", "f_i", "a.sc", "uni0410", "zero.tf"]
    _save(_builder("u51-names", names, cmap), out / "u51-names.ttf")


def build_fonts(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _fonts_40(out)
    _fonts_41(out)
    _fonts_44(out)
    _fonts_45(out)
    _fonts_46(out)
    _fonts_47(out)
    _fonts_49(out)
    _fonts_51(out)


# --------------------------------------------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------------------------------------------


def _font_opts(
    rng: random.Random, upem: int = 1000, vf: bool = False
) -> dict[str, object]:
    """Font settings that none of these notes is about."""
    opts: dict[str, object] = {}
    r = rng.random()
    if r < 0.3:
        opts["scale"] = rng.choice((upem, 2 * upem, 512, 1536, 2000, 999, 4096))
    elif r < 0.45:
        opts["scale"] = (
            f"{rng.choice((1000, 777, 2048))},{rng.choice((1000, 1500, 333))}"
        )
    if rng.random() < 0.3:
        opts["ppem"] = f"{rng.choice((12, 16, 24))},{rng.choice((12, 16, 24))}"
    if rng.random() < 0.15:
        opts["bold"] = f"{rng.choice(('0.02', '0.05'))},{rng.choice(('0', '0.03'))}"
    if vf and rng.random() < 0.5:
        opts["var"] = f"wght={rng.choice((100, 300, 700, 900))}"
    return opts


def gen_40a(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 40a: hb_style_get_value(OPTICAL_SIZE) from OS/2 version 5 bounds is in points (their average / 20).

    Inside: a version 5 OS/2 table with valid bounds is the source (no `opsz` axis, no ptem, no STAT `opsz`).
    Neighbours on which every release agrees: ptem set (b:ptem), an `opsz` fvar axis (b:fvar), a STAT `opsz`
    value (b:stat), a GPOS `size` feature with an older OS/2 or rejected bounds (b:size), neither (b:default, 12
    points), rejected bounds (b:bad-bounds), and other style tags of the same fonts (b:other-tag).
    """
    v5 = [synth / f"u40a-v5-{i}.ttf" for i in range(len(OPSZ_V5))]
    kinds = ["in"] * 8 + [
        "b:ptem",
        "b:fvar",
        "b:stat",
        "b:size",
        "b:default",
        "b:bad-bounds",
        "b:other-tag",
    ] * 2
    for i in range(n):
        kind = rng.choice(kinds)
        opts = _font_opts(rng)
        args = [OPSZ]
        if kind == "in":
            font = v5[i % len(v5)]
        elif kind == "b:ptem":
            font = rng.choice(v5)
            opts["ptem"] = rng.choice(("9", "10.5", "12", "36", "72", "6.25"))
        elif kind == "b:fvar":
            font = synth / "u40a-v5fvar.ttf"
            if rng.random() < 0.7:
                opts["var"] = f"opsz={rng.choice((6, 9, 12, 18, 36, 72))}"
        elif kind == "b:stat":
            font = synth / f"u40a-v5stat-{rng.randrange(3)}.ttf"
        elif kind == "b:size":
            font = rng.choice(
                [synth / f"u40a-v4size-{k}.ttf" for k in range(len(OPSZ_SIZE))]
                + [synth / f"u40a-v5bad-{k}.ttf" for k in range(1, len(OPSZ_BAD), 2)]
            )
        elif kind == "b:default":
            font = synth / f"u40a-v4-{rng.randrange(3)}.ttf"
        elif kind == "b:bad-bounds":
            font = synth / f"u40a-v5bad-{rng.randrange(0, len(OPSZ_BAD), 2)}.ttf"
        else:
            font = rng.choice(v5)
            args = [rng.choice((WGHT, WDTH, ITAL, SLNT))]
        yield api_case("40a", font, "style", args, nb=kind, drv="meta", **opts)


def gen_40b(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 40b: the slant angle hb_style_get_value() takes from fvar or STAT now includes the synthetic slant.

    Inside: SLANT_ANGLE from a `slnt` fvar axis (its default or a set coordinate) or from a STAT `slnt` value, with
    a nonzero synthetic slant. Neighbours on which every release agrees: the same fonts without synthetic slant
    (b:no-slant), the angle from `post`, which 14.3.0 already composes with the synthetic slant (b:post), and other
    style tags with synthetic slant (b:other-tag). Angles and slants are chosen so that the C library's tanf and
    atanf give the same bits on every machine (see ROBUST_ANGLES); SLANT_RATIO, the tangent of the composed angle,
    is left out for the same reason.
    """
    fvar = [synth / f"u40b-fvar-{i}.ttf" for i in range(len(SLANT_FVAR))]
    stat = [synth / f"u40b-stat-{i}.ttf" for i in range(len(SLANT_STAT))]
    post = [synth / f"u40b-post-{i}.ttf" for i in range(len(SLANT_POST))]
    robust = [(f, a, None) for f, (a, _) in zip(fvar, SLANT_FVAR) if a in ROBUST_ANGLES]
    robust += [
        (f, a, None) for f, (a, _) in zip(stat, SLANT_STAT) if a in ROBUST_ANGLES
    ]
    robust += [(f, a, a) for f in fvar for a in ROBUST_ANGLES]
    kinds = ["in"] * 6 + ["b:no-slant", "b:post", "b:other-tag"] * 2
    for i in range(n):
        kind = rng.choice(kinds)
        opts: dict[str, object] = {}
        args = [SLNT]
        if kind == "in":
            font, angle, coord = (
                robust[i % len(robust)] if rng.random() < 0.5 else rng.choice(robust)
            )
            if coord is not None:
                opts["var"] = f"slnt={coord!r}"
            opts["slant"] = slant_for(angle, rng.choice(RATIO_TARGETS))
        elif kind == "b:no-slant":
            font = rng.choice(fvar + stat)
            if font in fvar and rng.random() < 0.5:
                opts["var"] = f"slnt={rng.choice((-15, -10, -4.5, 0, 6, 12))}"
            if rng.random() < 0.3:
                opts["slant"] = "0"
        elif kind == "b:post":
            k = rng.randrange(len(post))
            font = post[k]
            opts["slant"] = slant_for(SLANT_POST[k], rng.choice(RATIO_TARGETS))
        else:
            font = rng.choice(fvar + stat)
            opts["slant"] = rng.choice(SYNTH_SLANTS)
            args = [rng.choice((WGHT, WDTH, ITAL, OPSZ))]
        if rng.random() < 0.3:
            opts["scale"] = rng.choice((2048, 1000, 600))
        yield api_case("40b", font, "style", args, nb=kind, drv="meta", **opts)


def gen_40c(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 40c: hb_style_get_value() skips STAT values flagged OLDER_SIBLING_FONT_ATTRIBUTE.

    Inside: the first STAT value (formats 1 to 3, table order) of the queried axis carries the older-sibling flag,
    with or without elidable; the function then takes the next unflagged value, or the OS/2, head or post polyfill.
    Neighbours on which every release agrees: the first value only elidable (b:elidable), an older-sibling value
    after the first unflagged one (b:sibling-later), no flagged value for the axis (b:no-sibling), and an fvar axis
    of the same tag, which wins over STAT (b:fvar). No synthetic slant (unit 40b) and no OS/2 version 5 (unit 40a);
    format 4 values are left out: 15.2.0 starts using them, which the note does not say.
    """
    pool: dict[str, list[tuple[Path, int]]] = {}
    for spec in STAT_FONTS:
        for a in STAT_AXES:
            label = stat_label(spec["axes"], a)
            if label:
                pool.setdefault(label, []).append((synth / spec["name"], tag(a)))
    pool["b:fvar"] = [(synth / "u40c-fvar.ttf", WGHT), (synth / "u40c-fvar.ttf", WDTH)]
    kinds = ["in"] * 6 + ["b:elidable", "b:sibling-later", "b:no-sibling", "b:fvar"] * 2
    kinds = [k for k in kinds if pool.get(k)]
    for i in range(n):
        kind = rng.choice(kinds)
        font, t = (
            pool[kind][i % len(pool[kind])] if kind == "in" else rng.choice(pool[kind])
        )
        opts = _font_opts(rng)
        opts.pop("bold", None)
        if kind == "b:fvar" and rng.random() < 0.5:
            opts["var"] = f"wght={rng.choice((200, 700))},wdth={rng.choice((75, 90))}"
        yield api_case("40c", font, "style", [t], nb=kind, drv="meta", **opts)


def gen_41(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 41: hb_face_collect_unicodes() collects every code point of cmap format 13 groups.

    Inside: the chosen subtable is format 13 ((3,10), (0,6) or (0,4)) and a group spans more code points than the
    glyphs after its glyph (glyph + last - first >= glyph count), which 14.3.0 cut short. Neighbours on which every
    release agrees: format 13 groups that fit (b:f13-short), a format 13 group whose glyph is past the end of the
    font (b:f13-glyph-past-end) or is glyph 0 (b:f13-notdef), both beside fitting groups, format 12 with every
    glyph inside the font (b:f12), and format 13 present but a (3,10) format 12 subtable chosen (b:f13-not-chosen).
    Left out: format 12 groups that run past the glyph count, whose last code point 15.2.0 now drops, and
    hb_face_collect_nominal_glyph_mapping(), which 15.2.0 also changes; the note names neither.
    """
    del n
    for k, (role, _, _) in enumerate(CMAP_FACES):
        yield api_case(
            "41", synth / CMAP_FILE, "unicodes", [], nb=role, drv="meta", idx=k
        )


def gen_44a(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 44a: the fallback vertical descender of a font without vhea is the synthesized descender.

    Inside: VERTICAL_DESCENDER on a font without vhea (14.3.0 gave x_scale / 2, now x_scale / 2 - x_scale).
    Neighbours on which every release agrees: the same tag on fonts with vhea (b:vhea), and the vertical ascender
    (b:v-ascender), vertical line gap (b:v-line-gap) and horizontal descender (b:h-descender) of fonts without vhea.
    """
    novhea = [f for name, f in sorted(noto.items()) if name != "NotoSansKR-Regular"]
    novhea_synth = [(synth / f"u44a-novhea-{u}.ttf", u) for u in NOVHEA_UPEM]
    vhea = [(noto["NotoSansKR-Regular"], 1000)] + [
        (synth / f"u44a-vhea-{i}.ttf", 1000) for i in range(len(VHEA))
    ]
    fonts = [(f, 1000) for f in novhea] + novhea_synth
    kinds = ["in"] * 6 + ["b:vhea", "b:v-ascender", "b:v-line-gap", "b:h-descender"] * 2
    for i in range(n):
        kind = rng.choice(kinds)
        font, upem = vhea[i % len(vhea)] if kind == "b:vhea" else fonts[i % len(fonts)]
        args = {
            "in": [VDSC],
            "b:vhea": [VDSC],
            "b:v-ascender": [VASC],
            "b:v-line-gap": [VLGP],
        }.get(kind, [HDSC])
        path = font.path if isinstance(font, Font) else font
        opts = _font_opts(rng, upem, vf="VF" in path.name)
        if rng.random() < 0.2:
            opts["scale"] = rng.choice((1, 3, 1001, 2047, 65535, -1000, "-800,1000"))
        yield api_case("44a", font, "metric", args, nb=kind, drv="meta", **opts)


def gen_44b(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 44b: the fallback hanging baseline converts the OpenType script tag before choosing its glyph.

    Inside: HANGING, horizontal, a font without BASE, a script whose hanging baseline the fallback measures from a
    glyph the font has (old or new OpenType tag, or hb_script_t through the `2` entry point). Neighbours on which
    every release agrees: vertical text (b:vertical), scripts the fallback does not list (b:other-script), listed
    scripts whose glyph the font lacks (b:no-glyph), other baselines (b:other-baseline), and fonts whose BASE table
    has the script's hanging baseline (b:base). Scales are whole multiples of the units per em, so that the glyph
    extents do not depend on the 15.2.0 extents rounding (unit 38); BASE tables list old script tags only, so that
    15.2.0's choice of a BASE-listed tag in the `2` entry points (a change no note states) does not apply.
    """
    plain = [
        (noto[k], 1000, {h[2] for h in HANGING if noto[k].has(h[2])})
        for k in ("NotoSansBengali-Regular", "NotoSansDevanagari-Regular")
    ]
    plain += [
        (synth / s["name"], s["upem"], set(s["heights"]))
        for s in HANG_FONTS
        if not s["base"]
    ]
    based = [(synth / s["name"], s["upem"], s) for s in HANG_FONTS if s["base"]]
    kinds = ["in"] * 7 + [
        "b:vertical",
        "b:other-script",
        "b:no-glyph",
        "b:other-baseline",
        "b:base",
    ] * 2
    for i in range(n):
        kind = rng.choice(kinds)
        opts: dict[str, object] = {}
        tags = [HANG]
        if kind == "b:base":
            font, upem, spec = rng.choice(based)
            chosen = rng.choice(sorted(spec["base"]))
            script = next(h for h in HANGING if h[1][0] == chosen)
            iso, ot = script[0], script[1][0]
            if rng.random() < 0.5:
                opts["stag"] = ot
            else:
                opts["script"] = iso
            opts["dir"] = rng.choice(("ltr", "rtl"))
        else:
            font, upem, have = (
                plain[i % len(plain)] if kind == "in" else rng.choice(plain)
            )
            listed = [h for h in HANGING if h[2] in have]
            missing = [h for h in HANGING if h[2] not in have]
            if kind == "b:other-script":
                iso, ots = rng.choice(OTHER_SCRIPTS)
            elif kind == "b:no-glyph":
                if not missing:
                    font, upem, have = plain[0]
                    missing = [h for h in HANGING if h[2] not in have]
                iso, ots, _ = rng.choice(missing)
            else:
                iso, ots, _ = rng.choice(listed)
            if rng.random() < 0.4:
                opts["script"] = iso
                if rng.random() < 0.5:
                    opts["lang"] = rng.choice(
                        ("en", "bn", "hi", "und", "ne", "sa", "fr")
                    )
            else:
                opts["stag"] = rng.choice(ots)
                if rng.random() < 0.3:
                    opts["ltag"] = rng.choice(("BEN ", "HIN ", "dflt", "SAN "))
            opts["dir"] = (
                rng.choice(("ttb", "btt"))
                if kind == "b:vertical"
                else rng.choice(("ltr", "ltr", "rtl"))
            )
            if kind == "b:other-baseline":
                tags = rng.sample(
                    [ROMN, IDEO, IDTP, ICFB, ICFT, MATH], k=rng.choice((1, 2))
                )
        if rng.random() < 0.4:
            opts["scale"] = upem * rng.choice((1, 2, 3))
        yield api_case("44b", font, "baseline", tags, nb=kind, drv="meta", **opts)


def gen_45(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 45: alternates collected from AlternateSubst and SingleSubst format 1 lookups.

    Inside: an AlternateSubst lookup (alternate counts are now keyed by the glyph; 14.3.0 keyed each alternate
    after the first by glyph + (index << 24)), plain, in an Extension, or in two subtables that share a glyph, and
    SingleSubst format 1 lookups (plain or in an Extension); sometimes with the count map seeded, as the API
    allows. Neighbours on which every release agrees: SingleSubst format 2 (b:single2), MultipleSubst with
    one-glyph sequences (b:multiple), and ligature lookups (b:other-type).
    """
    labels = {
        "alt": "in",
        "alt1": "in",
        "alt-ext": "in",
        "alt-2sub": "in",
        "sgl1": "in",
        "sgl1-ext": "in",
        "sgl2": "b:single2",
        "mul": "b:multiple",
        "lig": "b:other-type",
    }
    pool: dict[str, list[tuple[int, int, tuple]]] = {}
    for f, lookups in enumerate(ALTS_FONTS):
        for k, look in enumerate(lookups):
            pool.setdefault(labels[look[0]], []).append((f, k, look))
    kinds = ["in"] * 6 + ["b:single2", "b:multiple", "b:other-type"] * 2
    for i in range(n):
        kind = rng.choice(kinds)
        f, k, (lk, data) = (
            pool[kind][i % len(pool[kind])] if kind == "in" else rng.choice(pool[kind])
        )
        opts = {}
        if rng.random() < 0.25 and lk not in ("lig",):
            keys = list(data[0] if lk == "alt-2sub" else data) if lk != "lig" else []
            if keys:
                seeds = rng.sample(keys, k=min(len(keys), rng.randrange(1, 3)))
                opts["seed"] = ",".join(f"{g}:{rng.randrange(1, 4)}" for g in seeds)
        yield api_case(
            "45", synth / f"u45-alts-{f}.ttf", "alts", [k], nb=kind, drv="meta", **opts
        )


def gen_46(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 46: hb_face_create_or_fail() accepts a face index with named-instance bits (the top 16 bits).

    Inside: named-instance bits set and a face index (low 16 bits) inside the file. Neighbours on which every
    release agrees: no named-instance bits (b:no-bits), and a face index past the last face, with named-instance
    bits (b:past-end) or without (b:past-end-no-bits). hb_face_create_from_file_or_fail(), which calls the fixed
    function, is left out: the note names hb_face_create_or_fail() only.
    """
    files = [
        (noto[k].path, 1, i)
        for k, i in (
            ("NotoSans-VF", 9),
            ("NotoSerif-VF", 9),
            ("NotoSansHebrew-Regular", 0),
            ("NotoSansKR-Regular", 0),
            ("NotoSansArabic-Regular", 0),
        )
    ]
    files += [
        (synth / f"u46-coll-{i}.ttc", len(m), max(m)) for i, m in enumerate(COLLECTIONS)
    ]
    files += [
        (synth / f"u40b-fvar-{i}.ttf", 1, 3 if SLANT_FVAR[i][1] else 2)
        for i in range(3)
    ]
    kinds = ["in"] * 6 + ["b:no-bits", "b:past-end", "b:past-end-no-bits"] * 2
    for i in range(n):
        kind = rng.choice(kinds)
        path, count, instances = (
            files[i % len(files)] if kind == "in" else rng.choice(files)
        )
        inst = rng.randrange(1, instances + 3)
        if kind == "in":
            idx = (inst << 16) | rng.randrange(count)
        elif kind == "b:no-bits":
            idx = rng.randrange(count)
        elif kind == "b:past-end":
            idx = (inst << 16) | rng.randrange(count, count + 3)
        else:
            idx = rng.randrange(count, count + 3)
        yield api_case("46", path, "faceorfail", [], nb=kind, drv="meta", idx=idx)


def gen_47b(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 47b: hb_font_set_face() does nothing.

    Inside: a mutable font gets another face (another file or face index) or NULL; the case prints whether the
    font kept its face, that face's upem and glyph count, nominal glyphs, advances and a shaped run. Neighbours on
    which every release agrees: the font's own face (b:same-face) and an immutable font (b:immutable).
    """
    fonts = [synth / "u47b-a.ttf", synth / "u47b-b.ttf", synth / "u47b-c.ttf"]
    fonts += [
        noto[k].path
        for k in (
            "NotoSans-VF",
            "NotoSerif-VF",
            "NotoSansHebrew-Regular",
            "NotoSansArabic-Regular",
        )
    ]
    words = [
        "AVATAR",
        "TOWER",
        "FIT",
        "THE",
        "LTWA",
        "BAD",
        "ZEBRA",
        "OFFICE",
        "TH",
        "AW",
    ]
    kinds = ["in"] * 6 + ["b:same-face", "b:immutable"] * 2
    for i in range(n):
        kind = rng.choice(kinds)
        a = fonts[i % len(fonts)]
        text = [ord(c) for c in rng.choice(words)]
        opts: dict[str, object] = {}
        if kind == "b:same-face":
            opts["same"] = 1
        else:
            if kind == "b:immutable":
                opts["imm"] = 1
            if rng.random() < 0.15:
                opts["face2"] = "null"
            else:
                opts["face2"] = rng.choice([f for f in fonts if f != a])
                if "VF" in str(opts["face2"]) and rng.random() < 0.3:
                    opts["idx2"] = rng.choice((0x10000, 0x30000))
        if "VF" in a.name and rng.random() < 0.3:
            opts["var"] = f"wght={rng.choice((300, 700))}"
        if rng.random() < 0.3:
            opts["scale"] = rng.choice((2048, 500, 1000))
        yield api_case("47b", a, "setface", text, nb=kind, drv="meta", **opts)


def gen_48(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 48: hb_font_create_without_funcs_or_fail() (probe hbapi48, drv "api48").

    A pure API addition: every case is inside. Faces from single fonts and collections, with and without
    named-instance bits; the probe prints the new font's initial properties, what queries answer with no font
    functions installed, and, with funcs=1, a run shaped with client font functions installed afterwards.
    """
    files = [
        (noto[k].path, 1, i)
        for k, i in (
            ("NotoSans-VF", 9),
            ("NotoSerif-VF", 9),
            ("NotoSansHebrew-Regular", 0),
            ("NotoSansKR-Regular", 0),
            ("NotoSansBengali-Regular", 0),
        )
    ]
    files += [
        (synth / f"u46-coll-{i}.ttc", len(m), max(m)) for i, m in enumerate(COLLECTIONS)
    ]
    files += [
        (synth / f"u40b-fvar-{i}.ttf", 1, 3 if SLANT_FVAR[i][1] else 2)
        for i in range(len(SLANT_FVAR))
    ]
    files += [(synth / "u40a-v5fvar.ttf", 1, 3), (synth / "u47b-b.ttf", 1, 0)]
    words = ["Hello", "AVATAR", "office", "TOWER", "fi fl"]
    for i in range(n):
        path, count, instances = files[i % len(files)]
        idx = rng.randrange(count)
        if instances and rng.random() < 0.6:
            idx |= rng.randrange(1, instances + 2) << 16
        opts = {}
        text: list[int] = []
        if rng.random() < 0.4:
            opts["funcs"] = 1
            text = [ord(c) for c in rng.choice(words)]
        yield api_case(
            "48", path, "create", text, nb="in", drv="api48", idx=idx, **opts
        )


def gen_49(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 49: hb_ot_layout_get_extender_glyphs() (probe hbapi49, drv "api49").

    A pure API addition: every case is inside. JSTF version 1.0 tables with ExtenderGlyph lists of 0 to 12
    glyphs, scripts without an ExtenderGlyph table, language systems; calls page through the list (start offsets
    inside and past the end, counts larger and smaller than what is left), count-only calls with NULL pointers or a
    zero count, scripts the table does not list, with and without a language. Every case ends with a call that
    finds glyphs (`also`: a script with extender glyphs in that font, start 0, room for 16), so a function that
    returns 0 and reports nothing fails every case, whatever the calls before it expect. Left out: a font without
    JSTF (`x:no-jstf`: no call on its face finds anything, so a function that does nothing passes it), a NULL glyph
    array with a nonzero count (15.2.0 leaves the count as given, which is not "the number returned"), scripts with
    two OpenType tags (the tag the function picks is not stated), private-use language subtags that select a
    script, and JSTF 1.1 (the 24-bit tables the notes leave out).
    """
    scripts = [
        "Arab",
        "Latn",
        "Mong",
        "Syrc",
        "Hebr",
        "Thaa",
        "Copt",
        "Grek",
        "Armn",
        "Cyrl",
        "Geor",
        "Ethi",
        "Tfng",
    ]
    langs = [None, None, "ar", "fa", "ur", "en", "he", "syr", "dv", "hy", "ru"]
    fonts = [synth / f"u49-jstf-{i}.ttf" for i in range(len(JSTF_FONTS))]
    for i in range(n):
        k = i % len(fonts)
        font = fonts[k] if rng.random() < 0.9 else noto["NotoSansArabic-Regular"].path
        listed = [t[0].upper() + t[1:] for t in JSTF_FONTS[k]]
        opts: dict[str, object] = {
            "script": rng.choice(listed) if rng.random() < 0.7 else rng.choice(scripts)
        }
        lang = rng.choice(langs)
        if lang:
            opts["lang"] = lang
        calls: list[int] = []
        mode = rng.choice(("page", "page", "count", "null", "past"))
        if mode == "page":
            size = rng.choice((1, 2, 3, 5, 16))
            start = 0
            for _ in range(rng.randrange(1, 5)):
                calls += [start, size]
                start += size
        elif mode == "count":
            calls = [0, 0] if rng.random() < 0.5 else [rng.randrange(0, 4), 0]
            if rng.random() < 0.5:
                opts["glyphs"] = "null"
        elif mode == "null":
            calls = [rng.randrange(0, 4), 0xFFFFFFFF]
            opts["glyphs"] = "null"
        else:
            calls = [rng.choice((5, 12, 13, 100, 0xFFFF)), rng.choice((1, 4, 64))]
        if mode == "null" and rng.random() < 0.5:
            opts.pop("glyphs")
        # The closing call that finds glyphs, chosen without drawing from rng (the rest of the stream stays as it
        # was): a script of this font whose ExtenderGlyph list is not empty.
        finds = [s for s, (ext, _) in sorted(JSTF_FONTS[k].items()) if ext]
        nb = "x:no-jstf" if font == noto["NotoSansArabic-Regular"].path else "in"
        if nb == "in":
            also = finds[(i // len(fonts)) % len(finds)]
            opts["also"] = also[0].upper() + also[1:]
        yield api_case("49", font, "ext", calls, nb=nb, drv="api49", **opts)


_GLYPH_NAMES = [chr(c) for c in range(0x41, 0x5B)] + [
    "space",
    "A.alt",
    "f_i",
    "a.sc",
    "zero.tf",
    ".notdef",
]


def _text_glyphs(rng: random.Random, n: int, with_font: bool) -> str:
    items = []
    for _ in range(n):
        if with_font and rng.random() < 0.7:
            g = rng.choice(_GLYPH_NAMES)
        else:
            g = rng.choice(
                (
                    str(rng.randrange(0, 40)),
                    f"gid{rng.randrange(0, 40)}",
                    "uni0041",
                    "uni005A",
                )
            )
        s = g
        if rng.random() < 0.85:
            s += f"={rng.randrange(0, 50)}"
        if rng.random() < 0.3:
            s += f"@{rng.randrange(-300, 300)},{rng.randrange(-300, 300)}"
        if rng.random() < 0.85:
            s += f"+{rng.randrange(-50, 2500)}"
            if rng.random() < 0.3:
                s += f",{rng.randrange(-900, 900)}"
        if rng.random() < 0.2:
            s += f"#{rng.randrange(0, 4)}"
        if rng.random() < 0.1:
            x_off, y_off, x_adv, y_adv = (
                rng.randrange(-50, 50),
                rng.randrange(0, 800),
                rng.randrange(0, 600),
                -rng.randrange(0, 800),
            )
            s += f"<{x_off},{y_off},{x_adv},{y_adv}>"
        items.append(s)
    return "[" + "|".join(items) + "]"


def _json_glyphs(rng: random.Random, n: int, with_font: bool) -> str:
    items = []
    for _ in range(n):
        if with_font and rng.random() < 0.6:
            g = '"' + rng.choice(_GLYPH_NAMES) + '"'
        else:
            g = str(rng.randrange(0, 40))
        keys = [f'"g":{g}']
        for k, lo, hi in (
            ("cl", 0, 50),
            ("dx", -300, 300),
            ("dy", -300, 300),
            ("ax", -50, 2500),
            ("ay", -900, 900),
        ):
            if rng.random() < 0.8:
                keys.append(f'"{k}":{rng.randrange(lo, hi)}')
        if rng.random() < 0.2:
            keys.append(f'"fl":{rng.randrange(0, 4)}')
        if rng.random() < 0.2:
            rng.shuffle(keys)
        sep = rng.choice((",", ",", ", "))
        items.append("{" + sep.join(keys) + "}")
    return "[" + ",".join(items) + "]"


def _text_unicode(rng: random.Random, n: int) -> str:
    items = []
    for _ in range(n):
        cp = rng.choice(
            (
                rng.randrange(0x20, 0x7F),
                rng.randrange(0x400, 0x500),
                rng.randrange(0x1F600, 0x1F650),
            )
        )
        s = f"{rng.choice('Uu')}{'+' if rng.random() < 0.8 else ''}{cp:0{rng.choice((4, 4, 5))}X}"
        if rng.random() < 0.8:
            s += f"={rng.randrange(0, 50)}"
        items.append(s)
    return "<" + "|".join(items) + ">"


def _json_unicode(rng: random.Random, n: int) -> str:
    items = []
    for _ in range(n):
        keys = [f'"u":{rng.randrange(0x20, 0x2000)}']
        if rng.random() < 0.8:
            keys.append(f'"cl":{rng.randrange(0, 50)}')
        if rng.random() < 0.2:
            keys.reverse()
        items.append("{" + ",".join(keys) + "}")
    return "[" + ",".join(items) + "]"


def _u51_closing(seed: int, glyphs: bool, fmt: str) -> tuple[bytes, str]:
    """Well-formed input for the probe's closing call (`then`, `thenfmt`): one to three items in text or JSON,
    numeric glyph IDs so that no font is needed. Drawn from a stream of its own, so the rest of the unit's
    candidates stay as they were."""
    r = random.Random(f"u51-closing:{seed}")
    fmt = fmt if fmt in ("text", "json") else r.choice(("text", "json"))
    items = []
    for cl in range(r.randint(1, 3)):
        g, adv, cp = r.randrange(1, 40), r.randrange(0, 1200), r.randrange(0x41, 0x5B)
        if fmt == "json" and glyphs:
            items.append(f'{{"g":{g},"cl":{cl},"ax":{adv}}}')
        elif fmt == "json":
            items.append(f'{{"u":{cp},"cl":{cl}}}')
        else:
            items.append(f"{g}={cl}+{adv}" if glyphs else f"U+{cp:04X}={cl}")
    if fmt == "json":
        text = "[" + ",".join(items) + "]"
    elif glyphs:
        text = "[" + "|".join(items) + "]"
    else:
        text = "<" + "|".join(items) + ">"
    return text.encode("ascii"), fmt


def gen_51(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 51: hb_buffer_deserialize_glyphs2() and hb_buffer_deserialize_unicode2() (probe hbapi51, drv "api51").

    A pure API addition: every case is inside. Text and JSON input, whole or cut short or broken at some byte
    (bad syntax, an unknown glyph name), buf_len -1, exact, shorter, one past the text (its NUL) and 0, a NULL
    buf_consumed, a NULL font (nofont=1), input appended after earlier content, the empty (immutable) buffer, and format
    values that are neither text nor JSON. Every case ends with a closing call of the same function (`then`,
    `thenfmt`) that parses one to three well-formed items into a new buffer, with a buf_consumed pointer, so a
    function that returns false and consumes nothing fails every case, whatever the first call expects. Numbers stay
    well inside 32 bits: 15.2.0 parses out-of-range numbers differently, which no note states.
    """
    font = synth / "u51-names.ttf"
    junk = [
        "$",
        "!",
        "~",
        "]",
        "|",
        "=",
        "@",
        "+",
        ",",
        "x",
        "{",
        "}",
        ":",
        '"',
        " ",
        "\x7f",
        "-",
        "#",
        "<",
    ]
    for i in range(n):
        glyphs = rng.random() < 0.6
        fmt = (
            rng.choice(("text", "text", "json", "json"))
            if rng.random() < 0.95
            else rng.choice(("0", "1", "1414416728"))
        )
        with_font = glyphs and rng.random() < 0.8
        count = rng.randrange(1, 7)
        if glyphs:
            text = (_json_glyphs if fmt == "json" else _text_glyphs)(
                rng, count, with_font
            )
        else:
            text = (
                _json_unicode(rng, count)
                if fmt == "json"
                else _text_unicode(rng, count)
            )
        if fmt == "text" and rng.random() < 0.15:
            text = text[1:]  # the opening bracket is optional
        data = text.encode("ascii")
        opts: dict[str, object] = {"fmt": fmt}
        r = rng.random()
        if r < 0.25:
            pos = rng.randrange(0, len(data))
            data = data[:pos] + rng.choice(junk).encode("ascii") + data[pos + 1 :]
        elif r < 0.35 and glyphs:
            data = data.replace(b"A", b"Q_Q", 1) if b"A" in data else data
        elif r < 0.4:
            data = data + rng.choice((b" ", b"]", b"x", b"\n"))
        r = rng.random()
        if r < 0.25:
            opts["len"] = -1
            if rng.random() < 0.3:
                data = data + b"\0" + rng.choice((b"[A]", b"junk", b"<U+41>"))
        elif r < 0.45:
            opts["len"] = rng.randrange(0, len(data))
        elif r < 0.5:
            opts["len"] = len(data) + 1
        if rng.random() < 0.2:
            opts["cons"] = "null"
        if glyphs and not with_font:
            opts["nofont"] = 1
        if rng.random() < 0.12:
            pre = (
                (_json_glyphs if fmt == "json" else _text_glyphs)(rng, 2, with_font)
                if glyphs
                else (_json_unicode(rng, 2) if fmt == "json" else _text_unicode(rng, 2))
            )
            opts["pre"] = ",".join(f"{b:X}" for b in pre.encode("ascii"))
        elif rng.random() < 0.03:
            opts["empty"] = 1
        closing, closing_fmt = _u51_closing(i, glyphs, fmt)
        opts["then"] = ",".join(f"{b:X}" for b in closing)
        opts["thenfmt"] = closing_fmt
        yield api_case(
            "51",
            font,
            "glyphs2" if glyphs else "unicode2",
            list(data),
            nb="in",
            drv="api51",
            **opts,
        )


UNITS = {
    "40a": gen_40a,
    "40b": gen_40b,
    "40c": gen_40c,
    "41": gen_41,
    "44a": gen_44a,
    "44b": gen_44b,
    "45": gen_45,
    "46": gen_46,
    "47b": gen_47b,
    "48": gen_48,
    "49": gen_49,
    "51": gen_51,
}

PER_UNIT = {
    "40a": 600,
    "40b": 600,
    "40c": 500,
    "41": len(CMAP_FACES),
    "44a": 600,
    "44b": 800,
    "45": 500,
    "46": 500,
    "47b": 500,
    "48": 300,
    "49": 400,
    "51": 800,
}

W_TARGETS = {
    "40a": ["b:size", "b:default", "b:bad-bounds"],
    "40b": ["b:post"],
    "40c": ["b:elidable"],
    "41": ["b:f13-glyph-past-end"],
    "44a": ["b:v-ascender"],
    "44b": ["b:base"],
    "45": ["b:multiple"],
    "46": ["b:past-end"],
}
