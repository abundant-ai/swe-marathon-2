"""Construct the two public station reference photographs and synthetic scanner handovers."""

import numpy as np
from PIL import Image


def cards(seed: int) -> np.ndarray:
    """Return two distinct arrangements of the same 36 printed RGB swatches."""
    rng = np.random.default_rng(seed)
    palette = rng.integers(28, 236, size=(36, 3), dtype=np.uint8)
    return np.stack([palette[rng.permutation(36)].reshape(6, 6, 3) for _ in range(2)])


def sheet(patches: np.ndarray) -> Image.Image:
    """Place the two station cards side by side at a readable square-patch scale."""
    return Image.fromarray(
        np.concatenate(list(patches), axis=1).repeat(16, 0).repeat(16, 1)
    )


def exposure(
    patches: np.ndarray, response: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Simulate a chart exposure with rotation, bounded translation, camera response and an occluded patch."""
    tiles = np.rot90(patches, int(rng.integers(4)))
    paper = tiles.repeat(4, axis=0).repeat(4, axis=1)
    frame = np.full((32, 32, 3), rng.integers(32, 74), dtype=np.uint8)
    y, x = rng.integers(1, 8, size=2)
    frame[y : y + 24, x : x + 24] = paper
    row, col = rng.integers(6, size=2)
    frame[y + row * 4 : y + row * 4 + 4, x + col * 4 : x + col * 4 + 4] = rng.integers(
        60, 155, size=3
    )
    noise = rng.normal(0, 1.2, size=frame.shape)
    return np.rint(frame @ response.T + noise).clip(0, 255).astype(np.uint8)
