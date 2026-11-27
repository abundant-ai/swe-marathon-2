"""Whole-form registration pairs from independent real handwritten specimens."""

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if not (ROOT / "natural_data.py").exists():
    sys.path.insert(1, str(ROOT.parent / "natural"))
import natural_data

SITE = natural_data.SITE
SEEDS = natural_data.SEEDS
RECIPES = natural_data.RECIPES
BANK = natural_data.BANK
station = natural_data.station
branch_seed = natural_data.branch_seed
origin = natural_data.origin
many_gallery = natural_data.many_gallery
source = natural_data.source
from long_data import points

REGISTER = np.stack((BANK[1], 3 - BANK[0] - BANK[1]))


@lru_cache(maxsize=30)
def specimen_ids(site, partition):
    """Use identical held-out specimen IDs across all physical fields of each site."""
    _raw, labels = source.captures("test")
    g = np.random.default_rng(42551 + SEEDS[site])
    sets = [[], []]
    for digit in range(5):
        ids = g.permutation(np.flatnonzero(labels == digit))
        middle = len(ids) // 2
        sets[0].extend(ids[:middle])
        sets[1].extend(ids[middle:])
    return np.array(sets[partition])


@lru_cache(maxsize=90)
def captures(site, field, domain, partition):
    """Keep single-field activations unique over the original specimen and its four rotations."""
    raw, y = source.captures("test")
    ids = specimen_ids(site, partition)
    p, d, o = source.contents(raw, y, ids)
    x, shifted = points(branch_seed(SEEDS[site], field), p, domain)
    return x, d, o, source.measure(shifted)


@lru_cache(maxsize=30)
def paired(site, partition):
    """Construct every Cartesian pair of product and reference poses on each handwritten base form."""
    ids = specimen_ids(site, partition)
    n = len(ids)
    rng = np.random.default_rng(65487 + 129 * site + partition)
    order = rng.permutation(n)
    other = np.empty(n, int)
    other[order] = np.roll(order, 1)
    base = np.repeat(np.arange(n), 16)
    u = np.tile(np.repeat(np.arange(4), 4), n)
    v = np.tile(np.tile(np.arange(4), 4), n)
    return 4 * base + u, 4 * other[base] + v
