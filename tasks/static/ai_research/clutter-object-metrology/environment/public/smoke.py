"""Exercise the public submission interface and identify the exact source tested."""

import hashlib
import json
from pathlib import Path

import numpy as np
import submission

if Path("calibration.npz").is_file():
    with np.load("calibration.npz") as calibration:
        original = [calibration[k].copy() for k in ("W", "b", "v", "x", "tags")]
    w, b = map(np.asarray, submission.edit(*(v.copy() for v in original)))
    assert w.shape == original[0].shape and b.shape == original[1].shape
    assert np.isfinite(w).all() and np.isfinite(b).all()
    changed = np.any(w != original[0], axis=-1) | (b != original[1])
    assert changed.sum() <= 1, "Only one hidden unit can change."
    details = {"edited_rows": np.argwhere(changed).tolist()}
else:
    v, f, c, face_ids = map(np.asarray, submission.scene())
    assert v.ndim == 2 and v.shape[1] == 3 and c.shape == v.shape
    assert (
        np.isfinite(v).all() and np.isfinite(c).all() and 0 <= c.min() <= c.max() <= 255
    )
    assert f.ndim == 2 and f.shape[1] == 3 and 0 < len(f) <= 20000
    assert np.issubdtype(f.dtype, np.integer) and f.min() >= 0 and f.max() < len(v)
    assert face_ids.shape == (len(f),) and np.issubdtype(face_ids.dtype, np.integer)
    assert face_ids.min() >= 0 and face_ids.max() <= 3
    details = {
        "vertices": len(v),
        "triangles": len(f),
        "label_counts": np.bincount(face_ids.astype(int), minlength=4).tolist(),
    }
print(
    "SMOKE_PASS",
    hashlib.sha256(Path("submission.py").read_bytes()).hexdigest(),
    json.dumps(details),
)

Path("test_receipt.json").write_text(
    json.dumps(
        {
            "source_sha256": hashlib.sha256(
                Path("submission.py").read_bytes()
            ).hexdigest(),
            "details": details,
        }
    )
)
