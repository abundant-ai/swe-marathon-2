"""Recover the active attachment from time-aligned, independently surveyed poses."""

from collections.abc import Sequence
from itertools import combinations
from typing import TypedDict

import numpy as np

from .native_cell import Geometry, angular_delta, encoded, inverse, pose, transform
from .plan_native import canonical


class PoseRecord(TypedDict):
    """A rigid transform encoded in metres and xyzw quaternion order."""

    translation_m: list[float]
    quaternion_xyzw: list[float]


class Observation(TypedDict):
    """Camera pose and arm encoders aligned to one measured tick."""

    epoch: int
    owner: str
    capture_tick: int
    q: dict[str, list[float]]
    world_from_object: PoseRecord


def collect_grasp_observations(
    prior: dict[str, Observation], arrivals: Sequence[object], *, epoch: int, owner: str,
    first_tick: int, now_tick: int, max_age_ticks: int, joint_limits: np.ndarray,
) -> dict[str, Observation]:
    """Extend the active survey journal with distinct eligible capture ticks.

    Args:
        prior: Previously accepted arrivals for this owner and epoch, keyed
            by the decimal capture tick for JSON persistence.
        arrivals: Records delivered at the current dispatch. Discard malformed
            readings before they can claim a capture tick.
        epoch: Active grasp survey generation.
        owner: Measured holder whose grasp the interlock invalidated.
        first_tick: Measured tick at which the epoch began, inclusive.
        now_tick: Current measured tick, inclusive.
        max_age_ticks: Inclusive maximum capture age in 5 ms ticks.
        joint_limits: Commissioned lower and upper bounds for all 12 encoder axes.

    Returns:
        A new journal retaining the first valid reading per fresh capture.
        The function leaves the input journal and individual readings intact.
    """
    oldest = max(first_tick, now_tick - max_age_ticks)
    accepted = {key: row for key, row in prior.items() if oldest <= row["capture_tick"] <= now_tick}
    for item in arrivals:
        if not isinstance(item, dict):
            continue
        tick = item.get("capture_tick")
        if (type(tick) is not int or not oldest <= tick <= now_tick
                or type(item.get("epoch")) is not int or item["epoch"] != epoch
                or item.get("owner") != owner or str(tick) in accepted):
            continue
        try:
            q = canonical(item["q"])
            pose(item["world_from_object"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if np.any(q < joint_limits[:, 0]) or np.any(q > joint_limits[:, 1]):
            continue
        accepted[str(tick)] = item
    return accepted


def agrees(first: np.ndarray, second: np.ndarray, position_m: float, rotation_rad: float) -> bool:
    """Compare two homogeneous transforms in their common object frame.

    The translation norm is in metres and the relative rotation norm is the
    shortest rotation angle in radians. Both survey tolerances are inclusive.
    """
    offset = first[:3, 3] - second[:3, 3]
    angle = angular_delta(first[:3, :3], second[:3, :3])
    return bool(np.linalg.norm(offset) <= position_m and np.linalg.norm(angle) <= rotation_rad)


def largest_supports(neighbors: dict[int, set[int]], minimum: int) -> list[tuple[int, ...]]:
    """Enumerate every largest pairwise-agreeing subset of the survey graph.

    Neighbor sets contain only distinct, compatible capture ticks. A pivot
    limits the branches, and any branch unable to match the largest support
    found so far is skipped. Return only sets meeting the minimum count.
    """
    largest = minimum
    supports: list[tuple[int, ...]] = []

    def search(chosen: tuple[int, ...], available: set[int], visited: set[int]) -> None:
        """Extend one clique, skipping maximal cliques from earlier branches."""
        nonlocal largest
        if len(chosen) + len(available) < largest:
            return
        if not available and not visited:
            if len(chosen) > largest:
                largest = len(chosen)
                supports.clear()
            supports.append(tuple(sorted(chosen)))
            return

        pivot = max(available | visited, key=lambda tick: (len(available & neighbors[tick]), -tick))
        for tick in sorted(available - neighbors[pivot]):
            search((*chosen, tick), available & neighbors[tick], visited & neighbors[tick])
            available.remove(tick)
            visited.add(tick)

    search((), set(neighbors), set())
    return supports


def mean_pose(samples: Sequence[np.ndarray]) -> np.ndarray:
    """Fit position and proper rotation to a nonempty set of agreeing poses.

    The polar projection of the mean rotation gives a rigid fit without
    depending on how incoming quaternions choose their signs.
    """
    mean = np.mean(samples, axis=0)
    left, _, right = np.linalg.svd(mean[:3, :3])
    determinant = np.linalg.det(left @ right)
    left[:, -1] *= np.sign(determinant)
    return transform(mean[:3, 3], left @ right)


def fit_grasp(
    observations: dict[str, Observation], geometry: Geometry, owner: str, *,
    minimum_captures: int = 3, position_tolerance_m: float, rotation_tolerance_rad: float,
) -> tuple[PoseRecord, list[int]] | None:
    """Express the active gripper in the surveyed payload frame.

    Args:
        observations: Fresh distinct captures accepted by the survey journal.
        geometry: Calibrated arm geometry whose kinematic scratch data may
            be overwritten while evaluating each capture.
        owner: Physical holder throughout this epoch.
        minimum_captures: Number of distinct captures needed for agreement.
        position_tolerance_m: Inclusive Euclidean translation tolerance.
        rotation_tolerance_rad: Inclusive relative rotation tolerance.

    Returns:
        The object-from-grasp pose and ascending ticks of a largest supporting
        set. Return None when evidence is insufficient, incompatible fits tie
        for the largest support, or the fit violates the grasp envelope.
    """
    estimates: dict[int, np.ndarray] = {}
    for row in observations.values():
        geometry.sites(canonical(row["q"]))
        estimates[row["capture_tick"]] = inverse(pose(row["world_from_object"])) @ geometry.location(owner)

    tolerances = (position_tolerance_m, rotation_tolerance_rad)
    neighbors: dict[int, set[int]] = {tick: set() for tick in estimates}
    for first, second in combinations(estimates, 2):
        if agrees(estimates[first], estimates[second], *tolerances):
            neighbors[first].add(second)
            neighbors[second].add(first)

    fits = []
    for support in sorted(largest_supports(neighbors, minimum_captures)):
        samples = [estimates[tick] for tick in support]
        fitted = mean_pose(samples)
        if np.linalg.norm(fitted[:3, 3]) <= .48 and all(agrees(fitted, item, *tolerances) for item in samples):
            fits.append((fitted, support))
    if not fits or any(not agrees(first[0], second[0], *tolerances) for first, second in combinations(fits, 2)):
        return None
    fitted, support = fits[0]
    return encoded(fitted), list(support)
