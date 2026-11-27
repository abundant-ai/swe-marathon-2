"""Geometry optimiser: port of MOPAC's EF (eigenvector following, minimisation branch).

Only the minimisation path is ported (keyword EF, no TS): diagonal start Hessian (200 for each
Cartesian coordinate, "XYZ" input), BFGS update, projection of translations/rotations out of the
Hessian, pure Newton-Raphson step if the lowest non-zero eigenvalue is positive, P-RFO / trust
radius (QA) steps otherwise, and MOPAC's step acceptance and trust-radius rules.

The optimiser is independent of the quantum-chemical engine: it only needs a callable
``fun(x, last, want_grad) -> (heat, grad)``.
"""

import math

import numpy as np

EPS = 1.0e-12
BIG = 1.0e3
TOLL = 1.0e-8
STEP_LOC = 5.0e-2
TMSIX = 1.0e-6
TMTWO = 1.0e-2


class _FormdState:
    store_ddx = 0.0


def _bisect_lambda(eigval, fx, bl, bu, squared, d2max=0.0):
    """Bisection for lambda between bl and bu (both versions of FORMD)."""
    sstoll = TOLL
    xlambda = 0.0
    ncnt = 0
    lam = 0.5 * (bl + bu)
    while True:
        lam = 0.5 * (bl + bu)
        if squared:
            fl = float(np.sum((fx / (bl - eigval)) ** 2)) - d2max
            fu = float(np.sum((fx / (bu - eigval)) ** 2)) - d2max
            fm = float(np.sum((fx / (lam - eigval)) ** 2)) - d2max
        else:
            fl = float(np.sum(fx * fx / (bl - eigval))) - bl
            fu = float(np.sum(fx * fx / (bu - eigval))) - bu
            fm = float(np.sum(fx * fx / (lam - eigval))) - lam
        if abs(xlambda - lam) < sstoll:
            break
        ncnt += 1
        if ncnt > 1000:
            raise RuntimeError("too many iterations in lambda bisect")
        xlambda = lam
        if fm * fu < 0.0:
            bl = lam
        if fm * fl < 0.0:
            bu = lam
    return lam


