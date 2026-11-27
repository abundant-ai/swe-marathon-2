"""Recompute deployment credit and test boundaries against a complete trusted matched replay."""

import argparse
import copy
import json
import os
import sys
from pathlib import Path

import numpy as np


def check(package: Path, replay: Path) -> dict:
    """Verify accepted, missing-installation, chart-insensitive, partial and buffer-only behaviors."""
    public = package / "tests/public"
    os.environ["PILOT_PUBLIC"] = str(public)
    sys.path[:0] = [str(package / "tests"), str(public)]
    from verify import deployment_credit

    native = json.loads(replay.read_text())["runs"]

    def credit(runs: dict) -> float:
        return deployment_credit(runs, transfer=True)[0]

    matched = credit(native)
    assert matched == 1.0

    blinded = copy.deepcopy(native)
    for start in blinded.values():
        for a, b in zip(start["a"], start["b"], strict=True):
            b["stock_predictions"] = list(a["stock_predictions"])
    assert credit(blinded) == 0.0

    partial = copy.deepcopy(native)
    for start in partial.values():
        for a, b in zip(start["a"], start["b"], strict=True):
            y, z = np.asarray(a["stock_targets"]), np.asarray(b["stock_targets"])
            # Two correct predictions on roughly every fifth frame of every ID.
            pred = y.copy()
            for label in np.unique(y):
                hits = np.flatnonzero((y == label) & (y != z))
                pred[hits[::5]] = z[hits[::5]]
            a["stock_predictions"] = y.tolist()
            b["stock_predictions"] = pred.tolist()
    interior = credit(partial)
    assert 0.0 < interior < 1.0

    failed = copy.deepcopy(native)
    failed["replicate"]["b"][0] = {"error": "missing state"}
    assert credit(failed) == 0.0
    buffers = copy.deepcopy(native)
    buffers["submitted"]["a"][0]["learned_weight_gain_pp"] = 0.0
    assert credit(buffers) == 0.0
    return {
        "matched": matched,
        "copied_across_commissionings": 0.0,
        "partial": interior,
        "missing_second_deployment": 0.0,
        "submitted_buffers_only": 0.0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("matched_replay", type=Path)
    data = parser.parse_args()
    print(json.dumps(check(data.package, data.matched_replay), indent=2))
