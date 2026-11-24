"""Plan surveyed map canaries and atomically promote or roll back a snapshot."""

from collections import deque
from math import isfinite

from .maps import FREE, json_bytes, parse_cell, read_map, read_object, write_bytes
from .releases import active, blob_path, exclusive, read_blob, version_id


def neighbors(cell):
    """Return touching cells in the four-connected map."""
    x, y = cell
    return ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1))


def outside(store, output):
    """Keep reports out of the immutable store namespace."""
    if output.resolve().is_relative_to(store.resolve()):
        raise ValueError("Report cannot be inside the store")


def identifier(value):
    """Validate a pinned map identity before addressing its blob."""
    if not isinstance(value, str):
        raise ValueError("Invalid version")
    return version_id(value)


def pinned(store, version):
    """Validate the immutable record and read its public occupancy cells."""
    read_blob(store, version)
    return read_map(blob_path(store, version))


def shortest(free, start, goal):
    """Find the shortest available cell route or return no route."""
    if start not in free or goal not in free:
        return None
    parent = {start: None}
    todo = deque([start])
    while todo:
        cell = todo.popleft()
        if cell == goal:
            path = [goal]
            while parent[path[-1]] is not None:
                path.append(parent[path[-1]])
            return list(reversed(path))
        for other in neighbors(cell):
            if other in free and other not in parent:
                parent[other] = cell
                todo.append(other)
    return None


def route(store, version, request, output):
    """Export a route in a fixed map with live guard restrictions."""
    outside(store, output)
    grid, cells = pinned(store, identifier(version))
    report = read_object(request)
    if not isinstance(report.get("blocked"), list):
        raise ValueError("Expected blocked cells")
    blocked = {parse_cell(item, grid) for item in report["blocked"]}
    free = {cell for cell, state in cells.items() if state == FREE} - blocked
    start, goal = (parse_cell(report.get(key), grid) for key in ("start", "goal"))
    write_bytes(output, json_bytes({"version": version, "path": shortest(free, start, goal)}))


def measurement(value):
    """Read one finite, nonnegative survey error."""
    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        raise ValueError("Invalid survey error")
    return value


def validate_observation(row, grid):
    """Read the typed survey record before assessing a route."""
    if not isinstance(row, dict):
        raise ValueError("Invalid observation")
    seq, result = row.get("sequence"), row.get("result")
    if type(seq) is not int or seq <= 0 or result not in ("arrived", "guarded", "collision"):
        raise ValueError("Invalid observation kind or sequence")
    previous, requested, measured = (parse_cell(row.get(key), grid) for key in ("from", "requested", "measured"))
    return seq, identifier(row.get("version")), previous, requested, measured, result, measurement(row.get("error_m"))


def review_route(route_data, version, grid, cells):
    """Validate and replay one canary's feedback without guessing missing motion."""
    if not isinstance(route_data, dict):
        raise ValueError("Invalid route record")
    position, goal = (parse_cell(route_data.get(key), grid) for key in ("start", "goal"))
    max_moves = route_data.get("max_moves")
    error_limit = measurement(route_data.get("max_error_m"))
    log = route_data.get("observations")
    if type(max_moves) is not int or max_moves <= 0 or not isinstance(log, list):
        raise ValueError("Invalid route budget or observations")
    steps = [validate_observation(row, grid) for row in log]
    okay = cells.get(position) == FREE and cells.get(goal) == FREE and len(steps) <= max_moves
    blocked = set()
    for index, (seq, pin, before, requested, measured, result, error) in enumerate(steps, start=1):
        expected = position if result == "guarded" else requested
        legal = (seq == index and pin == version and before == position and position != goal
                 and requested in neighbors(position) and cells.get(requested) == FREE and requested not in blocked
                 and measured == expected and result != "collision" and error <= error_limit)
        okay = okay and legal
        if result == "guarded":
            blocked.add(requested)
        else:
            position = measured
    return okay and position == goal


def review(store, request, output):
    """Apply a surveyed promotion or rollback through the store's native lock."""
    outside(store, output)
    report = read_object(request)
    action = report.get("action")
    versions = [identifier(report.get(key)) for key in ("candidate", "expected_active", "fallback")]
    candidate, expected, fallback = versions
    routes = report.get("routes")
    if (action not in ("promote", "rollback") or (action == "rollback" and expected != candidate)
            or not isinstance(routes, list) or not routes):
        raise ValueError("Invalid review request")
    grid, cells = pinned(store, candidate)
    for version in (expected, fallback):
        read_blob(store, version)
    results = {}
    for item in routes:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in results:
            raise ValueError("Invalid or duplicate route ID")
        results[item["id"]] = review_route(item, candidate, grid, cells)
    with exclusive(store):
        selected = active(store)
        status = "held"
        if selected != expected:
            status = "stale"
        elif action == "promote" and all(results.values()):
            selected, status = candidate, "promoted"
            write_bytes(store / "active", (selected + "\n").encode("ascii"))
        elif action == "rollback" and not all(results.values()):
            selected, status = fallback, "rolled_back"
            write_bytes(store / "active", (selected + "\n").encode("ascii"))
    write_bytes(output, json_bytes({"status": status, "active_version": selected, "routes": results}))
