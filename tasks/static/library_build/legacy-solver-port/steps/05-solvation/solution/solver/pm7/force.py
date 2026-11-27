"""FORCE job: port of FORCE / FMAT / FREQCY of MOPAC (PRECISE Hessian from analytic-style gradients)."""

import math

import numpy as np

from . import gradient
from .constants import FPC_9, MASS, PI
from .energy import evaluate
from .scf import ScfState
from .system import Electrons, connectivity
from .sym import point_group_ops, build_group

SCFCRT = None
FPC_6 = 6.62607015e-27  # Planck, erg s
FPC_8 = 2.99792458e10  # c, cm/s
FPC_10 = 6.02214076e23  # Avogadro


def _axis(coord, mass):
    """AXIS: centred coordinates, principal-axes matrix and the smallest moment."""
    wsum = mass.sum()
    cm = (mass[:, None] * coord).sum(axis=0) / wsum
    xyz = coord - cm
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    t = np.array([1, 2, 3, 4, 5, 6], float) * 1.0e-10
    t[0] += np.sum(mass * (y * y + z * z))
    t[1] -= np.sum(mass * x * y)
    t[2] += np.sum(mass * (z * z + x * x))
    t[3] -= np.sum(mass * z * x)
    t[4] -= np.sum(mass * y * z)
    t[5] += np.sum(mass * (x * x + y * y))
    m = np.array([[t[0], t[1], t[3]], [t[1], t[2], t[4]], [t[3], t[4], t[5]]])
    eig, evec = np.linalg.eigh(m)
    for i in range(3):
        if evec[i, i] < 0.0:
            evec[:, i] = -evec[:, i]
    det = np.linalg.det(evec)
    if det < 0:
        s = 1.0
        idx = 0
        for j in range(3):
            if evec[j, j] < s:
                s = evec[j, j]
                idx = j
        evec[:, idx] = -evec[:, idx]
    return xyz, evec, eig


def _frame(fm, xyz, mass, rot, n_trivial):
    """FRAME mode 1: add 40000+100 i to the translations/rotations (fm is a full symmetric matrix)."""
    n = len(mass)
    n3 = 3 * n
    coord1 = xyz @ rot
    vib = np.zeros((6, n3))
    for i in range(n):
        w = math.sqrt(mass[i])
        j = 3 * i
        vib[0, j] = w
        vib[1, j + 1] = w
        vib[2, j + 2] = w
        vib[4, j] = coord1[i, 2] * w
        vib[5, j] = coord1[i, 1] * w
        vib[3, j + 1] = coord1[i, 2] * w
        vib[5, j + 1] = -coord1[i, 0] * w
        vib[3, j + 2] = -coord1[i, 1] * w
        vib[4, j + 2] = -coord1[i, 0] * w
    for i in range(n):
        j = 3 * i
        for k in range(3, 6):
            v = vib[k, j : j + 3].copy()
            vib[k, j : j + 3] = rot @ v
    sums = np.sum(vib**2, axis=1)
    if n_trivial == 5:
        thr = 0.01 + sums.min()
        for i in range(6):
            if sums[i] > thr:
                sums[i] = math.sqrt(1.0 / sums[i])
    else:
        sums = np.sqrt(1.0 / sums)
    shift = np.array([40000.0 + 100.0 * (i + 1) for i in range(6)])
    vib = vib * sums[:, None]
    return fm + (vib.T * shift) @ vib


def _block(hm, k, l):
    """3x3 block (rows: coordinates of atom k, columns: atom l) of the lower-triangle matrix hm (1-based)."""
    out = np.empty((3, 3))
    for a in range(3):
        for b in range(3):
            p = 3 * k + a + 1
            q = 3 * l + b + 1
            out[a, b] = hm[p, q] if p >= q else hm[q, p]
    return out


