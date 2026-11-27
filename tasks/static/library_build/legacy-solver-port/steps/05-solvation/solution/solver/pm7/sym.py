"""Point-group detection and Hessian symmetrisation used by MOPAC's FORCE (ports of MOLSYM, CHI, PLATO,
ORIENT, CARTAB, MAKOPR, SYMR/SYMP, SYMH/SYMPOP, SYMT).

Conventions: coordinates are (3, n) arrays (Fortran layout) in Angstrom, operation numbers are 1-based
(ielem[1..20], elem[1..20] 3x3 matrices, as in MOPAC), r is the 3x3 orientation matrix.
"""

import math

import numpy as np

from .sym_data import NALLOP

_J = {
    1: (1, -1, -1),
    2: (-1, 1, -1),
    3: (-1, -1, 1),
    4: (1, 1, -1),
    5: (1, -1, 1),
    6: (-1, 1, 1),
    7: (-1, -1, -1),
    8: (3, 0, 1),
    9: (4, 0, 1),
    10: (5, 0, 1),
    11: (6, 0, 1),
    12: (7, 0, 1),
    13: (8, 0, 1),
    14: (4, 0, -1),
    15: (6, 0, -1),
    16: (8, 0, -1),
    17: (10, 0, -1),
    18: (12, 0, -1),
    19: (5, 0, -1),
    20: (0, 0, -1),
}
TWOPI = 6.2831853071796


class SymState:
    def __init__(self, numat):
        self.numat = numat
        self.ielem = [0] * 21
        self.elem = {i: np.zeros((3, 3)) for i in range(1, 21)}
        self.jelem = np.zeros((21, numat), int)
        self.cub = np.eye(3)
        self.nclass = 1
        self.jy = [0] * 7
        self.igroup = 1


def mult33(fmat, iplace, st):
    """elem(iplace) <- F elem F^T"""
    e = st.elem[iplace]
    st.elem[iplace] = fmat @ e @ fmat.T


def bldsym(ioper, iplace, st):
    e = np.zeros((3, 3))
    for i in range(3):
        e[i, i] = _J[ioper][i]
    st.elem[iplace] = e
    if ioper != 20:
        if _J[ioper][0] >= 2:
            ang = TWOPI / float(_J[ioper][0])
            e[0, 0] = math.cos(ang)
            e[1, 1] = e[0, 0]
            e[1, 0] = math.sin(ang)
            e[0, 1] = -e[1, 0]
        if ioper == 8 or ioper == 15:
            mult33(st.cub, iplace, st)
        return
    e[0, 1] = 1.0
    e[1, 0] = 1.0


def symopr(coord, jump, r):
    """in place; jump>=0: coord <- r^T coord ; jump<0: coord <- r coord"""
    if jump >= 0:
        coord[:, :] = r.T @ coord
    else:
        coord[:, :] = r @ coord


def rotmol(coord, sina, cosa, i, j, r):
    symopr(coord, -1, r)
    i -= 1
    j -= 1
    for k in range(3):
        buff = -sina * r[k, i] + cosa * r[k, j]
        r[k, i] = cosa * r[k, i] + sina * r[k, j]
        r[k, j] = buff
    symopr(coord, 1, r)


def chi(toler, coord, ioper, nat, st):
    n = coord.shape[1]
    iresul = 1
    iqual = 0
    e = st.elem[ioper]
    for i in range(n):
        h = e @ coord[:, i]
        found = False
        for j in range(n):
            if nat[i] != nat[j]:
                continue
            if abs(coord[0, j] - h[0]) > toler:
                continue
            if abs(coord[1, j] - h[1]) > toler:
                continue
            if abs(coord[2, j] - h[2]) > toler:
                continue
            st.jelem[ioper, i] = j
            if i == j:
                iqual += 1
            found = True
            break
        if not found:
            iresul = 0
    st.ielem[ioper] = iresul
    return iqual


