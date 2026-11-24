"""Exercise schedule reconciliation against an independent three-vehicle plant."""

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, product
import json
import math
import os
import pwd
import subprocess
import sys

from fleet_world import PhysicalConflict, Rejected, require
from rmf_checks import executable


SECOND = 1_000_000_000
ROUNDING_NS = 10
POS_EPSILON = 1e-6


def ns(seconds):
    return round(seconds * SECOND)


@dataclass(frozen=True)
class Leg:
    origin: tuple
    destination: tuple
    depart: float
    speed: float
    acceleration: float

    @property
    def ramp(self):
        return min(self.speed / self.acceleration, math.sqrt(self.length / self.acceleration))

    @property
    def length(self):
        return math.dist(self.origin[:2], self.destination[:2])

    @property
    def cruise(self):
        return max(0.0, self.length / (self.ramp * self.acceleration) - self.ramp)

    @property
    def finish(self):
        return self.depart + 2 * self.ramp + self.cruise

    def knots(self):
        return self.depart, self.depart + self.ramp, self.finish - self.ramp, self.finish

    def pose(self, time):
        if time <= self.depart:
            return self.origin
        if time >= self.finish:
            return self.destination
        elapsed = time - self.depart
        if elapsed <= self.ramp:
            distance = 0.5 * self.acceleration * elapsed ** 2
        elif time >= self.finish - self.ramp:
            distance = self.length - 0.5 * self.acceleration * (self.finish - time) ** 2
        else:
            distance = self.acceleration * self.ramp * (elapsed - 0.5 * self.ramp)
        fraction = distance / self.length
        x, y = (a + fraction * (b - a) for a, b in zip(
            self.origin[:2], self.destination[:2], strict=True))
        return x, y, self.origin[2]

    @classmethod
    def from_station(cls, station, origin, destination, depart):
        profile = station["profile"]
        return cls(tuple(station[origin]), tuple(station[destination]), depart / SECOND,
                   profile["linear_velocity_mps"], profile["linear_acceleration_mps2"])


@dataclass(frozen=True)
class Path:
    legs: tuple
    radius: float
    carry_prefix: bool = False

    def pose(self, time):
        for leg in reversed(self.legs):
            if time >= leg.depart:
                return leg.pose(time)
        return self.legs[0].origin

    def checkpoints(self):
        # A courier itinerary starts at time zero even if it waits before its
        # first move. Native phases of each leg add checkpoints in time order.
        points = {} if self.carry_prefix else {0: self.legs[0].origin}
        for leg in self.legs:
            for time in leg.knots():
                points.setdefault(ns(time), leg.pose(time))
        return tuple(points.items())

    @property
    def finish_ns(self):
        return ns(self.legs[-1].finish)


def _extrema(coefficients):
    """Return all roots in (0, 1) of the derivative of squared separation."""
    c0, c1, c2, c3 = coefficients
    if abs(c3) > 1e-14:
        discriminant = (2 * c2) ** 2 - 12 * c3 * c1
        cuts = [] if discriminant < 0 else [
            (-2 * c2 + sign * math.sqrt(discriminant)) / (6 * c3) for sign in (-1, 1)
        ]
    elif abs(c2) > 1e-14:
        cuts = [-c1 / (2 * c2)]
    else:
        cuts = []

    def value(x):
        return c0 + x * (c1 + x * (c2 + x * c3))

    brackets = [0.0, *sorted(x for x in cuts if 0 < x < 1), 1.0]
    for left, right in zip(brackets, brackets[1:]):
        fl, fr = value(left), value(right)
        if abs(fl) < 1e-12 and left > 0:
            yield left
        if fl * fr >= 0:
            continue
        for _ in range(38):
            midpoint = (left + right) / 2
            fm = value(midpoint)
            if fl * fm <= 0:
                right = midpoint
            else:
                left, fl = midpoint, fm
        yield (left + right) / 2


