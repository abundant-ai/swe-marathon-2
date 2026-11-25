"""Exercise geometry, coordinated plans and interrupted transfers in a separate plant."""

from copy import deepcopy
from math import pi
from uuid import uuid4

from plant import SIDES, advance, complete, cursor, frames, measured_pose, motion_valid

REST = {"left": [0.0] * 4, "right": [0.0] * 4}


def rig(x, limits):
    return {
        "base": [x, 0.0, 0.21],
        "lengths": [0.45, 0.35],
        "radii": [0.024, 0.025],
        "limits": [[0.0, 1.6], limits, [-1.4, 1.4], [-1.5, 1.5]],
        "speed": [1.9, 3.7, 3.7, 3.7],
        "accel": [8.0, 12.0, 12.0, 12.0],
    }


def xyz(point, tick):
    return {"tick": tick, "a": list(point), "b": list(point)}


def obstacle(point, *, release=None, offset=0.74, radius=0.048):
    samples = [xyz(point, 0)]
    if release:
        above = (point[0], point[1], point[2] + offset)
        samples.extend((xyz(point, release), xyz(above, release + 3)))
    return {"radius": radius, "samples": samples}


def record(tick, pose, owner, velocity=None):
    return {"tick": tick, "pose": pose, "owner": owner, "velocity": velocity or REST}


def edge(identity, source, destination, ticks):
    return {"id": identity, "from": source, "to": destination, "ticks": ticks}


def seed(*, high=False, deadline=56):
    """Build a calibrated opposing assembly cell with one legitimate handoff."""
    arms = {"left": rig(-1.0, [-1.7, 1.7]), "right": rig(1.0, [1.4, 5.0])}
    home = {"left": [0.48, -0.68, 0.09, -0.12], "right": [0.52, pi + 0.64, -0.11, 0.17]}
    meet = {"left": [0.58, 0, 0, 0], "right": [0.58, pi, 0, 0]}
    destination = {
        "left": [0.81, -0.53, 0.1, -0.15],
        "right": [0.86, pi + 0.77, -0.13, 0.22],
    }
    nodes = {"home": home, "station": meet, "shelf": destination}
    edges = [
        edge("linear-teach", "home", "station", 8),
        edge("to-shelf", "station", "shelf", 8),
    ]
    if high:
        raised, bridge = deepcopy(home), deepcopy(meet)
        for side in SIDES:
            raised[side][0] += 0.48
            bridge[side][0] += 0.48
        nodes.update(raised=raised, bridge=bridge)
        edges.extend(
            (
                edge("lift-clear", "home", "raised", 5),
                edge("upper-transit", "raised", "bridge", 8),
                edge("lower-to-station", "bridge", "station", 5),
            )
        )
    return {
        "arms": arms,
        "payload": {
            "left": {"a": [0.094, 0, 0], "b": [0.306, 0, 0], "radius": 0.027},
            "right": {"a": [0.306, 0, 0], "b": [0.094, 0, 0], "radius": 0.027},
        },
        "fixtures": [],
        "margin": 0.008,
        "tick_seconds": 0.2,
        "nodes": nodes,
        "edges": edges,
        "handoffs": [
            {
                "id": "clamp-swap",
                "node": "station",
                "from": "left",
                "to": "right",
                "ticks": 2,
            }
        ],
        "measured": record(0, home, "left"),
        "start_node": "home",
        "goal_node": "shelf",
        "goal_owner": "right",
        "deadline": deadline,
        "brake_ticks": 0,
    }


def at_tip(spec, source, goal, fraction, side="left"):
    pose = measured_pose(spec["nodes"][source], spec["nodes"][goal], fraction)
    return frames(spec["arms"][side], pose[side])[1]


def explicit(data, before, after, end=8):
    return {
        **{
            key: data[key]
            for key in ("arms", "payload", "fixtures", "margin", "tick_seconds")
        },
        "before": before,
        "after": after,
        "start": 0,
        "end": end,
        "owner": "left",
    }


