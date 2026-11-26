"""Build the complete reconstruction, check public resource limits, and record its source digest."""

import hashlib
import io
import json
from pathlib import Path

import numpy as np


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(values, names):
    """Check geometry, labels, and the actual uncompressed numerical archive size."""
    require(
        isinstance(values, (tuple, list)) and len(values) == len(names),
        f"Return {names}",
    )
    arrays = dict(zip(names, map(np.asarray, values)))
    for name, array in arrays.items():
        kinds = "iu" if name in ("faces", "part_ids", "face_ids") else "iuf"
        require(
            array.dtype.kind in kinds and array.dtype.itemsize <= 8,
            f"Invalid dtype for {name}",
        )
    v, f, c, objects, parts = (arrays[name] for name in names[:5])
    require(
        v.ndim == 2 and v.shape[1] == 3 and 0 < len(v) <= 60000,
        "Invalid vertex dimensions",
    )
    require(
        c.shape == v.shape and np.isfinite(c).all() and 0 <= c.min() <= c.max() <= 255,
        "Invalid sRGB colors",
    )
    require(
        np.isfinite(v).all() and np.max(np.abs(v.astype(float))) <= 10000,
        "Invalid coordinates",
    )
    require(
        f.ndim == 2 and f.shape[1] == 3 and 0 < len(f) <= 20000,
        "Invalid triangle dimensions",
    )
    require(0 <= f.min() and f.max() < len(v), "Invalid vertex index")
    for labels, maximum in ((objects, 3), (parts, 4)):
        require(
            labels.shape == (len(f),) and 0 <= labels.min() <= labels.max() <= maximum,
            "Invalid labels",
        )
    wrong_object = (
        ((parts >= 1) & (parts <= 2) & (objects != 1))
        | ((parts == 3) & (objects != 2))
        | ((parts == 4) & (objects != 3))
    )
    require(not np.any(wrong_object), "A named part belongs to the wrong object")
    details = {
        "vertices": len(v),
        "triangles": len(f),
        "part_counts": np.bincount(parts.astype(int), minlength=5).tolist(),
    }
    require(
        sum(a.nbytes for a in arrays.values()) <= 5 * 1024**2,
        "Numerical data exceed 5 MiB",
    )
    disk = io.BytesIO()
    np.savez(disk, **arrays)
    size = disk.tell()
    require(size <= 5 * 1024**2, "Uncompressed numerical archive exceeds 5 MiB")
    details["numeric_archive_bytes"] = size
    return details


def check_fresh():
    import resource
    import sys

    sys.path = [
        str(Path.cwd()),
        *(entry for entry in sys.path if entry not in ("", "/checks")),
    ]
    for k, soft, hard in (
        (resource.RLIMIT_CPU, 600, 610),
        (resource.RLIMIT_AS, 3 * 1024**3, 3 * 1024**3),
        (resource.RLIMIT_FSIZE, 64 * 1024**2, 64 * 1024**2),
        (resource.RLIMIT_NOFILE, 128, 128),
    ):
        resource.setrlimit(k, (soft, hard))
    receipt = Path("/output/receipt.json")
    source = Path("submission.py").read_bytes()
    require(len(source) <= 2 * 1024**2, "Source exceeds 2 MiB")
    import submission

    names = ("vertices", "faces", "colors", "face_ids", "part_ids")
    details = check(submission.scene(), names)
    digest = hashlib.sha256(source).hexdigest()
    receipt.write_text(json.dumps({"source_sha256": digest, "details": details}))


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--clean-child"]:
        check_fresh()
    else:
        from clean_rebuild import run_clean

        work = Path(__file__).resolve().parent
        inputs = json.loads((work / "public-inputs.json").read_text())
        run_clean(work, inputs)
