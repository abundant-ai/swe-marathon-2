"""Neighbour-list versions of the geometry-only PM7 corrections for protein-size systems.

The small-molecule code (``corrections.py``) scans all atoms in Python loops; here the same
algorithms are evaluated with identical loop order and identical formulas, but candidate atoms
come from a k-d tree and the dispersion sum is vectorised.  ``tests`` in NOTES.md compare both
code paths on crambin.
"""

import math

import numpy as np
from scipy.spatial import cKDTree

from . import corrections as C
from .system import COVALENT_RADIUS


def connectivity(z, xyz):
    """Same result as system.connectivity (set_up_dentate) using a neighbour search."""
    n = len(z)
    za = np.asarray(z)
    rc = np.array([COVALENT_RADIUS[v] for v in z])
    tree = cKDTree(xyz)
    pr = tree.query_pairs(1.25 * 2.0 * rc.max(), output_type="ndarray")
    nb = [0] * n
    ib = [[] for _ in range(n)]
    if len(pr):
        i = np.maximum(pr[:, 0], pr[:, 1])
        j = np.minimum(pr[:, 0], pr[:, 1])
        il = np.minimum(za[i], za[j])
        iu = np.maximum(za[i], za[j])
        safety = np.full(len(i), 1.1)
        safety[(il == 1) & (iu == 6)] = 1.25
        safety[(il == 5) & (iu == 7)] = 1.0
        safety[(il == 6) & (iu < 8)] = 1.2
        safety[(il == 16) & (iu == 16)] = 1.2
        d2 = ((xyz[i] - xyz[j]) ** 2).sum(1)
        ok = d2 < (safety * (rc[i] + rc[j])) ** 2
        i = i[ok]
        j = j[ok]
        o = np.lexsort((j, i))
        for a, b in zip(i[o].tolist(), j[o].tolist()):
            if nb[a] < 15 and nb[b] < 15:
                ib[a].append(b)
                ib[b].append(a)
                nb[a] += 1
                nb[b] += 1
    for a in range(n):
        if z[a] != 1 or nb[a] < 2:
            continue
        ib[a] = [x for x in ib[a] if z[x] != 1]
        nb[a] = len(ib[a])
    return nb, ib


def dispersion_total(z, xyz, nbonds):
    """PM6_DH_Dispersion pair sum (all pairs closer than 100 A), vectorised."""
    n = len(z)
    tid = np.empty(n, dtype=int)
    keys = {}
    reps = []
    for a in range(n):
        key = (z[a], 4 if (z[a] == 6 and nbonds[a] == 4) else 0)
        if key not in keys:
            keys[key] = len(reps)
            reps.append(a)
        tid[a] = keys[key]
    nt = len(reps)
    c6t = np.zeros((nt, nt))
    r0t = np.zeros((nt, nt))
    for p in range(nt):
        for q in range(nt):
            a, b = reps[p], reps[q]
            ni, nj = z[a], z[b]
            c6i = (0.95 if nbonds[a] == 4 else 1.65) if ni == 6 else C._C6[ni]
            c6j = (0.95 if nbonds[b] == 4 else 1.65) if nj == 6 else C._C6[nj]
            ni_, nj_ = C._NEFF[ni], C._NEFF[nj]
            c6t[p, q] = (
                2.0
                * (c6i**2 * c6j**2 * ni_ * nj_) ** (1.0 / 3.0)
                / ((c6i * nj_**2) ** (1.0 / 3.0) + (c6j * ni_**2) ** (1.0 / 3.0))
            )
            r0t[p, q] = (
                (C._R0[ni] ** 3 + C._R0[nj] ** 3)
                / (C._R0[ni] ** 2 + C._R0[nj] ** 2)
                / 1000.0
                * 2.0
            )
    e = 0.0
    step = 256
    cols = np.arange(n)
    for s0 in range(0, n, step):
        s1 = min(n, s0 + step)
        d = xyz[s0:s1, None, :] - xyz[None, s0:, :]
        r2 = (d * d).sum(-1)
        ii = np.arange(s0, s1)[:, None]
        jj = cols[None, s0:]
        m = (jj > ii) & (r2 < 100.0**2)
        rows_idx, cols_idx = np.nonzero(m)
        r = np.sqrt(r2[rows_idx, cols_idx]) * 0.1
        ta = tid[s0 + rows_idx]
        tb = tid[s0 + cols_idx]
        c6 = c6t[ta, tb]
        r0 = r0t[ta, tb]
        damp = 1.0 / (1.0 + np.exp(-C._ALPHA * (r / (C._S * r0) - 1.0)))
        e += float(np.sum(-(c6 / r**6 * damp / (1000.0 * 4.184))))
    return e * C._CSCALE


def setup_nhco(z, xyz):
    """Same list as corrections.setup_nhco (loop order preserved)."""
    n = len(z)
    za = np.asarray(z)
    tree = cKDTree(xyz)
    nhco = []
    have_k = set()

    def near(c, r, elem):
        idx = tree.query_ball_point(xyz[c], r)
        idx = [x for x in idx if za[x] == elem]
        idx.sort()
        return idx

    for j in np.nonzero(za == 6)[0].tolist():
        found = False
        for i in near(j, 1.3, 8):
            # the original tests d(i,j) > 1.3 -> skip, i.e. keeps d <= 1.3; ball query is also <= (equal case measure zero)
            for k in near(j, 1.6, 7):
                for l in near(k, 1.3, 1):
                    mm = tree.query_ball_point(xyz[k], 1.7)
                    mm = sorted(x for x in mm if x != k and x != l and x != j)
                    for m in mm:
                        if k in have_k:
                            continue
                        nhco.append((i, j, k, m))
                        nhco.append((i, j, k, l))
                        have_k.add(k)
                        found = True
                        break
                    if found:
                        break
                if found:
                    break
            if found:
                break
    return nhco


