"""Frozen incoming day and night recipes and their shared station checkpoints."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if not (ROOT / "clock_data.py").exists():
    sys.path.insert(1, str(ROOT.parent / "prospective"))
import clock_data

STATIONS = clock_data.ROOT
SITE = clock_data.SITE
SEEDS = clock_data.SEEDS
commissioning = clock_data.commissioning

RECIPES = np.array(
    [
        [
            [[1, 0, 0, 1, 2], [0, 3, 3, 3, 3]],
            [[3, 1, 0, 3, 0], [2, 2, 3, 1, 1]],
            [[3, 3, 3, 2, 1], [0, 2, 1, 0, 2]],
            [[1, 2, 0, 3, 2], [0, 0, 2, 2, 1]],
            [[1, 2, 3, 1, 0], [0, 0, 0, 2, 3]],
            [[2, 3, 1, 0, 1], [1, 0, 3, 1, 0]],
        ],
        [
            [[2, 1, 2, 1, 0], [0, 2, 1, 2, 1]],
            [[3, 0, 1, 1, 0], [1, 3, 3, 2, 2]],
            [[3, 0, 0, 2, 1], [0, 1, 3, 1, 0]],
            [[3, 0, 1, 3, 2], [0, 2, 0, 2, 3]],
            [[0, 0, 1, 3, 0], [1, 2, 0, 2, 2]],
            [[1, 3, 3, 2, 2], [2, 0, 2, 3, 1]],
        ],
    ]
)