def formd(eigval, fx, dmax, u, st, donr=True, rrscal=False):
    """Geometry step (minimisation branch of FORMD).  Returns (d, ddx, xlamd, skal)."""
    nvar = len(eigval)
    skal = 1.0
    rscal = rrscal
    jt = 0
    for i in range(nvar):
        if eigval[i] != 0.0:
            jt = i
            break
    eone = eigval[jt]
    ssmin = max(abs(eone) * EPS, 10.0 * EPS)
    ssmax = max(BIG, abs(eone))
    ssmax = ssmax * BIG
    d2max = dmax * dmax
    lam = 0.0
    lam0 = 0.0
    goto = "1000"
    if donr and eone >= 0.0:
        goto = "1010"
    while True:
        if goto == "1000":
            frodo1 = frodo2 = False
            sstep = STEP_LOC
            if eone <= 0.0:
                lam = eone - sstep
            if eone > 0.0:
                sstep = eone
            bl = lam - sstep
            bu = lam + sstep * 0.5
            ncnt = 0
            failed = False
            while True:
                fl = float(np.sum(fx * fx / (bl - eigval))) - bl
                fu = float(np.sum(fx * fx / (bu - eigval))) - bu
                if fl * fu < 0.0:
                    break
                bl = bl - (eone - bl)
                bu = bu + 0.5 * (eone - bu)
                if bl <= -ssmax:
                    bl = -ssmax
                    frodo1 = True
                if abs(eone - bu) <= ssmin:
                    bu = eone - ssmin
                    frodo2 = True
                if frodo1 and frodo2:
                    failed = True
                    break
                ncnt += 1
                if ncnt > 1000:
                    raise RuntimeError("too many iterations bracketing lambda")
            if failed:
                goto = "1020"
                continue
            lam = _bisect_lambda(eigval, fx, bl, bu, squared=False)
            goto = "1010"
            continue
        if goto == "1010":
            temp = np.zeros(len(eigval))
            for i in range(len(eigval)):
                if lam == 0.0 and abs(eigval[i]) < TMTWO:
                    temp[i] = 0.0
                else:
                    temp[i] = fx[i] / (lam - eigval[i])
            d = u @ temp
            ddx = math.sqrt(float(d @ d))
            a_ = lam != 0.0 and abs(lam0 + lam) <= 1e-20
            b_ = lam != 0.0 and abs(lam0 + lam) > 1e-20
            if a_ or (b_ and st.store_ddx > 1e-9):
                if ddx > 2 * st.store_ddx:
                    d = d * st.store_ddx / ddx
                    ddx = 2 * st.store_ddx
            st.store_ddx = ddx
            if ddx < dmax + TMSIX:
                return d, ddx, lam, lam0, skal
            if lam == 0.0 and lam0 == 0.0:
                goto = "1000"
                continue
            if rscal:
                if ddx == 0.0:
                    raise RuntimeError("zero divide in formd")
                skal = dmax / ddx
                d = d * skal
                ddx = math.sqrt(float(d @ d))
                return d, ddx, lam, lam0, skal
            goto = "1020"
            continue
        if goto == "1020":
            lam = 0.0
            frodo1 = frodo2 = False
            sstep = STEP_LOC
            if eone <= 0.0:
                lam = eone - sstep
            if eone > 0.0:
                sstep = eone
            bl = lam - sstep
            bu = lam + sstep * 0.5
            found = False
            while True:
                fl = float(np.sum((fx / (bl - eigval)) ** 2)) - d2max
                fu = float(np.sum((fx / (bu - eigval)) ** 2)) - d2max
                if fl * fu < 0.0:
                    found = True
                    break
                bl = bl - (eone - bl)
                bu = bu + 0.5 * (eone - bu)
                if bl <= -ssmax:
                    bl = -ssmax
                    frodo1 = True
                if abs(eone - bu) <= ssmin:
                    bu = eone - ssmin
                    frodo2 = True
                if frodo1 and frodo2:
                    break
            if found:
                lam = _bisect_lambda(eigval, fx, bl, bu, squared=True, d2max=d2max)
                lam0 = -lam
                rscal = True
                goto = "1010"
                continue
            lam = eone - 10.0
            lam0 = 10.0
            rscal = True
            goto = "1010"
            continue


