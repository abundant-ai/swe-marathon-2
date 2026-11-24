"""Qualify generated curves and execute the resulting graph in the docking plant."""

from cmath import exp
from collections import defaultdict
from heapq import heappop, heappush
import json
from math import ceil, hypot, isfinite, pi
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
from typing import Callable

from plant import Record, Violation, require
from staging_plant import drive_case, footprint_gap

COMMON = ("bounds", "obstacles", "footprint", "margin_m", "forward_max_mps", "reverse_max_mps",
          "angular_max_radps", "position_tolerance_m", "heading_tolerance_rad")


def layout(**adjustments: object) -> Record:
    """Build the surveyed approach around a fixed enclosure and two possible holds."""
    return {"bounds": [-1.99, -1.71, 1.91, 1.69], "obstacles": [[-.74, -.38, -.31, .45]],
            "footprint": [.19, .13], "margin_m": .02, "forward_max_mps": .34, "reverse_max_mps": .22,
            "angular_max_radps": .80, "position_tolerance_m": .009, "heading_tolerance_rad": .020,
            "origin": [0, 0], "step_m": .3, "tick_seconds": .1, "start": [-4, 0, 2], "staging": [3, 0, 0],
            "turn_radius_cells": [1, 2], "closures": {"north": [-.68, .45, -.34, 1.71],
                                                       "south": [-.68, -1.72, -.34, -.38]},
            "route_limit_ticks": 132} | adjustments


