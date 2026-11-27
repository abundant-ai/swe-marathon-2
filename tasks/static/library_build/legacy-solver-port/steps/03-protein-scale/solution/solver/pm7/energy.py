"""Single-geometry evaluation (port of COMPFG): energy, charges, IP and dipole."""

from dataclasses import dataclass

import numpy as np

from . import corrections
from .constants import A0, FPC_1, FPC_8, FPC_9, MASS
from .hamiltonian import Hamiltonian, build_hamiltonian
from .params import ELEMENTS
from .scf import ScfState, ScfResult, run_scf
from .system import Electrons, connectivity


@dataclass
class Evaluation:
    coords: np.ndarray
    heat: float  # kcal/mol
    scf: ScfResult
    ham: Hamiltonian
    atheat: float
    corrections: dict
    charges: np.ndarray
    ip: float
    dipole: float


def base_atheat(z):
    return (
        sum(ELEMENTS[zz].eheat for zz in z)
        - sum(ELEMENTS[zz].eisol for zz in z) * FPC_9
    )


def atomic_charges(p, el):
    q = np.zeros(len(el.z))
    for i, zz in enumerate(el.z):
        a, b = el.offsets[i], el.offsets[i + 1]
        q[i] = ELEMENTS[zz].tore - float(np.sum(np.diag(p)[a:b]))
    return q


def dipole_moment(p, coords, el, q):
    """Port of DIPOLE (point-charge + sp/pd hybridisation terms), Debye."""
    z = el.z
    n = len(z)
    coords = np.array(coords, float)
    chargd = abs(float(np.sum(q))) > 0.5
    if chargd:
        mass = np.array([MASS[zz] for zz in z])
        center = (mass[:, None] * coords).sum(axis=0) / mass.sum()
        coords = coords - center
    dip_h = np.zeros(3)
    dip_p = np.zeros(3)
    factdm = FPC_8 * FPC_1 * 1.0e-10
    for i in range(n):
        ei = ELEMENTS[z[i]]
        ia = el.offsets[i]
        nor = ei.natorb
        if nor > 1:
            hyfsp = 2.0 * ei.dd * A0 * FPC_8 * FPC_1 * 1.0e-10
            for j in range(3):
                dip_h[j] -= hyfsp * p[ia + 1 + j, ia]
            if nor == 9:
                xt = 1.0 / np.sqrt(3.0)
                hyfpd = 2.0 * ei.ddp[5] * A0 * FPC_8 * FPC_1 * 1.0e-10
                P = lambda a, b: p[
                    ia + a, ia + b
                ]  # orbital offsets within the atom (row, col)
                dx = P(5, 3) + P(4, 1) + P(8, 2) - xt * P(6, 1)
                dy = P(7, 3) - P(4, 2) + P(8, 1) - xt * P(6, 2)
                dz = P(5, 1) + P(7, 2) + 2.0 * xt * P(6, 3)
                dip_h[0] -= dx * hyfpd
                dip_h[1] -= dy * hyfpd
                dip_h[2] -= dz * hyfpd
        dip_p += q[i] * coords[i] * factdm
    tot = dip_h + dip_p
    return float(np.sqrt(np.sum(tot**2)))


def ionization_potential(res, el):
    if el.uhf:
        eig_min = -res.eigs[el.nalpha - 1]
        if el.nbeta > 0:
            eig_min = min(eig_min, -res.eigb[el.nbeta - 1])
        return float(eig_min)
    eig_min = -res.eigs[el.nopen - 1]
    eig_min = min(eig_min, -res.eigs[el.nclose - 1])
    return float(eig_min)


def evaluate(
    job_z,
    coords,
    el,
    state=None,
    gnorm=0.0,
    precise=False,
    last=True,
    scfcrt=None,
    limscf=False,
    force=False,
):
    coords = np.asarray(coords, float)
    ham = build_hamiltonian(job_z, coords, el.offsets)
    corr = corrections.correction_energy(job_z, coords)
    atheat = base_atheat(job_z) + corr["total"]
    if state is None:
        state = ScfState()
    res = run_scf(
        ham,
        el,
        atheat,
        st=state,
        gnorm=gnorm,
        precise=precise,
        last=last,
        scfcrt=scfcrt,
        limscf=limscf,
        force=force,
    )
    heat = (res.ee + ham.enuclr) * FPC_9 + atheat
    q = atomic_charges(res.p, el)
    ip = ionization_potential(res, el)
    dip = dipole_moment(res.p, coords, el, q)
    return Evaluation(
        coords=coords,
        heat=heat,
        scf=res,
        ham=ham,
        atheat=atheat,
        corrections=corr,
        charges=q,
        ip=ip,
        dipole=dip,
    )
