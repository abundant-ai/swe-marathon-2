"""Generate candidate cases per unit for the sweep (step 3, window C first families).

Runs inside the pipeline image: `/opt/py/bin/python -I /pipe/cases.py OUT_DIR SEED [PER_UNIT]`. It reads the
downloaded fonts with fontTools, which is why it never runs on the host. Each candidate is only a candidate:
the sweep over base, releases and revert mutants decides whether it becomes a changed case of one unit, a held-fixed
case, or nothing. Development tooling, never shipped.
"""

from __future__ import annotations

import functools
import importlib
import json
import random
import sys
import tarfile
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from casekit import (
    CGJ,
    DOTTED,
    NBSP,
    NOTO,
    SHY,
    SYNTH,
    TARBALL,
    WJ,
    ZWJ,
    ZWNJ,
    Font,
    case,
    init_inputs,
)


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


INDIC = {
    # script: (first, last, virama, pre-base vowel signs, native digit one)
    "beng": (0x0980, 0x09FF, 0x09CD, (0x09BF, 0x09C7, 0x09C8), 0x09E7),
    "deva": (0x0900, 0x097F, 0x094D, (0x093F,), 0x0967),
}


def gen_indic_init(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Unit 1: no `init` on a first syllable that follows a letter or mark in the pre-context.

    Only fonts whose `init` substitutes a pre-base vowel sign can show the change. Pre-contexts: a letter or a mark
    (changed: `in:letter`, `in:mark`, `in:latin`), or nothing, a space, punctuation or a digit (neighbours that keep
    `init`: `b:none`, `b:space`, `b:punct`, `b:digit`); a first syllable later in the text is another neighbour
    (`b:later`). Format characters such as ZWJ are left out as pre-context: 15.2.0 treats them as it treats letters,
    which the note does not say.
    """
    usable = []
    for f in fonts:
        inputs = init_inputs(f.path)
        for lo, hi, virama, pre_base, digit in INDIC.values():
            signs = [cp for cp in pre_base if f.glyph_of.get(cp) in inputs]
            if signs:
                usable.append((f, lo, hi, virama, signs, digit))
    if not usable:
        return
    for i in range(n):
        f, lo, hi, virama, signs, digit = usable[i % len(usable)]
        cons = f.block(lo, hi, ("Lo",))
        marks = f.block(lo, hi, ("Mn", "Mc"))
        pre_kind = rng.choice(
            ("none", "letter", "letter", "mark", "mark", "latin")
            + ("space", "punct", "digit", "later")
        )
        pre = {
            "none": [],
            "letter": [rng.choice(cons)],
            "mark": [rng.choice(cons), rng.choice(marks)],
            "latin": [rng.choice((0x61, 0x6B))],
            "space": [0x20],
            "punct": [rng.choice((0x2C, 0x2E, 0x2D, 0x0964))],
            "digit": [rng.choice((0x31, digit))],
            "later": [rng.choice(cons)],
        }[pre_kind]
        syl = (
            [rng.choice(cons)]
            if rng.random() < 0.7
            else [rng.choice(cons), virama, rng.choice(cons)]
        )
        text = [*syl, rng.choice(signs)]
        if rng.random() < 0.4:
            text += [rng.choice(cons), rng.choice(signs)]
        opts = {"cl": rng.choice((0, 1))}
        if pre_kind == "later":
            text = [*pre, rng.choice((0x20, *pre)), *text]
        elif pre:
            opts["pre"] = ",".join(f"{cp:X}" for cp in pre)
        inside = pre_kind in ("letter", "mark", "latin")
        yield case(
            "1", "cand", f, text, nb=f"{'in' if inside else 'b'}:{pre_kind}", **opts
        )


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
    """Unit 5: a Hangul tone mark at the start of the text gets only one dotted circle.

    The start of the text is the client's beginning-of-text flag: 14.3.0 then gives a tone mark that opens the text
    the dotted circle every broken cluster at the start gets, plus a second one from the Hangul shaper. Changed
    (`in:start`): a tone mark opening the text, flagged. Neighbours every release treats alike: the same text without
    the flag (`b:noflag`), and flagged text that opens with a space, a syllable or a white circle (`b:space`,
    `b:syllable`, `b:white`), or a typed dotted circle with an acute (`b:dc-acute`). A dotted circle already in the
    text before the tone mark is left out: 15.2.0 changes that too, which the note does not say.
    """
    usable = [f for f in fonts if f.has(0x302E, 0x302F, DOTTED)]
    for i in range(n):
        f = usable[i % len(usable)]
        tone = rng.choice((0x302E, 0x302F))
        syl = rng.randrange(0xAC00, 0xD7A4)
        tail = rng.choice(([], [syl], [0x20, syl], [syl, syl]))
        shape = rng.choice(
            ("start", "start", "start", "noflag", "noflag")
            + ("space", "syllable", "white", "dc-acute")
        )
        text = {
            "start": [tone, *tail],
            "noflag": [tone, *tail],
            "space": [0x20, tone, *tail],
            "syllable": [syl, tone, *tail],
            "white": [0x25CB, tone, *tail],
            "dc-acute": [DOTTED, 0x0301, *tail],
        }[shape]
        opts: dict[str, object] = {"cl": rng.choice((0, 1, 2))}
        if shape != "noflag":
            opts["flags"] = "bot"
        yield case(
            "5",
            "cand",
            f,
            text,
            nb=f"{'in' if shape == 'start' else 'b'}:{shape}",
            **opts,
        )


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
    fonts = {
        p.stem: Font(p)
        for p in sorted(SYNTH.glob("k*.ttf")) + sorted(SYNTH.glob("trak-*.ttf"))
    }
    # Every word holds one of the fonts' kerning pairs (AV, TO, LY, WA) both forwards and backwards, so every case
    # can show kerning in either direction.
    words = ["AVATAR", "TOWAWAY", "WAYLAY", "TOTAL", "LYNYL", "TOOT", "AVA", "WAW"]
    for i in range(n):
        word = [ord(c) for c in rng.choice(words)]
        name = rng.choice(("trak-stat", "trak-stat", "trak-nostat"))
        direction = rng.choice(("ttb", "ttb", "ltr", "btt"))
        yield case(
            "22",
            "cand",
            fonts[name],
            word,
            nb=f"{name}-{direction}",
            dir=direction,
        )
        name = rng.choice(
            ("kerx-gsub-gpos-nokern",) * 3
            + ("kerx-gsub-gpos-kern",) * 2
            + ("kerx-gsub-gpos-nokern-cross", "kerx-gpos-nokern", "kerx-gpos-kern")
            + ("kerx-gsub-nogpos", "kerx-nogpos")
        )
        yield case(
            "23",
            "cand",
            fonts[name],
            word,
            nb=name,
            dir=rng.choice(("ltr", "ltr", "rtl")),
        )
        name = rng.choice(
            ("kern-gpos-novkrn-h", "kern-gpos-novkrn-v", "kern-gpos-vkrn-h")
            + ("kern-gpos-vkrn-v", "kern-nogpos-h", "kern-nogpos-v")
        )
        opts = {"dir": rng.choice(("ttb", "ttb", "ltr"))}
        if rng.random() < 0.7:
            opts["feat"] = "vkrn=1"
        yield case(
            "21",
            "cand",
            fonts[name],
            word,
            nb=f"{name}-{opts['dir']}-{'vkrn' if 'feat' in opts else 'novkrn'}",
            **opts,
        )


def gen_broad(rng: random.Random, fonts: list[Font], n: int) -> Iterator[dict]:
    """Held-fixed candidates: text near no note, in every font."""
    for f in fonts:
        letters = sorted(
            cp
            for cp in f.cmap
            if cp > 0x20 and unicodedata.category(chr(cp))[0] in "LMNP"
        )
        for _ in range(n):
            text = [rng.choice(letters) for _ in range(rng.randrange(1, 9))]
            opts = {"cl": rng.choice((0, 1))}
            if "VF" in f.path.name:
                opts["var"] = f"wght={rng.choice((400, 700))}"
            yield case("broad", "broad", f, text, **opts)


def builtin_units(
    noto: dict[str, Font],
) -> dict[str, Callable[[random.Random, int], Iterator[dict]]]:
    """The generators written during the spike, keyed by unit."""
    khmer = [noto["NotoSansKhmer-Regular"], noto["NotoSerifKhmer-Regular"]]
    indic = [noto["NotoSansBengali-Regular"], noto["NotoSansDevanagari-Regular"]]
    use = [
        noto["NotoSansBalinese-Regular"],
        noto["NotoSansJavanese-Regular"],
        noto["NotoSansTaiTham-Regular"],
    ]

    def aat(unit: str) -> Callable[[random.Random, int], Iterator[dict]]:
        return lambda rng, n: (c for c in gen_aat(rng, n) if c["unit"] == unit)

    return {
        "4": lambda rng, n: gen_khmer(rng, khmer, n),
        "1": lambda rng, n: gen_indic_init(
            rng, [*indic, Font(SYNTH / "beng-init.ttf")], n
        ),
        "2": lambda rng, n: gen_use_space(rng, use, n),
        "5": lambda rng, n: gen_hangul_tone(rng, [noto["NotoSansKR-Regular"]], n),
        "7": lambda rng, n: gen_vowel_constraints(rng, indic + use, n),
        "13": lambda rng, n: gen_precomposed(
            rng, indic + khmer + use + [noto["NotoSansMyanmar-Regular"]], n
        ),
        "14": lambda rng, n: gen_global_over_ranged(
            rng, [noto["NotoSans-VF"], noto["NotoSerif-VF"]], n
        ),
        "15": lambda rng, n: gen_missing_vs(
            rng, [noto["NotoSansHebrew-Regular"], noto["NotoSans-VF"]], n
        ),
        "21": aat("21"),
        "22": aat("22"),
        "23": aat("23"),
        "broad": lambda rng, n: gen_broad(rng, list(noto.values()), max(1, n // 30)),
    }


def _call_module_gen(
    gen: Callable[..., Iterator[dict]],
    noto: dict[str, Font],
    rng: random.Random,
    n: int,
) -> Iterator[dict]:
    return gen(rng, noto, SYNTH, n)


def module_units(
    noto: dict[str, Font],
) -> tuple[dict[str, Callable[[random.Random, int], Iterator[dict]]], dict[str, int]]:
    """Generators from the family modules (`gen_*.py` beside this file), and their per-unit candidate counts."""
    units: dict[str, Callable[[random.Random, int], Iterator[dict]]] = {}
    counts: dict[str, int] = {}
    here = Path(__file__).resolve().parent
    for path in sorted(here.glob("gen_*.py")):
        mod = importlib.import_module(path.stem)
        for unit, gen in getattr(mod, "UNITS", {}).items():
            units[unit] = functools.partial(_call_module_gen, gen, noto)
        counts.update(getattr(mod, "PER_UNIT", {}))
    return units, counts


def main() -> None:
    """cases.py OUT_DIR SEED [PER_UNIT] [UNIT,UNIT,...]

    Each unit draws from its own random stream (seed and unit id), so changing one generator leaves every other
    unit's candidates as they were. Shaping candidates go to cases.tsv, API candidates to <driver>.tsv.
    """
    out = Path(sys.argv[1])
    seed = int(sys.argv[2])
    per_unit = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    only = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
    out.mkdir(parents=True, exist_ok=True)
    noto = {p.stem: Font(p) for p in sorted(NOTO.glob("*.[ot]tf"))}
    gens = builtin_units(noto)
    extra, counts = module_units(noto)
    gens.update(extra)
    n = 0
    files: dict[str, object] = {}
    per_unit_count: dict[str, int] = {}
    with (out / "meta.jsonl").open("w") as meta:
        for unit, gen in sorted(gens.items()):
            if only and unit not in only:
                continue
            rng = random.Random(f"{seed}:{unit}")
            for c in gen(rng, counts.get(unit, per_unit)):
                n += 1
                c["id"] = f"c{n:06d}"
                drv = c.get("drv", "shape")
                name = "cases.tsv" if drv == "shape" else f"{drv}.tsv"
                if name not in files:
                    files[name] = (out / name).open("w")
                text = ",".join(f"{cp:X}" for cp in c["text"])
                files[name].write(
                    f"{c['id']}\t{c['font']}\t{c['idx']}\t{c['opts']}\t{text}\n"
                )
                meta.write(json.dumps(c) + "\n")
                per_unit_count[unit] = per_unit_count.get(unit, 0) + 1
    for f in files.values():
        f.close()
    print(
        json.dumps(
            {"candidates": n, "files": sorted(files), "per_unit": per_unit_count}
        )
    )


if __name__ == "__main__":
    main()
