"""Dev script: evaluate a pilot solver against the vendor binary on hidden decks, and its suite against mutants.
usage: eval_pilot.py <pilot_dir>
"""

import glob, os, shutil, subprocess, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT = os.path.abspath(sys.argv[1])
VENDOR = os.path.join(PILOT, "vendor", "nsflow-2.0")
SOLVER = os.path.join(PILOT, "work", "solver", "run")
WORK = "/tmp/pilot_eval"
HIDDEN = {
    "g1_cavity_re400": [
        "IMAX=16,JMAX=16,RE=400.,EPS=1e-9,ITERMAX=5000,NMAX=120,OPFX='o'"
    ],
    "g2_aspect_lowRe": [
        "IMAX=24,JMAX=12,XLEN=2.0,RE=15.,EPS=1e-9,ITERMAX=4000,NMAX=100,OPFX='o'"
    ],
    "g3_aup_tol": [
        "IMAX=14,JMAX=14,RE=500.,AUP=0.5,TOL=3e-3,CFLMAX=0.5,EPS=1e-9,ITERMAX=5000,NMAX=120,OPFX='o'"
    ],
    "g4_default_eps": ["IMAX=14,JMAX=14,RE=100.,NMAX=100,OPFX='o'"],
    "g5_freeslip_mix": [
        "IMAX=18,JMAX=14,RE=250.,ULID=2.,OMEGA=1.3,EPS=1e-9,ITERMAX=5000,NMAX=100,IBCW=2,IBCS=2,OPFX='o'"
    ],
    "g6_tend": ["IMAX=16,JMAX=16,RE=100.,TEND=1.2,EPS=1e-9,ITERMAX=5000,OPFX='o'"],
    "g7_restart_nsteps": [
        "IMAX=16,JMAX=16,RE=100.,EPS=1e-9,ITERMAX=5000,NMAX=50,OPFX='o'",
        "IMAX=16,JMAX=16,RE=100.,EPS=1e-9,ITERMAX=5000,NMAX=130,IRESTR=1,RFILE='prev.rst',OPFX='o'",
    ],
    "g8_restart_dt0": [
        "IMAX=20,JMAX=14,XLEN=1.5,RE=200.,EPS=1e-9,ITERMAX=5000,NMAX=40,OPFX='o'",
        "IMAX=20,JMAX=14,XLEN=1.5,RE=200.,DT0=0.02,EPS=1e-9,ITERMAX=5000,NMAX=100,IRESTR=1,RFILE='prev.rst',OPFX='o'",
    ],
    "g9_gravity_lid": [
        "IMAX=14,JMAX=14,RE=100.,GX=1.0,GY=-0.5,EPS=1e-9,ITERMAX=5000,NMAX=100,OPFX='o'"
    ],
}


def run(cmd, d, deck, check=True):
    return subprocess.run(
        cmd,
        input="&INPUT " + deck + " /\n",
        text=True,
        cwd=d,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=1800,
    )


def load(d):
    f = os.path.join(d, "o_final.dat")
    h = open(f).readline().split()
    return float(h[4]), np.loadtxt(f, comments="#")


def rel(a, b):
    return np.linalg.norm(a - b) / max(np.linalg.norm(a), 1e-300)


def play(cmd, name, decks, seed_rst=None):
    d = os.path.join(
        WORK,
        name,
        os.path.basename(os.path.dirname(cmd)) + "_" + str(abs(hash(cmd)) % 1000),
    )
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for k, deck in enumerate(decks):
        if k > 0:
            shutil.copy(os.path.join(d, "o_final.rst"), os.path.join(d, "prev.rst"))
        if seed_rst and k > 0:
            shutil.copy(seed_rst, os.path.join(d, "prev.rst"))
        run([cmd], d, deck)
    return d


