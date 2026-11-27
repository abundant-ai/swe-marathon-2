"""Check whether a clean training run follows the category labels supplied with its captures."""

import tempfile
from pathlib import Path

import numpy as np

from core_model import load
from test_stream import balanced, predict
from training_replay import rebuilt_checkpoint


def correspondence(seed):
    rng = np.random.default_rng(seed)
    classes = np.arange(10)
    while True:
        mapped = rng.permutation(classes)
        if np.all(mapped != classes):
            return mapped


def measure(trainer, source, public, probe, labels, seed, validate):
    assignment = correspondence(seed)
    with tempfile.TemporaryDirectory(prefix="core50-label-replay-") as temp:
        path = Path(temp) / "source.npz"
        with np.load(source, allow_pickle=False) as archive:
            arrays = dict(archive)
        arrays["y"] = assignment[arrays["y"]]
        np.savez(path, **arrays)
        with rebuilt_checkpoint(trainer, path, public) as result:
            validate(result)
            predicted = predict(load(result), probe)
    return balanced(predicted, assignment[labels])
