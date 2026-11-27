#!/usr/bin/env python3
"""Build the MOPAC step-1 pilot molecule set and reference outputs.

usage: make_pilot3.py MOPAC_BINARY OUTDIR

Reference runs use a clean environment (PATH only) so the binary resolves Apple
Accelerate, not a conda BLAS (see DESIGN.md 17.2).  Writes:
  OUTDIR/visible/<name>.mop,.json   (given to the agent)
  OUTDIR/hidden/<name>.mop,.json    (kept private)
"""

import json, math, os, random, re, shutil, subprocess, sys
import numpy as np

MOPAC, OUT = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (None, None)
ENV = {"PATH": "/usr/bin:/bin"}


class Mol:
    def __init__(self):
        self.el, self.xyz = [], []

    def add(self, el, a=None, r=None, b=None, ang=None, c=None, dih=None):
        n = len(self.el)
        if n == 0:
            p = np.zeros(3)
        elif n == 1:
            p = np.array([0, 0, r])
        else:
            A, B = self.xyz[a], self.xyz[b]
            if c is None:  # angle only: pick any other atom, dihedral 0
                c = next((i for i in range(n) if i not in (a, b)), None)
                dih = 0.0
            C = self.xyz[c] if c is not None else B + np.array([1.0, 0, 0])
            bc = A - B
            bc /= np.linalg.norm(bc)
            ab = B - C
            nrm = np.cross(ab, bc)
            if np.linalg.norm(nrm) < 1e-8:
                nrm = np.cross(bc, [1, 0, 0] if abs(bc[0]) < 0.9 else [0, 1, 0])
            nrm /= np.linalg.norm(nrm)
            m = np.cross(nrm, bc)
            th, ph = math.radians(ang), math.radians(dih)
            d = np.array(
                [
                    -r * math.cos(th),
                    r * math.sin(th) * math.cos(ph),
                    r * math.sin(th) * math.sin(ph),
                ]
            )
            p = A + d[0] * bc + d[1] * m + d[2] * nrm
        self.el.append(el)
        self.xyz.append(p)
        return n

    def methyl(self, C, B, A=None):
        if A is None:
            h = self.add("H", C, 1.09, B, 109.5)
            self.add("H", C, 1.09, B, 109.5, h, 120)
            self.add("H", C, 1.09, B, 109.5, h, -120)
        else:
            for d in (60, 180, -60):
                self.add("H", C, 1.09, B, 109.5, A, d)


def water():
    m = Mol()
    o = m.add("O")
    m.add("H", o, 0.96)
    m.add("H", o, 0.96, 1, 104.5)
    return m


def methane():
    m = Mol()
    c = m.add("C")
    m.add("H", c, 1.09)
    m.add("H", c, 1.09, 1, 109.5)
    m.add("H", c, 1.09, 1, 109.5, 2, 120)
    m.add("H", c, 1.09, 1, 109.5, 2, -120)
    return m


def ammonia():
    m = Mol()
    n = m.add("N")
    h = m.add("H", n, 1.01)
    m.add("H", n, 1.01, h, 107)
    m.add("H", n, 1.01, h, 107, 2, 112)
    return m


def ethylene():
    m = Mol()
    a = m.add("C")
    b = m.add("C", a, 1.34)
    h = m.add("H", a, 1.09, b, 121.5)
    m.add("H", a, 1.09, b, 121.5, h, 180)
    k = m.add("H", b, 1.09, a, 121.5, h, 0)
    m.add("H", b, 1.09, a, 121.5, h, 180)
    return m


def methanol():
    m = Mol()
    c = m.add("C")
    o = m.add("O", c, 1.43)
    h = m.add("H", o, 0.96, c, 108.5)
    m.methyl(c, o, h)
    return m


def formaldehyde():
    m = Mol()
    c = m.add("C")
    o = m.add("O", c, 1.21)
    h = m.add("H", c, 1.10, o, 121.5)
    m.add("H", c, 1.10, o, 121.5, h, 180)
    return m


def ethane():
    m = Mol()
    a = m.add("C")
    b = m.add("C", a, 1.53)
    m.methyl(a, b, None)
    m.methyl(b, a, 2)
    return m


