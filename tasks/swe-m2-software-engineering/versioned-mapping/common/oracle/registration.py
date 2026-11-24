"""Correlative 2D scan registration with a bounded prior and ambiguity check."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
from pathlib import Path

from .maps import OCCUPIED, Pose, Visit, finite, json_bytes, read_map, read_object, read_visit, vector, write_bytes


SUPPORT_RADIUS = 0.12
COARSE_RADIUS = 0.20
Point = tuple[float, float]


@dataclass(frozen=True)
class Prior:
    """Search box in site coordinates and a numerical yaw interval."""

    center: Pose
    xy: float
    yaw: float

    def contains(self, pose: Pose) -> bool:
        """Check all three bounds, allowing for roundoff at the endpoint."""
        return all(abs(a - b) <= radius + 1e-12
                   for a, b, radius in zip(pose, self.center, (self.xy, self.xy, self.yaw), strict=True))


@dataclass(frozen=True)
class Fit:
    """One evaluated placement and its geometrically supported hit evidence."""

    pose: Pose
    support: int
    squared_error: float

    @property
    def score(self) -> tuple[int, float]:
        """Prefer greater support, then locally smaller endpoint error."""
        return self.support, -self.squared_error


def read_prior(path: Path) -> Prior:
    """Load the prior supplied with an unsurveyed visit."""
    data = read_object(path)
    xy = finite(data.get("xy_radius_m"), "xy_radius_m")
    yaw = finite(data.get("yaw_radius_rad"), "yaw_radius_rad")
    if not 0 < xy <= 3 or not 0 < yaw <= 1:
        raise ValueError("Prior radii are outside supported bounds")
    return Prior(vector(data.get("center"), 3, "prior center"), xy, yaw)


def endpoints(visit: Visit) -> list[Point]:
    """Express observed hit endpoints in the visit frame."""
    return [
        (x + distance * math.cos(yaw + angle), y + distance * math.sin(yaw + angle))
        for scan in visit.scans
        for x, y, yaw in [scan.pose]
        for angle, distance, hit in scan.beams if hit
    ]


class OccupiedCenters:
    """Spatial bins for exact proximity queries against occupied cell centers."""

    def __init__(self, points: list[Point]) -> None:
        """Index candidate match points in square bins of the coarse radius."""
        self.bins: dict[tuple[int, int], list[Point]] = {}
        for x, y in points:
            key = (math.floor(x / COARSE_RADIUS), math.floor(y / COARSE_RADIUS))
            self.bins.setdefault(key, []).append((x, y))

    def distance_squared(self, x: float, y: float, cutoff_squared: float) -> float:
        """Return exact nearest squared distance up to the supplied cutoff."""
        bx, by = math.floor(x / COARSE_RADIUS), math.floor(y / COARSE_RADIUS)
        best = math.inf
        for ix in (bx - 1, bx, bx + 1):
            for iy in (by - 1, by, by + 1):
                for px, py in self.bins.get((ix, iy), ()):
                    distance = (px - x) ** 2 + (py - y) ** 2
                    if distance <= cutoff_squared and distance < best:
                        best = distance
        return best


def evaluate(pose: Pose, points: list[Point], centers: OccupiedCenters, radius: float) -> Fit:
    """Measure support and squared residual on a list of local endpoints."""
    x, y, heading = pose
    co, si = math.cos(heading), math.sin(heading)
    squared_cutoff = radius**2
    count, error = 0, 0.0
    for local_x, local_y in points:
        distance = centers.distance_squared(
            x + co * local_x - si * local_y,
            y + si * local_x + co * local_y,
            squared_cutoff,
        )
        if math.isfinite(distance):
            count += 1
            error += distance
    return Fit(pose, count, error)


def coordinates(center: float, radius: float, step: float) -> list[float]:
    """Make a centered inclusive grid of bounded search coordinates."""
    count = math.ceil(radius / step)
    return [center + radius * i / count for i in range(-count, count + 1)]


def sample_points(points: list[Point], maximum: int) -> list[Point]:
    """Take an evenly spaced subset from a large scan sequence."""
    if len(points) <= maximum:
        return points
    return [points[i * len(points) // maximum] for i in range(maximum)]


def mode_distance(first: Pose, second: Pose) -> tuple[float, float]:
    """Give planar displacement and absolute wrapped angular displacement."""
    return (
        math.hypot(first[0] - second[0], first[1] - second[1]),
        abs(math.remainder(first[2] - second[2], math.tau)),
    )


def coarse_modes(prior: Prior, points: list[Point], centers: OccupiedCenters) -> list[Pose]:
    """Find distinct promising basins using tolerant, coarse endpoint matching."""
    x, y, yaw = prior.center
    subset = sample_points(points, 24)
    fits = (
        evaluate(pose, subset, centers, COARSE_RADIUS)
        for pose in product(coordinates(x, prior.xy, 0.14), coordinates(y, prior.xy, 0.14),
                            coordinates(yaw, prior.yaw, 0.075))
    )
    modes: list[Pose] = []
    for fit in sorted(fits, key=lambda item: item.score, reverse=True):
        if any(distance < 0.25 and angle < 0.13
               for distance, angle in (mode_distance(fit.pose, mode) for mode in modes)):
            continue
        modes.append(fit.pose)
        if len(modes) == 14:
            break
    return modes


def refine(seed: Pose, prior: Prior, points: list[Point], centers: OccupiedCenters) -> Fit:
    """Polish one coarse pose using progressively smaller neighborhoods."""
    best = evaluate(seed, points, centers, SUPPORT_RADIUS)
    for translation_step, angle_step in ((0.065, 0.035), (0.025, 0.016), (0.008, 0.005)):
        center = best.pose
        for dx, dy, da in product((-1, 0, 1), repeat=3):
            pose = (center[0] + dx * translation_step, center[1] + dy * translation_step,
                    center[2] + da * angle_step)
            if prior.contains(pose):
                fit = evaluate(pose, points, centers, SUPPORT_RADIUS)
                if fit.score > best.score:
                    best = fit
    return best


def register(map_path: Path, visit_path: Path, prior_path: Path, output: Path) -> None:
    """Search supported alignments and publish the evidence for the reported status."""
    grid, cells = read_map(map_path)
    points = endpoints(read_visit(visit_path))
    prior = read_prior(prior_path)
    centers = OccupiedCenters([grid.center(cell) for cell, state in cells.items() if state == OCCUPIED])
    best = Fit(prior.center, 0, 0)
    status = "insufficient_support"
    if points and centers.bins:
        subset = sample_points(points, 140)
        modes = coarse_modes(prior, points, centers)
        polished = [refine(pose, prior, subset, centers).pose for pose in modes]
        scores = sorted((evaluate(pose, points, centers, SUPPORT_RADIUS) for pose in polished),
                        key=lambda item: item.score, reverse=True)
        best = scores[0]
        if len(points) >= 6 and best.support / len(points) >= 0.65:
            status = "ok"
            for other in scores[1:]:
                distance, angle = mode_distance(other.pose, best.pose)
                if (other.support / len(points) >= 0.80 and (best.support - other.support) / len(points) <= 0.02
                        and (distance >= 0.60 or angle >= 0.30)):
                    status = "ambiguous"
                    break
    write_bytes(output, json_bytes({
        "status": status,
        "world_from_visit": list(best.pose) if status == "ok" else None,
        "hit_endpoints": len(points), "supported_endpoints": best.support,
        "coverage": best.support / len(points) if points else 0.0,
    }))
