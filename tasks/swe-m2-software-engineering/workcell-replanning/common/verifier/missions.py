"""Deterministic workcell missions using the original two-link arm and rail."""

from copy import deepcopy
from math import cos, sin


ROBOT = {
    "lengths_m": [1.0, 0.8],
    "radii_m": [0.045, 0.055],
    "joint_limits": [[-1.35, 1.35], [-1.6, 1.6], [-1.5, 1.5]],
    "max_speeds": [0.8, 1.25, 1.4],
}
START = [-0.45, -0.81, 0.69]
GOAL = [0.41, 0.91, -0.63]
DETOUR = [[-0.86, -1.30, 1.43], [-1.30, -0.96, 1.42], [-0.04, 0.75, -0.41]]
TICK_SECONDS = 0.25
MARGIN = 0.017
# Original obstructed-workcell shelves and posts, carried over in this case.
SHELVES_AND_POSTS = (
    ((0.4091, 1.6479), (0.2664, 1.6467), 0.1951),
    ((0.9040, -0.5567), (0.8169, -0.4334), 0.0705),
    ((2.8846, -0.5621), (3.0155, -0.4480), 0.0776),
    ((0.6362, -1.4793), (0.7710, -1.3869), 0.1946),
)


def capsule(a, b, radius):
    return {"a": list(a), "b": list(b), "radius_m": radius}


def carriage(x, y, angle=0.26, length=0.19):
    half_x = cos(angle) * length / 2
    half_y = sin(angle) * length / 2
    return [x - half_x, y - half_y], [x + half_x, y + half_y]


def track(radius, *frames):
    return {
        "radius_m": radius,
        "keyframes": [
            {"tick": tick, "a": a, "b": b}
            for tick, x, y, *heading in frames
            for a, b in [carriage(x, y, *heading)]
        ],
    }


def spec(*, start=None, goal=None, fixtures=(), moving=(), detour=(),
         measured_tick=0, dq=None, brake_ticks=0, deadline=38, edge_ticks=12,
         approach=None, payload=None):
    start = START if start is None else start
    goal = GOAL if goal is None else goal
    dq = [0.0, 0.0, 0.0] if dq is None else dq
    elapsed = brake_ticks * TICK_SECONDS
    measured = [q - velocity * elapsed / 2 for q, velocity in zip(start, dq, strict=True)]
    nodes = {"approach": list(start), "handoff": list(goal)}
    edges = [{"id": "through-gate", "source": "approach", "target": "handoff", "ticks": edge_ticks}]
    if approach is not None:
        nodes["staging"] = list(approach)
        edges.append({"id": "reach-approach", "source": "staging", "target": "approach", "ticks": 4})
        start_node = "staging"
        measured = list(approach)
    else:
        start_node = "approach"
    previous = "approach"
    for i, configuration in enumerate(detour, 1):
        name = f"bay-{i}"
        nodes[name] = list(configuration)
        edges.append({"id": f"detour-{i}", "source": previous, "target": name, "ticks": 10})
        previous = name
    if detour:
        edges.append({"id": "reach-handoff", "source": previous, "target": "handoff", "ticks": 9})
    return {
        "robot": deepcopy(ROBOT),
        "scene": {
            "fixtures": list(fixtures) + [capsule((-2.8, -1.1), (-2.6, -0.8), 0.15)],
            "payload": ([capsule((0.22, 0.02), (0.57, -0.05), 0.075)]
                        if payload is None else list(payload)),
        },
        "moving_fixtures": list(moving),
        "tick_seconds": TICK_SECONDS,
        "margin": MARGIN,
        "limits": {"velocity": [0.78, 1.17, 1.36], "acceleration": [1.9, 2.7, 3.1]},
        "nodes": nodes,
        "edges": edges,
        "measured": {"tick": measured_tick, "q": measured, "dq": list(dq)},
        "start_node": start_node,
        "goal_node": "handoff",
        "brake_ticks": brake_ticks,
        "deadline": deadline,
    }


def reflect(data):
    """Use the equivalent loading station on the mirrored cell layout."""
    result = deepcopy(data)

    def flip_vector(vector):
        vector[1] = -vector[1]
        vector[2] = -vector[2]

    def flip_shape(shape):
        shape["a"][1] = -shape["a"][1]
        shape["b"][1] = -shape["b"][1]

    flip_vector(result["measured"]["q"])
    flip_vector(result["measured"]["dq"])
    for coordinates in result["nodes"].values():
        flip_vector(coordinates)
    for capsule_data in result["scene"]["fixtures"] + result["scene"]["payload"]:
        flip_shape(capsule_data)
    for obstacle in result["moving_fixtures"]:
        for frame in obstacle["keyframes"]:
            flip_shape(frame)
    return result


def moving_gate(open_at, clear_at, *, radius=0.11, gate=(2.15, 0.17)):
    """Slide the gate along a rail out of the reachable load envelope."""
    return track(radius, (0, *gate, 1.3), (open_at, *gate, 1.3), (clear_at, 3.35, 0.17, 1.3))


def staged_update(*, closing_at, reopen_at=None, detour=(), deadline=48):
    """Forecasts agree until the arm reaches its approach; suffixes differ."""
    approach = [-0.54, -0.85, 0.74]
    parked = track(0.11, (0, 3.35, 0.17, 1.3), (deadline, 3.37, 0.19, 1.3))
    pending = [(0, 3.35, 0.17, 1.3), (closing_at - 3, 3.35, 0.17, 1.3),
               (closing_at, 2.15, 0.17, 1.3)]
    if reopen_at is not None:
        pending.extend(((reopen_at, 2.15, 0.17, 1.3), (reopen_at + 4, 3.36, 0.17, 1.3)))
    initial = spec(approach=approach, detour=detour, deadline=deadline, moving=[parked])
    revised = spec(approach=approach, detour=detour, deadline=deadline, moving=[track(0.11, *pending)])
    return initial, revised


