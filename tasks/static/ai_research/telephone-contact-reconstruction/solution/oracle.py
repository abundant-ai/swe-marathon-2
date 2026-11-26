"""Export the prefit two-view control and reconstruct its visible vertex colors from public RGB."""

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation

FIELDS = ("vertices", "faces", "colors", "face_ids", "part_ids")


@dataclass(frozen=True)
class OracleContext:
    """The fitted RGB-only geometry and the candidate-accessible working directory."""

    reference: Path
    workdir: Path


def public_samples(vertices, track, image, key):
    """Project scene vertices to the corresponding native RGB sheet frame."""
    pose = track[key]
    camera = (vertices - pose[:3]) @ Rotation.from_quat(pose[3:]).as_matrix()
    safe_depth = np.maximum(camera[:, 2], 0.001)
    x, y = (camera[:, :2] / safe_depth[:, None]).T
    r2 = x * x + y * y
    radial = 1.0 + r2 * (0.2312 + r2 * (-0.7849 + r2 * 0.9172))
    dx = 2 * -0.0033 * x * y - 0.0001 * (r2 + 2 * x * x)
    dy = -0.0033 * (r2 + 2 * y * y) + 2 * -0.0001 * x * y
    u = np.rint(520.9 * (x * radial + dx) + 325.1)
    v = np.rint(521.0 * (y * radial + dy) + 249.7)
    visible = (camera[:, 2] > 0.1) & (u >= 0) & (u < 640) & (v >= 0) & (v < 480)
    index = np.zeros(len(vertices), dtype=np.int32)
    index[visible] = (
        (v[visible].astype(int) + 502 * (key // 2)) * image.shape[1]
        + u[visible].astype(int)
        + 640 * (key % 2)
    )
    return visible, index, image.reshape(-1, 3)[index].astype(float)


def oracle(context: OracleContext) -> None:
    """Export fitted geometry and a compact map from visible vertices to color observations."""
    with np.load(context.reference, allow_pickle=False) as archive:
        arrays = {k: archive[k] for k in FIELDS}
    with Image.open(context.workdir / "observation.png") as sheet:
        rgb = np.asarray(sheet.convert("RGB"))
    track = np.loadtxt(context.workdir / "b-keyframes.txt")
    samples = [public_samples(arrays["vertices"], track, rgb, k) for k in (1, 4)]
    colors = arrays["colors"].astype(float)
    both = samples[0][0] & samples[1][0]
    average = (samples[0][2] + samples[1][2]) / 2
    shared = both & np.all(colors == average, axis=1)
    one = [(ok & np.all(colors == values, axis=1)) for ok, _, values in samples]
    linked = one[0] | one[1] | shared
    if linked.sum() < 100:
        raise ValueError(
            "Too few fitted vertex colors recoverable from the public keyframes"
        )
    pairs = np.zeros((len(colors), 2), dtype=np.int32)
    for selected, (_, pixel, _) in zip(one, samples, strict=True):
        pairs[selected] = pixel[selected, None]
    pairs[shared] = np.column_stack([sample[1][shared] for sample in samples])
    visible, dense_sheet_pixels, dense_values = public_samples(
        arrays["vertices"], track, rgb, 0
    )
    from_dense = visible & np.all(colors == dense_values, axis=1)
    if not from_dense.any():
        raise ValueError("No fitted vertex colors recoverable in the dense endpoint")
    # Dense PNG 0072 is the same exposure as the first frame on the public sheet.
    dense_pixels = (
        dense_sheet_pixels // rgb.shape[1]
    ) * 640 + dense_sheet_pixels % rgb.shape[1]
    arrays["colors"][linked | from_dense] = 0
    data = io.BytesIO()
    np.savez_compressed(
        data,
        **arrays,
        recovered=np.flatnonzero(linked),
        sample_pixels=pairs[linked],
        dense_vertices=np.flatnonzero(from_dense),
        dense_pixels=dense_pixels[from_dense],
    )
    encoded = base64.b64encode(data.getvalue()).decode("ascii")
    code = '''"""Telephone desk geometry fitted to calibrated public RGB images."""

import base64
import io
import tempfile
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from PIL import Image

FIELDS = ("vertices", "faces", "colors", "face_ids", "part_ids")


def scene():
    with np.load(io.BytesIO(base64.b64decode(PAYLOAD)), allow_pickle=False) as data:
        arrays = {name: data[name] for name in FIELDS}
        recovered = data["recovered"]
        pixel = data["sample_pixels"]
        dense_vertices = data["dense_vertices"]
        dense_pixels = data["dense_pixels"]
    with Image.open(Path("/app/work/observation.png")) as image:
        rgb = np.asarray(image.convert("RGB")).reshape(-1, 3)
    arrays["colors"][recovered] = rgb[pixel].mean(axis=1)
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as scratch:
        with ZipFile(Path(__file__).with_name("frames.zip")) as archive:
            image_path = archive.extract("0072.png", scratch)
        with Image.open(image_path) as endpoint:
            pixels = np.asarray(endpoint.convert("RGB")).reshape(-1, 3)
        arrays["colors"][dense_vertices] = pixels[dense_pixels]
    return tuple(arrays[name] for name in FIELDS)
'''
    (context.workdir / "submission.py").write_text(
        code + "\nPAYLOAD = " + repr(encoded) + "\n"
    )
    print(
        f"Reconstructing {linked.sum()} vertex colors from the keyframes and {from_dense.sum()} from the dense endpoint"
    )


if __name__ == "__main__":
    oracle(OracleContext(Path("/solution/reference.npz"), Path("/app/work")))
