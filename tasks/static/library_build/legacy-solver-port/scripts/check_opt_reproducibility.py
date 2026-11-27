# Dev tool (never shipped). Run in the mopac-linref image with the refs mounted at /refs (steps/01-port-pm7/tests/private).
# Reruns the original MOPAC on randomly rotated copies of each opt input; a case whose own result moves by more than the
# verifier tolerance (3e-3 A in interatomic distances) is not reproducible from the problem statement.
import os, re, sys, json, subprocess, shutil, numpy as np, tempfile

H = "/refs/hidden"
SOL = "/agent/solver"


def floats(b):
    return [float(x.replace("D", "E")) for x in b.split()]


def aux(p):
    t = open(p).read()
    m = re.search(r"HEAT_OF_FORMATION:KCAL/MOL=\s*(\S+)", t)
    h = float(m.group(1).replace("D", "E"))
    m = re.search(
        r"ATOM_X_OPT:ANGSTROMS\[\d+\]=\s*\n(.*?)(?=\n [A-Z_.:/]+[\[=]|\Z)", t, re.S
    )
    return h, np.array(floats(m.group(1))).reshape(-1, 3)


def D(x):
    return np.linalg.norm(x[:, None] - x[None], axis=-1)


def parse_mop(p):
    L = open(p).read().splitlines()
    kw = L[0]
    el = []
    xyz = []
    for l in L[3:]:
        t = l.split()
        if len(t) >= 4:
            el.append(t[0])
            xyz.append([float(t[1]), float(t[3]), float(t[5])])
    return kw, L[1], el, np.array(xyz)


def write_mop(p, kw, el, xyz):
    open(p, "w").write(
        kw
        + "\nx\n\n"
        + "".join(
            f" {e:2s} {x[0]:.8f} 1 {x[1]:.8f} 1 {x[2]:.8f} 1\n" for e, x in zip(el, xyz)
        )
    )


def mopac(kw, el, xyz, tag):
    d = tempfile.mkdtemp()
    write_mop(f"{d}/j.mop", kw, el, xyz)
    subprocess.run(
        ["env", "-i", "PATH=/usr/bin:/bin", "/build/mopac", "j.mop"],
        cwd=d,
        capture_output=True,
        timeout=600,
    )
    return aux(f"{d}/j.aux")


def agent(kw, el, xyz):
    d = tempfile.mkdtemp()
    write_mop(f"{d}/j.mop", kw, el, xyz)
    r = subprocess.run(
        ["python3", f"{SOL}/run.py", "j.mop", "out.json"],
        cwd=d,
        capture_output=True,
        text=True,
        timeout=600,
    )
    o = json.load(open(f"{d}/out.json"))
    return o["heat_of_formation"], np.array(o["optimized_geometry"]).reshape(-1, 3)


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


import glob

rows = []
for jf in sorted(glob.glob("/refs/*/*/*.json")):
    ref = json.load(open(jf))
    if ref.get("kind") != "opt":
        continue
    name = os.path.basename(jf)[:-5]
    grp = jf.split("/")[2]
    kw, _, el, xyz = parse_mop(jf[:-5] + ".mop")
    xr = np.array(ref["optimized_geometry"]).reshape(-1, 3)
    dm = []
    for s_ in (1, 2, 3, 4):
        h, x = mopac(kw, el, xyz @ rot(s_).T + np.array([0.3, -0.2, 0.1]), "r")
        dm.append(np.abs(D(x) - D(xr)).max())
    rows.append((grp, name, max(dm)))
    print(
        f"{grp:8s} {name:28s} MOPAC-vs-MOPAC rotated max|dDist| {max(dm):.4f}  {'UNREPRODUCIBLE (>3e-3)' if max(dm) > 3e-3 else 'ok'}",
        flush=True,
    )
