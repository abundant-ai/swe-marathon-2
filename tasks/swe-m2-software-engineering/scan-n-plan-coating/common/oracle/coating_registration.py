"""Bounded rigid registration of rotary captures against a triangle surface."""

from dataclasses import dataclass
from math import ceil, isfinite, pi, remainder, tau

import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation
from scipy.stats import qmc


def _object(value, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _array(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _number(value, field):
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be a finite number")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return value


def _nonnegative(obj, field):
    value = _number(obj.get(field), field)
    if value < 0:
        raise ValueError(f"{field} must be nonnegative")
    return value


def _identifier(value, field):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _vector(value, size, field):
    values = _array(value, field)
    if len(values) != size:
        raise ValueError(f"{field} must contain {size} numbers")
    return [_number(entry, field) for entry in values]


def _points(value, field):
    rows = [_vector(row, 3, field) for row in _array(value, field)]
    return np.asarray(rows, dtype=float).reshape(-1, 3)


def _pose(value, field):
    value = _object(value, field)
    translation = np.array(_vector(value.get("translation_m"), 3, field))
    quaternion = _vector(value.get("quaternion_xyzw"), 4, field)
    if abs(np.linalg.norm(quaternion) - 1.0) > 1e-6:
        raise ValueError(f"{field} requires a unit quaternion")
    return Rotation.from_quat(quaternion), translation


class _Surface:
    """Exact nearest points on faces and their boundary segments."""

    def __init__(self, mesh):
        mesh = _object(mesh, "part_mesh")
        vertices = _points(mesh.get("vertices_m"), "vertices_m")
        face_indices = _array(mesh.get("triangles"), "triangles")
        if not face_indices:
            raise ValueError("triangles must contain at least one face")
        for face in face_indices:
            if len(_array(face, "triangle")) != 3 or any(
                type(index) is not int or not 0 <= index < len(vertices)
                for index in face
            ):
                raise ValueError("triangle indices must reference three vertices")

        # Centering also keeps the distance calculation stable for a mesh whose
        # design origin is away from the part.
        self.center = vertices.mean(axis=0)
        triangles = (vertices - self.center)[np.asarray(face_indices)]
        self.starts = triangles.transpose(1, 0, 2)
        self.edges = np.roll(self.starts, -1, axis=0) - self.starts
        self.edge_sq = np.einsum("eti,eti->et", self.edges, self.edges)
        raw_normal = np.cross(self.edges[0], -self.edges[2])
        area_twice = np.linalg.norm(raw_normal, axis=1)
        if np.any(area_twice <= 0) or not np.all(np.isfinite(area_twice)):
            raise ValueError("triangles must have finite nonzero area")
        self.normals = raw_normal / area_twice[:, None]
        self.dual_u = np.cross(-self.edges[2], self.normals) / area_twice[:, None]
        self.dual_v = np.cross(self.normals, self.edges[0]) / area_twice[:, None]

    def closest(self, points):
        # Bound temporary arrays even when there are a large number of samples.
        if len(points) > 256:
            return np.vstack([
                self.closest(points[start:start + 256])
                for start in range(0, len(points), 256)
            ])

        delta = points[:, None, :] - self.starts[0]
        u = np.einsum("pti,ti->pt", delta, self.dual_u)
        v = np.einsum("pti,ti->pt", delta, self.dual_v)
        height = np.einsum("pti,ti->pt", delta, self.normals)
        inside = (u >= 0) & (v >= 0) & (u + v <= 1)
        nearest_sq = np.where(inside, height**2, np.inf)
        nearest_delta = height[..., None] * self.normals
        for edge, start, edge_sq in zip(self.edges, self.starts, self.edge_sq):
            offset = points[:, None, :] - start
            along = np.einsum("pti,ti->pt", offset, edge)
            fraction = np.clip(along / edge_sq, 0.0, 1.0)
            displacement = offset - fraction[..., None] * edge
            distance_sq = np.einsum("pti,pti->pt", displacement, displacement)
            better = distance_sq < nearest_sq
            nearest_sq[better] = distance_sq[better]
            np.copyto(nearest_delta, displacement, where=better[..., None])

        faces = np.argmin(nearest_sq, axis=1)
        return nearest_delta[np.arange(len(points)), faces]


@dataclass(frozen=True)
class _Capture:
    key: str
    points: np.ndarray
    required: int


def _captures(scans, axis_rotation, axis_translation, fraction):
    captures = []
    seen = set()
    for capture in _array(scans.get("captures"), "captures"):
        capture = _object(capture, "capture")
        key = _identifier(capture.get("capture_id"), "capture_id")
        if key in seen:
            raise ValueError(f"duplicate capture_id {key!r}")
        seen.add(key)
        angle = remainder(_number(capture.get("positioner_rad"), "positioner_rad"), tau)
        camera_rotation, camera_translation = _pose(
            capture.get("base_from_camera"), "base_from_camera"
        )
        camera_points = _points(capture.get("points_camera_m"), "points_camera_m")
        if len(camera_points):
            rotate_back = (
                axis_rotation * Rotation.from_rotvec([0, 0, -angle]) * axis_rotation.inv()
            )
            base_at_angle = camera_rotation.apply(camera_points) + camera_translation
            base_home = rotate_back.apply(base_at_angle - axis_translation) + axis_translation
            required = ceil(len(camera_points) * fraction)
            if required and (required - 1) / len(camera_points) >= fraction:
                required -= 1
            captures.append(_Capture(key, base_home, required))
    return sorted(captures, key=lambda capture: capture.key)


def _inside_ball(value):
    radius = np.linalg.norm(value)
    if radius <= 1:
        return value, np.eye(3)
    unit = value / radius
    return unit, (np.eye(3) - np.outer(unit, unit)) / radius


def _left_jacobian(vector):
    x, y, z = vector
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    angle = np.linalg.norm(vector)
    if angle < 1e-4:
        return np.eye(3) + 0.5 * cross + (cross @ cross) / 6
    return (
        np.eye(3)
        + ((1 - np.cos(angle)) / angle**2) * cross
        + ((angle - np.sin(angle)) / angle**3) * (cross @ cross)
    )


class _Problem:
    def __init__(self, surface, captures, rotation, translation, settings):
        self.surface = surface
        self.captures = captures
        self.seed_r, self.seed_t = rotation, translation
        self.t_range = _nonnegative(settings, "search_translation_m")
        self.r_range = min(pi, _nonnegative(settings, "search_rotation_rad"))
        self.t_tol = _nonnegative(settings, "translation_tolerance_m")
        self.r_tol = _nonnegative(settings, "rotation_tolerance_rad")
        self.scan_tol = _nonnegative(settings, "scan_match_tolerance_m")
        # Keep squared quantities well-scaled, including exact-fit jobs.
        self.scan_scale = max(self.scan_tol, 1e-10)
        self.match_limit = (self.scan_tol + 1e-12) / self.scan_scale
        self.bounds = [
            (-1.0, 1.0) if radius > 0 else (0.0, 0.0)
            for radius in [self.t_range] * 3 + [self.r_range] * 3
        ]

    def pose(self, value):
        shift, _ = _inside_ball(value[:3])
        turn, _ = _inside_ball(value[3:])
        return (
            Rotation.from_rotvec(turn * self.r_range) * self.seed_r,
            self.seed_t + shift * self.t_range,
        )

    def distances(self, value, with_gradient=True):
        shift, shift_jac = _inside_ball(value[:3])
        turn, turn_jac = _inside_ball(value[3:])
        rotvec = turn * self.r_range
        rotation = Rotation.from_rotvec(rotvec) * self.seed_r
        translation = self.seed_t + shift * self.t_range
        center = rotation.apply(self.surface.center)
        if with_gradient:
            rotation_jac = _left_jacobian(rotvec) @ turn_jac * self.r_range
            translation_jac = shift_jac * self.t_range

        for capture in self.captures:
            relative = capture.points - translation
            query = rotation.inv().apply(relative - center)
            delta = self.surface.closest(query)
            scaled_delta = delta / self.scan_scale
            squared = np.einsum("pi,pi->p", scaled_delta, scaled_delta)
            jac = None
            if with_gradient:
                direction = rotation.apply(scaled_delta) * (2 / self.scan_scale)
                jac = np.column_stack((
                    -direction @ translation_jac,
                    np.cross(direction, relative) @ rotation_jac,
                ))
            yield capture, squared, jac

    def cost(self, value, scale, with_gradient=True):
        cost = 0.0
        gradient = np.zeros(6)
        for capture, squared, jac in self.distances(value, with_gradient):
            keep = max(1, capture.required)
            best = np.argpartition(squared, keep - 1)[:keep]
            residual = squared[best]
            cost += np.log1p(residual / scale**2).mean()
            if with_gradient:
                gradient += (jac[best] / (scale**2 + residual[:, None])).mean(axis=0)
        if with_gradient:
            return cost, gradient
        return cost

    def consistent(self, value):
        return all(
            np.count_nonzero(distance <= self.match_limit**2) >= capture.required
            for capture, distance, _ in self.distances(value, False)
        )

    def distinct(self, first, second):
        first_r, first_t = first
        second_r, second_t = second
        return (
            np.linalg.norm(first_t - second_t) > self.t_tol + 1e-12
            or (first_r.inv() * second_r).magnitude() > self.r_tol + 1e-12
        )

    def feasible_margin(self, value):
        """Bounds and worst required residual for each capture."""
        margin = [1 - value[:3] @ value[:3], 1 - value[3:] @ value[3:]]
        jac = [
            np.r_[-2 * value[:3], np.zeros(3)],
            np.r_[np.zeros(3), -2 * value[3:]],
        ]
        for capture, squared, gradient in self.distances(value):
            if capture.required:
                limit = np.argpartition(squared, capture.required - 1)[capture.required - 1]
                margin.append(self.match_limit**2 - squared[limit])
                jac.append(-gradient[limit])
        return np.asarray(margin), np.asarray(jac)


def _project(value):
    return np.r_[_inside_ball(value[:3])[0], _inside_ball(value[3:])[0]]


def _fit(problem, initial, scale):
    result = minimize(
        problem.cost,
        initial,
        args=(scale,),
        jac=True,
        bounds=problem.bounds,
        method="L-BFGS-B",
        options={"maxiter": 55, "ftol": 1e-9},
    )
    return _project(result.x)


def _starts(problem):
    samples = 2 * qmc.Sobol(6, scramble=False).random_base2(7) - 1
    # Map the cube to each search ball without placing every corner on the rim.
    for group in (samples[:, :3], samples[:, 3:]):
        radius = np.linalg.norm(group, axis=1)
        group *= (np.max(np.abs(group), axis=1) / np.maximum(radius, 1e-12))[:, None]
    if not problem.t_range:
        samples[:, :3] = 0.0
    if not problem.r_range:
        samples[:, 3:] = 0.0
    points = np.vstack((np.zeros(6), samples))
    coarse_scale = max(2.0, min(12.0, problem.t_range / (4 * problem.scan_scale)))
    ranked = sorted(points, key=lambda value: problem.cost(value, coarse_scale, False))
    retained = []
    for value in ranked:
        if all(np.linalg.norm(value - previous) > 0.30 for previous in retained):
            retained.append(value)
            if len(retained) == 14:
                break

    # Keep the actual seed and the best start in each physical rotation
    # direction. A symmetric solution's second basin may rank below many
    # nearly equivalent starts around the first basin.
    output = [np.zeros(6)]
    for direction in np.vstack((np.eye(3), -np.eye(3))):
        candidates = [value for value in ranked if value[3:] @ direction >= 0.2]
        if candidates:
            output.append(candidates[0])
    output.extend(retained)
    unique = []
    for value in output:
        if not any(np.array_equal(previous, value) for previous in unique):
            unique.append(value)
    return unique, coarse_scale


def _probe_ambiguity(problem, anchor, accepted):
    """Look for physically distinct witnesses on the local consistency set."""
    # Maximizing observable pose excursions detects the ambiguous case where
    # normal least-squares restarts converge to one arbitrary point on a flat
    # region. Test feasibility again after each optimizer result.
    directions = np.r_[np.eye(6), -np.eye(6)]
    cached_x = None
    margins = gradient = None

    def get_margins(value):
        nonlocal cached_x, margins, gradient
        if cached_x is None or not np.array_equal(cached_x, value):
            cached_x = value.copy()
            margins, gradient = problem.feasible_margin(value)
        return margins

    def get_jac(value):
        get_margins(value)
        return gradient

    constraint = {"type": "ineq", "fun": get_margins, "jac": get_jac}
    for direction in directions:
        axis = np.flatnonzero(direction)[0]
        radius, tolerance = (
            (problem.t_range, problem.t_tol) if axis < 3 else (problem.r_range, problem.r_tol)
        )
        if radius == 0 or 2 * radius <= tolerance:
            continue
        # Include a near witness if a discontinuous order statistic stalls the
        # constraint solver, e.g. with exactly coincident planar face edges.
        near = _project(anchor + direction * max(0.55 * tolerance / radius, 1e-5))
        if problem.consistent(near) and accepted(near):
            return True
        result = minimize(
            lambda value: -direction @ value,
            anchor,
            jac=lambda value: -direction,
            bounds=problem.bounds,
            constraints=constraint,
            method="SLSQP",
            options={"maxiter": 28, "ftol": 1e-9},
        )
        candidate = _project(result.x)
        if problem.consistent(candidate) and accepted(candidate):
            return True
        # Back off from a numerical boundary while retaining a physical witness.
        backed_off = 0.995 * candidate + 0.005 * anchor
        if problem.consistent(backed_off) and accepted(backed_off):
            return True
    return False


def register(job: dict, scans: dict) -> dict:
    """Return one complete registration or a successful review report."""
    job, scans = _object(job, "job"), _object(scans, "scans")
    job_id = _identifier(job.get("job_id"), "job_id")
    epoch = _identifier(scans.get("capture_epoch"), "capture_epoch")
    surface = _Surface(job.get("part_mesh"))
    axis_rotation, axis_translation = _pose(job.get("base_from_axis"), "base_from_axis")
    settings = _object(job.get("registration"), "registration")
    seed_r, seed_t = _pose(settings.get("initial_base_from_part_home"), "initial_base_from_part_home")
    fraction = _nonnegative(settings, "min_scan_inlier_fraction")
    if fraction > 1:
        raise ValueError("min_scan_inlier_fraction must be at most one")
    captures = _captures(scans, axis_rotation, axis_translation, fraction)
    problem = _Problem(surface, captures, seed_r, seed_t, settings)

    report = {
        "job_id": job_id,
        "capture_epoch": epoch,
        "status": "review",
        "base_from_part_home": None,
        "capture_ids": [],
    }
    if not captures:
        return report

    poses = []
    best_value = None
    best_cost = np.inf

    def accept(value):
        nonlocal best_value, best_cost
        pose = problem.pose(value)
        if any(problem.distinct(pose, other) for other in poses):
            return True
        poses.append(pose)
        cost = problem.cost(value, 0.6, False)
        if cost < best_cost:
            best_cost, best_value = cost, value
        return False

    if not (problem.t_range or problem.r_range):
        seed = np.zeros(6)
        if problem.consistent(seed):
            accept(seed)
    else:
        starts, coarse_scale = _starts(problem)
        for start in starts:
            rough = _fit(problem, start, coarse_scale)
            refined = _fit(problem, rough, 0.6)
            for candidate in (start, rough, refined):
                if problem.consistent(candidate) and accept(candidate):
                    return report
        if best_value is not None and _probe_ambiguity(problem, best_value, accept):
            return report

    if best_value is None:
        return report
    rotation, translation = problem.pose(best_value)
    report["status"] = "registered"
    report["base_from_part_home"] = {
        "translation_m": translation.tolist(),
        "quaternion_xyzw": rotation.as_quat(canonical=True).tolist(),
    }
    report["capture_ids"] = [capture.key for capture in captures]
    return report
