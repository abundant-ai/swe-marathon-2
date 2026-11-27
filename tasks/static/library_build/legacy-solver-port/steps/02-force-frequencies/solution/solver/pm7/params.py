"""PM7 element parameters and the derived quantities MOPAC builds in CALPAR / INID.

Everything here is a function of the element only (no geometry).  The result is an
immutable ``Element`` record per atomic number, collected in ``ELEMENTS``.

Ports: models/calpar.F90, integrals/mndod.F90 (inid, aijm, ddpo, inighd, scprm, rsc,
poij), moldat.F90 (natorb/dorbs), parameters_C (tore, eheat, npq).
"""

import math
from dataclasses import dataclass, field

import numpy as np

from . import pm7_data as D
from .constants import EV, FPC_9, MASS

SUPPORTED = (1, 6, 7, 8, 9, 15, 16, 17, 35)


# principal quantum numbers used by the MNDO/d radial code ('iii', 'iiid' in mndod_C)
def _iii(z):
    # data iii/ 2*1, 8*2, 8*3, 18*4, 18*5, 32*6 /
    if z <= 2:
        return 1
    if z <= 10:
        return 2
    if z <= 18:
        return 3
    if z <= 36:
        return 4
    if z <= 54:
        return 5
    return 6


def _iiid(z):
    # data iiid/ 30*3, 18*4, 32*5, 6*6 /
    if z <= 30:
        return 3
    if z <= 48:
        return 4
    if z <= 80:
        return 5
    return 6


# ---------------------------------------------------------------- factorial / binomial tables
FX = [0.0] * 31  # fx(i) = (i-1)!  (1-based as in the Fortran)
FX[1] = 1.0
for _i in range(2, 31):
    FX[_i] = FX[_i - 1] * (_i - 1)
BN = [[0.0] * 31 for _ in range(31)]  # b(i,j) of fbx (1-based): Pascal triangle
for _i in range(1, 31):
    BN[_i][1] = 1.0
for _i in range(2, 31):
    for _j in range(2, _i + 1):
        BN[_i][_j] = BN[_i - 1][_j - 1] + BN[_i - 1][_j]


def rsc(k, na, ea, nb, eb, nc, ec, nd, ed):
    """Radial part of a one-center two-electron integral (Slater-Condon parameter)."""
    aea, aeb, aec, aed = math.log(ea), math.log(eb), math.log(ec), math.log(ed)
    nab = na + nb
    ncd = nc + nd
    ecd = ec + ed
    eab = ea + eb
    e = ecd + eab
    n = nab + ncd
    ae = math.log(e)
    a2 = math.log(2.0)
    acd = math.log(ecd)
    aab = math.log(eab)
    ff = FX[n] / math.sqrt(
        FX[2 * na + 1] * FX[2 * nb + 1] * FX[2 * nc + 1] * FX[2 * nd + 1]
    )
    c = (
        EV
        * ff
        * math.exp(
            na * aea
            + nb * aeb
            + nc * aec
            + nd * aed
            + 0.5 * (aea + aeb + aec + aed)
            + a2 * (n + 2)
            - ae * n
        )
    )
    s0 = 1.0 / e
    s1 = 0.0
    s2 = 0.0
    m = ncd - k
    for i in range(1, m + 1):
        s0 = s0 * e / ecd
        s1 += s0 * (BN[ncd - k][i] - BN[ncd + k + 1][i]) / BN[n][i]
    m1 = m + 1
    m2 = ncd + k + 1
    for i in range(m1, m2 + 1):
        s0 = s0 * e / ecd
        s2 += s0 * BN[m2][i] / BN[n][i]
    s3 = math.exp(ae * n - acd * m2 - aab * (nab - k)) / BN[n][m2]
    return c * (s1 - s2 + s3)


