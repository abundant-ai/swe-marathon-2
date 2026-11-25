"""Measure coating recipe evidence from published joint and flow observations."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any, Protocol

import numpy as np

from coating_scene import CoatingScene, Pose
from surface_dose import AxisHit, DoseScore, RigidBody, SurfaceDose, first_hit
from trajectory import Knot, Segment, Vector, sample_process, segments


class ArmState(Protocol):
    """Native or independent arm kinematics supplied by the verifier."""

    def set_q(self, q_rad: tuple[float, ...]) -> None: ...
    def world_from_tool(self) -> Pose: ...


@dataclass(frozen=True)
class TraceEvidence:
    """Process measurements for the intervals accumulated in one session ledger."""

    dose: DoseScore
    emitted_ml: float
    enabled_samples: int
    off_recipe_samples: int
    max_normal_error_rad: float
    min_standoff_m: float | None
    max_standoff_m: float | None
    min_surface_speed_mps: float | None
    max_surface_speed_mps: float | None

@dataclass(frozen=True)
class AxisObservation:
    """Nozzle origin, direction and surfaces at one independent sample."""

    origin: Pose
    direction: Pose
    bodies: tuple[RigidBody, ...]


def above_limits(value: float, limits: tuple[float, float]) -> bool:
    """Report a finite sample outside the recipe's inclusive interval."""
    low, high = limits
    return value < low or value > high or not math.isfinite(value)


def valid_axis(hit: AxisHit | None, targets: frozenset[int]) -> bool:
    """Determine whether the nozzle first intersects a target on the part."""
    return hit is not None and hit.body_id == "part" and hit.face_index in targets


class ProcessTrace:
    """Accumulate part-local coating from disjoint measured controller intervals."""

    def __init__(
        self, scene: CoatingScene, target_faces: list[int], recipe: Mapping[str, Any], *,
        subdivisions: int = 4, max_cell_edge_m: float | None = None,
    ) -> None:
        self.scene = scene
        self.targets = frozenset(target_faces)
        self.recipe = recipe
        self.meter = SurfaceDose(
            scene.part, target_faces, subdivisions=subdivisions, max_cell_edge_m=max_cell_edge_m,
        )
        self.emitted_ml = 0.0
        self.enabled = 0
        self.off_recipe = 0
        self.max_normal = 0.0
        self.distances: list[float] = []
        self.speeds: list[float] = []

    def append(
        self, arm: ArmState, knots: tuple[Knot, ...], home: Pose, *, max_step_ns: int,
    ) -> None:
        """Integrate one chronological trace fragment using its own registration.

        Args:
            arm: Model using native forward kinematics and independent joint state.
            knots: Validated trajectory or previously unseen receipt fragment.
            home: Registration fixed for this issued motion.
            max_step_ns: Maximum quadrature substep in integer nanoseconds.

        The caller is responsible for proving fragment disjointness, for checking
        continuous clearance, and for benchmarking margins under finer sampling.
        """
        for segment in segments(knots):
            if segment.left.flow_ml_s == 0:
                continue
            for sample in sample_process((segment.left, segment.right), max_step_ns):
                self.enabled += 1
                self.emitted_ml += sample.flow_ml_s * sample.duration_s
                axis = self._place(arm, sample.q_rad, home)
                hit = self.meter.sample(
                    axis.bodies, axis.origin, axis.direction, flow_ml_s=sample.flow_ml_s,
                    duration_s=sample.duration_s, cone_half_angle_rad=self.recipe["cone_half_angle_rad"],
                )
                if hit is None or not valid_axis(hit, self.targets):
                    self.off_recipe += 1
                    continue
                speed = self._hit_speed(arm, segment, sample.t_ns, home)
                self.distances.append(hit.distance_m)
                self.max_normal = max(self.max_normal, hit.normal_error_rad)
                if speed is not None:
                    self.speeds.append(speed)
                if (above_limits(hit.distance_m, tuple(self.recipe["standoff_m"]))
                        or hit.normal_error_rad > self.recipe["max_normal_error_rad"]
                        or speed is None or above_limits(speed, tuple(self.recipe["surface_speed_mps"]))):
                    self.off_recipe += 1

    def _place(self, arm: ArmState, q_rad: Vector, home: Pose) -> AxisObservation:
        """Recover the tool axis and placed surfaces at a sample."""
        arm.set_q(q_rad[:6])
        tool = arm.world_from_tool()
        return AxisObservation(tool[:3, 3], tool[:3, 2], self.scene.place(q_rad[6], home))

    def _hit_speed(self, arm: ArmState, segment: Segment, t_ns: float, home: Pose) -> float | None:
        """Estimate part-frame hit speed with a centered derivative inside a segment.

        Use the controller polynomial with or without an adjacent receipt. If
        the part surface cannot be tracked on both sides, return no usable speed.
        """
        fraction = (t_ns - segment.left.t_ns) / (segment.right.t_ns - segment.left.t_ns)
        ds = min(1e-4 / segment.seconds, 0.5 * fraction, 0.5 * (1 - fraction))
        if ds <= 0:
            return None
        points = []
        for time in (fraction - ds, fraction + ds):
            position, _ = segment.at(time)
            axis = self._place(arm, position, home)
            hit = first_hit(axis.bodies, axis.origin, axis.direction)
            if hit is None or hit.part_point is None:
                return None
            points.append(hit.part_point)
        return float(np.linalg.norm(points[1] - points[0]) / (2 * ds * segment.seconds))

    def evidence(self) -> TraceEvidence:
        """Summarize observed motion and material accumulated through the last fragment."""
        return TraceEvidence(
            self.meter.score(self.recipe), self.emitted_ml, self.enabled, self.off_recipe, self.max_normal,
            min(self.distances, default=None), max(self.distances, default=None),
            min(self.speeds, default=None), max(self.speeds, default=None),
        )
