"""Spatial kinematics and bounded swept-capsule collision checks."""

import itertools
from bisect import bisect_right
from dataclasses import dataclass
from math import cos, isfinite, sin, sqrt

SIDES = ("left", "right")


def number(value, *, positive=False):
    if (
        type(value) not in (int, float)
        or not isfinite(value)
        or (positive and value <= 0)
    ):
        raise ValueError("Invalid numeric field")
    return float(value)


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid tick or duration")
    return value


def name(value):
    if not isinstance(value, str) or not value:
        raise ValueError("A nonempty ID is required")
    return value


def side(value):
    if value not in SIDES:
        raise ValueError("Unknown arm")
    return value


def vector(value, length, positive=False):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError("Invalid coordinate array")
    return tuple(number(x, positive=positive) for x in value)


def pair(value):
    return tuple(vector(value[s], 4) for s in SIDES)


def plus(a, b):
    return tuple(x + y for x, y in zip(a, b, strict=True))


def minus(a, b):
    return tuple(x - y for x, y in zip(a, b, strict=True))


def times(value, factor):
    return tuple(x * factor for x in value)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def norm(a):
    return sqrt(dot(a, a))


def mix(a, b, fraction):
    return plus(a, times(minus(b, a), fraction))


def point_segment(p, a, b):
    d = minus(b, a)
    size = dot(d, d)
    t = max(0.0, min(1.0, dot(minus(p, a), d) / size)) if size else 0.0
    return norm(minus(p, plus(a, times(d, t))))


def separation(shape_a, shape_b):
    """Compute the capsule distance from endpoint projections and an interior line pair."""
    a, b, ra = shape_a
    c, d, rb = shape_b
    v, w, offset = minus(b, a), minus(d, c), minus(a, c)
    vv, ww, vw = dot(v, v), dot(w, w), dot(v, w)
    vo, wo = dot(v, offset), dot(w, offset)
    determinant = vv * ww - vw * vw
    candidates = [
        point_segment(a, c, d),
        point_segment(b, c, d),
        point_segment(c, a, b),
        point_segment(d, a, b),
    ]
    if determinant > 0:
        t = (vw * wo - ww * vo) / determinant
        u = (vv * wo - vw * vo) / determinant
        if 0 <= t <= 1 and 0 <= u <= 1:
            candidates.append(norm(minus(plus(a, times(v, t)), plus(c, times(w, u)))))
    return min(candidates) - ra - rb


def points(value):
    return vector(value["a"], 3), vector(value["b"], 3)


@dataclass(frozen=True)
class Arm:
    """Joint bounds, gearbox limits and link capsules for one arm."""

    base: tuple
    lengths: tuple
    radii: tuple
    limits: tuple
    speed: tuple
    acceleration: tuple

    @classmethod
    def parse(cls, body):
        raw = body["limits"]
        if not isinstance(raw, list) or len(raw) != 4:
            raise ValueError("Four joint bounds are needed")
        limits = tuple(vector(lim, 2) for lim in raw)
        if any(lo >= hi for lo, hi in limits):
            raise ValueError("Inverted joint limit")
        return cls(
            vector(body["base"], 3),
            vector(body["lengths"], 2, True),
            vector(body["radii"], 2, True),
            limits,
            vector(body["speed"], 4, True),
            vector(body["accel"], 4, True),
        )

    def geometry(self, pose):
        """Return both world link capsules and the tool transform."""
        height, yaw, angle, elbow = pose
        base = plus(self.base, (0.0, 0.0, height))

        def offset(pitch, length):
            return times(
                (cos(yaw) * cos(pitch), sin(yaw) * cos(pitch), sin(pitch)), length
            )

        pivot = plus(base, offset(angle, self.lengths[0]))
        pitch = angle + elbow
        tip = plus(pivot, offset(pitch, self.lengths[1]))

        def transform(local):
            x, y, z = local
            forward = cos(pitch) * x - sin(pitch) * z
            return plus(
                tip,
                (
                    cos(yaw) * forward - sin(yaw) * y,
                    sin(yaw) * forward + cos(yaw) * y,
                    sin(pitch) * x + cos(pitch) * z,
                ),
            )

        return ((base, pivot, self.radii[0]), (pivot, tip, self.radii[1])), transform


