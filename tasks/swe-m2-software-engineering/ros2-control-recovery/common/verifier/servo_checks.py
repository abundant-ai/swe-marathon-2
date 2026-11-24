"""Drive protected joint sessions from an independent simulated hardware process."""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import pwd
from selectors import DefaultSelector, EVENT_READ
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

from probes import controller, snapshot


Record = dict[str, Any]
COMMAND = [sys.executable, "-B", "-m", "control_recovery", "servo", "--spec"]
PERIODS = (8_400_000, 11_000_000, 14_700_000, 9_500_000, 12_600_000, 7_300_000, 17_200_000)
METRICS = ("lease_and_maintenance", "live_effort", "trajectory_and_settling", "cycle_deadline")


class InvalidCycle(Exception):
    """A command could not be safely applied to the simulated hardware."""


class Session:
    """Exchange bounded per-cycle messages with one unprivileged supervisor."""

    def __init__(self, app: Path, spec: Path) -> None:
        options = {}
        if os.geteuid() == 0:
            account = pwd.getpwnam("candidate")
            options = {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}
        self.child = subprocess.Popen([*COMMAND, str(spec)], cwd=app, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      start_new_session=True, bufsize=0,
                                      env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
                                           "HOME": str(spec.parent), "PYTHONDONTWRITEBYTECODE": "1"},
                                      **options)
        self.selector = DefaultSelector()
        self.selector.register(self.child.stdout, EVENT_READ)
        self.buffer = b""
        self.first = True

    def exchange(self, packet: Record) -> tuple[Record, float | None]:
        """Send observed plant state and return one bounded reply and its elapsed seconds."""
        started = time.monotonic()
        payload = (json.dumps(packet, allow_nan=False, separators=(",", ":")) + "\n").encode()
        if self.child.stdin.write(payload) != len(payload):
            raise InvalidCycle("cycle packet was not consumed")
        deadline = started + (1.0 if self.first else 0.25)
        while b"\n" not in self.buffer:
            if time.monotonic() >= deadline or not self.selector.select(max(0, deadline - time.monotonic())):
                raise InvalidCycle("supervisor missed the cycle response deadline")
            fragment = os.read(self.child.stdout.fileno(), 4096)
            if not fragment or len(self.buffer) + len(fragment) > 2048:
                raise InvalidCycle("supervisor closed the reply stream or exceeded the line budget")
            self.buffer += fragment
        line, self.buffer = self.buffer.split(b"\n", 1)
        reply = json.loads(line)
        if not isinstance(reply, dict):
            raise InvalidCycle("expected a reply object")
        elapsed = None if self.first else time.monotonic() - started
        self.first = False
        return reply, elapsed

    def close(self, *, clean: bool = False) -> None:
        """Close a session, checking clean EOF only for deliberately finished missions."""
        self.selector.close()
        self.child.stdin.close()
        try:
            if clean:
                if self.child.wait(timeout=2) != 0 or self.buffer or self.child.stdout.read(1):
                    raise InvalidCycle("supervisor did not finish the stream cleanly")
        finally:
            try:
                os.killpg(self.child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.child.wait(timeout=2)
            self.child.stdout.close()


@dataclass
class Drive:
    """Private physical mode and lifecycle readback of one actuator."""

    generation: int
    mode: str
    ready: bool
    active_generation: int | None


@dataclass(frozen=True)
class Case:
    """Author one commissioning class, plant mismatch, and disturbance profile."""

    name: str
    variant: int
    inertia: float
    drag: float
    gravity: float
    load: float
    delays: dict[str, int]


CASES = (
    Case("maintenance", 0, 0.74, 0.19, 0.98, 1.18, {"mode": 4, "start": 6, "transfer": 5}),
    Case("pending_reset", 1, 0.94, 0.35, 1.19, -1.18, {"mode": 3, "start": 4, "transfer": 5}),
    Case("feedback_dropout", 2, 0.61, 0.26, 1.31, 1.45, {"mode": 5, "start": 5, "transfer": 6}),
)


class Plant:
    """Model actuator readback and physically integrate only accepted torque writes."""

    def __init__(self, case: Case) -> None:
        self.case = case
        self.primary, self.standby = (("right_bus", "left_bus") if case.variant == 1
                                      else ("axis_main", "axis_spare"))
        self.drives = {self.primary: Drive(8 + case.variant, "effort", True, 8 + case.variant),
                       self.standby: Drive(13 + case.variant, "idle", True, None)}
        if case.variant == 2:
            self.drives[self.standby].mode = "effort"
            self.drives[self.standby].active_generation = self.drives[self.standby].generation
        self.channels = {
            self.primary: {"root": "track_primary", "gain_nm": 12.0, "bias_nm": 0.42, "command_limit": 1.0},
            self.standby: {"root": "track_backup", "gain_nm": 5.0, "bias_nm": -0.62, "command_limit": 1.0},
        }
        self.observers = {self.primary: "primary_encoder", self.standby: "spare_encoder"}
        self.observing = {self.primary, self.standby}
        self.claimed = (self.primary, self.drives[self.primary].generation)
        self.reported = self.claimed
        self.stale_until = 0
        self.wanted = self.primary
        self.pending = None
        self.command_ids = set()
        self.index = 0
        self.start = 4_200_000_013 + case.variant * 11_733_751
        self.now = self.start
        self.position = self.target(0)[0] + 0.026
        self.speed = self.target(0)[1] - 0.023
        self.torque = 0.0
        self.max_effort = 4.0
        self.max_slew = 23.0
        self.history = []
        self.reboot = None
        self.age_limit = 37_000_000
        self.max_gap = self.gap = 0

    def configuration(self) -> Record:
        """Export only the nominal commissioning data to the candidate process."""
        return {"hardware": {
            key: {"modes": {"idle": [], "effort": ["joint_effort"]}} for key in self.drives},
            "controllers": {
                **{row["root"]: controller([self.observers[key]], key, "effort", ("joint_effort",))
                   for key, row in self.channels.items()},
                **{name: controller() for name in self.observers.values()},
            },
            "snapshot": self.snapshot(),
            "groups": [{"id": "protected_joint", "options": [[row["root"]] for row in self.channels.values()]}],
            "servo": {"drives": self.channels, "max_effort_nm": self.max_effort, "max_slew_nm_s": self.max_slew,
                      "max_feedback_age_ns": self.age_limit, "inertia": 0.77, "drag": 0.23, "gravity_nm": 1.13}}

    def snapshot(self) -> Record:
        """Report remembered lifecycle claims even while their generation is stale."""
        return snapshot({key: (drive.generation, drive.mode, "ready" if drive.ready else "fault")
                         for key, drive in self.drives.items()},
                        [*(self.observers[key] for key in sorted(self.observing)),
                         *(self.channels[key]["root"] for key, drive in self.drives.items()
                           if drive.active_generation is not None)])

    def target(self, elapsed: float) -> tuple[float, float, float]:
        """Return an authored smooth rotary trajectory and its derivatives."""
        sign = (-1.0 if self.case.variant == 1 else 1.0)
        first = (0.38 + self.case.variant * 0.04, 1.01 - self.case.variant * 0.04, 0.17 * self.case.variant)
        second = (0.115, 2.11 + self.case.variant * 0.09, 0.29)
        terms = (first, second)
        position = sum(amplitude * math.sin(frequency * elapsed + phase) for amplitude, frequency, phase in terms)
        speed = sum(amplitude * frequency * math.cos(frequency * elapsed + phase)
                    for amplitude, frequency, phase in terms)
        acceleration = -sum(amplitude * frequency**2 * math.sin(frequency * elapsed + phase)
                            for amplitude, frequency, phase in terms)
        return sign * position, sign * speed, sign * acceleration

    def good_drive(self, device: str) -> bool:
        """Validate actual drive readiness, mode and activation generation."""
        state = self.drives[device]
        return (state.ready and state.mode == "effort" and state.active_generation == state.generation
                and device in self.observing)

    def power(self, device: str, *, ready: bool) -> None:
        """Advance a device's authority generation while its lifecycle report survives."""
        state = self.drives[device]
        state.generation += 1
        state.mode, state.ready = "idle", ready
        if self.claimed is not None and self.claimed[0] == device:
            self.claimed = None
            self.stale_until = self.index + 2

    def prepare_cycle(self) -> bool:
        """Apply private device events and finish pending operations before reading."""
        index, case = self.index, self.case.variant
        restart = False
        if case == 0:
            if index == 24:
                self.wanted = self.standby
                self.observing.remove(self.standby)
            if index == 30:
                self.observing.add(self.standby)
            if index == 64:
                self.power(self.primary, ready=False)
            if index == 153:
                self.power(self.primary, ready=True)
            if index == 215:
                self.wanted = self.primary
        elif case == 1:
            if index == 25:
                self.wanted = self.standby
            if self.pending and self.reboot is None:
                operation, finish = self.pending
                if operation["kind"] == "transfer" and operation["device"] == self.standby and index == finish - 3:
                    self.power(self.standby, ready=True)
                    self.reboot = index
            if self.reboot is not None:
                restart = index == self.reboot + 1
                if index == self.reboot + 8:
                    self.power(self.primary, ready=False)
        else:
            if index == 69:
                self.power(self.primary, ready=False)
            if index == 151:
                self.power(self.primary, ready=True)
            restart = index == 155
        if self.pending and self.pending[1] == index:
            action, _ = self.pending
            device, kind = action["device"], action["kind"]
            state = self.drives[device]
            if state.ready and state.generation == action["generation"]:
                if kind == "mode":
                    state.mode = "effort"
                elif kind == "start" and state.mode == "effort":
                    state.active_generation = state.generation
                elif kind == "transfer" and self.good_drive(device):
                    self.claimed = device, state.generation
                    self.reported = self.claimed
                    self.stale_until = index
            self.pending = None
        if index >= self.stale_until:
            self.reported = self.claimed
        return restart

    def cycle_packet(self) -> Record:
        """Build an observation from actual simulated hardware and delayed encoder samples."""
        index = self.index
        period = PERIODS[(index * 3 + self.case.variant) % len(PERIODS)]
        self.history.append((self.now, self.position, self.speed))
        lag = (index // 3 + self.case.variant) % 3
        if self.case.variant == 2 and 71 <= index < 81:
            lag = index - 70
        sample_time, position, velocity = self.history[max(0, index - lag)]
        q, qd, qdd = self.target((self.now - self.start) / 1e9)
        lease = dict(zip(("device", "generation"), self.reported, strict=True)) if self.reported else None
        return {"cycle": index, "time_ns": self.now, "period_ns": period, "snapshot": self.snapshot(),
                "activation_generations": {device: state.active_generation for device, state in self.drives.items()},
                "lease": lease, "wanted": self.wanted, "pending": self.pending[0] if self.pending else None,
                "measurement": {"time_ns": sample_time, "position_rad": position, "velocity_rad_s": velocity},
                "target": {"position_rad": q, "velocity_rad_s": qd, "acceleration_rad_s2": qdd},
                "applied_nm": self.torque}

    def request(self, action: Record) -> None:
        """Queue a legal asynchronous lifecycle operation without committing its effects."""
        device = action["device"]
        if (self.pending is not None or device not in self.drives or type(action["id"]) is not str
                or not action["id"] or action["id"] in self.command_ids):
            raise InvalidCycle("invalid asynchronous action")
        state, kind = self.drives[device], action["kind"]
        if type(action["generation"]) is not int or not state.ready or state.generation != action["generation"]:
            raise InvalidCycle("action lacks current-generation authority")
        if kind == "mode":
            valid = state.mode != "effort" and state.active_generation != state.generation and action["mode"] == "effort"
        elif kind == "start":
            valid = state.mode == "effort" and state.active_generation != state.generation and device in self.observing
        elif kind == "transfer":
            valid = self.good_drive(device) and self.claimed != (device, state.generation)
        else:
            valid = False
        if not valid:
            raise InvalidCycle("mode, start, or transfer violated device readback")
        self.command_ids.add(action["id"])
        self.pending = action, self.index + self.case.delays[kind]

    def applied(self, effort: Record | None, dt: float) -> float:
        """Convert an authorized command to physical torque and enforce continuity on that torque."""
        owns = self.claimed is not None and self.good_drive(self.claimed[0])
        if not owns:
            if effort is not None:
                raise InvalidCycle("command was sent without a current physical lease")
            self.gap += 1
            self.max_gap = max(self.max_gap, self.gap)
            if self.gap <= 12:
                return self.torque
            coast = 9.0 * dt
            return math.copysign(max(0.0, abs(self.torque) - coast), self.torque)
        if not isinstance(effort, dict):
            raise InvalidCycle("a usable incumbent missed its output cycle")
        device, current = self.claimed
        if effort["device"] != device or type(effort["generation"]) is not int or effort["generation"] != current:
            raise InvalidCycle("write did not match the physical lease generation")
        command = effort["command"]
        channel = self.channels[device]
        if type(command) not in (int, float) or not math.isfinite(command) or abs(command) > channel["command_limit"] + 1e-8:
            raise InvalidCycle("command exceeded the drive envelope")
        torque = command * channel["gain_nm"] + channel["bias_nm"]
        if abs(torque) > self.max_effort + 1e-8 or abs(torque - self.torque) > self.max_slew * dt + 1e-8:
            raise InvalidCycle("physical effort exceeded its magnitude or measured-cycle slew bound")
        self.gap = 0
        return torque

    def advance(self, reply: Record, period_ns: int) -> None:
        """Apply one reply to the simulated hardware then advance the independent dynamics."""
        if type(reply["cycle"]) is not int or reply["cycle"] != self.index:
            raise InvalidCycle("reply belongs to another cycle")
        dt = period_ns / 1e9
        torque = self.applied(reply["effort"], dt)
        if reply["action"] is not None:
            self.request(reply["action"])
        self.torque = torque
        elapsed = (self.now - self.start) / 1e9
        load = self.case.load * (0.64 if elapsed >= 0.63 else 0.0)
        if 1.55 <= elapsed <= 2.08:
            load -= self.case.load * 1.42
        if elapsed >= 2.9:
            load += self.case.load * 0.74
        if 4.02 <= elapsed < 4.34:
            load -= self.case.load * 0.8
        load += 0.11 * math.sin(7.5 * elapsed + self.case.variant)
        acceleration = (torque - self.case.drag * self.speed - self.case.gravity * math.sin(self.position)
                        + load) / self.case.inertia
        self.speed += acceleration * dt
        self.position += self.speed * dt
        self.now += period_ns
        self.index += 1

def rms(values: list[float]) -> float:
    """Return the root-mean-square position error over the selected sample window."""
    return math.sqrt(sum(error**2 for error in values) / len(values))


def exercise(app: Path, spec: Path, case: Case) -> tuple[dict[str, bool], Record]:
    """Run physical actuator, simulated controller and submitted supervisor in lockstep."""
    checks = dict.fromkeys(METRICS, False)
    plant = Plant(case)
    spec.write_text(json.dumps(plant.configuration()), encoding="utf-8")
    session = Session(app, spec)
    ratios, track = [], []
    held = True
    ready_since, ready_epoch = 0, None
    try:
        for _ in range(402):
            restart = plant.prepare_cycle()
            if restart:
                session.close()
                session = Session(app, spec)
            wanted = plant.drives[plant.wanted]
            observed = ((plant.wanted, wanted.generation)
                        if wanted.ready and plant.wanted in plant.observing else None)
            if observed != ready_epoch:
                ready_since, ready_epoch = plant.index, observed
            if ready_epoch is not None and plant.index - ready_since >= 22:
                held &= plant.claimed == ready_epoch
            packet = plant.cycle_packet()
            elapsed = (plant.now - plant.start) / 1e9
            error = abs(plant.position - packet["target"]["position_rad"])
            if elapsed >= 0.35:
                track.append((elapsed, error))
            reply, duration = session.exchange(packet)
            if duration is not None:
                ratios.append(duration * 1e9 / packet["period_ns"])
            plant.advance(reply, packet["period_ns"])
        session.close(clean=True)
    except (InvalidCycle, OSError, KeyError, TypeError, OverflowError, ValueError, subprocess.TimeoutExpired) as error:
        if not session.child.stdout.closed:
            session.close()
        return checks, {"cycle": plant.index, "error": str(error)}
    p95 = sorted(ratios)[int((len(ratios) - 1) * 0.95)]
    errors = [error for _, error in track]
    final = [error for elapsed, error in track if (plant.now - plant.start) / 1e9 - elapsed <= 0.45]
    checks.update(lease_and_maintenance=held and (case.variant != 1 or plant.reboot is not None),
                  live_effort=plant.max_gap <= 12,
                  trajectory_and_settling=max(errors) <= 0.18 and rms(errors) <= 0.060 and rms(final) <= 0.020,
                  cycle_deadline=p95 <= 1.0)
    return checks, {"maximum_command_gap_cycles": plant.max_gap, "maximum_error_rad": max(errors),
                    "rms_rad": rms(errors), "final_rms_rad": rms(final), "p95_response_to_period_ratio": p95,
                    "restart_in_pending_transfer": plant.reboot is not None}


def malformed_line(app: Path, spec: Path) -> bool:
    """Require stream rejection for future-dated measurements without an output line."""
    plant = Plant(CASES[0])
    spec.write_text(json.dumps(plant.configuration()), encoding="utf-8")
    row = plant.cycle_packet()
    row["measurement"]["time_ns"] = row["time_ns"] + 1
    session = Session(app, spec)
    try:
        session.child.stdin.write((json.dumps(row) + "\n").encode())
        session.child.stdin.close()
        status = session.child.wait(timeout=2)
        return status not in (0, 124) and session.child.stdout.read(1) == b""
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        if session.child.stdin.closed:
            session.selector.close()
            if session.child.poll() is None:
                os.killpg(session.child.pid, signal.SIGKILL)
                session.child.wait(timeout=2)
            session.child.stdout.close()
        else:
            session.close()


def checks_servo(app: Path, scratch: Path) -> tuple[dict[str, dict[str, bool]], Record]:
    """Exercise independent live streams without exposing simulator state to submissions."""
    groups, evidence = {}, {}
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        root = Path(folder)
        root.chmod(0o755)
        for case in CASES:
            groups[case.name], evidence[case.name] = exercise(app, root / (case.name + ".json"), case)
        groups["input"] = {"future_measurement_rejected_without_reply": malformed_line(app, root / "invalid.json")}
    return groups, evidence
