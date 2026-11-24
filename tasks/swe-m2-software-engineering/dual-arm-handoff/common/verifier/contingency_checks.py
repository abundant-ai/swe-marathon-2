"""Execute every reachable receipt against the independent cell plant."""

from copy import deepcopy
from typing import Any

from plant import advance, cursor, motion_valid
from probes import at_tip, braking, edge, obstacle, seed

Wire = dict[str, Any]


def valid_report(spec: Wire, report: Wire | None, feasible: bool) -> bool:
    """Execute a submitted decision graph across timing and observation branches.

    Reconstruct the belief from receipts instead of trusting any claim in the
    report. Probes that are infeasible must return the blocked result.

    Args:
        spec: Commissioned scenes, sensors, timing, and planning window.
        report: Untrusted CLI result, or None when the command failed.
        feasible: Whether the scenario has independently established safe policy.

    Returns:
        Whether the reported absence of a policy or complete policy is valid.
    """
    if not feasible:
        return report == {"status": "blocked", "root": None, "decisions": {}}
    if not report or report.get("status") != "ready":
        return False
    graph = report.get("decisions")
    if not isinstance(graph, dict) or not isinstance(report.get("root"), str) or not report["root"]:
        return False
    baseline = spec["window"]
    scene_windows = {key: dict(baseline, fixtures=rows) for key, rows in spec["scenes"].items()}
    start = cursor(next(iter(scene_windows.values())))
    if start is None:
        return False
    pending = [(report["root"], *start, tuple(sorted(scene_windows)))]
    visited, touched = set(), set()
    while pending:
        point = pending.pop()
        if point in visited:
            continue
        visited.add(point)
        key, tick, node, owner, possible = point
        touched.add(key)
        operation, successors = graph[key]["command"], graph[key]["next"]
        if not isinstance(successors, dict) or any(not isinstance(n, str) or not n for n in successors.values()):
            return False
        if operation is None:
            if node != baseline["goal_node"] or owner != baseline["goal_owner"] or successors:
                return False
            pose = baseline["nodes"][node]
            if not all(motion_valid(scene_windows[s], pose, pose, tick, tick, owner) for s in possible):
                return False
            continue
        kind = operation["kind"]
        begin, end = operation["start"], operation["end"]
        if type(begin) is not int or type(end) is not int or begin != tick or not tick < end <= baseline["deadline"]:
            return False
        if kind == "scan":
            sensor = spec["scanners"].get(node)
            if sensor is None or operation.get("node") != node or end - tick != sensor["ticks"]:
                return False
            groups: dict[str, list[str]] = {}
            for scene in possible:
                if advance(scene_windows[scene], tick, node, owner, dict(operation, kind="wait")) is None:
                    return False
                groups.setdefault(sensor["labels"][scene], []).append(scene)
            if successors.keys() != groups.keys():
                return False
            pending.extend((successors[label], end, node, owner, tuple(group)) for label, group in groups.items())
            continue
        delays = spec["delays"].get(kind, [0])
        if set(successors) != {str(delay) for delay in delays}:
            return False
        for delay in delays:
            actual = dict(operation, start=begin + delay, end=end + delay)
            outcomes = set()
            for scene in possible:
                plant = scene_windows[scene]
                if delay:
                    hold = {"kind": "wait", "node": node, "start": begin, "end": begin + delay}
                    if advance(plant, begin, node, owner, hold) is None:
                        return False
                outcomes.add(advance(plant, begin + delay, node, owner, actual))
            if None in outcomes or len(outcomes) != 1:
                return False
            arrival, destination, holder = outcomes.pop()
            pending.append((successors[str(delay)], arrival, destination, holder, possible))
    return touched == graph.keys()


def request(window: Wire, *, scenes: Wire | None = None, scanners: Wire | None = None,
            move: list[int] | None = None, handoff: list[int] | None = None) -> Wire:
    """Compose a cell request from a base window and optional fluctuations."""
    return {"window": window, "scenes": scenes or {"clear": []}, "scanners": scanners or {},
            "delays": {"move": move or [0], "handoff": handoff or [0]}}


def obscured_cell(*, scan: bool) -> Wire:
    """Place a persistent obstruction on each of two disjoint travel routes."""
    window = seed(high=True, deadline=41)
    low = obstacle(at_tip(window, "home", "station", .54))
    high = obstacle(at_tip(window, "raised", "bridge", .52), radius=.036)
    scenes = {"settled-low": [low], "settled-high": [high]}
    readers = {"home": {"ticks": 2, "labels": {"settled-low": "A3", "settled-high": "B7"}}}
    return request(window, scenes=scenes, scanners=readers if scan else None, move=[0, 2], handoff=[0, 1])


def successive_readings() -> Wire:
    """Require access to a scanner and process a second ambiguous reading."""
    spec = obscured_cell(scan=True)
    window, readers = spec["window"], spec["scanners"]
    window["deadline"] = 56
    window["nodes"]["inspect"] = deepcopy(window["nodes"]["home"])
    window["nodes"]["inspect"]["left"][2] -= .17
    window["nodes"]["inspect"]["right"][3] += .12
    window["edges"].extend((edge("measure-in", "home", "inspect", 4), edge("measure-out", "inspect", "home", 4)))
    spec["scenes"]["low-secondary"] = deepcopy(spec["scenes"]["settled-low"])
    spec["scenes"]["high-secondary"] = deepcopy(spec["scenes"]["settled-high"])
    readers["home"]["labels"] = {"settled-low": "A", "settled-high": "A",
                                  "low-secondary": "B", "high-secondary": "B"}
    readers["inspect"] = {"ticks": 2, "labels": {"settled-low": "X", "settled-high": "Y",
                                                   "low-secondary": "Y", "high-secondary": "X"}}
    return spec


def timed_release() -> Wire:
    """Place a moving obstruction over the low route until it retracts."""
    window = seed(deadline=45)
    point = at_tip(window, "home", "station", .51)
    return request(window, scenes={"slow": [obstacle(point, release=11)],
                                   "fast": [obstacle(point, release=8)]}, move=[0, 1, 4], handoff=[0, 3])


def contingency_checks(run: Any) -> dict[str, bool]:
    """Grade complete policies and trustworthy failure on independent missions."""
    cases = {
        "ready_robust_arrival": (request(seed(deadline=30), move=[0, 1, 4], handoff=[0, 4]), True),
        "ready_scan_changes_safe_route": (obscured_cell(scan=True), True),
        "ready_nested_readings": (successive_readings(), True),
        "ready_fixture_retracts": (timed_release(), True),
        "ready_brake_then_monitor": (request(braking(), move=[0, 3], handoff=[1, 4]), True),
        "blocked_without_observation": (obscured_cell(scan=False), False),
        "blocked_nominal_route_is_too_late": (request(seed(deadline=29), move=[0, 4], handoff=[0, 4]), False),
        "blocked_invalid_station": (request(seed(deadline=25), move=[0, 1]), False),
    }
    cases["blocked_invalid_station"][0]["window"]["payload"]["right"]["a"][1] = .026
    defective = deepcopy(cases["ready_scan_changes_safe_route"][0])
    defective["scanners"]["home"]["labels"].pop("settled-low")
    evidence = {"contingency_malformed_sensor_preserves_output": run("contingency", defective, invalid=True)}
    for key, (spec, feasible) in cases.items():
        try:
            evidence[f"contingency_{key}"] = valid_report(spec, run("contingency", spec), feasible)
        except (ValueError, TypeError, AttributeError, KeyError, IndexError, OverflowError):
            evidence[f"contingency_{key}"] = False
    return evidence
