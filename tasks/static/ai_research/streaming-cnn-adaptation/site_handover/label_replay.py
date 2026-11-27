"""Measure whether a clean trainer learns a visually conditioned change of source vocabulary."""

import tempfile
from pathlib import Path

import numpy as np
from core_model import load
from test_stream import predict
from training_replay import rebuilt_checkpoint


def capture(rgb: np.ndarray, sensor: int) -> np.ndarray:
    """Render two gain settings with opposite color casts on a native source capture."""
    gains = ([1.0, 0.8, 0.42], [0.42, 0.8, 1.0])[sensor]
    return np.rint(rgb * np.asarray(gains)).astype(np.uint8)


def measure(trainer, source, public, probe, labels, seed, validate):
    """Grade the same reserved capture under two sensors with conflicting category IDs."""
    rng = np.random.default_rng(seed)
    first = rng.permutation(10)
    other = first[np.roll(np.arange(10), int(rng.integers(1, 10)))]
    with tempfile.TemporaryDirectory(prefix="core50-source-intervention-") as temp:
        path = Path(temp) / "source.npz"
        with np.load(source, allow_pickle=False) as archive:
            arrays = dict(archive)
        index = rng.permutation(len(arrays["y"]))
        for sensor, indices in enumerate(np.array_split(index, 2)):
            arrays["x"][indices] = capture(arrays["x"][indices], sensor)
            arrays["y"][indices] = (first, other)[sensor][arrays["y"][indices]]
        np.savez(path, **arrays)
        with rebuilt_checkpoint(trainer, path, public) as result:
            validate(result)
            net = load(result)
            p, q = (predict(net, capture(probe, s)) for s in (0, 1))
    correct = (p == first[labels]) & (q == other[labels])
    return float(np.mean([correct[labels == k].mean() for k in np.unique(labels)]))
