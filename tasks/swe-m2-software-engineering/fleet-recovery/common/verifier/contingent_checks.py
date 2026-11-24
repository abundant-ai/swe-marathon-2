"""Verify a contingent authority tree against independent motion and lift sessions."""

from dataclasses import dataclass
from itertools import combinations, product
import json
import math
import os
import pwd
import subprocess
import sys

from competition_checks import (
    Leg,
    Path,
    ROUNDING_NS,
    SECOND,
    continuous_clearance,
    ns,
    profile,
    station_path,
)
from fleet_world import Rejected, require
from rmf_checks import executable


FIRST = ns(5)
LIFT = ns(9.25)
SLOT = ns(.25)
POSITION_EPSILON = 1e-6
CLEARANCE_EPSILON = 1e-9


def fixture(urgent_relief):
    """Make one discontinuous carrier history or one early relief-departure history."""
    if urgent_relief:
        a, b, carrier = "sterile-picker", "north-runner", "materials-13"
        carrier_names = ("dock-normal", "late-yard")
        lift_names = ("main-current", "relief-dispatched")
        cabins = ("near-service", "far-service")
        deadlines = (16.60, 19.40)
        times = (((14.15, 17.10), (17., 21.)), ((17., 21.), (15., 13.)))
    else:
        a, b, carrier = "east", "north", "cart"
        carrier_names = ("first-departure", "second-departure")
        lift_names = ("primary-window", "relief-window")
        cabins = ("express", "reserve")
        deadlines = (14.60, 19.80)
        times = (((12., 17.10), (16., 21.)), ((16., 21.), (13., 18.)))

    def pose(x, y, angle):
        if urgent_relief:
            return [8.4 - y, -5.7 + x, math.remainder(angle + math.pi / 2, 2 * math.pi)]
        return [x, y, angle]

    courier = profile(.34, .8, .75)
    return {
        "map": "island-transfer" if not urgent_relief else "north-transfer",
        "slot_ns": SLOT,
        "max_time_ns": ns(28),
        "carrier_observe_ns": FIRST,
        "lift_observe_ns": LIFT,
        "couriers": {
            a: {"profile": courier, "home": pose(-3., 0., 0.), "stage": pose(-1.2, 0., 0.),
                "goal": pose(2., 0., 0.), "deadline_ns": ns(deadlines[0])},
            b: {"profile": courier, "home": pose(0., -3., math.pi / 2),
                "stage": pose(0., -1.2, math.pi / 2), "goal": pose(0., 2., math.pi / 2),
                "deadline_ns": ns(deadlines[1])},
        },
        "carrier": {"id": carrier, "profile": profile(.38, .85, .70),
                    "home": pose(-3.3, 3.3, -math.pi / 4),
                    "stage": pose(-2.1, 2.1, -math.pi / 4),
                    "goal": pose(2.4, -2.4, -math.pi / 4),
                    "options": {
                        carrier_names[0]: {"plan": 215, "departure_ns": ns(5.5)},
                        carrier_names[1]: {"plan": 219, "departure_ns": ns(7.)},
                    }},
        "cabins": {
            cabin: {"ride_ns": ns(1.25),
                    "doors": {a: pose(x, 0., 0.), b: pose(0., x, math.pi / 2)}}
            for cabin, x in zip(cabins, (2.55, 3.15), strict=True)
        },
        "lift_options": {
            name: {
                "version": (44, 52)[version],
                "slots": {
                    cabin: {person: {
                        "session_id": f"{cabin}/{person}/{version + 41}",
                        "board_ns": ns(times[version][j][i]),
                        "floor": 2 if urgent_relief else 0,
                    } for i, person in enumerate((a, b))}
                    for j, cabin in enumerate(cabins)
                },
            }
            for version, name in enumerate(lift_names)
        },
    }


def fields(value, names, context):
    require(type(value) is dict and set(value) == set(names), f"malformed {context}")
    return value


def validated_move(record, station, origin, finish, earliest, latest, slot, *, known_fields=()):
    fields(record, ("start_ns", "end_ns", *known_fields), "movement leg")
    start, end = record["start_ns"], record["end_ns"]
    require(type(start) is int and type(end) is int and start >= earliest
            and start % slot == 0 and end > start, "movement was scheduled outside its authority interval")
    p = station["profile"]
    leg = Leg(tuple(origin), tuple(finish), start / SECOND,
              p["linear_velocity_mps"], p["linear_acceleration_mps2"])
    observed_end = ns(leg.finish)
    require(abs(end - observed_end) <= ROUNDING_NS, "movement duration disagreed with native vehicle limits")
    require(max(end, observed_end) <= latest + ROUNDING_NS, "movement missed its authority or planning horizon")
    return leg


