"""Install all three staging scanners and characterize their public gallery numerically."""

import hashlib
import json
from pathlib import Path

import numpy as np
from contract import validate, validate_station
from worker import install


def activations(weights, bias, coupling, x):
    early = np.maximum(x[:, 0] @ weights[0].T + bias[0], 0.0)
    late = np.maximum(x[:, 1] @ weights[1].T + bias[1] + early @ coupling.T, 0.0)
    return np.stack([early, late], 1)


with np.load("calibration.npz") as data:
    banks = zip(*(data[k] for k in ("W", "b", "v", "x", "tags", "bridge")))
    details = []
    budgets = []
    for w, b, h, x, t, j in banks:
        new, bias, archive, bridge, rates = install(w, b, h, x, t, j)
        budgets.append(validate(w, b, h, j, new, bias, archive, bridge))
        old = np.einsum("nbh,bch->nc", activations(w, b, j, x), h)
        features = activations(new, bias, bridge, x)
        after = np.einsum("nbh,bch->nc", features, archive)
        known = t[:, 64] != 255
        a = features[known].reshape(known.sum(), -1)
        labels = t[known, 64:66]
        distances = np.mean((a[:, None] - a[None]) ** 2, axis=2)
        np.fill_diagonal(distances, np.inf)
        details.append(
            {
                "station": int(t[0, 66]),
                "field": int(t[0, 69]),
                "verified": int(known.sum()),
                "edited_rows": np.argwhere((w != new).any(-1) | (b != bias)).tolist(),
                "mean_shift_rate": rates.mean((1, 2)).tolist(),
                "neighbor_glyph_pose": (labels[distances.argmin(1)] == labels)
                .mean(0)
                .tolist(),
                "normalized_old_drift": (
                    np.sqrt(((old - after) ** 2).mean(0)) / old.std(0).clip(0.05, None)
                ).tolist(),
            }
        )
    validate_station(budgets)

sha = hashlib.sha256(Path("submission.py").read_bytes()).hexdigest()
Path("test_receipt.json").write_text(
    json.dumps({"source_sha256": sha, "details": details})
)
print("SMOKE_PASS", sha, json.dumps(details))
