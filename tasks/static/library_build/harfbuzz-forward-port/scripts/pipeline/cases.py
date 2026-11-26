"""Generate candidate cases per unit for the sweep (step 3, window C first families).

Runs inside the pipeline image: `/opt/py/bin/python -I /pipe/cases.py OUT_DIR SEED [PER_UNIT]`. It reads the
downloaded fonts with fontTools, which is why it never runs on the host. Each candidate is only a candidate:
the sweep over base, releases and revert mutants decides whether it becomes a changed case of one unit, a held-fixed
case, or nothing. Development tooling, never shipped.
"""

from __future__ import annotations

import json
import random
import sys
import tarfile
import unicodedata
from collections.abc import Iterator
from pathlib import Path

from fontTools.ttLib import TTFont

NOTO = Path("/dl/fonts")
SYNTH = Path("/work/fonts")
TARBALL = Path("/dl/harfbuzz/harfbuzz-14.3.0.tar.xz")

ZWJ, ZWNJ, CGJ, WJ, SHY, NBSP, DOTTED = (
    0x200D,
    0x200C,
    0x034F,
    0x2060,
    0x00AD,
    0x00A0,
    0x25CC,
)


class Font:
    """The cmap and layout features of one font file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        font = TTFont(str(path), lazy=True)
        self.cmap = set(font.getBestCmap() or {})
        self.features: set[str] = set()
        for tag in ("GSUB", "GPOS"):
            if tag in font and font[tag].table.FeatureList:
                self.features |= {
                    rec.FeatureTag for rec in font[tag].table.FeatureList.FeatureRecord
                }

    def has(self, *cps: int) -> bool:
        return all(cp in self.cmap for cp in cps)

    def block(self, lo: int, hi: int, cats: tuple[str, ...]) -> list[int]:
        out = []
        for cp in range(lo, hi + 1):
            if cp in self.cmap:
                try:
                    if unicodedata.category(chr(cp)) in cats:
                        out.append(cp)
                except ValueError:
                    pass
        return out


def case(unit: str, kind: str, font: Font, text: list[int], **opts: object) -> dict:
    opt = ";".join(f"{k}={v}" for k, v in opts.items())
    return {
        "unit": unit,
        "kind": kind,
        "font": str(font.path),
        "idx": 0,
        "opts": opt,
        "text": text,
    }


def gen_khmer(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Unit 4: Coeng Ro moved only once, and only as the first or second coeng."""
    ro, coeng = 0x179A, 0x17D2
    for i in range(n):
        f = fonts[i % len(fonts)]
        cons = f.block(0x1780, 0x17A2, ("Lo",))
        vowels = [0, *f.block(0x17B6, 0x17C5, ("Mn", "Mc"))]
        signs = [
            0,
            *[cp for cp in f.block(0x17C6, 0x17D1, ("Mn", "Mc")) if cp != coeng],
        ]
        text = []
        for _ in range(rng.choice((1, 1, 2))):
            text.append(rng.choice(cons))
            for _ in range(rng.choice((1, 2, 2, 3, 3, 4))):
                text += [coeng, ro if rng.random() < 0.5 else rng.choice(cons)]
            for extra in (rng.choice(vowels), rng.choice(signs)):
                if extra:
                    text.append(extra)
        yield case("4", "cand", f, text, cl=rng.choice((0, 1, 2)))


