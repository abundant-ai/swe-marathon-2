# Dev tool. Step-4 optimization reproducibility: rerun the original MOPAC on each opt input as is, with GNORM/10 and GNORM/100 (how far the stored reference is
# from a converged minimum) and, for Cartesian inputs with fixed flags, on a translated copy. Compared with the stored reference: heat and interatomic distances (tolerances 5e-3 kcal/mol, 3e-3 A).
import os, re, sys, json, glob, subprocess, tempfile, numpy as np


def fl(b):
    return [float(x.replace("D", "E")) for x in b.split()]


def aux(p):
    t = open(p).read()
    h = float(
        re.search(r"HEAT_OF_FORMATION:KCAL/MOL=\s*(\S+)", t).group(1).replace("D", "E")
    )
    m = re.search(
        r"ATOM_X_OPT:ANGSTROMS\[\d+\]=\s*\n(.*?)(?=\n [A-Z_.:/()\-]+[\[=]|\Z)", t, re.S
    )
    return h, np.array(fl(m.group(1))).reshape(-1, 3)


def D(x):
    return np.linalg.norm(x[:, None] - x[None], axis=-1)


def run(text):
    d = tempfile.mkdtemp()
    open(f"{d}/j.mop", "w").write(text)
    subprocess.run(
        ["env", "-i", "PATH=/usr/bin:/bin", "/build/mopac", "j.mop"],
        cwd=d,
        capture_output=True,
        timeout=900,
    )
    return aux(f"{d}/j.aux")


def gn(text, f):
    m = re.search(r"GNORM=([0-9.]+)", text)
    v = float(m.group(1)) / f
    return re.sub(r"GNORM=[0-9.]+", f"GNORM={v:g}", text, count=1)


def shift(text):
    L = text.split("\n")
    out = L[:3]
    for l in L[3:]:
        t = l.split()
        if len(t) >= 7:
            t[1] = f"{float(t[1]) + 0.3:.8f}"
            t[3] = f"{float(t[3]) - 0.2:.8f}"
            t[5] = f"{float(t[5]) + 0.1:.8f}"
            l = " ".join(t)
        out.append(l)
    return "\n".join(out)


print(
    f"{'case':30s} {'asis dH/dDist':20s} {'GNORM/10':20s} {'GNORM/100':20s} {'translated':20s} verdict",
    flush=True,
)
for jf in sorted(glob.glob("/refs/*/*/*.json")):
    ref = json.load(open(jf))
    if "optimized_geometry" not in ref:
        continue
    name = os.path.basename(jf)[:-5]
    text = open(jf[:-5] + ".mop").read()
    hr = ref["heat_of_formation"]
    xr = np.array(ref["optimized_geometry"]).reshape(-1, 3)

    def c(t):
        h, x = run(t)
        if len(x) != len(xr):
            return None
        return abs(h - hr), float(np.abs(D(x) - D(xr)).max())

    res = [c(text), c(gn(text, 10)), c(gn(text, 100))]
    cart = not re.search(
        r"\n [A-Z][a-z]? +[0-9.\-]+ [01] +[0-9.\-]+ [01] +[0-9.\-]+ [01] +[0-9]+ [0-9]+ [0-9]+",
        "\n" + text,
    )
    res.append(c(shift(text)) if cart else None)
    bad = any(r and (r[0] > 5e-3 or r[1] > 3e-3) for r in res)
    f = lambda r: "n/a".ljust(20) if r is None else f"{r[0]:.1e} / {r[1]:.4f}".ljust(20)
    print(
        f"{jf.split('/')[2][:3]} {name:26s} {f(res[0])} {f(res[1])} {f(res[2])} {f(res[3])} {'NOT REPRODUCIBLE' if bad else 'ok'}",
        flush=True,
    )
