"""Plan causal dual-arm routes through time and payload custody."""

from collections import defaultdict
from dataclasses import dataclass
from functools import cache

from .core import SIDES, Cell, integer, name, pair, plus, side, times


def close_pose(a, b):
    return (
        max(
            abs(x - y)
            for first, second in zip(a, b, strict=True)
            for x, y in zip(first, second, strict=True)
        )
        <= 1e-7
    )


def stationary(velocity):
    return all(x == 0 for arm in velocity for x in arm)


def records(value):
    if not isinstance(value, list):
        raise ValueError("Expected operation array")  # noqa: TRY004 - Callers handle malformed input as ValueError.
    result = {}
    for row in value:
        identity = name(row["id"])
        if identity in result:
            raise ValueError("Duplicate primitive")
        integer(row["ticks"], 1)
        result[identity] = row
    return result


@dataclass(frozen=True)
class Window:
    """A measured paired pose and commissioned transfer possibilities."""

    cell: Cell
    nodes: dict
    edges: dict
    transfers: dict
    start: str
    goal: str
    owner: int
    goal_owner: int
    tick: int
    deadline: int
    pose: tuple
    velocity: tuple
    brake: int

    @classmethod
    def parse(cls, spec):
        nodes = {name(key): pair(value) for key, value in spec["nodes"].items()}
        edges = records(spec["edges"])
        transfers = records(spec["handoffs"])
        if any(
            row["from"] not in nodes or row["to"] not in nodes for row in edges.values()
        ):
            raise ValueError("Unknown move node")
        for row in transfers.values():
            if row["node"] not in nodes or side(row["to"]) == side(row["from"]):
                raise ValueError("Invalid handoff")
        initial = spec["measured"]
        start, goal = name(spec["start_node"]), name(spec["goal_node"])
        tick, deadline = integer(initial["tick"]), integer(spec["deadline"])
        if not tick <= deadline <= tick + 80 or start not in nodes or goal not in nodes:
            raise ValueError("Invalid planning horizon or node")
        brake = integer(spec["brake_ticks"])
        return cls(
            Cell.parse(spec),
            nodes,
            edges,
            transfers,
            start,
            goal,
            SIDES.index(side(initial["owner"])),
            SIDES.index(side(spec["goal_owner"])),
            tick,
            deadline,
            pair(initial["pose"]),
            pair(initial["velocity"]),
            brake,
        )


def command(kind, begin, end, field, value):
    return {"kind": kind, "start": begin, "end": end, field: value}


def initial_action(window):
    """Validate the commissioned stop and derive the optional brake prefix."""
    stop = window.tick + window.brake
    if stop > window.deadline or stationary(window.velocity) == bool(window.brake):
        return None
    endpoint = tuple(
        plus(q, times(dq, window.brake * window.cell.tick_seconds / 2))
        for q, dq in zip(window.pose, window.velocity, strict=True)
    )
    if not close_pose(endpoint, window.nodes[window.start]):
        return None
    if not window.cell.certify(
        window.pose, endpoint, window.tick, stop, window.owner, brake=True
    ):
        return None
    return (
        (command("brake", window.tick, stop, "node", window.start),)
        if window.brake
        else ()
    )


def plan(window):
    """Explore reachable tick/node/owner states and stop at the first safe goal."""
    prefix = initial_action(window)
    blocked = {"status": "blocked", "commands": []}
    if prefix is None:
        return blocked
    first = window.tick + window.brake
    layers = {tick: {} for tick in range(first, window.deadline + 1)}
    layers[first][(window.start, window.owner)] = prefix
    moves, switches = defaultdict(list), defaultdict(list)
    for identity, row in window.edges.items():
        moves[row["from"]].append((identity, row["to"], row["ticks"]))
    for identity, row in window.transfers.items():
        owner = SIDES.index(row["from"])
        switches[row["node"], owner].append(
            (identity, SIDES.index(row["to"]), row["ticks"])
        )

    @cache
    def swept(a, b, lo, hi, owner):
        return window.cell.certify(window.nodes[a], window.nodes[b], lo, hi, owner)

    for tick, layer in layers.items():
        finished = layer.get((window.goal, window.goal_owner))
        if finished is not None:
            return {"status": "ready", "commands": list(finished)}
        for (node, owner), path in layer.items():
            end = tick + 1
            if end in layers and swept(node, node, tick, end, owner):
                layers[end].setdefault(
                    (node, owner), (*path, command("wait", tick, end, "node", node))
                )
            for identity, target, duration in moves[node]:
                end = tick + duration
                if end in layers and swept(node, target, tick, end, owner):
                    layers[end].setdefault(
                        (target, owner),
                        (*path, command("move", tick, end, "id", identity)),
                    )
            for identity, target, duration in switches[node, owner]:
                end = tick + duration
                if (
                    end in layers
                    and window.cell.matches_grasp(window.nodes[node])
                    and swept(node, node, tick, end, owner)
                    and swept(node, node, end, end, target)
                ):
                    layers[end].setdefault(
                        (node, target),
                        (*path, command("handoff", tick, end, "id", identity)),
                    )
    return blocked


def end_state(window, issued):
    """Read the commanded resting pose and load holder at the end of a primitive."""
    if issued["kind"] == "move":
        node, owner = window.edges[issued["id"]]["to"], window.owner
    elif issued["kind"] == "handoff":
        specification = window.transfers[issued["id"]]
        node, owner = specification["node"], SIDES.index(specification["to"])
    else:
        node, owner = issued["node"], window.owner
    return window.nodes[node], owner
