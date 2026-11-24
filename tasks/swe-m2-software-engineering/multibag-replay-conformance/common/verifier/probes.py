"""Verify native bag indexing, delivery traces, and downstream poses without oracle code."""

from dataclasses import dataclass
from hashlib import sha256
import json
from math import cos, isclose, pi, sin
from pathlib import Path
from typing import Callable

from rosbags.rosbag2 import StoragePlugin, Writer
from rosbags.typesys import Stores, get_typestore


TS = get_typestore(Stores.ROS2_JAZZY)
CLOCK, TEXT, TF = "rosgraph_msgs/msg/Clock", "std_msgs/msg/String", "tf2_msgs/msg/TFMessage"
Run = Callable[..., int]


@dataclass(frozen=True)
class Native:
    """One authored event independent of the playback model."""
    name: str
    source: str
    topic: str
    type: str
    record: int
    clock: int
    epoch: int
    payload: object


def stamp(ns: int) -> object:
    """Make an integer ROS message time."""
    return TS.types["builtin_interfaces/msg/Time"](*divmod(ns, 10**9))


def clock(value: int) -> object:
    """Make a native clock payload."""
    return TS.types[CLOCK](stamp(value))


def tf(parent: str, child: str, x: float, y: float, yaw: float, timestamp: int) -> object:
    """Encode one authored parent-from-child transform."""
    msg_type = TS.types
    header = msg_type["std_msgs/msg/Header"](stamp(timestamp), parent)
    rotation = msg_type["geometry_msgs/msg/Quaternion"](0.0, 0.0, sin(yaw / 2), cos(yaw / 2))
    translation = msg_type["geometry_msgs/msg/Vector3"](x, y, 0.0)
    transform = msg_type["geometry_msgs/msg/Transform"](translation, rotation)
    return msg_type[TF]([msg_type["geometry_msgs/msg/TransformStamped"](header, child, transform)])


def dump(path: Path, item: object) -> Path:
    """Write a trusted private script or recording manifest."""
    path.write_text(json.dumps(item) + "\n")
    return path