def gen_indic_init(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Unit 1: no `init` on a first syllable that follows a letter or mark in the pre-context."""
    blocks = {
        "beng": (0x0980, 0x09FF, 0x09BF, 0x09CD),
        "deva": (0x0900, 0x097F, 0x093F, 0x094D),
    }
    usable = [
        (f, b)
        for f in fonts
        for b in blocks.values()
        if f.has(b[2]) and "init" in f.features
    ]
    if not usable:
        return
    for i in range(n):
        f, (lo, hi, matra, virama) = usable[i % len(usable)]
        cons = f.block(lo, hi, ("Lo",))
        marks = f.block(lo, hi, ("Mn", "Mc"))
        pre_kind = rng.choice(
            (
                "none",
                "letter",
                "mark",
                "latin",
                "space",
                "punct",
                "digit",
                "zwj",
                "zwnj",
            )
        )
        pre = {
            "none": [],
            "letter": [rng.choice(cons)],
            "mark": [rng.choice(cons), rng.choice(marks)],
            "latin": [0x61],
            "space": [0x20],
            "punct": [rng.choice((0x2C, 0x2E, 0x2D, 0x0964))],
            "digit": [0x31],
            "zwj": [ZWJ],
            "zwnj": [ZWNJ],
        }[pre_kind]
        syl = (
            [rng.choice(cons)]
            if rng.random() < 0.7
            else [rng.choice(cons), virama, rng.choice(cons)]
        )
        text = [*syl, matra]
        if rng.random() < 0.4:
            text += [rng.choice(cons), matra]
        opts = {"cl": rng.choice((0, 1))}
        if pre:
            opts["pre"] = ",".join(f"{cp:X}" for cp in pre)
        yield case("1", "cand", f, text, **opts)


def gen_use_space(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Unit 2: a space is no base for a dependent vowel."""
    blocks = [(0x1B00, 0x1B7F), (0xA980, 0xA9DF), (0x1A20, 0x1AAF)]
    usable = [(f, b) for f in fonts for b in blocks if f.block(*b, ("Mn", "Mc"))]
    for i in range(n):
        f, (lo, hi) = usable[i % len(usable)]
        vowels = f.block(lo, hi, ("Mn", "Mc"))
        cons = f.block(lo, hi, ("Lo",))
        base = rng.choice((0x20, 0x20, 0x20, NBSP, DOTTED, 0x2002, 0x3000, None))
        text = []
        if rng.random() < 0.5:
            text.append(rng.choice(cons))
        text += [base if base is not None else rng.choice(cons), rng.choice(vowels)]
        if rng.random() < 0.3:
            text.append(rng.choice(vowels))
        yield case("2", "cand", f, text, cl=rng.choice((0, 1)))


def gen_hangul_tone(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Unit 5: one dotted circle for a tone mark at the start of the text."""
    for i in range(n):
        f = fonts[i % len(fonts)]
        tone = rng.choice((0x302E, 0x302F))
        syl = rng.randrange(0xAC00, 0xD7A4)
        shape = rng.choice(("start", "start2", "after", "space", "twice", "pre"))
        text = {
            "start": [tone],
            "start2": [tone, syl],
            "after": [syl, tone],
            "space": [0x20, tone],
            "twice": [syl, tone, tone],
            "pre": [tone, syl],
        }[shape]
        opts = {"cl": rng.choice((0, 1, 2))}
        if shape == "pre":
            opts["pre"] = f"{syl:X}"
        yield case("5", "cand", f, text, **opts)


def invalid_clusters() -> list[list[int]]:
    """Prohibited vowel sequences from the 14.3.0 tree's Microsoft data file."""
    with tarfile.open(TARBALL) as tar:
        member = tar.extractfile(
            "harfbuzz-14.3.0/src/ms-use/IndicShapingInvalidCluster.txt"
        )
        lines = member.read().decode("utf-8").splitlines()
    out = []
    for line in lines:
        body = line.split("#", 1)[0].split(";", 1)[0].strip()
        if body:
            try:
                out.append([int(tok, 16) for tok in body.split()])
            except ValueError:
                continue
    return out


def gen_vowel_constraints(
    rng: random.Random, fonts: list[Font], n: int
) -> Iterator[dict]:
    """Unit 7: a dotted circle also when a default ignorable sits between the vowels."""
    seqs = invalid_clusters()
    usable = [(f, s) for f in fonts for s in seqs if len(s) >= 2 and f.has(*s)]
    for i in range(n):
        f, seq = usable[i % len(usable)]
        between = rng.choice((ZWJ, ZWJ, ZWNJ, CGJ, WJ, SHY, 0x20, None))
        text = [seq[0]] + ([between] if between else []) + seq[1:]
        yield case("7", "cand", f, text, cl=rng.choice((0, 1)))


def gen_precomposed(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Unit 13: precomposed characters in Indic, Khmer, Myanmar and USE text with no marks."""
    ranges = [
        (0x0900, 0x097F),
        (0x0980, 0x09FF),
        (0x1000, 0x109F),
        (0x1780, 0x17FF),
        (0x1B00, 0x1B7F),
        (0xA980, 0xA9DF),
        (0x1A20, 0x1AAF),
    ]
    pool = []
    for f in fonts:
        for lo, hi in ranges:
            for cp in range(lo, hi + 1):
                d = unicodedata.decomposition(chr(cp)) if cp in f.cmap else ""
                if d and not d.startswith("<"):
                    pool.append((f, cp, lo, hi))
    for i in range(n):
        f, cp, lo, hi = pool[i % len(pool)]
        cons = f.block(lo, hi, ("Lo",))
        marks = f.block(lo, hi, ("Mn", "Mc"))
        shape = rng.choice(("alone", "after", "before", "mark"))
        text = {
            "alone": [cp],
            "after": [rng.choice(cons) if cons else 0x20, cp],
            "before": [cp, rng.choice(cons) if cons else 0x20],
            "mark": [cp, rng.choice(marks) if marks else cp],
        }[shape]
        yield case("13", "cand", f, text, cl=rng.choice((0, 1, 2)))


def gen_global_over_ranged(
    rng: random.Random, fonts: list[Font], n: int
) -> Iterator[dict]:
    """Unit 14: a global request overrides earlier ranged requests for the same feature."""
    words = [
        "office fifty",
        "Affluent 0123",
        "HELLO world",
        "final fjord",
        "ff fi fl ffi",
    ]
    usable = [f for f in fonts if f.has(0x61, 0x66)]
    for i in range(n):
        f = usable[i % len(usable)]
        feats = sorted(
            t
            for t in f.features
            if t
            in {
                "liga",
                "dlig",
                "smcp",
                "c2sc",
                "onum",
                "lnum",
                "zero",
                "case",
                "frac",
                "ss01",
                "ss02",
                "kern",
                "calt",
                "sups",
            }
        )
        word = rng.choice(words)
        text = [ord(c) for c in word]
        tag = rng.choice(feats)
        start = rng.randrange(0, len(text) - 1)
        end = rng.randrange(start + 1, len(text) + 1)
        v1, v2 = rng.choice(((0, 1), (1, 0), (1, 1), (0, 0)))
        shape = rng.choice(
            (
                "ranged-global",
                "ranged-global",
                "global-ranged",
                "ranged-other",
                "two-ranged",
            )
        )
        other = rng.choice([t for t in feats if t != tag] or [tag])
        feat = {
            "ranged-global": f"{tag}={v1}@{start}:{end},{tag}={v2}",
            "global-ranged": f"{tag}={v2},{tag}={v1}@{start}:{end}",
            "ranged-other": f"{tag}={v1}@{start}:{end},{other}={v2}",
            "two-ranged": f"{tag}={v1}@{start}:{end},{tag}={v2}@0:{end}",
        }[shape]
        opts = {"feat": feat}
        if "VF" in f.path.name and rng.random() < 0.3:
            opts["var"] = f"wght={rng.choice((300, 700))}"
        yield case("14", "cand", f, text, **opts)


def gen_missing_vs(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Unit 15: an unsupported character with a variation selector gets the buffer's not-found glyph."""
    selectors = [*range(0xFE00, 0xFE10), *range(0xE0100, 0xE0105)]
    for i in range(n):
        f = fonts[i % len(fonts)]
        present = sorted(f.cmap - {0x20})
        missing = next(
            cp
            for cp in (rng.randrange(0x4E00, 0x9FFF) for _ in range(50))
            if cp not in f.cmap
        )
        shape = rng.choice(
            ("missing-vs", "missing-vs", "missing", "present-vs", "missing-vs-no-nf")
        )
        text = {
            "missing-vs": [missing, rng.choice(selectors)],
            "missing": [missing],
            "present-vs": [rng.choice(present), rng.choice(selectors)],
            "missing-vs-no-nf": [missing, rng.choice(selectors)],
        }[shape]
        if rng.random() < 0.4:
            text = [rng.choice(present), *text]
        opts = {} if shape == "missing-vs-no-nf" else {"nf": rng.choice((1, 2, 3))}
        yield case("15", "cand", f, text, **opts)


def gen_aat(rng: random.Random, n: int) -> Iterator[dict]:
    """Units 21, 22, 23 on our synthetic fonts."""
    words = ["AVATAR", "TOWAWAY", "LYNX", "WAVE", "HELLO", "ATOLL", "VALLEY", "TOTAL"]
    for i in range(n):
        word = [ord(c) for c in rng.choice(words)]
        trak = Font(SYNTH / "trak-font.ttf")
        yield case(
            "22", "cand", trak, word, dir=rng.choice(("ttb", "ttb", "ltr", "btt"))
        )
        kx = Font(
            SYNTH
            / rng.choice(
                (
                    "kerx-gpos-nokern.ttf",
                    "kerx-gpos-nokern.ttf",
                    "kerx-gpos-kern.ttf",
                    "kerx-nogpos.ttf",
                )
            )
        )
        yield case("23", "cand", kx, word, dir=rng.choice(("ltr", "ltr", "rtl")))
        kv = Font(
            SYNTH
            / rng.choice(
                (
                    "kern-gpos-novkrn-h.ttf",
                    "kern-gpos-novkrn-v.ttf",
                    "kern-gpos-vkrn-h.ttf",
                    "kern-gpos-vkrn-v.ttf",
                    "kern-nogpos-h.ttf",
                    "kern-nogpos-v.ttf",
                )
            )
        )
        opts = {"dir": rng.choice(("ttb", "ttb", "ltr"))}
        if rng.random() < 0.7:
            opts["feat"] = "vkrn=1"
        yield case("21", "cand", kv, word, **opts)


def gen_broad(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Held-fixed candidates: text near no note, in every font."""
    for f in fonts:
        letters = sorted(
            cp
            for cp in f.cmap
            if 0x20 < cp < 0x3000 and unicodedata.category(chr(cp))[0] in "LMNP"
        )
        for _ in range(n):
            text = [rng.choice(letters) for _ in range(rng.randrange(1, 9))]
            opts = {"cl": rng.choice((0, 1))}
            if "VF" in f.path.name:
                opts["var"] = f"wght={rng.choice((400, 700))}"
            yield case("broad", "broad", f, text, **opts)


def main() -> None:
    out = Path(sys.argv[1])
    seed = int(sys.argv[2])
    per_unit = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    noto = {p.stem: Font(p) for p in sorted(NOTO.glob("*.[ot]tf"))}
    khmer = [noto["NotoSansKhmer-Regular"], noto["NotoSerifKhmer-Regular"]]
    indic = [noto["NotoSansBengali-Regular"], noto["NotoSansDevanagari-Regular"]]
    use = [
        noto["NotoSansBalinese-Regular"],
        noto["NotoSansJavanese-Regular"],
        noto["NotoSansTaiTham-Regular"],
    ]
    gens = [
        gen_khmer(rng, khmer, per_unit),
        gen_indic_init(rng, indic, per_unit),
        gen_use_space(rng, use, per_unit),
        gen_hangul_tone(rng, [noto["NotoSansKR-Regular"]], per_unit),
        gen_vowel_constraints(rng, indic + use, per_unit),
        gen_precomposed(
            rng, indic + khmer + use + [noto["NotoSansMyanmar-Regular"]], per_unit
        ),
        gen_global_over_ranged(
            rng, [noto["NotoSans-VF"], noto["NotoSerif-VF"]], per_unit
        ),
        gen_missing_vs(
            rng, [noto["NotoSansHebrew-Regular"], noto["NotoSans-VF"]], per_unit
        ),
        gen_aat(rng, per_unit // 3),
        gen_broad(rng, list(noto.values()), 60),
    ]
    n = 0
    with (out / "cases.tsv").open("w") as tsv, (out / "meta.jsonl").open("w") as meta:
        for gen in gens:
            for c in gen:
                n += 1
                c["id"] = f"c{n:06d}"
                text = ",".join(f"{cp:X}" for cp in c["text"])
                tsv.write(f"{c['id']}\t{c['font']}\t{c['idx']}\t{c['opts']}\t{text}\n")
                meta.write(json.dumps(c) + "\n")
    print(
        json.dumps(
            {"candidates": n, "fonts": {k: len(v.cmap) for k, v in noto.items()}}
        )
    )


if __name__ == "__main__":
    main()