def _bangle(xyz, i, j, k):
    """angle at j between i and k (1-based columns of xyz (3,*))"""
    i -= 1
    j -= 1
    k -= 1
    d2ij = float(np.sum((xyz[:, i] - xyz[:, j]) ** 2))
    d2jk = float(np.sum((xyz[:, j] - xyz[:, k]) ** 2))
    d2ik = float(np.sum((xyz[:, i] - xyz[:, k]) ** 2))
    xy = math.sqrt(d2ij * d2jk)
    temp = 0.5 * (d2ij + d2jk - d2ik)
    if xy < 1e-20:
        return 0.0
    temp = temp / xy
    if temp >= 1.0:
        return 0.0
    if temp <= -1.0:
        return math.pi
    return math.acos(temp)


def _plato(coord, r, nat, ier):
    """returns cubic flag; modifies coord and r"""
    n = coord.shape[1]
    toler = 0.1
    symopr(coord, -1, r)
    rmin = 0.1
    xmin = 0.0
    ymin = 0.0
    store_ligand = 0
    ligand_type = 0
    k = 100
    while True:
        found = False
        for i in range(n):
            xmin = float(np.sum(coord[:, i] ** 2))
            if xmin >= rmin:
                ligand_type = nat[i]
                found = True
                break
        if not found:
            # Fortran: loop finished, xmin holds last value (< rmin) -> xmin = ymin
            xmin = ymin
            break
        l = 0
        for i in range(n):
            dist = float(np.sum(coord[:, i] ** 2))
            if abs(dist - xmin) < toler and nat[i] == ligand_type:
                l += 1
        if l < k:
            k = l
            ymin = xmin
            store_ligand = ligand_type
        if l < 5:
            break
        rmin = xmin + 2.0 * toler
    ligand_type = store_ligand
    near = []
    for i in range(n):
        dist = float(np.sum(coord[:, i] ** 2))
        if dist >= toler and dist <= xmin + toler:
            if abs(dist - xmin) < toler and nat[i] == ligand_type:
                near.append(i)
    l = len(near)
    if l == 0:
        return False
    if l == 1:
        return False
    go1100 = False
    if l in (4, 6, 8, 12, 20):
        xm = 10000.0
        j = near[0]
        for ii in range(1, l):
            i = near[ii]
            dist = float(np.sum((coord[:, j] - coord[:, i]) ** 2))
            if dist < xm:
                xm = dist
        j1 = near[0]
        j2 = near[1]
        k1 = k2 = 0
        for ii in range(l):
            i = near[ii]
            dist1 = float(np.sum((coord[:, j1] - coord[:, i]) ** 2))
            dist2 = float(np.sum((coord[:, j2] - coord[:, i]) ** 2))
            if abs(dist2 - xm) < toler:
                k2 += 1
            if abs(dist1 - xm) < toler:
                k1 += 1
        if k1 == k2:
            kk = k1
        elif k1 > 2 or k2 > 2:
            return False
        else:
            kk = 0
        if (
            (l == 4 and kk == 3)
            or (l == 6 and kk == 4)
            or (l == 8 and kk == 3)
            or (l == 12 and kk == 5)
            or (l == 20 and kk == 3)
        ):
            i = near[l - 1]
            r[:, 2] = (
                coord[:, i] / dist
            )  # `dist` of the last loop pass (as in the Fortran)
            go1100 = True
    if not go1100:
        i1 = near[0]
        ipoly = [-1, -1, -1]
        allr = [0.0, 0.0, 0.0]
        for i in range(3):
            xm = 10000.0
            ipoly[i] = -1
            for j1 in range(1, l):
                j = near[j1]
                if any(ipoly[m] == j for m in range(i)):
                    continue
                r2j = float(np.sum((coord[:, i1] - coord[:, j]) ** 2))
                if xm > r2j:
                    xm = r2j
                    ipoly[i] = j
                    allr[i] = r2j
                    if xm < 0.01:
                        raise ValueError(
                            "Geometry is apparently cubic, but two atoms coincide"
                        )
        allr = [math.sqrt(x) for x in allr]
        if ipoly[0] < 0 or ipoly[1] < 0 or ipoly[2] < 0:
            return False
        pair = None
        for i in range(2):
            for j in range(i + 1, 3):
                if abs(allr[i] - allr[j]) < 0.01:
                    pair = (i, j)
                    break
            if pair:
                break
        if pair is None:
            return False
        i, j = pair
        xyz = np.zeros((3, 3))
        xyz[:, 2] = coord[:, ipoly[i]]
        xyz[:, 1] = coord[:, ipoly[j]]
        xyz[:, 0] = coord[:, i1]
        i3 = ipoly[i]
        i2 = ipoly[j]
        angle = _bangle(xyz, 3, 1, 2)
        if abs(angle - 1.0472) < 0.1:
            r[:, 2] = coord[:, i1] + coord[:, i2] + coord[:, i3]
        elif abs(angle - 1.5707963) < 0.1:
            r[:, 2] = coord[:, i2] + coord[:, i3]
        elif abs(angle - 1.885) < 0.1:
            r[:, 2] = 1.6180341 * (coord[:, i2] + coord[:, i3]) - coord[:, i1]
        else:
            return False
    s = math.sqrt(float(np.sum(r[:, 2] ** 2)))
    r[:, 2] = r[:, 2] / s
    buff = math.sqrt(r[0, 2] ** 2 + r[1, 2] ** 2)
    buff1 = math.sqrt(r[0, 2] ** 2 + r[2, 2] ** 2)
    if buff <= buff1:
        r[0, 0] = r[2, 2] / buff1
        r[1, 0] = 0.0
        r[2, 0] = -r[0, 2] / buff1
    else:
        r[0, 0] = r[1, 2] / buff
        r[1, 0] = -r[0, 2] / buff
        r[2, 0] = 0.0
    r[0, 1] = r[1, 2] * r[2, 0] - r[1, 0] * r[2, 2]
    r[1, 1] = r[2, 2] * r[0, 0] - r[2, 0] * r[0, 2]
    r[2, 1] = r[0, 2] * r[1, 0] - r[0, 0] * r[1, 2]
    symopr(coord, 1, r)
    return True


