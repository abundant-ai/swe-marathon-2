"""Verify timed workcell commands without calling the planner or its certificates."""

from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite
from typing import Literal

from geometry import Json, axis_frame, line_of, separation


Joint = tuple[float, float, float]
Capsule = tuple[complex, complex, float]
Cursor = tuple[int, str | None]
Kind = Literal["brake", "wait", "move"]

JOINT_TOLERANCE = 1e-8
CLEARANCE_TOLERANCE = 1e-9
MIN_INTERVAL_TICKS = 2 ** -20
MAX_INTERVALS = 65_536


@dataclass(frozen=True)
class Motion:
    """One commanded profile, with position given as start plus a scaled displacement."""

    kind: Kind
    tick: int
    ticks: int
    initial: Joint
    delta: Joint

    def fraction(self, elapsed_ticks: float) -> float:
        """Return the monotone position fraction at a tick offset within this command."""
        u = elapsed_ticks / self.ticks
        if self.kind == "brake":
            return u * (2 - u)
        if self.kind == "move":
            return u * u * (3 - 2 * u)
        return 0.0

    def q_at(self, elapsed_ticks: float) -> Joint:
        """Evaluate all three joints at a tick offset within this command."""
        fraction = self.fraction(elapsed_ticks)
        return tuple(q + fraction * step for q, step in zip(self.initial, self.delta, strict=True))

    def travel_coefficients(self, robot: Json, payload: list[Capsule]) -> tuple[float, ...]:
        """Bound each body's centreline travel per unit change in profile fraction."""
        slide, shoulder, elbow = self.delta
        upper_length, lower_length = robot["lengths_m"]
        upper = abs(slide) + upper_length * abs(shoulder)
        heading = abs(shoulder + elbow)
        lower = upper + lower_length * heading
        return (upper, lower, *(lower + max(abs(a), abs(b)) * heading for a, b, _ in payload))


@dataclass(frozen=True)
class Track:
    """One capsule whose two world-frame endpoints vary piecewise linearly."""

    ticks: tuple[int, ...]
    capsules: tuple[Capsule, ...]

    def at(self, elapsed_ticks: float) -> Capsule:
        """Interpolate endpoints at a relative tick, holding each end of the track."""
        index = bisect_right(self.ticks, elapsed_ticks)
        if index == 0:
            return self.capsules[0]
        if index == len(self.ticks):
            return self.capsules[-1]
        previous, following = index - 1, index
        left, right = self.ticks[previous], self.ticks[following]
        weight = (elapsed_ticks - left) / (right - left)
        a, b, radius = self.capsules[previous]
        c, d, _ = self.capsules[following]
        return a + weight * (c - a), b + weight * (d - b), radius


def track_for(fixture: Json, base_tick: int) -> Track:
    """Re-express fixture keyframes relative to one command's start tick."""
    radius = fixture["radius_m"]
    keyframes = fixture["keyframes"]
    return Track(
        tuple(frame["tick"] - base_tick for frame in keyframes),
        tuple((complex(*frame["a"]), complex(*frame["b"]), radius) for frame in keyframes),
    )


def bodies_at(robot: Json, payload: list[Capsule], q: Joint) -> tuple[Capsule, ...]:
    """Place the arm and any tool-local payload capsules in workcell coordinates."""
    origin, pivot, hand, heading = axis_frame(robot, q)
    upper, lower = robot["radii_m"]
    return ((origin, pivot, upper), (pivot, hand, lower),
            *((hand + heading * a, hand + heading * b, r) for a, b, r in payload))


def pair_clearances(
    body: tuple[Capsule, ...],
    body_travel: tuple[float, ...],
    obstacles: tuple[Capsule, ...],
    obstacle_travel: tuple[float, ...],
    margin: float,
) -> tuple[bool, bool]:
    """Return whether the sample and its whole bounded neighborhood clear the margin."""
    certified = True
    for part, travel in zip(body, body_travel, strict=True):
        for obstacle, movement in zip(obstacles, obstacle_travel, strict=True):
            clearance = separation(part, obstacle) - margin
            if clearance < -CLEARANCE_TOLERANCE:
                return False, False
            certified &= clearance >= travel + movement - CLEARANCE_TOLERANCE
    # The connected links may overlap at their joint. Compare each payload to the upper link.
    for load, travel in zip(body[2:], body_travel[2:], strict=True):
        clearance = separation(body[0], load) - margin
        if clearance < -CLEARANCE_TOLERANCE:
            return False, False
        certified &= clearance >= body_travel[0] + travel - CLEARANCE_TOLERANCE
    return True, certified


