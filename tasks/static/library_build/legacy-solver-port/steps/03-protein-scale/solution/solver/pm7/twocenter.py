"""Two-center two-electron integrals, core-electron attraction and core-core repulsion (PM7).

Ports (integrals/): reppd, reppd2, rijkl, charg, spcore, rotmat, rotatd (the rotation is done
as a generic tensor transformation instead of the hand-unrolled `tx`/`w2mat` loops), ccrep.

Conventions
-----------
* Atomic orbital order on an atom (molecular frame): s, px, py, pz, then d(x2-y2), d(xz),
  d(z2), d(yz), d(xy)  (MOPAC/diat order).
* Local (diatomic) frame order used by the multipole code: s, p_sigma, p_pi(x), p_pi(y),
  d_sigma(z2), d_pi(xz), d_pi(yz), d_delta(x2-y2), d_delta(xy)  (MOPAC `indexd` order).
* ``pair_integrals`` returns, for atoms i (first) and j (second):
      W[mu,nu,la,si]   (eV)  mu,nu on atom i, la,si on atom j
      Vi[mu,nu]        electrons of atom i attracted by the core of atom j (eV)
      Vj[la,si]        electrons of atom j attracted by the core of atom i (eV)
      enuc             core-core repulsion (eV)
"""

import math
from functools import lru_cache

import numpy as np

from . import pm7_data as D
from .constants import A0, EV, TRUNC_1, TRUNC_2
from .params import ELEMENTS, ALPB, XFAC, V_PAR

# ------------------------------------------------------------------ index tables
INDEXD = np.zeros((10, 10), dtype=int)  # 1-based
for _i in range(1, 10):
    for _j in range(1, _i + 1):
        INDEXD[_i, _j] = INDEXD[_j, _i] = -(_j * (_j - 1)) // 2 + _i + 9 * (_j - 1)
INDX = np.zeros((10, 10), dtype=int)
for _i in range(1, 10):
    for _j in range(1, _i + 1):
        INDX[_i, _j] = INDX[_j, _i] = (_i * (_i - 1)) // 2 + _j
LORB = [0, 0, 1, 1, 1, 2, 2, 2, 2, 2]  # 1-based: l of orbital
IPOS = [
    1,
    5,
    11,
    12,
    12,
    2,
    6,
    13,
    14,
    14,
    3,
    8,
    16,
    18,
    18,
    7,
    15,
    10,
    20,
    4,
    9,
    17,
    19,
    21,
    7,
    15,
    10,
    20,
    22,
    4,
    9,
    17,
    21,
    19,
]
NRI = [
    0,
    1,
    -1,
    1,
    1,
    -1,
    1,
    1,
    -1,
    -1,
    -1,
    1,
    1,
    -1,
    -1,
    -1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
]  # 1-based

CH = np.zeros((46, 3, 5))  # ch(ij, l, m): m index shifted by +2
for (_ij, _l, _m), _v in D.D_CH.items():
    CH[_ij, _l, _m + 2] = _v


def ev_point(r_ang):
    """to_point of mndod.F90: returns (point, const)."""
    point = EV * A0 / r_ang
    if r_ang < TRUNC_1:
        const = 1.0 - math.exp(-((r_ang - TRUNC_1) ** 2) * TRUNC_2)
    else:
        const = 0.0
    return point, const