def _symh(hm, i, n, mats, ipo, numat):
    """port of SYMH: rows of atom i from those of its image k = ipo(i,n) < i."""
    A = mats[n]
    k = ipo[n][i]
    for j in range(numat - 1, i, -1):
        l = ipo[n][j]
        B = _block(hm, k, l)
        if k > l:
            fact = 0.5
        else:
            fact = 0.5 if l < i else 1.0
        T2 = A.T @ (fact * B) @ A
        for a in range(3):
            for b in range(3):
                hm[3 * j + a + 1, 3 * i + b + 1] = T2[b, a]
    B = 0.5 * _block(hm, k, k)
    T2 = A.T @ B @ A
    for a in range(3):
        for b in range(a + 1):
            hm[3 * i + a + 1, 3 * i + b + 1] = T2[a, b]
    for p in range(3 * i + 1, 3 * i + 4):
        hm[p, 1 : p + 1] *= 2.0


def _symt(hm, nvar, mats, ipo):
    nsym = len(mats)
    if nsym < 2:
        return hm
    numat = nvar // 3
    ha = np.zeros_like(hm)
    for n in range(nsym):
        A = mats[n]
        for i in range(numat):
            for j in range(i):
                k = ipo[n][i]
                l = ipo[n][j]
                T2 = A.T @ _block(hm, k, l) @ A
                for a in range(3):
                    for b in range(3):
                        ha[3 * i + a + 1, 3 * j + b + 1] += T2[a, b]
            k = ipo[n][i]
            T2 = A.T @ _block(hm, k, k) @ A
            for a in range(3):
                for b in range(a + 1):
                    ha[3 * i + a + 1, 3 * i + b + 1] += T2[a, b]
    return ha / nsym


def hessian(z, coords, el, state, gnorm, precise, sym=None):
    """FMAT.  Returns the lower-triangle Hessian (1-based (nvar+1)^2 array), in mdyn/A."""
    n = len(z)
    nvar = 3 * n
    fact = 4.184 / FPC_10 * 1.0e21
    x0 = np.array(coords, float).ravel()
    hm = np.zeros((nvar + 1, nvar + 1))

    def grad_at(x):
        ev = evaluate(
            z,
            x.reshape(n, 3),
            el,
            state=state,
            gnorm=gnorm,
            precise=precise,
            last=True,
            scfcrt=SCFCRT,
            force=True,
        )
        return gradient.cartesian_gradient(
            z, x.reshape(n, 3), el, ev.scf, precise
        ).ravel()

    iskip = 0
    for i in range(1, nvar + 1):
        if (i - 1) % 3 == 0:
            atom = (i - 1) // 3
            iskip = 0
            if sym is not None:
                mats, ipo = sym
                for jop in range(len(mats)):
                    if ipo[jop][atom] >= atom:
                        continue
                    _symh(hm, atom, jop, mats, ipo, n)
                    iskip = 3
                    break
        if iskip > 0:
            iskip -= 1
            continue
        ic = i - 1
        delta = 1.0 / 120.0
        if precise:
            x = x0.copy()
            x[ic] += delta
            g = grad_at(x)
            delta = delta * 10.0 / math.sqrt(float(g @ g))
            delta = min(0.05, max(0.005, delta))
            x = x0.copy()
            x[ic] += delta
            g2old = grad_at(x)
            x = x0.copy()
            x[ic] -= delta
            g2rad = grad_at(x)
        x = x0.copy()
        x[ic] += 0.5 * delta
        grold = grad_at(x)
        x = x0.copy()
        x[ic] -= 0.5 * delta
        grad = grad_at(x)
        if precise:
            dumy = (8.0 * (grold - grad) - (g2old - g2rad)) / delta * fact / 12.0
        else:
            dumy = (grold - grad) * 0.5 / delta * fact
        for q in range(1, i + 1):
            hm[i, q] += dumy[q - 1]
        for k in range(i, nvar + 1):
            hm[k, i] += dumy[k - 1]
    return hm


