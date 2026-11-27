"""COSMO implicit solvent (Klamt's model as implemented in MOPAC's cosmo.F90), single points.

Port of: COSINI (radii, grids), DVFILL (direction vectors), COSCAV (solvent accessible surface,
segments, A matrix), SURCLO (closure of the concave regions with ring segments), ANSUDE
(ring areas), MKBMAT (B matrix), ADDNUC/ADDHCR (nuclear screening: core-core energy and
one-electron matrix) and ADDFCK (electronic screening: Fock contribution).

The surface is a discrete construction, so every selection rule (point inclusion test, segment
assignment with its tie handling, the 3 nearest neighbours, ordering of rings and ring segments)
is reproduced literally; arithmetic is done in the same order as the Fortran wherever a
comparison could depend on it.

Coordinates are in Angstrom, energies in eV.
"""

import math

import numpy as np

from .constants import A0, EV

PI = 3.14159265358979323846
TIE_FACTOR = 1.0e-14
TWOPI = 2.0 * PI

# van der Waals radii of the COSMO model (cosini 'rvdw'), indexed by atomic number
_RVDW = [
    1.30, 1.64, 2.13, 2.19, 2.05, 2.00, 1.83, 1.72,
    1.72, 1.80, 2.66, 2.02, 2.41, 2.46, 2.11, 2.16,
    2.05, 2.20, 3.22, 2.54, 2.64, 2.64, 2.52, 2.40,
    2.46, 2.41, 2.40, 1.91, 1.64, 1.63, 2.19, 2.46,
    2.22, 2.22, 2.16, 2.36,
]  # fmt: skip

