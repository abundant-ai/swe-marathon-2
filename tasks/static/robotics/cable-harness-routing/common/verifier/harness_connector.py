"""Independent keyed-pose and operator retention checks for trusted plant traces."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import asin, ceil, isfinite
from numbers import Integral, Real
from typing import Protocol

import numpy as np
from numpy.typing import ArrayLike


def _finite(value: Real, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be finite")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be finite") from error
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _nonnegative(value: Real, name: str) -> float:
    result = _finite(value, name)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _vector(value: ArrayLike, size: int, name: str) -> np.ndarray:
    try:
        vector = np.array(value, dtype=float, copy=True)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must contain {size} finite coordinates") from error
    if vector.shape != (size,) or not np.isfinite(vector).all():
        raise ValueError(f"{name} must contain {size} finite coordinates")
    vector.setflags(write=False)
    return vector


def _unit_quaternion(value: ArrayLike, name: str) -> np.ndarray:
    vector = _vector(value, 4, name)
    length = float(np.linalg.norm(vector))
    if abs(length - 1) > 1e-6:
        raise ValueError(f"{name} must be a unit XYZW quaternion")
    return vector / length


def _angular_distance(first: np.ndarray, second: np.ndarray) -> float:
    # The smaller quaternion chord identifies q and -q and behaves well
    # close to zero, where acos(dot(q, r)) loses precision.
    length = min(np.linalg.norm(first - second), np.linalg.norm(first + second))
    return 4 * asin(min(1.0, float(length / 2)))


@dataclass(frozen=True, eq=False)
class SeatRecipe:
    """Calibrated plug target pose and the independent operator's load."""

    position_m: ArrayLike
    quaternion_xyzw: ArrayLike
    insertion_axis_world: ArrayLike
    native_step_s: float
    position_tolerance_m: float = .0015
    rotation_tolerance_rad: float = .006
    retention_load_n: float = 3.
    retention_duration_s: float = .4
    applied_force_tolerance_n: float = 1e-8
    applied_moment_tolerance_nm: float = 1e-8
    displacement_limit_m: float | None = None

    def __post_init__(self) -> None:
        position = _vector(self.position_m, 3, "seat position")
        quaternion = _unit_quaternion(self.quaternion_xyzw, "seat orientation")
        axis = _vector(self.insertion_axis_world, 3, "insertion axis")
        length = float(np.linalg.norm(axis))
        if not 0 < length < float("inf"):
            raise ValueError("Insertion axis must have a nonzero direction")
        for name in ("native_step_s", "retention_load_n", "retention_duration_s"):
            if _nonnegative(getattr(self, name), name) == 0:
                raise ValueError(f"{name} must be positive")
        for name in ("position_tolerance_m", "rotation_tolerance_rad", "applied_force_tolerance_n",
                     "applied_moment_tolerance_nm"):
            _nonnegative(getattr(self, name), name)
        if self.displacement_limit_m is not None:
            _nonnegative(self.displacement_limit_m, "pull displacement limit")
        axis = axis / length
        axis.setflags(write=False)
        quaternion.setflags(write=False)
        object.__setattr__(self, "position_m", position)
        object.__setattr__(self, "quaternion_xyzw", quaternion)
        object.__setattr__(self, "insertion_axis_world", axis)


@dataclass(frozen=True)
class NativeContact:
    """Measured pair-specific contact on the plug, boot, socket, or gripper."""

    pair: tuple[str, str]
    normal_force_n: float
    distance_m: float


@dataclass(frozen=True)
class ConnectorSnapshot:
    """Native state at a tick and the operator load during the preceding step.

    The pose is measured at the keyed plug site. The operator wrench is in
    world axes about the calibrated pull point, with force then moment.
    Release is trusted evidence of physically absent gripper support, derived
    from jaw travel, engagement and contact rather than a command or mode.
    """

    tick: int
    position_m: ArrayLike
    quaternion_xyzw: ArrayLike
    interlock: bool
    gripper_released: bool | None
    operator_wrench_world: ArrayLike | None
    contacts: tuple[NativeContact, ...] | None
    gripper_wrench_world: ArrayLike | None = None


@dataclass(frozen=True)
class Finding:
    tick: int
    reason: str
    contact_pair: tuple[str, str] | None = None


