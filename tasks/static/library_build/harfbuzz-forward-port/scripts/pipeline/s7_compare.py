"""S7: compare the Unicode properties and shaping of a 14.3.0 tree regenerated from the shipped Unicode files with 15.0.0.

Host side (`python3 -I scripts/pipeline/s7_compare.py WORK_DIR`); it reads only our own `hbprops` and driver outputs.
Development tooling, never shipped.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

FIELDS = ("gc", "ccc", "script", "mirroring", "decomposition", "composes")


def props(path: Path) -> dict[int, tuple[str, ...]]:
    out = {}
    for line in path.read_text().splitlines():
        cp, *rest = line.split(" ")
        out[int(cp, 16)] = tuple(rest)
    return out


def ranges(cps: list[int]) -> list[str]:
    out: list[list[int]] = []
    for cp in sorted(cps):
        if out and cp == out[-1][1] + 1:
            out[-1][1] = cp
        else:
            out.append([cp, cp])
    return [f"{a:04X}" if a == b else f"{a:04X}..{b:04X}" for a, b in out]


def compare(a: dict, b: dict) -> dict:
    differ = [cp for cp in a if a[cp] != b.get(cp)]
    fields: Counter = Counter()
    for cp in differ:
        for name, x, y in zip(FIELDS, a[cp], b[cp], strict=False):
            if x != y:
                fields[name] += 1
    return {
        "code_points_differ": len(differ),
        "by_field": dict(fields),
        "ranges": ranges(differ)[:40],
    }


def outputs(path: Path) -> dict[str, str]:
    return dict(line.split("\t", 1) for line in path.read_text().splitlines())


def main() -> None:
    work = Path(sys.argv[1])
    runs = work / "runs"
    regen, rel150, rel143 = (
        props(runs / f"props-{n}.out")
        for n in ("regen-14.3.0", "rel-15.0.0", "rel-14.3.0")
    )
    report = {
        "props_14.3.0_vs_15.0.0": compare(rel143, rel150),
        "props_regen_vs_15.0.0": compare(regen, rel150),
    }
    o_regen, o_143, o_150 = (
        outputs(runs / f"{n}.out") for n in ("regen-14.3.0", "rel-14.3.0", "rel-15.0.0")
    )
    moved = [k for k in o_regen if o_regen[k] != o_143.get(k)]
    report["shaping"] = {
        "candidates": len(o_regen),
        "regen_differs_from_14.3.0": len(moved),
        "of_which_equal_15.0.0": sum(o_regen[k] == o_150.get(k) for k in moved),
        "15.0.0_differs_from_14.3.0": sum(o_150[k] != o_143.get(k) for k in o_150),
    }
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
