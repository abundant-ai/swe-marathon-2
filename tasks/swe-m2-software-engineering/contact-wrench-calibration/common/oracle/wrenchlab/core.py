"""Planar arm wrench transformations and commissioned compliant contact prediction."""

from dataclasses import dataclass
from math import atan2, cos, isfinite, pi, sin
from statistics import median

import numpy as np


def object_of(value):
    """Require a JSON object."""
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def list_of(value):
    """Require a JSON array."""
    if not isinstance(value, list):
        raise ValueError("expected an array")
    return value


def identifier(value):
    """Read a nonempty identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError("invalid identifier")
    return value


def number(value, positive=False):
    """Read a finite number, optionally requiring positivity."""
    if type(value) not in (int, float) or not isfinite(value) or (positive and value <= 0):
        raise ValueError("invalid number")
    return float(value)


def vector(value, size=2, positive=False):
    """Read an exactly sized, finite numeric vector."""
    items = list_of(value)
    if len(items) != size:
        raise ValueError("invalid vector size")
    return np.array([number(item, positive) for item in items])


def rotation(angle):
    """Convert a planar counterclockwise angle to a proper rotation."""
    return np.array([[cos(angle), -sin(angle)], [sin(angle), cos(angle)]])


def cross(a, b):
    """Compute the out-of-plane cross product."""
    return a[0] * b[1] - a[1] * b[0]


def link(length, angle):
    """Return a planar link vector."""
    return length * np.array([cos(angle), sin(angle)])


def tangent(point):
    """Rotate a displacement by a positive right angle."""
    return np.array([-point[1], point[0]])


@dataclass(frozen=True)
class Arm:
    """Measured 2R arm dimensions in a surveyed lab frame."""

    lengths: np.ndarray
    origin: np.ndarray
    angle: float
    offset: np.ndarray

    @classmethod
    def read(cls, data):
        """Load commissioned arm dimensions."""
        base = object_of(data["world_from_base"])
        return cls(vector(data["lengths_m"], positive=True), vector(base["xy"]),
                   number(base["yaw_rad"]), vector(data["pusher_offset_m"]))

    def coordinates(self, q):
        """Evaluate tool angle, pusher point and the point Jacobian."""
        first, second = self.angle + q[0], self.angle + q[0] + q[1]
        elbow = link(self.lengths[0], first)
        distal = link(self.lengths[1], second) + rotation(second) @ self.offset
        return second, self.origin + elbow + distal, np.column_stack((tangent(elbow + distal), tangent(distal)))


@dataclass(frozen=True)
class Calibrated:
    """A fixed sensor mount and sensor-axis additive bias."""

    offset: np.ndarray
    angle: float
    bias: np.ndarray

    @classmethod
    def read(cls, data):
        """Read the previously fitted sensor calibration."""
        mount = object_of(data["tool_from_sensor"])
        return cls(vector(mount["xy"]), number(mount["yaw_rad"]), vector(data["bias"], 3))

    def world(self, arm, angle, reading):
        """Recover world force and its moment about the pusher point."""
        clean = reading - self.bias
        world = rotation(angle + self.angle) @ clean[:2]
        lever = rotation(angle) @ (self.offset - arm.offset)
        return np.array([*world, clean[2] + cross(lever, world)])


def transform(spec):
    """Convert all submitted sensor readings into pusher and joint quantities."""
    arm = Arm.read(object_of(spec["arm"]))
    calibrated = Calibrated.read(object_of(spec["calibration"]))
    result = []
    used = set()
    for row in map(object_of, list_of(spec["samples"])):
        key = identifier(row["id"])
        if key in used:
            raise ValueError("duplicate sample ID")
        used.add(key)
        angle, pusher, J = arm.coordinates(vector(row["q"]))
        wrench = calibrated.world(arm, angle, vector(row["raw_wrench"], 3))
        joint_torque = J.T @ wrench[:2] + wrench[2]
        result.append({"id": key, "pusher_position_m": pusher.tolist(), "world_wrench": wrench.tolist(),
                       "joint_torque_nm": joint_torque.tolist()})
    return {"samples": result}


def robust_fit(design, response):
    """Estimate a small full-rank linear model from a dominant set of measurements."""
    count, columns = design.shape
    if count < columns or np.linalg.matrix_rank(design) < columns:
        return None
    random = np.random.default_rng(713)
    proposals = [np.linalg.lstsq(design, response, rcond=None)[0]]
    for _ in range(64):
        subset = random.choice(count, columns, replace=False)
        if np.linalg.matrix_rank(design[subset]) == columns:
            proposals.append(np.linalg.lstsq(design[subset], response[subset], rcond=None)[0])
    def score(value):
        residuals = np.abs(design @ value - response)
        count_used = max(columns, (3 * count) // 4)
        return np.sum(np.sort(residuals)[:count_used] ** 2)
    best = min(proposals, key=score)
    error = np.abs(design @ best - response)
    cutoff = max(3.5 * np.median(error), 1e-8)
    keep = error <= cutoff
    if np.count_nonzero(keep) >= columns and np.linalg.matrix_rank(design[keep]) == columns:
        best = np.linalg.lstsq(design[keep], response[keep], rcond=None)[0]
    return best


def calibrate(spec):
    """Fit sensor yaw, translation and bias from repeated known wrench applications."""
    Arm.read(object_of(spec["arm"]))
    records = []
    used = set()
    for row in map(object_of, list_of(spec["samples"])):
        key = identifier(row["id"])
        if key in used:
            raise ValueError("duplicate sample ID")
        used.add(key)
        vector(row["q"])
        records.append((vector(row["raw_wrench"], 3), vector(row["reference_tool_wrench"], 3)))
    if len(records) < 5:
        raise ValueError("at least five samples are required")
    raw, true = (np.stack(column) for column in zip(*records))
    design = np.column_stack((true[:, 1], -true[:, 0], -np.ones(len(records))))
    if np.linalg.matrix_rank(design) < 3:
        return {"status": "insufficient_excitation", "calibration": None}
    measured, applied = [values[:, 0] + 1j * values[:, 1] for values in (raw, true)]
    angles = []
    for i, applied_i in enumerate(applied):
        for j, applied_j in enumerate(applied[:i]):
            difference = measured[i] - measured[j]
            if abs(difference) > 1e-8 and abs(applied_i - applied_j) > 1e-8:
                ratio = (applied_i - applied_j) / difference
                angles.append(ratio / abs(ratio))
    if not angles:
        return {"status": "insufficient_excitation", "calibration": None}
    yaw = atan2(median(z.imag for z in angles), median(z.real for z in angles))
    force_bias = np.median(raw[:, :2] - true[:, :2] @ rotation(yaw), axis=0)
    x, y, torque_bias = map(float, robust_fit(design, true[:, 2] - raw[:, 2]))
    return {"status": "ok", "calibration": {"tool_from_sensor": {"xy": [x, y], "yaw_rad": yaw},
                                               "bias": [*force_bias.tolist(), torque_bias]}}


def feature(arm, step, point, velocity, radius):
    """Evaluate penetration and relative normal velocity at a command boundary."""
    angle, pusher, J = arm.coordinates(vector(step["q"]))
    drive = J @ vector(step["dq"])
    displacement = point - pusher
    distance = np.linalg.norm(displacement)
    if not 0 < distance < radius:
        return angle, np.zeros(2), np.zeros(2)
    n = displacement / distance
    return angle, n, np.array([radius - distance, n @ (drive - velocity)])


def qualify(spec):
    """Identify a compliant contact law and replay disjoint validation drives."""
    arm = Arm.read(object_of(spec["arm"]))
    calibrated = Calibrated.read(object_of(spec["calibration"]))
    body = object_of(spec["object"])
    mass = number(body["mass_kg"], True)
    radius = number(body["radius_m"], True) + number(body["pusher_radius_m"], True)
    dt = number(spec["dt_s"], True)
    runs = []
    seen = set()
    for entry in map(object_of, list_of(spec["validation"])):
        name = identifier(entry["id"])
        if name in seen:
            raise ValueError("duplicate validation ID")
        seen.add(name)
        points = list(map(object_of, list_of(entry["controls"])))
        for step in points:
            vector(step["q"])
            vector(step["dq"])
        runs.append((name, vector(entry["initial_position_m"]), vector(entry["initial_velocity_m_s"]), points))
    normal, values, velocity_rows, drags = [], [], [], []
    for sample in map(object_of, list_of(spec["fit"])):
        point, velocity = vector(sample["position_m"]), vector(sample["velocity_m_s"])
        after = vector(sample["next_velocity_m_s"])
        angle, direction, predictors = feature(arm, sample, point, velocity, radius)
        force = calibrated.world(arm, angle, vector(sample["raw_wrench"], 3))[:2]
        projection = float(force @ direction)
        if predictors[0] > 0 and projection > 1e-8:
            normal.append(predictors)
            values.append(projection)
        velocity_rows.append(velocity)
        drags.append(force - mass * (after - velocity) / dt)
    present = {"status": "insufficient_excitation", "parameters": None, "runs": []}
    if len(normal) < 3:
        return present
    contact = robust_fit(np.array(normal), np.array(values))
    if contact is None or contact[0] <= 0:
        return present
    measured_vel, observed_drag = np.array(velocity_rows), np.array(drags)
    coefficients = []
    for i in range(2):
        keep = np.abs(measured_vel[:, i]) > 1e-6
        if np.count_nonzero(keep) < 3:
            return present
        estimate = robust_fit(measured_vel[keep, i:i + 1], observed_drag[keep, i])
        coefficients.append(max(0., float(estimate[0])))
    k, c = float(contact[0]), max(0., float(contact[1]))
    parameters = {"stiffness_n_m": k, "damping_n_s_m": c, "drag_n_s_m": coefficients}
    records = []
    for name, point, velocity, controls in runs:
        samples = []
        for step in controls:
            _, direction, features = feature(arm, step, point, velocity, radius)
            force = max(0., np.array([k, c]) @ features) * direction
            velocity = velocity + dt * (force - np.array(coefficients) * velocity) / mass
            point = point + dt * velocity
            samples.append({"force_n": force.tolist(), "position_m": point.tolist(), "velocity_m_s": velocity.tolist()})
        records.append({"id": name, "steps": samples})
    return {"status": "ok", "parameters": parameters, "runs": records}
