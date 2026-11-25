"""Validate a harness controller decision against its observed motion authority."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any, Literal

Operation = Literal["running", "complete", "blocked"]
Mode = Literal["pinch", "slide"]


@dataclass(frozen=True)
class ObservationRef:
    """The current observed packet identity and detections available to the gripper."""

    observation_id: str
    generation: int
    visible_points: frozenset[str]


@dataclass(frozen=True)
class MotionLimits:
    """Public wire bounds for choosing a joint target."""

    lower_rad: tuple[float, ...]
    upper_rad: tuple[float, ...]
    max_command_ticks: int
    max_probe_ticks: int | None = None


@dataclass(frozen=True)
class Action:
    """One validated motion, grip, or hold request."""

    kind: str
    target_q_rad: tuple[float, ...] = ()
    ticks: int = 0
    point_id: str | None = None
    mode: Mode | None = None


@dataclass(frozen=True)
class Response:
    """An accepted decision tied to the observed state and logical motion ID."""

    observation_id: str
    generation: int
    command_id: str
    status: Operation
    action: Action
    reason: str | None = None


def integer(value: object, field: str) -> int:
    """Read a nonnegative JSON integer without accepting boolean values."""
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def identifier(value: object, field: str) -> str:
    """Read a nonempty wire identity."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def joint_target(raw: object, limits: MotionLimits) -> tuple[float, ...]:
    """Read the declared joint order and reject values outside its public bounds."""
    if not isinstance(raw, list) or len(raw) != len(limits.lower_rad):
        raise ValueError("target_q_rad must match the job joint order")
    q = []
    for value, lower, upper in zip(raw, limits.lower_rad, limits.upper_rad, strict=True):
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("target_q_rad exceeds a published joint bound")
        q.append(float(value))
    return tuple(q)


def grip_mode(raw: object) -> Mode:
    """Read one of the two supported gripping modes."""
    if raw == "pinch":
        return "pinch"
    if raw == "slide":
        return "slide"
    raise ValueError("Unknown grip mode")


def parse_action(raw: object, observed: ObservationRef, limits: MotionLimits) -> Action:
    """Validate syntactic actuator eligibility independently of plant execution.

    This checks the public contract for one request. The plant owns collisions,
    gripping contact, actual motion limits, and later receipt identities.
    """
    if not isinstance(raw, Mapping):
        raise ValueError("action must be an object")
    kind = raw.get("kind")
    if kind in ("move", "probe"):
        bound = limits.max_command_ticks
        if kind == "probe":
            if limits.max_probe_ticks is None:
                raise ValueError("No probe has been authorized at this checkpoint")
            bound = min(bound, limits.max_probe_ticks)
        ticks = integer(raw.get("ticks"), "ticks")
        if not 1 <= ticks <= bound:
            raise ValueError("ticks exceeds the action bounds")
        return Action(kind, target_q_rad=joint_target(raw.get("target_q_rad"), limits), ticks=ticks)
    if kind == "acquire":
        point = identifier(raw.get("point_id"), "point_id")
        if point not in observed.visible_points:
            raise ValueError("A grasp requires a current observed point")
        return Action(kind, point_id=point, mode=grip_mode(raw.get("mode")))
    if kind == "set_mode":
        return Action(kind, mode=grip_mode(raw.get("mode")))
    if kind in ("release", "hold"):
        return Action(kind)
    raise ValueError("Unknown motion action")


def parse_response(raw: object, observed: ObservationRef, limits: MotionLimits) -> Response:
    """Parse one response without granting motion from another observation or generation."""
    if not isinstance(raw, Mapping):
        raise ValueError("Response must be an object")
    observation_id = identifier(raw.get("observation_id"), "observation_id")
    generation = integer(raw.get("generation"), "generation")
    if observation_id != observed.observation_id or generation != observed.generation:
        raise ValueError("Response does not belong to the current observation")
    status = raw.get("status")
    if status not in ("running", "complete", "blocked"):
        raise ValueError("Unknown operation status")
    reason = raw.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("reason must be a string")
    action = parse_action(raw.get("action"), observed, limits)
    if status != "running" and action.kind != "hold":
        raise ValueError("Terminal responses must hold position")
    return Response(observation_id, generation, identifier(raw.get("command_id"), "command_id"), status, action, reason)
