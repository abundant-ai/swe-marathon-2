"""SCF driver: a line-by-line port of MOPAC's ITER (shift/damping/convergence logic included).

MOPAC's reference numbers (charges, IP, dipole, gradients) are taken from the density it
holds when its own convergence test passes, so the loop has to be reproduced, not just the
fixed point.  Pulay/Camp-King/pseudo-diagonalisation are not used by default and are not
ported; every iteration does a full diagonalisation, exactly like MOPAC's default path.

State carried between calls is explicit in ``ScfState`` (densities, previous densities used
by the extrapolator, level-shift variables, eigenvalues).
"""

import math
from dataclasses import dataclass, field

import numpy as np

from .constants import FPC_9


@dataclass
class ScfState:
    """Variables that MOPAC keeps with SAVE between successive ITER calls."""

    first: bool = True
    p: np.ndarray = None
    pa: np.ndarray = None
    pb: np.ndarray = None
    pold: np.ndarray = None
    pold2: np.ndarray = None
    pbold: np.ndarray = None
    pbold2: np.ndarray = None
    eigs: np.ndarray = None
    eigb: np.ndarray = None
    c: np.ndarray = None
    cb: np.ndarray = None
    ten: float = -80.0
    tenold: float = 10.0
    shift: float = 1.0
    shiftb: float = 0.0
    shfmax: float = 20.0
    shfto: float = 0.0
    shftbo: float = 0.0
    bshift: float = -80.0
    newdg: bool = False
    oknewd: bool = False
    pl: float = 1.0
    plb: float = 0.0
    trans: float = 0.2
    plchek: float = 0.005
    nscf: int = 0
    emin: float = 0.0
    irrr: int = 5


@dataclass
class ScfResult:
    ee: float  # electronic energy (eV)
    escf_loop: float
    p: np.ndarray
    pa: np.ndarray
    pb: np.ndarray
    eigs: np.ndarray
    eigb: np.ndarray
    c: np.ndarray
    cb: np.ndarray
    niter: int
    pl: float


def _diag(f):
    """eigenvectors_LAPACK: diagonal perturbed by i*1e-10 (i = 1..n) before diagonalisation."""
    n = f.shape[0]
    a = f.copy()
    a[np.diag_indices(n)] += np.arange(1, n + 1) * 1.0e-10
    e, c = np.linalg.eigh(a)
    return e, c


def _helect(p, h, f):
    return 0.5 * float(np.sum(p * (h + f)))


def _cnvg(pnew, p, p1, niter, rhfuhf):
    """MOPAC CNVG on full symmetric matrices.  Returns pl; modifies pnew, p (=pold), p1 in place."""
    n = pnew.shape[0]
    pl = 0.0
    faca = 0.0
    damp = 1.0e10
    if niter > 3:
        damp = 0.05
    facb = 0.0
    fac = 0.0
    extrap = (niter % 3) != 0
    sum1 = 0.0
    dg = np.arange(n)
    a = pnew[dg, dg].copy()
    sum1 = float(np.sum(a))
    sa = np.abs(a - p[dg, dg])
    pl = float(sa.max()) if n else 0.0
    if not extrap:
        faca = float(np.sum(sa**2))
        facb = float(np.sum((a - 2.0 * p[dg, dg] + p1) ** 2))
    p1[:] = p[dg, dg]
    p[dg, dg] = a
    if facb > 1.0e-10 and faca < (100.0 * facb):
        fac = math.sqrt(faca / facb)
    # off-diagonals: p(ie) = a + fac*(a - p(ie))   (p(ie) is the OLD density element)
    iu = np.tril_indices(n, -1)
    anew = pnew[iu]
    pold_off = p[iu]
    pext = anew + fac * (anew - pold_off)
    p[iu] = pext
    p[(iu[1], iu[0])] = pext
    pnew[iu] = pext
    pnew[(iu[1], iu[0])] = pext
    # diagonal
    sum2 = 0.0
    for i in range(n):
        v = p[i, i]
        if abs(v - p1[i]) > damp:
            v = p1[i] + math.copysign(damp, v - p1[i])
        else:
            v = v + fac * (v - p1[i])
        v = min(rhfuhf, max(v, 0.0))
        sum2 += v
        p[i, i] = v
        pnew[i, i] = v
    sum0 = sum1
    while True:
        if sum2 > 1.0e-3:
            s = sum1 / sum2
        else:
            s = 0.0
        sum1 = sum0
        if sum2 < 1.0e-3 or abs(s - 1.0) < 1.0e-5:
            break
        sum2 = 0.0
        for i in range(n):
            v = p[i, i] * s + 1.0e-20
            v = max(v, 0.0)
            if v > rhfuhf:
                v = rhfuhf
                sum1 -= rhfuhf
            else:
                sum2 += v
            p[i, i] = v
            pnew[i, i] = v
    return pl


