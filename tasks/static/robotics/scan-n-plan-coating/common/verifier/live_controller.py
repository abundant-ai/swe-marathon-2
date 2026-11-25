"""Trusted ideal-tracking controller with independently measured motion and flow."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import math
from typing import Any

from trajectory import AXES, Knot, Segment, Vector, segments


Document = dict[str, Any]


def wire_sample(knot: Knot) -> Document:
    """Encode a measured sample using an absolute integer clock and held flow."""
    return {"t_ns": knot.t_ns, "q_rad": list(knot.q_rad), "qd_rad_s": list(knot.qd_rad_s), "flow_ml_s": knot.flow_ml_s}


def brake_knots(now_ns: int, q_rad: Vector, qd_rad_s: Vector, motion: Mapping[str, Any]) -> tuple[Knot, Knot]:
    """Generate a constant-deceleration stop aligned with the controller cadence.

    Each joint begins from observed position and velocity. A spare tick
    below the acceleration limit leaves room for floating-point error in
    the Hermite tests. Flow goes to zero at the braking boundary.
    """
    period_ns = motion["control_period_ns"]
    seconds = max(abs(speed) / limit for speed, limit in zip(qd_rad_s, motion["max_acceleration_rad_s2"], strict=True))
    ticks = math.ceil(seconds / (period_ns * 1e-9)) + 1
    stop_after_ns = ticks * period_ns
    half_seconds = stop_after_ns * 0.5e-9
    rest = tuple(q + half_seconds * speed for q, speed in zip(q_rad, qd_rad_s, strict=True))
    return Knot(now_ns, q_rad, qd_rad_s, 0.0), Knot(now_ns + stop_after_ns, rest, (0.0,) * AXES, 0.0)


@dataclass
class ObservedMotion:
    """The controller's own measured material trace for one accepted motion."""

    command_id: str
    scene_revision: int
    issued_ns: int
    samples: list[Knot] = field(default_factory=list)

    def receipts(self, chunks: int = 1) -> list[Document]:
        """Split the completed trace into consecutive disjoint half-open receipts."""
        intervals = len(self.samples) - 1
        if chunks < 1 or intervals < chunks:
            raise ValueError("Cannot split the measured trace into nonempty receipts")
        result = []
        for number in range(chunks):
            left = number * intervals // chunks
            right = (number + 1) * intervals // chunks
            result.append({"receipt_id": f"{self.command_id}:sample:{left}-{right}",
                           "command_id": self.command_id, "scene_revision": self.scene_revision,
                           "samples": [wire_sample(knot) for knot in self.samples[left:right + 1]]})
        return result


class LiveController:
    """Advance only accepted trajectories and independently inhibit their material flow.

    Motion follows the published Hermite polynomials at exact controller
    ticks. The actual valve signal can differ from the request when the
    independent interlock inhibits spraying or the fixture calibrates a
    non-unit pump gain. Integrate the held measured valve signal, rather
    than controller acknowledgments, to time material-triggered faults.
    """

    def __init__(self, job: Mapping[str, Any], *, flow_gain: float = 1.0) -> None:
        """Start the simulated plant at the known idle commissioning state."""
        if not math.isfinite(flow_gain) or not 0 < flow_gain <= 1:
            raise ValueError("Expected a positive measured pump gain at most one")
        self.motion = job["motion"]
        self.period_ns = self.motion["control_period_ns"]
        self.q = tuple(float(item) for item in job["start_q_rad"])
        self.qd = (0.0,) * AXES
        self.now_ns = 0
        self.mode = "idle"
        self.permitted = True
        self.current: ObservedMotion | None = None
        self.finished: list[ObservedMotion] = []
        self.emitted_ml = 0.0
        self.requested_ml = 0.0
        self.pump_gain = flow_gain
        self._path: tuple[Segment, ...] = ()
        self._path_index = 0
        self._requested_flow = 0.0

    def observation(self, *, measured_ns: int | None = None) -> Document:
        """Publish current q/dq, physical mode, active ID and the trace horizon."""
        last = self.current
        return {
            "measured_ns": self.now_ns if measured_ns is None else measured_ns,
            "q_rad": list(self.q), "qd_rad_s": list(self.qd), "mode": self.mode,
            "command_id": None if last is None else last.command_id,
            "trace_through_ns": None if last is None else last.samples[-1].t_ns,
        }

    def set_permit(self, permit: bool) -> None:
        """Apply the hardware interlock at the current half-open sample boundary."""
        self.permitted = permit
        if self.mode in ("running", "stopping") and self.current is not None:
            self.current.samples[-1] = replace(self.current.samples[-1], flow_ml_s=self._actual_flow())

    def accept(self, command_id: str, scene_revision: int, plan: tuple[Knot, ...]) -> None:
        """Begin a legal accepted trajectory and initialize its physical receipt trace."""
        self.current = ObservedMotion(command_id, scene_revision, self.now_ns)
        absolute = tuple(replace(knot, t_ns=self.now_ns + knot.t_ns) for knot in plan)
        self._path = tuple(segments(absolute))
        self._path_index = 0
        self.mode = "running"
        self._requested_flow = absolute[0].flow_ml_s
        self.current.samples.append(Knot(self.now_ns, self.q, self.qd, self._actual_flow()))

    def stop(self, profile: tuple[Knot, Knot]) -> None:
        """Apply a configured braking profile to the current authorized motion."""
        if self.mode != "running" or self.current is None:
            raise ValueError("Cannot stop a motion that is not running")
        self._path = tuple(segments(profile))
        self._path_index = 0
        self.mode = "stopping"
        self._requested_flow = 0.0
        self.current.samples[-1] = replace(self.current.samples[-1], flow_ml_s=0.0)

    def _actual_flow(self) -> float:
        """Return the measured valve flow after independent plant inhibition."""
        if not self.permitted or self.mode != "running":
            return 0.0
        return self._requested_flow * self.pump_gain

    def advance(self, periods: int = 1) -> None:
        """Advance the mission and, while active, collect every controller sample."""
        if type(periods) is not int or periods < 1:
            raise ValueError("Expected a positive integer number of controller periods")
        if self.mode in ("idle", "stopped"):
            self.now_ns += self.period_ns * periods
            return
        for _ in range(periods):
            self.now_ns += self.period_ns
            if self.mode not in ("running", "stopping"):
                continue
            record = self.current
            assert record is not None
            dt = self.period_ns * 1e-9
            self.requested_ml += dt * self._requested_flow
            self.emitted_ml += dt * record.samples[-1].flow_ml_s
            segment = self._path[self._path_index]
            if self.now_ns == segment.right.t_ns:
                self.q, self.qd = segment.right.q_rad, segment.right.qd_rad_s
                self._requested_flow = segment.right.flow_ml_s
                self._path_index += 1
                if self._path_index == len(self._path):
                    self.mode = "stopped"
                    self._requested_flow = 0.0
            else:
                fraction = (self.now_ns - segment.left.t_ns) / (segment.right.t_ns - segment.left.t_ns)
                self.q, self.qd = segment.at(fraction)
            record.samples.append(Knot(self.now_ns, self.q, self.qd, self._actual_flow()))
            if self.mode == "stopped":
                self.finished.append(record)
