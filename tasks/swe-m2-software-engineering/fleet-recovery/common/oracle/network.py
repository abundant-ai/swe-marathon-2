"""Allocate jobs and route an energy-constrained fleet through shared resources."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from heapq import heappop, heappush
from itertools import count
import json
from pathlib import Path
from typing import Any, Callable

from .elevators import array, integer, name, record, windows

Wire = dict[str, Any]
Constraint = frozenset[tuple[str, int]]


@dataclass(frozen=True)
class Shift:
    """One fixed instance of a facility assignment and traffic plan."""

    tick: int
    end: int
    calendar: dict
    lanes: dict
    chargers: dict
    robots: dict
    jobs: list


@dataclass(frozen=True)
class Move:
    """A scheduled action and its complete exclusive resource footprint."""

    kind: str
    identity: str
    begin: int
    end: int
    resources: tuple[str, ...]

    def wire(self) -> Wire:
        """Convert the action to the allocator's public itinerary fields."""
        return {"kind": self.kind, "id": self.identity, "start": self.begin, "end": self.end}


def unique(value: object) -> tuple[str, ...]:
    """Read distinct identifiers in their supplied order."""
    members = tuple(name(key) for key in array(value))
    if len(members) != len(set(members)):
        raise ValueError("Duplicate identifier")
    return members


def parse(packet: Wire) -> Shift:
    """Validate robot, work and route fields before searching any schedules."""
    first = integer(packet["tick"])
    last = integer(packet["horizon"], first, first + 40)
    nodes = set(unique(packet["nodes"]))
    calendar = {name(key): windows(value) for key, value in record(packet["resources"]).items()}

    def resource_ids(value: object) -> tuple[str, ...]:
        """Read a commissioned collection of mutually exclusive resources."""
        ids = unique(value)
        if not set(ids) <= calendar.keys():
            raise ValueError("Unknown occupied resource")
        return ids

    lanes, chargers, robots = {}, {}, {}
    for lane in array(packet["lanes"]):
        key, a, b = (name(lane[field]) for field in ("id", "from", "to"))
        if key in lanes or a not in nodes or b not in nodes or a == b:
            raise ValueError("Invalid lane endpoints or identity")
        duration = integer(lane["travel"], 1) + integer(lane["clearance_slack"])
        lanes[key] = (a, b, duration, integer(lane["energy"]), resource_ids(lane["resources"]))
    for charger in array(packet["chargers"]):
        key, node = name(charger["id"]), name(charger["node"])
        if key in chargers or node not in nodes:
            raise ValueError("Unknown charger station or duplicate identity")
        chargers[key] = (node, integer(charger["ticks"], 1), integer(charger["gain"], 1), resource_ids(charger["resources"]))
    for robot in array(packet["robots"]):
        key, node = name(robot["id"]), name(robot["node"])
        allowed = unique(robot["lanes"])
        if key in robots or node not in nodes or not allowed or not set(allowed) <= lanes.keys():
            raise ValueError("Uncommissioned robot or lanes")
        reserve = integer(robot["reserve"])
        capacity = integer(robot["capacity"], reserve)
        robots[key] = (node, integer(robot["battery"], reserve, capacity), capacity, reserve, allowed)
    jobs = []
    identities = set()
    for job in array(packet["jobs"]):
        key, pickup, drop = (name(job[field]) for field in ("id", "pickup", "drop"))
        ready, deadline = integer(job["ready"]), integer(job["deadline"])
        priority = integer(job["priority"], 0, 1)
        eligible = unique(job["robots"])
        if (key in identities or pickup not in nodes or drop not in nodes or pickup == drop
                or deadline < ready or not eligible or not set(eligible) <= robots.keys()):
            raise ValueError("Unknown job stations or robots")
        resources = record(job["resources"])
        pickup_resources, drop_resources = (resource_ids(resources[k]) for k in ("pickup", "drop"))
        jobs.append((key, priority, ready, deadline, pickup, drop, integer(job["dwell"], 1),
                     eligible, pickup_resources, drop_resources))
        identities.add(key)
    if len(jobs) > 6 or len(robots) > 4:
        raise ValueError("Fleet or workload exceeds the declared bound")
    return Shift(first, last, calendar, lanes, chargers, robots, jobs)


def available(calendar: dict, fixed: Constraint, occupied: tuple[str, ...], begin: int, end: int) -> bool:
    """Check every resource window and exclusion over a worst-case reservation."""
    return all(any(lo <= begin and end <= hi for lo, hi in calendar[resource])
               and all((resource, tick) not in fixed for tick in range(begin, end))
               for resource in occupied)