def mopac_frame(coords):
    """Cartesian -> internal -> Cartesian (XYZINT/GMETRY) amounts to: atom 1 at the origin, atom 2 on +x,
    atom 3 in the xy plane with y >= 0."""
    c = np.array(coords, float)
    n = len(c)
    if n < 2:
        return c
    v = c - c[0]
    ex = v[1] / np.linalg.norm(v[1])
    if n == 2:
        ey = np.cross(ex, np.array([0.0, 0.0, 1.0]))
        if np.linalg.norm(ey) < 1e-6:
            ey = np.cross(ex, np.array([0.0, 1.0, 0.0]))
    else:
        w = v[2] - (v[2] @ ex) * ex
        ey = w
        if np.linalg.norm(w) < 1e-9:
            # collinear start: use the first atom with a perpendicular displacement
            ey = None
            for k in range(3, n):
                w = v[k] - (v[k] @ ex) * ex
                if np.linalg.norm(w) > 1e-9:
                    ey = w
                    break
            if ey is None:
                ey = np.cross(ex, np.array([0.0, 0.0, 1.0]))
                if np.linalg.norm(ey) < 1e-6:
                    ey = np.cross(ex, np.array([0.0, 1.0, 0.0]))
    ey = ey / np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    return v @ np.array([ex, ey, ez]).T


def force_job(job):
    z = job.z
    n = len(z)
    el = Electrons(z, job.charge, job.uhf, job.msdel)
    coords = mopac_frame(job.coords)
    state = ScfState()
    ev = evaluate(
        z,
        coords,
        el,
        state=state,
        gnorm=0.0,
        precise=job.precise,
        last=True,
        force=True,
    )
    heat = ev.heat
    ev = evaluate(
        z,
        coords,
        el,
        state=state,
        gnorm=0.0,
        precise=job.precise,
        last=True,
        force=True,
    )  # 2nd COMPFG (with gradient)
    g0 = gradient.cartesian_gradient(z, coords, el, ev.scf, job.precise)
    gnorm = float(np.sqrt(np.sum(g0**2)))
    mass = np.array([MASS[zz] for zz in z])
    nvar = 3 * n

    xyz, rot, eig = _axis(coords, mass)
    nvib = nvar - 6
    linear = eig[0] < 3.0e-4
    if linear:
        nvib += 1
    n_trivial = nvar - nvib

    sym = None
    if not job.nosym:
        try:
            nb, ib = connectivity(z, coords)
            ops, st = point_group_ops(
                coords - (mass[:, None] * coords).sum(axis=0) / mass.sum(),
                z,
                mass,
                nb,
                ib,
            )
            sym = build_group(
                coords - coords.mean(axis=0), ops
            )  # None: MOPAC stops with "PROBLEM IN SYMR"
        except Exception:
            sym = None
    hm = hessian(z, coords, el, state, gnorm, job.precise, sym=sym)
    for loop in range(20):
        sumerr = 0.0
        for i in range(1, nvar + 1):
            s = 0.0
            for j in range(1, i):
                s += hm[i, j]
            for j in range(i + 1, nvar + 1):
                s += hm[j, i]
            err = hm[i, i] + s
            sumerr += abs(err)
            hm[i, i] = -s - err * 0.5
        if sym is not None:
            hm = _symt(hm, nvar, sym[0], sym[1])
        if sumerr < 1.0e-6:
            break
    hl = hm[1:, 1:]
    fm = np.tril(hl) + np.tril(hl, -1).T
    oldf = fm.copy()
    w = np.repeat(1.0 / np.sqrt(mass), 3)
    fm = fm * w[:, None] * w[None, :]
    fm = _frame(fm, xyz, mass, rot, n_trivial)
    ev_ = np.linalg.eigvalsh(fm)
    freq = ev_.copy()
    for i in range(nvar):
        j = int((freq[i] + 50.0) * 0.01)
        freq[i] = freq[i] - j * 100
    freq = freq * 1.0e5
    c2pi = 1.0 / (FPC_8 * PI * 2.0)
    fr = np.sign(freq) * np.sqrt(FPC_10 * np.abs(freq)) * c2pi
    fr = fr[:nvib]
    const = 0.5 * FPC_10 * FPC_6 * FPC_8 / (1.0e10 * 4.184)
    zpe = float(np.sum(fr[fr > 0])) * const
    return {
        "heat_of_formation": heat,
        "zero_point_energy": zpe,
        "frequencies": sorted(float(f) for f in fr),
    }
