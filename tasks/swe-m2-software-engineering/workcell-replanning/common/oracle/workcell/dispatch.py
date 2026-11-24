"""Journal one rest-to-rest primitive at a time for the machine controller."""

from contextlib import contextmanager
import fcntl
import json
from math import isclose
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from .model import Object, identifier, integer, joint, obj, robot_from
from .timed import plan_window, read_window


def parse_request(packet: Object) -> None:
    """Require valid envelope, acknowledgement and motion window fields."""
    identifier(packet["mission_id"])
    if integer(packet["sequence"]) < 1 or integer(packet["revision"]) < 0:
        raise ValueError("invalid sequence or revision")
    if packet["previous"] is not None:
        previous = obj(packet["previous"])
        identifier(previous["command_id"])
        if previous["outcome"] not in ("completed", "cancelled"):
            raise ValueError("invalid command outcome")
    window = obj(packet["window"])
    read_window(robot_from(window["robot"]), window)


def same_json(first: Object, second: Object) -> bool:
    """Compare records independently of key order and preserve JSON data types."""
    return json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(
        second, sort_keys=True, allow_nan=False
    )


def completion_pose(window: Object, command: Object) -> list[float]:
    """Resolve the rest pose at the end of a journaled primitive."""
    if command["kind"] != "move":
        return window["nodes"][command["node"]]
    edge = next(edge for edge in window["edges"] if edge["id"] == command["edge"])
    return window["nodes"][edge["target"]]


def follows_command(packet: Object, entry: Object) -> bool:
    """Check how the controller resolved the previous pending command."""
    previous = packet["previous"]
    issued = entry["decision"]["command"]
    if issued is None:
        return previous is None
    if previous is None or previous["command_id"] != entry["decision"]["command_id"]:
        return False
    measured = packet["window"]["measured"]
    if previous["outcome"] == "cancelled":
        return (packet["revision"] > entry["packet"]["revision"]
                and issued["start"] <= measured["tick"] < issued["end"])
    target = completion_pose(entry["packet"]["window"], issued)
    return (measured["tick"] == issued["end"]
            and all(value == 0 for value in joint(measured["dq"]))
            and all(isclose(a, b, abs_tol=1e-8, rel_tol=0)
                    for a, b in zip(measured["q"], target, strict=True)))


def accepts(packet: Object, entry: Object | None) -> bool:
    """Check causal order, forecast consistency and command acknowledgement."""
    if entry is None:
        return packet["sequence"] == 1 and packet["previous"] is None
    last = entry["packet"]
    if packet["sequence"] != last["sequence"] + 1 or packet["revision"] < last["revision"]:
        return False
    if packet["revision"] == last["revision"]:
        telemetry = {"measured", "start_node", "brake_ticks"}
        old = {key: value for key, value in last["window"].items() if key not in telemetry}
        new = {key: value for key, value in packet["window"].items() if key not in telemetry}
        if not same_json(old, new):
            return False
    return follows_command(packet, entry)


@contextmanager
def locked_journal(path: Path):
    """Hold a stable advisory lock across load, decision and atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    directory = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        yield
    finally:
        os.close(directory)


def write_journal(path: Path, journal: Object) -> None:
    """Commit a whole journal with storage barriers before publishing its reply."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".dispatch-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(journal, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        descriptor = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def dispatch(packet: Object, state_path: Path) -> Object:
    """Return a stable decision or reject a request without advancing the journal."""
    parse_request(packet)
    with locked_journal(state_path):
        try:
            journal = obj(json.loads(state_path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            journal = {}
        mission = packet["mission_id"]
        entry = journal.get(mission)
        if entry is not None and same_json(packet, entry["packet"]):
            return entry["decision"]

        decision = {field: packet[field] for field in ("mission_id", "sequence", "revision")}
        decision.update(status="rejected", command=None, command_id=None)
        if not accepts(packet, entry):
            return decision

        window = packet["window"]
        report = plan_window(robot_from(window["robot"]), window)
        decision["status"] = report["status"]
        if report["commands"]:
            decision["command"] = report["commands"][0]
            decision["command_id"] = str(uuid4())
        journal[mission] = {"packet": packet, "decision": decision}
        write_journal(state_path, journal)
        return decision