@lru_cache(maxsize=4096)
def continuous_clearance(first, second):
    """Minimize swept circle separation exactly up to numerical root tolerance."""
    knots = sorted({0.0, *(t for pair in (first, second) for leg in pair.legs for t in leg.knots())})
    minimum = math.inf
    for start, end in zip(knots, knots[1:]):
        if end - start < 1e-12:
            continue
        origin, middle, finish = [
            tuple(a - b for a, b in zip(first.pose(time)[:2], second.pose(time)[:2], strict=True))
            for time in (start, (start + end) / 2, end)
        ]
        # Within this interval relative position is a quadratic in u on [0,1].
        quadratic = tuple(2 * (q + r - 2 * p) for q, p, r in zip(origin, middle, finish, strict=True))
        linear = tuple(r - q - a for q, r, a in zip(origin, finish, quadratic, strict=True))
        coefficients = (
            math.fsum(a * b for a, b in zip(origin, linear, strict=True)),
            math.fsum(v * v + 2 * q * a for q, v, a in zip(origin, linear, quadratic, strict=True)),
            3 * math.fsum(v * a for v, a in zip(linear, quadratic, strict=True)),
            2 * math.fsum(a * a for a in quadratic),
        )
        for u in (0.0, 1.0, *_extrema(coefficients)):
            displacement = tuple(q + u * (v + u * a)
                                 for q, v, a in zip(origin, linear, quadratic, strict=True))
            minimum = min(minimum, math.hypot(*displacement))
    return minimum - first.radius - second.radius


def station_path(station, segments, carrier=False):
    return Path(tuple(Leg.from_station(station, origin, destination, depart)
                      for origin, destination, depart in segments), station["profile"]["radius_m"], carrier)


def point_checkpoint(path, axis, sign, threshold):
    return next((index, time, pose) for index, (time, pose) in enumerate(path.checkpoints())
                if sign * (pose[axis] - threshold) >= -1e-12)


class Driver:
    """Use fresh unprivileged candidate processes with the same durable state."""

    def __init__(self, app, directory, site):
        directory.mkdir(mode=0o755)
        self.app = app
        self.directory = directory
        self.site = directory / "site.json"
        self.site.write_text(json.dumps(site))
        self.state = directory / "state"
        self.state.mkdir(mode=0o777)
        self.state.chmod(0o777)
        self.number = 0

    def exchange(self, request, *, rejected=False):
        self.number += 1
        packet = self.directory / f"packet-{self.number}.json"
        packet.write_text(json.dumps(request, allow_nan=False))
        output = self.state / f"reply-{self.number}.json"
        identity = {}
        if os.geteuid() == 0:
            try:
                user = pwd.getpwnam("candidate")
            except KeyError:
                user = pwd.getpwnam("nobody")
            identity = {"user": user.pw_uid, "group": user.pw_gid, "extra_groups": []}
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.state), "LC_ALL": "C.UTF-8",
            "FLEET_RMF_NATIVE": executable("rmf-native"),
        }
        for key in ("RMF_ROOT", "EIGEN_INCLUDE", "FLEET_COMPETITION_NATIVE"):
            if key in os.environ:
                environment[key] = os.environ[key]
        try:
            invocation = subprocess.run(
                [sys.executable, "-B", "-m", "fleet_recovery", "rmf-negotiate",
                 "--site", str(self.site), "--state", str(self.state / "journal.json"),
                 "--event", str(packet), "--output", str(output)],
                cwd=self.app, env=environment, **identity, capture_output=True, timeout=55,
            )
        except subprocess.TimeoutExpired as error:
            raise Rejected("negotiation command timed out") from error
        if rejected:
            require(invocation.returncode != 0, "altering a committed request ID succeeded")
            return None
        require(invocation.returncode == 0 and output.is_file() and not output.is_symlink(),
                "negotiation command failed to publish a reply")
        require(output.stat().st_size <= 100_000, "negotiation reply is oversized")
        response = json.loads(output.read_text())
        require(type(response) is dict and set(response) == {
            "status", "version", "plan", "revoke", "commands",
        }, "negotiation response is malformed")
        require(type(response["commands"]) is list and type(response["revoke"]) is list,
                "command or cancellation records are malformed")
        return response


def profile(radius, speed, acceleration):
    return {"radius_m": radius, "linear_velocity_mps": speed, "linear_acceleration_mps2": acceleration,
            "angular_velocity_radps": .9, "angular_acceleration_radps2": .8}


