"""Independent trajectory checks using complex coordinates and distance bounds."""

from cmath import rect
from math import isclose, isfinite
from typing import Any

Json = dict[str, Any]


def axis_frame(robot: Json, q: list[float]) -> tuple[complex, complex, complex, complex]:
    """Return base, elbow, hand position and unit tool heading in world coordinates."""
    x, shoulder, elbow = q
    upper, lower = robot["lengths_m"]
    origin = complex(x, 0)
    pivot = origin + rect(upper, shoulder)
    heading = rect(1, shoulder + elbow)
    return origin, pivot, pivot + lower * heading, heading


def line_of(shape: Json) -> tuple[complex, complex, float]:
    """Read endpoints and radius from one capsule."""
    return complex(*shape["a"]), complex(*shape["b"]), shape["radius_m"]


def determinant(a: complex, b: complex) -> float:
    """Calculate the signed area of two vectors."""
    return (a.conjugate() * b).imag


def distances(a: complex, b: complex, p: complex) -> float:
    """Return the distance from p to the line segment ab."""
    difference = b - a
    if difference == 0:
        return abs(p - a)
    ratio = ((p - a) / difference).real
    return abs(p - (a + max(0.0, min(1.0, ratio)) * difference))


def separation(first: tuple, second: tuple) -> float:
    """Compute signed capsule clearance in metres."""
    a, b, r = first
    c, d, s = second
    d1, d2 = determinant(b - a, c - a), determinant(b - a, d - a)
    d3, d4 = determinant(d - c, a - c), determinant(d - c, b - c)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return -r - s
    return min(distances(a, b, c), distances(a, b, d), distances(c, d, a), distances(c, d, b)) - r - s


def measured_clearance(robot: Json, scene: Json, q: list[float]) -> float:
    """Measure minimum clearance over the specified world and body pairs."""
    base, pivot, hand, heading = axis_frame(robot, q)
    upper = (base, pivot, robot["radii_m"][0])
    lower = (pivot, hand, robot["radii_m"][1])
    body = [upper, lower]
    clearances = []
    if scene["attached"] is not None:
        a, b, radius = line_of(scene["attached"]["capsule"])
        attached = (hand + heading * a, hand + heading * b, radius)
        body.append(attached)
        clearances.append(separation(upper, attached))
    obstacles = [line_of(obstacle) for obstacle in scene["objects"].values()]
    clearances.extend(separation(part, obstacle) for part in body for obstacle in obstacles)
    return min(clearances, default=float("inf"))


def interpolate(a: list[float], b: list[float], u: float) -> list[float]:
    """Evaluate the controller interpolation at a fraction between the endpoints."""
    return [(1 - u) * left + u * right for left, right in zip(a, b, strict=True)]


def enough_clearance(robot: Json, scene: Json, a: list[float], b: list[float], margin: float) -> bool:
    """Prove clearance by sampling with a conservative unsampled travel allowance."""
    upper, lower = robot["lengths_m"]
    slide, shoulder, elbow = (abs(left - right) for left, right in zip(a, b, strict=True))
    reach = 0.0
    if scene["attached"] is not None:
        load = scene["attached"]["capsule"]
        reach = max(abs(complex(*load["a"])), abs(complex(*load["b"])))
    pair_distance_rate = 2 * (slide + upper * shoulder + (lower + reach) * (shoulder + elbow))

    intervals = [(0.0, 1.0)]
    inspected = 0
    while intervals and inspected < 8192:
        inspected += 1
        left, right = intervals.pop()
        middle = (left + right) / 2
        clearance = measured_clearance(robot, scene, interpolate(a, b, middle))
        if clearance < margin - 1e-8:
            return False
        if clearance - pair_distance_rate * (right - left) / 2 >= margin - 1e-9:
            continue
        if right - left < 1 / 65_536:
            return False
        intervals.extend(((left, middle), (middle, right)))
    return not intervals


def close(a: object, b: float, tolerance: float = 1e-8) -> bool:
    """Check a finite JSON number against an independently derived scalar."""
    try:
        return type(a) in (int, float) and isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
    except OverflowError:
        return False


def legal_trajectory(robot: Json, scene: Json, trajectory: object, start: list, goal: list, margin: float) -> bool:
    """Verify the proposed timed trajectory and swept geometry without the submission."""
    if not isinstance(trajectory, list) or len(trajectory) < 2:
        return False
    for row in trajectory:
        if not isinstance(row, dict) or type(row.get("time_ms")) is not int:
            return False
        q = row.get("q")
        if not isinstance(q, list) or len(q) != 3:
            return False
        try:
            if not all(type(x) in (int, float) and isfinite(x) and lo - 1e-9 <= x <= hi + 1e-9
                       for x, (lo, hi) in zip(q, robot["joint_limits"], strict=True)):
                return False
        except OverflowError:
            return False
    if trajectory[0]["time_ms"] != 0:
        return False
    if not all(close(x, y) for x, y in zip(trajectory[0]["q"], start, strict=True)):
        return False
    if not all(close(x, y) for x, y in zip(trajectory[-1]["q"], goal, strict=True)):
        return False

    for first, second in zip(trajectory, trajectory[1:]):
        dt = second["time_ms"] - first["time_ms"]
        if dt <= 0:
            return False
        a, b = first["q"], second["q"]
        if any(abs(x - y) * 1000 / speed > dt + 1e-7
               for x, y, speed in zip(a, b, robot["max_speeds"], strict=True)):
            return False
        if not enough_clearance(robot, scene, a, b, margin):
            return False
    return True
