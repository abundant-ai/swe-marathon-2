"""Plan a nonanticipative traffic policy and issue only observed commitments."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess

from .competition import PROFILE, near, pose, replace_json, strict_int


def positive_number(value):
    return (type(value) in (int, float) and math.isfinite(value) and value > 0)


def identifier(value):
    if not isinstance(value, str) or not value:
        raise ValueError("expected a nonempty identifier")


def named(record, minimum=1, maximum=8):
    if not isinstance(record, dict) or not minimum <= len(record) <= maximum:
        raise ValueError("invalid number of named records")
    for name in record:
        identifier(name)


def load_site(path):
    site = json.loads(path.read_text())
    identifier(site["map"])
    slot = strict_int(site["slot_ns"], 1)
    horizon = strict_int(site["max_time_ns"], 1)
    first = strict_int(site["carrier_observe_ns"], 1)
    second = strict_int(site["lift_observe_ns"], 1)
    if not first < second < horizon or horizon // slot > 128:
        raise ValueError("invalid schedule horizon or observations")
    named(site["couriers"], 2, 2)
    courier_ids = set(site["couriers"])
    carrier = site["carrier"]
    identifier(carrier["id"])
    if carrier["id"] in courier_ids:
        raise ValueError("carrier needs a separate identity")
    for platform in (*site["couriers"].values(), carrier):
        for name in ("home", "stage", "goal"):
            pose(platform[name])
        if any(not positive_number(platform["profile"][name]) for name in PROFILE):
            raise ValueError("invalid motion profile")
    for courier in site["couriers"].values():
        if strict_int(courier["deadline_ns"], 1) > horizon:
            raise ValueError("deadline exceeds the site horizon")
    named(carrier["options"])
    for option in carrier["options"].values():
        strict_int(option["plan"], 1)
        if not first <= strict_int(option["departure_ns"]) < horizon:
            raise ValueError("carrier path would precede the observation or exceed horizon")
    named(site["cabins"])
    named(site["lift_options"])
    for cabin in site["cabins"].values():
        strict_int(cabin["ride_ns"], 1)
        if set(cabin["doors"]) != courier_ids:
            raise ValueError("missing cabin door")
        for door in cabin["doors"].values():
            pose(door)
    for option in site["lift_options"].values():
        strict_int(option["version"], 1)
        if set(option["slots"]) != set(site["cabins"]):
            raise ValueError("incomplete lift schedule")
        for timings in option["slots"].values():
            if set(timings) != courier_ids:
                raise ValueError("incomplete courier timing set")
            for timing in timings.values():
                identifier(timing["session_id"])
                strict_int(timing["board_ns"], 1)
                if type(timing["floor"]) is not int:
                    raise ValueError("expected integer floor")
    return site


def read_event(path):
    event = json.loads(path.read_text())
    identifier(event["request_id"])
    strict_int(event["now_ns"])
    kind = event["kind"]
    if kind == "start":
        if event["now_ns"] != 0:
            raise ValueError("start must be at time zero")
    elif kind == "carrier":
        identifier(event["option"])
        strict_int(event["plan"], 1)
        pose(event["pose"])
    elif kind == "lift":
        identifier(event["option"])
        strict_int(event["version"], 1)
    elif kind == "door":
        for key in ("courier", "cabin", "session_id"):
            identifier(event[key])
        pose(event["pose"])
        if type(event["open"]) is not bool or type(event["floor"]) is not int:
            raise ValueError("invalid door state")
    else:
        raise ValueError("unknown event kind")
    return event


def native_binary(directory):
    override = os.environ.get("FLEET_CONTINGENT_NATIVE") or os.environ.get("FLEET_RMF_CONTINGENT_NATIVE")
    if override:
        return Path(override)
    installed = Path(__file__).with_name(".fleet-contingent-native")
    if installed.is_file() and os.access(installed, os.X_OK):
        return installed
    target = directory / ".fleet-contingent-native"
    if target.is_file():
        return target
    source = Path(__file__).with_name("contingent_native.cpp")
    root = Path(os.environ.get("RMF_ROOT", "/opt/fleet-rmf"))
    ros = root / "opt/ros/jazzy"
    libraries = (ros / "lib/x86_64-linux-gnu", ros / "lib", root / "usr/lib/x86_64-linux-gnu")
    search = ":".join(map(str, libraries))
    directory.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "g++", "-std=c++17", "-O2", "-I" + str(ros / "include"),
        "-I" + os.environ.get("EIGEN_INCLUDE", "/usr/include/eigen3"),
        str(source), "-L" + str(libraries[0]), "-L" + str(libraries[1]),
        "-Wl,-rpath-link," + str(libraries[2]), "-Wl,--disable-new-dtags,-rpath," + search,
        "-lrmf_traffic", "-lrmf_utils", "-o", str(target),
    ], check=True, capture_output=True, timeout=50)
    return target


def make_policy(site, native):
    couriers = sorted(site["couriers"])
    carriers = sorted(site["carrier"]["options"])
    cabins = sorted(site["cabins"])
    outcomes = sorted(site["lift_options"])
    timeline = ("slot_ns", "max_time_ns", "carrier_observe_ns", "lift_observe_ns")
    values = [[json.dumps(site["map"], ensure_ascii=False), *(site[key] for key in timeline)]]
    for robot in [*(site["couriers"][key] for key in couriers), site["carrier"]]:
        values.append([robot["profile"][key] for key in PROFILE])
        values.extend(robot[key] for key in ("home", "stage", "goal"))
    values.append([site["couriers"][key]["deadline_ns"] for key in couriers])
    values.append([len(carriers), len(cabins), len(outcomes)])
    values.append([site["carrier"]["options"][key]["departure_ns"] for key in carriers])
    for name in cabins:
        cabin = site["cabins"][name]
        values.append([cabin["ride_ns"]])
        values.extend(cabin["doors"][key] for key in couriers)
    for name in outcomes:
        slots = site["lift_options"][name]["slots"]
        for cabin in cabins:
            values.append([slots[cabin][key]["board_ns"] for key in couriers])
    body = "\n".join(" ".join(map(str, row)) for row in values) + "\n"
    result = subprocess.run([native], input=body, text=True, check=True, capture_output=True, timeout=20)
    lines = iter(result.stdout.splitlines())
    if next(lines) == "blocked":
        return None

    def moves():
        return {key: dict(zip(("start_ns", "end_ns"), map(int, next(lines).split()), strict=True))
                for key in couriers}

    root = {"approaches": moves(), "after_carrier": {}}
    for branch in carriers:
        suffix = {"crossings": moves(), "after_lift": {}}
        for outcome in outcomes:
            assignments = {}
            for key in couriers:
                cabin, start, end, board, delivery = map(int, next(lines).split())
                assignments[key] = {"cabin": cabins[cabin], "start_ns": start, "end_ns": end,
                                    "board_ns": board, "arrival_ns": delivery}
            suffix["after_lift"][outcome] = {"dock": assignments}
        root["after_carrier"][branch] = suffix
    return root


def travel_commands(kind, moves):
    result = []
    for courier, move in moves.items():
        command = {"kind": kind, "courier": courier, "start_ns": move["start_ns"],
                   "end_ns": move["end_ns"]}
        if kind == "dock":
            command["cabin"] = move["cabin"]
        result.append(command)
    return result


def observe_carrier(site, state, event):
    name = event["option"]
    option = site["carrier"]["options"].get(name)
    if (state["carrier"] is not None or option is None
            or event["now_ns"] < site["carrier_observe_ns"]
            or event["plan"] != option["plan"] or not near(event["pose"], site["carrier"]["stage"])):
        return []
    moves = state["policy"]["after_carrier"][name]["crossings"]
    if event["now_ns"] > min(move["start_ns"] for move in moves.values()):
        return []
    state["carrier"] = name
    return travel_commands("cross", moves)


def observe_lift(site, state, event):
    name = event["option"]
    option = site["lift_options"].get(name)
    if (state["carrier"] is None or state["lift"] is not None or option is None
            or event["now_ns"] < site["lift_observe_ns"] or event["version"] != option["version"]):
        return []
    suffix = state["policy"]["after_carrier"][state["carrier"]]
    moves = suffix["after_lift"][name]["dock"]
    if event["now_ns"] > min(move["start_ns"] for move in moves.values()):
        return []
    state["lift"] = name
    return travel_commands("dock", moves)


def observe_door(site, state, event):
    courier = event["courier"]
    if state["lift"] is None or courier in state["boarded"] or courier not in site["couriers"]:
        return []
    branch = state["policy"]["after_carrier"][state["carrier"]]["after_lift"][state["lift"]]
    move = branch["dock"][courier]
    cabin = move["cabin"]
    slot = site["lift_options"][state["lift"]]["slots"][cabin][courier]
    if (event["cabin"] != cabin or event["session_id"] != slot["session_id"]
            or event["floor"] != slot["floor"] or not event["open"] or event["now_ns"] != slot["board_ns"]
            or not near(event["pose"], site["cabins"][cabin]["doors"][courier])):
        return []
    state["boarded"].append(courier)
    return [{"kind": "board", "courier": courier, "cabin": cabin, "session_id": slot["session_id"],
             "start_ns": move["board_ns"], "end_ns": move["arrival_ns"]}]


def evaluate(site, state, event, state_path):
    now = event["now_ns"]
    if now < state["now"]:
        raise ValueError("new request moved mission time backwards")
    state["now"] = now
    kind = event["kind"]
    commands = []
    if not state["initialized"]:
        if kind != "start":
            raise ValueError("a fresh journal needs a start event")
        state["policy"] = make_policy(site, native_binary(state_path.parent))
        state["initialized"] = True
        if state["policy"] is not None:
            commands = travel_commands("approach", state["policy"]["approaches"])
    elif kind == "start":
        raise ValueError("mission already initialized")
    elif state["policy"] is not None:
        observer = {"carrier": observe_carrier, "lift": observe_lift, "door": observe_door}[kind]
        commands = observer(site, state, event)
    return {"status": "ready" if state["policy"] is not None else "blocked",
            "policy": state["policy"], "commands": commands}


def command(argv):
    parser = argparse.ArgumentParser()
    for option in ("site", "state", "event", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        site = load_site(args.site)
        event = read_event(args.event)
        initial = {"initialized": False, "now": 0, "boarded": [], "policy": None,
                   "carrier": None, "lift": None, "receipts": {}}
        state = json.loads(args.state.read_text()) if args.state.exists() else initial
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
    except (OSError, TypeError, KeyError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(2, f"rmf contingent: {error}\n")
    return 0