def clearance_of(paths):
    return min(continuous_clearance(first, second) for first, second in combinations(paths, 2))


@dataclass(frozen=True)
class Certificate:
    approaches: dict
    crossings: dict
    docks: dict
    leaf_metrics: dict


def certify(site, policy):
    """Validate every leaf using independently reconstructed rest-to-rest motion."""
    fields(policy, ("approaches", "after_carrier"), "contingency policy")
    people = site["couriers"]
    carrier = site["carrier"]
    slot = site["slot_ns"]
    horizon = site["max_time_ns"]
    first = site["carrier_observe_ns"]
    second = site["lift_observe_ns"]
    approaches = fields(policy["approaches"], people, "common approaches")
    carriers = fields(policy["after_carrier"], carrier["options"], "carrier branches")
    shared = {}
    gate_routes = {}
    selected_docks = {}
    measurements = {}

    for name, initial in approaches.items():
        platform = people[name]
        shared[name] = validated_move(initial, platform, platform["home"], platform["stage"], 0,
                                      first, slot)

    for option, carrier_plan in carrier["options"].items():
        branch = fields(carriers[option], ("crossings", "after_lift"), f"carrier branch {option}")
        crossings = fields(branch["crossings"], people, "crossing authorities")
        lifts = fields(branch["after_lift"], site["lift_options"], "lift branches")
        cart = station_path(carrier, (("home", "stage", 0),
                                     ("stage", "goal", carrier_plan["departure_ns"])), carrier=True)
        first_routes = {}
        for name, movement in crossings.items():
            platform = people[name]
            first_routes[name] = validated_move(
                movement, platform, platform["stage"], platform["goal"],
                max(first, ns(shared[name].finish) - ROUNDING_NS), horizon, slot,
            )
        gate_routes[option] = crossings
        for lift_option, plan in lifts.items():
            fields(plan, ("dock",), f"lift branch {lift_option}")
            docks = fields(plan["dock"], people, "dock authorities")
            slots = site["lift_options"][lift_option]["slots"]
            routes = {}
            reservations = {}
            deadlines = {}
            for name, move in docks.items():
                require(type(move) is dict and move.get("cabin") in site["cabins"],
                        "dock authority chose an unavailable cabin")
                cabin_id = move["cabin"]
                cabin = site["cabins"][cabin_id]
                platform = people[name]
                slot_record = slots[cabin_id][name]
                board = slot_record["board_ns"]
                arrival = board + cabin["ride_ns"]
                leg = validated_move(
                    move, platform, platform["goal"], cabin["doors"][name],
                    max(second, ns(first_routes[name].finish) - ROUNDING_NS), board, slot,
                    known_fields=("cabin", "board_ns", "arrival_ns"),
                )
                require(type(move["board_ns"]) is int and type(move["arrival_ns"]) is int
                        and move["board_ns"] == board and move["arrival_ns"] == arrival,
                        "dock authority did not use the current published lift session")
                require(arrival <= min(platform["deadline_ns"], horizon),
                        "lift plan missed a courier delivery deadline")
                reservations.setdefault(cabin_id, []).append((board, arrival))
                routes[name] = Path(
                    (shared[name], first_routes[name], leg), platform["profile"]["radius_m"])
                deadlines[name] = arrival
            for occupancy in reservations.values():
                occupancy.sort()
                require(all(current[1] <= later[0] for current, later in zip(occupancy, occupancy[1:])),
                        "two lift allocations overlap in one cabin")

            clearance = clearance_of([*routes.values(), cart])
            require(clearance > CLEARANCE_EPSILON,
                    f"counterfactual {option}/{lift_option} has unsafe swept clearance {clearance:.7f} m")
            leaf = (option, lift_option)
            selected_docks[leaf] = docks
            measurements[leaf] = {
                "minimum_clearance_m": clearance,
                "completion_ns": deadlines,
                "crossing_departures_ns": {name: entry["start_ns"] for name, entry in crossings.items()},
                "cabin_assignments": {name: entry["cabin"] for name, entry in docks.items()},
            }
    return Certificate(approaches, gate_routes, selected_docks, measurements)