def _orient(coord, r, nat, st):
    toler = 0.1
    wink = (0.955316618125, 0.65235813978437)
    wink2 = 0.0
    ielem = st.ielem
    if ielem[8] >= 1:
        for i in (1, 2):
            jota = 18 - 4 * i
            wink2 = wink[i - 1]
            sina = math.sin(wink2)
            cosa = math.cos(wink2)
            rotmol(coord, sina, cosa, 1, 3, r)
            chi(toler, coord, jota, nat, st)
            if ielem[jota] > 0:
                break
            if i == 1:
                chi(toler, coord, 3, nat, st)
                if ielem[3] == 1:
                    break
            wink2 = -wink2
            sinb = math.sin(2.0 * wink2)
            cosb = math.cos(2.0 * wink2)
            rotmol(coord, sinb, cosb, 1, 3, r)
            chi(toler, coord, jota, nat, st)
            if ielem[jota] > 0:
                break
            if i == 1:
                chi(toler, coord, 3, nat, st)
                if ielem[3] == 1:
                    break
            rotmol(coord, sina, cosa, 1, 3, r)
        chi(toler, coord, 9, nat, st)
        if ielem[10] > 0:
            chi(toler, coord, 17, nat, st)
    else:
        wink2 = -wink[0]
        if ielem[10] > 0:
            wink2 = -wink[1]
        sina = -math.sin(wink2)
        cosa = math.cos(wink2)
        rotmol(coord, sina, cosa, 1, 3, r)
        chi(toler, coord, 8, nat, st)
        rotmol(coord, -sina, cosa, 1, 3, r)
        if ielem[8] <= 0:
            if ielem[9] <= 0:
                wink2 = -wink2
            else:
                rotmol(coord, 0.707106781186, 0.707106781186, 1, 2, r)
    j = sum(ielem[1:18])
    if j == 2 and ielem[1] + ielem[8] == 2:
        return
    st.cub[0, 0] = math.cos(wink2)
    st.cub[2, 2] = st.cub[0, 0]
    st.cub[0, 2] = math.sin(wink2)
    st.cub[2, 0] = -st.cub[0, 2]
    mult33(st.cub, 8, st)
    mult33(st.cub, 15, st)
    chi(toler, coord, 8, nat, st)
    chi(toler, coord, 15, nat, st)


