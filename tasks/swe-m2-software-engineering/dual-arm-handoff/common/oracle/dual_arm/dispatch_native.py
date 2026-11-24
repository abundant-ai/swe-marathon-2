"""Journal native move authority and settle it against measured arm receipts."""

import fcntl
import json
import os
from uuid import uuid4

import numpy as np

from .native_cell import angular_delta
from .plan_native import Problem, brake, canonical, plan_native


# Task-space acceptance at the terminal pose is separate from joint readback.
ENDPOINT_JOINT_RAD = .035
STOPPED_RAD_S = .17
READY_RAD_S = .025
GOAL_TRANSLATION_M = .025
GOAL_ROTATION_RAD = .075


def identifier(value):
    """Require nonempty mission and command identifiers."""
    if type(value) is not str or not value:
        raise ValueError("expected a nonempty authority identifier")
    return value


def counter(value, minimum):
    """Validate integer sequence or revision values."""
    if type(value) is not int or value < minimum:
        raise ValueError("invalid native dispatch counter")
    return value


def encoded(value):
    """Compare requests without sensitivity to JSON object order."""
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def checked_packet(packet):
    """Validate complete controller evidence before accessing durable state."""
    if type(packet) is not dict:
        raise ValueError("controller packet must be an object")
    identity = {"mission": identifier(packet["mission"]), "sequence": counter(packet["sequence"], 1),
                "revision": counter(packet["revision"], 0)}
    evidence = packet["previous"]
    if evidence is not None:
        if type(evidence) is not dict or evidence.get("outcome") not in ("completed", "withdrawn"):
            raise ValueError("invalid drive completion or withdrawal evidence")
        identifier(evidence["id"])
        if "receiver_confirmed" in evidence and type(evidence["receiver_confirmed"]) is not bool:
            raise ValueError("receiver confirmation must be boolean")
    window = packet["window"]
    if type(window) is not dict:
        raise ValueError("native planning window must be an object")
    # Reject nonfinite JSON even in preserved metadata.
    encoded(packet)
    return identity, Problem.read(window)


def fixed_window(window):
    """Keep commissioning, payload, trajectory bounds and task targets immutable."""
    return {key: value for key, value in window.items() if key not in {"measured", "fixtures"}}


def authority(existing, packet, current):
    """Classify a receipt without relying on its asserted motion outcome alone."""
    if existing is None:
        if packet["sequence"] == 1 and packet["previous"] is None:
            return "new"
        return None

    old, reply = existing["packet"], existing["reply"]
    old_window, new_window = old["window"], packet["window"]
    old_measurement = old_window["measured"]
    if (packet["sequence"] != old["sequence"] + 1 or packet["revision"] < old["revision"]
            or current.tick < old_measurement["tick"]
            or encoded(fixed_window(old_window)) != encoded(fixed_window(new_window))):
        return None
    newer = packet["revision"] > old["revision"]
    if not newer and encoded(old_window["fixtures"]) != encoded(new_window["fixtures"]):
        return None

    command, evidence = reply["command"], packet["previous"]
    old_owner = old_measurement["owner"]
    if command is None:
        if evidence is None and current.owner == old_owner:
            return "new"
        return None
    if evidence is None or evidence["id"] != reply["command_id"]:
        return None
    if evidence["outcome"] == "withdrawn":
        if (command["kind"] == "move" and newer and command["start"] < current.tick < command["end"]
                and current.owner == old_owner):
            return "withdrawn"
        return None

    if current.tick != command["end"] or np.any(np.abs(current.velocity) > STOPPED_RAD_S):
        return None
    if command["kind"] == "transfer":
        if evidence.get("receiver_confirmed") is not True or current.owner != command["to"]:
            return None
        expected = canonical(old_measurement["q"])
    else:
        if current.owner != old_owner:
            return None
        expected = canonical(command["q"])
    if np.all(np.abs(current.start - expected) <= ENDPOINT_JOINT_RAD):
        return "completed"
    return None


def terminal(problem):
    """Check the actual object and holder instead of assuming the plan finished."""
    if problem.owner != problem.receiver or np.any(np.abs(problem.velocity) > READY_RAD_S):
        return False
    geometry = problem.geometry
    geometry.sites(problem.start)
    measured = geometry.payload_pose(problem.owner)
    target = problem.goal
    shift = np.linalg.norm(measured[:3, 3] - target[:3, 3])
    angle = np.linalg.norm(angular_delta(target[:3, :3], measured[:3, :3]))
    return (shift <= GOAL_TRANSLATION_M and angle <= GOAL_ROTATION_RAD
            and geometry.distance(problem.start, problem.owner, problem.margin) >= problem.margin)


def choose(packet, problem, receipt):
    """Brake after revocation or dispatch one certified prefix from the measured state."""
    if receipt == "withdrawn":
        stopped = brake(problem)
        if stopped is None:
            return "blocked", None
        return "issued", stopped[0]
    if terminal(problem):
        return "ready", None
    planned = plan_native(packet["window"])
    if planned["commands"]:
        return "issued", planned["commands"][0]
    return planned["status"], None


def dispatch_native(packet, state_path, publish):
    """Persist the accepted controller decision before returning it to the publisher."""
    identity, problem = checked_packet(packet)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock = os.open(state_path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = json.loads(state_path.read_text())
        except FileNotFoundError:
            state = {}
        if type(state) is not dict:
            raise ValueError("native authority journal must be an object")
        key = identity["mission"]
        existing = state.get(key)
        if existing is not None and encoded(existing["packet"]) == encoded(packet):
            return existing["reply"]
        receipt = authority(existing, packet, problem)
        if receipt is None:
            return dict(identity, status="rejected", command=None, command_id=None)
        status, command = choose(packet, problem, receipt)
        result = dict(identity, status=status, command=command, command_id=uuid4().hex if command else None)
        state[key] = {"packet": packet, "reply": result}
        publish(state_path, state)
        os.fsync(lock)
        return result
    finally:
        os.close(lock)