_KSET = [
    (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (12, 11), (12, 10), (12, 9), (12, 8), (12, 7),
    (2, 3), (3, 4), (4, 5), (5, 6), (6, 2), (7, 8), (8, 9), (9, 10), (10, 11), (11, 7),
    (2, 7), (7, 3), (3, 8), (8, 4), (4, 9), (9, 5), (5, 10), (10, 6), (6, 11), (11, 2),
]  # fmt: skip
_FSET = [
    (1, 2, 3), (1, 3, 4), (1, 4, 5), (1, 5, 6), (1, 6, 2),
    (12, 11, 10), (12, 10, 9), (12, 9, 8), (12, 8, 7), (12, 7, 11),
    (2, 3, 7), (3, 4, 8), (4, 5, 9), (5, 6, 10), (6, 2, 11),
    (7, 8, 3), (8, 9, 4), (9, 10, 5), (10, 11, 6), (11, 7, 2),
]  # fmt: skip


try:  # Python >= 3.13
    _fma = math.fma
except AttributeError:  # exact fused multiply-add (a*b+c rounded once)
    from fractions import Fraction as _Fr

    def _fma(a, b, c):
        return float(_Fr(a) * _Fr(b) + _Fr(c))


_SPL = 134217729.0  # 2**27 + 1 (Veltkamp splitting)


def vfma(a, b, c):
    """Vectorised a*b + c with a single rounding (error-free product and sum; agrees with a
    hardware fused multiply-add except in double-rounding cases of probability ~1e-16)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    c = np.asarray(c, float)
    p = a * b
    t1 = _SPL * a
    ah = t1 - (t1 - a)
    al = a - ah
    t2 = _SPL * b
    bh = t2 - (t2 - b)
    bl = b - bh
    e = ((ah * bh - p) + ah * bl + al * bh) + al * bl
    s = p + c
    bb = s - p
    t = (p - (s - bb)) + (c - bb)
    return s + (t + e)


def _rot3(x0, x1, x2, t0, t1, t2):
    """x0*t0 + x1*t1 + x2*t2 as compiled (SLP form of the original): fma(x2, t2, fma(x0, t0, x1*t1))."""
    return vfma(x2, t2, vfma(x0, t0, x1 * t1))


def _sqrt(x):
    return math.sqrt(x) if x >= 0.0 else float("nan")


# ----------------------------------------------------------------------------------------------
def dvfill(nppa):
    """Direction vectors of an almost regular icosahedral grid; returns (nppa, 4): x, y, z, weight."""
    d = [[0.0] * 4 for _ in range(nppa + 1)]  # 1-based
    d[1][0] = -1.0
    nd = 1
    r = math.sqrt(0.8)
    h = math.sqrt(0.2)
    for i in (-1, 1):
        for j in range(1, 6):
            nd += 1
            beta = 1.0 + j * 0.4 * PI + (i + 1) * 0.1 * PI
            d[nd][1] = r * math.cos(beta)
            d[nd][2] = r * math.sin(beta)
            d[nd][0] = i * h
    d[12][0] = 1.0
    d[12][1] = 0.0
    d[12][2] = 0.0
    nd = 12
    cphi = math.cos(1.0)
    sphi = math.sin(1.0)
    for i in range(1, 13):
        xx, yy = d[i][0], d[i][1]
        d[i][0] = cphi * xx + sphi * yy
        d[i][1] = -sphi * xx + cphi * yy
    m2 = (nppa - 2) // 10
    m = int(math.floor(math.sqrt(m2 + 0.0) + 0.5))
    k = 0
    if m2 != m * m:
        k = 1
        m2 = m2 // 3
        m = int(math.floor(math.sqrt(m2 + 0.0) + 0.5))
    if 10 * 3**k * m**2 + 2 != nppa:
        raise ValueError("VALUE OF NPPA NOT ALLOWED: IT MUST BE 10*3**K*M**2 + 2")
    for na, nb in _KSET:
        for j in range(1, m):
            nd += 1
            for ix in range(3):
                d[nd][ix] = _fma(d[na][ix], (m - j), d[nb][ix] * j)
    for na, nb, nc in _FSET:
        for j1 in range(1, m):
            for j2 in range(1, m - j1):
                nd += 1
                for ix in range(3):
                    d[nd][ix] = _fma(
                        d[nc][ix], j2, _fma(d[na][ix], (m - j1 - j2), d[nb][ix] * j1)
                    )
        if k != 0:
            t = 1.0 / 3
            for j1 in range(0, m):
                for j2 in range(0, m - j1):
                    nd += 1
                    for ix in range(3):
                        d[nd][ix] = _fma(
                            d[nc][ix],
                            (j2 + t),
                            _fma(
                                d[na][ix], (m - j1 - j2 - 2 * t), d[nb][ix] * (j1 + t)
                            ),
                        )
            t = 2.0 / 3
            for j1 in range(0, m - 1):
                for j2 in range(0, m - j1 - 1):
                    nd += 1
                    for ix in range(3):
                        d[nd][ix] = _fma(
                            d[nc][ix],
                            (j2 + t),
                            _fma(
                                d[na][ix], (m - j1 - j2 - 2 * t), d[nb][ix] * (j1 + t)
                            ),
                        )
    sumar = 0.0
    for i in range(1, nppa + 1):
        dist = 0.0
        for ix in range(3):
            dist = _fma(d[i][ix], d[i][ix], dist)
        dist = 1.0 / math.sqrt(dist)
        dist2 = (m * dist) ** 2
        for ix in range(3):
            d[i][ix] = d[i][ix] * dist
        ar = 5.0 if i <= 12 else 6.0 * dist2
        d[i][3] = ar
        sumar = sumar + ar
    sumar = 4 * PI / sumar
    for i in range(1, nppa + 1):
        d[i][3] = d[i][3] * sumar
    return np.array(d[1:], float)


class CosmoParams:
    """Defaults of COSINI (RSOLV, NSPA, DISEX) and the dielectric factor of EPS=."""

    def __init__(self, eps, rsolv=1.30005, nspa=42, disex=4.0):
        self.eps = eps
        self.fepsi = (eps - 1.0) / (eps + 0.5)
        self.rsolv = max(rsolv, 0.5)
        n0_1 = nspa
        if nspa != 42:
            x = (nspa - 2) / 10.0 + 1e-8
            n1 = 10 * int(math.sqrt(x)) ** 2 + 2
            n2 = 30 * int(math.sqrt(x / 3)) ** 2 + 2
            n0_1 = max(n1, n2)
            n0_1 = max(12, n0_1)
        self.nspa = n0_1
        n1 = (n0_1 - 2) // 10
        n0_2 = 10 * n1 // 3 + 2
        if n1 % 3 != 0:
            n0_2 = 10 * int(math.sqrt(n1 / 3.0)) ** 2 + 2
        n0_2 = max(n0_2, 12)
        self.n0 = (n0_1, n0_2)
        self.disex2 = 4 * (1.7 * disex) ** 2 / self.nspa
        self.dirsm = np.concatenate([dvfill(n0_1), dvfill(n0_2)])
        self.dirvec = dvfill(1082)


_PARAM_CACHE = {}


def get_params(eps, rsolv=1.30005, nspa=42, disex=4.0):
    key = (rsolv, nspa, disex)
    cp = _PARAM_CACHE.get(key)
    if cp is None:
        cp = CosmoParams(eps, rsolv, nspa, disex)
        _PARAM_CACHE[key] = cp
    out = CosmoParams.__new__(CosmoParams)
    out.__dict__.update(cp.__dict__)
    out.eps = eps
    out.fepsi = (eps - 1.0) / (eps + 0.5)
    return out


# ----------------------------------------------------------------------------------------------
def _ansude(ra, rb, d, rs):
    """Area of two intersecting spheres (only the pieces needed without gradients)."""
    qa = ra + rs
    qb = rb + rs
    ca = (qa**2 + d**2 - qb**2) / (2.0 * qa * d)
    cb = (qb**2 + d**2 - qa**2) / (2.0 * qb * d)
    sa = _sqrt(1.0 - ca * ca)
    sb = _sqrt(1.0 - cb * cb)
    ta = PI * sa
    tb = PI * sb
    fza = (1.0 - math.cos(ta)) / 2
    fzb = (1.0 - math.cos(tb)) / 2
    xa = fzb**1 * rs * (ca + cb)
    xb = fza**1 * rs * (ca + cb)
    ya = ra * sa - fzb * rb * sb
    yb = rb * sb - fza * ra * sa
    za = _sqrt(xa * xa + ya * ya)
    zb = _sqrt(xb * xb + yb * yb)
    rinc = 0.5 * (za + zb) / _sqrt(rs * rs * (ca + cb) ** 2 + (ra * sa - rb * sb) ** 2)
    aar = PI * ra * (sa * za)
    abr = PI * rb * (sb * zb)
    return aar, abr, rinc


class Cavity:
    pass


def build_cavity(z, coord, cp):
    """COSCAV.  ``coord`` (n,3) is moved by the 3e-9 Angstrom asymmetry of the original and
    returned in the Cavity object.  Returns the cavity with segments, area, volume and A matrix.

    Arithmetic note: the reference binary is compiled with ``-O3`` for a CPU with fused
    multiply-add and gfortran contracts ``a*b + c`` into one rounding.  Ties between the segment
    centres in the assignment loop are decided at the 1e-14 level (``spm = sp*(1+1e-14)``), which
    is the size of the rounding noise of the rotation matrices, so the expressions that feed the
    assignment (distances, rotation matrix, rotated grid, scalar products, centroids) are
    evaluated with the same fused operations (``_fma``/``vfma``; each pattern was checked against
    the compiled routine bit for bit)."""
    n = len(z)
    coord = np.array(coord, float)
    # make coordinates a bit asymmetric
    for i in range(n):
        for j in range(3):
            coord[i, j] = _fma(math.cos((i + 1) * (j + 1) * 0.1), 3.0e-9, coord[i, j])
    rsolv = cp.rsolv
    n0 = cp.n0
    dirvec = cp.dirvec
    dirsm = cp.dirsm
    srad = [_RVDW[zz - 1] for zz in z]
    fdiagr = 2.1 * math.sqrt(PI)
    cl = coord.tolist()

    def d2(i, j):
        a, b = cl[i], cl[j]
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        dz = a[2] - b[2]
        return _fma(dz, dz, _fma(dy, dy, dx * dx))

    # neighbour lists (atoms whose solvent-extended spheres intersect)
    lipa = []
    for i in range(n):
        ri = srad[i]
        r = ri + rsolv
        rr = r + rsolv
        lst = []
        for j in range(n):
            if j != i and d2(i, j) < (rr + srad[j]) ** 2:
                lst.append(j)
        lipa.append(lst)

    cosurf = []  # list of [x, y, z, area]
    iatsp = []
    nsetf_pts = []  # per segment: list of basic grid point indices
    area = 0.0
    cosvol = 0.0
    tms = [None] * n
    din_atom = [True] * n  # True: atom carries no segment
    dv4 = dirvec[:, 3]
    for i in range(n):
        ri = srad[i]
        r = ri + rsolv
        ri2 = ri * ri
        xa = cl[i]
        nipa = lipa[i]
        # three nearest neighbours
        dist1 = dist2 = dist3 = 1.0e20
        nn1 = nn2 = nn3 = -1
        for j in range(n):
            if j == i:
                continue
            dist = d2(i, j)
            if dist + 0.05 < dist3:
                dist3 = dist
                nn3 = j
            if dist3 + 0.05 < dist2:
                dist = dist2
                dist2 = dist3
                dist3 = dist
                nn3 = nn2
                nn2 = j
            if dist2 + 0.05 < dist1:
                dist = dist1
                dist1 = dist2
                dist2 = dist
                nn2 = nn1
                nn1 = j
        tm = [[0.0] * 3 for _ in range(3)]
        if nn1 < 0:
            tm[0] = [1.0, 0.0, 0.0]
        else:
            dd1 = d2(i, nn1)
            dist = 1.0 / math.sqrt(dd1)
            tm[0] = [(cl[nn1][k] - xa[k]) * dist for k in range(3)]
        rr = -1.0
        while True:
            if nn2 < 0:
                rr = rr + 1.0
                dist = math.sqrt(
                    9.0 * (tm[0][1] + rr) ** 2
                    + 4.0 * (tm[0][0] + rr**2) ** 2
                    + tm[0][2] ** 2
                )
                xx = [
                    3.0 * (tm[0][1] + rr) / dist,
                    tm[0][2] / dist,
                    2.0 * (tm[0][0] + rr**2) / dist,
                ]
            else:
                dist2_ = d2(i, nn2)
                dist = 1.0 / math.sqrt(dist2_)
                xx = [(cl[nn2][k] - xa[k]) * dist for k in range(3)]
            sp = _fma(xx[2], tm[0][2], _fma(xx[0], tm[0][0], xx[1] * tm[0][1]))
            if sp * sp > 0.99:
                nn2 = nn3
                nn3 = -1
                continue
            break
        sininv = 1.0 / math.sqrt(1.0 - sp * sp)
        tm[1] = [_fma(-sp, tm[0][k], xx[k]) * sininv for k in range(3)]
        tm[2] = [
            _fma(tm[0][1], tm[1][2], -(tm[1][1] * tm[0][2])),
            _fma(tm[0][2], tm[1][0], -(tm[1][2] * tm[0][0])),
            _fma(tm[0][0], tm[1][1], -(tm[1][0] * tm[0][1])),
        ]
        tms[i] = tm
        # rotate the basic grid
        dirtm = np.empty((1082, 3))
        for ix in range(3):
            dirtm[:, ix] = _rot3(
                dirvec[:, 0],
                dirvec[:, 1],
                dirvec[:, 2],
                tm[0][ix],
                tm[1][ix],
                tm[2][ix],
            )
        # points of the basic grid on the solvent accessible surface
        pts = np.empty((1082, 3))
        for ix in range(3):
            pts[:, ix] = vfma(dirtm[:, ix], r, xa[ix])
        din = np.ones(1082, bool)
        for k in nipa:
            dx = pts[:, 0] - cl[k][0]
            dy = pts[:, 1] - cl[k][1]
            dz = pts[:, 2] - cl[k][2]
            dist = np.sqrt(vfma(dz, dz, vfma(dy, dy, dx * dx))) - rsolv - srad[k]
            din &= ~(dist < 0)
        jlist = np.nonzero(din)[0]
        narea = len(jlist)
        for j in jlist:
            cosvol = cosvol + ri2 * dirvec[j, 3] * (
                dirtm[j, 0] * xa[0] + dirtm[j, 1] * xa[1] + dirtm[j, 2] * xa[2] + ri
            )
            area = area + ri2 * dirvec[j, 3]
        if narea == 0:
            continue
        din_atom[i] = False
        i0 = 1
        if z[i] == 1:
            i0 = 2
        jmax = n0[i0 - 1]
        i0 = (i0 - 1) * n0[0]
        sm = dirsm[i0 : i0 + jmax]
        csa = np.empty((jmax, 3))
        for ix in range(3):
            csa[:, ix] = _rot3(
                sm[:, 0], sm[:, 1], sm[:, 2], tm[0][ix], tm[1][ix], tm[2][ix]
            )
        dtm = dirtm[jlist]
        wj = dv4[jlist]
        x1, x2, x3 = dtm[:, 0], dtm[:, 1], dtm[:, 2]
        niter = 0
        while True:
            niter += 1
            nseg = len(csa)
            spm = np.full(len(jlist), -1.0)
            ipm = np.full(len(jlist), -1, dtype=int)
            for k in range(nseg):
                sp = vfma(x3, csa[k, 2], vfma(x2, csa[k, 1], x1 * csa[k, 0]))
                m = sp >= spm
                spm = np.where(m, sp * (1.0 + TIE_FACTOR), spm)
                ipm = np.where(m, k, ipm)
            nar = np.bincount(ipm[ipm >= 0], minlength=nseg)
            ph = np.zeros((nseg, 3))
            order = np.argsort(
                ipm, kind="stable"
            )  # points of a segment in increasing j
            starts = np.concatenate([[0], np.cumsum(nar)[:-1]])
            for t in range(int(nar.max())):
                sel = np.nonzero(nar > t)[0]
                pt = order[starts[sel] + t]
                for ix in range(3):
                    ph[sel, ix] = vfma(dtm[pt, ix], wj[pt], ph[sel, ix])
            # remove empty segments, normalise the centroids
            keep = [k for k in range(nseg) if nar[k] != 0]
            if len(keep) != nseg:
                niter = 1
            newcs = []
            for k in keep:
                dists = _fma(
                    ph[k, 2], ph[k, 2], _fma(ph[k, 1], ph[k, 1], ph[k, 0] * ph[k, 0])
                )
                dists = max(dists, 1.0e-20)
                dist = 1.0 / math.sqrt(dists)
                newcs.append([ph[k, 0] * dist, ph[k, 1] * dist, ph[k, 2] * dist])
            csa = np.array(newcs)
            if niter >= 2:
                break
        # (a pass that removes segments is always followed by another one, so the assignment of
        # the last pass refers to the final list of segments)
        nseg = len(csa)
        nar = np.bincount(ipm, minlength=nseg)
        order = np.argsort(ipm, kind="stable")
        starts = np.concatenate([[0], np.cumsum(nar)[:-1]])
        ar = np.zeros(nseg)
        for t in range(int(nar.max())):
            sel = np.nonzero(nar > t)[0]
            pt = order[starts[sel] + t]
            ar[sel] = vfma(wj[pt], ri2, ar[sel])
        for k in range(nseg):
            pts_k = [int(jj) for jj in jlist[order[starts[k] : starts[k] + nar[k]]]]
            cosurf.append(
                [
                    _fma(csa[k, 0], ri, xa[0]),
                    _fma(csa[k, 1], ri, xa[1]),
                    _fma(csa[k, 2], ri, xa[2]),
                    float(ar[k]),
                ]
            )
            iatsp.append(i)
            nsetf_pts.append(pts_k)

    # ---- closure of the concave regions
    cav = Cavity()
    cav.coord = coord
    cav.tms = tms
    res = _surclo(coord, lipa, din_atom, srad, cosurf, iatsp, nsetf_pts, z, n0, rsolv)
    rsc_rows, ring_cum, extra_area, extra_vol = res
    area += extra_area
    cosvol += extra_vol
    cosvol = cosvol / 3
    nps = len(cosurf)
    cav.nps = nps
    cav.area = area
    cav.volume = cosvol
    cav.cosurf = np.array(cosurf, float).reshape(nps, 4)
    cav.iatsp = np.array(iatsp, int)
    cav.srad = srad

    # ---- A matrix
    cav.amat = _build_amat(
        coord,
        tms,
        srad,
        cav.cosurf,
        cav.iatsp,
        nsetf_pts,
        rsc_rows,
        ring_cum,
        dirvec,
        cp.disex2,
        fdiagr,
    )
    return cav


def _surclo(coord, lipa, din_atom, srad, cosurf, iatsp, nsetf_pts, z, n0, rsolv):
    """SURCLO: ring segments closing the concave region; segments are merged into/added to
    ``cosurf``/``iatsp``/``nsetf_pts`` in place.  Returns the ring segments sorted by segment."""
    n = len(z)
    rsc = []  # [x, y, z, area]
    ipsrs = []  # atom (0-based) each ring segment belongs to
    tarset = [0.0] * 51  # persists between rings, as in the Fortran (1-based)
    phiset = [0.0] * 51
    iset = [0] * 51
    extra_area = 0.0
    extra_vol = 0.0
    for ia in range(n - 1):
        if din_atom[ia]:
            continue
        ra = srad[ia] + rsolv
        xa1 = [coord[ia, k] for k in range(3)]
        for ib in lipa[ia]:
            if not ib > ia:
                continue
            if din_atom[ib]:
                continue
            rb = srad[ib] + rsolv
            xa2 = [coord[ib, k] for k in range(3)]
            xx = [xa2[k] - xa1[k] for k in range(3)]
            dab = 0.0
            for ix in range(3):
                dab = dab + xx[ix] ** 2
            dab = math.sqrt(dab)
            aar, abr, rinc = _ansude(ra - rsolv, rb - rsolv, dab, rsolv)
            cosa = (ra**2 + dab**2 - rb**2) / (2 * dab * ra)
            cosb = (rb**2 + dab**2 - ra**2) / (2 * dab * rb)
            sina = _sqrt(1.0 - cosa**2)
            da = ra * cosa
            hh = ra * sina
            ddd = rsolv * (cosa + cosb) / dab
            fz = [
                (1.0 - math.cos(hh * PI / ra)) / 2,
                (1.0 - math.cos(hh * PI / rb)) / 2,
            ]
            if cosa * cosb < 0.0:
                fz = [1.0, 1.0]
            yx = [rsolv / ra, rsolv / rb]
            xd = [xa1[ix] + da * xx[ix] / dab for ix in range(3)]
            rvx = [
                xx[1] * 3.0 - xx[2] * 2.0,
                xx[2] * 1.0 - xx[0] * 3.0,
                xx[0] * 2.0 - xx[1] * 1.0,
            ]
            dist = math.sqrt(rvx[0] ** 2 + rvx[1] ** 2 + rvx[2] ** 2)
            if dist < 1e-9:
                rvx = [
                    xx[1] * 4.0 - xx[2] * 2.0,
                    xx[2] * 1.0 - xx[0] * 4.0,
                    xx[0] * 2.0 - xx[1] * 1.0,
                ]
                dist = math.sqrt(rvx[0] ** 2 + rvx[1] ** 2 + rvx[2] ** 2)
            rvx = [hh * rvx[ix] / dist for ix in range(3)]
            rvy = [
                (xx[1] * rvx[2] - xx[2] * rvx[1]) / dab,
                (xx[2] * rvx[0] - xx[0] * rvx[2]) / dab,
                (xx[0] * rvx[1] - xx[1] * rvx[0]) / dab,
            ]
            # triple points on the ring
            ntrp = 0
            ntrp2 = 0
            for ic in lipa[ia]:
                if ic == ib:
                    continue
                rc = srad[ic] + rsolv
                dabc = 0.0
                sp = 0.0
                xa3 = [coord[ic, k] for k in range(3)]
                for ix in range(3):
                    xxx = coord[ic, ix] - xd[ix]
                    sp = sp + xxx * xx[ix]
                    dabc = dabc + xxx**2
                dabc = math.sqrt(dabc)
                cosa = sp / dab / dabc
                sina = math.sqrt(max(1.0e-28, 1.0 - cosa * cosa))
                cj = (dabc * dabc + hh * hh - rc * rc) / (2 * dabc * hh * sina)
                if cj < 1.0:
                    ntrp2 += 2
                if cj <= 1.0 and cj >= -1.0:
                    sj = math.sqrt(1.0 - cj * cj)
                    tvx = [
                        (xa3[ix] - xd[ix]) - cosa * dabc * xx[ix] / dab
                        for ix in range(3)
                    ]
                    dist = math.sqrt(tvx[0] ** 2 + tvx[1] ** 2 + tvx[2] ** 2)
                    tvx = [hh * tvx[ix] / dist for ix in range(3)]
                    tvy = [
                        (xx[1] * tvx[2] - xx[2] * tvx[1]) / dab,
                        (xx[2] * tvx[0] - xx[0] * tvx[2]) / dab,
                        (xx[0] * tvx[1] - xx[1] * tvx[0]) / dab,
                    ]
                    for l in (-1, 1):
                        il = ntrp + 1
                        trp = [
                            xd[ix] + cj * tvx[ix] + sj * tvy[ix] * l for ix in range(3)
                        ]
                        blocked = False
                        for k in lipa[ia]:
                            if k != ib and k != ic:
                                dabck = 0.0
                                for ix in range(3):
                                    dabck = dabck + (trp[ix] - coord[k, ix]) ** 2
                                dabck = math.sqrt(dabck)
                                if dabck < srad[k] + rsolv:
                                    blocked = True
                                    break
                        if blocked:
                            continue
                        ntrp += 1
                        spx = 0.0
                        spy = 0.0
                        for ix in range(3):
                            spx = spx + rvx[ix] * (trp[ix] - xd[ix])
                            spy = spy + rvy[ix] * (trp[ix] - xd[ix])
                        arg = spx / (hh**2 + 1.0e-10)
                        phi = math.acos(arg) if -1.0 <= arg <= 1.0 else float("nan")
                        if spy < 0.0:
                            phi = -phi
                        phiset[il] = phi
                        sp = 0.0
                        for ix in range(3):
                            sp = sp + (-spy * rvx[ix] + spx * rvy[ix]) * (
                                trp[ix] - xa3[ix]
                            )
                        iset[ntrp] = -1 if sp < 0.0 else 1
                        sp = 0.0
                        dac = 0.0
                        dbc = 0.0
                        ee = [[0.0] * 3 for _ in range(3)]
                        for ix in range(3):
                            ee[0][ix] = trp[ix] + rsolv / srad[ia] * (xa1[ix] - trp[ix])
                            ee[1][ix] = trp[ix] + rsolv / srad[ib] * (xa2[ix] - trp[ix])
                            ee[2][ix] = trp[ix] + rsolv / srad[ic] * (xa3[ix] - trp[ix])
                            sp = sp + (ee[0][ix] - ee[2][ix]) * (ee[1][ix] - ee[2][ix])
                            dac = dac + (ee[0][ix] - ee[2][ix]) * (
                                ee[0][ix] - ee[2][ix]
                            )
                            dbc = dbc + (ee[1][ix] - ee[2][ix]) * (
                                ee[1][ix] - ee[2][ix]
                            )
                        tarset[il] = 0.8 * _sqrt(dac * dbc - sp * sp) / 12
            if ntrp + ntrp2 == 0:
                phiset[1] = 0.0
                phiset[2] = TWOPI
                tarset[2] = 0.0
                iset[1] = 1
                iset[2] = -1
                ntrp = 2
            # sort the triple points
            guard = 0
            while True:
                icnt = 0
                for l in range(2, ntrp + 1):
                    if phiset[l] < phiset[l - 1]:
                        phiset[l], phiset[l - 1] = phiset[l - 1], phiset[l]
                        iset[l], iset[l - 1] = iset[l - 1], iset[l]
                        tarset[l], tarset[l - 1] = tarset[l - 1], tarset[l]
                        icnt += 1
                if icnt <= 0:
                    if iset[1] == -1:
                        phiset[1] = phiset[1] + TWOPI
                        guard += 1
                        if guard > 1000:  # (original would loop forever)
                            break
                    else:
                        break
            sumphi = 0.0
            for l in range(2, ntrp + 1, 2):
                k = l - 1
                phiu = phiset[k]
                phio = phiset[l]
                nsa = int((phio - phiu) / 2 / PI * 20)
                nsa = max(nsa + 1, 2)
                sumphi = sumphi + phio - phiu
                dp = (phio - phiu) / (nsa - 1)
                for ich in (1, 2):
                    iat = ib if ich == 1 else ia
                    htr = aar / TWOPI if iat == ia else abr / TWOPI
                    xtc = xa1 if ich == 1 else xa2
                    xto = xa2 if ich == 1 else xa1
                    for ja in range(ich, nsa + 1, 2):
                        jb = max(ja - 1, 1)
                        jc = min(ja + 1, nsa)
                        phi = phiu + (ja - 1) * dp
                        cphi = math.cos(phi)
                        sphi = math.sin(phi)
                        xja = [0.0] * 3
                        for ix in range(3):
                            ca = (
                                xd[ix] + (cphi * rvx[ix] + sphi * rvy[ix]) * fz[ich - 1]
                            )
                            ca = ca + (xtc[ix] - ca) * yx[ich - 1]
                            xja[ix] = ca + (xto[ix] - xtc[ix]) * ddd * (
                                1.0 - fz[ich - 1]
                            )
                        phi = phiu + (jb - 1) * dp
                        cphi = math.cos(phi)
                        sphi = math.sin(phi)
                        xjb = [0.0] * 3
                        for ix in range(3):
                            ca = xd[ix] + cphi * rvx[ix] + sphi * rvy[ix]
                            xjb[ix] = ca + (xto[ix] - ca) * yx[2 - ich]
                        phi = phiu + (jc - 1) * dp
                        cphi = math.cos(phi)
                        sphi = math.sin(phi)
                        xjc = [0.0] * 3
                        for ix in range(3):
                            ca = xd[ix] + cphi * rvx[ix] + sphi * rvy[ix]
                            xjc[ix] = ca + (xto[ix] - ca) * yx[2 - ich]
                        spn = 0.0
                        spn2 = 0.0
                        dist = 0.0
                        row = [0.0] * 4
                        for ix in range(3):
                            row[ix] = (xja[ix] * 0.5 + xjb[ix] + xjc[ix]) / 2.5
                            i2 = (ix + 1) % 3
                            i3 = (i2 + 1) % 3
                            cnrs = (xjc[i2] - xjb[i2]) * (xja[i3] - xjb[i3]) - (
                                xja[i2] - xjb[i2]
                            ) * (xjc[i3] - xjb[i3])
                            dist = dist + cnrs**2
                            spn = spn + cnrs * (row[ix] - coord[iat, ix])
                            spn2 = spn2 + cnrs * row[ix]
                        dist = 1.0 / math.sqrt(dist)
                        if spn < 0.0:
                            dist = -dist
                        row[3] = (jc - jb) * dp * htr
                        if ja == 1:
                            row[3] = row[3] + tarset[k] * rinc
                        if ja == nsa:
                            row[3] = row[3] + tarset[l] * rinc
                        extra_vol = extra_vol + row[3] * spn2 * dist
                        extra_area = extra_area + row[3]
                        rsc.append(row)
                        ipsrs.append(iat)
    nrs = len(rsc)
    # sort ring segments with respect to atoms (stable)
    order = sorted(range(nrs), key=lambda q: ipsrs[q])
    rsc = [rsc[q] for q in order]
    ipsrs = [ipsrs[q] for q in order]
    # nearest primary segment of the same atom
    nps = len(cosurf)
    nipsrs = [0] * nps
    iat0 = -1
    ips0 = ips1 = 0
    d2max = 0.0
    ips1 = -1
    seg_of = [0] * nrs
    for i in range(nrs):
        iat = ipsrs[i]
        if iat > iat0:
            iat0 = iat
            d2max = 16 * srad[iat] ** 2 / n0[0]
            if z[iat] == 1:
                d2max = d2max * n0[0] / n0[1]
            ips = ips1 + 1
            while ips < nps and iatsp[ips] != iat:
                ips += 1
            ips0 = ips
            ips = ips0
            while ips < nps - 1 and not iatsp[ips + 1] > iat:
                ips += 1
            ips1 = ips
        ipsmin = -1
        d2min = 1.0e6
        row = rsc[i]
        for ips in range(ips0, ips1 + 1):
            dd = 0.0
            for ix in range(3):
                dd = dd + (cosurf[ips][ix] - row[ix]) ** 2
            if dd < d2min:
                ipsmin = ips
                d2min = dd
        if d2min > d2max:
            ips1 += 1
            cosurf.insert(ips1, [row[0], row[1], row[2], row[3]])
            iatsp.insert(ips1, iatsp[ips1 - 1])
            nsetf_pts.insert(ips1, [])
            nipsrs.insert(ips1, 1)
            nps += 1
            seg_of[i] = ips1
        else:
            seg_of[i] = ipsmin
            nipsrs[ipsmin] += 1
            arseg = cosurf[ipsmin][3]
            arsegn = arseg + row[3]
            for ix in range(3):
                cosurf[ipsmin][ix] = (
                    arseg * cosurf[ipsmin][ix] + row[3] * row[ix]
                ) / arsegn
            cosurf[ipsmin][3] = arsegn
    # sort the ring segments with respect to the primary segments (stable)
    order = sorted(range(nrs), key=lambda q: seg_of[q])
    rsc_sorted = [rsc[q] for q in order]
    cum = []
    s = 0
    for k in range(nps):
        s += nipsrs[k]
        cum.append(s)
    return rsc_sorted, cum, extra_area, extra_vol


def _build_amat(
    coord, tms, srad, cosurf, iatsp, nsetf_pts, rsc, ring_cum, dirvec, disex2, fdiagr
):
    nps = len(cosurf)
    # grid points of every atom in the (rotated) vdW sphere
    atom_pts = {}
    for i in set(int(a) for a in iatsp):
        r = srad[i]
        tm = tms[i]
        y = dirvec[:, :3] * r
        g = np.empty((1082, 3))
        for ix in range(3):
            g[:, ix] = (
                y[:, 0] * tm[0][ix]
                + y[:, 1] * tm[1][ix]
                + y[:, 2] * tm[2][ix]
                + coord[i, ix]
            )
        atom_pts[i] = g
    elems = []
    for ips in range(nps):
        i = int(iatsp[ips])
        r = srad[i]
        idx = nsetf_pts[ips]
        pts = atom_pts[i][idx] if idx else np.zeros((0, 3))
        w = dirvec[idx, 3] * r * r if idx else np.zeros(0)
        a = ring_cum[ips - 1] if ips > 0 else 0
        b = ring_cum[ips]
        if b > a:
            rr = np.array(rsc[a:b], float)
            pts = np.concatenate([pts, rr[:, :3]])
            w = np.concatenate([w, rr[:, 3]])
        elems.append((pts, w))
    m = max(len(e[1]) for e in elems)
    F = np.zeros((nps, m, 3))
    W = np.zeros((nps, m))
    for ips, (p, w) in enumerate(elems):
        F[ips, : len(w)] = p
        W[ips, : len(w)] = w
        # padding: distinct far-away positions with zero weight
        if len(w) < m:
            F[ips, len(w) :, 0] = 1.0e6 + np.arange(m - len(w)) * 1.0e3
    A = np.zeros((nps, nps))
    # diagonal
    for ips in range(nps):
        p, w = elems[ips]
        k = len(w)
        aa = float(np.sum(fdiagr * np.sqrt(w**3)))
        if k > 1:
            dx = p[:, None, :] - p[None, :, :]
            dm = np.sqrt(np.sum(dx * dx, axis=2))
            iu = np.tril_indices(k, -1)
            aa += float(np.sum(2 * w[iu[0]] * w[iu[1]] / dm[iu]))
        A[ips, ips] = aa / cosurf[ips, 3] ** 2
    # off diagonal
    cx = cosurf[:, :3]
    dxx = cx[:, None, :] - cx[None, :, :]
    d2m = dxx[:, :, 0] ** 2 + dxx[:, :, 1] ** 2 + dxx[:, :, 2] ** 2
    il = np.tril_indices(nps, -1)
    far = d2m[il] > disex2
    A[il[0][far], il[1][far]] = 1.0 / np.sqrt(d2m[il][far])
    ci, cj = il[0][~far], il[1][~far]
    chunk = max(1, int(4.0e6 // max(1, m * m)))
    for s in range(0, len(ci), chunk):
        a = ci[s : s + chunk]
        b = cj[s : s + chunk]
        pa_, pb_ = F[a], F[b]
        dx = pa_[:, :, None, :] - pb_[:, None, :, :]
        dm = np.sqrt(np.sum(dx * dx, axis=3))
        prod = W[a][:, :, None] * W[b][:, None, :]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(prod == 0.0, 0.0, prod / dm)  # (padding has zero weight)
        aa = t.sum(axis=(1, 2))
        A[a, b] = aa / cosurf[a, 3] / cosurf[b, 3]
    A = np.tril(A) + np.tril(A, -1).T
    return A


# ----------------------------------------------------------------------------------------------
class CosmoModel:
    """Cavity + B matrix + the screening operators used in the SCF."""

    def __init__(self, z, coord, el, cp, tore):
        self.cp = cp
        self.cav = build_cavity(z, coord, cp)
        self.coord = self.cav.coord
        self.z = list(z)
        self.el = el
        self.fcon = A0 * EV
        self.fepsi = cp.fepsi
        try:  # Cholesky factorisation of A (COSCL1/COSCL2); A is symmetric positive definite
            import scipy.linalg as sl

            cho = sl.cho_factor(self.cav.amat, lower=True)
            self._solve = lambda y: sl.cho_solve(cho, y)
        except Exception:  # pragma: no cover
            ainv = np.linalg.inv(self.cav.amat)
            self._solve = lambda y: ainv @ y
        self._make_bmat(tore)

    def _make_bmat(self, tore):
        from .params import ELEMENTS

        cav = self.cav
        z = self.z
        n = len(z)
        nps = cav.nps
        rows, cols, gden, idenat = [], [], [], []
        blocks = []
        off = self.el.offsets
        for i in range(n):
            e = ELEMENTS[z[i]]
            idel = e.natorb
            a = off[i]
            idenat.append(len(rows))
            for j in range(idel):
                for k in range(j + 1):
                    rows.append(a + j)
                    cols.append(a + k)
                    gden.append(-1.0 if j == k else -2.0)
        lm61 = len(rows)
        self.rows = np.array(rows)
        self.cols = np.array(cols)
        self.gden = np.array(gden)
        self.idenat = idenat
        B = np.zeros((lm61, nps))
        # PM7 has no 'dsd', 'dpd', 'ddd' (they are set only for INDO)
        dsdi = dpdi = dddi = 0.0
        iden = 0
        for i in range(n):
            e = ELEMENTS[z[i]]
            idel = e.natorb
            ddi = e.dd * A0
            qqi2 = (A0 * e.qq) ** 2
            xa = cav.cosurf[:, :3] - self.coord[i]
            dist = xa[:, 0] ** 2 + xa[:, 1] ** 2 + xa[:, 2] ** 2
            rm1 = 1.0 / np.sqrt(dist)
            B[iden, :] = rm1
            if idel > 1:
                rm3 = rm1**3
                rm5 = rm1**5
                x, y, zc = xa[:, 0], xa[:, 1], xa[:, 2]
                B[iden + 2, :] = rm1 + 3 * x**2 * qqi2 * rm5 - qqi2 * rm3
                B[iden + 5, :] = rm1 + 3 * y**2 * qqi2 * rm5 - qqi2 * rm3
                B[iden + 9, :] = rm1 + 3 * zc**2 * qqi2 * rm5 - qqi2 * rm3
                B[iden + 1, :] = x * ddi * rm3
                B[iden + 3, :] = y * ddi * rm3
                B[iden + 6, :] = zc * ddi * rm3
                B[iden + 4, :] = 3 * x * y * qqi2 * rm5
                B[iden + 7, :] = 3 * x * zc * qqi2 * rm5
                B[iden + 8, :] = 3 * zc * y * qqi2 * rm5
                if idel > 4:
                    for iii in range(5, 10):
                        B[iden + (iii * (iii + 1)) // 2 - 1, :] = rm1
                    # MOPAC d-orbital order: x2-y2, xz, z2, yz, xy
                    B[iden + 14, :] = rm1 + dddi * rm3 - 3 * dddi * zc**2 * rm5
                    B[iden + 20, :] = rm1 + dddi * rm3 - 3 * dddi * y**2 * rm5
                    B[iden + 27, :] = rm1 - dddi * rm3 + 3 * dddi * zc**2 * rm5
                    B[iden + 35, :] = rm1 + dddi * rm3 - 3 * dddi * x**2 * rm5
                    B[iden + 44, :] = rm1 + dddi * rm3 - 3 * dddi * zc**2 * rm5
                    atmp = 2 * zc**2 - x**2 - y**2
                    B[iden + 10, :] = 3 * dsdi * (x**2 - y**2) * rm5 / 2.0
                    B[iden + 15, :] = 3 * dsdi * x * zc * rm5
                    B[iden + 21, :] = math.sqrt(3.0) * atmp * rm5 / 2.0
                    B[iden + 28, :] = 3 * dsdi * y * zc * rm5
                    B[iden + 36, :] = 3 * dsdi * x * y * rm5
                    B[iden + 11, :] = dpdi * x * rm3
                    B[iden + 12, :] = dpdi * y * rm3
                    B[iden + 13, :] = 0.0
                    B[iden + 16, :] = dpdi * zc * rm3
                    B[iden + 17, :] = 0.0
                    B[iden + 18, :] = dpdi * x * rm3
                    B[iden + 22, :] = -dpdi * x * rm3 / math.sqrt(3.0)
                    B[iden + 23, :] = -dpdi * y * rm3 / math.sqrt(3.0)
                    B[iden + 24, :] = 2 * dpdi * zc * rm3 / math.sqrt(3.0)
                    B[iden + 29, :] = 0.0
                    B[iden + 30, :] = dpdi * zc * rm3
                    B[iden + 31, :] = dpdi * y * rm3
                    B[iden + 37, :] = dpdi * y * rm3
                    B[iden + 38, :] = dpdi * x * rm3
                    B[iden + 39, :] = 0.0
                    B[iden + 19, :] = 3 * dddi * x * zc * rm5
                    B[iden + 25, :] = 3 * dddi * rm5 * (x**2 - y**2)
                    B[iden + 26, :] = math.sqrt(3.0) * dddi * rm5 * x * zc
                    B[iden + 32, :] = 3 * dddi * y * zc * rm5
                    B[iden + 33, :] = 3 * dddi * x * y * rm5
                    B[iden + 34, :] = math.sqrt(3.0) * dddi * rm5 * y * zc
                    B[iden + 40, :] = 0.0
                    B[iden + 41, :] = 3 * dddi * y * zc * rm5
                    B[iden + 42, :] = -2 * math.sqrt(3.0) * dddi * rm5 * x * y
                    B[iden + 43, :] = 3 * dddi * x * zc * rm5
            iden += (idel * (idel + 1)) // 2
        self.B = B
        # ---- nuclear part (ADDNUC / ADDHCR)
        qnuc = np.zeros(lm61)
        for i in range(n):
            qnuc[idenat[i]] = tore[i]
        phin = B.T @ qnuc
        qsc = -self.fepsi * self._solve(phin)
        self.q_nuc = qsc
        self.enuc = self.fcon * float(np.sum(qsc * phin)) / 2

    def add_to_h(self, h):
        """ADDHCR: returns h with the nuclear screening potential subtracted."""
        v = self.fcon * (self.B @ self.q_nuc)
        h2 = h.copy()
        h2[self.rows, self.cols] -= v
        off = self.rows != self.cols
        h2[self.cols[off], self.rows[off]] -= v[off]
        return h2

    def fock(self, p):
        """ADDFCK: Fock contribution of the electronic screening charges (total density p)."""
        qden = self.gden * p[self.rows, self.cols]
        phi = self.B.T @ qden
        qsc = -self.fepsi * self._solve(phi)
        v = -self.fcon * (self.B @ qsc)
        g = np.zeros_like(p)
        g[self.rows, self.cols] = v
        off = self.rows != self.cols
        g[self.cols[off], self.rows[off]] = v[off]
        return g
