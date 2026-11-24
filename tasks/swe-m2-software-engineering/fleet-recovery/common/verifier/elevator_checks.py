"""Independently execute shared-lift forecasts and physical settlement cases."""

from copy import deepcopy
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys


def fixture_report(floor, fuse, settled=None):
    return {"floor": floor, "sequence": fuse, "settled": settled}


def lift(floor, travel, *, windows=None):
    return {"travel": travel, "dwell": 1, "windows": [[0, 40]] if windows is None else windows,
            "report": fixture_report(floor, 5)}


def job(name, robot, src, dst, limit, lifts, ready=0):
    return {"id": name, "robot": robot, "origin": src, "destination": dst, "ready": ready,
            "deadline": limit, "lifts": lifts}


def seed():
    """Commission tight work where assigning the flexible parcel greedily loses the fixed job."""
    return {"event_id": "ready", "tick": 0, "lifts": {"A": lift(0, 1), "B": lift(0, 2)},
            "jobs": [job("linen", "mobile", 0, 2, 6, ["A", "B"]),
                     job("tools", "fixed", 0, 3, 5, ["A"])]}


class Client:
    """Run each packet in a fresh process with the same shift journal."""

    def __init__(self, app: Path, directory: Path, command: str = "elevators") -> None:
        """Run the named fleet command using a private per-case working directory."""
        self.app, self.directory = app, directory
        self.command = command
        directory.mkdir()
        directory.chmod(0o777)
        self.index = 0

    def __call__(self, spec: dict, invalid: bool = False, lost_reply: bool = False) -> dict | bool | None:
        """Send one packet, optionally checking rejection or simulating failed output."""
        self.index += 1
        request = self.directory / f"dispatch-{self.index}.json"
        target = self.directory / f"report-{self.index}.json"
        request.write_text(json.dumps(spec), encoding="utf-8")
        sentinel = '{"valid":true}\n'
        if lost_reply:
            target.mkdir()
        elif invalid:
            target.write_text(sentinel, encoding="utf-8")
            target.chmod(0o666)
        params = [sys.executable, "-BI", "-c",
                  "import runpy,sys;sys.path.insert(0,'.');runpy.run_module('fleet_recovery',run_name='__main__')",
                  self.command, "--request", str(request), "--state", str(self.directory / "shift"),
                  "--output", str(target)]
        options = {}
        if os.geteuid() == 0:
            identity = pwd.getpwnam("candidate")
            options = {"user": identity.pw_uid, "group": identity.pw_gid, "extra_groups": []}
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(self.directory)}
        with subprocess.Popen(params, cwd=self.app, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True, **options) as task:
            try:
                code = task.wait(timeout=10)
            except subprocess.TimeoutExpired:
                code = 124
            finally:
                try:
                    os.killpg(task.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                task.wait(timeout=3)
        if lost_reply:
            return code not in (0, 124) and target.is_dir()
        if not target.is_file() or target.is_symlink() or target.stat().st_size > 36_000:
            return False if invalid else None
        if invalid:
            return code not in (0, 124) and target.read_text() == sentinel
        return json.loads(target.read_text()) if code == 0 else None


def lawful_plan(response, spec, *, blocked=(), completed=(), expected=None):
    """Replay proposed lift legs with private known facts and an authored optimum."""
    if not isinstance(response, dict):
        return False
    expected_ids = sorted(completed)
    if response.get("completed") != expected_ids:
        return False
    job_by = {item["id"]: item for item in spec["jobs"]}
    lifts = spec["lifts"]
    slots = {key: (spec["tick"], value["report"]["floor"])
             for key, value in lifts.items() if key not in blocked and value["report"]["floor"] is not None}
    plan, grants = response.get("plan"), response.get("grants")
    if not isinstance(plan, list) or not isinstance(grants, list):
        return False
    seen = set()
    for entry in plan:
        if not isinstance(entry, dict) or type(entry.get("depart")) is not int:
            return False
        identity, car = entry.get("job"), entry.get("lift")
        if identity not in job_by or identity in seen or identity in completed or car not in slots:
            return False
        seen.add(identity)
        order = job_by[identity]
        earliest, floor = slots[car]
        if (car not in order["lifts"] or entry.get("robot") != order["robot"]
                or any(type(entry.get(key)) is not int for key in ("pickup", "settle"))):
            return False
        lo, pickup, hi = entry["depart"], entry["pickup"], entry["settle"]
        config = lifts[car]
        rate, dwell = config["travel"], config["dwell"]
        if (lo < earliest or pickup < max(lo + abs(order["origin"] - floor) * rate, order["ready"])
                or hi != pickup + 2*dwell + abs(order["destination"]-order["origin"])*rate
                or hi > order["deadline"] or not any(a <= lo <= hi <= b for a, b in config["windows"])):
            return False
        slots[car] = hi, order["destination"]
    if [x["depart"] for x in plan] != sorted(x["depart"] for x in plan):
        return False
    wanted = [entry for entry in plan if entry["depart"] == spec["tick"]]
    if (len(grants) != len(wanted) or len({grant.get("id") for grant in grants}) != len(grants)
            or any(not isinstance(grant.get("id"), str) or not grant["id"] for grant in grants)
            or any({k: v for k, v in grant.items() if k != "id"} not in wanted for grant in grants)):
        return False
    if expected is not None and (len(plan), max((x["settle"] for x in plan), default=0)) != expected:
        return False
    return True


def ack(grant, outcome="delivered"):
    return {"id": grant["id"], "outcome": outcome}


def primary_recovery(call):
    """Fail over one car, keep the other moving, and resolve the original grant after restart."""
    initial = seed()
    original = call(initial)
    if not lawful_plan(original, initial, expected=(2, 6)):
        return False
    grants = {item["lift"]: item for item in original["grants"]}
    if set(grants) != {"A", "B"} or {key: val["job"] for key, val in grants.items()} != {"A": "tools", "B": "linen"}:
        return False

    shift = deepcopy(initial)
    shift.update(event_id="late-reply", tick=6)
    shift["lifts"]["A"]["report"] = fixture_report(3, 5, ack(grants["A"]))
    shift["lifts"]["B"]["report"] = fixture_report(2, 6, ack(grants["B"]))
    shift["jobs"] = [item for item in initial["jobs"] if item["id"] == "linen"]
    shift["jobs"].extend((job("meal", "meal-bot", 2, 3, 10, ["B"]),
                         job("bags", "bag-bot", 3, 4, 19, ["A"])))
    interim = call(shift)
    if not lawful_plan(interim, shift, blocked=("A",), completed=("linen",), expected=(1, 10)):
        return False
    if not interim["grants"] or interim["grants"][0]["job"] != "meal":
        return False
    if call(initial) != original:
        return False

    out_of_date = deepcopy(shift)
    out_of_date.update(event_id="foreign", tick=10)
    out_of_date["lifts"]["A"]["report"] = fixture_report(3, 6, {"id": "different", "outcome": "delivered"})
    out_of_date["lifts"]["B"]["report"] = fixture_report(3, 7, ack(interim["grants"][0]))
    lost = call(out_of_date)
    if not lawful_plan(lost, out_of_date, blocked=("A",), completed=("linen", "meal"), expected=(0, 0)):
        return False
    final = deepcopy(out_of_date)
    final.update(event_id="receiver-online", tick=12)
    final["lifts"]["A"]["report"] = fixture_report(3, 9, ack(grants["A"]))
    resumed = call(final)
    return lawful_plan(resumed, final, completed=("linen", "meal", "tools"), expected=(1, 15))


def calendar(call, joined=False):
    """Respect lift-specific clocks, waiting and the physical car's floor."""
    spec = {"event_id": "calendar", "tick": 2,
            "lifts": {"A": lift(3, 1, windows=[[0, 3], [7, 11], [11, 16]] if joined else [[0, 3], [7, 16]]),
                      "B": lift(None, 1)},
            "jobs": [job("tray", "loop", 2, 5, 13, ["A"], 8)]}
    target = (0, 0) if joined else (1, 13)
    result = call(spec)
    return lawful_plan(result, spec, expected=target) and result["grants"] == []


def return_to_pickup(call):
    """Accept a fresh returned receipt without marking an undelivered parcel complete."""
    spec = seed()
    result = call(spec)
    if not lawful_plan(result, spec, expected=(2, 6)) or len(result["grants"]) != 2:
        return False
    active = {order["lift"]: order for order in result["grants"]}
    after = deepcopy(spec)
    after.update(event_id="returned", tick=3)
    after["lifts"]["A"]["report"] = fixture_report(0, 6, ack(active["A"], "returned"))
    after["lifts"]["B"]["report"] = fixture_report(None, 6)
    after["jobs"].append(job("fresh", "service-bot", 0, 1, 6, ["A"]))
    result = call(after)
    return (lawful_plan(result, after, blocked=("B",), expected=(1, 6))
            and len(result["grants"]) == 1 and result["grants"][0]["job"] == "fresh")


def serial_optimum(call):
    """Require two consecutive trips and the better of the two physical floor orderings."""
    spec = {"event_id": "two-trips", "tick": 0, "lifts": {"A": lift(0, 1)},
            "jobs": [job("low", "low-bot", 0, 2, 20, ["A"]), job("high", "high-bot", 2, 4, 20, ["A"])]}
    initial = call(spec)
    if not lawful_plan(initial, spec, expected=(2, 8)) or len(initial["grants"]) != 1:
        return False
    grant = initial["grants"][0]
    if grant["job"] != "low":
        return False
    settled = deepcopy(spec)
    settled.update(event_id="second-trip", tick=4)
    settled["lifts"]["A"]["report"] = fixture_report(2, 6, ack(grant))
    return lawful_plan(call(settled), settled, completed=("low",), expected=(1, 8))


def reject_changed_event(call):
    """Preserve a durable decision on a conflicting duplicate or bad availability calendar."""
    spec = seed()
    first = call(spec)
    if not lawful_plan(first, spec, expected=(2, 6)):
        return False
    altered = deepcopy(spec)
    altered["tick"] = 1
    broken = deepcopy(altered)
    broken["event_id"] = "bad-window"
    broken["lifts"]["A"]["windows"] = [[0, 7], [5, 10]]
    if not (call(altered, invalid=True) and call(broken, invalid=True) and call(spec) == first):
        return False
    later = deepcopy(spec)
    later.update(event_id="new-work", tick=7)
    later["lifts"]["A"]["report"] = fixture_report(3, 7)
    later["jobs"] = [job("unreleased", "another", 3, 4, 10, ["A"])]
    return lawful_plan(call(later), later, blocked=("A", "B"), expected=(0, 0))


def elevator_suite(app, root):
    """Report closed-loop observable outcomes for disjoint scenarios."""
    cases = (
        ("joint_optimum_and_restart", primary_recovery),
        ("wait_for_calendar", calendar),
        ("never_join_fragments", lambda c: calendar(c, joined=True)),
        ("returned_custody_is_not_delivery", return_to_pickup),
        ("floor_ordering_and_second_trip", serial_optimum),
        ("reject_invalid_and_preserve_grant", reject_changed_event),
    )
    results = {}
    for name, task in cases:
        try:
            results[name] = bool(task(Client(app, root / name)))
        except (ValueError, OSError, KeyError, TypeError, IndexError):
            results[name] = False
    return results
