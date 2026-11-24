"""Check protected handovers by replay and independent reachable-assignment search."""

from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from itertools import product
from typing import Any, Callable, Iterator

from probes import Record, closure, controller, hardware_claims, snapshot


Command = dict[str, Any]
Run = Callable[..., object]


@dataclass(frozen=True)
class State:
    """Active controllers and current device modes in sorted hardware order."""

    active: frozenset[str]
    modes: tuple[str, ...]


class Timeline:
    """Independent serial tick simulator for authored handover specifications."""

    def __init__(self, spec: Record):
        self.spec = spec
        self.schedule = spec["schedule"]
        self.limit = self.schedule["deadline"]
        self.controllers = spec["controllers"]
        self.deps = {name: closure(self.controllers, [name]) for name in self.controllers}
        self.hardware = tuple(sorted(spec["hardware"]))
        self.positions = {name: index for index, name in enumerate(self.hardware)}
        readback = spec["snapshot"]
        self.devices = readback["devices"]
        self.initial = State(frozenset(readback["active"]), tuple(self.devices[name]["mode"] for name in self.hardware))
        self.services = tuple(tuple(self.required(option) for option in service)
                              for service in self.schedule["protected"])
        self.groups = [(group["id"], tuple(self.required(option) for option in group["options"]))
                       for group in spec["groups"]]
        self.open_ticks = {
            device: {tick for tick in range(self.limit + 1) if device_state["state"] == "ready" and
                     not any(begin <= tick < end for begin, end in self.schedule["maintenance"].get(device, ()))}
            for device, device_state in self.devices.items()
        }

    def required(self, option: list[str]) -> frozenset[str]:
        """Resolve all controllers, including transitive dependencies, for one option."""
        return frozenset(closure(self.controllers, option))

    @cache
    def claims(self, active: frozenset[str]) -> dict[str, str] | None:
        """Derive compatible modes and reject dependency gaps or conflicting claims."""
        if any(not self.deps[name] <= active for name in active):
            return None
        if any(not any(option <= active for option in service) for service in self.services):
            return None
        return hardware_claims(self.spec, active, set())

    def holding(self, state: State, first: int, last: int) -> bool:
        """Check an unchanged active state on an inclusive tick interval."""
        demands = self.claims(state.active)
        return demands is not None and all(
            state.modes[self.positions[device]] == mode
            and all(tick in self.open_ticks[device] for tick in range(first, last + 1))
            for device, mode in demands.items()
        )

    def duration(self, kind: str, name: str, mode: str = "") -> int:
        """Return the commissioned duration for the named primitive."""
        values = self.schedule["durations"][kind]
        return values.get(name, {}).get(mode, 1) if kind == "mode" else values.get(name, 1)

    def advance(self, state: State, command: Command) -> State | None:
        """Apply a primitive after checking safety at both sides of its state boundary."""
        first, last = command["start"], command["end"]
        kind = command.get("kind")
        if not self.holding(state, first, first):
            return None
        active, modes = state.active, state.modes
        if kind in ("start", "stop"):
            name = command.get("controller")
            if not isinstance(name, str) or name not in self.controllers or last - first != self.duration(kind, name):
                return None
            if kind == "stop":
                if name not in active:
                    return None
                after = State(active - {name}, modes)
                return after if self.holding(after, first, last) else None
            if name in active or not (self.deps[name] - {name}) <= active:
                return None
            for device, claim in self.controllers[name]["claims"].items():
                if state.modes[self.positions[device]] != claim["mode"] or any(
                    tick not in self.open_ticks[device] for tick in range(first, last + 1)
                ):
                    return None
            after = State(active | {name}, modes)
            return after if self.holding(state, first, last) and self.holding(after, last, last) else None

        if kind != "mode":
            return None
        device, mode = command.get("device"), command.get("mode")
        if (not isinstance(device, str) or device not in self.positions or not isinstance(mode, str)
                or mode not in self.spec["hardware"][device]["modes"]
                or type(command.get("generation")) is not int or command["generation"] != self.devices[device]["generation"]
                or last - first != self.duration(kind, device, mode)):
            return None
        if any(device in self.controllers[name]["claims"] for name in active):
            return None
        if any(tick not in self.open_ticks[device] for tick in range(first, last + 1)):
            return None
        access = self.schedule["switch_windows"].get(device, [(0, self.limit + 1)])
        if not any(lo <= first and last <= hi for lo, hi in access):
            return None
        index = self.positions[device]
        after = State(active, modes[:index] + (mode,) + modes[index + 1:])
        return after if self.holding(state, first, last) and self.holding(after, last, last) else None

    def options(self, state: State, tick: int) -> Iterator[Command]:
        """Enumerate possible serial actions without choosing a preferred target."""
        for name in self.controllers:
            kind = "stop" if name in state.active else "start"
            yield {"kind": kind, "controller": name, "start": tick, "end": tick + self.duration(kind, name)}
        for device, modes in self.spec["hardware"].items():
            for mode in modes["modes"]:
                if mode != state.modes[self.positions[device]]:
                    yield {"kind": "mode", "device": device, "mode": mode,
                           "generation": self.devices[device]["generation"], "start": tick,
                           "end": tick + self.duration("mode", device, mode)}

    @cache
    def reachable(self, tick: int, state: State, target: frozenset[str]) -> bool:
        """Find any safe route to a fixed active target through the deadline."""
        if not self.holding(state, tick, tick):
            return False
        if target <= state.active and self.holding(state, tick, self.limit):
            return True
        if tick == self.limit:
            return False
        for command in self.options(state, tick):
            end = command["end"]
            if end <= self.limit:
                after = self.advance(state, command)
                if after is not None and self.reachable(end, after, target):
                    return True
        return self.reachable(tick + 1, state, target)

    def best(self) -> dict[str, int | None] | None:
        """Try all requested assignments in published rank order, returning the best reachable one."""
        group_sizes = tuple(len(options) for _, options in self.groups)
        rankings = sorted(product(*(range(size + 1) for size in group_sizes)),
                          key=lambda ranks: (sum(rank == size for rank, size in zip(ranks, group_sizes, strict=True)), ranks))
        for ranks in rankings:
            chosen = {key: index if index < len(options) else None
                      for (key, options), index in zip(self.groups, ranks, strict=True)}
            roots = frozenset().union(*(options[index] for (_, options), index in zip(self.groups, ranks, strict=True)
                                       if index < len(options)))
            if hardware_claims(self.spec, roots, set()) is None:
                continue
            if self.reachable(0, self.initial, roots):
                return chosen
        return None

    def verifies(self, report: object, best: dict[str, int | None] | None) -> bool:
        """Validate a candidate trajectory without preferring a particular optimal schedule."""
        if not isinstance(report, dict):
            return False
        if best is None:
            return report.get("status") == "blocked" and report.get("selected") == {} and report.get("operations") == []
        selected, operations = report.get("selected"), report.get("operations")
        if (report.get("status") != "scheduled" or not isinstance(selected, dict) or selected != best
                or any(value is not None and type(value) is not int for value in selected.values())
                or not isinstance(operations, list) or len(operations) > self.limit):
            return False
        state, tick = self.initial, 0
        for command in operations:
            if not isinstance(command, dict):
                return False
            first, last = command.get("start"), command.get("end")
            if type(first) is not int or type(last) is not int or not tick <= first < last <= self.limit:
                return False
            if not self.holding(state, tick, first):
                return False
            after = self.advance(state, command)
            if after is None:
                return False
            state, tick = after, last
        if not self.holding(state, tick, self.limit):
            return False
        actual = {key: next((index for index, option in enumerate(options) if option <= state.active), None)
                  for key, options in self.groups}
        return actual == selected


