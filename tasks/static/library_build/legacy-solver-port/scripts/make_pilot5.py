#!/usr/bin/env python3
"""Build pilot-5 (FORCE) references from the pilot-4 molecules.
usage: make_pilot5.py MOPAC_BIN PILOT4_REF OUT_DIR
For each pilot-4 single-point molecule: reference-optimize (PM7 PRECISE EF GNORM=0.01),
then run PM7 FORCE PRECISE at that geometry. JSON: kind=force, elements, keywords,
heat_of_formation, zero_point_energy, frequencies (3N-6 or 3N-5 vibrational, ascending).
Visible = 6 molecules, hidden = rest.
"""

import glob, json, os, re, shutil, subprocess, sys

BIN, REF, OUT = sys.argv[1:4]
VIS = {
    "water",
    "methane",
    "formaldehyde",
    "methyl_chloride",
    "ammonium",
    "methyl_radical",
}


def aux(path):
    d, key = {}, None
    for ln in open(path):
        m = re.match(r"\s*([A-Z_.:()\-*/0-9a-z]+?)(\[\d+\])?=(.*)$", ln)
        if (
            m
            and ln[0] == " "
            and m.group(1).isupper()
            or (m and m.group(1)[0].isupper() and "=" in ln and not ln.startswith("  "))
        ):
            key = m.group(1)
            d[key] = m.group(3).split()
            continue
        if key:
            d[key] += ln.split()
    return d


def run(work, name, text):
    os.makedirs(work, exist_ok=True)
    open(f"{work}/{name}.mop", "w").write(text)
    subprocess.run(
        [BIN, f"{name}.mop"],
        cwd=work,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        timeout=900,
    )
    return aux(f"{work}/{name}.aux")


for jf in sorted(glob.glob(f"{REF}/*/*/*.json")):
    name = os.path.basename(jf)[:-5]
    if name.endswith("_opt"):
        continue
    ref = json.load(open(jf))
    if len(ref["elements"]) < 2:
        continue
    lines = open(jf[:-5] + ".mop").read().split("\n")
    extras = " ".join(
        t
        for t in lines[0].split()
        if t in ("UHF", "DOUBLET", "TRIPLET") or t.startswith("CHARGE=")
    )
    els = ref["elements"]
    coords = [l.split()[1:6:2] for l in lines[3:] if l.strip()]
    body = "\n".join(f" {e} {c[0]} 1 {c[1]} 1 {c[2]} 1" for e, c in zip(els, coords))
    w = f"{OUT}/_work/{name}"
    a = run(
        w,
        "opt",
        f"PM7 {extras} PRECISE EF GNORM=0.01 AUX(PRECISION=9) NOINTER XYZ T=1200\n{name}\n\n{body}\n",
    )
    x = [float(v.replace("D", "E")) for v in a["ATOM_X_OPT:ANGSTROMS"]]
    body = "\n".join(
        f" {e} {x[3 * i]:.8f} 1 {x[3 * i + 1]:.8f} 1 {x[3 * i + 2]:.8f} 1"
        for i, e in enumerate(els)
    )
    kw = f"PM7 {extras} PRECISE FORCE AUX(PRECISION=9) NOINTER XYZ".replace("  ", " ")
    f = run(w, "force", f"{kw}\n{name}\n\n{body}\n")
    n = len(els)
    lin = any(
        k in open(f"{w}/force.aux").read()
        for k in ("POINT_GROUP=D*h", "POINT_GROUP=C*v")
    )
    nv = 3 * n - 5 if lin else 3 * n - 6
    fr = sorted(float(v) for v in f["VIB._FREQ:CM(-1)"])
    # MOPAC lists vibrations first, then 6 (5) trans/rot; keep the first nv
    fr = sorted(float(v) for v in f["VIB._FREQ:CM(-1)"][:nv])
    g = "visible" if name in VIS else "hidden"
    os.makedirs(f"{OUT}/{g}/{name}", exist_ok=True)
    open(f"{OUT}/{g}/{name}/{name}.mop", "w").write(f"{kw}\n{name}\n\n{body}\n")
    json.dump(
        dict(
            kind="force",
            elements=els,
            keywords=kw,
            heat_of_formation=float(
                f["HEAT_OF_FORMATION:KCAL/MOL"][0].replace("D", "E")
            ),
            zero_point_energy=float(f["ZERO_POINT_ENERGY:KCAL/MOL"][0]),
            frequencies=fr,
        ),
        open(f"{OUT}/{g}/{name}/{name}.json", "w"),
        indent=1,
    )
    shutil.copy(f"{w}/force.aux", f"{OUT}/{g}/{name}/{name}.aux")
    print(g, name, n, round(min(fr), 1))
