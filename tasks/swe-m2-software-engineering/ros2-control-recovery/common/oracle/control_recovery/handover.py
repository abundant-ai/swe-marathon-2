"""Plan controller mode changes through time with continuous protected coverage."""

from collections import defaultdict
from dataclasses import dataclass
from functools import cache

from .core import counter, names_of, object_of


@dataclass(frozen=True)
class Configuration:
    """Controllers with active authority and device modes in fixed device order."""

    active: frozenset[str]
    modes: tuple[str, ...]


@dataclass(frozen=True)
class Handover:
    """Commissioned timing, outage windows and alternative protected services."""

    deadline: int
    protected: tuple
    starts: dict
    stops: dict
    modes: dict
    maintenance: dict
    slots: dict

    @classmethod
    def parse(cls, spec, installation):
        body = object_of(spec["schedule"])
        deadline = counter(body["deadline"])
        hardware = spec["hardware"]
        if deadline > 36 or len(installation.requirements) > 10 or len(hardware) > 4:
            raise ValueError("handover exceeds the commissioned size")
        if not isinstance(body["protected"], list):
            raise ValueError("protected services must be a list")
        services = tuple(
            parse_service(alternatives, installation.closures) for alternatives in body["protected"]
        )

        def intervals(field):
            raw = object_of(body[field])
            if not raw.keys() <= hardware.keys():
                raise ValueError("unknown device in schedule")
            parsed = {}
            for device, windows in raw.items():
                if not isinstance(windows, list):
                    raise ValueError("windows must be a list")
                parsed[device] = tuple(parse_interval(pair, deadline) for pair in windows)
            return parsed

        durations = object_of(body["durations"])
        start = parse_durations(durations["start"], installation.requirements)
        stop = parse_durations(durations["stop"], installation.requirements)
        mode = {}
        for device, values in object_of(durations["mode"]).items():
            mode[device] = parse_durations(values, hardware[device]["modes"])
        return cls(deadline, services, start, stop, mode, intervals("maintenance"),
                   intervals("switch_windows"))

    def span(self, kind, identity, mode=None):
        """Read the configured operation duration with its one-tick default."""
        if kind == "mode":
            return self.modes.get(identity, {}).get(mode, 1)
        table = self.starts if kind == "start" else self.stops
        return table.get(identity, 1)


def parse_service(alternatives, closures):
    """Expand every option into all the authoritative controllers it needs."""
    if not isinstance(alternatives, list) or not alternatives:
        raise ValueError("protected service must offer an option")
    choices = []
    for roots in alternatives:
        roots = names_of(roots)
        if not roots:
            raise ValueError("an option needs controllers")
        choices.append(frozenset().union(*(closures[root] for root in roots)))
    return tuple(choices)


def parse_interval(pair, deadline):
    """Read a half-open integer window within the declared observation horizon."""
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError("invalid interval")
    begin, end = (counter(number) for number in pair)
    if not begin < end <= deadline + 1:
        raise ValueError("invalid interval bounds")
    return begin, end


def parse_durations(raw, names):
    """Require positive operation durations for known configured names."""
    table = {key: counter(value, 1) for key, value in object_of(raw).items()}
    if not table.keys() <= names.keys():
        raise ValueError("unknown operation duration identity")
    return table


