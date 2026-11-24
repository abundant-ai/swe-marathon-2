"""Recover a bounded causal ROS 2 incident trace from multiple native recorders."""

from collections import defaultdict, deque
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import heapq
import math
from pathlib import Path

from rosbags.rosbag2 import Reader

from .native import Json, STORES, integer, load, save, text
from .transforms import TF, Pose, compose, frame, inverse


Bounds = tuple[int, int]
NativeKey = tuple[str, int, int]


class Conflict(Exception):
    """Report internally contradictory evidence rather than malformed input."""


def sequence(value: object) -> list:
    """Read one array from the incident evidence."""
    if not isinstance(value, list):
        raise ValueError("Expected array")
    return value


def natural(value: object) -> int:
    """Read a nonnegative integer sequence or latency."""
    result = integer(value)
    if result < 0:
        raise ValueError("Expected nonnegative integer")
    return result


@dataclass(frozen=True)
class Segment:
    """One calibrated record-clock interval with inclusive offset uncertainty."""

    start: int
    end: int
    rate: Fraction
    lower: Fraction
    upper: Fraction

    def emission(self, record: int, latency: Bounds) -> Bounds:
        """Bound emission time from the exact clock and transport intervals."""
        low, high = latency
        return math.ceil(self.rate * record + self.lower - high), math.floor(self.rate * record + self.upper - low)


def calibration(rows: list[Json]) -> list[Segment]:
    """Reconcile the trusted pulse bounds for each disjoint recorder interval."""
    result = []
    for row in rows:
        start, end = integer(row["local_start_ns"]), integer(row["local_end_ns"])
        num, den = map(integer, sequence(row["rate"]))
        pulses = sequence(row["pulses"])
        if not start < end or min(num, den) <= 0 or not pulses:
            raise ValueError("Invalid clock segment")
        rate = Fraction(num, den)
        lows, highs = [], []
        for pulse in pulses:
            stamp = integer(pulse["local_ns"])
            first, last = integer(pulse["earliest_ns"]), integer(pulse["latest_ns"])
            if not start <= stamp < end or first > last:
                raise ValueError("Invalid sync pulse")
            lows.append(first - rate * stamp)
            highs.append(last - rate * stamp)
        lower, upper = max(lows), min(highs)
        if lower > upper:
            raise Conflict("timing_conflict")
        result.append(Segment(start, end, rate, lower, upper))
    result.sort(key=lambda piece: piece.start)
    if any(a.end > b.start for a, b in zip(result, result[1:])):
        raise ValueError("Overlapping clock segments")
    return result


@dataclass
class Capture:
    """A declared native recorder and the requested decoded storage entries."""

    path: Path
    segments: list[Segment]
    keys: set[NativeKey]

    def read(self) -> dict[NativeKey, tuple[str, bytes]]:
        """Find only referenced messages, counting storage-order ties per topic."""
        located = {}
        counts = defaultdict(int)
        wanted = {(topic, stamp) for topic, stamp, _ in self.keys}
        with Reader(self.path) as reader:
            for connection, stamp, payload in reader.messages():
                group = connection.topic, stamp
                if group not in wanted:
                    continue
                ordinal = counts[group]
                counts[group] += 1
                key = *group, ordinal
                if key in self.keys:
                    located[key] = connection.msgtype, bytes(payload)
                    if len(located) == len(self.keys):
                        break
        if self.keys != located.keys():
            raise ValueError("Referenced native record is missing")
        return located

    def interval(self, record: int, latency: Bounds) -> Bounds:
        """Look up the supported clock piece for a referenced receipt timestamp."""
        for piece in self.segments:
            if piece.start <= record < piece.end:
                return piece.emission(record, latency)
        raise ValueError("Record outside clock calibration")


@dataclass
class Emission:
    """A wire-deduplicated logical event and its immediate predecessors."""

    name: str
    producer: str
    boot: str
    number: int
    predecessors: set[str]
    topic: str
    type: str
    raw: bytes
    lower: int
    upper: int

    def report(self) -> Json:
        """Describe the original CDR and current tightened witness interval."""
        return {"id": self.name, "topic": self.topic, "type": self.type,
                "sha256": sha256(self.raw).hexdigest(), "earliest_ns": self.lower, "latest_ns": self.upper}


