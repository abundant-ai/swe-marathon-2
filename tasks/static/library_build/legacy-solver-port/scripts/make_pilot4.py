#!/usr/bin/env python3
"""Pilot-4 molecule set: wider scope than pilot 3.

usage: make_pilot4.py MOPAC_BINARY OUTDIR

Adds F, P, S, Cl, Br; charged species; UHF radicals/triplets; geometry
optimization jobs. Reuses the internal-coordinate builder of make_pilot3.py.
Reference runs use env PATH=/usr/bin:/bin (Apple Accelerate).
"""

import json, os, random, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_pilot3 as b3
from make_pilot3 import Mol, mop

MOPAC, OUT = sys.argv[1], sys.argv[2]
ENV = {"PATH": "/usr/bin:/bin"}


def ch3x(X, d):
    m = Mol()
    c = m.add("C")
    x = m.add(X, c, d)
    m.methyl(c, x, None)
    return m


def ch2f2():
    m = Mol()
    c = m.add("C")
    f1 = m.add("F", c, 1.36)
    f2 = m.add("F", c, 1.36, f1, 108.5)
    m.add("H", c, 1.09, f1, 109, f2, 120)
    m.add("H", c, 1.09, f1, 109, f2, -120)
    return m


def chloroethane():
    m = Mol()
    c0 = m.add("C")
    c1 = m.add("C", c0, 1.52)
    cl = m.add("Cl", c1, 1.79, c0, 110.5)
    m.methyl(c0, c1, cl)
    m.add("H", c1, 1.09, c0, 111, cl, 120)
    m.add("H", c1, 1.09, c0, 111, cl, -120)
    return m


def h2s():
    m = Mol()
    s = m.add("S")
    m.add("H", s, 1.34)
    m.add("H", s, 1.34, 1, 92)
    return m


def methanethiol():
    m = Mol()
    c = m.add("C")
    s = m.add("S", c, 1.82)
    h = m.add("H", s, 1.34, c, 96.5)
    m.methyl(c, s, h)
    return m


def dimethyl_sulfide():
    m = Mol()
    s = m.add("S")
    c1 = m.add("C", s, 1.81)
    c2 = m.add("C", s, 1.81, c1, 99)
    m.methyl(c1, s, c2)
    m.methyl(c2, s, c1)
    return m


def dimethyl_disulfide():
    m = Mol()
    s0 = m.add("S")
    s1 = m.add("S", s0, 2.05)
    c2 = m.add("C", s0, 1.81, s1, 103)
    c3 = m.add("C", s1, 1.81, s0, 103, c2, 85)
    m.methyl(c2, s0, s1)
    m.methyl(c3, s1, s0)
    return m


def dmso():
    m = Mol()
    s = m.add("S")
    o = m.add("O", s, 1.50)
    c1 = m.add("C", s, 1.80, o, 107)
    c2 = m.add("C", s, 1.80, o, 107, c1, -105)
    m.methyl(c1, s, o)
    m.methyl(c2, s, o)
    return m


def so2():
    m = Mol()
    s = m.add("S")
    o = m.add("O", s, 1.43)
    m.add("O", s, 1.43, o, 119)
    return m


def ph3():
    m = Mol()
    p = m.add("P")
    h = m.add("H", p, 1.42)
    m.add("H", p, 1.42, h, 93.5)
    m.add("H", p, 1.42, h, 93.5, 2, 98)
    return m


def trimethylphosphine():
    m = Mol()
    p = m.add("P")
    c1 = m.add("C", p, 1.84)
    c2 = m.add("C", p, 1.84, c1, 99)
    c3 = m.add("C", p, 1.84, c1, 99, c2, 100)
    m.methyl(c1, p, c2)
    m.methyl(c2, p, c1)
    m.methyl(c3, p, c1)
    return m


def phosphoric_acid():
    m = Mol()
    p = m.add("P")
    o1 = m.add("O", p, 1.48)
    o2 = m.add("O", p, 1.62, o1, 112)
    o3 = m.add("O", p, 1.62, o1, 112, o2, 120)
    o4 = m.add("O", p, 1.62, o1, 112, o2, -120)
    for o in (o2, o3, o4):
        m.add("H", o, 0.96, p, 115, o1, 60)
    return m


def ring(m, elems, bond=1.40):
    idx = [m.add(elems[0])]
    idx.append(m.add(elems[1], idx[0], bond))
    idx.append(m.add(elems[2], idx[1], bond, idx[0], 120))
    for k in range(3, 6):
        idx.append(m.add(elems[k], idx[k - 1], bond, idx[k - 2], 120, idx[k - 3], 0))
    return idx


def subst(m, idx, pos, el, d):
    a = idx[pos]
    b = idx[(pos + 1) % 6]
    c = idx[(pos + 2) % 6]
    return m.add(el, a, d, b, 120, c, 180)


def benzene_like(elems, subs=None):
    m = Mol()
    idx = ring(m, elems)
    subs = subs or {}
    made = {}
    for i in range(6):
        if elems[i] == "N":
            continue
        if i in subs:
            made[i] = subst(m, idx, i, *subs[i])
        else:
            subst(m, idx, i, "H", 1.08)
    return m, idx, made