def fixture(transform):
    stage_id, direct_id, carrier_id = ("picker-north", "courier-19", "laden-3") if transform else (
        "courier-a", "courier-b", "carrier")
    shift = .5 if transform else 0.0

    def pose(x, y, yaw):
        if transform:
            return [8.4 - y, -5.7 + x, math.remainder(yaw + math.pi / 2, 2 * math.pi)]
        return [x, y, yaw]

    c = profile(.34, .8, .75)
    site = {
        "map": "transfer-level",
        "slot_ns": ns(.5),
        "max_time_ns": ns(25),
        "couriers": {
            stage_id: {"home": pose(-2, 0, 0), "stage": pose(-1.2, 0, 0), "goal": pose(2, 0, 0),
                       "profile": c},
            direct_id: {"home": pose(0, -2, math.pi / 2), "stage": None, "goal": pose(0, 2, math.pi / 2),
                        "profile": c},
        },
        "carrier": {
            "id": carrier_id, "profile": profile(.38, .85, .70),
            "home": pose(-3.3, 3.3, -math.pi / 4), "stage": pose(-2.1, 2.1, -math.pi / 4),
            "goal": pose(2.4, -2.4, -math.pi / 4),
        },
        "guards": [
            {"participant": direct_id, "axis": 0 if transform else 1,
             "sign": -1 if transform else 1, "position_m": 6.9 if transform else 1.5},
            {"participant": carrier_id, "axis": 1 if transform else 0,
             "sign": 1, "position_m": -4.7 if transform else 1.0},
        ],
    }

    def job(ready, deadline, priority):
        return {"ready_ns": ns(ready + shift), "deadline_ns": ns(deadline + shift), "priority": priority}

    initial = {"base": None, "version": 1, "mode": "normal", "carrier_plan": 83 if transform else 12,
               "carrier_tail_ns": ns(3.5 + shift), "jobs": {
                   stage_id: job(6, 18, 7), direct_id: job(6, 21, 2),
               }}
    revised = {"base": None, "version": 3, "mode": "protected", "carrier_plan": 94 if transform else 13,
               "carrier_tail_ns": ns(6.5 + shift), "jobs": {
                   stage_id: job(7, 20.9, 7), direct_id: job(6.5, 16.2, 12),
               }}
    return site, initial, revised, stage_id, direct_id


def carrier_path(site, patch):
    return station_path(site["carrier"], (("home", "stage", 0),
                        ("stage", "goal", patch["carrier_tail_ns"])), carrier=True)


def guard_checkpoint(site, participant, path):
    guard = next(item for item in site["guards"] if item["participant"] == participant)
    return point_checkpoint(path, guard["axis"], guard["sign"], guard["position_m"])


def slots(site, first_ns, last_ns):
    step = site["slot_ns"]
    return range((first_ns + step - 1) // step * step,
                 min(site["max_time_ns"], last_ns) + 1, step)


def completion_vector(patch, paths):
    order = sorted(paths, key=lambda key: (-patch["jobs"][key]["priority"], key))
    return tuple(paths[key].finish_ns for key in order)


def clear_of(first, second):
    return continuous_clearance(first, second) > 1e-9


def best_finish(site, patch, stage_id, direct_id, now_ns):
    """Enumerate independent timing choices and retain only swept-clear plans."""
    staged = patch["mode"] == "protected"
    c = carrier_path(site, patch)
    carrier_guard = guard_checkpoint(site, site["carrier"]["id"], c)[1] if staged else 0
    a, b = site["couriers"][stage_id], site["couriers"][direct_id]
    ja, jb = patch["jobs"][stage_id], patch["jobs"][direct_id]
    best = None
    for b_depart in slots(site, max(now_ns, jb["ready_ns"]), jb["deadline_ns"]):
        bp = station_path(b, (("home", "goal", b_depart),))
        if bp.finish_ns > min(jb["deadline_ns"], site["max_time_ns"]) or not clear_of(bp, c):
            continue
        b_guard = guard_checkpoint(site, direct_id, bp)[1] if staged else 0
        for a_depart in slots(site, max(now_ns, ja["ready_ns"]), ja["deadline_ns"]):
            if staged:
                approach = station_path(a, (("home", "stage", a_depart),))
                earliest_gate = max(approach.finish_ns, b_guard, carrier_guard)
                options = (station_path(a, (("home", "stage", a_depart), ("stage", "goal", gate)))
                           for gate in slots(site, earliest_gate, ja["deadline_ns"]))
            else:
                options = (station_path(a, (("home", "goal", a_depart),)),)
            for ap in options:
                if ap.finish_ns <= min(ja["deadline_ns"], site["max_time_ns"]) and clear_of(ap, c) and clear_of(ap, bp):
                    rank = completion_vector(patch, {stage_id: ap, direct_id: bp})
                    if best is None or rank < best:
                        best = rank
                    break
    return best


