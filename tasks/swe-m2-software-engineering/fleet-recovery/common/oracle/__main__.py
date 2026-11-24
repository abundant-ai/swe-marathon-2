"""Schedule parcel deliveries and record issued movement authority."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from heapq import heappop, heappush
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


Record = dict[str, Any]


@dataclass(frozen=True)
class Lane:
    """Directed edge and its exclusive resources."""

    end: str
    cost: int
    resources: frozenset[str]


@dataclass(frozen=True)
class Site:
    """Index the site graph for movement checks and routing."""

    nodes: dict[str, frozenset[str]]
    lanes: dict[str, dict[str, Lane]]
    robots: dict[str, Record]


def load_site(path: Path) -> Site:
    """Load the operator's graph and add each waypoint's implicit resource."""
    data = json.loads(path.read_text())
    nodes = {name: frozenset([f"node:{name}", *resources]) for name, resources in data["nodes"].items()}
    lanes: dict[str, dict[str, Lane]] = {name: {} for name in nodes}
    for edge in data["lanes"]:
        a, b = edge["from"], edge["to"]
        footprint = nodes[a] | nodes[b] | frozenset(edge["resources"])
        lanes[a][b] = Lane(b, edge["ticks"], footprint)
    return Site(nodes, lanes, data["robots"])


def initial_state(site: Site) -> Record:
    """Start with the configured occupied locations and no issued commands."""
    return {
        "robots": {
            name: {"node": record["start"], "online": True, "located": True, "seq": -1, "pending": None, "job": None}
            for name, record in site.robots.items()
        },
        "jobs": {}, "closures": [], "responses": {}, "serial": 0,
    }


def footprint(site: Site, robot: Record) -> frozenset[str]:
    """Keep endpoints and lane resources protected until a movement settles."""
    command = robot["pending"]
    if command and command["kind"] == "move":
        return site.lanes[command["from"]][command["to"]].resources
    return site.nodes[robot["node"]]


def available(site: Site, a: str, lane: Lane, held: set[str], closed: set[str]) -> bool:
    """Allow an unconflicted edge while respecting closures and confirmed egress."""
    egress = site.nodes[a] - site.nodes[lane.end]
    return not lane.resources.intersection(held | (closed - egress))


def next_node(site: Site, robot: str, start: str, goal: str, held: set[str], closed: set[str]) -> str | None:
    """Find the next executable hop, using the configured loop where required."""
    configuration = site.robots[robot]
    if configuration["mode"] == "loop":
        loop = configuration["loop"]
        following = loop[(loop.index(start) + 1) % len(loop)]
        return following if available(site, start, site.lanes[start][following], held, closed) else None
    paths = [(0, start, "")]
    visited = set()
    while paths:
        distance, node, first = heappop(paths)
        if node in visited:
            continue
        if node == goal:
            return first
        visited.add(node)
        for lane in site.lanes[node].values():
            if lane.end not in visited and available(site, node, lane, held, closed):
                heappush(paths, (distance + lane.cost, lane.end, first or lane.end))
    return None


def chosen_command(
    site: Site, robot: str, node: str, job: Record, held: set[str], closed: set[str],
) -> Record | None:
    """Choose an action or one hop for the robot's current parcel target."""
    action = "drop" if job["picked"] else "pickup"
    target = job["dropoff"] if job["picked"] else job["pickup"]
    if node == target:
        return {"kind": action, "node": node}
    destination = next_node(site, robot, node, target, held, closed)
    if destination is None:
        return None
    return {"kind": "move", "from": node, "to": destination}


def capabilities_match(site: Site, robot: str, start: str, job: Record) -> bool:
    """Avoid assigning work that cannot reach both stations in the directed site."""
    config = site.robots[robot]
    pickup, dropoff = job["pickup"], job["dropoff"]
    if config["mode"] == "route":
        return all(next_node(site, robot, origin, target, set(), set()) is not None
                   for origin, target in ((start, pickup), (pickup, dropoff)))
    return {pickup, dropoff}.issubset(config["loop"])


