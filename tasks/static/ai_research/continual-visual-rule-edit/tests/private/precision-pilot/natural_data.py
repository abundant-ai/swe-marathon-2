"""Ordinary fixed-width checkpoints trained on historical inspection orders."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if not (ROOT / "long_data.py").exists():
    sys.path.insert(1, str(ROOT.parent / "extended"))
import long_data

SEEDS = long_data.SEEDS
SITE = long_data.SITE
BANK = long_data.BANK
RECIPES = long_data.RECIPES
branch_seed = long_data.branch_seed
origin = long_data.origin
arrays = long_data.arrays
many_gallery = long_data.many_gallery
encode = long_data.encode
coordinates = long_data.coordinates
source = long_data.source
site_of = long_data.site_of
from coupled import hidden, update


def train(seed: int, age: int = 32) -> dict:
    """Train and age a width-28 scanner without widening or transplanting any hidden rows."""
    raw, y, parts = source.partitions()
    pixels, _, _ = source.contents(raw, y, parts[1])
    x = source.turn(encode(pixels, site_of(origin(seed))), coordinates(seed))
    features = source.measure(pixels)
    mean = features.mean(0)
    f = (features - mean) / features.std(0).clip(0.01, None)
    rng = np.random.default_rng(seed)
    width = 28
    s = {
        "W": rng.normal(0, 0.075, (2, width, 48)),
        "b": np.zeros((2, width)),
        "bridge": rng.normal(0, 0.19, (width, width)),
        "v": rng.normal(0, 0.045, (2, width)),
        "c": np.zeros(1),
    }
    for step in range(age):
        labels = f @ rng.normal(size=4) > 0
        for _ in range(85):
            idx = rng.integers(len(x), size=64)
            update(s, x[idx], labels[idx], 0.045, 0.028)
    h = hidden(x, s)
    proj = np.c_[h.reshape(len(h), -1), np.ones(len(h))]
    fit = np.linalg.solve(
        proj.T @ proj + 0.75 * np.eye(2 * width + 1), proj.T @ (2.0 * (f > 0) - 1)
    )
    s.update(
        legacy=fit[:-1].reshape(2, width, 4).transpose(0, 2, 1),
        intercepts=fit[-1],
        cut=mean,
        coordinates=coordinates(seed),
    )
    return s


def station(seed: int) -> dict:
    """Load one field's unexpanded network and its archive heads."""
    with np.load(ROOT / "data" / f"bank-{seed}.npz") as f:
        return dict(f)


if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor

    seeds = [branch_seed(s, k) for s in (*SEEDS, 977) for k in range(3)]
    with ProcessPoolExecutor(4) as pool:
        for seed, state in zip(seeds, pool.map(train, seeds)):
            np.savez_compressed(ROOT / "data" / f"bank-{seed}.npz", **state)
    ss = [station(branch_seed(977, k)) for k in range(3)]
    gs = [many_gallery(branch_seed(977, k)) for k in range(3)]
    np.savez_compressed(
        ROOT / "data" / "calibration.npz",
        W=np.stack([a["W"] for a in ss]),
        b=np.stack([a["b"] for a in ss]),
        v=np.stack([a["legacy"] for a in ss]),
        bridge=np.stack([a["bridge"] for a in ss]),
        x=np.stack([g[0] for g in gs]),
        tags=np.stack([g[1] for g in gs]),
    )
