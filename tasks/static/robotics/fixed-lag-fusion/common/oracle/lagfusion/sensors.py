"""Apply frozen calibration and produce independent linear pose factors."""

from dataclasses import dataclass
from math import cos, pi, sin

import numpy as np

from .contract import (
    Array,
    Json,
    Observation,
    covariance,
    delta_factor,
    integer,
    name,
    number,
    obj,
    projection_factor,
    vector,
)


@dataclass(frozen=True)
class Calibration:
    """A fixed wheel transform, signed offset, and per-anchor range bias."""

    offset: int
    wheel: Array
    biases: dict[str, float]


def calibration_from(value: object) -> Calibration:
    """Validate the successful estimate used by replay and ingestion."""
    data = obj(value)
    if data["status"] != "ok":
        raise ValueError("a successful calibration is required")
    angle = number(data["wheel_yaw_rad"])
    if not -pi <= angle <= pi:
        raise ValueError("wheel calibration yaw outside [-pi,pi]")
    scale = number(data["wheel_scale"], positive=True)
    wheel = scale * np.array([[cos(angle), -sin(angle)], [sin(angle), cos(angle)]])
    biases = {
        name(key): number(item) for key, item in obj(data["range_bias_m"]).items()
    }
    return Calibration(integer(data["offset_ticks"], None), wheel, biases)


@dataclass(frozen=True)
class Sensors:
    """Normalize raw factors from one commissioned sensor and anchor configuration."""

    calibration: Calibration | None
    anchors: dict[str, Array]

    def __call__(self, event: Json) -> Observation:
        """Return an observation at its corrected acquisition extent."""
        op = event["op"]
        if op == "imu":
            tick = integer(event["tick"])
            factor = delta_factor(
                tick, vector(event["value"]), covariance(event["covariance"])
            )
            return Observation(tick - 1, tick, factor)
        calibration = self.calibration
        if calibration is None:
            raise ValueError("wheel and range factors require calibration")
        if op == "wheel":
            tick = integer(event["device_tick"]) + calibration.offset
            A = calibration.wheel
            corrected = A @ vector(event["value"])
            uncertainty = A @ covariance(event["covariance"]) @ A.T
            uncertainty = (uncertainty + uncertainty.T) / 2
            return Observation(
                tick - 1, tick, delta_factor(tick, corrected, uncertainty)
            )

        tick = integer(event["tick"])
        first, second = name(event["anchor_a"]), name(event["anchor_b"])
        a, b = self.anchors[first], self.anchors[second]
        axis = b - a
        if first == second or not np.any(axis):
            raise ValueError("range pair requires two different anchor positions")
        raw_a = number(event["range_a_m"], nonnegative=True)
        raw_b = number(event["range_b_m"], nonnegative=True)
        variance = number(event["variance_m4"], positive=True)
        ra, rb = raw_a - calibration.biases[first], raw_b - calibration.biases[second]
        if min(ra, rb) < 0:
            return Observation(tick, tick, None)
        value = (ra * ra - rb * rb - float(a @ a) + float(b @ b)) / 2
        return Observation(tick, tick, projection_factor(tick, axis, value, variance))


def adapter_from(spec: Json) -> Sensors:
    """Construct a frozen adapter from the optional model fields in a request."""
    calibration = (
        calibration_from(spec["calibration"]) if "calibration" in spec else None
    )
    anchors = {
        name(key): vector(value) for key, value in obj(spec.get("anchors", {})).items()
    }
    return Sensors(calibration, anchors)