def logical_records(spec: Json, parent: Path) -> tuple[dict[str, Emission], dict[str, list[str]]]:
    """Decode native occurrences, join copied wire events, and add producer predecessors."""
    captures = {}
    for row in sequence(spec["captures"]):
        name, hint = text(row["id"]), Path(text(row["path"]))
        if name in captures or hint.is_absolute():
            raise ValueError("Capture names must be unique and paths relative")
        captures[name] = Capture(parent / hint, calibration(sequence(row["segments"])), set())
    if not captures:
        raise ValueError("No captures")
    boots = {}
    for producer, raw in spec["boots"].items():
        producer = text(producer)
        values = [text(boot) for boot in sequence(raw)]
        if not values or len(set(values)) != len(values):
            raise ValueError("Invalid producer boots")
        boots[producer] = values
    definitions = {}
    slot_by_boot = defaultdict(dict)
    for row in sequence(spec["events"]):
        name, producer, boot = map(text, (row["id"], row["producer"], row["boot"]))
        number = natural(row["sequence"])
        if name in definitions or boot not in boots[producer] or number in slot_by_boot[producer, boot]:
            raise ValueError("Repeated event identity or unknown boot")
        slot_by_boot[producer, boot][number] = name
        copies = []
        for copy in sequence(row["copies"]):
            recorder = text(copy["capture"])
            key = text(copy["topic"]), integer(copy["record_ns"]), natural(copy["ordinal"])
            low, high = natural(copy["latency_min_ns"]), natural(copy["latency_max_ns"])
            if low > high:
                raise ValueError("Invalid latency bounds")
            captures[recorder].keys.add(key)
            copies.append((recorder, key, captures[recorder].interval(key[1], (low, high))))
        if not copies:
            raise ValueError("No native copies")
        causes = {text(value) for value in sequence(row["causes"])}
        definitions[name] = producer, boot, number, causes, copies
    located = {name: value.read() for name, value in captures.items()}
    result = {}
    for name, (producer, boot, number, causes, copies) in definitions.items():
        if not causes <= definitions.keys():
            raise ValueError("Unknown causal predecessor")
        signatures = {(key[0], *located[recorder][key]) for recorder, key, _ in copies}
        if len(signatures) != 1:
            raise Conflict("payload_conflict")
        topic, type_, raw = signatures.pop()
        first = max(bounds[0] for _, _, bounds in copies)
        last = min(bounds[1] for _, _, bounds in copies)
        if first > last:
            raise Conflict("timing_conflict")
        result[name] = Emission(name, producer, boot, number, causes, topic, type_, raw, first, last)
    for producer, order in boots.items():
        chain = [name for boot in order for _, name in sorted(slot_by_boot[producer, boot].items())]
        for older, newer in zip(chain, chain[1:]):
            result[newer].predecessors.add(older)
    return result, boots


def ordered(events: dict[str, Emission]) -> list[Emission]:
    """Detect causal cycles and tighten both bounds before choosing a stable witness."""
    downstream = defaultdict(list)
    remaining = {name: len(event.predecessors) for name, event in events.items()}
    for name, event in events.items():
        for earlier in event.predecessors:
            downstream[earlier].append(name)
    open_ = deque(sorted(name for name, degree in remaining.items() if degree == 0))
    order = []
    while open_:
        name = open_.popleft()
        order.append(name)
        for child in downstream[name]:
            remaining[child] -= 1
            if remaining[child] == 0:
                open_.append(child)
    if len(order) != len(events):
        raise Conflict("causal_cycle")
    for name in order:
        for child in downstream[name]:
            events[child].lower = max(events[child].lower, events[name].lower)
    for name in reversed(order):
        for child in downstream[name]:
            events[name].upper = min(events[name].upper, events[child].upper)
        if events[name].lower > events[name].upper:
            raise Conflict("timing_conflict")
    remaining = {name: len(event.predecessors) for name, event in events.items()}
    frontier = [(events[name].lower, name) for name, degree in remaining.items() if degree == 0]
    heapq.heapify(frontier)
    witness = []
    while frontier:
        _, name = heapq.heappop(frontier)
        witness.append(events[name])
        for child in downstream[name]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(frontier, (events[child].lower, child))
    return witness