# ------------------------------------------------------------------ sp multipole integrals (reppd)
def reppd(ni, nj, rij):
    """Return (ri[1..22] array of length 23, gab).  rij in Angstrom, feathered (PM7)."""
    ei, ej = ELEMENTS[ni], ELEMENTS[nj]
    ev1 = EV / 2
    ev2 = ev1 / 2
    ev3 = ev2 / 2
    ev4 = ev3 / 2
    ri = np.zeros(23)
    r = rij / A0
    si = ei.natorb >= 3
    sj = ej.natorb >= 3
    aee = ei.po[9] + ej.po[9]
    aee = aee * aee
    gab = EV / math.sqrt(r * r + aee)
    aee = 0.5 / ei.am + 0.5 / ej.am
    aee = aee * aee
    td = 2.0
    pp = 0.5
    sqrt = math.sqrt
    if not si and not sj:
        ri[1] = EV / sqrt(r * r + aee)
    elif si and not sj:
        da = ei.dd
        qa = ei.qq * td
        ade = pp / ei.ad + pp / ej.am
        ade = ade * ade
        aqe = pp / ei.aq + pp / ej.am
        aqe = aqe * aqe
        rsq = r * r
        a1 = rsq + aee
        xxx = r + da
        a2 = xxx * xxx + ade
        xxx = r - da
        a3 = xxx * xxx + ade
        xxx = r + qa
        a4 = xxx * xxx + aqe
        xxx = r - qa
        a5 = xxx * xxx + aqe
        a6 = rsq + aqe
        a7 = a6 + qa * qa
        s1, s2, s3, s4, s5, s6, s7 = (sqrt(x) for x in (a1, a2, a3, a4, a5, a6, a7))
        ee = EV / s1
        ri[1] = ee
        ri[2] = ev1 / s2 - ev1 / s3
        ri[3] = ee + ev2 / s4 + ev2 / s5 - ev1 / s6
        ri[4] = ee + ev1 / s7 - ev1 / s6
    elif not si and sj:
        db = ej.dd
        qb = ej.qq * td
        aed = pp / ei.am + pp / ej.ad
        aed = aed * aed
        aeq = pp / ei.am + pp / ej.aq
        aeq = aeq * aeq
        rsq = r * r
        a1 = rsq + aee
        xxx = r - db
        a2 = xxx * xxx + aed
        xxx = r + db
        a3 = xxx * xxx + aed
        xxx = r - qb
        a4 = xxx * xxx + aeq
        xxx = r + qb
        a5 = xxx * xxx + aeq
        a6 = rsq + aeq
        a7 = a6 + qb * qb
        s1, s2, s3, s4, s5, s6, s7 = (sqrt(x) for x in (a1, a2, a3, a4, a5, a6, a7))
        ee = EV / s1
        ri[1] = ee
        ri[5] = ev1 / s2 - ev1 / s3
        ri[11] = ee + ev2 / s4 + ev2 / s5 - ev1 / s6
        ri[12] = ee + ev1 / s7 - ev1 / s6
    else:
        da = ei.dd
        db = ej.dd
        qa = ei.qq * td
        qb = ej.qq * td
        ade = pp / ei.ad + pp / ej.am
        ade = ade * ade
        aqe = pp / ei.aq + pp / ej.am
        aqe = aqe * aqe
        aed = pp / ei.am + pp / ej.ad
        aed = aed * aed
        aeq = pp / ei.am + pp / ej.aq
        aeq = aeq * aeq
        axx = pp / ei.ad + pp / ej.ad
        axx = axx * axx
        adq = pp / ei.ad + pp / ej.aq
        adq = adq * adq
        aqd = pp / ei.aq + pp / ej.ad
        aqd = aqd * aqd
        aqq = pp / ei.aq + pp / ej.aq
        aqq = aqq * aqq
        rsq = r * r
        arg = [0.0] * 73
        arg[1] = rsq + aee
        xxx = r + da
        arg[2] = xxx * xxx + ade
        xxx = r - da
        arg[3] = xxx * xxx + ade
        xxx = r - qa
        arg[4] = xxx * xxx + aqe
        xxx = r + qa
        arg[5] = xxx * xxx + aqe
        arg[6] = rsq + aqe
        arg[7] = arg[6] + qa * qa
        xxx = r - db
        arg[8] = xxx * xxx + aed
        xxx = r + db
        arg[9] = xxx * xxx + aed
        xxx = r - qb
        arg[10] = xxx * xxx + aeq
        xxx = r + qb
        arg[11] = xxx * xxx + aeq
        arg[12] = rsq + aeq
        arg[13] = arg[12] + qb * qb
        xxx = da - db
        arg[14] = rsq + axx + xxx * xxx
        xxx = da + db
        arg[15] = rsq + axx + xxx * xxx
        xxx = r + da - db
        arg[16] = xxx * xxx + axx
        xxx = r - da + db
        arg[17] = xxx * xxx + axx
        xxx = r - da - db
        arg[18] = xxx * xxx + axx
        xxx = r + da + db
        arg[19] = xxx * xxx + axx
        xxx = r + da
        arg[20] = xxx * xxx + adq
        arg[21] = arg[20] + qb * qb
        xxx = r - da
        arg[22] = xxx * xxx + adq
        arg[23] = arg[22] + qb * qb
        xxx = r - db
        arg[24] = xxx * xxx + aqd
        arg[25] = arg[24] + qa * qa
        xxx = r + db
        arg[26] = xxx * xxx + aqd
        arg[27] = arg[26] + qa * qa
        xxx = r + da - qb
        arg[28] = xxx * xxx + adq
        xxx = r - da - qb
        arg[29] = xxx * xxx + adq
        xxx = r + da + qb
        arg[30] = xxx * xxx + adq
        xxx = r - da + qb
        arg[31] = xxx * xxx + adq
        xxx = r + qa - db
        arg[32] = xxx * xxx + aqd
        xxx = r + qa + db
        arg[33] = xxx * xxx + aqd
        xxx = r - qa - db
        arg[34] = xxx * xxx + aqd
        xxx = r - qa + db
        arg[35] = xxx * xxx + aqd
        arg[36] = rsq + aqq
        xxx = qa - qb
        arg[37] = arg[36] + xxx * xxx
        xxx = qa + qb
        arg[38] = arg[36] + xxx * xxx
        arg[39] = arg[36] + qa * qa
        arg[40] = arg[36] + qb * qb
        arg[41] = arg[39] + qb * qb
        xxx = r - qb
        arg[42] = xxx * xxx + aqq
        arg[43] = arg[42] + qa * qa
        xxx = r + qb
        arg[44] = xxx * xxx + aqq
        arg[45] = arg[44] + qa * qa
        xxx = r + qa
        arg[46] = xxx * xxx + aqq
        arg[47] = arg[46] + qb * qb
        xxx = r - qa
        arg[48] = xxx * xxx + aqq
        arg[49] = arg[48] + qb * qb
        xxx = r + qa - qb
        arg[50] = xxx * xxx + aqq
        xxx = r + qa + qb
        arg[51] = xxx * xxx + aqq
        xxx = r - qa - qb
        arg[52] = xxx * xxx + aqq
        xxx = r - qa + qb
        arg[53] = xxx * xxx + aqq
        qa = ei.qq
        qb = ej.qq
        xxx = da - qb
        xxx = xxx * xxx
        yyy = r - qb
        yyy = yyy * yyy
        zzz = da + qb
        zzz = zzz * zzz
        www = r + qb
        www = www * www
        arg[54] = xxx + yyy + adq
        arg[55] = xxx + www + adq
        arg[56] = zzz + yyy + adq
        arg[57] = zzz + www + adq
        xxx = qa - db
        xxx = xxx * xxx
        yyy = qa + db
        yyy = yyy * yyy
        zzz = r + qa
        zzz = zzz * zzz
        www = r - qa
        www = www * www
        arg[58] = zzz + xxx + aqd
        arg[59] = www + xxx + aqd
        arg[60] = zzz + yyy + aqd
        arg[61] = www + yyy + aqd
        xxx = qa - qb
        xxx = xxx * xxx
        arg[62] = arg[36] + td * xxx
        yyy = qa + qb
        yyy = yyy * yyy
        arg[63] = arg[36] + td * yyy
        arg[64] = arg[36] + td * (qa * qa + qb * qb)
        zzz = r + qa - qb
        zzz = zzz * zzz
        arg[65] = zzz + xxx + aqq
        arg[66] = zzz + yyy + aqq
        zzz = r + qa + qb
        zzz = zzz * zzz
        arg[67] = zzz + xxx + aqq
        arg[68] = zzz + yyy + aqq
        zzz = r - qa - qb
        zzz = zzz * zzz
        arg[69] = zzz + xxx + aqq
        arg[70] = zzz + yyy + aqq
        zzz = r - qa + qb
        zzz = zzz * zzz
        arg[71] = zzz + xxx + aqq
        arg[72] = zzz + yyy + aqq
        q = [0.0] + [sqrt(arg[i]) for i in range(1, 73)]
        ee = EV / q[1]
        dze = (-ev1 / q[2]) + ev1 / q[3]
        qzze = ev2 / q[4] + ev2 / q[5] - ev1 / q[6]
        qxxe = ev1 / q[7] - ev1 / q[6]
        edz = (-ev1 / q[8]) + ev1 / q[9]
        eqzz = ev2 / q[10] + ev2 / q[11] - ev1 / q[12]
        eqxx = ev1 / q[13] - ev1 / q[12]
        dxdx = ev1 / q[14] - ev1 / q[15]
        dzdz = ev2 / q[16] + ev2 / q[17] - ev2 / q[18] - ev2 / q[19]
        dzqxx = ev2 / q[20] - ev2 / q[21] - ev2 / q[22] + ev2 / q[23]
        qxxdz = ev2 / q[24] - ev2 / q[25] - ev2 / q[26] + ev2 / q[27]
        dzqzz = (
            (-ev3 / q[28])
            + ev3 / q[29]
            - ev3 / q[30]
            + ev3 / q[31]
            - ev2 / q[22]
            + ev2 / q[20]
        )
        qzzdz = (
            (-ev3 / q[32])
            + ev3 / q[33]
            - ev3 / q[34]
            + ev3 / q[35]
            + ev2 / q[24]
            - ev2 / q[26]
        )
        qxxqxx = ev3 / q[37] + ev3 / q[38] - ev2 / q[39] - ev2 / q[40] + ev2 / q[36]
        qxxqyy = ev2 / q[41] - ev2 / q[39] - ev2 / q[40] + ev2 / q[36]
        qxxqzz = (
            ev3 / q[43]
            + ev3 / q[45]
            - ev3 / q[42]
            - ev3 / q[44]
            - ev2 / q[39]
            + ev2 / q[36]
        )
        qzzqxx = (
            ev3 / q[47]
            + ev3 / q[49]
            - ev3 / q[46]
            - ev3 / q[48]
            - ev2 / q[40]
            + ev2 / q[36]
        )
        qzzqzz = (
            ev4 / q[50]
            + ev4 / q[51]
            + ev4 / q[52]
            + ev4 / q[53]
            - ev3 / q[48]
            - ev3 / q[46]
            - ev3 / q[42]
            - ev3 / q[44]
            + ev2 / q[36]
        )
        dxqxz = (-ev2 / q[54]) + ev2 / q[55] + ev2 / q[56] - ev2 / q[57]
        qxzdx = (-ev2 / q[58]) + ev2 / q[59] + ev2 / q[60] - ev2 / q[61]
        qxzqxz = (
            ev3 / q[65]
            - ev3 / q[67]
            - ev3 / q[69]
            + ev3 / q[71]
            - ev3 / q[66]
            + ev3 / q[68]
            + ev3 / q[70]
            - ev3 / q[72]
        )
        ri[1] = ee
        ri[2] = -dze
        ri[3] = ee + qzze
        ri[4] = ee + qxxe
        ri[5] = -edz
        ri[6] = dzdz
        ri[7] = dxdx
        ri[8] = (-edz) - qzzdz
        ri[9] = (-edz) - qxxdz
        ri[10] = -qxzdx
        ri[11] = ee + eqzz
        ri[12] = ee + eqxx
        ri[13] = (-dze) - dzqzz
        ri[14] = (-dze) - dzqxx
        ri[15] = -dxqxz
        ri[16] = ee + eqzz + qzze + qzzqzz
        ri[17] = ee + eqzz + qxxe + qxxqzz
        ri[18] = ee + eqxx + qzze + qzzqxx
        ri[19] = ee + eqxx + qxxe + qxxqxx
        ri[20] = qxzqxz
        ri[21] = ee + eqxx + qxxe + qxxqyy
        ri[22] = pp * (qxxqxx - qxxqyy)
    # l_feather (PM7)
    point, const = ev_point(rij)
    mixed = (1, 3, 4, 11, 12, 16, 17, 18, 19, 21)
    for k in range(1, 23):
        if k in mixed:
            ri[k] = ri[k] * const + (1.0 - const) * point
        else:
            ri[k] = ri[k] * const
    gab = gab * const + (1.0 - const) * point
    ri = ri * np.array(NRI, dtype=float)
    return ri, gab


