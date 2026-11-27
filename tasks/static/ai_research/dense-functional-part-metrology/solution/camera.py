"""Published Freiburg 1 RGB lens model, calibrated projections and ray triangulation."""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

F = np.array([517.3, 516.5])
C = np.array([318.6, 255.3])
K1, K2, P1, P2, K3 = 0.2624, -0.9531, -0.0054, 0.0026, 1.1633


def distort(xy):
    """Apply the Freiburg 1 Brown–Conrady RGB calibration to normalized rays."""
    x, y = np.asarray(xy).T
    r = x * x + y * y
    k = 1 + r * (K1 + r * (K2 + r * K3))
    return np.column_stack(
        (
            x * k + 2 * P1 * x * y + P2 * (r + 2 * x * x),
            y * k + P1 * (r + 2 * y * y) + 2 * P2 * x * y,
        )
    )


def world_to_rgb(points, pose):
    """Map metric first-camera points to their distorted native RGB pixel centers."""
    camera = (np.atleast_2d(points) - pose[:3, 3]) @ pose[:3, :3]
    return distort(camera[:, :2] / camera[:, 2:]) * F + C


def rays(pixels, pose):
    """Return unnormalized world ray directions for native RGB pixel centers."""
    distorted = (np.atleast_2d(pixels) - C) / F
    xy = distorted.copy()
    for _ in range(20):
        xy += distorted - distort(xy)
    return np.column_stack((xy, np.ones(len(xy)))) @ pose[:3, :3].T


def poses_from_rows(rows):
    """Convert x,y,z,qx,qy,qz,qw camera-to-first-camera rows to rigid transforms."""
    poses = np.tile(np.eye(4), (len(rows), 1, 1))
    poses[:, :3, :3] = Rotation.from_quat(rows[:, 3:]).as_matrix()
    poses[:, :3, 3] = rows[:, :3]
    return poses


def triangulate(pixels, poses):
    """Fit one 3D point to all labeled image centers by reprojection least squares."""
    directions = np.stack([rays(x, p)[0] for x, p in zip(pixels, poses)])
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    p = np.eye(3)[None, :, :] - directions[:, :, None] * directions[:, None, :]
    point = np.linalg.lstsq(
        p.sum(0), (p @ poses[:, :3, 3, None]).sum(0)[:, 0], rcond=None
    )[0]

    def residual(x):
        return np.concatenate(
            [world_to_rgb(x, pose)[0] - uv for uv, pose in zip(pixels, poses)]
        )

    return least_squares(residual, point, loss="soft_l1", f_scale=1).x


def unit_circle(n=48):
    theta = 2 * np.pi * np.arange(n) / n
    return np.stack((np.cos(theta), np.sin(theta)), axis=1)


def ellipse_pixels(params):
    """Sample the optical ellipse contour recorded by a benchmark author on an input RGB frame."""
    x, y, rx, ry, angle = params
    t = np.deg2rad(angle)
    transform = np.array([[np.cos(t), np.sin(t)], [-np.sin(t), np.cos(t)]])
    return np.array([x, y]) + (unit_circle() * [rx, ry]) @ transform
