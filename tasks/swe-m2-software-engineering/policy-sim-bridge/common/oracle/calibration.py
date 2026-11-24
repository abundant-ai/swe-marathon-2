"""Match commissioning capture clocks and infer signed physical channel identities."""

from bisect import bisect_left
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from math import fsum, sqrt
from typing import Any, Callable

from .model import Record, integer, mapping, names, number, vector

Binding = tuple[int, int, float]
Hypothesis = tuple[float, tuple[Binding, ...]]


@dataclass(frozen=True)
class Row:
    """One measured position, velocity and actuator target, with local timestamp."""

    time: int
    q: list[float]
    dq: list[float]
    u: list[float]


def signed(value: object) -> int:
    """Read a signed integer and rule out JSON booleans."""
    if type(value) is not int:
        raise ValueError("expected integer clock value")
    return value


def grid(values: object) -> list[int]:
    """Read a nonempty list of distinct signed clock candidates."""
    if type(values) is not list or not values:
        raise ValueError("clock grid is empty")
    numbers = [signed(value) for value in values]
    if len(set(numbers)) != len(numbers):
        raise ValueError("duplicate clock grid member")
    return numbers


def rows(values: object, qwidth: int, awidth: int) -> list[Row]:
    """Parse a capture and ensure consistent widths and chronology."""
    if type(values) is not list:
        raise ValueError("expected sample sequence")
    frames = [Row(signed(row["time_ns"]), vector(row["position"], qwidth),
                  vector(row["velocity"], qwidth), vector(row["control"], awidth))
              for row in map(mapping, values)]
    if any(a.time >= b.time for a, b in zip(frames, frames[1:])):
        raise ValueError("nonincreasing sample times")
    return frames


def pair(reference: list[Row], target: list[Row], offset: int, rate: int,
         anchor: int, gap: int) -> list[tuple[Row, Row]]:
    """Create aligned time-supported pairs at the proposed clock correction."""
    stamps = [r.time for r in reference]
    matched = []
    for actual in target:
        t = actual.time + offset + (actual.time - anchor) * rate // 1_000_000
        slot = bisect_left(stamps, t)
        if slot < len(stamps) and stamps[slot] == t:
            matched.append((reference[slot], actual))
            continue
        if 0 < slot < len(stamps):
            first, last = reference[slot - 1], reference[slot]
            if max(t - first.time, last.time - t) > gap:
                continue
            w = (t - first.time) / (last.time - first.time)
            interpolated = [[u + w * (v - u) for u, v in zip(a, b, strict=True)]
                            for a, b in ((first.q, last.q), (first.dq, last.dq), (first.u, last.u))]
            matched.append((Row(t, *interpolated), actual))
    return matched


def top_two(edges: list[list[tuple[float, Binding]]]) -> tuple[Hypothesis, ...]:
    """Return two best globally injective assignments over bounded channel counts."""
    count = len(edges)

    @lru_cache(None)
    def solve(row: int, used: int) -> tuple[Hypothesis, ...]:
        """Resolve the suffix of unused target positions for this memoized mask."""
        if row == count:
            return ((0.0, ()),)
        results = []
        for cost, entry in edges[row]:
            bit = 1 << entry[0]
            if used & bit:
                continue
            for remainder, selections in solve(row + 1, used | bit):
                results.append((cost + remainder, (entry, *selections)))
        results.sort()
        return tuple(results[:2])

    return solve(0, 0)


def sensor_edges(pairs: list[tuple[Row, Row]], n: int,
                 m: int, velocity_weight: float) -> list[list[tuple[float, Binding]]]:
    """Derive the independent offset and residual for each possible signed binding."""
    costs = []
    for j in range(n):
        row = []
        for slot in range(m):
            for sign in (-1, 1):
                offsets = [actual.q[slot] - sign * truth.q[j] for truth, actual in pairs]
                bias = fsum(offsets) / len(offsets)
                loss = fsum((delta - bias)**2 + (velocity_weight * (actual.dq[slot] - sign * truth.dq[j]))**2
                            for delta, (truth, actual) in zip(offsets, pairs, strict=True))
                row.append((number(loss / (len(pairs) * n)), (slot, sign, bias)))
        costs.append(row)
    return costs


def actuator_edges(pairs: list[tuple[Row, Row]], joint_by_action: tuple[Binding, ...],
                   slots: int) -> list[list[tuple[float, Binding]]]:
    """Build one actuator assignment cost matrix using the identified joint coordinate."""
    return [[
        (number(fsum((actual.u[slot] - zero - sign * truth.u[a])**2 for truth, actual in pairs)
                / (len(pairs) * len(joint_by_action))), (slot, sign, zero))
        for slot in range(slots)]
        for a, (_, sign, zero) in enumerate(joint_by_action)]


