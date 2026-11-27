"""Measure whether a cursor aimed from a fitted mesh lands on the named visible control."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt, find_objects, label

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "tests/private/functional-parts"))
from score import Reference, mask, native_labels


def aim(visible: np.ndarray) -> tuple[int, int] | None:
    """Pick the most interior pixel of the largest predicted visible patch.

    The distance is measured to the patch boundary. When several pixels tie,
    choose the one nearest the patch's centroid, then the first in raster order.
    The policy only uses the projected reconstruction.
    """
    regions, count = label(visible)
    if count == 0:
        return None
    index = np.bincount(regions.ravel())[1:].argmax() + 1
    crop = find_objects(regions, max_label=index)[index - 1]
    patch = regions[crop] == index
    distances = distance_transform_edt(np.pad(patch, 1))[1:-1, 1:-1]
    candidates = np.argwhere(distances == distances.max())
    centroid = np.argwhere(patch).mean(0)
    pos = candidates[np.square(candidates - centroid).sum(1).argmin()]
    return (int(pos[0] + crop[0].start), int(pos[1] + crop[1].start))


def evaluate(artifact: Path, poses: np.ndarray) -> dict:
    """Score the same predeclared 38 part-view pairs, counting invisible predictions as misses."""
    with np.load(artifact, allow_pickle=False) as data:
        mesh = tuple(
            data[k] for k in ("vertices", "faces", "colors", "face_ids", "part_ids")
        )
    cases = []
    for i, projected in enumerate(native_labels(mesh, poses)):
        outlines = json.loads(
            (TASK / f"tests/private/functional-parts/held-{i}.json").read_text()
        )
        for name, rings in outlines.items():
            target = mask(rings)
            point = aim(projected == int(name))
            cases.append(
                {
                    "view": i,
                    "part": int(name),
                    "pixel_yx": point,
                    "hit": bool(point is not None and target[point]),
                    "interior_hit": bool(
                        point is not None and binary_erosion(target)[point]
                    ),
                }
            )
    if len(cases) != 38:
        raise ValueError("Expected all 38 annotated control-view pairs")
    return {
        "mesh_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "pairs": len(cases),
        "hits": sum(c["hit"] for c in cases),
        "interior_hits": sum(c["interior_hit"] for c in cases),
        "no_prediction": sum(c["pixel_yx"] is None for c in cases),
        "cases": cases,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "experiment",
        type=Path,
        help="Three condition folders containing scored trial meshes",
    )
    p.add_argument("output", type=Path)
    args = p.parse_args()
    reference = Reference.load(
        TASK / "tests/private/precision-pilot/data/clutter/data", "a"
    )
    results = {}
    for artifact in sorted(args.experiment.glob("*/*/artifact.npz")):
        key = artifact.parent.relative_to(args.experiment).as_posix()
        results[key] = evaluate(artifact, reference.poses)
        print(key, results[key]["hits"], results[key]["interior_hits"], flush=True)
    args.output.write_text(
        json.dumps(
            {
                "hover_policy": "largest patch, maximum distance to its edge",
                "unit": "held-out annotated part-view pair",
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
