"""Dev script: which cases of a candidate characterization suite kill which mutant binaries?"""

import os, shutil, subprocess, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = "/tmp/killm"
RE, PE = 37.5, 26.6
CASES = {
    "cavity": ["IMAX=16,JMAX=16,RE=100.,EPS=1e-8,ITERMAX=5000,NMAX=200,OPFX='o'"],
    "freeslip": [
        "IMAX=24,JMAX=16,XLEN=1.5,RE=400.,GAMMA=0.5,TAU=0.4,OMEGA=1.5,EPS=1e-7,ITERMAX=3000,NMAX=150,IBCW=2,IBCS=2,OPFX='o'"
    ],
    "obstacle": [
        "IMAX=20,JMAX=20,RE=200.,EPS=1e-8,ITERMAX=5000,NMAX=250,IOA1=7,IOB1=12,JOA1=6,JOB1=11,IOA2=15,IOB2=17,JOA2=14,JOB2=18,OPFX='o'"
    ],
    "heated": [
        "IMAX=16,JMAX=16,RE=%s,PEC=%s,ITEMP=1,ULID=0.,GAMMA=0.3,EPS=1e-8,ITERMAX=5000,NMAX=250,OPFX='o'"
        % (RE, PE)
    ],
    "heated_obst": [
        "IMAX=20,JMAX=20,RE=%s,PEC=%s,ITEMP=1,ULID=0.,IBCTE=2,EPS=1e-8,ITERMAX=5000,NMAX=200,IOA1=8,IOB1=12,JOA1=8,JOB1=12,OPFX='o'"
        % (RE, PE)
    ],
    "loose_tol": ["IMAX=16,JMAX=16,RE=100.,EPS=1e-3,ITERMAX=5000,NMAX=200,OPFX='o'"],
    "restart": [
        "IMAX=16,JMAX=16,RE=100.,EPS=1e-8,ITERMAX=5000,NMAX=100,OPFX='o'",
        "IMAX=16,JMAX=16,RE=100.,EPS=1e-8,ITERMAX=5000,NMAX=300,IRESTR=1,RFILE='prev.rst',OPFX='o'",
    ],
    "restart_heat": [
        "IMAX=16,JMAX=16,RE=%s,PEC=%s,ITEMP=1,ULID=0.,EPS=1e-8,ITERMAX=5000,NMAX=100,OPFX='o'"
        % (RE, PE),
        "IMAX=16,JMAX=16,RE=%s,PEC=%s,ITEMP=1,ULID=0.,EPS=1e-8,ITERMAX=5000,NMAX=300,IRESTR=1,RFILE='prev.rst',OPFX='o'"
        % (RE, PE),
    ],
    "lid_fast": [
        "IMAX=24,JMAX=24,RE=1000.,ULID=2.,EPS=1e-8,ITERMAX=5000,NMAX=150,OPFX='o'"
    ],
}


def run_case(binary, name, decks):
    d = os.path.join(WORK, os.path.basename(os.path.dirname(binary)), name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for k, deck in enumerate(decks):
        subprocess.run(
            [binary],
            input="&INPUT " + deck + " /\n",
            text=True,
            cwd=d,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        if k < len(decks) - 1:
            shutil.copy(os.path.join(d, "o_final.rst"), os.path.join(d, "prev.rst"))
    h = open(os.path.join(d, "o_final.dat")).readline().split()
    return float(h[4]), np.loadtxt(os.path.join(d, "o_final.dat"), comments="#")


def differs(a, b, tol):
    if abs(a[0] - b[0]) > tol * abs(a[0]):
        return True
    cols = [2, 3] + ([5] if a[1].shape[1] > 5 else [])
    return any(
        np.linalg.norm(a[1][:, c] - b[1][:, c]) > tol * np.linalg.norm(a[1][:, c])
        for c in cols
    )


base = os.path.join(ROOT, "legacy", "nsflow")
mdir = os.path.join(ROOT, "experiment", "mutants")
mutants = sorted(os.listdir(mdir), key=lambda s: int(s.split("_")[0][1:]))
ref = {n: run_case(base, n, d) for n, d in CASES.items()}
for tol in (1e-6, 1e-10):
    print("=== tolerance %.0e (relative L2 on u, v, T, and physical time)" % tol)
    print("%-22s" % "mutant" + " ".join("%-12s" % c[:12] for c in CASES) + " killed")
    killed = 0
    for m in mutants:
        row = []
        for n, d in CASES.items():
            row.append(
                differs(ref[n], run_case(os.path.join(mdir, m, "nsflow"), n, d), tol)
            )
        killed += any(row)
        print(
            "%-22s" % m
            + " ".join("%-12s" % ("KILL" if r else ".") for r in row)
            + (" yes" if any(row) else " NO")
        )
    print("mutants killed: %d / %d" % (killed, len(mutants)))