def transforms(event: Emission) -> list[tuple[str, str, Pose]]:
    """Parse native TF without comparing header stamps from unrelated producer clocks."""
    if event.type != TF:
        raise ValueError("Unexpected TF message type")
    values = []
    for transform in STORES.deserialize_cdr(event.raw, TF).transforms:
        parent, child = frame(transform.header.frame_id), frame(transform.child_frame_id)
        p, q = transform.transform.translation, transform.transform.rotation
        if not all(map(math.isfinite, (p.x, p.y, p.z, q.x, q.y, q.z, q.w))) or abs(p.z) > 1e-9 or max(
            abs(q.x), abs(q.y)
        ) > 1e-9 or q.z == q.w == 0:
            raise ValueError("Underlying transform is not planar")
        values.append((parent, child, (complex(p.x, p.y), 2 * math.atan2(q.z, q.w))))
    return values


def resolve(graph_poses: dict, source: str, target: str) -> Pose | None:
    """Find a directed or inverse pose in an unambiguous planar forest."""
    branches, parents = defaultdict(list), {}
    for (parent, child), pose in graph_poses.items():
        if child in parents:
            return None
        parents[child] = parent
        branches[child].append((parent, pose))
        branches[parent].append((child, inverse(pose)))
    for node in parents:
        walked = set()
        while node in parents:
            if node in walked:
                return None
            walked.add(node)
            node = parents[node]
    if source not in branches or target not in branches:
        return None
    stack = [(source, (0j, 0.0))]
    visited = {source}
    while stack:
        node, so_far = stack.pop()
        if node == target:
            return so_far
        for other, transform in branches[node]:
            if other not in visited:
                visited.add(other)
                stack.append((other, compose(transform, so_far)))
    return None


@dataclass
class IncidentObserver:
    """Query only stable recorder cuts and boot-scoped transform authorities."""

    events: list[Emission]
    boot_order: dict[str, list[str]]
    poses: dict[str, list[tuple[str, str, Pose]]]

    def at(self, at: int, age: int, source: str, target: str) -> tuple[str, Pose | None]:
        """Separate temporal ambiguity from absence or graph disagreement."""
        tf_producers = {event.producer for event in self.events if event.name in self.poses}
        first = {}
        active = {}
        for event in self.events:
            first.setdefault((event.producer, event.boot), event)
            if event.name in self.poses and event.lower <= at < event.upper:
                return "ambiguous", None
        for producer in tf_producers:
            for boot in self.boot_order[producer]:
                event = first.get((producer, boot))
                if event is not None and event.lower <= at:
                    if event.upper > at:
                        return "ambiguous", None
                    active[producer] = boot
        sources = defaultdict(dict)
        for event in self.events:
            if event.name in self.poses and event.upper <= at and active.get(event.producer) == event.boot:
                for parent, child, pose in self.poses[event.name]:
                    sources[parent, child, event.topic][event.producer] = event, pose
        available = {}
        for (parent, child, topic), values in sources.items():
            if len(values) != 1:
                return "ambiguous", None
            event, pose = next(iter(values.values()))
            if topic == "/tf":
                if at - event.upper > age:
                    continue
                if at - event.lower > age:
                    return "ambiguous", None
            available[parent, child, topic] = pose
        pairs = {(parent, child): pose for (parent, child, topic), pose in available.items() if topic == "/tf_static"}
        pairs.update({(parent, child): pose for (parent, child, topic), pose in available.items() if topic == "/tf"})
        result = resolve(pairs, source, target)
        return ("ok", result) if result is not None else ("unavailable", None)

    def lookup(self, row: Json) -> Json:
        """Render one pose query at a master-clock incident cut."""
        at, age = integer(row["at_ns"]), natural(row["max_age_ns"])
        source, target = frame(row["source_frame"]), frame(row["target_frame"])
        status, pose = self.at(at, age, source, target)
        encoded = [pose[0].real, pose[0].imag, (pose[1] + math.pi) % math.tau - math.pi] if pose else None
        return {"at_ns": at, "source_frame": source, "target_frame": target,
                "status": status, "target_from_source": encoded}


def incident(spec: Path, output: Path) -> None:
    """Publish one auditable incident reconstruction or typed evidence conflict."""
    data = load(spec)
    queries = sequence(data["lookups"])
    try:
        entries, boots = logical_records(data, spec.parent)
        poses = {entry.name: transforms(entry) for entry in entries.values() if entry.topic in {"/tf", "/tf_static"}}
        witness = ordered(entries)
        observer = IncidentObserver(witness, boots, poses)
        report = {"status": "ok", "events": [event.report() for event in witness],
                  "lookups": [observer.lookup(query) for query in queries]}
    except Conflict as error:
        report = {"status": str(error), "events": [], "lookups": []}
    save(output, dict(report, schema_version=1))