def missions():
    result = []

    def add(family, name, case, ready=True, prior=None):
        row = {"id": name, "family": family, "spec": case, "expect_ready": ready}
        if prior is not None:
            row["prior"] = prior
        result.append(row)

    add("moving_gate", "slow-gate-open", spec(moving=[moving_gate(9, 15)], deadline=31))
    berth = spec(moving=[
        track(0.115, (0, 3.36, 0.17, 1.3), (8, 3.36, 0.17, 1.3),
              (11, 2.1251, 0.1419, 1.3), (16, 2.1251, 0.1419, 1.3), (21, 3.36, 0.17, 1.3)),
        track(0.11, (0, 2.2134, 0.6677, 0.85), (17, 2.2134, 0.6677, 0.85),
              (22, 3.4, 0.6677, 1.25)),
    ], deadline=36)
    berth["nodes"]["transfer-berth"] = [-0.02, 0.05, 0.03]
    berth["edges"] = [
        {"id": "enter-berth", "source": "approach", "target": "transfer-berth", "ticks": 6},
        {"id": "leave-berth", "source": "transfer-berth", "target": "handoff", "ticks": 6},
    ]
    add("moving_gate", "early-berth-entry-strands-arm", reflect(berth))
    add("moving_gate", "closed-gate-use-detour", spec(moving=[
        track(0.105, (0, 2.15, 0.17, 1.3), (19, 2.16, 0.20, 1.18),
              (45, 2.14, 0.18, 1.36)),
    ], fixtures=[capsule(*fixture) for fixture in SHELVES_AND_POSTS], detour=DETOUR, deadline=46))
    add("moving_gate", "gate-opens-too-late", spec(moving=[moving_gate(25, 29)], deadline=24), False)

    add("braking", "loaded-three-axis-brake", spec(moving=[moving_gate(10, 16)], dq=[0.28, 0.42, -0.31],
                                                   brake_ticks=3, deadline=34))
    add("braking", "mirrored-reverse-brake", reflect(spec(moving=[moving_gate(10, 14)],
        dq=[-0.31, -0.45, 0.33], measured_tick=4, brake_ticks=4, deadline=36)))
    add("braking", "brake-before-closing-window", spec(moving=[
        track(0.115, (0, 3.35, 0.17, 1.3), (11, 3.35, 0.17, 1.3), (16, 2.15, 0.17, 1.3)),
    ], dq=[0.41, -0.23, 0.25], measured_tick=2, brake_ticks=3, deadline=27))
    add("braking", "braking-misses-last-safe-window", spec(moving=[
        track(0.115, (0, 3.35, 0.17, 1.3), (8, 3.35, 0.17, 1.3), (12, 2.15, 0.17, 1.3)),
    ], dq=[-0.27, 0.31, -0.26], measured_tick=3, brake_ticks=3, deadline=29), False)

    prior, revised = staged_update(closing_at=7, reopen_at=19, deadline=42)
    add("forecast", "early-close-wait-for-reopen", revised, prior=prior)
    result[-1]["interrupt"] = {
        "edge": "reach-approach", "tick": 2, "brake_ticks": 2,
        "resume_node": "approach", "resume_ticks": 2,
    }
    prior, revised = staged_update(closing_at=7, detour=DETOUR, deadline=49)
    add("forecast", "extended-close-routes-around", revised, prior=prior)
    prior, revised = staged_update(closing_at=6, reopen_at=13, deadline=36)
    add("forecast", "mirrored-shorter-revised-shift", reflect(revised), prior=reflect(prior))
    prior, revised = staged_update(closing_at=7, deadline=37)
    add("forecast", "closed-through-shift", revised, False, prior=prior)

    add("restart", "reopened-during-reconnect", spec(
        start=[-0.36, -0.72, 0.61], goal=[0.47, 0.95, -0.65], moving=[moving_gate(14, 20)],
        measured_tick=7, dq=[0.22, 0.37, -0.29], brake_ticks=3, deadline=38))
    timed = spec(moving=[
        track(0.115, (0, 3.35, 0.17, 1.3), (21, 3.35, 0.17, 1.3), (24, 2.15, 0.17, 1.3)),
    ], measured_tick=9, dq=[0.23, -0.44, 0.21], brake_ticks=4, deadline=37)
    timed["limits"]["acceleration"][1] = 1.9
    timed["edges"].insert(0, {"id": "obsolete-fast-profile", "source": "approach",
                              "target": "handoff", "ticks": 9})
    add("restart", "advance-before-close-within-acceleration", reflect(timed))
    add("restart", "two-carriages-clear-after-reconnect", spec(moving=[
        track(0.11, (0, 2.15, 0.17, 1.3), (18, 2.15, 0.17, 1.3), (24, 3.35, 0.17, 1.3)),
        track(0.10, (0, 3.1, 0.27, 0.7), (18, 3.1, 0.27, 0.7), (21, 2.19, 0.28, 0.55),
              (29, 2.18, 0.27, 0.55), (33, 3.25, 0.38, -0.3)),
    ], payload=[capsule((0.22, 0.02), (0.57, -0.05), 0.075),
                capsule((0.26, 0.05), (0.52, 0.11), 0.05)],
        measured_tick=10, dq=[-0.25, 0.31, 0.34], brake_ticks=4, deadline=44))
    add("restart", "reconnect-too-late-for-available-detour",
        reflect(spec(moving=[moving_gate(45, 49)], measured_tick=11, dq=[0.29, -0.37, 0.25],
                     brake_ticks=3, detour=DETOUR, deadline=34)), False)
    return result
