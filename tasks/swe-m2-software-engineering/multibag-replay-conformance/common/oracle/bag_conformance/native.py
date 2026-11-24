"""Read native ROS 2 bags and construct one deterministic record timeline."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore


Json = dict[str, Any]
STORES = get_typestore(Stores.ROS2_JAZZY)
CLOCK = "rosgraph_msgs/msg/Clock"


def load(path: Path) -> Json:
    """Read one JSON object."""
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def save(path: Path, payload: Json) -> None:
    """Publish a complete deterministic JSON report atomically."""
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    with NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temp = Path(output.name)
        try:
            output.write(encoded)
            output.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def integer(value: object) -> int:
    """Validate an integer timestamp or count."""
    if type(value) is not int:
        raise ValueError("Expected integer")
    return value


def text(value: object) -> str:
    """Require a nonempty string identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError("Expected identifier")
    return value


def qos(value: Json, *, publisher: bool = False) -> tuple[str, str, int]:
    """Parse the bounded playback QoS contract."""
    reliability, durability = value["reliability"], value["durability"]
    depth = integer(value["depth"]) if publisher else 1
    if reliability not in ("reliable", "best_effort") or durability not in ("volatile", "transient_local") or depth <= 0:
        raise ValueError("Invalid replay QoS")
    return reliability, durability, depth


def stamp(value: Any) -> int:
    """Convert a native builtin_interfaces/Time without float rounding."""
    if not 0 <= value.nanosec < 1_000_000_000:
        raise ValueError("Invalid native timestamp")
    return value.sec * 1_000_000_000 + value.nanosec


@dataclass(frozen=True)
class Event:
    """An indexed event and the native bytes needed by downstream consumers."""

    row: Json
    raw: bytes
    offered: tuple[str, str, int] | None


def events(spec_path: Path) -> list[Event]:
    """Open each native source and normalize its record clock, order, and epoch."""
    spec = load(spec_path)
    sources = spec["sources"]
    authority = text(spec["clock_source"])
    if not isinstance(sources, list) or not sources:
        raise ValueError("Expected bag sources")
    given = set()
    types = {}
    combined = []
    for source_index, source in enumerate(sources):
        source_id, offset = text(source["id"]), integer(source["offset_ns"])
        if source_id in given:
            raise ValueError("Duplicate source ID")
        given.add(source_id)
        supplied = source["publishers"]
        if not isinstance(supplied, dict):
            raise ValueError("Expected publisher map")
        offers = {key: qos(value, publisher=True) for key, value in supplied.items()}
        hint = Path(text(source["path"]))
        if hint.is_absolute():
            raise ValueError("Bag paths must be relative to the spec")
        local = spec_path.parent / hint
        with Reader(local) as reader:
            declared = set()
            for connection in reader.connections:
                topic, type_ = connection.topic, connection.msgtype
                if topic in declared or (topic in types and types[topic] != type_):
                    raise ValueError("Conflicting connection")
                declared.add(topic)
                types[topic] = type_
            if declared - {"/clock"} != offers.keys() or "/clock" in declared and (
                source_id != authority or types["/clock"] != CLOCK
            ):
                raise ValueError("Invalid clock authority or publisher map")
            for position, (connection, timestamp, raw) in enumerate(reader.messages()):
                source_time = timestamp + offset
                native = bytes(raw)
                row = {"source": source_id, "topic": connection.topic, "type": connection.msgtype,
                       "record_ns": source_time, "sha256": sha256(native).hexdigest()}
                combined.append(((source_time, connection.topic != "/clock", source_index, position), row, native,
                                 offers.get(connection.topic)))
    if authority not in given or types.get("/clock") != CLOCK:
        raise ValueError("Missing clock authority")
    timeline = []
    clock = None
    epoch = 0
    for _, row, raw, offered in sorted(combined, key=lambda item: item[0]):
        if row["topic"] == "/clock":
            new = stamp(STORES.deserialize_cdr(raw, CLOCK).clock)
            if clock is not None and new < clock:
                epoch += 1
            clock = new
        if clock is None:
            raise ValueError("Ordinary event before clock")
        timeline.append(Event(dict(row, clock_ns=clock, epoch=epoch), raw, offered))
    return timeline


def index(spec: Path, output: Path) -> None:
    """Save the published wire identity and replay ordering of the native recording."""
    save(output, {"schema_version": 1, "events": [event.row for event in events(spec)]})
