"""Cumulative verifier for legacy-solver-port (MOPAC PM7).

usage: verify.py --step N --solver DIR --refs DIR [--out reward.json] [--workers K]

REFS layout (private; made by scripts/make_pilot*.py with the original MOPAC, never shipped to the solver):
  REFS/step1/{visible,hidden}/<case>/<case>.{mop,json}      sp and opt references (kind = sp | opt)
  REFS/step2/...                                            FORCE references (kind = force)
  REFS/step3/...                                            protein references (kind = scale)
  REFS/step4/...                                            format references (kind = fmt)
Step N scores steps 1..N. Only hidden cases count toward the reward; the denominator of each step is its
number of hidden cases (fixed, no matter how many jobs crash). Visible cases are reported only.
A case passes when every quantity is within tolerance. Any harness error exits non-zero and writes no reward.
The solver directory is copied alone into a clean temp dir; jobs run with a minimal environment.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

SP = {
    "heat_of_formation": 1e-4,
    "gradients": 1e-3,
    "atom_charges": 1e-5,
    "ionization_potential": 1e-4,
    "dipole": 1e-4,
}
OPT = {
    "heat_of_formation": 5e-3,
    "geometry": 3e-3,
    "atom_charges": 1e-3,
    "ionization_potential": 1e-3,
    "dipole": 1e-3,
}
FORCE = {"heat_of_formation": 1e-4, "zero_point_energy": 1e-3, "frequencies": 0.2}
SCALE = {"heat_of_formation": 1.0, "atom_charges": 0.02}
# The solver is the candidate's code: when the verifier runs as root it is executed as this unprivileged user, so it
# cannot read the references (/tests/private, mode 0700, root) or write the reward file.
SOLVER_UID = 10001
TIMEOUT = {"sp": 900, "opt": 900, "force": 900, "scale": 1800, "fmt": 900}


def err(a, b):
    a, b = np.atleast_1d(np.array(a, float)), np.atleast_1d(np.array(b, float))
    return float(np.max(np.abs(a - b))) if a.shape == b.shape else float("inf")


def dist(x):
    x = np.array(x, float).reshape(-1, 3)
    return np.linalg.norm(x[:, None] - x[None], axis=-1)


def dummy_rows(mop):
    """Rows of a Z-matrix that involve a dummy atom (the atom itself or one of its three reference atoms).
    Their final values are not determined by the energy (flat directions), so they depend on the optimizer path
    and are not checked."""
    try:
        lines = Path(mop).read_text().splitlines()[3:]
        rows = [ln.split() for ln in lines if ln.strip()]
        dum = {i + 1 for i, t in enumerate(rows) if t[0].upper() in ("XX", "X")}
        return {
            i
            for i, t in enumerate(rows)
            if (i + 1) in dum or any(int(v) in dum for v in t[7:10])
        }
    except Exception:  # noqa: BLE001
        return set()


def ic_ok(got, ref, skip=()):
    g, r = np.array(got, float), np.array(ref, float)
    if g.shape != r.shape:
        return False
    keep = [i for i in range(len(r)) if i not in skip]
    g, r = g[keep], r[keep]
    d = np.abs(g - r)
    dd = np.abs((g[:, 2] - r[:, 2] + 180) % 360 - 180)
    return d[:, 0].max() <= 5e-3 and d[:, 1].max() <= 0.2 and dd.max() <= 0.5


def tolerances(ref):
    k = ref["kind"]
    if k == "sp":
        return SP
    if k == "opt":
        return OPT
    if k == "force":
        return FORCE
    if k == "scale":
        return SCALE
    if k == "fmt":
        t = dict(OPT if "optimized_geometry" in ref else SP)
        t.pop("gradients", None)
        t["internal"] = 0
        return t
    raise ValueError(k)


def purge_solver_files(root):
    """Remove what the candidate's solver left in a shared folder, so that a case cannot use files made by an earlier case."""
    for entry in os.scandir(root):
        try:
            if entry.stat(follow_symlinks=False).st_uid == SOLVER_UID:
                if entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(entry.path, ignore_errors=True)
                else:
                    os.unlink(entry.path)
        except OSError:
            continue


