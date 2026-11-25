"""Closed-loop lidar missions through recorded and authored cylinder fields.

The verifier owns the true field: cylinders on a fixed lattice, the closed
rectangular arena and optional moving discs. Each tick it reports the exact
pose, the twist applied over the previous tick, a planar range scan and, when
the mission has movers, their tracks. A returned twist is checked against the
speed and acceleration limits and then certified over the whole tick against
every obstacle before it is applied.
"""

from cmath import exp, phase
from math import asin, ceil, floor, pi, sin, sqrt, tau
import json

from courses import MISSIONS
from transport import Driver, Violation, require, writable

WIDTH, HEIGHT = 4.5, 7.5
ORIGIN = complex(0.075, 1.575)
PITCH = 0.15
COLUMNS = ROWS = 30
CYLINDER = 0.075
START, GOAL = (2.25, 0.75), (2.25, 6.75)
SCAN = {"angle_min_rad": -0.75 * pi, "angle_increment_rad": 1.5 * pi / 360, "count": 361,
        "range_min_m": 0.05, "range_max_m": 3.0}
PARAMETERS = ("radius_m", "margin_m", "dt", "max_v", "max_w", "max_accel", "max_alpha",
              "goal_tolerance_m", "deadline")
SLACK = 1e-9
CERTIFY_LIMIT = 4096


def motion(z: complex, yaw: float, v: float, w: float):
    """Return the exact center path s -> position of a held unicycle command."""
    heading = exp(1j * yaw)
    if w == 0:
        return lambda s: z + heading * (v * s)
    return lambda s: z + heading * exp(0.5j * w * s) * (2 * v * sin(0.5 * w * s) / w)


def gap_to_origin(p: complex, q: complex) -> float:
    """Distance from the origin to the segment between two points."""
    d = q - p
    span = d.real * d.real + d.imag * d.imag
    t = 0.0 if span == 0 else min(1.0, max(0.0, -(p.real * d.real + p.imag * d.imag) / span))
    return abs(p + d * t)


def certify_disc(offset, need: float, bend: float, duration: float, cause: str) -> float:
    """Prove |offset(s)| >= need on [0, duration] given |offset''| <= bend.

    On any interval the offset stays within bend*h^2/8 of its chord, so the
    chord's distance from the origin minus that bound is a certified floor.
    Intervals that cannot be certified are bisected; any sample inside the
    required clearance is a contact.
    """
    p, q = offset(0.0), offset(duration)
    lowest = min(abs(p), abs(q))
    require(lowest >= need - SLACK, cause)
    work, splits = [(0.0, duration, p, q)], 0
    while work:
        a, b, p, q = work.pop()
        if gap_to_origin(p, q) - bend * (b - a) ** 2 / 8 >= need - 2 * SLACK:
            continue
        splits += 1
        require(splits <= CERTIFY_LIMIT, "swept clearance could not be certified")
        middle = 0.5 * (a + b)
        m = offset(middle)
        lowest = min(lowest, abs(m))
        require(abs(m) >= need - SLACK, cause)
        work += [(a, middle, p, m), (middle, b, m, q)]
    return lowest - need


def certify_wall(distance, need: float, bend: float, duration: float, cause: str) -> float:
    """Prove a signed wall distance stays >= need on [0, duration]."""
    p, q = distance(0.0), distance(duration)
    lowest = min(p, q)
    require(lowest >= need - SLACK, cause)
    work, splits = [(0.0, duration, p, q)], 0
    while work:
        a, b, p, q = work.pop()
        if min(p, q) - bend * (b - a) ** 2 / 8 >= need - 2 * SLACK:
            continue
        splits += 1
        require(splits <= CERTIFY_LIMIT, "swept clearance could not be certified")
        middle = 0.5 * (a + b)
        m = distance(middle)
        lowest = min(lowest, m)
        require(m >= need - SLACK, cause)
        work += [(a, middle, p, m), (middle, b, m, q)]
    return lowest - need


class Patrol:
    """A disc shuttling along a polyline at bounded speed, dwelling at both ends."""

    def __init__(self, record: dict, dt: float) -> None:
        """Expand the route into one position per tick over a full cycle."""
        self.radius = record["radius_m"]
        self.dt = dt
        points = [complex(*point) for point in record["route"]]
        step = record["speed_mps"] * dt

        def legs(sequence: list) -> list:
            """Positions at each tick while traversing consecutive route points."""
            out = []
            for a, b in zip(sequence, sequence[1:]):
                n = max(1, ceil(abs(b - a) / step * (1 + 1e-9)))
                out += [a + (b - a) * (i / n) for i in range(n)]
            return out

        dwell = record.get("dwell", 0)
        self.cycle = legs(points) + [points[-1]] * dwell + legs(points[::-1]) + [points[0]] * dwell
        self.offset = record.get("offset", 0)

    def position(self, tick: int) -> complex:
        """Center at an integer tick."""
        return self.cycle[(tick + self.offset) % len(self.cycle)]

    def velocity(self, tick: int) -> complex:
        """Constant velocity held from this tick to the next one."""
        return (self.position(tick + 1) - self.position(tick)) / self.dt