# ------------------------------------------------------------------ d-orbital multipole integrals
def charg(r, l1, l2, m, da, db, add):
    sqrt = math.sqrt
    if l1 == 0 and l2 == 0:
        return 1.0 / sqrt(r**2 + add)
    if l1 == 1 and l2 == 0:
        return (
            -1.0 / sqrt((r + da) ** 2 + add) + 1.0 / sqrt((r - da) ** 2 + add)
        ) / 2.0
    if l1 == 0 and l2 == 1:
        return (1.0 / sqrt((r + db) ** 2 + add) - 1.0 / sqrt((r - db) ** 2 + add)) / 2.0
    if l1 == 1 and l2 == 1 and m == 0:
        dzdz = (
            1.0 / sqrt((r + da - db) ** 2 + add)
            + 1.0 / sqrt((r - da + db) ** 2 + add)
            - 1.0 / sqrt((r - da - db) ** 2 + add)
            - 1.0 / sqrt((r + da + db) ** 2 + add)
        )
        return dzdz / 4.0
    if l1 == 1 and l2 == 1 and m == 1:
        dxdx = 2.0 / sqrt(r**2 + (da - db) ** 2 + add) - 2.0 / sqrt(
            r**2 + (da + db) ** 2 + add
        )
        return dxdx * 0.25
    if l1 == 0 and l2 == 2:
        qqzz = (
            1.0 / sqrt((r - db) ** 2 + add)
            - 2.0 / sqrt(r**2 + db**2 + add)
            + 1.0 / sqrt((r + db) ** 2 + add)
        )
        return qqzz / 4.0
    if l1 == 2 and l2 == 0:
        qzzq = (
            1.0 / sqrt((r - da) ** 2 + add)
            - 2.0 / sqrt(r**2 + da**2 + add)
            + 1.0 / sqrt((r + da) ** 2 + add)
        )
        return qzzq / 4.0
    if l1 == 1 and l2 == 2 and m == 0:
        dzqzz = (
            1.0 / sqrt((r - da - db) ** 2 + add)
            - 2.0 / sqrt((r - da) ** 2 + db**2 + add)
            + 1.0 / sqrt((r + db - da) ** 2 + add)
            - 1.0 / sqrt((r - db + da) ** 2 + add)
            + 2.0 / sqrt((r + da) ** 2 + db**2 + add)
            - 1.0 / sqrt((r + da + db) ** 2 + add)
        )
        return dzqzz / 8.0
    if l1 == 2 and l2 == 1 and m == 0:
        qzzdz = (
            -1.0 / sqrt((r - da - db) ** 2 + add)
            + 2.0 / sqrt((r - db) ** 2 + da**2 + add)
            - 1.0 / sqrt((r + da - db) ** 2 + add)
            + 1.0 / sqrt((r - da + db) ** 2 + add)
            - 2.0 / sqrt((r + db) ** 2 + da**2 + add)
            + 1.0 / sqrt((r + da + db) ** 2 + add)
        )
        return qzzdz / 8.0
    if l1 == 2 and l2 == 2 and m == 0:
        zzzz = (
            1.0 / sqrt((r - da - db) ** 2 + add)
            + 1.0 / sqrt((r + da + db) ** 2 + add)
            + 1.0 / sqrt((r - da + db) ** 2 + add)
            + 1.0 / sqrt((r + da - db) ** 2 + add)
            - 2.0 / sqrt((r - da) ** 2 + db**2 + add)
            - 2.0 / sqrt((r - db) ** 2 + da**2 + add)
            - 2.0 / sqrt((r + da) ** 2 + db**2 + add)
            - 2.0 / sqrt((r + db) ** 2 + da**2 + add)
            + 2.0 / sqrt(r**2 + (da - db) ** 2 + add)
            + 2.0 / sqrt(r**2 + (da + db) ** 2 + add)
        )
        xyxy = (
            4.0 / sqrt(r**2 + (da - db) ** 2 + add)
            + 4.0 / sqrt(r**2 + (da + db) ** 2 + add)
            - 8.0 / sqrt(r**2 + da**2 + db**2 + add)
        )
        return zzzz / 16.0 - xyxy / 64.0
    if l1 == 1 and l2 == 2 and m == 1:
        ab = db / sqrt(2.0)
        dxqxz = (
            -2.0 / sqrt((r - ab) ** 2 + (da - ab) ** 2 + add)
            + 2.0 / sqrt((r + ab) ** 2 + (da - ab) ** 2 + add)
            + 2.0 / sqrt((r - ab) ** 2 + (da + ab) ** 2 + add)
            - 2.0 / sqrt((r + ab) ** 2 + (da + ab) ** 2 + add)
        )
        return dxqxz / 8.0
    if l1 == 2 and l2 == 1 and m == 1:
        aa = da / sqrt(2.0)
        qxzdx = (
            -2.0 / sqrt((r + aa) ** 2 + (aa - db) ** 2 + add)
            + 2.0 / sqrt((r - aa) ** 2 + (aa - db) ** 2 + add)
            + 2.0 / sqrt((r + aa) ** 2 + (aa + db) ** 2 + add)
            - 2.0 / sqrt((r - aa) ** 2 + (aa + db) ** 2 + add)
        )
        return qxzdx / 8.0
    if l1 == 2 and l2 == 2 and m == 1:
        aa = da / sqrt(2.0)
        ab = db / sqrt(2.0)
        qxzqxz = (
            2.0 / sqrt((r + aa - ab) ** 2 + (aa - ab) ** 2 + add)
            - 2.0 / sqrt((r + aa + ab) ** 2 + (aa - ab) ** 2 + add)
            - 2.0 / sqrt((r - aa - ab) ** 2 + (aa - ab) ** 2 + add)
            + 2.0 / sqrt((r - aa + ab) ** 2 + (aa - ab) ** 2 + add)
            - 2.0 / sqrt((r + aa - ab) ** 2 + (aa + ab) ** 2 + add)
            + 2.0 / sqrt((r + aa + ab) ** 2 + (aa + ab) ** 2 + add)
            + 2.0 / sqrt((r - aa - ab) ** 2 + (aa + ab) ** 2 + add)
            - 2.0 / sqrt((r - aa + ab) ** 2 + (aa + ab) ** 2 + add)
        )
        return qxzqxz / 16.0
    if l1 == 2 and l2 == 2 and m == 2:
        xyxy = (
            4.0 / sqrt(r**2 + (da - db) ** 2 + add)
            + 4.0 / sqrt(r**2 + (da + db) ** 2 + add)
            - 8.0 / sqrt(r**2 + da**2 + db**2 + add)
        )
        return xyxy / 16.0
    return 0.0


