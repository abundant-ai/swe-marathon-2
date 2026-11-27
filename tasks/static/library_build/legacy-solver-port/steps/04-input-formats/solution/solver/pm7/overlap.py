"""Diatomic Slater-orbital overlap integrals and the resonance (beta) block of H.

Ports: integrals/diat.F90 (diat, diat2, ss), coe.F90, set.F90 (set, aintgs, bintgs),
bfn.F90, h1elec.F90.  The numerical series/closed-form switches of the Fortran
(`last` terms, thresholds on |x|) are reproduced on purpose: they decide the value
of the overlaps at the 1e-7 level and the reference numbers contain them.
"""

import math

import numpy as np

from .constants import A0
from .params import ELEMENTS

CUTOF1 = 225.0  # (distance)**2 cutoff for overlaps, Angstrom**2
CUTOFS = 1.0e4  # h1elec distance**2 cutoff

FACT = [
    1.0,
    1.0,
    2.0,
    6.0,
    24.0,
    120.0,
    720.0,
    5040.0,
    40320.0,
    362880.0,
    3628800.0,
    39916800.0,
    479001600.0,
    6227020800.0,
    8.71782912e10,
    1.307674368e12,
    2.092278989e13,
    3.556874281e14,
]

# binomial coefficients bi(i,j), i,j = 0..12
_BI = [[0.0] * 13 for _ in range(13)]
for _i in range(13):
    _BI[_i][0] = 1.0
    _BI[_i][_i] = 1.0
for _i in range(0, 12):
    for _j in range(1, _i + 1):
        _BI[_i + 1][_j] = _BI[_i][_j] + _BI[_i][_j - 1]

_AFF = {
    (0, 0, 0): 1.0,
    (1, 0, 0): 1.0,
    (1, 1, 0): math.sqrt(0.5),
    (2, 0, 0): 1.5,
    (2, 1, 0): math.sqrt(1.5),
    (2, 2, 0): math.sqrt(0.375),
    (2, 0, 2): -0.5,
}


def _series(x, i, last):
    y = 0.0
    for m in range(0, last + 1):
        xf = 1.0 if m == 0 else FACT[m]
        y += (-x) ** m * (2 * ((m + i + 1) % 2)) / (xf * (m + i + 1))
    return y


def bfn(x):
    """B-integrals B_0..B_12 as used by ss() (bf(0:12))."""
    k = 12
    absx = abs(x)
    bf = [0.0] * 13
    if absx <= 3.0:
        if absx > 2.0:
            last = 15
        elif absx > 1.0:
            last = 12
        elif absx > 0.5:
            last = 7
        elif absx <= 1e-6:
            for i in range(0, k + 1):
                bf[i] = (2 * ((i + 1) % 2)) / (i + 1.0)
            return bf
        else:
            last = 6
        for i in range(0, k + 1):
            bf[i] = _series(x, i, last)
        return bf
    expx = math.exp(x)
    expmx = 1.0 / expx
    bf[0] = (expx - expmx) / x
    for i in range(1, k + 1):
        bf[i] = (i * bf[i - 1] + (-1.0) ** i * expx - expmx) / x
    return bf


def ss(na, nb, la1, lb1, m1, ua, ub, r1):
    """STO overlap in the diatomic frame (function SS of diat.F90).  r1 in Angstrom."""
    m = m1 - 1
    lb = lb1 - 1
    la = la1 - 1
    r = r1 / A0
    p = (ua + ub) * r * 0.5
    b = (ua - ub) * r * 0.5
    quo = 1.0 / p
    af = [0.0] * 20
    af[0] = quo * math.exp(-p)
    for n in range(1, 20):
        af[n] = n * quo * af[n - 1] + af[0]
    bf = bfn(b)
    total = 0.0
    lam1 = la - m
    lbm1 = lb - m
    for i in range(0, lam1 + 1, 2):
        ia = na + i - la
        ic = la - i - m
        for j in range(0, lbm1 + 1, 2):
            ib = nb + j - lb
            idd = lb - j - m
            sum1 = 0.0
            iab = ia + ib
            for k1 in range(0, ia + 1):
                for k2 in range(0, ib + 1):
                    for k3 in range(0, ic + 1):
                        for k4 in range(0, idd + 1):
                            for k5 in range(0, m + 1):
                                iaf = iab - k1 - k2 + k3 + k4 + 2 * k5
                                for k6 in range(0, m + 1):
                                    ibf = k1 + k2 + k3 + k4 + 2 * k6
                                    sum1 += (
                                        _BI[idd][k4]
                                        * _BI[ic][k3]
                                        * _BI[ib][k2]
                                        * _BI[ia][k1]
                                        * _BI[m][k5]
                                        * _BI[m][k6]
                                        * (1 - 2 * ((m + k2 + k4 + k5 + k6) % 2))
                                        * af[iaf]
                                        * bf[ibf]
                                    )
            total += sum1 * _AFF.get((la, m, i), 0.0) * _AFF.get((lb, m, j), 0.0)
    return (
        total
        * r ** (na + nb + 1)
        * ua**na
        * ub**nb
        / 2.0
        * math.sqrt(
            ua * ub / (FACT[na + na] * FACT[nb + nb]) * ((la + la + 1) * (lb + lb + 1))
        )
    )


