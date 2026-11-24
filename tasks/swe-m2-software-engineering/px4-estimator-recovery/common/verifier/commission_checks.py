"""Generate and independently inspect asynchronous inertial commissioning cases."""

from csv import writer
from json import dumps, loads
from math import cos, isclose, isfinite, sin, sqrt
from pathlib import Path
from random import Random
from subprocess import DEVNULL, run
import sys

from transport import candidate_environment, identity, require


COMMISSION_CASES = [
    {"name": "two-asynchronous-inertial-units", "variant": 0},
    {"name": "large-clock-origin-and-reversed-drift", "variant": 1},
    {"name": "mounted-imu-with-independent-thermal-profile", "variant": 2},
    {"name": "independent-skews-near-clock-search-boundaries", "variant": 3},
    {"name": "static-bench-cannot-identify-intrinsics", "variant": "static"},
    {"name": "affine-motion-cannot-identify-clock", "variant": "affine"},
    {"name": "invalid-capture-preserves-calibration-output", "variant": "invalid"},
]

REFERENCE_HEADER = ("timestamp_us", "wx", "wy", "wz", "fx", "fy", "fz")
CAPTURE_HEADER = ("device", "stamp_us", "interval_us", "temp_c", "dax", "day", "daz", "dvx", "dvy", "dvz")

PARAMETER_TOLERANCES = {
    "offset_us": 900.0,
    "skew_ppm": 28.0,
    "gyro_gain": 0.003,
    "accel_gain": 0.004,
    "gyro_bias": 0.009,
    "accel_bias": 0.026,
    "gyro_temp_slope": 0.00055,
    "accel_temp_slope": 0.0013,
}


def cross(left: list[float], right: list[float]) -> list[float]:
    """Return the independent three-dimensional cross product."""
    a, b, c = left
    x, y, z = right
    return [b * z - c * y, c * x - a * z, a * y - b * x]


def rotate(q: list[float], value: list[float]) -> list[float]:
    """Rotate a vector by a known normalized Hamilton quaternion."""
    w, *axis = q
    first = cross(axis, value)
    second = cross(axis, first)
    return [x + 2 * (w * y + z) for x, y, z in zip(value, first, second, strict=True)]


def inverse(q: list[float]) -> list[float]:
    """Invert a unit quaternion."""
    return [q[0], *(-x for x in q[1:])]


def truth(variant: int | str, seconds: float, holdout: bool = False) -> list[float]:
    """Return multiaxis bench motion at the IMU point in the body frame."""
    if variant == "static":
        return [0.0, 0.0, 0.0, 0.0, 0.0, -9.81]
    if variant == "affine":
        return [(.018 + .006 * i) * seconds + .1 * i for i in range(6)]
    index = variant if isinstance(variant, int) else 0
    bias = [0.03, -0.08, 0.44, 0.13, -0.31, -9.54]
    amplitude = [1.22, .79, 1.61, 3.7, 3.1, 2.6]
    frequencies = [.86, 1.48, 2.06, 1.91, .67, 1.14]
    signal = []
    for i, (base, gain, frequency) in enumerate(zip(bias, amplitude, frequencies, strict=True)):
        a = seconds * frequency * (1.28 if holdout else 1.0) + .29 * index + .7 * i
        b = seconds * (2.55 + .39 * i) - .16 * index + (1.44 if holdout else .73)
        c = seconds * (.168 + .034 * i) + .23 * index + (.59 if holdout else 0.0)
        signal.append(base + gain * (sin(a) + .47 * cos(b) + .21 * sin(c)))
    return signal