def rijkl(ei, ej, ij, kl, li, lj, lk, ll, ic, r):
    """Local-frame two-center integral (without the eV factor).  r in bohr."""
    pij = pkl = 0.0
    dij = dkl = 0.0
    l1min = abs(li - lj)
    l1max = li + lj
    lij = INDX[li + 1, lj + 1]
    l2min = abs(lk - ll)
    l2max = lk + ll
    lkl = INDX[lk + 1, ll + 1]
    l1max = min(l1max, 2)
    l1min = min(l1min, 2)
    l2max = min(l2max, 2)
    l2min = min(l2min, 2)
    total = 0.0
    for l1 in range(l1min, l1max + 1):
        if l1 == 0:
            if lij == 1:
                pij = ei.po[9] if ic == 1 else ei.po[1]
            elif lij == 3:
                pij = ei.po[7]
            elif lij == 6:
                pij = ei.po[8]
        else:
            dij = ei.ddp[lij]
            pij = ei.po[lij]
        for l2 in range(l2min, l2max + 1):
            if l2 == 0:
                if lkl == 1:
                    pkl = ej.po[9] if ic == 2 else ej.po[1]
                elif lkl == 3:
                    pkl = ej.po[7]
                elif lkl == 6:
                    pkl = ej.po[8]
            else:
                dkl = ej.ddp[lkl]
                pkl = ej.po[lkl]
            add = (pij + pkl) ** 2
            lmin = min(l1, l2)
            s1 = 0.0
            for m in range(-lmin, lmin + 1):
                ccc = CH[ij, l1, m + 2] * CH[kl, l2, m + 2]
                if ccc == 0.0:
                    continue
                s1 += charg(r, l1, l2, abs(m), dij, dkl, add) * ccc
            total += s1
    return total


