"""Input formats: Z-matrix (dummy atoms, fixed flags) and PDB (GEO_DAT), plus internal-coordinate output."""

import os
import re

import numpy as np

from .constants import MASS
from .energy import evaluate
from . import gradient
from .scf import ScfState
from .system import Electrons, Job, parse_keywords
from .params import SUPPORTED
from .constants import ATOMIC_NUMBER


# ---------------------------------------------------------------- geometry maps
def zmat_to_cart(vals, refs):
    """vals: (n,3) [r, angle(deg), dihedral(deg)]; refs: list of (a,b,c) 0-based or None. Returns (n,3)."""
    n = len(vals)
    x = np.zeros((n, 3))
    for i in range(n):
        a, b, c = refs[i]
        r, th, ph = vals[i]
        if a is None:
            continue
        if b is None:
            x[i] = x[a] + np.array([r, 0.0, 0.0])
            continue
        th, ph = np.radians(th), np.radians(ph)
        if c is None:
            # first angle: place in the xz plane
            ab = x[b] - x[a]
            u = ab / np.linalg.norm(ab)
            perp = np.cross(u, [0.0, 1.0, 0.0])
            if np.linalg.norm(perp) < 1e-8:
                perp = np.cross(u, [1.0, 0.0, 0.0])
            perp /= np.linalg.norm(perp)
            m = np.cross(perp, u)
            x[i] = x[a] + r * (np.cos(th) * u + np.sin(th) * m)
            continue
        bc = x[a] - x[b]
        bc /= np.linalg.norm(bc)
        nv = np.cross(x[b] - x[c], bc)
        nn = np.linalg.norm(nv)
        if nn < 1e-8:
            nv = np.cross(bc, [0.0, 1.0, 0.0])
            nn = np.linalg.norm(nv)
        nv /= nn
        m = np.cross(nv, bc)
        d = r * np.array(
            [-np.cos(th), np.sin(th) * np.cos(ph), -np.sin(th) * np.sin(ph)]
        )
        x[i] = x[a] + d[0] * bc + d[1] * m + d[2] * nv
    return x


def _angle(p, q, r):
    u, v = p - q, r - q
    c = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def _dihedral(p0, p1, p2, p3):
    b0, b1, b2 = p1 - p0, p2 - p1, p3 - p2
    n1, n2 = np.cross(b0, b1), np.cross(b1, b2)
    m = np.cross(n1, b1 / np.linalg.norm(b1))
    return float(np.degrees(np.arctan2(np.dot(m, n2), np.dot(n1, n2))))


def cart_to_zmat(x, refs):
    out = []
    for i, (a, b, c) in enumerate(refs):
        r = ang = dih = 0.0
        if a is not None:
            r = float(np.linalg.norm(x[i] - x[a]))
        if b is not None:
            ang = _angle(x[i], x[a], x[b])
        if c is not None:
            dih = _dihedral(x[i], x[a], x[b], x[c])
        out.append([r, ang, dih])
    return out


# ---------------------------------------------------------------- readers
class ZInfo:
    def __init__(self, elements, vals, flags, refs):
        self.elements, self.vals, self.flags, self.refs = elements, vals, flags, refs
        self.real = [i for i, e in enumerate(elements) if e.upper() not in ("XX", "X")]

    def variables(self):
        """Indices (atom, col) of the free internal coordinates (atoms 1-3 have fewer real coordinates)."""
        v = []
        for i, (a, b, c) in enumerate(self.refs):
            for col, ref in enumerate((a, b, c)):
                if ref is not None and self.flags[i][col] == 1:
                    v.append((i, col))
        return v


def read_zmat(lines, kwline):
    elems, vals, flags, refs = [], [], [], []
    for ln in lines:
        t = ln.split()
        elems.append(re.sub(r"[^A-Za-z]", "", t[0]))
        vals.append([float(t[1]), float(t[3]), float(t[5])])
        flags.append([int(float(t[2])), int(float(t[4])), int(float(t[6]))])
        rr = [int(t[7]), int(t[8]), int(t[9])]
        i = len(elems) - 1
        if i == 0:
            refs.append((None, None, None))
        else:
            r = [x - 1 if x > 0 else None for x in rr]
            if i == 1:
                r[1] = r[2] = None
            if i == 2:
                r[2] = None
            refs.append(tuple(r))
    return ZInfo(
        [e[0].upper() + e[1:].lower() for e in elems],
        np.array(vals, float),
        flags,
        refs,
    )


def read_pdb(path):
    elems, xyz = [], []
    for ln in open(path):
        if ln.startswith(("ATOM", "HETATM")):
            e = ln[76:78].strip() if len(ln) >= 78 else ""
            if not e:
                e = re.sub(r"[^A-Za-z]", "", ln[12:16])[:1]
            elems.append(e[0].upper() + e[1:].lower())
            xyz.append([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])])
    return elems, np.array(xyz, float)


