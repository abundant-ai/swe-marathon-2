#!/usr/bin/env python3
"""Build step-4 (input-format migration) references from the step-1 molecule set.
usage: make_pilot7.py MOPAC_BIN PILOT4_REF_DIR OUT_DIR
Variants (kind="fmt"): zmat (plain Z-matrix, 1SCF or opt), dummy (leading dummy atom XX), fixed (some flags 0, opt),
pdb (HETATM PDB read via GEO_DAT=, 1SCF).  Reference = MOPAC run on the same input.
JSON: kind, variant, elements (no dummies), keywords, heat_of_formation, atom_charges, ionization_potential, dipole,
optimized_geometry (opt only; no dummies), internal_coordinates (Z-matrix jobs: rows [r, angle, dihedral] incl. dummies,
final values from the .arc FINAL GEOMETRY block).
"""

import glob, json, os, re, shutil, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zmat

BIN, REF, OUT = sys.argv[1:4]
env = {"PATH": "/usr/bin:/bin"}
rng = np.random.default_rng(7)


def vec(t, key):
    m = re.search(re.escape(key) + r"\[\d+\]=\s*\n(.*?)\n [A-Z]", t, re.S)
    return [
        float(v.replace("D", "E")) if re.match(r"^[-+0-9.]", v) else v
        for v in m.group(1).split()
    ]


def parse_arc(path):
    L = open(path).read().split("\n")
    i = max(k for k, l in enumerate(L) if "FINAL GEOMETRY OBTAINED" in l)
    rows = []
    for l in L[i + 4 :]:
        p = l.split()
        if len(p) < 9 or not re.match(r"^[A-Za-z]{1,2}$", p[0]):
            break
        rows.append([float(p[1]), float(p[3]), float(p[5])])
    return rows


def read_mop(path):
    L = open(path).read().split("\n")
    at = [l.split() for l in L[3:] if l.strip()]
    return (
        L[0],
        [a[0] for a in at],
        np.array([[float(a[1]), float(a[3]), float(a[5])] for a in at]),
    )


def run(w, name, kw, title, body_lines):
    os.makedirs(w, exist_ok=True)
    open(f"{w}/{name}.mop", "w").write(
        f"{kw}\n{title}\n\n" + "\n".join(body_lines) + ("\n" if body_lines else "")
    )
    subprocess.run([BIN, f"{name}.mop"], cwd=w, env=env, capture_output=True)
    if not os.path.exists(f"{w}/{name}.aux"):
        return None
    return open(f"{w}/{name}.aux").read()


made = []
for g in ("visible", "hidden"):
    for mp in sorted(glob.glob(f"{REF}/{g}/*/*.mop")):
        name = os.path.basename(mp)[:-4]
        kw0, els, x = read_mop(mp)
        is_opt = "EF" in kw0.split()
        made.append((g, name, kw0, els, x, is_opt))

cases = []
for g, name, kw0, els, x, is_opt in made:
    n = len(els)
    if n < 3:
        continue
    base = [
        t
        for t in kw0.split()
        if t not in ("XYZ", "GRAD", "1SCF", "NOINTER") and not t.startswith("AUX")
    ]
    base_opt = [
        t
        for t in base
        if t not in ("PRECISE", "EF") and not t.startswith(("GNORM", "T="))
    ]
    for variant in ("zmat", "dummy", "fixed", "pdb"):
        if variant == "fixed" and (not is_opt or n < 5):
            continue
        if variant == "pdb" and is_opt:
            continue
        opt = is_opt if variant != "pdb" else False
        kws = (
            base_opt
            + (
                ["PRECISE", "EF", "GNORM=0.001" if variant == "fixed" else "GNORM=0.01"]
                if opt
                else ["1SCF"]
            )
            + ["AUX(PRECISION=9)", "NOINTER"]
            + (["T=1200"] if opt else [])
        )
        kw = " ".join(kws)
        cases.append((g, name, variant, els, x, kw, opt))

