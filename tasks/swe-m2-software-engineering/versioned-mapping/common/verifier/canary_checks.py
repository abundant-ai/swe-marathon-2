"""Drive a live canary on private obstructions and check release decisions."""

from copy import deepcopy
import hashlib
import json

from probes import map_doc, read, write


def next_cells(cell):
    """Return cells with one unit of Manhattan separation."""
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]


def distance(space, start, goal):
    """Independently measure a shortest route length by reachability layers."""
    if start not in space or goal not in space:
        return None
    seen, frontier, steps = {start}, {start}, 0
    while frontier:
        if goal in frontier:
            return steps
        frontier = {point for cell in frontier for point in next_cells(cell) if point in space} - seen
        seen.update(frontier)
        steps += 1
    return None


def opened_store(run, root):
    """Drive the earlier publication interface to get the two pinned inputs."""
    layout = {(x, y): "free" if x != 4 or y == 5 else "occupied"
              for x in range(9) for y in range(8)}
    base = write(root / "aisles.json", map_doc(layout, width=9, height=8, resolution=0.13))
    base_version = hashlib.sha256(base.read_bytes()).hexdigest()
    store = root / "maps"
    if run("init", "--store", store, "--map", base).returncode:
        raise ValueError("Cannot initialize the test map store")
    patch = write(root / "revisit.json", {
        "schema_version": 1, "base_sha256": base_version,
        "changes": [{"cell": [4, 2], "from": "occupied", "to": "free",
                     "support": ["survey-east-2", "survey-west-4"]}],
    })
    release = run("publish", "--store", store, "--base", base_version, "--patch", patch)
    if release.returncode:
        raise ValueError("Cannot publish canary map")
    candidate = json.loads(release.stdout)["version"]
    layout[(4, 2)] = "free"
    return store, base_version, candidate, {cell for cell, state in layout.items() if state == "free"}


def drive(run, root, store, candidate, open_cells, guard, route_id, origin, goal, *, bad_survey=False):
    """Execute the candidate's route against the live guard until success or no route."""
    limits = {"id": route_id, "start": list(origin), "goal": list(goal), "max_moves": 25, "max_error_m": .12}
    position, discovered, observations = origin, set(), []
    for index in range(1, 26):
        if position == goal:
            break
        input_path = write(root / f"{route_id}-{index}.json",
                           {"start": list(position), "goal": list(goal), "blocked": sorted(discovered)})
        output = root / f"{route_id}-{index}-plan.json"
        response = run("route", "--store", store, "--version", candidate, "--request", input_path, "--output", output)
        if response.returncode:
            raise ValueError("Route CLI did not provide a decision")
        report = read(output)
        if report.get("version") != candidate:
            raise ValueError("Planner lost the immutable map pin")
        path = report.get("path")
        reachable = distance(open_cells - discovered, position, goal)
        if path is None and reachable is None:
            break
        if (not isinstance(path, list) or reachable is None or len(path) != reachable + 1
                or path[0] != list(position) or path[-1] != list(goal)):
            raise ValueError("Planner did not provide a legal shortest path")
        parsed = [tuple(cell) for cell in path]
        if (any(cell not in open_cells - discovered for cell in parsed)
                or any(right not in next_cells(left) for left, right in zip(parsed, parsed[1:]))):
            raise ValueError("Planner traversed an occupied or guarded cell")
        requested, before = parsed[1], position
        if requested in guard:
            discovered.add(requested)
            outcome = "guarded"
        else:
            position, outcome = requested, "arrived"
        observations.append({
            "sequence": index, "version": candidate, "from": list(before), "requested": list(requested),
            "measured": list(position), "result": outcome, "error_m": .31 if bad_survey and position == goal else .025,
        })
    return dict(limits, observations=observations), position == goal and not bad_survey


def snapshot(run, root, store, version, label):
    destination = root / (label + ".json")
    if run("snapshot", "--store", store, "--version", version, "--output", destination).returncode:
        raise ValueError("Snapshot export failed")
    return destination.read_bytes()


def decision(run, root, store, request, label, want_status, expected_active, expected_routes):
    spec, output = write(root / (label + "-request.json"), request), root / (label + "-decision.json")
    result = run("review", "--store", store, "--request", spec, "--output", output)
    if result.returncode:
        return False
    report = read(output)
    return (report == {"status": want_status, "active_version": expected_active, "routes": expected_routes}
            and hashlib.sha256(snapshot(run, root, store, "active", label + "-active")).hexdigest() == expected_active)


