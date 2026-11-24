"""Private, analytic fixtures for workcell replay, motion, and recovery."""

from cmath import rect
from itertools import permutations
from math import pi
from typing import Callable

from geometry import Json, axis_frame, close, interpolate, legal_trajectory, measured_clearance

Run = Callable[[str, Json, bool], Json | bool]
Robot = {
    "lengths_m": [1.0, 0.8],
    "radii_m": [0.045, 0.055],
    "joint_limits": [[-1.35, 1.35], [-1.6, 1.6], [-1.5, 1.5]],
    "max_speeds": [0.8, 1.25, 1.4],
}
Margin = 0.017


def capsule(a: complex, b: complex, radius: float) -> Json:
    """Encode a world or tool-frame capsule from complex endpoints."""
    return {"a": [a.real, a.imag], "b": [b.real, b.imag], "radius_m": radius}


def snapshot(revision: int, world: Json, load: Json | None = None) -> Json:
    """Build a snapshot whose ownership and revision are explicitly known."""
    return {"revision": revision, "objects": world, "attached": load}


def event(op: str, name: str, revision: int, **details: object) -> Json:
    """Create a revision event with a unique identity."""
    return {"op": op, "id": name, "event_id": f"message-{revision}",
            "revision": revision, "base_revision": revision - 1, **details}


def valid_shape(value: object, wanted: Json) -> bool:
    """Compare structured capsule values with the analytic expected pose."""
    if not isinstance(value, dict) or not close(value.get("radius_m"), wanted["radius_m"]):
        return False
    points = (value.get("a"), value.get("b"))
    if any(not isinstance(point, list) or len(point) != 2 for point in points):
        return False
    for order in (("a", "b"), ("b", "a")):
        if all(close(x, y) for point, endpoint in zip(points, order, strict=True)
               for x, y in zip(point, wanted[endpoint], strict=True)):
            return True
    return False


def has_revision(data: Json, revision: int) -> bool:
    """Check the integer revision without accepting booleans."""
    return type(data.get("revision")) is int and data["revision"] == revision


def scene_checks(run: Run) -> dict[str, bool]:
    """Validate world-to-tool and tool-to-world changes with explicit known poses."""
    # A grasp from a rotated tool frame, later slid and turned before release.
    grasp_q = [0.27, -0.38, 1.15]
    release_q = [-0.58, pi / 2, -0.18]
    local_a, local_b, radius = complex(0.12, 0.09), complex(0.46, -0.11), 0.047
    _, _, origin, heading = axis_frame(Robot, grasp_q)
    _, _, release_origin, release_heading = axis_frame(Robot, release_q)
    world = capsule(origin + local_a * heading, origin + local_b * heading, radius)
    detached = capsule(release_origin + release_heading * local_a, release_origin + release_heading * local_b, radius)
    clamp = capsule(complex(0, 1), complex(0.2, 1), 0.07)
    scene = snapshot(12, {"payload": world})
    inserted = event("add", "fixture", 13, capsule=clamp)
    grasped = event("attach", "payload", 14, q=grasp_q)
    released = event("detach", "payload", 15, q=release_q)
    shifted_clamp = capsule(complex(1.3, 0.9), complex(1.35, 0.8), 0.07)
    shifted = event("move", "fixture", 16, capsule=shifted_clamp)
    spec = {"robot": Robot, "initial_scene": scene}
    held = run("scene", spec | {"events": [inserted, grasped]}, False)
    attachment = held.get("attached")
    replayed = run("scene", spec | {"events": [inserted, grasped, released, shifted, grasped]}, False)
    removed = run("scene", spec | {"events": [inserted, event("remove", "payload", 14)]}, False)
    invalid = [
        [inserted, grasped, grasped | {"q": release_q}],
        [inserted, released],
        [inserted, event("attach", "payload", 14, q=[5, 0, 0])],
        [inserted, grasped, event("add", "payload", 15, capsule=world)],
        [inserted, event("move", "missing", 14, capsule=clamp)],
    ]
    return {
        "exact_revision_and_ownership": has_revision(held, 14) and isinstance(held.get("objects"), dict)
        and set(held["objects"]) == {"fixture"}
        and isinstance(attachment, dict) and attachment.get("id") == "payload",
        "rotated_grasp_pose": isinstance(attachment, dict) and valid_shape(attachment.get("capsule"),
                                                                           capsule(local_a, local_b, radius)),
        "detach_and_retransmission": has_revision(replayed, 16) and "attached" in replayed
        and replayed["attached"] is None and isinstance(replayed.get("objects"), dict)
        and valid_shape(replayed["objects"].get("payload"), detached)
        and valid_shape(replayed["objects"].get("fixture"), shifted_clamp),
        "remove_preserves_other_object": has_revision(removed, 14) and isinstance(removed.get("objects"), dict)
        and set(removed["objects"]) == {"fixture"} and valid_shape(removed["objects"]["fixture"], clamp),
        "bad_transactions_preserve_output": all(
            run("scene", spec | {"events": events}, True) for events in invalid),
    }


