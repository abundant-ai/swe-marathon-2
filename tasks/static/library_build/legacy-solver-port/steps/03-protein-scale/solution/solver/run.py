#!/usr/bin/env python3
"""Command line entry:  python3 run.py job.mop out.json

Standalone PM7 port (H, C, N, O, F, P, S, Cl, Br).  Needs only numpy.
Inputs: Cartesian .mop, Z-matrix (dummy atoms, fixed flags), PDB through GEO_DAT.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BIG_ATOMS = 250  # Cartesian single points with more atoms go to the linear-scaling path (pm7/scale.py)


def _count_atoms(path):
    """Cheap pre-scan (before numpy is imported): number of atom lines of a Cartesian .mop."""
    try:
        with open(path) as f:
            lines = f.read().splitlines()
        return sum(1 for ln in lines[3:] if ln.strip()), lines[0].upper()
    except Exception:
        return 0, ""


if len(sys.argv) == 3:
    _n, _kw = _count_atoms(sys.argv[1])
    if _n > BIG_ATOMS and " 1SCF" in " " + _kw:
        # the large-system path is task parallel (threads, one BLAS thread each); a multi-threaded
        # BLAS underneath would oversubscribe the cores.  Must be set before numpy is imported.
        for _v in (
            "OPENBLAS_NUM_THREADS",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            os.environ[_v] = "1"

from pm7.driver import run_job, single_point, optimise  # noqa: E402
from pm7.system import read_mop  # noqa: E402
from pm7 import formats  # noqa: E402


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: run.py job.mop out.json\n")
        return 2
    job, zi = formats.load(argv[1])
    if job is None:
        job = read_mop(argv[1])
    xall = None
    if zi is not None and not job.one_scf and not job.force:
        res, xall = formats.optimise_internal(job, zi)
    elif (
        len(job.elements) > BIG_ATOMS and job.one_scf and not job.force and not job.uhf
    ):
        from pm7 import scale

        try:
            res, _ = scale.single_point_big(job)
        except scale.NotSupported:
            res = run_job(job)
    else:
        res = run_job(job)
    out = {
        "kind": "force" if job.force else ("sp" if job.one_scf else "opt"),
        "elements": [e for e in job.elements],
        "keywords": job.keywords,
    }
    out.update(res)
    if zi is not None:
        if xall is None:
            xall = formats.zmat_to_cart(zi.vals, zi.refs)
        out["internal_coordinates"] = formats.cart_to_zmat(xall, zi.refs)
    with open(argv[2], "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
