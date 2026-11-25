"""Independent nozzle ray casting and part-local coating dose integration."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import acos, pi, sin
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
_RAY_EPS = 1e-10  # metres, also used to resolve coincident surfaces
_BARY_EPS = 1e-10
_LEAF_SIZE = 16
_RAY_BATCH = 768


def _float_array(value: ArrayLike, shape: tuple[int, ...] | None = None) -> FloatArray:
    """Make an owned, finite floating-point array with an optional exact shape."""
    result = np.array(value, dtype=np.float64, copy=True)
    if (shape is not None and result.shape != shape) or not np.isfinite(result).all():
        raise ValueError("Expected a finite array of the specified shape")
    return result


def _dot(rows: FloatArray, columns: FloatArray) -> FloatArray:
    """Return all pairwise dot products of two arrays of three-vectors."""
    return np.einsum("ij,kj->ik", rows, columns)


@dataclass(frozen=True)
class _Node:
    """Local bounds and either indexed faces or the two child nodes."""

    lower: FloatArray
    upper: FloatArray
    faces: IntArray
    children: tuple["_Node", ...] = ()


class TriangleMesh:
    """An immutable copied indexed mesh and reusable local ray geometry.

    Only nonzero-area triangles participate in intersections or quadrature.
    The original indices and winding are retained throughout.
    """

    def __init__(self, vertices: ArrayLike, triangles: ArrayLike) -> None:
        self.vertices = _float_array(vertices)
        raw = np.asarray(triangles)
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("Vertices must have shape (n, 3)")
        if raw.ndim != 2 or raw.shape[1] != 3 or raw.dtype.kind not in "iu":
            raise ValueError("Triangles must contain three integer indices per row")
        if np.any(raw < 0) or np.any(raw >= len(self.vertices)):
            raise ValueError("Triangle references an unknown vertex")
        self.triangles = raw.astype(np.int64, copy=True)
        self.vertices.setflags(write=False)
        self.triangles.setflags(write=False)
        indexed = self.vertices[self.triangles]
        self.starts = indexed[:, 0]
        self.side_u = indexed[:, 1] - self.starts
        self.side_v = indexed[:, 2] - self.starts
        cross = np.cross(self.side_u, self.side_v)
        doubled_area = np.linalg.norm(cross, axis=1)
        self.areas = 0.5 * doubled_area
        self.areas.setflags(write=False)
        self.longest_edges = np.max(np.linalg.norm(indexed - np.roll(indexed, 1, axis=1), axis=2), axis=1)
        scale = np.where(doubled_area > 0.0, doubled_area, 1.0)[:, None]
        self.normals = cross / scale
        self.u_grad = np.cross(self.side_v, self.normals) / scale
        self.v_grad = np.cross(self.normals, self.side_u) / scale
        indices = np.flatnonzero(doubled_area > 0.0)
        if len(indices):
            lower = indexed.min(axis=1)
            upper = indexed.max(axis=1)
            centers = (lower + upper) / 2
            self.tree = _build_tree(indices, lower, upper, centers)
        else:
            self.tree = None


def _build_tree(
    faces: IntArray, lower: FloatArray, upper: FloatArray, centers: FloatArray,
) -> _Node:
    """Build reproducible median-split bounds for the mesh's nondegenerate faces."""
    lo, hi = lower[faces].min(axis=0), upper[faces].max(axis=0)
    if len(faces) <= _LEAF_SIZE:
        return _Node(lo, hi, np.sort(faces))
    axis = int(np.argmax(np.ptp(centers[faces], axis=0)))
    ranked = faces[np.argsort(centers[faces, axis], kind="stable")]
    half = len(ranked) // 2
    children = tuple(_build_tree(group, lower, upper, centers) for group in (ranked[:half], ranked[half:]))
    return _Node(lo, hi, np.empty(0, dtype=np.int64), children)


class RigidBody:
    """Place an indexed mesh with a proper world-from-body rigid transform."""

    def __init__(self, body_id: str, mesh: TriangleMesh, world_from_body: ArrayLike) -> None:
        if not isinstance(body_id, str) or not body_id:
            raise ValueError("Expected a nonempty body identifier")
        pose = _float_array(world_from_body, (4, 4))
        rotation = pose[:3, :3]
        if (not np.allclose(pose[3], [0, 0, 0, 1], atol=1e-9, rtol=0)
                or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8, rtol=0)
                or np.linalg.det(rotation) <= 0):
            raise ValueError("Body pose must be a proper rigid transform")
        pose.setflags(write=False)
        self.body_id = body_id
        self.mesh = mesh
        self.world_from_body = pose
        self.rotation = rotation
        self.translation = pose[:3, 3]


