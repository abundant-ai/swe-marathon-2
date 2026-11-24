"""Track a loaded rotary joint through observable, generation-fenced handover."""

from collections import deque
from dataclasses import dataclass, field, replace
import json
import math
from typing import Any, TextIO

from .core import Installation, counter, name_of, object_of


Record = dict[str, Any]


def number(value: object, minimum: float = -math.inf, *, strict: bool = False) -> float:
    """Parse a finite wire quantity with an optional lower bound."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected a finite numeric quantity")
    if value < minimum or (strict and value == minimum):
        raise ValueError("Quantity outside its range")
    return float(value)


def bound(value: float, lower: float, upper: float) -> float:
    """Constrain a scalar to a nonempty feasible interval."""
    if lower > upper:
        raise ValueError("No feasible effort within the drive limits")
    return min(max(value, lower), upper)


@dataclass(frozen=True)
class Drive:
    """Describe a commissioned drive, the root's mode, and its calibration."""

    root: str
    mode: str
    gain: float
    bias: float
    limit: float


@dataclass(frozen=True)
class ServoSpec:
    """Hold the immutable commissioning data for a control session."""

    packet: Record
    drives: dict[str, Drive]
    max_effort: float
    max_slew: float
    max_age: int
    inertia: float
    drag: float
    gravity: float

    @classmethod
    def parse(cls, packet: Record) -> "ServoSpec":
        """Validate each drive against its commissioned controller and interfaces."""
        graph = Installation.parse(packet)
        config = object_of(packet["servo"])
        rows = object_of(config["drives"])
        if len(rows) != 2:
            raise ValueError("Expected two drives")
        drives = {}
        for device, item in rows.items():
            root = name_of(item["root"])
            claim = [claim for claim in graph.claims[root] if claim.device == device and claim.interfaces]
            if len(claim) != 1 or device not in graph.devices:
                raise ValueError("Drive root must claim its device")
            drives[device] = Drive(root, claim[0].mode, number(item["gain_nm"], 0, strict=True),
                                   number(item["bias_nm"]), number(item["command_limit"], 0, strict=True))
        if len({drive.root for drive in drives.values()}) != len(drives):
            raise ValueError("Drive roots must be distinct")
        return cls(packet, drives, number(config["max_effort_nm"], 0, strict=True),
                   number(config["max_slew_nm_s"], 0, strict=True), counter(config["max_feedback_age_ns"]),
                   number(config["inertia"], 0, strict=True), number(config["drag"], 0),
                   number(config["gravity_nm"], 0))


@dataclass(frozen=True)
class Cycle:
    """Represent one valid cycle packet and a current installation view."""

    sequence: int
    now: int
    period: float
    installation: Installation
    generations: dict[str, int | None]
    lease: tuple[str, int] | None
    wanted: str
    pending: Record | None
    measured: tuple[int, float, float]
    target: tuple[float, float, float]
    effort: float

    @classmethod
    def parse(cls, spec: ServoSpec, row: Record) -> "Cycle":
        """Parse a live packet without editing the original commissioning graph."""
        sequence, now = counter(row["cycle"]), counter(row["time_ns"])
        snapshot = Installation.parse({**spec.packet, "snapshot": row["snapshot"]})
        generations = object_of(row["activation_generations"])
        if generations.keys() != spec.drives.keys():
            raise ValueError("Expected activation readback for both drives")
        for value in generations.values():
            if value is not None:
                counter(value)
        lease = row["lease"]
        if lease is not None:
            lease = name_of(lease["device"]), counter(lease["generation"])
            if lease[0] not in spec.drives:
                raise ValueError("Uncommissioned lease")
        wanted = name_of(row["wanted"])
        if wanted not in spec.drives:
            raise ValueError("Uncommissioned wanted device")
        pending = row["pending"]
        if pending is not None:
            name_of(pending["id"])
            counter(pending["generation"])
            device, kind = pending["device"], pending["kind"]
            if device not in spec.drives or kind not in ("mode", "start", "transfer"):
                raise ValueError("Invalid pending action")
            if kind == "mode" and pending["mode"] != spec.drives[device].mode:
                raise ValueError("Invalid pending mode")
        measured = row["measurement"]
        sample_ns = counter(measured["time_ns"])
        if sample_ns > now:
            raise ValueError("Feedback sample is newer than the cycle")
        target = row["target"]
        return cls(sequence, now, counter(row["period_ns"], 1) / 1e9, snapshot, generations, lease, wanted, pending,
                   (sample_ns, number(measured["position_rad"]), number(measured["velocity_rad_s"])),
                   tuple(number(target[k]) for k in ("position_rad", "velocity_rad_s", "acceleration_rad_s2")),
                   number(row["applied_nm"]))


