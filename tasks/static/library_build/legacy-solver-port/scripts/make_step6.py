"""Build the step-6 (COSMO gradients) references with the original MOPAC. Run inside the mopac-linref image:

  docker run --rm -v <task>/steps/01-port-pm7/tests/private:/src:ro -v <out>:/out mopac-linref python3 /path/make_step6.py

Inputs: every single-point molecule of the step-1 references, geometry perturbed (seeded), keyword EPS=<value> added.
The rotation spread printed here is not a reproducibility criterion for COSMO (the surface depends on the frame); see README.
"""

import glob
import json
import os
import random
import re
import subprocess
import tempfile

import numpy as np

SRC, OUT = "/src", "/out"
EPS = [78.4, 78.4, 46.7, 37.5, 24.3, 10.4, 4.81]
VISIBLE = {"water", "methane", "ammonium", "formaldehyde"}


def fl(block):
    return [float(x.replace("D", "E")) for x in block.split()]


def run(kw, el, xyz):
    d = tempfile.mkdtemp()
    body = "".join(
        f" {e} {v[0]:.8f} 1 {v[1]:.8f} 1 {v[2]:.8f} 1\n" for e, v in zip(el, xyz)
    )
    open(f"{d}/j.mop", "w").write(f"{kw}\nx\n\n{body}")
    subprocess.run(
        ["env", "-i", "PATH=/usr/bin:/bin", "/build/mopac", "j.mop"],
        cwd=d,
        capture_output=True,
        timeout=900,
        check=False,
    )
    t = open(f"{d}/j.aux").read()
    g = lambda tag: float(re.search(tag + r"=\s*(\S+)", t).group(1).replace("D", "E"))
    ch = re.search(
        r"ATOM_CHARGES\[\d+\]=\s*\n(.*?)(?=\n [A-Z_.:/()\-]+[\[=]|\Z)", t, re.S
    )
    gr = re.search(
        r"GRADIENTS:KCAL/MOL/ANGSTROM\[\d+\]=\s*\n(.*?)(?=\n [A-Z_.:/()\-]+[\[=]|\Z)",
        t,
        re.S,
    )
    return {
        "gradients": fl(gr.group(1)),
        "heat_of_formation": g("HEAT_OF_FORMATION:KCAL/MOL"),
        "atom_charges": fl(ch.group(1)),
        "ionization_potential": g("IONIZATION_POTENTIAL:EV"),
        "dipole": g("DIPOLE:DEBYE"),
        "area": g("AREA:SQUARE ANGSTROMS"),
        "volume": g("VOLUME:CUBIC ANGSTROMS"),
    }


def rot(seed):
    q = np.random.RandomState(seed).randn(4)
    q /= np.linalg.norm(q)
    a, b, c, d = q
    return np.array(
        [
            [a * a + b * b - c * c - d * d, 2 * (b * c - a * d), 2 * (b * d + a * c)],
            [2 * (b * c + a * d), a * a - b * b + c * c - d * d, 2 * (c * d - a * b)],
            [2 * (b * d - a * c), 2 * (c * d + a * b), a * a - b * b - c * c + d * d],
        ]
    )


rng = random.Random(6)
os.makedirs(OUT, exist_ok=True)
for jf in sorted(glob.glob(f"{SRC}/*/*/*.json")):
    ref = json.load(open(jf))
    if ref["kind"] != "sp":
        continue
    name = os.path.basename(jf)[:-5]
    lines = open(jf[:-5] + ".mop").read().splitlines()
    extras = " ".join(
        t
        for t in lines[0].split()
        if t in ("UHF", "DOUBLET", "TRIPLET") or t.startswith("CHARGE=")
    )
    el = ref["elements"]
    x = np.array([[float(v) for v in l.split()[1:6:2]] for l in lines[3:] if l.strip()])
    x = x + np.array([[rng.gauss(0, 0.02) for _ in range(3)] for _ in x])
    eps = rng.choice(EPS)
    kw = f"PM7 {extras} 1SCF GRAD EPS={eps} AUX(PRECISION=9) NOINTER XYZ".replace(
        "  ", " "
    )
    try:
        r0 = run(kw, el, x)
        rs = [run(kw, el, x @ rot(s).T + np.array([0.3, -0.2, 0.1])) for s in (1, 2, 3)]
    except Exception as e:  # noqa: BLE001
        print("skip", name, e, flush=True)
        continue
    spread = {
        k: float(max(np.max(np.abs(np.array(q[k]) - np.array(r0[k]))) for q in rs))
        for k in r0
    }
    group = "visible" if name in VISIBLE else "hidden"
    d = f"{OUT}/{group}/cosmo_grad_{name}"
    os.makedirs(d, exist_ok=True)
    body = "".join(
        f" {e} {v[0]:.8f} 1 {v[1]:.8f} 1 {v[2]:.8f} 1\n" for e, v in zip(el, x)
    )
    open(f"{d}/cosmo_grad_{name}.mop", "w").write(f"{kw}\ncosmo_grad_{name}\n\n{body}")
    json.dump(
        {
            "kind": "cosmograd",
            "elements": el,
            "keywords": kw,
            **r0,
            "_rotation_spread": spread,
        },
        open(f"{d}/cosmo_grad_{name}.json", "w"),
        indent=1,
    )
    print(
        group,
        name,
        eps,
        "heat %.4f" % r0["heat_of_formation"],
        "spread",
        {k: "%.1e" % v for k, v in spread.items()},
        flush=True,
    )
