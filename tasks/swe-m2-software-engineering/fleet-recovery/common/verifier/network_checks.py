"""Replay proposed fleet schedules through independent physical accounting."""

import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
from typing import Any, Callable

Wire = dict[str, Any]


def lane(key: str, source: str, target: str, travel: int, slack: int, energy: int, *resources: str) -> Wire:
    """Commission a directed lane with a worst-case release time."""
    return {"id": key, "from": source, "to": target, "travel": travel, "clearance_slack": slack,
            "energy": energy, "resources": list(resources)}


def robot(key: str, home: str, allowed: list[str], *, charge: int = 8, capacity: int = 8, reserve: int = 1) -> Wire:
    """Give one robot the workcell's measured lane and battery limits."""
    return {"id": key, "node": home, "lanes": allowed, "battery": charge, "capacity": capacity, "reserve": reserve}


def job(key: str, start: str, end: str, allowed: list[str], deadline: int, *, ready: int = 0, priority: int = 1) -> Wire:
    """Create a delivery with an explicit custody dwell at each station."""
    return {"id": key, "pickup": start, "drop": end, "robots": allowed, "deadline": deadline, "ready": ready,
            "priority": priority, "dwell": 1, "resources": {"pickup": [], "drop": []}}


def site(nodes: list[str], lanes: list[Wire], robots: list[Wire], jobs: list[Wire], *,
         resources: Wire | None = None, chargers: list[Wire] | None = None, tick: int = 0, horizon: int = 18) -> Wire:
    """Build a bounded facility request from independent authored components."""
    return {"tick": tick, "horizon": horizon, "nodes": nodes, "lanes": lanes, "robots": robots, "jobs": jobs,
            "resources": resources or {}, "chargers": chargers or []}


def call(app: Path, root: Path, spec: Wire, invalid: bool = False) -> Wire | bool | None:
    """Run the allocator on one private facility and read an ordinary report."""
    root.mkdir(mode=0o755)
    request = root / "job.json"
    request.write_text(json.dumps(spec))
    output = root / "out"
    output.mkdir()
    output.chmod(0o777)
    report = output / "plan.json"
    previous = b'{"earlier":true}\n'
    if invalid:
        report.write_bytes(previous)
        report.chmod(0o666)
    args = [sys.executable, "-BI", "-c",
            "import runpy,sys;sys.path.insert(0,'.');runpy.run_module('fleet_recovery',run_name='__main__')",
            "allocate", "--request", str(request), "--output", str(report)]
    identity = {}
    if os.geteuid() == 0:
        user = pwd.getpwnam("candidate")
        identity = dict(user=user.pw_uid, group=user.pw_gid, extra_groups=[])
    with subprocess.Popen(args, cwd=app, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          start_new_session=True, env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(output)},
                          **identity) as child:
        try:
            code = child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            code = 124
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=3)
    if report.is_symlink() or not report.is_file() or report.stat().st_size > 300_000:
        return False if invalid else None
    if invalid:
        return code not in (0, 124) and report.read_bytes() == previous
    return json.loads(report.read_text()) if code == 0 else None


def replay(spec: Wire, proposal: Wire | bool | None, expected: set[str], latest: int, total: int) -> bool:
    """Check independent physical occupancy, energy, custody and optimal known outcomes."""
    if not isinstance(proposal, dict) or not isinstance(proposal.get("itineraries"), list):
        return False
    rows = proposal["itineraries"]
    robots, jobs, lanes, chargers = ({row["id"]: row for row in spec[key]}
                                     for key in ("robots", "jobs", "lanes", "chargers"))
    reservation = set()
    completed = set()
    times = []
    order = [row["robot"] for row in rows]
    if order != sorted(set(order)):
        return False
    for row in rows:
        robot = robots[row["robot"]]
        assigned = jobs[row["job"]]
        identity = assigned["id"]
        if identity in completed or robot["id"] not in assigned["robots"] or not isinstance(row["actions"], list):
            return False
        position, energy, prior, phase = robot["node"], robot["battery"], spec["tick"], 0
        for action in row["actions"]:
            kind, name, start, end = (action[field] for field in ("kind", "id", "start", "end"))
            if (type(start) is not int or type(end) is not int or phase == 2 or not prior <= start < end <= spec["horizon"]):
                return False
            if kind == "move":
                movement = lanes[name]
                if name not in robot["lanes"] or movement["from"] != position:
                    return False
                # Both early and latest physical arrival are within the same reservation.
                early = start + movement["travel"]
                if early + movement["clearance_slack"] != end:
                    return False
                energy -= movement["energy"]
                if energy < robot["reserve"]:
                    return False
                position, occupied = movement["to"], movement["resources"]
            elif kind == "charge":
                device = chargers[name]
                if device["node"] != position or end - start != device["ticks"] or energy >= robot["capacity"]:
                    return False
                energy = min(robot["capacity"], energy + device["gain"])
                occupied = device["resources"]
            else:
                stage = ("pickup", "drop")[phase]
                if kind != stage or position != assigned[stage] or name != identity or end - start != assigned["dwell"]:
                    return False
                if kind == "pickup" and start < assigned["ready"]:
                    return False
                if kind == "drop" and end > assigned["deadline"]:
                    return False
                occupied = assigned["resources"][kind]
                phase += 1
            for resource in occupied:
                if not any(lo <= start and end <= hi for lo, hi in spec["resources"][resource]):
                    return False
                for tick in range(start, end):
                    if (resource, tick) in reservation:
                        return False
                    reservation.add((resource, tick))
            prior = end
        if phase != 2:
            return False
        completed.add(identity)
        times.append(prior)
    return completed == expected and max(times, default=0) == latest and sum(times) == total