print("=== hidden-deck fidelity (relative L2 vs vendor)")
print("%-20s %10s %10s %10s %10s %s" % ("deck", "dT_phys", "u", "v", "p(dm)", "rst"))
for name, decks in HIDDEN.items():
    v = play(VENDOR, name + "_v", decks)
    try:
        c = play(SOLVER, name + "_c", decks)
        tv, dv = load(v)
        tc, dc = load(c)
        pv = dv[:, 4] - dv[:, 4].mean()
        pc = dc[:, 4] - dc[:, 4].mean()
        same = (
            open(os.path.join(v, "o_final.rst"), "rb").read()
            == open(os.path.join(c, "o_final.rst"), "rb").read()
        )
        print(
            "%-20s %10.2e %10.2e %10.2e %10.2e %s"
            % (
                name,
                abs(tv - tc) / abs(tv),
                rel(dv[:, 2], dc[:, 2]),
                rel(dv[:, 3], dc[:, 3]),
                rel(pv, pc),
                "byte-equal" if same else "differs",
            )
        )
    except Exception as e:
        print("%-20s FAILED: %s" % (name, str(e)[:120]))
# cross-read: vendor continues from the candidate's restart file
try:
    d1 = play(SOLVER, "x_c", [HIDDEN["g7_restart_nsteps"][0]])
    d2 = os.path.join(WORK, "x_vc")
    shutil.rmtree(d2, ignore_errors=True)
    os.makedirs(d2)
    shutil.copy(os.path.join(d1, "o_final.rst"), os.path.join(d2, "prev.rst"))
    run([VENDOR], d2, HIDDEN["g7_restart_nsteps"][1])
    dref = play(VENDOR, "g7_restart_nsteps_v", HIDDEN["g7_restart_nsteps"])
    tv, dv = load(dref)
    tc, dc = load(d2)
    print(
        "vendor reading candidate restart: dT %.2e u %.2e"
        % (abs(tv - tc) / abs(tv), rel(dv[:, 2], dc[:, 2]))
    )
except Exception as e:
    print("cross-read FAILED:", str(e)[:150])
# suite quality: candidate suite decks vs mutant binaries (golden = vendor binary on the same deck)
print("=== characterization suite vs mutants (u, v, T at 1e-6)")
suite = sorted(
    glob.glob(
        os.path.join(PILOT, "work", "characterization", "**", "*.in"), recursive=True
    )
)
print("suite decks found:", len(suite))
mdir = os.path.join(ROOT, "experiment", "mutants2")
applicable = sorted(os.listdir(mdir))


def decks_of(path):
    txt = open(path).read()
    return [txt.strip().replace("&INPUT", "").rstrip("/").strip()]


killed = {}
for m in applicable:
    killed[m] = False
for k, path in enumerate(suite):
    base = os.path.dirname(path)
    # a case may chain with a preceding restart file named in its deck; run it in a copy of its folder
    for who in ["vendor"] + applicable:
        d = os.path.join(WORK, "suite", who, "%02d" % k)
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(base, d)
        cmd = VENDOR if who == "vendor" else os.path.join(mdir, who, "nsflow")
        try:
            subprocess.run(
                [cmd],
                stdin=open(path),
                cwd=d,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=600,
                env=dict(os.environ, DYLD_LIBRARY_PATH=os.environ["FORTLIB"]),
            )
        except Exception:
            pass
    ref = os.path.join(WORK, "suite", "vendor", "%02d" % k)
    for m in applicable:
        mm = os.path.join(WORK, "suite", m, "%02d" % k)
        for f in glob.glob(os.path.join(ref, "*_final.dat")):
            g = os.path.join(mm, os.path.basename(f))
            if not os.path.exists(g):
                continue
            a, b = np.loadtxt(f, comments="#"), np.loadtxt(g, comments="#")
            if a.ndim < 2 or b.ndim < 2 or a.shape != b.shape:
                killed[m] = killed[m] or (a.shape != b.shape)
                continue
            ha, hb = open(f).readline().split(), open(g).readline().split()
            if abs(float(ha[4]) - float(hb[4])) > 1e-6 * abs(float(ha[4])) or any(
                rel(a[:, c], b[:, c]) > 1e-6 for c in (2, 3)
            ):
                killed[m] = True
print({m: ("KILLED" if v else "survived") for m, v in killed.items()})
print(
    "kill rate: %d / %d (mutants of NSFLOW 2; equivalence not checked)"
    % (sum(killed.values()), len(killed))
)
