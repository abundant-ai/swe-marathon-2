"""Book exclusive corridor and lift bundles and settle them on device consensus."""

import argparse
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .elevators import array, integer, name, record, windows

Record = dict[str, Any]
HORIZON = 32


@dataclass(frozen=True)
class Slot:
    """A tentative itinerary and its exclusive time allocations."""

    wire: Record
    resources: tuple[str, ...]
    mask: int


def parse(packet: Record) -> tuple[dict, dict]:
    """Validate the booking request before touching the authority journal.

    Returns one current window calendar and report per commissioned resource.
    The original validated job objects remain the identities for later requests.
    """
    name(packet["event_id"])
    integer(packet["tick"])
    resources = record(packet["resources"])
    if not 1 <= len(resources) <= 8:
        raise ValueError("Expected one to eight resources")
    calendars, reports = {}, {}
    for identity, resource in resources.items():
        name(identity)
        calendars[identity] = windows(resource["windows"])
        report = record(resource["report"])
        integer(report["sequence"])
        if report["receipt"] is not None:
            receipt = record(report["receipt"])
            name(receipt["grant"])
            if receipt["outcome"] not in ("returned", "delivered"):
                raise ValueError("Unknown receipt outcome")
        reports[identity] = report

    jobs = array(packet["jobs"])
    identities, robots = set(), set()
    if len(jobs) > 6:
        raise ValueError("Expected at most six jobs")
    for job in jobs:
        identity, robot = name(job["id"]), name(job["robot"])
        if identity in identities or robot in robots or integer(job["priority"]) not in (0, 1):
            raise ValueError("Invalid job identity or priority")
        if integer(job["ready"]) > integer(job["deadline"]):
            raise ValueError("Readiness exceeds deadline")
        identities.add(identity)
        robots.add(robot)
        routes = array(job["routes"])
        if not 1 <= len(routes) <= 3:
            raise ValueError("Expected one to three route choices")
        codes = set()
        for route in routes:
            code = name(route["id"])
            members = [name(member) for member in array(route["resources"])]
            if code in codes or not members or len(set(members)) != len(members) or not set(members) <= calendars.keys():
                raise ValueError("Invalid route resources or identity")
            codes.add(code)
            integer(route["duration"], 1)
    return calendars, reports


def placements(job: Record, tick: int, calendars: dict, held: set[str]) -> list[Slot]:
    """Enumerate all window-compatible starts without currently held resources."""
    slots = []
    earliest = max(tick, job["ready"])
    latest = min(tick + HORIZON, job["deadline"])
    for route in job["routes"]:
        members = tuple(route["resources"])
        if held.intersection(members):
            continue
        duration = route["duration"]
        for start in range(earliest, latest - duration + 1):
            end = start + duration
            if all(any(lo <= start and end <= hi for lo, hi in calendars[item]) for item in members):
                wire = {"job": job["id"], "robot": job["robot"], "route": route["id"],
                        "depart": start, "finish": end}
                slots.append(Slot(wire, members, ((1 << duration) - 1) << (start - tick)))
    return sorted(slots, key=lambda slot: (slot.wire["finish"], slot.wire["route"]))


def optimize(queue: list[Record], tick: int, calendars: dict, held: set[str]) -> list[Slot]:
    """Choose the service-optimal conflict-free plan in priority/FIFO order.

    The caller orders queue by urgent class and durable admission. Enumerate
    one placement or skip per job. An optimistic bound ignores competition
    among the remaining jobs, so pruning preserves every better plan.
    """
    options = [placements(job, tick, calendars, held) for job in queue]
    occupied = dict.fromkeys(calendars, 0)
    best: list[Slot] = []
    best_key: tuple | None = None

    def visit(index: int, prefix: tuple[int, ...], plan: list[Slot], last: int, total: int) -> None:
        """Tighten the best plan using compatible schedules under this prefix."""
        compatible = [[slot for slot in slots if all(not occupied[r] & slot.mask for r in slot.resources)]
                      for slots in options[index:]]
        optimistic = prefix + tuple(int(bool(slots)) for slots in compatible)
        earliest = [slots[0].wire["finish"] for slots in compatible if slots]
        rank = (sum(keep * job["priority"] for keep, job in zip(optimistic, queue, strict=True)),
                sum(optimistic), optimistic, -max((last, *earliest)), -total - sum(earliest))
        nonlocal best, best_key
        if best_key is not None and rank <= best_key:
            return
        if index == len(options):
            best, best_key = plan[:], rank
            return
        for slot in compatible[0]:
            for resource in slot.resources:
                occupied[resource] |= slot.mask
            finish = slot.wire["finish"]
            visit(index + 1, (*prefix, 1), [*plan, slot], max(last, finish), total + finish)
            for resource in slot.resources:
                occupied[resource] ^= slot.mask
        visit(index + 1, (*prefix, 0), plan, last, total)

    visit(0, (), [], 0, 0)
    return sorted(best, key=lambda slot: (slot.wire["depart"], slot.wire["job"]))