def sample_truth(variant: int | str, elapsed_us: float, holdout: bool = False) -> list[float]:
    """Use the independently authored 10 ms reference grid's interpolation."""
    index = int(elapsed_us // 10_000)
    fraction = elapsed_us / 10_000 - index
    low = truth(variant, index / 100.0, holdout)
    high = truth(variant, (index + 1) / 100.0, holdout)
    return [q + fraction * (r - q) for q, r in zip(low, high, strict=True)]


def device_calibration(
    index: int,
    origin: int,
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Author two differently mounted units with independently perturbed electronics."""
    rng = Random(9519 + index * 31337)
    metadata, parameters = {}, {}
    for order, serial in enumerate(("imu-port", "imu-starboard")):
        axis = [rng.uniform(-1, 1) for _ in range(3)]
        norm = sqrt(sum(x * x for x in axis))
        angle = rng.uniform(.30, 1.05)
        mount = [cos(angle / 2), *(sin(angle / 2) * x / norm for x in axis)]
        sign = (-1) ** (index + order)
        chosen_offset = sign * rng.uniform(12_000, 43_000)
        chosen_skew = -sign * rng.uniform(320, 795)
        if index == 3:
            chosen_offset, chosen_skew = ((50_800, -1004), (-55_300, 1083))[order]
        metadata[serial] = {
            "clock_origin_us": origin,
            "body_from_imu_wxyz": mount,
            "offset_range_us": [-52_000, 52_000] if order == 0 else [-57_000, 63_000],
            "skew_range_ppm": [-1050.0, 1120.0],
        }
        parameters[serial] = {
            "offset_us": chosen_offset,
            "skew_ppm": chosen_skew,
            "gyro_gain": [rng.uniform(.962, 1.052) for _ in range(3)],
            "accel_gain": [rng.uniform(.951, 1.06) for _ in range(3)],
            "gyro_bias": [rng.uniform(-.076, .076) for _ in range(3)],
            "accel_bias": [rng.uniform(-.22, .22) for _ in range(3)],
            "gyro_temp_slope": [rng.uniform(-.0048, .0048) for _ in range(3)],
            "accel_temp_slope": [rng.uniform(-.021, .021) for _ in range(3)],
        }
    return metadata, parameters


def make_kit(root: Path, variant: int | str = 0) -> dict:
    """Generate training files and return private coefficients for a later flight."""
    root.mkdir(parents=True, exist_ok=True)
    index = variant if isinstance(variant, int) else 0
    base_time = 71_500_000 + index * 901_231
    if index % 3 == 1:
        base_time += 17_500_000_000_000
    metadata, parameters = device_calibration(index, base_time)
    if variant == "affine":
        for device in metadata.values():
            device["body_from_imu_wxyz"] = [1.0, 0.0, 0.0, 0.0]
    reference = root / "reference.csv"
    with reference.open("w", newline="") as stream:
        table = writer(stream)
        table.writerow(REFERENCE_HEADER)
        for i in range(-25, 6151):
            table.writerow([base_time + i * 10_000, *truth(variant, i / 100)])
    rng = Random(47195 + index * 19)
    observations = []
    for order, (serial, data) in enumerate(metadata.items()):
        calibration = parameters[serial]
        scale = 1 + calibration["skew_ppm"] * 1e-6
        for i in range(520 + order * 40):
            elapsed = 240_000 + i * (113_333 if order == 0 else 105_750) + rng.randint(-15_000, 15_000)
            interval = rng.randint(4800, 14_000)
            temperature = 29 + 7.1 * sin(i / 51.0 + order) + 2.2 * cos(i / 19.0) + .007 * i
            middle = elapsed - interval / 2
            at = middle + calibration["offset_us"] + (scale - 1) * middle
            rates = sample_truth(variant, at)
            fields = []
            for first, kind in ((0, "gyro"), (3, "accel")):
                sensor_rate = rotate(inverse(data["body_from_imu_wxyz"]), rates[first:first + 3])
                for axis, rate in enumerate(sensor_rate):
                    measured = (rate * calibration[kind + "_gain"][axis] + calibration[kind + "_bias"][axis]
                                + (temperature - 25) * calibration[kind + "_temp_slope"][axis])
                    if isinstance(variant, int):
                        measured += rng.gauss(0, 0.0011 if kind == "gyro" else 0.0058)
                    fields.append(measured * interval * scale * 1e-6)
            observations.append([serial, base_time + elapsed, interval, temperature, *fields])
    rng.shuffle(observations)
    if variant == "invalid":
        observations[-1][2] = 0
    captures = root / "captures.csv"
    with captures.open("w", newline="") as stream:
        table = writer(stream)
        table.writerow(CAPTURE_HEADER)
        table.writerows(observations)
    spec = root / "spec.json"
    spec.write_text(dumps({"reference": reference.name, "captures": captures.name, "devices": metadata}) + "\n")
    return {"spec": spec, "parameters": parameters, "devices": metadata}


def parameter_error(value, expected: dict, device: str) -> None:
    """Check the proposed physical calibration against independently planted parameters."""
    require(isinstance(value, dict) and value.keys() == expected.keys(), f"{device}: calibration fields differ")
    for field, target in expected.items():
        observed = value[field]
        candidates = observed if isinstance(observed, list) else [observed]
        targets = target if isinstance(target, list) else [target]
        require(len(candidates) == len(targets)
                and all(type(v) in (int, float) and isfinite(v) for v in candidates),
                f"{device}: malformed {field}")
        require(all(isclose(v, goal, abs_tol=PARAMETER_TOLERANCES[field], rel_tol=0)
                    for v, goal in zip(candidates, targets, strict=True)),
                f"{device}: {field} outside independent commissioning tolerance")


def heldout_error(kit: dict, estimates: dict, variant: int) -> dict[str, float]:
    """Observe corrected readings and timestamps on unrelated motion and temperatures."""
    rng = Random(9232 + variant)
    maxima = {"clock_us": 0.0, "gyro_rad_s": 0.0, "accel_m_s2": 0.0}
    for device, data in kit["devices"].items():
        actual = kit["parameters"][device]
        estimate = estimates[device]
        mount = data["body_from_imu_wxyz"]
        actual_scale = 1 + actual["skew_ppm"] * 1e-6
        estimate_scale = 1 + estimate["skew_ppm"] * 1e-6
        for _ in range(90):
            midpoint = rng.uniform(61_000_000, 105_000_000)
            temperature = rng.uniform(18.0, 48.0)
            elapsed_actual = actual["offset_us"] + midpoint * actual_scale
            elapsed_estimated = estimate["offset_us"] + midpoint * estimate_scale
            maxima["clock_us"] = max(maxima["clock_us"], abs(elapsed_actual - elapsed_estimated))
            rates = sample_truth(variant, elapsed_actual, holdout=True)
            for first, kind, metric in ((0, "gyro", "gyro_rad_s"), (3, "accel", "accel_m_s2")):
                body = rates[first:first + 3]
                sensor = rotate(inverse(mount), body)
                corrected = []
                for axis, rate in enumerate(sensor):
                    raw = (rate * actual[kind + "_gain"][axis] + actual[kind + "_bias"][axis]
                           + (temperature - 25) * actual[kind + "_temp_slope"][axis])
                    calibrated = ((raw * actual_scale / estimate_scale - estimate[kind + "_bias"][axis]
                                   - (temperature - 25) * estimate[kind + "_temp_slope"][axis])
                                  / estimate[kind + "_gain"][axis])
                    corrected.append(calibrated)
                aligned = rotate(mount, corrected)
                err = sqrt(sum((a - b) ** 2 for a, b in zip(aligned, body, strict=True)))
                maxima[metric] = max(maxima[metric], err)
    require(maxima["clock_us"] < 3000, "clock calibration did not extrapolate on held-out motion")
    require(maxima["gyro_rad_s"] < .038, "corrected gyro readings missed held-out motion")
    require(maxima["accel_m_s2"] < .10, "corrected accelerometer readings missed held-out motion")
    return maxima


def check_commission(app: Path, root: Path, case: dict) -> dict:
    """Run the actual packaged commissioning command and inspect its output."""
    kit = make_kit(root / "inputs", case["variant"])
    scratch = root / "candidate"
    scratch.mkdir()
    scratch.chmod(0o777)
    output = scratch / "calibration.json"
    permissions = {"cwd": app, "stdout": DEVNULL, "stderr": DEVNULL, "timeout": 25,
                   "env": candidate_environment(scratch), **identity()}
    command = [sys.executable, "-B", "-m", "px4_recovery", "commission"]
    if case["variant"] == "invalid":
        healthy = make_kit(root / "first-valid-capture")
        result = run([*command,"--spec",str(healthy["spec"]),"--output",str(output)], **permissions)
        require(result.returncode == 0 and output.is_file() and not output.is_symlink()
                and output.stat().st_size < 64_000,
                "atomic recovery needs an existing valid candidate calibration")
        sentinel = output.read_bytes()
        report = loads(sentinel)
        require(isinstance(report,dict) and report.get("status")=="ok", "initial calibration must be successful")
    result = run([*command,"--spec",str(kit["spec"]),"--output",str(output)], **permissions)
    if case["variant"] == "invalid":
        require(result.returncode != 0 and output.is_file() and not output.is_symlink()
                and output.stat().st_size == len(sentinel) and output.read_bytes() == sentinel,
                "a malformed capture replaced a previous calibration")
        return {"status": "rejected"}
    require(result.returncode == 0 and output.is_file() and not output.is_symlink() and output.stat().st_size < 64_000,
            "commission did not produce a bounded JSON report")
    report = loads(output.read_text())
    require(isinstance(report, dict) and set(report) == {"status", "devices"}, "commission report fields differ")
    if case["variant"] in ("static", "affine"):
        require(report == {"status": "unobservable", "devices": {}},
                "commission inferred a calibration from unobservable input motion")
        return {"status": "unobservable"}
    require(report["status"] == "ok" and isinstance(report["devices"], dict)
            and report["devices"].keys() == kit["devices"].keys(), "commission devices or status differed")
    for device, expected in kit["parameters"].items():
        parameter_error(report["devices"][device], expected, device)
    return {"status": "ok", "heldout_maximum_errors": heldout_error(kit, report["devices"], case["variant"])}