# keep the benchmark reasonably sized: visible = 6 cases, hidden = the rest of a random subset
rng.shuffle(cases)
rows_out = []
vis_quota = {"zmat": 2, "dummy": 1, "fixed": 1, "pdb": 1}
for g, name, variant, els, x, kw, opt in cases:
    key = f"{variant}_{name}"
    use_g = None
    # visible quotas come from source-visible OR hidden molecules; visibility is decided here by quota, but the
    # source-hidden molecule is never shown for the same variant twice.
    if vis_quota.get(variant, 0) > 0 and g == "visible":
        vis_quota[variant] -= 1
        use_g = "visible"
    elif g == "hidden":
        use_g = "hidden"
    else:
        continue
    w = f"{OUT}/_work/{key}"
    if variant == "pdb":
        pdb = []
        for i, (e, p) in enumerate(zip(els, x)):
            pdb.append(
                "HETATM%5d %-4s UNK A   1    %8.3f%8.3f%8.3f  1.00  0.00          %2s"
                % (i + 1, e + str(i + 1), p[0], p[1], p[2], e)
            )
        pdb.append("END")
        os.makedirs(w, exist_ok=True)
        open(f"{w}/{key}.pdb", "w").write("\n".join(pdb) + "\n")
        kw_run = kw.replace("1SCF", f'1SCF GEO_DAT="{key}.pdb"')
        a = run(w, key, kw_run, key, [])
        body = None
    else:
        xx, ee = x.copy(), list(els)
        if variant == "dummy":
            d = x.mean(axis=0) + np.array([0.3, 0.1, 3.0])
            xx = np.vstack([d, x])
            ee = ["XX"] + ee
        refs = zmat.build_refs(xx)
        if refs is None:
            print("skip (collinear)", key)
            continue
        zr = zmat.to_zmat(xx, refs)
        flags = None
        if variant == "fixed":
            flags = [[1, 1, 1] for _ in zr]
            k = int(rng.integers(3, len(zr)))
            flags[k][2] = 0  # fix one dihedral
            flags[int(rng.integers(1, len(zr)))][0] = 0  # fix one bond
        body = zmat.write_zmat(ee, zr, flags)
        kw_run = kw
        a = run(w, key, kw_run, key, body)
    if a is None:
        print("MOPAC failed", key)
        continue
    d = f"{OUT}/{use_g}/{key}"
    os.makedirs(d, exist_ok=True)
    out = open(f"{w}/{key}.out").read()
    ref = dict(
        kind="fmt",
        variant=variant,
        elements=list(els),
        keywords=kw_run,
        heat_of_formation=float(
            re.search(r"HEAT_OF_FORMATION:KCAL/MOL=\s*(\S+)", a)
            .group(1)
            .replace("D", "E")
        ),
        atom_charges=vec(a, "ATOM_CHARGES"),
        ionization_potential=float(
            re.search(r"IONIZATION_POTENTIAL:EV=\s*(\S+)", a).group(1).replace("D", "E")
        ),
        dipole=float(re.search(r"DIPOLE:DEBYE=\s*(\S+)", a).group(1).replace("D", "E")),
    )
    if opt:
        ref["optimized_geometry"] = vec(a, "ATOM_X_OPT:ANGSTROMS")
        assert len(ref["optimized_geometry"]) == 3 * len(els), (
            key,
            len(ref["optimized_geometry"]),
            len(els),
        )
    if variant != "pdb":
        ref["internal_coordinates"] = parse_arc(f"{w}/{key}.arc")
    json.dump(ref, open(f"{d}/{key}.json", "w"))
    shutil.copy(f"{w}/{key}.mop", d)
    if variant == "pdb":
        shutil.copy(f"{w}/{key}.pdb", d)
    print(use_g, key, ref["heat_of_formation"], flush=True)
