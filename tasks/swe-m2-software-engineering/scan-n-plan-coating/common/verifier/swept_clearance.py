"""Certify continuous clearance using independent distance and motion bounds."""

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import Literal

from trajectory import Segment, Vector

Clearance = Callable[[Vector], float]


@dataclass(frozen=True)
class ClearanceResult:
    """Continuous interval outcome and the underlying probe evidence."""

    status: Literal["clear", "violation", "unresolved"]
    minimum_sample_m: float
    samples: int
    fraction: float | None


def certify_clearance(
    segment: Segment, distance: Clearance, minimum_m: float, arm_radii_m: tuple[float, ...],
    rotating_radius_m: float, *, max_depth: int = 16,
) -> ClearanceResult:
    """Prove or falsify a segment's clearance, keeping uncertain cases explicit.

    Args:
        segment: Parsed interpolated motion for six arm joints and one fixture.
        distance: Independent signed separation query for all relevant pairs
            at the requested configuration. A positive clipped distance may be
            supplied if it is a lower bound on geometric separation.
        minimum_m: Required lower bound on continuous clearance, in metres.
        arm_radii_m: Six conservative lever-arm bounds that cover every point
            moved by each revolute joint. Bounds must come from trusted geometry.
        rotating_radius_m: Maximum radial distance, in metres, for a point on the
            rotating part or fixture about the calibrated positioner axis.
        max_depth: Maximum bisection depth before reporting unresolved.

    Returns:
        Clear only when the Lipschitz lower bound certifies every interval.
        Violation provides a witness sample below the margin. Unresolved
        means the finite calculation did not certify or disprove the bound.

    The caller establishes that the start lies outside closed obstacles and
    bounds any motion or scene changes not modeled by the seven joint axes.
    """
    if len(arm_radii_m) != 6 or not all(
        math.isfinite(value) and value >= 0 for value in (*arm_radii_m, rotating_radius_m, minimum_m)
    ):
        raise ValueError("Clearance margins and lever arms must be finite and nonnegative")
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError("Clearance depth must be a nonnegative integer")
    axes = segment.bounds()
    arm_speed = sum(radius * axis.max_speed_rad_s for radius, axis in zip(arm_radii_m, axes))
    support_speed = rotating_radius_m * axes[6].max_speed_rad_s
    relative_speed = max(2 * arm_speed, arm_speed + support_speed)
    if not math.isfinite(relative_speed):
        raise ValueError("Segment has no finite motion bound")

    pending = [(0.0, 1.0, 0)]
    smallest = math.inf
    count = 0
    uncertain = None
    while pending:
        begin, end, depth = pending.pop()
        midpoint = 0.5 * (begin + end)
        configuration, _ = segment.at(midpoint)
        observed = distance(configuration)
        if not math.isfinite(observed):
            raise ValueError("Clearance observer returned a nonfinite distance")
        smallest = min(smallest, observed)
        count += 1
        if observed < minimum_m:
            return ClearanceResult("violation", smallest, count, midpoint)
        half_seconds = (end - begin) * segment.seconds * 0.5
        if observed - relative_speed * half_seconds >= minimum_m:
            continue
        if depth == max_depth:
            if uncertain is None:
                uncertain = midpoint
            continue
        pending.extend(((midpoint, end, depth + 1), (begin, midpoint, depth + 1)))
    if uncertain is not None:
        return ClearanceResult("unresolved", smallest, count, uncertain)
    return ClearanceResult("clear", smallest, count, None)
