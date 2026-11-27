"""Post-SCF and molecular-mechanics energy corrections of PM7 (kcal/mol) and their gradients.

Ports (corrections/, compfg.F90, set_up_dentate.F90, moldat.F90):
  * PM6_DH_Dispersion  (dispersion, PM7 constants)
  * Hydrogen_bond_corrections / all_h_bonds / setup_DH_Plus / EH_plus   (PM7 hydrogen bonds)
  * C_triple_bond_C (+ analytic derivative)
  * N-H-C=O dihedral molecular-mechanics term (setup_nhco, htype(PM7) = 3.1595)
The geometry-dependent helpers dihed/dang/bangle replicate MOPAC's conventions.
"""

import math

import numpy as np

from .constants import A0, EV, FPC_9, PI
from .system import connectivity


# ------------------------------------------------------------------ geometry helpers
def bangle(xyz, i, j, k):
    d2ij = float(np.sum((xyz[i] - xyz[j]) ** 2))
    d2jk = float(np.sum((xyz[j] - xyz[k]) ** 2))
    d2ik = float(np.sum((xyz[i] - xyz[k]) ** 2))
    xy = math.sqrt(d2ij * d2jk)
    if xy < 1e-20:
        return 0.0
    temp = 0.5 * (d2ij + d2jk - d2ik) / xy
    temp = min(1.0, temp)
    temp = max(-1.0, temp)
    return math.acos(temp)


def _dang(a1, a2, b1, b2):
    zero = 1.0e-6
    if abs(a1) >= zero or abs(a2) >= zero:
        if abs(b1) >= zero or abs(b2) >= zero:
            anorm = 1.0 / math.sqrt(a1**2 + a2**2)
            bnorm = 1.0 / math.sqrt(b1**2 + b2**2)
            a1 *= anorm
            a2 *= anorm
            b1 *= bnorm
            b2 *= bnorm
            sinth = a1 * b2 - a2 * b1
            costh = a1 * b1 + a2 * b2
            costh = min(1.0, costh)
            costh = max(-1.0, costh)
            rcos = math.acos(costh)
            if abs(rcos) >= 4.0e-5:
                if sinth > 0.0:
                    rcos = 6.28318530717959 - rcos
                rcos = -rcos
                return rcos
    return 0.0


def dihed(xyz, i, j, k, l):
    """Dihedral angle i-j-k-l in [0, 2 pi) with MOPAC's sign convention (non-periodic)."""
    xi1, yi1, zi1 = xyz[i] - xyz[k]
    xj1, yj1, zj1 = xyz[j] - xyz[k]
    xl1, yl1, zl1 = xyz[l] - xyz[k]
    dist = math.sqrt(xj1 * xj1 + yj1 * yj1 + zj1 * zj1)
    cosa = zj1 / dist
    cosa = min(1.0, cosa)
    cosa = max(-1.0, cosa)
    ddd = 1.0 - cosa**2
    yxdist = dist * math.sqrt(ddd) if ddd > 0.0 else 0.0
    if ddd <= 0.0 or yxdist <= 1.0e-6:
        xi2, xl2, yi2, yl2 = xi1, xl1, yi1, yl1
        costh = cosa
        sinth = 0.0
    else:
        cosph = yj1 / yxdist
        sinph = xj1 / yxdist
        xi2 = xi1 * cosph - yi1 * sinph
        xl2 = xl1 * cosph - yl1 * sinph
        yi2 = xi1 * sinph + yi1 * cosph
        yj2 = xj1 * sinph + yj1 * cosph
        yl2 = xl1 * sinph + yl1 * cosph
        costh = cosa
        sinth = yj2 / dist
    yi3 = yi2 * costh - zi1 * sinth
    yl3 = yl2 * costh - zl1 * sinth
    angle = _dang(xl2, yl3, xi2, yi3)
    if angle < 0.0:
        angle = PI * 2.0 + angle
    if angle >= 6.28318530717959:
        angle = 0.0
    return angle


