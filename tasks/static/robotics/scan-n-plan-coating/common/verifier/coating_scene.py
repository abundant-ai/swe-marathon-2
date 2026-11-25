"""Place coating geometry from a job and independent rotary-axis readback."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from surface_dose import RigidBody, TriangleMesh

Pose = NDArray[np.float64]


def rigid_pose(value: Mapping[str, Any]) -> Pose:
    """Interpret the public translation/quaternion convention as a rigid transform.

    Args:
        value: Pose object with metres and an XYZW unit quaternion.

    Returns:
        A homogeneous transform mapping source points into the destination frame.

    Raises:
        ValueError: An invalid vector, quaternion or transform.
    """
    translation = np.array(value["translation_m"], dtype=np.float64)
    quaternion = np.array(value["quaternion_xyzw"], dtype=np.float64)
    if (translation.shape != (3,) or quaternion.shape != (4,)
            or not np.isfinite(translation).all() or not np.isfinite(quaternion).all()):
        raise ValueError("Invalid rigid pose")
    norm = float(np.linalg.norm(quaternion))
    if abs(norm - 1.0) > 1e-6:
        raise ValueError("Pose quaternion is not a unit quaternion")
    x, y, z, w = quaternion / norm
    rotation = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    return transform


def rotate_z(angle_rad: float) -> Pose:
    """Return the rotation about the calibrated axis's positive Z."""
    cosine, sine = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([
        [cosine, -sine, 0.0, 0.0],
        [sine, cosine, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ])


def mesh(value: Mapping[str, Any]) -> TriangleMesh:
    """Build a ray mesh while preserving the public part face numbering."""
    return TriangleMesh(value["vertices_m"], value["triangles"])


@dataclass(frozen=True)
class CoatingScene:
    """Fixed job geometry and its transforms, reusable across trace samples."""

    part: TriangleMesh
    base_from_axis: Pose
    axis_from_base: Pose
    fixtures: tuple[RigidBody, ...]
    world: tuple[RigidBody, ...]

    @classmethod
    def from_job(cls, job: Mapping[str, Any]) -> "CoatingScene":
        """Parse the trusted geometry once before evaluating a trace."""
        axis = rigid_pose(job["base_from_axis"])
        fixtures, world = (
            tuple(
                RigidBody(entry["id"], mesh(entry["mesh"]), rigid_pose(entry["pose"]))
                for entry in job.get(field, ())
            )
            for field in ("fixture_collision", "world_collision")
        )
        return cls(mesh(job["part_mesh"]), axis, np.linalg.inv(axis), fixtures, world)

    def place(self, positioner_rad: float, base_from_part_home: Pose) -> tuple[RigidBody, ...]:
        """Place meshes for one measured axis angle and registration epoch.

        Args:
            positioner_rad: Current signed positioner angle in radians.
            base_from_part_home: Home part pose belonging to this trace interval.

        Returns:
            Part, moving fixtures and fixed world surfaces in the robot base frame.
            A new registration changes only the part transform, not the fixtures.
        """
        base_from_rotated_axis = self.base_from_axis @ rotate_z(positioner_rad)
        part = RigidBody("part", self.part, base_from_rotated_axis @ self.axis_from_base @ base_from_part_home)
        moving = tuple(
            RigidBody(entry.body_id, entry.mesh, base_from_rotated_axis @ entry.world_from_body)
            for entry in self.fixtures
        )
        return (part, *moving, *self.world)
