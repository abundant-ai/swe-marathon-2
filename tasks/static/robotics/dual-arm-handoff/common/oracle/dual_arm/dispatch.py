"""Journal one authorized dual-arm operation at a time."""

import fcntl
import json
import os
from uuid import uuid4

from .core import integer, name
from .planning import Window, close_pose, end_state, plan, stationary


def equivalent(left, right):
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def acceptable(previous, current, window):
    """Check sequence, authority and the controller's terminal evidence."""
    if previous is None:
        return current["sequence"] == 1 and current["previous"] is None
    old, retired = previous["packet"], previous["reply"]
    if (
        current["sequence"] != old["sequence"] + 1
        or current["revision"] < old["revision"]
    ):
        return False
    old_window = old["window"]
    if window.tick < old_window["measured"]["tick"]:
        return False
    offset = {"measured", "start_node", "brake_ticks"}
    if current["revision"] == old["revision"]:
        stable = lambda item: {
            key: value for key, value in item.items() if key not in offset
        }
        if not equivalent(stable(old_window), stable(current["window"])):
            return False
    evidence = current["previous"]
    cmd = retired["command"]
    if cmd is None:
        return evidence is None
    if evidence is None or evidence["id"] != retired["command_id"]:
        return False
    original = Window.parse(old_window)
    if evidence["outcome"] == "withdrawn":
        return (
            cmd["kind"] == "move"
            and current["revision"] > old["revision"]
            and cmd["start"] <= window.tick < cmd["end"]
            and window.owner == original.owner
        )
    expected, owner = end_state(original, cmd)
    return (
        window.tick == cmd["end"]
        and window.owner == owner
        and stationary(window.velocity)
        and close_pose(window.pose, expected)
    )


def dispatch(packet, path, publish):
    """Accept a new controller event or return its persisted latest reply."""
    mission = name(packet["mission"])
    identity = {
        "mission": mission,
        "sequence": integer(packet["sequence"], 1),
        "revision": integer(packet["revision"]),
    }
    previous = packet["previous"]
    if previous is not None:
        if not isinstance(previous, dict) or previous.get("outcome") not in (
            "withdrawn",
            "completed",
        ):
            raise ValueError("Invalid acknowledgement")
        name(previous.get("id"))
    window = Window.parse(packet["window"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {}
        existing = state.get(mission)
        if existing is not None and equivalent(existing["packet"], packet):
            return existing["reply"]
        if not acceptable(existing, packet, window):
            return dict(identity, status="rejected", command=None, command_id=None)
        route = plan(window)
        command = route["commands"][0] if route["commands"] else None
        result = dict(
            identity,
            status="issued" if command else route["status"],
            command=command,
            command_id=uuid4().hex if command else None,
        )
        state[mission] = {"packet": packet, "reply": result}
        publish(path, state)
        os.fsync(fd)
        return result
    finally:
        os.close(fd)
