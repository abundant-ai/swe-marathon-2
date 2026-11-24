"""Planar pose composition for timestamped transformations."""

from math import atan2, cos, sin

Pose = tuple[float, float, float]


def wrap(angle: float) -> float:
    """Reduce an angle in radians using the usual signed principal value."""
    return atan2(sin(angle), cos(angle))


def compose(a: Pose, b: Pose) -> Pose:
    """Compose a destination-from-intermediate and intermediate-from-source pose."""
    x, y, yaw = a
    u, v, bearing = b
    c, s = cos(yaw), sin(yaw)
    return x + c * u - s * v, y + s * u + c * v, wrap(yaw + bearing)


def inverse(pose: Pose) -> Pose:
    """Reverse the direction of the supplied transform."""
    x, y, yaw = pose
    c, s = cos(yaw), sin(yaw)
    return -c * x - s * y, s * x - c * y, -yaw
