"""Fit functionally labeled faces using public RGB traces and tracked rays."""

from __future__ import annotations

import numpy as np
from camera import (  # bundled module
    ellipse_pixels,
    rays,
    triangulate,
    unit_circle,
    world_to_rgb,
)
from scipy.optimize import least_squares

COLORS = {8: [198, 105, 33], 9: [64, 118, 208], 10: [213, 208, 207]}


def fit_ellipse(observations, poses, normal):
    """Fit one planar 3D ellipse to the centers and native image conics across inputs."""
    contours = np.asarray([ellipse_pixels(obs) for obs in observations])
    target = contours.mean(axis=1)
    center = triangulate(target, poses)
    p = poses[0]
    direction = rays(contours[0], p)
    points = (
        p[:3, 3]
        + direction
        * (np.dot(center - p[:3, 3], normal) / (direction @ normal))[:, None]
    )
    axes = np.linalg.lstsq(unit_circle(), points - center, rcond=None)[0]

    # Tensor square roots measure discrepancies in native pixels in both contour axes.
    def geometry(x):
        return x[:3] + unit_circle() @ x[3:].reshape(2, 3)

    def moment(contour):
        mean = contour.mean(axis=0)
        centered = contour - mean
        e, u = np.linalg.eigh(2 * centered.T @ centered / len(centered))
        return np.r_[
            mean,
            (u * np.sqrt(np.maximum(0, e))) @ u.T[0],
            (u * np.sqrt(np.maximum(0, e))) @ u.T[1],
        ]

    moments = [moment(c) for c in contours]

    def residual(x):
        world = geometry(x)
        return np.concatenate(
            [moment(world_to_rgb(world, p)) - m for p, m in zip(poses, moments)]
        )

    result = least_squares(
        residual, np.r_[center, axes.ravel()], loss="soft_l1", max_nfev=200
    )
    return geometry(result.x)


def patch(rings):
    """Triangulate a bounded cap or annulus, respecting the visible negative space."""
    if len(rings) == 2:
        outer, inner = rings
        # Align winding/phase of the two independently fitted 3D rings.
        possibilities = [
            np.roll(seq, k, axis=0)
            for seq in (inner, inner[::-1])
            for k in range(len(inner))
        ]
        inner = min(possibilities, key=lambda pts: np.square(outer - pts).sum())
        n = len(outer)
        a = np.arange(n)
        b = np.roll(a, -1)
        return np.vstack((outer, inner)), np.vstack(
            (np.stack((a, b, n + a), axis=1), np.stack((b, n + b, n + a), axis=1))
        )
    outer = rings[0]
    n = len(outer)
    a = np.arange(n)
    return np.vstack((outer, outer.mean(0))), np.stack(
        (a, np.roll(a, -1), np.full(n, n)), axis=1
    )


def fit_parts(data, poses):
    """Triangulate control footprints using four independent public RGB images."""
    views = list(map(int, (k for k in data if k.isdigit())))

    def observed(part):
        selected = [i for i in views if str(part) in data[str(i)]]
        return [data[str(i)][str(part)] for i in selected], poses[selected]

    centers = []
    for part in range(1, 9):
        obs, ps = observed(part)
        centers.append(triangulate([o[:2] for o in obs], ps))
    normal = np.linalg.svd(centers - np.mean(centers, axis=0))[2][-1]
    result = {}
    for part in range(1, 11):
        obs, ps = observed(part)
        if part == 10:
            rings = [
                np.asarray([triangulate(np.asarray(obs)[:, j], ps) for j in range(4)])
            ]
        elif part == 9:
            rings = [fit_ellipse([o[j] for o in obs], ps, normal) for j in range(2)]
        else:
            rings = [fit_ellipse(obs, ps, normal)]
        result[part] = patch(rings)
    return result


def add_parts(context, traces, poses):
    """Remove overlapping shell triangles and attach the metric multiview contact surfaces."""
    from scipy.spatial import cKDTree

    v, f, c, ids = context
    meshes = fit_parts(traces, poses)
    keep = np.ones(len(f), bool)
    centers = v[f].mean(axis=1)
    for part, (points, indices) in meshes.items():
        obj = 1 if part <= 8 else part - 7
        nearest = cKDTree(points[indices].mean(axis=1)).query(centers)[0]
        keep &= ~((ids == obj) & (nearest < (0.012 if part <= 8 else 0.019)))
    groups = [[v], [f[keep]], [c], [ids[keep]], [np.zeros(keep.sum(), np.uint8)]]
    offset = len(v)
    for part, (points, indices) in meshes.items():
        obj = 1 if part <= 8 else part - 7
        color = COLORS.get(part, [35, 34, 38])
        values = (
            points,
            indices + offset,
            np.tile(color, (len(points), 1)),
            np.full(len(indices), obj),
            np.full(len(indices), part),
        )
        for target, value in zip(groups, values):
            target.append(value)
        offset += len(points)
    return tuple(np.concatenate(arrays) for arrays in groups)