@lru_cache(maxsize=None)
def _plan(na, nb):
    """Loop plan of reppd2 for orbital counts (na, nb): ordered list of rep entries and the
    local-tensor fill map."""
    lasti, lastk = na, nb
    entries = []  # (numb, nold, i,j,k,l, ij, kl)
    fill = []  # (a,b,c,d, numb) 0-based orbital indices, all index permutations
    for i in range(1, lasti + 1):
        for j in range(1, i + 1):
            ij = INDEXD[i, j]
            for k in range(1, lastk + 1):
                for l in range(1, k + 1):
                    kl = INDEXD[k, l]
                    numb = D.D_IND2.get((int(ij), int(kl)), 0)
                    if numb == 0:
                        continue
                    for a, b in {(i, j), (j, i)}:
                        for c, d in {(k, l), (l, k)}:
                            fill.append((a - 1, b - 1, c - 1, d - 1, numb))
                    if numb <= 34:
                        continue
                    nold = D.D_ISYM.get(numb, 0)
                    entries.append((numb, nold, i, j, k, l, int(ij), int(kl)))
    fa = np.array([f[0] for f in fill], dtype=int)
    fb = np.array([f[1] for f in fill], dtype=int)
    fc = np.array([f[2] for f in fill], dtype=int)
    fd = np.array([f[3] for f in fill], dtype=int)
    fn = np.array([f[4] for f in fill], dtype=int)
    return entries, (fa, fb, fc, fd, fn)


