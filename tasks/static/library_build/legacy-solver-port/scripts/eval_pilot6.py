#!/usr/bin/env python3
"""usage: eval_pilot6.py PILOT_DIR REF6_DIR [TIMEOUT_S]. Heat 1.0 kcal/mol, charges 0.01 (max abs)."""

import glob, json, os, shutil, subprocess, sys, tempfile, time
import numpy as np

PILOT, REF = sys.argv[1], sys.argv[2]
TMO = int(sys.argv[3]) if len(sys.argv) > 3 else 1800
TOL = dict(heat_of_formation=1.0, atom_charges=0.01)
tmp = tempfile.mkdtemp(prefix="p6eval_")
shutil.copytree(os.path.join(PILOT, "work", "solver"), os.path.join(tmp, "solver"))
py = shutil.which("python3")
env = {"PATH": os.path.dirname(py) + ":/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
err = lambda a, b: (
    float(
        np.max(
            np.abs(
                np.atleast_1d(np.array(a, float)) - np.atleast_1d(np.array(b, float))
            )
        )
    )
    if np.size(a) == np.size(b)
    else float("inf")
)
rows = []
for group in ("visible", "hidden"):
    for jf in sorted(glob.glob(f"{REF}/{group}/*/*.json")):
        name = os.path.basename(jf)[:-5]
        ref = json.load(open(jf))
        work = os.path.join(tmp, "run_" + name)
        os.makedirs(work)
        shutil.copy(jf[:-5] + ".mop", work)
        t = time.time()
        try:
            r = subprocess.run(
                [py, os.path.join(tmp, "solver", "run.py"), name + ".mop", "out.json"],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                timeout=TMO,
            )
            rc, tail = r.returncode, r.stderr[-100:]
        except subprocess.TimeoutExpired:
            rc, tail = "TIMEOUT", ""
        el = time.time() - t
        res = {k: float("inf") for k in TOL}
        try:
            got = json.load(open(os.path.join(work, "out.json")))
            for k in TOL:
                if k in got:
                    res[k] = err(got[k], ref[k])
        except Exception:
            pass
        ok = {k: res[k] <= TOL[k] for k in res}
        rows.append((group, name, rc, el, res, ok))
        print(
            f"{group:8s} {name:16s} n={len(ref['elements']):5d} rc={rc!s:>7s} {el:7.1f}s "
            + " ".join(f"{k[:5]}={res[k]:.2e}{'' if ok[k] else '*'}" for k in res),
            tail.replace("\n", " "),
            flush=True,
        )
for g in ("visible", "hidden"):
    sel = [r for r in rows if r[0] == g]
    if sel:
        print(
            f"\n{g}: {len(sel)} jobs; all-quantities pass {sum(all(r[5].values()) for r in sel)}/{len(sel)}"
        )
        for k in TOL:
            print(f"  {k:20s} {sum(r[5][k] for r in sel)}/{len(sel)}")
print("temp dir", tmp)
