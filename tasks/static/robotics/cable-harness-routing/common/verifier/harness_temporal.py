"""Independent cable route checks over trusted plant observations."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real

import numpy as np

from harness_metrology import Centerline, ClipGate, Point, observe_gate


@dataclass(frozen=True)
class RouteClip:
    """A material through-plane and a mouth plane with its normal inward."""

    seat: ClipGate
    mouth: ClipGate

    def __post_init__(self) -> None:
        if self.seat.clip_id != self.mouth.clip_id:
            raise ValueError("Seat and mouth must identify the same clip")


@dataclass(frozen=True)
class TemporalSnapshot:
    """A trusted plant sample after one native integration tick."""

    tick: int
    line: Centerline
    latched_clip_ids: frozenset[str]


@dataclass(frozen=True)
class EntryCrossing:
    """One time-domain crossing by the material observed at the seat."""

    tick: float
    bracket_ticks: tuple[int, int]
    material_s_m: float
    point_m: Point
    inward: bool
    inside_mouth: bool


@dataclass(frozen=True)
class Installation:
    clip_id: str
    tick: int
    material_s_m: float
    entry: EntryCrossing | None
    carried_in: bool


@dataclass(frozen=True)
class RouteFinding:
    tick: int
    clip_id: str | None
    reason: str


@dataclass(frozen=True)
class RouteAssessment:
    observed_ticks: int
    installations: tuple[Installation, ...]
    final_occupants_m: tuple[tuple[str, float], ...]
    findings: tuple[RouteFinding, ...]

    @property
    def passed(self) -> bool:
        return self.observed_ticks >= 2 and not self.findings


def _side(distance: float, epsilon: float) -> int:
    return 1 if distance > epsilon else (-1 if distance < -epsilon else 0)


def _past_entry(
    history: Sequence[TemporalSnapshot], tag: float, mouth: ClipGate, epsilon: float,
) -> EntryCrossing | None:
    """Find the last crossing by this exact material tag, wherever it occurred."""
    latest = None
    previous = None
    coplanar: list[tuple[int, np.ndarray]] = []
    for frame in history:
        point = np.asarray(frame.line.point_at_material(tag))
        signed = float((point - mouth.origin_m) @ mouth.normal)
        side = _side(signed, epsilon)
        if side == 0:
            coplanar.append((frame.tick, point))
            continue
        if previous is not None and previous[1] != side:
            before_tick, _, before_signed, before_point = previous
            if coplanar:
                tick, crossing = coplanar[0]
                inside = all(mouth.contains(sample, epsilon) for _, sample in coplanar)
            else:
                weight = before_signed / (before_signed - signed)
                tick = before_tick + weight * (frame.tick - before_tick)
                crossing = before_point + weight * (point - before_point)
                inside = mouth.contains(crossing, epsilon)
            latest = EntryCrossing(
                float(tick), (before_tick, frame.tick), tag,
                (float(crossing[0]), float(crossing[1]), float(crossing[2])),
                side > 0, inside,
            )
        previous = (frame.tick, side, signed, point)
        coplanar.clear()
    return latest


def _nonnegative(value: Real, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be finite and nonnegative")
    result = float(value)
    if not isfinite(result) or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def assess_route(
    snapshots: Iterable[TemporalSnapshot], clips: Sequence[RouteClip], *,
    require_complete: bool = True,
    max_snapshot_gap_ticks: int | None = None,
    max_material_drift_m: float | None = None,
    geometry_tolerance_m: float = 1e-9,
    carried_in: Mapping[str, float] | None = None,
) -> RouteAssessment:
    """Measure signed entry, ordered occupancy, and preservation after latch.

    Consume trusted snapshots from before placement through the retention
    pull. A protected clip must remain closed and admit exactly one correctly
    oriented, in-range crossing at every subsequent observation. Material
    order is independent of the chronological order of latching.

    Interrupted runs may carry forward material assignments from already
    audited history. Those clips must be valid at the first new tick. When
    supplied, material drift bounds the displacement of the observed seat
    crossing relative to its retained assignment. Recipe intervals always
    apply. A blocked run can skip completion but must preserve installed clips.
    """
    clips = tuple(clips)
    ids = {clip.seat.clip_id for clip in clips}
    if not clips or len(ids) != len(clips):
        raise ValueError("Route needs nonempty unique clip IDs")
    epsilon = _nonnegative(geometry_tolerance_m, "geometry tolerance")
    drift = None if max_material_drift_m is None else _nonnegative(max_material_drift_m, "material drift")
    gap = max_snapshot_gap_ticks
    if gap is not None and (not isinstance(gap, Integral) or isinstance(gap, (bool, np.bool_)) or gap <= 0):
        raise ValueError("Maximum snapshot gap must be a positive integer")
    trusted = {} if carried_in is None else {
        identity: _nonnegative(tag, "carried material") for identity, tag in carried_in.items()
    }
    if set(trusted) - ids:
        raise ValueError("A carried clip is absent from the route")
    for clip in clips:
        identity = clip.seat.clip_id
        if identity in trusted:
            low, high = clip.seat.material_range_m
            if not low <= trusted[identity] <= high:
                raise ValueError("Carried material is outside the route recipe")

    history = []
    first_latch: dict[str, int] = {}
    installed: dict[str, Installation] = {}
    findings: dict[tuple[str | None, str], RouteFinding] = {}
    current = {}
    previous_tick = None
    tags = None

    def report(tick: int, identity: str | None, reason: str) -> None:
        findings.setdefault((identity, reason), RouteFinding(tick, identity, reason))

    for frame in snapshots:
        tick = frame.tick
        if not isinstance(tick, Integral) or isinstance(tick, (bool, np.bool_)) or tick < 0:
            raise ValueError("Native ticks must be nonnegative integers")
        tick = int(tick)
        if previous_tick is not None:
            if tick <= previous_tick:
                raise ValueError("Native ticks must be strictly increasing")
            if gap is not None and tick - previous_tick > gap:
                report(tick, None, "snapshot_gap")
        else:
            for identity in trusted.keys() - frame.latched_clip_ids:
                report(tick, identity, "carried_clip_open")
        previous_tick = tick
        if tags is None:
            tags = frame.line.material_s_m
        elif not np.array_equal(frame.line.material_s_m, tags):
            raise ValueError("Native material identity changed between snapshots")
        history.append(frame)
        current = {}
        last_rest = None

        for clip in clips:
            identity = clip.seat.clip_id
            latched = identity in frame.latched_clip_ids
            if not latched and identity not in first_latch and identity not in trusted:
                continue
            if not latched:
                report(tick, identity, "released_after_latch")
            first = identity not in first_latch
            if latched and first:
                first_latch[identity] = tick
            observed = observe_gate(frame.line, clip.seat, geometry_tolerance_m=epsilon)
            if not observed.seated:
                report(tick, identity, "seat_" + observed.status)
                continue

            actual = observed.crossings[0]
            tag = actual.material_s_m
            if last_rest is not None and tag <= last_rest:
                report(tick, identity, "material_order")
            last_rest = tag
            if latched:
                current[identity] = tag

            if identity in installed:
                original = installed[identity].material_s_m
                if drift is not None and abs(tag - original) > drift:
                    report(tick, identity, "material_drift")
                continue
            if not latched or not first:
                continue
            if identity in trusted:
                if drift is not None and abs(tag - trusted[identity]) > drift:
                    report(tick, identity, "carried_material_mismatch")
                else:
                    installed[identity] = Installation(identity, tick, trusted[identity], None, True)
                continue

            entry = _past_entry(history, tag, clip.mouth, epsilon)
            if entry is None:
                report(tick, identity, "missing_lateral_entry")
            elif not entry.inward:
                report(tick, identity, "outward_lateral_entry")
            elif not entry.inside_mouth:
                report(tick, identity, "entry_outside_mouth")
            elif (np.asarray(actual.point_m) - clip.mouth.origin_m) @ clip.mouth.normal <= epsilon:
                report(tick, identity, "latch_outside_mouth")
            else:
                installed[identity] = Installation(identity, tick, tag, entry, False)

    if require_complete and previous_tick is not None:
        for clip in clips:
            identity = clip.seat.clip_id
            if identity not in installed:
                report(previous_tick, identity, "missing_installation")
            elif identity not in current:
                report(previous_tick, identity, "missing_final_seat")
    return RouteAssessment(len(history), tuple(installed.values()), tuple(current.items()), tuple(findings.values()))