def errors(pairs: list[tuple[Row, Row]], sensors: tuple[Binding, ...],
           actuators: tuple[Binding, ...]) -> Record | None:
    """Evaluate physical-unit holdout error without changing the calibrated coordinates."""
    if not pairs:
        return None
    q = fsum((actual.q[i] - zero - sign * truth.q[j])**2 for truth, actual in pairs
             for j, (i, sign, zero) in enumerate(sensors))
    dq = fsum((actual.dq[i] - sign * truth.dq[j])**2 for truth, actual in pairs
              for j, (i, sign, _) in enumerate(sensors))
    u = fsum((actual.u[i] - zero - sign * truth.u[j])**2 for truth, actual in pairs
             for j, (i, sign, zero) in enumerate(actuators))
    return {"position_rmse": sqrt(q / (len(pairs) * len(sensors))),
            "velocity_rmse": sqrt(dq / (len(pairs) * len(sensors))),
            "control_rmse": sqrt(u / (len(pairs) * len(actuators)))}


def neutral_report(status: str) -> Record:
    """Report no usable calibration when fit overlap or identifiability is missing."""
    return {"status": status, "clock": None, "mapping": None, "validation_pairs": 0, "metrics": None}


def calibrate(input_record: object) -> Record:
    """Infer a unique aligned map on fit data and check it on independent samples."""
    spec = mapping(input_record)
    training = names(spec["joint_names"])
    actions = names(spec["action_order"])
    sensors = names(spec["sensor_order"])
    actuators = names(spec["actuator_order"])
    if (not set(actions).issubset(training) or not len(training) <= len(sensors) <= 12
            or not len(actions) <= len(actuators) <= 12 or len(training) > 8):
        raise ValueError("invalid commissioning channel dimensions")
    clock, limits = map(mapping, (spec["clock"], spec["limits"]))
    offsets, rates = grid(clock["offsets_ns"]), grid(clock["rates_ppm"])
    if len(offsets) * len(rates) > 81 or min(rates) <= -1_000_000:
        raise ValueError("clock grid exceeds allowed range")
    anchor, max_gap = signed(clock["anchor_ns"]), integer(clock["max_gap_ns"])
    min_pairs, coverage = integer(limits["min_pairs"], 3), number(limits["min_coverage"])
    weight, ambiguity = number(limits["velocity_weight_s"]), number(limits["ambiguity"])
    bounds = {field: number(limits[f"max_{field}"]) for field in ("position_rmse", "velocity_rmse", "control_rmse")}
    if not 0 < coverage <= 1 or weight <= 0 or min(ambiguity, *bounds.values()) < 0:
        raise ValueError("invalid commissioning limits")
    captures = []
    for phase in ("fit", "validation"):
        raw = mapping(spec[phase])
        captures.append((rows(raw["reference"], len(training), len(actions)),
                         rows(raw["target"], len(sensors), len(actuators))))
    reference, target = captures[0]
    ranked = []
    for offset, rate in product(offsets, rates):
        matched = pair(reference, target, offset, rate, anchor, max_gap)
        if len(matched) < min_pairs or len(matched) < coverage * len(target):
            continue
        for score, choices in top_two(sensor_edges(matched, len(training), len(sensors), weight)):
            ranked.append((score, offset, rate, choices))
    ranked.sort()
    if not ranked:
        return neutral_report("insufficient_overlap")
    if len(ranked) > 1 and ranked[1][0] - ranked[0][0] <= ambiguity:
        return neutral_report("ambiguous")
    _, offset, rate, selected = ranked[0]
    by_action = tuple(selected[training.index(name)] for name in actions)
    fit_pairs = pair(reference, target, offset, rate, anchor, max_gap)
    drives = top_two(actuator_edges(fit_pairs, by_action, len(actuators)))
    if len(drives) > 1 and drives[1][0] - drives[0][0] <= ambiguity:
        return neutral_report("ambiguous")
    _, chosen_drive = drives[0]
    action_binding = {name: actuators[slot] for name, (slot, _, _) in zip(actions, chosen_drive, strict=True)}
    binding = {name: {"sensor": sensors[slot], "sign": sign, "zero": zero,
                      "actuator": action_binding.get(name)}
               for name, (slot, sign, zero) in zip(training, selected, strict=True)}
    reference, target = captures[1]
    matched = pair(reference, target, offset, rate, anchor, max_gap)
    rmse = errors(matched, selected, chosen_drive)
    valid = (len(matched) >= min_pairs and len(matched) >= coverage * len(target)
             and rmse is not None and all(rmse[key] <= bound for key, bound in bounds.items()))
    return {"status": "ok" if valid else "validation_failed", "clock": {"offset_ns": offset, "rate_ppm": rate},
            "mapping": binding, "validation_pairs": len(matched), "metrics": rmse}


def bind(raw: object, result: object) -> Record:
    """Apply a validated successful commissioning map without mutating the template."""
    deploy = deepcopy(mapping(raw))
    result = mapping(result)
    found = mapping(result["mapping"])
    if result["status"] != "ok" or set(found) != set(mapping(deploy["joints"])):
        raise ValueError("commissioning result is unavailable for this deployment")
    for name, source in found.items():
        entry = mapping(source)
        deploy["joints"][name].update(sensor=entry["sensor"], sign=entry["sign"], zero=entry["zero"])
        if name in deploy["action_order"]:
            deploy["actions"][name]["actuator"] = entry["actuator"]
        elif entry["actuator"] is not None:
            raise ValueError("unmapped training joint has an actuator binding")
    return deploy
