"""Estimate a linear board response from two unordered sets of handheld object views."""

from itertools import permutations
from functools import lru_cache

import numpy as np
from PIL import Image


def make_panel(clips, matrix, rng):
    before = clips[::2].copy()
    after = np.clip(np.rint(clips[1::2] @ matrix.T), 0, 255).astype(np.uint8)

    # Each camera round has its own acquisition order. Each tile is a separate real exposure.
    def mosaic(tiles):
        tiles = tiles[rng.permutation(len(tiles))]
        return np.concatenate(
            [np.concatenate(tiles[i : i + 5], axis=1) for i in (0, 5)]
        )

    return Image.fromarray(
        np.concatenate((mosaic(before), mosaic(after)), axis=0)
    ).resize((640, 512), Image.Resampling.NEAREST)


def matching(cost):
    @lru_cache(None)
    def extend(mask):
        row = mask.bit_count()
        if row == len(cost):
            return 0.0, ()
        candidates = []
        for j in range(len(cost)):
            if mask & (1 << j):
                continue
            rest, order = extend(mask | (1 << j))
            candidates.append((float(cost[row, j]) + rest, (j,) + order))
        return min(candidates)

    return extend(0)


def appearance(tiles):
    spatial = tiles.reshape(10, 8, 4, 8, 4, 3).mean((2, 4))
    levels = np.quantile(
        tiles.reshape(10, -1, 3), (0.10, 0.35, 0.65, 0.90), axis=1
    ).transpose(1, 0, 2)
    return np.concatenate(
        (spatial.reshape(10, -1), np.tile(levels.reshape(10, -1), (1, 8))), axis=1
    )


def estimate(path):
    with Image.open(path) as sheet:
        raw = (
            np.array(
                sheet.convert("RGB").resize((160, 128), Image.Resampling.NEAREST),
                dtype=np.float64,
            )
            / 255
        )
    tiles = raw.reshape(4, 32, 5, 32, 3).transpose(0, 2, 1, 3, 4).reshape(20, 32, 32, 3)
    original, sensor = np.split(tiles, 2)
    target = appearance(original)
    # An initial channel routing hypothesis gives a candidate metric for matching the rounds.
    median = np.quantile(original, 0.65, axis=(0, 1, 2))
    best_cost = float("inf")
    for perm in permutations(range(3)):
        routed = sensor[..., list(perm)]
        gain = median / np.maximum(0.02, np.quantile(routed, 0.65, axis=(0, 1, 2)))
        transformed = appearance(routed * gain)
        cost = np.mean(abs(target[:, None] - transformed[None]), axis=-1)
        total, order = matching(cost)
        if total < best_cost:
            best_cost = total
            pairing = list(order)
            inverse = np.diag(gain) @ np.eye(3)[list(perm)]
    # Use local patches to align different viewpoints, and downweight occlusions and moving edges.
    sensor = sensor[pairing]
    offsets = [(dy, dx) for dy in range(-3, 4) for dx in range(-3, 4)]
    originals = original[:, 4:-4, 4:-4]
    prev = inverse.copy()
    for _ in range(4):
        corrected = sensor @ inverse.T
        residuals = []
        samples = []
        for dy, dx in offsets:
            a, b = 4 + dy, 4 + dx
            error = abs(corrected[:, a : a + 24, b : b + 24] - originals).mean(-1)
            padded = np.pad(error, ((0, 0), (1, 1), (1, 1)), mode="edge")
            loss = (
                sum(
                    padded[:, i : i + 24, j : j + 24]
                    for i in range(3)
                    for j in range(3)
                )
                / 9
            )
            residuals.append(loss + 0.0015 * (abs(dx) + abs(dy)))
            samples.append(sensor[:, a : a + 24, b : b + 24])
        losses = np.stack(residuals)
        choice = losses.argmin(0)
        selected = np.take_along_axis(
            np.stack(samples), choice[None, ..., None], axis=0
        )[0]
        weight = (1 / (0.015 + losses.min(0))).clip(0, 40).reshape(-1, 1)
        x = selected.reshape(-1, 3)
        y = originals.reshape(-1, 3)
        inv = np.linalg.solve(
            x.T @ (x * weight) + 0.05 * np.eye(3), x.T @ (y * weight) + 0.05 * prev.T
        )
        inverse = inv.T
    return inverse