def geometry_checks(run):
    spec = seed()
    initial = explicit(spec, spec["nodes"]["home"], spec["nodes"]["station"])
    midpoint = deepcopy(initial)
    midpoint["fixtures"] = [obstacle(at_tip(spec, "home", "station", 0.5))]
    above = deepcopy(initial)
    for side, sign in (("left", -1), ("right", 1)):
        above["arms"][side]["base"][0] = sign * 0.72
    first = {"left": [0.52, 0, 0, 0], "right": [1.05, pi, 0, 0]}
    above["before"] = above["after"] = first
    crossing = deepcopy(above)
    badpose = deepcopy(first)
    badpose["right"][0] = badpose["left"][0]
    crossing["before"] = crossing["after"] = badpose
    result = {}
    for key, query, expected in (
        ("clear_spatial_motion", initial, True),
        ("detect_between_tick_collision", midpoint, False),
        ("respect_vertical_separation", above, True),
        ("interarm_collision_at_same_height", crossing, False),
        ("reject_dynamically_fast_move", dict(initial, end=1), False),
    ):
        assert (
            motion_valid(
                query, query["before"], query["after"], 0, query["end"], "left"
            )
            == expected
        ), key
        result[key] = run("certify", query) == {"safe": expected}
    return result


def waited():
    spec = seed(deadline=40)
    spec["fixtures"] = [obstacle(at_tip(spec, "home", "station", 0.48), release=12)]
    return spec


def apparent_grasp():
    spec = seed(deadline=24)
    spec["payload"]["right"]["a"][1] = 0.025
    spec["payload"]["right"]["b"][1] = 0.025
    return spec


def detour():
    spec = seed(high=True, deadline=40)
    spec["fixtures"] = [obstacle(at_tip(spec, "home", "station", 0.48))]
    return spec


def braking():
    spec = seed(deadline=42)
    speed = {"left": [0.19, -0.17, 0.06, -0.1], "right": [0.1, 0.12, -0.07, 0.03]}
    stopped = spec["nodes"]["home"]
    start = {
        side: [p - 0.4 * dq for p, dq in zip(stopped[side], speed[side], strict=True)]
        for side in SIDES
    }
    spec["measured"] = record(0, start, "left", speed)
    spec["brake_ticks"] = 4
    return spec


def plan_checks(run):
    rows = (
        ("plan_with_wait", waited(), True),
        ("find_spatial_detour", detour(), True),
        ("brake_and_transfer", braking(), True),
        ("withhold_bad_custody_match", apparent_grasp(), False),
        ("cannot_meet_window", dict(waited(), deadline=13), False),
    )
    return {key: complete(spec, run("plan", spec), ready) for key, spec, ready in rows}


def packet(window, mission=None):
    return {
        "mission": mission or uuid4().hex,
        "sequence": 1,
        "revision": 31,
        "window": window,
        "previous": None,
    }


def accepted(p, reply, status):
    return (
        isinstance(reply, dict)
        and all(reply.get(key) == p[key] for key in ("mission", "sequence", "revision"))
        and reply.get("status") == status
        and "command" in reply
        and "command_id" in reply
        and (
            isinstance(reply["command"], dict)
            and isinstance(reply["command_id"], str)
            and bool(reply["command_id"])
            if status == "issued"
            else reply["command"] is None and reply["command_id"] is None
        )
    )


def completed(p, reply, state):
    tick, node, owner = state
    prior = p["window"]
    window = dict(
        prior,
        start_node=node,
        brake_ticks=0,
        measured=record(tick, prior["nodes"][node], owner),
    )
    return dict(
        p,
        sequence=p["sequence"] + 1,
        window=window,
        previous={"id": reply["command_id"], "outcome": "completed"},
    )


def execute(run, state, p, reply, *, known_ids=()):
    """Drive the supervised handoff with independently acknowledged poses."""
    issued = set(known_ids)
    for _ in range(81):
        spec = p["window"]
        current = cursor(spec)
        if current is None:
            return False
        if accepted(p, reply, "ready"):
            return current[1:] == (spec["goal_node"], spec["goal_owner"])
        if not accepted(p, reply, "issued") or reply["command_id"] in issued:
            return False
        issued.add(reply["command_id"])
        later = advance(spec, *current, reply["command"])
        if later is None:
            return False
        following = completed(p, reply, later)
        if reply["command"]["kind"] == "handoff":
            forged = deepcopy(following)
            forged["window"]["measured"]["owner"] = current[2]
            if not accepted(forged, run("dispatch", forged, state=state), "rejected"):
                return False
        p = following
        reply = run("dispatch", p, state=state)
    return False


