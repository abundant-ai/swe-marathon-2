"""Core Hamiltonian, two-electron integral lists and the two-electron Fock builder.

The state object ``Hamiltonian`` is built from a geometry (port of HCORE) and is immutable
afterwards:

    h        (N,N)   one-electron matrix (eV): U_ss/pp/dd, beta*S, core attraction
    enuclr   float   core-core repulsion (eV)
    one-/two-center integral lists used by ``fock_two_electron``.
"""

from dataclasses import dataclass

import numpy as np

from .overlap import h1elec
from .params import ELEMENTS
from .twocenter import pair_integrals


@dataclass
class Hamiltonian:
    norbs: int
    h: np.ndarray
    enuclr: float
    # two-center lists (entries for atom pairs i>j; mu,nu on i ; la,si on j)
    t_mu: np.ndarray
    t_nu: np.ndarray
    t_la: np.ndarray
    t_si: np.ndarray
    t_w: np.ndarray
    # one-center lists
    o_a: np.ndarray
    o_b: np.ndarray
    o_c: np.ndarray
    o_d: np.ndarray
    o_w: np.ndarray

    def __post_init__(self):
        n = self.norbs
        self._t_mn = self.t_mu * n + self.t_nu
        self._t_ls = self.t_la * n + self.t_si
        self._t_ml = self.t_mu * n + self.t_la
        self._t_ns = self.t_nu * n + self.t_si
        self._o_ab = self.o_a * n + self.o_b
        self._o_cd = self.o_c * n + self.o_d
        self._o_ac = self.o_a * n + self.o_c
        self._o_bd = self.o_b * n + self.o_d

    # ------------------------------------------------------------------
    def coulomb(self, ptot):
        n = self.norbs
        pf = ptot.ravel()
        j = np.zeros(n * n)
        j += np.bincount(self._t_mn, weights=self.t_w * pf[self._t_ls], minlength=n * n)
        j += np.bincount(self._t_ls, weights=self.t_w * pf[self._t_mn], minlength=n * n)
        j += np.bincount(self._o_ab, weights=self.o_w * pf[self._o_cd], minlength=n * n)
        return j.reshape(n, n)

    def exchange(self, pspin):
        n = self.norbs
        pf = pspin.ravel()
        k = np.zeros(n * n)
        k += np.bincount(self._t_ml, weights=self.t_w * pf[self._t_ns], minlength=n * n)
        k = k.reshape(n, n)
        k = k + k.T
        k += np.bincount(
            self._o_ac, weights=self.o_w * pf[self._o_bd], minlength=n * n
        ).reshape(n, n)
        return k

    def fock_two_electron(self, ptot, pspin, jmat=None):
        """G = J(Ptot) - K(Pspin); F = h + G."""
        if jmat is None:
            jmat = self.coulomb(ptot)
        return jmat - self.exchange(pspin)


def build_hamiltonian(z, coords, offsets):
    """Port of HCORE for an isolated molecule."""
    n = int(offsets[-1])
    nat = len(z)
    h = np.zeros((n, n))
    enuclr = 0.0
    tm, tn, tl, ts, tw = [], [], [], [], []
    oa, ob, oc, od, ow = [], [], [], [], []
    for i in range(nat):
        ei = ELEMENTS[z[i]]
        ia = offsets[i]
        na = ei.natorb
        for k, u in enumerate(_uspd(ei)):
            h[ia + k, ia + k] = u
        g1 = ei.onecenter
        a, b, c, d = np.meshgrid(
            np.arange(na), np.arange(na), np.arange(na), np.arange(na), indexing="ij"
        )
        nz = g1 != 0.0
        oa.append((a + ia)[nz])
        ob.append((b + ia)[nz])
        oc.append((c + ia)[nz])
        od.append((d + ia)[nz])
        ow.append(g1[nz])
        for j in range(i):
            ej = ELEMENTS[z[j]]
            ja = offsets[j]
            nb = ej.natorb
            di = h1elec(z[i], z[j], coords[i], coords[j])
            h[ia : ia + na, ja : ja + nb] += di
            h[ja : ja + nb, ia : ia + na] += di.T
            W, Vi, Vj, enuc = pair_integrals(z[i], z[j], coords[i], coords[j])
            enuclr += enuc
            h[ia : ia + na, ia : ia + na] += Vi
            h[ja : ja + nb, ja : ja + nb] += Vj
            if W.size:
                m, nn, l, s = np.meshgrid(
                    np.arange(na),
                    np.arange(na),
                    np.arange(nb),
                    np.arange(nb),
                    indexing="ij",
                )
                nzw = W != 0.0
                tm.append((m + ia)[nzw])
                tn.append((nn + ia)[nzw])
                tl.append((l + ja)[nzw])
                ts.append((s + ja)[nzw])
                tw.append(W[nzw])

    def cat(lst, dt=float):
        return np.concatenate(lst) if lst else np.zeros(0, dtype=dt)

    return Hamiltonian(
        n,
        h,
        enuclr,
        cat(tm, int),
        cat(tn, int),
        cat(tl, int),
        cat(ts, int),
        cat(tw),
        cat(oa, int),
        cat(ob, int),
        cat(oc, int),
        cat(od, int),
        cat(ow),
    )


def _uspd(el):
    u = [el.uss]
    if el.natorb > 1:
        u += [el.upp] * 3
    if el.natorb > 4:
        u += [el.udd] * 5
    return u
