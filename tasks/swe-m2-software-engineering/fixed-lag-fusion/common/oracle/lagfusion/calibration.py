"""Calibrate wheel timing and planar mounting against surveyed samples."""

from collections import defaultdict
from math import atan2, hypot
from statistics import median

from .contract import Json, integer, name, number, obj, rows, vector


def read_track(value: object) -> dict[int, complex]:
    """Read unordered, unique survey or wheel displacement ticks."""
    result = {}
    for item in map(obj, rows(value)):
        tick = integer(item["tick"])
        if tick in result:
            raise ValueError("duplicate calibration tick")
        result[tick] = complex(*vector(item["delta"]))
    return result


def wheel_fit(wheel: dict[int, complex], survey: dict[int, complex], offset: int,
              minimum: int, floor: float) -> tuple[float, int, complex] | None:
    """Estimate a robust orientation-preserving map from excited matched deltas."""
    matched = [(value, survey[tick + offset]) for tick, value in wheel.items()
               if abs(value) > floor and tick + offset in survey]
    if len(matched) < minimum:
        return None
    ratios = [truth / reading for reading, truth in matched]
    mapped = complex(median(value.real for value in ratios), median(value.imag for value in ratios))
    score = median(abs(mapped * reading - truth) for reading, truth in matched)
    return score, len(matched), mapped


def calibrate(spec: Json) -> Json:
    """Recover surveyed wheel timing, scale, rotation and per-anchor range biases."""
    wheel = read_track(spec["wheel"])
    survey = read_track(spec["survey"])
    candidates = [integer(value, None) for value in rows(spec["offset_candidates"])]
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError("offset candidates must be nonempty and distinct")
    minimum = integer(spec["min_pairs"], 3)
    floor = number(spec["motion_floor_m"], positive=True)
    ambiguity = number(spec["ambiguity_m"], nonnegative=True)
    anchors = {name(key): vector(value) for key, value in obj(spec["anchors"]).items()}
    if not anchors:
        raise ValueError("range calibration requires surveyed anchors")
    differences = defaultdict(list)
    for data in map(obj, rows(spec["ranges"])):
        anchor = name(data["anchor"])
        x, y = vector(data["position"]) - anchors[anchor]
        differences[anchor].append(number(data["distance_m"], nonnegative=True) - hypot(x, y))
    report = dict.fromkeys(("offset_ticks", "wheel_scale", "wheel_yaw_rad", "wheel_pairs", "wheel_median_m", "range_bias_m"))
    report["status"] = "insufficient_support"
    valid = []
    for offset in candidates:
        result = wheel_fit(wheel, survey, offset, minimum, floor)
        if result is not None and abs(result[2]) > 0:
            valid.append((result[0], offset, result[1], result[2]))
    valid.sort()
    if not valid or any(len(differences[key]) < minimum for key in anchors):
        return report
    if len(valid) > 1 and valid[1][0] - valid[0][0] <= ambiguity:
        report["status"] = "ambiguous"
        return report
    loss, offset, matched, transform = valid[0]
    return {"status": "ok", "offset_ticks": offset, "wheel_scale": abs(transform),
            "wheel_yaw_rad": atan2(transform.imag, transform.real), "wheel_pairs": matched,
            "wheel_median_m": loss, "range_bias_m": {key: median(differences[key]) for key in anchors}}
