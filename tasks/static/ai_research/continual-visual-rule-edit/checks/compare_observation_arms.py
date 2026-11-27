"""Compare physical weight choices across separately authored, measured GPT programs."""

import argparse
import json
from itertools import combinations
from pathlib import Path


def describe(folder, cases):
    """Read the independently measured installation without executing its source."""
    report = json.loads((folder / "verifier__metrics.json").read_text())
    result = {
        "trial": folder.name,
        "build": report["build"],
        "reward": report.get("reward"),
        "source_sha256": report.get("source_sha256"),
        "test_receipt_matches": report.get("test_receipt_matches"),
    }
    if report["build"] != "valid":
        return result, None
    sites = report["measured"]["rows"]
    if len(sites) != 6 or any(len(banks) != 3 for banks in sites):
        raise ValueError(f"Incomplete bank coverage for {folder.name}")
    addresses = {
        (site, field, stage, index)
        for site, fields in enumerate(sites)
        for field, renewed in enumerate(fields)
        for stage, index in renewed
    }
    opened = [{field for field, rows in enumerate(fields) if rows} for fields in sites]
    result["renewed_rows"] = len(addresses)
    result["opened_banks_by_site"] = [sorted(banks) for banks in opened]
    result["sites_with_exact_required_pair"] = {
        arm: sum(
            actual == expected for actual, expected in zip(opened, targets, strict=True)
        )
        for arm, targets in cases.items()
    }
    result["diagnostic_target_rewards"] = report["target_rewards"]
    return result, addresses


def compare(cohort, evidence, design):
    """Enumerate every within- and between-condition pair of observed valid programs."""
    cases = {
        arm: [{site["product"], site["register"]} for site in plan["rules"]]
        for arm, plan in design["arms"].items()
    }
    trials = []
    measured = []
    for condition, ids in cohort.items():
        for trial in ids:
            result, addresses = describe(evidence / trial, cases)
            result["condition"] = condition
            trials.append(result)
            if addresses is not None:
                measured.append((result, addresses))
    pairs = []
    for (left, a), (right, b) in combinations(measured, 2):
        union = len(a | b)
        pairs.append(
            {
                "trials": [left["trial"], right["trial"]],
                "conditions": [left["condition"], right["condition"]],
                "common_addresses": len(a & b),
                "union_addresses": union,
                "jaccard": len(a & b) / union if union else None,
            }
        )
    return {"trials": trials, "address_comparisons": pairs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cohort",
        type=Path,
        help="JSON mapping observation conditions to trial directory names",
    )
    parser.add_argument(
        "evidence", type=Path, help="Directory containing the trial directories"
    )
    parser.add_argument(
        "--design", type=Path, default=Path(__file__).with_name("sheet-design.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        json.loads(args.cohort.read_text()),
        args.evidence,
        json.loads(args.design.read_text()),
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
