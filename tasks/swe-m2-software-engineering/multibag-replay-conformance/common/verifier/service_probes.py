"""Verify durable reader receipts and snapshot isolation over mixed native storage."""

from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Callable
from uuid import uuid4

import numpy as np
from rosbags.rosbag2 import StoragePlugin, Writer

from probes import TEXT, TF, TS, tf

BASE = 1_755_555_912_345_678_900
MIB = 1024 * 1024
CAMERA = "sensor_msgs/msg/CompressedImage"


class Client:
    """Run every command in a fresh process with one shared service journal."""

    def __init__(self, run: Callable[..., int], home: Path) -> None:
        """Create a fixture folder whose output can be written by the candidate."""
        self.run, self.home = run, home
        home.mkdir(mode=0o755)
        self.out = home / "output"
        self.out.mkdir()
        self.out.chmod(0o1777)

    def command(self, packet: dict, *, invalid: bool = False, discard_reply: bool = False, capped: bool = False) -> dict | bool | None:
        """Issue one file-based request, optionally discarding an accepted response without reading it."""
        item = uuid4().hex
        request = self.home / f"request-{item}.json"
        request.write_text(json.dumps(packet))
        report = self.out / f"result-{item}.json"
        original = '{"retained":true}\n'
        if invalid:
            report.write_text(original)
            report.chmod(0o666)
        options = {"memory_mib": 256} if capped else {}
        code = self.run("serve", "--state", self.out / "state", "--request", request, "--output", report, **options)
        if discard_reply:
            return code == 0 and report.is_file() and not report.is_symlink()
        if not report.is_file() or report.is_symlink() or report.stat().st_size > 25 * MIB:
            return False if invalid else None
        if invalid:
            return code not in (0, 124, 125) and report.read_text() == original
        return json.loads(report.read_text()) if code == 0 else None


def event(identifier: str, operation: str, **fields: object) -> dict:
    """Build an immutable request envelope with a fixture-chosen identity."""
    return {"request_id": identifier, "operation": operation, **fields}


def record(stamp: int, topic: str, kind: str, data: object) -> tuple[int, str, str, bytes]:
    """Encode a small native CDR payload at a Unix-sized timestamp."""
    return BASE + stamp, topic, kind, bytes(TS.serialize_cdr(data, kind))


def shard(client: Client, tag: str, stream: str, boot: str, storage: StoragePlugin,
          rows: list[tuple[int, str, str, bytes]], repeats: list[dict] | None = None) -> dict:
    """Write an authored mixed-format split and return only its public manifest."""
    with Writer(client.home / tag, version=9, storage_plugin=storage) as writer:
        connections = {}
        for tick, topic, kind, raw in rows:
            if topic not in connections:
                connections[topic] = writer.add_connection(topic, kind, typestore=TS)
            writer.write(connections[topic], tick, raw)
    return {"id": tag, "path": tag, "stream": stream, "boot": boot,
            "latched_topics": sorted({topic for _, topic, _, _ in rows if topic == "/tf_static"}), "repeats": repeats or []}


def wire(spec: dict, ordinal: int, row: tuple[int, str, str, bytes], late: bool = False) -> dict:
    """Compute the expected published wire identity and original native bytes."""
    timestamp, topic, kind, raw = row
    return {"shard": spec["id"], "ordinal": ordinal, "stream": spec["stream"], "boot": spec["boot"],
            "topic": topic, "type": kind, "stamp_ns": timestamp, "cdr_b64": b64encode(raw).decode(),
            "sha256": sha256(raw).hexdigest(), "latched": late}


def matches(reply: dict | bool | None, reader: str, wanted: list[dict]) -> bool:
    """Check exact publication bytes and a usable receipt identity."""
    return isinstance(reply, dict) and reply.get("reader") == reader and reply.get("events") == wanted and (
        not reply.get("done") and isinstance(reply.get("batch"), str) and bool(reply["batch"]) if wanted else
        reply.get("done") is True and reply.get("batch") is None)