class Field:
    """Ground truth for one mission: static cylinders, arena walls and movers."""

    def __init__(self, mission: dict) -> None:
        """Index the occupied lattice sites and expand the mover patrols."""
        self.mission = mission
        self.dt = mission["dt"]
        self.body = mission["radius_m"] + mission["margin_m"]
        self.sites = [ORIGIN + PITCH * complex(i, j) for j, row in enumerate(mission["rows"])
                      for i, cell in enumerate(row) if cell == "#"]
        self.start = complex(*mission.get("start_m", START))
        self.goal = complex(*mission.get("goal_m", GOAL))
        self.scan_config = SCAN | mission.get("scan", {})
        self.movers = [Patrol(record, self.dt) for record in mission.get("movers", ())]

    def public(self) -> dict:
        """The mission description handed to the navigator."""
        spec = {"bounds_m": [WIDTH, HEIGHT],
                "lattice": {"origin_m": [ORIGIN.real, ORIGIN.imag], "pitch_m": PITCH,
                            "columns": COLUMNS, "rows": ROWS},
                "obstacle_radius_m": CYLINDER,
                "start_m": [self.start.real, self.start.imag],
                "goal_m": [self.goal.real, self.goal.imag],
                "scan": dict(self.scan_config)}
        spec |= {key: self.mission[key] for key in PARAMETERS}
        if self.movers:
            spec["max_track_speed_mps"] = self.mission["max_track_speed_mps"]
        return spec

    def discs(self, tick: int) -> list:
        """Mover centers and radii at a tick."""
        return [(mover.position(tick), mover.radius) for mover in self.movers]

    def scan(self, z: complex, yaw: float, movers: list) -> list:
        """Planar ranges from the robot center, nearest surface per ray."""
        config = self.scan_config
        count, first = config["count"], yaw + config["angle_min_rad"]
        increment = config["angle_increment_rad"]
        low, high = config["range_min_m"], config["range_max_m"]
        units = [exp(1j * (first + k * increment)) for k in range(count)]
        ranges = [self.wall_range(z, u) for u in units]
        for center, radius in [(site, CYLINDER) for site in self.sites] + movers:
            d = center - z
            distance = abs(d)
            if distance - radius > high:
                continue
            if distance <= radius:
                ranges = [0.0] * count
                break
            half = asin(radius / distance)
            middle = (phase(d) - first) % tau
            for shift in (-tau, 0.0, tau):
                lo = max(0, ceil((middle - half + shift) / increment))
                hi = min(count - 1, floor((middle + half + shift) / increment))
                for k in range(lo, hi + 1):
                    u = units[k]
                    along = d.real * u.real + d.imag * u.imag
                    across = distance * distance - along * along
                    if along > 0 and across <= radius * radius:
                        t = along - sqrt(radius * radius - across)
                        if t < ranges[k]:
                            ranges[k] = t
        return [round(t, 4) if low <= t <= high else None for t in ranges]

    @staticmethod
    def wall_range(z: complex, u: complex) -> float:
        """Distance along a ray to the arena boundary."""
        tx = (WIDTH - z.real) / u.real if u.real > 0 else (-z.real / u.real if u.real < 0 else float("inf"))
        ty = (HEIGHT - z.imag) / u.imag if u.imag > 0 else (-z.imag / u.imag if u.imag < 0 else float("inf"))
        return min(tx, ty)

    def observe(self, tick: int, z: complex, yaw: float, v0: float, w0: float) -> dict:
        """Build the observation the navigator receives for this tick."""
        movers = self.discs(tick)
        record = {"tick": tick, "pose": [z.real, z.imag, yaw], "velocity": [v0, w0],
                  "scan": self.scan(z, yaw, movers)}
        if self.movers:
            record["tracks"] = [
                {"id": k, "position": [c.real, c.imag],
                 "velocity": [mover.velocity(tick).real, mover.velocity(tick).imag], "radius_m": r}
                for k, (mover, (c, r)) in enumerate(zip(self.movers, movers))]
        return record

    def command(self, reply: dict, v0: float, w0: float) -> tuple:
        """Validate one reply against the protocol and the actuator limits."""
        mission = self.mission
        status, v, w = reply.get("status"), reply.get("v_mps"), reply.get("w_radps")
        require(status in ("running", "waiting", "succeeded", "timeout"), "unknown navigator status")
        require(all(type(x) in (int, float) and abs(x) <= 1e6 for x in (v, w)),
                "twist must be finite numbers")
        v, w = float(v), float(w)
        require(0 <= v <= mission["max_v"] + 1e-9 and abs(w) <= mission["max_w"] + 1e-9,
                "twist exceeds the speed limits")
        require(abs(v - v0) <= mission["max_accel"] * self.dt + 1e-9
                and abs(w - w0) <= mission["max_alpha"] * self.dt + 1e-9,
                "twist exceeds the acceleration limits")
        if status != "running":
            require(v == 0 and w == 0, f"{status} must hold the robot still")
        return status, v, w

    def certify(self, tick: int, z: complex, yaw: float, v: float, w: float) -> tuple:
        """Certify the swept body over one tick; return the static and mover gaps."""
        dt, need = self.dt, self.body
        path = motion(z, yaw, v, w)
        cache = {}

        def at(s: float) -> complex:
            """Memoized center position along the held arc."""
            if s not in cache:
                cache[s] = path(s)
            return cache[s]

        bend = v * abs(w)
        reach = v * dt + 1e-6
        static, moving = float("inf"), float("inf")
        cause = "swept robot body touched a cylinder"
        for site in self.sites:
            if abs(site - z) <= reach + need + CYLINDER:
                static = min(static, certify_disc(lambda s, c=site: at(s) - c, need + CYLINDER,
                                                  bend, dt, cause))
        walls = ((lambda s: at(s).real), (lambda s: WIDTH - at(s).real),
                 (lambda s: at(s).imag), (lambda s: HEIGHT - at(s).imag))
        for wall in walls:
            if wall(0.0) <= reach + need:
                static = min(static, certify_wall(wall, need, bend, dt,
                                                  "swept robot body crossed the arena boundary"))
        for mover in self.movers:
            c, u = mover.position(tick), mover.velocity(tick)
            if abs(c - z) <= reach + abs(u) * dt + need + mover.radius:
                moving = min(moving, certify_disc(lambda s, c=c, u=u: at(s) - c - u * s,
                                                  need + mover.radius, bend, dt,
                                                  "moving robot body touched a moving obstacle"))
        return static, moving

    def advance(self, z: complex, yaw: float, v: float, w: float) -> tuple:
        """Apply one held command for a full tick."""
        return motion(z, yaw, v, w)(self.dt), phase(exp(1j * (yaw + w * self.dt)))