@dataclass(frozen=True)
class AxisHit:
    """The axis ray's first surface, including points and normals in both frames."""

    body_id: str
    face_index: int
    distance_m: float
    world_point: FloatArray
    world_normal: FloatArray
    part_point: FloatArray | None
    part_normal: FloatArray | None
    normal_error_rad: float


def _slab_members(
    node: _Node, origin: FloatArray, rays: FloatArray, limit: FloatArray,
) -> NDArray[np.bool_]:
    """Select rays that can hit the node by their current distance limit."""
    near = np.zeros(len(rays))
    far = limit + _RAY_EPS
    for axis in range(3):
        low = node.lower[axis] - _RAY_EPS - origin[axis]
        high = node.upper[axis] + _RAY_EPS - origin[axis]
        directions = rays[:, axis]
        parallel = directions == 0
        divisor = np.where(parallel, 1, directions)
        first, second = low / divisor, high / divisor
        near = np.maximum(near, np.where(parallel, -np.inf, np.minimum(first, second)))
        far = np.minimum(far, np.where(parallel, np.inf if low <= 0 <= high else -np.inf,
                                        np.maximum(first, second)))
    return near <= far


def _leaf_hits(
    mesh: TriangleMesh, faces: IntArray, origin: FloatArray, rays: FloatArray, limit: FloatArray,
) -> tuple[FloatArray, IntArray]:
    """Intersect eligible rays with a leaf, including back-facing triangles.

    Returns the first positive distance and source face per ray, with infinity
    and -1 for misses. Coincident candidates use the smaller face index.
    """
    displacement = origin - mesh.starts[faces]
    normals = mesh.normals[faces]
    direction = _dot(rays, normals)
    nonparallel = np.abs(direction) > 1e-14
    height = -np.einsum("ij,ij->i", displacement, normals)
    distance = height / np.where(nonparallel, direction, 1)
    ug, vg = mesh.u_grad[faces], mesh.v_grad[faces]
    u = np.einsum("ij,ij->i", displacement, ug) + distance * _dot(rays, ug)
    v = np.einsum("ij,ij->i", displacement, vg) + distance * _dot(rays, vg)
    inside = (nonparallel & (distance > _RAY_EPS) & (distance <= limit[:, None] + _RAY_EPS)
              & (u >= -_BARY_EPS) & (v >= -_BARY_EPS) & (u + v <= 1 + _BARY_EPS))
    distances = np.where(inside, distance, np.inf)
    minimum = distances.min(axis=1, keepdims=True)
    winner = np.argmax(inside & (distances <= minimum + _RAY_EPS), axis=1)
    return distances[np.arange(len(rays)), winner], np.where(np.isfinite(minimum[:, 0]), faces[winner], -1)


def _mesh_hits(
    mesh: TriangleMesh, origin: FloatArray, rays: FloatArray, upper: FloatArray,
) -> tuple[FloatArray, IntArray]:
    """Perform bounded ray casting in the mesh frame and retain original indices."""
    distance = upper.copy()
    indices = np.full(len(rays), -1, dtype=np.int64)
    if mesh.tree is not None and len(rays):
        stack = [(mesh.tree, np.arange(len(rays)))]
        while stack:
            node, candidates = stack.pop()
            candidates = candidates[_slab_members(node, origin, rays[candidates], distance[candidates])]
            if not len(candidates):
                continue
            if node.children:
                stack.extend((child, candidates) for child in node.children)
                continue
            new, face = _leaf_hits(mesh, node.faces, origin, rays[candidates], distance[candidates])
            current = distance[candidates]
            prior = indices[candidates]
            choose = (face >= 0) & ((prior < 0) | (new < current - _RAY_EPS)
                                   | ((new <= current + _RAY_EPS) & (face < prior)))
            distance[candidates[choose]] = new[choose]
            indices[candidates[choose]] = face[choose]
    return np.where(indices >= 0, distance, np.inf), indices