# ---------------------------------------------------------------- diat2 (small-basis closed forms)
class _SetState:
    """Module state of overlaps_C used by set/diat2."""

    __slots__ = ("a", "b", "sa", "sb", "isp", "ips")

    def __init__(self):
        self.a = [0.0] * 9
        self.b = [0.0] * 9
        self.sa = self.sb = 0.0
        self.isp = self.ips = 0


def _aintgs(x, k, a):
    c = math.exp(-x)
    a[1] = c / x
    for i in range(1, k + 1):
        a[i + 1] = (a[i] * i + c) / x


def _bintgs(x, k, b):
    absx = abs(x)
    use_exp = False
    last = None
    if absx > 3.0:
        use_exp = True
    elif absx > 2.0:
        if k <= 10:
            use_exp = True
        else:
            last = 15
    elif absx > 1.0:
        if k <= 7:
            use_exp = True
        else:
            last = 12
    elif absx > 0.5:
        if k <= 5:
            use_exp = True
        else:
            last = 7
    elif absx <= 1e-6:
        for i in range(0, k + 1):
            b[i + 1] = (2 * ((i + 1) % 2)) / (i + 1.0)
        return
    else:
        last = 6
    if use_exp:
        expx = math.exp(x)
        expmx = 1.0 / expx
        b[1] = (expx - expmx) / x
        for i in range(1, k + 1):
            b[i + 1] = (i * b[i] + (-1.0) ** i * expx - expmx) / x
    else:
        for i in range(0, k + 1):
            b[i + 1] = _series(x, i, last)


def _set(st, s1, s2, na, nb, rab, ii):
    if na <= nb:
        st.isp, st.ips, st.sa, st.sb = 1, 2, s1, s2
    else:
        st.isp, st.ips, st.sa, st.sb = 2, 1, s2, s1
    j = ii + 2
    if ii > 3:
        j -= 1
    alpha = 0.5 * rab * (st.sa + st.sb)
    beta = 0.5 * rab * (st.sb - st.sa)
    jcall = j - 1
    _aintgs(alpha, jcall, st.a)
    _bintgs(beta, jcall, st.b)


_INMB = [0, 1, 0, 2, 2, 3, 4, 5, 6, 7, 0, 8, 8, 8, 9, 10, 11, 12]  # 1-based
_III = [
    0,
    1,
    2,
    4,
    2,
    4,
    4,
    2,
    4,
    4,
    4,
    2,
    4,
    4,
    4,
    4,
    2,
    4,
    4,
    4,
    4,
    4,
    2,
    4,
    4,
    4,
    4,
    4,
    4,
    3,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    3,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    6,
    3,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    6,
    6,
    3,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    6,
    6,
    6,
    3,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    6,
    6,
    6,
    6,
]


