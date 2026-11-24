"""Compile certified curvature-limited routes with temporary aisle holds."""

import argparse
from dataclasses import dataclass
from functools import cache
from heapq import heappop, heappush
import json
from math import ceil, isfinite, pi
from pathlib import Path
from typing import Any, Callable

from .staging import clearance, sweep

Record = dict[str, Any]
State = tuple[int, int, int]
NAV_FIELDS = ("bounds", "obstacles", "footprint", "margin_m", "forward_max_mps", "reverse_max_mps",
              "angular_max_radps", "position_tolerance_m", "heading_tolerance_rad")
DIRECTION = ((1, 0), (0, 1), (-1, 0), (0, -1))


def numbers(value: Any, length: int) -> list[float]:
    """Read a fixed-length array of finite numeric coordinates."""
    if not isinstance(value, list) or len(value) != length or any(type(v) not in (int, float) or not isfinite(v) for v in value):
        raise ValueError("Invalid numeric array")
    return value


def rectangle(value: Any) -> list[float]:
    """Read ordered planar rectangle bounds."""
    bounds = numbers(value, 4)
    if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        raise ValueError("Inverted rectangle")
    return bounds


def position(value: Any) -> State:
    """Read lattice coordinates, accepting signed squares and cardinal heading."""
    if not isinstance(value, list) or len(value) != 3 or any(type(v) is not int for v in value) or value[2] not in range(4):
        raise ValueError("Invalid survey pose")
    return tuple(value)


@dataclass(frozen=True)
class Survey:
    """Validated world geometry and discrete motion parameters."""

    nav: Record
    origin: list[float]
    cell: float
    dt: float
    start: State
    goal: State
    radii: list[int]
    closures: dict[str, list[float]]
    budget: int

    @classmethod
    def parse(cls, packet: Record) -> "Survey":
        """Create a validated survey before any generated files are written."""
        nav = {key: packet[key] for key in NAV_FIELDS}
        for key in ("step_m", "tick_seconds", "forward_max_mps", "reverse_max_mps", "angular_max_radps",
                    "position_tolerance_m", "heading_tolerance_rad"):
            if numbers([packet[key]], 1)[0] <= 0:
                raise ValueError("Motion geometry requires positive parameters")
        if min(numbers(nav["footprint"], 2)) <= 0 or numbers([nav["margin_m"]], 1)[0] < 0:
            raise ValueError("Invalid hull dimensions")
        rectangle(nav["bounds"])
        if not isinstance(nav["obstacles"], list):
            raise ValueError("Obstacles must be an array")
        for obstacle in nav["obstacles"]:
            rectangle(obstacle)
        radii, closures, budget = (packet[key] for key in ("turn_radius_cells", "closures", "route_limit_ticks"))
        if (not isinstance(radii, list) or not 1 <= len(radii) <= 4
                or any(type(r) is not int or r <= 0 for r in radii) or len(set(radii)) != len(radii)):
            raise ValueError("Invalid turn radii")
        if (not isinstance(closures, dict) or len(closures) > 4 or any(not key for key in closures)
                or type(budget) is not int or budget <= 0):
            raise ValueError("Invalid closures or travel budget")
        return cls(nav, numbers(packet["origin"], 2), packet["step_m"], packet["tick_seconds"],
                   position(packet["start"]), position(packet["staging"]), radii,
                   {key: rectangle(bounds) for key, bounds in closures.items()}, budget)

    def pose(self, state: State) -> list[float]:
        """Convert the discrete pose into a staging configuration pose."""
        x, y, heading = state
        return [self.origin[0] + self.cell * x, self.origin[1] + self.cell * y, heading * pi / 2]


@dataclass(frozen=True)
class Motion:
    """A certified single-twist transition with its runtime closure labels."""

    to: State
    ticks: int
    velocity: float
    angular: float
    blocked: tuple[str, ...]