def local_tensor(ei, ej, ri, r_au, r_ang):
    """Local-frame tensor L[a,b,c,d] (eV) for atoms with orbital counts natorb."""
    na, nb = ei.natorb, ej.natorb
    entries, (fa, fb, fc, fd, fn) = _plan(na, nb)
    rep = np.zeros(492)
    for n in range(1, 35):
        rep[n] = ri[IPOS[n - 1]]
    if entries:
        point, const = ev_point(r_ang)
        for numb, nold, i, j, k, l, ij, kl in entries:
            if nold >= 35:
                rep[numb] = rep[nold]
            elif nold <= -35:
                rep[numb] = -rep[-nold]
            elif nold == 0:
                v = (
                    rijkl(ei, ej, ij, kl, LORB[i], LORB[j], LORB[k], LORB[l], 0, r_au)
                    * EV
                )
                coulomb = i == j and k == l
                if coulomb:
                    v = v * const + (1.0 - const) * point
                else:
                    v = v * const
                rep[numb] = v
    L = np.zeros((na, na, nb, nb))
    L[fa, fb, fc, fd] = rep[fn]
    return L


# ------------------------------------------------------------------ core-electron attraction
def spcore(ei, ej, r):
    """Core attraction terms in the local frame (eV), r in bohr.  Returns cored[1..10][1..2]."""
    ni, nj = ei.z, ej.z
    core = np.zeros((11, 3))
    sqrt = math.sqrt
    r2 = r * r
    aci = ei.po[9]
    acj = ej.po[9]
    ssi = (aci + ej.po[1]) ** 2
    ssj = (acj + ei.po[1]) ** 2
    core[1, 1] = -ej.tore * EV / sqrt(r2 + ssj)
    core[1, 2] = -ei.tore * EV / sqrt(r2 + ssi)
    pxy = [0.0, 1.0, -0.5, -0.5, 0.5, 0.25, 0.25, 0.5]
    if ni >= 3 or nj >= 3:
        if ni >= 3:
            ppj = (acj + ei.po[7]) ** 2
            da = ei.ddp[2]
            qa = ei.ddp[3] / sqrt(2.0)
            twoqa = qa + qa
            adj = (ei.po[2] + acj) ** 2
            aqj = (ei.po[3] + acj) ** 2
            xj = [0.0] * 8
            xj[1] = r2 + ppj
            xj[2] = r2 + aqj
            xj[3] = (r + da) ** 2 + adj
            xj[4] = (r - da) ** 2 + adj
            xj[5] = (r - twoqa) ** 2 + aqj
            xj[6] = (r + twoqa) ** 2 + aqj
            xj[7] = r2 + twoqa * twoqa + aqj
            for i in range(1, 8):
                xj[i] = pxy[i] / sqrt(xj[i])
            aj2 = (xj[3] + xj[4]) * EV
            aj3 = (xj[1] + xj[2] + xj[5] + xj[6]) * EV
            aj4 = (xj[1] + xj[2] + xj[7]) * EV
            core[2, 1] = -ej.tore * aj2
            core[3, 1] = -ej.tore * aj3
            core[4, 1] = -ej.tore * aj4
        if nj >= 3:
            ppi = (aci + ej.po[7]) ** 2
            db = ej.ddp[2]
            qb = ej.ddp[3] / sqrt(2.0)
            adi = (ej.po[2] + aci) ** 2
            aqi = (ej.po[3] + aci) ** 2
            twoqb = qb + qb
            xi = [0.0] * 8
            xi[1] = r2 + ppi
            xi[2] = r2 + aqi
            xi[3] = (r + db) ** 2 + adi
            xi[4] = (r - db) ** 2 + adi
            xi[5] = (r - twoqb) ** 2 + aqi
            xi[6] = (r + twoqb) ** 2 + aqi
            xi[7] = r2 + twoqb * twoqb + aqi
            for i in range(1, 8):
                xi[i] = pxy[i] / sqrt(xi[i])
            ai2 = -(xi[3] + xi[4]) * EV
            ai3 = (xi[1] + xi[2] + xi[5] + xi[6]) * EV
            ai4 = (xi[1] + xi[2] + xi[7]) * EV
            core[2, 2] = -ei.tore * ai2
            core[3, 2] = -ei.tore * ai3
            core[4, 2] = -ei.tore * ai4
    return core