def load(path):
    """Returns (job, zinfo or None). The job holds real atoms only."""
    lines = open(path).read().splitlines()
    kwline = lines[0]
    title = lines[1] if len(lines) > 1 else ""
    k = parse_keywords(kwline)
    body = [ln for ln in lines[3:] if ln.strip()]
    m = re.search(r'GEO_DAT\s*=\s*"?([^"\s]+)"?', kwline, re.I)
    zi = None
    if m:
        pdb = m.group(1)
        if not os.path.isabs(pdb):
            pdb = os.path.join(os.path.dirname(os.path.abspath(path)), pdb)
        elems, xyz = read_pdb(pdb)
        flags = np.ones((len(elems), 3), int)
    elif body and all(len(ln.split()) >= 10 for ln in body):
        zi = read_zmat(body, kwline)
        xall = zmat_to_cart(zi.vals, zi.refs)
        elems = [zi.elements[i] for i in zi.real]
        xyz = xall[zi.real]
        flags = np.ones((len(elems), 3), int)
    else:
        return None, None
    job = Job(
        keywords=kwline.strip(),
        title=title,
        elements=elems,
        coords=xyz,
        flags=flags,
        charge=k["charge"],
        uhf=k["uhf"],
        msdel=k["msdel"],
        one_scf=k["one_scf"],
        grad=k["grad"],
        precise=k["precise"],
        gnorm_limit=k["gnorm"],
        force=k["force"],
        nosym=k["nosym"],
    )
    for z in job.z:
        if z not in SUPPORTED:
            raise ValueError("unsupported element %d" % z)
    return job, zi


# ---------------------------------------------------------------- internal-coordinate optimisation
def optimise_internal(job, zi, tight=2.0e-4):
    """Minimise PM7 heat over the free internal coordinates (flag 1); others stay fixed.
    BFGS with backtracking line search, tight convergence (the minimum does not depend on the path)."""
    z = job.z
    el = Electrons(z, job.charge, job.uhf, job.msdel)
    state = ScfState()
    var = zi.variables()
    nv = len(var)
    n = len(zi.elements)
    q0 = np.array([zi.vals[i][col] for (i, col) in var], float)
    if nv == 0:
        return None

    def cart(qs):
        v = zi.vals.copy()
        for k, (i, col) in enumerate(var):
            v[i][col] = qs[k] if col == 0 else np.degrees(qs[k])
        return zmat_to_cart(v, zi.refs)

    def fun(qs, last=False):
        xall = cart(qs)
        xr = xall[zi.real]
        ev = evaluate(
            z,
            xr,
            el,
            state=state,
            gnorm=0.0,
            precise=job.precise,
            last=last,
            limscf=False,
        )
        g = gradient.cartesian_gradient(z, xr, el, ev.scf, job.precise)
        gfull = np.zeros((n, 3))
        gfull[zi.real] = g
        # chain rule by central differences of the (cheap) geometry map
        J = np.empty((n * 3, nv))
        for k in range(nv):
            h = 1e-5
            qp, qm = qs.copy(), qs.copy()
            qp[k] += h
            qm[k] -= h
            J[:, k] = (cart(qp) - cart(qm)).ravel() / (2 * h)
        return ev.heat, J.T @ gfull.ravel(), xall

    qs = np.array(
        [
            zi.vals[i][col] if col == 0 else np.radians(zi.vals[i][col])
            for (i, col) in var
        ],
        float,
    )
    hdiag = np.array([300.0 if col == 0 else 80.0 for (_, col) in var])
    H = np.diag(hdiag)
    e, g, _ = fun(qs)
    for it in range(300):
        if np.max(np.abs(g)) < tight:
            break
        step = -np.linalg.solve(H, g)
        smax = np.max(
            np.abs(step / np.where(np.array([c for _, c in var]) == 0, 0.1, 0.15))
        )
        if smax > 1.0:
            step /= smax
        t = 1.0
        for _ in range(20):
            e2, g2, _ = fun(qs + t * step)
            if e2 <= e + 1e-4 * t * float(g @ step) or e2 < e - 1e-9:
                break
            t *= 0.5
        s = t * step
        y = g2 - g
        qs = qs + s
        if float(y @ s) > 1e-12:
            Hs = H @ s
            H = H - np.outer(Hs, Hs) / float(s @ Hs) + np.outer(y, y) / float(y @ s)
        e, g = e2, g2
    e, g, xall = fun(qs, last=True)
    xr = xall[zi.real]
    ev = evaluate(z, xr, el, state=state, gnorm=0.0, precise=job.precise, last=True)
    out = {
        "heat_of_formation": ev.heat,
        "atom_charges": ev.charges.tolist(),
        "ionization_potential": ev.ip,
        "dipole": ev.dipole,
        "optimized_geometry": xr.tolist(),
    }
    return out, xall