def find_hbonds(z, xyz):
    n = len(z)
    za = np.asarray(z)
    tree = cKDTree(xyz)
    rah = 1.4
    acc = [i for i in range(n) if z[i] in (7, 8)]
    hb = []
    used = np.zeros(n, bool)
    for i in acc:
        cand = sorted(j for j in tree.query_ball_point(xyz[i], rah) if za[j] == 1)
        for j in cand:
            if not used[j]:
                hb.append(j)
                used[j] = True
    hb_pos = {j: p for p, j in enumerate(hb)}
    acc_arr = np.array(acc, dtype=int)
    acc_tree = cKDTree(xyz[acc_arr]) if len(acc) else None
    pairs = []
    seen = set()
    cutoff = 7.0
    for i in acc:
        hnear = sorted(
            (j for j in tree.query_ball_point(xyz[i], rah) if j in hb_pos),
            key=lambda j: hb_pos[j],
        )
        if not hnear:
            continue
        kk = sorted(acc_arr[x] for x in acc_tree.query_ball_point(xyz[i], cutoff))
        for j in hnear:
            for k in kk:
                if k == i:
                    continue
                if C.bangle(xyz, k, j, i) > C.PI * 0.5:
                    if (k, j, i) in seen or (i, j, k) in seen:
                        continue
                    seen.add((i, j, k))
                    pairs.append((i, j, k))
    return pairs


def setup_dh_plus(z, xyz, pairs):
    """C.setup_dh_plus with neighbour-list candidate sets (identical loop order)."""
    rows = []
    n = len(z)
    tree = cKDTree(xyz)
    bonding = lambda x, y: C.COVRAD[z[x]] + C.COVRAD[z[y]]
    dist = lambda a, b: C._dist(xyz, a, b)
    RB = 3.0

    def cand(c):
        return sorted(tree.query_ball_point(xyz[c], RB))

    for A, H, B in pairs:
        hb = [-1] * 11
        hb[1], hb[9], hb[5] = A, H, B
        bl1, bl2 = [], []
        cA = cand(A)
        cB = cand(B)
        for cl, X, bl in ((cA, A, bl1), (cB, B, bl2)):
            for j in cl:
                if dist(j, X) < bonding(j, X) and X != j:
                    bl.append(j)
                    if len(bl) == 5:
                        s = 0.0
                        l = -1
                        for kk in range(5):
                            s1 = dist(X, bl[kk])
                            if s < s1:
                                s = s1
                                l = kk
                        del bl[l]
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

        def side(bl, A_, cols):
            c2, c3, c4 = cols
            nr = len(bl)
            if nr in (3, 4):
                old = -1.0
                for kk in bl:
                    d = dist(kk, H)
                    if d > old:
                        old = d
                        hb[c2] = kk
                old = -1.0
                for kk in bl:
                    d = dist(kk, H)
                    if d > old and kk != hb[c2]:
                        old = d
                        hb[c3] = kk
                old = -1.0
                for kk in bl:
                    d = dist(kk, H)
                    if d > old and kk != hb[c2] and kk != hb[c3]:
                        old = d
                        hb[c4] = kk
            elif nr == 2:
                old = -1.0
                for kk in bl:
                    d = dist(kk, H)
                    if d > old:
                        old = d
                        hb[c2] = kk
                for kk in bl:
                    if kk != hb[c2]:
                        hb[c3] = kk
                hb[c4] = H if dist(A_, H) < bonding(A_, H) else A_
            elif nr == 1:
                hb[c2] = bl[0]
                bc = []
                for kk in cand(hb[c2]):
                    if dist(kk, hb[c2]) < bonding(kk, hb[c2]) and hb[c2] != kk:
                        bc.append(kk)
                old = -1.0
                for kk in bc:
                    d = dist(kk, H)
                    if d > old:
                        old = d
                        hb[c3] = kk
                hb[c4] = H if dist(A_, H) < bonding(A_, H) else A_
            elif nr == 0:
                v = H if dist(A_, H) < bonding(A_, H) else A_
                hb[c2] = hb[c3] = hb[c4] = v

        side(bl1, A, (2, 3, 4))
        side(bl2, B, (6, 7, 8))
        rows.append(rec)
    return rows


def hbond_energy(z, xyz):
    if not any(zz in (7, 8) for zz in z):
        return 0.0
    pairs = find_hbonds(z, xyz)
    rows = setup_dh_plus(z, xyz, pairs)
    e = 0.0
    for rec in rows:
        e += C.eh_plus(z, xyz, rec)
    return e


def correction_energy(z, xyz):
    """Fast equivalent of corrections.correction_energy (energy pieces only)."""
    xyz = np.asarray(xyz, float)
    nbonds, ibonds = connectivity(z, xyz)
    out = {}
    out["c_triple"] = C.c_triple_bond_energy(z, xyz, ibonds)
    out["nhco"] = C.nhco_energy(z, xyz, setup_nhco(z, xyz))
    out["disp"] = dispersion_total(z, xyz, nbonds)
    out["hbond"] = hbond_energy(z, xyz)
    out["total"] = out["c_triple"] + out["nhco"] + out["disp"] + out["hbond"]
    return out
