"""Molecule description: elements, geometry, charge/spin bookkeeping, connectivity."""

import math
import re
from dataclasses import dataclass, field

import numpy as np

from .constants import ATOMIC_NUMBER, MASS, SYMBOLS
from .params import ELEMENTS, SUPPORTED

# covalent radii used by MOPAC's connectivity test (atom_radius_covalent)
COVALENT_RADIUS = {
    1: 0.37,
    6: 0.77,
    7: 0.75,
    8: 0.73,
    9: 0.71,
    15: 1.06,
    16: 1.02,
    17: 0.99,
    35: 1.14,
}


@dataclass
class Job:
    keywords: str
    title: str
    elements: list
    coords: np.ndarray  # (n,3) Angstrom
    flags: np.ndarray  # (n,3) optimisation flags (1 = optimise)
    charge: int = 0
    uhf: bool = False
    msdel: int = None  # n_alpha - n_beta (None: default)
    one_scf: bool = False
    grad: bool = False
    precise: bool = False
    gnorm_limit: float = 1.0
    ts: bool = False
    force: bool = False
    nosym: bool = False
    eps: float = None  # dielectric constant of EPS= (COSMO), None: gas phase
    rsolv: float = None
    nspa: int = None
    disex: float = None

    @property
    def z(self):
        return [ATOMIC_NUMBER[e.upper()] for e in self.elements]


def parse_keywords(line):
    kw = " " + line.upper() + " "
    words = kw.split()
    job = {}
    job["uhf"] = " UHF " in kw
    job["one_scf"] = " 1SCF " in kw
    job["grad"] = " GRAD " in kw
    job["precise"] = " PRECISE " in kw
    m = re.search(r" CHARGE=(-?\d+)", kw)
    job["charge"] = int(m.group(1)) if m else 0
    msdel = None
    for name, v in (
        ("SING", 0),
        ("DOUB", 1),
        ("TRIP", 2),
        ("QUAR", 3),
        ("QUIN", 4),
        ("SEXT", 5),
    ):
        if " " + name in kw:
            msdel = v
    job["msdel"] = msdel
    m = re.search(r" GNORM=([0-9.eE+-]+)", kw)
    job["gnorm"] = float(m.group(1)) if m else 1.0
    job["rhf"] = " RHF " in kw
    job["force"] = " FORCE " in kw
    job["nosym"] = " NOSYM" in kw
    for key, name in (
        ("eps", "EPS"),
        ("rsolv", "RSOLV"),
        ("nspa", "NSPA"),
        ("disex", "DISEX"),
    ):
        m = re.search(r" " + name + r"=([-+0-9.eEdD]+)", kw)
        job[key] = float(m.group(1).replace("D", "E")) if m else None
    return job


def mopac_number(tok):
    """MOPAC's READA/DIGIT text -> double conversion (geometry fields).

    The integer part is accumulated as c1 = c1*10 + d and the fraction as c2 = c2 + d*deciml with
    deciml = deciml/10 at every digit, compiled with fused multiply-add: the result differs from
    the correctly rounded value in the last bits for about a third of all inputs.  The COSMO cavity
    is a discrete construction whose tie decisions see those bits, so jobs with EPS= use it."""
    try:
        fma = math.fma
    except AttributeError:
        from fractions import Fraction

        def fma(a, b, c):
            return float(Fraction(a) * Fraction(b) + Fraction(c))

    def digit(txt):
        c1 = 0.0
        c2 = 0.0
        neg = False
        i = 0
        while i < len(txt):
            ch = txt[i]
            if "0" <= ch <= "9":
                c1 = c1 * 10.0 + (ord(ch) - 48)
            elif ch in "-+ ":
                if ch == "-":
                    neg = True
            elif ch == ".":
                break
            else:
                break
            i += 1
        deciml = 1.0
        for ch in txt[i + 1 :]:
            if "0" <= ch <= "9":
                deciml = deciml / 10.0
                c2 = fma(float(ord(ch) - 48), deciml, c2)
            else:
                break
        r = c1 + c2
        return -r if neg else r

    for k, ch in enumerate(tok):
        if ch in "eEdD" and k > 0:
            return digit(tok[:k]) * 10.0 ** digit(tok[k + 1 :])
    return digit(tok)