def propane():
    m = Mol()
    c0 = m.add("C")
    c1 = m.add("C", c0, 1.53)
    c2 = m.add("C", c1, 1.53, c0, 112)
    m.methyl(c0, c1, c2)
    m.methyl(c2, c1, c0)
    m.add("H", c1, 1.10, c0, 109.5, c2, 120)
    m.add("H", c1, 1.10, c0, 109.5, c2, -120)
    return m


def ethanol():
    m = Mol()
    c0 = m.add("C")
    c1 = m.add("C", c0, 1.52)
    o = m.add("O", c1, 1.43, c0, 109.5)
    m.add("H", o, 0.96, c1, 108.5, c0, 180)
    m.methyl(c0, c1, o)
    m.add("H", c1, 1.10, c0, 109.5, o, 120)
    m.add("H", c1, 1.10, c0, 109.5, o, -120)
    return m


def dimethyl_ether():
    m = Mol()
    o = m.add("O")
    c1 = m.add("C", o, 1.42)
    c2 = m.add("C", o, 1.42, c1, 111)
    m.methyl(c1, o, c2)
    m.methyl(c2, o, c1)
    return m


def acetaldehyde():
    m = Mol()
    c0 = m.add("C")
    o = m.add("O", c0, 1.21)
    c1 = m.add("C", c0, 1.51, o, 124)
    m.add("H", c0, 1.11, o, 121, c1, 180)
    m.methyl(c1, c0, o)
    return m


def acetone():
    m = Mol()
    c0 = m.add("C")
    o = m.add("O", c0, 1.22)
    c1 = m.add("C", c0, 1.52, o, 121.5)
    c2 = m.add("C", c0, 1.52, o, 121.5, c1, 180)
    m.methyl(c1, c0, o)
    m.methyl(c2, c0, o)
    return m


def formic_acid():
    m = Mol()
    c = m.add("C")
    o1 = m.add("O", c, 1.20)
    o2 = m.add("O", c, 1.34, o1, 125)
    m.add("H", c, 1.10, o1, 124, o2, 180)
    m.add("H", o2, 0.97, c, 107, o1, 0)
    return m


def acetic_acid():
    m = Mol()
    c0 = m.add("C")
    o1 = m.add("O", c0, 1.21)
    o2 = m.add("O", c0, 1.35, o1, 123)
    c1 = m.add("C", c0, 1.51, o1, 125, o2, 180)
    m.add("H", o2, 0.97, c0, 107, o1, 0)
    m.methyl(c1, c0, o1)
    return m


def methylamine():
    m = Mol()
    n = m.add("N")
    c = m.add("C", n, 1.47)
    h = m.add("H", n, 1.01, c, 110)
    m.add("H", n, 1.01, c, 110, h, 120)
    m.methyl(c, n, h)
    return m


def formamide():
    m = Mol()
    c = m.add("C")
    o = m.add("O", c, 1.22)
    n = m.add("N", c, 1.36, o, 124)
    m.add("H", c, 1.10, o, 122, n, 180)
    m.add("H", n, 1.01, c, 119, o, 0)
    m.add("H", n, 1.01, c, 120, o, 180)
    return m


def urea():
    m = Mol()
    c = m.add("C")
    o = m.add("O", c, 1.23)
    n1 = m.add("N", c, 1.38, o, 121)
    n2 = m.add("N", c, 1.38, o, 121, n1, 180)
    for n in (n1, n2):
        m.add("H", n, 1.01, c, 119, o, 0)
        m.add("H", n, 1.01, c, 120, o, 180)
    return m


def glycine():
    m = Mol()
    c0 = m.add("C")
    o1 = m.add("O", c0, 1.21)
    o2 = m.add("O", c0, 1.35, o1, 123)
    m.add("H", o2, 0.97, c0, 107, o1, 0)
    c1 = m.add("C", c0, 1.52, o1, 124, o2, 180)
    n = m.add("N", c1, 1.46, c0, 110, o1, 0)
    m.add("H", c1, 1.10, c0, 109, n, 120)
    m.add("H", c1, 1.10, c0, 109, n, -120)
    m.add("H", n, 1.01, c1, 110, c0, 60)
    m.add("H", n, 1.01, c1, 110, c0, -60)
    return m


