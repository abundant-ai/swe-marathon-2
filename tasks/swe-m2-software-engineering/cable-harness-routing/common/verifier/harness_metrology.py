"""Independent centerline measurements in the trusted rod's material order."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
Point = tuple[float, float, float]
GateStatus = Literal["seated", "no_crossing", "ambiguous", "wrong_direction", "wrong_material"]


def _number(value: Real, field_name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be finite")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{field_name} must be finite") from error
    if not isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _nonnegative(value: Real, field_name: str) -> float:
    result = _number(value, field_name)
    if result < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return result


def _array(value: ArrayLike, shape: tuple[int, ...], name: str) -> FloatArray:
    try:
        result = np.array(value, dtype=float, copy=True)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be finite numeric coordinates") from error
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite coordinates of shape {shape}")
    result.setflags(write=False)
    return result


def _unit(value: FloatArray, name: str) -> FloatArray:
    length = float(np.linalg.norm(value))
    if not 0 < length < float("inf"):
        raise ValueError(f"{name} must have a nonzero direction")
    result = value / length
    result.setflags(write=False)
    return result


def _point(value: FloatArray) -> Point:
    return float(value[0]), float(value[1]), float(value[2])


@dataclass(frozen=True, eq=False)
class Centerline:
    """Ordered world points and independent rest-material tags, all in metres.

    A stretched cable changes its spatial arclength while these material
    identities remain fixed. Equal adjacent world points are allowed.
    """

    points_m: ArrayLike
    material_s_m: ArrayLike
    _arc_m: FloatArray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        shape = np.shape(self.points_m)
        if len(shape) != 2 or shape[0] < 2 or shape[1] != 3:
            raise ValueError("A centerline needs at least two XYZ points")
        points = _array(self.points_m, shape, "points_m")
        tags = _array(self.material_s_m, (shape[0],), "material_s_m")
        if tags[0] < 0 or np.any(tags[1:] <= tags[:-1]):
            raise ValueError("Material tags must be nonnegative and strictly increasing")
        arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
        if not np.isfinite(arc).all():
            raise ValueError("Centerline arclength is not finite")
        arc.setflags(write=False)
        object.__setattr__(self, "points_m", points)
        object.__setattr__(self, "material_s_m", tags)
        object.__setattr__(self, "_arc_m", arc)

    @property
    def spatial_length_m(self) -> float:
        """Length of the deformed centerline polyline."""
        return float(self._arc_m[-1])

    @property
    def material_range_m(self) -> tuple[float, float]:
        """First and last rest-material coordinate included in this observation."""
        return float(self.material_s_m[0]), float(self.material_s_m[-1])

    @property
    def max_segment_m(self) -> float:
        """Largest spatial gap between successive rod observations."""
        return float(np.diff(self._arc_m).max())

    def point_at_material(self, s_m: Real) -> Point:
        """Interpolate the world position of an arbitrary included material tag."""
        query = _number(s_m, "material arclength")
        return self._interpolate(query, self.material_s_m, "material arclength")

    def point_at_arc(self, s_m: Real) -> Point:
        """Interpolate at a deformed distance from the first sample."""
        query = _number(s_m, "spatial arclength")
        return self._interpolate(query, self._arc_m, "spatial arclength")

    def _interpolate(self, query: float, coordinates: FloatArray, name: str) -> Point:
        if not coordinates[0] <= query <= coordinates[-1]:
            raise ValueError(f"{name} is outside the observed interval")
        index = int(np.searchsorted(coordinates, query, side="left"))
        if query == coordinates[index]:
            return _point(self.points_m[index])
        before, after = coordinates[index - 1:index + 1]
        weight = (query - before) / (after - before)
        return _point(self.points_m[index - 1] + weight * (self.points_m[index] - self.points_m[index - 1]))


@dataclass(frozen=True, eq=False)
class ClipGate:
    """A plane and allowed cable-center aperture in the centerline frame.

    Set either a circular radius or rectangular half extents. Rectangular
    extents are measured along the supplied in-plane u axis and normal × u.
    Through direction is the sign of traversal along increasing material
    arclength. Temporal entry from a fixture's mouth is a separate observation.
    """

    clip_id: str
    origin_m: ArrayLike
    normal: ArrayLike
    material_range_m: tuple[float, float]
    through_direction: int = field(default=1, kw_only=True)
    radius_m: float | None = field(default=None, kw_only=True)
    half_extents_m: ArrayLike | None = field(default=None, kw_only=True)
    u_axis: ArrayLike | None = field(default=None, kw_only=True)
    _basis: FloatArray | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.clip_id, str) or not self.clip_id:
            raise ValueError("clip_id must be nonempty")
        if (not isinstance(self.through_direction, Integral) or isinstance(self.through_direction, (bool, np.bool_))
                or self.through_direction not in (-1, 1)):
            raise ValueError("through_direction must be +1 or -1")
        origin = _array(self.origin_m, (3,), "gate origin")
        normal = _unit(_array(self.normal, (3,), "gate normal"), "gate normal")
        material_range = _array(self.material_range_m, (2,), "material range")
        if material_range[0] < 0 or material_range[1] < material_range[0]:
            raise ValueError("Material range must be nonnegative and ordered")
        if (self.radius_m is None) == (self.half_extents_m is None):
            raise ValueError("Specify exactly one gate aperture shape")
        basis = None
        if self.radius_m is not None:
            radius = _nonnegative(self.radius_m, "gate radius")
            if self.u_axis is not None:
                raise ValueError("A circular gate does not need a u axis")
            object.__setattr__(self, "radius_m", radius)
        else:
            extent = _array(self.half_extents_m, (2,), "gate half extents")
            if np.any(extent < 0):
                raise ValueError("Gate half extents must be nonnegative")
            u = _unit(_array(self.u_axis, (3,), "gate u axis"), "gate u axis")
            tangent = u - normal * (normal @ u)
            if np.linalg.norm(tangent) < 1e-12:
                raise ValueError("Gate u axis must span the aperture plane")
            u = _unit(tangent, "gate u axis")
            basis = np.stack((u, np.cross(normal, u)))
            basis.setflags(write=False)
            object.__setattr__(self, "half_extents_m", extent)
            object.__setattr__(self, "u_axis", u)
        object.__setattr__(self, "origin_m", origin)
        object.__setattr__(self, "normal", normal)
        object.__setattr__(self, "material_range_m", (float(material_range[0]), float(material_range[1])))
        object.__setattr__(self, "_basis", basis)

    def _plane_coords(self, point: FloatArray) -> FloatArray:
        relative = point - self.origin_m
        if self._basis is not None:
            return self._basis @ relative
        return relative - self.normal * (self.normal @ relative)

    def contains(self, point: FloatArray, tolerance_m: float) -> bool:
        local = self._plane_coords(point)
        if self.radius_m is not None:
            return float(np.linalg.norm(local)) <= self.radius_m + tolerance_m
        return bool(np.all(np.abs(local) <= self.half_extents_m + tolerance_m))

    def _crosses_aperture(self, start: FloatArray, end: FloatArray, tolerance_m: float) -> bool:
        first = self._plane_coords(start)
        line = self._plane_coords(end) - first
        if self.radius_m is not None:
            squared = float(line @ line)
            fraction = 0.0 if squared == 0 else float(np.clip(-(first @ line) / squared, 0, 1))
            return float(np.linalg.norm(first + fraction * line)) <= self.radius_m + tolerance_m

        left, right = 0.0, 1.0
        for start_coord, step, extent in zip(first, line, self.half_extents_m + tolerance_m, strict=True):
            if step == 0:
                if abs(start_coord) > extent:
                    return False
                continue
            entry, leave = sorted(((-extent - start_coord) / step, (extent - start_coord) / step))
            left, right = max(left, entry), min(right, leave)
            if left > right:
                return False
        return True


@dataclass(frozen=True)
class Crossing:
    """An isolated transverse crossing of the aperture, in material order."""

    point_m: Point
    material_s_m: float
    spatial_s_m: float
    direction: int


@dataclass(frozen=True)
class GateObservation:
    clip_id: str
    status: GateStatus
    crossings: tuple[Crossing, ...]
    coplanar_material_ranges_m: tuple[tuple[float, float], ...]
    tangencies: int

    @property
    def seated(self) -> bool:
        return self.status == "seated"


def observe_gate(
    line: Centerline, gate: ClipGate, *, geometry_tolerance_m: float = 1e-9,
    material_tolerance_m: float = 1e-9,
) -> GateObservation:
    """Measure all in-aperture crossings, including wrong material or direction.

    An isolated sampled vertex is counted once if its neighbors straddle the
    plane. An in-aperture coplanar run has no unique material crossing. It is
    ambiguous even when another branch has an isolated crossing. A tangency
    or cable endpoint has no transverse crossing.
    """
    geometry_eps = _nonnegative(geometry_tolerance_m, "geometry tolerance")
    material_eps = _nonnegative(material_tolerance_m, "material tolerance")
    points, tags = line.points_m, line.material_s_m
    signed = (points - gate.origin_m) @ gate.normal
    signs = np.where(signed > geometry_eps, 1, np.where(signed < -geometry_eps, -1, 0))
    transverse = []
    runs = []
    tangencies = 0
    i = 0
    while i < len(points):
        current = signs[i]
        if current != 0:
            if i + 1 < len(points) and current * signs[i + 1] < 0:
                fraction = signed[i] / (signed[i] - signed[i + 1])
                point = points[i] + fraction * (points[i + 1] - points[i])
                if gate.contains(point, geometry_eps):
                    material = tags[i] + fraction * (tags[i + 1] - tags[i])
                    arc = line._arc_m[i] + fraction * (line._arc_m[i + 1] - line._arc_m[i])
                    transverse.append(Crossing(_point(point), float(material), float(arc), int(signs[i + 1])))
            i += 1
            continue

        start = i
        while i + 1 < len(points) and signs[i + 1] == 0:
            i += 1
        stop = i
        if stop > start:
            if any(gate._crosses_aperture(points[j], points[j + 1], geometry_eps) for j in range(start, stop)):
                runs.append((float(tags[start]), float(tags[stop])))
        elif gate.contains(points[i], geometry_eps):
            if 0 < i < len(points) - 1 and signs[i - 1] * signs[i + 1] < 0:
                transverse.append(Crossing(
                    _point(points[i]), float(tags[i]), float(line._arc_m[i]), int(signs[i + 1])
                ))
            else:
                tangencies += 1
        i += 1

    status: GateStatus
    if runs or len(transverse) > 1:
        status = "ambiguous"
    elif not transverse:
        status = "no_crossing"
    elif transverse[0].direction != gate.through_direction:
        status = "wrong_direction"
    else:
        low, high = gate.material_range_m
        status = "seated" if low - material_eps <= transverse[0].material_s_m <= high + material_eps else "wrong_material"
    return GateObservation(gate.clip_id, status, tuple(transverse), tuple(runs), tangencies)


@dataclass(frozen=True)
class BendMeasurement:
    """Finite-resolution minimum circumradius, with explicit missing evidence."""

    status: Literal["finite", "straight", "unresolved"]
    minimum_radius_m: float | None
    at_spatial_s_m: float | None
    half_window_m: float
    stride_m: float
    max_native_gap_m: float
    sampled_centers: int

    def passes_minimum(self, minimum_m: float) -> bool:
        limit = _nonnegative(minimum_m, "minimum bend radius")
        return self.status == "straight" or (
            self.status == "finite" and self.minimum_radius_m is not None and self.minimum_radius_m >= limit
        )


def measure_bend(
    line: Centerline, *, half_window_m: float, stride_m: float | None = None,
    max_native_gap_m: float | None = None,
) -> BendMeasurement:
    """Estimate the smallest bend radius resolved by a physical arclength gauge.

    For each sampled center, fit a circle through the center and two points
    separated by the specified deformed half-window. Centers include all native
    vertices where both arms of the gauge fit, plus a uniform grid. End bands
    shorter than the half-window are outside the gauge's support. The result
    describes the measured polyline and can miss bends below native resolution.
    A straight sample has unbounded radius. A reversal has zero radius.
    """
    half = _nonnegative(half_window_m, "bend half-window")
    stride = half / 2 if stride_m is None else _nonnegative(stride_m, "bend stride")
    if half == 0 or stride == 0:
        raise ValueError("Bend half-window and stride must be positive")
    max_gap = line.max_segment_m
    length = line.spatial_length_m
    limit = None if max_native_gap_m is None else _nonnegative(max_native_gap_m, "maximum native gap")
    if np.unique(line._arc_m).size < 3 or length < 2 * half or (limit is not None and max_gap > limit):
        return BendMeasurement("unresolved", None, None, half, stride, max_gap, 0)

    last = length - half
    intervals = max(1, int(np.ceil((last - half) / stride)))
    grid = np.linspace(half, last, intervals + 1)
    native = line._arc_m[(line._arc_m >= half) & (line._arc_m <= last)]
    centers = np.unique(np.r_[grid, native])
    best_radius, best_at = None, None
    unmeasured = False
    for center in centers:
        a, b, c = (
            np.asarray(line.point_at_arc(s_m)) for s_m in (center - half, center, min(length, center + half))
        )
        incoming, outgoing = b - a, c - b
        left, right, chord = (float(np.linalg.norm(vector)) for vector in (incoming, outgoing, c - a))
        near_zero = 1e-10 * half
        if left <= near_zero or right <= near_zero:
            unmeasured = True
            continue
        cross = float(np.linalg.norm(np.cross(incoming, outgoing)))
        if chord <= near_zero or (cross <= 1e-10 * left * right and incoming @ outgoing < 0):
            radius = 0.0
        elif cross <= 1e-10 * left * right:
            continue
        else:
            radius = left * right * chord / (2 * cross)
            if not isfinite(radius):
                unmeasured = True
                continue
        if best_radius is None or radius < best_radius:
            best_radius, best_at = radius, float(center)

    status = "unresolved" if unmeasured else ("straight" if best_radius is None else "finite")
    return BendMeasurement(status, best_radius, best_at, half, stride, max_gap, len(centers))


@dataclass(frozen=True)
class Snapshot:
    """Trusted centerline readout from a native plant tick."""

    tick: int
    line: Centerline


@dataclass(frozen=True)
class RetentionViolation:
    tick: int
    clip_id: str | None
    reason: str


@dataclass(frozen=True)
class RetentionResult:
    assessed_snapshots: int
    first_tick: int | None
    last_tick: int | None
    first_crossings_m: tuple[tuple[str, float], ...]
    last_crossings_m: tuple[tuple[str, float], ...]
    violations: tuple[RetentionViolation, ...]

    @property
    def passed(self) -> bool:
        return self.assessed_snapshots >= 2 and not self.violations


def assess_retention(
    snapshots: Iterable[Snapshot], gates: Sequence[ClipGate], *,
    max_material_drift_m: float | None = None, max_snapshot_gap_ticks: int | None = None,
) -> RetentionResult:
    """Check route order and every measured aperture throughout the pull.

    Gates are provided in the recipe's material order. An optional material
    drift limit is relative to the first snapshot, and an optional tick gap
    limit prevents overclaiming evidence across missing samples. Callers supply
    both limits from the physical recipe when applicable.
    """
    drift = None if max_material_drift_m is None else _nonnegative(max_material_drift_m, "material drift limit")
    max_gap = max_snapshot_gap_ticks
    if max_gap is not None and (type(max_gap) is not int or max_gap <= 0):
        raise ValueError("Maximum snapshot gap must be a positive integer")
    gates = tuple(gates)
    if not gates or len({gate.clip_id for gate in gates}) != len(gates):
        raise ValueError("Retention needs nonempty unique gate IDs in recipe order")

    failures = {}
    first_tick = previous_tick = None
    initial: dict[str, float] = {}
    current: dict[str, float] = {}
    count = 0

    def fail(tick: int, clip_id: str | None, reason: str) -> None:
        failures.setdefault((clip_id, reason), RetentionViolation(tick, clip_id, reason))

    for snapshot in snapshots:
        tick = snapshot.tick
        if not isinstance(tick, Integral) or isinstance(tick, (bool, np.bool_)) or tick < 0:
            raise ValueError("Snapshot ticks must be nonnegative integers")
        tick = int(tick)
        if previous_tick is not None:
            if tick <= previous_tick:
                raise ValueError("Snapshot ticks must be strictly increasing")
            if max_gap is not None and tick - previous_tick > max_gap:
                fail(tick, None, "snapshot_gap")
        else:
            first_tick = tick
        previous_tick = tick
        current = {}
        last_material = None
        for gate in gates:
            observed = observe_gate(snapshot.line, gate)
            if not observed.seated:
                fail(tick, gate.clip_id, observed.status)
                continue
            material = observed.crossings[0].material_s_m
            current[gate.clip_id] = material
            if last_material is not None and material <= last_material:
                fail(tick, gate.clip_id, "material_order")
            last_material = material
            if count == 0:
                initial[gate.clip_id] = material
            elif drift is not None and gate.clip_id in initial and abs(material - initial[gate.clip_id]) > drift:
                fail(tick, gate.clip_id, "material_drift")
        count += 1

    return RetentionResult(count, first_tick, previous_tick, tuple(initial.items()), tuple(current.items()),
                           tuple(failures.values()))
