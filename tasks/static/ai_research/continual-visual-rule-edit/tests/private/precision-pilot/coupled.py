"""Train station adapters with a learned residual connection from early to late features."""

import numpy as np
from panel_data import ROOT, SEEDS, coordinates, encode, probes, site_of, source


def hidden(x, s):
    a = x[:, 0] @ s["W"][0].T + s["b"][0]
    early = np.maximum(a, 0.0)
    z = x[:, 1] @ s["W"][1].T + s["b"][1] + early @ s["bridge"].T
    late = np.maximum(z, 0.0)
    return np.stack([early, late], 1)


def update(s, x, y, lr, sparse=0.0, trunk_fraction=1.0):
    h = hidden(x, s)
    logit = np.einsum("nbh,bh->n", h, s["v"]) + s["c"]
    n = len(y)
    err = (1 / (1 + np.exp(-np.clip(logit, -40, 40))) - y) / n
    g1 = (err[:, None] * s["v"][1] + sparse / (2 * n)) * (h[:, 1] > 0)
    g0 = (err[:, None] * s["v"][0] + sparse / (2 * n) + g1 @ s["bridge"]) * (
        h[:, 0] > 0
    )
    rate = lr * trunk_fraction
    s["bridge"] -= rate * g1.T @ h[:, 0]
    for k, g in enumerate((g0, g1)):
        s["W"][k] -= rate * g.T @ x[:, k]
        s["b"][k] -= rate * g.sum(0)
    s["v"] -= lr * np.einsum("n,nbh->bh", err, h)
    s["c"] -= lr * err.sum()


def train(seed, age=32):
    raw, y, parts = source.partitions()
    pix, _, _ = source.contents(raw, y, parts[1])
    site = site_of(seed)
    x = source.turn(encode(pix, site), coordinates(seed))
    f = source.measure(pix)
    mean = f.mean(0)
    f = (f - mean) / f.std(0).clip(0.01, None)
    rng = np.random.default_rng(seed)
    s = {
        "W": rng.normal(0, 0.075, (2, 24, 48)),
        "b": np.zeros((2, 24)),
        "bridge": rng.normal(0, 0.19, (24, 24)),
        "v": rng.normal(0, 0.045, (2, 24)),
        "c": np.zeros(1),
    }
    for step in range(age):
        y = f @ rng.normal(size=4) > 0
        for _ in range(85):
            ids = rng.integers(len(x), size=64)
            update(s, x[ids], y[ids], 0.045, 0.028)
    h = hidden(x, s)
    a = np.c_[h.reshape(len(h), -1), np.ones(len(h))]
    fit = np.linalg.solve(a.T @ a + 0.75 * np.eye(49), a.T @ (2.0 * (f > 0) - 1))
    heads = fit[:-1].reshape(2, 24, 4).transpose(0, 2, 1)
    rng = np.random.default_rng(seed + 88431)
    out = {k: [] for k in ("W", "b", "v", "legacy")}
    donor = []
    scales = []
    perms = []
    for k in range(2):
        d = rng.choice(np.argsort(h[:, k].std(0))[-16:], 4, replace=False)
        scale = rng.uniform(0.6, 1.7, 4)
        perm = rng.permutation(28)
        donor.append(d)
        scales.append(scale)
        perms.append(perm)
        w = np.vstack([s["W"][k], s["W"][k, d] * scale[:, None]])
        b = np.r_[s["b"][k], s["b"][k, d] * scale]
        v = s["v"][k].copy()
        spl = v[d] * rng.uniform(0.35, 0.65, 4)
        v[d] -= spl
        v = np.r_[v, spl / scale]
        old = heads[k].copy()
        alloc = old[:, d] * rng.uniform(0.25, 0.75, (4, 4)) + rng.normal(
            0, 0.06, (4, 4)
        )
        old[:, d] -= alloc
        for key, value in [
            ("W", w[perm]),
            ("b", b[perm]),
            ("v", v[perm]),
            ("legacy", np.column_stack([old, alloc / scale])[:, perm]),
        ]:
            out[key].append(value)
    j = s["bridge"].copy()
    move = j[:, donor[0]] * rng.uniform(0.35, 0.65, (24, 4)) + rng.normal(
        0, 0.075, (24, 4)
    )
    j[:, donor[0]] -= move
    j = np.column_stack([j, move / scales[0]])
    j = np.vstack([j, j[donor[1]] * scales[1][:, None]])
    out = {k: np.stack(v) for k, v in out.items()}
    out.update(
        bridge=j[perms[1]][:, perms[0]],
        c=s["c"],
        intercepts=fit[-1],
        cut=mean,
        coordinates=coordinates(seed),
    )
    for _ in range(15):
        ids = rng.integers(len(x), size=64)
        update(out, x[ids], f[ids, 0] > 0, 0.010)
    return out


if __name__ == "__main__":
    for seed in SEEDS:
        np.savez_compressed(ROOT / "data" / f"net-{seed}.npz", **train(seed))
    public = train(977)
    x, t = probes(977)
    np.savez_compressed(
        ROOT / "data" / "calibration.npz",
        W=public["W"],
        b=public["b"],
        v=public["legacy"],
        bridge=public["bridge"],
        x=x,
        tags=t,
    )