# ------------------------------------------------------------------ dispersion
_C6 = {
    1: 0.16,
    6: 1.65,
    7: 1.11,
    8: 0.70,
    9: 0.57,
    15: 3.25,
    16: 5.79,
    17: 5.97,
    35: 11.60,
}
_R0 = {
    1: 156.0,
    6: 170.0,
    7: 155.0,
    8: 152.0,
    9: 147.0,
    15: 180.0,
    16: 180.0,
    17: 175.0,
    35: 185.0,
}
_NEFF = {
    1: 0.80,
    6: 2.50,
    7: 2.82,
    8: 3.15,
    9: 3.48,
    15: 4.50,
    16: 4.80,
    17: 5.10,
    35: 6.00,
}
_ALPHA, _S, _CSCALE = 15.450118, 1.226593, 2.286419


def dispersion_atom(z, xyz, nbonds, k):
    """Dispersion energy of atom k with all other atoms (PM6_DH_Disp(k,1)), kcal/mol, times cscale."""
    return _disp(z, xyz, nbonds, [k], all_pairs=False)


def dispersion_total(z, xyz, nbonds):
    return _disp(z, xyz, nbonds, list(range(len(z))), all_pairs=True)


def _disp(z, xyz, nbonds, atoms, all_pairs):
    e = 0.0
    n = len(z)
    for ii, i in enumerate(atoms):
        ni = z[i]
        j_start = ii + 1 if all_pairs else 0
        for j in range(j_start, n):
            if i == j:
                continue
            nj = z[j]
            c6i = (0.95 if nbonds[i] == 4 else 1.65) if ni == 6 else _C6[ni]
            c6j = (0.95 if nbonds[j] == 4 else 1.65) if nj == 6 else _C6[nj]
            ni_, nj_ = _NEFF[ni], _NEFF[nj]
            c6 = (
                2.0
                * (c6i**2 * c6j**2 * ni_ * nj_) ** (1.0 / 3.0)
                / ((c6i * nj_**2) ** (1.0 / 3.0) + (c6j * ni_**2) ** (1.0 / 3.0))
            )
            r0 = (
                (_R0[ni] ** 3 + _R0[nj] ** 3)
                / (_R0[ni] ** 2 + _R0[nj] ** 2)
                / 1000.0
                * 2.0
            )
            d2 = float(np.sum((xyz[i] - xyz[j]) ** 2))
            if d2 < 100.0**2:
                rij = math.sqrt(d2) * 0.1
                damp = 1.0 / (1.0 + math.exp(-_ALPHA * (rij / (_S * r0) - 1.0)))
                e -= c6 / rij**6 * damp / (1000.0 * 4.184)
    return e * _CSCALE


def dispersion_gradient(z, xyz, nbonds, delta=1.0e-5):
    """Forward-difference gradient exactly as PM6_DH_Dispersion does."""
    n = len(z)
    g = np.zeros((n, 3))
    xyz = xyz.copy()
    for k in range(n):
        sum2 = dispersion_atom(z, xyz, nbonds, k)
        for i in range(3):
            xyz[k, i] += delta
            s = dispersion_atom(z, xyz, nbonds, k)
            sum1 = (sum2 - s) / delta
            if abs(sum1) < 50.0:
                g[k, i] -= sum1
            xyz[k, i] -= delta
    return g


# ------------------------------------------------------------------ hydrogen bonds (PM7)
_COVRAD = [
    0.32,
    0.46,
    1.20,
    0.94,
    0.77,
    0.75,
    0.71,
    0.63,
    0.64,
    0.67,
    1.40,
    1.25,
    1.13,
    1.04,
    1.10,
    1.02,
    0.99,
    0.96,
    1.76,
    1.54,
    1.33,
    1.22,
    1.21,
    1.10,
    1.07,
    1.04,
    1.00,
    0.99,
    1.01,
    1.09,
    1.12,
    1.09,
    1.15,
    1.10,
    1.14,
    1.17,
]
COVRAD = {zz: 4.0 / 3.0 * _COVRAD[zz - 1] for zz in range(1, 37)}


def _dist(xyz, a, b):
    return math.sqrt(float(np.sum((xyz[a] - xyz[b]) ** 2)))


class HBondList:
    """hblist of MOPAC: for each hydrogen bond the atoms (0-based, -1 = unset) plus bond counts."""

    def __init__(self):
        self.rows = []  # each: dict with keys a(1..10 as list of len 10), nra, nrb

    def __len__(self):
        return len(self.rows)


