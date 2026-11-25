"""Deterministic private geometry and independent checks for part registration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from sys import float_info
from typing import Any

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation


@dataclass(frozen=True)
class RegistrationCase:
    """A public request and its private physical expectation."""

    name: str
    job: dict[str, Any]
    scans: dict[str, Any]
    expectation: str
    truth: dict[str, Any] | None = None
    alternatives: tuple[dict[str, Any], ...] = ()


def _pose(rotation: Rotation, translation: np.ndarray | list[float]) -> dict[str, Any]:
    return {
        "translation_m": np.asarray(translation).tolist(),
        "quaternion_xyzw": rotation.as_quat().tolist(),
    }


def _read_pose(pose: dict[str, Any]) -> tuple[Rotation, np.ndarray]:
    return Rotation.from_quat(pose["quaternion_xyzw"]), np.asarray(pose["translation_m"])


def _turned_part(
    axis: tuple[Rotation, np.ndarray], home: tuple[Rotation, np.ndarray], angle: float
) -> tuple[Rotation, np.ndarray]:
    axis_rotation, axis_origin = axis
    home_rotation, home_origin = home
    turn = axis_rotation * Rotation.from_rotvec([0., 0., angle]) * axis_rotation.inv()
    return turn * home_rotation, axis_origin + turn.apply(home_origin - axis_origin)


def _convex_mesh(vertices: np.ndarray) -> dict[str, Any]:
    """Triangulate the authored shape and orient each facet outwards."""
    center = vertices.mean(axis=0)
    faces = []
    for indices in ConvexHull(vertices).simplices:
        a, b, c = sorted(int(index) for index in indices)
        normal = np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a])
        face = [a, b, c] if normal @ (vertices[a] - center) > 0. else [a, c, b]
        faces.append(face)
    return {"vertices_m": vertices.tolist(), "triangles": sorted(faces)}


def _fairing(mirrored: bool) -> dict[str, Any]:
    # A chamfered flange with a raised, sloping shoulder and keyed corner.
    vertices = np.array([
        [-.188, -.088, -.073], [-.132, -.151, -.073], [.119, -.151, -.073],
        [.188, -.087, -.073], [.177, .106, -.073], [.088, .148, -.073],
        [-.152, .130, -.073], [-.189, .047, -.073], [-.157, -.087, .021],
        [-.110, -.116, .069], [.099, -.114, .098], [.158, -.076, .062],
        [.142, .101, .039], [.066, .113, .105], [-.092, .099, .091],
        [-.144, .034, .058],
    ])
    if mirrored:
        vertices *= [-.91, 1.07, 1.13]
        vertices[12:15, 0] += .026
        vertices[8:12, 2] += .018
    return _convex_mesh(vertices)


def _square_hub() -> dict[str, Any]:
    # The asymmetric height profile fixes the vertical direction while the
    # machined square geometry leaves the azimuth undetermined modulo 90°.
    rings = [(.128, -.074), (.128, .018), (.096, .087)]
    vertices = np.array([[x * radius, y * radius, z] for radius, z in rings
                         for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]])
    return _convex_mesh(vertices)


def _camera(
    axis: tuple[Rotation, np.ndarray], angle: float, sector: float, height: float, roll: float
) -> tuple[Rotation, np.ndarray]:
    """Aim a commissioned scanner at the nominal fixture, independent of the part pose."""
    axis_rotation, axis_origin = axis
    turn = angle + sector
    camera_origin = axis_origin + axis_rotation.apply([.72 * np.cos(turn), .72 * np.sin(turn), height])
    sight = axis_origin + axis_rotation.apply([.017, -.026, .111]) - camera_origin
    forward = sight / np.linalg.norm(sight)
    right = np.cross(forward, axis_rotation.apply([0., 0., 1.]))
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    orientation = Rotation.from_matrix(np.column_stack([right, down, forward]))
    return orientation * Rotation.from_rotvec([0., 0., roll]), camera_origin


def _capture(
    mesh: dict[str, Any], axis: tuple[Rotation, np.ndarray], home: tuple[Rotation, np.ndarray],
    name: str, view: tuple[float, float, float, float], rng: np.random.Generator,
    *, count: int, noise_m: float, outliers: int,
) -> dict[str, Any]:
    angle, sector, height, roll = view
    camera_rotation, camera_origin = _camera(axis, angle, sector, height, roll)
    part_rotation, part_origin = _turned_part(axis, home, angle)
    faces = np.asarray(mesh["vertices_m"])[mesh["triangles"]]
    normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
    part_camera = part_rotation.inv().apply(camera_origin - part_origin)
    visible = np.einsum("ij,ij->i", normals, part_camera - faces[:, 0]) > 0.
    # Each outward-facing triangle of a convex part has an unobstructed
    # view. Sample by area, then crop in the camera's actual viewing frame.
    weights = np.linalg.norm(normals[visible], axis=1)
    sample = rng.choice(faces[visible].shape[0], count * 9, p=weights / weights.sum())
    triangles = faces[visible][sample]
    u, v = rng.uniform(size=(2, len(sample)))
    root = np.sqrt(u)
    points_part = ((1. - root)[:, None] * triangles[:, 0]
                   + (root * (1. - v))[:, None] * triangles[:, 1]
                   + (root * v)[:, None] * triangles[:, 2])
    points_camera = camera_rotation.inv().apply(part_rotation.apply(points_part) + part_origin - camera_origin)
    depth = points_camera[:, 2]
    view_coordinates = points_camera[:, :2] / depth[:, None]
    inside = ((depth > 0.) & (np.abs(view_coordinates[:, 0] - .015) < .233)
              & (np.abs(view_coordinates[:, 1] + .007) < .201))
    points = points_camera[inside][:count]
    if len(points) != count:
        raise ValueError(f"The authored camera crop is too small for {name}")
    points = points + rng.normal(0., noise_m, size=points.shape)
    # A few unrelated returns inside the broad camera cone survive filtering.
    clutter = rng.uniform([-.148, -.123, .47], [.151, .127, .90], size=(outliers, 3))
    points = np.concatenate([points, clutter])
    rng.shuffle(points)
    return {"capture_id": name, "positioner_rad": angle,
            "base_from_camera": _pose(camera_rotation, camera_origin),
            "points_camera_m": points.round(7).tolist()}


def _build(
    name: str, *, seed: int, mirrored: bool = False, symmetry: bool = False,
    views: tuple[tuple[float, float, float, float], ...],
    mount_origin: list[float], mount_angles: list[float],
    seed_shift: list[float], seed_rotation: list[float],
) -> RegistrationCase:
    mesh = _square_hub() if symmetry else _fairing(mirrored)
    axis = (Rotation.from_euler("xyz", [.184, -.226, .31] if not mirrored else [-.26, .16, -.42]),
            np.array([.43, -.17, .33] if not mirrored else [.34, .24, .29]))
    rotation, origin = axis
    home = (rotation * Rotation.from_euler("xyz", mount_angles), origin + rotation.apply(mount_origin))
    generator = np.random.default_rng(seed)
    ids = [f"scan-{value:06x}" for value in generator.choice(2**24, len(views), replace=False)]
    captures = [
        _capture(mesh, axis, home, acquisition, view, generator,
                 count=109 + 6 * index, noise_m=.00083 if mirrored else .00070,
                 outliers=13 + 2 * index)
        for index, (acquisition, view) in enumerate(zip(ids, views, strict=True))
    ]
    generator.shuffle(captures)
    job = {
        "job_id": f"coating-{generator.integers(2**31):08x}",
        "part_mesh": mesh,
        "base_from_axis": _pose(*axis),
        "registration": {
            "initial_base_from_part_home": _pose(
                home[0] * Rotation.from_rotvec(seed_rotation), home[1] + np.asarray(seed_shift)
            ),
            "search_translation_m": .145,
            "search_rotation_rad": .93 if symmetry else .64,
            "translation_tolerance_m": .016,
            "rotation_tolerance_rad": .064,
            "scan_match_tolerance_m": .0028,
            "min_scan_inlier_fraction": .86,
        },
    }
    scans = {"capture_epoch": f"mount-{generator.integers(2**31):08x}", "captures": captures}
    truth = _pose(*home)
    alternatives = (_pose(home[0] * Rotation.from_rotvec([0., 0., np.pi / 2]), home[1]),) if symmetry else ()
    return RegistrationCase(name, job, scans, "review" if symmetry else "registered", truth, alternatives)


def registration_cases() -> tuple[RegistrationCase, ...]:
    """Return private positive, review, and invalid cases with reproducible inputs."""
    clockwise = _build(
        "reconcile-oblique-clockwise-captures", seed=62161,
        views=((-1.25, -.08, .43, .23), (.52, 1.92, .51, -.31), (1.87, -2.43, .29, .51)),
        mount_origin=[.062, -.039, .134], mount_angles=[.088, -.138, .19],
        seed_shift=[-.055, .048, -.027], seed_rotation=[.28, -.19, .11],
    )
    counterclockwise = _build(
        "reconcile-remounted-counterclockwise-part", seed=92851, mirrored=True,
        views=((1.71, .54, .26, -.44), (-.38, 2.83, .41, .20), (-1.44, -1.56, .35, -.28)),
        mount_origin=[-.037, .048, .146], mount_angles=[-.128, .128, -.24],
        seed_shift=[.032, -.063, .039], seed_rotation=[-.272, .20, -.187],
    )
    hub = _build(
        "review-square-hub-with-equivalent-azimuths", seed=37859, symmetry=True,
        views=((-1.07, -.11, .33, .19), (.21, 2.28, .40, -.24), (1.32, -2.03, .48, .42)),
        mount_origin=[.016, -.021, .128], mount_angles=[.051, -.039, .16],
        seed_shift=[.016, -.011, .015], seed_rotation=[0., 0., np.pi / 4],
    )
    empty = {"capture_epoch": "operator-has-no-captures", "captures": []}
    duplicate = deepcopy(clockwise.scans)
    duplicate["captures"].append(deepcopy(duplicate["captures"][0]))
    invalid_pose = deepcopy(counterclockwise.scans)
    invalid_pose["captures"][0]["base_from_camera"]["quaternion_xyzw"] = [0., 0., 0., 0.]
    invalid_mesh = deepcopy(clockwise.job)
    invalid_mesh["part_mesh"]["triangles"][0][2] = len(invalid_mesh["part_mesh"]["vertices_m"])
    return (
        clockwise,
        counterclockwise,
        hub,
        RegistrationCase("review-empty-scan-set", clockwise.job, empty, "review"),
        RegistrationCase("reject-duplicate-capture-id", clockwise.job, duplicate, "malformed"),
        RegistrationCase("reject-invalid-camera-quaternion", counterclockwise.job, invalid_pose, "malformed"),
        RegistrationCase("reject-invalid-triangle-index", invalid_mesh, clockwise.scans, "malformed"),
    )


def public_registration_sample() -> tuple[dict[str, Any], dict[str, Any]]:
    """Provide a working sample with an independent geometry and capture seed."""
    case = _build(
        "example-oblique-initial-mount", seed=16417, mirrored=True,
        views=((-.61, -.28, .36, -.18), (.79, 1.95, .43, .27), (1.48, -2.71, .30, .18)),
        mount_origin=[.041, .028, .115], mount_angles=[-.088, .064, .153],
        seed_shift=[-.028, -.038, .023], seed_rotation=[-.15, .144, -.116],
    )
    return case.job, case.scans


def _squared_mesh_distance(points: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Measure points against the full triangles, including their boundaries."""
    a, b, c = np.moveaxis(faces, 1, 0)
    ab, ac = b - a, c - a
    delta = points[:, None, :] - a
    ab2 = np.einsum("ij,ij->i", ab, ab)
    ac2 = np.einsum("ij,ij->i", ac, ac)
    ab_ac = np.einsum("ij,ij->i", ab, ac)
    along_ab = np.einsum("pij,ij->pi", delta, ab)
    along_ac = np.einsum("pij,ij->pi", delta, ac)
    determinant = ab2 * ac2 - ab_ac**2
    u = (ac2 * along_ab - ab_ac * along_ac) / determinant
    v = (ab2 * along_ac - ab_ac * along_ab) / determinant
    normal = np.cross(ab, ac)
    unit_normal = normal / np.linalg.norm(normal, axis=1)[:, None]
    planar = np.einsum("pij,ij->pi", delta, unit_normal)**2
    interior = (u >= 0.) & (v >= 0.) & (u + v <= 1.)
    squared = np.where(interior, planar, np.inf)
    for start, stop in ((a, b), (b, c), (c, a)):
        edge = stop - start
        step = points[:, None, :] - start
        projection = np.einsum("pij,ij->pi", step, edge) / np.einsum("ij,ij->i", edge, edge)
        residual = step - np.clip(projection, 0., 1.)[:, :, None] * edge
        squared = np.minimum(squared, np.einsum("pij,pij->pi", residual, residual))
    return squared.min(axis=1)


