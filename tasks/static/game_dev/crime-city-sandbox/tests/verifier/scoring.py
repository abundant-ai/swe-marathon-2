"""Reward arithmetic (notes/PHASE1-PLAN.md, section 1). Pure functions, no I/O.

    reward = G_static * G_import * G_boot * sum_f(w_f * S_f) / sum_f(w_f)
    S_f    = (1 / N_f) * sum_i s_i            N_f fixed by the release manifest
    s_i    = 0 when a standing check or a precondition fails (crash, hang, telemetry
             tampering, broken registry or events), else
             sum_j(w_ij * pass_ij) / sum_j(w_ij) over the instance's assertions

Instances that never ran (deadline, missing file) count as 0 within their family's
fixed N_f, so a slow or broken game cannot shrink a denominator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Check:
    """One expectation outcome as scoring sees it.

    Attributes:
        id: Expectation id.
        kind: "assert", "pre" or "standing".
        w: Weight (asserts only).
        ok: True when it held; False or None (could not be judged) count as failed.
    """

    id: str
    kind: str
    w: float
    ok: bool | None


@dataclass
class InstanceResult:
    """The graded result of one instance.

    Attributes:
        name: Play name.
        family: Family letter from the manifest.
        score: s_i in [0, 1].
        failure: Why the instance was zeroed or not run ("standing:process",
            "pre:<id>", "not_run:deadline", "not_run:missing", "kit_exception"), or None.
        checks: The outcomes (as dicts) behind the score.
        attempts: How many times the instance ran (2 after a retry).
        wall_s: Wall seconds spent on the instance.
        detail: Extra diagnostics (errors, exit codes).
    """

    name: str
    family: str
    score: float
    failure: str | None
    checks: list[dict] = field(default_factory=list)
    attempts: int = 1
    wall_s: float = 0.0
    detail: dict = field(default_factory=dict)


def instance_score(checks: list[Check]) -> tuple[float, str | None]:
    """s_i from an instance's standing checks, preconditions and assertions.

    Args:
        checks: Every outcome of the instance.

    Returns:
        (score, failure): failure names the first standing check or precondition that
        zeroed the instance, "no_assertions" when there is nothing to score, else None.
    """
    for c in checks:
        if c.kind == "standing" and c.ok is not True:
            return 0.0, f"standing:{c.id}"
    for c in checks:
        if c.kind == "pre" and c.ok is not True:
            return 0.0, f"pre:{c.id}"
    asserts = [c for c in checks if c.kind == "assert"]
    total = sum(max(0.0, c.w) for c in asserts)
    if total <= 0:
        return 0.0, "no_assertions"
    return sum(max(0.0, c.w) for c in asserts if c.ok is True) / total, None


def family_scores(
    results: list[InstanceResult], families: dict[str, dict]
) -> dict[str, float]:
    """S_f for every family of the manifest.

    Args:
        results: Graded instances (any family not in the manifest is ignored).
        families: {family: {"w": weight, "n": fixed instance count}} from the manifest.

    Returns:
        {family: S_f}; a family with no results scores 0.

    Raises:
        ValueError: A family declares n < 1, or has more results than its n.
    """
    out = {}
    for fam, spec in families.items():
        n = int(spec["n"])
        if n < 1:
            raise ValueError(f"family {fam} has n={n}")
        scores = [r.score for r in results if r.family == fam]
        if len(scores) > n:
            raise ValueError(f"family {fam} has {len(scores)} results for n={n}")
        out[fam] = sum(scores) / n
    return out


def total_reward(
    gates: dict[str, bool], families: dict[str, dict], scores: dict[str, float]
) -> float:
    """The reward: gates times the weighted family scores (weights normalised).

    Args:
        gates: {gate name: passed}.
        families: The manifest's families ({"w", "n"}).
        scores: S_f per family (family_scores).

    Returns:
        The reward in [0, 1], rounded to 6 decimals; 0 when any gate failed.
    """
    if not all(gates.values()):
        return 0.0
    wsum = sum(float(f["w"]) for f in families.values())
    if wsum <= 0:
        return 0.0
    value = sum(float(families[f]["w"]) * scores.get(f, 0.0) for f in families) / wsum
    return round(min(1.0, max(0.0, value)), 6)


def retry_budget(n_instances: int, fraction: float = 0.15) -> int:
    """How many instances may be rerun (physics-sensitive ones scoring below 1)."""
    return math.floor(n_instances * fraction)


def integration_gap(scores: dict[str, float]) -> float | None:
    """mean(S_A, S_B, S_H, S_I) - mean(S_E, S_F, S_L, S_M) (plan, section 8).

    Returns:
        The gap, or None when the manifest lacks one of the eight families.
    """
    found = ("A", "B", "H", "I")
    integ = ("E", "F", "L", "M")
    if not all(f in scores for f in found + integ):
        return None
    return sum(scores[f] for f in found) / 4 - sum(scores[f] for f in integ) / 4