def snapshot(run: Callable[..., int], root: Path) -> tuple[bool, bool, bool]:
    """Prove old readers survive real file retirement, boot changes, and unread accepted responses."""
    client = Client(run, root)
    call = client.command
    position = TS.types[TEXT]("same original sensor sample")
    old_rows = [record(100, "/tf_static", TF, tf("map", "cam", 1, 0, 0, 5)),
                record(105, "/sensor", TEXT, position),
                record(106, "/tf_static", TF, tf("map", "cam", 2, 0, 0, 7)),
                record(112, "/sensor", TEXT, position)]
    auxiliary = [record(103, "/tf_static", TF, tf("map", "imu", 3, 0, 0, 8)),
                 record(125, "/sensor", TEXT, position)]
    original = shard(client, "old-primary", "base", "run-1", StoragePlugin.SQLITE3, old_rows)
    other = shard(client, "other-lidar", "lidar", "run-2", StoragePlugin.MCAP, auxiliary)
    attach = event("initial", "attach", base_generation=0, shards=[original, other])
    if call(attach) != {"generation": 1, "events": 6}:
        return False, False, False
    topics = ["/tf_static", "/sensor"]
    pinned = event("old-open", "open", reader="old", generation=None, topics=topics, begin_ns=BASE+107, end_ns=BASE+160)
    if call(pinned) != {"reader": "old", "generation": 1}:
        return False, False, False
    first = event("old-first", "poll", reader="old", max_events=1, max_bytes=2048)
    if not call(first, discard_reply=True):
        return False, False, False
    identical = (BASE + 109, *old_rows[2][1:])
    second_rows = [identical, record(113, "/sensor", TEXT, position), record(114, "/sensor", TEXT, position)]
    new_rows = [record(121, "/diag", TEXT, TS.types[TEXT]("fresh boot")),
                record(137, "/tf_static", TF, tf("map", "cam", 5, 0, 0, 11)),
                record(142, "/sensor", TEXT, position)]
    second = shard(client, "secondary", "base", "run-1", StoragePlugin.MCAP, second_rows,
                   repeats=[{"ordinal": 0, "from_shard": original["id"], "from_ordinal": 2}])
    replacement = shard(client, "new-primary", "base", "run-3", StoragePlugin.SQLITE3, new_rows)
    combined = event("after-lost", "attach", base_generation=1, shards=[second, replacement])
    if call(combined) != {"generation": 2, "events": 11}:
        return False, False, False
    for entry in (original, other, second, replacement):
        shutil.rmtree(root / entry["path"])
    duplicate = call(event("poll-changed-limit", "poll", reader="old", max_events=9, max_bytes=2048))
    head = call(first)
    keep_first = matches(duplicate, "old", [wire(other, 0, auxiliary[0], True)]) and head == duplicate
    if not keep_first:
        return False, False, False
    packet = event("ack-first", "ack", reader="old", batch=head["batch"])
    if not call(packet, discard_reply=True):
        return False, False, False
    tail = call(event("after-ack-loss", "poll", reader="old", max_events=8, max_bytes=2048))
    old_correct = matches(tail, "old", [wire(original, 2, old_rows[2], True), wire(original, 3, old_rows[3]),
                                        wire(other, 1, auxiliary[1])])
    old_correct &= call(packet) == {"reader": "old", "batch": head["batch"], "acknowledged": True}
    old_correct &= call(event("wrong-ack", "ack", reader="old", batch=head["batch"]), invalid=True) is True
    if old_correct:
        old_correct &= bool(call(event("ack-end", "ack", reader="old", batch=tail["batch"])))
        old_correct &= matches(call(event("old-done", "poll", reader="old", max_events=1, max_bytes=2048)), "old", [])

    new = event("new-open", "open", reader="new", generation=None, topics=topics, begin_ns=BASE+126, end_ns=BASE+151)
    boot_correct = call(new) == {"reader": "new", "generation": 2}
    new_reply = call(event("new-poll", "poll", reader="new", max_events=5, max_bytes=2048))
    boot_correct &= matches(new_reply, "new", [wire(other, 0, auxiliary[0], True),
                                                wire(replacement, 1, new_rows[1]), wire(replacement, 2, new_rows[2])])
    no_duplicate = event("all-open", "open", reader="all", generation=2, topics=topics, begin_ns=BASE+107, end_ns=BASE+120)
    repeat_correct = call(no_duplicate) == {"reader": "all", "generation": 2}
    reply = call(event("all-poll", "poll", reader="all", max_events=12, max_bytes=2048))
    repeat_correct &= matches(reply, "all", [wire(other, 0, auxiliary[0], True), wire(original, 2, old_rows[2], True),
                                             wire(original, 3, old_rows[3]), wire(second, 1, second_rows[1]),
                                             wire(second, 2, second_rows[2])])
    return bool(old_correct), bool(boot_correct), bool(repeat_correct)