def field_mission(app, root, case: dict) -> dict:
    """Drive the submitted navigator through one hidden field mission."""
    mission = MISSIONS[case["mission"]]
    world = Field(mission)
    config = root / "field.json"
    config.write_text(json.dumps(world.public(), allow_nan=False))
    config.chmod(0o644)
    driver = Driver(app, config, writable(root / "home"))
    z, yaw = world.start, mission["start_yaw"]
    v0 = w0 = 0.0
    travelled = 0.0
    static_gap = mover_gap = float("inf")
    try:
        for tick in range(mission["deadline"] + 1):
            reply = driver.paced(world.observe(tick, z, yaw, v0, w0), tick, world.dt)
            status, v, w = world.command(reply, v0, w0)
            require(status != "timeout", "navigator reported timeout before reaching the goal")
            if status == "succeeded":
                require(abs(z - world.goal) <= mission["goal_tolerance_m"] + 1e-9,
                        "reported success outside the goal tolerance")
                return {"finish_tick": tick, "path_m": round(travelled, 4),
                        "static_gap_m": round(static_gap, 4) if static_gap < 1e9 else None,
                        "mover_gap_m": round(mover_gap, 4) if mover_gap < 1e9 else None,
                        "mean_reply_s": round(driver.spent / max(1, tick), 4),
                        "max_reply_s": round(driver.slowest, 4)}
            if v > 0:
                static, moving = world.certify(tick, z, yaw, v, w)
                static_gap, mover_gap = min(static_gap, static), min(mover_gap, moving)
            z, yaw = world.advance(z, yaw, v, w)
            travelled += v * world.dt
            v0, w0 = v, w
        raise Violation("did not stop inside the goal tolerance before the deadline")
    finally:
        driver.close()