class Driver:
    """Send valid and invalid observations through independently restarted processes."""

    def __init__(self, app, directory, site):
        directory.mkdir(mode=0o755)
        self.app = app
        self.directory = directory
        self.site = directory / "site.json"
        self.site.write_text(json.dumps(site))
        self.inbox = directory / "control"
        self.inbox.mkdir(mode=0o777)
        self.inbox.chmod(0o777)
        self.sequence = 0

    def exchange(self, packet, *, conflict=False):
        self.sequence += 1
        message = self.directory / f"packet-{self.sequence}.json"
        message.write_text(json.dumps(packet, allow_nan=False))
        reply = self.inbox / f"reply-{self.sequence}.json"
        identity = {}
        if os.geteuid() == 0:
            try:
                user = pwd.getpwnam("candidate")
            except KeyError:
                user = pwd.getpwnam("nobody")
            identity = {"user": user.pw_uid, "group": user.pw_gid, "extra_groups": []}
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.inbox), "LC_ALL": "C.UTF-8",
            "FLEET_RMF_NATIVE": executable("rmf-native"),
        }
        for name in ("RMF_ROOT", "EIGEN_INCLUDE", "FLEET_COMPETITION_NATIVE",
                     "FLEET_CONTINGENT_NATIVE", "FLEET_RMF_CONTINGENT_NATIVE"):
            if name in os.environ:
                environment[name] = os.environ[name]
        argv = [sys.executable, "-B", "-m", "fleet_recovery", "rmf-contingent", "--site",
                str(self.site), "--state", str(self.inbox / "journal"), "--event",
                str(message), "--output", str(reply)]
        try:
            child = subprocess.run(argv, cwd=self.app, env=environment, **identity,
                                   capture_output=True, timeout=55)
        except subprocess.TimeoutExpired as error:
            raise Rejected("contingent authority command timed out") from error
        if conflict:
            require(child.returncode != 0, "reusing a committed request ID with different content succeeded")
            return None
        error = child.stderr.decode(errors="replace").strip()[-400:]
        require(child.returncode == 0 and not reply.is_symlink() and reply.is_file(),
                f"contingent authority command failed to publish a reply{': ' + error if error else ''}")
        require(reply.stat().st_size <= 100_000, "contingent authority reply is oversized")
        response = fields(json.loads(reply.read_text()), ("status", "policy", "commands"), "authority reply")
        require(type(response["commands"]) is list, "command list is malformed")
        return response


def request(request_id, now, kind, **payload):
    return {"request_id": request_id, "now_ns": now, "kind": kind, **payload}


def expect(response, policy, expected):
    require(response["status"] == "ready" and response["policy"] == policy,
            "a runtime observation changed the precommitted policy")
    clean = []
    for command in response["commands"]:
        require(type(command) is dict and type(command.get("start_ns")) is int
                and type(command.get("end_ns")) is int, "actuator authority is malformed")
        clean.append(command)
    canonical = lambda records: sorted(json.dumps(record, sort_keys=True) for record in records)
    require(canonical(clean) == canonical(expected), "missing, replayed, or premature movement authority")


def move_commands(kind, movement):
    commands = []
    for courier, record in movement.items():
        command = {"kind": kind, "courier": courier,
                   "start_ns": record["start_ns"], "end_ns": record["end_ns"]}
        if kind == "dock":
            command["cabin"] = record["cabin"]
        commands.append(command)
    return commands