def static_clearance(spec: Json, tick: int, q: Joint) -> bool:
    """Check closed-time clearance at one supplied posture and tick."""
    payload = [line_of(item) for item in spec["scene"]["payload"]]
    body = bodies_at(spec["robot"], payload, q)
    obstacles = tuple(line_of(item) for item in spec["scene"]["fixtures"])
    obstacles += tuple(track_for(item, tick).at(0) for item in spec["moving_fixtures"])
    return pair_clearances(body, (0.0,) * len(body), obstacles, (0.0,) * len(obstacles), spec["margin"])[0]


def swept_clearance(spec: Json, motion: Motion) -> bool:
    """Prove continuous clearance, subdividing when exact samples leave an uncertain interval.

    A capsule centreline's Hausdorff distance from its sampled location is bounded
    by the greater travel of its endpoints. Unsampled distance can therefore
    decrease by at most the sum of the two bodies' motion bounds. Every fixture
    keyframe is a split, so moving fixture endpoints are affine on each interval.
    """
    robot, margin = spec["robot"], spec["margin"]
    payload = [line_of(item) for item in spec["scene"]["payload"]]
    fixed = tuple(line_of(item) for item in spec["scene"]["fixtures"])
    moving = tuple(track_for(item, motion.tick) for item in spec["moving_fixtures"])
    fractions_to_travel = motion.travel_coefficients(robot, payload)
    cuts = sorted({0, motion.ticks} | {tick for track in moving for tick in track.ticks if 0 < tick < motion.ticks})
    fixed_travel = (0.0,) * len(fixed)

    for tick in cuts:
        body = bodies_at(robot, payload, motion.q_at(tick))
        obstacles = fixed + tuple(track.at(tick) for track in moving)
        if not pair_clearances(body, (0.0,) * len(body), obstacles, (0.0,) * len(obstacles), margin)[0]:
            return False

    intervals = list(zip(cuts, cuts[1:]))
    visited = 0
    while intervals:
        visited += 1
        if visited > MAX_INTERVALS:
            return False
        left, right = intervals.pop()
        middle = (left + right) / 2
        midpoint_fraction = motion.fraction(middle)
        excursion = max(midpoint_fraction - motion.fraction(left), motion.fraction(right) - midpoint_fraction)
        body = bodies_at(robot, payload, motion.q_at(middle))
        body_travel = tuple(coefficient * excursion for coefficient in fractions_to_travel)
        moving_midpoint = tuple(track.at(middle) for track in moving)
        obstacle_travel = fixed_travel + tuple(
            max(max(abs(a - p), abs(b - q)) for p, q, _ in (track.at(left), track.at(right)))
            for track, (a, b, _) in zip(moving, moving_midpoint, strict=True)
        )
        sampled, proved = pair_clearances(body, body_travel, fixed + moving_midpoint, obstacle_travel, margin)
        if not sampled:
            return False
        if not proved:
            if right - left <= MIN_INTERVAL_TICKS:
                return False
            intervals.extend(((left, middle), (middle, right)))
    return True


def kinematics_valid(spec: Json, motion: Motion) -> bool:
    """Check the analytic extrema of joint position, speed and acceleration."""
    starting, ending = motion.initial, motion.q_at(motion.ticks)
    joint_bounds = spec["robot"]["joint_limits"]
    if not all(low - JOINT_TOLERANCE <= first <= high + JOINT_TOLERANCE
               and low - JOINT_TOLERANCE <= last <= high + JOINT_TOLERANCE
               for first, last, (low, high) in zip(starting, ending, joint_bounds, strict=True)):
        return False
    duration = motion.ticks * spec["tick_seconds"]
    velocity_scale, acceleration_scale = {
        "wait": (0, 0), "brake": (2, 2), "move": (1.5, 6),
    }[motion.kind]
    speeds = spec["robot"]["max_speeds"]
    for delta, robot_speed, speed, acceleration in zip(
        motion.delta, speeds, spec["limits"]["velocity"], spec["limits"]["acceleration"], strict=True,
    ):
        velocity_peak = velocity_scale * abs(delta) / duration
        acceleration_peak = acceleration_scale * abs(delta) / duration**2
        if (velocity_peak > min(robot_speed, speed) + JOINT_TOLERANCE
                or acceleration_peak > acceleration + JOINT_TOLERANCE):
            return False
    return True


