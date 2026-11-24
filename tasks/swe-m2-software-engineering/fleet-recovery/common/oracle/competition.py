"""Reconcile traffic revisions with durable request and authority receipts."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


PROFILE = ("radius_m", "linear_velocity_mps", "linear_acceleration_mps2",
           "angular_velocity_radps", "angular_acceleration_radps2")
NAMES = ("home", "stage", "goal")
TOLERANCE_M = 1e-6


def strict_int(value, minimum=0):
    if type(value) is not int or value < minimum or value >= 2**60:
        raise ValueError("integer outside contract")
    return value


def pose(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("pose must have three finite components")
    if any(type(component) not in (float, int) or not math.isfinite(component)
           for component in value):
        raise ValueError("pose must have three finite components")
    return value


def load_site(path):
    site = json.loads(path.read_text())
    strict_int(site["slot_ns"], 1)
    strict_int(site["max_time_ns"], 1)
    if site["max_time_ns"] // site["slot_ns"] > 128:
        raise ValueError("too many departure slots")
    if not isinstance(site["map"], str) or not site["map"]:
        raise ValueError("expected map name")
    couriers = site["couriers"]
    carrier = site["carrier"]
    if len(couriers) != 2 or carrier["id"] in couriers:
        raise ValueError("exactly two couriers and distinct carrier are required")
    stages = [name for name, record in couriers.items() if record["stage"] is not None]
    if len(stages) != 1 or carrier["stage"] is None:
        raise ValueError("carrier and exactly one courier require stage poses")
    site["stage_owner"] = stages[0]
    site["direct_owner"] = next(name for name in couriers if name != stages[0])
    for robot in (*couriers.values(), carrier):
        for name in ("home", "goal"):
            pose(robot[name])
        if robot["stage"] is not None:
            pose(robot["stage"])
        for name in PROFILE:
            value = robot["profile"][name]
            if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
                raise ValueError("invalid native vehicle limit")
    guards = site["guards"]
    if len(guards) != 2 or {guard["participant"] for guard in guards} != {
        carrier["id"], site["direct_owner"],
    }:
        raise ValueError("exactly two current trajectory guards are required")
    for guard in guards:
        if (type(guard["axis"]) is not int or guard["axis"] not in (0, 1)
                or type(guard["sign"]) is not int or guard["sign"] not in (-1, 1)
                or type(guard["position_m"]) not in (float, int)
                or not math.isfinite(guard["position_m"])):
            raise ValueError("invalid guard")
    return site


def validate_patch(patch, site):
    version = strict_int(patch["version"], 1)
    base = patch["base"]
    if base is not None and strict_int(base) >= version:
        raise ValueError("patch must advance from its base")
    strict_int(patch["carrier_plan"], 1)
    tail = strict_int(patch["carrier_tail_ns"])
    if tail > site["max_time_ns"] or patch["mode"] not in {"normal", "protected"}:
        raise ValueError("invalid schedule")
    if set(patch["jobs"]) != set(site["couriers"]):
        raise ValueError("schedule must specify both couriers")
    for job in patch["jobs"].values():
        strict_int(job["ready_ns"])
        strict_int(job["deadline_ns"])
        if type(job["priority"]) is not int or abs(job["priority"]) >= 2**31:
            raise ValueError("invalid priority")


def validate_event(event, site):
    if not isinstance(event["request_id"], str) or not event["request_id"]:
        raise ValueError("nonempty request_id is required")
    now = strict_int(event["now_ns"])
    if now > site["max_time_ns"]:
        raise ValueError("request exceeds mission horizon")
    if "patch" in event:
        validate_patch(event["patch"], site)
    by_participant = set(site["couriers"]) | {site["carrier"]["id"]}
    for key in ("cancelled", "progress"):
        reports = event.get(key, [])
        if not isinstance(reports, list):
            raise ValueError("adapter reports must be arrays")
        for report in reports:
            if report["participant"] not in by_participant:
                raise ValueError("unknown reported participant")
            strict_int(report["plan"], 1)
            pose(report["pose"])
            if key == "progress":
                strict_int(report["checkpoint"])


def replace_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(record, stream, allow_nan=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


def native_binary(directory):
    override = os.environ.get("FLEET_COMPETITION_NATIVE")
    if override:
        return Path(override)
    packaged = Path(__file__).with_name(".fleet-competition-native")
    if packaged.is_file() and os.access(packaged, os.X_OK):
        return packaged
    target = directory / ".fleet-competition-native"
    if not target.is_file():
        fleet_binary = Path(__file__).with_name("competition_native.cpp")
        root = Path(os.environ.get("RMF_ROOT", "/opt/fleet-rmf"))
        ros = root / "opt/ros/jazzy"
        libraries = (ros / "lib/x86_64-linux-gnu", ros / "lib",
                     root / "usr/lib/x86_64-linux-gnu")
        search = ":".join(map(str, libraries))
        directory.mkdir(parents=True, exist_ok=True)
        config = [
            "g++", "-std=c++17", "-O2", "-I" + str(ros / "include"),
            "-I" + os.environ.get("EIGEN_INCLUDE", "/usr/include/eigen3"),
            str(fleet_binary), "-L" + str(libraries[0]), "-L" + str(libraries[1]),
            "-Wl,-rpath-link," + str(libraries[2]),
            "-Wl,--disable-new-dtags,-rpath," + search, "-lrmf_traffic", "-lrmf_utils",
            "-o", str(target),
        ]
        subprocess.run(config, check=True, capture_output=True, timeout=50)
    return target


def schedule(site, patch, now, first_plan, native):
    couriers = sorted(site["couriers"])
    header = [json.dumps(site["map"], ensure_ascii=False), int(patch["mode"] == "protected"),
              now, site["slot_ns"], site["max_time_ns"], patch["carrier_tail_ns"]]
    values = [header]
    for robot in [*(site["couriers"][name] for name in couriers), site["carrier"]]:
        values.append([robot["profile"][name] for name in PROFILE])
        values.extend((robot["home"], robot["stage"] or robot["home"], robot["goal"]))
    for name in couriers:
        job = patch["jobs"][name]
        values.append([job["ready_ns"], min(job["deadline_ns"], site["max_time_ns"]),
                       job["priority"], int(name == site["stage_owner"])])
    by_guard = {guard["participant"]: guard for guard in site["guards"]}
    for name in (site["direct_owner"], site["carrier"]["id"]):
        guard = by_guard[name]
        values.append([guard["axis"], guard["sign"], guard["position_m"]])
    body = "\n".join(" ".join(map(str, row)) for row in values) + "\n"
    result = subprocess.run([native], input=body, check=True, text=True,
                            capture_output=True, timeout=20)
    lines = iter(result.stdout.splitlines())
    if next(lines) == "blocked":
        return None, {}
    result = {}
    checkpoints = {}

    def read_checkpoints():
        trajectory = []
        for _ in range(int(next(lines))):
            at, *position = next(lines).split()
            trajectory.append([int(at), *map(float, position)])
        return trajectory

    for offset, name in enumerate(couriers):
        legs = []
        for _ in range(int(next(lines))):
            first, last, start, end = map(int, next(lines).split())
            legs.append({"from": NAMES[first], "to": NAMES[last],
                         "start_ns": start, "end_ns": end})
        result[name] = {"plan": first_plan + offset, "legs": legs}
        checkpoints[name] = read_checkpoints()
    checkpoints[site["carrier"]["id"]] = read_checkpoints()
    return result, checkpoints


def fresh_state():
    return {"version": None, "stale": True, "patch": None, "plan": None, "next_plan": 1,
            "pending": {}, "issued": [], "progress": {}, "checkpoints": {}, "now": 0,
            "receipts": {}, "plan_needed": False, "blocked": False}


def accept_patch(state, patch):
    version = state["version"]
    if version is not None and patch["version"] <= version:
        return []
    if patch["base"] is not None and (version is None or patch["base"] != version):
        state["stale"] = True
        return []
    revocations = []
    if state["plan"] is not None:
        state["pending"] = {name: details["plan"] for name, details in state["plan"].items()}
        revocations = [{"participant": name, "plan": plan}
                       for name, plan in state["pending"].items()]
    state.update(version=patch["version"], stale=False, patch=patch, plan=None,
                 progress={}, checkpoints={}, issued=[], plan_needed=True, blocked=False)
    return revocations


def near(first, second):
    return math.dist(first[:2], second[:2]) <= TOLERANCE_M


def reconcile_cancelled(state, site, confirmations):
    for report in confirmations:
        name = report["participant"]
        if (state["pending"].get(name) == report["plan"]
                and near(report["pose"], site["couriers"][name]["home"])):
            del state["pending"][name]


def record_progress(state, site, reports, now):
    carrier = site["carrier"]["id"]
    for report in reports:
        name = report["participant"]
        plan = state["patch"]["carrier_plan"] if name == carrier else state["plan"][name]["plan"]
        index = report["checkpoint"]
        trajectory = state["checkpoints"][name]
        if plan != report["plan"] or index >= len(trajectory):
            continue
        checkpoint = trajectory[index]
        prior = state["progress"].get(name)
        if checkpoint[0] <= now and (prior is None or index >= prior["checkpoint"]):
            if near(report["pose"], checkpoint[1:]):
                state["progress"][name] = report


def guards_ready(state, site):
    staged = site["stage_owner"]
    observation = state["progress"].get(staged)
    if not observation or not near(observation["pose"], site["couriers"][staged]["stage"]):
        return False
    for guard in site["guards"]:
        other = state["progress"].get(guard["participant"])
        if not other or guard["sign"] * (other["pose"][guard["axis"]] - guard["position_m"]) < 0:
            return False
    return True


def evaluate(site, state, event, state_path):
    now = event["now_ns"]
    if now < state["now"]:
        raise ValueError("new event moved the mission clock backwards")
    state["now"] = now
    revocations = accept_patch(state, event["patch"]) if "patch" in event else []
    reconcile_cancelled(state, site, event.get("cancelled", []))
    reply = {"status": "stale", "version": state["version"], "plan": None,
             "revoke": revocations, "commands": []}
    if state["stale"]:
        return reply
    if state["pending"]:
        reply["status"] = "awaiting_cancel"
        return reply

    if state["plan_needed"]:
        state["plan"], state["checkpoints"] = schedule(
            site, state["patch"], now, state["next_plan"], native_binary(state_path.parent))
        state["plan_needed"] = False
        if state["plan"] is None:
            state["blocked"] = True
        else:
            state["next_plan"] += len(state["plan"])
            for name, details in state["plan"].items():
                reply["commands"].append({"participant": name, "plan": details["plan"], "leg": 0})
    if state["blocked"]:
        reply["status"] = "blocked"
        return reply

    record_progress(state, site, event.get("progress", []), now)
    if state["patch"]["mode"] == "protected" and 1 not in state["issued"]:
        owner = site["stage_owner"]
        planned_start = state["plan"][owner]["legs"][1]["start_ns"]
        if now > planned_start:
            state["blocked"] = True
            reply["status"] = "blocked"
            return reply
        if guards_ready(state, site):
            reply["commands"].append({"participant": owner, "plan": state["plan"][owner]["plan"],
                                      "leg": 1})
            state["issued"].append(1)
    reply["status"] = "scheduled"
    reply["plan"] = state["plan"]
    return reply


def command(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        site = load_site(args.site)
        event = json.loads(args.event.read_text())
        validate_event(event, site)
        state = json.loads(args.state.read_text()) if args.state.exists() else fresh_state()
        request = event["request_id"]
        previous = state["receipts"].get(request)
        if previous is not None:
            if previous["event"] != event:
                raise ValueError("request ID already refers to a different event")
            reply = previous["reply"]
        else:
            reply = evaluate(site, state, event, args.state)
            state["receipts"][request] = {"event": event, "reply": reply}
            replace_json(args.state, state)
        replace_json(args.output, reply)
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(2, f"rmf negotiation: {error}\n")
    return 0