def find_hbonds(z, xyz):
    n = len(z)
    # find_XH_bonds
    rah = 1.4
    acc = []
    hb = []
    used = [False] * n
    for i in range(n):
        if z[i] in (7, 8):
            acc.append(i)
            for j in range(n):
                if z[j] == 1 and not used[j]:
                    if float(np.sum((xyz[i] - xyz[j]) ** 2)) < rah**2:
                        hb.append(j)
                        used[j] = True
    # find_H__Y_bonds
    cutoff = 7.0
    pairs = []  # (i=donor X, j=H, k=acceptor Y)
    for i in acc:
        for j in hb:
            if float(np.sum((xyz[i] - xyz[j]) ** 2)) < rah**2:
                for k in acc:
                    if k == i:
                        continue
                    if float(np.sum((xyz[k] - xyz[i]) ** 2)) < cutoff**2:
                        if bangle(xyz, k, j, i) > PI * 0.5:
                            if any(
                                p[1] == j and p[0] == k and p[2] == i for p in pairs
                            ):
                                continue
                            if any(
                                p[1] == j and p[0] == i and p[2] == k for p in pairs
                            ):
                                continue
                            pairs.append((i, j, k))
    return pairs


def setup_dh_plus(z, xyz, pairs):
    rows = []
    n = len(z)

    def bonding(x, y):
        return COVRAD[z[x]] + COVRAD[z[y]]

    for A, H, B in pairs:
        hb = [-1] * 11  # 1-based columns 1..10
        hb[1], hb[9], hb[5] = A, H, B
        bl1, bl2 = [], []
        for j in range(n):
            xa = _dist(xyz, j, A)
            xb = _dist(xyz, j, B)
            if xa < bonding(j, A) and A != j:
                bl1.append(j)
                if len(bl1) == 5:
                    s = 0.0
                    l = -1
                    for kk in range(5):
                        s1 = _dist(xyz, A, bl1[kk])
                        if s < s1:
                            s = s1
                            l = kk
                    del bl1[l]
            if xb < bonding(j, B) and B != j:
                bl2.append(j)
                if len(bl2) == 5:
                    s = 0.0
                    l = -1
                    for kk in range(5):
                        s1 = _dist(xyz, B, bl2[kk])
                        if s < s1:
                            s = s1
                            l = kk
                    del bl2[l]
        for j in bl1:
            if j == B:
                hb[10] = -666
            for k in bl2:
                if j == k and k != H:
                    hb[10] = -666
        rec = {"hb": hb, "nra": len(bl1), "nrb": len(bl2)}
        if hb[10] == -666:
            rows.append(rec)
            continue

        def side(bl, A_, cols, bonding_):
            c2, c3, c4 = cols
            nr = len(bl)
            if nr in (3, 4):
                old = -1.0
                for kk in bl:
                    d = _dist(xyz, kk, H)
                    if d > old:
                        old = d
                        hb[c2] = kk
                old = -1.0
                for kk in bl:
                    d = _dist(xyz, kk, H)
                    if d > old and kk != hb[c2]:
                        old = d
                        hb[c3] = kk
                old = -1.0
                for kk in bl:
                    d = _dist(xyz, kk, H)
                    if d > old and kk != hb[c2] and kk != hb[c3]:
                        old = d
                        hb[c4] = kk
            elif nr == 2:
                old = -1.0
                for kk in bl:
                    d = _dist(xyz, kk, H)
                    if d > old:
                        old = d
                        hb[c2] = kk
                for kk in bl:
                    if kk != hb[c2]:
                        hb[c3] = kk
                hb[c4] = H if _dist(xyz, A_, H) < bonding_(A_, H) else A_
            elif nr == 1:
                hb[c2] = bl[0]
                bc = []
                for kk in range(n):
                    if _dist(xyz, kk, hb[c2]) < bonding_(kk, hb[c2]) and hb[c2] != kk:
                        bc.append(kk)
                old = -1.0
                for kk in bc:
                    d = _dist(xyz, kk, H)
                    if d > old:
                        old = d
                        hb[c3] = kk
                hb[c4] = H if _dist(xyz, A_, H) < bonding_(A_, H) else A_
            elif nr == 0:
                v = H if _dist(xyz, A_, H) < bonding_(A_, H) else A_
                hb[c2] = hb[c3] = hb[c4] = v

        side(bl1, A, (2, 3, 4), bonding)
        side(bl2, B, (6, 7, 8), bonding)
        rows.append(rec)
    return rows


