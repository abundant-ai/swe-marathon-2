"""Require correct stock IDs for the same visible inventory frames in both chart-selected rooms."""

import numpy as np


def per_site(labels: np.ndarray, different: np.ndarray, success: np.ndarray) -> float:
    """Average paired correctness by the local stock IDs with conflicting targets."""
    return float(
        np.mean(
            [
                success[different & (labels == k)].mean()
                for k in np.unique(labels[different])
            ]
        )
    )


def crossed_credit(results: dict, summary: dict) -> tuple[float, dict]:
    """Apply the paired-site requirement within each CNN and schedule to otherwise eligible submissions."""
    for tag, worlds in results.items():
        pairs = {}
        for schedule in ("clips", "switches"):
            rows = {
                row["order"]: row for row in worlds["a"] if row["schedule"] == schedule
            }
            left, right = rows[4201], rows[7303]
            y, z = np.asarray(left["stock_targets"]), np.asarray(right["stock_targets"])
            if len(y) != len(z) or y.ndim != 1:
                raise RuntimeError("Mismatched stockroom counterfactuals")
            different = y != z
            if different.mean() < 0.5:
                raise RuntimeError(
                    "Counterfactual stockroom assignments insufficiently distinct"
                )
            # Evaluate all objects whose site IDs conflict, weighting the represented stock IDs equally.
            success = (np.asarray(left["stock_predictions"]) == y) & (
                np.asarray(right["stock_predictions"]) == z
            )

            rate = min(per_site(y, different, success), per_site(z, different, success))
            pairs[schedule] = {
                "paired_correct": rate,
                "conflicting_frames": int(different.sum()),
                "credit": min(1.0, rate / 0.35),
            }
            summary[tag]["credit"] = min(
                summary[tag]["credit"], pairs[schedule]["credit"]
            )
        summary[tag]["same_frames_in_both_stockrooms"] = pairs
    return min(row["credit"] for row in summary.values()), summary


def commissioning_credit(results: dict, *, transfer: bool) -> tuple[float, dict]:
    """Score each complete installation, then test both answers for the same post-renewal stream."""
    from verify import single_installation_credit

    summary = {}
    for world in ("a", "b"):
        projected = {tag: {"a": visits[world]} for tag, visits in results.items()}
        _, info = single_installation_credit(projected, transfer=transfer)
        if "reason" in info:
            return 0.0, {"reason": f"Incomplete installation {world}"}
        summary.update({f"{world}_{tag}": value for tag, value in info.items()})
    for tag, visits in results.items():
        right = {(v["schedule"], v["order"]): v for v in visits["b"]}
        paired = {}
        for row in visits["a"]:
            key = row["schedule"], row["order"]
            other = right[key]
            y, z = (np.asarray(v["stock_targets"]) for v in (row, other))
            different = y != z
            if different.mean() < 0.5:
                raise RuntimeError("Insufficient changed targets after recommissioning")
            success = (np.asarray(row["stock_predictions"]) == y) & (
                np.asarray(other["stock_predictions"]) == z
            )
            rate = min(per_site(y, different, success), per_site(z, different, success))
            paired[f"{key[0]}-{key[1]}"] = float(rate)
        for world in ("a", "b"):
            record = summary[f"{world}_{tag}"]
            record["renewal_pair_accuracy"] = paired
            record["credit"] = min(record["credit"], min(paired.values()) / 0.35)
    return min(row["credit"] for row in summary.values()), summary