def benzene():
    return benzene_like(["C"] * 6)[0]


def toluene():
    m, idx, made = benzene_like(["C"] * 6, {0: ("C", 1.51)})
    m.methyl(made[0], idx[0], idx[1])
    return m


def phenol():
    m, idx, made = benzene_like(["C"] * 6, {0: ("O", 1.36)})
    m.add("H", made[0], 0.96, idx[0], 109, idx[1], 0)
    return m


def aniline():
    m, idx, made = benzene_like(["C"] * 6, {0: ("N", 1.40)})
    m.add("H", made[0], 1.01, idx[0], 115, idx[1], 0)
    m.add("H", made[0], 1.01, idx[0], 115, idx[1], 180)
    return m


def halobenzene(X, d):
    return benzene_like(["C"] * 6, {0: (X, d)})[0]


def pyridine():
    return benzene_like(["N", "C", "C", "C", "C", "C"], None)[0]


def _amino_acid_core(m):
    c0 = m.add("C")
    o1 = m.add("O", c0, 1.21)
    o2 = m.add("O", c0, 1.35, o1, 123)
    m.add("H", o2, 0.97, c0, 107, o1, 0)
    c1 = m.add("C", c0, 1.52, o1, 124, o2, 180)
    n = m.add("N", c1, 1.46, c0, 110, o1, 0)
    m.add("H", n, 1.01, c1, 110, c0, 60)
    m.add("H", n, 1.01, c1, 110, c0, -60)
    return c0, c1, n


def alanine():
    m = Mol()
    c0, c1, n = _amino_acid_core(m)
    m.add("H", c1, 1.10, c0, 109, n, 120)
    cb = m.add("C", c1, 1.53, c0, 109, n, -120)
    m.methyl(cb, c1, c0)
    return m


def cysteine():
    m = Mol()
    c0, c1, n = _amino_acid_core(m)
    m.add("H", c1, 1.10, c0, 109, n, 120)
    cb = m.add("C", c1, 1.53, c0, 109, n, -120)
    s = m.add("S", cb, 1.82, c1, 113, c0, 180)
    m.add("H", s, 1.34, cb, 96, c1, 60)
    m.add("H", cb, 1.09, c1, 109, s, 120)
    m.add("H", cb, 1.09, c1, 109, s, -120)
    return m


def ammonium():
    m = Mol()
    n = m.add("N")
    m.add("H", n, 1.03)
    m.add("H", n, 1.03, 1, 109.5)
    m.add("H", n, 1.03, 1, 109.5, 2, 120)
    m.add("H", n, 1.03, 1, 109.5, 2, -120)
    return m


def hydronium():
    m = Mol()
    o = m.add("O")
    h = m.add("H", o, 0.98)
    m.add("H", o, 0.98, h, 112)
    m.add("H", o, 0.98, h, 112, 2, 115)
    return m


def hydroxide():
    m = Mol()
    o = m.add("O")
    m.add("H", o, 0.96)
    return m


def acetate():
    m = Mol()
    c0 = m.add("C")
    o1 = m.add("O", c0, 1.26)
    o2 = m.add("O", c0, 1.26, o1, 125)
    c1 = m.add("C", c0, 1.52, o1, 117, o2, 180)
    m.methyl(c1, c0, o1)
    return m


def methylammonium():
    m = Mol()
    c = m.add("C")
    n = m.add("N", c, 1.50)
    h = m.add("H", n, 1.03, c, 110)
    m.add("H", n, 1.03, c, 110, h, 120)
    m.add("H", n, 1.03, c, 110, h, -120)
    m.methyl(c, n, h)
    return m


def methyl_radical():
    m = Mol()
    c = m.add("C")
    m.add("H", c, 1.08)
    m.add("H", c, 1.08, 1, 120)
    m.add("H", c, 1.08, 1, 120, 2, 180)
    return m


def hydroxyl():
    m = Mol()
    o = m.add("O")
    m.add("H", o, 0.97)
    return m


def no2():
    m = Mol()
    n = m.add("N")
    o = m.add("O", n, 1.20)
    m.add("O", n, 1.20, o, 134)
    return m


def o2():
    m = Mol()
    o = m.add("O")
    m.add("O", o, 1.21)
    return m


def ch2_triplet():
    m = Mol()
    c = m.add("C")
    h = m.add("H", c, 1.08)
    m.add("H", c, 1.08, h, 135)
    return m


def methoxy():
    m = Mol()
    c = m.add("C")
    o = m.add("O", c, 1.37)
    m.methyl(c, o, None)
    return m


def U(fn):  # unchanged pilot-3 builders
    return fn