def capture_support(case: RegistrationCase, pose: dict[str, Any]) -> dict[str, float]:
    """Measure each nonempty capture's support for a reported home pose."""
    axis = _read_pose(case.job["base_from_axis"])
    home = _read_pose(pose)
    mesh = case.job["part_mesh"]
    faces = np.asarray(mesh["vertices_m"])[mesh["triangles"]]
    threshold = case.job["registration"]["scan_match_tolerance_m"] ** 2
    support = {}
    for capture in case.scans["captures"]:
        if not capture["points_camera_m"]:
            continue
        camera_rotation, camera_origin = _read_pose(capture["base_from_camera"])
        part_rotation, part_origin = _turned_part(axis, home, capture["positioner_rad"])
        points = camera_rotation.apply(capture["points_camera_m"]) + camera_origin
        local = part_rotation.inv().apply(points - part_origin)
        support[capture["capture_id"]] = float(np.mean(_squared_mesh_distance(local, faces) <= threshold))
    return support


def _valid_vector(value: Any, length: int) -> bool:
    return (isinstance(value, list) and len(value) == length
            and all(type(item) in (int, float) and -float_info.max <= item <= float_info.max
                    for item in value))


def check_registration(case: RegistrationCase, report: Any) -> tuple[bool, str, dict[str, float]]:
    """Check the CLI report against the published contract and planted geometry."""
    fields = {"job_id", "capture_epoch", "status", "base_from_part_home", "capture_ids"}
    if not isinstance(report, dict) or not fields <= report.keys():
        return False, "registration report is missing required fields", {}
    if report["job_id"] != case.job["job_id"] or report["capture_epoch"] != case.scans["capture_epoch"]:
        return False, "registration report identifies another job or capture epoch", {}
    ids = report["capture_ids"]
    available = {row["capture_id"] for row in case.scans["captures"] if row["points_camera_m"]}
    if (not isinstance(ids, list) or any(not isinstance(item, str) for item in ids)
            or len(set(ids)) != len(ids) or not set(ids) <= available):
        return False, "registration cites duplicate, missing, or empty captures", {}
    pose = report["base_from_part_home"]
    if report["status"] != case.expectation:
        return False, f"expected {case.expectation} registration status", {}
    if case.expectation == "review":
        return (True, "withheld an unresolved alignment", {}) if pose is None else (
            False, "review result includes an unsupported part pose", {})
    if case.expectation != "registered" or case.truth is None:
        return False, "no successful report is permitted for this case", {}
    if (not isinstance(pose, dict) or not _valid_vector(pose.get("translation_m"), 3)
            or not _valid_vector(pose.get("quaternion_xyzw"), 4)
            or max(abs(value) for value in pose["quaternion_xyzw"]) > 1. + 1e-6
            or abs(np.linalg.norm(pose["quaternion_xyzw"]) - 1.) > 1e-6):
        return False, "registered pose is malformed or its quaternion is not unit length", {}
    actual_rotation, actual_origin = _read_pose(pose)
    truth_rotation, truth_origin = _read_pose(case.truth)
    limits = case.job["registration"]
    translation_error = float(np.linalg.norm(actual_origin - truth_origin))
    rotation_error = float((truth_rotation.inv() * actual_rotation).magnitude())
    metrics = {"rotation_error_rad": rotation_error, "reported_support_count": float(len(ids))}
    if np.isfinite(translation_error):
        metrics["translation_error_m"] = translation_error
    if (translation_error > limits["translation_tolerance_m"]
            or rotation_error > limits["rotation_tolerance_rad"]):
        return False, "registered part differs from the surveyed pose beyond tolerance", metrics
    support = capture_support(case, pose)
    metrics["minimum_capture_support"] = min(support.values(), default=0.)
    if not ids or any(support[name] < limits["min_scan_inlier_fraction"] for name in ids):
        return False, "registered pose lacks its claimed supporting scans", metrics
    return True, "registered the surveyed part with observed support", metrics