def cold_route(name, row, pin):
    """Generate an independent already surveyed short route in the clear aisle."""
    steps = []
    for index in range(1, 7):
        steps.append({
            "sequence": index, "version": pin, "from": [index, row], "requested": [index + 1, row],
            "measured": [index + 1, row], "result": "arrived", "error_m": .02,
        })
    return {"id": name, "start": [1, row], "goal": [7, row], "max_moves": 8, "max_error_m": .1,
            "observations": steps}


def canary_fixture(run, root):
    """Exercise detours, held decisions, stale authority and physical rollback."""
    store, base, candidate, open_cells = opened_store(run, root)
    baseline = snapshot(run, root, store, base, "baseline-pin")
    target = snapshot(run, root, store, candidate, "candidate-pin")
    qualify = {"action": "promote", "candidate": candidate, "expected_active": base, "fallback": base}
    first, completed = drive(run, root, store, candidate, open_cells, {(4, 2)}, "detour", (1, 2), (7, 2))
    second, second_done = drive(run, root, store, candidate, open_cells, set(), "parallel", (1, 5), (7, 5))
    blocked, blocked_done = drive(run, root, store, candidate, open_cells, {(4, 2), (4, 5)},
                                  "closed", (1, 2), (7, 2))
    observed_guard = any(item["result"] == "guarded" for item in first["observations"])
    checks = {}
    checks["hold_for_incomplete_survey"] = not blocked_done and decision(
        run, root, store, dict(qualify, routes=[blocked, second]), "hold", "held", base,
        {"closed": False, "parallel": True},
    )
    wrong_pin = cold_route("wrong", 5, base)
    checks["hold_for_wrong_snapshot"] = decision(
        run, root, store, dict(qualify, routes=[wrong_pin]), "wrong-map", "held", base, {"wrong": False},
    )
    collision = cold_route("contact", 5, candidate)
    collision["observations"][0]["result"] = "collision"
    guarded = cold_route("repeat", 5, candidate)
    stopped = dict(guarded["observations"][0], result="guarded", measured=[1,5])
    guarded["observations"].insert(0, stopped)
    for index, row in enumerate(guarded["observations"], start=1):
        row["sequence"] = index
    after_goal = cold_route("after-goal", 5, candidate)
    for origin, destination in (([7,5],[7,6]),([7,6],[7,5])):
        after_goal["observations"].append({
            "sequence": len(after_goal["observations"]) + 1, "version": candidate,
            "from": origin, "requested": destination, "measured": destination,
            "result": "arrived", "error_m": .03,
        })
    checks["hold_for_broken_physical_traces"] = decision(
        run, root, store, dict(qualify, routes=[collision, guarded, after_goal]), "broken",
        "held", base, {"contact": False, "repeat": False, "after-goal": False},
    )
    checks["promote_after_live_guarded_detour"] = observed_guard and completed and second_done and decision(
        run, root, store, dict(qualify, routes=[first, second]), "promote", "promoted", candidate,
        {"detour": True, "parallel": True},
    )
    checks["stale_promotion_retains_new_active"] = decision(
        run, root, store, dict(qualify, routes=[second]), "stale", "stale", candidate, {"parallel": True},
    )
    accuracy, _ = drive(run, root, store, candidate, open_cells, set(), "loss", (1, 5), (7, 5), bad_survey=True)
    checks["survey_loss_rolls_back_after_cutover"] = decision(
        run, root, store, dict(qualify, action="rollback", expected_active=candidate, routes=[second, accuracy]),
        "rollback", "rolled_back", base, {"parallel": True, "loss": False},
    )
    sent = deepcopy(second)
    sent["observations"][0]["sequence"] = True
    spec = write(root / "malformed.json", dict(qualify, routes=[sent]))
    output = write(root / "malformed-decision.json", {"original": True})
    malformed = run("review", "--store", store, "--request", spec, "--output", output)
    checks["malformed_log_preserves_decision"] = (malformed.returncode not in (0, 124)
                                                  and read(output) == {"original": True})
    checks["both_pinned_snapshots_survive"] = (
        snapshot(run, root, store, base, "base-final") == baseline
        and snapshot(run, root, store, candidate, "candidate-final") == target
        and hashlib.sha256(snapshot(run, root, store, "active", "active-final")).hexdigest() == base
    )
    return checks
