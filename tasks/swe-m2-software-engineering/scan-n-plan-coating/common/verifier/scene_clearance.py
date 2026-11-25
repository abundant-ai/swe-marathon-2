"""Sample the arm's clearance from posed coating scene triangle surfaces."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math
from weakref import WeakKeyDictionary

import fcl
import mujoco
import numpy as np
from numpy.typing import NDArray

from native_arm import NativeArm
from surface_dose import RigidBody, TriangleMesh


FloatArray = NDArray[np.float64]
INTERSECTION_M = -1.0


@dataclass(frozen=True)
class _ArmShape:
    """One native arm geometry and its equivalent FCL primitive."""

    geom_id: int
    collider: fcl.CollisionObject
    local_half_extents: FloatArray


@dataclass(frozen=True)
class _MeshShape:
    """A local-coordinate FCL triangle hierarchy and its local AABB."""

    geometry: fcl.BVHModel
    center: FloatArray
    half_extents: FloatArray


def _primitive(
    geom_type: int, size: FloatArray, name: str,
) -> tuple[fcl.CollisionGeometry, FloatArray]:
    """Translate MuJoCo primitive parameters to FCL in the native geom frame.

    MuJoCo box extents and cylinder axial length are half sizes.
    Both libraries center their primitives at the geom origin and use local
    positive Z for a cylinder's long axis.
    """
    if geom_type == mujoco.mjtGeom.mjGEOM_CYLINDER:
        radius, half_length = size[:2]
        if not np.isfinite([radius, half_length]).all() or min(radius, half_length) <= 0:
            raise ValueError(f"Invalid native cylinder dimensions on {name}")
        return fcl.Cylinder(float(radius), float(2 * half_length)), np.array([radius, radius, half_length])
    if geom_type == mujoco.mjtGeom.mjGEOM_BOX:
        if not np.isfinite(size).all() or np.any(size <= 0):
            raise ValueError(f"Invalid native box dimensions on {name}")
        return fcl.Box(*map(float, 2 * size)), size.copy()
    if geom_type == mujoco.mjtGeom.mjGEOM_SPHERE:
        radius = float(size[0])
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError(f"Invalid native sphere radius on {name}")
        return fcl.Sphere(radius), np.full(3, radius)
    raise ValueError(f"Unsupported MuJoCo arm collision geometry {geom_type} on {name}")


def _triangle_bvh(mesh: TriangleMesh) -> _MeshShape | None:
    """Build an FCL surface hierarchy without filling holes or concavities.

    Zero-area triangles have no collision surface. The caller maintains the
    original TriangleMesh and its face numbering separately for dose.
    """
    triangles = mesh.triangles[mesh.areas > 0]
    if not len(triangles):
        return None
    vertices = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
    faces = np.ascontiguousarray(triangles, dtype=np.int32)
    geometry = fcl.BVHModel()
    geometry.beginModel(len(faces), len(vertices))
    geometry.addSubModel(vertices, faces)
    geometry.endModel()
    used = vertices[np.unique(faces)]
    lower, upper = used.min(axis=0), used.max(axis=0)
    return _MeshShape(geometry, (lower + upper) / 2, (upper - lower) / 2)


class SceneClearance:
    """Measure sampled arm self-clearance and distance to observed scene surfaces.

    Place the arm with NativeArm.set_q and pass CoatingScene.place output to
    each at call. Local mesh hierarchies are reused across changes in pose.
    The scene mesh represents its indexed surface. A wholly enclosed arm
    primitive can remain separated from that surface, even for a closed
    mesh. Continuous motion certification belongs to the trajectory caller.
    """

    def __init__(self, arm: NativeArm) -> None:
        """Build an FCL collision primitive for every native arm geom."""
        self.arm = arm
        shapes = []
        for geom in arm.arm_geoms:
            native = geom.geom_id
            geometry, extent = _primitive(int(arm.model.geom_type[native]), arm.model.geom_size[native], geom.name)
            shapes.append(_ArmShape(native, fcl.CollisionObject(geometry), extent))
        self._shapes = tuple(shapes)
        indices = {item.geom_id: i for i, item in enumerate(self._shapes)}
        self._pairs = tuple((indices[left], indices[right]) for left, right in arm.self_pairs)
        self._meshes: WeakKeyDictionary[TriangleMesh, _MeshShape | None] = WeakKeyDictionary()
        self._collide = fcl.CollisionRequest(num_max_contacts=1, enable_contact=False)
        self._distance = fcl.DistanceRequest(enable_nearest_points=False, enable_signed_distance=False)

    def _scene_mesh(self, mesh: TriangleMesh) -> _MeshShape | None:
        """Return the local hierarchy for a currently referenced mesh."""
        if mesh not in self._meshes:
            self._meshes[mesh] = _triangle_bvh(mesh)
        return self._meshes[mesh]

    def _place_arm(self) -> tuple[FloatArray, FloatArray]:
        """Set FCL poses and return conservative world AABBs in arm shape order."""
        centers = np.empty((len(self._shapes), 3))
        extents = np.empty_like(centers)
        for index, shape in enumerate(self._shapes):
            rotation = self.arm.data.geom_xmat[shape.geom_id].reshape(3, 3)
            position = self.arm.data.geom_xpos[shape.geom_id]
            shape.collider.setTransform(fcl.Transform(rotation, position))
            centers[index] = position
            extents[index] = np.abs(rotation) @ shape.local_half_extents
        return centers, extents

    def _self_clearance(self, centers: FloatArray, extents: FloatArray, cap: float) -> float:
        """Use proven separating AABBs to bound numerical native distance results."""
        best = cap
        for first, second in self._pairs:
            lower = float(np.linalg.norm(np.maximum(
                np.abs(centers[first] - centers[second]) - extents[first] - extents[second], 0.0,
            )))
            if lower > max(best, 0.0):
                continue
            estimate = mujoco.mj_geomDistance(
                self.arm.model, self.arm.data, self._shapes[first].geom_id, self._shapes[second].geom_id,
                cap, None,
            )
            if not math.isfinite(estimate):
                raise ValueError("Nonfinite native arm self-distance")
            # Disjoint containing boxes certify separation even if the native
            # primitive query returns a spurious zero for this placement.
            if lower > 1e-10:
                estimate = max(estimate, lower)
            best = min(best, estimate)
        return best

    def at(self, bodies: Iterable[RigidBody], *, distance_cap_m: float = 1.0) -> float:
        """Return the minimum sampled distance from the current arm pose.

        Args:
            bodies: Part, fixtures and world mesh placements from this sample.
            distance_cap_m: Positive finite bound at which to clip separation.

        Returns:
            Nonnegative clipped separation, a negative native self-penetration,
            or `INTERSECTION_M` if an external triangle intersects the arm.
            The intersection marker represents failure, not a penetration depth.

        Raises:
            ValueError: Invalid distance cap or a nonfinite native distance.
        """
        if not math.isfinite(distance_cap_m) or distance_cap_m <= 0:
            raise ValueError("Clearance cap must be finite and positive")
        centers, arm_extents = self._place_arm()
        best = self._self_clearance(centers, arm_extents, distance_cap_m)
        if best < 0:
            return best
        for body in bodies:
            mesh = self._scene_mesh(body.mesh)
            if mesh is None:
                continue
            center = body.rotation @ mesh.center + body.translation
            extent = np.abs(body.rotation) @ mesh.half_extents
            axis_gap = np.maximum(np.abs(centers - center) - arm_extents - extent, 0.0)
            lower = np.linalg.norm(axis_gap, axis=1)
            eligible = np.flatnonzero(lower <= best + 1e-12)
            if not len(eligible):
                continue
            collider = fcl.CollisionObject(mesh.geometry, fcl.Transform(body.rotation, body.translation))
            # A box overlap triggers the explicit intersection test. Distance
            # queries alone do not reliably report signed mesh penetration.
            for index in eligible:
                if lower[index] > best + 1e-12:
                    continue
                primitive = self._shapes[index].collider
                if (lower[index] <= 1e-12
                        and fcl.collide(primitive, collider, self._collide, fcl.CollisionResult()) > 0):
                    return INTERSECTION_M
                distance = fcl.distance(primitive, collider, self._distance, fcl.DistanceResult())
                if not math.isfinite(distance):
                    raise ValueError(f"Nonfinite FCL distance to body {body.body_id}")
                if distance < 0:
                    return INTERSECTION_M
                best = min(best, distance)
        return best