def same_joints(first: Joint, second: Joint) -> bool:
    """Compare finite joint readings with an absolute tolerance in joint units."""
    return all(isfinite(a) and isfinite(b) and abs(a - b) <= JOINT_TOLERANCE
               for a, b in zip(first, second, strict=True))


def stationary_start(spec: Json) -> bool:
    """Check the measured pose when the specification requires no braking."""
    measured = spec["measured"]
    q = tuple(measured["q"])
    zero = (0.0, 0.0, 0.0)
    return (same_joints(q, spec["nodes"][spec["start_node"]]) and same_joints(measured["dq"], zero)
            and all(low - JOINT_TOLERANCE <= value <= high + JOINT_TOLERANCE
                    for value, (low, high) in zip(q, spec["robot"]["joint_limits"], strict=True))
            and static_clearance(spec, measured["tick"], q))


def run_command(spec: Json, command: object, tick: int, node: str | None) -> Cursor | None:
    """Validate one command given an earlier accepted execution cursor.

    A null node denotes a pending initial brake from the measured tick. A
    successful result advances to the command's ending tick and resting node.
    A malformed or uncertifiable command returns None.
    """
    if not isinstance(command, dict) or type(command.get("start")) is not int or type(command.get("end")) is not int:
        return None
    end, kind = command["end"], command.get("kind")
    if command["start"] != tick or not tick < end <= spec["deadline"]:
        return None
    ticks = end - tick
    nodes, start_node = spec["nodes"], spec["start_node"]
    if node is None:
        measured = spec["measured"]
        if (kind != "brake" or command.get("node") != start_node or tick != measured["tick"]
                or ticks != spec["brake_ticks"]):
            return None
        initial = tuple(measured["q"])
        duration = ticks * spec["tick_seconds"]
        delta = tuple(value * duration / 2 for value in measured["dq"])
        target = start_node
        motion = Motion("brake", tick, ticks, initial, delta)
        if not same_joints(motion.q_at(ticks), nodes[target]):
            return None
    elif kind == "wait" and command.get("node") == node:
        target = node
        motion = Motion("wait", tick, ticks, tuple(nodes[node]), (0.0, 0.0, 0.0))
    elif kind == "move":
        edge = next((edge for edge in spec["edges"] if edge["id"] == command.get("edge")), None)
        if edge is None or edge["source"] != node or edge["ticks"] != ticks:
            return None
        target = edge["target"]
        initial = tuple(nodes[node])
        delta = tuple(last - first for first, last in zip(initial, nodes[target], strict=True))
        motion = Motion("move", tick, ticks, initial, delta)
    else:
        return None
    if not kinematics_valid(spec, motion) or not swept_clearance(spec, motion):
        return None
    return end, target


def valid_prefix(spec: Json, commands: object, *, stop_at_goal: bool = False) -> Cursor | None:
    """Validate a partial contiguous execution from the measured state."""
    measured_tick, deadline = spec["measured"]["tick"], spec["deadline"]
    if not isinstance(commands, list) or len(commands) > deadline - measured_tick:
        return None
    if spec["brake_ticks"] == 0:
        if not stationary_start(spec):
            return None
        cursor = (measured_tick, spec["start_node"])
    else:
        cursor = (measured_tick, None)
    for command in commands:
        if stop_at_goal and cursor[1] == spec["goal_node"]:
            return None
        cursor = run_command(spec, command, *cursor)
        if cursor is None:
            return None
    return cursor


def valid_plan(spec: Json, report: object, *, expect_ready: bool) -> bool:
    """Check a complete plan against an independently known feasible or blocked mission."""
    if not isinstance(report, dict) or report.get("status") != ("ready" if expect_ready else "blocked"):
        return False
    commands = report.get("commands")
    if not isinstance(commands, list):
        return False
    if not expect_ready and not commands:
        start = spec["measured"]["tick"]
        brake_end = start + spec["brake_ticks"]
        node, deadline = spec["start_node"], spec["deadline"]
        fallback = []
        if spec["brake_ticks"]:
            fallback.append({"kind": "brake", "start": start, "end": brake_end, "node": node})
        if brake_end < deadline:
            fallback.append({"kind": "wait", "start": brake_end, "end": deadline, "node": node})
        return not fallback or valid_prefix(spec, fallback) is None

    end_state = valid_prefix(spec, commands, stop_at_goal=expect_ready)
    if end_state is None:
        return False
    tick, node = end_state
    if expect_ready:
        return node == spec["goal_node"] and tick <= spec["deadline"]
    return (node == spec["start_node"] and tick == spec["deadline"]
            and all(command["kind"] in ("brake", "wait") for command in commands))
