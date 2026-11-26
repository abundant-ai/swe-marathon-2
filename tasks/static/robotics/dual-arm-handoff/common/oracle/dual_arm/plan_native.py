"""Synthesize task-space grasps and timed joint-space motion in a native cell."""

from dataclasses import dataclass
from math import ceil

import numpy as np

from .native_cell import (
    ARMS,
    Geometry,
    angular_delta,
    assemble,
    number,
    pose,
    positive_int,
    vector,
)

DT = 0.005


def canonical(values):
    return np.concatenate([vector(values[key], 6) for key in ARMS])


def grouped(q):
    return {key: q[i * 6 : i * 6 + 6].tolist() for i, key in enumerate(ARMS)}


@dataclass(frozen=True)
class Problem:
    geometry: Geometry
    start: np.ndarray
    velocity: np.ndarray
    speed: np.ndarray
    acceleration: np.ndarray
    tick: int
    deadline: int
    owner: str
    receiver: str
    stations: tuple
    goal: np.ndarray
    margin: float
    dwell: int

    @classmethod
    def read(cls, spec):
        if "layout" in spec:
            # Stage 7 windows can name the drawn staging cell instead.
            from .drawn_cell import resolve

            spec = resolve(spec)
        model = spec["calibration"]
        if model["status"] != "ok" or set(model["calibration"]) != set(ARMS):
            raise ValueError("commissioned arm calibration required")
        start = spec["measured"]
        owner, receiver = start["owner"], spec["destination"]["owner"]
        if owner not in ARMS or receiver not in ARMS:
            raise ValueError("invalid payload authority")
        tick, deadline = (
            positive_int(start["tick"], 0),
            positive_int(spec["deadline_tick"], 0),
        )
        if not tick <= deadline <= tick + 7000:
            raise ValueError("invalid native planning horizon")
        stations = spec["handoff_object_poses"]
        fixtures = spec["fixtures"]
        if (
            not isinstance(stations, list)
            or len(stations) > 8
            or not isinstance(fixtures, list)
            or len(fixtures) > 16
        ):
            raise ValueError("invalid fixture or handoff list")
        speed = vector(spec["speed_rad_s"], 12, positive=True)
        accel = vector(spec["acceleration_rad_s2"], 12, positive=True)
        margin = number(spec["clearance_m"], positive=True)
        dwell = positive_int(spec["transfer_ticks"])
        cell = assemble(
            spec["robot_xml"], model["calibration"], spec["payload"], fixtures
        )
        q, v = canonical(start["q"]), canonical(start["dq"])
        bounds = cell.ranges
        if np.any(q < bounds[:, 0]) or np.any(q > bounds[:, 1]):
            raise ValueError("measured joint outside range")
        return cls(
            Geometry(cell),
            q,
            v,
            speed,
            accel,
            tick,
            deadline,
            owner,
            receiver,
            tuple(map(pose, stations)),
            pose(spec["destination"]["world_from_object"]),
            margin,
            dwell,
        )


def inside(problem, point):
    limits = problem.geometry.cell.ranges
    return bool(np.all(point >= limits[:, 0]) and np.all(point <= limits[:, 1]))


def certified(problem, start, stop, owner):
    """Certify every configuration on a line, independent of its monotone timing law."""
    clearance = lambda q: problem.geometry.distance(q, owner, problem.margin)
    if (
        not inside(problem, stop)
        or min(clearance(start), clearance(stop)) < problem.margin
    ):
        return False
    displacement = stop - start
    # The namespaced UR5e with the bounded tool and payload fits within
    # a 2.8 m downstream lever. Both bodies in a pair can move.
    rate = 5.6 * sum(np.abs(displacement))
    queue = [(0.0, 1.0)]
    while queue:
        a, b = queue.pop()
        mid = (a + b) / 2
        value = clearance(start + mid * displacement)
        if value < problem.margin:
            return False
        if value - rate * (b - a) / 2 >= problem.margin:
            continue
        if b - a < 1.0 / 16384:
            return False
        queue.extend(((a, mid), (mid, b)))
    return True


def route(problem, start, stop, owner):
    """Try direct and staged transfers before extending a bounded joint-space tree."""
    if certified(problem, start, stop, owner):
        return [stop]
    for split in (np.r_[stop[:6], start[6:]], np.r_[start[:6], stop[6:]]):
        if certified(problem, start, split, owner) and certified(
            problem, split, stop, owner
        ):
            return [split, stop]
    rng = np.random.default_rng(331)
    nodes = [start]
    parents = [None]
    weight = np.ones(12)
    for attempt in range(220):
        choice = (
            stop
            if attempt % 4 == 0
            else (
                start
                + rng.uniform(0.0, 1.0) * (stop - start)
                + rng.normal(0.0, 0.38, 12)
            )
        )
        index = min(
            range(len(nodes)),
            key=lambda i: np.linalg.norm(weight * (nodes[i] - choice)),
        )
        at = nodes[index]
        change = choice - at
        length = np.linalg.norm(change)
        if length < 1e-9:
            continue
        new = at + min(0.27 / length, 1.0) * change
        if not certified(problem, at, new, owner):
            continue
        parents.append(index)
        nodes.append(new)
        if not certified(problem, new, stop, owner):
            continue
        path = [stop, new]
        parent = len(nodes) - 1
        while parents[parent] is not None:
            parent = parents[parent]
            if parent:
                path.append(nodes[parent])
        return list(reversed(path))
    return None