def project_hessian(f, x, masses):
    """PRJFC: remove translations/rotations (as MOPAC does it) from the Cartesian Hessian."""
    nvar = len(x)
    nat = nvar // 3
    coord = x.reshape(nat, 3)
    rm = np.repeat(1.0 / np.sqrt(masses), 3)
    totm = float(np.sum(masses))
    cmass = (masses[:, None] * coord).sum(axis=0) / totm
    xm = (np.sqrt(masses)[:, None] * (coord - cmass)).ravel()
    rot = np.zeros((3, 3))
    for i in range(nat):
        l = 3 * i
        rot[0, 0] += xm[l + 1] ** 2 + xm[l + 2] ** 2
        rot[0, 1] -= xm[l] * xm[l + 1]
        rot[0, 2] -= xm[l] * xm[l + 2]
        rot[1, 1] += xm[l] ** 2 + xm[l + 2] ** 2
        rot[1, 2] -= xm[l + 1] * xm[l + 2]
        rot[2, 2] += xm[l] ** 2 + xm[l + 1] ** 2
    rot[1, 0] = rot[0, 1]
    rot[2, 0] = rot[0, 2]
    rot[2, 1] = rot[1, 2]
    cut8 = 1.0e-8
    chk = rot[0, 0] * rot[1, 1] * rot[2, 2]
    if abs(chk) > cut8:
        rot = np.linalg.inv(rot)
    elif abs(rot[0, 0]) > cut8:
        if abs(rot[1, 1]) > cut8:
            det = rot[0, 0] * rot[1, 1] - rot[0, 1] * rot[1, 0]
            trp = rot[0, 0]
            rot[0, 0] = rot[1, 1] / det
            rot[1, 1] = trp / det
            rot[0, 1] = -rot[0, 1] / det
            rot[1, 0] = -rot[1, 0] / det
        elif abs(rot[2, 2]) > cut8:
            det = rot[0, 0] * rot[2, 2] - rot[0, 2] * rot[2, 0]
            trp = rot[0, 0]
            rot[0, 0] = rot[2, 2] / det
            rot[2, 2] = trp / det
            rot[0, 2] = -rot[0, 2] / det
            rot[2, 0] = -rot[2, 0] / det
        else:
            rot[0, 0] = 1.0 / rot[0, 0]
    elif abs(rot[1, 1]) > cut8:
        if abs(rot[2, 2]) > cut8:
            det = rot[2, 2] * rot[1, 1] - rot[2, 1] * rot[1, 2]
            trp = rot[2, 2]
            rot[2, 2] = rot[1, 1] / det
            rot[1, 1] = trp / det
            rot[2, 1] = -rot[2, 1] / det
            rot[1, 2] = -rot[1, 2] / det
        else:
            rot[1, 1] = 1.0 / rot[1, 1]
    elif abs(rot[2, 2]) > cut8:
        rot[2, 2] = 1.0 / rot[2, 2]
    else:
        raise RuntimeError("every diagonal element is zero")
    # tens(ia,ib,ic): Levi-Civita-like tensor, Fortran column-major data statement
    tdata = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    tens = np.zeros((3, 3, 3))
    idx = 0
    for ic in range(3):
        for ib in range(3):
            for ia in range(3):
                tens[ia, ib, ic] = tdata[idx]
                idx += 1
    p = np.zeros((nvar, nvar))
    # P_rot[(i,ic),(j,jc)] = sum tens(ia,ib,ic) tens(ja,jb,jc) rot(ia,ja) x(i,ib) x(j,jb)
    xr = xm.reshape(nat, 3)
    # A[ic, ib] contributions: sum_ia tens(ia,ib,ic) * ... handle via einsum
    prot = np.einsum("abc,deg,ad,ib,je->icjg", tens, tens, rot, xr, xr, optimize=True)
    for i in range(nat):
        for j in range(nat):
            p[3 * i : 3 * i + 3, 3 * j : 3 * j + 3] = prot[i, :, j, :]
    for i in range(nat):
        for j in range(nat):
            tr = 1.0 / (rm[3 * i] * rm[3 * j] * totm)
            for c in range(3):
                p[3 * i + c, 3 * j + c] += tr
    # only the lower triangle is computed in MOPAC and mirrored; the full expression is symmetric
    pl = np.tril(p)
    p = pl + np.tril(pl, -1).T
    p = -p
    p[np.diag_indices(nvar)] += 1.0
    p[np.abs(p) < cut8] = 0.0
    return p @ f @ p


