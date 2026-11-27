#!/usr/bin/env python3
"""usage: eval_pilot7.py PILOT_DIR SCALE_REF_DIR FMT_REF_DIR [TIMEOUT_S=1800] [ONLY=scale|fmt]
scale: heat 0.1, charges 0.005 (max abs). fmt: step-1 tolerances; internal coords r 5e-3, angle 0.2, dihedral 0.5 (mod 360)."""

import glob, json, os, shutil, subprocess, sys, tempfile, time
import numpy as np

PILOT, SREF, FREF = sys.argv[1:4]
TMO = int(sys.argv[4]) if len(sys.argv) > 4 else 1800
ONLY = sys.argv[5] if len(sys.argv) > 5 else "both"
SC = dict(heat_of_formation=0.1, atom_charges=0.005)
SP = dict(
    heat_of_formation=1e-4, atom_charges=1e-5, ionization_potential=1e-4, dipole=1e-4
)
OP = dict(
    heat_of_formation=5e-3,
    geometry=3e-3,
    atom_charges=1e-3,
    ionization_potential=1e-3,
    dipole=1e-3,
)
tmp = tempfile.mkdtemp(prefix="p7eval_")
shutil.copytree(os.path.join(PILOT, "work", "solver"), os.path.join(tmp, "solver"))
py = shutil.which("python3")
env = {"PATH": os.path.dirname(py) + ":/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}


def err(a, b):
    a, b = np.atleast_1d(np.array(a, float)), np.atleast_1d(np.array(b, float))
    return float(np.max(np.abs(a - b))) if a.shape == b.shape else float("inf")


def dist(x):
    x = np.array(x, float).reshape(-1, 3)
    return np.linalg.norm(x[:, None] - x[None], axis=-1)


def ic_err(got, ref):
    g, r = np.array(got, float), np.array(ref, float)
    if g.shape != r.shape:
        return (inf := float("inf"),) * 3
    d = np.abs(g - r)
    dd = np.abs((g[:, 2] - r[:, 2] + 180) % 360 - 180)
    return float(d[:, 0].max()), float(d[:, 1].max()), float(dd.max())


rows = []
for group in ("visible", "hidden"):
    for base, kindsel in ((SREF, "scale"), (FREF, "fmt")):
        if ONLY not in ("both", kindsel):
            continue
        for jf in sorted(glob.glob(f"{base}/{group}/*/*.json")):
            name = os.path.basename(jf)[:-5]
            ref = json.load(open(jf))
            kind = ref["kind"]
            work = os.path.join(tmp, "run_" + name)
            os.makedirs(work)
            for f in glob.glob(jf[:-5] + ".*"):
                if not f.endswith(".json"):
                    shutil.copy(f, work)
            t = time.time()
            try:
                r = subprocess.run(
                    [
                        py,
                        os.path.join(tmp, "solver", "run.py"),
                        name + ".mop",
                        "out.json",
                    ],
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
            if kind == "scale":
                tol = SC
            else:
                tol = dict(OP if "optimized_geometry" in ref else SP)
                tol["internal"] = 1
            res = {k: float("inf") for k in tol}
            try:
                got = json.load(open(os.path.join(work, "out.json")))
                for k in tol:
                    if k == "geometry":
                        res[k] = err(
                            dist(got["optimized_geometry"]),
                            dist(ref["optimized_geometry"]),
                        )
                    elif k == "internal":
                        if "internal_coordinates" in ref:
                            a, b, c = ic_err(
                                got.get("internal_coordinates", []),
                                ref["internal_coordinates"],
                            )
                            res[k] = (
                                0.0
                                if (a <= 5e-3 and b <= 0.2 and c <= 0.5)
                                else max(a, b, c)
                            )
                        else:
                            res[k] = 0.0
                    elif k in got:
                        res[k] = err(got[k], ref[k])
            except Exception:
                pass
            ok = {k: res[k] <= tol[k] for k in res}
            rows.append((group, kind, ref.get("variant", ""), name, ok))
            print(
                f"{group:8s} {name:26s} rc={rc!s:>7s} {el:7.1f}s "
                + " ".join(f"{k[:5]}={res[k]:.1e}{'' if ok[k] else '*'}" for k in res),
                tail.replace("\n", " "),
                flush=True,
            )
for g in ("visible", "hidden"):
    for kind in ("scale", "fmt"):
        sel = [r for r in rows if r[0] == g and r[1] == kind]
        if sel:
            print(
                f"{g} {kind}: {len(sel)} jobs; all-quantities pass {sum(all(r[4].values()) for r in sel)}/{len(sel)}"
            )
            for v in sorted({r[2] for r in sel}):
                s2 = [r for r in sel if r[2] == v]
                print(
                    f"   {v or '-':6s} {sum(all(r[4].values()) for r in s2)}/{len(s2)}"
                )
print("temp dir", tmp)
