"""Visible-face and outline operations on the public camera views."""

import ctypes
import subprocess
import tempfile
from pathlib import Path
import numpy as np


def native_surfaces(mesh, poses):
    """Find depth and nearest face at every native integer pixel center under the B lens."""
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "render.c"
        source.write_text(RASTER_SOURCE)
        dll = Path(tmp) / "raster.so"
        subprocess.run(
            [
                "gcc",
                "-O2",
                "-std=c99",
                "-shared",
                "-fPIC",
                str(source),
                "-lm",
                "-o",
                str(dll),
            ],
            check=True,
        )
        render = ctypes.CDLL(str(dll)).raster
        double = np.ctypeslib.ndpointer(np.float64, flags="C_CONTIGUOUS")
        render.argtypes = [
            double,
            ctypes.c_size_t,
            double,
            np.ctypeslib.ndpointer(np.int32, flags="C_CONTIGUOUS"),
        ]
        render.restype = None
        for pose in poses:
            camera = (mesh[0] - pose[:3, 3]) @ pose[:3, :3]
            tri = np.ascontiguousarray(camera[mesh[1]], np.float64)
            depth = np.full((480, 640), np.inf)
            face = np.full((480, 640), -1, np.int32)
            render(tri, len(tri), depth, face)
            yield camera, depth, face


def mask(rings):
    """Fill polygon interiors at exact integer-valued pixel centers, subtracting holes."""
    result = np.zeros((480, 640), bool)
    for i, ring in enumerate(rings):
        p = np.asarray(ring, float)
        lower = np.maximum(np.floor(p.min(axis=0)).astype(int), 0)
        upper = np.minimum(np.ceil(p.max(axis=0)).astype(int), [639, 479])
        x, y = np.meshgrid(
            np.arange(lower[0], upper[0] + 1), np.arange(lower[1], upper[1] + 1)
        )
        inside = np.zeros(x.shape, bool)
        for a, b in zip(p, np.roll(p, -1, axis=0)):
            if a[1] == b[1]:
                continue
            inside ^= ((a[1] > y) != (b[1] > y)) & (
                x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            )
        target = result[lower[1] : upper[1] + 1, lower[0] : upper[0] + 1]
        if i == 0:
            target |= inside
        else:
            target &= ~inside
    return result
