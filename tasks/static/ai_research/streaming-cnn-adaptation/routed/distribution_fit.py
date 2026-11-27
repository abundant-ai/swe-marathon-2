"""Recover a sensor response from two independent photographic passes over the same objects."""

import itertools
import numpy as np
from PIL import Image


def estimate(path):
    with Image.open(path) as sheet:
        data = (
            np.asarray(
                sheet.convert("RGB").resize((160, 128), Image.Resampling.NEAREST),
                dtype=float,
            )
            / 255
        )
    reference, observed = (a.reshape(-1, 3)[::3] for a in np.split(data, 2))
    random = np.random.default_rng(13)
    directions = np.vstack(
        [
            np.eye(3),
            np.eye(3) - np.roll(np.eye(3), 1, axis=0),
            random.normal(size=(24, 3)),
        ]
    )
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    q = np.linspace(0.025, 0.975, 45)
    target = np.quantile(reference @ directions.T, q, axis=0).T
    scales = np.maximum(0.025, target[:, -1] - target[:, 0])
    indices = np.rint(q * (len(observed) - 1)).astype(int)
    fits = []
    for permutation in itertools.permutations(range(3)):
        routed = observed[:, permutation]
        gains = np.median(reference, axis=0) / np.maximum(
            0.015, np.median(routed, axis=0)
        )
        initial = np.diag(gains) @ np.eye(3)[list(permutation)]
        inverse = initial.copy()
        for iteration in range(12):
            projected = observed @ inverse.T @ directions.T
            ix = np.argsort(projected, axis=0)[indices].T
            samples = observed[ix]
            design = np.einsum("dc,dqi->dqci", directions, samples).reshape(
                len(directions), len(q), 9
            )
            residual = (
                np.einsum("dqi,i->dq", design, inverse.ravel()) - target
            ) / scales[:, None]
            weight = (1 / np.maximum(0.045, abs(residual))) ** 0.5 / scales[:, None]
            x = (design * weight[..., None]).reshape(-1, 9)
            y = (target * weight).ravel()
            prior = 4.0
            inverse = np.linalg.solve(
                x.T @ x + prior * np.eye(9), x.T @ y + prior * initial.ravel()
            ).reshape(3, 3)
        values = np.quantile(observed @ inverse.T @ directions.T, q, axis=0).T
        fits.append((np.mean(abs(values - target) / scales[:, None]), inverse))
    return min(fits, key=lambda pair: pair[0])[1]
