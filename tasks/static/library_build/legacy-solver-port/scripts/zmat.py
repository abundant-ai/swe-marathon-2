#!/usr/bin/env python3
"""Cartesian -> Z-matrix helper used to build step-4 inputs (not shown to the solver agent)."""

import numpy as np


def _ang(p, q, r):
    u, v = p - q, r - q
    c = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def dihedral(p0, p1, p2, p3):
    """IUPAC dihedral p0-p1-p2-p3 in degrees."""
    b0, b1, b2 = p1 - p0, p2 - p1, p3 - p2
    n1, n2 = np.cross(b0, b1), np.cross(b1, b2)
    m = np.cross(n1, b1 / np.linalg.norm(b1))
    return float(np.degrees(np.arctan2(np.dot(m, n2), np.dot(n1, n2))))


def build_refs(x):
    """For each atom choose (a, b, c) earlier atoms: nearest, then nearest to a, then nearest to b; avoid collinear."""
    n = len(x)
    refs = [(None, None, None)]
    for k in range(1, n):
        order = sorted(range(k), key=lambda j: np.linalg.norm(x[k] - x[j]))
        a = order[0]
        if k == 1:
            refs.append((a, None, None))
            continue
        ob = sorted(
            [j for j in range(k) if j != a], key=lambda j: np.linalg.norm(x[a] - x[j])
        )
        done = False
        for b in ob:
            if not 20 < _ang(x[k], x[a], x[b]) < 160:
                continue
            if k == 2:
                refs.append((a, b, None))
                done = True
                break
            oc = sorted(
                [j for j in range(k) if j not in (a, b)],
                key=lambda j: np.linalg.norm(x[b] - x[j]),
            )
            for c in oc:
                if 20 < _ang(x[a], x[b], x[c]) < 160:
                    refs.append((a, b, c))
                    done = True
                    break
            if done:
                break
        if not done:
            return None
    return refs


def to_zmat(x, refs):
    """Return list of (a,b,c,r,ang,dih) with 0-based refs and degrees."""
    rows = []
    for k in range(len(x)):
        a, b, c = refs[k]
        r = ang = dih = None
        if a is not None:
            r = float(np.linalg.norm(x[k] - x[a]))
        if b is not None:
            ang = float(_ang(x[k], x[a], x[b]))
        if c is not None:
            dih = dihedral(x[k], x[a], x[b], x[c])
        rows.append((a, b, c, r, ang, dih))
    return rows


def write_zmat(els, rows, flags=None):
    """Full 9-column Z-matrix lines (MOPAC free format needs placeholders); flags[k] = (fr, fa, fd) ints."""
    out = []
    for k, (a, b, c, r, ang, dih) in enumerate(rows):
        f = flags[k] if flags else (1, 1, 1)
        if k == 0:
            out.append(f" {els[k]}  0.0 0  0.0 0  0.0 0  0 0 0")
            continue
        rr = f"{r:.8f} {f[0]}"
        aa = f"{ang:.8f} {f[1]}" if ang is not None else "0.0 0"
        dd = f"{dih:.8f} {f[2]}" if dih is not None else "0.0 0"
        out.append(
            f" {els[k]}  {rr}  {aa}  {dd}  {a + 1} {(b + 1) if b is not None else 0} {(c + 1) if c is not None else 0}"
        )
    return out
