"""Candidates and fonts for family F4: legacy `kern`, Apple `kerx`, `morx`, `mort` and `trak` (units 20 to 26).

Runs inside the pipeline image: cases.py imports the generators, synth_fonts.py calls `build_fonts`. Every font is
ours: box outlines, the Latin capitals, a few combining marks and the one table a unit needs. fontTools 4.69.1 has no
`kerx` module, keeps AAT `kern` formats other than 0 as raw bytes and lays out `morx` state arrays its own way, so the
AAT tables here are assembled with struct from the Apple TrueType Reference Manual (`kern`, `kerx`, `morx`, `mort`,
`feat`) and checked against HarfBuzz's parsers (hb-aat-layout-*.hh, hb-ot-kern-table.hh). Development tooling, never
shipped.

Labels (`nb`): `in` is inside the unit's stated condition; `b:<name>` is a neighbour one stated condition away, which
every release must lay out alike. Units 21, 22 and 23 use the fonts synth_fonts.py builds; these generators replace
the spike's `gen_aat` labels with short boundary names.
"""

from __future__ import annotations

import random
import struct
from collections.abc import Callable, Iterator
from pathlib import Path

from casekit import Font, case
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables.DefaultTable import DefaultTable

UPEM = 1000
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ACUTE, GRAVE, MACRON, DOTBELOW = 0x0301, 0x0300, 0x0304, 0x0323
MARKS = {
    ACUTE: "acutecomb",
    GRAVE: "gravecomb",
    MACRON: "macroncomb",
    DOTBELOW: "dotbelowcomb",
}
RESET = -0x8000  # pair value 0x8000: resets cross-stream kerning
NO_ACTION = 0xFFFF  # `kerx` and `morx` entries: no action
DELETED = 0xFFFF  # AAT deleted-glyph sentinel
END = -1  # 0xFFFF ends a `kerx` format 1 value list
CROSS_KERX, VERTICAL_KERX = 0x40000000, 0x80000000
# Extended state tables: newState is a state index.
PUSH, DONT_ADVANCE, KERX_RESET = 0x8000, 0x4000, 0x2000
MARK_GLYPH = 0x8000  # `kerx` format 4: remember the current glyph
MARK_FIRST, MARK_LAST = 0x8000, 0x2000  # `mort` rearrangement
INSERT_BEFORE = 0x0800  # `morx` insertion: current-glyph list goes before it

SCALES = (None, None, 1000, 2000, 500, 1500, 3000, 750, 1234)


# --------------------------------------------------------------------------------------------------------------
# Glyphs and fonts


class Glyphs:
    """Glyph order of one font: .notdef, space, A-Z, optional combining marks, then unencoded extras."""

    def __init__(
        self, marks: bool = False, extra: tuple[tuple[str, int], ...] = ()
    ) -> None:
        self.names = [".notdef", "space", *LETTERS]
        self.cmap = {0x20: "space", **{ord(c): c for c in LETTERS}}
        self.adv = {
            ".notdef": 500,
            "space": 250,
            **{c: 500 + 20 * i for i, c in enumerate(LETTERS)},
        }
        if marks:
            for cp, name in MARKS.items():
                self.names.append(name)
                self.cmap[cp] = name
                self.adv[name] = 0
        for name, width in extra:
            self.names.append(name)
            self.adv[name] = width

    def g(self, name: str) -> int:
        return self.names.index(name)

    def ids(self, letters: str) -> list[int]:
        return [self.g(c) for c in letters]


def _outline(width: int):
    pen = TTGlyphPen(None)
    right = max(width - 50, 150)
    pen.moveTo((50, 0))
    pen.lineTo((50, 700))
    pen.lineTo((right, 700))
    pen.lineTo((right, 0))
    pen.closePath()
    return pen.glyph()


