"""Private geometric and dynamics checks for candidate dual-arm operations."""

import itertools
from math import cos, sin, sqrt

SIDES = ("left", "right")


def sub(a, b):
    return [x - y for x, y in zip(a, b, strict=True)]


def norm(a):
    return sqrt(sum(x * x for x in a))


def scaled(a, b, factor):
    return [x + factor * (y - x) for x, y in zip(a, b, strict=True)]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def clamp(u):
    return min(1.0, max(0.0, u))


def gap(first, second):
    """Project a pair of capsule centrelines using a constrained two-segment solution."""
    a, b, radius = first
    c, d, other = second
    u, v, w = sub(b, a), sub(d, c), sub(a, c)
    square_u, square_v = dot(u, u), dot(v, v)
    projected = dot(v, w)
    if square_u <= 1e-30 and square_v <= 1e-30:
        return norm(w) - radius - other
    if square_u <= 1e-30:
        s, t = 0, clamp(projected / square_v)
    else:
        left = dot(u, w)
        if square_v <= 1e-30:
            s, t = clamp(-left / square_u), 0
        else:
            skew = dot(u, v)
            determinant = square_u * square_v - skew * skew
            s = (
                clamp((skew * projected - left * square_v) / determinant)
                if determinant > 0
                else 0
            )
            t = (skew * s + projected) / square_v
            if t < 0 or t > 1:
                t = clamp(t)
                s = clamp((t * skew - left) / square_u)
    return (
        norm([origin + s * x - t * y for origin, x, y in zip(w, u, v, strict=True)])
        - radius
        - other
    )


def frames(model, pose):
    """Derive link endpoints and three tool basis vectors for an arm."""
    h, y, p, e = pose
    anchor = [model["base"][0], model["base"][1], model["base"][2] + h]
    l1, l2 = model["lengths"]
    cy, sy = cos(y), sin(y)
    pitch = p + e
    fwd = [cy * cos(pitch), sy * cos(pitch), sin(pitch)]
    lateral = [-sy, cy, 0]
    up = [-cy * sin(pitch), -sy * sin(pitch), cos(pitch)]
    joint = [
        anchor[0] + l1 * cy * cos(p),
        anchor[1] + l1 * sy * cos(p),
        anchor[2] + l1 * sin(p),
    ]
    tool = [
        coordinate + l2 * direction
        for coordinate, direction in zip(joint, fwd, strict=True)
    ]
    links = ((anchor, joint, model["radii"][0]), (joint, tool, model["radii"][1]))
    return links, tool, (fwd, lateral, up)


def cargo(spec, pose, side):
    _, origin, bases = frames(spec["arms"][side], pose[side])
    load = spec["payload"][side]
    endpoints = []
    for end in ("a", "b"):
        endpoints.append(
            [
                x
                + sum(
                    axes[i] * coordinate
                    for axes, coordinate in zip(bases, load[end], strict=True)
                )
                for i, x in enumerate(origin)
            ]
        )
    return (*endpoints, load["radius"])


def fixture_at(track, tick):
    """Read a linear forecast interval independently of candidate interpolation."""
    points = track["samples"]
    a, b = points[0], points[0]
    for before, after in itertools.pairwise(points):
        if before["tick"] <= tick <= after["tick"]:
            a, b = before, after
            break
    else:
        if tick > points[-1]["tick"]:
            a, b = points[-1], points[-1]
    u = 0 if a == b else (tick - a["tick"]) / (b["tick"] - a["tick"])
    return (scaled(a["a"], b["a"], u), scaled(a["b"], b["b"], u), track["radius"])


def clearance(spec, pose, side, tick):
    """Enumerate independent pairwise clearance against the live objects."""
    arm_a, arm_b = (frames(spec["arms"][name], pose[name])[0] for name in SIDES)
    load = cargo(spec, pose, side)
    obstacles = [fixture_at(item, tick) for item in spec["fixtures"]]
    pairs = [(x, y) for x in arm_a for y in arm_b]
    pairs += [(x, load) for x in (*arm_a, *arm_b)]
    pairs += [(x, y) for x in (*arm_a, *arm_b, load) for y in obstacles]
    return min(gap(x, y) for x, y in pairs)


def measured_pose(before, after, fraction):
    return {side: scaled(before[side], after[side], fraction) for side in SIDES}


def close_pose(a, b):
    return all(max(map(abs, sub(a[side], b[side]))) <= 1e-7 for side in SIDES)


def station_matched(spec, pose):
    a, b = (cargo(spec, pose, side) for side in SIDES)
    return max(norm(sub(a[0], b[0])), norm(sub(a[1], b[1])), abs(a[2] - b[2])) <= 1e-7