# name -> (builder, keyword extras, kind)
VIS = {
    "water": (b3.water, "", "sp"),
    "methane": (b3.methane, "", "sp"),
    "formaldehyde": (b3.formaldehyde, "", "sp"),
    "methyl_chloride": (lambda: ch3x("Cl", 1.78), "", "sp"),
    "methanethiol": (methanethiol, "", "sp"),
    "ammonium": (ammonium, "CHARGE=1", "sp"),
    "methyl_radical": (methyl_radical, "UHF DOUBLET", "sp"),
    "methanol_opt": (b3.methanol, "", "opt"),
}
HID = {
    "fluoromethane": (lambda: ch3x("F", 1.38), "", "sp"),
    "difluoromethane": (ch2f2, "", "sp"),
    "bromomethane": (lambda: ch3x("Br", 1.94), "", "sp"),
    "chloroethane": (chloroethane, "", "sp"),
    "hydrogen_sulfide": (h2s, "", "sp"),
    "dimethyl_sulfide": (dimethyl_sulfide, "", "sp"),
    "dimethyl_disulfide": (dimethyl_disulfide, "", "sp"),
    "dmso": (dmso, "", "sp"),
    "sulfur_dioxide": (so2, "", "sp"),
    "phosphine": (ph3, "", "sp"),
    "trimethylphosphine": (trimethylphosphine, "", "sp"),
    "phosphoric_acid": (phosphoric_acid, "", "sp"),
    "benzene": (benzene, "", "sp"),
    "toluene": (toluene, "", "sp"),
    "phenol": (phenol, "", "sp"),
    "aniline": (aniline, "", "sp"),
    "fluorobenzene": (lambda: halobenzene("F", 1.35), "", "sp"),
    "chlorobenzene": (lambda: halobenzene("Cl", 1.74), "", "sp"),
    "bromobenzene": (lambda: halobenzene("Br", 1.90), "", "sp"),
    "pyridine": (pyridine, "", "sp"),
    "alanine": (alanine, "", "sp"),
    "cysteine": (cysteine, "", "sp"),
    "hydronium": (hydronium, "CHARGE=1", "sp"),
    "hydroxide": (hydroxide, "CHARGE=-1", "sp"),
    "acetate": (acetate, "CHARGE=-1", "sp"),
    "methylammonium": (methylammonium, "CHARGE=1", "sp"),
    "hydroxyl_radical": (hydroxyl, "UHF DOUBLET", "sp"),
    "nitrogen_dioxide": (no2, "UHF DOUBLET", "sp"),
    "oxygen_triplet": (o2, "UHF TRIPLET", "sp"),
    "methylene_triplet": (ch2_triplet, "UHF TRIPLET", "sp"),
    "methoxy_radical": (methoxy, "UHF DOUBLET", "sp"),
    "acetic_acid_opt": (b3.acetic_acid, "", "opt"),
    "dimethyl_sulfide_opt": (dimethyl_sulfide, "", "opt"),
    "chlorobenzene_opt": (lambda: halobenzene("Cl", 1.74), "", "opt"),
    "glycine_opt": (b3.glycine, "", "opt"),
    "pyridine_opt": (pyridine, "", "opt"),
    "urea_opt": (b3.urea, "", "opt"),
}


def run(d, name):
    subprocess.run(
        [MOPAC, name + ".mop"], cwd=d, env=ENV, capture_output=True, timeout=600
    )


def build(group, table, seed):
    rng = random.Random(seed)
    for name, (fn, extra, kind) in table.items():
        d = os.path.join(OUT, group, name)
        os.makedirs(d, exist_ok=True)
        m = fn()
        pre = f"PM7 {extra} ".replace("  ", " ")
        open(f"{d}/pre.mop", "w").write(
            mop("pre", m.el, m.xyz, pre + "PRECISE EF NOINTER XYZ AUX GNORM=0.05 T=600")
        )
        run(d, "pre")
        try:
            x = np.array(b3.aux(f"{d}/pre.aux")["x_opt"]).reshape(-1, 3)
        except Exception as e:
            print("FAILED pre-opt", name, e)
            continue
        sig = 0.08 if kind == "opt" else 0.03
        x = x + np.array([[rng.gauss(0, sig) for _ in range(3)] for _ in x])
        if kind == "sp":
            kw = pre + "1SCF GRAD AUX(PRECISION=9) NOINTER XYZ"
        else:
            kw = pre + "PRECISE EF GNORM=0.01 AUX(PRECISION=9) NOINTER XYZ T=1200"
        open(f"{d}/{name}.mop", "w").write(mop(name, m.el, x, kw, flag=1))
        run(d, name)
        try:
            ref = b3.aux(f"{d}/{name}.aux")
        except Exception as e:
            print("FAILED run", name, e)
            continue
        out = dict(
            kind=kind,
            elements=m.el,
            keywords=kw,
            heat_of_formation=ref["heat_of_formation"],
            atom_charges=ref["atom_charges"],
            ionization_potential=ref["ionization_potential"],
            dipole=ref["dipole"],
        )
        if kind == "sp":
            out["gradients"] = ref["gradients"]
        else:
            out["optimized_geometry"] = ref["x_opt"]
        json.dump(out, open(f"{d}/{name}.json", "w"), indent=1)
        for f in os.listdir(d):
            if f not in (name + ".mop", name + ".json", name + ".aux"):
                os.remove(os.path.join(d, f))
        print(
            group,
            name,
            kind,
            len(m.el),
            "atoms heat",
            round(ref["heat_of_formation"], 3),
        )


build("visible", VIS, 11)
build("hidden", HID, 12)
