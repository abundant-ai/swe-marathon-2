"""Check booking quality, atomic authority, and physical resource clearance."""

from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any

from elevator_checks import Client

Wire = dict[str, Any]


def job(identity: str, priority: int, deadline: int, *routes: tuple[str, int, tuple[str, ...]], ready: int = 0) -> Wire:
    """Commission a delivery and its mutually exclusive route alternatives."""
    return {"id": identity, "robot": f"robot-{identity}", "priority": priority, "ready": ready, "deadline": deadline,
            "routes": [{"id": code, "duration": duration, "resources": list(members)} for code, duration, members in routes]}


def request(identity: str, jobs: list[Wire], *, tick: int = 0, windows: Wire | None = None) -> Wire:
    """Create a complete authority request for two cars and two approaches."""
    override = windows or {}
    return {"event_id": identity, "tick": tick, "jobs": jobs,
            "resources": {resource: {"windows": override.get(resource, [[0, 36]]),
                                      "report": {"sequence": 0, "receipt": None}}
                          for resource in ("A", "B", "vestibule", "staff")}}


def interval(spec: Wire, job: Wire, route: Wire, begin: int, end: int) -> bool:
    """Check one route against independent time windows and its job deadline."""
    return (max(spec["tick"], job["ready"]) <= begin < end <= min(job["deadline"], spec["tick"] + 32)
            and end == begin + route["duration"]
            and all(any(lo <= begin and end <= hi for lo, hi in spec["resources"][resource]["windows"])
                    for resource in route["resources"]))


def quality(selection: tuple | list, order: list[Wire]) -> tuple:
    """Compute the public preference order for one set of nonoverlapping routes."""
    chosen = {item[0]: item[2] for item in selection}
    return (sum(row["priority"] for row in order if row["id"] in chosen), len(chosen),
            tuple(int(row["id"] in chosen) for row in order), -max(chosen.values(), default=0), -sum(chosen.values()))


def exact_small_optimum(spec: Wire, order: list[Wire], held: set[str]) -> tuple:
    """Enumerate independent time cells for the small authored control cases."""
    options = []
    for job in order:
        allowed = [None]
        for route in job["routes"]:
            if held.intersection(route["resources"]):
                continue
            for start in range(spec["tick"], min(job["deadline"], spec["tick"] + 32)):
                finish = start + route["duration"]
                if interval(spec, job, route, start, finish):
                    cells = {(item, tick) for item in route["resources"] for tick in range(start, finish)}
                    allowed.append((job["id"], start, finish, cells))
        options.append(allowed)
    best = quality([], order)
    for plan in product(*options):
        chosen = [entry for entry in plan if entry is not None]
        if len(set().union(*(entry[3] for entry in chosen))) == sum(len(entry[3]) for entry in chosen):
            best = max(best, quality(chosen, order))
    return best


def lawful(result: Wire | None, spec: Wire, *, held: tuple[str, ...] = (), completed: tuple[str, ...] = (),
           excluded: tuple[str, ...] = (), admission: tuple[str, ...] = ()) -> bool:
    """Check exact plan quality, exclusive time cells and issued grants."""
    if not isinstance(result, dict) or result.get("completed") != sorted(completed):
        return False
    jobs = {row["id"]: row for row in spec["jobs"] if row["id"] not in completed + excluded}
    ordered_ids = list(dict.fromkeys([*admission, *jobs]))
    order = sorted((jobs[key] for key in ordered_ids if key in jobs), key=lambda row: -row["priority"])
    planned, reservations, selected = set(), set(), []
    rows = result["plan"]
    if not isinstance(rows, list) or rows != sorted(rows, key=lambda row: (row["depart"], row["job"])):
        return False
    for row in rows:
        identity, begin, end = (row[key] for key in ("job", "depart", "finish"))
        if identity in planned or identity not in jobs or type(begin) is not int or type(end) is not int:
            return False
        source = jobs[identity]
        route = next((item for item in source["routes"] if item["id"] == row["route"]), None)
        if (route is None or row["robot"] != source["robot"] or set(held).intersection(route["resources"])
                or not interval(spec, source, route, begin, end)):
            return False
        cells = {(resource, time) for resource in route["resources"] for time in range(begin, end)}
        if reservations.intersection(cells):
            return False
        reservations.update(cells)
        planned.add(identity)
        selected.append((identity, begin, end))
    issued = result["grants"]
    expected = [row for row in rows if row["depart"] == spec["tick"]]
    grant_ids = [row["id"] for row in issued]
    if len(issued) != len(expected) or any(not isinstance(key, str) or not key for key in grant_ids):
        return False
    projected = sorted(({key: val for key, val in row.items() if key != "id"} for row in issued), key=lambda row: row["job"])
    if len(set(grant_ids)) != len(grant_ids) or projected != expected:
        return False
    return quality(selected, order) == exact_small_optimum(spec, order, set(held))


def observe(spec: Wire, resource: str, seq: int, grant: Wire, outcome: str = "delivered") -> None:
    """Write one device receipt into the next live request."""
    spec["resources"][resource]["report"] = {"sequence": seq, "receipt": {"grant": grant["id"], "outcome": outcome}}


