#!/usr/bin/env python3
"""Evaluate a pilot-3 candidate port on hidden and visible molecules.

usage: eval_pilot3.py PILOT_DIR REF_DIR

PILOT_DIR has work/solver/. The solver is copied alone into a fresh temp
directory (mopac-src and examples absent), then run on every molecule.
REF_DIR is the output of make_pilot3.py (visible/, hidden/).
"""

import glob, json, os, shutil, subprocess, sys, tempfile, time
import numpy as np

PILOT, REF = sys.argv[1], sys.argv[2]
TOL = dict(
    heat_of_formation=1e-4,
    gradients=1e-3,
    atom_charges=1e-5,
    eigenvalues=1e-4,
    ionization_potential=1e-4,
    dipole=1e-4,
)
LOOSE = {k: v * 100 for k, v in TOL.items()}

tmp = tempfile.mkdtemp(prefix="p3eval_")
shutil.copytree(os.path.join(PILOT, "work", "solver"), os.path.join(tmp, "solver"))
env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONDONTWRITEBYTECODE": "1"}
py = shutil.which("python3")
env["PATH"] = os.path.dirname(py) + ":" + env["PATH"]


def err(a, b):
    a, b = np.atleast_1d(np.array(a, float)), np.atleast_1d(np.array(b, float))
    if a.shape != b.shape:
        return float("inf")
    return float(np.max(np.abs(a - b)))


rows, summary = [], {}
for group in ("visible", "hidden"):
    for jf in sorted(glob.glob(f"{REF}/{group}/*/*.json")):
        name = os.path.basename(jf)[:-5]
        ref = json.load(open(jf))
        work = os.path.join(tmp, "run_" + name)
        os.makedirs(work)
        shutil.copy(jf[:-5] + ".mop", work)
        out = os.path.join(work, "out.json")
        t = time.time()
        try:
            r = subprocess.run(
                [py, os.path.join(tmp, "solver", "run.py"), name + ".mop", "out.json"],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            rc, tail = r.returncode, r.stderr[-200:]
        except subprocess.TimeoutExpired:
            rc, tail = "TIMEOUT", ""
        el = time.time() - t
        res = {}
        if os.path.exists(out):
            try:
                got = json.load(open(out))
            except Exception as e:
                got = {}
            for k in TOL:
                res[k] = err(got[k], ref[k]) if k in got else float("inf")
        else:
            res = {k: float("inf") for k in TOL}
        strict = {k: res[k] <= TOL[k] for k in TOL}
        loose = {k: res[k] <= LOOSE[k] for k in TOL}
        rows.append((group, name, rc, el, res, strict, loose, tail))

print(
    f"{'set':8s} {'molecule':15s} {'rc':>3s} {'s':>5s} "
    + " ".join(f"{k[:8]:>9s}" for k in TOL)
)
for g, n, rc, el, res, strict, loose, tail in rows:
    print(
        f"{g:8s} {n:15s} {rc!s:>3s} {el:5.1f} "
        + " ".join(f"{res[k]:9.2e}" for k in TOL),
        "" if rc == 0 else tail.replace("\n", " ")[-80:],
    )
for g in ("visible", "hidden"):
    sel = [r for r in rows if r[0] == g]
    if not sel:
        continue
    print(f"\n{g}: {len(sel)} molecules")
    for k in TOL:
        s = sum(r[5][k] for r in sel)
        l = sum(r[6][k] for r in sel)
        print(f"  {k:22s} strict {s}/{len(sel)}   100x-looser {l}/{len(sel)}")
    allok = sum(all(r[5].values()) for r in sel)
    print(f"  all quantities strict: {allok}/{len(sel)}")
print("\ntemp dir", tmp)