def eh_plus(z, xyz, rec):
    """EH_plus for one hydrogen bond (PM7 branch), kcal/mol."""
    hb = rec["hb"]
    nra, nrb = rec["nra"], rec["nrb"]
    shortcut, longcut, covcut = 2.4, 7.0, 1.2
    scale_nsp3 = -0.171271 * A0**2
    scale_osp3 = -0.098822 * A0**2
    scale_nsp2 = -0.171271 * A0**2
    scale_osp2 = scale_osp3
    hartree2kcal = EV * FPC_9
    if hb[10] == -666:
        return 0.0
    A, H, B = hb[1], hb[9], hb[5]
    angle_cos = -math.cos(bangle(xyz, A, H, B))
    if angle_cos <= 0:
        return 0.0
    torsion = lambda a, b, c, d: dihed(xyz, a, b, c, d)
    dist = lambda a, b: _dist(xyz, a, b)

    def target(donor, nr):
        torsion_check = 0.0
        set1 = False
        set2 = False
        if z[donor] == 8:
            if nr == 1:
                a_s = PI
                a_s2 = PI / (180.0 / 120.0)
                t_s = 0.0
                set2 = True
            else:
                a_s = PI / (180.0 / 109.48)
                a_s2 = a_s
                t_s = PI / (180.0 / 54.74)
        elif z[donor] == 7:
            if nr == 2:
                a_s = PI / (180.0 / 120.0)
                a_s2 = a_s
                t_s = 0.0
            else:
                a_s = PI / (180.0 / 109.48)
                a_s2 = a_s
                t_s = PI / (180.0 / 54.74)
                set1 = True
        else:
            a_s = a_s2 = t_s = 0.0
        return a_s, a_s2, t_s, set1, set2, torsion_check

    def one_side(c1, c2, c3, c4, nr):
        D_ = hb[c1]
        a_s, a_s2, t_s, set1, set2, tcheck = target(D_, nr)
        if set1:
            tcheck = torsion(hb[c3], hb[c2], hb[c1], hb[c4])
            if tcheck <= -PI:
                tcheck += 2.0 * PI
            if tcheck > PI:
                tcheck -= 2.0 * PI
            if tcheck < 0:
                tcheck = -PI - tcheck
            else:
                tcheck = PI - tcheck
            tbac = tcheck
            if tcheck < 0:
                tcheck = -1.0 * tcheck
            tcheck = tcheck * 180.0 / PI
            t_s = t_s + PI / (180.0 / ((54.74 - tcheck) / 54.74 * 35.26))
            a_s = a_s - PI / (180.0 / ((54.74 - tcheck) / 54.74 * 19.48))
            a_s2 = a_s
            tcheck = tbac
        angle2 = bangle(xyz, hb[c2], hb[c1], H)
        a2c = math.cos(a_s - angle2)
        a2c2 = math.cos(a_s2 - angle2)
        if a2c2 > a2c:
            a2c = a2c2
        if a2c <= 0.0:
            return None
        tcor = torsion(hb[c3], hb[c2], hb[c1], H)
        if tcor <= -PI:
            tcor += 2.0 * PI
        if tcor > PI:
            tcor -= 2.0 * PI
        if (not set2) or (abs(tcor * 180.0 / PI) > 90.0):
            if tcor < 0.0:
                tcor = -PI - tcor
            else:
                tcor = PI - tcor
        if tcheck < 0:
            tv = t_s - tcor
            if tv <= -PI:
                tv += 2.0 * PI
            if tv > PI:
                tv -= 2.0 * PI
            tcos = math.cos(tv)
        elif tcheck > 0:
            tv = -t_s - tcor
            if tv <= -PI:
                tv += 2.0 * PI
            if tv > PI:
                tv -= 2.0 * PI
            tcos = math.cos(tv)
        else:
            tv = t_s - tcor
            tv2 = -t_s - tcor
            if tv <= -PI:
                tv += 2.0 * PI
            if tv > PI:
                tv -= 2.0 * PI
            if tv2 <= -PI:
                tv2 += 2.0 * PI
            if tv2 > PI:
                tv2 -= 2.0 * PI
            tcos = math.cos(tv)
            tcos2 = math.cos(tv2)
            if tcos2 > tcos:
                tcos = tcos2
        if dist(H, hb[c1]) > dist(H, hb[c2]) and set2:
            tcos = 0.0
        if hb[c3] == hb[c4] or H == hb[c4]:
            tcos = 1.0
        return a2c, tcos

    r1 = one_side(1, 2, 3, 4, nra)
    if r1 is None:
        return 0.0
    angle2_cos, torsion_cos = r1
    if torsion_cos < 0:
        return 0.0
    r2 = one_side(5, 6, 7, 8, nrb)
    if r2 is None:
        return 0.0
    angle2_cos_new, torsion_cos_new = r2
    torsion_cos_new = abs(torsion_cos_new)
    if z[A] == 7:
        scale_a = scale_nsp3 if nra >= 3 else scale_nsp2
    else:
        scale_a = scale_osp3 if nra >= 2 else scale_osp2
    if z[B] == 7:
        scale_b = scale_nsp3 if nrb >= 3 else scale_nsp2
    else:
        scale_b = scale_osp3 if nrb >= 2 else scale_osp2
    scale_c = (scale_a + scale_b) / 2.0
    ha = dist(H, A)
    hbd = dist(H, B)
    xc = min(ha, hbd)
    xy = max(ha, hbd) - xc
    if xy > 0.5:
        damping = 1.0 - 1.0 / (1.0 + math.exp(-60.0 * (xc / covcut - 1.0)))
    else:
        damping = 1.0
    xc = dist(A, B)
    damping = damping / (1.0 + math.exp(-100.0 * (xc / shortcut - 1.0)))
    damping = damping * (1.0 - 1.0 / (1.0 + math.exp(-10.0 * (xc / longcut - 1.0))))
    xy = dist(A, B)
    e = (
        scale_c
        / xy**2.0
        * angle_cos**2
        * (
            1.0
            - (1.0 - angle2_cos * torsion_cos * angle2_cos_new * torsion_cos_new) ** 2
        )
        * hartree2kcal
        * damping
    )
    if z[A] == 8 and z[B] == 8:
        short = -2.5 * math.exp(-80.0 * (max(xy - 2.67, 0.0)) ** 2) * angle_cos**4
        e += short
    return e


