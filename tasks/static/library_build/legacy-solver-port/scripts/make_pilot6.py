#!/usr/bin/env python3
"""Build pilot-6 (protein-size single points) references.
usage: make_pilot6.py MOPAC_BIN TESTS_DIR OUT_DIR
Each PDB entry: ADD-H -> hydrogenated .pdb -> MOZYME PM7 1SCF (the reference, since dense PM7 is
impractical at 3500 atoms). A Cartesian .mop (PM7 1SCF CHARGE=n) is written from the AUX geometry.
JSON: kind=scale, elements, keywords, heat_of_formation, atom_charges.
"""

import json, os, re, shutil, subprocess, sys, time

BIN, TESTS, OUT = sys.argv[1:4]
SRC = [
    ("visible", "crambin_1cbn", "PDB1CBN.ent"),
    ("hidden", "crambin_1ejg", "PDB1EJG.ent"),
    ("hidden", "bR_1ap9", "Bacteriorhodopsin_1AP9.ent"),
    ("hidden", "bR_1at9", "Bacteriorhodopsin_1AT9.ent"),
    ("hidden", "bR_1c3w", "Bacteriorhodopsin_1C3W.ent"),
]
env = {"PATH": "/usr/bin:/bin"}


def vec(t, key):
    m = re.search(re.escape(key) + r"\[\d+\]=\s*\n(.*?)\n [A-Z]", t, re.S)
    return m.group(1).split()


for g, name, ent in SRC:
    w = f"{OUT}/_work/{name}"
    os.makedirs(w, exist_ok=True)
    shutil.copy(f"{TESTS}/{ent}", w)
    open(f"{w}/h.mop", "w").write(f'geo_dat="{ent}" ADD-H HTML\nh\n\n')
    subprocess.run([BIN, "h.mop"], cwd=w, env=env, capture_output=True)
    geo = "h.pdb" if os.path.exists(f"{w}/h.pdb") else ent
    open(f"{w}/m.mop", "w").write(
        f'geo_dat="{geo}" 1SCF MOZYME PM7 AUX(PRECISION=9)\nm\n\n'
    )
    t0 = time.time()
    subprocess.run([BIN, "m.mop"], cwd=w, env=env, capture_output=True)
    dt = time.time() - t0
    a = open(f"{w}/m.aux").read()
    o = open(f"{w}/m.out").read()
    chg = int(re.search(r"COMPUTED CHARGE ON SYSTEM:\s*([+-]?\d+)", o).group(1))
    els = vec(a, "ATOM_EL")
    x = vec(a, "ATOM_X:ANGSTROMS")
    heat = float(
        re.search(r"HEAT_OF_FORMATION:KCAL/MOL=\s*(\S+)", a).group(1).replace("D", "E")
    )
    q = [float(v.replace("D", "E")) for v in vec(a, "ATOM_CHARGES")]
    kw = f"PM7 1SCF CHARGE={chg} AUX(PRECISION=9) NOINTER XYZ"
    body = "\n".join(
        f" {e} {x[3 * i]} 1 {x[3 * i + 1]} 1 {x[3 * i + 2]} 1"
        for i, e in enumerate(els)
    )
    d = f"{OUT}/{g}/{name}"
    os.makedirs(d, exist_ok=True)
    open(f"{d}/{name}.mop", "w").write(f"{kw}\n{name}\n\n{body}\n")
    json.dump(
        dict(
            kind="scale",
            elements=els,
            keywords=kw,
            heat_of_formation=heat,
            atom_charges=q,
        ),
        open(f"{d}/{name}.json", "w"),
    )
    print(g, name, len(els), "charge", chg, "heat", heat, f"{dt:.0f}s", flush=True)
