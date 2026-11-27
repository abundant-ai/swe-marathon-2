"""Dev script: run the Fortran reference and a candidate on a deck, compare outputs.
usage: compare_to_fortran.py <case-name> <deck-body> [restart-from-case]
"""

import os, subprocess, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORT = os.path.join(ROOT, "legacy", "nsflow")
CAND = [
    sys.executable,
    os.path.join(ROOT, "experiment", "solution_A_v1_step3", "nsflow.py"),
]
WORK = os.environ.get("NSWORK", "/tmp/nscmp")


def run(cmd, case, deck, sub):
    d = os.path.join(WORK, case, sub)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for f in (
        os.listdir(os.path.join(WORK, case, "seed"))
        if os.path.isdir(os.path.join(WORK, case, "seed"))
        else []
    ):
        shutil.copy(os.path.join(WORK, case, "seed", f), d)
    subprocess.run(
        cmd,
        input="&INPUT " + deck + " /\n",
        text=True,
        cwd=d,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return d


def load(path):
    h = open(path).readline().split()
    return float(h[4]), np.loadtxt(path, comments="#")


def compare(case, deck, seed=None):
    if seed:
        s = os.path.join(WORK, case, "seed")
        shutil.rmtree(os.path.join(WORK, case), ignore_errors=True)
        os.makedirs(s)
        shutil.copy(seed, os.path.join(s, "seed.rst"))
    else:
        shutil.rmtree(os.path.join(WORK, case), ignore_errors=True)
        os.makedirs(os.path.join(WORK, case))
    a = run([FORT], case, deck, "fortran")
    b = run(CAND, case, deck, "candidate")
    ta, da = load(os.path.join(a, "o_final.dat"))
    tb, db = load(os.path.join(b, "o_final.dat"))
    rel = np.linalg.norm(da[:, 2:] - db[:, 2:]) / np.linalg.norm(da[:, 2:])
    ra = open(os.path.join(a, "o_final.rst"), "rb").read()
    rb = open(os.path.join(b, "o_final.rst"), "rb").read()
    print(
        "%-14s dT=%.2e relL2=%.2e max|d|=%.2e rst bytes equal=%s"
        % (case, abs(ta - tb), rel, np.abs(da[:, 2:] - db[:, 2:]).max(), ra == rb)
    )
    return os.path.join(a, "o_final.rst")


if __name__ == "__main__":
    compare(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