def recovery_lost_reply(run, state):
    """Retry a persisted first decision after its output write fails."""
    p = packet(waited())
    if run("dispatch", p, state=state, lost_reply=True) is not True:
        return False
    forged = dict(p, revision=p["revision"] + 1)
    if not accepted(forged, run("dispatch", forged, state=state), "rejected"):
        return False
    original = run("dispatch", p, state=state)
    retransmitted = run("dispatch", dict(reversed(tuple(p.items()))), state=state)
    return original == retransmitted and execute(run, state, p, original)


def recovery_interruption(run, state):
    """Withdraw an in-flight move, preserve cargo, brake, then use a repaired forecast."""
    prior = seed(deadline=18)
    p = packet(prior)
    original = run("dispatch", p, state=state)
    if not accepted(p, original, "issued"):
        return False
    old = original["command"]
    if any(
        old.get(key) != value
        for key, value in {
            "kind": "move",
            "start": 0,
            "end": 8,
            "id": "linear-teach",
        }.items()
    ):
        return False
    before, after = (prior["nodes"][key] for key in ("home", "station"))
    interrupt = 4
    stopped = measured_pose(before, after, 0.6875)
    now = measured_pose(before, after, 0.5)
    # The midpoint cubic slope is 1.5/T, then constant braking runs for two ticks.
    speed = {
        side: [
            1.5 * (b - a) / 1.6 for a, b in zip(before[side], after[side], strict=True)
        ]
        for side in SIDES
    }
    revised = deepcopy(prior)
    revised["nodes"]["braking-rest"] = stopped
    revised["edges"].append(edge("rejoin-after-brake", "braking-rest", "station", 6))
    revised.update(
        deadline=51,
        brake_ticks=2,
        start_node="braking-rest",
        measured=record(interrupt, now, "left", speed),
    )
    gate = at_tip(revised, "braking-rest", "station", 0.68)
    revised["fixtures"] = [obstacle(gate, release=18, radius=0.019)]
    update = dict(
        p,
        sequence=2,
        revision=p["revision"] + 1,
        window=revised,
        previous={"id": original["command_id"], "outcome": "withdrawn"},
    )
    obsolete = dict(update, revision=p["revision"])
    premature = deepcopy(update)
    premature["window"]["measured"]["owner"] = "right"
    for fake in (obsolete, premature):
        if not accepted(fake, run("dispatch", fake, state=state), "rejected"):
            return False
    next_reply = run("dispatch", update, state=state)
    if (
        not accepted(update, next_reply, "issued")
        or next_reply["command"]["kind"] != "brake"
    ):
        return False
    if not accepted(p, run("dispatch", p, state=state), "rejected"):
        return False
    return execute(run, state, update, next_reply, known_ids=(original["command_id"],))


def safe_block(run, state):
    p = packet(apparent_grasp())
    return accepted(p, run("dispatch", p, state=state), "blocked")


def checks(run, level):
    evidence = geometry_checks(run)
    if level >= 2:
        evidence.update(plan_checks(run))
    if level >= 3:
        for label, probe in (
            ("lost_reply", recovery_lost_reply),
            ("interrupted_motion", recovery_interruption),
            ("no_custody_transition", safe_block),
        ):
            folder = run.scratch / label
            folder.mkdir(mode=0o755)
            folder.chmod(0o777)
            try:
                evidence["dispatch_" + label] = bool(probe(run, folder / "state.json"))
            except (
                ValueError,
                TypeError,
                AttributeError,
                KeyError,
                IndexError,
                OverflowError,
            ):
                evidence["dispatch_" + label] = False
    if level == 4:
        from contingency_checks import contingency_checks

        evidence.update(contingency_checks(run))
    return evidence
