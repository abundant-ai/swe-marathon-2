"""Measure nearest visible contact hits using independent calibrated RGB-D observations."""

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion

PARENTS = {1: 1, 2: 1, 3: 2, 4: 3}
EXPECTED_SUPPORT = {1: 190, 2: 106, 3: 8, 4: 96}
SCORED_CONTACTS = (1, 2, 4)


def count_queries(part_id, outline, labels, depth, sensor, parent_labels):
    # RGB-D samples lie at these native optical pixel centers.
    inside = binary_erosion(outline)[2::4, 2::4]
    outside = ~binary_dilation(outline)[2::4, 2::4]
    known = sensor > 0
    positive = inside & known & (parent_labels == PARENTS[part_id])
    proposed = (labels == part_id) & known
    hit = positive & proposed & (np.abs(depth - sensor) <= 0.03)
    # Ignore unmeasured depth, ambiguous contour pixels and inconsistent annotations.
    incorrect = proposed & (outside | (positive & ~hit))
    return np.array([positive.sum(), hit.sum(), incorrect.sum()], dtype=np.int64)


def summarize_counts(views):
    by_part = {}
    for part_id, support in EXPECTED_SUPPORT.items():
        counts = [v[part_id] for v in views]
        n, hits, wrong = map(int, np.sum(counts, axis=0))
        if n != support:
            raise RuntimeError(f"Expected {support} registered contact samples for {part_id}, got {n}")
        by_part[part_id] = {
            "eligible": n, "correct": hits, "incorrect_picks": wrong,
            "f1": 2 * hits / (n + hits + wrong),
            "per_view": [list(map(int, row)) for row in counts],
        }
    return {
        "by_part": by_part,
        "macro_f1": float(np.mean([by_part[i]["f1"] for i in SCORED_CONTACTS])),
    }
