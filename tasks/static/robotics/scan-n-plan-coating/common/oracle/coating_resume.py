"""Repair a stopped coating sweep from its measured delivered prefix."""

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from coating_planner import (
    CoatingDose, CollisionGuard, MaterialState, Motion, SerialArm, bounds_ok, bypass_dry_intervals, hermite,
    parse_motion, validated_pose,
)

Row = dict[str, Any]


@dataclass(frozen=True)
class DeliveredSweep:
    """Measured end of useful spray, normal gain, and requested deficit flow by interval."""

    cut_ns: int
    gain: float
    deficit_spans: tuple[tuple[int, int, float], ...]


def nozzle_epoch_offset(job: dict, before: dict, after: dict) -> float | None:
    """Return the signed physical index shift when an axial remount explains the change."""
    axis_r, axis_t = validated_pose(job["base_from_axis"], "base_from_axis")
    old_r, old_t = validated_pose(before["base_from_part_home"], "old mount")
    new_r, new_t = validated_pose(after["base_from_part_home"], "new mount")
    shift = new_r * old_r.inv()
    relative = (axis_r.inv() * shift * axis_r).as_rotvec()
    expected = shift.apply(old_t - axis_t) + axis_t
    if np.linalg.norm(relative[:2]) > 1e-7 or np.linalg.norm(expected - new_t) > 1e-7:
        return None
    return float(relative[2])


def delivered_sweep(trajectory: list[Row], receipts: Iterable[Row], issued_ns: int) -> DeliveredSweep | None:
    """Compare held requested and observed flow on each reconciled controller interval."""
    ticks = [row["t_ns"] for row in trajectory]
    intervals = []
    cut = 0
    for packet in receipts:
        rows = packet["samples"]
        for left, right in zip(rows, rows[1:]):
            measured = left["flow_ml_s"]
            start, end = left["t_ns"] - issued_ns, right["t_ns"] - issued_ns
            index = bisect_right(ticks, start) - 1
            if not (0 <= index < len(ticks) - 1 and start < end <= ticks[index + 1]):
                if measured <= 0:
                    continue
                return None
            commanded = trajectory[index]["flow_ml_s"]
            if commanded <= 0:
                if measured > 0:
                    return None
                continue
            intervals.append((start, end, commanded, measured))
            if measured > 0:
                cut = max(cut, end)

    observed = sorted(
        (measured / commanded, end - start)
        for start, end, commanded, measured in intervals if measured > 0
    )
    if not 0 < cut < ticks[-1] or not observed:
        return None
    # Use the upper quartile of elapsed wet delivery to estimate normal gain.
    # Dry samples and short runs of reduced delivery should not lower the repair target.
    wet_duration = sum(duration for _, duration in observed)
    elapsed = 0
    for gain, duration in observed:
        elapsed += duration
        if 4 * elapsed >= 3 * wet_duration:
            break
    if not 0 < gain <= 1.5:
        return None
    deficit_spans = tuple(sorted(
        (start, end, commanded - measured / gain)
        for start, end, commanded, measured in intervals
        if end <= cut and measured < .9 * gain * commanded
    ))
    return DeliveredSweep(cut, gain, deficit_spans)


def portion_at(trajectory: list[Row], tick: int) -> Row:
    """Recover exact positions and velocities of the issued polynomial at a cut."""
    times = [row["t_ns"] for row in trajectory]
    i = bisect_right(times, tick) - 1
    left, right = trajectory[i:i+2]
    length = right["t_ns"] - left["t_ns"]
    u = (tick - left["t_ns"]) / length
    dt = length * 1e-9
    q0, q1 = np.asarray(left["q_rad"]), np.asarray(right["q_rad"])
    v0, v1 = np.asarray(left["qd_rad_s"]), np.asarray(right["qd_rad_s"])
    a = -2 * (q1 - q0) + dt * (v0 + v1)
    b = 3 * (q1 - q0) - dt * (2 * v0 + v1)
    speed = (3 * a * u**2 + 2 * b * u) / dt + v0
    return {"t_ns": tick, "q_rad": hermite(left, right, u).tolist(),
            "qd_rad_s": speed.tolist(), "flow_ml_s": left["flow_ml_s"]}