def competing(run: Callable[..., int], root: Path) -> bool:
    """Test compare-and-swap across real simultaneous writers and a past response."""
    client = Client(run, root)
    wire0 = record(21, "/diag", TEXT, TS.types[TEXT]("sealed status"))
    left = shard(client, "left", "L", "b", StoragePlugin.MCAP, [wire0])
    right = shard(client, "right", "R", "b", StoragePlugin.SQLITE3, [wire0])
    events = [event(key, "attach", base_generation=0, shards=[item]) for key, item in (("left", left), ("right", right))]
    with ThreadPoolExecutor(max_workers=2) as executors:
        outcomes = list(executors.map(client.command, events))
    chosen = {"generation": 1, "events": 1}
    if outcomes.count(chosen) != 1 or outcomes.count(None) != 1:
        return False
    winner = outcomes.index(chosen)
    bad = deepcopy(events[winner])
    bad["base_generation"] = 1
    loser = 1 - winner
    selected = [left, right][loser]
    if not client.command(bad, invalid=True):
        return False
    if client.command(event("next-gen", "attach", base_generation=1, shards=[selected])) != {"generation": 2, "events": 2}:
        return False
    if client.command(events[winner]) != chosen:
        return False
    selected = event("tied-open", "open", reader="ties", generation=2, topics=["/diag"],
                     begin_ns=BASE+21, end_ns=BASE+22)
    if client.command(selected) != {"reader": "ties", "generation": 2}:
        return False
    delivered = client.command(event("tied-poll", "poll", reader="ties", max_events=4, max_bytes=2048))
    return matches(delivered, "ties", [wire(left, 0, wire0), wire(right, 0, wire0)])


def conflicting_repeat(run: Callable[..., int], root: Path) -> bool:
    """Reject changed data claiming to be an old latch and preserve the generation."""
    client = Client(run, root)
    start = record(22, "/tf_static", TF, tf("map", "cam", 1, 0, 0, 2))
    lie = record(24, "/tf_static", TF, tf("map", "cam", 3, 0, 0, 2))
    a = shard(client, "valid", "robot", "boot", StoragePlugin.MCAP, [start])
    b = shard(client, "invalid", "robot", "boot", StoragePlugin.SQLITE3, [lie],
              repeats=[{"ordinal": 0, "from_shard": "valid", "from_ordinal": 0}])
    first = event("first", "attach", base_generation=0, shards=[a])
    second = event("second", "attach", base_generation=1, shards=[b])
    if client.command(first) != {"generation": 1, "events": 1} or not client.command(second, invalid=True):
        return False
    if client.command(event("read", "open", reader="read", generation=None, topics=["/tf_static"],
                            begin_ns=BASE+21, end_ns=BASE+99)) != {"reader": "read", "generation": 1}:
        return False
    result = client.command(event("poll", "poll", reader="read", max_events=2, max_bytes=4096))
    return matches(result, "read", [wire(a, 0, start)])


def bulk(run: Callable[..., int], root: Path) -> bool:
    """Serve a native camera recording larger than the service's entire memory cap."""
    client = Client(run, root)
    count = 272
    header = TS.types["std_msgs/msg/Header"](TS.types["builtin_interfaces/msg/Time"](9, 3), "front")
    frame = TS.types[CAMERA](header, "compressed", np.zeros(MIB, dtype=np.uint8))
    payload = bytes(TS.serialize_cdr(frame, CAMERA))
    bag = {"id": "camera", "path": "camera", "stream": "video", "boot": "first", "latched_topics": [], "repeats": []}
    with Writer(root / "camera", version=9, storage_plugin=StoragePlugin.SQLITE3) as writer:
        connection = writer.add_connection("/camera", CAMERA, typestore=TS)
        for index in range(count):
            writer.write(connection, BASE + index, payload)
    if client.command(event("load", "attach", base_generation=0, shards=[bag]), capped=True) != {"generation": 1, "events": count}:
        return False
    shutil.rmtree(root / "camera")
    begin = count - 3
    if client.command(event("seek", "open", reader="clip", generation=1, topics=["/camera"], begin_ns=BASE+begin,
                            end_ns=BASE+count), capped=True) != {"reader": "clip", "generation": 1}:
        return False
    too_small = event("underflow", "poll", reader="clip", max_events=4, max_bytes=MIB)
    if client.command(too_small, invalid=True, capped=True) is not True:
        return False
    result = client.command(event("read-bulk", "poll", reader="clip", max_events=4, max_bytes=2 * len(payload)), capped=True)
    rows = [wire(bag, i, (BASE+i, "/camera", CAMERA, payload)) for i in range(begin, begin+2)]
    return matches(result, "clip", rows)


def service_checks(run: Callable[..., int], root: Path) -> dict[str, bool]:
    """Grade transactional semantics and bounded native ingestion separately."""
    evidence = {}
    try:
        pinned, epochs, repeats = snapshot(run, root / "sealed-series")
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError):
        pinned, epochs, repeats = False, False, False
    evidence.update(pinned_history_and_restart=pinned, boot_latches_survive_only_where_live=epochs, explicit_repeats_only=repeats)
    for label, case in (("concurrent_attach_atomic", competing), ("conflicting_repeat_rollback", conflicting_repeat),
                        ("native_shard_larger_than_memory", bulk)):
        try:
            evidence[label] = bool(case(run, root / label))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError):
            evidence[label] = False
    return evidence