def detour() -> tuple[Wire, set[str], int, int]:
    """One urgent fixed-route robot forces another to take a different hallway."""
    lanes = [lane("direct", "alpha-home", "alpha-end", 2, 1, 2, "gate"),
             lane("via", "alpha-home", "bypass", 2, 0, 1, "service-hall"),
             lane("away", "bypass", "alpha-end", 3, 0, 1, "service-hall"),
             lane("fixed", "beta-home", "beta-end", 3, 1, 2, "gate")]
    robots = [robot("flexible", "alpha-home", ["direct", "via", "away"]), robot("fixed", "beta-home", ["fixed"])]
    jobs = [job("feeding", "alpha-home", "alpha-end", ["flexible"], 7), job("sterile", "beta-home", "beta-end", ["fixed"], 6)]
    spec = site(["alpha-home", "alpha-end", "beta-home", "beta-end", "bypass"], lanes, robots, jobs,
                resources={"gate": [[0, 18]], "service-hall": [[0, 18]]})
    return spec, {"feeding", "sterile"}, 7, 13


def energy_job() -> tuple[Wire, set[str], int, int]:
    """The flexible assignment can only serve both requests by precharging one robot."""
    lanes = [lane("loaded-rise", "A", "X", 3, 0, 4, "lift"),
             lane("runner", "P", "Q", 2, 0, 1, "hall"), lane("cross", "P", "A", 1, 0, 1, "hall")]
    chargers = [{"id": "battery-bus", "node": "A", "ticks": 2, "gain": 4, "resources": ["power"]}]
    robots = [robot("carrier", "A", ["loaded-rise"], charge=2, capacity=6),
              robot("runner", "P", ["runner", "cross", "loaded-rise"], charge=5, capacity=5)]
    jobs = [job("materials", "A", "X", ["carrier", "runner"], 8, ready=2), job("lab", "P", "Q", ["runner"], 4)]
    spec = site(["A", "X", "P", "Q"], lanes, robots, jobs, chargers=chargers,
                resources={"lift": [[0, 18]], "hall": [[0, 18]], "power": [[0, 2], [9, 11]]})
    return spec, {"materials", "lab"}, 7, 11


def prioritize() -> tuple[Wire, set[str], int, int]:
    """Earlier admitted urgent work wins even when a later job finishes sooner."""
    edges = [lane("slow", "origin", "long", 4, 1, 2), lane("quick", "origin", "short", 1, 0, 1)]
    fleet = [robot("only", "origin", ["slow", "quick"])]
    work = [job("routine", "origin", "short", ["only"], 5, priority=0),
            job("first-urgent", "origin", "long", ["only"], 9), job("quick-urgent", "origin", "short", ["only"], 8)]
    return site(["origin", "short", "long"], edges, fleet, work), {"first-urgent"}, 7, 7