@dataclass(frozen=True)
class Authority:
    """Use observed generation, dependency closure, and interface state to issue safe actions."""

    cycle: Cycle
    spec: ServoSpec

    @property
    def active(self) -> frozenset[str]:
        """Remove lifecycle readback known to belong to an earlier generation."""
        invalid = {row.root for device, row in self.spec.drives.items()
                   if self.cycle.generations[device] != self.cycle.installation.devices[device].generation}
        return self.cycle.installation.active - invalid

    def usable(self, device: str) -> bool:
        """Check that a drive's complete current-generation chain can write."""
        drive = self.spec.drives[device]
        installation = replace(self.cycle.installation, active=self.active)
        return drive.root in self.active - installation.unsafe()

    def owner(self) -> str | None:
        """Return the fresh lease only when it confers real command authority."""
        if self.cycle.lease is None:
            return None
        device, generation = self.cycle.lease
        reading = self.cycle.installation.devices[device]
        return device if generation == reading.generation and self.usable(device) else None

    def progress(self, owner: str | None) -> Record | None:
        """Prefer service restoration, then make-before-break the requested handover."""
        cycle = self.cycle
        if cycle.pending is not None:
            return None
        installation = replace(cycle.installation, active=self.active)
        broken = installation.unsafe()
        choices = [cycle.wanted, *(key for key in self.spec.drives if key != cycle.wanted)]
        active = [device for device in choices if self.usable(device)]
        if owner is None and active:
            return self.action(active[0], "transfer")
        if owner == cycle.wanted:
            return None
        for device in choices:
            if device == owner:
                continue
            reading = installation.devices[device]
            drive = self.spec.drives[device]
            dependencies = installation.closures[drive.root] - {drive.root}
            if not reading.ready or not dependencies <= installation.active - broken:
                continue
            if device in active:
                return self.action(device, "transfer")
            if drive.root not in self.active:
                return self.action(device, "mode" if reading.mode != drive.mode else "start")
        return None

    def action(self, device: str, kind: str) -> Record:
        """Build a nonblocking action fenced by the current device generation."""
        generation = self.cycle.installation.devices[device].generation
        row = {"id": f"{self.cycle.sequence}:{device}:{generation}", "kind": kind,
               "device": device, "generation": generation}
        if kind == "mode":
            row["mode"] = self.spec.drives[device].mode
        return row


@dataclass
class Tracker:
    """Compute physical torque with bounded feedback and measured continuity."""

    spec: ServoSpec
    integral: float = 0.0
    load_nm: float = 0.0
    last_cycle: int | None = None
    last_sample: tuple[int, float, float] | None = None
    applied: deque[tuple[int, int, float]] = field(default_factory=lambda: deque(maxlen=80))

    def observe(self, cycle: Cycle) -> None:
        """Estimate load from the measured acceleration and actual intervening efforts."""
        if self.last_cycle is not None:
            self.applied.append((self.last_cycle, cycle.now, cycle.effort))
        self.last_cycle = cycle.now
        recent = self.last_sample
        stamp, position, speed = cycle.measured
        if recent is None:
            self.last_sample = cycle.measured
            return
        old_stamp, old_position, old_speed = recent
        if stamp <= old_stamp:
            return
        self.last_sample = cycle.measured
        if not self.applied or self.applied[0][0] > old_stamp:
            return
        elapsed = (stamp - old_stamp) / 1e9
        provided = sum(torque * max(0, min(end, stamp) - max(start, old_stamp))
                       for start, end, torque in self.applied) / (stamp - old_stamp)
        predicted = self.spec.inertia * (speed - old_speed) / elapsed
        friction = self.spec.drag * (old_speed + speed) / 2
        gravity = self.spec.gravity * math.sin((old_position + position) / 2)
        load_estimate = bound(predicted + friction + gravity - provided, -2.5, 2.5)
        self.load_nm += (1 - math.exp(-elapsed / 0.075)) * (load_estimate - self.load_nm)

    def effort(self, cycle: Cycle, device: str) -> Record:
        """Choose a calibrated command inside both hardware and instantaneous slew limits."""
        spec = self.spec
        drive = spec.drives[device]
        stamp, position, speed = cycle.measured
        expected, expected_speed, expected_accel = cycle.target
        age = cycle.now - stamp
        lower = max(-spec.max_effort, drive.bias - drive.limit * drive.gain,
                    cycle.effort - spec.max_slew * cycle.period)
        upper = min(spec.max_effort, drive.bias + drive.limit * drive.gain,
                    cycle.effort + spec.max_slew * cycle.period)
        if age > spec.max_age:
            desired = cycle.effort
            used = bound(desired, lower, upper)
        else:
            delay = age / 1e9
            acceleration = (cycle.effort - spec.drag * speed - spec.gravity * math.sin(position)
                            + self.load_nm) / spec.inertia
            position += speed * delay + 0.5 * acceleration * delay**2
            speed += acceleration * delay
            error = expected - position
            proposed = bound(self.integral + 5.0 * error * cycle.period, -1.6, 1.6)
            desired = (spec.inertia * (expected_accel + 45.0 * error + 11.0 * (expected_speed - speed))
                       + spec.drag * speed + spec.gravity * math.sin(position) + proposed - self.load_nm)
            used = bound(desired, lower, upper)
            if used == desired or (desired - used) * error <= 0:
                self.integral = proposed
        return {"device": device, "generation": cycle.installation.devices[device].generation,
                "command": (used - drive.bias) / drive.gain}


def servo(packet: Record, source: TextIO, sink: TextIO) -> None:
    """Process well-formed NDJSON cycles and flush one answer before accepting the next."""
    spec = ServoSpec.parse(packet)
    tracker = Tracker(spec)
    previous = -1, -1
    for line in source:
        cycle = Cycle.parse(spec, object_of(json.loads(line)))
        if cycle.sequence <= previous[0] or cycle.now <= previous[1]:
            raise ValueError("Cycle and time must increase")
        previous = cycle.sequence, cycle.now
        authority = Authority(cycle, spec)
        owner = authority.owner()
        tracker.observe(cycle)
        result = {"cycle": cycle.sequence, "effort": tracker.effort(cycle, owner) if owner else None,
                  "action": authority.progress(owner)}
        print(json.dumps(result, allow_nan=False, separators=(",", ":")), file=sink, flush=True)
