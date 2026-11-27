"""PM7 single point for protein-size systems (linear-scaling SCF).

Physics is the same as the dense code (same pair integrals, overlaps, core-core terms and
post-SCF corrections); what changes is how it is organised:

* Pairs closer than 7 A (TRUNC_1) use the exact NDDO two-center integrals.  Beyond 7 A the
  PM7 feathering turns every two-center quantity into a point-charge interaction
  (checked numerically in NOTES.md), so those pairs are handled with a monopole field
  (dense atom-atom 1/R matrix) plus the point-charge exchange term -pt*P_{mu,la} on the
  sparsity pattern (pairs up to RK), and the resonance integrals up to RH.
* All matrices (H, F, P) live in one block-sparse pattern stored as CSR data arrays.
* The density matrix comes from a divide-and-conquer scheme: overlapping subsystems (core atoms
  + buffer shell) are diagonalised densely, with one common Fermi level so that the electron
  count is exact.  Subsystem diagonalisations run in threads (LAPACK releases the GIL).
"""

import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import scipy.sparse as sp
from scipy.spatial import cKDTree

from . import scale_corr
from .constants import A0, EV, FPC_9
from .energy import base_atheat
from .overlap import h1elec
from .params import ELEMENTS
from .system import Electrons
from .twocenter import ccrep, pair_integrals

RNEAR = 7.0  # exact two-center integrals below this distance (TRUNC_1)
VERBOSE = bool(os.environ.get("PM7_VERBOSE"))
_T0 = time.time()


def log(*a):
    if VERBOSE:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
            1e6 if sys.platform == "darwin" else 1e3
        )
        print(
            "[scale %.1fs %.1fGB]" % (time.time() - _T0, rss),
            *a,
            file=sys.stderr,
            flush=True,
        )


def ncpu():
    try:
        n = len(os.sched_getaffinity(0))
    except Exception:
        n = os.cpu_count() or 1
    return max(1, min(n, 8))


_G = {}


def _pair_worker(args):
    key, lo, hi = args
    z, xyz, I, J = _G["z"], _G["xyz"], _G["I"], _G["J"]
    idx = _G["groups"][key][lo:hi]
    nA, nB = key
    m = len(idx)
    h1 = np.zeros((m, nA, nB))
    W4 = np.zeros((m, nA, nA, nB, nB))
    e1b = np.zeros((m, nA, nA))
    e2a = np.zeros((m, nB, nB))
    enuc = np.zeros(m)
    for k, p in enumerate(idx):
        i, j = I[p], J[p]
        h1[k] = h1elec(z[i], z[j], xyz[i], xyz[j])
        W, Vi, Vj, en = pair_integrals(z[i], z[j], xyz[i], xyz[j])
        if W.size:
            W4[k] = W
        e1b[k] = Vi
        e2a[k] = Vj
        enuc[k] = en
    return key, lo, h1, W4, e1b, e2a, enuc


def _h1_worker(args):
    key, lo, hi = args
    z, xyz, I, J = _G["z"], _G["xyz"], _G["I"], _G["J"]
    idx = _G["groups"][key][lo:hi]
    nA, nB = key
    h1 = np.zeros((len(idx), nA, nB))
    for k, p in enumerate(idx):
        i, j = I[p], J[p]
        h1[k] = h1elec(z[i], z[j], xyz[i], xyz[j])
    return key, lo, h1


class Cls:
    pass


class NotSupported(Exception):
    pass


def _run_tasks(fn, tasks, nproc):
    out = []
    if nproc > 1 and len(tasks) > 1:
        import multiprocessing as mp

        ctx = mp.get_context("fork")
        with ctx.Pool(nproc) as pool:
            for r in pool.imap_unordered(fn, tasks):
                out.append(r)
    else:
        for t in tasks:
            out.append(fn(t))
    return out