def report(path: Path) -> dict:
    """Read a bounded submitted report."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, UnicodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def fixture(root: Path, variant: int) -> tuple[Path, dict]:
    """Write native mixed-storage bags with analytically authored ordering and clock roles."""
    offset = variant * 1000
    stream = [
        Native("c0", "timing", "/clock", CLOCK, 10, 100, 0, clock(100)),
        Native("imu0", "sensors", "/sensor", TEXT, 10, 100, 0, TS.types[TEXT]("unreliable beginning")),
        Native("cam0", "sensors", "/tf_static", TF, 11, 100, 0, tf("/base", "cam", 1, 0, 0, 0)),
        Native("base0", "sensors", "/tf_static", TF, 12, 100, 0, tf("world", "base", 0, 2, pi / 2, 0)),
        Native("tag0", "timing", "/tf_static", TF, 13, 100, 0, tf("base", "tag", 0, 2, 0, 0)),
        Native("imu1", "sensors", "/sensor", TEXT, 14, 100, 0, TS.types[TEXT]("unreliable same tick")),
        Native("cam1", "timing", "/sensor", TEXT, 14, 100, 0, TS.types[TEXT]("reliable same tick")),
        Native("c1", "timing", "/clock", CLOCK, 15, 130, 0, clock(130)),
        Native("d1", "timing", "/tf", TF, 16, 130, 0, tf("world", "base", 6, 0, 0, 120)),
        Native("cam2", "sensors", "/tf_static", TF, 17, 130, 0, tf("base", "cam", 2, 0, 0, 0)),
        Native("c2", "timing", "/clock", CLOCK, 18, 180, 0, clock(180)),
        Native("c3", "timing", "/clock", CLOCK, 20, 10, 1, clock(10)),
        Native("d2", "timing", "/tf", TF, 21, 10, 1, tf("world", "base", 4, 0, 0, 10)),
        Native("cam3", "sensors", "/tf_static", TF, 22, 10, 1, tf("base", "cam", 3, 0, 0, 0)),
        Native("bad", "timing", "/tf", TF, 24, 10, 1, tf("different", "cam", 5, 0, 0, 10)),
    ]
    formats = ((StoragePlugin.SQLITE3, StoragePlugin.MCAP) if variant == 0
               else (StoragePlugin.MCAP, StoragePlugin.SQLITE3))
    raw = {item.name: bytes(TS.serialize_cdr(item.payload, item.type)) for item in stream}
    expected = {item.name: {"source": item.source, "topic": item.topic, "type": item.type,
                            "record_ns": offset + item.record, "clock_ns": item.clock, "epoch": item.epoch,
                            "sha256": sha256(raw[item.name]).hexdigest()} for item in stream}
    publishers = [
        {"/sensor": {"reliability": "best_effort", "durability": "volatile", "depth": 1},
         "/tf_static": {"reliability": "reliable", "durability": "transient_local", "depth": 2}},
        {"/sensor": {"reliability": "reliable", "durability": "volatile", "depth": 1},
         "/tf": {"reliability": "reliable", "durability": "volatile", "depth": 1},
         "/tf_static": {"reliability": "best_effort", "durability": "transient_local", "depth": 1}},
    ]
    sources = []
    for source, plugin, offers, correction in zip(("sensors", "timing"), formats, publishers, (-5, 4), strict=True):
        bag = root / source
        with Writer(bag, version=9, storage_plugin=plugin) as writer:
            connections = {}
            for item in stream:
                if item.source != source:
                    continue
                if item.topic not in connections:
                    connections[item.topic] = writer.add_connection(item.topic, item.type, typestore=TS)
                writer.write(connections[item.topic], offset + item.record - correction, raw[item.name])
        sources.append({"id": source, "path": source, "offset_ns": correction, "publishers": offers})
    return dump(root / "request.json", {"sources": sources, "clock_source": "timing"}), expected


def sub(name: str, topic: str = "/tf_static", reliability: str = "reliable",
        durability: str = "transient_local") -> dict:
    """Make a subscription with explicit compatibility and history behavior."""
    return {"kind": "subscribe", "subscriber": name, "topic": topic,
            "reliability": reliability, "durability": durability}


def delivery(events: dict, op: int, subscriber: str, retained: bool, *names: str) -> list[dict]:
    """Expand directly authored expected event IDs into delivery records."""
    return [dict(events[name], operation=op, subscriber=subscriber, retained=retained) for name in names]


def index_probe(run: Run, work: Path, source: Path, events: dict) -> dict[str, bool]:
    """Check exact native wire identities and invalid authority rejection."""
    target = work / "index.json"
    expected = {"schema_version": 1, "events": list(events.values())}
    accurate = run("index", "--spec", source, "--output", target) == 0 and report(target) == expected
    invalid = json.loads(source.read_bytes())
    invalid["clock_source"] = "sensors"
    wrong = dump(work / "wrong-clock.json", invalid)
    before = target.read_bytes() if accurate else b""
    rejected = accurate and run("index", "--spec", wrong, "--output", target) not in (0, 124) and target.read_bytes() == before
    return {"mixed_bag_exact_bytes_and_epochs": accurate, "wrong_authority_is_atomic": rejected}


def replay_probe(run: Run, work: Path, source: Path, events: dict, base: int) -> dict[str, bool]:
    """Check partial-order compatibility, per-publisher caches, and seek restore."""
    ops = [sub("late"), sub("loose", reliability="best_effort"),
           sub("live", "/sensor", durability="volatile"), {"kind": "advance", "until_ns": base + 22},
           sub("reset"), {"kind": "seek", "record_ns": base + 14}, sub("seeked", reliability="best_effort"),
           {"kind": "advance", "until_ns": base + 15}]
    path = dump(work / "replay-script.json", {"start_ns": base + 18, "operations": ops})
    target = work / "trace.json"
    expected = (delivery(events, 0, "late", True, "base0", "cam2")
                + delivery(events, 1, "loose", True, "base0", "tag0", "cam2")
                + delivery(events, 6, "seeked", True, "cam0", "base0", "tag0")
                + delivery(events, 7, "live", False, "cam1"))
    cli = ("replay", "--spec", source, "--script", path, "--output", target)
    success = run(*cli) == 0
    actual = report(target) if success else {}
    before = target.read_bytes() if success and target.is_file() else b""
    dump(path, {"start_ns": base + 18, "operations": [sub("repeat"), sub("repeat")]})
    return {"compatible_cache_replay_and_seek": actual == {"schema_version": 1, "deliveries": expected,
                                                            "cursor_ns": base + 15},
            "duplicate_subscription_preserves_trace": bool(before) and run(*cli) not in (0, 124)
            and target.read_bytes() == before}


def pose_probe(run: Run, work: Path, source: Path, events: dict, base: int) -> dict[str, bool]:
    """Assert consumer-visible pose and expiry at specific script operations."""
    def lookup(name: str = "late", source: str = "/cam", target: str = "/world", age: int = 20) -> dict:
        """Construct a named consumer query at the current replay time."""
        return {"kind": "lookup", "subscriber": name, "source_frame": source, "target_frame": target,
                "max_age_ns": age}

    def advance(at: int) -> dict:
        """Use a known relative event boundary."""
        return {"kind": "advance", "until_ns": base + at}

    ops = [sub("late"), sub("late", "/tf", durability="volatile"), lookup(), advance(17), lookup(),
           advance(19), lookup(), lookup(source="/world", target="/cam"), {"kind": "seek", "record_ns": base + 17},
           lookup(), sub("after", reliability="best_effort"), lookup("after"),
           advance(22), lookup(), advance(24), lookup(age=0), advance(25), lookup()]
    path = dump(work / "pose-script.json", {"start_ns": base + 15, "operations": ops})
    target = work / "pose-report.json"
    run("qualify", "--spec", source, "--script", path, "--output", target)
    result = report(target)
    expected = [(2, "late", "cam", "world", (0, 3, pi / 2)), (4, "late", "cam", "world", (7, 0, 0)),
                (6, "late", "cam", "world", (0, 4, pi / 2)), (7, "late", "world", "cam", (-4, 0, -pi / 2)),
                (9, "late", "cam", "world", None), (11, "after", "cam", "world", (0, 3, pi / 2)),
                (13, "late", "cam", "world", None), (15, "late", "cam", "world", (7, 0, 0)),
                (17, "late", "cam", "world", None)]
    rows = result.get("lookups")
    if not isinstance(rows, list) or len(rows) != len(expected):
        return {"pose_after_calibration_and_expiry": False, "seek_and_clock_reset_clear_consumer": False,
                "observer_deliveries_preserve_raw_event": False}
    passes = []
    for observed, (op, name, source_frame, target_frame, pose) in zip(rows, expected, strict=True):
        if not isinstance(observed, dict):
            passes.append(False)
            continue
        wanted = {"operation": op, "subscriber": name, "source_frame": source_frame, "target_frame": target_frame,
                  "status": "ok" if pose is not None else "unavailable"}
        got = observed.get("target_from_source")
        correct = got is None if pose is None else (
            isinstance(got, list) and len(got) == 3 and all(
                type(a) in (float, int) and isclose(a, b, abs_tol=1e-8) for a, b in zip(got, pose, strict=True)))
        passes.append(correct and all(observed.get(key) == value for key, value in wanted.items()))
    expected_wire = (
        delivery(events, 0, "late", True, "cam0", "base0") + delivery(events, 3, "late", False, "d1")
        + delivery(events, 5, "late", False, "cam2") + delivery(events, 10, "after", True, "cam0", "base0", "tag0")
        + delivery(events, 12, "after", False, "cam2") + delivery(events, 12, "late", False, "cam2", "d2")
        + delivery(events, 14, "after", False, "cam3") + delivery(events, 14, "late", False, "cam3")
        + delivery(events, 16, "late", False, "bad"))
    return {"pose_after_calibration_and_expiry": all(passes[:4]),
            "seek_and_clock_reset_clear_consumer": all(passes[4:]),
            "observer_deliveries_preserve_raw_event": result.get("schema_version") == 1
            and result.get("cursor_ns") == base + 25 and result.get("deliveries") == expected_wire}


def verify(run: Run, work: Path, stage: int) -> dict[str, dict[str, bool]]:
    """Run the cumulative workflow and a storage-swapped time-shifted case."""
    source, events = fixture(work, 0)
    groups = {"index": index_probe(run, work, source, events)}
    if stage >= 2:
        groups["replay"] = replay_probe(run, work, source, events, 0)
    if stage >= 3:
        groups["poses"] = pose_probe(run, work, source, events, 0)
        alternate = work / "swap"
        alternate.mkdir(mode=0o777)
        alternate.chmod(0o1777)
        source, events = fixture(alternate, 3)
        groups["storage_swap"] = pose_probe(run, alternate, source, events, 3000)
    return groups