def shortest(shift: Shift, robot_id: str, job: tuple, constraints: Constraint) -> tuple[Move, ...] | None:
    """Find one earliest-finish itinerary for an assigned robot and job."""
    start, battery, capacity, reserve, allowed = shift.robots[robot_id]
    identity, _, ready, deadline, pickup, drop, dwell, _, at_pickup, at_drop = job
    end = min(deadline, shift.end)
    fallback = shift.tick, start, 0, battery, ()
    movement = defaultdict(list)
    charging = defaultdict(list)
    for key in allowed:
        a, b, duration, energy, occupied = shift.lanes[key]
        movement[a].append((key, b, duration, energy, occupied))
    for key, (node, duration, gain, occupied) in shift.chargers.items():
        charging[node].append((key, duration, gain, occupied))
    queue = [(shift.tick, 0, fallback)]
    serial = count(1)
    best = {(shift.tick, start, 0): battery}
    while queue:
        _, _, (tick, node, phase, energy, fixed_path) = heappop(queue)
        if energy < best[tick, node, phase]:
            continue
        if phase == 2:
            return fixed_path
        choices = [(node, phase, tick+1, energy, None)]
        if phase == 0 and node == pickup and tick >= ready:
            choices.append((node, 1, tick+dwell, energy, Move("pickup", identity, tick, tick+dwell, at_pickup)))
        if phase == 1 and node == drop:
            choices.append((node, 2, tick+dwell, energy, Move("drop", identity, tick, tick+dwell, at_drop)))
        for key, target, duration, cost, occupied in movement[node]:
            if energy - cost >= reserve:
                choices.append((target, phase, tick+duration, energy-cost, Move("move", key, tick, tick+duration, occupied)))
        for key, duration, gain, occupied in charging[node]:
            if energy < capacity:
                choices.append((node, phase, tick+duration, min(capacity, energy+gain), Move("charge", key, tick, tick+duration, occupied)))
        for dest, phase_after, arrive, remain, action in choices:
            key = arrive, dest, phase_after
            if arrive > end or remain <= best.get(key, -1):
                continue
            if action and not available(shift.calendar, constraints, action.resources, tick, arrive):
                continue
            best[key] = remain
            path = fixed_path + ((action,) if action is not None else ())
            heappush(queue, (arrive, next(serial), (arrive, dest, phase_after, remain, path)))
    return None


def timing(routes: dict[str, tuple[Move, ...]]) -> tuple[int, int]:
    """Return task completion makespan and total finish time for a coordinated plan."""
    completions = [items[-1].end for items in routes.values()]
    return max(completions, default=0), sum(completions)


def conflict(routes: dict[str, tuple[Move, ...]]) -> tuple[str, str, str, int] | None:
    """Find a shared exclusive resource tick occupied by two scheduled robots."""
    active = {}
    for robot, itinerary in sorted(routes.items()):
        for action in itinerary:
            for resource in action.resources:
                for tick in range(action.begin, action.end):
                    cell = resource, tick
                    if cell in active:
                        return active[cell], robot, resource, tick
                    active[cell] = robot
    return None


def coordinate(assignments: dict[str, int], path: Callable, ceiling: tuple[int, int] | None) -> dict | None:
    """Search resource exclusions until a fixed assignment admits a safe schedule."""
    constraints = dict.fromkeys(assignments, frozenset())
    roots = {robot: path(robot, task, constraints[robot]) for robot, task in assignments.items()}
    serial = count()
    queue = [(timing(roots), next(serial), constraints, roots)]
    explored = set()
    while queue:
        estimate, _, restrictions, routes = heappop(queue)
        if ceiling is not None and estimate >= ceiling:
            return None
        clash = conflict(routes)
        if clash is None:
            return routes
        first, second, zone, tick = clash
        for robot in (first, second):
            tightened = restrictions | {robot: restrictions[robot] | {(zone, tick)}}
            fingerprint = tuple(sorted(tightened.items()))
            if fingerprint in explored:
                continue
            explored.add(fingerprint)
            alternative = path(robot, assignments[robot], tightened[robot])
            if alternative is not None:
                revised = routes | {robot: alternative}
                heappush(queue, (timing(revised), next(serial), tightened, revised))
    return None


def allocate(shift: Shift) -> Wire:
    """Solve joint assignment and traffic reservations in declared rank order."""
    @cache
    def route(robot: str, job: int, constraints: Constraint) -> tuple[Move, ...] | None:
        """Reuse exact single-robot solutions across equivalent branch constraints."""
        return shortest(shift, robot, shift.jobs[job], constraints)

    robots = tuple(sorted(shift.robots))
    ranked_jobs = sorted(range(len(shift.jobs)), key=lambda i: -shift.jobs[i][1])
    tasks = []

    def assign(index: int, allocated: dict[str, int]) -> None:
        """Enumerate feasible matchings by adding at most one job to each robot."""
        if index == len(robots):
            chosen = set(allocated.values())
            priority = sum(shift.jobs[job][1] for job in chosen)
            tasks.append(((priority, len(chosen), tuple(int(job in chosen) for job in ranked_jobs)), allocated))
            return
        robot = robots[index]
        for job in ranked_jobs:
            if (job not in allocated.values() and robot in shift.jobs[job][7]
                    and route(robot, job, frozenset()) is not None):
                assign(index + 1, allocated | {robot: job})
        assign(index + 1, allocated)

    assign(0, {})
    best_rank = None
    best_times = None
    winning_routes, winning_assignment = {}, {}
    for rank, matching in sorted(tasks, key=lambda item: item[0], reverse=True):
        if best_rank is not None and rank < best_rank:
            break
        result = coordinate(matching, route, best_times)
        if result is not None:
            best_rank, best_times = rank, timing(result)
            winning_routes, winning_assignment = result, matching
    return {"itineraries": [{"robot": robot, "job": shift.jobs[winning_assignment[robot]][0],
                              "actions": [action.wire() for action in winning_routes[robot]]}
                             for robot in sorted(winning_routes)]}


def command(write: Callable[[Path, Wire], None]) -> int:
    """Read one network request and atomically publish an optimized itinerary set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        packet = record(json.loads(args.request.read_text(encoding="utf-8")))
        write(args.output, allocate(parse(packet)))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
        parser.exit(1, f"fleet_recovery allocate: {error}\n")
    return 0
