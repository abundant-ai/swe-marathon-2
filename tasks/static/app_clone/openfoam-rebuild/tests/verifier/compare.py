"""Compares output with the expected output.

Text is compared exactly. Integers must be equal. Any other number may differ by max(tolerance
for its path, one unit in the last digit printed by either side, at most one in the sixth
significant digit in exponent form); binary numbers by a relative 1e-12. Files the reader cannot interpret
must be identical byte for byte. With calibrating=True nothing is
judged: the largest difference per path is recorded instead.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import numpy as np

from . import foamfile as ff
from . import normalise as N

_NUM = re.compile(r"(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?(?![\w.])")
_BINARY_REL = 1e-12
MAX_REPORTED = 20


@dataclass
class Result:
    mismatches: list = field(default_factory=list)  # human-readable, first MAX_REPORTED
    n_mismatches: int = 0
    spreads: dict = field(default_factory=dict)  # path -> largest |expected - other|
    int_paths: set = field(
        default_factory=set
    )  # paths whose differing values are integers

    @property
    def ok(self) -> bool:
        return self.n_mismatches == 0

    def fail(self, path: str, msg: str):
        self.n_mismatches += 1
        if len(self.mismatches) < MAX_REPORTED:
            self.mismatches.append(f"{path}: {msg}")

    def spread(self, path: str, d: float):
        self.spreads[path] = max(self.spreads.get(path, 0.0), d)


def _allowance(ug, uc, g):
    """Rounding allowance for numbers written with units ug and uc (ff.unit; NaN: integer),
    expected values g. Two integers: none. Otherwise the finer printed precision, where an
    expected integer below 10^6 may be a number OpenFOAM printed to six significant digits
    (larger ones it prints in exponent form)."""
    ug, uc, g = (np.asarray(x, dtype=float) for x in (ug, uc, g))
    with np.errstate(divide="ignore"):
        sixth = np.where(
            (g == 0) | (np.abs(g) >= 1e6),
            0.0,
            10.0 ** (np.floor(np.log10(np.abs(g))) - 5),
        )
    both = np.isnan(ug) & np.isnan(uc)
    return np.where(both, 0.0, np.fmin(np.where(np.isnan(ug), sixth, ug), uc))


def _numbers(path, g, c, units, tols, res: Result, calibrating: bool):
    """g, c: arrays of equal shape; units: rounding allowance per element (or scalar)."""
    g = np.asarray(g, dtype=float)
    c = np.asarray(c, dtype=float)
    both_nan = np.isnan(g) & np.isnan(c)
    same_inf = np.isinf(g) & (g == c)
    with np.errstate(invalid="ignore"):
        d = np.where(both_nan | same_inf, 0.0, np.abs(g - c))
    d = np.where(np.isnan(d), np.inf, d)
    if calibrating:
        res.spread(path, float(d.max()) if d.size else 0.0)
        return
    allowed = np.maximum(tols.get(path, 0.0), units)
    # plus the error of reading the two printed numbers into floats
    bad = d > allowed + 4 * np.finfo(float).eps * np.maximum(np.abs(g), np.abs(c))
    if bad.any():
        idx = np.argwhere(bad)
        i = tuple(idx[0])
        res.fail(
            path,
            f"{int(bad.sum())} of {g.size} numbers differ; first at {list(i)}: "
            f"expected {g[i]!r}, got {c[i]!r} (allowed {float(np.broadcast_to(allowed, g.shape)[i]):.3g})",
        )


def _walk(path, g, c, tols, res, calibrating):
    tg, tc = type(g), type(c)
    if isinstance(g, ff.Num) and isinstance(c, ff.Num):
        if g.is_int and c.is_int and path not in tols:
            if int(g.text) != int(c.text):
                if calibrating:
                    res.spread(path, abs(g.value - c.value))
                    res.int_paths.add(path)
                else:
                    res.fail(path, f"expected {g.text}, got {c.text}")
            return
        _numbers(
            path,
            [g.value],
            [c.value],
            _allowance(ff.unit(g.text), ff.unit(c.text), g.value),
            tols,
            res,
            calibrating,
        )
        return
    if isinstance(g, ff.Arr) and isinstance(c, ff.Arr):
        if g.data.shape != c.data.shape:
            res.fail(path, f"list of shape {g.data.shape} expected, got {c.data.shape}")
            return
        if g.texts is not None:
            units = _allowance(
                g.texts, c.texts if c.texts is not None else np.nan, g.data
            )
        else:
            units = _BINARY_REL * (np.abs(g.data).max() if g.data.size else 0.0)
        _numbers(path, g.data, c.data, units, tols, res, calibrating)
        return
    if (
        isinstance(g, ff.Arr)
        and isinstance(c, ff.Seq)
        and not c.items
        and g.data.size == 0
    ):
        return
    if tg is not tc:
        res.fail(path, f"{_describe(g)} expected, got {_describe(c)}")
        return
    if isinstance(g, (ff.Word, ff.Str)):
        if str(g) != str(c):
            res.fail(path, f"{g!r} expected, got {c!r}")
        return
    if isinstance(g, ff.Seq):
        if g.kind != c.kind or len(g.items) != len(c.items):
            res.fail(
                path,
                f"{g.kind}-list of {len(g.items)} items expected, got {c.kind}-list of {len(c.items)}",
            )
            return
        for i, (a, b) in enumerate(zip(g.items, c.items)):
            _walk(f"{path}[{i}]", a, b, tols, res, calibrating)
        return
    if isinstance(g, ff.Dict):
        # entries in any order; a key written twice is matched in order
        kg, kc = g.keys(), c.keys()
        if sorted(map(str, kg)) != sorted(map(str, kc)):
            missing = [str(k) for k in kg if k not in kc]
            extra = [str(k) for k in kc if k not in kg]
            res.fail(
                path or "/",
                f"keys differ (missing {missing[:5]}, unexpected {extra[:5]}"
                + (", repeated differently" if not missing and not extra else "")
                + ")",
            )
            return
        rest = {}
        for k, vc in c.entries:
            rest.setdefault(str(k), []).append(vc)
        for k, vg in g.entries:
            _value(
                f"{path}/{k if k is not None else '-'}",
                vg,
                rest[str(k)].pop(0),
                tols,
                res,
                calibrating,
            )
        return
    res.fail(path, f"cannot compare {_describe(g)}")


def _value(path, vg, vc, tols, res, calibrating):
    if len(vg) != len(vc):
        res.fail(path, f"{len(vg)} items expected, got {len(vc)}")
        return
    for j, (a, b) in enumerate(zip(vg, vc)):
        _walk(path if len(vg) == 1 else f"{path}#{j}", a, b, tols, res, calibrating)


def _describe(x):
    if isinstance(x, ff.Num):
        return f"number {x.text}"
    if isinstance(x, (ff.Word, ff.Str)):
        return f"{type(x).__name__.lower()} {str(x)!r}"
    if isinstance(x, ff.Arr):
        return f"numeric list {x.data.shape}"
    if isinstance(x, ff.Seq):
        return f"{x.kind}-list of {len(x.items)}"
    return type(x).__name__


# ---- printed output and other text files ----


def skeleton(line: str) -> str:
    return _NUM.sub("#", line)


def compare_lines(
    expected: list[str],
    cand: list[str],
    tols=None,
    res=None,
    prefix="",
    calibrating=False,
) -> Result:
    """Line by line: text exact, numbers within tolerance. A number's path is the line with
    numbers replaced by '#', plus its position in the line."""
    tols = tols or {}
    res = res or Result()
    if len(expected) != len(cand):
        res.fail(
            prefix or "output",
            f"{len(expected)} lines expected, got {len(cand)}"
            + _first_diff(expected, cand),
        )
        return res
    for n, (lg, lc) in enumerate(zip(expected, cand), 1):
        sg, sc = skeleton(lg), skeleton(lc)
        if sg != sc:
            res.fail(f"{prefix}line {n}", f"expected {lg!r}, got {lc!r}")
            continue
        for k, (mg, mc) in enumerate(zip(_NUM.finditer(lg), _NUM.finditer(lc))):
            key = f"{prefix}{sg}#{k}"
            g = ff.Num(float(mg.group()), mg.group())
            c = ff.Num(float(mc.group()), mc.group())
            sub = Result()
            _walk(key, g, c, tols, sub, calibrating)
            for p, d in sub.spreads.items():
                res.spread(p, d)
            res.int_paths |= sub.int_paths
            if sub.n_mismatches:
                res.fail(f"{prefix}line {n}", f"expected {lg!r}, got {lc!r}")
                break
    return res


def _first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b), 1):
        if skeleton(x) != skeleton(y):
            return f"; first difference at line {i}: expected {x!r}, got {y!r}"
    i = min(len(a), len(b))
    return f"; first extra line {i + 1}: {(a if len(a) > len(b) else b)[i]!r}"


# ---- files and case folders ----


def _is_foam(data: bytes) -> bool:
    head = data[:4096]
    if head[:2] == b"\x1f\x8b":
        return True
    return b"FoamFile" in head


def compare_file(
    exp_path, cand_path, tols=None, res=None, prefix="", calibrating=False
) -> Result:
    tols = tols or {}
    res = res or Result()
    with open(exp_path, "rb") as f:
        gd = f.read()
    with open(cand_path, "rb") as f:
        cd = f.read()
    if _is_foam(gd):
        try:
            g = ff.parse(gd)
        except ff.ParseError:
            if gd != cd:
                res.fail(prefix, "differs (compared byte for byte)")
            return res
        try:
            c = ff.parse(cd)
        except ff.ParseError as e:
            res.fail(prefix, f"not a valid OpenFOAM file: {e}")
            return res
        _walk(prefix, g, c, tols, res, calibrating)
        return res
    try:
        gt, ct = gd.decode("utf-8"), cd.decode("utf-8")
    except UnicodeDecodeError:
        if gd != cd:
            res.fail(prefix, "binary file differs")
        return res
    gl = [N.strip_dates(x) for x in gt.split("\n")]
    cl = [N.strip_dates(x) for x in ct.split("\n")]
    return compare_lines(gl, cl, tols, res, prefix + ":", calibrating)


def list_files(root, ignore=()) -> list[str]:
    out = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(d, f), root)
            if not any(re.fullmatch(p, rel) for p in ignore):
                out.append(rel)
    return out


def compare_tree(
    exp_dir, cand_dir, files=None, tols=None, ignore=(), calibrating=False
) -> Result:
    """Same set of files (or just `files`), each compared."""
    tols = tols or {}
    res = Result()
    gf = files if files is not None else list_files(exp_dir, ignore)
    if files is None:
        cf = list_files(cand_dir, ignore)
        missing = sorted(set(gf) - set(cf))
        extra = sorted(set(cf) - set(gf))
        for m in missing[:MAX_REPORTED]:
            res.fail(m, "missing")
        res.n_mismatches += max(0, len(missing) - MAX_REPORTED)
        for e in extra[:MAX_REPORTED]:
            res.fail(e, "not expected")
        res.n_mismatches += max(0, len(extra) - MAX_REPORTED)
    for rel in gf:
        cp = os.path.join(cand_dir, rel)
        if not os.path.isfile(cp):
            if files is not None:
                res.fail(rel, "missing")
            continue
        compare_file(os.path.join(exp_dir, rel), cp, tols, res, rel, calibrating)
    return res


def spreads_tree(a, b, files=None, ignore=()) -> Result:
    return compare_tree(a, b, files, ignore=ignore, calibrating=True)