def settle(state: Record, reports: dict[str, Record], tick: int) -> None:
    """Reconcile fresh evidence and release only bundles with unanimous receipts."""
    seen = state["sequences"]
    fresh = {resource: report for resource, report in reports.items() if report["sequence"] > seen.get(resource, -1)}
    seen.update({resource: report["sequence"] for resource, report in fresh.items()})
    for authority in list(state["held"].values()):
        grant, resources, evidence = (authority[key] for key in ("grant", "resources", "evidence"))
        for resource in resources:
            receipt = fresh.get(resource, {}).get("receipt")
            if (receipt and receipt["grant"] == grant["id"]
                    and (receipt["outcome"] == "returned" or tick >= grant["finish"])):
                evidence[resource] = receipt["outcome"]
        if evidence.keys() == set(resources) and len(set(evidence.values())) == 1:
            if next(iter(evidence.values())) == "delivered":
                state["completed"].append(grant["job"])
            del state["held"][grant["id"]]


def advance(state: Record, packet: Record, calendars: dict, reports: dict) -> Record:
    """Accept an event in memory and compute its complete replayable response."""
    event, tick = packet["event_id"], packet["tick"]
    if event in state["events"]:
        prior = state["events"][event]
        if json.dumps(prior["request"], sort_keys=True) != json.dumps(packet, sort_keys=True):
            raise ValueError("Event identity was reused with different contents")
        return prior["reply"]
    if tick < state["tick"] or set(calendars) != set(state["resources"]):
        raise ValueError("Stale request or changed resource set")
    prior_jobs, admission = state["jobs"], state["admission"]
    for job in packet["jobs"]:
        if job["id"] in prior_jobs and prior_jobs[job["id"]] != job:
            raise ValueError("Job fields changed under an existing identity")
        if job["id"] not in prior_jobs:
            admission[job["id"]] = len(admission)
            prior_jobs[job["id"]] = job
    state["tick"] = tick
    settle(state, reports, tick)
    in_flight = list(state["held"].values())
    excluded = {authority["grant"]["job"] for authority in in_flight} | set(state["completed"])
    busy_robots = {authority["grant"]["robot"] for authority in in_flight}
    queue = [job for job in packet["jobs"] if job["id"] not in excluded and job["robot"] not in busy_robots]
    queue.sort(key=lambda job: (-job["priority"], admission[job["id"]]))
    held = {resource for authority in in_flight for resource in authority["resources"]}
    booked = optimize(queue, tick, calendars, held)
    grants = []
    for slot in booked:
        if slot.wire["depart"] == tick:
            grant = dict(slot.wire, id=uuid4().hex)
            grants.append(grant)
            state["held"][grant["id"]] = {"grant": grant, "resources": slot.resources, "evidence": {}}
    reply = {"plan": [slot.wire for slot in booked], "grants": grants, "completed": sorted(state["completed"])}
    state["events"][event] = {"request": packet, "reply": reply}
    return reply


def command(write: Callable[[Path, Record], None]) -> int:
    """Run one corridor event with durable journal-before-reply semantics."""
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("request", "state", "output"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    args = parser.parse_args()
    try:
        packet = record(json.loads(args.request.read_text(encoding="utf-8")))
        calendars, reports = parse(packet)
        state_path = args.state.resolve()
        if state_path == args.output.resolve():
            raise ValueError("State and report paths must differ")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(state_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            state = {"tick": 0, "resources": sorted(calendars), "jobs": {}, "admission": {}, "events": {},
                     "sequences": {}, "held": {}, "completed": []}
            if state_path.exists():
                state = record(json.loads(state_path.read_text(encoding="utf-8")))
            reply = advance(state, packet, calendars, reports)
            write(state_path, state)
        finally:
            os.close(fd)
        write(args.output, reply)
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as error:
        parser.exit(1, f"fleet_recovery corridors: {error}\n")
    return 0
