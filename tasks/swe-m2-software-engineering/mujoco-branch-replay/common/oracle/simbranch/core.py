"""Native MuJoCo stepping and durable counterfactual rollout studies."""

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
from math import isclose, isfinite
import os
from pathlib import Path, PurePosixPath
import tempfile
from xml.etree import ElementTree

import mujoco
import numpy as np


STATE = mujoco.mjtState.mjSTATE_INTEGRATION
FIELDS = {"ctrl", "qfrc_applied", "xfrc_applied", "mocap_pos", "eq_active"}


def encoded(value) -> bytes:
    """Serialize a JSON value stably for fingerprints and request identity."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def object_of(value):
    """Require a JSON object."""
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def list_of(value):
    """Require a JSON array."""
    if not isinstance(value, list):
        raise ValueError("expected an array")
    return value


def tick_of(value, first=0, last=1200) -> int:
    """Read an integer simulation boundary within the requested window."""
    if type(value) is not int or not first <= value <= last:
        raise ValueError("invalid simulation tick")
    return value


def name_of(value) -> str:
    """Read an opaque run ID without a filesystem interpretation."""
    if not isinstance(value, str) or not value:
        raise ValueError("invalid run ID")
    return value


def array_of(value, shape: tuple[int, ...], binary=False) -> np.ndarray:
    """Validate the shape and finite values of a native input array."""
    rows = list_of(value)
    if shape and shape[0] == 0 and not rows:
        return np.empty(shape)
    array = np.asarray(rows, dtype=object)
    if array.shape != shape:
        raise ValueError("incorrect native array shape")
    for item in array.flat:
        allowed = type(item) is int and item in (0, 1) if binary else (
            type(item) in (float, int) and isfinite(item)
        )
        if not allowed:
            raise ValueError("invalid native array entry")
    return array.astype(float)


@dataclass(frozen=True)
class Model:
    """A compiled in-memory model and its stable content identity."""

    native: mujoco.MjModel
    identity: str

    @classmethod
    def compile(cls, spec):
        source = object_of(spec)
        xml = source["xml"]
        if not isinstance(xml, str):
            raise ValueError("XML must be text")
        assets = {}
        for raw, content in object_of(source["assets"]).items():
            path = PurePosixPath(raw)
            if raw in ("", ".") or path.is_absolute() or ".." in path.parts or not isinstance(content, str):
                raise ValueError("invalid text asset")
            assets[raw] = content.encode()
        validate_model_paths(xml, source["assets"])
        identity = hashlib.sha256(encoded({"xml": xml, "assets": source["assets"]})).hexdigest()
        return cls(mujoco.MjModel.from_xml_string(xml, assets), identity)

    def integration(self, data):
        values = np.empty(mujoco.mj_stateSize(self.native, STATE), dtype=np.float64)
        mujoco.mj_getState(self.native, data, values, STATE)
        return values.tolist()

    def start(self, checkpoint):
        data = mujoco.MjData(self.native)
        if checkpoint is None:
            return 0, data
        fields = object_of(checkpoint)
        if fields["model_id"] != self.identity:
            raise ValueError("checkpoint belongs to a different model")
        tick = tick_of(fields["tick"])
        state = array_of(fields["integration"], (mujoco.mj_stateSize(self.native, STATE),))
        mujoco.mj_setState(self.native, data, state, STATE)
        if not isclose(data.time, tick * self.native.opt.timestep, abs_tol=1e-9, rel_tol=0):
            raise ValueError("checkpoint time and tick disagree")
        return tick, data


def validate_model_paths(xml, assets):
    """Keep externally named model resources within the supplied in-memory asset set."""
    pending = [xml]
    inspected = set()
    supplied = {name: PurePosixPath(name).parts for name in assets}
    try:
        while pending:
            for element in ElementTree.fromstring(pending.pop()).iter():
                for key in ("file", "assetdir", "meshdir", "texturedir"):
                    if key not in element.attrib:
                        continue
                    path = PurePosixPath(element.attrib[key])
                    if path.is_absolute() or ".." in path.parts:
                        raise ValueError("model paths must be relative to in-memory assets")
                    if key != "file":
                        continue
                    candidates = [
                        name for name, parts in supplied.items()
                        if parts[-len(path.parts):] == path.parts
                    ]
                    if not candidates:
                        raise ValueError("model file is absent from the in-memory assets")
                    for name in candidates:
                        if name not in inspected and name.endswith(".xml"):
                            inspected.add(name)
                            pending.append(assets[name])
    except ElementTree.ParseError as exc:
        raise ValueError("invalid MJCF XML") from exc


def schedule(spec, data, start, end):
    """Compile complete input replacements and reject conflicting same-tick updates."""
    result = defaultdict(dict)
    for event in list_of(spec["updates"]):
        event = object_of(event)
        tick = tick_of(event["tick"], start, end - 1)
        replacements = object_of(event["set"])
        if not replacements or not replacements.keys() <= FIELDS or replacements.keys() & result[tick].keys():
            raise ValueError("invalid or duplicate scheduled input")
        for field, value in replacements.items():
            result[tick][field] = array_of(value, getattr(data, field).shape, field == "eq_active")
    return result


def selection(values, start, end):
    """Read unique requested boundaries."""
    ticks = [tick_of(item, start, end) for item in list_of(values)]
    if len(ticks) != len(set(ticks)):
        raise ValueError("duplicate sample boundary")
    return set(ticks)


def rollout(model, spec, *, checkpoint=None, checkpoints=False):
    """Advance one native data object and observe requested pre-update boundaries."""
    start, data = model.start(checkpoint)
    end = tick_of(spec["end"], start)
    events = schedule(spec, data, start, end)
    samples_at = selection(spec["sample_ticks"], start, end)
    save_at = selection(spec["checkpoint_ticks"], start, end) if checkpoints else set()
    samples, saved = [], []
    for tick in range(start, end + 1):
        if tick in samples_at:
            samples.append({"tick": tick, "qpos": data.qpos.tolist(), "qvel": data.qvel.tolist(),
                            "act": data.act.tolist()})
        if tick in save_at:
            saved.append({"model_id": model.identity, "tick": tick, "integration": model.integration(data)})
        if tick < end:
            for field, value in events.get(tick, {}).items():
                getattr(data, field)[...] = value
            mujoco.mj_step(model.native, data)
    report = {"model_id": model.identity, "samples": samples}
    if checkpoints:
        report["checkpoints"] = saved
    return report


@contextmanager
def locked_directory(path):
    """Keep concurrent journal readers and writers on one stable lock inode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield descriptor
    finally:
        os.close(descriptor)