def spec(
    controllers: dict[str, Record], hardware: dict[str, Record],
    initial: Record, groups: list[Record], protected: list[list[list[str]]],
    deadline: int, *, starts: dict[str, int] | None = None, stops: dict[str, int] | None = None,
    modes: dict[str, dict[str, int]] | None = None, maintenance: dict[str, list[list[int]]] | None = None,
    windows: dict[str, list[list[int]]] | None = None,
) -> Record:
    """Build a complete native schedule request using standby-free defaults."""
    return {"controllers": controllers, "hardware": hardware, "snapshot": initial, "groups": groups,
            "schedule": {"deadline": deadline, "protected": protected,
                         "durations": {"start": starts or {}, "stop": stops or {}, "mode": modes or {}},
                         "maintenance": maintenance or {}, "switch_windows": windows or {}}}


def drive_handover() -> Record:
    """Require a two-controller standby chain before releasing a protected drive."""
    return spec(
        {
            "velocity_driver": controller(device="axis", mode="velocity", interfaces=("servo",)),
            "velocity_guard": controller(["velocity_driver"]),
            "position_driver": controller(device="axis", mode="position", interfaces=("servo",)),
            "position_guard": controller(["position_driver"]),
            "watchdog_bus": controller(device="relay", mode="hold", interfaces=("safe",)),
            "watchdog": controller(["watchdog_bus"]),
        },
        {"axis": {"modes": {"velocity": ["servo"], "position": ["servo"]}},
         "relay": {"modes": {"hold": ["safe"]}}},
        snapshot({"axis": (23, "velocity", "ready"), "relay": (41, "hold", "ready")},
                 ["velocity_driver", "velocity_guard"]),
        [{"id": "delivery", "options": [["position_guard"], ["velocity_guard"]]}],
        [[["velocity_guard"], ["watchdog"], ["position_guard"]]], 14,
        starts={"watchdog_bus": 2, "watchdog": 2, "position_driver": 2}, stops={"velocity_guard": 2},
        modes={"axis": {"position": 2}}, windows={"axis": [[7, 9]]},
    )