def propene():
    m = Mol()
    c0 = m.add("C")
    c1 = m.add("C", c0, 1.34)
    c2 = m.add("C", c1, 1.50, c0, 125)
    m.add("H", c0, 1.09, c1, 121.5, c2, 0)
    m.add("H", c0, 1.09, c1, 121.5, c2, 180)
    m.add("H", c1, 1.09, c0, 120, c2, 180)
    m.methyl(c2, c1, c0)
    return m


def nitromethane():
    m = Mol()
    c = m.add("C")
    n = m.add("N", c, 1.49)
    o1 = m.add("O", n, 1.22, c, 117)
    m.add("O", n, 1.22, c, 117, o1, 180)
    m.methyl(c, n, o1)
    return m


VISIBLE = dict(
    water=water,
    methane=methane,
    ammonia=ammonia,
    ethylene=ethylene,
    methanol=methanol,
    formaldehyde=formaldehyde,
)
HIDDEN = dict(
    ethane=ethane,
    propane=propane,
    ethanol=ethanol,
    dimethyl_ether=dimethyl_ether,
    acetaldehyde=acetaldehyde,
    acetone=acetone,
    formic_acid=formic_acid,
    acetic_acid=acetic_acid,
    methylamine=methylamine,
    formamide=formamide,
    urea=urea,
    glycine=glycine,
    propene=propene,
    nitromethane=nitromethane,
)


def mop(name, el, xyz, kw, flag=1):
    lines = [kw, name, ""]
    for e, p in zip(el, xyz):
        lines.append(f" {e:2s} " + " ".join(f"{x:14.8f} {flag}" for x in p))
    return "\n".join(lines) + "\n"


def run(d, name):
    subprocess.run(
        [MOPAC, name + ".mop"], cwd=d, env=ENV, capture_output=True, timeout=300
    )


def floats(block):
    return [float(x.replace("D", "E")) for x in block.split()]


def aux(path):
    t = open(path).read()
    out = {}
    m = re.search(r"HEAT_OF_FORMATION:KCAL/MOL=\s*(\S+)", t)
    out["heat_of_formation"] = float(m.group(1).replace("D", "E"))
    m = re.search(r"IONIZATION_POTENTIAL:EV=\s*(\S+)", t)
    out["ionization_potential"] = float(m.group(1).replace("D", "E"))
    m = re.search(r"DIPOLE:DEBYE=\s*(\S+)", t)
    out["dipole"] = float(m.group(1).replace("D", "E"))
    for key, tag in [
        ("gradients", "GRADIENTS:KCAL/MOL/ANGSTROM"),
        ("atom_charges", "ATOM_CHARGES"),
        ("eigenvalues", "EIGENVALUES"),
        ("x_opt", "ATOM_X_OPT:ANGSTROMS"),
    ]:
        m = re.search(tag + r"\[\d+\]=\s*\n(.*?)(?=\n [A-Z_.:/]+[\[=]|\Z)", t, re.S)
        out[key] = floats(m.group(1))
    return out


def build(group, mols, perturb_seed):
    rng = random.Random(perturb_seed)
    for name, fn in mols.items():
        d = os.path.join(OUT, group, name)
        os.makedirs(d, exist_ok=True)
        m = fn()
        open(f"{d}/opt.mop", "w").write(
            mop("opt", m.el, m.xyz, "PM7 PRECISE EF NOINTER XYZ AUX GNORM=0.05 T=300")
        )
        run(d, "opt")
        x = np.array(aux(f"{d}/opt.aux")["x_opt"]).reshape(-1, 3)
        x = x + np.array([[rng.gauss(0, 0.03) for _ in range(3)] for _ in x])
        open(f"{d}/{name}.mop", "w").write(
            mop(name, m.el, x, "PM7 1SCF GRAD AUX(PRECISION=9) NOINTER XYZ", flag=1)
        )
        run(d, name)
        ref = aux(f"{d}/{name}.aux")
        ref.pop("x_opt")
        ref["elements"] = m.el
        json.dump(ref, open(f"{d}/{name}.json", "w"), indent=1)
        for f in os.listdir(d):
            if f not in (name + ".mop", name + ".json", name + ".aux"):
                os.remove(os.path.join(d, f))
        print(group, name, len(m.el), "atoms", "heat", ref["heat_of_formation"])


if __name__ == "__main__":
    build("visible", VISIBLE, 1)
    build("hidden", HIDDEN, 2)