def invoke(app: Path, folder: Path, survey: Record, *, invalid: bool = False) -> Record | bool:
    """Ask a fresh low-privilege process to compile one surveyed layout."""
    folder.mkdir(mode=0o755)
    request = folder / "layout.json"
    request.write_text(json.dumps(survey))
    outputs = folder / "out"
    outputs.mkdir()
    outputs.chmod(0o777)
    report = outputs / "report.json"
    sentinel = '{"previous":"report"}\n'
    if invalid:
        report.write_text(sentinel)
        report.chmod(0o666)
    identity = {}
    if os.geteuid() == 0:
        try:
            account = pwd.getpwnam("candidate")
        except KeyError:
            account = pwd.getpwnam("nobody")
        identity = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
    with subprocess.Popen([sys.executable, "-B", "-m", "dock_recovery", "compile", "--layout", str(request),
                           "--output", str(report)], cwd=app, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True, **identity,
                          env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(outputs), "LANG": "C.UTF-8"}) as command:
        try:
            code = command.wait(timeout=24)
        except subprocess.TimeoutExpired:
            code = 124
        finally:
            try:
                os.killpg(command.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            command.wait(timeout=3)
    require(report.is_file() and not report.is_symlink() and report.stat().st_size < 2_000_000, "no usable compile report")
    if invalid:
        return code not in (0, 124) and report.read_text() == sentinel
    require(code == 0, f"compilation exited {code}")
    return json.loads(report.read_text())


def rigid_motion(start: complex, yaw: float, v: float, w: float, elapsed: float) -> tuple[complex, float]:
    """Integrate the hypothesized twist independently using a complex heading."""
    attitude = exp(1j * yaw)
    displacement = attitude * v * elapsed if abs(w) < 1e-12 else attitude * (exp(1j * w * elapsed) - 1) * v / (1j * w)
    return start + displacement, yaw + w * elapsed


def remains_clear(survey: Record, start: complex, yaw: float, v: float, w: float, duration: float) -> bool:
    """Use corner projections and a sampling error envelope over the swept body."""
    radius = hypot(*(length + survey["margin_m"] for length in survey["footprint"]))
    reach = (abs(v) + radius * abs(w)) * duration
    for segments in (12, 48, 192, 768):
        gap = min(footprint_gap(survey, *rigid_motion(start, yaw, v, w, duration * index / segments))
                  for index in range(segments + 1))
        if gap <= 0:
            return False
        if gap > reach / (2 * segments):
            return True
    require(False, "unable to certify clearance for the generated edge")
    return False


def distance(graph: Record, disabled: set[str]) -> int | None:
    """Measure minimum execution ticks over the submitted graph for this hold."""
    moves = defaultdict(list)
    for edge in graph["edges"]:
        if edge["id"] not in disabled:
            moves[edge["source"]].append((edge["target"], edge["segments"][0]["ticks"]))
    queue, visited = [(0, graph["start"])], set()
    while queue:
        length, node = heappop(queue)
        if node == graph["staging"]:
            return length
        if node not in visited:
            visited.add(node)
            for target, time in moves[node]:
                heappush(queue, (length + time, target))
    return None


def qualify(survey: Record, report: Record, routes: Record) -> None:
    """Check all generated geometry and known reachable/unreachable hold regimes."""
    require(report.get("status") == "ready", "the surveyed layout has a feasible nominal route")
    graph, blocked = report["navigation"], report["blocked_edges"]
    require(all(graph[key] == survey[key] for key in COMMON), "changed the commissioned platform or geometry")
    require(blocked.keys() == survey["closures"].keys(), "missing or foreign closure identities")
    require(all(isinstance(key, str) and key for key in graph["nodes"]), "malformed pose IDs")
    xy = complex(*survey["origin"])
    spacing = survey["step_m"]
    nodes = {}
    for key, (x, y, yaw) in graph["nodes"].items():
        require(all(type(a) in (int, float) and isfinite(a) for a in (x, y, yaw)), "nonfinite surveyed pose")
        location = (complex(x, y) - xy) / spacing
        ix, iy, ih = round(location.real), round(location.imag), round(yaw / (pi / 2))
        require(abs(location - complex(ix, iy)) < 1e-7 and abs(yaw - ih * pi / 2) < 1e-7, "nonlattice pose")
        nodes[key] = (ix, iy, ih % 4)
    require(nodes[graph["start"]] == tuple(survey["start"]) and nodes[graph["staging"]] == tuple(survey["staging"]),
            "generated graph changes the start or staging pose")
    identities = set()
    mapping = defaultdict(set)
    for edge in graph["edges"]:
        key = edge["id"]
        require(isinstance(key, str) and key and key not in identities, "duplicate or invalid edge ID")
        identities.add(key)
        require(len(edge["segments"]) == 1, "graph edge must be one primitive")
        piece = edge["segments"][0]
        n, v, w = (piece[field] for field in ("ticks", "v_mps", "w_radps"))
        require(type(n) is int and n > 0 and all(type(a) in (int, float) and isfinite(a) for a in (v, w)), "primitive type is invalid")
        maximum = survey["forward_max_mps"] if v > 0 else survey["reverse_max_mps"]
        require(0 < abs(v) <= maximum + 1e-12 and abs(w) <= survey["angular_max_radps"] + 1e-12, "bad speed or point turn")
        duration = survey["tick_seconds"] * n
        turn, length = abs(w * duration), abs(v * duration)
        if turn < 1e-10:
            require(abs(length - spacing) < 1e-7, "straight primitive does not advance one cell")
            minimum = spacing / maximum
        else:
            require(abs(turn - pi / 2) < 1e-7, "turn is not a quarter circle")
            radii = [spacing * rad for rad in survey["turn_radius_cells"]]
            radius = min(radii, key=lambda r: abs(r - length / turn))
            require(abs(radius - length / turn) < 1e-7, "turn radius is not commissioned")
            minimum = (pi / 2) * max(radius / maximum, 1 / survey["angular_max_radps"])
        require(n == ceil(minimum / survey["tick_seconds"] - 1e-12), "primitive did not use the minimum tick count")
        x, y, yaw = graph["nodes"][edge["source"]]
        end, rotation = rigid_motion(complex(x, y), yaw, v, w, duration)
        ex, ey, angle = graph["nodes"][edge["target"]]
        require(abs(end - complex(ex, ey)) < 1e-7 and abs(exp(1j * rotation) - exp(1j * angle)) < 1e-7,
                "reported edge target does not match its physical end pose")
        require(remains_clear(survey, complex(x, y), yaw, v, w, duration), "generated edge intersects static geometry")
        for closure, zone in survey["closures"].items():
            if not remains_clear(survey | {"obstacles": [zone]}, complex(x, y), yaw, v, w, duration):
                mapping[closure].add(key)
    for closure, ids in blocked.items():
        require(len(ids) == len(set(ids)) and set(ids) == mapping[closure], "wrong closed-zone swept occupancy")
    for closure, reachable in routes.items():
        time = distance(graph, set(blocked.get(closure, [])))
        require((time is not None and time <= survey["route_limit_ticks"]) == reachable, f"wrong route availability for {closure}")


def exercise_compiler(app: Path, root: Path, driver: type) -> dict[str, Record]:
    """Evaluate offline generated graphs and missions driven with real closures."""
    checks = {}

    def record(name: str, process: Callable[[], object]) -> None:
        """Keep named local evidence while treating invalid candidate output as failure."""
        try:
            checks[name] = {"passed": True, "observation": process()}
        except (Violation, KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError) as error:
            checks[name] = {"passed": False, "observation": str(error)}

    def mission(label: str, survey: Record, routes: Record, closed: str | None, *, restart: bool = False) -> Record:
        """Compile a layout, hold the chosen zone, and execute to confirmed charge."""
        report = invoke(app, root / f"compile-{label}", survey)
        qualify(survey, report, routes)
        deadline = survey["route_limit_ticks"] + 115
        held = report["blocked_edges"].get(closed, [])
        incident = {"name": label, "stage": 6, "tag": label[-6:], "navigation": report["navigation"], "deadline": deadline,
                    "holds": [(0, deadline + 5, held)]}
        if restart:
            incident.update(restart_at=9, map_holes=[(6, 13)], tag_delay=3, prestage_echo=True)
        evidence = drive_case(app, root / f"run-{label}", incident, driver)
        require(evidence["staged_at"] <= survey["route_limit_ticks"] + (7 if restart else 0), "staging exceeded travel budget")
        require(not set(evidence["route"]).intersection(held), "entered a held physical zone")
        return evidence

    both = layout()
    alternatives = {None: True, "north": True, "south": True}
    record("mission-close-north", lambda: mission("compiled-north", both, alternatives, "north"))
    record("mission-close-south", lambda: mission("compiled-south", both, alternatives, "south", restart=True))
    reverse = layout(start=[4, 0, 1], closures={}, route_limit_ticks=40)
    record("mission-reverse-quarter-circle", lambda: mission("compiled-astern", reverse, {None: True}, None))

    def one_route() -> bool:
        """Check a certified graph with one infeasible held regime and a viable nominal path."""
        survey = layout(obstacles=[*both["obstacles"], [-.62, -1.71, -.40, -.37]])
        report = invoke(app, root / "compile-single-corridor", survey)
        qualify(survey, report, {None: True, "north": False, "south": True})
        return True

    record("cannot-bypass-both-barriers", one_route)

    def blocked(layout_map: Record, name: str) -> bool:
        """Check a physical infeasibility or an insufficient commissioning deadline."""
        report = invoke(app, root / name, layout_map)
        require(report == {"status": "blocked", "navigation": None, "blocked_edges": {}}, "expected a blocked survey report")
        return True

    record("blocked-by-static-wall", lambda: blocked(layout(obstacles=[[-.73, -1.72, -.32, 1.71]]), "wall"))
    record("blocked-by-deadline", lambda: blocked(reverse | {"route_limit_ticks": 28}, "short-deadline"))

    def malformed() -> bool:
        """Confirm a bad radius report leaves the existing output intact."""
        require(invoke(app, root / "compile-invalid", layout(turn_radius_cells=[1, 1]), invalid=True), "invalid survey changed output")
        return True

    record("reject-invalid-survey", malformed)
    return checks
