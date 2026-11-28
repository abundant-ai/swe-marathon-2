"""Shared pieces of the candidate generators: the font reader, the case records and a few code points.

Runs inside the pipeline image only (it imports fontTools and reads the downloaded fonts). Development tooling, never
shipped. Generator modules (`gen_*.py` beside this file) import from here.

A case record is a dict with:
- `unit`: the unit id (see units.tsv), or `broad`;
- `kind`: `cand` (the sweep decides what it becomes) or `broad`;
- `drv`: which driver runs it: `shape` (tests/driver/hbdrv.c), `api` (hbapi.c), `meta` (hbmeta.c), or `api33`,
  `api48`, `api49`, `api51` (the separately compiled probes of what 14.3.0 does not have: the script constants of
  unit 33 and the functions of units 48, 49 and 51);
- `font`, `idx`: the font file and face index;
- `opts`: `key=value` pairs joined by `;` (shaping options, or for the API drivers `cmd=NAME;...`);
- `text`: a list of integers (code points for shaping; command arguments for the API drivers);
- `nb`: which side of the unit's stated condition the candidate sits on: `in` or `in:<part>` (inside it, expected
  to change; the part names which piece of the condition, where the generator knows it), `b:<name>` (a boundary
  neighbour: one stated condition negated, expected to stay as 14.3.0 has it), or `x:<name>` (left out: swept for
  the record, never graded).
"""

from __future__ import annotations

import unicodedata
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
        self.glyph_of: dict[int, str] = dict(font.getBestCmap() or {})
        self.cmap = set(self.glyph_of)
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


def case(
    unit: str,
    kind: str,
    font: Font | Path | str,
    text: list[int],
    nb: str = "",
    drv: str = "shape",
    **opts: object,
) -> dict:
    """One candidate. `nb` names which neighbour of the unit's condition it is (analysis only, never shaped)."""
    opt = ";".join(f"{k}={v}" for k, v in opts.items())
    out = {
        "unit": unit,
        "kind": kind,
        "font": str(font.path if isinstance(font, Font) else font),
        "idx": 0,
        "opts": opt,
        "text": text,
    }
    if nb:
        out["nb"] = nb
    if drv != "shape":
        out["drv"] = drv
    return out


def api_case(
    unit: str,
    font: Font | Path | str,
    cmd: str,
    args: list[int] | None = None,
    nb: str = "",
    drv: str = "api",
    idx: int = 0,
    **params: object,
) -> dict:
    """A candidate for an API driver: `cmd` and its `params` go to `opts`, integer arguments to `text`."""
    out = case(unit, "cand", font, list(args or []), nb=nb, drv=drv, cmd=cmd, **params)
    out["idx"] = idx
    return out


def init_inputs(path: Path) -> set[str]:
    """Glyphs that an `init` lookup of the font substitutes (single, multiple, alternate, ligature; extensions unwrapped)."""
    font = TTFont(str(path), lazy=True)
    if "GSUB" not in font or not font["GSUB"].table.FeatureList:
        return set()
    table = font["GSUB"].table
    lookups = {
        i
        for rec in table.FeatureList.FeatureRecord
        if rec.FeatureTag == "init"
        for i in rec.Feature.LookupListIndex
    }
    out: set[str] = set()
    for i in lookups:
        lookup = table.LookupList.Lookup[i]
        for sub in lookup.SubTable:
            if lookup.LookupType == 7:
                sub = sub.ExtSubTable
            for attr in ("mapping", "alternates", "ligatures"):
                out |= set(getattr(sub, attr, None) or {})
    return out
