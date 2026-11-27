"""Masked commissioning records and product-specific fixture orientations."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if not (ROOT / "panel_data.py").exists():
    sys.path.insert(1, str(ROOT.parent / "relative"))
    sys.path.append(str(ROOT.parent))
    sys.path.append(str(ROOT.parents[1]))
import panel_data

SEEDS = panel_data.SEEDS
SITE = panel_data.SITE
source = panel_data.source
site_of = panel_data.site_of
coordinates = panel_data.coordinates

NOMINAL = np.array(
    [
        [
            [1, 0, 0, 1, 2],
            [3, 1, 0, 3, 0],
            [3, 3, 3, 2, 1],
            [1, 2, 0, 3, 2],
            [1, 2, 3, 1, 0],
            [2, 3, 1, 0, 1],
        ],
        [
            [2, 2, 1, 1, 1],
            [3, 3, 0, 2, 2],
            [3, 1, 0, 3, 1],
            [2, 2, 0, 0, 0],
            [1, 1, 1, 3, 0],
            [0, 3, 2, 0, 3],
        ],
    ]
)
HISTORICAL = np.array(
    [
        [2, 0, 1, 1, 3],
        [3, 1, 3, 2, 0],
        [3, 2, 0, 0, 1],
        [3, 2, 0, 1, 2],
        [2, 2, 1, 3, 0],
        [3, 3, 1, 0, 2],
    ]
)
LANES = np.array(
    [
        [0, 1, 0, 0, 1],
        [0, 0, 1, 1, 0],
        [0, 1, 0, 1, 0],
        [1, 0, 0, 1, 0],
        [1, 1, 0, 0, 0],
        [1, 0, 0, 0, 1],
    ]
)


def encode(pixels, site):
    with np.load(ROOT / "data" / f"backbone-{site}.npz") as m:
        early = np.maximum((pixels / 16.0 - 0.30) @ m["w1"].T + m["b1"], 0)
        late = np.maximum(early @ m["w2"].T + m["b2"], 0)
        return (np.stack([early, late], 1) - m["mu"]) / m["std"]


def commissioning(seed):
    pix, digit, pose = source.gallery()
    rng = np.random.default_rng(82000 + seed)
    idx = np.concatenate(
        [
            rng.choice(np.flatnonzero((digit == i) & (pose == j)), 9, replace=False)
            for i in range(5)
            for j in range(4)
        ]
    )
    rng.shuffle(idx)
    site = site_of(seed)
    vectors = source.turn(encode(pix[idx], site), coordinates(seed))
    tags = np.c_[
        pix[idx], source.DIGITS[digit[idx]], pose[idx], np.full(len(idx), SITE[site])
    ].astype(np.uint8)
    rng = np.random.default_rng(1577 + int(tags[0, 66]))
    digit, angle = tags[:, 64], tags[:, 65]
    verified = [
        rng.choice(np.flatnonzero((digit == i) & (angle == j)))
        for i in np.unique(digit)
        for j in np.unique(angle)
    ]
    mask = np.ones(len(tags), bool)
    mask[verified] = False
    tags = tags.copy()
    tags[mask, 64:66] = 255
    return vectors, tags