def _ordered_bodies(bodies: Iterable[RigidBody]) -> tuple[RigidBody, ...]:
    """Materialize the scene in stable body-ID order and reject duplicate IDs."""
    result = tuple(sorted(bodies, key=lambda body: body.body_id))
    if any(a.body_id == b.body_id for a, b in zip(result, result[1:])):
        raise ValueError("Body identifiers must be unique")
    return result


def _nozzle(origin: ArrayLike, axis: ArrayLike) -> tuple[FloatArray, FloatArray]:
    """Normalize a finite world nozzle axis and copy its world-space origin."""
    position = _float_array(origin, (3,))
    direction = _float_array(axis, (3,))
    length = np.linalg.norm(direction)
    if not np.isfinite(length) or length <= 0:
        raise ValueError("Nozzle axis must be nonzero")
    return position, direction / length


def _scene_hits(
    bodies: tuple[RigidBody, ...], origin: FloatArray, rays: FloatArray, upper: FloatArray,
) -> tuple[FloatArray, IntArray, IntArray]:
    """Cast normalized world rays and break coincident hits by body ID then face."""
    nearest = upper.copy()
    owner = np.full(len(rays), -1, dtype=np.int64)
    faces = np.full(len(rays), -1, dtype=np.int64)
    for index, body in enumerate(bodies):
        local_origin = (origin - body.translation) @ body.rotation
        local_rays = rays @ body.rotation
        distance, face = _mesh_hits(body.mesh, local_origin, local_rays, nearest)
        closer = (face >= 0) & ((owner < 0) | (distance < nearest - _RAY_EPS))
        nearest[closer], owner[closer], faces[closer] = distance[closer], index, face[closer]
    return np.where(owner >= 0, nearest, np.inf), owner, faces


def _axis_hit(
    bodies: tuple[RigidBody, ...], origin: FloatArray, direction: FloatArray, part: RigidBody | None,
) -> AxisHit | None:
    """Build the observation for a normalized axis ray and optional part frame."""
    distances, owners, faces = _scene_hits(bodies, origin, direction[None, :], np.array([np.inf]))
    if owners[0] < 0:
        return None
    body, face, distance = bodies[owners[0]], int(faces[0]), float(distances[0])
    point = origin + distance * direction
    normal = body.rotation @ body.mesh.normals[face]
    local_point = None if part is None else part.rotation.T @ (point - part.translation)
    local_normal = None if part is None else part.rotation.T @ normal
    error = acos(float(np.clip(-direction @ normal, -1, 1)))
    return AxisHit(body.body_id, face, distance, point, normal, local_point, local_normal, error)


def first_hit(
    bodies: Iterable[RigidBody], nozzle_origin: ArrayLike, nozzle_axis: ArrayLike, *, part_id: str = "part",
) -> AxisHit | None:
    """Measure the first axis intercept, including blockers hit from their backs.

    Body poses and the nozzle are in the world frame. Part coordinates are
    provided when the scene contains `part_id`, even if a fixture blocks the
    axis. A miss returns None. The axis may be non-unit.
    """
    ordered = _ordered_bodies(bodies)
    origin, direction = _nozzle(nozzle_origin, nozzle_axis)
    part = next((body for body in ordered if body.body_id == part_id), None)
    return _axis_hit(ordered, origin, direction, part)


@dataclass(frozen=True)
class _Surface:
    """Stable body-frame area elements, with source triangle provenance."""

    centers: FloatArray
    areas: FloatArray
    faces: IntArray


def _centroids(divisions: int) -> FloatArray:
    """Produce exactly divisions squared barycentric microtriangle centroids."""
    i, j = np.triu_indices(divisions, 0)
    a, b = i, j - i
    secondary = j < divisions - 1
    forward = np.column_stack((a + 1 / 3, b + 1 / 3))
    backward = np.column_stack((a[secondary] + 2 / 3, b[secondary] + 2 / 3))
    return np.concatenate((forward, backward)) / divisions


