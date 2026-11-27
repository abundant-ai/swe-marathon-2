"""Check held RGB-D agreement at overlapping measured surfaces, independently of any submitted mesh."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter, minimum_filter

TASK = Path(__file__).resolve().parents[1]
PRIVATE = TASK / "tests/private"
sys.path.insert(0, str(PRIVATE / "dense-telephone-parts"))
from telephone_optics import rays, world_to_rgb
from telephone_score import ROOT, Reference


def audit():
    ref = Reference.load(PRIVATE / "precision-pilot/data/clutter/data", "b")
    with np.load(ROOT / "optical-poses.npz") as a:
        poses = a["poses"]
    with np.load(ROOT / "scoring-rgb.npz") as a:
        rgb = a["rgb"].astype(float)
    records = []
    for i, source in enumerate(ref.depth):
        sy, sx = np.where(source > 0)
        uv = np.column_stack((4 * sx + 2, 4 * sy + 2))
        xyz = poses[i, :3, 3] + source[sy, sx, None] * rays(uv, poses[i])
        for j, target in enumerate(ref.depth):
            if i == j:
                continue
            projected = (world_to_rgb(xyz, poses[j]) - 2) / 4
            rounded = np.rint(projected).astype(int)
            inside = ((rounded >= 1) & (rounded < [159, 119])).all(axis=1)
            x, y = rounded.clip([0, 0], [159, 119]).T
            # Drop boundaries, holes, and large depth steps where nearest sampling mixes surfaces.
            nearest = minimum_filter(target, size=3)
            farthest = maximum_filter(target, size=3)
            flat = (nearest[y, x] > 0) & (farthest[y, x] - nearest[y, x] < 0.05)
            z = (xyz - poses[j, :3, 3]) @ poses[j, :3, 2]
            valid = inside & flat & (z > 0)
            delta = np.abs(z[valid] - target[y[valid], x[valid]])
            color = np.abs(
                rgb[i, sy[valid], sx[valid]] - rgb[j, y[valid], x[valid]]
            ).mean(axis=1)
            agree = delta <= 0.05
            records.append(
                {
                    "source": i,
                    "target": j,
                    "rays": int(valid.sum()),
                    "within_5cm": float(agree.mean()),
                    "joint": float(np.mean(agree & (color <= 25.5))),
                    "color_given_depth": float((color[agree] <= 25.5).mean()),
                }
            )
    return {
        "sample": "directed overlap, positive locally smooth target depth",
        "pairs": records,
        "mean_depth_5cm": float(np.mean([q["within_5cm"] for q in records])),
        "mean_joint": float(np.mean([q["joint"] for q in records])),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(audit(), indent=2))