def hbond_energy_and_gradient(z, xyz, want_grad, delta=1.0e-5):
    """E_hb (kcal/mol) and (optionally) its gradient as computed in Hydrogen_bond_corrections."""
    n = len(z)
    if not any(zz in (7, 8) for zz in z):
        return 0.0, np.zeros((n, 3))
    xyz = np.array(xyz, float)
    pairs = find_hbonds(z, xyz)
    rows = setup_dh_plus(z, xyz, pairs)
    grad = np.zeros((n, 3))
    ehb = 0.0
    for rec in rows:
        s = eh_plus(z, xyz, rec)
        ehb += s
        if want_grad and s < -0.01:
            hb = rec["hb"]
            dlist = []
            for c in range(1, 10):
                if hb[c] >= 0 and hb[c] not in dlist:
                    dlist.append(hb[c])
            H = hb[9]
            for k in dlist:
                if float(np.sum((xyz[H] - xyz[k]) ** 2)) < 8.0**2:
                    for i in range(3):
                        xyz[k, i] += delta
                        s1 = eh_plus(z, xyz, rec)
                        if abs(s1) > 1.0e-5:
                            s1 = (s1 - s) / delta
                            grad[k, i] += s1
                        xyz[k, i] -= delta
    return ehb, grad


# ------------------------------------------------------------------ C-C triple bond correction
def c_triple_bond_energy(z, xyz, ibonds):
    rmin, rmax, param1, param2 = 1.21, 1.33, -5.0, 25.0
    total = 0.0
    for i in range(len(z)):
        if z[i] != 6:
            continue
        for j in ibonds[i]:
            if j > i:
                continue
            if z[j] == 6:
                rab = float(np.sum((xyz[i] - xyz[j]) ** 2))
                if rab < rmin**2:
                    total += 1.0
                if rab >= rmin**2 and rab < rmax**2:
                    rab = (math.sqrt(rab) - rmin) / (rmax - rmin)
                    total += (
                        1.0
                        - 10.0 * rab**3
                        + 15.0 * rab**4
                        - 6.0 * rab**5
                        + (param1 + rab * param2)
                        * (rab**3 - 3.0 * rab**4 + 3.0 * rab**5 - rab**6)
                    )
    return total * 12.0