def _quadrature(mesh: TriangleMesh, subdivisions: int, max_edge: float | None) -> _Surface:
    """Assign equal triangle-cell areas and fixed centroid samples in local coordinates."""
    faces = np.flatnonzero(mesh.areas > 0)
    levels = np.full(len(faces), subdivisions, dtype=np.int64)
    if max_edge is not None:
        levels = np.maximum(levels, np.ceil(mesh.longest_edges[faces] / max_edge).astype(np.int64))
    points, areas, indices = [], [], []
    for count in np.unique(levels):
        chosen = faces[levels == count]
        uv = _centroids(int(count))
        region = (mesh.starts[chosen, None, :] + uv[None, :, :1] * mesh.side_u[chosen, None, :]
                  + uv[None, :, 1:] * mesh.side_v[chosen, None, :])
        points.append(region.reshape(-1, 3))
        areas.append(np.repeat(mesh.areas[chosen] / len(uv), len(uv)))
        indices.append(np.repeat(chosen, len(uv)))
    if not points:
        return _Surface(np.empty((0, 3)), np.empty(0), np.empty(0, dtype=np.int64))
    return _Surface(np.concatenate(points), np.concatenate(areas), np.concatenate(indices))


@dataclass(frozen=True)
class DoseScore:
    """Area-weighted recipe result and independently integrated deposited volume."""

    covered_fraction: float
    off_target_ml: float
    target_min_ml_m2: float
    target_max_ml_m2: float
    target_area_m2: float
    covered_area_m2: float
    target_deposited_ml: float
    part_deposited_ml: float
    total_deposited_ml: float
    qualified: bool


