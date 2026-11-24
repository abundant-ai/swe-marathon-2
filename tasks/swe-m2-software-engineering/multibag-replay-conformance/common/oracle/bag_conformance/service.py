"""Serve native recording generations and durable replay cursors."""

from base64 import b64encode
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from rosbags.rosbag2 import Reader

from .native import Json, integer, load, save, text

MIB = 1024 * 1024
SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (number INTEGER PRIMARY KEY, events INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, input TEXT NOT NULL, output TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS streams (stream TEXT NOT NULL, boot TEXT NOT NULL, number INTEGER NOT NULL,
 PRIMARY KEY(stream, boot), UNIQUE(stream, number));
CREATE TABLE IF NOT EXISTS shards (id TEXT PRIMARY KEY, stream TEXT NOT NULL, boot TEXT NOT NULL, generation INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS events (
 shard TEXT NOT NULL, ordinal INTEGER NOT NULL, stamp INTEGER NOT NULL, generation INTEGER NOT NULL,
 stream TEXT NOT NULL, boot TEXT NOT NULL, topic TEXT NOT NULL, type TEXT NOT NULL,
 digest TEXT NOT NULL, latched INTEGER NOT NULL, payload BLOB NOT NULL,
 PRIMARY KEY(shard, ordinal));
CREATE INDEX IF NOT EXISTS events_timeline ON events(stamp, shard, ordinal, generation, topic);
CREATE INDEX IF NOT EXISTS stream_boot_events ON events(stream, boot, stamp, shard, ordinal);
CREATE TABLE IF NOT EXISTS readers (
 id TEXT PRIMARY KEY, generation INTEGER NOT NULL, topics TEXT NOT NULL, begin INTEGER NOT NULL, ending INTEGER NOT NULL,
 latch_offset INTEGER NOT NULL DEFAULT 0, stamp INTEGER NOT NULL DEFAULT -1,
 shard TEXT NOT NULL DEFAULT '', ordinal INTEGER NOT NULL DEFAULT -1,
 batch TEXT, pending TEXT, next_cursor TEXT);
CREATE TABLE IF NOT EXISTS prelude (
 reader TEXT NOT NULL, position INTEGER NOT NULL, shard TEXT NOT NULL, ordinal INTEGER NOT NULL,
 PRIMARY KEY(reader, position));
"""


def encoded(value: object) -> str:
    """Canonicalize a JSON value for durable idempotency and reply storage."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def nonnegative(value: object) -> int:
    """Read one native timestamp, generation, or ordinal."""
    number = integer(value)
    if not 0 <= number < 2**63:
        raise ValueError("Value is outside the integer storage domain")
    return number


def array(value: object) -> list:
    """Validate a JSON-array field without accepting iterable substitutes."""
    if not isinstance(value, list):
        raise ValueError("Expected an array")
    return value


def strings(value: object) -> list[str]:
    """Read a list of unique nonempty identifiers in submitted order."""
    words = [text(x) for x in array(value)]
    if len(words) != len(set(words)):
        raise ValueError("Duplicate string in selector")
    return words


def current(db: sqlite3.Connection) -> tuple[int, int]:
    """Read the last committed generation and cumulative event count."""
    row = db.execute("SELECT number, events FROM generations ORDER BY number DESC LIMIT 1").fetchone()
    return tuple(row) if row is not None else (0, 0)


def register_boot(db: sqlite3.Connection, stream: str, boot: str) -> None:
    """Record a boot or verify that its stream still has authority to append."""
    previous = db.execute("SELECT boot, number FROM streams WHERE stream=? ORDER BY number DESC LIMIT 1", (stream,)).fetchone()
    if previous is None or previous["boot"] != boot:
        if db.execute("SELECT 1 FROM streams WHERE stream=? AND boot=?", (stream, boot)).fetchone():
            raise ValueError("Cannot append an already retired boot")
        db.execute("INSERT INTO streams VALUES (?,?,?)", (stream, boot, 0 if previous is None else previous["number"] + 1))


def load_shard(db: sqlite3.Connection, definition: Json, parent: Path, generation: int) -> tuple[str, int]:
    """Index one native split without collecting all wire payloads in memory."""
    shard, stream, boot = map(text, (definition["id"], definition["stream"], definition["boot"]))
    filename = Path(text(definition["path"]))
    if filename.is_absolute() or not (parent / filename).resolve().is_relative_to(parent.resolve()):
        raise ValueError("Bag paths must be under the supplied recording directory")
    latched = set(strings(definition["latched_topics"]))
    repeats = {}
    for item in array(definition["repeats"]):
        ordinal = nonnegative(item["ordinal"])
        if ordinal in repeats:
            raise ValueError("Repeated native ordinal")
        repeats[ordinal] = text(item["from_shard"]), nonnegative(item["from_ordinal"])

    register_boot(db, stream, boot)
    db.execute("INSERT INTO shards VALUES (?,?,?,?)", (shard, stream, boot, generation))
    created = 0
    with Reader(parent / filename) as reader:
        if not latched <= {connection.topic for connection in reader.connections}:
            raise ValueError("Undeclared latched topic")
        for ordinal, (connection, stamp, raw) in enumerate(reader.messages()):
            stamp = nonnegative(stamp)
            topic, kind = connection.topic, connection.msgtype
            digest = sha256(raw).hexdigest()
            if ordinal in repeats:
                source, source_ordinal = repeats.pop(ordinal)
                copy = db.execute("""SELECT stream,boot,topic,type,digest,payload,latched FROM events
                                    WHERE shard=? AND ordinal=? AND generation < ?""",
                                  (source, source_ordinal, generation)).fetchone()
                identity = (stream, boot, topic, kind, digest, raw, 1)
                if topic not in latched or copy is None or tuple(copy) != identity:
                    raise ValueError("Invalid transient-local repeat")
                continue
            if len(raw) > 16 * MIB:
                raise ValueError("Native payload exceeds the declared bound")
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (shard, ordinal, stamp, generation, stream, boot, topic, kind, digest, topic in latched, raw))
            created += 1
    if repeats:
        raise ValueError("Missing native replay source")
    return stream, created


def check_intervals(db: sqlite3.Connection, stream: str) -> None:
    """Reject appended events that invert a stream's commissioned boot order."""
    boots = db.execute("SELECT boot FROM streams WHERE stream=? ORDER BY number", (stream,))
    latest = None
    for row in boots:
        identity = stream, row["boot"]
        first = db.execute("""SELECT stamp,shard,ordinal FROM events WHERE stream=? AND boot=?
                              ORDER BY stamp,shard,ordinal LIMIT 1""", identity).fetchone()
        if first is None:
            continue
        last = db.execute("""SELECT stamp,shard,ordinal FROM events WHERE stream=? AND boot=?
                             ORDER BY stamp DESC,shard DESC,ordinal DESC LIMIT 1""", identity).fetchone()
        if latest is not None and tuple(first) <= latest:
            raise ValueError("Publication order overlaps a retired boot")
        latest = tuple(last)


def attach(db: sqlite3.Connection, packet: Json, parent: Path) -> Json:
    """Advance the current generation by committing all sealed native splits."""
    previous, total = current(db)
    if nonnegative(packet["base_generation"]) != previous:
        raise ValueError("Stale generation")
    entries = array(packet["shards"])
    if not entries:
        raise ValueError("Expected at least one shard")
    affected = set()
    for item in entries:
        stream, new = load_shard(db, item, parent, previous + 1)
        total += new
        affected.add(stream)
    for stream in affected:
        check_intervals(db, stream)
    generation = previous + 1
    db.execute("INSERT INTO generations VALUES (?,?)", (generation, total))
    return {"generation": generation, "events": total}


def open_reader(db: sqlite3.Connection, packet: Json) -> Json:
    """Pin an immutable generation and materialize only its latch prelude IDs."""
    reader = text(packet["reader"])
    wanted = packet["generation"]
    generation = current(db)[0] if wanted is None else nonnegative(wanted)
    if not db.execute("SELECT 1 FROM generations WHERE number=?", (generation,)).fetchone():
        raise ValueError("Unknown recording generation")
    begin, end = (nonnegative(packet[k]) for k in ("begin_ns", "end_ns"))
    topics = encoded(strings(packet["topics"]))
    if end <= begin:
        raise ValueError("Invalid replay range")
    db.execute("INSERT INTO readers(id,generation,topics,begin,ending) VALUES (?,?,?,?,?)",
               (reader, generation, topics, begin, end))
    db.execute("""INSERT INTO prelude(reader,position,shard,ordinal)
        WITH last_boot AS (
          SELECT stream, boot, row_number() OVER(PARTITION BY stream ORDER BY stamp DESC,shard DESC,ordinal DESC) AS r
          FROM events WHERE generation <= ? AND stamp < ?
        ), cached AS (
          SELECT e.stamp,e.shard,e.ordinal,
                 row_number() OVER(PARTITION BY e.stream,e.topic ORDER BY e.stamp DESC,e.shard DESC,e.ordinal DESC) AS r
          FROM events e JOIN last_boot b ON b.stream=e.stream AND b.boot=e.boot AND b.r=1
          WHERE e.generation <= ? AND e.stamp < ? AND e.latched AND e.topic IN (SELECT value FROM json_each(?))
        ) SELECT ?,row_number() OVER(ORDER BY stamp,shard,ordinal)-1,shard,ordinal FROM cached WHERE r=1""",
        (generation, begin, generation, begin, topics, reader))
    return {"reader": reader, "generation": generation}


def available(db: sqlite3.Connection, reader: sqlite3.Row) -> Iterator[tuple[sqlite3.Row, bool]]:
    """Yield pending prelude or ordered event identities, without raw payloads."""
    for row in db.execute("""SELECT e.shard,e.ordinal,e.stamp,e.stream,e.boot,e.topic,e.type,e.digest,length(e.payload) AS size
        FROM prelude p JOIN events e ON e.shard=p.shard AND e.ordinal=p.ordinal
        WHERE p.reader=? AND p.position >= ? ORDER BY p.position""", (reader["id"], reader["latch_offset"])):
        yield row, True
    for row in db.execute("""SELECT shard,ordinal,stamp,stream,boot,topic,type,digest,length(payload) AS size FROM events
        WHERE stamp >= ? AND stamp < ? AND (stamp,shard,ordinal) > (?,?,?) AND generation <= ?
        AND topic IN (SELECT value FROM json_each(?)) ORDER BY stamp,shard,ordinal""",
        (reader["begin"], reader["ending"], reader["stamp"], reader["shard"], reader["ordinal"],
         reader["generation"], reader["topics"])):
        yield row, False


def poll(db: sqlite3.Connection, packet: Json, reader: sqlite3.Row) -> Json:
    """Return a new bounded batch or the one the reader still needs to acknowledge."""
    count, budget = (nonnegative(packet[name]) for name in ("max_events", "max_bytes"))
    if not (1 <= count <= 1024 and 1 <= budget <= 16 * MIB):
        raise ValueError("Invalid batch limits")
    if reader["pending"] is not None:
        return json.loads(reader["pending"])
    result = []
    remaining = budget
    latch_offset = reader["latch_offset"]
    cursor = [reader["stamp"], reader["shard"], reader["ordinal"]]
    for row, prelude in available(db, reader):
        if row["size"] > remaining:
            if not result:
                raise ValueError("First payload exceeds the byte budget")
            break
        raw, = db.execute("SELECT payload FROM events WHERE shard=? AND ordinal=?", (row["shard"], row["ordinal"])).fetchone()
        result.append({name: row[name] for name in ("shard", "ordinal", "stream", "boot", "topic", "type")} |
                      {"stamp_ns": row["stamp"], "cdr_b64": b64encode(raw).decode(), "sha256": row["digest"], "latched": prelude})
        remaining -= row["size"]
        if prelude:
            latch_offset += 1
        else:
            cursor = [row["stamp"], row["shard"], row["ordinal"]]
        if len(result) == count:
            break
    batch = uuid4().hex if result else None
    reply = {"reader": reader["id"], "batch": batch, "done": not result, "events": result}
    if batch:
        db.execute("UPDATE readers SET batch=?,pending=?,next_cursor=? WHERE id=?",
                   (batch, encoded(reply), encoded([latch_offset, *cursor]), reader["id"]))
    return reply


def apply(db: sqlite3.Connection, packet: Json, parent: Path) -> Json:
    """Advance one operation in the caller's database transaction."""
    verb = packet["operation"]
    if verb == "attach":
        return attach(db, packet, parent)
    if verb == "open":
        return open_reader(db, packet)
    identity = text(packet["reader"])
    reader = db.execute("SELECT * FROM readers WHERE id=?", (identity,)).fetchone()
    if reader is None:
        raise ValueError("Unknown reader")
    if verb == "poll":
        return poll(db, packet, reader)
    if verb != "ack" or text(packet["batch"]) != reader["batch"]:
        raise ValueError("Stale or unknown acknowledgement")
    position = json.loads(reader["next_cursor"])
    db.execute("""UPDATE readers SET latch_offset=?,stamp=?,shard=?,ordinal=?,
                  batch=NULL,pending=NULL,next_cursor=NULL WHERE id=?""", (*position, identity))
    return {"reader": identity, "batch": packet["batch"], "acknowledged": True}


def serve(request: Path, state: Path, output: Path) -> None:
    """Serialize one service request, committing response and state before output."""
    packet = load(request)
    identity = text(packet["request_id"])
    disposition = packet["operation"]
    if disposition not in ("attach", "open", "poll", "ack"):
        raise ValueError("Unknown replay operation")
    state.mkdir(parents=True, exist_ok=True)
    database = state / "recordings.db"
    if output.resolve() == database.resolve():
        raise ValueError("The response may not replace the recording database")
    canonical = encoded(packet)
    with closing(sqlite3.connect(database, timeout=30)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA temp_store=FILE")
        db.executescript(SCHEMA)
        with db:
            db.execute("BEGIN IMMEDIATE")
            saved = db.execute("SELECT input,output FROM requests WHERE id=?", (identity,)).fetchone()
            if saved is None:
                reply = apply(db, packet, request.parent)
                db.execute("INSERT INTO requests VALUES (?,?,?)", (identity, canonical, encoded(reply)))
            elif saved["input"] != canonical:
                raise ValueError("Changed request replay")
            else:
                reply = json.loads(saved["output"])
    save(output, reply)
