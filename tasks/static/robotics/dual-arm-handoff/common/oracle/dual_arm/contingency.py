"""Synthesize a policy over timed robot states and possible fixture scenes."""

from collections import defaultdict
from functools import cache
from heapq import heappop, heappush
from typing import Any, NamedTuple

from .core import SIDES, Cell, integer, name
from .planning import Window, command, initial_action


class State(NamedTuple):
    """A restful snapshot and the hidden scenes consistent with its history."""

    tick: int
    node: str
    owner: int
    scenes: tuple[str, ...]


def commission(spec: dict[str, Any]) -> tuple[dict[str, Window], dict, dict]:
    """Parse the forecast alternatives and commissioned devices for synthesis.

    Args:
        spec: Complete contingency request with empty baseline fixtures.

    Returns:
        Scene-specific windows, scanner definitions, and sorted start delays.

    Raises:
        ValueError: A forecast, commissioned device, or delay is invalid.
    """
    window, scenes, scanners, raw_delays = (
        spec[key] for key in ("window", "scenes", "scanners", "delays")
    )
    if (
        window["fixtures"] != []
        or not isinstance(scenes, dict)
        or not 1 <= len(scenes) <= 8
    ):
        raise ValueError("Expected one to eight alternative fixture scenes")
    windows = {
        name(label): Window.parse(dict(window, fixtures=fixtures))
        for label, fixtures in scenes.items()
    }
    nodes = next(iter(windows.values())).nodes
    if not isinstance(scanners, dict) or not scanners.keys() <= nodes.keys():
        raise ValueError("Unknown scanner pose")
    for reader in scanners.values():
        integer(reader["ticks"], 1)
        labels = reader["labels"]
        if not isinstance(labels, dict) or labels.keys() != windows.keys():
            raise ValueError("Scanner must describe every scene")
        for label in labels.values():
            name(label)
    delays = {}
    for kind in ("move", "handoff"):
        raw = raw_delays[kind]
        if not isinstance(raw, list) or not raw:
            raise ValueError("Expected a nonempty delay array")
        delays[kind] = tuple(sorted(integer(delay) for delay in raw))
        if delays[kind][-1] > 4 or len(set(delays[kind])) != len(raw):
            raise ValueError("Invalid or duplicate delay")
    return windows, scanners, delays


def remaining_ticks(
    initial: Window, outgoing: dict, delays: dict
) -> dict[tuple[str, int], int]:
    """Compute a lower bound under largest delays, ignoring fixtures and scans."""
    incoming = defaultdict(list)
    for source, choices in outgoing.items():
        for kind, _, target, length, owners in choices:
            pairs = (owners,) if owners else ((0, 0), (1, 1))
            for before, after in pairs:
                incoming[target, after].append(
                    (length + delays[kind][-1], source, before)
                )
    goal = initial.goal, initial.goal_owner
    best = {goal: 0}
    pending = [(0, *goal)]
    while pending:
        cost, node, owner = heappop(pending)
        if cost != best[node, owner]:
            continue
        for length, source, before in incoming[node, owner]:
            candidate = cost + length
            if candidate < best.get((source, before), float("inf")):
                best[source, before] = candidate
                heappush(pending, (candidate, source, before))
    return best