def solve_ik(problem, side, target, seed):
    """Search nearby elbow and wrist alternatives without receiving taught joint poses."""
    idx = 0 if side == "left" else 6
    generator = np.random.default_rng(73 + idx)
    hints = [seed]
    for count in range(1, 14):
        guess = seed.copy()
        guess[idx : idx + 6] += generator.normal(0.0, 0.34 + 0.047 * count, 6)
        hints.append(
            np.clip(
                guess,
                problem.geometry.cell.ranges[:, 0],
                problem.geometry.cell.ranges[:, 1],
            )
        )
    r = []
    grasp = target @ problem.geometry.cell.offsets[side]
    for hint in hints:
        solution = problem.geometry.ik(side, grasp, hint)
        if solution is not None and not any(
            np.linalg.norm(solution - old) < 0.02 for old in r
        ):
            r.append(solution)
            yield solution


def dual_ik(problem, target, seed):
    left = list(solve_ik(problem, "left", target, seed))
    if not left:
        return
    right = list(solve_ik(problem, "right", target, seed))
    for a in left:
        for b in right:
            yield np.r_[a, b]


def move_time(problem, start, stop):
    diag = abs(stop - start)
    length = max(
        np.max(1.5 * diag / problem.speed),
        np.max(np.sqrt(6.0 * diag / problem.acceleration)),
    )
    return max(3, ceil(length * 1.2 / DT))


def serialize(problem, q, first, path):
    """Assign exact rest-to-rest kinematics and a stationary transfer dwell."""
    commands, tick = [], first
    for primitive, value in path:
        if primitive == "transfer":
            end = tick + problem.dwell
            commands.append(
                {"kind": "transfer", "start": tick, "end": end, "to": value}
            )
        else:
            end = tick + move_time(problem, q, value)
            commands.append(
                {"kind": "move", "start": tick, "end": end, "q": grouped(value)}
            )
            q = value
        tick = end
    return commands if tick <= problem.deadline else None


def brake(problem):
    """Stop on measured velocity with constant acceleration and fixed custody."""
    if not np.any(abs(problem.velocity) > 1e-10):
        return None
    length = max(4, ceil(np.max(np.abs(problem.velocity) / problem.acceleration) / DT))
    q = problem.start + 0.5 * length * DT * problem.velocity
    end = problem.tick + length
    if (
        end > problem.deadline
        or np.any(abs(problem.velocity) > problem.speed)
        or not certified(problem, problem.start, q, problem.owner)
    ):
        return None
    return {"kind": "brake", "start": problem.tick, "end": end, "q": grouped(q)}, q


def near_pose(first, second, linear=0.013, angular=0.043):
    """Compare physical endpoint frames at the published metrology tolerance."""
    return (
        np.linalg.norm(first[:3, 3] - second[:3, 3]) <= linear
        and np.linalg.norm(angular_delta(first[:3, :3], second[:3, :3])) <= angular
    )


def plan_native(spec):
    """Find a physical route from current encoders and task-space grasp constraints."""
    p = Problem.read(spec)
    failed = {"status": "blocked", "commands": []}
    tick, start, prefix = p.tick, p.start, []
    if np.any(abs(p.velocity) > 0.025):
        stopped = brake(p)
        if stopped is None:
            return failed
        entry, start = stopped
        tick, prefix = entry["end"], [entry]
    if p.geometry.distance(start, p.owner, p.margin) < p.margin:
        return failed
    p.geometry.sites(start)
    object_at_start = p.geometry.payload_pose(p.owner)
    if p.owner == p.receiver:
        if near_pose(object_at_start, p.goal):
            return {"status": "ready", "commands": prefix}
        handoffs = [(start, [])]
    else:
        prospective = p.geometry.payload_pose(p.receiver)
        ready_here = near_pose(object_at_start, prospective) and any(
            near_pose(object_at_start, item) for item in p.stations
        )
        handoffs = [(start, [("transfer", p.receiver)])] if ready_here else []
        for station in p.stations if not ready_here else ():
            for paired in dual_ik(p, station, start):
                if (
                    min(p.geometry.distance(paired, side, p.margin) for side in ARMS)
                    < p.margin
                ):
                    continue
                path = route(p, start, paired, p.owner)
                if path is not None:
                    handoffs.append(
                        (
                            paired,
                            [*(("move", q) for q in path), ("transfer", p.receiver)],
                        )
                    )
                    break
    axis = slice(0, 6) if p.receiver == "left" else slice(6, 12)
    for paired, path in handoffs:
        for joint in solve_ik(p, p.receiver, p.goal, paired):
            finish = paired.copy()
            finish[axis] = joint
            if p.geometry.distance(finish, p.receiver, p.margin) < p.margin:
                continue
            final = route(p, paired, finish, p.receiver)
            if final is None:
                continue
            commands = serialize(p, start, tick, [*path, *(("move", q) for q in final)])
            if commands is not None:
                return {"status": "ready", "commands": prefix + commands}
    return failed