def native_plan(reply, site, patch, stage_id, direct_id, now):
    require(reply["status"] == "scheduled" and reply["version"] == patch["version"],
            "a feasible current schedule was not prepared")
    candidate = reply["plan"]
    require(type(candidate) is dict and set(candidate) == set(site["couriers"]),
            "schedule did not include both responsive couriers")
    trajectories = {}
    for participant, itinerary in candidate.items():
        require(type(itinerary) is dict and set(itinerary) == {"plan", "legs"} and
                type(itinerary["plan"]) is int and itinerary["plan"] > 0,
                "invalid participant plan ID or schedule shape")
        waypoints = ("home", "stage", "goal") if (
            participant == stage_id and patch["mode"] == "protected") else ("home", "goal")
        require(len(itinerary["legs"]) == len(waypoints) - 1, "wrong number of route legs")
        station = site["couriers"][participant]
        job = patch["jobs"][participant]
        latest = max(now, job["ready_ns"])
        intervals = []
        for index, record in enumerate(itinerary["legs"]):
            origin, destination = waypoints[index:index + 2]
            require(type(record) is dict and set(record) == {"from", "to", "start_ns", "end_ns"} and
                    record["from"] == origin and record["to"] == destination,
                    "plan used an unavailable route segment")
            depart = record["start_ns"]
            finish = record["end_ns"]
            require(type(depart) is int and type(finish) is int and
                    depart >= latest - ROUNDING_NS and depart % site["slot_ns"] == 0,
                    "departure missed its measured ready time or the site slot grid")
            interval = Leg.from_station(station, origin, destination, depart)
            true_finish = ns(interval.finish)
            require(abs(finish - true_finish) <= ROUNDING_NS, "reported leg time disagrees with native motion limits")
            latest = true_finish
            intervals.append(interval)
        require(latest <= min(job["deadline_ns"], site["max_time_ns"]),
                "courier plan missed its deadline")
        trajectories[participant] = Path(tuple(intervals), station["profile"]["radius_m"])
    carrier = carrier_path(site, patch)
    pairs = list(combinations((*trajectories.values(), carrier), 2))
    clearance = min(continuous_clearance(a, b) for a, b in pairs)
    if clearance < -1e-8:
        raise PhysicalConflict(f"planned authority caused a swept footprint overlap of {-clearance:.5f} m")
    require(clearance > 1e-9, "candidate granted touching circular footprints")
    if patch["mode"] == "protected":
        guard_time = max(
            guard_checkpoint(site, direct_id, trajectories[direct_id])[1],
            guard_checkpoint(site, site["carrier"]["id"], carrier)[1],
        )
        require(ns(trajectories[stage_id].legs[1].depart) + ROUNDING_NS >= guard_time,
                "protected leg was planned before its predicted guards")
    require(completion_vector(patch, trajectories) == best_finish(site, patch, stage_id, direct_id, now),
            "a higher-priority feasible completion was delayed")
    return candidate, trajectories, clearance


def request(identifier, when, **fields):
    return {"request_id": identifier, "now_ns": when, **fields}


def no_authority(reply, status, version):
    require(reply["status"] == status and reply["version"] == version and reply["plan"] is None
            and reply["commands"] == [], f"{status} did not suspend new movement authority")


def cancel_record(participant, plan, pose):
    return {"participant": participant, "plan": plan, "pose": list(pose)}


def observed(participant, plan, index, pose):
    return {"participant": participant, "plan": plan, "checkpoint": index, "pose": list(pose)}


def check_commands(reply, expected):
    keys = []
    for command in reply["commands"]:
        require(type(command) is dict and set(command) == {"participant", "plan", "leg"} and
                type(command["plan"]) is int and type(command["leg"]) is int,
                "malformed actuator command")
        keys.append((command["participant"], command["plan"], command["leg"]))
    require(sorted(keys) == sorted(expected), "obsolete, missing, or premature actuator authority")


def expected_cancellations(plan):
    return sorted((participant, record["plan"]) for participant, record in plan.items())


def verify_cancellations(reply, old):
    require(all(type(x) is dict and set(x) == {"participant", "plan"} for x in reply["revoke"]),
            "malformed cancel authority")
    require(sorted((item["participant"], item["plan"]) for item in reply["revoke"])
            == expected_cancellations(old), "the adapter did not revoke both prior itinerary IDs")


