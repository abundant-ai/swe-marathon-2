"""Journal the active estimator and latest response for each producer stream."""

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from .contract import Json, integer, name, obj, read_config, read_events
from .gaussian import Smoother, canonical
from .sensors import adapter_from


@contextmanager
def lock(state: Path) -> Iterator[None]:
    """Hold a stable sidecar lock around loading, calculating and committing."""
    state.parent.mkdir(parents=True, exist_ok=True)
    with state.with_name(state.name + ".lock").open("ab") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def commit(state: Path, journal: Json) -> None:
    """Durably replace the journal and sync its directory before returning."""
    data = canonical(journal) + "\n"
    staged = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=state.parent,
            prefix=".lagfusion-state-",
            delete=False,
        ) as handle:
            staged = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        staged.replace(state)
        descriptor = os.open(state.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def ingest(packet: Json, state: Path) -> Json:
    """Apply a well-formed packet once, preserving its exact retransmit response."""
    stream = name(packet["stream_id"])
    sequence = integer(packet["sequence"], 1)
    model = {
        key: packet[key]
        for key in ("config", "calibration", "anchors")
        if key in packet
    }
    config = read_config(packet["config"])
    events = read_events(packet["events"], adapter_from(packet), revisions=True)
    request = canonical(packet)
    with lock(state):
        try:
            journal = obj(json.loads(state.read_text(encoding="utf-8")))
        except FileNotFoundError:
            journal = {}
        entry = journal.get(stream)
        if entry is not None and request == entry["request"]:
            return entry["reply"]
        rejected = {
            "stream_id": stream,
            "sequence": sequence,
            "status": "rejected",
            "result": None,
        }
        expected = 1 if entry is None else entry["reply"]["sequence"] + 1
        if sequence != expected or (
            entry is not None and canonical(model) != canonical(entry["model"])
        ):
            return rejected

        smoother = Smoother(config, entry["state"] if entry is not None else None)
        report = smoother.execute(events)
        reply = {
            "stream_id": stream,
            "sequence": sequence,
            "status": "accepted",
            "result": report,
        }
        journal[stream] = {
            "request": request,
            "model": model,
            "reply": reply,
            "state": smoother.encoded(),
        }
        commit(state, journal)
        return reply