def ef_minimize(
    fun,
    x0,
    masses,
    tol2=0.01,
    dmax=0.2,
    ddmax=0.5,
    ddmin=1.0e-4,
    hess_diag=200.0,
    maxcycles=2000,
    verbose=False,
):
    """EF minimisation.  ``fun(x, last, want_grad, gnorm)`` returns (funct, grad or None).

    Returns (x_final, info)."""
    nvar = len(x0)
    x = np.array(x0, float)
    demin, gmin = 1.0e-2, 5.0
    rmin, rmax = 0.0, 1.0e3
    st = _FormdState()
    funct, grad = fun(x, True, True, 0.0)
    gnorm_state = {"gnorm": 0.0}
    olde = funct
    rmx = math.sqrt(float(grad @ grad))
    info = {"cycles": 0, "status": "ok"}
    if rmx < tol2:
        info["status"] = "already optimised"
        funct, _ = fun(x, True, False, 0.0)
        return x, info
    hess = np.eye(nvar) * hess_diag
    absmin = 1.0e9
    itry1 = 0
    cos_const = 1.0
    ihess = 0
    nstep = 0
    oldf = np.zeros(nvar)
    d = np.zeros(nvar)
    ddx = 0.0
    best_funct = 1.0e10
    best_x = x.copy()
    nmass = len(masses)
    finish = None
    while True:
        if ihess > 0:
            # BFGS update (updhes, iupd = 2)
            tvec = hess @ d
            svec = grad - oldf
            dds = float(svec @ d)
            ddtd = float(d @ tvec)
            if abs(dds) < 1.0e-20 or abs(ddtd) < 1.0e-20:
                raise RuntimeError("zero divide in updhes")
            upd = np.outer(svec, svec) / dds - np.outer(tvec, tvec) / ddtd
            hess = hess + upd
        gnorm = math.sqrt(float(grad @ grad))
        gnorm_state["gnorm"] = gnorm
        if best_funct > funct:
            best_funct = funct
            best_x = x.copy()
        ihess += 1
        nstep += 1
        rmx = math.sqrt(float(grad @ grad))
        if rmx < tol2:
            finish = "gradient"
            break
        if nstep > 5:
            if absmin - funct < 1.0e-5:
                if itry1 > 15 or (rmx < 0.1 and itry1 > 9):
                    finish = "stationary"
                    break
                itry1 += 1
            else:
                itry1 = 0
                absmin = funct
        olde = funct
        if nstep > 5:
            cosine = float(grad @ oldf) / math.sqrt(
                float(grad @ grad) * float(oldf @ oldf)
            )
            if cosine > 0.9:
                cos_const = cos_const * 1.5
            else:
                cos_const = 1.0
        oldf = grad.copy()
        if nvar == 3 * nmass and nmass > 2:
            hess = project_hessian(hess, x, masses)
        eigval, u = np.linalg.eigh(hess)
        eigval = np.where(np.abs(eigval) < 1.0e-6, 0.0, eigval)
        fx = u.T @ grad
        fx = np.where(eigval == 0.0, 0.0, fx)
        # inner loop: form step, evaluate, accept/reject
        while True:
            d, ddx, xlamd, xlamd0, skal = formd(eigval, fx, dmax, u, st)
            d = d * cos_const
            x = x + d
            depre = 0.0
            for i in range(nvar):
                xtmp = xlamd
                if abs(xtmp - eigval[i]) >= TMTWO:
                    ss = skal * fx[i] / (xtmp - eigval[i])
                    depre += ss * (fx[i] + 0.5 * ss * eigval[i])
            funct, grad = fun(x, False, True, gnorm_state["gnorm"])
            deact = funct - olde
            if depre == 0.0:
                finish = "zero depre"
                break
            ratio = deact / depre
            lrjk = False
            if (ratio < rmin or ratio > rmax) and (
                abs(depre) > demin or abs(deact) > demin
            ):
                lrjk = True
            if lrjk and abs(dmax - ddmin) < 1.0e-20:
                lrjk = False
            if not lrjk:
                break
            x = x - d
            dmax = min(dmax, ddx) / 2.0
            if dmax < ddmin:
                finish = "trust"
                break
        if finish:
            if finish == "trust" or finish == "zero depre":
                if best_funct < funct:
                    funct = best_funct
                    x = best_x.copy()
            break
        if (rmx > gmin) or (abs(depre) > demin or abs(deact) > demin):
            if ratio >= 3.0:
                dmax = min(dmax, ddx) / 2.0
            if ratio >= 0.5 and ddx > (dmax - TMSIX):
                dmax = dmax * math.sqrt(2.0)
            if abs(ratio - 1.0) < 0.1:
                dmax = dmax * math.sqrt(2.0)
            dmax = max(dmax, ddmin)
            dmax = min(dmax, ddmax)
        if rmx < gmin and (abs(depre) < demin and abs(deact) < demin):
            dmax = max(dmax, 0.1)
        if dmax < ddmin:
            finish = "trust"
            break
        if nstep >= maxcycles:
            finish = "cycles"
            break
    info["cycles"] = nstep
    info["status"] = finish
    return x, info
