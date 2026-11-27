"""Create the reference-card replacement photograph delivered at scanner startup."""

import numpy as np


def photograph(
    anchors: np.ndarray, new: np.ndarray, permutation: np.ndarray
) -> np.ndarray:
    """Each column pairs a room's archived card with its replacement, in arbitrary column order."""
    layout = np.full((32, 32, 3), 242, dtype=np.uint8)
    for y, cards in ((2, anchors), (18, new)):
        for x, i in zip((2, 18), permutation, strict=True):
            layout[y : y + 12, x : x + 12] = cards[i].repeat(2, 0).repeat(2, 1)
    return layout