@dataclass(frozen=True)
class ConnectorAssessment:
    first_seated_tick: int | None
    observed_pull_steps: int
    effective_pull_steps: int
    effective_pull_duration_s: float
    min_axial_pull_n: float | None
    max_pull_position_error_m: float | None
    max_pull_rotation_error_rad: float | None
    max_pull_displacement_m: float | None
    max_axial_withdrawal_m: float | None
    final_position_error_m: float | None
    final_rotation_error_rad: float | None
    peak_contact_force_n: float
    peak_contact_penetration_m: float
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return self.first_seated_tick is not None and not self.findings


class RouteEvidence(Protocol):
    @property
    def passed(self) -> bool: ...


def _tick(value: int, name: str) -> int:
    if not isinstance(value, Integral) or isinstance(value, (bool, np.bool_)) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return int(value)


def _switch(value: bool | None, name: str, optional: bool = False) -> bool | None:
    if value is None and optional:
        return None
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a physical boolean observation")
    return bool(value)


def _largest(previous: float | None, value: float) -> float:
    return value if previous is None else max(previous, value)


def assess_connector(
    snapshots: Iterable[ConnectorSnapshot], recipe: SeatRecipe, *,
    pull_start_tick: int, pull_end_tick: int,
    route: RouteEvidence | None = None, require_route: bool = False,
    permitted_contacts: Iterable[tuple[str, str]] | None = None,
    max_contact_force_n: float | None = None,
    max_contact_penetration_m: float | None = None,
) -> ConnectorAssessment:
    """Check keyed seat before release and continuous retention under load.

    Pull ticks specify the independent operator interval. The start tick is
    the baseline before load and the end tick is after the last loaded step.
    A terminal pose or interlock alone cannot substitute for missing samples.
    Measured pose must remain within calibration at every tick in that
    interval. An optional displacement budget additionally limits travel
    from the pre-pull pose. The caller supplies optional contact restrictions
    from the job and geometry.
    """
    start = _tick(pull_start_tick, "pull start")
    end = _tick(pull_end_tick, "pull end")
    if end <= start:
        raise ValueError("The pull interval must advance native time")
    force_limit = None if max_contact_force_n is None else _nonnegative(max_contact_force_n, "contact force limit")
    penetration_limit = (None if max_contact_penetration_m is None else
                         _nonnegative(max_contact_penetration_m, "contact penetration limit"))
    allowed = None if permitted_contacts is None else {tuple(sorted(pair)) for pair in permitted_contacts}

    findings: dict[tuple[str, tuple[str, str] | None], Finding] = {}

    def report(tick: int, reason: str, pair: tuple[str, str] | None = None) -> None:
        findings.setdefault((reason, pair), Finding(tick, reason, pair))

    if route is not None and not route.passed:
        report(start, "route_not_preserved")
    if require_route and route is None:
        report(start, "route_unverified")

    first_seat = previous = None
    pull_origin = None
    observed = streak = sustained = 0
    peak_force = peak_penetration = 0.0
    min_force = pull_position = pull_rotation = excursion = withdrawal = None
    final_position = final_rotation = final_interlock = None
    end_observed = False
    expected_force = -recipe.retention_load_n * recipe.insertion_axis_world

    for row in snapshots:
        tick = _tick(row.tick, "native tick")
        if previous is not None:
            if tick <= previous:
                raise ValueError("Native ticks must be strictly increasing")
            if tick - previous != 1:
                report(tick, "native_trace_gap")
                streak = 0
        previous = tick
        position = _vector(row.position_m, 3, "measured plug position")
        orientation = _unit_quaternion(row.quaternion_xyzw, "measured plug orientation")
        engaged = _switch(row.interlock, "interlock")
        released = _switch(row.gripper_released, "physical release", optional=True)
        wrench = None if row.operator_wrench_world is None else _vector(row.operator_wrench_world, 6, "operator wrench")
        pos_error = float(np.linalg.norm(position - recipe.position_m))
        rot_error = _angular_distance(orientation, recipe.quaternion_xyzw)
        position_ok = pos_error <= recipe.position_tolerance_m + 1e-12
        rotation_ok = rot_error <= recipe.rotation_tolerance_rad + 1e-12
        aligned = position_ok and rotation_ok
        final_position, final_rotation, final_interlock = pos_error, rot_error, engaged
        if tick >= start and engaged and not aligned:
            report(tick, "interlock_pose_inconsistent")
        if engaged and aligned and first_seat is None and tick <= start:
            first_seat = tick

        if row.contacts is None:
            report(tick, "contact_unverified")
        else:
            for contact in row.contacts:
                if (len(contact.pair) != 2 or not all(isinstance(name, str) and name for name in contact.pair)):
                    raise ValueError("Native contact requires both geometry names")
                pair = tuple(sorted(contact.pair))
                force = _nonnegative(contact.normal_force_n, "contact force")
                distance = _finite(contact.distance_m, "contact distance")
                peak_force = max(peak_force, force)
                peak_penetration = max(peak_penetration, -distance)
                if allowed is not None and pair not in allowed and (force > 0 or distance < 0):
                    report(tick, "forbidden_contact", pair)
                if force_limit is not None and force > force_limit:
                    report(tick, "contact_force", pair)
                if penetration_limit is not None and -distance > penetration_limit:
                    report(tick, "contact_penetration", pair)

        if tick == start:
            pull_origin = position
        if tick == end:
            end_observed = True
        if not start <= tick <= end:
            continue
        if not engaged:
            report(tick, "interlock_lost")
        if row.gripper_wrench_world is not None:
            support = _vector(row.gripper_wrench_world, 6, "effective gripper wrench")
            if (np.linalg.norm(support[:3]) > recipe.applied_force_tolerance_n
                    or np.linalg.norm(support[3:]) > recipe.applied_moment_tolerance_nm):
                released = False
        if released is None:
            report(tick, "release_unverified")
        elif not released:
            report(tick, "gripper_support")
        if not position_ok:
            report(tick, "retention_position")
        if not rotation_ok:
            report(tick, "retention_rotation")
        pull_position = _largest(pull_position, pos_error)
        pull_rotation = _largest(pull_rotation, rot_error)
        if pull_origin is not None:
            displacement = float(np.linalg.norm(position - pull_origin))
            excursion = _largest(excursion, displacement)
            withdrawal = _largest(withdrawal, float((pull_origin - position) @ recipe.insertion_axis_world))
            if recipe.displacement_limit_m is not None and displacement > recipe.displacement_limit_m + 1e-12:
                report(tick, "retention_displacement")

        if tick > start:
            observed += 1
            if wrench is None:
                report(tick, "pull_wrench_unverified")
                streak = 0
                continue
            axial_force = float(-wrench[:3] @ recipe.insertion_axis_world)
            min_force = axial_force if min_force is None else min(min_force, axial_force)
            force_ok = float(np.linalg.norm(wrench[:3] - expected_force)) <= recipe.applied_force_tolerance_n
            moment_ok = float(np.linalg.norm(wrench[3:])) <= recipe.applied_moment_tolerance_nm
            if not force_ok:
                report(tick, "pull_force")
            if not moment_ok:
                report(tick, "operator_moment")
            streak = streak + 1 if force_ok and moment_ok and released else 0
            sustained = max(sustained, streak)

    if first_seat is None:
        report(start, "keyed_seat_unverified")
    if previous is not None and previous > end:
        if not final_interlock:
            report(previous, "final_interlock_lost")
        if final_position > recipe.position_tolerance_m + 1e-12:
            report(previous, "final_position")
        if final_rotation > recipe.rotation_tolerance_rad + 1e-12:
            report(previous, "final_rotation")
    if pull_origin is None or not end_observed or observed != end - start:
        report(end, "pull_history_incomplete")
    exact_required = recipe.retention_duration_s / recipe.native_step_s
    required_steps = ceil(exact_required - 1e-12 * max(1.0, exact_required))
    if sustained < max(1, required_steps):
        report(end, "pull_duration")

    return ConnectorAssessment(
        first_seat, observed, sustained, sustained * recipe.native_step_s, min_force,
        pull_position, pull_rotation, excursion, withdrawal, final_position, final_rotation,
        peak_force, peak_penetration, tuple(findings.values()),
    )