def _save(
    out: Path, name: str, gl: Glyphs, tables: dict[str, bytes], fea: str = ""
) -> None:
    fb = FontBuilder(UPEM, isTTF=True)
    # Fixed `head` dates (FontBuilder stamps the current time), so every build writes the same bytes.
    fb.font["head"].created = fb.font["head"].modified = 3_786_825_600
    fb.setupGlyphOrder(gl.names)
    fb.setupCharacterMap(gl.cmap)
    fb.setupGlyf(
        {
            n: TTGlyphPen(None).glyph() if n == "space" else _outline(gl.adv[n])
            for n in gl.names
        }
    )
    fb.setupHorizontalMetrics({n: (gl.adv[n], 50) for n in gl.names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": name, "styleName": "Regular"})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    for tag, data in tables.items():
        table = DefaultTable(tag)
        table.data = data
        fb.font[tag] = table
    if fea:
        addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(out / f"{name}.ttf"))


# --------------------------------------------------------------------------------------------------------------
# Table assemblers (big-endian; offsets as the Apple manual and HarfBuzz define them)


def _bsearch(n: int, unit: int, wide: bool) -> bytes:
    """Binary-search header: 16-bit fields in `kern`, 32-bit in `kerx`."""
    p = 1 << (n.bit_length() - 1) if n else 0
    sel = p.bit_length() - 1 if n else 0
    return struct.pack(">IIII" if wide else ">HHHH", n, unit * p, sel, unit * (n - p))


def _pair_body(pairs: dict[tuple[int, int], int], wide: bool) -> bytes:
    """Format 0 body: sorted (left, right, value) records."""
    items = sorted(pairs.items())
    records = b"".join(
        struct.pack(">HHh", first, second, v) for (first, second), v in items
    )
    return _bsearch(len(items), 6, wide) + records


def _lookup8(first: int, values: list[int]) -> bytes:
    """AAT lookup table, format 8 (trimmed array): first glyph, count, one 16-bit value per glyph."""
    return struct.pack(">HHH", 8, first, len(values)) + struct.pack(
        f">{len(values)}H", *values
    )


def _range_lookup(mapping: dict[int, int], default: int = 0) -> bytes:
    lo, hi = min(mapping), max(mapping)
    return _lookup8(lo, [mapping.get(g, default) for g in range(lo, hi + 1)])


def _class_table(classes: dict[int, int]) -> bytes:
    """Class table of an old-style state table: first glyph, count, one byte per glyph (1, out of bounds, in gaps)."""
    lo, hi = min(classes), max(classes)
    data = struct.pack(">HH", lo, hi - lo + 1) + bytes(
        classes.get(g, 1) for g in range(lo, hi + 1)
    )
    return data + b"\0" * (len(data) % 2)


def _kern_ot(subtables: list[tuple[int, int, bytes]]) -> bytes:
    """OpenType `kern`, version 0. Coverage byte: 0x01 horizontal, 0x04 cross-stream."""
    out = struct.pack(">HH", 0, len(subtables))
    for fmt, coverage, body in subtables:
        out += struct.pack(">HHBB", 0, 6 + len(body), fmt, coverage) + body
    return out


def _kern_aat(subtables: list[tuple[int, int, bytes]]) -> bytes:
    """Apple `kern`, version 1.0. Coverage byte: 0x80 vertical, 0x40 cross-stream."""
    out = struct.pack(">II", 0x00010000, len(subtables))
    for fmt, coverage, body in subtables:
        out += struct.pack(">IBBH", 8 + len(body), coverage, fmt, 0) + body
    return out


def _kern_f2(
    head: int, left: dict[int, int], right: dict[int, int], rows: list[list[int]]
) -> bytes:
    """`kern` format 2. Offsets count from the subtable start (`head` header bytes); a left class value is the array
    offset plus row * rowWidth, a right one column * 2, so their sum addresses the value from the subtable start."""
    width = 2 * len(rows[0])
    lo_l, hi_l = min(left), max(left)
    lo_r, hi_r = min(right), max(right)
    left_off = head + 8
    right_off = left_off + 4 + 2 * (hi_l - lo_l + 1)
    array_off = right_off + 4 + 2 * (hi_r - lo_r + 1)
    out = struct.pack(">HHHH", width, left_off, right_off, array_off)
    out += struct.pack(">HH", lo_l, hi_l - lo_l + 1)
    out += b"".join(
        struct.pack(">H", array_off + width * left.get(g, 0))
        for g in range(lo_l, hi_l + 1)
    )
    out += struct.pack(">HH", lo_r, hi_r - lo_r + 1)
    out += b"".join(
        struct.pack(">H", 2 * right.get(g, 0)) for g in range(lo_r, hi_r + 1)
    )
    return out + b"".join(struct.pack(f">{len(r)}h", *r) for r in rows)


def _kern_f3(
    num_glyphs: int, left: dict[int, int], right: dict[int, int], rows: list[list[int]]
) -> bytes:
    """`kern` format 3: byte classes per glyph and byte indices into a list of values."""
    values = [0, *sorted({v for r in rows for v in r} - {0})]
    out = struct.pack(">HBBBB", num_glyphs, len(values), len(rows), len(rows[0]), 0)
    out += struct.pack(f">{len(values)}h", *values)
    out += bytes(left.get(g, 0) for g in range(num_glyphs))
    out += bytes(right.get(g, 0) for g in range(num_glyphs))
    out += bytes(values.index(v) for r in rows for v in r)
    return out + b"\0" * (len(out) % 2)


def _kerx(subtables: list[bytes]) -> bytes:
    return struct.pack(">HHI", 2, 0, len(subtables)) + b"".join(subtables)


def _kerx_sub(fmt: int, body: bytes, coverage: int = 0) -> bytes:
    """One `kerx` subtable: length, coverage (flags | format), tupleCount 0, body."""
    return struct.pack(">III", 12 + len(body), coverage | fmt, 0) + body


def _kerx_f2(
    left: dict[int, int], right: dict[int, int], rows: list[list[int]], spill: list[int]
) -> bytes:
    """`kerx` format 2: lookups give byte offsets into the array (row * rowWidth, column * 2). `spill` values follow the
    array; they are what an index-for-byte-offset reading of the same classes reaches past its end."""
    width = 2 * len(rows[0])
    lt = _range_lookup({g: width * r for g, r in left.items()})
    rt = _range_lookup({g: 2 * c for g, c in right.items()})
    left_off = 12 + 16
    right_off = left_off + len(lt)
    array_off = right_off + len(rt)
    cells = [v for r in rows for v in r] + spill
    return (
        struct.pack(">IIII", width, left_off, right_off, array_off)
        + lt
        + rt
        + struct.pack(f">{len(cells)}h", *cells)
    )


def _kerx_f6(
    left: dict[int, int], right: dict[int, int], rows: list[list[int]]
) -> bytes:
    """`kerx` format 6 with 16-bit values: row lookup gives row * columnCount, column lookup the column."""
    ncols = len(rows[0])
    rt = _range_lookup({g: ncols * r for g, r in left.items()})
    ct = _range_lookup(dict(right))
    row_off = 12 + 24
    col_off = row_off + len(rt)
    arr_off = col_off + len(ct)
    cells = [v for r in rows for v in r]
    head = struct.pack(">IHHIIII", 0, len(rows), ncols, row_off, col_off, arr_off, 0)
    return head + rt + ct + struct.pack(f">{len(cells)}h", *cells)


def _stx(
    n_classes: int,
    classes: dict[int, int],
    rows: list[list[int]],
    entries: list[bytes],
    field: Callable[[int], bytes],
    tail: bytes,
) -> bytes:
    """Extended state table (`kerx` formats 1 and 4, `morx`): STXHeader, one 32-bit subtable field computed from the
    offset of `tail`, class lookup (1, out of bounds, in gaps), 16-bit state array, entry table, then `tail`.
    Offsets count from the STXHeader."""
    cls = _range_lookup(classes, 1)
    cls += b"\0" * (-len(cls) % 4)
    states = b"".join(struct.pack(f">{n_classes}H", *row) for row in rows)
    states += b"\0" * (-len(states) % 4)
    ent = b"".join(entries)
    ent += b"\0" * (-len(ent) % 4)
    off_cls = 20
    off_states = off_cls + len(cls)
    off_ent = off_states + len(states)
    off_tail = off_ent + len(ent)
    head = struct.pack(">IIII", n_classes, off_cls, off_states, off_ent) + field(
        off_tail
    )
    return head + cls + states + ent + tail


def _st(
    n_classes: int,
    classes: dict[int, int],
    rows: list[list[int]],
    initial: int,
    entries: list[tuple[int, int, int | None]],
    lists: list[list[int]] | None = None,
) -> bytes:
    """Old-style state table (`kern` format 1 when `lists` is given, `mort`): STHeader, class table, 8-bit state array,
    entry table, value lists. Offsets count from the STHeader.

    `rows` are in physical order and `initial` is the row the state array offset names, state 0; rows before it are
    negative states. An entry is (target row, flags, value list or None): its newState is the byte offset of the
    target row, and for `kern` the byte offset of the value list fills the low 14 bits of the flags."""
    extra = 2 if lists is not None else 0
    cls = _class_table(classes)
    row_bytes = b"".join(bytes(r) for r in rows)
    row_bytes += b"\0" * (len(row_bytes) % 2)
    off_rows = 8 + extra + len(cls)
    off_ent = off_rows + len(row_bytes)
    off_val = off_ent + 4 * len(entries)
    starts, pos = [], off_val
    for values in lists or []:
        starts.append(pos)
        pos += 2 * len(values)
    ent = b"".join(
        struct.pack(
            ">HH",
            off_rows + target * n_classes,
            flags | (starts[li] if li is not None else 0),
        )
        for target, flags, li in entries
    )
    head = struct.pack(
        ">HHHH", n_classes, 8 + extra, off_rows + initial * n_classes, off_ent
    )
    vals = b""
    if lists is not None:
        head += struct.pack(">H", off_val)
        # Eight zero words after the lists: HarfBuzz checks as many values as there are glyphs on the stack before
        # reading a list, so a list at the very end of a subtable would otherwise be skipped for deep stacks.
        vals = b"".join(struct.pack(f">{len(v)}h", *v) for v in lists) + b"\0" * 16
    return head + cls + row_bytes + ent + vals


def _morx(chains: list[bytes]) -> bytes:
    return struct.pack(">HHI", 2, 0, len(chains)) + b"".join(chains)


def _morx_chain(
    default: int, features: list[tuple[int, int, int, int]], subtables: list[bytes]
) -> bytes:
    body = b"".join(struct.pack(">HHII", *f) for f in features) + b"".join(subtables)
    return (
        struct.pack(">IIII", default, 16 + len(body), len(features), len(subtables))
        + body
    )


def _morx_sub(kind: int, body: bytes, flags: int = 1) -> bytes:
    """One `morx` subtable: length, coverage (layout order, horizontal) | type, subFeatureFlags, body."""
    return struct.pack(">III", 12 + len(body), kind, flags) + body


def _mort(chains: list[bytes]) -> bytes:
    return struct.pack(">HHI", 1, 0, len(chains)) + b"".join(chains)


def _mort_chain(default: int, subtables: list[bytes]) -> bytes:
    body = b"".join(subtables)
    return struct.pack(">IIHH", default, 12 + len(body), 0, len(subtables)) + body


def _mort_sub(kind: int, body: bytes, flags: int = 1) -> bytes:
    return struct.pack(">HHI", 8 + len(body), kind, flags) + body


def _feat(features: list[tuple[int, bool, list[int]]]) -> bytes:
    """`feat` table: (feature type, exclusive, settings) sorted by type; names point at unused name ids."""
    features = sorted(features)
    head = struct.pack(">IHHI", 0x00010000, len(features), 0, 0)
    names, settings = b"", b""
    base = 12 + 12 * len(features)
    for i, (ftype, exclusive, sel) in enumerate(features):
        names += struct.pack(
            ">HHIHh",
            ftype,
            len(sel),
            base + len(settings),
            0x8000 if exclusive else 0,
            256 + i,
        )
        settings += b"".join(struct.pack(">Hh", s, 300 + s) for s in sel)
    return head + names + settings


def _gdef(bases: list[str], marks: list[str]) -> str:
    return f"table GDEF {{ GlyphClassDef [{' '.join(bases)}], , [{' '.join(marks)}], ; }} GDEF;\n"


# --------------------------------------------------------------------------------------------------------------
# Unit 20: cross-stream pair kerning from `kern`, the reset value 0x8000


U20_PAIRS = {
    "AV": 150,
    "VA": RESET,
    "TO": 120,
    "OT": RESET,
    "LY": -90,
    "YL": RESET,
    "WA": 60,
    "PA": RESET,
    "KO": -150,
    "RT": 200,
    "FJ": -40,
    "JF": RESET,
}
U20_CROSS = (
    "u20-ot-f0",
    "u20-ot-f2",
    "u20-ot-f3",
    "u20-aat-f0",
    "u20-aat-f2",
    "u20-aat-f3",
)
U20_INSTREAM = ("u20-ot-f0-in", "u20-aat-f0-in", "u20-aat-f2-in")


def _u20_tables(gl: Glyphs) -> dict:
    pairs = {(gl.g(k[0]), gl.g(k[1])): v for k, v in U20_PAIRS.items()}
    lefts = sorted({k[0] for k in U20_PAIRS})
    rights = sorted({k[1] for k in U20_PAIRS})
    left = {gl.g(c): i + 1 for i, c in enumerate(lefts)}
    right = {gl.g(c): i + 1 for i, c in enumerate(rights)}
    rows = [[0] * (len(rights) + 1)] + [
        [0] + [U20_PAIRS.get(a + b, 0) for b in rights] for a in lefts
    ]
    return {"pairs": pairs, "left": left, "right": right, "rows": rows}


def u20_fonts(out: Path) -> None:
    gl = Glyphs()
    t = _u20_tables(gl)
    n = len(gl.names)
    f0 = _pair_body(t["pairs"], False)
    specs = {
        "u20-ot-f0": _kern_ot([(0, 0x05, f0)]),
        "u20-ot-f2": _kern_ot(
            [(2, 0x05, _kern_f2(6, t["left"], t["right"], t["rows"]))]
        ),
        "u20-ot-f3": _kern_ot(
            [(3, 0x05, _kern_f3(n, t["left"], t["right"], t["rows"]))]
        ),
        "u20-aat-f0": _kern_aat([(0, 0x40, f0)]),
        "u20-aat-f2": _kern_aat(
            [(2, 0x40, _kern_f2(8, t["left"], t["right"], t["rows"]))]
        ),
        "u20-aat-f3": _kern_aat(
            [(3, 0x40, _kern_f3(n, t["left"], t["right"], t["rows"]))]
        ),
        "u20-ot-f0-in": _kern_ot([(0, 0x01, f0)]),
        "u20-aat-f0-in": _kern_aat([(0, 0x00, f0)]),
        "u20-aat-f2-in": _kern_aat(
            [(2, 0x00, _kern_f2(8, t["left"], t["right"], t["rows"]))]
        ),
    }
    for name, kern in specs.items():
        _save(out, name, gl, {"kern": kern})


def _adjacent(s: str) -> set[str]:
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _u20_word(rng: random.Random, chunks: list[str]) -> str:
    fill = "EHMNSUXZ"
    parts = list(chunks)
    for _ in range(rng.choice((0, 1, 1, 2, 3))):
        parts.insert(
            rng.randrange(len(parts) + 1),
            rng.choice((*fill, " ", rng.choice(fill) * 2)),
        )
    return "".join(parts)


def gen_20(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 20: a cross-stream `kern` pair whose value is 0x8000 resets the cross-stream shift.

    In: a cross-stream subtable (formats 0, 2, 3; OpenType and Apple headers) and text holding a pair whose value is
    0x8000; 14.3.0 shifts that glyph and those after it by -32768 units. Neighbours: `b:value`, the same subtables and
    text whose kerned pairs all have ordinary values; `b:in-stream`, the 0x8000 pairs in an in-stream subtable, where
    they are ordinary -32768 kerning. The scale half of the note: ordinary cross-stream values under x and y scales
    that differ (in; the shift takes the y scale in horizontal text), with in-stream pairs under such scales as their
    neighbour. `kerx` resets are left out (15.2.0 changes them too, the note names `kern` only).
    """
    resets = [k for k, v in U20_PAIRS.items() if v == RESET]
    plain = [k for k, v in U20_PAIRS.items() if v != RESET]
    for i in range(n):
        kind = (
            "in",
            "in",
            "axis",
            "axis",
            "b:value",
            "b:value",
            "b:in-stream",
            "b:in-stream",
        )[i % 8]
        font = rng.choice(U20_INSTREAM if kind == "b:in-stream" else U20_CROSS)
        direction = rng.choice(("ltr", "ltr", "ltr", "rtl"))
        for _ in range(50):
            if kind in ("b:value", "axis"):
                chunks = rng.sample(plain, rng.choice((1, 1, 2, 3)))
            else:
                chunks = rng.sample(resets, rng.choice((1, 1, 2))) + rng.sample(
                    plain, rng.choice((0, 1, 1, 2))
                )
                rng.shuffle(chunks)
            word = _u20_word(rng, chunks)
            seen = _adjacent(word[::-1] if direction == "rtl" else word)
            hits_reset = bool(seen & set(resets))
            if (kind in ("b:value", "axis")) != hits_reset and seen & set(U20_PAIRS):
                break
        else:
            continue
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        if direction != "ltr":
            opts["dir"] = direction
        scale = rng.choice(SCALES)
        if kind == "axis" or (kind == "b:in-stream" and i % 16 >= 8):
            # The axis half of the note: x and y scales that differ (cross-stream offsets take the y scale).
            x = rng.choice((800, 1000, 1500, 2048))
            opts["scale"] = (
                f"{x},{rng.choice([y for y in (600, 1000, 2000, 4096) if y != x])}"
            )
        elif scale:
            opts["scale"] = scale
        yield case(
            "20",
            "cand",
            synth / f"{font}.ttf",
            [ord(c) for c in word],
            nb="in" if kind == "axis" else kind,
            **opts,
        )


# --------------------------------------------------------------------------------------------------------------
# Unit 24: AAT, a later request for a feature overrides earlier ones


# tag: (AAT type, on setting, off setting, letter it changes); 'aalt' takes its value as the setting.
U24_TAGS = {
    "liga": (1, 2, 3, "A"),
    "dlig": (1, 4, 5, "B"),
    "clig": (1, 18, 19, "G"),
    "calt": (36, 0, 1, "F"),
    "swsh": (36, 2, 3, "H"),
    "case": (33, 0, 1, "E"),
    "smcp": (37, 1, 0, "D"),
    "aalt": (17, 1, 0, "C"),
}
U24_ALTS = {
    "liga": "A.liga",
    "dlig": "B.dlig",
    "clig": "G.clig",
    "calt": "F.calt",
    "swsh": "H.swsh",
    "case": "E.case",
    "smcp": "D.smcp",
}
U24_DEFAULT_ON = {"liga", "clig", "calt"}


def u24_fonts(out: Path) -> None:
    extra = tuple((g, 600) for g in (*U24_ALTS.values(), "C.alt1", "C.alt2"))
    gl = Glyphs(extra=extra)
    bit = {tag: 1 << i for i, tag in enumerate(U24_ALTS)}
    alt1, alt2 = 1 << len(U24_ALTS), 1 << (len(U24_ALTS) + 1)
    all_bits = 0xFFFFFFFF
    features = []
    for tag, (ftype, on, off, _) in U24_TAGS.items():
        if tag == "aalt":
            continue
        features.append((ftype, on, bit[tag], all_bits))
        features.append((ftype, off, 0, all_bits & ~bit[tag]))
    features += [
        (17, 0, 0, all_bits & ~(alt1 | alt2)),
        (17, 1, alt1, all_bits & ~alt2),
        (17, 2, alt2, all_bits & ~alt1),
    ]
    features.sort()
    subtables = [
        _morx_sub(4, _lookup8(gl.g(U24_TAGS[tag][3]), [gl.g(alt)]), bit[tag])
        for tag, alt in U24_ALTS.items()
    ]
    subtables += [
        _morx_sub(4, _lookup8(gl.g("C"), [gl.g("C.alt1")]), alt1),
        _morx_sub(4, _lookup8(gl.g("C"), [gl.g("C.alt2")]), alt2),
    ]
    default = sum(bit[t] for t in U24_DEFAULT_ON)
    morx = _morx([_morx_chain(default, features, subtables)])
    feat = _feat(
        [
            (1, False, [2, 3, 4, 5, 18, 19]),
            (17, True, [0, 1, 2]),
            (33, False, [0, 1]),
            (36, False, [0, 1, 2, 3]),
            (37, True, [0, 1]),
        ]
    )
    _save(out, "u24-morx", gl, {"morx": morx, "feat": feat})
    fea = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n"
    for tag, alt in U24_ALTS.items():
        fea += f"feature {tag} {{ sub {U24_TAGS[tag][3]} by {alt}; }} {tag};\n"
    fea += "feature aalt { sub C from [C.alt1 C.alt2]; } aalt;\n"
    _save(out, "u24-gsub", gl, {}, fea)


def _setting(tag: str, value: int) -> int:
    """The AAT setting a request selects (what HarfBuzz compares), 'aalt' values as they are."""
    _, on, off, _ = U24_TAGS[tag]
    return value if tag == "aalt" else (on if value else off)


def _value(rng: random.Random, tag: str) -> int:
    return rng.choice((0, 1, 2)) if tag == "aalt" else rng.choice((0, 1, 1, 2))


def _u24_text(rng: random.Random, letters: str) -> tuple[list[int], list[int]]:
    """Text holding each letter of `letters` at least once; returns code points and the letters' positions."""
    fill = "IKMNSUXZ"
    chars = list(letters) + [rng.choice(fill) for _ in range(rng.randrange(1, 5))]
    chars += [rng.choice(letters) for _ in range(rng.choice((0, 1, 2)))]
    rng.shuffle(chars)
    return [ord(c) for c in chars], [i for i, c in enumerate(chars) if c in letters]


def _ranged(tag: str, value: int, start: int, end: int) -> str:
    return f"{tag}={value}@{start}:{end}"


def gen_24(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 24: in `morx` fonts, the later of two requests for one feature wins (14.3.0 kept the first).

    In: a `morx` + `feat` font, one OpenType tag requested two or three times with values that select different AAT
    settings, over ranges that overlap on a glyph the feature changes; other tags may be requested once if their AAT
    feature type differs. Neighbours: `b:other-setting`, two tags of one AAT type with different settings (`liga` and
    `dlig`, `calt` and `swsh`), each requested once; `b:same-setting`, one tag repeated with the same setting;
    `b:disjoint`, one tag with different settings on ranges that do not overlap; `b:opentype`, the in-requests on a
    `GSUB` font with the same substitutions (a ranged request followed by a global one for the same tag is left out:
    unit 14 changes that in OpenType). Two different tags that select one exclusive AAT feature (such as `onum` and
    `lnum`) are left out: whether they are 'a feature' requested twice is not clear from the note.
    """
    aat, ot = synth / "u24-morx.ttf", synth / "u24-gsub.ttf"
    by_type: dict[int, list[str]] = {}
    for tag, (ftype, *_rest) in U24_TAGS.items():
        by_type.setdefault(ftype, []).append(tag)
    kinds = (
        "in",
        "in",
        "in",
        "in",
        "b:other-setting",
        "b:other-setting",
        "b:same-setting",
        "b:disjoint",
        "b:opentype",
        "b:opentype",
    )
    for i in range(n):
        kind = kinds[i % len(kinds)]
        if kind == "b:other-setting":
            ftype = rng.choice((1, 1, 36))
            tags = rng.sample(by_type[ftype], 2)
            text, _ = _u24_text(rng, "".join(U24_TAGS[t][3] for t in tags))
            ln = len(text)
            # The first request moves its feature off its default, so a port that drops it shows.
            first_default_on = tags[0] in U24_DEFAULT_ON
            reqs = []
            for j, tag in enumerate(tags):
                value = (0 if first_default_on else 1) if j == 0 else _value(rng, tag)
                if rng.random() < 0.5:
                    reqs.append(f"{tag}={value}")
                else:
                    start = rng.randrange(0, ln)
                    reqs.append(
                        _ranged(tag, value, start, rng.randrange(start + 1, ln + 1))
                    )
            yield case("24", "cand", aat, text, nb=kind, feat=",".join(reqs))
            continue
        tag = rng.choice(list(U24_TAGS))
        ftype = U24_TAGS[tag][0]
        text, where = _u24_text(rng, U24_TAGS[tag][3])
        ln = len(text)
        pos = rng.choice(where)
        if kind == "b:same-setting":
            v1 = _value(rng, tag)
            same = [v for v in (0, 1, 2, 3) if _setting(tag, v) == _setting(tag, v1)]
            values = [v1, rng.choice(same)]
        else:
            while True:
                values = [_value(rng, tag) for _ in range(rng.choice((2, 2, 2, 3)))]
                if len({_setting(tag, v) for v in values}) > 1 and _setting(
                    tag, values[-1]
                ) != _setting(tag, values[-2]):
                    break
        if kind == "b:disjoint":
            cut = rng.randrange(1, ln) if ln > 1 else 1
            reqs = [_ranged(tag, values[0], 0, cut), _ranged(tag, values[1], cut, ln)]
        else:
            shapes = ["gg", "gr", "rr", "nest"] + (
                [] if kind == "b:opentype" else ["rg"]
            )
            shape = rng.choice(shapes)
            start = rng.randrange(0, pos + 1)
            end = rng.randrange(pos + 1, ln + 1)
            if shape == "gg":
                reqs = [f"{tag}={v}" for v in values]
            elif shape == "gr":
                reqs = [f"{tag}={values[0]}"] + [
                    _ranged(tag, v, start, end) for v in values[1:]
                ]
            elif shape == "rg":
                reqs = [_ranged(tag, v, start, end) for v in values[:-1]] + [
                    f"{tag}={values[-1]}"
                ]
            elif shape == "rr":
                reqs = [
                    _ranged(
                        tag,
                        v,
                        rng.randrange(0, pos + 1),
                        rng.randrange(pos + 1, ln + 1),
                    )
                    for v in values
                ]
            else:
                # Nested ranges that end at different places, as in upstream's own test.
                reqs = [
                    _ranged(tag, values[0], 0, pos + 1),
                    _ranged(tag, values[1], 0, ln),
                ]
                reqs.append(
                    _ranged(
                        tag,
                        values[-1] if len(values) > 2 else values[0],
                        0,
                        rng.randrange(pos + 1, ln + 1),
                    )
                )
        if rng.random() < 0.4:
            # One request for a tag of another AAT feature type; its letter goes after the ranges in use.
            other = rng.choice([t for t in U24_TAGS if U24_TAGS[t][0] != ftype])
            reqs.insert(rng.randrange(len(reqs) + 1), f"{other}={_value(rng, other)}")
            if rng.random() < 0.5:
                text.append(ord(U24_TAGS[other][3]))
        font = ot if kind == "b:opentype" else aat
        yield case(
            "24",
            "cand",
            font,
            text,
            nb=kind,
            feat=",".join(reqs),
            cl=rng.choice((0, 1)),
        )


# --------------------------------------------------------------------------------------------------------------
# Unit 25a: `kerx` formats 1 and 2


U25A_LEFT = "ATLW"
U25A_RIGHT = "VOYA"


def _u25a_rows() -> list[list[int]]:
    """Class kerning: row 0 and column 0 are zero, every other cell distinct."""
    rows = [[0] * (len(U25A_RIGHT) + 1)]
    for r in range(1, len(U25A_LEFT) + 1):
        rows.append(
            [0] + [-(17 * r + 13 * c + 30) for c in range(1, len(U25A_RIGHT) + 1)]
        )
    return rows


# Class indices of the format 1 machines: 4 A, 5 V, 6 T, 7 O, 8 L, 9 Y, 10 W.
U25A_F1_CLASSES = {"A": 4, "V": 5, "T": 6, "O": 7, "L": 8, "Y": 9, "W": 10}
# Value lists (kern lists end in an odd value, kerx lists in 0xFFFF): AV, TO, LY, WA, a three-value list for AO, and
# a list for an action that pushes nothing.
U25A_LISTS = {
    "AV": [-80, -41],
    "TO": [-62, -35],
    "LY": [-121, -50],
    "WA": [-48, -27],
    "AO": [-30, -22, -15],
    "V": [-26, -11],
}
U25A_KERN_LISTS = {
    "AV": [-80, -1],
    "TO": [-62, -35],
    "LY": [-122, -1],
    "WA": [-48, -1],
    "AO": [-30, -22, -1],
    "V": [-26, -1],
}


def _u25a_machine():
    """Rows (classes 0-10) and entries of the contextual kerning machine shared by the `kerx` and `kern` fonts.

    States: 0 start of text, 1 start of line, 2 after A, 3 after T, 4 after L, 5 after W. An entry is (state, flags,
    value list name or None); a Y at the start state carries the `kerx` reset flag."""
    entries = [
        (0, 0, None),  # 0 nothing
        (2, PUSH, None),  # 1 A
        (3, PUSH, None),  # 2 T
        (4, PUSH, None),  # 3 L
        (5, PUSH, None),  # 4 W
        (0, PUSH, "AV"),  # 5 V after A
        (0, PUSH, "TO"),  # 6 O after T
        (0, PUSH, "LY"),  # 7 Y after L
        (2, PUSH, "WA"),  # 8 A after W
        (0, PUSH, "AO"),  # 9 O after A: three values for two pushes
        (0, 0, "V"),  # 10 V at the start state: acts without pushing
        (0, KERX_RESET, None),  # 11 Y at the start state: reset (kerx only)
    ]
    start = [0, 0, 0, 0, 1, 10, 2, 0, 3, 11, 4]
    rows = [
        start,
        start,
        [0, 0, 0, 0, 1, 5, 2, 9, 3, 0, 4],
        [0, 0, 0, 0, 1, 0, 2, 6, 3, 0, 4],
        [0, 0, 0, 0, 1, 0, 2, 0, 3, 7, 4],
        [0, 0, 0, 0, 8, 0, 2, 0, 3, 0, 4],
    ]
    return rows, entries


def u25a_fonts(out: Path) -> None:
    gl = Glyphs()
    rows = _u25a_rows()
    left = {gl.g(c): i + 1 for i, c in enumerate(U25A_LEFT)}
    right = {gl.g(c): i + 1 for i, c in enumerate(U25A_RIGHT)}
    width = len(U25A_RIGHT) + 1
    # Read as an index instead of a byte offset, the class values of row r and column c reach cell 2 * (width * r + c),
    # past the array from row 2 on; the spill cells give those reads values of their own.
    spill = [-(7 * k + 5) for k in range(2 * width * len(rows))]
    _save(
        out,
        "u25a-kerx-f2",
        gl,
        {"kerx": _kerx([_kerx_sub(2, _kerx_f2(left, right, rows, spill))])},
    )
    _save(
        out,
        "u25a-kern-f2",
        gl,
        {"kern": _kern_aat([(2, 0x00, _kern_f2(8, left, right, rows))])},
    )
    pairs = {(a, b): rows[left[a]][right[b]] for a in left for b in right}
    _save(
        out,
        "u25a-kerx-f0",
        gl,
        {"kerx": _kerx([_kerx_sub(0, _pair_body(pairs, True))])},
    )
    _save(
        out,
        "u25a-kerx-f6",
        gl,
        {"kerx": _kerx([_kerx_sub(6, _kerx_f6(left, right, rows))])},
    )

    machine_rows, machine_entries = _u25a_machine()
    classes = {gl.g(c): k for c, k in U25A_F1_CLASSES.items()}
    n_classes = 11
    # kerx: value lists at indices 3 and up (index 0-2 hold a decoy list), each ended by 0xFFFF.
    values = [-90, -70, END]
    start_of: dict[str, int] = {}
    for name, vals in U25A_LISTS.items():
        start_of[name] = len(values)
        values += vals + [END]
    entries = [
        struct.pack(">HHH", state, flags, start_of[li] if li else NO_ACTION)
        for state, flags, li in machine_entries
    ]
    values += [0] * 8  # room for the stack-depth check of the byte-offset reading
    tail = struct.pack(f">{len(values)}h", *values)
    f1 = _stx(
        n_classes,
        classes,
        machine_rows,
        entries,
        lambda off: struct.pack(">I", off),
        tail,
    )
    _save(out, "u25a-kerx-f1", gl, {"kerx": _kerx([_kerx_sub(1, f1)])})
    # kern: the same machine; lists end in an odd value, most in -1 (0xFFFF, the `kerx` end marker), and `kern` has
    # no reset flag (0x2000 is offset bits there).
    names = list(U25A_LISTS)
    kern_lists = [U25A_KERN_LISTS[name] for name in names]
    kern_entries = [
        (state, flags & ~KERX_RESET, names.index(li) if li else None)
        for state, flags, li in machine_entries
    ]
    st = _st(n_classes, classes, machine_rows, 0, kern_entries, kern_lists)
    _save(out, "u25a-kern-f1", gl, {"kern": _kern_aat([(1, 0x00, st)])})


U25A_FONTS = {
    "u25a-kerx-f2": "in:f2",
    "u25a-kerx-f1": "in:f1",
    "u25a-kern-f1": "b:kern-format1",
    "u25a-kern-f2": "b:kern-format2",
    "u25a-kerx-f0": "b:other-format",
    "u25a-kerx-f6": "b:other-format",
}


def gen_25a(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 25a: in `kerx` format 2 the sum of the two class values is a byte offset from the start of the kerning
    array; in format 1 an entry's value index counts values, a list ends at the word 0xFFFF, and every other value,
    odd or even, kerns the glyph it pops from the kerning stack (Chap6kerx.md).

    In: `kerx` format 1 and format 2 subtables. 15.1.0 also follows CoreText's format 1 history (90417543f: an
    eight-slot ring that lists read without popping, slots never filled standing for the first glyph, the reset flag
    ignored), which neither the note nor the digest describes. The machine below can reach it (a list read before or
    beyond the glyphs pushed for it, a reset), so classify.py leaves out every candidate whose output 15.1.0 without
    90417543f (build rk-25a-hist) changes. In the format 1 cases that remain, every list finds at least as many glyphs
    on the stack as it has values (or an empty stack, and then does nothing), and the digest's stack and CoreText's
    ring hand it the same glyphs. Neighbours: `b:kern-format1` and `b:kern-format2`, the same machine and classes in
    an Apple `kern` table, whose legacy reading stays (its lists end in an odd value, most of them in -1, the word
    that ends a `kerx` list); `b:other-format`, the same kerning as `kerx` formats 0 and 6.
    """
    fonts = list(U25A_FONTS)
    weights = [3, 4, 3, 2, 1, 1]
    alphabet = "AVTOLYWAVOEHN "
    for _ in range(n):
        font = rng.choices(fonts, weights)[0]
        length = rng.randrange(2, 10)
        word = "".join(rng.choice(alphabet) for _ in range(length)).strip() or "AV"
        if rng.random() < 0.5:
            pair = rng.choice(
                ("AV", "TO", "LY", "WA", "AO", "WAV", "AVO", "TOT", "AAV")
            )
            at = rng.randrange(len(word) + 1)
            word = word[:at] + pair + word[at:]
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        if rng.random() < 0.2:
            opts["dir"] = "rtl"
        scale = rng.choice(SCALES)
        if scale:
            opts["scale"] = scale
        yield case(
            "25a",
            "cand",
            synth / f"{font}.ttf",
            [ord(c) for c in word],
            nb=U25A_FONTS[font],
            **opts,
        )


# --------------------------------------------------------------------------------------------------------------
# Unit 25b: `kerx` format 4 marks take the cross-stream offset of the glyph they attach to


# Control-point coordinate actions (markX, markY, currX, currY). Every x is zero.
U25B_ACTIONS = [(0, 700, 0, 40), (0, 250, 0, 0), (0, -200, 0, 0), (0, -900, 0, 30)]
ABOVE = (ACUTE, GRAVE, MACRON)


def _u25b_format4(gl: Glyphs) -> bytes:
    """Classes 4 base letters, 5 marks above, 6 marks below. States 0 start, 1 start of line, 2 after a base (the base
    is marked), 3 after a mark above (that mark is marked). A mark above attaches to the marked glyph and becomes it;
    a mark below attaches to the marked glyph and leaves it."""
    classes = {gl.g(c): 4 for c in LETTERS}
    classes.update({gl.g(MARKS[m]): 5 for m in ABOVE})
    classes[gl.g(MARKS[DOTBELOW])] = 6
    entries = [
        (0, 0, NO_ACTION),  # 0 nothing
        (2, MARK_GLYPH, NO_ACTION),  # 1 base
        (3, MARK_GLYPH, 0),  # 2 mark above on a base
        (3, MARK_GLYPH, 1),  # 3 mark above on a mark above
        (2, 0, 2),  # 4 mark below on a base
        (3, 0, 3),  # 5 mark below on a mark above
    ]
    start = [0, 0, 0, 0, 1, 0, 0]
    rows = [start, start, [0, 0, 0, 0, 1, 2, 4], [0, 0, 0, 0, 1, 3, 5]]
    data = b"".join(struct.pack(">hhhh", *a) for a in U25B_ACTIONS)
    ent = [struct.pack(">HHH", *e) for e in entries]
    return _stx(
        7, classes, rows, ent, lambda off: struct.pack(">I", (2 << 30) | off), data
    )


U25B_CROSS = {"AV": 150, "TO": -120, "LY": 90, "WA": -60, "KO": 200, "PE": -90}
U25B_KERN = {"AV": -80, "TO": -60, "LY": -100, "WA": -40, "VA": -70, "PE": -50}


def u25b_fonts(out: Path) -> None:
    gl = Glyphs(marks=True)
    f4 = _kerx_sub(4, _u25b_format4(gl))
    cross = {(gl.g(k[0]), gl.g(k[1])): v for k, v in U25B_CROSS.items()}
    kern = {(gl.g(k[0]), gl.g(k[1])): v for k, v in U25B_KERN.items()}
    _save(out, "u25b-stack", gl, {"kerx": _kerx([f4])})
    _save(
        out,
        "u25b-cross",
        gl,
        {"kerx": _kerx([_kerx_sub(0, _pair_body(cross, True), CROSS_KERX), f4])},
    )
    _save(
        out,
        "u25b-instream",
        gl,
        {"kerx": _kerx([_kerx_sub(0, _pair_body(kern, True)), f4])},
    )


def _u25b_cluster(rng: random.Random, base: str, marks: int, stack: bool) -> list[int]:
    """A base and `marks` marks. Without `stack` the marks below come first and at most one mark above ends the
    cluster, so every mark attaches to the base."""
    if stack:
        seq = [rng.choice((*ABOVE, *ABOVE, DOTBELOW)) for _ in range(marks)]
    elif marks:
        seq = [DOTBELOW] * (marks - 1) + [rng.choice((*ABOVE, *ABOVE, DOTBELOW))]
    else:
        seq = []
    return [ord(base), *seq]


def _u25b_stacked(text: list[int]) -> bool:
    """True when some mark attaches to a mark above (a mark after a mark above, before the next base)."""
    after_above = False
    for cp in text:
        if cp in ABOVE:
            if after_above:
                return True
            after_above = True
        elif cp == DOTBELOW:
            if after_above:
                return True
        else:
            after_above = False
    return False


def gen_25b(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 25b: a `kerx` format 4 mark takes the cross-stream offset of the glyph it attaches to (a 14.3.0 regression).

    In: format 4 attachments to a glyph with a cross-stream offset, that is a mark on a mark (stacking) or a mark on a
    glyph shifted by cross-stream kerning earlier in the line. Neighbours: `b:unshifted-base`, one mark on a base no
    cross-stream kerning moved; `b:in-stream-shift`, one mark on a base that in-stream kerning moved along the line,
    whose offset the attachment already follows. Left to right only: the machine marks bases before their marks.
    """
    kinds = (
        "stack",
        "stack",
        "cross",
        "cross",
        "cross",
        "unshifted",
        "instream",
        "instream",
    )
    for i in range(n):
        kind = kinds[i % len(kinds)]
        clusters: list[int] = []
        for _ in range(rng.choice((1, 2, 2, 3))):
            if kind == "cross" and rng.random() < 0.6:
                pair = rng.choice(list(U25B_CROSS))
                clusters += [ord(pair[0])] + _u25b_cluster(
                    rng, pair[1], rng.choice((1, 1, 2)), rng.random() < 0.3
                )
            elif kind == "instream" and rng.random() < 0.7:
                pair = rng.choice(list(U25B_KERN))
                clusters += [ord(pair[0])] + _u25b_cluster(
                    rng, pair[1], rng.choice((1, 1, 2)), False
                )
            else:
                base = rng.choice(LETTERS)
                stack = kind == "stack" and rng.random() < 0.7
                clusters += _u25b_cluster(
                    rng,
                    base,
                    rng.choice((1, 2, 3)) if stack else rng.choice((0, 1, 1, 2)),
                    stack,
                )
            if rng.random() < 0.2:
                clusters.append(0x20)
        stacked = _u25b_stacked(clusters)
        if kind in ("stack", "cross"):
            font = "u25b-stack" if kind == "stack" else "u25b-cross"
            if not stacked and kind == "stack":
                continue
            nb = "in"
        elif kind == "unshifted":
            if stacked:
                continue
            font, nb = "u25b-stack", "b:unshifted-base"
        else:
            if stacked:
                continue
            font, nb = "u25b-instream", "b:in-stream-shift"
        if not any(cp in MARKS for cp in clusters):
            continue
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        scale = rng.choice(SCALES)
        if scale:
            opts["scale"] = scale
        yield case("25b", "cand", synth / f"{font}.ttf", clusters, nb=nb, **opts)


# --------------------------------------------------------------------------------------------------------------
# Unit 25c: `kern` and `mort` state tables whose initial state is not the first state


U25C_LEAD, U25C_FOLLOW = "ATLW", "VOY"
U25C_PAIRS = {"EH": -60, "HE": -45, "NU": -75}


def _u25c_layout(layout: str) -> tuple[list[str], int]:
    """Physical row order of the two-state machines and the index of the initial row.

    `neg`: the after-lead row comes first, so it is state -1; `pos`: start, start of line, after-lead (state 2);
    `unreached`: a row no entry names, then the `pos` rows."""
    return {
        "neg": (["after", "start", "line"], 1),
        "pos": (["start", "line", "after"], 0),
        "unreached": (["spare", "start", "line", "after"], 1),
    }[layout]


def _u25c_kern(gl: Glyphs, layout: str) -> bytes:
    classes = {gl.g(c): 4 for c in U25C_LEAD}
    classes.update({gl.g(c): 5 for c in U25C_FOLLOW})
    order, initial = _u25c_layout(layout)
    at = {name: i for i, name in enumerate(order)}
    entries = [
        (at["start"], 0, None),
        (at["after"], PUSH, None),
        (at["start"], PUSH, 0),
    ]
    start = [0, 0, 0, 0, 1, 0]
    rows = {"start": start, "line": start, "spare": start, "after": [0, 0, 0, 0, 1, 2]}
    st = _st(6, classes, [rows[name] for name in order], initial, entries, [[-80, -41]])
    pairs = {(gl.g(k[0]), gl.g(k[1])): v for k, v in U25C_PAIRS.items()}
    return _kern_aat([(1, 0x00, st), (0, 0x00, _pair_body(pairs, False))])


def _u25c_mort(gl: Glyphs, layout: str) -> bytes:
    """Rearrangement: a lead letter marks the first glyph; a following letter marks the last and swaps them (Ax => xA).
    A second chain subtable, noncontextual, turns N into U so that a dropped table shows on any text with N."""
    classes = {gl.g(c): 4 for c in U25C_LEAD}
    classes.update({gl.g(c): 5 for c in U25C_FOLLOW})
    order, initial = _u25c_layout(layout)
    at = {name: i for i, name in enumerate(order)}
    entries = [
        (at["start"], 0, None),
        (at["after"], MARK_FIRST, None),
        (at["start"], MARK_LAST | 1, None),
    ]
    start = [0, 0, 0, 0, 1, 0]
    rows = {"start": start, "line": start, "spare": start, "after": [0, 0, 0, 0, 1, 2]}
    st = _st(6, classes, [rows[name] for name in order], initial, entries)
    noncontextual = _lookup8(gl.g("N"), [gl.g("U")])
    return _mort([_mort_chain(1, [_mort_sub(0, st), _mort_sub(4, noncontextual)])])


def u25c_fonts(out: Path) -> None:
    gl = Glyphs()
    for layout in ("neg", "pos", "unreached"):
        _save(out, f"u25c-kern-{layout}", gl, {"kern": _u25c_kern(gl, layout)})
        _save(out, f"u25c-mort-{layout}", gl, {"mort": _u25c_mort(gl, layout)})


U25C_FONTS = {
    "u25c-kern-neg": "in",
    "u25c-mort-neg": "in",
    "u25c-kern-pos": "b:first-initial",
    "u25c-mort-pos": "b:first-initial",
    "u25c-kern-unreached": "b:unreached-rows",
    "u25c-mort-unreached": "b:unreached-rows",
}


def gen_25c(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 25c: `kern` and `mort` tables whose state machines reach states before the initial one now apply.

    In: an Apple `kern` table (format 1 machine plus a format 0 subtable) and a `mort` table (rearrangement plus
    noncontextual), each with a machine whose state array offset names its second row and whose entries go to the
    first; 14.3.0 rejected such tables whole. Neighbours: `b:first-initial`, the same machines laid out with the initial
    state first; `b:unreached-rows`, a row before the initial one that no entry names.
    """
    fonts = list(U25C_FONTS)
    weights = [3, 3, 2, 2, 1, 1]
    alphabet = "ATLWVOYEHNU "
    for _ in range(n):
        font = rng.choices(fonts, weights)[0]
        word = (
            "".join(rng.choice(alphabet) for _ in range(rng.randrange(2, 9))).strip()
            or "AV"
        )
        if rng.random() < 0.6:
            pair = rng.choice(U25C_LEAD) + rng.choice(U25C_FOLLOW)
            at = rng.randrange(len(word) + 1)
            word = word[:at] + pair + word[at:]
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        scale = rng.choice(SCALES)
        if scale:
            opts["scale"] = scale
        yield case(
            "25c",
            "cand",
            synth / f"{font}.ttf",
            [ord(c) for c in word],
            nb=U25C_FONTS[font],
            **opts,
        )


# --------------------------------------------------------------------------------------------------------------
# Unit 26: AAT insertion at the end of the text


U26_EXTRA = (("ins.mark", 300), ("ins.base", 450), ("ins.tail", 350))
# Trigger classes and what they insert: 4 ABC deleted-glyph sentinel, 5 DEF a mark, 6 GH a base, 7 JK a base and a mark.
U26_TRIGGERS = {"ABC": 4, "DEF": 5, "GH": 6, "JK": 7}


def _u26_insertion(gl: Glyphs, where: str) -> bytes:
    """`morx` insertion subtable. `eot`: a trigger letter (optionally followed by acutes) at the end of the text makes
    the end-of-text transition insert its list. `before` and `after`: each trigger inserts its list before or after
    itself in its own transition, and the end of the text does nothing."""
    glyph_list = [
        DELETED,
        gl.g("ins.mark"),
        gl.g("ins.base"),
        gl.g("ins.tail"),
        gl.g("ins.mark"),
    ]
    lists = {4: (0, 1), 5: (1, 1), 6: (2, 1), 7: (3, 2)}  # class: (index, count)
    classes = {gl.g(c): k for letters, k in U26_TRIGGERS.items() for c in letters}
    classes.update({gl.g(c): 8 for c in LETTERS if gl.g(c) not in classes})
    classes[gl.g(MARKS[ACUTE])] = 9
    n_classes = 10
    entries: list[bytes] = [struct.pack(">HHHH", 0, 0, NO_ACTION, NO_ACTION)]
    if where == "eot":
        # States 2-5 remember the last trigger class 4-7; acutes keep the state; EOT inserts.
        go = {k: len(entries) + k - 4 for k in lists}
        entries += [struct.pack(">HHHH", k - 2, 0, NO_ACTION, NO_ACTION) for k in lists]
        eot = {k: len(entries) + k - 4 for k in lists}
        entries += [
            struct.pack(">HHHH", 0, lists[k][1] << 5, lists[k][0], NO_ACTION)
            for k in lists
        ]
        rows = []
        for state in range(6):
            k = state + 2 if state >= 2 else None
            rows.append(
                [
                    eot[k] if k else 0,
                    0,
                    0,
                    0,
                    go[4],
                    go[5],
                    go[6],
                    go[7],
                    0,
                    go[k] if k else 0,
                ]
            )
    else:
        flag = INSERT_BEFORE if where == "before" else 0
        act = {k: len(entries) + k - 4 for k in lists}
        entries += [
            struct.pack(">HHHH", 0, flag | (lists[k][1] << 5), lists[k][0], NO_ACTION)
            for k in lists
        ]
        row = [0, 0, 0, 0, act[4], act[5], act[6], act[7], 0, 0]
        rows = [row, row]
    tail = struct.pack(f">{len(glyph_list)}H", *glyph_list)
    body = _stx(
        n_classes, classes, rows, entries, lambda off: struct.pack(">I", off), tail
    )
    return _morx([_morx_chain(1, [], [_morx_sub(5, body)])])


def u26_fonts(out: Path) -> None:
    gl = Glyphs(marks=True, extra=U26_EXTRA)
    gdef = _gdef([*LETTERS, "ins.base", "ins.tail"], [*MARKS.values(), "ins.mark"])
    for where in ("eot", "before", "after"):
        morx = _u26_insertion(gl, where)
        _save(out, f"u26-{where}", gl, {"morx": morx})
        _save(out, f"u26-{where}-gdef", gl, {"morx": morx}, gdef)


def gen_26(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 26: AAT insertion in the end-of-text transition gives the inserted glyph its own properties.

    In: a `morx` insertion made at the end of the text (the deleted-glyph sentinel, which 14.3.0 left in the output, or
    with `GDEF`, a mark after a base or a base after a mark, which 14.3.0 classed as the glyph before). Neighbours:
    `b:mid-before`, the same lists inserted before a glyph in its own transition; `b:mid-after`, inserted after it,
    the last glyph of the text included.
    """
    triggers = "".join(U26_TRIGGERS)
    others = "ILMNOPQRSTUVWXYZ"
    kinds = ("eot", "eot", "eot", "before", "after")
    for i in range(n):
        kind = kinds[i % len(kinds)]
        word = [rng.choice(others + triggers) for _ in range(rng.randrange(0, 6))]
        if kind == "eot":
            word.append(rng.choice(triggers))
            if rng.random() < 0.3:
                word.append(chr(ACUTE))
        elif not any(c in triggers for c in word) or rng.random() < 0.3:
            word.append(rng.choice(triggers))
        if rng.random() < 0.2 and kind != "eot":
            word.insert(rng.randrange(len(word) + 1), chr(ACUTE))
        gdef = rng.random() < 0.6
        font = f"u26-{kind}{'-gdef' if gdef else ''}"
        nb = {"eot": "in", "before": "b:mid-before", "after": "b:mid-after"}[kind]
        yield case(
            "26",
            "cand",
            synth / f"{font}.ttf",
            [ord(c) for c in word],
            nb=nb,
            cl=rng.choice((0, 1, 2)),
        )


# --------------------------------------------------------------------------------------------------------------
# Units 21, 22, 23 on synth_fonts.py's fonts, with short labels


AAT_WORDS = ["AVATAR", "TOWAWAY", "WAYLAY", "TOTAL", "LYNYL", "TOOT", "AVA", "WAW"]

# Unit 23's class kerning: `kerx` format 6 (synth_fonts.py builds the format 0 fonts). Left glyphs fall into rows and
# right glyphs into columns; row 0 and column 0 are the glyphs of no class and kern nothing.
U23_LEFT = {"A": 1, "W": 1, "V": 1, "T": 2, "Y": 2, "L": 2, "O": 3}
U23_RIGHT = {"V": 1, "W": 1, "Y": 1, "A": 2, "O": 3, "T": 3}
U23_ROWS = [
    [0, 0, 0, 0],
    [0, -110, -50, -30],
    [0, -70, -80, -60],
    [0, -40, -20, -10],
]
U23_PAIRS = {("A", "V"): -120, ("T", "O"): -90, ("L", "Y"): -150, ("W", "A"): -60}
U23_GSUB = "feature ss02 { sub A by B; } ss02;"
U23_NOKERN = "feature ss01 { pos A 30; } ss01;"
U23_KERN = "feature kern { pos A V -40; pos T O -40; } kern;"
# name: (label, features, also a format 0 subtable before the format 6 one)
U23_F6_FONTS = {
    "u23-kerx6-gsub-gpos-nokern": ("in:f6", U23_GSUB + U23_NOKERN, False),
    "u23-kerx06-gsub-gpos-nokern": ("in:f0-f6", U23_GSUB + U23_NOKERN, True),
    "u23-kerx6-gsub-gpos-kern": ("b:gpos-kern", U23_GSUB + U23_KERN, False),
    "u23-kerx6-gpos-nokern": ("b:no-gsub", U23_NOKERN, False),
    "u23-kerx6-gpos-kern": ("b:no-gsub", U23_KERN, False),
    "u23-kerx6-gsub-nogpos": ("b:no-gpos", U23_GSUB, False),
    "u23-kerx6-nogpos": ("b:no-gpos", "", False),
}


def u23_fonts(out: Path) -> None:
    """Unit 23 with class kerning: a `kerx` format 6 subtable (16-bit values) beside `GSUB` and a `GPOS` without a
    kerning feature, its neighbours as for format 0 (synth_fonts.kerx_fonts), and a font with a format 0 subtable
    followed by a format 6 one."""
    gl = Glyphs()
    left = {gl.g(c): r for c, r in U23_LEFT.items()}
    right = {gl.g(c): k for c, k in U23_RIGHT.items()}
    f6 = _kerx_sub(6, _kerx_f6(left, right, U23_ROWS))
    f0 = _kerx_sub(
        0, _pair_body({(gl.g(a), gl.g(b)): v for (a, b), v in U23_PAIRS.items()}, True)
    )
    for name, (_, fea, with_f0) in U23_F6_FONTS.items():
        _save(out, name, gl, {"kerx": _kerx([f0, f6] if with_f0 else [f6])}, fea)


def _word_and_range(rng: random.Random) -> tuple[list[int], int, int]:
    word = [ord(c) for c in rng.choice(AAT_WORDS)]
    start = rng.randrange(0, len(word) - 1)
    return word, start, rng.randrange(start + 2, len(word) + 1)


def gen_21(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 21: the legacy `kern` table applies in vertical text when the client requests `vkrn` and `GPOS` lacks it.

    In: vertical text, `vkrn` requested for the whole run or a range, a vertical `kern` subtable and a `GPOS` without
    `vkrn` (or no `GPOS`). Neighbours: `b:not-requested`, the same without any `vkrn` request; `b:vkrn-off`, `vkrn=0`
    requested; `b:gpos-vkrn`, `vkrn` requested in a font whose `GPOS` has it; `b:horizontal`, horizontal text with a
    horizontal `kern` subtable. Vertical `kerx` subtables are left out: with `vkrn` requested 15.2.0 applies them too,
    which the note (about `kern`) does not say.
    """
    kinds = (
        "in",
        "in",
        "in",
        "b:not-requested",
        "b:vkrn-off",
        "b:gpos-vkrn",
        "b:horizontal",
    )
    for i in range(n):
        kind = kinds[i % len(kinds)]
        word, start, end = _word_and_range(rng)
        opts: dict[str, object] = {
            "dir": rng.choice(("ttb", "ttb", "btt"))
            if kind != "b:horizontal"
            else "ltr"
        }
        request = f"vkrn=1@{start}:{end}" if rng.random() < 0.35 else "vkrn=1"
        if kind == "in":
            font = rng.choice(("kern-gpos-novkrn-v", "kern-nogpos-v"))
            opts["feat"] = request
        elif kind == "b:not-requested":
            font = rng.choice(("kern-gpos-novkrn-v", "kern-nogpos-v"))
        elif kind == "b:vkrn-off":
            font = rng.choice(("kern-gpos-novkrn-v", "kern-nogpos-v"))
            opts["feat"] = request.replace("vkrn=1", "vkrn=0")
        elif kind == "b:gpos-vkrn":
            font = "kern-gpos-vkrn-v"
            opts["feat"] = request
        else:
            font = rng.choice(
                ("kern-gpos-novkrn-h", "kern-gpos-vkrn-h", "kern-nogpos-h")
            )
            if rng.random() < 0.5:
                opts["feat"] = request
        if rng.random() < 0.3:
            opts["scale"] = rng.choice((2000, 500, 1500))
        yield case("21", "cand", synth / f"{font}.ttf", word, nb=kind, **opts)


def gen_22(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 22: `trak` in vertical text adds the track along the advance (14.3.0 shortened the column).

    In: the `trak` font with `STAT` (HarfBuzz tracks only such fonts), vertical text. Neighbours: `b:horizontal`, the
    same font in horizontal text; `b:no-stat`, vertical text in the same `trak` font without `STAT`, which no release
    tracks.
    """
    kinds = ("in", "in", "in", "b:horizontal", "b:horizontal", "b:no-stat")
    for i in range(n):
        kind = kinds[i % len(kinds)]
        word = [ord(c) for c in rng.choice(AAT_WORDS)]
        if kind == "in":
            font, direction = "trak-stat", rng.choice(("ttb", "btt"))
        elif kind == "b:horizontal":
            font, direction = "trak-stat", rng.choice(("ltr", "ltr", "rtl"))
        else:
            font, direction = "trak-nostat", rng.choice(("ttb", "btt"))
        opts: dict[str, object] = {"dir": direction}
        if rng.random() < 0.3:
            opts["scale"] = rng.choice((2000, 500, 1500))
        yield case("22", "cand", synth / f"{font}.ttf", word, nb=kind, **opts)


def gen_23(
    rng: random.Random, noto: dict[str, Font], synth: Path, n: int
) -> Iterator[dict]:
    """Unit 23: `kerx` pair and class kerning apply together with a `GPOS` that has no kerning feature.

    In: `GSUB`, a `GPOS` without `kern`, and in-stream `kerx` kerning: pairs (format 0, `in:f0`), classes (format 6,
    `in:f6`), or both subtables (`in:f0-f6`). Neighbours: `b:gpos-kern`, the `GPOS` has `kern` (`kerx` stays off);
    `b:no-gsub`, no `GSUB` (HarfBuzz then uses `kerx` instead of `GPOS`, before and after); `b:no-gpos`, no `GPOS`.
    A cross-stream `kerx` subtable beside `GPOS` is left out: 15.2.0 keeps it off, and whether the note's "pair
    kerning" covers it is not clear. So is format 2, whose class values 15.1.0 reads as byte offsets (unit 25a): a
    port of this note alone would get its kerning wrong. The format 6 candidates follow the format 0 ones, so those
    are as before.
    """
    kinds = ("in", "in", "in", "b:gpos-kern", "b:gpos-kern", "b:no-gsub", "b:no-gpos")
    fonts = {
        "in": ("kerx-gsub-gpos-nokern",),
        "b:gpos-kern": ("kerx-gsub-gpos-kern",),
        "b:no-gsub": ("kerx-gpos-nokern", "kerx-gpos-kern"),
        "b:no-gpos": ("kerx-gsub-nogpos", "kerx-nogpos"),
    }
    for i in range(n):
        kind = kinds[i % len(kinds)]
        word = [ord(c) for c in rng.choice(AAT_WORDS)]
        opts: dict[str, object] = {"dir": rng.choice(("ltr", "ltr", "rtl"))}
        if rng.random() < 0.3:
            opts["cl"] = rng.choice((1, 2))
        if rng.random() < 0.3:
            opts["scale"] = rng.choice((2000, 500, 1500))
        yield case(
            "23",
            "cand",
            synth / f"{rng.choice(fonts[kind])}.ttf",
            word,
            nb="in:f0" if kind == "in" else kind,
            **opts,
        )
    words = AAT_WORDS + ["VALLEY", "OTTAWA", "LAYOVER", "YAWL", "TAO"]
    by_label: dict[str, list[str]] = {}
    for name, (label, _, _) in U23_F6_FONTS.items():
        by_label.setdefault(label, []).append(name)
    kinds6 = ("in:f6",) * 45 + ("in:f0-f6",) * 25 + ("b:gpos-kern",) * 30
    kinds6 += ("b:no-gsub",) * 30 + ("b:no-gpos",) * 30
    for kind in kinds6:
        word = [ord(c) for c in rng.choice(words)]
        opts = {"dir": rng.choice(("ltr", "ltr", "rtl"))}
        if rng.random() < 0.3:
            opts["cl"] = rng.choice((1, 2))
        if rng.random() < 0.3:
            opts["scale"] = rng.choice((2000, 500, 1500))
        font = synth / f"{rng.choice(by_label[kind])}.ttf"
        yield case("23", "cand", font, word, nb=kind, **opts)


# --------------------------------------------------------------------------------------------------------------


def build_fonts(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    u20_fonts(out)
    u24_fonts(out)
    u25a_fonts(out)
    u25b_fonts(out)
    u25c_fonts(out)
    u26_fonts(out)
    u23_fonts(out)


UNITS = {
    "20": gen_20,
    "21": gen_21,
    "22": gen_22,
    "23": gen_23,
    "24": gen_24,
    "25a": gen_25a,
    "25b": gen_25b,
    "25c": gen_25c,
    "26": gen_26,
}

PER_UNIT = {
    "20": 900,
    "21": 700,
    "22": 500,
    "23": 600,
    "24": 1000,
    "25a": 900,
    "25b": 900,
    "25c": 700,
    "26": 800,
}

W_TARGETS = {
    "20": ["b:in-stream"],
    "21": ["b:not-requested", "b:vkrn-off"],
    "22": ["b:horizontal"],
    "23": ["b:gpos-kern"],
    "24": ["b:other-setting"],
    "25a": ["b:kern-format1"],
    "25b": ["b:in-stream-shift"],
    "26": ["b:mid-before"],
}