@dataclass(frozen=True)
class Fixture:
    """A capsule whose endpoints follow measured forecast sample times."""

    ticks: tuple
    positions: tuple
    radius: float

    @classmethod
    def parse(cls, item):
        entries = item["samples"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("Each fixture needs a sample")
        ticks = tuple(integer(row["tick"]) for row in entries)
        if tuple(sorted(set(ticks))) != ticks:
            raise ValueError("Fixture times must increase")
        return cls(
            ticks,
            tuple(points(row) for row in entries),
            number(item["radius"], positive=True),
        )

    def at(self, tick):
        index = bisect_right(self.ticks, tick)
        if index == 0:
            return (*self.positions[0], self.radius)
        if index == len(self.ticks):
            return (*self.positions[-1], self.radius)
        lo, hi = self.ticks[index - 1 : index + 1]
        first, second = self.positions[index - 1 : index + 1]
        u = (tick - lo) / (hi - lo)
        return (
            *(mix(p, q, u) for p, q in zip(first, second, strict=True)),
            self.radius,
        )


@dataclass(frozen=True)
class Cell:
    """Calibrated arms, payload grasps and forecast obstacles."""

    arms: tuple
    payload: tuple
    fixtures: tuple
    margin: float
    tick_seconds: float

    @classmethod
    def parse(cls, request):
        parts = tuple(
            (
                *points(request["payload"][s]),
                number(request["payload"][s]["radius"], positive=True),
            )
            for s in SIDES
        )
        margin = number(request["margin"])
        rows = request["fixtures"]
        if margin < 0 or not isinstance(rows, list):
            raise ValueError("Invalid clearance settings")
        return cls(
            tuple(Arm.parse(request["arms"][s]) for s in SIDES),
            parts,
            tuple(Fixture.parse(row) for row in rows),
            margin,
            number(request["tick_seconds"], positive=True),
        )

    def geometry(self, pose, owner):
        left, right = (arm.geometry(q) for arm, q in zip(self.arms, pose, strict=True))
        transform = (left, right)[owner][1]
        a, b, radius = self.payload[owner]
        return left[0], right[0], (transform(a), transform(b), radius)

    def matches_grasp(self, pose):
        _, _, a = self.geometry(pose, 0)
        _, _, b = self.geometry(pose, 1)
        return (
            max(norm(minus(a[0], b[0])), norm(minus(a[1], b[1])), abs(a[2] - b[2]))
            <= 1e-7
        )

    def clearance(self, pose, owner, tick):
        left, right, cargo = self.geometry(pose, owner)
        links = (*left, *right)
        gaps = [separation(a, b) for a in left for b in right]
        gaps.extend(separation(a, cargo) for a in links)
        static = [fixture.at(tick) for fixture in self.fixtures]
        gaps.extend(separation(a, b) for a in (*links, cargo) for b in static)
        return min(gaps)

    def dynamics(self, before, after, seconds, brake):
        for arm, q0, q1 in zip(self.arms, before, after, strict=True):
            for a, b, (lo, hi), speed, accel in zip(
                q0, q1, arm.limits, arm.speed, arm.acceleration, strict=True
            ):
                if not (lo - 1e-9 <= min(a, b) <= max(a, b) <= hi + 1e-9):
                    return False
                if seconds and (
                    abs(a - b) * (2 if brake else 1.5) > speed * seconds + 1e-9
                    or abs(a - b) * (2 if brake else 6) > accel * seconds**2 + 1e-9
                ):
                    return False
        return True

    def certify(self, before, after, start, end, owner, brake=False):
        """Prove each smooth interval with a displacement bound on capsule endpoints."""
        duration = end - start
        if not self.dynamics(before, after, duration * self.tick_seconds, brake):
            return False

        def evaluate(tick):
            u = (tick - start) / duration if duration else 0
            s = u * (2 - u) if brake else u * u * (3 - 2 * u)
            q = tuple(mix(a, b, s) for a, b in zip(before, after, strict=True))
            return self.clearance(q, owner, tick)

        if evaluate(start) < self.margin - 1e-9 or evaluate(end) < self.margin - 1e-9:
            return False
        if not duration:
            return True
        travel = []
        for index, (arm, q0, q1) in enumerate(
            zip(self.arms, before, after, strict=True)
        ):
            height, yaw, pitch, elbow = map(abs, minus(q1, q0))
            reach = max(norm(p) for p in self.payload[index][:2])
            travel.append(height + (sum(arm.lengths) + reach) * (yaw + pitch + elbow))
        body_rate = max(travel) * (2.0 if brake else 1.5) / duration
        cuts = sorted(
            {
                start,
                end,
                *(
                    tick
                    for f in self.fixtures
                    for tick in f.ticks
                    if start < tick < end
                ),
            }
        )
        for lo, hi in itertools.pairwise(cuts):
            obstacle_rate = max(
                (
                    norm(minus(a, b)) / (hi - lo)
                    for f in self.fixtures
                    for a, b in zip(f.at(lo)[:2], f.at(hi)[:2], strict=True)
                ),
                default=0,
            )
            rate = max(2 * body_rate, body_rate + obstacle_rate)
            todo = [(lo, hi)]
            while todo:
                a, b = todo.pop()
                middle = (a + b) / 2
                gap = evaluate(middle)
                if gap < self.margin - 1e-9:
                    return False
                if gap - rate * (b - a) / 2 >= self.margin - 1e-9:
                    continue
                if b - a < 1 / 8192:
                    return False
                todo.extend(((a, middle), (middle, b)))
        return True


def certify(request):
    """Validate an explicit rest-to-rest move."""
    start, end = integer(request["start"]), integer(request["end"])
    if end <= start:
        raise ValueError("Motion must take positive time")
    return {
        "safe": Cell.parse(request).certify(
            pair(request["before"]),
            pair(request["after"]),
            start,
            end,
            SIDES.index(side(request["owner"])),
        )
    }