def replacement(app, directory, transform=False, miss_guard=False, loaded=False):
    site, initial, revised, stage_id, direct_id = fixture(transform)
    if loaded:
        # A heavier staged courier and a faster direct courier change the
        # native acceleration checkpoints and both optimal completion times.
        site["couriers"][stage_id]["profile"] = profile(.35, .74, .68)
        site["couriers"][direct_id]["profile"] = profile(.32, .83, .78)
        site["carrier"]["profile"] = profile(.38, .88, .72)
        revised["jobs"][stage_id]["deadline_ns"] = ns(21.1)
        revised["jobs"][direct_id]["deadline_ns"] = ns(16.4)
    driver = Driver(app, directory, site)
    stage_site, direct_site = site["couriers"][stage_id], site["couriers"][direct_id]
    carrier_id = site["carrier"]["id"]
    initial_event = request("initial", 0, patch=initial)
    initial_reply = driver.exchange(initial_event)
    old, old_paths, initial_clearance = native_plan(initial_reply, site, initial, stage_id, direct_id, 0)
    check_commands(initial_reply, [(p, record["plan"], 0) for p, record in old.items()])
    require(initial_reply["revoke"] == [], "first full snapshot emitted a spurious cancellation")

    gap_event = request("gap", ns(2), patch={**revised, "base": 2})
    gap = driver.exchange(gap_event)
    no_authority(gap, "stale", 1)
    require(gap["revoke"] == [], "a patch with a missing base changed old authority")
    accepted_event = request("catch-up", ns(2.5), patch=revised)
    accepted = driver.exchange(accepted_event)
    no_authority(accepted, "awaiting_cancel", 3)
    verify_cancellations(accepted, old)
    # Never replace the carrier prefix. It is already moving at the instant of
    # the catch-up, and the same exact rest-to-rest segment physically continues.
    old_c, new_c = carrier_path(site, initial), carrier_path(site, revised)
    require(old_c.legs[0] == new_c.legs[0] and
            math.dist(new_c.pose(2.5)[:2], new_c.legs[0].origin[:2]) > .1,
            "test fixture lacks a moving committed carrier")
    require(not clear_of(old_paths[direct_id], new_c), "fixture did not invalidate the earlier crossing")

    incomplete_event = request("first-cancel", ns(2.75), cancelled=[
        cancel_record(stage_id, old[stage_id]["plan"], stage_site["home"]),
        cancel_record(direct_id, old[direct_id]["plan"] + 100_000, direct_site["home"]),
        cancel_record(direct_id, old[direct_id]["plan"], direct_site["goal"]),
    ])
    incomplete = driver.exchange(incomplete_event)
    no_authority(incomplete, "awaiting_cancel", 3)
    require(incomplete["revoke"] == [], "fresh cancellation exchange repeated the revocations")
    last_cancel_event = request("second-cancel", ns(3.0), cancelled=[
        cancel_record(direct_id, old[direct_id]["plan"], direct_site["home"]),
    ])
    new_reply = driver.exchange(last_cancel_event)
    chosen, routes, clearance = native_plan(new_reply, site, revised, stage_id, direct_id, ns(3.0))
    require(new_reply["revoke"] == [] and
            all(chosen[id_]["plan"] != old[id_]["plan"] for id_ in chosen),
            "replacement reused an obsolete itinerary plan ID")
    check_commands(new_reply, [(p, record["plan"], 0) for p, record in chosen.items()])
    driver.exchange({**last_cancel_event, "cancelled": []}, rejected=True)
    require(driver.exchange(accepted_event) == accepted and driver.exchange(incomplete_event) == incomplete
            and driver.exchange(last_cancel_event) == new_reply and driver.exchange(gap_event) == gap,
            "a fresh process did not recover exact prior request receipts")
    old_packet = driver.exchange(request("old-patch-after-replan", ns(3.25), patch=initial))
    require(old_packet["status"] == "scheduled" and old_packet["version"] == 3
            and old_packet["plan"] == chosen and old_packet["revoke"] == [],
            "a late older schedule overwrote the current itinerary and authority")
    check_commands(old_packet, [])

    # First deliver a valid stage stop and convincing but invalid guard reports.
    staged_path, direct_path = routes[stage_id], routes[direct_id]
    a_index, at_stage, a_position = next(
        (i, t, p) for i, (t, p) in enumerate(staged_path.checkpoints())
        if math.dist(p[:2], stage_site["stage"][:2]) <= 1e-9
    )
    b_index, _, b_position = guard_checkpoint(site, direct_id, direct_path)
    c_index, at_carrier, c_position = guard_checkpoint(site, carrier_id, new_c)
    b_before_time, b_before = direct_path.checkpoints()[b_index - 1]
    gate_start = chosen[stage_id]["legs"][1]["start_ns"]
    prior_time = max(at_stage, at_carrier, b_before_time) + ROUNDING_NS
    prior_time = min(gate_start, prior_time)
    bad = driver.exchange(request("bad-progress", prior_time, progress=[
        observed(stage_id, chosen[stage_id]["plan"], a_index, a_position),
        observed(direct_id, old[direct_id]["plan"], b_index, b_position),
        observed(direct_id, chosen[direct_id]["plan"], b_index, direct_site["home"]),
        observed(carrier_id, initial["carrier_plan"], c_index, c_position),
    ]))
    require(bad["status"] == "scheduled" and bad["plan"] == chosen, "invalid progress rewrote a valid plan")
    check_commands(bad, [])
    one_guard = driver.exchange(request("one-guard", prior_time, progress=[
        observed(carrier_id, revised["carrier_plan"], c_index, c_position),
        observed(direct_id, chosen[direct_id]["plan"], b_index - 1, b_before),
    ]))
    require(one_guard["status"] == "scheduled" and one_guard["plan"] == chosen,
            "one guard changed the selected joint itinerary")
    check_commands(one_guard, [])
    final_event = request("other-guard", gate_start + (site["slot_ns"] if miss_guard else 0), progress=[
        observed(direct_id, chosen[direct_id]["plan"], b_index, b_position),
    ])
    final = driver.exchange(final_event)
    if miss_guard:
        no_authority(final, "blocked", 3)
    else:
        require(final["status"] == "scheduled" and final["version"] == 3 and final["plan"] == chosen,
                "valid current-plan guards did not release the reserved itinerary")
        check_commands(final, [(stage_id, chosen[stage_id]["plan"], 1)])
        require(driver.exchange(final_event) == final, "gate actuation receipt changed after process restart")
        idle = driver.exchange(request("idle", gate_start + site["slot_ns"], progress=[
            observed(direct_id, chosen[direct_id]["plan"], b_index - 1, b_before),
        ]))
        check_commands(idle, [])
        serial_finish = Leg.from_station(stage_site, "home", "goal", routes[direct_id].finish_ns).finish
        require(ns(serial_finish) > revised["jobs"][stage_id]["deadline_ns"],
                "fixture allowed waiting for the direct courier to finish before departure")

    return {"initial_separation_m": initial_clearance,
            "replanned_separation_m": clearance if not miss_guard else None,
            "replanned_finishes_ns": {p: route.finish_ns for p, route in routes.items()},
            "gate_start_ns": gate_start, "direct_guard_index": b_index,
            "carrier_guard_index": c_index, "late_gate_blocked": miss_guard}