def adjusted_suffix(trajectory: list[Row], cut: int, shift: float) -> list[Row]:
    """Trim the already observed path while expressing its continuation in the new index."""
    chosen = [portion_at(trajectory, cut), *(row for row in trajectory if row["t_ns"] > cut)]
    return [
        {**row, "t_ns": row["t_ns"] - cut, "q_rad": [*row["q_rad"][:6], row["q_rad"][6] - shift]}
        for row in chosen
    ]


def repair_spans(trajectory: list[Row], sweep: DeliveredSweep, shift: float) -> list[Row]:
    """Reuse the issued path with deficit flow before the cut and nominal flow after it."""
    deficits = {start: (end, flow) for start, end, flow in sweep.deficit_spans}
    first = sweep.deficit_spans[0][0]
    cut = sweep.cut_ns
    after_start = (row["t_ns"] for row in trajectory if row["t_ns"] >= first)
    boundaries = sorted({first, cut, *deficits, *(end for end, _ in deficits.values()), *after_start})
    repair_until = first
    repair_flow = 0.0
    rows = []
    for tick in boundaries:
        row = trajectory[-1] if tick == trajectory[-1]["t_ns"] else portion_at(trajectory, tick)
        repair_until, repair_flow = deficits.get(tick, (repair_until, repair_flow))
        if tick >= cut:
            flow = row["flow_ml_s"]
        else:
            flow = repair_flow if tick < repair_until else 0.0
        rows.append({**row, "t_ns": tick - first, "q_rad": [*row["q_rad"][:6], row["q_rad"][6] - shift],
                     "flow_ml_s": flow})
    return rows


def make_row(tick: int, q: np.ndarray, v: np.ndarray, flow: float = 0.0) -> Row:
    """Serialize one time-domain state and held flow value."""
    return {"t_ns": tick, "q_rad": q.tolist(), "qd_rad_s": v.tolist(), "flow_ml_s": flow}


def join_dry(motion: Motion, suffix: list[Row], guard: CollisionGuard) -> list[Row] | None:
    """Find a short dry bridge and final index move under public motion limits."""
    q_next = np.asarray(suffix[0]["q_rad"])
    v_next = np.asarray(suffix[0]["qd_rad_s"])
    q_end = np.asarray(suffix[-1]["q_rad"])
    v_end = np.asarray(suffix[-1]["qd_rad_s"])
    final = q_end.copy()
    final[6] = motion.final_angle
    ticks = motion.max_ticks - suffix[-1]["t_ns"] // motion.period_ns
    if ticks < 1:
        return None
    zero = np.zeros(7)
    tail = 0
    if not np.array_equal(q_end, final) or np.any(v_end):
        for duration in range(1, ticks):
            dt = motion.period_s * duration
            if not bounds_ok(q_end, final, v_end, zero, dt, *motion.bounds):
                continue
            probe = [make_row(0, q_end, v_end), make_row(duration * motion.period_ns, final, zero)]
            if guard.accepts(probe):
                tail = duration
                break
        if not tail:
            return None
    start = make_row(0, motion.start, motion.velocity_at_start)
    for bridge in range(1, ticks - tail + 1):
        dt = bridge * motion.period_s
        if not bounds_ok(motion.start, q_next, motion.velocity_at_start, v_next, dt, *motion.bounds):
            continue
        if not guard.accepts([start, make_row(bridge * motion.period_ns, q_next, v_next)]):
            continue
        rows = [start, *({**row, "t_ns": row["t_ns"] + bridge * motion.period_ns} for row in suffix)]
        if tail:
            rows.append(make_row(rows[-1]["t_ns"] + tail * motion.period_ns, final, zero))
        return rows
    return None


