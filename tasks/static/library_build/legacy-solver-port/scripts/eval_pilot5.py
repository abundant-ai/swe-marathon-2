#!/usr/bin/env python3
"""usage: eval_pilot5.py PILOT_DIR REF5_DIR  (FORCE jobs). Heat 1e-4, ZPE 1e-3, freqs 0.05 cm-1."""

import glob, json, os, shutil, subprocess, sys, tempfile, time
import numpy as np

PILOT, REF = sys.argv[1], sys.argv[2]
TOL = dict(
    heat_of_formation=1e-4,
    zero_point_energy=1e-3,
    frequencies=float(os.environ.get("FREQ_TOL", "0.05")),
)
tmp = tempfile.mkdtemp(prefix="p5eval_")
shutil.copytree(os.path.join(PILOT, "work", "solver"), os.path.join(tmp, "solver"))
py = shutil.which("python3")
env = {"PATH": os.path.dirname(py) + ":/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}


def err(a, b):
    a, b = np.atleast_1d(np.array(a, float)), np.atleast_1d(np.array(b, float))
    return float(np.max(np.abs(a - b))) if a.shape == b.shape else float("inf")


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
                timeout=900,
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
                    a = sorted(got[k]) if k == "frequencies" else got[k]
                    res[k] = err(a, ref[k])
        except Exception:
            pass
        ok = {k: res[k] <= TOL[k] for k in res}
        rows.append((group, name, rc, el, res, ok, tail))
        print(
            f"{group:8s} {name:20s} rc={rc!s:>3s} {el:6.1f}s "
            + " ".join(f"{k[:5]}={res[k]:.1e}{'' if ok[k] else '*'}" for k in res),
            "" if rc == 0 else tail.replace("\n", " "),
        )
for g in ("visible", "hidden"):
    sel = [r for r in rows if r[0] == g]
    if sel:
        print(
            f"\n{g}: {len(sel)} jobs; all-quantities pass {sum(all(r[5].values()) for r in sel)}/{len(sel)}"
        )
        for k in TOL:
            print(f"  {k:22s} {sum(r[5][k] for r in sel)}/{len(sel)}")
print("temp dir", tmp)
