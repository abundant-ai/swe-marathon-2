"""Replay a submitted offline plan against independent geometry and process evidence."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from coating_scene import CoatingScene, Pose, rigid_pose
from native_arm import NativeArm
from process_trace import ProcessTrace, TraceEvidence
from scene_clearance import SceneClearance
from swept_clearance import certify_clearance
from trajectory import Knot, Segment, parse_knots, segments


@dataclass(frozen=True)
class OfflineEvidence:
    """Physical observations and validation outcome for one planned trajectory."""

    status: Literal["qualified", "invalid", "blocked", "unresolved"]
    explanations: tuple[str, ...]
    process: TraceEvidence | None = None
    minimum_sampled_clearance_m: float | None = None
    clearance_samples: int = 0


def rotating_radius(scene: CoatingScene, home: Pose) -> float:
    """Bound the distance to the positioner axis for each moving surface point."""
    axis_from_part = scene.axis_from_base @ home
    surfaces = [(scene.part, axis_from_part)]
    surfaces.extend((fixture.mesh, fixture.world_from_body) for fixture in scene.fixtures)
    maximum = 0.0
    for mesh, pose in surfaces:
        vertices = mesh.vertices @ pose[:3, :3].T + pose[:3, 3]
        maximum = max(maximum, float(np.max(np.linalg.norm(vertices[:, :2], axis=1))))
    return maximum


def arm_lever_bound(arm: NativeArm) -> float:
    """Bound each revolute lever using the total translation budget of the native arm."""
    model = arm.model
    link_reach = np.linalg.norm(model.body_pos, axis=1).sum()
    largest_shape = max(
        np.linalg.norm(model.geom_pos[record.geom_id]) + model.geom_rbound[record.geom_id]
        for record in arm.arm_geoms
    )
    return float(link_reach + largest_shape)


def validated_knots(
    job: Mapping[str, Any], plan: Mapping[str, Any], *, coordinated: bool,
) -> tuple[Knot, ...]:
    """Validate command timing, complete start/finish state, and fixed-axis semantics."""
    motion = job["motion"]
    knots = parse_knots(plan.get("trajectory"), motion["control_period_ns"], job["recipe"]["max_flow_ml_s"])
    start, finish = knots[0], knots[-1]
    if start.t_ns != 0 or start.q_rad != tuple(job["start_q_rad"]) or any(start.qd_rad_s):
        raise ValueError("Plan must start from the specified measured configuration at rest and time zero.")
    if (finish.t_ns > motion["max_duration_ns"] or finish.q_rad[6] != job["final_positioner_rad"]
            or any(finish.qd_rad_s)):
        raise ValueError("Plan must finish within the duration at rest and at the requested positioner angle.")
    if not coordinated and any(knot.q_rad[6] != start.q_rad[6] or knot.qd_rad_s[6] for knot in knots):
        raise ValueError("Fixed-positioner plan changes the seventh axis.")
    return knots


def joint_violations(
    motion: Mapping[str, Any], arm: NativeArm, polynomials: tuple[Segment, ...],
) -> list[str]:
    """Detect violations of motion and robot limits, including interior extrema."""
    lower = [max(job, robot) for job, robot in zip(motion["lower_rad"], (*arm.lower_rad, -np.inf), strict=True)]
    upper = [min(job, robot) for job, robot in zip(motion["upper_rad"], (*arm.upper_rad, np.inf), strict=True)]
    speed = [
        min(job, robot) for job, robot in zip(motion["max_velocity_rad_s"], (*arm.max_velocity_rad_s, np.inf), strict=True)
    ]
    failures: set[str] = set()
    for segment in polynomials:
        for index, bound in enumerate(segment.bounds()):
            if bound.lower_rad < lower[index] - 1e-9 or bound.upper_rad > upper[index] + 1e-9:
                failures.add(f"Continuous position limit on wire axis {index + 1}.")
            if bound.max_speed_rad_s > speed[index] + 1e-9:
                failures.add(f"Continuous speed limit on wire axis {index + 1}.")
            if bound.max_acceleration_rad_s2 > motion["max_acceleration_rad_s2"][index] + 1e-9:
                failures.add(f"Continuous acceleration limit on wire axis {index + 1}.")
    return sorted(failures)


def audit_offline(
    job: Mapping[str, Any], registration: Mapping[str, Any], plan: Mapping[str, Any], *,
    urdf: Path, srdf: Path, coordinated: bool, max_process_step_ns: int = 5_000_000,
    max_cell_edge_m: float = 0.004,
) -> OfflineEvidence:
    """Measure a planned coating pass without reading the candidate's predicted dose.

    Args:
        job: Trusted job, including geometry and public recipe limits.
        registration: Trusted alignment received by the candidate planner.
        plan: Submitted JSON output for plan-pass or plan-coordinated.
        urdf: Verifier-owned robot model path.
        srdf: Verifier-owned self-collision manifest path.
        coordinated: Allow the seventh axis to move when true.
        max_process_step_ns: Independent process quadrature upper time step.
        max_cell_edge_m: Upper spatial quadrature edge length in metres.

    Returns:
        Case evidence. A blocked response is reported for the case author to
        compare with independent feasibility. Unresolved clearance remains
        separate from an observed submitted motion violation.
    """
    if plan.get("job_id") != job["job_id"] or plan.get("scene_revision") != job["scene_revision"]:
        return OfflineEvidence("invalid", ("Plan identity does not match the requested scene.",))
    if plan.get("status") == "blocked" and plan.get("trajectory") == []:
        return OfflineEvidence("blocked", ())
    if plan.get("status") != "ready" or registration.get("status") != "registered":
        return OfflineEvidence("invalid", ("Plan requires a registered scene and a known status.",))
    try:
        knots = validated_knots(job, plan, coordinated=coordinated)
    except ValueError as error:
        return OfflineEvidence("invalid", (str(error),))
    scene = CoatingScene.from_job(job)
    home = rigid_pose(registration["base_from_part_home"])
    model = job["robot_model"]
    arm = NativeArm(urdf, srdf, model["arm_joints"], model["tool_frame"])
    motion = job["motion"]
    polynomials = tuple(segments(knots))
    findings = joint_violations(motion, arm, polynomials)
    if findings:
        return OfflineEvidence("invalid", tuple(findings))

    plant = SceneClearance(arm)
    fixture_radius = rotating_radius(scene, home)
    arm_bound = (arm_lever_bound(arm),) * 6

    def measured_distance(q: tuple[float, ...]) -> float:
        """Measure robot self- and external separation at one configuration."""
        arm.set_q(q[:6])
        return plant.at(scene.place(q[6], home))

    clearance = [
        certify_clearance(segment, measured_distance, motion["min_clearance_m"], arm_bound, fixture_radius)
        for segment in polynomials
    ]
    minimum = min(item.minimum_sample_m for item in clearance)
    samples = sum(item.samples for item in clearance)
    if any(item.status == "violation" for item in clearance):
        return OfflineEvidence("invalid", ("Observed a continuous-path clearance violation.",), None, minimum, samples)
    if any(item.status == "unresolved" for item in clearance):
        return OfflineEvidence("unresolved", ("Continuous clearance could not be established.",), None, minimum, samples)

    trace = ProcessTrace(scene, job["target_faces"], job["recipe"], max_cell_edge_m=max_cell_edge_m)
    trace.append(arm, knots, home, max_step_ns=max_process_step_ns)
    process = trace.evidence()
    if process.enabled_samples == 0 or process.off_recipe_samples:
        findings.append("The enabled nozzle motion must stay within the public process window.")
    if not process.dose.qualified:
        findings.append("Measured target dose or off-target volume is outside the public bounds.")
    return OfflineEvidence("invalid" if findings else "qualified", tuple(findings), process, minimum, samples)
