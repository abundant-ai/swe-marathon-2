"""Paired feeder scans with fixed acquisition changes, preserving the underlying real handwriting."""

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if not (ROOT / "shift_data.py").exists():
    sys.path.insert(1, str(ROOT.parent / "changeover"))
import shift_data

SITE = shift_data.SITE
SEEDS = shift_data.SEEDS
STATIONS = shift_data.STATIONS
RECIPES = shift_data.RECIPES
from clock_data import commissioning, coordinates, encode
from panel_data import site_of, source

BANK = np.array([[0, 2, 1, 0, 2, 1], [1, 0, 2, 2, 1, 0]])
FIELDS = ("part", "lot", "audit")


def branch_seed(station_seed: int, field: int) -> int:
    """Return the independent training seed for one physical scanner on the form."""
    return station_seed + 1000 * field


def origin(seed: int) -> int:
    """Recover the common station ID, independent of the field commissioning seed."""
    return seed % 1000


def station(seed: int) -> dict:
    """Load one aged field-specific checkpoint, trained in its own channel system."""
    with np.load(ROOT / "data" / f"bank-{seed}.npz") as f:
        return dict(f)


def shifted(
    pixels: np.ndarray, dx: float, dy: float, blur: float, gamma: float
) -> np.ndarray:
    """Apply a label-preserving subpixel feeder shift, optical ink spread and response curve."""
    x = np.asarray(pixels, float).reshape(-1, 8, 8) / 16.0

    def offset(v, h, w):
        padded = np.pad(v, ((0, 0), (2, 2), (2, 2)))
        return padded[:, 2 - h : 10 - h, 2 - w : 10 - w]

    lo_x = int(np.floor(dx))
    lo_y = int(np.floor(dy))
    a = dx - lo_x
    b = dy - lo_y
    new = (
        (1 - a) * (1 - b) * offset(x, lo_y, lo_x)
        + a * (1 - b) * offset(x, lo_y, lo_x + 1)
        + (1 - a) * b * offset(x, lo_y + 1, lo_x)
        + a * b * offset(x, lo_y + 1, lo_x + 1)
    )
    smoothed = (
        offset(new, -1, 0) + offset(new, 1, 0) + offset(new, 0, -1) + offset(new, 0, 1)
    ) / 4
    return (
        np.rint(16 * ((1 - blur) * new + blur * smoothed).clip(0, 1) ** gamma)
        .reshape(-1, 64)
        .astype(np.uint8)
    )


SETTINGS = (
    (0.0, 0.0, 0.0, 1.0),
    (0.65, 0.30, 0.10, 0.86),
    (-0.55, -0.50, 0.24, 1.13),
    (-0.25, 0.7, 0.15, 0.97),
    (0.5, -0.65, 0.23, 1.06),
)


def points(seed: int, pixels: np.ndarray, domain: int) -> tuple[np.ndarray, np.ndarray]:
    """Encode one acquisition domain using the checkpoint site’s frozen feature extractor."""
    p = shifted(pixels, *SETTINGS[domain])
    x = source.turn(encode(p, site_of(origin(seed))), coordinates(seed))
    return x, p


@lru_cache(maxsize=64)
def arrays(seed: int, domain: int) -> list[tuple[np.ndarray, ...]]:
    """Return disjoint future-training and held-out specimens from the original test writers."""
    raw, y = source.captures("test")
    rng = np.random.default_rng(42551 + seed)
    train = []
    test = []
    for d in range(5):
        ids = rng.permutation(np.flatnonzero(y == d))
        n = len(ids) // 2
        train.extend(ids[:n])
        test.extend(ids[n:])
    result = []
    for subset in (train, test):
        p, d, pose = source.contents(raw, y, np.asarray(subset))
        x, new = points(seed, p, domain)
        result.append((x, d, pose, source.measure(new)))
    return result


def many_gallery(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Pair all three measured feeder views by specimen while exposing only twenty verified labels."""
    _base, t = commissioning(origin(seed))
    samples = []
    tags = []
    for k in (0, 1, 2):
        x, p = points(seed, t[:, :64], k)
        mt = t.copy()
        mt[:, :64] = p
        if k:
            mt[:, 64:66] = 255
        samples.append(x)
        tags.append(
            np.c_[
                mt, np.full(len(t), k), np.arange(len(t)), np.full(len(t), seed // 1000)
            ]
        )
    return np.concatenate(samples), np.concatenate(tags)