def motion_valid(spec, before, after, start, end, owner, *, braking=False):
    """Check continuous clearance with an independent swept-distance envelope."""
    duration = end - start
    factor = 2 if braking else 1.5
    for side in SIDES:
        model = spec["arms"][side]
        for axis, (lo, hi) in enumerate(model["limits"]):
            a, b = before[side][axis], after[side][axis]
            delta = abs(a - b)
            if min(a, b) < lo - 1e-9 or max(a, b) > hi + 1e-9:
                return False
            dt = duration * spec["tick_seconds"]
            if dt and (
                factor * delta > model["speed"][axis] * dt + 1e-8
                or (2 if braking else 6) * delta > model["accel"][axis] * dt * dt + 1e-8
            ):
                return False
    threshold = spec["margin"] - 1e-9
    if (
        clearance(spec, before, owner, start) < threshold
        or clearance(spec, after, owner, end) < threshold
    ):
        return False
    if not duration:
        return True
    # Every endpoint lies within this lever arm of each angular axis.
    envelope = []
    for side in SIDES:
        changes = list(map(abs, sub(after[side], before[side])))
        radius = sum(spec["arms"][side]["lengths"]) + max(
            norm(spec["payload"][side]["a"]), norm(spec["payload"][side]["b"])
        )
        envelope.append(factor * (changes[0] + radius * sum(changes[1:])) / duration)
    body_speed = max(envelope)
    fixture_speed = max(
        (
            max(norm(sub(a[k], b[k])) for k in ("a", "b")) / (b["tick"] - a["tick"])
            for item in spec["fixtures"]
            for a, b in zip(item["samples"], item["samples"][1:])
        ),
        default=0,
    )
    rate = max(2 * body_speed, body_speed + fixture_speed)
    intervals = [(start, end)]
    while intervals:
        left, right = intervals.pop()
        pivot = (left + right) / 2
        u = (pivot - start) / duration
        fraction = 2 * u - u * u if braking else 3 * u * u - 2 * u * u * u
        distance = clearance(spec, measured_pose(before, after, fraction), owner, pivot)
        if distance < threshold:
            return False
        if distance - rate * (right - left) / 2 >= threshold:
            continue
        if right - left < 1 / 8192:
            return False
        intervals.extend(((left, pivot), (pivot, right)))
    return True


def advance(spec, tick, node, owner, cmd):
    """Execute one authorized primitive and report the actual resting state."""
    if (
        not isinstance(cmd, dict)
        or type(cmd.get("start")) is not int
        or type(cmd.get("end")) is not int
        or cmd["start"] != tick
        or not tick < cmd["end"] <= spec["deadline"]
    ):
        return None
    end, kind = cmd["end"], cmd.get("kind")
    after_owner = owner
    if node is None:
        if (
            kind != "brake"
            or cmd.get("node") != spec["start_node"]
            or end - tick != spec["brake_ticks"]
        ):
            return None
        measured = spec["measured"]
        before = measured["pose"]
        duration = spec["tick_seconds"] * (end - tick)
        after = {
            side: [
                q + dq * duration / 2
                for q, dq in zip(before[side], measured["velocity"][side], strict=True)
            ]
            for side in SIDES
        }
        target = spec["start_node"]
        if not close_pose(after, spec["nodes"][target]):
            return None
    else:
        before = spec["nodes"][node]
        after = before
        target = node
        if kind == "move":
            edge = next(
                (row for row in spec["edges"] if row["id"] == cmd.get("id")), None
            )
            if edge is None or edge["from"] != node or edge["ticks"] != end - tick:
                return None
            target = edge["to"]
            after = spec["nodes"][target]
        elif kind == "handoff":
            event = next(
                (row for row in spec["handoffs"] if row["id"] == cmd.get("id")), None
            )
            if (
                event is None
                or event["node"] != node
                or event["from"] != owner
                or event["ticks"] != end - tick
                or not station_matched(spec, before)
            ):
                return None
            after_owner = event["to"]
        elif kind != "wait" or cmd.get("node") != node:
            return None
    if not motion_valid(spec, before, after, tick, end, owner, braking=kind == "brake"):
        return None
    if (
        after_owner != owner
        and clearance(spec, after, after_owner, end) < spec["margin"] - 1e-9
    ):
        return None
    return end, target, after_owner


def cursor(spec):
    measured = spec["measured"]
    if spec["brake_ticks"]:
        return measured["tick"], None, measured["owner"]
    pose = spec["nodes"][spec["start_node"]]
    if (
        any(any(measured["velocity"][side]) for side in SIDES)
        or not close_pose(measured["pose"], pose)
        or not motion_valid(
            spec, pose, pose, measured["tick"], measured["tick"], measured["owner"]
        )
    ):
        return None
    return measured["tick"], spec["start_node"], measured["owner"]


def complete(spec, report, feasible):
    if not isinstance(report, dict):
        return False
    if not feasible:
        return report == {"status": "blocked", "commands": []}
    if report.get("status") != "ready" or not isinstance(report.get("commands"), list):
        return False
    state = cursor(spec)
    for step in report["commands"]:
        if state is None:
            return False
        state = advance(spec, *state, step)
    return state is not None and state[1:] == (spec["goal_node"], spec["goal_owner"])