def poij(l, d, fg):
    """Additive term rho from the requirement that one-center integrals are reproduced."""
    if l == 0:
        return 0.5 * EV / fg
    epsil = 1.0e-8
    g1 = 0.382
    g2 = 0.618
    dsq = d * d
    ev4 = EV * 0.25
    ev8 = EV / 8.0
    a1 = 0.1
    a2 = 5.0
    f1 = 0.0
    f2 = 0.0
    for _ in range(100):
        delta = a2 - a1
        if delta < epsil:
            break
        y1 = a1 + delta * g1
        y2 = a1 + delta * g2
        if l == 1:
            f1 = (ev4 * (1.0 / y1 - 1.0 / math.sqrt(y1**2 + dsq)) - fg) ** 2
            f2 = (ev4 * (1.0 / y2 - 1.0 / math.sqrt(y2**2 + dsq)) - fg) ** 2
        elif l == 2:
            f1 = (
                ev8
                * (
                    1.0 / y1
                    - 2.0 / math.sqrt(y1**2 + dsq * 0.5)
                    + 1.0 / math.sqrt(y1**2 + dsq)
                )
                - fg
            ) ** 2
            f2 = (
                ev8
                * (
                    1.0 / y2
                    - 2.0 / math.sqrt(y2**2 + dsq * 0.5)
                    + 1.0 / math.sqrt(y2**2 + dsq)
                )
                - fg
            ) ** 2
        else:
            raise ValueError(l)
        if f1 < f2:
            a2 = y2
        else:
            a1 = y1
    return a2 if f1 >= f2 else a1


@dataclass
class Element:
    z: int
    symbol_mass: float
    natorb: int
    dorbs: bool
    tore: float
    eheat: float
    eisol: float
    npq: tuple
    # raw PM7 parameters
    uss: float
    upp: float
    udd: float
    betas: float
    betap: float
    betad: float
    zs: float
    zp: float
    zd: float
    zsn: float
    zpn: float
    zdn: float
    gss: float
    gsp: float
    gpp: float
    gp2: float
    hsp: float
    guess1: tuple
    guess2: tuple
    guess3: tuple
    # derived
    dd: float = 0.0
    qq: float = 0.0
    am: float = 0.0
    ad: float = 0.0
    aq: float = 0.0
    po: np.ndarray = field(default_factory=lambda: np.zeros(10))  # po[1..9]
    ddp: np.ndarray = field(default_factory=lambda: np.zeros(7))  # ddp[1..6]
    aij: np.ndarray = field(default_factory=lambda: np.zeros(7))  # aij[1..6]
    repd: np.ndarray = field(default_factory=lambda: np.zeros(53))  # repd[1..52]
    onecenter: np.ndarray = (
        None  # full 4-index one-center integral tensor (n,n,n,n), eV
    )


def _build_element(z):
    p = D.ELEMENT_PARAMS[z]
    g = D.GUESS[z]
    zs, zp, zd = p.get("zs7", 0.0), p.get("zp7", 0.0), p.get("zd7", 0.0)
    dorbs = zd > 1e-8
    if dorbs:
        natorb = 9
    elif zp > 1e-20:
        natorb = 4
    elif zs > 1e-20:
        natorb = 1
    else:
        natorb = 0
    ios, iop, iod = D.IOS[z - 1], D.IOP[z - 1], D.IOD[z - 1]
    el = Element(
        z=z,
        symbol_mass=MASS[z],
        natorb=natorb,
        dorbs=dorbs,
        tore=float(ios + iop + iod),
        eheat=D.EHEAT[z],
        eisol=0.0,
        npq=tuple(int(D.NPQ[k][z - 1]) for k in range(3)),
        uss=p.get("uss7", 0.0),
        upp=p.get("upp7", 0.0),
        udd=p.get("udd7", 0.0),
        betas=p.get("betas7", 0.0),
        betap=p.get("betap7", 0.0),
        betad=p.get("betad7", 0.0),
        zs=zs,
        zp=zp,
        zd=zd,
        zsn=p.get("zsn7", 0.0),
        zpn=p.get("zpn7", 0.0),
        zdn=p.get("zdn7", 0.0),
        gss=p.get("gss7", 0.0),
        gsp=p.get("gsp7", 0.0),
        gpp=p.get("gpp7", 0.0),
        gp2=p.get("gp27", 0.0),
        hsp=p.get("hsp7", 0.0),
        guess1=tuple(g[1]),
        guess2=tuple(g[2]),
        guess3=tuple(g[3]),
    )
    return el, int(ios), int(iop), int(iod)