def molsym(coord, nat, nbonds, ibonds, st):
    """coord (3,n) is modified in place (centred); returns r (3x3)."""
    n = coord.shape[1]
    ielem = st.ielem
    toler = 0.1
    kndex = 0
    st.cub = np.eye(3)
    for i in range(1, 19):
        bldsym(i, i, st)
        ielem[i] = 0
    ielem[19] = 0
    ielem[20] = 0
    wmol = float(sum(nat))
    shift = sum(nat[i] * coord[:, i] for i in range(n)) / wmol
    coord -= shift[:, None]
    f = np.zeros(6)
    ij = 0
    for i in range(3):
        for j in range(i + 1):
            f[ij] = (ij + 1) * 1.0e-8 + sum(
                nat[k] * coord[i, k] * coord[j, k] for k in range(n)
            )
            ij += 1
    iscube = True
    r = np.eye(3)
    ew = np.zeros(3)
    axis = False
    goto = None  # None: continue to 1100, '270' or '250'
    while True:
        fm = np.array([[f[0], f[1], f[3]], [f[1], f[2], f[4]], [f[3], f[4], f[5]]])
        ew, r = np.linalg.eigh(fm)
        r = r.copy()
        det = (
            r[0, 0] * (r[1, 1] * r[2, 2] - r[2, 1] * r[1, 2])
            + r[0, 1] * (r[1, 2] * r[2, 0] - r[1, 0] * r[2, 2])
            + r[0, 2] * (r[1, 0] * r[2, 1] - r[1, 1] * r[2, 0])
        )
        if det > 1.0:
            s = 1.01
            ii = 0
            for j in range(3):
                if r[j, j] >= s:
                    continue
                s = r[j, j]
                ii = j
            r[:, ii] = -r[:, ii]
        r[0, 2] = r[1, 0] * r[2, 1] - r[2, 0] * r[1, 1]
        r[1, 2] = r[2, 0] * r[0, 1] - r[0, 0] * r[2, 1]
        r[2, 2] = r[0, 0] * r[1, 1] - r[1, 0] * r[0, 1]
        linear = ew[1] < 1.0e-2
        sphere = ew[2] < 1.0e-2
        cubic = (ew[2] - ew[0]) < 5.0e-3 * max(ew[2], 40.0)
        if sphere:
            for i in (7, 8, 10, 20):
                ielem[i] = 1
            st.cub = np.zeros((3, 3))
            st.cub[0, 1] = 1.0
            st.cub[1, 2] = 1.0
            st.cub[2, 0] = 1.0
            goto = "270"
            break
        elif linear:
            symopr(coord, 1, r)
            ielem[20] = 1
            goto = "250"
            break
        if not cubic and ew[2] - ew[1] < 1.0e-2 * ew[2]:
            for i in range(3):
                rxy = -r[i, 0]
                r[i, 0] = r[i, 2]
                r[i, 2] = rxy
            ew[0], ew[2] = ew[2], ew[0]
        axis = abs(ew[0] - ew[1]) < 0.01 * ew[1]
        symopr(coord, 1, r)
        if not cubic:
            break
        ielem[19] = 1
        cubic = _plato(coord, r, nat, None)
        if (not iscube) or cubic:
            break
        f = np.zeros(6)
        ij = 0
        for i in range(3):
            for j in range(i + 1):
                f[ij] = (ij + 1) * 1.0e-8
                for k in range(n):
                    s = 0.0
                    for l in range(n):
                        s += math.sqrt(float(np.sum((coord[:, k] - coord[:, l]) ** 2)))
                    f[ij] += s * coord[i, k] * coord[j, k]
                ij += 1
        f[0] = f[0] - 0.8 * f[0]
        f[2] = f[2] - 0.8 * f[0]
        f[5] = f[5] - 0.8 * f[0]
        ielem[19] = 0
        iscube = False
    if goto is None:
        if axis:
            while True:  # label 130
                iturn = 7
                restart = False
                for i in range(8, 19):
                    if i < 14:
                        tole = toler * 9.0 / (i - 5) ** 2
                    else:
                        tole = toler * 16.0 / (2 * i - 24) ** 2
                    chi(tole, coord, i, nat, st)
                    if ielem[i] != 1 or i >= 14:
                        continue
                    if iturn > 9:
                        toler = toler * 0.5
                        restart = True
                        break
                    iturn = i
                if restart:
                    continue
                if (
                    ielem[14] + ielem[15] + ielem[17] > 1
                    or ielem[15] + ielem[16] + ielem[17] > 1
                    or ielem[16] + ielem[17] + ielem[18] > 1
                ):
                    toler = toler * 0.5
                    continue
                break
            iturn = iturn - 5
            kndex = None
            ii = None
            for i in range(n):
                distxy = coord[0, i] ** 2 + coord[1, i] ** 2
                if distxy < toler:
                    continue
                rmin = 1000.0
                kndex = None
                for j in range(i + 1, n):
                    if abs(abs(coord[2, i]) - abs(coord[2, j])) > 0.2:
                        continue
                    rxy = coord[0, j] ** 2 + coord[1, j] ** 2
                    if abs(rxy - distxy) > toler or nat[i] != nat[j]:
                        continue
                    if nbonds[i] != nbonds[j]:
                        continue
                    used = [False] * (max(nbonds[i], nbonds[j]) + 2)
                    for k in range(nbonds[i]):
                        l = nbonds[j]
                        for ll in range(nbonds[j]):
                            if nat[ibonds[i][k]] == nat[ibonds[j][ll]] and not used[ll]:
                                l = ll
                                break
                        if l < nbonds[i]:
                            used[l] = True
                    cnt = sum(1 for k in range(nbonds[i]) if used[k])
                    if cnt < nbonds[i]:
                        continue
                    rxy = (coord[0, i] - coord[0, j]) ** 2 + (
                        coord[1, i] - coord[1, j]
                    ) ** 2
                    if rxy > rmin:
                        continue
                    kndex = j
                    rmin = rxy
                ii = i
                break
            if kndex is None:
                axis = False
            else:
                hx = coord[0, ii] + coord[0, kndex]
                hy = coord[1, ii] + coord[1, kndex]
                distxy = math.sqrt(hx**2 + hy**2)
                sina = hy / distxy
                cosa = hx / distxy
                rotmol(coord, sina, cosa, 1, 2, r)
                chi(toler, coord, 5, nat, st)
                if ielem[5] != 1:
                    chi(toler, coord, 1, nat, st)
                    if ielem[1] != 0:
                        theta = 1.5707963268 / float(iturn)
                        sina = math.sin(theta)
                        cosa = math.cos(theta)
                        icheck = 0
                        while True:  # label 180
                            rotmol(coord, sina, cosa, 1, 2, r)
                            if icheck > 0:
                                axis = iturn != 2
                                break
                            chi(toler, coord, 5, nat, st)
                            if ielem[5] > 0:
                                break
                            icheck = 1
                            sina = -sina
        # label 190
        if cubic:
            _orient(coord, r, nat, st)
        if not axis:
            toler = 0.2
            icyc = [0] * 8
            for i in range(1, 7):
                iq = chi(toler, coord, i, nat, st)
                icyc[i] = (1 + iq) * ielem[i]
            naxes = ielem[1] + ielem[2] + ielem[3]
            if naxes <= 1:
                iz = 1
                if ielem[1] == 1:
                    pass
                else:
                    iz = 2
                    if ielem[2] == 1:
                        pass
                    else:
                        iz = 3
                        if ielem[3] == 1:
                            pass
                        else:
                            if icyc[5] > icyc[4]:
                                iz = 2
                            if icyc[6] > icyc[7 - iz]:
                                iz = 1
            else:
                iz = 1
                if icyc[2] > icyc[1]:
                    iz = 2
                if icyc[3] > icyc[iz]:
                    iz = 3
            icyc[7 - iz] = -1
            ix = 1
            if icyc[5] > icyc[6]:
                ix = 2
            if icyc[4] > icyc[7 - ix]:
                ix = 3
            iy = 6 - ix - iz
            rhelp = np.zeros((3, 3))
            rhelp[:, 0] = r[:, ix - 1]
            rhelp[:, 1] = r[:, iy - 1]
            rhelp[0, 2] = r[1, ix - 1] * r[2, iy - 1] - r[2, ix - 1] * r[1, iy - 1]
            rhelp[1, 2] = r[2, ix - 1] * r[0, iy - 1] - r[0, ix - 1] * r[2, iy - 1]
            rhelp[2, 2] = r[0, ix - 1] * r[1, iy - 1] - r[1, ix - 1] * r[0, iy - 1]
            symopr(coord, -1, r)
            r = rhelp
            symopr(coord, 1, r)
        goto = "250"
    if goto == "250":
        for i in range(1, 8):
            chi(toler, coord, i, nat, st)
    symopr(coord, -1, r)
    total = ew.sum()
    ew = total - ew
    _cartab(st)
    return r


