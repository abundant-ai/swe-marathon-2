"""Family scores, pairs, the stub baseline and the weighted reward.

score = sum over families f of w_f * g_f / sum of w_f over the families the case set holds,
with g_f = max(0, (pass_f - b_f) / (1 - b_f)). A case that belongs to a pair counts only if
both members pass. Weights are fixed by documented importance. The case set is meant to hold
every family; while one is missing it is reported in the metrics and its weight is left out of
the denominator, so the reference still scores 1.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from .contracts import CaseResult

WEIGHTS: Mapping[str, float] = {
    "R": 0.20,
    "B-dedup": 0.17,
    "B-scope": 0.05,
    "K": 0.15,
    "V": 0.13,
    "V-msg": 0.05,
    "L": 0.10,
    "M": 0.05,
    "P": 0.05,
    "X": 0.03,
    "F": 0.02,
}


def family_pass_rates(results: list[CaseResult]) -> dict[str, dict[str, float]]:
    """Per family: units (single cases, or pairs), units passed, and the pass fraction."""
    units: dict[str, dict[str, bool]] = defaultdict(dict)
    for r in results:
        key = f"pair:{r.pair}" if r.pair else f"case:{r.case_id}"
        units[r.family][key] = units[r.family].get(key, True) and r.passed
    out: dict[str, dict[str, float]] = {}
    for family, members in units.items():
        total = len(members)
        passed = sum(1 for ok in members.values() if ok)
        out[family] = {
            "units": total,
            "passed": passed,
            "rate": passed / total if total else 0.0,
        }
    return out


def reward(
    rates: Mapping[str, Mapping[str, float]], baselines: Mapping[str, float]
) -> tuple[float, dict]:
    """Weighted reward over the families present, with each family's stub baseline netted out."""
    total = 0.0
    present_weight = 0.0
    detail: dict[str, dict[str, float]] = {}
    for family, weight in WEIGHTS.items():
        if family not in rates:
            detail[family] = {"weight": weight, "present": 0.0}
            continue
        b = baselines.get(family, 0.0)
        p = rates[family]["rate"]
        g = max(0.0, (p - b) / (1.0 - b)) if b < 1.0 else 0.0
        total += weight * g
        present_weight += weight
        detail[family] = {
            "weight": weight,
            "present": 1.0,
            "pass": p,
            "baseline": b,
            "g": g,
        }
    score = total / present_weight if present_weight else 0.0
    return round(score, 6), detail
