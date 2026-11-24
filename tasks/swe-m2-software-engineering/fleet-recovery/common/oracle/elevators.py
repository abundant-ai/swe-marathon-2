"""Optimize shared lift use and recover issued grants from a durable journal."""

import argparse
from functools import cache
import fcntl
import json
import os
from pathlib import Path
from uuid import uuid4


def record(value):
    """Read a JSON object used by the lift protocol."""
    if not isinstance(value, dict):
        raise ValueError("Expected an object")
    return value


def integer(value, minimum=0, maximum=None):
    """Read an exact integer in its commissioned range."""
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError("Invalid integer")
    return value


def name(value):
    """Read a nonempty identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid identifier")
    return value


def array(value):
    """Read a JSON array."""
    if not isinstance(value, list):
        raise ValueError("Expected an array")
    return value


def windows(value):
    """Parse independent lift authorizations in chronological order."""
    result = []
    for interval in array(value):
        if len(array(interval)) != 2:
            raise ValueError("Invalid window")
        lo, hi = map(integer, interval)
        if lo >= hi:
            raise ValueError("Empty window")
        result.append((lo, hi))
    result.sort()
    if any(a[1] > b[0] for a, b in zip(result, result[1:])):
        raise ValueError("Overlapping windows")
    return result


def parse(packet):
    """Validate and normalize the active shift request."""
    name(packet["event_id"])
    integer(packet["tick"])
    lifts = record(packet["lifts"])
    if not 1 <= len(lifts) <= 2:
        raise ValueError("Expected one or two lifts")
    fixed, timing, reports = {}, {}, {}
    for lift, value in lifts.items():
        name(lift)
        device = record(value)
        fixed[lift] = [integer(device["travel"], 1), integer(device["dwell"], 1)]
        timing[lift] = windows(device["windows"])
        observed = record(device["report"])
        integer(observed["sequence"])
        if observed["floor"] is not None:
            integer(observed["floor"], 0, 20)
        if observed["settled"] is not None:
            settlement = record(observed["settled"])
            name(settlement["id"])
            if settlement["outcome"] not in ("delivered", "returned"):
                raise ValueError("Unknown settlement kind")
        reports[lift] = observed
    jobs = {}
    assigned_robots = set()
    for raw in array(packet["jobs"]):
        job = record(raw)
        identity, robot = name(job["id"]), name(job["robot"])
        src, dst = (integer(job[key], 0, 20) for key in ("origin", "destination"))
        ready, deadline = (integer(job[key]) for key in ("ready", "deadline"))
        supported = [name(lift) for lift in array(job["lifts"])]
        if (identity in jobs or robot in assigned_robots or src == dst or ready > deadline
                or not supported or len(supported) != len(set(supported)) or not set(supported) <= lifts.keys()):
            raise ValueError("Invalid parcel or fleet constraint")
        jobs[identity] = job
        assigned_robots.add(robot)
    if len(jobs) > 8:
        raise ValueError("Too many jobs")
    return fixed, timing, reports, jobs


def trip(job, lift, free_tick, floor, durations, calendar):
    """Place a job at the earliest feasible opportunity after the previous position."""
    travel, dwell = durations
    empty = abs(floor - job["origin"]) * travel
    length = abs(job["origin"] - job["destination"]) * travel + dwell * 2
    for lo, hi in calendar:
        leave = max(lo, free_tick)
        load = max(job["ready"], leave + empty)
        settle = load + length
        if settle <= min(hi, job["deadline"]):
            return (leave, lift, job["id"], job["robot"], load, settle)
    return None


def optimized(queue, starts, fixed, timing):
    """Match both lift itineraries jointly, allowing unschedulable jobs to remain queued."""
    lifts = tuple(sorted(starts))

    @cache
    def solve(remaining, slots):
        best = ()
        best_rank = (0, 0)
        for job_id in remaining:
            rest = tuple(other for other in remaining if other != job_id)
            job = queue[job_id]
            for index, lift in enumerate(lifts):
                if lift not in job["lifts"]:
                    continue
                free, floor = slots[index]
                edge = trip(job, lift, free, floor, fixed[lift], timing[lift])
                if edge is None:
                    continue
                future = slots[:index] + ((edge[-1], job["destination"]),) + slots[index + 1:]
                plan = tuple(sorted((edge, *solve(rest, future))))
                score = len(plan), -max(step[-1] for step in plan)
                if score > best_rank or (score == best_rank and plan < best):
                    best, best_rank = plan, score
        return best

    return solve(tuple(sorted(queue)), tuple(starts[identity] for identity in lifts))


def evidence(state, reports, tick):
    """Apply only fresh physical reports and matching terminal grant evidence."""
    held, seen, completed = state["held"], state["reports"], state["completed"]
    for lift, observed in reports.items():
        if observed["sequence"] <= seen.get(lift, {"sequence": -1})["sequence"]:
            continue
        seen[lift] = observed
        grant, ack = held.get(lift), observed["settled"]
        if grant is None or ack is None or ack["id"] != grant["id"]:
            continue
        if (ack["outcome"] == "delivered" and tick >= grant["settle"]
                and observed["floor"] == grant["destination"]):
            completed.append(grant["job"])
            del held[lift]
        elif ack["outcome"] == "returned" and observed["floor"] == grant["origin_floor"]:
            del held[lift]


def step(state, data, definitions):
    """Reconcile physical authority and release just the immediately executable trips."""
    fixed, timing, reports, jobs = definitions
    tick, event = data["tick"], data["event_id"]
    old = state["events"].get(event)
    if old is not None:
        if json.dumps(old["request"], sort_keys=True) != json.dumps(data, sort_keys=True):
            raise ValueError("Changed retransmission")
        return old["reply"]
    if tick < state["tick"] or fixed != state["fixed"]:
        raise ValueError("Stale tick or amended lift commissioned settings")
    for identity, job in jobs.items():
        if identity in state["jobs"] and state["jobs"][identity] != job:
            raise ValueError("A commissioned parcel changed under its existing ID")
        state["jobs"][identity] = job
    state["tick"] = tick
    evidence(state, reports, tick)
    held, seen = state["held"], state["reports"]
    reserved_jobs = {item["job"] for item in held.values()} | set(state["completed"])
    reserved_robots = {item["robot"] for item in held.values()}
    queue = {key: job for key, job in jobs.items()
             if key not in reserved_jobs and job["robot"] not in reserved_robots}
    ready = {lift: (tick, report["floor"]) for lift, report in seen.items()
             if report["floor"] is not None and lift not in held}
    plan, grants = [], []
    for entry in optimized(queue, ready, fixed, timing):
        leave, lift, job, robot, load, settle = entry
        trip_data = {"job": job, "lift": lift, "robot": robot,
                     "depart": leave, "pickup": load, "settle": settle}
        plan.append(trip_data)
        if leave == tick:
            grant = dict(trip_data, id=uuid4().hex)
            held[lift] = dict(grant, origin_floor=ready[lift][1], destination=queue[job]["destination"])
            grants.append(grant)
    reply = {"plan": plan, "grants": grants, "completed": sorted(state["completed"])}
    state["events"][event] = {"request": data, "reply": reply}
    return reply


def command(write):
    """Serve the lift planning extension with serialized journal writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        packet = record(json.loads(args.request.read_text(encoding="utf-8")))
        parsed = parse(packet)
        state_path = args.state.resolve()
        if state_path == args.output.resolve():
            raise ValueError("State and report paths must differ")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(state_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            state = {"fixed": parsed[0], "held": {}, "reports": {}, "jobs": {},
                     "completed": [], "events": {}, "tick": 0}
            if state_path.exists():
                state = record(json.loads(state_path.read_text(encoding="utf-8")))
            reply = step(state, packet, parsed)
            write(state_path, state)
        finally:
            os.close(fd)
        write(args.output, reply)
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as error:
        parser.exit(1, f"fleet_recovery elevators: {error}\n")
    return 0