def _calpar(el, ios, iop, iod):
    """Port of CALPAR for a main-group element (one z)."""
    z = el.z
    p4 = 2.0**4
    gssc = max(ios - 1, 0)
    k = iop
    gspc = ios * k
    l = min(k, 6 - k)
    gp2c = (k * (k - 1)) / 2 + 0.5 * (l * (l - 1)) / 2
    gppc = -0.5 * (l * (l - 1)) / 2
    hspc = -k * ios * 0.5
    if z != 1 and not (el.zp < 1e-4 and el.zs < 1e-4):
        el.zp = max(0.3, el.zp)
        hpp = 0.5 * (el.gpp - el.gp2)
        hpp = max(0.1, hpp)
        el.hsp = max(1e-7, el.hsp)
        el.eisol = (
            el.uss * ios
            + el.upp * iop
            + el.udd * iod
            + el.gss * gssc
            + el.gpp * gppc
            + el.gsp * gspc
            + el.gp2 * gp2c
            + el.hsp * hspc
        )
        qn = (
            1
            if z <= 2
            else (
                2
                if z <= 10
                else (3 if z <= 18 else (4 if z <= 36 else (5 if z <= 54 else 6)))
            )
        )
        zs, zp = el.zs, el.zp
        el.dd = (
            (2.0 * qn + 1)
            * (4.0 * zs * zp) ** (qn + 0.5)
            / (zs + zp) ** (2.0 * qn + 2)
            / math.sqrt(3.0)
        )
        el.qq = math.sqrt((4.0 * qn * qn + 6.0 * qn + 2.0) / 20.0) / zp
        jmax = 5
        gdd1 = (el.hsp / (EV * el.dd**2)) ** (1.0 / 3.0)
        d1 = gdd1
        d2 = gdd1 + 0.04
        for _ in range(jmax):
            df = d2 - d1
            hsp1 = 0.5 * d1 - 0.5 / math.sqrt(4.0 * el.dd**2 + 1.0 / d1**2)
            hsp2 = 0.5 * d2 - 0.5 / math.sqrt(4.0 * el.dd**2 + 1.0 / d2**2)
            if abs(hsp2 - hsp1) < 1e-25:
                break
            d3 = d1 + df * (el.hsp / EV - hsp1) / (hsp2 - hsp1)
            d1 = d2
            d2 = d3
        gqq = (p4 * hpp / (EV * 48.0 * el.qq**4)) ** 0.2
        q1 = gqq
        q2 = gqq + 0.04
        for _ in range(jmax):
            qf = q2 - q1
            hpp1 = (
                0.25 * q1
                - 0.5 / math.sqrt(4.0 * el.qq**2 + 1.0 / q1**2)
                + 0.25 / math.sqrt(8.0 * el.qq**2 + 1.0 / q1**2)
            )
            hpp2 = (
                0.25 * q2
                - 0.5 / math.sqrt(4.0 * el.qq**2 + 1.0 / q2**2)
                + 0.25 / math.sqrt(8.0 * el.qq**2 + 1.0 / q2**2)
            )
            if abs(hpp2 - hpp1) < 1e-25:
                break
            q3 = q1 + qf * (hpp / EV - hpp1) / (hpp2 - hpp1)
            q1 = q2
            q2 = q3
        el.am = el.gss / EV
        el.ad = d2
        el.aq = q2
    if el.am < 1e-20:
        el.am = el.gss / EV if el.gss > 1e-20 else 1.0
    if z == 1:
        el.eisol = el.uss
        el.am = el.gss / EV
        el.ad = el.am
        el.aq = el.am