def _core_d(ei, ej, r, core):
    """Port of the core(5:10, .) block of reppd2.  r in bohr."""
    lp = [
        (5, 1, 0),
        (5, 2, 1),
        (5, 5, 2),
        (6, 3, 1),
        (6, 6, 2),
        (8, 8, 2),
    ]  # (o1, o2, l_o2)
    if ej.dorbs:
        for n, (o1, o2, l2) in enumerate(lp):
            kl = int(INDEXD[o1, o2])
            core[5 + n, 2] = -rijkl(ei, ej, 1, kl, 0, 0, 2, l2, 1, r) * EV * ei.tore
    if ei.dorbs:
        for n, (o1, o2, l2) in enumerate(lp):
            kl = int(INDEXD[o1, o2])
            core[5 + n, 1] = -rijkl(ei, ej, kl, 1, 2, l2, 0, 0, 2, r) * EV * ej.tore


# ------------------------------------------------------------------ rotation
def rotation_blocks(dvec, want_d):
    """Local -> molecular orbital transformation R (9x9 block diagonal), R[loc, mol].
    dvec = coord_j - coord_i (Angstrom).  Port of rotmat."""
    small = 1.0e-7
    pt5sq3 = 0.8660254037841
    x11, x22, x33 = dvec
    b = x11 * x11 + x22 * x22
    r = math.sqrt(b + x33 * x33)
    sqb = math.sqrt(b)
    sb = sqb / r
    if sb > small:
        ca = x11 / sqb
        sa = x22 / sqb
        cb = x33 / r
    else:
        sa = 0.0
        sb = 0.0
        if x33 < 0.0:
            ca = -1.0
            cb = -1.0
        elif x33 > 0.0:
            ca = 1.0
            cb = 1.0
        else:
            ca = 0.0
            cb = 0.0
    p = np.zeros((3, 3))
    p[0, 0] = ca * sb
    p[1, 0] = ca * cb
    p[2, 0] = -sa
    p[0, 1] = sa * sb
    p[1, 1] = sa * cb
    p[2, 1] = ca
    p[0, 2] = cb
    p[1, 2] = -sb
    p[2, 2] = 0.0
    R = np.zeros((9, 9))
    R[0, 0] = 1.0
    R[1:4, 1:4] = p
    if want_d:
        c2a = 2.0 * ca * ca - 1.0
        c2b = 2.0 * cb * cb - 1.0
        s2a = 2.0 * sa * ca
        s2b = 2.0 * sb * cb
        d = np.zeros((5, 5))
        d[0, 0] = pt5sq3 * c2a * sb * sb
        d[1, 0] = 0.5 * c2a * s2b
        d[2, 0] = -s2a * sb
        d[3, 0] = c2a * (cb * cb + 0.5 * sb * sb)
        d[4, 0] = -s2a * cb
        d[0, 1] = pt5sq3 * ca * s2b
        d[1, 1] = ca * c2b
        d[2, 1] = -sa * cb
        d[3, 1] = -0.5 * ca * s2b
        d[4, 1] = sa * sb
        d[0, 2] = cb * cb - 0.5 * sb * sb
        d[1, 2] = -pt5sq3 * s2b
        d[2, 2] = 0.0
        d[3, 2] = pt5sq3 * sb * sb
        d[4, 2] = 0.0
        d[0, 3] = pt5sq3 * sa * s2b
        d[1, 3] = sa * c2b
        d[2, 3] = ca * cb
        d[3, 3] = -0.5 * sa * s2b
        d[4, 3] = -ca * sb
        d[0, 4] = pt5sq3 * s2a * sb * sb
        d[1, 4] = 0.5 * s2a * s2b
        d[2, 4] = c2a * sb
        d[3, 4] = s2a * (cb * cb + 0.5 * sb * sb)
        d[4, 4] = c2a * cb
        R[4:9, 4:9] = d
    return R