def shared_power() -> tuple[Wire, set[str], int, int]:
    """The longer charge must run first and the second robot must already have custody."""
    edges = [lane("east", "A", "X", 2, 1, 3, "east-hall"), lane("west", "B", "Y", 2, 1, 3, "west-hall")]
    chargers = [{"id": "quick", "node": "A", "ticks": 2, "gain": 3, "resources": ["shore-power"]},
                {"id": "long", "node": "B", "ticks": 3, "gain": 3, "resources": ["shore-power"]}]
    robots = [robot("battery-a", "A", ["east"], charge=1, capacity=4), robot("battery-b", "B", ["west"], charge=1, capacity=4)]
    jobs = [job("equipment", "A", "X", ["battery-a"], 9), job("clinical", "B", "Y", ["battery-b"], 8)]
    spec = site(["A", "B", "X", "Y"], edges, robots, jobs, chargers=chargers,
                resources={"east-hall": [[0, 12]], "west-hall": [[0, 12]], "shore-power": [[0, 5]]})
    return spec, {"equipment", "clinical"}, 9, 17


def sum_completion() -> tuple[Wire, set[str], int, int]:
    """A shorter crossing should get the shared resource first when makespan ties."""
    edges = [lane("fast", "A", "B", 2, 0, 1, "lane"), lane("slow", "C", "D", 4, 0, 1, "lane")]
    fleet = [robot("fast", "A", ["fast"]), robot("slow", "C", ["slow"])]
    work = [job("long-delivery", "C", "D", ["slow"], 12), job("short-delivery", "A", "B", ["fast"], 12)]
    return site(["A", "B", "C", "D"], edges, fleet, work, resources={"lane": [[0, 18]]}), {
        "long-delivery", "short-delivery"}, 8, 12


def blocked() -> tuple[Wire, set[str], int, int]:
    """Refuse a route whose worst-case clearance straddles two adjacent permits."""
    edges = [lane("slow", "A", "B", 1, 3, 2, "lift")]
    fleet = [robot("only", "A", ["slow"])]
    work = [job("preserve-clearance", "A", "B", ["only"], 7)]
    return site(["A", "B"], edges, fleet, work, resources={"lift": [[0, 3], [3, 7]]}), set(), 0, 0


def four_robot_shift() -> tuple[Wire, set[str], int, int]:
    """Keep two timed priority crossings while an unrelated lane and a wait preserve four deliveries."""
    edges = [lane("a-cross", "a", "alpha", 2, 1, 2, "J"), lane("a-circumvent", "a", "detour", 2, 0, 1, "K"),
             lane("a-return", "detour", "alpha", 3, 0, 1, "K"), lane("b-cross", "b", "beta", 2, 1, 2, "J"),
             lane("c-cross", "c", "gamma", 1, 1, 1, "K"), lane("c-circumvent", "c", "gamma", 3, 0, 1, "L"),
             lane("d-cross", "d", "delta", 2, 1, 2, "L")]
    fleet = [robot("A", "a", ["a-cross", "a-circumvent", "a-return"]), robot("B", "b", ["b-cross"]),
             robot("C", "c", ["c-cross", "c-circumvent"]), robot("D", "d", ["d-cross"])]
    work = [job("nonessential", "c", "gamma", ["C"], 4, priority=0),
            job("alpha", "a", "alpha", ["A"], 8), job("beta", "b", "beta", ["B"], 5),
            job("gamma", "c", "gamma", ["C"], 6), job("delta", "d", "delta", ["D"], 5)]
    spec = site(["a", "b", "c", "d", "alpha", "beta", "gamma", "delta", "detour"], edges, fleet, work,
                resources={"J": [[0, 12]], "K": [[0, 12]], "L": [[0, 12]]})
    return spec, {"alpha", "beta", "gamma", "delta"}, 8, 22


def network_suite(app: Path, root: Path) -> dict[str, bool]:
    """Grade complete independent itineraries against hand-derived optima."""
    evidence = {}
    fixtures = (("shared_passage_detour", detour), ("charging_and_assignment", energy_job),
                ("ordered_charging_with_shared_power", shared_power),
                ("four_robots_with_disjoint_deadline_slack", four_robot_shift),
                ("retained_urgent_admission", prioritize), ("resolve_makespan_tie_by_total_time", sum_completion),
                ("worst_case_clearance_blocks_fragmented_permit", blocked))
    for scenario, fixture in fixtures:
        try:
            spec, expected, latest, total = fixture()
            evidence[scenario] = replay(spec, call(app, root/scenario, spec), expected, latest, total)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
            evidence[scenario] = False
    spec, _, _, _ = detour()
    spec["robots"][0]["lanes"].append("uncommissioned")
    evidence["reject_malformed_commissioning"] = bool(call(app, root/"invalidate-route", spec, invalid=True))
    return evidence