def _inid(el):
    """Port of INID for one element (d-orbital radial integrals, additive terms)."""
    z = el.z
    po = np.zeros(10)
    ddp = np.zeros(7)
    aij = np.zeros(7)
    repd = np.zeros(53)
    if el.dorbs:
        # AIJM
        z1, z2, z3 = el.zs, el.zp, el.zd
        nsp = _iii(z)
        nd = _iiid(z)

        def aijl(za, zb, n1, n2, l):
            zz = za + zb + 1e-20
            return (
                FX[n1 + n2 + l + 1]
                / math.sqrt(FX[2 * n1 + 1] * FX[2 * n2 + 1])
                * (2 * za / zz) ** n1
                * math.sqrt(2 * za / zz)
                * (2 * zb / zz) ** n2
                * math.sqrt(2 * zb / zz)
                * 2**l
                / zz**l
            )

        if z >= 3 and z1 * z2 >= 0.01:
            aij[2] = aijl(z1, z2, nsp, nsp, 1)
            aij[3] = aijl(z2, z2, nsp, nsp, 2)
            aij[4] = aijl(z1, z3, nsp, nd, 2)
            aij[5] = aijl(z2, z3, nsp, nd, 1)
            aij[6] = aijl(z3, z3, nd, nd, 2)
        # INIGHD
        if el.zdn > 1e-4:
            ns, ndd = nsp, nd
            es, ep, ed = el.zsn, el.zpn, el.zdn
            r016 = rsc(0, ns, es, ns, es, ndd, ed, ndd, ed)
            r036 = rsc(0, ns, ep, ns, ep, ndd, ed, ndd, ed)
            r066 = rsc(0, ndd, ed, ndd, ed, ndd, ed, ndd, ed)
            r155 = rsc(1, ns, ep, ndd, ed, ns, ep, ndd, ed)
            r125 = rsc(1, ns, es, ns, ep, ns, ep, ndd, ed)
            r244 = rsc(2, ns, es, ndd, ed, ns, es, ndd, ed)
            r236 = rsc(2, ns, ep, ns, ep, ndd, ed, ndd, ed)
            r266 = rsc(2, ndd, ed, ndd, ed, ndd, ed, ndd, ed)
            r234 = rsc(2, ns, ep, ns, ep, ns, es, ndd, ed)
            r246 = rsc(2, ns, es, ndd, ed, ndd, ed, ndd, ed)
            r355 = rsc(3, ns, ep, ndd, ed, ns, ep, ndd, ed)
            r466 = rsc(4, ndd, ed, ndd, ed, ndd, ed, ndd, ed)
            # f0sd / g2sd are zero for these elements (main group)
            s3 = 1.7320508
            s5 = 2.23606797
            s15 = 3.87298334
            r = repd
            r[1] = r016
            r[2] = 2.0 / (3.0 * s5) * r125
            r[3] = 1.0 / s15 * r125
            r[4] = 2.0 / (5.0 * s5) * r234
            r[5] = r036 + 4.0 / 35.0 * r236
            r[6] = r036 + 2.0 / 35.0 * r236
            r[7] = r036 - 4.0 / 35.0 * r236
            r[8] = -1.0 / (3.0 * s5) * r125
            r[9] = math.sqrt(3.0 / 125.0) * r234
            r[10] = s3 / 35.0 * r236
            r[11] = 3.0 / 35.0 * r236
            r[12] = -1.0 / (5.0 * s5) * r234
            r[13] = r036 - 2.0 / 35.0 * r236
            r[14] = -2.0 * s3 / 35.0 * r236
            r[15] = -r[3]
            r[16] = -r[11]
            r[17] = -r[9]
            r[18] = -r[14]
            r[19] = 1.0 / 5.0 * r244
            r[20] = 2.0 / (7.0 * s5) * r246
            r[21] = r[20] / 2.0
            r[22] = -r[20]
            r[23] = 4.0 / 15.0 * r155 + 27.0 / 245.0 * r355
            r[24] = 2.0 * s3 / 15.0 * r155 - 9.0 * s3 / 245.0 * r355
            r[25] = 1.0 / 15.0 * r155 + 18.0 / 245.0 * r355
            r[26] = (-s3 / 15.0 * r155) + 12.0 * s3 / 245.0 * r355
            r[27] = (-s3 / 15.0 * r155) - 3.0 * s3 / 245.0 * r355
            r[28] = -r[27]
            r[29] = r066 + 4.0 / 49.0 * r266 + 4.0 / 49.0 * r466
            r[30] = r066 + 2.0 / 49.0 * r266 - 24.0 / 441.0 * r466
            r[31] = r066 - 4.0 / 49.0 * r266 + 6.0 / 441.0 * r466
            r[32] = math.sqrt(3.0 / 245.0) * r246
            r[33] = 1.0 / 5.0 * r155 + 24.0 / 245.0 * r355
            r[34] = 1.0 / 5.0 * r155 - 6.0 / 245.0 * r355
            r[35] = 3.0 / 49.0 * r355
            r[36] = 1.0 / 49.0 * r266 + 30.0 / 441.0 * r466
            r[37] = s3 / 49.0 * r266 - 5.0 * s3 / 441.0 * r466
            r[38] = r066 - 2.0 / 49.0 * r266 - 4.0 / 441.0 * r466
            r[39] = (-2.0 * s3 / 49.0 * r266) + 10.0 * s3 / 441.0 * r466
            r[40] = -r[32]
            r[41] = -r[34]
            r[42] = -r[35]
            r[43] = -r[37]
            r[44] = 3.0 / 49.0 * r266 + 20.0 / 441.0 * r466
            r[45] = -r[39]
            r[46] = 1.0 / 5.0 * r155 - 3.0 / 35.0 * r355
            r[47] = -r[46]
            r[48] = 4.0 / 49.0 * r266 + 15.0 / 441.0 * r466
            r[49] = 3.0 / 49.0 * r266 - 5.0 / 147.0 * r466
            r[50] = -r[49]
            r[51] = r066 + 4.0 / 49.0 * r266 - 34.0 / 441.0 * r466
            r[52] = 35.0 / 441.0 * r466
        # DDPO (uses repd and aij)
        if el.gss > 0.1:
            po[1] = poij(0, 1.0, el.gss)
        if z >= 3:
            d = aij[2] / math.sqrt(12.0)
            ddp[2] = d
            po[2] = poij(1, d, el.hsp)
            po[7] = po[1]
            d = math.sqrt(aij[3] * 0.1)
            ddp[3] = d
            po[3] = poij(2, d, 0.5 * (el.gpp - el.gp2))
            da = math.sqrt(1.0 / 60.0)
            d = math.sqrt(aij[4] * da)
            ddp[4] = d
            po[4] = poij(2, d, repd[19])
            d = aij[5] / math.sqrt(20.0)
            ddp[5] = d
            po[5] = poij(1, d, repd[23] - 1.8 * repd[35])
            fg = 0.2 * (repd[29] + 2.0 * repd[30] + 2.0 * repd[31])
            po[8] = poij(0, 1.0, fg) if fg > 1e-5 else 1e5
            d = math.sqrt(aij[6] / 14.0)
            ddp[6] = d
            po[6] = poij(2, d, repd[44] - (20.0 / 35.0) * repd[52])
    # second loop of INID (main group / small basis)
    if el.am < 1e-4:
        el.am = 1.0
    po[1] = 0.5 / el.am
    if el.ad > 1e-5:
        po[2] = 0.5 / el.ad
    if el.aq > 1e-5:
        po[3] = 0.5 / el.aq
    po[7] = po[1]
    ddp[2] = el.dd
    ddp[3] = el.qq * math.sqrt(2.0)
    po[9] = po[1]  # pocord is zero for these elements
    if z == 1:
        po[2] = 0.0
        po[3] = 0.0
    el.po, el.ddp, el.aij, el.repd = po, ddp, aij, repd


