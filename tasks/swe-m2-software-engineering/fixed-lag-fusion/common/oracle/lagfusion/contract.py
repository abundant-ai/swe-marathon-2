"""Records and validation shared by the batch fusion and durable receiver."""

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import Any

import numpy as np

Json = dict[str, Any]
Array = np.ndarray


def obj(value: object) -> Json:
    """Require a JSON object."""
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def rows(value: object, size: int | None = None) -> list[Any]:
    """Require an array and, when provided, its exact length."""
    if not isinstance(value, list) or (size is not None and len(value) != size):
        raise ValueError("unexpected array shape")
    return value


def integer(value: object, minimum: int | None = 0) -> int:
    """Require an integer within the stated lower bound."""
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("invalid integer")
    return value


def number(value: object, *, positive: bool = False, nonnegative: bool = False) -> float:
    """Require a finite number meeting optional sign bounds."""
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("invalid number")
    if (positive and value <= 0) or (nonnegative and value < 0):
        raise ValueError("number outside allowed sign bounds")
    return float(value)


def name(value: object) -> str:
    """Require a nonempty identifier or report label."""
    if not isinstance(value, str) or not value:
        raise ValueError("invalid identifier")
    return value


def vector(value: object, size: int = 2) -> Array:
    """Parse a finite numeric vector."""
    return np.array([number(item) for item in rows(value, size)])


def matrix(value: object, height: int, width: int) -> Array:
    """Parse a finite numeric matrix."""
    return np.stack([vector(row, width) for row in rows(value, height)])


def covariance(value: object, size: int = 2) -> Array:
    """Validate a symmetric positive definite Gaussian covariance."""
    result = matrix(value, size, size)
    if not np.array_equal(result, result.T):
        raise ValueError("covariance must be symmetric")
    np.linalg.cholesky(result)
    return result


@dataclass(frozen=True)
class Config:
    """Initial prior and the adjacent random-walk model."""

    start: int
    lag: int
    mean: Array
    prior: Array
    process: Array


def read_config(value: object) -> Config:
    """Parse the bounded smoothing configuration."""
    data = obj(value)
    lag = integer(data["lag_ticks"], 1)
    if lag > 24:
        raise ValueError("lag_ticks exceeds 24")
    return Config(integer(data["start_tick"]), lag, vector(data["prior_mean"]),
                  covariance(data["prior_covariance"]), covariance(data["process_covariance"]))


@dataclass(frozen=True)
class Factor:
    """A linear observation covering one tick or two adjacent ticks."""

    first: int
    last: int
    design: Array
    value: Array
    noise: Array

    def encoded(self) -> Json:
        """Encode just the normalized measurement needed to restore the active graph."""
        return {"first": self.first, "last": self.last, "design": self.design.tolist(),
                "value": self.value.tolist(), "noise": self.noise.tolist()}


def load_factor(data: Json) -> Factor:
    """Restore a normalized, active observation from an accepted state file."""
    first, last = integer(data["first"], None), integer(data["last"], None)
    size = len(rows(data["value"]))
    if last - first not in (0, 1) or size not in (1, 2):
        raise ValueError("invalid journaled factor")
    return Factor(first, last, matrix(data["design"], size, 2 * (last - first + 1)),
                  vector(data["value"], size), covariance(data["noise"], size))


def delta_factor(tick: int, value: Array, noise: Array) -> Factor:
    """Create a two-pose displacement factor."""
    eye = np.eye(2)
    return Factor(tick - 1, tick, np.hstack((-eye, eye)), value, noise)


def projection_factor(tick: int, axis: Array, value: float, variance: float) -> Factor:
    """Create a scalar projection on the specified pose."""
    if not np.any(axis):
        raise ValueError("projection axis must be nonzero")
    return Factor(tick, tick, axis.reshape(1, 2), np.array([value]), np.array([[variance]]))


@dataclass(frozen=True)
class Observation:
    """Normalized observation and its acquisition extent, including invalid ranges."""

    first: int
    last: int
    factor: Factor | None


@dataclass(frozen=True)
class Event:
    """Validated replay event, with raw contents available for exact retry checks."""

    op: str
    data: Json
    observation: Observation | None = None


Adapter = Callable[[Json], Observation]


def read_observation(data: Json, adapter: Adapter | None) -> Observation:
    """Normalize a batch factor, optionally using the commissioned sensor adapter."""
    op = name(data["op"])
    if op in ("delta", "position"):
        tick = integer(data["tick"])
        value = vector(data["value"])
        noise = covariance(data["covariance"])
        factor = delta_factor(tick, value, noise) if op == "delta" else Factor(tick, tick, np.eye(2), value, noise)
    elif op == "projection":
        factor = projection_factor(integer(data["tick"]), vector(data["axis"]),
                                   number(data["value"]), number(data["variance"], positive=True))
    elif adapter is not None and op in ("wheel", "imu", "range_pair"):
        return adapter(data)
    else:
        raise ValueError("unknown observation operation")
    return Observation(factor.first, factor.last, factor)


def read_events(value: object, adapter: Adapter | None, *, revisions: bool = False) -> list[Event]:
    """Validate replay events without changing the current time window."""
    events = []
    for raw in rows(value):
        data = obj(raw)
        op = name(data["op"])
        observation = None
        if op == "advance":
            integer(data["tick"])
        elif op == "snapshot":
            name(data["label"])
        elif revisions and op in ("upsert", "retract"):
            name(data["id"])
            integer(data["revision"], 1)
            first, last = (integer(data[key], None) for key in ("first_tick", "last_tick"))
            if last - first not in (0, 1):
                raise ValueError("invalid factor extent")
            if op == "upsert":
                observation = read_observation(obj(data["factor"]), adapter)
                if (first, last) != (observation.first, observation.last):
                    raise ValueError("revision extent differs from observation")
        else:
            observation = read_observation(data, adapter)
        events.append(Event(op, data, observation))
    return events