# ------------------------------------------------------------------ core-core repulsion
def ccrep(ni, nj, r_ang, gab):
    """Core-core repulsion (eV), PM7 form.  r in Angstrom, gab from reppd (eV)."""
    ei, ej = ELEMENTS[ni], ELEMENTS[nj]
    par1, par2, par3, par4 = V_PAR[1], V_PAR[2], V_PAR[3], V_PAR[4]
    r = r_ang
    enuc = ei.tore * ej.tore * gab
    fff = XFAC.get((ni, nj), 0.0)
    abond = ALPB.get((ni, nj), 0.0)
    if abs(fff) < 1e-5:
        # PM7: poor guess of the pair parameters from the diagonal ones
        fff = 0.5 * (XFAC.get((ni, ni), 0.0) + XFAC.get((nj, nj), 0.0))
        abond = 0.5 * (ALPB.get((ni, ni), 0.0) + ALPB.get((nj, nj), 0.0))
    scale = 0.0
    if abs(fff) > 1e-5:
        if abond < 1e-6:
            abond = 1.2
        scale = 1.0 + 2.0 * fff * math.exp(-abond * (r + 0.0003 * r**6))
        i = max(ni, nj)
        j = min(ni, nj)
        if j == 1:
            if i in (6, 7):
                scale = 1.0 + 2.0 * fff * math.exp(-abond * r**2)
            elif i == 8:
                scale = (
                    1.0
                    + 2.0 * fff * math.exp(-abond * r**2)
                    - par3 * math.exp(-par4 * r * 2)
                )
        elif j == 6:
            if i == 6:
                scale = scale + par1 * math.exp(-par2 * r)
        elif j == 8:
            if i == 14:
                scale = scale - 0.7e-3 * math.exp(-((r - 2.9) ** 2))
        enuclr = enuc * scale
    else:
        abond = 0.0
        scale = 10.0 * math.exp(-2.18 * r)
        enuclr = abs(scale * enuc) + enuc
    # van der Waals-like gaussian terms
    scale = 0.0
    ax = ei.guess2[0] * (r - ei.guess3[0]) ** 2
    if ax < 25.0:
        scale += ei.tore * ej.tore / r * ei.guess1[0] * math.exp(-ax)
    ax = ej.guess2[0] * (r - ej.guess3[0]) ** 2
    if ax < 25.0:
        scale += ei.tore * ej.tore / r * ej.guess1[0] * math.exp(-ax)
    ng = 0 if abond > 1e-4 else 4
    for ig in range(ng):
        if abs(ei.guess1[ig]) > 0.0:
            ax = ei.guess2[ig] * (r - ei.guess3[ig]) ** 2
            if ax <= 25.0:
                scale += ei.tore * ej.tore / r * ei.guess1[ig] * math.exp(-ax)
        if abs(ej.guess1[ig]) <= 0.0:
            continue
        ax = ej.guess2[ig] * (r - ej.guess3[ig]) ** 2
        if ax > 25.0:
            continue
        scale += ei.tore * ej.tore / r * ej.guess1[ig] * math.exp(-ax)
    enuclr += scale
    ax = r / (ni**0.3333 + nj**0.3333)
    if ax < 3.0:
        sc = 1.0e-8 / ax**12
        enuclr += min(sc, 1.0e5)
    return enuclr


# ------------------------------------------------------------------ driver
def pair_integrals(ni, nj, xi, xj):
    """Two-center integrals for atom i (atomic number ni, position xi) and atom j.
    Returns W (na,na,nb,nb), Vi (na,na), Vj (nb,nb), enuc."""
    ei, ej = ELEMENTS[ni], ELEMENTS[nj]
    xi = np.asarray(xi, float)
    xj = np.asarray(xj, float)
    dvec = xj - xi
    rij2 = float(dvec @ dvec)
    na, nb = ei.natorb, ej.natorb
    if rij2 < 0.00002:
        return np.zeros((na, na, nb, nb)), np.zeros((na, na)), np.zeros((nb, nb)), 0.0
    r_ang = math.sqrt(rij2)
    ri, gab = reppd(ni, nj, r_ang)
    r_au = r_ang / A0
    core = spcore(ei, ej, r_au)
    L = local_tensor(ei, ej, ri, r_au, r_ang)
    if ei.dorbs or ej.dorbs:
        _core_d(ei, ej, r_au, core)
    point, const = ev_point(r_ang)
    pt1 = -(EV / r_au) * ej.tore
    pt2 = -(EV / r_au) * ei.tore
    mixed = (1, 3, 4, 7, 9, 10)
    for k in range(1, 11):
        if k in mixed:
            core[k, 1] = core[k, 1] * const + (1.0 - const) * pt1
            core[k, 2] = core[k, 2] * const + (1.0 - const) * pt2
        else:
            core[k, 1] = core[k, 1] * const
            core[k, 2] = core[k, 2] * const
    R = rotation_blocks(dvec, ei.dorbs or ej.dorbs)
    Ra = R[:na, :na]
    Rb = R[:nb, :nb]
    W = np.einsum("abcd,am,bn,cl,ds->mnls", L, Ra, Ra, Rb, Rb, optimize=True)
    Vi = _core_matrix(core[:, 1], na, Ra)
    Vj = _core_matrix(core[:, 2], nb, Rb)
    enuc = ccrep(ni, nj, r_ang, gab)
    return W, Vi, Vj, enuc


def _core_matrix(c, n, R):
    """Local-frame core-attraction operator -> molecular frame.  c = cored[1..10]."""
    V = np.zeros((n, n))
    V[0, 0] = c[1]
    if n > 1:
        V[0, 1] = V[1, 0] = c[2]
        V[1, 1] = c[3]
        V[2, 2] = V[3, 3] = c[4]
    if n > 4:
        V[0, 4] = V[4, 0] = c[5]
        V[1, 4] = V[4, 1] = c[6]
        V[4, 4] = c[7]
        V[2, 5] = V[5, 2] = c[8]
        V[3, 6] = V[6, 3] = c[8]
        V[5, 5] = V[6, 6] = c[9]
        V[7, 7] = V[8, 8] = c[10]
    return R.T @ V @ R
