"""Deliver durable recording batches through native localhost ROS 2 publishers."""

from base64 import b64decode
from contextlib import closing
import fcntl
import json
from pathlib import Path
import re
import sqlite3
import sys
from time import monotonic, sleep
from uuid import uuid4

from .native import text
from .service import SCHEMA, apply, current, encoded, nonnegative, open_reader, poll, strings


LIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS live_readers (
 reader TEXT PRIMARY KEY, generation INTEGER NOT NULL, epoch INTEGER NOT NULL, prefix TEXT NOT NULL,
 selected TEXT NOT NULL, cursor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS live_instance (slot INTEGER PRIMARY KEY CHECK(slot=1), identity TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS live_receipts (id TEXT PRIMARY KEY, contents TEXT NOT NULL, reply TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS live_boots (
 reader TEXT NOT NULL, stream TEXT NOT NULL, boot TEXT NOT NULL, PRIMARY KEY(reader, stream));
CREATE TABLE IF NOT EXISTS live_latches (
 reader TEXT NOT NULL, stream TEXT NOT NULL, topic TEXT NOT NULL, shard TEXT NOT NULL, ordinal INTEGER NOT NULL,
 PRIMARY KEY(reader, stream, topic));
"""


DURABLE = {"open", "seek", "prepare", "ack"}
TOPIC = re.compile(r"(?:/[A-Za-z_][A-Za-z0-9_]*)+\Z")


def reader_name(value):
    """Accept an opaque short ID and encode it independently of ROS naming rules."""
    name = text(value)
    if len(name.encode()) > 32:
        raise ValueError("Replay reader identity exceeds 32 UTF-8 bytes")
    return name


def location(instance, reader, generation, epoch):
    """Give each seek a DDS namespace distinct from historical readers or seeks."""
    return {"reader": reader, "generation": generation, "epoch": epoch,
            "prefix": f"/bag_replay/server_{instance}/r_{reader.encode().hex()}/s_{epoch}"}


def coordinates(row):
    """Export seek coordinates without leaking the underlying index key."""
    return {key: row[key] for key in ("reader", "generation", "epoch", "prefix")}


class Archive:
    """Manage durable command receipts and the acknowledged ROS latch snapshot."""

    def __init__(self, state):
        self.db = sqlite3.connect(state / "recordings.db", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA temp_store=FILE")
        self.db.executescript(SCHEMA + LIVE_SCHEMA)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO live_instance VALUES (1,?)", (uuid4().hex,))
        self.identity = self.db.execute("SELECT identity FROM live_instance WHERE slot=1").fetchone()[0]

    def read(self, identity):
        row = self.db.execute("SELECT * FROM live_readers WHERE reader=?", (identity,)).fetchone()
        if row is None:
            raise ValueError("Unknown live replay reader")
        return row

    def cursor(self, row):
        return self.db.execute("SELECT * FROM readers WHERE id=?", (row["cursor"],)).fetchone()

    def wire(self, shard, ordinal):
        """Read one native retained record using immutable recording identity."""
        row = self.db.execute("SELECT * FROM events WHERE shard=? AND ordinal=?", (shard, ordinal)).fetchone()
        if row is None:
            raise ValueError("Missing sealed recording event")
        return row

    def latches(self):
        """Restore no unacknowledged emit attempts after starting a new process."""
        return self.db.execute("""SELECT l.reader,l.shard,l.ordinal FROM live_latches l
                           JOIN live_readers r USING(reader) ORDER BY l.reader,l.stream,l.topic""")

    def attach_reader(self, packet, identity, prior):
        """Build a private history cursor over the entire archive, including unselected boots."""
        if prior is None:
            selected = strings(packet["topics"])
            wanted = packet["generation"]
            generation = current(self.db)[0] if wanted is None else nonnegative(wanted)
            epoch = 0
        else:
            selected = json.loads(prior["selected"])
            generation = prior["generation"]
            epoch = prior["epoch"] + 1
        if not selected or any(not TOPIC.fullmatch(topic) for topic in selected):
            raise ValueError("Select valid absolute ROS topic names")
        reported = self.db.execute("SELECT DISTINCT topic,type FROM events WHERE generation<=?", (generation,))
        types = {}
        for row in reported:
            types.setdefault(row["topic"], set()).add(row["type"])
        if any(len(types.get(topic, ())) != 1 for topic in selected):
            raise ValueError("Selected topic missing or its native type varies within the snapshot")
        from rosidl_runtime_py.utilities import get_message

        for topic in selected:
            get_message(next(iter(types[topic])))
        internal = "__dds_live__" + uuid4().hex
        open_reader(self.db, {"reader": internal, "generation": generation, "topics": list(types),
                              "begin_ns": packet["begin_ns"], "end_ns": packet["end_ns"]})
        region = location(self.identity, identity, generation, epoch)
        if prior is None:
            self.db.execute("INSERT INTO live_readers VALUES (?,?,?,?,?,?)",
                            (identity, generation, epoch, region["prefix"], encoded(selected), internal))
        else:
            self.db.execute("UPDATE live_readers SET epoch=?,prefix=?,cursor=? WHERE reader=?",
                            (epoch, region["prefix"], internal, identity))
            self.db.execute("DELETE FROM readers WHERE id=?", (prior["cursor"],))
            self.db.execute("DELETE FROM prelude WHERE reader=?", (prior["cursor"],))
            self.db.execute("DELETE FROM live_latches WHERE reader=?", (identity,))
            self.db.execute("DELETE FROM live_boots WHERE reader=?", (identity,))
        return region

    def update_latches(self, reader, events):
        """Commit active boot state and exact retained source IDs, independent of writer delivery."""
        selected = set(json.loads(reader["selected"]))
        identity = reader["reader"]
        for event in events:
            stream, boot = event["stream"], event["boot"]
            previous = self.db.execute("SELECT boot FROM live_boots WHERE reader=? AND stream=?", (identity, stream)).fetchone()
            if previous is None or previous["boot"] != boot:
                self.db.execute("DELETE FROM live_latches WHERE reader=? AND stream=?", (identity, stream))
                self.db.execute("INSERT OR REPLACE INTO live_boots VALUES (?,?,?)", (identity, stream, boot))
            source = self.wire(event["shard"], event["ordinal"])
            if source["latched"] and source["topic"] in selected:
                self.db.execute("INSERT OR REPLACE INTO live_latches VALUES (?,?,?,?,?)",
                                (identity, stream, source["topic"], source["shard"], source["ordinal"]))

    def pending(self, reader, epoch, batch):
        """Require the current seek and a still-unacknowledged prepared batch."""
        current_row = self.cursor(reader)
        if nonnegative(epoch) != reader["epoch"] or text(batch) != current_row["batch"]:
            raise ValueError("Unknown or superseded live batch")
        return json.loads(current_row["pending"])

    def apply(self, packet):
        operation, identity = packet["operation"], reader_name(packet["reader"])
        if operation == "open":
            return self.attach_reader(packet, identity, None)
        reader = self.read(identity)
        fields = coordinates(reader)
        if operation == "seek":
            return self.attach_reader(packet, identity, reader)
        if operation == "prepare":
            existing = self.cursor(reader)
            prepared = poll(self.db, packet, existing)
            selected = set(json.loads(reader["selected"]))
            visible = [{key: value for key, value in item.items() if key != "cdr_b64"}
                       for item in prepared["events"] if item["topic"] in selected]
            return fields | {"batch": prepared["batch"], "done": prepared["done"],
                             "scanned": len(prepared["events"]), "events": visible}
        prepared = self.pending(reader, packet["epoch"], packet["batch"])
        self.update_latches(reader, prepared["events"])
        apply(self.db, {"operation": "ack", "reader": reader["cursor"], "batch": packet["batch"]}, Path("."))
        return {"reader": identity, "epoch": reader["epoch"], "batch": packet["batch"], "acknowledged": True}

    def durable(self, packet):
        """Make accepted replay changes visible before their replies may be written."""
        key = text(packet["request_id"])
        fingerprint = encoded(packet)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            previous = self.db.execute("SELECT contents,reply FROM live_receipts WHERE id=?", (key,)).fetchone()
            if previous is not None:
                if previous["contents"] != fingerprint:
                    raise ValueError("Changed live request replay")
                return json.loads(previous["reply"]), False
            reply = self.apply(packet)
            self.db.execute("INSERT INTO live_receipts VALUES (?,?,?)", (key, fingerprint, encoded(reply)))
        return reply, True


class Transport:
    """Publish native serialized CDR and retire transient-local writers on boot or seek."""

    def __init__(self, archive):
        import rclpy
        from rclpy.duration import Duration
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
        from rosidl_runtime_py.utilities import get_message

        self.rclpy = rclpy
        self.archive = archive
        self.get_message = get_message
        self.duration = Duration
        self.profiles = {latched: QoSProfile(depth=1 if latched else 128, reliability=ReliabilityPolicy.RELIABLE,
                                           durability=DurabilityPolicy.TRANSIENT_LOCAL if latched else DurabilityPolicy.VOLATILE)
                         for latched in (False, True)}
        self.boots = {}
        self.writers = {}
        rclpy.init()
        self.node = rclpy.create_node("multibag_worker_" + uuid4().hex[:12])

    def close(self):
        self.node.destroy_node()
        self.rclpy.try_shutdown()

    def retire(self, reader, stream=None):
        """Remove DDS history belonging to a superseded reader or stream incarnation."""
        for key, writer in tuple(self.writers.items()):
            if key[0] == reader and (stream is None or key[1] == stream):
                self.node.destroy_publisher(writer)
                del self.writers[key]
        for key in tuple(self.boots):
            if key[0] == reader and (stream is None or key[1] == stream):
                del self.boots[key]

    def writer(self, reader, source):
        """Offer a reliable publisher with exactly the recorded durability."""
        latched = bool(source["latched"])
        key = reader["reader"], source["stream"], source["topic"], latched
        if key not in self.writers:
            msg = self.get_message(source["type"])
            self.writers[key] = self.node.create_publisher(msg, reader["prefix"] + source["topic"], self.profiles[latched])
        return self.writers[key]

    def publish(self, reader, source, payload, wait_for, deadline):
        identity = reader["reader"]
        key = identity, source["stream"]
        if self.boots.get(key) != source["boot"]:
            self.retire(*key)
            self.boots[key] = source["boot"]
        if source["topic"] not in json.loads(reader["selected"]):
            return 0
        writer = self.writer(reader, source)
        if source["topic"] in wait_for:
            while writer.get_subscription_count() == 0:
                if monotonic() >= deadline:
                    raise ValueError("Timed out waiting for a matching DDS subscriber")
                sleep(.012)
        writer.publish(payload)
        if source["topic"] in wait_for:
            remaining = max(0., deadline - monotonic())
            if not writer.wait_for_all_acked(self.duration(seconds=remaining)):
                raise ValueError("Timed out completing reliable DDS publication")
        return 1

    def restore(self):
        """Reoffer acknowledged durable history without replaying regular messages."""
        for stored in self.archive.latches():
            reader = self.archive.read(stored["reader"])
            source = self.archive.wire(stored["shard"], stored["ordinal"])
            self.publish(reader, source, source["payload"], (), 0.)

    def emit(self, packet):
        """Replay a pending batch at least once per successful emission attempt."""
        reader = self.archive.read(reader_name(packet["reader"]))
        prepared = self.archive.pending(reader, packet["epoch"], packet["batch"])
        waits = set(strings(packet.get("wait_for_subscribers", [])))
        declared = set(json.loads(reader["selected"]))
        if not waits <= declared & {item["topic"] for item in prepared["events"]}:
            raise ValueError("Subscriber waits must target selected messages in the batch")
        published = 0
        deadline = monotonic() + 3.
        for item in prepared["events"]:
            source = self.archive.wire(item["shard"], item["ordinal"])
            published += self.publish(reader, source, b64decode(item["cdr_b64"], validate=True), waits, deadline)
        return {"reader": reader["reader"], "epoch": reader["epoch"], "batch": packet["batch"], "published": published}


def live(state: Path):
    """Serve a durable NDJSON control channel alongside a native Jazzy ROS node."""
    state.mkdir(parents=True, exist_ok=True)
    with (state / "live.lock").open("ab") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        archive = Archive(state)
        with closing(archive.db):
            transport = Transport(archive)
            try:
                transport.restore()
                for line in sys.stdin:
                    try:
                        packet = json.loads(line)
                        action = packet["operation"]
                        if action in DURABLE:
                            reply, accepted = archive.durable(packet)
                            if accepted and action == "seek":
                                transport.retire(packet["reader"])
                        elif action == "emit":
                            reply = transport.emit(packet)
                        else:
                            raise ValueError("Unknown live command")
                    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError, ImportError, sqlite3.Error) as error:
                        reply = {"error": str(error)[:240]}
                    print(encoded(reply), flush=True)
            finally:
                transport.close()


def receipt(state: Path, request_id: str):
    """Read a committed receipt without acquiring the live writer lease or sending ROS messages."""
    database = state.resolve() / "recordings.db"
    reply = None
    if database.is_file():
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)) as view:
            table = view.execute("SELECT 1 FROM sqlite_schema WHERE name='live_receipts'").fetchone()
            if table is not None:
                received = view.execute("SELECT reply FROM live_receipts WHERE id=?", (text(request_id),)).fetchone()
                if received is not None:
                    reply = json.loads(received[0])
    print(encoded(reply), flush=True)
