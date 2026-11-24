"""Commission clock, temperature, offset and gain from known excitation."""

from csv import DictReader
from dataclasses import dataclass
from itertools import product
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np


REFERENCE_FIELDS = {"timestamp_us", "wx", "wy", "wz", "fx", "fy", "fz"}
CAPTURE_FIELDS = {"device", "stamp_us", "interval_us", "temp_c", "dax", "day", "daz", "dvx", "dvy", "dvz"}


@dataclass
class Device:
    """Fit data expressed relative to the first reference timestamp."""

    bound: np.ndarray
    rotation: np.ndarray
    relative_capture_mid_us: np.ndarray
    ref_origin_us: int
    nominal_duration_s: np.ndarray
    temperature: np.ndarray
    raw_delta: np.ndarray

    def physical(self, point: np.ndarray) -> np.ndarray:
        """Map a unit-box search into offset in microseconds and skew in ppm."""
        return self.bound[:, 0] + point * (self.bound[:, 1] - self.bound[:, 0])

    def capture_time(self, point: np.ndarray) -> tuple[np.ndarray, float]:
        """Convert a candidate clock to physical sample midpoints and duration scale."""
        offset, skew_ppm = self.physical(point)
        scale = 1 + skew_ppm * 1e-6
        return self.ref_origin_us + offset + self.relative_capture_mid_us * scale, scale


def finite(value) -> float:
    """Parse a finite numeric field from a spec or decoded capture."""
    v = float(value)
    if isinstance(value, bool) or not math.isfinite(v):
        raise ValueError("non-finite or non-numeric calibration value")
    return v


def bounds(pair, lower_limit: float = -math.inf) -> list[float]:
    """Read a nonempty closed search interval."""
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError("clock search interval must have two bounds")
    lower, upper = map(finite, pair)
    if lower <= lower_limit or not lower < upper:
        raise ValueError("invalid clock search bounds")
    return [lower, upper]


def rotation(values) -> np.ndarray:
    """Convert a Hamilton wxyz rotation into a body-from-IMU matrix."""
    if not isinstance(values, list) or len(values) != 4:
        raise ValueError("mount rotation must be a four-component quaternion")
    q = np.array([finite(v) for v in values])
    length = np.linalg.norm(q)
    if length == 0 or not np.isfinite(length):
        raise ValueError("mount quaternion has no direction")
    w, x, y, z = q / length
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def csv_rows(path: Path, fields: set[str]):
    """Yield rows of an exact named-column schema."""
    with path.open(newline="") as stream:
        table = DictReader(stream)
        if not table.fieldnames or len(table.fieldnames) != len(fields) or set(table.fieldnames) != fields:
            raise ValueError("commissioning CSV fields differ from the required schema")
        for row in table:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("commissioning CSV row width does not match its schema")
            yield row


def read_spec(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Device]]:
    """Read commissioning inputs and validate their declared timing support."""
    spec = json.loads(path.read_text())
    if not isinstance(spec, dict) or not isinstance(spec.get("devices"), dict) or not spec["devices"]:
        raise ValueError("commissioning spec has no devices")
    timestamps, records = [], []
    for row in csv_rows(path.parent / spec["reference"], REFERENCE_FIELDS):
        stamp = int(row["timestamp_us"])
        if timestamps and stamp <= timestamps[-1]:
            raise ValueError("reference timestamps must strictly increase")
        timestamps.append(stamp)
        records.append([finite(row[k]) for k in ("wx", "wy", "wz", "fx", "fy", "fz")])
    if len(timestamps) < 2:
        raise ValueError("reference needs two or more samples")
    zero = timestamps[0]
    clock = np.array([t - zero for t in timestamps], dtype=float)

    captures: dict[str, list] = {device: [] for device in spec["devices"]}
    unique = set()
    for row in csv_rows(path.parent / spec["captures"], CAPTURE_FIELDS):
        device, stamp = row["device"], int(row["stamp_us"])
        duration = int(row["interval_us"])
        if device not in captures or duration <= 0 or (device, stamp) in unique:
            raise ValueError("invalid or duplicate capture")
        unique.add((device, stamp))
        values = [finite(row[k]) for k in ("dax", "day", "daz", "dvx", "dvy", "dvz")]
        captures[device].append((stamp, duration, finite(row["temp_c"]), values))

    devices = {}
    for serial, source in spec["devices"].items():
        origin = source["clock_origin_us"]
        if not serial or type(origin) is not int:
            raise ValueError("invalid device identifier or clock origin")
        entries = captures[serial]
        device = Device(
            bound=np.array([bounds(source["offset_range_us"]),
                            bounds(source["skew_range_ppm"], -1e6)]),
            rotation=rotation(source["body_from_imu_wxyz"]),
            relative_capture_mid_us=np.array([stamp - origin - span / 2 for stamp, span, _, _ in entries]),
            ref_origin_us=origin - zero,
            nominal_duration_s=np.array([span * 1e-6 for _, span, _, _ in entries]),
            temperature=np.array([temp - 25 for _, _, temp, _ in entries]),
            raw_delta=np.array([values for _, _, _, values in entries]).reshape((-1, 6)),
        )
        if entries:
            for point in product((0.0, 1.0), repeat=2):
                mapped, _ = device.capture_time(np.array(point))
                if mapped.min() < clock[0] or mapped.max() > clock[-1]:
                    raise ValueError("reference does not cover the clock search rectangle")
        devices[serial] = device
    return clock, np.array(records), devices