def _nope():
    nope = [0, 1]
    for i in range(2, 58):
        nope.append(nope[i - 1] + NALLOP[nope[i - 1]] + 4)
    return nope


def _symdec(n1, ielem):
    in1 = n1
    for i in range(1, 21):
        ibin = in1 % 2
        if ielem[i] != 1 and ibin == 1:
            return False
        in1 //= 2
    return True


def _cartab(st, nosym=False):
    nope = _nope()
    igroup = 57
    while igroup >= 1:
        if _symdec(NALLOP[nope[igroup] + 3], st.ielem):
            break
        igroup -= 1
    if igroup < 1:
        igroup = 1
    if nosym:
        igroup = 1
    st.igroup = igroup
    istart = nope[igroup]
    st.nclass = NALLOP[istart] + 1
    jy = [0] * 7
    for k in range(2, st.nclass + 1):
        jy[k] = NALLOP[istart + 4 + (k - 2)]
    st.jy = jy


def _makopr(coord, r, nat, st):
    symopr(coord, 1, r)
    if st.nclass < 2:
        return
    for i in range(2, st.nclass + 1):
        bldsym(st.jy[i], i, st)
    toler = 0.2
    for i in range(2, st.nclass + 1):
        chi(toler, coord, i, nat, st)
    symopr(coord, -1, r)