class BigCalc:
    def __init__(self, z, xyz, charge, rk=10.0, rh=9.0, nthreads=None):
        self.z = list(z)
        self.xyz = np.asarray(xyz, float)
        self.nat = len(z)
        self.rk = rk
        self.rh = rh
        self.nthreads = nthreads or ncpu()
        el = Electrons(z, charge, False, 0)
        self.el = el
        if el.uhf:
            raise NotSupported(
                "open-shell systems are not supported by the large-system path"
            )
        self.norb = el.norbs
        self.nfirst = np.asarray(el.offsets[:-1])
        self.nsz = np.array(el.natorb)
        self.zarr = np.array(z)
        self.tore = np.array([ELEMENTS[v].tore for v in z])
        self.nel = el.nelecs
        self.orb_atom = np.repeat(np.arange(self.nat), self.nsz)

    # ------------------------------------------------------------------ static part
    def build_static(self):
        z, xyz, nat = self.z, self.xyz, self.nat
        tree = cKDTree(xyz)
        self.tree = tree
        pr = tree.query_pairs(max(self.rk, self.rh), output_type="ndarray")
        a, b = pr[:, 0], pr[:, 1]
        I = np.maximum(a, b)
        J = np.minimum(a, b)
        order = np.lexsort((J, I))
        I, J = I[order], J[order]
        d = np.sqrt(((xyz[I] - xyz[J]) ** 2).sum(1))
        near = d < RNEAR
        self.npair = len(I)
        log("pairs", len(I), "near", int(near.sum()))
        nsz = self.nsz
        # classes: near pairs (full integrals) and mid pairs (resonance integral + point-charge exchange)
        _G.update(z=z, xyz=xyz, I=I, J=J)
        groups_n, groups_m, groups_h = {}, {}, {}
        for key in set(zip(nsz[I].tolist(), nsz[J].tolist())):
            sel = (nsz[I] == key[0]) & (nsz[J] == key[1])
            gn = np.nonzero(sel & near)[0]
            gm = np.nonzero(sel & ~near)[0]
            if len(gn):
                groups_n[key] = gn
            if len(gm):
                groups_m[key] = gm
        # mid pairs beyond rh keep only the exchange pattern (h1 = 0)
        h_ok = d <= self.rh
        tasks_n, tasks_m = [], []
        for key, idx in groups_n.items():
            chunk = max(100, min(2000, len(idx) // (self.nthreads * 6) + 1))
            for lo in range(0, len(idx), chunk):
                tasks_n.append((key, lo, min(len(idx), lo + chunk)))
        # mid group: h1 only for pairs within rh
        groups_mh = {}
        for key, idx in groups_m.items():
            ih = idx[h_ok[idx]]
            if len(ih):
                groups_mh[key] = ih
        for key, idx in groups_mh.items():
            chunk = max(100, min(4000, len(idx) // (self.nthreads * 6) + 1))
            for lo in range(0, len(idx), chunk):
                tasks_m.append((key, lo, min(len(idx), lo + chunk)))
        t0 = time.time()
        _G["groups"] = groups_n
        res_n = _run_tasks(
            _pair_worker, tasks_n, self.nthreads if self.npair > 500 else 1
        )
        log("near pair integrals %.1fs" % (time.time() - t0))
        t0 = time.time()
        _G["groups"] = groups_mh
        res_m = _run_tasks(
            _h1_worker, tasks_m, self.nthreads if self.npair > 500 else 1
        )
        log("mid resonance integrals %.1fs" % (time.time() - t0))
        _G.clear()
        rn = {}
        for r in res_n:
            rn[(r[0], r[1])] = r[2:]
        rm = {}
        for r in res_m:
            rm[(r[0], r[1])] = r[2]
        self.classes = []
        enuc_near = 0.0
        for key in sorted(set(groups_n) | set(groups_m)):
            nA, nB = key
            c = Cls()
            c.nA, c.nB = nA, nB
            parts = []
            if key in groups_n:
                los = sorted(l for (k, l) in rn if k == key)
                p_ = [rn[(key, l)] for l in los]
                gi = groups_n[key]
                c.iA_n, c.iB_n = I[gi], J[gi]
                c.h1_n = np.concatenate([q[0] for q in p_])
                c.W4 = np.concatenate([q[1] for q in p_])
                c.e1b = np.concatenate([q[2] for q in p_])
                c.e2a = np.concatenate([q[3] for q in p_])
                enuc_near += float(np.concatenate([q[4] for q in p_]).sum())
            else:
                c.iA_n = np.zeros(0, int)
                c.iB_n = np.zeros(0, int)
                c.h1_n = np.zeros((0, nA, nB))
                c.W4 = np.zeros((0, nA, nA, nB, nB))
                c.e1b = np.zeros((0, nA, nA))
                c.e2a = np.zeros((0, nB, nB))
            if key in groups_m:
                gm = groups_m[key]
                c.iA_m, c.iB_m = I[gm], J[gm]
                c.h1_m = np.zeros((len(gm), nA, nB))
                if key in groups_mh:
                    ih = groups_mh[key]
                    los = sorted(l for (k, l) in rm if k == key)
                    hh = np.concatenate([rm[(key, l)] for l in los])
                    # groups_mh[key] is a subset of groups_m[key] (same order)
                    pos = np.searchsorted(gm, ih)
                    c.h1_m[pos] = hh
                c.pt_m = EV * A0 / d[gm]
            else:
                c.iA_m = np.zeros(0, int)
                c.iB_m = np.zeros(0, int)
                c.h1_m = np.zeros((0, nA, nB))
                c.pt_m = np.zeros(0)
            self.classes.append(c)
        self._enuc_near = enuc_near
        del rn, rm, res_n, res_m
        self._build_pattern()
        self._far_setup(d, I, J, near)
        log("static done; nnz", self.nnz)

    def _build_pattern(self):
        nsz, nf = self.nsz, self.nfirst
        N = self.norb
        nat = self.nat
        dsize = nsz**2
        doff = np.concatenate([[0], np.cumsum(dsize)])
        eid_list, row_list, col_list = [], [], []
        for n in sorted(set(nsz.tolist())):
            ats = np.nonzero(nsz == n)[0]
            r_ = (
                nf[ats][:, None, None]
                + np.arange(n)[None, :, None]
                + np.zeros((1, 1, n), dtype=int)
            )
            c_ = (
                nf[ats][:, None, None]
                + np.zeros((1, n, 1), dtype=int)
                + np.arange(n)[None, None, :]
            )
            e_ = doff[ats][:, None, None] + np.arange(n * n).reshape(1, n, n)
            eid_list.append(e_.ravel().astype(np.int32))
            row_list.append(r_.ravel().astype(np.int32))
            col_list.append(c_.ravel().astype(np.int32))
        base = int(doff[-1])
        for c in self.classes:
            nA, nB = c.nA, c.nB
            iA = np.concatenate([c.iA_n, c.iA_m])
            iB = np.concatenate([c.iB_n, c.iB_m])
            c.iA, c.iB = iA, iB
            p = len(iA)
            rA = (
                nf[iA][:, None, None]
                + np.arange(nA)[None, :, None]
                + np.zeros((1, 1, nB), dtype=int)
            )
            cB = (
                nf[iB][:, None, None]
                + np.zeros((1, nA, 1), dtype=int)
                + np.arange(nB)[None, None, :]
            )
            eU = base + np.arange(p * nA * nB).reshape(p, nA, nB)
            base += p * nA * nB
            eL = base + np.arange(p * nA * nB).reshape(p, nA, nB)
            base += p * nA * nB
            eid_list += [eU.ravel().astype(np.int32), eL.ravel().astype(np.int32)]
            rA32 = rA.ravel().astype(np.int32)
            cB32 = cB.ravel().astype(np.int32)
            row_list += [rA32, cB32]
            col_list += [cB32, rA32]
            c.eU, c.eL = eU.astype(np.int32), eL.astype(np.int32)
            del rA, cB, eU, eL
        eid = np.concatenate(eid_list)
        row = np.concatenate(row_list)
        col = np.concatenate(col_list)
        nnz = len(eid)
        self.nnz = nnz
        key = row.astype(np.int64) * N + col
        perm = np.argsort(key, kind="stable")
        del key
        pos_of_eid = np.empty(nnz, dtype=np.int32)
        pos_of_eid[eid[perm]] = np.arange(nnz, dtype=np.int32)
        rs = row[perm]
        cs = col[perm]
        self.indices = cs.astype(np.int32)
        self.indptr = np.concatenate(
            [[0], np.cumsum(np.bincount(rs, minlength=N))]
        ).astype(np.int64)
        del perm, eid, row, col, rs, cs
        self.dpos_atom = {}
        for n in sorted(set(nsz.tolist())):
            ats = np.nonzero(nsz == n)[0]
            self.dpos_atom[n] = (
                ats,
                pos_of_eid[
                    doff[ats][:, None, None] + np.arange(n * n).reshape(1, n, n)
                ],
            )
        dpos_flat = pos_of_eid[: int(doff[-1])]
        for c in self.classes:
            c.pU = pos_of_eid[c.eU]
            c.pL = pos_of_eid[c.eL]
            del c.eU, c.eL
            c.pDA = dpos_flat[
                doff[c.iA][:, None] + np.arange(c.nA**2)[None, :]
            ].reshape(-1, c.nA, c.nA)
            c.pDB = dpos_flat[
                doff[c.iB][:, None] + np.arange(c.nB**2)[None, :]
            ].reshape(-1, c.nB, c.nB)
            c.nn = len(c.iA_n)
        dg = np.empty(N, dtype=np.int32)
        for n, (ats, pp) in self.dpos_atom.items():
            for a_ in range(n):
                dg[nf[ats] + a_] = pp[:, a_, a_]
        self.diagpos = dg
        del pos_of_eid
        # one-electron Hamiltonian in pattern storage
        Hd = np.zeros(nnz)
        uspd = np.concatenate([self._uspd(v) for v in self.z])
        Hd[dg] += uspd
        wpos, wval = [], []
        kpt = np.zeros(nnz)
        for c in self.classes:
            nn = c.nn
            h1 = np.concatenate([c.h1_n, c.h1_m])
            Hd[c.pU] = h1
            Hd[c.pL] = h1
            wpos += [c.pDA[:nn].ravel(), c.pDB[:nn].ravel()]
            wval += [c.e1b.ravel(), c.e2a.ravel()]
            ptb = np.broadcast_to(c.pt_m[:, None, None], (len(c.pt_m), c.nA, c.nB))
            kpt[c.pU[nn:]] = ptb
            kpt[c.pL[nn:]] = ptb
            c.pU_n, c.pL_n = c.pU[:nn], c.pL[:nn]
            c.h1_n = c.h1_m = None
        Hd += np.bincount(np.concatenate(wpos), np.concatenate(wval), minlength=nnz)
        self.H = Hd
        self.kpt = kpt
        # transposition permutation
        rows_ = np.repeat(np.arange(N), np.diff(self.indptr))
        key = self.indices.astype(np.int64) * N + rows_
        o = np.argsort(key, kind="stable")
        tperm = np.empty(nnz, dtype=np.int32)
        tperm[o] = np.arange(nnz, dtype=np.int32)
        self.tperm = tperm
        self.rows_ = rows_.astype(np.int32)
        del key, o

    @staticmethod
    def _uspd(zz):
        e = ELEMENTS[zz]
        u = [e.uss]
        if e.natorb > 1:
            u += [e.upp] * 3
        if e.natorb > 4:
            u += [e.udd] * 5
        return np.array(u)

    def _far_setup(self, d, I, J, near):
        nat, xyz = self.nat, self.xyz
        Rinv = np.zeros((nat, nat), dtype=np.float64)
        step = 512
        for s in range(0, nat, step):
            dd = xyz[s : s + step, None, :] - xyz[None, :, :]
            r = np.sqrt((dd * dd).sum(-1))
            with np.errstate(divide="ignore"):
                v = EV * A0 / r
            v[r < RNEAR] = 0.0
            Rinv[s : s + step] = v
        self.Rinv = Rinv
        zc = self.tore
        far_static = -(Rinv @ zc)
        self.far_static = far_static
        self.H[self.diagpos] += far_static[self.orb_atom]
        self.enuc_far = 0.5 * float(zc @ Rinv @ zc)
        # core-core repulsion beyond RNEAR differs from point charges only through the terms of
        # ccrep that do not vanish exponentially fast (O-H: exp(-par4*2r)); tabulate and add.
        self.enuc_far += self._ccrep_tail()
        self.enuclr = self.enuc_near_sum() + self.enuc_far

    def enuc_near_sum(self):
        return self._enuc_near

    def _ccrep_tail(self, rmax=16.0):
        tot = 0.0
        zs = sorted(set(self.z))
        xyz = self.xyz
        tree = self.tree
        rg = np.linspace(RNEAR, rmax, 1801)
        for ia, za in enumerate(zs):
            for zb in zs[ia:]:
                ea, eb = ELEMENTS[za], ELEMENTS[zb]
                pt = EV * A0 / rg
                tab = (
                    np.array([ccrep(za, zb, r, p) for r, p in zip(rg, pt)])
                    - ea.tore * eb.tore * pt
                )
                if np.abs(tab).max() < 1e-10:
                    continue
                # cutoff where the tail is negligible
                ok = np.nonzero(np.abs(tab) > 1e-10)[0]
                rc = rg[ok.max()] if len(ok) else RNEAR
                ia_ = np.nonzero(self.zarr == za)[0]
                ib_ = np.nonzero(self.zarr == zb)[0]
                tb = cKDTree(xyz[ib_])
                ta = cKDTree(xyz[ia_])
                sd = ta.sparse_distance_matrix(tb, rc, output_type="coo_matrix")
                r = sd.data
                m = r >= RNEAR
                if za == zb:
                    m &= ia_[sd.row] < ib_[sd.col]
                r = r[m]
                if len(r):
                    tot += float(np.interp(r, rg, tab).sum())
        return tot

    # ------------------------------------------------------------------ Fock builder
    def build_onecenter(self):
        self.one = []
        for n, (ats, pp) in self.dpos_atom.items():
            for zz in sorted(set(self.zarr[ats].tolist())):
                sel = np.nonzero(self.zarr[ats] == zz)[0]
                T = ELEMENTS[zz].onecenter
                self.one.append(
                    (
                        pp[sel],
                        T.reshape(n * n, n * n).T.copy(),
                        T.transpose(0, 2, 1, 3).reshape(n * n, n * n).T.copy(),
                        n,
                    )
                )
        self.jpos = np.concatenate(
            [c.pDA[: c.nn].ravel() for c in self.classes]
            + [c.pDB[: c.nn].ravel() for c in self.classes]
        )

    def twoel(self, Pt, Ps):
        G = np.zeros(self.nnz)
        for pq, Tj, Tk, n in self.one:
            m = len(pq)
            G[pq] = (Pt[pq].reshape(m, -1) @ Tj).reshape(m, n, n) - (
                Ps[pq].reshape(m, -1) @ Tk
            ).reshape(m, n, n)
        ja, jb = [], []
        for c in self.classes:
            nn = c.nn
            if not nn:
                continue
            JA = np.einsum("pabcd,pcd->pab", c.W4, Pt[c.pDB[:nn]], optimize=True)
            JB = np.einsum("pabcd,pab->pcd", c.W4, Pt[c.pDA[:nn]], optimize=True)
            K = np.einsum("pabcd,pbd->pac", c.W4, Ps[c.pU_n], optimize=True)
            G[c.pU_n] = -K
            G[c.pL_n] = -K
            ja.append(JA.ravel())
            jb.append(JB.ravel())
        cls_n = [c for c in self.classes if c.nn]
        jpos = np.concatenate(
            [c.pDA[: c.nn].ravel() for c in cls_n]
            + [c.pDB[: c.nn].ravel() for c in cls_n]
        )
        G += np.bincount(jpos, np.concatenate(ja + jb), minlength=self.nnz)
        # point-charge exchange of the 7 A .. rk shell
        G -= self.kpt * Ps
        # monopole Coulomb of everything beyond 7 A
        pop = np.bincount(self.orb_atom, weights=Pt[self.diagpos], minlength=self.nat)
        G[self.diagpos] += (self.Rinv @ pop)[self.orb_atom]
        return G

    def fock(self, P):
        """closed shell: P = alpha density (occupations 0..1); returns F (same for both spins)."""
        return self.H + self.twoel(2.0 * P, P)

    def energy_elec(self, P, F):
        # E = 1/2 sum_spin P.(H+F) = P.(H+F)   (alpha = beta)
        return float(P @ (self.H + F))

    # ------------------------------------------------------------------ divide and conquer
    def make_groups(self, core_size=30):
        xyz = self.xyz
        groups = []
        stack = [np.arange(self.nat)]
        while stack:
            g = stack.pop()
            if len(g) <= core_size:
                groups.append(np.sort(g))
                continue
            x = xyz[g] - xyz[g].mean(0)
            _, _, vt = np.linalg.svd(x, full_matrices=False)
            o = np.argsort(x @ vt[0])
            h = len(g) // 2
            stack.append(g[o[:h]])
            stack.append(g[o[h:]])
        self.groups = groups

    def sub_atoms(self, g, buffer):
        lst = self.tree.query_ball_point(self.xyz[g], buffer)
        return np.unique(np.concatenate([np.asarray(x, dtype=np.int64) for x in lst]))

    def build_partition(self, core_size=30, buffer=7.0):
        if not hasattr(self, "groups") or self.core_size != core_size:
            self.make_groups(core_size)
            self.core_size = core_size
        nf, nsz = self.nfirst, self.nsz
        subs = []
        for g in self.groups:
            atoms = self.sub_atoms(g, buffer)
            cnt = nsz[atoms]
            start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
            orbs = np.repeat(nf[atoms] - start, cnt) + np.arange(int(cnt.sum()))
            core_mask = np.zeros(self.nat, bool)
            core_mask[g] = True
            corb = np.repeat(core_mask[atoms], cnt)
            subs.append((atoms, orbs, corb))
        self.subs = subs
        self.buffer = buffer
        sizes = np.array([len(s[1]) for s in subs])
        log(
            "partition buffer %.1f: %d subsystems, mean orbs %.0f, max %d, cost %.2e"
            % (
                buffer,
                len(subs),
                sizes.mean(),
                sizes.max(),
                float((sizes.astype(float) ** 3).sum()),
            )
        )

    def _extract(self, Fm, orbs):
        A = Fm[orbs]  # rows
        lo = np.full(self.norb, -1, dtype=np.int32)
        lo[orbs] = np.arange(len(orbs), dtype=np.int32)
        lc = lo[A.indices]
        keep = lc >= 0
        rr = np.repeat(np.arange(len(orbs)), np.diff(A.indptr))
        Fs = np.zeros((len(orbs), len(orbs)))
        Fs[rr[keep], lc[keep]] = A.data[keep]
        return Fs, lo

    def dc_density(self, F, nhalf, mu_guess=None, kT=0.05, win=1.0):
        """Alpha density (pattern storage) from the divide-and-conquer eigen-decompositions of F."""
        N = self.norb
        Fm = sp.csr_matrix((F, self.indices, self.indptr), shape=(N, N))
        nsub = len(self.subs)
        indptr, indices = self.indptr, self.indices

        def one(si, mu_lo, mu_hi, keepwin):
            atoms, orbs, corb = self.subs[si]
            Fs, lo = self._extract(Fm, orbs)
            e, C = np.linalg.eigh(Fs)
            del Fs
            Cc = C[corb]
            w = np.einsum("ij,ij->j", Cc, Cc)
            dbg = os.environ.get("PM7_DEBUGATOM")
            if (
                dbg
                and int(dbg) in atoms[corb[np.cumsum(self.nsz[atoms]) - 1]]
                and mu_guess is not None
            ):
                sel = (np.abs(e - mu_guess) < 2.5) & (w > 0.03)
                log(
                    "   DEBUG sub %d: eig near mu(%.3f): %s"
                    % (
                        si,
                        mu_guess,
                        " ".join(
                            "%.3f(w%.2f)" % (a, b) for a, b in zip(e[sel], w[sel])
                        ),
                    )
                )
            if not keepwin:
                return e, w
            full = e < mu_lo
            inwin = (e >= mu_lo) & (e <= mu_hi)
            Cf = C[:, full]
            Prow = Cc[:, full] @ Cf.T
            self._fill(Prow, orbs, corb, lo)
            wd = None
            if inwin.any():
                wd = (
                    e[inwin],
                    w[inwin],
                    np.ascontiguousarray(Cc[:, inwin]),
                    np.ascontiguousarray(C[:, inwin]),
                )
            return float(w[full].sum()), wd

        def run(keepwin, mu_lo=None, mu_hi=None):
            with ThreadPoolExecutor(self.nthreads) as ex:
                return list(
                    ex.map(lambda si: one(si, mu_lo, mu_hi, keepwin), range(nsub))
                )

        def count(es, ws, mu):
            x = np.clip((es - mu) / kT, -60, 60)
            return float((ws / (1.0 + np.exp(x))).sum())

        def bisect(es, ws, target, lo, hi):
            for _ in range(200):
                mid = 0.5 * (lo + hi)
                if count(es, ws, mid) < target:
                    lo = mid
                else:
                    hi = mid
                if hi - lo < 1e-13:
                    break
            return 0.5 * (lo + hi)

        self._out = np.zeros(self.nnz)
        tries = 0
        while True:
            if mu_guess is None:
                res = run(False)
                es = np.concatenate([r[0] for r in res])
                ws = np.concatenate([r[1] for r in res])
                del res
                mu_guess = bisect(es, ws, nhalf, es.min() - 1.0, es.max() + 1.0)
                o_ = np.argsort(es)
                cc = np.cumsum(ws[o_])
                lo_e = es[o_][np.searchsorted(cc, nhalf - 1.0)]
                hi_e = es[o_][np.searchsorted(cc, nhalf + 1.0)]
                log(
                    "mu from full pass: %.4f (count-1 level %.3f, count+1 level %.3f)"
                    % (mu_guess, lo_e, hi_e)
                )
            mu_lo, mu_hi = mu_guess - win, mu_guess + win
            self._out[:] = 0.0
            res = run(True, mu_lo, mu_hi)
            nfull = sum(r[0] for r in res)
            wins = [(si, r[1]) for si, r in enumerate(res) if r[1] is not None]
            if wins:
                es = np.concatenate([r[1][0] for r in wins])
                ws = np.concatenate([r[1][1] for r in wins])
                nmax = nfull + float(ws.sum())
            else:
                es = ws = np.zeros(0)
                nmax = nfull
            if nfull - 1e-9 <= nhalf <= nmax + 1e-9 and len(es):
                mu = bisect(es, ws, nhalf - nfull, mu_lo - 1.0, mu_hi + 1.0)
                if VERBOSE:
                    log(
                        "   states weight within 0.1/0.3/0.6/1.0 eV of mu=%.3f: %.3f %.3f %.3f %.3f"
                        % (
                            mu,
                            *[
                                float(ws[np.abs(es - mu) < r].sum())
                                for r in (0.1, 0.3, 0.6, 1.0)
                            ],
                        )
                    )
                break
            tries += 1
            log(
                "window miss (%.3f..%.3f for %.3f); retry with full pass"
                % (nfull, nmax, nhalf)
            )
            mu_guess = None
            if tries > 3:
                raise RuntimeError("cannot fix the electron count")
        # add the partially occupied window states
        for si, (ew, ww, Ccw, Cw) in wins:
            f = 1.0 / (1.0 + np.exp(np.clip((ew - mu) / kT, -60, 60)))
            atoms, orbs, corb = self.subs[si]
            lo_ = np.full(N, -1, dtype=np.int32)
            lo_[orbs] = np.arange(len(orbs), dtype=np.int32)
            self._fill((Ccw * f) @ Cw.T, orbs, corb, lo_, add=True)
        out = self._out
        out = 0.5 * (out + out[self.tperm])
        self.mu = mu
        return out, mu

    def _fill(self, Prow, orbs, corb, lo, add=False):
        indptr, indices, out = self.indptr, self.indices, self._out
        crow = orbs[corb]
        for k, r in enumerate(crow):
            s, t = indptr[r], indptr[r + 1]
            lc = lo[indices[s:t]]
            ok = lc >= 0
            v = np.zeros(t - s)
            v[ok] = Prow[k, lc[ok]]
            if add:
                out[s:t] += v
            else:
                out[s:t] = v

    def dense_density(self, F, nhalf):
        N = self.norb
        Fd = sp.csr_matrix((F, self.indices, self.indptr), shape=(N, N)).toarray()
        e, C = np.linalg.eigh(Fd)
        Cc = C[:, : int(round(nhalf))]
        Pd = Cc @ Cc.T
        self.mu = 0.5 * (e[int(round(nhalf)) - 1] + e[int(round(nhalf))])
        return Pd[self.rows_, self.indices], self.mu

    # ------------------------------------------------------------------ SCF
    def _pulay(self, hin, hres, P, res, alpha, up, from_up):
        hin.append(P[up].astype(np.float32))
        hres.append(res[up].astype(np.float32))
        if len(hin) > self.hist:
            hin.pop(0)
            hres.pop(0)
        m = len(hin)
        if m < 2:
            return P + alpha * res
        B = np.array([[float(np.dot(a, b)) for b in hres] for a in hres])
        A = np.zeros((m + 1, m + 1))
        A[:m, :m] = B / np.abs(B).max()
        A[m, :m] = 1
        A[:m, m] = 1
        rhs = np.zeros(m + 1)
        rhs[m] = 1
        try:
            c = np.linalg.solve(A + np.diag([1e-10] * m + [0]), rhs)[:m]
        except np.linalg.LinAlgError:
            c = np.zeros(m)
            c[-1] = 1
        acc = np.zeros(len(hin[0]))
        for ci, xi, ri in zip(c, hin, hres):
            acc += ci * xi
            acc += (ci * alpha) * ri
        return from_up(acc)

    def scf(
        self,
        mode="dc",
        core_size=30,
        buffer=7.0,
        small_buffer=None,
        tol=1e-4,
        small_tol=2e-3,
        maxit=100,
        alpha=0.3,
        hist=6,
        kT=0.05,
        max_big=4,
    ):
        """small_buffer: if given (< buffer), SCF is converged with the cheap partition and the
        large-buffer density enters through a frozen correction Delta = D_big(F) - D_small(F)."""
        alpha = float(os.environ.get("PM7_ALPHA", alpha))
        maxit = int(os.environ.get("PM7_MAXIT", maxit))
        self.hist = hist
        self.stall_dE = float(os.environ.get("PM7_STALL", "0.03"))
        self.deadline = float(os.environ.get("PM7_DEADLINE", "1300"))
        self.pulay_dE = float(os.environ.get("PM7_PDE", "100"))
        self.kt_fac = float(os.environ.get("PM7_KTFAC", "0"))
        self.kt_max = float(os.environ.get("PM7_KTMAX", "0.3"))
        self.pulay_start = float(os.environ.get("PM7_PSTART", "0.1"))
        self.alpha0 = float(os.environ.get("PM7_ALPHA0", "0.3"))
        self.build_onecenter()
        nhalf = self.nel / 2.0
        P = np.zeros(self.nnz)
        P[self.diagpos] = self.el.pdiag * 0.5
        up = np.nonzero(self.rows_ <= self.indices)[0]
        low = np.nonzero(self.rows_ > self.indices)[0]
        low_src = self.tperm[low]

        def from_up(v):
            y = np.zeros(self.nnz)
            y[up] = v
            y[low] = y[low_src]
            return y

        two = mode == "dc" and small_buffer is not None and small_buffer < buffer
        if mode == "dc":
            self.build_partition(core_size, small_buffer if two else buffer)
        state = {"mu": None}

        state["kT"] = kT

        def dens(F, label=""):
            t0 = time.time()
            if mode == "dc":
                Po, mu = self.dc_density(
                    F,
                    nhalf,
                    state["mu"],
                    kT=state["kT"],
                    win=max(
                        1.0 if state.get("err", 1.0) < 0.05 else 3.0, 20.0 * state["kT"]
                    ),
                )
            else:
                Po, mu = self.dense_density(F, nhalf)
            state["mu"] = mu
            log("   density %s %.1fs mu=%.4f" % (label, time.time() - t0, mu))
            return Po

        def energy(P, F, Po):
            ehf = 2.0 * float(F @ Po) - float(P @ (F - self.H))
            return (ehf + self.enuclr) * FPC_9 + self.atheat

        def run(P, delta, tol_, maxit_, tag):
            hin, hres = [], []
            E = 0.0
            best = 1e9
            calm = 0
            for it in range(1, maxit_ + 1):
                F = self.fock(P)
                Po = dens(F, tag)
                if delta is not None:
                    Po = Po + delta
                res = Po - P
                err = float(np.abs(res).max())
                Eold, E = E, energy(P, F, Po)
                state["err"] = err
                state["kT"] = float(np.clip(self.kt_fac * err, kT, self.kt_max))
                log(
                    "%s it %2d E=%.6f dE=%.2e max|dP|=%.2e"
                    % (tag, it, E, E - Eold, err)
                )
                self.nit = getattr(self, "nit", 0) + 1
                if err < tol_:
                    return P, Po, F, E, err
                # soft-mode stagnation: residual small and E_HF no longer moving
                calm = calm + 1 if (err < 5e-3 and abs(E - Eold) < self.stall_dE) else 0
                if calm >= 2:
                    log("   energy stagnated (|dE| < %.3f twice): stop" % self.stall_dE)
                    return P, Po, F, E, err
                if time.time() - _T0 > self.deadline and err < 2e-2:
                    log("   time budget reached: stop at max|dP| = %.2e" % err)
                    return P, Po, F, E, err
                if err > 2.0 * best and hin:
                    log("   residual grew: restart mixing history")
                    hin.clear()
                    hres.clear()
                best = min(best, err)
                if VERBOSE:
                    rr = np.abs(res)
                    rowmax = np.maximum.reduceat(rr, self.indptr[:-1])
                    am = np.bincount(self.orb_atom, weights=rowmax, minlength=self.nat)
                    top = np.argsort(-am)[:4]
                    qch = self.tore - np.bincount(
                        self.orb_atom, weights=2.0 * P[self.diagpos], minlength=self.nat
                    )
                    log(
                        "   worst atoms: "
                        + " ".join(
                            "%d(Z%d,q%.2f,r%.2f)" % (a, self.z[a], qch[a], am[a])
                            for a in top
                        )
                    )
                if err > self.pulay_start and not (
                    it > 3 and abs(E - Eold) < self.pulay_dE
                ):
                    P = (
                        P + self.alpha0 * res
                    )  # heavy damping while far from convergence
                else:
                    P = self._pulay(hin, hres, P, res, alpha, up, from_up)
            return P, Po, F, E, err

        if not two:
            P, Po, F, E, err = run(P, None, tol, maxit, "scf")
            self.P, self.heat = Po, E
            return E
        # stage A: cheap partition
        P, Po, F, E, err = run(P, None, small_tol, maxit, "A")
        if os.environ.get("PM7_DELTA", "") != "1":
            # stage B: continue the SCF with the large-buffer partition (few iterations from a good start)
            self.build_partition(core_size, buffer)
            state["err"] = err
            P, Po, F, E, err = run(P, None, tol, maxit, "B")
            self.P, self.heat = Po, E
            return E
        # (alternative: frozen-correction scheme, see NOTES.md)
        delta = None
        for k in range(max_big):
            F = self.fock(P)
            Ps = dens(F, "small")
            self.build_partition(core_size, buffer)
            Pb = dens(F, "big")
            self.build_partition(core_size, small_buffer)
            state["mu"] = state["mu"]
            delta = Pb - Ps
            err0 = float(np.abs(Pb - P).max())
            E = energy(P, F, Pb)
            log("B%d: big-buffer residual %.2e  E_HF=%.6f" % (k, err0, E))
            if err0 < tol or k == max_big - 1:
                self.P, self.heat = Pb, E
                return E
            P, Po, F, E, err = run(P, delta, tol, maxit, "B%d" % k)
        self.P, self.heat = Po, E
        return E

    def charges(self):
        pop = np.bincount(
            self.orb_atom, weights=2.0 * self.P[self.diagpos], minlength=self.nat
        )
        return self.tore - pop


DENSE_MAX_ORBS = 2600  # exact diagonalisation of the whole (sparse-assembled) Fock matrix below this size


def single_point_big(job, mode=None, **kw):
    z = job.z
    bc = BigCalc(z, job.coords, job.charge)
    t0 = time.time()
    corr = scale_corr.correction_energy(z, job.coords)
    bc.atheat = base_atheat(z) + corr["total"]
    log("corrections %.1fs" % (time.time() - t0), corr)
    bc.build_static()
    if mode is None:
        mode = "dense" if bc.norb <= DENSE_MAX_ORBS else "dc"
    if mode == "dense":
        kw.setdefault("tol", 1e-6)
    else:
        kw.setdefault("buffer", 9.0)
        kw.setdefault("small_buffer", 6.0)
        kw.setdefault("tol", 5e-4)
    heat = bc.scf(mode=mode, **kw)
    return {"heat_of_formation": float(heat), "atom_charges": bc.charges().tolist()}, bc
