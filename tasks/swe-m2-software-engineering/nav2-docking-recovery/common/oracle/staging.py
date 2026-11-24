"""Search certified SE(2) staging primitives and maintain their progress."""

from heapq import heappop, heappush
from math import cos, hypot, pi, sin
from typing import Any

Record = dict[str, Any]


def moved(q: list[float], v: float, w: float, seconds: float) -> list[float]:
    """Integrate a constant body twist exactly for its command interval."""
    x, y, yaw = q
    theta = yaw + w * seconds
    if abs(w) < 1e-12:
        return [x + v * seconds * cos(yaw), y + v * seconds * sin(yaw), theta]
    return [x + v / w * (sin(theta) - sin(yaw)), y - v / w * (cos(theta) - cos(yaw)), theta]


def clearance(nav: Record, q: list[float]) -> float:
    """Compute a separating-axis lower bound on rectangular footprint clearance."""
    x, y, yaw = q
    hx, hy = (side + nav["margin_m"] for side in nav["footprint"])
    c, s = cos(yaw), sin(yaw)
    ex, ey = abs(c) * hx + abs(s) * hy, abs(s) * hx + abs(c) * hy
    a, b, d, e = nav["bounds"]
    gaps = [x - ex - a, d - x - ex, y - ey - b, e - y - ey]
    for x0, y0, x1, y1 in nav["obstacles"]:
        ox, oy = (x0 + x1) / 2 - x, (y0 + y1) / 2 - y
        bx, by = (x1 - x0) / 2, (y1 - y0) / 2
        gaps.append(max(abs(ox) - bx - ex, abs(oy) - by - ey,
                        abs(c * ox + s * oy) - (abs(c) * bx + abs(s) * by + hx),
                        abs(-s * ox + c * oy) - (abs(s) * bx + abs(c) * by + hy)))
    return min(gaps)


def sweep(nav: Record, pose: list[float], v: float, w: float, duration: float) -> bool:
    """Certify a continuous primitive using a rigid-body point-motion bound."""
    radius = hypot(*(side + nav["margin_m"] for side in nav["footprint"]))
    speed = abs(v) + abs(w) * radius
    pending = [(0.0, duration)]
    while pending:
        low, high = pending.pop()
        midpoint = (low + high) / 2
        gap = clearance(nav, moved(pose, v, w, midpoint))
        if gap <= 0:
            return False
        if gap > speed * (high - low) / 2 + 1e-10:
            continue
        if high - low < 1e-5:
            return False
        pending.extend(((low, midpoint), (midpoint, high)))
    return True


def valid_edges(nav: Record, dt: float) -> list[str]:
    """Return geometric and kinematic edges with certified nominal sweeps."""
    viable = []
    for edge in nav["edges"]:
        q = nav["nodes"][edge["source"]]
        for segment in edge["segments"]:
            v, w = segment["v_mps"], segment["w_radps"]
            duration = dt * segment["ticks"]
            if (not -nav["reverse_max_mps"] <= v <= nav["forward_max_mps"]
                    or abs(w) > nav["angular_max_radps"] or not sweep(nav, q, v, w, duration)):
                break
            q = moved(q, v, w, duration)
        else:
            viable.append(edge["id"])
    return viable


def choose(nav: Record, node: str, permitted: set[str]) -> str | None:
    """Use shortest taught travel time to pick the next available edge."""
    queue = [(0, node, "")]
    visited = set()
    while queue:
        score, start, first = heappop(queue)
        if start == nav["staging"]:
            return first or None
        if start in visited:
            continue
        visited.add(start)
        for edge in nav["edges"]:
            if edge["source"] == start and edge["id"] in permitted and edge["target"] not in visited:
                heappush(queue, (score + sum(segment["ticks"] for segment in edge["segments"]),
                                 edge["target"], first or edge["id"]))
    return None


def close(nav: Record, measured: list[float], node: str) -> bool:
    """Confirm that a world-frame measurement is within a taught pose tolerance."""
    x, y, a = nav["nodes"][node]
    qx, qy, qa = measured
    heading = (qa - a + pi) % (2 * pi) - pi
    return hypot(x - qx, y - qy) <= nav["position_tolerance_m"] and abs(heading) <= nav["heading_tolerance_rad"]


def staged(state: Record, config: Record, observation: Record) -> Record | None:
    """Drive or pause one certified tick, then hand off at a stationary staging pose."""
    nav = config.get("navigation")
    if nav is None or state.get("navigation_done"):
        return None
    progress = state.get("navigation_progress")
    if progress is None:
        progress = {"node": nav["start"], "edge": None, "offset": 0,
                    "legal": valid_edges(nav, config["tick_seconds"])}
        state["navigation_progress"] = progress
    hold = {"v_mps": 0.0, "w_radps": 0.0, "status": "running", "stage_edge": progress["edge"]}
    tick = observation["tick"]
    if tick >= config["deadline_tick"]:
        state["terminal"] = "failed"
        return hold | {"status": "failed"}
    map_pose = observation.get("map_pose")
    if map_pose is None or observation["odom"] is None:
        return hold
    if progress["edge"] is None:
        node = progress["node"]
        if not close(nav, map_pose, node):
            return hold
        if node == nav["staging"]:
            state.update(navigation_done=True, acquire_from=tick, track=None)
            return hold
        permitted = set(progress["legal"]) - set(observation.get("blocked_edges", []))
        progress["edge"] = choose(nav, node, permitted)
        if progress["edge"] is None:
            return hold
    edge = next(item for item in nav["edges"] if item["id"] == progress["edge"])
    offset = progress["offset"]
    for segment in edge["segments"]:
        if offset < segment["ticks"]:
            v, w = segment["v_mps"], segment["w_radps"]
            if not sweep(nav, map_pose, v, w, config["tick_seconds"]):
                return hold | {"stage_edge": edge["id"]}
            progress["offset"] += 1
            if progress["offset"] == sum(part["ticks"] for part in edge["segments"]):
                progress.update(node=edge["target"], edge=None, offset=0)
            return hold | {"v_mps": v, "w_radps": w, "stage_edge": edge["id"]}
        offset -= segment["ticks"]
    raise ValueError("invalid staging segment progress")