def predicted_flow(
    rows: list[Row], meter: CoatingDose, registration: dict, prior: MaterialState, gain: float,
) -> list[Row] | None:
    """Select an allowable continuation using delivered flow and already-coated area."""
    projected = [{**row, "flow_ml_s": gain * row["flow_ml_s"]} for row in rows]
    estimate, usable = meter.trace(projected, registration, prior=prior, verify_recipe=True)
    if not usable:
        return None
    change = estimate.part_dose_ml_m2 - prior.part_dose_ml_m2
    excess = estimate.off_target_ml - prior.off_target_ml
    allowed = meter.recipe["max_off_target_ml"] * .95 - prior.off_target_ml
    peak = max(row["flow_ml_s"] for row in rows)
    maximum = min(1.5, allowed / max(excess, 1e-12), meter.recipe["max_flow_ml_s"] / peak)
    if maximum <= 0.0:
        return None
    candidates = np.unique(np.r_[np.linspace(.4 * maximum, maximum, 30), min(1.0, maximum)])
    best: tuple[float, float] | None = None
    for factor in candidates:
        result = MaterialState(prior.part_dose_ml_m2 + factor * change, prior.off_target_ml + factor * excess)
        if meter.qualifies(result):
            claim = (meter.coverage(result) - .02 * float(factor), float(factor))
            best = claim if best is None or claim > best else best
    if best is None:
        return None
    return [{**row, "flow_ml_s": best[1] * row["flow_ml_s"]} for row in rows]


def _try_suffix(
    suffix: list[Row], motion: Motion, guard: CollisionGuard, meter: CoatingDose,
    registration: dict, prior: MaterialState, gain: float,
) -> list[Row] | None:
    """Qualify a residual sweep and attach the dry moves from rest and to final angle.

    The suffix is in the current mounting frame with times relative to the
    interrupted cut. A dry interval can take a detour around the current
    world geometry before the approach and departure are checked. Return a
    new trajectory with adjusted flow if it meets clearance and joint limits,
    fits the deadline, and is predicted to qualify with measured prior dose.
    """
    for left, right in zip(suffix, suffix[1:]):
        dt = (right["t_ns"] - left["t_ns"]) * 1e-9
        if not bounds_ok(np.asarray(left["q_rad"]), np.asarray(right["q_rad"]),
                         np.asarray(left["qd_rad_s"]), np.asarray(right["qd_rad_s"]), dt, *motion.bounds):
            return None
    if not guard.accepts(suffix):
        suffix = bypass_dry_intervals(suffix, motion, guard)
        if suffix is None:
            return None
    rows = join_dry(motion, suffix, guard)
    return None if rows is None else predicted_flow(rows, meter, registration, prior, gain)


def _orbit_offsets(suffix: list[Row], motion: Motion) -> list[float]:
    """Return nearby table shifts in radians within necessary position and time bounds.

    The remaining time outside the suffix limits total table travel to its
    entry and from its exit. Use that bound and the joint headroom to sample
    both sides of the nominal sweep, with finer spacing around zero. The
    actual bridge and return are checked separately, including acceleration.
    """
    angles = [row["q_rad"][6] for row in suffix]
    seconds = motion.max_ticks * motion.period_s - suffix[-1]["t_ns"] * 1e-9
    travel = motion.velocity[6] * seconds
    entry_shift = motion.start[6] - angles[0]
    exit_shift = motion.final_angle - angles[-1]
    if travel <= 0.0 or travel < abs(entry_shift - exit_shift):
        return []
    # |offset - entry_shift| + |offset - exit_shift| <= travel.
    midpoint = (entry_shift + exit_shift) / 2.0
    low = max(motion.lower[6] - min(angles), midpoint - travel / 2.0)
    high = min(motion.upper[6] - max(angles), midpoint + travel / 2.0)
    offsets = set()
    for sign, start, end in ((1.0, low, high), (-1.0, -high, -low)):
        start = max(start, 0.0)
        if end <= 0.0 or start > end:
            continue
        local_step = .04
        local_end = min(end, 8 * local_step)
        local = [i * local_step for i in range(1, 9) if start <= i * local_step <= local_end]
        distant = np.linspace(max(start, local_end), end, 6) if end > local_end else []
        offsets.update(sign * float(angle) for angle in (*local, *distant, start, end) if angle > 1e-8)
    return sorted(offsets, key=lambda angle: (abs(angle), -angle))