class Planner:
    """Search timed configurations while retaining at least one active guard chain."""

    def __init__(self, installation, constraints):
        self.graph = installation
        self.constraints = constraints
        self.device_ids = tuple(sorted(installation.devices))
        self.device_slot = {device: index for index, device in enumerate(self.device_ids)}
        options = [option for _, group in installation.groups for option in group]
        options.extend(option for service in constraints.protected for option in service)
        self.interesting = frozenset().union(installation.active, *options)
        self.modes_needed = defaultdict(set)
        for name in self.interesting:
            for claim in installation.claims[name]:
                self.modes_needed[claim.device].add(claim.mode)
        self.open_at = {
            name: tuple(
                installation.devices[name].ready
                and not any(start <= tick < end for start, end in constraints.maintenance.get(name, ()))
                for tick in range(constraints.deadline + 1)
            )
            for name in self.device_ids
        }

    @cache
    def device_set(self, active):
        """Read the devices currently owned by a set of controllers."""
        return frozenset(claim.device for name in active for claim in self.graph.claims[name])

    @cache
    def compatible(self, configuration):
        """Check active claims, dependency closures, modes and protected service roots."""
        active = configuration.active
        if any(not self.graph.closures[name] <= active for name in active):
            return False
        if not self.graph.compatible(active, frozenset()):
            return False
        for name in active:
            for claim in self.graph.claims[name]:
                if configuration.modes[self.device_slot[claim.device]] != claim.mode:
                    return False
        return all(any(option <= active for option in service) for service in self.constraints.protected)

    def safe(self, configuration, start, end):
        """Check a held state through all included tick boundaries."""
        return self.compatible(configuration) and all(
            all(self.open_at[device][start:end + 1]) for device in self.device_set(configuration.active)
        )

    def moves(self, configuration, tick):
        """Generate valid timed changes from an independently safe current state."""
        active, modes = configuration.active, configuration.modes
        deadline = self.constraints.deadline
        for name in sorted(active):
            end = tick + self.constraints.span("stop", name)
            next_state = Configuration(active - {name}, modes)
            if end <= deadline and self.safe(next_state, tick, end):
                yield end, next_state, {"kind": "stop", "controller": name, "start": tick, "end": end}
        for name in sorted(self.interesting - active):
            end = tick + self.constraints.span("start", name)
            next_state = Configuration(active | {name}, modes)
            if end <= deadline and self.safe(next_state, tick, end):
                yield end, next_state, {"kind": "start", "controller": name, "start": tick, "end": end}
        owners = self.device_set(active)
        for device in self.device_ids:
            if device in owners:
                continue
            slot = self.device_slot[device]
            for mode in sorted(self.modes_needed[device] - {modes[slot]}):
                end = tick + self.constraints.span("mode", device, mode)
                allowed = self.constraints.slots.get(device, [(0, deadline + 1)])
                if (end > deadline or not all(self.open_at[device][tick:end + 1])
                        or not any(start <= tick and end <= stop for start, stop in allowed)
                        or not self.safe(configuration, tick, end)):
                    continue
                next_state = Configuration(active, modes[:slot] + (mode,) + modes[slot + 1:])
                yield end, next_state, {"kind": "mode", "device": device, "mode": mode, "start": tick,
                                        "end": end, "generation": self.graph.devices[device].generation}

    def selection(self, configuration):
        """Compute the best active requested option and its ordered comparison score."""
        ranks = tuple(next((index for index, option in enumerate(group) if option <= configuration.active),
                           len(group)) for _, group in self.graph.groups)
        values = {name: index if index < len(group) else None
                  for (name, group), index in zip(self.graph.groups, ranks, strict=True)}
        score = (sum(value is not None for value in values.values()), tuple(-index for index in ranks))
        return score, values

    def solve(self):
        """Find the highest coverage attainable at the deadline after safe serial operations."""
        origin = Configuration(self.graph.active, tuple(self.graph.devices[i].mode for i in self.device_ids))
        layers = [{} for _ in range(self.constraints.deadline + 1)]
        if self.safe(origin, 0, 0):
            layers[0][origin] = ()
        for tick, layer in enumerate(layers[:-1]):
            for state, history in layer.items():
                if self.safe(state, tick, tick + 1):
                    layers[tick + 1].setdefault(state, history)
                for end, final, op in self.moves(state, tick):
                    layers[end].setdefault(final, (*history, op))
        reached = layers[-1]
        if not reached:
            return {"status": "blocked", "selected": {}, "operations": []}
        def ranking(configuration):
            score, _ = self.selection(configuration)
            return score, -len(reached[configuration])
        final = max(reached, key=ranking)
        _, selected = self.selection(final)
        return {"status": "scheduled", "selected": selected, "operations": list(reached[final])}


def schedule(spec, installation):
    """Plan the timed transfer using the already validated controller graph."""
    return Planner(installation, Handover.parse(spec, installation)).solve()
