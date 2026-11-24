"""Certify and search timed workcell moves against tracked capsules."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from heapq import heappop, heappush
from math import hypot, isclose

from .model import (
    Capsule, Joint, Object, Point, Robot, array, capsule, frame,
    identifier, integer, joint, number, obj, point, world_point,
)
from .motion import clearance, mix


CLEARANCE_TOLERANCE = 1e-9
BRAKE_TOLERANCE = 1e-8
State = tuple[str, int]


@dataclass(frozen=True)
class Track:
    """Represent a capsule whose endpoints interpolate on a relative tick axis."""

    ticks: tuple[int, ...]
    endpoints: tuple[tuple[Point, Point], ...]
    radius: float

    def at(self, tick: float) -> Capsule:
        """Sample the track, holding the first or last pose outside its keyframes."""
        upper = bisect_right(self.ticks, tick)
        if upper == 0:
            a, b = self.endpoints[0]
        elif upper == len(self.ticks):
            a, b = self.endpoints[-1]
        else:
            lower = upper - 1
            fraction = (tick - self.ticks[lower]) / (self.ticks[upper] - self.ticks[lower])
            (a0, b0), (a1, b1) = self.endpoints[lower], self.endpoints[upper]
            a = point_mix(a0, a1, fraction)
            b = point_mix(b0, b1, fraction)
        return Capsule(a, b, self.radius)


@dataclass(frozen=True)
class Edge:
    """A directed transfer with a deterministic positive duration in ticks."""

    id: str
    source: str
    target: str
    ticks: int


@dataclass(frozen=True)
class Window:
    """A validated planning window with a clock relative to the measurement."""

    fixtures: tuple[Capsule, ...]
    payload: tuple[Capsule, ...]
    tracks: tuple[Track, ...]
    tick_seconds: float
    margin: float
    velocity: Joint
    acceleration: Joint
    nodes: dict[str, Joint]
    edges: tuple[Edge, ...]
    tick_origin: int
    measured_q: Joint
    measured_dq: Joint
    start: str
    goal: str
    brake_ticks: int
    horizon: int


@dataclass(frozen=True)
class Sweep:
    """A wait, rest-to-rest transfer, or braking curve in relative ticks."""

    start: int
    end: int
    first: Joint
    last: Joint
    braking: bool = False

    def progress(self, tick: float) -> float:
        """Map a relative tick to the scalar along the joint-space segment."""
        if self.start == self.end:
            return 0.0
        u = (tick - self.start) / (self.end - self.start)
        return u * (2 - u) if self.braking else u * u * (3 - 2 * u)


def point_mix(a: Point, b: Point, fraction: float) -> Point:
    """Interpolate a pair of 2D coordinates."""
    return a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])


def read_track(value: object, origin: int) -> Track:
    """Read tracked capsule keyframes and shift their ticks to the measurement origin."""
    data = obj(value)
    frames = [obj(item) for item in array(data["keyframes"])]
    ticks = tuple(integer(item["tick"]) for item in frames)
    if not ticks or ticks[0] < 0 or any(before >= after for before, after in zip(ticks, ticks[1:])):
        raise ValueError("fixture keyframe ticks must be nonnegative and strictly increasing")
    return Track(tuple(tick - origin for tick in ticks),
                 tuple((point(item["a"]), point(item["b"])) for item in frames),
                 number(data["radius_m"], positive=True))


def read_window(robot: Robot, spec: Object) -> Window:
    """Parse the timed planner inputs without deciding whether the motion is feasible."""
    measured = obj(spec["measured"])
    origin = integer(measured["tick"])
    horizon = integer(spec["deadline"]) - origin
    brake_ticks = integer(spec["brake_ticks"])
    if origin < 0 or not 0 <= horizon <= 128 or brake_ticks < 0:
        raise ValueError("invalid measured tick, deadline, or braking duration")
    limits = obj(spec["limits"])
    velocity = tuple(min(old, timed) for old, timed in zip(robot.speeds, joint(limits["velocity"], positive=True)))
    acceleration = joint(limits["acceleration"], positive=True)
    tick_seconds = number(spec["tick_seconds"], positive=True)
    margin = number(spec["margin"])
    if margin < 0:
        raise ValueError("clearance margin must be nonnegative")

    nodes = {identifier(name): joint(raw) for name, raw in obj(spec["nodes"]).items()}
    start, goal = identifier(spec["start_node"]), identifier(spec["goal_node"])
    if start not in nodes or goal not in nodes:
        raise ValueError("start and goal must identify graph nodes")
    edges = []
    edge_ids = set()
    for item in array(spec["edges"]):
        data = obj(item)
        edge = Edge(identifier(data["id"]), identifier(data["source"]), identifier(data["target"]), integer(data["ticks"]))
        if edge.id in edge_ids or edge.source not in nodes or edge.target not in nodes or edge.ticks <= 0:
            raise ValueError("invalid transfer, unknown endpoint, or duplicate edge ID")
        edge_ids.add(edge.id)
        edges.append(edge)

    scene = obj(spec["scene"])
    return Window(tuple(map(capsule, array(scene["fixtures"]))), tuple(map(capsule, array(scene["payload"]))),
                  tuple(read_track(track, origin) for track in array(spec["moving_fixtures"])),
                  tick_seconds, margin, velocity, acceleration, nodes, tuple(edges), origin,
                  joint(measured["q"]), joint(measured["dq"]), start, goal, brake_ticks, horizon)


def body_shapes(robot: Robot, payload: tuple[Capsule, ...], q: Joint) -> tuple[Capsule, ...]:
    """Construct upper arm, forearm and rigidly attached capsules in world coordinates."""
    base, elbow, tip, heading = frame(robot, q)
    return (Capsule(base, elbow, robot.radii[0]), Capsule(elbow, tip, robot.radii[1]),
            *(Capsule(world_point(item.a, tip, heading), world_point(item.b, tip, heading), item.radius)
              for item in payload))


def body_travel(robot: Robot, payload: tuple[Capsule, ...], first: Joint, last: Joint) -> tuple[float, ...]:
    """Bound centreline travel per unit of joint interpolation progress."""
    slide, shoulder, elbow = (end - start for start, end in zip(first, last))
    turn = abs(shoulder + elbow)
    upper = abs(slide) + robot.lengths[0] * abs(shoulder)
    lower = upper + robot.lengths[1] * turn
    return (upper, lower, *(lower + max(hypot(*item.a), hypot(*item.b)) * turn for item in payload))


def certify_sweep(robot: Robot, window: Window, sweep: Sweep, *, tracked: bool = False) -> bool:
    """Verify all continuous clearance for either static pairs or the tracked obstacles.

    Capsule separation changes by at most the sum of each centreline's endpoint
    travel bound. Split at fixture keyframes so endpoint paths are affine on each
    interval. At a midpoint compare the measured gap minus the travel allowance
    to the margin and subdivide whenever the certificate is inconclusive.
    """
    if tracked and not window.tracks:
        return True
    if not tracked and not (window.fixtures or window.payload):
        return True
    travel = body_travel(robot, window.payload, sweep.first, sweep.last)
    cuts = {sweep.start, sweep.end}
    if tracked:
        cuts.update(t for track in window.tracks for t in track.ticks if sweep.start < t < sweep.end)
    ordered = sorted(cuts)
    ranges = list(zip(ordered, ordered[1:])) or [(sweep.start, sweep.end)]
    minimum = window.margin - CLEARANCE_TOLERANCE

    for first, last in ranges:
        fixed = window.fixtures if not tracked else ()
        rates = []
        if tracked and first != last:
            for track in window.tracks:
                a, b = track.at(first), track.at(last)
                rates.append(max(hypot(a.a[0] - b.a[0], a.a[1] - b.a[1]),
                                 hypot(a.b[0] - b.b[0], a.b[1] - b.b[1])) / (last - first))
        else:
            rates = [0.0] * (len(window.tracks) if tracked else len(fixed))

        pending = [(first, last, 0)]
        checked = 0
        while pending:
            lower, upper, depth = pending.pop()
            checked += 1
            midpoint = (lower + upper) / 2
            progress = sweep.progress(midpoint)
            progress_radius = max(progress - sweep.progress(lower), sweep.progress(upper) - progress)
            shapes = body_shapes(robot, window.payload, mix(sweep.first, sweep.last, progress))
            geometry = tuple(track.at(midpoint) for track in window.tracks) if tracked else fixed
            radius = (upper - lower) / 2
            agenda = [(clearance(shape, fixture), bound * progress_radius + rate * radius)
                      for shape, bound in zip(shapes, travel)
                      for fixture, rate in zip(geometry, rates)]
            if not tracked:
                agenda.extend((clearance(shapes[0], shape), (travel[0] + bound) * progress_radius)
                              for shape, bound in zip(shapes[2:], travel[2:]))
            if any(gap < minimum for gap, _ in agenda):
                return False
            if all(gap - uncertainty >= minimum for gap, uncertainty in agenda):
                continue
            if depth >= 24 or checked >= 8192:
                return False
            pending.extend(((lower, midpoint, depth + 1), (midpoint, upper, depth + 1)))
    return True


def brake(robot: Robot, window: Window) -> Sweep | None:
    """Certify the prescribed brake profile and its match to the graph start."""
    q = window.measured_q
    start = window.nodes[window.start]
    ticks = window.brake_ticks
    moving = any(window.measured_dq)
    if ticks > window.horizon or bool(ticks) != moving:
        return None
    duration = ticks * window.tick_seconds
    endpoint = tuple(position + speed * duration / 2 for position, speed in zip(q, window.measured_dq))
    if not (robot.has_joint_position(q) and robot.has_joint_position(endpoint) and robot.has_joint_position(start)):
        return None
    if not all(isclose(actual, target, abs_tol=BRAKE_TOLERANCE, rel_tol=0) for actual, target in zip(endpoint, start)):
        return None
    for speed, maximum, acceleration in zip(window.measured_dq, window.velocity, window.acceleration):
        if abs(speed) > min(maximum, acceleration * duration) * (1 + 1e-12):
            return None
    motion = Sweep(0, ticks, q, endpoint, braking=True)
    if not (certify_sweep(robot, window, motion) and certify_sweep(robot, window, motion, tracked=True)):
        return None
    if endpoint != start:
        rounded_stop = Sweep(ticks, ticks, start, start)
        if not (certify_sweep(robot, window, rounded_stop) and certify_sweep(robot, window, rounded_stop, tracked=True)):
            return None
    return motion


def command(window: Window, kind: str, start: int, end: int, identity: str) -> Object:
    """Encode a command using absolute ticks and the field required by its kind."""
    return {"kind": kind, "start": start + window.tick_origin, "end": end + window.tick_origin,
            ("edge" if kind == "move" else "node"): identity}


def fast_potential(edges: tuple[Edge, ...], goal: str) -> dict[str, int]:
    """Compute admissible minimum travel times to the goal ignoring obstacles."""
    reversed_graph: dict[str, list[Edge]] = defaultdict(list)
    for edge in edges:
        reversed_graph[edge.target].append(edge)
    costs = {goal: 0}
    queue = [(0, goal)]
    while queue:
        elapsed, target = heappop(queue)
        if costs[target] != elapsed:
            continue
        for edge in reversed_graph[target]:
            candidate = elapsed + edge.ticks
            if edge.source not in costs or candidate < costs[edge.source]:
                costs[edge.source] = candidate
                heappush(queue, (candidate, edge.source))
    return costs


def valid_edges(robot: Robot, window: Window) -> tuple[Edge, ...]:
    """Keep directed transfers meeting position, velocity and acceleration limits."""
    valid_nodes = {name for name, q in window.nodes.items() if robot.has_joint_position(q)}
    allowed = []
    for edge in window.edges:
        if edge.source not in valid_nodes or edge.target not in valid_nodes or edge.ticks > window.horizon:
            continue
        seconds = window.tick_seconds * edge.ticks
        differences = [abs(a - b) for a, b in zip(window.nodes[edge.source], window.nodes[edge.target])]
        if all(1.5 * d <= v * seconds * (1 + 1e-12) and 6 * d <= a * seconds ** 2 * (1 + 1e-12)
               for d, v, a in zip(differences, window.velocity, window.acceleration)):
            allowed.append(edge)
    return tuple(allowed)


def reconstruct(window: Window, state: State, previous: dict[State, tuple[State, Edge | None]]) -> list[Object]:
    """Reconstruct transfers and combine consecutive stationary ticks into waits."""
    reverse_commands = []
    while state in previous:
        prior, edge = previous[state]
        if edge is None:
            item = command(window, "wait", prior[1], state[1], state[0])
            if reverse_commands and reverse_commands[-1]["kind"] == "wait" and reverse_commands[-1]["node"] == state[0]:
                reverse_commands[-1]["start"] = item["start"]
            else:
                reverse_commands.append(item)
        else:
            reverse_commands.append(command(window, "move", prior[1], state[1], edge.id))
        state = prior
    return reverse_commands[::-1]


def route(robot: Robot, window: Window) -> list[Object] | None:
    """Search all reachable certified node/tick states up to the mission deadline."""
    edges = valid_edges(robot, window)
    potential = fast_potential(edges, window.goal)
    if window.start not in potential or window.brake_ticks + potential[window.start] > window.horizon:
        return None
    outgoing: dict[str, list[Edge]] = defaultdict(list)
    for edge in edges:
        if edge.target in potential:
            outgoing[edge.source].append(edge)

    @cache
    def static_move(edge: Edge) -> bool:
        """Cache fixed-fixture clearance for a transfer independently of its departure tick."""
        sweep = Sweep(0, edge.ticks, window.nodes[edge.source], window.nodes[edge.target])
        return certify_sweep(robot, window, sweep)

    @cache
    def static_wait(name: str) -> bool:
        """Check fixed-fixture clearance for a stationary graph configuration once."""
        q = window.nodes[name]
        return certify_sweep(robot, window, Sweep(0, 0, q, q))

    start = (window.start, window.brake_ticks)
    previous: dict[State, tuple[State, Edge | None]] = {}
    queue = [(start[1] + potential[window.start], start[1], start[0])]
    while queue:
        _, tick, name = heappop(queue)
        state = (name, tick)
        if name == window.goal:
            return reconstruct(window, state, previous)

        for edge in (*outgoing[name], None):
            target = name if edge is None else edge.target
            arrival = tick + (1 if edge is None else edge.ticks)
            estimate = arrival + potential[target]
            following = (target, arrival)
            if estimate > window.horizon or following in previous:
                continue
            if not (static_wait(name) if edge is None else static_move(edge)):
                continue
            sweep = Sweep(tick, arrival, window.nodes[name], window.nodes[target])
            if not certify_sweep(robot, window, sweep, tracked=True):
                continue
            previous[following] = (state, edge)
            heappush(queue, (estimate, arrival, target))
    return None


def plan_window(robot: Robot, spec: Object) -> Object:
    """Return a complete timed route or the certified stopping commands for this window."""
    window = read_window(robot, spec)
    stopped = brake(robot, window)
    if stopped is None:
        return {"status": "blocked", "commands": []}
    commands = []
    if stopped.end:
        commands.append(command(window, "brake", 0, stopped.end, window.start))
    plan = route(robot, window)
    if plan is not None:
        return {"status": "ready", "commands": commands + plan}

    q = window.nodes[window.start]
    if stopped.end < window.horizon:
        hold = Sweep(stopped.end, window.horizon, q, q)
        if not (certify_sweep(robot, window, hold) and certify_sweep(robot, window, hold, tracked=True)):
            return {"status": "blocked", "commands": []}
        commands.append(command(window, "wait", hold.start, hold.end, window.start))
    return {"status": "blocked", "commands": commands}