def _onecenter_tensor(el):
    """Full (n,n,n,n) tensor of one-center two-electron integrals (eV), from WSTORE."""
    n = el.natorb
    if n == 0:
        return np.zeros((0, 0, 0, 0))
    ntri = n * (n + 1) // 2
    w = np.zeros((ntri + 1, ntri + 1))  # 1-based packed pair indices

    def pk(i, j):  # 1-based orbitals -> packed index (i>=j)
        if i < j:
            i, j = j, i
        return i * (i - 1) // 2 + j

    w[1, 1] = el.gss
    if n > 2:
        ipx, ipy, ipz = 3, 6, 10
        for a in (ipx, ipy, ipz):
            w[a, 1] = el.gsp
            w[1, a] = el.gsp
            w[a, a] = el.gpp
        w[ipy, ipx] = w[ipz, ipx] = w[ipz, ipy] = el.gp2
        w[ipx, ipy] = w[ipx, ipz] = w[ipy, ipz] = el.gp2
        w[2, 2] = el.hsp
        w[4, 4] = el.hsp
        w[7, 7] = el.hsp
        hpp = 0.5 * (el.gpp - el.gp2)
        w[5, 5] = hpp
        w[8, 8] = hpp
        w[9, 9] = hpp
        if ntri > 10:
            for i in range(243):
                w[D.D_INTIJ[i], D.D_INTKL[i]] = el.repd[D.D_INTREP[i]]
    g = np.zeros((n, n, n, n))
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            for k in range(1, n + 1):
                for l in range(1, n + 1):
                    g[i - 1, j - 1, k - 1, l - 1] = w[pk(i, j), pk(k, l)]
    return g


def build_elements():
    out = {}
    for z in SUPPORTED:
        el, ios, iop, iod = _build_element(z)
        _calpar(el, ios, iop, iod)
        _inid(el)
        el.onecenter = _onecenter_tensor(el)
        out[z] = el
    return out


ELEMENTS = build_elements()

# bond parameters (alpb, xfac) symmetrised, with the PM7 average-guess rule applied lazily
ALPB = {}
XFAC = {}
for (_i, _j), _v in D.ALPB.items():
    ALPB[(_i, _j)] = _v
    ALPB[(_j, _i)] = _v
for (_i, _j), _v in D.XFAC.items():
    XFAC[(_i, _j)] = _v
    XFAC[(_j, _i)] = _v

V_PAR = D.V_PAR
