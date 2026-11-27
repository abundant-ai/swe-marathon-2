"""Report which physical scanner received the incoming rows renewed by a submitted editor."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "solution"))
from read_handover import read


def describe(measured: dict, image: Path, calibration: Path) -> dict:
    """Map actual changed weight addresses to roles inferred independently from a given sheet."""
    with np.load(calibration, allow_pickle=False) as data:
        tags = data["tags"][0]
    roles, _, _ = read(image, tags[tags[:, 67] == 0])
    sources = measured["rows"]
    if len(sources) != 6 or any(len(fields) != 3 for fields in sources):
        raise ValueError(
            "Expected six measured sites with three physical banks per site"
        )
    totals = {"product": 0, "registration": 0, "other": 0}
    sites = []
    for station, (product, register), fields in zip(
        (17, 23, 42, 58, 71, 86), roles, sources, strict=True
    ):
        names = ["other"] * 3
        names[product] = "product"
        names[register] = "registration"
        row_counts = {
            name: len(changed) for name, changed in zip(names, fields, strict=True)
        }
        for name, count in row_counts.items():
            totals[name] += count
        opened = [i for i, addresses in enumerate(fields) if addresses]
        exact_pair = set(opened) == {product, register}
        sites.append(
            {
                "station": station,
                "product_bank": int(product),
                "registration_bank": int(register),
                "rows": row_counts,
                "renewed_banks": opened,
                "exact_pair": exact_pair,
            }
        )
    return {
        "total": totals,
        "exact_pairs": sum(site["exact_pair"] for site in sites),
        "sites": sites,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "metrics",
        type=Path,
        help="The verifier's metrics.json with measured installations",
    )
    parser.add_argument(
        "image", type=Path, help="The handover whose physical roles are being tested"
    )
    parser.add_argument(
        "calibration", type=Path, help="The released commissioning gallery"
    )
    args = parser.parse_args()
    report = json.loads(args.metrics.read_text())
    if report["build"] != "valid":
        parser.error("A valid measured rebuild is required")
    print(
        json.dumps(describe(report["measured"], args.image, args.calibration), indent=2)
    )