def synthesize(spec: dict[str, Any]) -> dict[str, Any]:
    """Find a policy that completes on every reachable scanner and timing branch.

    Args:
        spec: The parsed request, before any controller or scanner result.

    Returns:
        A wire-format decision graph with only reachable nodes, or a blocked
        report when the finite-horizon search proves no policy exists.
    """
    windows, scanners, delays = commission(spec)
    initial = next(iter(windows.values()))
    blocked = {"status": "blocked", "root": None, "decisions": {}}
    prefixes = [initial_action(window) for window in windows.values()]
    if any(prefix is None for prefix in prefixes):
        return blocked

    outgoing = defaultdict(list)
    for identity, edge in initial.edges.items():
        outgoing[edge["from"]].append(
            ("move", identity, edge["to"], edge["ticks"], None)
        )
    for identity, event in initial.transfers.items():
        if initial.cell.matches_grasp(initial.nodes[event["node"]]):
            owners = tuple(SIDES.index(event[key]) for key in ("from", "to"))
            outgoing[event["node"]].append(
                ("handoff", identity, event["node"], event["ticks"], owners)
            )
    lower_bound = remaining_ticks(initial, outgoing, delays)
    cells = {scene: window.cell for scene, window in windows.items()}
    static = {
        cell: all(len(fixture.ticks) == 1 for fixture in cell.fixtures)
        for cell in cells.values()
    }

    @cache
    def sweep(
        cell: Cell, source: str, target: str, start: int, end: int, owner: int
    ) -> bool:
        """Cache physical sweeps, sharing results between identical forecasts."""
        return cell.certify(
            initial.nodes[source], initial.nodes[target], start, end, owner
        )

    def safe(
        scene: str, source: str, target: str, start: int, end: int, owner: int
    ) -> bool:
        """Reuse the same time-independent sweep when fixtures are static."""
        cell = cells[scene]
        if static[cell]:
            start, end = 0, end - start
        return sweep(cell, source, target, start, end, owner)

    decisions: dict[State, tuple[dict | None, dict[str, State]]] = {}

    @cache
    def visit(state: State) -> bool:
        """Record one command whose every outcome keeps this state winning."""
        tick, node, owner, possible = state
        if tick + lower_bound.get((node, owner), float("inf")) > initial.deadline:
            return False
        if not all(safe(s, node, node, tick, tick, owner) for s in possible):
            return False
        if node == initial.goal and owner == initial.goal_owner:
            decisions[state] = None, {}
            return True
        scanner = scanners.get(node)
        if scanner:
            groups = defaultdict(list)
            for scene in possible:
                groups[scanner["labels"][scene]].append(scene)
            end = tick + scanner["ticks"]
            if (
                len(groups) > 1
                and end <= initial.deadline
                and all(safe(s, node, node, tick, end, owner) for s in possible)
            ):
                branches = {
                    label: State(end, node, owner, tuple(group))
                    for label, group in groups.items()
                }
                if all(visit(child) for child in branches.values()):
                    decisions[state] = (
                        command("scan", tick, end, "node", node),
                        branches,
                    )
                    return True
        choices = [*outgoing[node], ("wait", node, node, 1, None)]
        for kind, identity, target, ticks, owners in choices:
            edge_delays = delays.get(kind, (0,))
            if tick + ticks + edge_delays[-1] > initial.deadline or (
                owners and owner != owners[0]
            ):
                continue
            next_owner = owners[1] if owners else owner
            if not all(
                safe(s, node, node, tick, tick + delay, owner)
                and safe(s, node, target, tick + delay, tick + delay + ticks, owner)
                for s in possible
                for delay in edge_delays
            ):
                continue
            branches = {
                str(delay): State(tick + delay + ticks, target, next_owner, possible)
                for delay in edge_delays
            }
            if all(visit(child) for child in branches.values()):
                field = "node" if kind == "wait" else "id"
                decisions[state] = (
                    command(kind, tick, tick + ticks, field, identity),
                    branches,
                )
                return True
        return False

    starting = State(
        initial.tick + initial.brake,
        initial.start,
        initial.owner,
        tuple(sorted(windows)),
    )
    if not visit(starting):
        return blocked
    if initial.brake:
        root = State(initial.tick, initial.start, initial.owner, starting.scenes)
        decisions[root] = prefixes[0][0], {"0": starting}
    else:
        root = starting

    graph = {}
    identifiers = {}

    def emit(state: State) -> str:
        """Serialize reachable policy nodes and reuse identical timed belief states."""
        if state in identifiers:
            return identifiers[state]
        key = str(len(identifiers))
        identifiers[state] = key
        operation, next_states = decisions[state]
        graph[key] = {
            "command": operation,
            "next": {label: emit(child) for label, child in next_states.items()},
        }
        return key

    return {"status": "ready", "root": emit(root), "decisions": graph}