def path(*positions: list[float], step: int = 2000) -> list[Json]:
    """Create a timed trajectory from fixtures already known to meet speed limits."""
    return [{"time_ms": index * step, "q": q} for index, q in enumerate(positions)]


def sweep_checks(run: Run) -> dict[str, bool]:
    """Create narrow swept collisions off the midpoint, plus feasible controls."""
    start, end = [0.09, -0.72, 0.0], [0.09, 0.84, 0.0]
    test_length = 1.54
    angles = (0.311, -0.431)
    cases = []
    for angle, radius in zip(angles, (0.011, 0.015), strict=True):
        peg = 0.09 + rect(test_length, angle)
        cases.append((snapshot(32, {"thin-stop": capsule(peg, peg + rect(0.014, angle), radius)}), path(start, end)))
    load = {"id": "carrier", "capsule": capsule(complex(0.22, 0.02), complex(0.54, -0.01), 0.051)}
    angle = 0.265
    payload_peg = 0.09 + rect(2.26, angle)
    cases.append((snapshot(41, {"thin-stop": capsule(payload_peg, payload_peg + 0.009j, 0.016)}, load),
                  path(start, end)))
    resting = [0, 0, 1.3]
    _, _, hand, heading = axis_frame(Robot, resting)
    self_load = {"id": "carrier", "capsule": capsule((0.34 - hand) / heading, (0.51 + 0.01j - hand) / heading, 0.025)}
    cases.append((snapshot(43, {}, self_load), path(resting, resting)))

    def report(scene: Json, trajectory: list[Json]) -> Json:
        """Run the certificate command using a known scene."""
        return run("certify", {"robot": Robot, "scene": scene, "margin_m": Margin, "trajectory": trajectory}, False)

    def witness(artifact: Json, scene: Json, waypoints: list[Json]) -> bool:
        """Independently check that a reported fraction actually violates clearance."""
        index, fraction = artifact.get("segment_index"), artifact.get("witness_fraction")
        if not (has_revision(artifact, scene["revision"]) and artifact.get("status") == "collision"
                and type(index) is int and 0 <= index < len(waypoints) - 1
                and type(fraction) in (int, float) and 0 <= fraction <= 1):
            return False
        sample = interpolate(waypoints[index]["q"], waypoints[index + 1]["q"], fraction)
        return measured_clearance(Robot, scene, sample) < Margin + 1e-9

    def accepts(scene: Json, trajectory: list[Json]) -> bool:
        """Require a valid report with explicit null diagnostic fields."""
        result = report(scene, trajectory)
        return has_revision(result, scene["revision"]) and result.get("status") == "valid" and all(
            key in result and result[key] is None for key in ("segment_index", "witness_fraction"))

    results = [witness(report(scene, trajectory), scene, trajectory) for scene, trajectory in cases]
    clear = snapshot(44, {"remote": capsule(2.9 + 0.1j, 2.9 + 0.6j, 0.02)}, load)
    direct = path(start, end)
    violations = [
        (report(clear, path(start, end, step=20)), "speed_limit"),
        (report(clear, path(start, [1.8, 0.2, -0.2], step=10)), "joint_limit"),
    ]
    return {
        "continuous_arm_sweeps": all(results[:2]),
        "rotating_load_sweep": results[2],
        "load_upper_arm_contact": results[3],
        "valid_loaded_and_unloaded_controls": accepts(clear, direct) and accepts(snapshot(34, clear["objects"]), direct),
        "joint_and_speed_precedence": all(
            artifact.get("status") == status and type(artifact.get("segment_index")) is int
            and artifact["segment_index"] == 0 and "witness_fraction" in artifact and artifact["witness_fraction"] is None
            for artifact, status in violations),
        "malformed_waypoint_preserves_output": bool(run("certify", {
            "robot": Robot, "scene": clear, "margin_m": Margin,
            "trajectory": [{"time_ms": 0, "q": start}, {"time_ms": 0, "q": end}],
        }, True)),
    }


def recovery_case(sign: float, phase: float, start: list[float], measured: list[float]) -> tuple[Json, Json]:
    """Define a stale direct move whose attached load crosses a displaced fixture."""
    goal = [0.09, sign * 0.85, 0.0]
    load = {"id": "carrier", "capsule": capsule(0.24 + 0.045j, 0.54 - 0.012j, 0.058)}
    radius = 0.029
    old_peg = complex(-2.85, -1.35)
    new_peg = 0.09 + rect(2.25, phase)
    initial = snapshot(51, {"fixture": capsule(old_peg, old_peg + 0.1j, radius)}, load)
    shifted = capsule(new_peg, new_peg + 0.045j, radius)
    update = event("move", "fixture", 52, capsule=shifted)
    spec = {"robot": Robot, "initial_scene": initial, "events": [update], "planned_revision": 51,
            "margin_m": Margin, "remaining": path(start, goal), "measured_q": measured, "goal_q": goal}
    return spec, snapshot(52, {"fixture": shifted}, load)