def new_commands(site: Site, state: Record) -> list[Record]:
    """Schedule independent choices and immediately reserve each emitted footprint."""
    robots = state["robots"]
    closed = set(state["closures"])
    jobs = state["jobs"]
    waiting = sorted(jobs, key=lambda name: (-jobs[name]["priority"], jobs[name]["arrival"]))
    commands = []
    for robot_id, robot in robots.items():
        if not robot["online"] or not robot["located"] or robot["pending"]:
            continue
        held = set().union(*(footprint(site, other) for name, other in robots.items() if name != robot_id))
        assigned = robot["job"]
        choices = [assigned] if assigned else waiting
        for job_id in choices:
            job = jobs[job_id]
            if job["status"] != "active" or job["owner"] not in (None, robot_id) or robot_id not in job["eligible"]:
                continue
            if job["owner"] is None and not capabilities_match(site, robot_id, robot["node"], job):
                continue
            action = chosen_command(site, robot_id, robot["node"], job, held, closed)
            if action is None:
                continue
            state["serial"] += 1
            command = {"command": f"authority-{state['serial']}", "robot": robot_id, "job": job_id, **action}
            robot.update(pending=command, job=job_id)
            job["owner"] = robot_id
            commands.append(command)
            break
    return commands


def update_telemetry(state: Record, event: Record) -> None:
    """Reconcile fresh motion evidence without releasing an unresolved claim."""
    robot = state["robots"][event["robot"]]
    if event["seq"] <= robot["seq"]:
        return
    robot.update(seq=event["seq"], online=event["online"], located=False)
    if not event["online"] or event["node"] is None:
        return
    pending = robot["pending"]
    if not pending:
        robot["located"] = event["node"] == robot["node"]
        return
    if event["settled"] != pending["command"]:
        return
    node, kind = event["node"], pending["kind"]
    valid = node in (pending["from"], pending["to"]) if kind == "move" else node == pending["node"]
    if not valid:
        return
    job = state["jobs"][pending["job"]]
    robot.update(node=node, located=True, pending=None)
    if kind == "pickup":
        job["picked"] = True
    if kind == "drop":
        job["status"] = "completed"
    if job["status"] != "active":
        robot["job"] = None


def cancel_job(state: Record, job_id: str) -> None:
    """Cancel unpicked work without revoking the underlying movement authority."""
    job = state["jobs"].get(job_id)
    if not job or job["picked"] or job["status"] != "active":
        return
    robot = state["robots"].get(job["owner"])
    pending = robot["pending"] if robot else None
    if pending and pending["kind"] == "pickup":
        return
    job["status"] = "cancelled"
    if robot and pending is None:
        robot["job"] = None


def apply_event(site: Site, state: Record, event: Record) -> Record:
    """Apply a new event, or return the original response to a duplicate."""
    event_id = event["id"]
    if event_id in state["responses"]:
        return state["responses"][event_id]
    kind = event["kind"]
    commands = []
    if kind == "job":
        state["jobs"].setdefault(event["job"], {
            **event, "priority": event.get("priority", 0), "arrival": len(state["jobs"]),
            "owner": None, "picked": False, "status": "active",
        })
    elif kind == "telemetry":
        update_telemetry(state, event)
    elif kind == "closure":
        closed = set(state["closures"])
        if event["closed"]:
            closed.add(event["resource"])
        else:
            closed.discard(event["resource"])
        state["closures"] = sorted(closed)
    elif kind == "cancel":
        cancel_job(state, event["job"])
    elif kind == "tick":
        commands = new_commands(site, state)
    else:
        raise ValueError(f"Unknown event kind {kind!r}")
    response = {"commands": commands}
    state["responses"][event_id] = response
    return response


def store_state(path: Path, state: Record) -> None:
    """Atomically commit state and the outgoing response before exposing it."""
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".fleet-state-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(state, stream, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            temporary.replace(path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


def main() -> int:
    """Serve the synchronous line protocol and give each event a durable commit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    site = load_site(args.site)
    args.state.mkdir(parents=True, exist_ok=True)
    path = args.state / "coordinator.json"
    state = json.loads(path.read_text()) if path.exists() else initial_state(site)
    for line in sys.stdin:
        response = apply_event(site, state, json.loads(line))
        store_state(path, state)
        print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "elevators":
        from .elevators import command

        sys.argv.pop(1)
        sys.exit(command(store_state))
    if len(sys.argv) > 1 and sys.argv[1] == "corridors":
        from .corridors import command

        sys.argv.pop(1)
        sys.exit(command(store_state))
    if len(sys.argv) > 1 and sys.argv[1] == "allocate":
        from .network import command

        sys.argv.pop(1)
        sys.exit(command(store_state))
    if len(sys.argv) > 1 and sys.argv[1] == "rmf-contingent":
        from .contingent import command

        raise SystemExit(command(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "rmf-negotiate":
        from .competition import command

        raise SystemExit(command(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "rmf-handover":
        from .rmf_handover import command

        sys.argv.pop(1)
        sys.exit(command(store_state))
    sys.exit(main())
