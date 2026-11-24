"""Physical, independently surveyed nonlinear commissioning cases."""

from copy import deepcopy
from math import atan2, cos, hypot, pi, sin, sqrt
from pathlib import Path

import numpy as np

from probes import Run, surveyed_path
from reference import Json, near


ANCHORS = {"A45": [-1.35, -0.8], "D7": [2.5, -1.9], "T3": [0.52, 2.52]}
CHANNELS = ["rf-12", "rf-5", "rf-97"]
MAPPING = {
    "before reboot": dict(zip(CHANNELS, ("D7", "A45", "T3"), strict=True)),
    "after reboot": dict(zip(CHANNELS, ("T3", "D7", "A45"), strict=True)),
}


def convert(x: list[float], scale: float, yaw: float) -> list[float]:
    """Convert an XY vector using the known physical wheel transformation."""
    return [scale * (cos(yaw) * x[0] - sin(yaw) * x[1]),
            scale * (sin(yaw) * x[0] + cos(yaw) * x[1])]


def path_shape(seed: int, count: int) -> list[list[float]]:
    """Create a curved calibration drive with motion at multiple time scales."""
    angle = (seed % 17) / 13.0
    result = []
    for tick in range(count):
        x = (0.86 * sin(tick * 0.39 + angle) + 0.33 * cos(tick * 0.77 - angle)
             + 0.021 * tick + 0.14 * sin(tick * 1.05 + angle))
        y = (0.73 * cos(tick * 0.31 + angle) + 0.28 * sin(tick * 0.64 + angle)
             - 0.19 * cos(tick * 1.11 + angle))
        result.append([x, y])
    return result


