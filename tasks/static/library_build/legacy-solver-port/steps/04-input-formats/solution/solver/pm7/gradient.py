"""Cartesian energy gradient (port of DERIV/DCART/DHC).

MOPAC does not differentiate the integrals analytically: for every atom pair it evaluates the
pair energy (one-electron + two-center two-electron + core-core terms, with the *final* density
of the SCF held fixed) at displaced geometries.  Without PRECISE this is a forward difference
(step 1e-4 A, with the partner atom shifted by 5e-5 A along x, y and z); with PRECISE a central
difference.  The truncation error of the forward difference is part of the reference numbers, so
the same stencil is used here.
"""

import numpy as np

from . import corrections
from .constants import FPC_9
from .overlap import h1elec
from .params import ELEMENTS
from .twocenter import pair_integrals

CHNGE = 1.0e-4
CHNGE2 = CHNGE * 0.5


def pair_energy(zi, zj, xi, xj, pt, pa, pb, uhf):
    """dhc: energy (eV) of the pair (i,j) for fixed density blocks.

    pt/pa/pb are dicts with blocks 'ii','jj','ij' (i = first atom).  Returns ee + enuc."""
    W, Vi, Vj, enuc = pair_integrals(zi, zj, xi, xj)
    Hres = h1elec(zi, zj, xi, xj)
    jii = np.einsum("mnls,ls->mn", W, pt["jj"])
    jjj = np.einsum("mnls,mn->ls", W, pt["ii"])

    def spin_energy(p):
        k = np.einsum("mnls,ns->ml", W, p["ij"])
        e = 0.0
        e += np.sum(p["ii"] * (Vi + Vi + jii))
        e += np.sum(p["jj"] * (Vj + Vj + jjj))
        e += 2.0 * np.sum(p["ij"] * (Hres + Hres - k))
        return 0.5 * e

    if uhf:
        ee = spin_energy(pa) + spin_energy(pb)
    else:
        ee = 2.0 * spin_energy(pa)
    return ee + enuc


def _blocks(p, offs, i, j, na, nb):
    ia, ja = offs[i], offs[j]
    return {
        "ii": p[ia : ia + na, ia : ia + na],
        "jj": p[ja : ja + nb, ja : ja + nb],
        "ij": p[ia : ia + na, ja : ja + nb],
    }


def cartesian_gradient(z, coords, el, scf, precise):
    """Gradient (kcal/mol/Angstrom) including all corrections.  Shape (n,3)."""
    n = len(z)
    coords = np.asarray(coords, float)
    dxyz = np.zeros((n, 3))
    p, pa, pb = scf.p, scf.pa, scf.pb
    offs = el.offsets
    for ii in range(n):
        ei = ELEMENTS[z[ii]]
        for jj in range(ii):
            ej = ELEMENTS[z[jj]]
            # first atom of dhc is jj, second is ii; energies are symmetric, we put ii first
            bt = _blocks(p, offs, ii, jj, ei.natorb, ej.natorb)
            ba = _blocks(pa, offs, ii, jj, ei.natorb, ej.natorb)
            bb = _blocks(pb, offs, ii, jj, ei.natorb, ej.natorb)
            xi0 = coords[ii].copy()
            xj0 = coords[jj].copy()
            if not precise:
                xjs = xj0 + CHNGE2
                aa = pair_energy(z[ii], z[jj], xi0, xjs, bt, ba, bb, el.uhf)
                for k in range(3):
                    xi = xi0.copy()
                    xi[k] += CHNGE
                    ee = pair_energy(z[ii], z[jj], xi, xjs, bt, ba, bb, el.uhf)
                    deriv = (aa - ee) * FPC_9 / CHNGE
                    dxyz[ii, k] -= deriv
                    dxyz[jj, k] += deriv
            else:
                for k in range(3):
                    xi = xi0.copy()
                    xi[k] -= CHNGE2
                    aa = pair_energy(z[ii], z[jj], xi, xj0, bt, ba, bb, el.uhf)
                    xi = xi0.copy()
                    xi[k] += CHNGE2
                    ee = pair_energy(z[ii], z[jj], xi, xj0, bt, ba, bb, el.uhf)
                    deriv = (aa - ee) * FPC_9 / CHNGE
                    dxyz[ii, k] -= deriv
                    dxyz[jj, k] += deriv
    dxyz += corrections.correction_gradient(z, coords)
    return dxyz
