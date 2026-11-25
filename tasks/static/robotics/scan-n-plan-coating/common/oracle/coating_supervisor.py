"""Persist coating command authority and reconcile the controller's measured history."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

Document = dict[str, Any]
Receipt = dict[str, Any]


class ProtocolError(ValueError):
    """A published packet cannot change the committed mission state."""


class Dose(Protocol):
    """Candidate estimate accumulated from actually observed material delivery."""

    data: Any

    def qualified(self) -> bool: ...


@dataclass(frozen=True)
class MeasuredDose:
    """The part-local draft dose and its recipe comparison."""

    data: Any
    meets_recipe: bool

    def qualified(self) -> bool:
        """Return whether already observed material satisfies the recipe."""
        return self.meets_recipe


def integer(value: object, field: str) -> int:
    """Parse a nonnegative integer without accepting boolean as an integer."""
    if type(value) is not int or value < 0:
        raise ProtocolError(f"Invalid {field}")
    return value


def identifier(value: object, field: str) -> str:
    """Read a nonempty public command or receipt identity."""
    if not isinstance(value, str) or not value:
        raise ProtocolError(f"Invalid {field}")
    return value


def vector(value: object, field: str) -> list[float]:
    """Read a finite seven-axis state in wire order."""
    if not isinstance(value, list) or len(value) != 7:
        raise ProtocolError(f"Invalid {field}")
    try:
        if not all(type(element) in (int, float) and math.isfinite(element) for element in value):
            raise ProtocolError(f"Invalid {field}")
    except OverflowError as error:
        raise ProtocolError(f"Invalid {field}") from error
    return value


def rejection(packet: object) -> Document:
    """Return the disclosed negative acknowledgment without a command."""
    sequence = packet.get("seq") if isinstance(packet, dict) else None
    return {"seq": sequence if type(sequence) is int and sequence >= 0 else None,
            "status": "rejected", "command": None}


def start_state(job: Document, registration: Document) -> Document:
    """Create an empty journal for a new coating mission."""
    return {
        "job_id": job["job_id"], "next_seq": 0, "now_ns": 0, "revision": job["scene_revision"],
        "world_collision": job["world_collision"], "registration": registration,
        "issued": {}, "receipts": {}, "active": None, "stop_sent": {}, "next_id": 1,
        "previous": None, "reply": None,
    }


def read_controller(packet: Document) -> Document:
    """Validate fields used to decide whether motion authority may be issued."""
    report = packet.get("controller")
    if not isinstance(report, dict):
        raise ProtocolError("Missing controller observation")
    measured = integer(report.get("measured_ns"), "measured_ns")
    if report.get("mode") not in ("idle", "running", "stopping", "stopped"):
        raise ProtocolError("Unknown controller mode")
    if measured > packet["now_ns"]:
        raise ProtocolError("Future controller observation")
    vector(report.get("q_rad"), "q_rad")
    vector(report.get("qd_rad_s"), "qd_rad_s")
    command_id = report.get("command_id")
    through = report.get("trace_through_ns")
    if command_id is None and (report["mode"] != "idle" or through is not None):
        raise ProtocolError("Controller motion lacks an identity")
    if command_id is not None:
        identifier(command_id, "command_id")
        if integer(through, "trace_through_ns") > packet["now_ns"]:
            raise ProtocolError("Future trace")
    return report


def apply_scene(state: Document, change: object) -> bool:
    """Apply a higher revision for subsequent motion, keeping older command snapshots."""
    if change is None:
        return False
    if not isinstance(change, dict) or not isinstance(change.get("world_collision"), list):
        raise ProtocolError("Malformed scene update")
    revision = integer(change.get("scene_revision"), "scene_revision")
    if revision <= state["revision"]:
        raise ProtocolError("Scene must advance")
    registration = change.get("registration")
    if registration is not None:
        if (not isinstance(registration, dict) or registration.get("job_id") != state["job_id"]
                or registration.get("status") not in ("review", "registered")):
            raise ProtocolError("Invalid replacement registration")
        state["registration"] = registration
    state["revision"] = revision
    state["world_collision"] = change["world_collision"]
    return True


def apply_receipts(state: Document, inputs: object, period: int, maximum_flow: float, now_ns: int) -> None:
    """Merge valid disjoint measured intervals and reject conflicting duplicates."""
    if not isinstance(inputs, list):
        raise ProtocolError("Receipt batch must be an array")
    receipts = state["receipts"]
    for item in inputs:
        if not isinstance(item, dict):
            raise ProtocolError("Receipt must be an object")
        key = identifier(item.get("receipt_id"), "receipt_id")
        if key in receipts:
            if item != receipts[key]:
                raise ProtocolError("Conflicting receipt")
            continue
        motion_id = identifier(item.get("command_id"), "command_id")
        authority = state["issued"].get(motion_id)
        revision = integer(item.get("scene_revision"), "scene_revision")
        if authority is None or revision != authority["revision"]:
            raise ProtocolError("Unknown receipt authority")
        rows = item.get("samples")
        if not isinstance(rows, list) or len(rows) < 2:
            raise ProtocolError("Incomplete receipt")
        expected = None
        for row in rows:
            if not isinstance(row, dict):
                raise ProtocolError("Invalid process sample")
            tick = integer(row.get("t_ns"), "t_ns")
            if tick < authority["issued_ns"] or tick > now_ns or (tick - authority["issued_ns"]) % period:
                raise ProtocolError("Off-clock receipt")
            if expected is not None and tick != expected:
                raise ProtocolError("Unmeasured interval")
            expected = tick + period
            vector(row.get("q_rad"), "q_rad")
            vector(row.get("qd_rad_s"), "qd_rad_s")
            amount = row.get("flow_ml_s")
            if type(amount) not in (int, float) or not 0 <= amount <= maximum_flow:
                raise ProtocolError("Invalid measured flow")
        start, end = rows[0]["t_ns"], rows[-1]["t_ns"]
        for previous in receipts.values():
            if previous["command_id"] != motion_id:
                continue
            lo, hi = previous["samples"][0]["t_ns"], previous["samples"][-1]["t_ns"]
            if start < hi and lo < end:
                raise ProtocolError("Overlapping receipts")
        receipts[key] = item


def full_trace(state: Document, command: str, end: int) -> bool:
    """Determine whether every measured interval is available through the stop."""
    available = sorted(
        (item for item in state["receipts"].values() if item["command_id"] == command),
        key=lambda item: item["samples"][0]["t_ns"],
    )
    boundary = state["issued"][command]["issued_ns"]
    for item in available:
        start = item["samples"][0]["t_ns"]
        if start != boundary:
            return False
        boundary = item["samples"][-1]["t_ns"]
    return boundary == end


def authority_id(state: Document) -> str:
    """Allocate and commit a monotonically increasing command identity."""
    result = f"coating-{state['next_id']}"
    state["next_id"] += 1
    return result


def decide(
    job: Document, state: Document, packet: Document, report: Document, changed: bool,
    measure: Callable[[Document], Dose], plan: Callable[[Document, Document, list[float], Dose, Document], Document],
) -> Document:
    """Choose stop, wait, execute, or a terminal outcome from accepted observations."""
    result = {"seq": packet["seq"], "status": "waiting", "command": None}
    now = packet["now_ns"]
    motion = job["motion"]
    permit = packet["spray_permitted"]
    fresh = now - report["measured_ns"] <= motion["state_max_age_ns"]
    stopped = report["mode"] in ("idle", "stopped") and all(
        abs(speed) <= motion["stop_velocity_rad_s"] for speed in report["qd_rad_s"]
    )
    command = state["active"]
    if command is not None:
        revoked = changed or state["issued"][command]["revision"] != state["revision"] or not fresh or not permit
        matching = report["command_id"] == command
        if not stopped or not matching:
            if revoked and command not in state["stop_sent"]:
                stop_id = authority_id(state)
                state["stop_sent"][command] = stop_id
                result["command"] = {"kind": "stop", "command_id": stop_id, "motion_id": command}
            elif not revoked and report["mode"] == "running" and matching:
                result["status"] = "ready"
            return result
        if not fresh or not full_trace(state, command, report["trace_through_ns"]):
            return result
        state["issued"][command]["ended_ns"] = report["trace_through_ns"]
        state["active"] = None
    if not fresh or not stopped:
        return result
    prior = measure(state)
    if prior.qualified() and abs(report["q_rad"][6] - job["final_positioner_rad"]) <= 1e-8:
        result["status"] = "complete"
        return result
    remaining = motion["max_duration_ns"] - now
    if remaining <= 0:
        result["status"] = "blocked"
        return result
    registration = state["registration"]
    if not permit or registration["status"] != "registered":
        return result
    adjusted_job = {
        **job, "world_collision": state["world_collision"], "scene_revision": state["revision"],
        "start_q_rad": report["q_rad"], "motion": {**motion, "max_duration_ns": remaining},
    }
    proposed = plan(adjusted_job, registration, report["qd_rad_s"], prior, state)
    if proposed["status"] == "blocked":
        result["status"] = "blocked"
        return result
    command = authority_id(state)
    state["active"] = command
    state["issued"][command] = {
        "issued_ns": now, "revision": state["revision"], "world_collision": state["world_collision"],
        "registration": registration, "trajectory": proposed["trajectory"],
    }
    result["status"] = "ready"
    result["command"] = {
        "kind": "execute", "command_id": command, "scene_revision": state["revision"],
        "trajectory": proposed["trajectory"],
    }
    return result


def transact(
    job: Document, state: Document, packet: object, *,
    measure: Callable[[Document], Dose],
    plan: Callable[[Document, Document, list[float], Dose, Document], Document],
) -> tuple[Document, Document]:
    """Return the accepted next journal and its reply, or preserve state on error."""
    try:
        if not isinstance(packet, dict):
            raise ProtocolError("Packet must be an object")
        sequence = integer(packet.get("seq"), "seq")
        if sequence == state["next_seq"] - 1 and packet == state["previous"]:
            return state, state["reply"]
        if sequence != state["next_seq"]:
            raise ProtocolError("Unexpected sequence")
        now = integer(packet.get("now_ns"), "now_ns")
        if now < state["now_ns"] or type(packet.get("spray_permitted")) is not bool:
            raise ProtocolError("Invalid mission clock or permit")
        if "scene" not in packet:
            raise ProtocolError("Missing scene field")
        report = read_controller(packet)
        draft = deepcopy(state)
        changed = apply_scene(draft, packet["scene"])
        apply_receipts(draft, packet.get("receipts"), job["motion"]["control_period_ns"],
                       job["recipe"]["max_flow_ml_s"], now)
        reply = decide(job, draft, packet, report, changed, measure, plan)
        draft.update(next_seq=sequence + 1, now_ns=now, previous=packet, reply=reply)
        return draft, reply
    except ProtocolError:
        return state, rejection(packet)


def persist(destination: Path, journal: Document) -> None:
    """Durably replace the current journal before publishing the reply."""
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, delete=False) as stream:
        pending = Path(stream.name)
        try:
            json.dump(journal, stream, allow_nan=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            pending.replace(destination)
            fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            pending.unlink(missing_ok=True)


def reject_constant(value: str) -> None:
    """Reject non-JSON NaN and infinity literals before they reach the journal."""
    raise ValueError(f"Invalid JSON constant {value}")


def run(job: Document, registration: Document, state_dir: Path) -> None:
    """Serve supervisor requests using only the public job and measured receipts."""
    from coating_planner import CoatingDose, plan_residual

    state_dir.mkdir(exist_ok=True)
    destination = state_dir / "journal.json"
    journal = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else start_state(job, registration)
    if journal["job_id"] != job["job_id"]:
        raise ValueError("State directory belongs to a different job")

    meter = CoatingDose(job)
    cached: tuple[tuple[str, ...], MeasuredDose] | None = None

    def measure(state: Document) -> MeasuredDose:
        """Rebuild part-local dose from the issuing motion's immutable scene."""
        nonlocal cached
        keys = tuple(sorted(state["receipts"]))
        if cached is not None and cached[0] == keys:
            return cached[1]
        material = meter.empty()
        rows = sorted(state["receipts"].values(), key=lambda receipt: receipt["samples"][0]["t_ns"])
        for receipt in rows:
            authority = state["issued"][receipt["command_id"]]
            scene_job = {**job, "world_collision": authority["world_collision"]}
            material = meter.accumulate(
                receipt["samples"], registration=authority["registration"], scene_job=scene_job, prior=material,
            )
        observed = MeasuredDose(material, bool(meter.qualifies(material)))
        cached = (keys, observed)
        return observed

    def plan(
        adjusted: Document, mounted: Document, speed: list[float], prior: Dose, state: Document,
    ) -> Document:
        """Warm-start from the interrupted sweep, with geometric replanning as fallback."""
        from coating_resume import resume_tail

        stopped = [(key, motion) for key, motion in state["issued"].items() if "ended_ns" in motion]
        if stopped and not prior.qualified():
            key, last = max(stopped, key=lambda entry: entry[1]["issued_ns"])
            if key in state["stop_sent"]:
                receipts = (entry for entry in state["receipts"].values() if entry["command_id"] == key)
                continuation = resume_tail(adjusted, mounted, speed, prior.data, last, receipts)
                if continuation is not None:
                    return continuation
        return plan_residual(adjusted, mounted, start_velocity_rad_s=speed, prior=prior.data)

    for line in sys.stdin:
        try:
            packet = json.loads(line, parse_constant=reject_constant)
        except ValueError:
            packet = None
        updated, reply = transact(job, journal, packet, measure=measure, plan=plan)
        if updated is not journal:
            persist(destination, updated)
            journal = updated
        print(json.dumps(reply, allow_nan=False), flush=True)