def record_capture(identifier: str, epoch: str, start: int, trajectory: list[list[float]],
                   cfg: Json, seed: int, *, fit: bool, fault: int) -> tuple[Json, dict[int, list[float]]]:
    """Measure one latent trajectory using independently seeded sensor observations."""
    rng = np.random.default_rng(seed)
    count = len(trajectory)
    positions = {start + index: point for index, point in enumerate(trajectory)}
    last = start + count - 1
    offset, scale, yaw = cfg["offset_ticks"], cfg["wheel_scale"], cfg["wheel_yaw_rad"]
    offsets = cfg["offset_candidates"]
    mapping = cfg["receiver_maps"][epoch]
    anchors = cfg["anchors"]
    wheel, imu, fixes, ranges = [], [], [], []
    for tick in range(start, last + 1):
        i = tick - start
        point = positions[tick]
        if i:
            change = [a - b for a, b in zip(point, positions[tick - 1], strict=True)]
            if all(start < tick - offset + item <= last for item in offsets) and (i % 7 or not fault):
                sigma = 0.005 if fault < 2 else 0.008
                reading = (np.array(change) + rng.normal(0, sigma * 0.28, 2)).tolist()
                wheel.append({"device_tick": tick - offset, "delta": convert(reading, 1 / scale, -yaw), "sigma_m": sigma})
            if fit or i % 6 != 2:
                sigma = 0.049 if fault < 3 else 0.074
                motion = np.array(change) + rng.normal(0, 0.01 if fit else 0.022, 2)
                imu.append({"tick": tick, "delta": motion.tolist(), "sigma_m": sigma})
        if i in ((0, count // 2, count - 1) if fit else (0,)):
            fixes.append({"tick": tick, "position": (np.array(point) + rng.normal(0, 0.0014, 2)).tolist(),
                          "sigma_m": 0.010})
        # Two channels at most in any tick. These are deliberately not a batch of
        # simultaneous named observations from which to form all squared pairs.
        indices = [i % 3] if i % 4 else [i % 3, (i + 1) % 3]
        for number in indices:
            if fault >= 2 and i in (7, 8) and number == 1:
                continue
            receiver = CHANNELS[number]
            anchor = mapping[receiver]
            known = anchors[anchor]
            dist = hypot(point[0] - known[0], point[1] - known[1])
            perturbed = fault and (3 * i + 7 * number + seed) % 16 == 0
            reading = dist + cfg["range_bias_m"][anchor] + rng.normal(0, 0.005) + (0.58 if perturbed else 0.0)
            ranges.append({"tick": tick, "receiver": receiver, "distance_m": float(reading), "sigma_m": 0.025})
    ticket = {"id": identifier, "epoch": epoch, "start_tick": start, "end_tick": last, "wheel": wheel,
              "imu": imu, "fixes": fixes, "ranges": ranges}
    for samples in (wheel, imu, fixes, ranges):
        rng.shuffle(samples)
    return ticket, positions


def trial(index: int, mocap: list[np.ndarray]) -> tuple[Json, Json, dict]:
    """Create a sealed commissioning job with signed offsets and differing associations."""
    anchors = deepcopy(ANCHORS)
    mapping = deepcopy(MAPPING)
    offsets = [-2, 0, 2] if index < 2 else [-3, -1, 0, 2]
    offset = (-2, 2, -1, -3)[index]
    scale = (1.36, 0.66, 1.82, 0.94)[index]
    yaw = (-0.81, 1.43, -2.08, 2.51)[index]
    biases = dict(zip(anchors, ((0.18, -0.11, 0.09), (0.42, -0.25, 0.045),
                               (-0.13, 0.34, 0.19), (0.31, 0.07, -0.19))[index], strict=True))
    if index == 3:
        mapping["before reboot"], mapping["after reboot"] = mapping["after reboot"], mapping["before reboot"]
    physical = {"offset_ticks": offset, "wheel_scale": scale, "wheel_yaw_rad": yaw, "range_bias_m": biases,
                "receiver_maps": mapping, "anchors": anchors, "offset_candidates": offsets}
    rng = 431 + index * 37
    fit_plan = [
        ("fit-primary", "before reboot", 40),
        ("fit-reconnected", "after reboot", 230),
    ]
    if index == 3:
        fit_plan.append(("fit-before-later", "before reboot", 320))
    holdout = [("verify-reconnected", "after reboot", 401), ("verify-original", "before reboot", 600)]
    truth = {}
    partitions = []
    clip_start = (2, 20, 42, 58)
    for is_fit, schedule in ((True, fit_plan), (False, holdout)):
        captures = []
        for label, epoch, start in schedule:
            phase = len(truth)
            if index == 0:
                points = mocap[clip_start[phase]:clip_start[phase] + 18]
                path = [(2.4 * (point - points[0]) + np.array([0.15, -0.72])).tolist() for point in points]
            else:
                path = path_shape(rng + 7 * phase, 18 + index)
            capture, positions = record_capture(label, epoch, start, path, physical,
                                                rng + phase * 13, fit=is_fit, fault=index)
            captures.append(capture)
            truth[label] = positions
        partitions.append(captures)
    spec = {"anchors": anchors, "receivers": CHANNELS, "offset_candidates": offsets, "huber_k": 1.5,
            "ambiguity_cost": 0.02, "fit_captures": partitions[0], "validation_captures": partitions[1]}
    expected = {key: physical[key] for key in ("offset_ticks", "wheel_scale", "wheel_yaw_rad", "range_bias_m", "receiver_maps")}
    return spec, expected, truth


def extract_poses(report: object, captures: list[Json]) -> dict[str, dict[int, list[float]]] | None:
    """Validate complete ordered position tracks before computing physical metrics."""
    if not isinstance(report, list) or len(captures) != len(report):
        return None
    decoded = {}
    for track, capture in zip(report, captures, strict=True):
        if not isinstance(track, dict) or track.get("id") != capture["id"]:
            return None
        rows = track.get("poses")
        stamps = range(capture["start_tick"], capture["end_tick"] + 1)
        if not isinstance(rows, list) or len(stamps) != len(rows):
            return None
        poses = {}
        for row, tick in zip(rows, stamps, strict=True):
            if not isinstance(row, dict) or type(row.get("tick")) is not int or row["tick"] != tick:
                return None
            point = row.get("position")
            if not isinstance(point, list) or len(point) != 2:
                return None
            try:
                if any(type(value) not in (int, float) or not np.isfinite(value) for value in point):
                    return None
            except (OverflowError, TypeError):
                return None
            poses[tick] = point
        decoded[capture["id"]] = poses
    return decoded


def objective(spec: Json, fit: dict, model: Json) -> float:
    """Independently recompute the declared Huber objective on the reported fit."""
    total = 0.0
    for capture in spec["fit_captures"]:
        path = fit[capture["id"]]
        for key in ("wheel", "imu", "fixes"):
            for reading in capture[key]:
                if key == "fixes":
                    predicted = path[reading["tick"]]
                    measured = reading["position"]
                else:
                    wheel = key == "wheel"
                    tick = (reading["device_tick"] + model["offset_ticks"] if wheel else reading["tick"])
                    predicted = [a - b for a, b in zip(path[tick], path[tick - 1], strict=True)]
                    measured = reading["delta"]
                    if wheel:
                        measured = convert(measured, model["wheel_scale"], model["wheel_yaw_rad"])
                total += 0.5 * sum(((a - b) / reading["sigma_m"]) ** 2 for a, b in zip(predicted, measured, strict=True))
        for reading in capture["ranges"]:
            anchor = model["receiver_maps"][capture["epoch"]][reading["receiver"]]
            position = path[reading["tick"]]
            mapped = spec["anchors"][anchor]
            predicted = hypot(mapped[0] - position[0], mapped[1] - position[1]) + model["range_bias_m"][anchor]
            size = abs(predicted - reading["distance_m"]) / reading["sigma_m"]
            cutoff = min(spec["huber_k"], size)
            total += 0.5 * cutoff ** 2 + spec["huber_k"] * (size - cutoff)
    return total


def rmse(trajectories: dict, expected: dict) -> float:
    """Measure error in the surveyed coordinate frame without posthoc alignment."""
    errors = []
    for key, path in trajectories.items():
        for tick, stored in path.items():
            truth = expected[key][tick]
            errors.append((stored[0] - truth[0]) ** 2 + (stored[1] - truth[1]) ** 2)
    return sqrt(sum(errors) / len(errors))


def qualifies(result: Json, spec: Json, model: Json, truth: dict, *, debug: bool = False) -> bool:
    """Require a correct wiring map, physical parameter accuracy and held-out geometry."""
    if result.get("status") != "ok" or not isinstance(result.get("calibration"), dict):
        if debug:
            print("did not qualify", result.get("status"))
        return False
    observed = result["calibration"]
    offset, biases = observed.get("offset_ticks"), observed.get("range_bias_m")
    fit = extract_poses(result.get("fit"), spec["fit_captures"])
    validation = extract_poses(result.get("validation"), spec["validation_captures"])
    if (type(offset) is not int or offset != model["offset_ticks"]
            or observed.get("receiver_maps") != model["receiver_maps"] or not isinstance(biases, dict)
            or set(biases) != set(model["range_bias_m"]) or fit is None or validation is None):
        if debug:
            print("discrete or track mismatch", model["offset_ticks"], observed)
        return False
    if not near(observed.get("wheel_scale"), model["wheel_scale"], 0.045) or not near(
            observed.get("wheel_yaw_rad"), model["wheel_yaw_rad"], 0.045):
        if debug:
            print("wheel mismatch", observed, model)
        return False
    if not all(near(biases[key], expected, 0.095) for key, expected in model["range_bias_m"].items()):
        if debug:
            print("bias mismatch", biases, model["range_bias_m"])
        return False
    try:
        loss = objective(spec, fit, observed)
        baseline = objective(spec, truth, model)
        errors = (rmse(fit, truth), rmse(validation, truth))
        if debug:
            print("loss", loss, "planted", baseline, "physical errors", errors)
        return near(result.get("fit_cost"), loss, 5e-7) and loss <= baseline * 1.035 + 0.02 and errors[0] < 0.09 and errors[1] < 0.105
    except (OverflowError, ValueError, KeyError, TypeError):
        return False


def symmetric_case() -> Json:
    """Produce an observable trajectory with an intentionally unidentified radio swap."""
    anchors = {"A45": [-2.0, 0.0], "D7": [2.0, 0.0], "T3": [0.0, 4.0]}
    mapping = {"before reboot": dict(zip(CHANNELS, anchors, strict=True))}
    physical = {"anchors": anchors, "range_bias_m": {anchor: 0.0 for anchor in anchors},
                "offset_ticks": 0, "wheel_scale": 1.21, "wheel_yaw_rad": -0.54,
                "offset_candidates": [0], "receiver_maps": mapping}
    path = [[0.0, 0.1 * count + 0.19 * sin(count)] for count in range(18)]
    fit, clean = record_capture("midline", "before reboot", 12, path, physical, 551, fit=True, fault=0)
    other, _ = record_capture("midline-repeat", "before reboot", 55, path, physical, 991, fit=False, fault=0)
    for reading in fit["ranges"]:
        key = mapping[fit["epoch"]][reading["receiver"]]
        point, mapped = clean[reading["tick"]], anchors[key]
        reading["distance_m"] = hypot(point[0] - mapped[0], point[1] - mapped[1])
    for reading in fit["fixes"]:
        reading["position"] = clean[reading["tick"]]
        reading["sigma_m"] = 0.001
    return {"anchors": anchors, "receivers": CHANNELS, "offset_candidates": [0], "huber_k": 1.5,
            "ambiguity_cost": 0.15, "fit_captures": [fit], "validation_captures": [other]}


def abstains(report: Json, status: str) -> bool:
    """Check that an unsupported or ambiguous fit exports no calibration."""
    return (report.get("status") == status and "calibration" in report and report["calibration"] is None
            and "fit_cost" in report and report["fit_cost"] is None
            and report.get("fit") == [] and report.get("validation") == [])


def network_cases(run: Run, dataset: Path) -> dict[str, bool]:
    """Score integrated commissioning missions rather than isolated favorable fields."""
    sample = surveyed_path(dataset)
    cases = [trial(index, sample) for index in range(4)]
    results = [run("qualify-network", spec) for spec, _, _ in cases]
    missions = {
        name: qualifies(result, *case)
        for name, result, case in zip(
            ("measured_room_path_recommissioned", "swapped_radios_after_restart",
             "recover_from_non_line_of_sight_ranges", "share_binding_across_calibration_drives"),
            results, cases, strict=True,
        )
    }
    canonical, mapping, truth = cases[0]
    alternative = deepcopy(canonical)
    mocap_positions = [point.tolist() for point in sample[30:48]]
    physical = mapping | {"anchors": canonical["anchors"], "offset_candidates": canonical["offset_candidates"]}
    revised, revised_truth = record_capture("independent-check", "after reboot", 834, mocap_positions,
                                              physical, 806, fit=False, fault=0)
    alternative["validation_captures"] = [revised]
    altered = run("qualify-network", alternative)
    original = results[0]
    missions["calibration_is_immutable_under_validation_replacement"] = (
        qualifies(altered, alternative, mapping, truth | {"independent-check": revised_truth})
        and altered.get("calibration") == original.get("calibration")
        and altered.get("fit") == original.get("fit")
        and altered.get("fit_cost") == original.get("fit_cost"))
    symmetric = symmetric_case()
    missions["reject_unidentifiable_receiver_symmetry"] = abstains(
        run("qualify-network", symmetric), "ambiguous")
    unsupported = deepcopy(symmetric)
    unsupported["fit_captures"][0]["wheel"] = []
    missions["reject_structurally_unexcited_calibration"] = abstains(
        run("qualify-network", unsupported), "insufficient_support")
    malformed = deepcopy(canonical)
    malformed["fit_captures"][0]["wheel"][0]["device_tick"] = 0
    missions["invalid_timestamp_support_is_atomic"] = run(
        "qualify-network", malformed, invalid=True).get("atomic", False)
    return missions