class Profile:
    """Eliminate each axis's gain and thermal terms for a proposed clock."""

    def __init__(self, clock: np.ndarray, truth: np.ndarray, device: Device):
        self.clock = clock
        self.truth = truth
        self.device = device
        self.nominal_rates = device.raw_delta / device.nominal_duration_s[:, None]
        self.residual_scale = np.maximum(np.std(self.nominal_rates, axis=0), 0.01)
        self.constant_and_thermal = np.stack((np.ones(len(device.temperature)), device.temperature), axis=1)

    def fit(self, point: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        """Return profiled residuals and physical coefficients, or deficient rank."""
        mid, clock_scale = self.device.capture_time(point)
        rates = np.column_stack([np.interp(mid, self.clock, axis) for axis in self.truth.T])
        predicted_input = np.column_stack((rates[:, :3] @ self.device.rotation,
                                           rates[:, 3:] @ self.device.rotation))
        measured = self.nominal_rates / clock_scale
        errors = np.empty_like(measured)
        coefficients = np.empty((3, 6))
        for feature in range(6):
            design = np.column_stack((predicted_input[:, feature], self.constant_and_thermal))
            coefficient, _, rank, _ = np.linalg.lstsq(design, measured[:, feature], rcond=1e-10)
            if rank < 3:
                return None
            errors[:, feature] = measured[:, feature] - design @ coefficient
            coefficients[:, feature] = coefficient
        return (errors / self.residual_scale).ravel(), coefficients

    def derivative(self, point: np.ndarray) -> np.ndarray | None:
        """Estimate the profiled clock Jacobian, using one-sided support at edges."""
        columns = []
        for axis in range(2):
            shift = np.zeros(2)
            shift[axis] = 0.00025
            left, right = np.clip(point - shift, 0, 1), np.clip(point + shift, 0, 1)
            lo, hi = self.fit(left), self.fit(right)
            if lo is None or hi is None:
                return None
            columns.append((hi[0] - lo[0]) / (right[axis] - left[axis]))
        return np.column_stack(columns)

    def best(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Scan the bounded clock domain before a local variable-projection solve."""
        best_loss = math.inf
        point = None
        for grid_point in product(np.linspace(0, 1, 9), repeat=2):
            trial = np.array(grid_point)
            fitted = self.fit(trial)
            if fitted is not None:
                loss = np.dot(fitted[0], fitted[0])
                if loss < best_loss:
                    point, best_loss = trial, loss
        if point is None:
            return None

        current = self.fit(point)
        for _ in range(20):
            jacobian = self.derivative(point)
            if jacobian is None:
                return None
            if np.linalg.svd(jacobian, compute_uv=False)[-1] < 1e-5 * math.sqrt(len(current[0])):
                return None
            displacement = np.linalg.lstsq(jacobian, -current[0], rcond=1e-8)[0]
            if np.linalg.norm(displacement) < 1e-8:
                break
            for reduction in (1, .5, .25, .125, .0625, .03125):
                candidate = np.clip(point + reduction * displacement, 0, 1)
                attempt = self.fit(candidate)
                if attempt is not None and np.dot(attempt[0], attempt[0]) < best_loss:
                    point, current = candidate, attempt
                    best_loss = np.dot(current[0], current[0])
                    break
            else:
                break
        coefficient = current[1]
        if np.any(coefficient[0] <= 0):
            return None
        return self.device.physical(point), coefficient


def parameter_summary(clock: np.ndarray, coefficients: np.ndarray) -> dict:
    """Serialize calibrated rates in sensor axes and physical time units."""
    result = {"offset_us": float(clock[0]), "skew_ppm": float(clock[1])}
    for columns, prefix in ((slice(0, 3), "gyro"), (slice(3, 6), "accel")):
        for row, name in enumerate(("gain", "bias", "temp_slope")):
            result[f"{prefix}_{name}"] = coefficients[row, columns].tolist()
    return result


def commission(spec_path: Path, output_path: Path) -> None:
    """Fit every declared device and publish an atomic commissioning decision."""
    clock, truth, devices = read_spec(spec_path)
    results = {}
    for serial, device in devices.items():
        fit = Profile(clock, truth, device).best() if len(device.temperature) >= 16 else None
        if fit is None:
            results = {}
            break
        results[serial] = parameter_summary(*fit)
    report = {"status": "ok" if results else "unobservable", "devices": results}
    serialized = json.dumps(report, allow_nan=False, indent=2) + "\n"
    with NamedTemporaryFile(mode="w", dir=output_path.parent, prefix=".commission-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(serialized)
            stream.flush()
            os.replace(temporary, output_path)
        finally:
            temporary.unlink(missing_ok=True)
