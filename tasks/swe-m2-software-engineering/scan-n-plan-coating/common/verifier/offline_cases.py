"""Author curved workpieces, process recipes, and reachability checks."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import cos, sin
from typing import Any

import numpy as np

from coating_scene import rigid_pose, rotate_z


@dataclass(frozen=True)
class OfflineCase:
    """Private expected outcome for one public offline job and survey report."""

    name: str
    stage: int
    job: dict[str, Any]
    registration: dict[str, Any]
    expectation: str
    proof: dict[str, float] | None = None


@dataclass(frozen=True)
class Panel:
    """Authored dimensional and mounting variation for a coating job."""

    job_id: str
    sector_rad: float
    radius_m: float
    z_m: float
    target_half_angle_rad: float
    target_height_m: float
    shoulder_rad: float
    elbow_rad: float
    process_angle_rad: float
    seed_direction: int = 1


_FLANGE = Panel("lot-5938", .16, .869, .254, .184, .031, -.62, 1.30, .19)
_RETURN = Panel("lot-7937", -.43, .844, .275, .173, .028, -.72, 1.42, -.27, -1)
_MOVING_FLANGE = Panel("lot-6348", .28, .865, .259, .183, .031, -.64, 1.31, .23)
_MOVING_RETURN = Panel("lot-5729", -.37, .841, .274, .175, .030, -.72, 1.43, -.17, -1)
_PUBLIC = Panel("coating-preview", .39, .875, .245, .177, .029, -.60, 1.30, .12)

_ARM_JOINTS = ["turret_yaw", "shoulder_pitch", "elbow_pitch", "wrist_roll", "wrist_pitch", "nozzle_roll"]
_ARM_SPEED = [2.4, 2.2, 2.5, 3.0, 3.0, 4.0]
_START_INDEX_OFFSET = 1.43
_ROTARY_TRAVEL = .56


def _pose(heading: float, xyz: np.ndarray | list[float]) -> dict[str, Any]:
    return {
        "translation_m": np.asarray(xyz).tolist(),
        "quaternion_xyzw": [0., 0., sin(heading / 2), cos(heading / 2)],
    }


def _act(matrix: np.ndarray, xyz: np.ndarray) -> np.ndarray:
    return xyz @ matrix[:3, :3].T + matrix[:3, 3]


def _labelled_shell(panel: Panel, base_from_part: np.ndarray) -> tuple[dict[str, Any], list[int]]:
    """Build a watertight curved panel with separate target and masked face IDs."""
    half = panel.target_half_angle_rad
    theta = panel.sector_rad + np.concatenate([
        np.linspace(-.288, -half, 5, endpoint=False),
        np.linspace(-half, half, 18, endpoint=False),
        np.linspace(half, .284, 6),
    ])
    lower, upper = -.5 * panel.target_height_m, .5 * panel.target_height_m
    heights = panel.z_m + np.array([-.052, -.029, lower, 0., upper, .034, .061])
    n_a, n_z = len(theta), len(heights)
    vertices = np.array([[radius * cos(angle), radius * sin(angle), height]
                         for radius in [panel.radius_m, panel.radius_m + .014]
                         for angle in theta for height in heights])
    triangles, targets = [], []

    def idx(r, a, z):
        return (r * n_a + a) * n_z + z

    def add(corners, normal, coat=False):
        for offsets in ((0, 1, 2), (0, 2, 3)):
            a, b, c = [corners[k] for k in offsets]
            if np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a]) @ normal < 0:
                b, c = c, b
            if coat:
                targets.append(len(triangles))
            triangles.append([a, b, c])

    for a in range(n_a - 1):
        middle = (theta[a] + theta[a + 1]) / 2
        radial = np.array([cos(middle), sin(middle), 0.])
        for z in range(n_z - 1):
            for side, sign in ((0, -1), (1, 1)):
                coat = side == 0 and abs(middle - panel.sector_rad) < half and z in (2, 3)
                add([idx(side, a, z), idx(side, a + 1, z),
                     idx(side, a + 1, z + 1), idx(side, a, z + 1)], sign * radial, coat)
        for z, sign in ((0, -1), (n_z - 1, 1)):
            add([idx(0, a, z), idx(1, a, z), idx(1, a + 1, z), idx(0, a + 1, z)], [0., 0., sign])
    for a, sign in ((0, -1), (n_a - 1, 1)):
        side_normal = sign * np.array([-sin(theta[a]), cos(theta[a]), 0.])
        for z in range(n_z - 1):
            add([idx(0, a, z), idx(1, a, z), idx(1, a, z + 1), idx(0, a, z + 1)], side_normal)
    return {"vertices_m": _act(np.linalg.inv(base_from_part), vertices).tolist(), "triangles": triangles}, targets


def _jaw(center: list[float], heading: float) -> dict[str, Any]:
    mesh = {"vertices_m": [[x, y, z] for x in (-.012, .012) for y in (-.021, .021) for z in (-.048, .048)],
            "triangles": [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                          [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]}
    return {"mesh": mesh, "pose": _pose(heading, center)}


def _requested_job(panel: Panel, stage: int) -> tuple[dict[str, Any], dict[str, Any]]:
    turn = stage == 3
    park_offset = .69 if turn else panel.target_half_angle_rad + .055
    park = panel.sector_rad - panel.seed_direction * park_offset
    first_index = final_index = panel.process_angle_rad
    if turn:
        first_index -= panel.seed_direction * _START_INDEX_OFFSET
        final_index += panel.seed_direction * _ROTARY_TRAVEL
    # The positioner mounts beside the workpiece. The calibrated positioner
    # axis differs from both the robot base origin and the part survey frame.
    sector = rotate_z(panel.sector_rad)
    axis_origin = _act(sector, np.array([panel.radius_m + .027, -.032 * panel.seed_direction, panel.z_m - .023]))
    axis_yaw = panel.sector_rad - .27 * panel.seed_direction
    axis = rigid_pose(_pose(axis_yaw, axis_origin))
    surveyed_xyz = _act(sector, np.array([panel.radius_m - .007, .012, panel.z_m]))
    surveying_yaw = panel.sector_rad + .23 * panel.seed_direction
    surveyed_pose = _pose(surveying_yaw, surveyed_xyz)
    surveyed = rigid_pose(surveyed_pose)
    processed = axis @ rotate_z(panel.process_angle_rad) @ np.linalg.inv(axis) @ surveyed
    panel_wire, target_faces = _labelled_shell(panel, processed)

    # Jaw frames are calibrated to the positioner rather than to the part.
    # At the process index the brackets sit behind the concave coating face.
    jaw_centers = [_act(sector, np.array([panel.radius_m + .069, side * .153, panel.z_m]))
                   for side in (-1, 1)]
    fixture_from_base = np.linalg.inv(axis @ rotate_z(panel.process_angle_rad))
    fixture_heading = panel.sector_rad - axis_yaw - panel.process_angle_rad
    fixtures = [{"id": f"clamp-{index}", **_jaw(_act(fixture_from_base, center).tolist(), fixture_heading)}
                for index, center in enumerate(jaw_centers)]

    shoulder, elbow = panel.shoulder_rad, panel.elbow_rad
    job = {
        "job_id": panel.job_id,
        "part_mesh": panel_wire,
        "base_from_axis": _pose(axis_yaw, axis_origin),
        "registration": {
            "initial_base_from_part_home": _pose(surveying_yaw + .07, surveyed_xyz + [.016, .012, -.010]),
            "search_translation_m": .110, "search_rotation_rad": .45,
            "translation_tolerance_m": .014, "rotation_tolerance_rad": .060,
            "scan_match_tolerance_m": .0028, "min_scan_inlier_fraction": .86,
        },
        "robot_model": {"urdf_path": "/app/examples/cell/arm.urdf", "srdf_path": "/app/examples/cell/arm.srdf",
                        "arm_joints": _ARM_JOINTS.copy(), "tool_frame": "tool_tip"},
        "fixture_collision": fixtures,
        "world_collision": [],
        "target_faces": target_faces,
        "masked_faces": sorted(set(range(len(panel_wire["triangles"]))) - set(target_faces)),
        "start_q_rad": [park, shoulder, elbow, 0., -(shoulder + elbow), 0., first_index],
        "final_positioner_rad": final_index,
        "scene_revision": 4 if panel.seed_direction == 1 else 7,
        "motion": {
            "lower_rad": [-2.25, shoulder - .115, elbow - .12, -1.65, -1.55, -2.30, -2.10],
            "upper_rad": [2.25, shoulder + .105, elbow + .18, 1.65, .33, 2.30, 2.10],
            "max_velocity_rad_s": [*_ARM_SPEED, .55],
            "max_acceleration_rad_s2": [2.25, 2.25, 2.45, 3.25, 3.25, 3.25, 1.65],
            "min_clearance_m": .0115,
            "control_period_ns": 20_000_000,
            "max_duration_ns": 9_500_000_000 if turn else 3_900_000_000,
        },
        "recipe": {
            "standoff_m": [.182, .225], "surface_speed_mps": [.158, .237], "max_normal_error_rad": .054,
            "cone_half_angle_rad": .100, "max_flow_ml_s": 1.38,
            "target_dose_ml_m2": [78., 248.], "min_covered_fraction": .88, "max_off_target_ml": .36,
        },
    }
    registration = {"job_id": panel.job_id, "capture_epoch": f"{panel.job_id}-mount",
                    "status": "registered", "base_from_part_home": surveyed_pose, "capture_ids": ["survey-a", "survey-b"]}
    return job, registration


def _horizontal_tool_limit(job: dict[str, Any]) -> float:
    """Overestimate horizontal tool reach for the supplied six-axis cell model.

    The upper arm contributes .34 m, followed by the .27 m forearm and .07 m
    wrist-roll offset on the same line. Allow the full .05 m wrist pitch offset
    and .074 m nozzle in any direction. The turret and shoulder origins are
    on the world Z axis and do not add planar radius.
    """
    lower = job["motion"]["lower_rad"]
    upper = job["motion"]["upper_rad"]

    def horizontal_component(lo: float, hi: float) -> float:
        # These commissioned intervals are strictly within ±π/2.
        assert -np.pi / 2 <= lo <= hi <= np.pi / 2
        return cos(float(np.clip(0., lo, hi)))

    return (.34 * horizontal_component(lower[1], upper[1])
            + .34 * horizontal_component(lower[1] + lower[2], upper[1] + upper[2]) + .124)


def _no_locked_start_spray(job: dict[str, Any], registration: dict[str, Any], heading: float) -> dict[str, float]:
    """Compare per-face required nozzle projection with the joint envelope."""
    axis = rigid_pose(job["base_from_axis"])
    home = rigid_pose(registration["base_from_part_home"])
    pose = axis @ rotate_z(job["start_q_rad"][6]) @ np.linalg.inv(axis) @ home
    mesh = job["part_mesh"]
    vertices = _act(pose, np.asarray(mesh["vertices_m"]))
    target = vertices[np.asarray(mesh["triangles"])[job["target_faces"]]]
    normals = np.cross(target[:, 1] - target[:, 0], target[:, 2] - target[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    radial = np.array([cos(heading), sin(heading), 0.])
    displacement = 2 * sin(job["recipe"]["max_normal_error_rad"] / 2)
    max_projection = np.clip(-normals @ radial + displacement, 0., 1.)
    required = float(np.min((target @ radial).min(axis=1) - job["recipe"]["standoff_m"][1] * max_projection))
    maximum = _horizontal_tool_limit(job)
    return {"required_tool_projection_m": required, "maximum_tool_radius_m": maximum,
            "locked_start_unreachable_margin_m": required - maximum}


def _positive(panel: Panel, stage: int, name: str) -> OfflineCase:
    job, registration = _requested_job(panel, stage)
    proof = _no_locked_start_spray(job, registration, panel.sector_rad) if stage == 3 else None
    if proof is not None and proof["locked_start_unreachable_margin_m"] <= 0:
        raise ValueError(f"The authored start orientation permits a coating axis in {name}")
    return OfflineCase(name, stage, job, registration, "qualified", proof)


def _blocked(positive: OfflineCase) -> OfflineCase:
    """Place all target points beyond nozzle-and-standoff reach at any angle."""
    job, registration = deepcopy(positive.job), deepcopy(positive.registration)
    job["job_id"] += "-remote"
    registration["job_id"] = job["job_id"]
    origin = np.asarray(job["base_from_axis"]["translation_m"])
    shift = origin.copy()
    shift[2] = 0.
    shift *= .53 / np.linalg.norm(shift)
    for pose in (job["base_from_axis"], registration["base_from_part_home"],
                 job["registration"]["initial_base_from_part_home"]):
        pose["translation_m"] = (np.array(pose["translation_m"]) + shift).tolist()
    axis, home = rigid_pose(job["base_from_axis"]), rigid_pose(registration["base_from_part_home"])
    mesh = job["part_mesh"]
    vertices = np.asarray(mesh["vertices_m"])
    target_vertices = np.unique(np.asarray(mesh["triangles"])[job["target_faces"]])
    fixture_points = _act(np.linalg.inv(axis) @ home, vertices[target_vertices])
    target_radius = np.linalg.norm(axis[:2, 3]) - float(np.max(np.linalg.norm(fixture_points[:, :2], axis=1)))
    max_range = .804 + job["recipe"]["standoff_m"][1]
    margin = float(target_radius - max_range)
    if margin <= 0:
        raise ValueError("The remote part is too close to establish an unreachable job")
    proof = {"minimum_target_radius_m": float(target_radius), "maximum_nozzle_hit_radius_m": max_range,
             "unreachable_margin_m": margin}
    return OfflineCase("remote-fixture-outside-tool-and-standoff-reach", positive.stage,
                       job, registration, "blocked", proof)


def offline_cases(stage: int) -> tuple[OfflineCase, ...]:
    """Return exactly one stage's positives, physical refusal and malformed input."""
    if stage == 2:
        first = _positive(_FLANGE, stage, "coat-trimmed-flange-at-fixed-index")
        second = _positive(_RETURN, stage, "coat-narrow-raised-return-reverse")
    elif stage == 3:
        first = _positive(_MOVING_FLANGE, stage, "turn-flange-out-of-inaccessible-start")
        second = _positive(_MOVING_RETURN, stage, "reverse-rotary-reach-to-raised-return")
    else:
        raise ValueError("Offline coating cases are available for stages 2 and 3")
    invalid_registration = deepcopy(first.registration) | {"job_id": "different-mounted-part"}
    return first, second, _blocked(second), OfflineCase(
        "reject-registration-for-another-job", stage, deepcopy(first.job), invalid_registration, "malformed"
    )


def public_motion_sample() -> tuple[dict[str, Any], dict[str, Any]]:
    """Provide independent preview geometry in the same wire layout."""
    return _requested_job(_PUBLIC, 2)