def slot_fixture(*, split: bool = False) -> Record:
    """Use a late usable mode slot or refuse to merge disjoint authorizations."""
    return spec(
        {
            "safe": controller(device="relay", mode="hold", interfaces=("safe",)),
            "limited_motion": controller(device="axis", mode="velocity", interfaces=("servo",)),
            "position_delivery": controller(device="axis", mode="position", interfaces=("servo",)),
        },
        {"axis": {"modes": {"velocity": ["servo"], "position": ["servo"]}},
         "relay": {"modes": {"hold": ["safe"]}}},
        snapshot({"axis": (21, "velocity", "ready"), "relay": (6, "hold", "ready")}, ["safe"]),
        [{"id": "delivery", "options": [["position_delivery"], ["limited_motion"]]}], [[["safe"]]], 8,
        modes={"axis": {"position": 2}}, windows={"axis": [[1, 2], [2, 3]] if split else [[5, 7]]},
    )


def outage(*, infeasible: bool = False) -> Record:
    """Continue the current service after a planned outage requires a temporary standby."""
    return spec(
        {
            "primary": controller(device="north", mode="hold", interfaces=("watch",)),
            "secondary": controller(device="south", mode="hold", interfaces=("watch",)),
            "mission": controller(["primary"]),
        },
        {"north": {"modes": {"hold": ["watch"]}}, "south": {"modes": {"hold": ["watch"]}}},
        snapshot({"north": (12, "hold", "ready"), "south": (3, "hold", "ready")}, ["primary", "mission"]),
        [{"id": "service", "options": [["mission"], ["secondary"]]}],
        [[["primary"], ["secondary"]]], 11, starts={"secondary": 5 if infeasible else 2, "primary": 2},
        maintenance={"north": [[4, 7]]},
    )


