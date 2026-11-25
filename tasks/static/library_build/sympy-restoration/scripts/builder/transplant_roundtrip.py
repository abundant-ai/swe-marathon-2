"""Oracle transplant test: skeleton + bodies from pristine -> candidate; all unit doctests must pass."""

import collections
import os
import shutil
import sys
import time
from pathlib import Path

B = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(B, "task_src"))
import restorelib

skel, work, cand, units_path = sys.argv[1:5]
units, byfile = restorelib.load_units(units_path)
if os.path.exists(cand):
    shutil.rmtree(cand)
shutil.copytree(
    os.path.join(skel, "sympy"),
    os.path.join(cand, "sympy"),
    ignore=shutil.ignore_patterns("__pycache__"),
)
t0 = time.time()
states, notes = restorelib.build_candidate(skel, work, cand, byfile, {})
print(
    "transplant sec",
    round(time.time() - t0, 1),
    collections.Counter(s.split(":")[0] for s in states.values()),
    "notes",
    len(notes),
)
bad = {u: s for u, s in states.items() if s != "restored"}
print("non-restored sample:", list(bad.items())[:8])
# identical to pristine?
diff = [
    rel
    for rel in byfile
    if Path(os.path.join(cand, rel)).read_text()
    != Path(os.path.join(work, rel)).read_text()
]
print("candidate files differing from source tree:", len(diff), diff[:5])
run = collections.defaultdict(list)
for u in units:
    if states[u["uid"]] == "restored":
        run[u["module"]].append(u["dotted"])
t0 = time.time()
res, tamper = restorelib.run_doctests(
    cand, run, os.path.join(B, "task_src", "rdoctest.py"), workers=10
)
c = collections.Counter(r["status"] for r in res.values())
print("doctest sec", round(time.time() - t0, 1), dict(c), "tamper", tamper)
for n, r in list(res.items()):
    if r["status"] != "pass":
        print(
            "  ",
            n,
            r["status"],
            (r.get("exc") or "")[:200],
            (r.get("out") or "")[-300:].replace("\n", " | "),
        )
        break
