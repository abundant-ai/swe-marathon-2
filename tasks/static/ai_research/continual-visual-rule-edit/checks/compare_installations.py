"""Compare the deployed values of two verifier-produced scanner installations."""

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

import numpy as np

SITES = (17, 23, 42, 58, 71, 86)
FIELDS = ("part", "lot", "audit")
SHAPES = {
    "W": (2, 28, 48),
    "b": (2, 28),
    "heads": (2, 4, 28),
    "bridge": (28, 28),
    "pace": (2, 2, 28),
}


def load_installation(path: Path) -> dict[str, np.ndarray]:
    """Read finite parameters from an already verified six-site artifact."""
    with np.load(path, allow_pickle=False) as archive:
        values = {
            f"{kind}{bank}": archive[f"{kind}{bank}"]
            for bank in range(len(SITES) * len(FIELDS))
            for kind in SHAPES
        }
        if set(values) != set(archive.files) or len(archive.files) != len(values):
            raise ValueError(f"Unexpected archive members in {path}")
    for bank in range(len(SITES) * len(FIELDS)):
        for kind, shape in SHAPES.items():
            value = values[f"{kind}{bank}"]
            if (
                value.shape != shape
                or value.dtype.kind != "f"
                or not np.isfinite(value).all()
            ):
                raise ValueError(f"Invalid {kind} at bank {bank} in {path}")
    return values


def difference(first: dict, second: dict) -> dict:
    """Count unequal values in corresponding physical arrays, including learning rates."""
    totals = dict.fromkeys(SHAPES, 0)
    sites = []
    checkpoint_banks = rate_banks = rates_only = changed_rows = 0
    for index, site in enumerate(SITES):
        fields = {}
        for field, name in enumerate(FIELDS):
            bank = index * len(FIELDS) + field
            changed = {
                kind: first[f"{kind}{bank}"] != second[f"{kind}{bank}"]
                for kind in SHAPES
            }
            counts = {kind: int(a.sum()) for kind, a in changed.items()}
            incoming = np.argwhere(changed["W"].any(axis=2) | changed["b"])
            checkpoint = any(counts[kind] for kind in ("W", "b", "heads", "bridge"))
            rate = counts["pace"] > 0
            checkpoint_banks += checkpoint
            rate_banks += rate
            rates_only += rate and not checkpoint
            changed_rows += len(incoming)
            for kind, count in counts.items():
                totals[kind] += count
            if checkpoint or rate:
                fields[name] = {
                    "unequal_values": counts,
                    "different_incoming_stage_rows": incoming.tolist(),
                }
        sites.append({"site": site, "different_fields": fields})
    return {
        "identical_numeric_installation": not any(totals.values()),
        "banks_with_checkpoint_differences": checkpoint_banks,
        "banks_with_rate_differences": rate_banks,
        "banks_differing_only_in_rates": rates_only,
        "different_incoming_rows": changed_rows,
        "unequal_values": totals,
        "sites": sites,
    }


def compare(paths: list[Path]) -> dict:
    """Compare all pairs independently of ZIP metadata or source-code formatting."""
    artifacts = [load_installation(path) for path in paths]
    files = [
        {"filename": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in paths
    ]
    return {
        "files": files,
        "comparison": "Exact numeric inequality across eighteen physical banks",
        "pairs": [
            {"first": a, "second": b, **difference(artifacts[a], artifacts[b])}
            for a, b in combinations(range(len(paths)), 2)
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path, nargs="+")
    args = parser.parse_args()
    if len(args.artifacts) < 2:
        parser.error("Pass at least two verified numerical installations")
    print(json.dumps(compare(args.artifacts), indent=2))
