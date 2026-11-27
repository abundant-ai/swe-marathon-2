"""Replay the stock scorer on completed measurements and on one deliberately failed arrival probe."""

import argparse
import copy
import json
import os
import sys
from pathlib import Path


def check(release: Path, metrics: Path) -> dict:
    """Check the reference report and verify that a loss at arrival invalidates deployment credit."""
    sys.path.insert(0, str(release / "tests"))
    os.environ["PILOT_PUBLIC"] = str(release / "tests/public")
    from verify import deployment_credit

    report = json.loads(metrics.read_text())
    results = report["runs"]
    counts = [
        run["first_appearance_count"]
        for start in results.values()
        for run in start["a"]
    ]
    if set(counts) != {30}:
        raise ValueError(
            f"Each three-station schedule must have exactly thirty first sightings: {counts}"
        )
    original, _ = deployment_credit(results, transfer=True)
    negative = copy.deepcopy(results)
    for result in negative.values():
        for run in result["a"]:
            run["blocks"][0]["probe"]["adapted"] = 0.02
            run["blocks"][0]["probe"]["frozen"] = 0.10
    damaged, details = deployment_credit(negative, transfer=True)
    for row in details.values():
        if abs(row["components"]["arrival_objects"] + 0.08) > 1e-10:
            raise ValueError("Arrival probe regression was hidden")
    if original != report["reward"] or damaged != 0:
        raise ValueError("Unexpected deployment score")
    lost_order = copy.deepcopy(results)
    for worlds in lost_order.values():
        for run in worlds["a"]:
            if run["order"] == 7303:
                run["adapted"] = max(0.0, run["frozen"] - 0.10)
    masked, _ = deployment_credit(lost_order, transfer=True)
    if masked != 0:
        raise ValueError("A regression on the reversed visit order was hidden")
    return dict(
        reversed_order_regression=masked,
        reference=original,
        missing_arrival_gain=damaged,
        first_observations_per_run=counts,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("metrics", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.release.resolve(), args.metrics), indent=2))
