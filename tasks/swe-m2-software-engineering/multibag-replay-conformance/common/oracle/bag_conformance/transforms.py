"""Qualify the transform graph observable to each replay subscriber."""

from collections import defaultdict, deque
import math
from pathlib import Path

from .native import Event, Json, STORES, integer, load, save, stamp, text
from .playback import Player, player_for


Pose = tuple[complex, float]
TF = "tf2_msgs/msg/TFMessage"


def frame(value: object) -> str:
    """Normalize ROS frame names and reject empty names."""
    return text(text(value).lstrip("/"))


def rotate(yaw: float) -> complex:
    """Return a complex unit vector for planar rotation."""
    return complex(math.cos(yaw), math.sin(yaw))


def compose(first: Pose, second: Pose) -> Pose:
    """Compose target-from-middle with middle-from-source."""
    return first[0] + rotate(first[1]) * second[0], first[1] + second[1]


def inverse(pose: Pose) -> Pose:
    """Invert a rigid planar pose."""
    return -rotate(-pose[1]) * pose[0], -pose[1]


class Observer:
    """Independent consumer state populated only by delivered TF messages."""

    def __init__(self, player: Player):
        self.player = player
        self.cache = defaultdict(dict)
        self.lookups = []

    def receive(self, subscriber: str, event: Event) -> None:
        """Apply each transform in the delivered native TF message."""
        topic = event.row["topic"]
        if topic not in ("/tf", "/tf_static"):
            return
        if event.row["type"] != TF:
            raise ValueError("Unexpected transform topic type")
        for record in STORES.deserialize_cdr(event.raw, TF).transforms:
            parent, child = frame(record.header.frame_id), frame(record.child_frame_id)
            p, q = record.transform.translation, record.transform.rotation
            if not all(map(math.isfinite, (p.x, p.y, p.z, q.x, q.y, q.z, q.w))) or abs(p.z) > 1e-9 or max(
                abs(q.x), abs(q.y)
            ) > 1e-9 or q.w == q.z == 0:
                raise ValueError("Expected a finite planar transform")
            angle = 2 * math.atan2(q.z, q.w)
            self.cache[subscriber][parent, child, topic] = (stamp(record.header.stamp), (complex(p.x, p.y), angle))

    def resolve(self, subscriber: str, source: str, target: str, age: int) -> Pose | None:
        """Resolve one path across the currently usable and unambiguous forest."""
        now = self.player.clock
        cache = self.cache[subscriber]
        chosen = {}
        for (parent, child, topic), (timestamp, pose) in cache.items():
            if topic == "/tf_static":
                chosen.setdefault((parent, child), pose)
            elif now is not None and 0 <= now - timestamp <= age:
                chosen[parent, child] = pose
        parents, graph = {}, defaultdict(list)
        for (parent, child), pose in chosen.items():
            if child in parents:
                return None
            parents[child] = parent
            graph[child].append((parent, pose))
            graph[parent].append((child, inverse(pose)))
        for node in parents:
            seen = set()
            while node in parents:
                if node in seen:
                    return None
                seen.add(node)
                node = parents[node]
        if source not in graph or target not in graph:
            return None
        pending = deque([(source, (0j, 0.0))])
        visited = {source}
        while pending:
            node, pose = pending.popleft()
            if node == target:
                return pose
            for peer, edge in graph[node]:
                if peer not in visited:
                    visited.add(peer)
                    pending.append((peer, compose(edge, pose)))
        return None

    def lookup(self, row: Json, operation: int) -> None:
        """Record whether this subscriber could resolve the requested pose."""
        subscriber = text(row["subscriber"])
        source, target = frame(row["source_frame"]), frame(row["target_frame"])
        age = integer(row["max_age_ns"])
        if age < 0:
            raise ValueError("Negative pose age")
        pose = self.resolve(subscriber, source, target, age)
        result = [pose[0].real, pose[0].imag, (pose[1] + math.pi) % math.tau - math.pi] if pose else None
        self.lookups.append({"operation": operation, "subscriber": subscriber, "source_frame": source,
                             "target_frame": target, "status": "ok" if pose else "unavailable",
                             "target_from_source": result})


def qualify(spec: Path, script: Path, output: Path) -> None:
    """Replay consumer callbacks and write downstream transform evidence."""
    player = player_for(spec)
    observer = Observer(player)
    player.on_delivery = observer.receive
    player.on_reset = observer.cache.clear
    result = player.execute(load(script), observer.lookup)
    save(output, dict(result, lookups=observer.lookups))