def obstructed_workcell() -> tuple[Json, Json]:
    """Build a workcell with a proven detour and blocked single-axis shortcuts."""
    start = [-0.45, -0.81, 0.69]
    goal = [0.41, 0.91, -0.63]
    load = {"id": "long-tote", "capsule": capsule(0.22 + 0.02j, 0.57 - 0.05j, 0.075)}
    fixtures = {
        "top-shelf": capsule(0.4091 + 1.6479j, 0.2664 + 1.6467j, 0.1951),
        "inner-post": capsule(0.9040 - 0.5567j, 0.8169 - 0.4334j, 0.0705),
        "gate": capsule(1.5928 - 0.2035j, 1.4811 - 0.1467j, 0.1696),
        "outer-post": capsule(2.8846 - 0.5621j, 3.0155 - 0.4480j, 0.0776),
        "lower-shelf": capsule(0.6362 - 1.4793j, 0.7710 - 1.3869j, 0.1946),
    }
    initial_fixtures = {
        name: capsule(-2.9 + 0.16j * index, -2.9 + 0.16j * index, shape["radius_m"])
        for index, (name, shape) in enumerate(fixtures.items())
    }
    final = snapshot(56, fixtures, load)
    initial = snapshot(51, initial_fixtures, load)
    witness = path(start, [-0.86, -1.30, 1.43], [-1.30, -0.96, 1.42],
                   [-0.04, 0.75, -0.41], goal, step=3000)
    if not legal_trajectory(Robot, final, witness, start, goal, Margin):
        raise RuntimeError("broken fixture: witness must establish that a loaded detour exists")
    for order in permutations(range(3)):
        single_axis = [start]
        for axis in order:
            q = list(single_axis[-1])
            q[axis] = goal[axis]
            single_axis.append(q)
        if legal_trajectory(Robot, final, path(*single_axis), start, goal, Margin):
            raise RuntimeError("broken fixture: independent joint-order shortcut is valid")
    return {
        "robot": Robot, "initial_scene": initial, "planned_revision": 51, "margin_m": Margin,
        "events": [event("move", name, index, capsule=shape) for index, (name, shape) in enumerate(fixtures.items(), 52)],
        "remaining": path(start, goal), "measured_q": start, "goal_q": goal,
    }, final


def recovery_checks(run: Run) -> dict[str, bool]:
    """Require a certified detour, reuse on safe revisions, and stop from unsafe poses."""
    cases = [
        recovery_case(1, 0.29, [0.09, -0.72, 0.0], [0.09, -0.72, 0.0]),
        recovery_case(-1, -0.37, [0.09, 0.73, 0.0], [0.17, 0.57, 0.14]),
        recovery_case(1, 0.42, [0.09, -0.68, 0.0], [-0.035, -0.53, -0.09]),
        obstructed_workcell(),
    ]

    def reroutes(spec: Json, scene: Json) -> bool:
        """Check one returned trajectory poses, timing, scene, and continuous clearance."""
        result = run("recover", spec, False)
        return has_revision(result, scene["revision"]) and result.get("status") == "replanned" and legal_trajectory(
            Robot, scene, result.get("trajectory"), spec["measured_q"], spec["goal_q"], Margin)

    for spec, scene in cases:
        if legal_trajectory(Robot, scene, spec["remaining"], spec["remaining"][0]["q"], spec["goal_q"], Margin):
            raise RuntimeError("broken fixture: late revision should obstruct the old path")
        if measured_clearance(Robot, scene, spec["measured_q"]) <= Margin:
            raise RuntimeError("broken fixture: late revision blocks recovery at the measured pose")

    base, _ = cases[0]
    harmless = event("move", "fixture", 52, capsule=capsule(-2.7 + 2.7j, -2.6 + 2.5j, 0.06))
    reused = run("recover", base | {"events": [harmless]}, False)
    _, _, hand, heading = axis_frame(Robot, base["measured_q"])
    collision = hand + 0.35 * heading
    trap = event("move", "fixture", 52, capsule=capsule(collision, collision, 0.07))
    stopped = run("recover", base | {"events": [trap]}, False)
    late_reuse = run("recover", base | {"events": [harmless, harmless]}, False)
    return {
        "replan_thin_obstacle_loaded": reroutes(*cases[0]),
        "recover_from_measured_pose": reroutes(*cases[1]),
        "replan_variant_under_same_revision": reroutes(*cases[2]),
        "coordinate_links_through_multi_fixture_update": reroutes(*cases[3]),
        "reuse_safe_path_on_revision_advance": all(
            has_revision(report, 52) and report.get("status") == "unchanged" and report.get("trajectory") == base["remaining"]
            for report in (reused, late_reuse)),
        "stop_at_obstructed_measurement": has_revision(stopped, 52) and stopped.get("status") == "stopped"
        and "trajectory" in stopped and stopped["trajectory"] is None,
        "bad_plan_revision_preserves_output": bool(run("recover", base | {"planned_revision": 50}, True)),
    }