def _diat2(na, esa, epa, r12, nb, esb, epb):
    """Overlaps for atoms with s,p basis of the first/second row.  Returns s[i][j][k] (1-based)."""
    st = _SetState()
    s = {}
    jmax = max(_INMB[na], _INMB[nb])
    jmin = min(_INMB[na], _INMB[nb])
    nbond = (jmax * (jmax - 1)) // 2 + jmin
    ii = _III[nbond]
    rab = r12 / A0
    a, b = st.a, st.b
    if ii == 1:
        _set(st, esa, esb, na, nb, rab, ii)
        s[(1, 1, 1)] = (
            0.25
            * math.sqrt((st.sa * st.sb * rab * rab) ** 3)
            * (a[3] * b[1] - b[3] * a[1])
        )
        return s
    if ii == 2:
        _set(st, esa, esb, na, nb, rab, ii)
        rab4 = rab**4 * 0.125
        w = math.sqrt(st.sa**3 * st.sb**5) * rab4
        v = math.sqrt(1.0 / 3.0)
        s[(1, 1, 1)] = w * v * (a[4] * b[1] - b[4] * a[1] + a[3] * b[2] - b[3] * a[2])
        if na > 1:
            _set(st, epa, esb, na, nb, rab, ii)
        if nb > 1:
            _set(st, esa, epb, na, nb, rab, ii)
        w = math.sqrt(st.sa**3 * st.sb**5) * rab4
        s[(st.isp, st.ips, 1)] = w * (
            a[3] * b[1] - b[3] * a[1] + a[4] * b[2] - b[4] * a[2]
        )
        return s
    if ii == 4:
        _set(st, esa, esb, na, nb, rab, ii)
        rab4 = rab**5 * 0.0625
        w = math.sqrt((st.sa * st.sb) ** 5) * rab4
        s[(1, 1, 1)] = w * (a[5] * b[1] + b[5] * a[1] - 2.0 * a[3] * b[3]) / 3.0
        _set(st, esa, epb, na, nb, rab, ii)
        if na > nb:
            _set(st, epa, esb, na, nb, rab, ii)
        w = math.sqrt((st.sa * st.sb) ** 5) * rab4
        rt3 = 1.0 / math.sqrt(3.0)
        d = a[4] * (b[1] - b[3]) - a[2] * (b[3] - b[5])
        e = b[4] * (a[1] - a[3]) - b[2] * (a[3] - a[5])
        s[(st.isp, st.ips, 1)] = w * rt3 * (d + e)
        _set(st, epa, esb, na, nb, rab, ii)
        if na > nb:
            _set(st, esa, epb, na, nb, rab, ii)
        w = math.sqrt((st.sa * st.sb) ** 5) * rab4
        d = a[4] * (b[1] - b[3]) - a[2] * (b[3] - b[5])
        e = b[4] * (a[1] - a[3]) - b[2] * (a[3] - a[5])
        s[(st.ips, st.isp, 1)] = w * rt3 * (d - e)
        _set(st, epa, epb, na, nb, rab, ii)
        w = math.sqrt((st.sa * st.sb) ** 5) * rab4
        s[(2, 2, 1)] = -w * (b[3] * (a[5] + a[1]) - a[3] * (b[5] + b[1]))
        s[(2, 2, 2)] = (
            0.5
            * w
            * (a[5] * (b[1] - b[3]) - b[5] * (a[1] - a[3]) - a[3] * b[1] + b[3] * a[1])
        )
        return s
    raise NotImplementedError("diat2 bond type %d" % ii)


# ---------------------------------------------------------------- rotation coefficients (coe)
def _coe(x2, y2, z2, norbi, norbj):
    rt34 = 0.86602540378444
    rt13 = 0.57735026918963
    xy = x2**2 + y2**2
    r = math.sqrt(xy + z2**2)
    xy = math.sqrt(xy)
    if xy >= 1e-10:
        ca = x2 / xy
        cb = z2 / r
        sa = y2 / xy
        sb = xy / r
    else:
        sa = sb = 0.0
        if z2 <= 0.0:
            if z2 != 0.0:
                ca = cb = -1.0
            else:
                ca = cb = 0.0
        else:
            ca = cb = 1.0
    c = [0.0] * 76  # 1-based linear c(75)
    nij = max(norbi, norbj)
    c[37] = 1.0
    if nij >= 2:
        c[56] = ca * cb
        c[41] = ca * sb
        c[26] = -sa
        c[53] = -sb
        c[38] = cb
        c[23] = 0.0
        c[50] = sa * cb
        c[35] = sa * sb
        c[20] = ca
        if nij >= 5:
            c2a = 2 * ca * ca - 1.0
            c2b = 2 * cb * cb - 1.0
            s2a = 2 * sa * ca
            s2b = 2 * sb * cb
            c[75] = c2a * cb * cb + 0.5 * c2a * sb * sb
            c[60] = 0.5 * c2a * s2b
            c[45] = rt34 * c2a * sb * sb
            c[30] = -s2a * sb
            c[15] = -s2a * cb
            c[72] = -0.5 * ca * s2b
            c[57] = ca * c2b
            c[42] = rt34 * ca * s2b
            c[27] = -sa * cb
            c[12] = sa * sb
            c[69] = rt13 * sb * sb * 1.5
            c[54] = -rt34 * s2b
            c[39] = cb * cb - 0.5 * sb * sb
            c[66] = -0.5 * sa * s2b
            c[51] = sa * c2b
            c[36] = rt34 * sa * s2b
            c[21] = ca * cb
            c[6] = -ca * sb
            c[63] = s2a * cb * cb + 0.5 * s2a * sb * sb
            c[48] = 0.5 * s2a * s2b
            c[33] = rt34 * s2a * sb * sb
            c[18] = c2a * sb
            c[3] = c2a * cb
    return c, r