def blocked(app, directory):
    site, _, patch, stage_id, direct_id = fixture(False)
    # Both couriers could independently meet these deadlines without the shared
    # carrier. The urgent job cannot make its deadline in the physical mission.
    patch = {**patch, "version": 1, "jobs": {
        **patch["jobs"], direct_id: {**patch["jobs"][direct_id], "deadline_ns": ns(15.9)},
    }}
    require(best_finish(site, patch, stage_id, direct_id, 0) is None, "blocked fixture admits a safe route")
    driver = Driver(app, directory, site)
    response = driver.exchange(request("impossible", 0, patch=patch))
    no_authority(response, "blocked", 1)
    require(response["revoke"] == [], "infeasible first schedule emitted a spurious revocation")
    return {"urgent_deadline_ns": patch["jobs"][direct_id]["deadline_ns"]}


def competition_suite(app, root):
    observations = {}
    cases = (
        ("joint_replan_preserves_moving_prefix", replacement, {}),
        ("rotated_shifted_replan_requires_both_guard_reports", replacement, {"transform": True}),
        ("asymmetric_acceleration_requires_new_timing", replacement, {"loaded": True}),
        ("late_progress_cannot_launch_a_missed_departure", replacement, {"miss_guard": True}),
        ("infeasible_urgent_deadline_stays_blocked", blocked, {}),
    )
    for name, check, kwargs in cases:
        try:
            result = check(app, root / name, **kwargs)
        except (Rejected, OSError, ValueError, TypeError, KeyError, IndexError, StopIteration) as error:
            observations[name] = {"passed": False, "observation": str(error),
                                  "physical_conflict": isinstance(error, PhysicalConflict)}
        else:
            observations[name] = {"passed": True, "observation": result}
    return observations
