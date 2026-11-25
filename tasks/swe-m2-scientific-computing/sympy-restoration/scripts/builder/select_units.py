"""Select restorable units from candidates using pristine-run evidence.

usage: select_units.py <work_dir> <out_units.json> [--fanin K] [--max-stmts N] [--max-sec S]
                       [--drop names.json ...]
Inputs in work_dir: candidates.json, r_pristine_trace.json, import_trace.json,
optional r_pristine_seed*.json (determinism runs).
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("work")
ap.add_argument("out")
ap.add_argument("--fanin", type=int, default=20)
ap.add_argument("--max-stmts", type=int, default=100)
ap.add_argument("--max-sec", type=float, default=3.0)
ap.add_argument("--drop", action="append", default=[])
args = ap.parse_args()

W = args.work
cands = json.load(open(os.path.join(W, "candidates.json")))
names = [u["module"] + "." + u["qualname"] for u in cands]
res = json.load(open(os.path.join(W, "r_pristine_trace.json")))["results"]
imp = set(json.load(open(os.path.join(W, "import_trace.json")))["import_called"])

EXCLUDE_PREFIX = (
    "sympy/plotting/",
    "sympy/parsing/",
    "sympy/interactive/",
    "sympy/external/",
    "sympy/testing/",
    "sympy/utilities/_compilation/",
    "sympy/utilities/runtests.py",
    "sympy/utilities/pytest.py",
    "sympy/utilities/autowrap.py",
    "sympy/utilities/codegen.py",
    "sympy/utilities/lambdify.py",
    "sympy/utilities/exceptions.py",
    "sympy/utilities/decorator.py",
    "sympy/core/cache.py",
    "sympy/multipledispatch/",
    "sympy/__init__.py",
    "sympy/abc.py",
    "sympy/conftest.py",
    "sympy/release.py",
    "sympy/this.py",
    "sympy/galgebra.py",
)

why = {}
ok = []
drop_names = set()
for d in args.drop:
    drop_names |= set(json.load(open(d)))

# other determinism runs
seed_runs = []
for p in sorted(glob.glob(os.path.join(W, "r_pristine_seed*.json"))):
    seed_runs.append(json.load(open(p))["results"])

for i, u in enumerate(cands):
    n = names[i]
    r = res.get(n, {"status": "missing"})
    if u["file"].startswith(EXCLUDE_PREFIX):
        why[n] = "path"
    elif n in drop_names:
        why[n] = "dropped"
    elif r["status"] != "pass":
        why[n] = "pristine:" + r["status"]
    elif i not in r.get("called", []):
        why[n] = "self-not-called"
    elif i in imp:
        why[n] = "import-time"
    elif r.get("n_real", 0) < 1 or r.get("tried", 0) < 1:
        why[n] = "no-examples"
    elif u["n_stmts"] > args.max_stmts:
        why[n] = "too-big"
    elif r.get("sec", 0) > args.max_sec:
        why[n] = "slow"
    elif u["name"].startswith("__") and u["name"].endswith("__") and u["name"] in ("__new__", "__init__"):
        why[n] = "ctor"
    elif any(sr.get(n, {}).get("status") != "pass" for sr in seed_runs):
        why[n] = "flaky"
    else:
        ok.append(i)

# iterative fan-in pruning: fan-in counted over currently selected units only
sel = set(ok)
while True:
    fanin = collections.Counter()
    for i in sel:
        for j in res[names[i]].get("called", []):
            if j != i and j in sel:
                fanin[j] += 1
    bad = {j for j in sel if fanin[j] > args.fanin}
    if not bad:
        break
    # remove the worst offenders first (top 25%), then recount
    worst = sorted(bad, key=lambda j: -fanin[j])
    cut = worst[: max(1, len(worst) // 4)]
    for j in cut:
        why[names[j]] = "fanin"
    sel -= set(cut)

sel = sorted(sel, key=lambda i: (cands[i]["file"], cands[i]["body_start"]))
units = []
for k, i in enumerate(sel):
    u = dict(cands[i])
    u["uid"] = f"U{k + 1:04d}"
    u["dotted"] = names[i]
    u["cidx"] = i
    units.append(u)
idx2uid = {u["cidx"]: u["uid"] for u in units}
for u in units:
    r = res[u["dotted"]]
    u["deps"] = sorted(idx2uid[j] for j in r.get("called", []) if j in idx2uid and j != u["cidx"])
    u["n_examples"] = r.get("n_real", 0)
    u["sec"] = r.get("sec", 0)
json.dump(units, open(args.out, "w"))
c = collections.Counter(why.values())
print("selected", len(units), "| dropped:", dict(c))
k = collections.Counter("/".join(u["file"].split("/")[:2]) for u in units)
print(k.most_common(40))
fo = sorted(len(u["deps"]) for u in units)
print("deps per unit: p50", fo[len(fo) // 2], "p90", fo[int(len(fo) * 0.9)], "max", fo[-1])
st = sorted(u["n_stmts"] for u in units)
print("stmts: p25", st[len(st) // 4], "p50", st[len(st) // 2], "p75", st[len(st) * 3 // 4], "p90", st[int(len(st) * 0.9)], "sum_lines", sum(u["n_lines"] for u in units))