def _rotate_suffix(
    suffix: list[Row], offset: float, arm: SerialArm, motion: Motion,
    axis_rotation: Rotation, axis_translation: np.ndarray,
) -> list[Row]:
    """Rotate the table and nozzle together while keeping part-relative spray geometry.

    For each knot, solve arm IK for the rotated nozzle point and direction,
    and use its Jacobian to rotate the two derivatives. Preserve the timed
    flow and table rates. An unreachable IK target raises ValueError for the
    search to skip. The caller checks exact polynomial limits and clearance.
    """
    rotation = axis_rotation * Rotation.from_rotvec([0.0, 0.0, offset]) * axis_rotation.inv()
    retargeted = []
    seed = np.asarray(suffix[0]["q_rad"][:6])
    for row in suffix:
        q = np.asarray(row["q_rad"])
        speed = np.asarray(row["qd_rad_s"])
        point, direction, point_jacobian, direction_jacobian = arm.nozzle(q[:6])
        target = axis_translation + rotation.apply(point - axis_translation)
        seed = arm.inverse(target, rotation.apply(direction), seed, motion.lower[:6], motion.upper[:6])
        _, _, retargeted_point, retargeted_direction = arm.nozzle(seed)
        target_speed = np.r_[rotation.apply(point_jacobian @ speed[:6]),
                             rotation.apply(direction_jacobian @ speed[:6])]
        rates = np.linalg.lstsq(np.vstack((retargeted_point, retargeted_direction)), target_speed, rcond=1e-7)[0]
        retargeted.append(make_row(row["t_ns"], np.r_[seed, q[6] + offset], np.r_[rates, speed[6]], row["flow_ml_s"]))
    return retargeted


def resume_tail(
    job: dict, registration: dict, start_velocity: list[float], prior: MaterialState, authority: Mapping[str, Any],
    receipts: Iterable[Row],
) -> dict | None:
    """Try a direct or coordinated continuation from the measured coating cut.

    Receipts belong to the interrupted authority; job and registration
    describe the current world, mount, measured stop and time remaining.
    Try the direct suffix first, then repair earlier delivery deficits. If the
    current world obstructs those paths, search table offsets. Return None
    when the broader residual planner must find a fresh geometric path.
    """
    source = authority["trajectory"]
    sweep = delivered_sweep(source, receipts, authority["issued_ns"])
    shift = nozzle_epoch_offset(job, authority["registration"], registration)
    if sweep is None or shift is None:
        return None
    suffix = adjusted_suffix(source, sweep.cut_ns, shift)
    options = [suffix] if any(row["flow_ml_s"] > 0 for row in suffix) else []
    if sweep.deficit_spans:
        options.append(repair_spans(source, sweep, shift))
    meter = CoatingDose(job)
    motion = parse_motion(job, meter.arm, True, start_velocity)
    mounted = validated_pose(registration["base_from_part_home"], "base_from_part_home")
    guard = CollisionGuard(meter.arm, meter.workpiece, mounted, motion.clearance)
    for rows in options:
        accepted = _try_suffix(rows, motion, guard, meter, registration, prior, sweep.gain)
        if accepted is not None:
            return {"status": "ready", "trajectory": accepted}
    workpiece = meter.workpiece
    if not workpiece.world:
        return None
    for rows in options:
        for offset in _orbit_offsets(rows, motion):
            try:
                rotated = _rotate_suffix(rows, offset, meter.arm, motion,
                                         workpiece.axis_rotation, workpiece.axis_translation)
            except ValueError:
                continue
            accepted = _try_suffix(rotated, motion, guard, meter, registration, prior, sweep.gain)
            if accepted is not None:
                return {"status": "ready", "trajectory": accepted}
    return None
