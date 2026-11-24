"""Replay deterministic subscriber deliveries and native publisher history."""

from bisect import bisect_left
from collections import deque
from typing import Callable
from pathlib import Path

from .native import Event, Json, events, integer, load, qos, save, text


Consumer = Callable[[str, Event], None]


def compatible(offered: tuple, requested: tuple) -> bool:
    """Check DDS request-versus-offer rules for the chosen QoS policies."""
    return ((requested[0] == "best_effort" or offered[0] == "reliable")
            and (requested[1] == "volatile" or offered[1] == "transient_local"))


class Player:
    """Seekable deterministic player with cache local to a publisher and clock epoch."""

    def __init__(self, timeline: list[Event], topics: set[str]):
        self.timeline = timeline
        self.times = [event.row["record_ns"] for event in timeline]
        self.topics = topics
        self.subscribed = {}
        self.history = {}
        self.deliveries = []
        self.clock = None
        self.epoch = None
        self.cursor = 0
        self.position = 0
        self.on_delivery = lambda subscriber, event: None
        self.on_reset = lambda: None

    def observe(self, index: int) -> None:
        """Advance the playback clock and retain the event without delivering it."""
        event = self.timeline[index]
        row = event.row
        if self.epoch is not None and row["epoch"] != self.epoch:
            self.history.clear()
            self.on_reset()
        self.epoch, self.clock = row["epoch"], row["clock_ns"]
        offer = event.offered
        if offer and offer[1] == "transient_local":
            key = (row["source"], row["topic"])
            self.history.setdefault(key, deque(maxlen=offer[2])).append(index)

    def seek(self, target: int) -> None:
        """Restore intrinsic publisher history without replaying to subscribers."""
        self.cursor = target
        self.position = bisect_left(self.times, target)
        self.history.clear()
        self.clock = self.epoch = None
        self.on_reset()
        for index in range(self.position):
            self.observe(index)

    def send(self, index: int, subscriber: str, operation: int, retained: bool) -> None:
        """Deliver one original payload to the trace and observer."""
        event = self.timeline[index]
        self.deliveries.append(dict(event.row, operation=operation, subscriber=subscriber, retained=retained))
        self.on_delivery(subscriber, event)

    def subscribe(self, row: Json, operation: int) -> None:
        """Register subscriber QoS and send eligible cached history."""
        subscriber, topic = text(row["subscriber"]), text(row["topic"])
        requested = qos(row)
        key = subscriber, topic
        if key in self.subscribed or topic not in self.topics:
            raise ValueError("Duplicate subscription or unknown topic")
        self.subscribed[key] = requested
        if requested[1] != "transient_local":
            return
        indexes = sorted(index for (_, name), history in self.history.items() if name == topic for index in history)
        for index in indexes:
            if compatible(self.timeline[index].offered, requested):
                self.send(index, subscriber, operation, True)

    def advance(self, target: int, operation: int) -> None:
        """Play native events in the requested half-open interval in replay order."""
        if target < self.cursor:
            raise ValueError("Backward play requires a seek")
        stop = bisect_left(self.times, target, lo=self.position)
        for index in range(self.position, stop):
            self.observe(index)
            event = self.timeline[index]
            if event.offered is None:
                continue
            for (subscriber, topic), requested in sorted(self.subscribed.items()):
                if topic == event.row["topic"] and compatible(event.offered, requested):
                    self.send(index, subscriber, operation, False)
        self.position, self.cursor = stop, target

    def execute(self, script: Json, lookup: Callable[[Json, int], None] | None = None) -> Json:
        """Execute an ordered playback script and return the visible delivery trace."""
        self.seek(integer(script["start_ns"]))
        steps = script["operations"]
        if not isinstance(steps, list):
            raise ValueError("Expected operation list")
        for number, command in enumerate(steps):
            kind = command["kind"]
            if kind == "subscribe":
                self.subscribe(command, number)
            elif kind == "advance":
                self.advance(integer(command["until_ns"]), number)
            elif kind == "seek":
                self.seek(integer(command["record_ns"]))
            elif kind == "lookup" and lookup is not None:
                lookup(command, number)
            else:
                raise ValueError("Unsupported replay operation")
        return {"schema_version": 1, "deliveries": self.deliveries, "cursor_ns": self.cursor}


def player_for(spec: Path) -> Player:
    """Open native sources and retain declarations even for empty topics."""
    timeline = events(spec)
    topics = {topic for source in load(spec)["sources"] for topic in source["publishers"]}
    return Player(timeline, topics)


def replay(spec: Path, script: Path, output: Path) -> None:
    """Write only observable subscriber deliveries, without a ROS daemon."""
    save(output, player_for(spec).execute(load(script)))