def c_triple_bond_gradient(z, xyz, ibonds):
    rmin, rmax, param1, param2 = 1.21, 1.33, -5.0, 25.0
    g = np.zeros((len(z), 3))
    for i in range(len(z)):
        if z[i] != 6:
            continue
        for j in ibonds[i]:
            if j > i or z[j] != 6:
                continue
            rab = float(np.sum((xyz[i] - xyz[j]) ** 2))
            if rab >= rmin**2 and rab < rmax**2:
                drab = 0.5 / (math.sqrt(rab) * (rmax - rmin))
                rab = (math.sqrt(rab) - rmin) / (rmax - rmin)
                dx = 2.0 * (xyz[i] - xyz[j]) * drab
                dsum = (
                    -10.0 * 3.0 * rab**2
                    + 15.0 * 4.0 * rab**3
                    - 6.0 * 5.0 * rab**4
                    + (param1 + rab * param2)
                    * (
                        3.0 * rab**2
                        - 3.0 * 4.0 * rab**3
                        + 3.0 * 5.0 * rab**4
                        - 6.0 * rab**5
                    )
                    + param2 * (rab**3 - 3.0 * rab**4 + 3.0 * rab**5 - rab**6)
                )
                g[i] += 12.0 * dsum * dx
                g[j] -= 12.0 * dsum * dx
    return g


# ------------------------------------------------------------------ N-H-C=O torsion (MM) term
HTYPE_PM7 = 3.1595


def setup_nhco(z, xyz):
    n = len(z)
    d = lambda a, b: _dist(xyz, a, b)
    nhco = []
    for j in range(n):
        if z[j] != 6:
            continue
        found = False
        for i in range(n):
            if z[i] != 8:
                continue
            if d(i, j) > 1.3:
                continue
            for k in range(n):
                if z[k] != 7:
                    continue
                if d(k, j) > 1.6:
                    continue
                for l in range(n):
                    if z[l] != 1:
                        continue
                    if d(k, l) > 1.3:
                        continue
                    for m in range(n):
                        if m == k or m == l or m == j:
                            continue
                        if d(m, k) > 1.7:
                            continue
                        if any(nhco[jj][2] == k for jj in range(0, len(nhco), 2)):
                            continue
                        nhco.append((i, j, k, m))
                        nhco.append((i, j, k, l))
                        found = True
                        break
                    if found:
                        break
                if found:
                    break
            if found:
                break
    return nhco


def nhco_energy(z, xyz, nhco):
    s = 0.0
    for a, b, c, d in nhco:
        ang = dihed(xyz, a, b, c, d)
        s += HTYPE_PM7 * math.sin(ang) ** 2
    return s


def nhco_gradient(z, xyz, nhco, delta=1.0e-8):
    g = np.zeros((len(z), 3))
    if not nhco:
        return g
    xyz = np.array(xyz, float)
    for a, b, c, d in nhco:
        for atom in (a, b, c, d):
            for k in range(3):
                xyz[atom, k] -= delta
                refh = HTYPE_PM7 * math.sin(dihed(xyz, a, b, c, d)) ** 2
                xyz[atom, k] += 2.0 * delta
                heat = HTYPE_PM7 * math.sin(dihed(xyz, a, b, c, d)) ** 2
                xyz[atom, k] -= delta
                g[atom, k] -= (refh - heat) / (2.0 * delta)
    return g


# ------------------------------------------------------------------ aggregate
def correction_energy(z, xyz):
    """Total of all geometry-only corrections (kcal/mol): returns dict of pieces."""
    nbonds, ibonds = connectivity(z, xyz)
    out = {}
    out["c_triple"] = c_triple_bond_energy(z, xyz, ibonds)
    nh = setup_nhco(z, xyz)
    out["nhco"] = nhco_energy(z, xyz, nh)
    out["disp"] = dispersion_total(z, xyz, nbonds)
    out["hbond"], _ = hbond_energy_and_gradient(z, xyz, False)
    out["total"] = out["c_triple"] + out["nhco"] + out["disp"] + out["hbond"]
    return out


def correction_gradient(z, xyz):
    """Gradient (kcal/mol/Angstrom) of the corrections, as accumulated by deriv/dcart."""
    nbonds, ibonds = connectivity(z, xyz)
    g = c_triple_bond_gradient(z, xyz, ibonds)
    nh = setup_nhco(z, xyz)
    g = g + nhco_gradient(z, xyz, nh)
    g = g + dispersion_gradient(z, xyz, nbonds)
    _, gh = hbond_energy_and_gradient(z, xyz, True)
    return g + gh
