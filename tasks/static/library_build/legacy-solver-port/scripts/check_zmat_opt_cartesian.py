# Dev tool. Step-4 optimization reproducibility, second perturbation: the Z-matrix has no orientation freedom, so convert each Z-matrix opt input to the
# equivalent Cartesian start geometry (via a MOPAC 1SCF run) and optimise that in Cartesian with the same keywords. A reference that is a well-defined
# minimum must come out within tolerance (heat 5e-3 kcal/mol, interatomic distances 3e-3 A). Cases with fixed-coordinate flags are skipped (constraints are
# expressed in internal coordinates).
import os, re, sys, json, glob, subprocess, tempfile, numpy as np


def fl(b):
    return [float(x.replace("D", "E")) for x in b.split()]


def aux(p, tag):
    t = open(p).read()
    h = float(
        re.search(r"HEAT_OF_FORMATION:KCAL/MOL=\s*(\S+)", t).group(1).replace("D", "E")
    )
    m = re.search(tag + r"\[\d+\]=\s*\n(.*?)(?=\n [A-Z_.:/()\-]+[\[=]|\Z)", t, re.S)
    return h, np.array(fl(m.group(1))).reshape(-1, 3)


def D(x):
    return np.linalg.norm(x[:, None] - x[None], axis=-1)


def run(text, tag):
    d = tempfile.mkdtemp()
    open(f"{d}/j.mop", "w").write(text)
    subprocess.run(
        ["env", "-i", "PATH=/usr/bin:/bin", "/build/mopac", "j.mop"],
        cwd=d,
        capture_output=True,
        timeout=900,
    )
    return aux(f"{d}/j.aux", tag)


print(f"{'case':30s} dH(kcal/mol)  max|dDist|(A)  verdict", flush=True)
for jf in sorted(glob.glob("/refs/*/*/*.json")):
    ref = json.load(open(jf))
    if "optimized_geometry" not in ref:
        continue
    name = os.path.basename(jf)[:-5]
    text = open(jf[:-5] + ".mop").read()
    L = text.split("\n")
    if "fixed" in name:
        continue
    kw = re.sub(r"\bEF\b", "1SCF", L[0])
    kw = re.sub(r"GNORM=[0-9.]+", "", kw)
    _, x0 = run("\n".join([kw] + L[1:]), "ATOM_X:ANGSTROMS")
    els = [
        l.split()[0]
        for l in L[3:]
        if l.strip() and l.split()[0].upper() not in ("XX", "X")
    ]
    cart = "\n".join(
        [L[0] + " XYZ", L[1], ""]
        + [f" {e} {v[0]:.8f} 1 {v[1]:.8f} 1 {v[2]:.8f} 1" for e, v in zip(els, x0)]
    )
    h, x = run(cart, "ATOM_X_OPT:ANGSTROMS")
    xr = np.array(ref["optimized_geometry"]).reshape(-1, 3)
    dh = abs(h - ref["heat_of_formation"])
    dd = float(np.abs(D(x) - D(xr)).max())
    print(
        f"{jf.split('/')[2][:3]} {name:26s} {dh:.1e}     {dd:.4f}       {'NOT REPRODUCIBLE' if dh > 5e-3 or dd > 3e-3 else 'ok'}",
        flush=True,
    )