def write(path: Path, value) -> None:
    """Publish a complete JSON document with an atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".simulation-") as temp:
        staging = Path(temp) / "document"
        with staging.open("wb") as output:
            output.write(encoded(value) + b"\n")
            output.flush()
            os.fsync(output.fileno())
        staging.replace(path)


def parent_checkpoint(run, finished):
    """Resolve the exact saved boundary requested by a child run."""
    parent = run["parent"]
    if parent is None:
        return None
    source = finished[parent["id"]]["report"]["checkpoints"]
    wanted = tick_of(parent["tick"])
    for checkpoint in source:
        if checkpoint["tick"] == wanted:
            return checkpoint
    raise ValueError("parent has no checkpoint at the requested tick")


def resolve_runs(model, requests, finished):
    """Execute each new run once after its parent, or replay an identical stored result."""
    requested = {}
    for item in list_of(requests):
        item = object_of(item)
        name = name_of(item["id"])
        if name in requested or (name in finished and encoded(finished[name]["request"]) != encoded(item)):
            raise ValueError("duplicate or changed run ID")
        requested[name] = item
        if item["parent"] is not None:
            name_of(object_of(item["parent"])["id"])
    pending = set(requested) - finished.keys()
    while pending:
        ready = [
            name for name in sorted(pending)
            if requested[name]["parent"] is None or requested[name]["parent"]["id"] in finished
        ]
        if not ready:
            raise ValueError("unknown parent or cyclic branch study")
        for name in ready:
            run = requested[name]
            checkpoint = parent_checkpoint(run, finished)
            result = rollout(model, run, checkpoint=checkpoint, checkpoints=True)
            finished[name] = {"request": run, "report": result}
            pending.remove(name)
    return {"model_id": model.identity, "runs": {name: finished[name]["report"] for name in requested}}


def study(model, spec, state):
    """Validate and commit a whole branch request before returning its report."""
    with locked_directory(state) as directory:
        try:
            current = object_of(json.loads(state.read_text(encoding="utf-8")))
        except FileNotFoundError:
            current = {"model_id": model.identity, "runs": {}}
        if current["model_id"] != model.identity:
            raise ValueError("journal has another model")
        result = resolve_runs(model, spec["runs"], object_of(current["runs"]))
        write(state, current)
        os.fsync(directory)
        return result