def point_group_ops(coord_lab, z, mass, nbonds, ibonds, nosym=False):
    """Replicates symtrz(itype=2): returns (list of 3x3 lab-frame operation matrices incl. identity first,
    igroup).  coord_lab: (n,3)."""
    n = len(z)
    nat = [int(z[i]) * 20 + int(round(mass[i] * 20.0)) for i in range(n)]
    st = SymState(n)
    cotim = np.array(coord_lab, float).T.copy()
    r = molsym(cotim, nat, nbonds, ibonds, st)
    if nosym:
        st.igroup = 1
        st.nclass = 1
    _makopr(cotim, r, nat, st)
    ops = [np.eye(3)]
    for i in range(2, st.nclass + 1):
        mult33(r, i, st)
        ops.append(st.elem[i].copy())
    return ops, st


def build_group(coord_lab, ops):
    """symr/symp: closure of the generators, with the atom permutation ipo (0-based, per operation).
    Returns (matrices list, ipo array (nsym, n)) or None on failure."""
    n = coord_lab.shape[0]
    x = coord_lab - coord_lab.sum(axis=0) / n
    mats = [np.eye(3)]
    ipo = [list(range(n))]
    for g in ops[1:]:
        mats.append(g.copy())
        p = []
        for i in range(n):
            h = g @ x[i]
            cand = [
                j
                for j in range(n)
                if abs(h[0] - x[j, 0]) + abs(h[1] - x[j, 1]) + abs(h[2] - x[j, 2]) < 0.6
            ]
            if len(cand) != 1:
                return None
            p.append(cand[0])
        ipo.append(p)
    nsym = len(mats)
    # symp: closure
    i, j = 2, 1
    maxfun = 120
    while True:
        j += 1
        if j > nsym:
            j = 2
            i += 1
            if i > nsym:
                break
        if nsym == maxfun:
            break
        ri = mats[i - 1]
        rj = mats[j - 1]
        new = ri @ rj
        dup = False
        for m in mats[:nsym]:
            if np.sum(np.abs(m - new)) < 1.0e-2:
                dup = True
                break
        if dup:
            continue
        mats.append(new)
        nsym += 1
        ipo.append([ipo[i - 1][ipo[j - 1][nn]] for nn in range(n)])
    return mats, np.array(ipo, int)
