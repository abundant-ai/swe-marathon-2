# Dev tool. FORCE reproducibility: rerun the original MOPAC on rotated copies of each FORCE input and compare with the stored reference
# (verifier tolerances: heat 1e-4, ZPE 1e-3, every sorted frequency 0.2 cm-1). Optionally compare an agent solver (/agent/solver).
import os, re, sys, json, glob, subprocess, tempfile, numpy as np


def fl(b):
    return [float(x.replace("D", "E")) for x in b.split()]


def blk(t, tag):
    m = re.search(
        tag + r"(?:\[\d+\])?[=:]\s*\n?(.*?)(?=\n [A-Z_.:/()\-]+[\[=]|\Z)", t, re.S
    )
    return fl(m.group(1))


def parse_aux(p, n):
    t = open(p).read()
    h = float(
        re.search(r"HEAT_OF_FORMATION:KCAL/MOL=\s*(\S+)", t).group(1).replace("D", "E")
    )
    z = float(
        re.search(r"ZERO_POINT_ENERGY:KCAL/MOL=\s*(\S+)", t).group(1).replace("D", "E")
    )
    lin = "POINT_GROUP=D*h" in t or "POINT_GROUP=C*v" in t
    nv = 3 * n - 5 if lin else 3 * n - 6
    m = re.search(
        r"VIB\._FREQ:CM\(-1\)\[\d+\]=\s*\n(.*?)(?=\n [A-Z_.:/()\-]+[\[=]|\Z)", t, re.S
    )
    return h, z, sorted(fl(m.group(1))[:nv])


def rd(p):
    L = open(p).read().splitlines()
    el = []
    xyz = []
    for l in L[3:]:
        t = l.split()
        if len(t) >= 6:
            el.append(t[0])
            xyz.append([float(t[1]), float(t[3]), float(t[5])])
    return L[0], el, np.array(xyz)


def wr(p, kw, el, xyz):
    open(p, "w").write(
        kw
        + "\nx\n\n"
        + "".join(
            f" {e} {x[0]:.8f} 1 {x[1]:.8f} 1 {x[2]:.8f} 1\n" for e, x in zip(el, xyz)
        )
    )


def mopac(kw, el, xyz):
    d = tempfile.mkdtemp()
    wr(f"{d}/j.mop", kw, el, xyz)
    subprocess.run(
        ["env", "-i", "PATH=/usr/bin:/bin", "/build/mopac", "j.mop"],
        cwd=d,
        capture_output=True,
        timeout=900,
    )
    return parse_aux(f"{d}/j.aux", len(el))


def agent(kw, el, xyz):
    d = tempfile.mkdtemp()
    wr(f"{d}/j.mop", kw, el, xyz)
    subprocess.run(
        ["python3", "/agent/solver/run.py", "j.mop", "out.json"],
        cwd=d,
        capture_output=True,
        timeout=900,
    )
    o = json.load(open(f"{d}/out.json"))
    return o["heat_of_formation"], o["zero_point_energy"], sorted(o["frequencies"])


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


def cmp(ref, got):
    h, z, f = got
    if len(f) != len(ref["frequencies"]):
        return (
            abs(h - ref["heat_of_formation"]),
            abs(z - ref["zero_point_energy"]),
            9e9,
        )
    return (
        abs(h - ref["heat_of_formation"]),
        abs(z - ref["zero_point_energy"]),
        float(np.max(np.abs(np.array(f) - np.array(ref["frequencies"])))),
    )


use_agent = os.path.isdir("/agent/solver")
print(
    f"{'case':26s} {'MOPAC rotated: dH / dZPE / dfreq(max)':44s} {'verdict':14s}"
    + ("  AGENT: dH / dZPE / dfreq" if use_agent else ""),
    flush=True,
)
for jf in sorted(glob.glob("/refs/*/*/*.json")):
    ref = json.load(open(jf))
    if ref.get("kind") != "force":
        continue
    name = os.path.basename(jf)[:-5]
    kw, el, xyz = rd(jf[:-5] + ".mop")
    ds = np.array(
        [
            cmp(ref, mopac(kw, el, xyz @ rot(s).T + np.array([0.3, -0.2, 0.1])))
            for s in (1, 2, 3)
        ]
    ).max(axis=0)
    bad = ds[0] > 1e-4 or ds[1] > 1e-3 or ds[2] > 0.2
    line = f"{jf.split('/')[2][:3]} {name:22s} {ds[0]:.1e} / {ds[1]:.1e} / {ds[2]:9.3f}      {'NOT REPRODUCIBLE' if bad else 'ok':16s}"
    if use_agent:
        try:
            a = cmp(ref, agent(kw, el, xyz))
            line += f"  {a[0]:.1e} / {a[1]:.1e} / {a[2]:.3f}"
        except Exception as e:
            line += "  agent error"
    print(line, flush=True)
