"""Track independent PX4-style offset reset counters."""

from math import isfinite
from typing import Any

Record = dict[str, Any]


def series(value: object, width: int, *, nullable: bool = False) -> list:
    """Validate a numeric sensor vector of known width."""
    if type(value) is not list or len(value) != width:
        raise ValueError("bad sensor vector width")
    if not all(nullable and x is None or type(x) in (float, int) and isfinite(x) for x in value):
        raise ValueError("non-finite sensor value")
    return value


class Estimate:
    """Maintain one stationary reference and the newest truthful position and velocity."""

    def __init__(self) -> None:
        """Start before the first observed frame."""
        self.stamp: int | None = None
        self.publish: int | None = None
        self.offset = [0.0, 0.0, 0.0]
        self.counters: list[int] | None = None
        self.missing = [False, False]
        self.position: list = [None, None, None]
        self.velocity: list = [None, None, None]

    def ingest(self, row: Record) -> bool:
        """Accept a fresh capture, reconcile counters, and honor per-axis validity."""
        capture, publish = row["timestamp_sample"], row["timestamp"]
        if (type(capture) is not int or type(publish) is not int or not 0 <= capture <= publish
                or self.publish is not None and publish < self.publish):
            raise ValueError("malformed publication/acquisition time")
        values, velocity = [series(row[key], 3) for key in ("position", "velocity")]
        counters = [row["xy_reset_counter"], row["z_reset_counter"]]
        if not all(type(c) is int and 0 <= c < 256 for c in counters):
            raise ValueError("counter not an unsigned byte")
        valid = [row["xy_valid"], row["z_valid"]]
        if not all(type(x) is bool for x in valid):
            raise ValueError("invalid validity field")
        delta = series([*series(row["delta_xy"], 2), row["delta_z"]], 3)
        anchor = series(row.get("anchor", [None] * 3), 3, nullable=True)
        self.publish = publish
        if self.stamp is not None and capture <= self.stamp:
            return False
        for j, axes in enumerate(((0, 1), (2,))):
            step = 0 if self.counters is None else (counters[j] - self.counters[j]) % 256
            if step == 1:
                for axis in axes:
                    self.offset[axis] += delta[axis]
            elif step > 1:
                self.missing[j] = True
            if valid[j] and all(anchor[axis] is not None for axis in axes):
                self.missing[j] = False
                for axis in axes:
                    self.offset[axis] = values[axis] - anchor[axis]
            for axis in axes:
                self.position[axis] = values[axis] - self.offset[axis] if valid[j] and not self.missing[j] else None
                self.velocity[axis] = velocity[axis] if self.position[axis] is not None else None
        self.stamp, self.counters = capture, counters
        return True
