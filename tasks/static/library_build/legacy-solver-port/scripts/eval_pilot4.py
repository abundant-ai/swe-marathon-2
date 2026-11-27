#!/usr/bin/env python3
"""Evaluate a pilot-4 candidate on hidden and visible molecules.

usage: eval_pilot4.py PILOT_DIR REF_DIR

Copies work/solver alone into a clean temp dir and runs every job.
Single points: heat 1e-4, gradients 1e-3, charges 1e-5, IP 1e-4, dipole 1e-4.
Optimizations: heat 5e-3, pairwise distances 3e-3, charges 1e-3, IP 1e-3, dipole 1e-3.
"""

import glob, json, os, shutil, subprocess, sys, tempfile, time
import numpy as np

PILOT, REF = sys.argv[1], sys.argv[2]
TOL = {
    "sp": dict(
        heat_of_formation=1e-4,
        gradients=1e-3,
        atom_charges=1e-5,
        ionization_potential=1e-4,
        dipole=1e-4,
    ),
    "opt": dict(
        heat_of_formation=5e-3,
        geometry=3e-3,
        atom_charges=1e-3,
        ionization_potential=1e-3,
        dipole=1e-3,
    ),
}
tmp = tempfile.mkdtemp(prefix="p4eval_")
shutil.copytree(os.path.join(PILOT, "work", "solver"), os.path.join(tmp, "solver"))
py = shutil.which("python3")
env = {"PATH": os.path.dirname(py) + ":/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}


def err(a, b):
    a, b = np.atleast_1d(np.array(a, float)), np.atleast_1d(np.array(b, float))
    return float(np.max(np.abs(a - b))) if a.shape == b.shape else float("inf")


def dist(x):
    x = np.array(x, float).reshape(-1, 3)
    return np.linalg.norm(x[:, None] - x[None], axis=-1)


rows = []
for group in ("visible", "hidden"):
    for jf in sorted(glob.glob(f"{REF}/{group}/*/*.json")):
        name = os.path.basename(jf)[:-5]
        ref = json.load(open(jf))
        kind = ref["kind"]
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
                timeout=900,
            )
            rc, tail = r.returncode, r.stderr[-120:]
        except subprocess.TimeoutExpired:
            rc, tail = "TIMEOUT", ""
        el = time.time() - t
        res = {k: float("inf") for k in TOL[kind]}
        try:
            got = json.load(open(os.path.join(work, "out.json")))
            for k in TOL[kind]:
                if k == "geometry":
                    res[k] = (
                        err(
                            dist(got["optimized_geometry"]),
                            dist(ref["optimized_geometry"]),
                        )
                        if "optimized_geometry" in got
                        else float("inf")
                    )
                elif k in got:
                    res[k] = err(got[k], ref[k])
        except Exception:
            pass
        ok = {k: res[k] <= TOL[kind][k] for k in res}
        rows.append((group, name, kind, rc, el, res, ok, tail))

for g, n, kind, rc, el, res, ok, tail in rows:
    print(
        f"{g:8s} {n:22s} {kind:3s} rc={rc!s:>3s} {el:6.1f}s "
        + " ".join(f"{k[:5]}={res[k]:.1e}{'' if ok[k] else '*'}" for k in res),
        "" if rc == 0 else tail.replace("\n", " "),
    )
for g in ("visible", "hidden"):
    for kind in ("sp", "opt"):
        sel = [r for r in rows if r[0] == g and r[2] == kind]
        if not sel:
            continue
        print(
            f"\n{g} {kind}: {len(sel)} jobs; all-quantities pass {sum(all(r[6].values()) for r in sel)}/{len(sel)}"
        )
        for k in TOL[kind]:
            print(f"  {k:22s} {sum(r[6][k] for r in sel)}/{len(sel)}")
print("\ntemp dir", tmp)