def _density(c, nocc, occ):
    cc = c[:, :nocc]
    return occ * (cc @ cc.T)


def run_scf(
    ham,
    el,
    atheat,
    st=None,
    gnorm=0.0,
    precise=False,
    last=True,
    scfcrt=None,
    itrmax=2000,
    full_exit_diag=True,
    limscf=False,
    force=False,
    fock_hook=None,
):
    """One call of ITER.  ``atheat`` is MOPAC's atheat (kcal/mol) at the time of the call;
    it only enters through energy differences.  Returns ScfResult; ``st`` is updated."""
    n = el.norbs
    h = ham.h
    enuclr = ham.enuclr
    uhf = el.uhf
    nclose, nopen, nalpha, nbeta = el.nclose, el.nopen, el.nalpha, el.nbeta
    ihomo = max(1, nclose + nalpha)
    ihomob = max(1, nclose + nbeta)
    na2el = nclose
    na1el = nalpha + nopen
    nb1el = nbeta + nopen
    if st is None:
        st = ScfState()
    enrgy = FPC_9
    eold = 1.0e2
    ready = False
    diff = 0.0
    glow = False
    if st.first:
        st.first = False
        st.irrr = 5
        st.shift = 1.0
        st.shfmax = 20.0
        st.bshift = -80.0
        st.ten = st.bshift
        st.tenold = 10.0
        st.newdg = False
        st.pl = 1.0
        st.plb = 0.0
        st.shfto = 0.0
        st.shftbo = 0.0
        st.trans = 0.2
        st.plchek = 0.005
        st.p = np.zeros((n, n))
        st.pa = np.zeros((n, n))
        st.pb = np.zeros((n, n))
        w1 = na1el / (na1el + 1.0e-6 + nb1el)
        w2 = 1.0 - w1
        if w1 < 1.0e-6:
            w1 = 0.5
        if w2 < 1.0e-6:
            w2 = 0.5
        random = 1.0
        glow = gnorm < 2.0 and gnorm > 1.0e-9
        if (not glow) and uhf and na1el == nb1el:
            random = 1.1
        for i in range(n):
            pd = el.pdiag[i]
            st.p[i, i] = pd
            st.pa[i, i] = pd * w1 * random
            random = 1.0 / random
            st.pb[i, i] = pd * w2 * random
        if uhf:
            for i in range(n):
                random = 1.0 / random
                st.pb[i, i] = el.pdiag[i] * w2 * random
        st.pold = st.pa.copy()
        if uhf:
            st.pbold = st.pb.copy()
        st.pold2 = np.diag(st.pold).copy()
        st.pbold2 = np.diag(st.pbold).copy() if uhf else np.zeros(n)
        st.eigs = np.zeros(n)
        st.eigb = np.zeros(n)
        st.c = np.zeros((n, n))
        st.cb = np.zeros((n, n))
        scf_crt = 1.0e-4
        if force:
            scf_crt = scf_crt * 0.001
        elif precise or nopen != nclose:
            scf_crt = scf_crt * 0.01
        scf_crt = max(scf_crt, 1.0e-12)
        st._scfcrt = scf_crt
        st.nscf = 0
    else:
        if st.nscf > 0 and not uhf:
            st.pb = st.pa.copy()
            st.p = 2.0 * st.pa
    if scfcrt is not None:
        st._scfcrt = scfcrt
    scfcrt = st._scfcrt
    if st.irrr != 5:
        if uhf:
            st.pold = st.pa.copy()
            st.pbold = st.pb.copy()
            st.pold2 = np.diag(st.pa).copy()
            st.pbold2 = np.diag(st.pb).copy()
        else:
            st.pold = st.p.copy()
            st.pold2 = np.diag(st.p).copy()
    # (TURN OFF SHIFT IF NOT A FULL SCF: always full here)
    if st.newdg:
        st.newdg = abs(st.bshift) < 0.001
    if last:
        st.newdg = False
    gs = not force
    selcon = scfcrt
    if gs:
        selcon = min(min(scfcrt * 100.0, 0.1), max(scfcrt * gnorm**3, scfcrt))
    pltest = 0.05 * math.sqrt(abs(selcon))
    if nalpha != nbeta and uhf:
        pltest = 0.001
    iredy = 1
    niter = 0
    p, pa, pb = st.p, st.pa, st.pb
    pold, pold2, pbold, pbold2 = st.pold, st.pold2, st.pbold, st.pbold2
    eigs, eigb, c, cb = st.eigs, st.eigb, st.c, st.cb
    shift, shiftb, ten, tenold, shfmax = (
        st.shift,
        st.shiftb,
        st.ten,
        st.tenold,
        st.shfmax,
    )
    bshift = st.bshift
    newdg, oknewd = st.newdg, st.oknewd
    pl, plb = st.pl, st.plb
    shfto, shftbo = st.shfto, st.shftbo
    trans, plchek = st.trans, st.plchek
    rhfuhf = 1.0 if uhf else 2.0
    iu = np.triu_indices(n)
    packed_index = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1):
            packed_index[i, j] = packed_index[j, i] = (i + 1) * i // 2 + j + 1
    eye = np.eye(n)
    rebuild = False
    ee = 0.0
    escf = 0.0
    scorr = 0.0
    iemin = 0
    iemax = 0
    escf0 = [0.0] * 6  # 1-based
    emin = st.emin
    while True:
        if not rebuild:
            niter += 1
            if niter > itrmax:
                break
            # ---- Fock matrix (one-electron part, with level shift)
            if abs(shift) > 1.0e-10 and bshift != 0.0:
                if niter > 1:
                    if newdg:
                        if diff > 0.0:
                            shift = 1.0
                            if diff > 1:
                                newdg = False
                        else:
                            shift = -0.1
                    else:
                        if ihomo < n:
                            shift = ten + eigs[ihomo] - eigs[ihomo - 1] + shift
                        else:
                            shift = 0.0
                    if diff > 0.0:
                        if shift > 4.0:
                            shfmax = 4.5
                        if shift > shfmax:
                            shfmax = max(shfmax - 0.5, 0.0)
                    shift = max(-20.0, min(shfmax, shift))
                    if abs(shift - shfmax) < 1.0e-5:
                        shfmax = shfmax + 0.01
                    if uhf:
                        if newdg:
                            shiftb = ten - tenold
                        else:
                            shiftb = ten + eigb[ihomob] - eigb[ihomob - 1] + shiftb
                        if diff > 0.0:
                            shiftb = min(4.0, shiftb)
                        shiftb = max(-20.0, min(shfmax, shiftb))
                        eigb[ihomob:] = eigb[ihomob:] + shiftb
                tenold = ten
                if pl > plchek:
                    shftbo = shiftb
                    shfto = shift
                else:
                    shiftb = shftbo
                    shift = shfto
                eigs[ihomo:] = eigs[ihomo:] + shift
                f0 = h + shift * pa + 1.0e-16 * packed_index
                f0 = f0 - shift * eye
            elif niter < 2 and not last:
                f0 = (
                    h.copy()
                )  # (random perturbation of the first Fock matrix, not reached)
            else:
                f0 = h.copy()
        else:
            f0 = h.copy()
            shift = 0.0
            shiftb = 0.0
        # ---- two-electron part
        jm = ham.coulomb(p)
        fa = f0 + (jm - ham.exchange(pa))
        if (
            fock_hook is not None
        ):  # COSMO: screening-charge term (ADDFCK), total density
            gsol = fock_hook(p)
            fa = fa + gsol
        if uhf:
            if shiftb != 0.0:
                fb0 = h + shiftb * pb
                fb0 = fb0 - shiftb * eye
            else:
                fb0 = h.copy()
            fb = fb0 + (jm - ham.exchange(pb))
            if fock_hook is not None:
                fb = fb + gsol
        # ---- energy
        ee = _helect(pa, h, fa)
        if uhf:
            ee = ee + _helect(pb, h, fb)
        else:
            ee = ee * 2.0
        scorr = 0.0
        escf = (ee + enuclr) * enrgy + atheat + scorr
        rebuild = False
        diff = escf - eold
        if diff > 0:
            ten = ten - 1.0
        else:
            ten = ten * 0.975 + 0.05
        sellim = max(selcon, 1.0e-15 * max(abs(ee), 1.0))
        converged = (
            niter > 4 and (pl == 0.0 or (pl < pltest and abs(diff) < sellim)) and ready
        )
        if converged:
            if abs(shift) < 1.0e-10:
                break
            shift = 0.0
            shiftb = 0.0
            rebuild = True
            continue
        # ---- limscf: fast exit when the energy is consistently below/above the best so far
        if limscf and emin != 0.0:
            exit_now = False
            if escf < emin:
                iemax = 0
                iemin = min(5, iemin + 1)
                for k in range(1, iemin):
                    escf0[k] = escf0[k + 1]
                escf0[iemin] = escf
                if iemin > 3:
                    ok = True
                    for k in range(2, iemin + 1):
                        if abs(escf0[k] - escf0[k - 1]) > 0.05 * (emin - escf):
                            ok = False
                            break
                    exit_now = ok
            else:
                iemin = 0
                iemax = min(5, iemax + 1)
                for k in range(1, iemax):
                    escf0[k] = escf0[k + 1]
                escf0[iemax] = escf
                if iemax > 3:
                    ok = True
                    for k in range(2, iemax + 1):
                        if abs(escf0[k] - escf0[k - 1]) > 0.05 * (escf - emin):
                            ok = False
                            break
                    exit_now = ok
            if exit_now:
                if abs(shift) < 1.0e-10:
                    break
                shift = 0.0
                shiftb = 0.0
                rebuild = True
                continue
        ready = iredy > 0 and (abs(diff) < sellim * 10.0 or pl == 0.0)
        iredy += 1
        eold = escf
        # ---- diagonalise, new density
        eigs, c = _diag(fa)
        pnew = _density(c, na2el if not uhf else nalpha, 2.0 if not uhf else 1.0)
        if not uhf:
            pl = _cnvg(pnew, pold, pold2, niter, rhfuhf)
            p = pnew
        else:
            pl = _cnvg(pnew, pold, pold2, niter, rhfuhf)
            pa = pnew
            eigb, cb = _diag(fb)
            pnb = _density(cb, nbeta, 1.0)
            plb = _cnvg(pnb, pbold, pbold2, niter, rhfuhf)
            pb = pnb
            p = pa + pb
        if not uhf:
            pa = p * 0.5
            pb = pa.copy()
        oknewd = pl < sellim or oknewd
        newdg = (pl < trans and oknewd) or newdg
        if pl < trans * 0.3333:
            oknewd = True
    # ---- converged: final energy from the last (unshifted) Fock matrix
    ee = _helect(pa, h, fa)
    if uhf:
        ee = ee + _helect(pb, h, fb)
    else:
        ee = ee * 2.0
    if full_exit_diag and (st.nscf == 0 or last):
        eigs, c = _diag(fa)
        if uhf:
            eigb, cb = _diag(fb)
    st.nscf += 1
    shift = 1.0
    escf = (ee + enuclr) * enrgy + atheat
    st.p, st.pa, st.pb = p, pa, pb
    st.pold, st.pold2, st.pbold, st.pbold2 = pold, pold2, pbold, pbold2
    st.eigs, st.eigb, st.c, st.cb = eigs, eigb, c, cb
    st.shift, st.shiftb, st.ten, st.tenold, st.shfmax = (
        shift,
        shiftb,
        ten,
        tenold,
        shfmax,
    )
    st.newdg, st.oknewd = newdg, oknewd
    st.pl, st.plb = pl, plb
    st.shfto, st.shftbo = shfto, shftbo
    st.irrr = 2
    if st.emin == 0.0:
        st.emin = escf
    else:
        st.emin = min(st.emin, escf)
    return ScfResult(
        ee=ee,
        escf_loop=escf,
        p=p,
        pa=pa,
        pb=pb,
        eigs=eigs,
        eigb=eigb,
        c=c,
        cb=cb,
        niter=niter,
        pl=pl,
    )
