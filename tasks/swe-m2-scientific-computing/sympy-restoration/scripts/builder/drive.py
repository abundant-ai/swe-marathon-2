"""Parallel driver: run dt_run.py for many modules, gather results.

usage: drive.py <tree_root> <candidates.json> <out.json> [--trace] [--workers N]
                [--timeout SEC] [--hashseed S] [--only names.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("cands")
ap.add_argument("out")
ap.add_argument("--trace", action="store_true")
ap.add_argument("--workers", type=int, default=10)
ap.add_argument("--timeout", type=float, default=20.0)
ap.add_argument("--hashseed", default="0")
ap.add_argument("--only")
args = ap.parse_args()

HERE = os.path.dirname(os.path.abspath(__file__))
cands = json.load(open(args.cands))
only = set(json.load(open(args.only))) if args.only else None
bymod = collections.defaultdict(list)
for u in cands:
    nm = u["module"] + "." + u["qualname"]
    if only is None or nm in only:
        bymod[u["module"]].append(nm)


def run(mod):
    names = bymod[mod]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(names, f)
        nf = f.name
    cmd = [sys.executable, os.path.join(HERE, "dt_run.py"), args.root, mod, "--names", nf, "--timeout", str(args.timeout)]
    if args.trace:
        cmd += ["--trace", os.path.abspath(args.cands)]
    env = dict(os.environ, PYTHONHASHSEED=str(args.hashseed), PYTHONDONTWRITEBYTECODE="1")
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout * len(names) + 300, env=env)
        out, err = p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        out, err = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "TIMEOUT"
    os.unlink(nf)
    recs = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                recs.append(json.loads(line))
            except Exception:  # noqa: BLE001
                pass
    return mod, recs, err[-2000:], round(time.time() - t0, 1)


res = {}
errs = {}
t0 = time.time()
with ThreadPoolExecutor(args.workers) as ex:
    for mod, recs, err, sec in ex.map(run, sorted(bymod)):
        got = {r["name"] for r in recs if "name" in r}
        for r in recs:
            if "name" in r:
                res[r["name"]] = r
            elif "module_error" in r:
                errs[mod] = r["module_error"]
        missing = [n for n in bymod[mod] if n not in got]
        for n in missing:
            res[n] = {"name": n, "status": "missing"}
        if err.strip() and (missing or mod in errs):
            errs.setdefault(mod, err[-500:])
json.dump({"results": res, "module_errors": errs}, open(args.out, "w"))
c = collections.Counter(r["status"] for r in res.values())
print(dict(c), "module_errors:", len(errs), "sec:", round(time.time() - t0, 1))