def allocation() -> Record:
    """Make the best static pair inaccessible and the locally preferred fallback conflicting."""
    return spec(
        {
            "hold": controller(device="relay", mode="hold", interfaces=("watch",)),
            "lead_pos": controller(device="axis", mode="position", interfaces=("left",)),
            "lead_vel_left": controller(device="axis", mode="velocity", interfaces=("left",)),
            "lead_vel_right": controller(device="axis", mode="velocity", interfaces=("right",)),
            "task_pos": controller(device="axis", mode="position", interfaces=("right",)),
            "task_vel": controller(device="axis", mode="velocity", interfaces=("left",)),
        },
        {"axis": {"modes": {"position": ["left", "right"], "velocity": ["left", "right"]}},
         "relay": {"modes": {"hold": ["watch"]}}},
        snapshot({"axis": (71, "velocity", "ready"), "relay": (36, "hold", "ready")}, ["hold", "lead_vel_left"]),
        [{"id": "lead", "options": [["lead_pos"], ["lead_vel_left"], ["lead_vel_right"]]},
         {"id": "loaded_task", "options": [["task_pos"], ["task_vel"]]},
         {"id": "safety", "options": [["hold"]]}],
        [[["hold"]]], 9, modes={"axis": {"position": 3}}, windows={"axis": [[5, 7]]},
    )


def priority() -> Record:
    """Break a true one-group capacity tie using the published group ordering."""
    return spec(
        {"main": controller(device="bridge", mode="hold", interfaces=("only",)),
         "aux": controller(device="bridge", mode="hold", interfaces=("only",)),
         "watch": controller()},
        {"bridge": {"modes": {"hold": ["only"]}}},
        snapshot({"bridge": (16, "hold", "ready")}, ["watch"]),
        [{"id": "first", "options": [["main"]]}, {"id": "second", "options": [["aux"]]}],
        [[["watch"]]], 4,
    )


def startup(*, deadline_loss: bool = False) -> Record:
    """Require recovery after a lost mid-start interval or block on lost final protection."""
    protected = [[["loader"]]] if deadline_loss else [[["safety"]]]
    active = ["safety", "loader"] if deadline_loss else ["safety"]
    return spec(
        {"safety": controller(), "loader": controller(device="rack", mode="hold", interfaces=("gate",))},
        {"rack": {"modes": {"hold": ["gate"]}}},
        snapshot({"rack": (5, "hold", "ready")}, active),
        [{"id": "load", "options": [["loader"]]}], protected, 8,
        starts={"loader": 4}, maintenance={"rack": [[8, 9]] if deadline_loss else [[1, 4]]},
    )


def cases() -> list[tuple[str, Record, dict[str, int | None] | None]]:
    """Return authored expected optima as a cross-check on independent reachability."""
    return [
        ("make_before_break_standby_chain", drive_handover(), {"delivery": 0}),
        ("wait_for_whole_mode_slot", slot_fixture(), {"delivery": 0}),
        ("do_not_merge_short_authorizations", slot_fixture(split=True), {"delivery": 1}),
        ("preempt_outage_even_with_initial_goal", outage(), {"service": 0}),
        ("blocked_when_standby_misses_outage", outage(infeasible=True), None),
        ("best_reachable_joint_assignment", allocation(), {"lead": 2, "loaded_task": 1, "safety": 0}),
        ("ordered_priority_for_equal_service", priority(), {"first": 0, "second": None}),
        ("start_checks_entire_device_ready_interval", startup(), {"load": 0}),
        ("blocked_protection_at_inclusive_deadline", startup(deadline_loss=True), None),
    ]


def checks_handover(run: Run) -> dict[str, bool]:
    """Exercise legal alternatives, protected failures and malformed timed input."""
    evidence = {}
    for name, request, authored in cases():
        timeline = Timeline(request)
        optimum = timeline.best()
        if optimum != authored:
            raise RuntimeError(f"Invalid handover fixture {name}: expected {authored}, search found {optimum}")
        evidence[name] = timeline.verifies(run("schedule", request), optimum)
    malformed = []
    invalid = deepcopy(drive_handover())
    invalid["schedule"]["durations"]["start"]["watchdog"] = True
    malformed.append(invalid)
    invalid = deepcopy(slot_fixture())
    invalid["schedule"]["switch_windows"]["axis"] = [[5, 10]]
    malformed.append(invalid)
    invalid = deepcopy(priority())
    invalid["schedule"]["protected"] = [[["undeclared"]]]
    malformed.append(invalid)
    evidence["reject_malformed_timing_preserves_existing_report"] = all(
        run("schedule", request, invalid=True) is True for request in malformed)
    Timeline.claims.cache_clear()
    Timeline.reachable.cache_clear()
    return evidence