def read_mop(path):
    with open(path) as f:
        lines = f.read().splitlines()
    kwline = lines[0]
    num = mopac_number if parse_keywords(kwline)["eps"] is not None else float
    title = lines[1] if len(lines) > 1 else ""
    atoms = []
    flags = []
    elems = []
    for ln in lines[3:]:
        if not ln.strip():
            continue
        t = ln.split()
        elems.append(re.sub(r"[^A-Za-z]", "", t[0]))
        if len(t) >= 7:
            vals = [num(t[1]), num(t[3]), num(t[5])]
            fl = [int(float(t[2])), int(float(t[4])), int(float(t[6]))]
        else:
            vals = [num(t[1]), num(t[2]), num(t[3])]
            fl = [1, 1, 1]
        atoms.append(vals)
        flags.append(fl)
    k = parse_keywords(kwline)
    job = Job(
        keywords=kwline.strip(),
        title=title,
        elements=[e[0].upper() + e[1:].lower() for e in elems],
        coords=np.array(atoms, float),
        flags=np.array(flags, int),
        charge=k["charge"],
        uhf=k["uhf"],
        msdel=k["msdel"],
        one_scf=k["one_scf"],
        grad=k["grad"],
        precise=k["precise"],
        gnorm_limit=k["gnorm"],
        force=k["force"],
        nosym=k["nosym"],
        eps=k["eps"],
        rsolv=k["rsolv"],
        nspa=None if k["nspa"] is None else int(round(k["nspa"])),
        disex=k["disex"],
    )
    for z in job.z:
        if z not in SUPPORTED:
            raise ValueError("unsupported element %d" % z)
    return job


class Electrons:
    """Electron counting (moldat): nelecs, nclose, nalpha, nbeta, pdiag."""

    def __init__(self, z, charge, uhf, msdel):
        self.z = list(z)
        self.charge = charge
        self.natorb = [ELEMENTS[zz].natorb for zz in z]
        self.norbs = sum(self.natorb)
        elecs = -charge + sum(ELEMENTS[zz].tore for zz in z)
        self.nelecs = int(round(max(elecs, 0.0)))
        odd = self.nelecs % 2 != 0
        if not uhf and (odd or (msdel not in (None, 0))):
            # MOPAC would use RHF + half-electron/C.I. for a triplet without UHF; not ported,
            # an unrestricted determinant is used instead (documented in NOTES.md)
            uhf = True
        self.uhf = uhf
        if msdel is None:
            msdel = 0 if not odd else 1
        self.msdel = msdel
        if uhf:
            self.nbeta = (self.nelecs - msdel) // 2
            self.nalpha = self.nelecs - self.nbeta
            self.nclose = 0
            self.nopen = 0
        else:
            self.nclose = self.nelecs // 2
            self.nopen = self.nclose  # nopen = nopen + nclose of moldat (closed shell)
            self.nalpha = 0
            self.nbeta = 0
        self.fract = 0.0
        yy = charge / (self.norbs + 1e-10)
        pdiag = np.zeros(self.norbs)
        off = 0
        for zz, n in zip(z, self.natorb):
            el = ELEMENTS[zz]
            if n == 1:
                pdiag[off] = el.tore - yy
            elif n == 4:
                pdiag[off : off + 4] = el.tore * 0.25 - yy
            else:
                pdiag[off : off + 4] = el.tore * 0.25 - yy
                pdiag[off + 4 : off + 9] = -yy
            off += n
        self.pdiag = pdiag
        self.offsets = np.concatenate([[0], np.cumsum(self.natorb)])


def connectivity(z, coords):
    """Bond list (set_up_dentate): returns (nbonds, ibonds) with 0-based neighbour lists."""
    n = len(z)
    nb = [0] * n
    ib = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i):
            d2 = float(np.sum((coords[i] - coords[j]) ** 2))
            il, iu = min(z[i], z[j]), max(z[i], z[j])
            safety = 1.1
            if il == 1:
                if iu == 6:
                    safety = 1.25
            elif il == 5:
                if iu == 7:
                    safety = 1.0
            elif il == 6:
                if iu < 8:
                    safety = 1.2
            elif il == 16:
                if iu == 16:
                    safety = 1.2
            if d2 < (safety * (COVALENT_RADIUS[z[i]] + COVALENT_RADIUS[z[j]])) ** 2:
                if nb[i] < 15 and nb[j] < 15:
                    ib[i].append(j)
                    ib[j].append(i)
                    nb[i] += 1
                    nb[j] += 1
    # hydrogen attached to hydrogen: keep only non-H neighbours (as in set_up_dentate)
    for i in range(n):
        if z[i] != 1 or nb[i] < 2:
            continue
        ib[i] = [j for j in ib[i] if z[j] != 1]
        nb[i] = len(ib[i])
    return nb, ib
