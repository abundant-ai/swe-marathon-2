"""Attribute missing room coverage to empty rays, misplaced surfaces and appearance."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PRIVATE = Path(__file__).resolve().parents[1] / "tests/private"
sys.path.insert(0, str(PRIVATE / "dense-telephone-parts"))
from telephone_score import ROOT, Reference, appearance, native_surfaces


def budget(path):
    with np.load(path, allow_pickle=False) as archive:
        mesh = tuple(
            archive[key] for key in ("vertices", "faces", "colors", "face_ids")
        )
    reference = Reference.load(PRIVATE / "precision-pilot/data/clutter/data", "b")
    with np.load(ROOT / "optical-poses.npz") as archive:
        poses = archive["poses"]
    with np.load(ROOT / "scoring-rgb.npz") as archive:
        colors = archive["rgb"]
    rows = []
    for k, (camera, distances, faces) in enumerate(native_surfaces(mesh, poses)):
        depth, face = distances[2::4, 2::4], faces[2::4, 2::4]
        sensor = reference.depth[k]
        known = sensor > 0
        rendered = face >= 0
        error = depth - sensor
        for group, selected in (
            ("all", known),
            ("background", known & (reference.labels[k] == 0)),
            ("objects", known & (reference.labels[k] != 0)),
        ):
            measure = appearance(
                mesh, camera, depth, face, colors[k], np.where(selected, sensor, 0)
            )
            joint = measure["rgbd_5cm_10percent_coverage"]
            misses = {
                "no_triangle": (~rendered)[selected].mean(),
                "surface_too_near": (rendered & (error < -0.05))[selected].mean(),
                "surface_too_far": (rendered & (error > 0.05))[selected].mean(),
                "depth_correct_color_wrong": measure["depth_5cm_coverage"] - joint,
                "depth_and_color_correct": joint,
            }
            if not np.isclose(sum(misses.values()), 1):
                raise ValueError("Fractions must account for every measured ray")
            rows.append(dict(view=k, group=group, rays=int(selected.sum()), **misses))
    return {
        "views": rows,
        "macro": {
            group: {
                key: float(np.mean([row[key] for row in rows if row["group"] == group]))
                for key in misses
            }
            for group in ("all", "background", "objects")
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    print(json.dumps(budget(parser.parse_args().mesh), indent=2))