_IVAL = {
    (1, 1): 1,
    (2, 1): 0,
    (3, 1): 9,
    (1, 2): 1,
    (2, 2): 3,
    (3, 2): 8,
    (1, 3): 1,
    (2, 3): 4,
    (3, 3): 7,
    (1, 4): 1,
    (2, 4): 2,
    (3, 4): 6,
    (1, 5): 0,
    (2, 5): 0,
    (3, 5): 5,
}


def diat(ni, nj, xj):
    """Overlap matrix between atoms ni (at origin) and nj (at xj).  Returns di[9,9] (0-based)."""
    ei, ej = ELEMENTS[ni], ELEMENTS[nj]
    di = np.zeros((9, 9))
    x2, y2, z2 = float(xj[0]), float(xj[1]), float(xj[2])
    pq1, pq2 = ei.npq[0], ej.npq[0]
    r2 = x2**2 + y2**2 + z2**2
    if pq1 == 0 or pq2 == 0 or r2 >= CUTOF1:
        return di
    if ei.natorb == 0 or ej.natorb == 0:
        return di
    c, r = _coe(x2, y2, z2, ei.natorb, ej.natorb)
    if r < 0.001:
        return di
    ia = min(pq1 + 1, 3)
    ib = min(pq2 + 1, 3)
    a = ia - 1
    b = ib - 1
    use2 = (ei.natorb < 5 and ni <= 17 and ni not in (2, 10)) and (
        ej.natorb < 5 and nj <= 17 and nj not in (2, 10)
    )
    s = {}
    if use2:
        s = _diat2(ni, ei.zs, ei.zp, r, nj, ej.zs, ej.zp)
    else:
        ul1 = [0.0, ei.zs, ei.zp, max(ei.zd, 0.3)]
        ul2 = [0.0, ej.zs, ej.zp, max(ej.zd, 0.3)]
        newk = min(a, b)
        nk1 = newk + 1
        for i in range(1, ia + 1):
            pq1i = ei.npq[i - 1]
            for j in range(1, ib + 1):
                pq2j = ej.npq[j - 1]
                for k in range(1, nk1 + 1):
                    if k > i or k > j:
                        continue
                    pi_ = max(pq1i, i)
                    pj_ = max(pq2j, j)
                    s[(i, j, k)] = ss(pi_, pj_, i, j, k, ul1[i], ul2[j], r)

    def S(k, i, j):
        return s.get((i, j, k), 0.0)

    def C(m, i, k):  # c(i,k,m) of c(3,5,5): linear index (i-1) + 3(k-1) + 15(m-1) + 1
        return c[(i - 1) + 3 * (k - 1) + 15 * (m - 1) + 1]

    for i in range(1, ia + 1):
        kmin = 4 - i
        kmax = 2 + i
        for j in range(1, ib + 1):
            if j == 2:
                aa, bb = -1.0, 1.0
            else:
                aa = 1.0
                bb = -1.0 if j == 3 else 1.0
            lmin = 4 - j
            lmax = 2 + j
            for k in range(kmin, kmax + 1):
                for l in range(lmin, lmax + 1):
                    iiv = _IVAL[(i, k)]
                    jjv = _IVAL[(j, l)]
                    di[iiv - 1, jjv - 1] = (
                        S(1, i, j) * (C(3, i, k) * C(3, j, l)) * aa
                        + S(2, i, j)
                        * (C(4, i, k) * C(4, j, l) + C(2, i, k) * C(2, j, l))
                        * bb
                        + S(3, i, j)
                        * (C(5, i, k) * C(5, j, l) + C(1, i, k) * C(1, j, l))
                    )
    return di


def h1elec(ni, nj, xi, xj):
    """Resonance block between atom ni at xi and nj at xj: returns (norbi, norbj) array."""
    ei, ej = ELEMENTS[ni], ELEMENTS[nj]
    rab = float(np.sum((np.asarray(xi) - np.asarray(xj)) ** 2))
    ni_, nj_ = ei.natorb, ej.natorb
    if rab > CUTOFS:
        return np.zeros((ni_, nj_))
    smat = diat(ni, nj, np.asarray(xj, float) - np.asarray(xi, float))
    bi = np.array([ei.betas] + [ei.betap] * 3 + [ei.betad] * 5) * 0.5
    bj = np.array([ej.betas] + [ej.betap] * 3 + [ej.betad] * 5) * 0.5
    out = smat[:ni_, :nj_] * (bi[:ni_, None] + bj[None, :nj_])
    return out
