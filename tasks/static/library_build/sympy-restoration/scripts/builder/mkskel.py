"""Build a skeleton tree: copy pristine package, blank selected unit bodies.

usage: mkskel.py <pristine_root> <units.json> <out_root> [--pkg sympy]
Writes <out_root>/<pkg>/... and <out_root>/units_skel.json (line numbers in the skeleton).
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from units import blank_source, find_units

ap = argparse.ArgumentParser()
ap.add_argument("pristine")
ap.add_argument("units")
ap.add_argument("out")
ap.add_argument("--pkg", default="sympy")
args = ap.parse_args()

units = json.loads(Path(args.units).read_text())
byfile = collections.defaultdict(list)
for u in units:
    byfile[u["file"]].append(u)

dst = os.path.join(args.out, args.pkg)
if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(
    os.path.join(args.pristine, args.pkg),
    dst,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
)
skel_units = []
for f, us in sorted(byfile.items()):
    p = os.path.join(args.out, f)
    src = Path(os.path.join(args.pristine, f)).read_text(encoding="utf-8")
    new = blank_source(src, us)
    Path(p).write_text(new, encoding="utf-8")
    # recompute positions in the skeleton
    found = {x["qualname"]: x for x in find_units(new, f)}
    # placeholders have no doctest-bearing change, so find_units still sees them
    for u in us:
        x = found.get(u["qualname"])
        assert x is not None, (f, u["qualname"])
        assert x["body_start"] == x["body_end"], (f, u["qualname"], x)
        v = dict(u)
        v.update(
            {
                k: x[k]
                for k in ("def_line", "deco_line", "doc_end", "body_start", "body_end")
            }
        )
        skel_units.append(v)
skel_units.sort(key=lambda u: u["uid"])
with open(os.path.join(args.out, "units_skel.json"), "w") as stream:
    json.dump(skel_units, stream)
print("skeleton written:", dst, "units:", len(skel_units), "files:", len(byfile))
