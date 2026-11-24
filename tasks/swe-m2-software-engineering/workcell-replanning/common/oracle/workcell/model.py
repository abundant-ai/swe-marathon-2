"""Validate workcell data and transform its planar capsules."""

from dataclasses import dataclass
from math import cos, isfinite, sin
from typing import Any

Point = tuple[float, float]
Joint = tuple[float, float, float]
Object = dict[str, Any]


@dataclass(frozen=True)
class Capsule:
    """A closed centreline segment and positive radius in metres."""

    a: Point
    b: Point
    radius: float

    def encoded(self) -> Object:
        """Encode this capsule in the public JSON format."""
        return {"a": self.a, "b": self.b, "radius_m": self.radius}


@dataclass(frozen=True)
class Robot:
    """A prismatic base with two planar revolute links."""

    lengths: Point
    radii: Point
    limits: tuple[Point, Point, Point]
    speeds: Joint

    def has_joint_position(self, q: Joint) -> bool:
        """Check the inclusive bounds for a well-formed joint reading."""
        return all(lower <= value <= upper for value, (lower, upper) in zip(q, self.limits))


def obj(value: object) -> Object:
    """Require a JSON object."""
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def array(value: object, size: int | None = None) -> list:
    """Require an array, optionally of a fixed length."""
    if not isinstance(value, list) or (size is not None and len(value) != size):
        raise ValueError("invalid array")
    return value


def number(value: object, *, positive: bool = False) -> float:
    """Read a finite number, optionally strictly positive."""
    if type(value) not in (int, float) or not isfinite(value) or (positive and value <= 0):
        raise ValueError("invalid finite number")
    return float(value)


def integer(value: object) -> int:
    """Read an integer excluding booleans."""
    if type(value) is not int:
        raise ValueError("invalid integer")
    return value


def identifier(value: object) -> str:
    """Read a nonempty string identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError("invalid identifier")
    return value


def point(value: object, *, positive: bool = False) -> Point:
    """Read two finite numbers."""
    a, b = array(value, 2)
    return number(a, positive=positive), number(b, positive=positive)


def joint(value: object, *, positive: bool = False) -> Joint:
    """Read a finite base, shoulder and elbow tuple."""
    a, b, c = array(value, 3)
    return number(a, positive=positive), number(b, positive=positive), number(c, positive=positive)


def capsule(value: object) -> Capsule:
    """Read a capsule in the caller's coordinate frame."""
    data = obj(value)
    return Capsule(point(data["a"]), point(data["b"]), number(data["radius_m"], positive=True))


def robot_from(value: object) -> Robot:
    """Read the planar robot model with ordered joint limits."""
    data = obj(value)
    low_base, low_shoulder, low_elbow = map(point, array(data["joint_limits"], 3))
    limits = (low_base, low_shoulder, low_elbow)
    if any(lower >= upper for lower, upper in limits):
        raise ValueError("joint limit pairs must be increasing")
    return Robot(point(data["lengths_m"], positive=True), point(data["radii_m"], positive=True),
                 limits, joint(data["max_speeds"], positive=True))


def offset(p: Point, length: float, angle: float) -> Point:
    """Advance a point along a heading by a signed distance."""
    return p[0] + length * cos(angle), p[1] + length * sin(angle)


def frame(robot: Robot, q: Joint) -> tuple[Point, Point, Point, float]:
    """Compute world coordinates for the base, elbow and tool, plus tool heading."""
    base = (q[0], 0.0)
    elbow = offset(base, robot.lengths[0], q[1])
    heading = q[1] + q[2]
    tool = offset(elbow, robot.lengths[1], heading)
    return base, elbow, tool, heading


def rotate(p: Point, angle: float) -> Point:
    """Rotate a 2D vector around its coordinate origin."""
    return cos(angle) * p[0] - sin(angle) * p[1], sin(angle) * p[0] + cos(angle) * p[1]


def world_point(p: Point, origin: Point, heading: float) -> Point:
    """Apply a tool-to-world rigid transform to a point."""
    x, y = rotate(p, heading)
    return x + origin[0], y + origin[1]


def tool_point(p: Point, origin: Point, heading: float) -> Point:
    """Apply the world-to-tool rigid transform to a point."""
    return rotate((p[0] - origin[0], p[1] - origin[1]), -heading)