def alternate_approach(call: Client) -> bool:
    """Resolve shared corridor conflicts jointly with physical lift choice."""
    spec = request("arrival", [
        job("flexible", 1, 6, ("main", 4, ("A", "vestibule")), ("staff-route", 6, ("B", "staff"))),
        job("fixed", 1, 5, ("car-A", 5, ("A", "vestibule"))),
        job("small", 0, 10, ("service-loop", 4, ("staff",)))])
    result = call(spec)
    return lawful(result, spec) and {row["job"] for row in result["grants"]} == {"flexible", "fixed"}


def fragmented_calendar(call: Client) -> bool:
    """Reserve a whole route in an overlapping service window after the shift starts."""
    spec = request("service", [job("mail", 1, 18, ("car-A", 5, ("A", "vestibule")),
                                    ("car-B", 6, ("B", "staff")), ready=4),
                               job("small", 0, 17, ("service-loop", 3, ("staff",)), ready=8)], tick=2,
                   windows={"A": [[1, 5], [5, 9], [13, 18]], "vestibule": [[2, 10], [12, 18]],
                            "staff": [[4, 8], [10, 17]]})
    return lawful(call(spec), spec)


def first_admission(call: Client) -> bool:
    """Earlier urgent work survives reordered input and beats more routine trips."""
    early = job("early", 1, 8, ("car-A", 8, ("A", "vestibule")))
    late = job("late", 1, 8, ("car-A", 8, ("A", "vestibule")))
    routine = [job("routine-1", 0, 8, ("car-A", 3, ("A",))),
               job("routine-2", 0, 8, ("car-A", 3, ("A",)))]
    initial = request("closed", [early], windows={"vestibule": []})
    if not lawful(call(initial), initial):
        return False
    spec = request("open", [*routine, late, early])
    result = call(spec)
    return lawful(result, spec, admission=("early",)) and len(result["grants"]) == 1 and result["grants"][0]["job"] == "early"


def consensus(call: Client) -> bool:
    """Lose the reply, obtain independent device evidence and clear atomically."""
    crate = job("crate", 1, 9, ("car-A", 6, ("A", "vestibule", "staff")))
    successor = job("replacement", 0, 23, ("other-car", 4, ("B", "vestibule")))
    overlap = ("A", "vestibule", "staff")
    start = request("first", [crate])
    if not call(start, lost_reply=True):
        return False
    before_retry = request("conflict-before-retrying", [successor], tick=1)
    if not lawful(call(before_retry), before_retry, held=overlap):
        return False
    response = call(start)
    if not lawful(response, start) or len(response["grants"]) != 1:
        return False
    grant = response["grants"][0]
    unrelated = job("direct", 1, 11, ("car-B", 3, ("B",)))
    later = request("partly-cleared", [successor, unrelated], tick=7)
    later["resources"]["vestibule"]["windows"] = []
    observe(later, "A", 1, grant)
    observe(later, "vestibule", 1, grant, "returned")
    partial = call(later)
    if not lawful(partial, later, held=overlap) or len(partial["grants"]) != 1:
        return False
    direct = partial["grants"][0]
    conflicting = request("still-contradictory", [successor], tick=10)
    observe(conflicting, "B", 1, direct)
    observe(conflicting, "vestibule", 1, grant)
    observe(conflicting, "staff", 9, grant)
    if not lawful(call(conflicting), conflicting, held=overlap, completed=("direct",)) or call(start) != response:
        return False
    resolved = deepcopy(conflicting)
    resolved.update(event_id="consensus", tick=12)
    observe(resolved, "vestibule", 2, grant)
    final = call(resolved)
    return lawful(final, resolved, completed=("crate", "direct")) and len(final["grants"]) == 1


def returned_stale(call: Client) -> bool:
    """Keep return evidence separate from delivery and reject invalid replay."""
    order = job("dispatch", 1, 21, ("cross", 6, ("A", "vestibule")))
    initial = request("initial", [order])
    first = call(initial)
    if not lawful(first, initial) or len(first["grants"]) != 1:
        return False
    grant = first["grants"][0]
    early = request("too-early", [order], tick=2)
    observe(early, "A", 1, grant)
    observe(early, "vestibule", 1, grant, "returned")
    if not lawful(call(early), early, held=("A", "vestibule"), excluded=("dispatch",)):
        return False
    stale = deepcopy(initial)
    stale["event_id"] = "past"
    changed = deepcopy(initial)
    changed["jobs"] = []
    if not (call(stale, invalid=True) and call(changed, invalid=True)):
        return False
    fresh = deepcopy(early)
    fresh.update(event_id="confirmed-return", tick=3)
    observe(fresh, "A", 2, grant, "returned")
    reply = call(fresh)
    return lawful(reply, fresh) and len(reply["grants"]) == 1 and reply["grants"][0]["id"] != grant["id"]


def corridor_suite(app: Path, root: Path) -> dict[str, bool]:
    """Run independent operations in fresh working directories per scenario."""
    evidence = {}
    for label, probe in (("route_swap_avoids_approach_conflict", alternate_approach),
                         ("overlap_without_joining_windows", fragmented_calendar),
                         ("priority_and_original_admission", first_admission),
                         ("clearance_consensus_after_restart", consensus),
                         ("returned_is_not_delivered_and_rejection_preserves_state", returned_stale)):
        try:
            evidence[label] = probe(Client(app, root / label, "corridors"))
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
            evidence[label] = False
    return evidence