def generated(survey: Survey, state: State) -> tuple[Motion, ...]:
    """Generate and certify the translations and quarter turns from one pose."""
    x, y, heading = state
    dx, dy = DIRECTION[heading]
    origin = survey.pose(state)
    motions = []
    for gear, speed in ((1, survey.nav["forward_max_mps"]), (-1, survey.nav["reverse_max_mps"])):
        for turn, radius in [(0, 1), *((turn, radius) for turn in (-1, 1) for radius in survey.radii)]:
            angle = turn * pi / 2
            length = radius * survey.cell * (abs(angle) if turn else 1)
            ticks = ceil(max(length / speed, abs(angle) / survey.nav["angular_max_radps"]) / survey.dt - 1e-12)
            ticks = max(1, ticks)
            duration = ticks * survey.dt
            velocity, angular = gear * length / duration, angle / duration
            target = x + gear * radius * (dx - turn * dy), y + gear * radius * (dy + turn * dx), (heading + turn) % 4
            if not sweep(survey.nav, origin, velocity, angular, duration):
                continue
            blocked = tuple(key for key, zone in survey.closures.items()
                            if not sweep(survey.nav | {"obstacles": [zone]}, origin, velocity, angular, duration))
            motions.append(Motion(target, ticks, velocity, angular, blocked))
    return tuple(motions)


def travel(survey: Survey, transitions: Callable[[State], tuple[Motion, ...]], closed: str | None) -> list[tuple[State, Motion]] | None:
    """Find the shortest certified route within the travel budget for one hold."""
    if clearance(survey.nav, survey.pose(survey.start)) <= 0:
        return None
    if closed is not None and clearance(survey.nav | {"obstacles": [survey.closures[closed]]}, survey.pose(survey.start)) <= 0:
        return None
    queue = [(0, survey.start)]
    best = {survey.start: 0}
    back: dict[State, tuple[State, Motion]] = {}
    while queue:
        elapsed, state = heappop(queue)
        if best[state] != elapsed:
            continue
        if state == survey.goal:
            result = []
            while state != survey.start:
                parent, edge = back[state]
                result.append((parent, edge))
                state = parent
            return result[::-1]
        for option in transitions(state):
            arrival = elapsed + option.ticks
            if closed in option.blocked or arrival > survey.budget or arrival >= best.get(option.to, float("inf")):
                continue
            best[option.to] = arrival
            back[option.to] = state, option
            heappush(queue, (arrival, option.to))
    return None


def compile_routes(packet: Record) -> Record:
    """Merge nominal and recoverable closure routes into one supervisor graph."""
    survey = Survey.parse(packet)

    @cache
    def transitions(state: State) -> tuple[Motion, ...]:
        """Reuse certified geometry for the nominal and held route searches."""
        return generated(survey, state)

    nominal = travel(survey, transitions, None)
    if nominal is None:
        return {"status": "blocked", "navigation": None, "blocked_edges": {}}
    paths = [nominal, *(travel(survey, transitions, closed) for closed in survey.closures)]
    all_edges = list(dict.fromkeys(segment for path in paths if path is not None for segment in path))
    nodes = {}

    def node(state: State) -> str:
        """Register the survey pose with a stable ID in the published graph."""
        label = ":".join(map(str, state))
        nodes[label] = survey.pose(state)
        return label

    blocked = {key: [] for key in survey.closures}
    edges = []
    for source, motion in all_edges:
        identity = str(len(edges))
        edges.append({"id": identity, "source": node(source), "target": node(motion.to),
                      "segments": [{"ticks": motion.ticks, "v_mps": motion.velocity, "w_radps": motion.angular}]})
        for key in motion.blocked:
            blocked[key].append(identity)
    return {"status": "ready", "navigation": survey.nav | {"nodes": nodes, "edges": edges,
                    "start": node(survey.start), "staging": node(survey.goal)}, "blocked_edges": blocked}


def command(argv: list[str], write: Callable[[Path, Record], None]) -> int:
    """Compile one survey, leaving the previous report intact on invalid input."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args(argv)
    try:
        report = compile_routes(json.loads(options.layout.read_text(encoding="utf-8")))
        write(options.output, report)
    except (OSError, KeyError, TypeError, ValueError, AttributeError, OverflowError) as error:
        parser.exit(1, f"dock_recovery compile: {error}\n")
    return 0
