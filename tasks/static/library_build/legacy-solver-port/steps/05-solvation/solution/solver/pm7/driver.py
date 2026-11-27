"""High-level jobs: single point and geometry optimisation, producing the AUX-style results."""

import numpy as np

from . import gradient
from .constants import MASS
from .energy import evaluate
from .optimize import ef_minimize
from .scf import ScfState
from .system import Electrons, Job


def single_point_cosmo(job: Job):
    """1SCF with the COSMO solvent (EPS=)."""
    from .cosmo import get_params
    from .energy import evaluate_cosmo

    z = job.z
    el = Electrons(z, job.charge, job.uhf, job.msdel)
    kw = {}
    if job.rsolv is not None:
        kw["rsolv"] = job.rsolv
    if job.nspa is not None:
        kw["nspa"] = job.nspa
    if job.disex is not None:
        kw["disex"] = job.disex
    cp = get_params(job.eps, **kw)
    ev = evaluate_cosmo(z, job.coords, el, cp, precise=job.precise)
    return {
        "heat_of_formation": ev.heat,
        "atom_charges": ev.charges.tolist(),
        "ionization_potential": ev.ip,
        "dipole": ev.dipole,
        "area": ev.cosmo.cav.area,
        "volume": ev.cosmo.cav.volume,
    }


def single_point(job: Job):
    if job.eps is not None:
        return single_point_cosmo(job)
    z = job.z
    el = Electrons(z, job.charge, job.uhf, job.msdel)
    ev = evaluate(
        z, job.coords, el, state=ScfState(), gnorm=0.0, precise=job.precise, last=True
    )
    out = {
        "heat_of_formation": ev.heat,
        "atom_charges": ev.charges.tolist(),
        "ionization_potential": ev.ip,
        "dipole": ev.dipole,
    }
    if job.grad:
        g = gradient.cartesian_gradient(z, job.coords, el, ev.scf, job.precise)
        out["gradients"] = g.ravel()[job.flags.ravel() == 1].tolist()
    return out


def optimise(job: Job):
    z = job.z
    el = Electrons(z, job.charge, job.uhf, job.msdel)
    state = ScfState()
    masses = np.array([MASS[zz] for zz in z])
    n = len(z)
    free = job.flags.ravel() == 1
    xfull = job.coords.ravel().copy()

    def fun(xf, last, want_grad, gnorm):
        x = xfull.copy()
        x[free] = xf
        coords = x.reshape(n, 3)
        ev = evaluate(
            z,
            coords,
            el,
            state=state,
            gnorm=gnorm,
            precise=job.precise,
            last=last,
            limscf=True,
        )
        g = None
        if want_grad:
            g = gradient.cartesian_gradient(z, coords, el, ev.scf, job.precise).ravel()[
                free
            ]
        return ev.heat, g

    xf, info = ef_minimize(fun, xfull[free], masses, tol2=job.gnorm_limit)
    x = xfull.copy()
    x[free] = xf
    # final SCF at the optimised geometry (last = 1)
    ev = evaluate(
        z,
        x.reshape(n, 3),
        el,
        state=state,
        gnorm=0.0,
        precise=job.precise,
        last=True,
        limscf=True,
    )
    out = {
        "heat_of_formation": ev.heat,
        "atom_charges": ev.charges.tolist(),
        "ionization_potential": ev.ip,
        "dipole": ev.dipole,
        "optimized_geometry": x.tolist(),
    }
    return out, info


def run_job(job: Job):
    if job.force:
        from .force import force_job

        return force_job(job)
    if job.one_scf:
        return single_point(job)
    out, _ = optimise(job)
    return out