class SurfaceDose:
    """Integrate a time series of independently observed cone placements.

    Target face selection is by stable part triangle index. Both target and
    non-target part elements persist in local coordinates through remounts.
    Fixture and world deposition contributes to accumulated off-target volume
    even if a body is later removed or replaced. One instance represents one
    physical part and mission.
    """

    def __init__(
        self, part_mesh: TriangleMesh, target_faces: Iterable[int], *, part_id: str = "part",
        subdivisions: int = 4, max_cell_edge_m: float | None = None,
    ) -> None:
        faces = np.asarray(tuple(target_faces))
        if (faces.ndim != 1 or not len(faces) or faces.dtype.kind not in "iu"
                or (faces < 0).any() or (faces >= len(part_mesh.triangles)).any()
                or not np.any(part_mesh.areas[faces] > 0)):
            raise ValueError("Target indices must specify positive part area")
        if type(subdivisions) is not int or subdivisions < 1:
            raise ValueError("Expected a positive subdivision count")
        if max_cell_edge_m is not None and (not np.isfinite(max_cell_edge_m) or max_cell_edge_m <= 0):
            raise ValueError("Expected a finite positive quadrature edge limit")
        self.part_mesh = part_mesh
        self.part_id = part_id
        self.subdivisions = subdivisions
        self.max_cell_edge_m = max_cell_edge_m
        self._cache: dict[TriangleMesh, _Surface] = {}
        self._part = self._surface(part_mesh)
        self._target = np.isin(self._part.faces, faces)
        self._dose = np.zeros(len(self._part.areas))
        self._external_volume: dict[str, float] = {}

    def _surface(self, mesh: TriangleMesh) -> _Surface:
        """Return the local area grid, reusing it for later placements of this mesh."""
        surface = self._cache.get(mesh)
        if surface is None:
            surface = self._cache[mesh] = _quadrature(mesh, self.subdivisions, self.max_cell_edge_m)
        return surface

    @property
    def part_dose_ml_m2(self) -> FloatArray:
        """Return a copy of cumulative part-cell doses in the local grid order."""
        return self._dose.copy()

    @property
    def external_volume_ml(self) -> dict[str, float]:
        """Return accumulated fixture and world dose volumes keyed by body ID."""
        return self._external_volume.copy()

    def sample(
        self, bodies: Iterable[RigidBody], nozzle_origin: ArrayLike, nozzle_axis: ArrayLike, *,
        flow_ml_s: float, duration_s: float, cone_half_angle_rad: float,
    ) -> AxisHit | None:
        """Integrate how much a held flow deposits at this pose over duration_s.

        The caller supplies the non-overlapping duration represented by this
        observation in seconds. This function knows no command, clock, or
        trajectory interpolation. A zero-duration or zero-flow sample still
        measures the first axis hit. Bodies must include the original part mesh
        under its configured ID. Pose and duration are observed externally.
        """
        values = np.asarray((flow_ml_s, duration_s, cone_half_angle_rad), dtype=np.float64)
        if not np.isfinite(values).all() or flow_ml_s < 0 or duration_s < 0 or not 0 < cone_half_angle_rad <= pi:
            raise ValueError("Invalid flow, duration, or cone angle")
        ordered = _ordered_bodies(bodies)
        origin, direction = _nozzle(nozzle_origin, nozzle_axis)
        part = next((body for body in ordered if body.body_id == self.part_id), None)
        if part is None or (part.mesh is not self.part_mesh
                            and not (np.array_equal(part.mesh.vertices, self.part_mesh.vertices)
                                     and np.array_equal(part.mesh.triangles, self.part_mesh.triangles))):
            raise ValueError("Observation must contain the accumulator's unchanged physical part")
        axis_hit = _axis_hit(ordered, origin, direction, part)
        if not flow_ml_s or not duration_s:
            return axis_hit
        # 2*pi*(1-cos(angle)) rewritten to retain accuracy for small cones.
        solid_angle = 4 * pi * sin(cone_half_angle_rad / 2) ** 2
        if solid_angle <= 0:
            raise ValueError("Cone solid angle underflow")
        scale = flow_ml_s * duration_s / solid_angle
        if not np.isfinite(scale):
            raise ValueError("Integrated flow per solid angle overflow")
        cone_limit = np.cos(cone_half_angle_rad)
        for number, body in enumerate(ordered):
            surface = self._part if body is part else self._surface(body.mesh)
            indices, dose = self._deposit(ordered, number, surface, origin, direction, cone_limit, scale)
            if body is part:
                self._dose[indices] += dose
            elif len(indices):
                self._external_volume[body.body_id] = (self._external_volume.get(body.body_id, 0.0)
                                                      + float(dose @ surface.areas[indices]))
        return axis_hit

    def _deposit(
        self, bodies: tuple[RigidBody, ...], receiver: int, surface: _Surface,
        origin: FloatArray, axis: FloatArray, cone_limit: float, scale: float,
    ) -> tuple[IntArray, FloatArray]:
        """Compute sparse dose on front-facing local elements that own their first hit."""
        body = bodies[receiver]
        local_origin = (origin - body.translation) @ body.rotation
        local_axis = axis @ body.rotation
        displacement = surface.centers - local_origin
        squared = np.einsum("ij,ij->i", displacement, displacement)
        distance = np.sqrt(squared)
        normals = body.mesh.normals[surface.faces]
        facing = -np.einsum("ij,ij->i", normals, displacement)
        selected = np.flatnonzero((distance > _RAY_EPS) & (facing > 0)
                                  & (displacement @ local_axis >= distance * (cone_limit - 1e-14)))
        visible = []
        for start in range(0, len(selected), _RAY_BATCH):
            rows = selected[start:start + _RAY_BATCH]
            radius = distance[rows]
            world_rays = (displacement[rows] / radius[:, None]) @ body.rotation.T
            _, owners, faces = _scene_hits(bodies, origin, world_rays, radius)
            visible.append(rows[(owners == receiver) & (faces == surface.faces[rows])])
        rows = np.concatenate(visible) if visible else selected
        return rows, scale * (facing[rows] / distance[rows]) / squared[rows]

    def score(self, recipe: Mapping[str, Any]) -> DoseScore:
        """Compute area in the inclusive recipe band and cumulative excess volume.

        Recipe uses the wire keys `target_dose_ml_m2`, `min_covered_fraction`
        and `max_off_target_ml`. Every target cell, including an uncoated
        cell, contributes to the denominator and the reported dose range.
        """
        lower, upper = _float_array(recipe["target_dose_ml_m2"], (2,))
        minimum = float(recipe["min_covered_fraction"])
        maximum = float(recipe["max_off_target_ml"])
        if (not 0 <= lower <= upper or not np.isfinite(minimum) or not 0 <= minimum <= 1
                or not np.isfinite(maximum) or maximum < 0):
            raise ValueError("Invalid coating qualification values")
        areas = self._part.areas[self._target]
        target = self._dose[self._target]
        covered_area = float(areas[(target >= lower) & (target <= upper)].sum())
        target_area = float(areas.sum())
        fraction = covered_area / target_area
        target_volume = float(target @ areas)
        part_off_target = float(self._dose[~self._target] @ self._part.areas[~self._target])
        excess = part_off_target + sum(self._external_volume.values())
        return DoseScore(fraction, excess, float(target.min()), float(target.max()), target_area, covered_area,
                         target_volume, target_volume + part_off_target, target_volume + excess,
                         fraction >= minimum and excess <= maximum)