def run_history(app, directory, site, carrier_option, lift_option):
    """Only release each authority from its own correct event in one possible history."""
    driver = Driver(app, directory, site)
    first, second = site["carrier_observe_ns"], site["lift_observe_ns"]
    carrier = site["carrier"]
    plan = carrier["options"][carrier_option]["plan"]
    version = site["lift_options"][lift_option]["version"]
    carrier_observation = {"option": carrier_option, "plan": plan, "pose": carrier["stage"]}
    lift_observation = {"option": lift_option, "version": version}

    begin = request("begin", 0, "start")
    initial = driver.exchange(begin)
    require(initial["status"] == "ready", "no feasible policy was issued for the available histories")
    policy = initial["policy"]
    certificate = certify(site, policy)
    approach_commands = move_commands("approach", certificate.approaches)
    expect(initial, policy, approach_commands)
    # Even an otherwise good lift message cannot authorize the later leg early.
    expect(driver.exchange(request("lift-without-carrier", first - 2 * SLOT, "lift", **lift_observation)),
           policy, [])
    expect(driver.exchange(request("early-carrier", first - SLOT, "carrier", **carrier_observation)),
           policy, [])
    for name, alteration in (
        ("carrier-stale-plan", {"plan": plan - 1}),
        ("carrier-wrong-pose", {"pose": carrier["home"]}),
    ):
        expect(driver.exchange(request(name, first, "carrier", **(carrier_observation | alteration))),
               policy, [])
    carrier_event = request("observed-carrier", first, "carrier", **carrier_observation)
    carrier_response = driver.exchange(carrier_event)
    crossing_commands = move_commands("cross", certificate.crossings[carrier_option])
    expect(carrier_response, policy, crossing_commands)
    expect(driver.exchange(request("same-carrier-new-id", first, "carrier", **carrier_observation)),
           policy, [])
    donor = next(index for index in carrier["options"] if index != carrier_option)
    expect(driver.exchange(request("obsolete-carrier-replacement", first + SLOT, "carrier",
                                   **(carrier_observation | {"option": donor,
                                      "plan": carrier["options"][donor]["plan"]}))), policy, [])
    expect(driver.exchange(request("early-lift", second - SLOT, "lift", **lift_observation)),
           policy, [])
    expect(driver.exchange(request("stale-lift", second, "lift",
                                   **(lift_observation | {"version": version - 1}))), policy, [])
    lift_event = request("observed-lift", second, "lift", **lift_observation)
    lift_response = driver.exchange(lift_event)
    docks = certificate.docks[(carrier_option, lift_option)]
    expect(lift_response, policy, move_commands("dock", docks))
    donor_lift = next(index for index in site["lift_options"] if index != lift_option)
    expect(driver.exchange(request("obsolete-lift-replacement", second, "lift", option=donor_lift,
                                   version=site["lift_options"][donor_lift]["version"])), policy, [])
    driver.exchange({**carrier_event, "plan": plan - 1}, conflict=True)
    require(driver.exchange(begin) == initial and driver.exchange(carrier_event) == carrier_response
            and driver.exchange(lift_event) == lift_response, "restarting lost an exact authority receipt")

    previously_observed = second
    boards = {}
    for name, dock in sorted(docks.items(), key=lambda item: item[1]["board_ns"]):
        cabin = dock["cabin"]
        board = dock["board_ns"]
        session = site["lift_options"][lift_option]["slots"][cabin][name]
        door = {"courier": name, "cabin": cabin, "session_id": session["session_id"],
                "floor": session["floor"], "open": True, "pose": site["cabins"][cabin]["doors"][name]}
        alternate = next(key for key in site["cabins"] if key != cabin)
        if board - ns(.01) >= previously_observed:
            early = request(f"early-{name}", board - ns(.01), "door", **door)
            expect(driver.exchange(early), policy, [])
        invalid = {
            "wrong-cabin": {"cabin": alternate},
            "stale-session": {"session_id": f"obsolete/{session['session_id']}"},
            "wrong-floor": {"floor": session["floor"] + 1},
            "closed": {"open": False},
            "wrong-pose": {"pose": site["couriers"][name]["goal"]},
        }
        for label, changes in invalid.items():
            expect(driver.exchange(request(f"{label}-{name}", board, "door", **(door | changes))),
                   policy, [])
        board_event = request(f"observed-boarding-{name}", board, "door", **door)
        board_response = driver.exchange(board_event)
        applied = {"kind": "board", "courier": name, "cabin": cabin,
                   "session_id": session["session_id"],
                   "start_ns": board, "end_ns": dock["arrival_ns"]}
        expect(board_response, policy, [applied])
        expect(driver.exchange(request(f"repeat-boarding-{name}", board, "door", **door)), policy, [])
        boards[name] = (board_event, board_response)
        previously_observed = board
    for event, response in boards.values():
        require(driver.exchange(event) == response, "a later observation changed a boarding receipt")
    receipts = (tuple(approach_commands), tuple(crossing_commands))
    return receipts, certificate.leaf_metrics[(carrier_option, lift_option)]


def mission(app, root, urgent_relief):
    root.mkdir(mode=0o755)
    site = fixture(urgent_relief)
    histories = {}
    common = None
    observed = {}
    for carrier, lift in product(site["carrier"]["options"], site["lift_options"]):
        (approach, crossing), metrics = run_history(app, root / f"{carrier}--{lift}", site, carrier, lift)
        normalize = lambda commands: sorted((c["courier"], c["start_ns"], c["end_ns"]) for c in commands)
        approach = normalize(approach)
        crossing = normalize(crossing)
        require(common is None or common == approach,
                "approach authority differed between histories before the first observation")
        require(carrier not in observed or observed[carrier] == crossing,
                "crossing authority depended on the still-unobserved lift outcome")
        common = approach
        observed[carrier] = crossing
        histories[f"{carrier}/{lift}"] = metrics
    return {"histories": histories, "verified_histories": len(histories),
            "common_approach": common, "carrier_conditioned_crossing": observed,
            "minimum_clearance_m": min(values["minimum_clearance_m"] for values in histories.values())}


def contingent_suite(app, root):
    observations = {}
    for name, urgent_relief in (("uncertain_carrier_crossing", False),
                                ("urgent_relief_after_crossing_commitments", True)):
        try:
            result = mission(app, root / name, urgent_relief)
        except (Rejected, OSError, ValueError, TypeError, KeyError, IndexError) as error:
            observations[name] = {"passed": False, "observation": str(error), "physical_conflict": False}
        else:
            observations[name] = {"passed": True, "observation": result}
    return observations
