"""Search and time safe paths from the measured joint configuration."""

from math import ceil
from random import Random

from .model import Joint, Object, Robot, integer, joint, number
from .motion import inspect_edge, mix, path_from, pose_safe, certify
from .scene import Scene, reconcile


def squared_distance(a: Joint, b: Joint) -> float:
    """Return the cost for nearest-neighbour search in three joint coordinates."""
    return sum((x - y) ** 2 for x, y in zip(a, b))


def certified_route(robot: Robot, scene: Scene, start: Joint, goal: Joint, margin: float) -> list[Joint] | None:
    """Find and shorten a route using bounded, deterministic bidirectional RRT."""
    if not (pose_safe(robot, scene, start, margin) and pose_safe(robot, scene, goal, margin)):
        return None

    def open_edge(a: Joint, b: Joint) -> bool:
        """Accept only a certified edge between in-bounds configurations."""
        return inspect_edge(robot, scene, a, b, margin).status == "valid"

    if open_edge(start, goal):
        return [start, goal]

    random = Random(2367)
    trees = [[(start, -1)], [(goal, -1)]]
    for iteration in range(1900):
        which = iteration % 2
        growing, other = trees[which], trees[1 - which]
        target = other[0][0] if iteration % 5 == 0 else tuple(random.uniform(a, b) for a, b in robot.limits)
        near = min(range(len(growing)), key=lambda index: squared_distance(growing[index][0], target))
        node = growing[near][0]
        difference = max(abs(a - b) for a, b in zip(node, target))
        step = mix(node, target, min(1.0, 0.30 / difference)) if difference > 0 else node
        if step == node or not open_edge(node, step):
            continue
        growing.append((step, near))
        other_near = min(range(len(other)), key=lambda index: squared_distance(other[index][0], step))
        if not open_edge(other[other_near][0], step):
            continue

        paths = []
        for tree, index in ((growing, len(growing) - 1), (other, other_near)):
            chain = []
            while index >= 0:
                q, index = tree[index]
                chain.append(q)
            paths.append(chain)
        if which:
            paths.reverse()
        route = paths[0][::-1] + paths[1]
        shortened = [route[0]]
        selected = 0
        while selected < len(route) - 1:
            reachable = len(route) - 1
            while reachable > selected + 1 and not open_edge(route[selected], route[reachable]):
                reachable -= 1
            shortened.append(route[reachable])
            selected = reachable
        return shortened
    return None


def timed_path(route: list[Joint], speeds: Joint) -> list[Object]:
    """Assign integer millisecond times with a small positive speed reserve."""
    rows = [{"time_ms": 0, "q": route[0]}]
    for start, end in zip(route, route[1:]):
        duration = ceil(1001 * max(abs(x - y) / speed for x, y, speed in zip(start, end, speeds)))
        rows.append({"time_ms": rows[-1]["time_ms"] + max(1, duration), "q": end})
    return rows


def recover(robot: Robot, spec: Object) -> Object:
    """Return an executable remaining path, a replacement, or a stop decision."""
    initial = spec["initial_scene"]
    scene = reconcile(robot, initial, spec["events"])
    if integer(spec["planned_revision"]) != initial["revision"]:
        raise ValueError("plan revision does not identify the initial scene")
    start, goal = joint(spec["measured_q"]), joint(spec["goal_q"])
    remaining = path_from(spec["remaining"])
    if remaining[-1][1] != goal:
        raise ValueError("remaining path goal does not agree with goal_q")
    margin = number(spec["margin_m"])
    if margin < 0:
        raise ValueError("negative clearance margin")
    if start == remaining[0][1] and certify(robot, scene, remaining, margin).status == "valid":
        return {"revision": scene.revision, "status": "unchanged", "trajectory": spec["remaining"]}
    route = certified_route(robot, scene, start, goal, margin)
    if route is None:
        return {"revision": scene.revision, "status": "stopped", "trajectory": None}
    return {"revision": scene.revision, "status": "replanned", "trajectory": timed_path(route, robot.speeds)}