def run_case(solver, jf, timeout_scale=1.0):
    ref = json.loads(Path(jf).read_text())
    name = os.path.basename(jf)[:-5]
    work = tempfile.mkdtemp(prefix="v_" + name + "_")
    drop = os.geteuid() == 0
    if drop:
        os.chown(work, SOLVER_UID, SOLVER_UID)
    for f in glob.glob(jf[:-5] + ".*"):
        if not f.endswith(".json"):
            shutil.copy(f, work)
            if drop:
                os.chown(
                    os.path.join(work, os.path.basename(f)), SOLVER_UID, SOLVER_UID
                )
    py = shutil.which("python3")
    env = {
        "PATH": os.path.dirname(py) + ":/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": work,
        "HOME": work,
    }
    t = time.time()
    try:
        r = subprocess.run(
            [py, os.path.join(solver, "run.py"), name + ".mop", "out.json"],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT[ref["kind"]] * timeout_scale,
            user=SOLVER_UID if drop else None,
            group=SOLVER_UID if drop else None,
        )
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"
    el = time.time() - t
    tol = tolerances(ref)
    ok = {k: False for k in tol}
    try:
        got = json.loads((Path(work) / "out.json").read_text())
        for k, tv in tol.items():
            if k == "geometry":
                ok[k] = (
                    err(
                        dist(got["optimized_geometry"]), dist(ref["optimized_geometry"])
                    )
                    <= tv
                )
            elif k == "internal":
                ok[k] = (
                    ic_ok(
                        got["internal_coordinates"],
                        ref["internal_coordinates"],
                        dummy_rows(os.path.join(work, name + ".mop")),
                    )
                    if "internal_coordinates" in ref
                    else True
                )
            elif k in got:
                a = sorted(got[k]) if k == "frequencies" else got[k]
                ok[k] = err(a, ref[k]) <= tv
    except Exception:  # noqa: BLE001, S110  (a candidate output that cannot be parsed fails the case)
        pass
    shutil.rmtree(work, ignore_errors=True)
    if drop:
        purge_solver_files("/tmp")
    return name, rc, el, all(ok.values()), ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, required=True)
    ap.add_argument("--solver", required=True)
    ap.add_argument("--refs", required=True)
    ap.add_argument("--out", default="reward.json")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.solver):
        os.makedirs(a.solver, exist_ok=True)
    if not os.path.exists(os.path.join(a.solver, "run.py")):
        # A missing solver is a candidate failure (every case fails, reward 0), not a harness error.
        print("no run.py in solver dir: every case will fail", file=sys.stderr)
    tmp = tempfile.mkdtemp(prefix="solver_")
    os.chmod(tmp, 0o755)
    solver = os.path.join(tmp, "solver")
    shutil.copytree(a.solver, solver, ignore=shutil.ignore_patterns("__pycache__"))
    for root, dirs, files in os.walk(solver):
        for n in dirs + files:
            os.chmod(
                os.path.join(root, n),
                os.stat(os.path.join(root, n)).st_mode
                | 0o444
                | (0o111 if n in dirs else 0),
            )
    os.chmod(solver, 0o755)
    result = {"steps": {}}
    for s in range(1, a.step + 1):
        base = os.path.join(a.refs, f"step{s}")
        hidden = sorted(glob.glob(f"{base}/hidden/*/*.json"))
        visible = sorted(glob.glob(f"{base}/visible/*/*.json"))
        if not hidden:
            print(f"no hidden references for step {s}", file=sys.stderr)
            sys.exit(3)
        rows = []
        for group, files in (("visible", visible), ("hidden", hidden)):
            for jf in files:
                name, rc, el, ok_all, ok = run_case(solver, jf)
                rows.append((group, name, rc, el, ok_all, ok))
                print(
                    f"step{s} {group:7s} {name:28s} rc={rc!s:>7s} {el:7.1f}s {'PASS' if ok_all else 'FAIL ' + ','.join(k for k, v in ok.items() if not v)}",
                    flush=True,
                )
        hid = [r for r in rows if r[0] == "hidden"]
        n_pass = sum(r[4] for r in hid)
        result["steps"][s] = {
            "hidden_pass": n_pass,
            "hidden_total": len(hid),
            "score": n_pass / len(hid),
            "visible_pass": sum(r[4] for r in rows if r[0] == "visible"),
            "visible_total": len(visible),
            "failed": [r[1] for r in hid if not r[4]],
        }
    total = sum(v["hidden_total"] for v in result["steps"].values())
    passed = sum(v["hidden_pass"] for v in result["steps"].values())
    result["reward"] = (
        passed / total
    )  # fixed denominator: every hidden case of steps 1..N
    result["reward_current_step"] = result["steps"][a.step]["score"]
    # Harbor needs reward.json to hold flat numbers only; per-case detail goes to a separate file.
    flat = {
        "reward": result["reward"],
        "reward_current_step": result["reward_current_step"],
    }
    for s, v in result["steps"].items():
        flat[f"step{s}_score"] = v["score"]
    Path(a.out).write_text(json.dumps(flat, indent=1))
    Path(os.path.splitext(a.out)[0] + "_details.json").write_text(
        json.dumps(result, indent=1)
    )
    print(json.dumps(flat))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
