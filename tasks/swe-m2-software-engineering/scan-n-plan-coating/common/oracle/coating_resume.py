"""Repair a stopped coating sweep from its measured delivered prefix."""

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np

from coating_planner import (
    CoatingDose, CollisionGuard, MaterialState, Motion, bounds_ok, hermite, parse_motion, validated_pose,
)

Row = dict[str, Any]


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


def delivered_cut(trajectory: list[Row], receipts: Iterable[Row], issued_ns: int) -> tuple[int, float] | None:
    """Find the last positively measured half-open interval and its observed flow factor."""
    ticks = [row["t_ns"] for row in trajectory]
    delivered = expected = 0.0
    cut = 0
    for packet in receipts:
        rows = packet["samples"]
        for left, right in zip(rows, rows[1:]):
            measured = left["flow_ml_s"]
            if measured <= 0:
                continue
            midpoint = (left["t_ns"] + right["t_ns"]) / 2 - issued_ns
            index = bisect_right(ticks, midpoint) - 1
            if not 0 <= index < len(ticks) - 1:
                return None
            seconds = (right["t_ns"] - left["t_ns"]) * 1e-9
            delivered += measured * seconds
            expected += trajectory[index]["flow_ml_s"] * seconds
            cut = max(cut, right["t_ns"] - issued_ns)
    if not 0 < cut < ticks[-1] or not 0 < delivered <= expected * 1.5:
        return None
    return cut, delivered / expected


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


def resume_tail(
    job: dict, registration: dict, start_velocity: list[float], prior: MaterialState, authority: Mapping[str, Any],
    receipts: Iterable[Row],
) -> dict | None:
    """Try a collision-cleared continuation and verify its cumulative process prediction.

    A non-axial remount, incomplete trace, or unsuitable tail leaves the
    broader residual planner responsible for finding a fresh geometric path.
    """
    source = authority["trajectory"]
    cut_data = delivered_cut(source, receipts, authority["issued_ns"])
    shift = nozzle_epoch_offset(job, authority["registration"], registration)
    if cut_data is None or shift is None:
        return None
    cut, gain = cut_data
    suffix = adjusted_suffix(source, cut, shift)
    if not any(row["flow_ml_s"] > 0 for row in suffix):
        return None
    meter = CoatingDose(job)
    motion = parse_motion(job, meter.arm, True, start_velocity)
    mounted = validated_pose(registration["base_from_part_home"], "base_from_part_home")
    guard = CollisionGuard(meter.arm, meter.workpiece, mounted, motion.clearance)
    for left, right in zip(suffix, suffix[1:]):
        dt = (right["t_ns"] - left["t_ns"]) * 1e-9
        if not bounds_ok(np.asarray(left["q_rad"]), np.asarray(right["q_rad"]),
                         np.asarray(left["qd_rad_s"]), np.asarray(right["qd_rad_s"]), dt, *motion.bounds):
            return None
    if not guard.accepts(suffix):
        return None
    rows = join_dry(motion, suffix, guard)
    if rows is None:
        return None
    accepted = predicted_flow(rows, meter, registration, prior, gain)
    if accepted is None:
        return None
    return {"status": "ready", "trajectory": accepted}
