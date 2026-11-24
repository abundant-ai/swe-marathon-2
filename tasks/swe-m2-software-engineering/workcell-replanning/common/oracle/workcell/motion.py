"""Validate interpolated joint motion with capsule distance and travel bounds."""

from collections.abc import Iterator
from dataclasses import dataclass
from math import hypot

from .model import Capsule, Joint, Point, Robot, array, frame, integer, joint, obj, world_point
from .scene import Scene

Path = list[tuple[int, Joint]]
EPSILON = 1e-10


@dataclass(frozen=True)
class MotionResult:
    """Validity and an optional parameter identifying an unsafe segment point."""

    status: str
    segment: int | None = None
    fraction: float | None = None


def path_from(value: object) -> Path:
    """Parse time and joint arrays without deciding whether they describe safe motion."""
    rows = [obj(row) for row in array(value)]
    path = [(integer(row["time_ms"]), joint(row["q"])) for row in rows]
    if len(path) < 2 or path[0][0] != 0 or any(a[0] >= b[0] for a, b in zip(path, path[1:])):
        raise ValueError("waypoint times must start at zero and increase")
    return path


def subtract(a: Point, b: Point) -> Point:
    """Subtract two planar points or vectors."""
    return a[0] - b[0], a[1] - b[1]


def dot(a: Point, b: Point) -> float:
    """Return the dot product of two planar vectors."""
    return a[0] * b[0] + a[1] * b[1]


def cross(a: Point, b: Point) -> float:
    """Return the signed area spanned by two planar vectors."""
    return a[0] * b[1] - a[1] * b[0]


def point_segment(p: Point, a: Point, b: Point) -> float:
    """Return point-to-segment distance, including a degenerate segment."""
    direction = subtract(b, a)
    from_a = subtract(p, a)
    norm_sq = dot(direction, direction)
    if norm_sq == 0:
        return hypot(*from_a)
    fraction = max(0.0, min(1.0, dot(from_a, direction) / norm_sq))
    return hypot(from_a[0] - fraction * direction[0], from_a[1] - fraction * direction[1])


def clearance(a: Capsule, b: Capsule) -> float:
    """Compute distance between the capsule centrelines minus both radii."""
    u, v = subtract(a.b, a.a), subtract(b.b, b.a)
    delta = subtract(b.a, a.a)
    determinant = cross(u, v)
    if determinant and 0 <= cross(delta, v) / determinant <= 1 and 0 <= cross(delta, u) / determinant <= 1:
        return -a.radius - b.radius
    distance = min(point_segment(p, b.a, b.b) for p in (a.a, a.b))
    distance = min(distance, *(point_segment(p, a.a, a.b) for p in (b.a, b.b)))
    return distance - a.radius - b.radius


def mix(a: Joint, b: Joint, fraction: float) -> Joint:
    """Evaluate the controller's joint-linear path at a segment parameter."""
    return tuple(x + fraction * (y - x) for x, y in zip(a, b))


def moving_capsules(robot: Robot, scene: Scene, q: Joint) -> list[Capsule]:
    """Build world-frame capsules for the links and current load."""
    base, elbow, tool, heading = frame(robot, q)
    shapes = [Capsule(base, elbow, robot.radii[0]), Capsule(elbow, tool, robot.radii[1])]
    if scene.load is not None:
        _, load = scene.load
        shapes.append(Capsule(world_point(load.a, tool, heading), world_point(load.b, tool, heading), load.radius))
    return shapes


def pair_clearances(robot: Robot, scene: Scene, q: Joint, travel: Joint) -> Iterator[tuple[float, float]]:
    """Yield measured pair clearance and a bound on its change per segment fraction."""
    shapes = moving_capsules(robot, scene, q)
    for shape, speed in zip(shapes, travel):
        for obstacle in scene.world.values():
            yield clearance(shape, obstacle), speed
    if len(shapes) == 3:
        yield clearance(shapes[0], shapes[2]), travel[0] + travel[2]


def travel_bound(robot: Robot, scene: Scene, start: Joint, end: Joint) -> Joint:
    """Bound centreline travel per unit segment fraction for each moving capsule."""
    base, shoulder, elbow = (b - a for a, b in zip(start, end))
    forearm_angle = abs(shoulder + elbow)
    upper_speed = abs(base) + robot.lengths[0] * abs(shoulder)
    forearm_speed = upper_speed + robot.lengths[1] * forearm_angle
    if scene.load is None:
        return upper_speed, forearm_speed, forearm_speed
    capsule = scene.load[1]
    load_reach = max(hypot(*capsule.a), hypot(*capsule.b))
    return upper_speed, forearm_speed, forearm_speed + load_reach * forearm_angle


def pose_safe(robot: Robot, scene: Scene, q: Joint, margin: float) -> bool:
    """Check joint bounds and clearance for one static configuration."""
    return robot.has_joint_position(q) and all(
        distance >= margin + EPSILON for distance, _ in pair_clearances(robot, scene, q, (0.0, 0.0, 0.0))
    )


def inspect_edge(robot: Robot, scene: Scene, start: Joint, end: Joint, margin: float) -> MotionResult:
    """Certify an entire geometric edge or return a witnessed or unresolved violation."""
    travel = travel_bound(robot, scene, start, end)
    for q, fraction in ((start, 0.0), (end, 1.0)):
        if any(distance < margin - EPSILON for distance, _ in pair_clearances(robot, scene, q, travel)):
            return MotionResult("collision", fraction=fraction)

    pending = [(0.0, 1.0, 0)]
    unresolved = False
    processed = 0
    while pending and processed < 16_384:
        lower, upper, depth = pending.pop()
        processed += 1
        middle = (lower + upper) / 2
        checks = list(pair_clearances(robot, scene, mix(start, end, middle), travel))
        if any(distance < margin - EPSILON for distance, _ in checks):
            return MotionResult("collision", fraction=middle)
        if all(distance - rate * (upper - lower) / 2 >= margin + EPSILON for distance, rate in checks):
            continue
        if depth == 18 or all(rate == 0 for _, rate in checks):
            unresolved = True
            continue
        pending.append((middle, upper, depth + 1))
        pending.append((lower, middle, depth + 1))
    return MotionResult("unresolved" if unresolved or pending else "valid")


def certify(robot: Robot, scene: Scene, path: Path, margin: float) -> MotionResult:
    """Apply global joint and speed precedence, then certify each geometric segment."""
    for index, (_, q) in enumerate(path):
        if not robot.has_joint_position(q):
            return MotionResult("joint_limit", max(index - 1, 0))
    for index, ((t0, start), (t1, end)) in enumerate(zip(path, path[1:])):
        seconds = (t1 - t0) / 1000
        if any(abs(a - b) > limit * seconds for a, b, limit in zip(start, end, robot.speeds)):
            return MotionResult("speed_limit", index)
    for index, ((_, start), (_, end)) in enumerate(zip(path, path[1:])):
        result = inspect_edge(robot, scene, start, end, margin)
        if result.status != "valid":
            return MotionResult(result.status, index, result.fraction)
    return MotionResult("valid")
