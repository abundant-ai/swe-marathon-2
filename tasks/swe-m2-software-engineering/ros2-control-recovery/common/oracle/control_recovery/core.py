"""Model exclusive command claims and plan one feedback-controlled operation."""

from collections import defaultdict
from dataclasses import dataclass


def object_of(value):
    """Require an object wherever the public format uses keyed records."""
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def name_of(value):
    """Read one nonempty wire identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError("empty or invalid identifier")
    return value


def names_of(value):
    """Read a list of unique identifiers."""
    if not isinstance(value, list):
        raise ValueError("expected a list of identifiers")
    names = [name_of(item) for item in value]
    if len(set(names)) != len(names):
        raise ValueError("duplicate identifier")
    return names


def counter(value, minimum=0):
    """Read an integral generation or sequence number."""
    if type(value) is not int or value < minimum:
        raise ValueError("invalid integer counter")
    return value


@dataclass(frozen=True)
class Readback:
    """One observed device generation, mode and lifecycle state."""

    generation: int
    mode: str
    ready: bool


@dataclass(frozen=True)
class Claim:
    """Exclusive command interfaces on one hardware device."""

    device: str
    mode: str
    interfaces: tuple[str, ...]


@dataclass(frozen=True)
class Installation:
    """Parsed commissioned graphs and observed active state."""

    requirements: dict
    claims: dict
    closures: dict
    devices: dict[str, Readback]
    active: frozenset[str]
    groups: list

    @classmethod
    def parse(cls, spec):
        hardware = {
            name_of(device): {name_of(mode): set(names_of(interfaces))
                              for mode, interfaces in object_of(record["modes"]).items()}
            for device, record in object_of(spec["hardware"]).items()
        }
        controllers = object_of(spec["controllers"])
        requirements, claims = {}, {}
        for controller, record in controllers.items():
            requirements[name_of(controller)] = names_of(record["requires"])
            claims[controller] = tuple(
                Claim(device, name_of(claim["mode"]), tuple(names_of(claim["interfaces"])))
                for device, claim in object_of(record["claims"]).items()
            )
            for claim in claims[controller]:
                if not set(claim.interfaces) <= hardware[claim.device][claim.mode]:
                    raise ValueError("controller claimed an uncommissioned interface")

        closures = dependency_closures(requirements)
        snapshot = object_of(spec["snapshot"])
        devices = {}
        for device, record in object_of(snapshot["devices"]).items():
            mode, state = name_of(record["mode"]), record["state"]
            if (mode != "unknown" and mode not in hardware[device]) or state not in ("ready", "fault"):
                raise ValueError("invalid observed hardware mode or state")
            devices[device] = Readback(counter(record["generation"]), mode, state == "ready")
        if devices.keys() != hardware.keys():
            raise ValueError("snapshot must cover the commissioned devices")
        active = frozenset(names_of(snapshot["active"]))
        if not active <= controllers.keys():
            raise ValueError("snapshot contains unknown controllers")

        raw_groups = spec["groups"]
        if not isinstance(raw_groups, list) or len(raw_groups) > 8:
            raise ValueError("invalid service group list")
        groups = []
        for group in raw_groups:
            name = name_of(group["id"])
            options = group["options"]
            if not isinstance(options, list) or len(options) > 4:
                raise ValueError("invalid option list")
            expanded = []
            for roots in options:
                names = names_of(roots)
                if not names:
                    raise ValueError("an option needs at least one controller")
                expanded.append(frozenset().union(*(closures[root] for root in names)))
            groups.append((name, expanded))
        names_of([name for name, _ in groups])
        return cls(requirements, claims, closures, devices, active, groups)

    def unsafe(self):
        """Find active controllers whose resources or transitive dependencies are unsafe."""
        owners = defaultdict(list)
        modes = defaultdict(set)
        clients = defaultdict(set)
        broken = set()
        for controller in self.active:
            for claim in self.claims[controller]:
                observed = self.devices[claim.device]
                if not observed.ready or observed.mode != claim.mode:
                    broken.add(controller)
                modes[claim.device].add(claim.mode)
                clients[claim.device].add(controller)
                for interface in claim.interfaces:
                    owners[claim.device, interface].append(controller)
        for owners_on_interface in owners.values():
            if len(owners_on_interface) > 1:
                broken.update(owners_on_interface)
        for device, values in modes.items():
            if len(values) > 1:
                broken.update(clients[device])
        return {controller for controller in self.active
                if not self.closures[controller] <= self.active or self.closures[controller] & broken}

    def compatible(self, controllers, forbidden):
        """Check whether the complete selected set fits the available devices."""
        owner = set()
        modes = {}
        for controller in controllers:
            for claim in self.claims[controller]:
                reading = self.devices[claim.device]
                if not reading.ready or (claim.device, reading.generation, claim.mode) in forbidden:
                    return False
                if modes.setdefault(claim.device, claim.mode) != claim.mode:
                    return False
                for name in claim.interfaces:
                    key = claim.device, name
                    if key in owner:
                        return False
                    owner.add(key)
        return True


def dependency_closures(requirements):
    """Build dependency closures in order and reject a cycle or missing reference."""
    closures = {}
    pending = set(requirements)
    while pending:
        ready = [name for name in pending if all(dep in closures for dep in requirements[name])]
        if not ready:
            raise ValueError("cyclic or unknown controller dependency")
        for name in ready:
            closures[name] = frozenset({name}).union(*(closures[dep] for dep in requirements[name]))
            pending.remove(name)
    return closures


def inspect(installation):
    """Classify all reported active controllers."""
    unsafe = installation.unsafe()
    return {"usable": sorted(installation.active - unsafe), "deactivate": sorted(unsafe)}


def choose(installation, forbidden):
    """Maximize service coverage, exploring equal-coverage choices in preference order."""
    groups = installation.groups
    best_count, best_choices, best_target = -1, (), frozenset()

    def search(index, controllers, choices, count):
        nonlocal best_count, best_choices, best_target
        if count + len(groups) - index <= best_count:
            return
        if index == len(groups):
            best_count, best_choices, best_target = count, choices, controllers
            return
        _, alternatives = groups[index]
        for rank, option in enumerate(alternatives):
            target = controllers | option
            if installation.compatible(target, forbidden):
                search(index + 1, target, (*choices, rank), count + 1)
        search(index + 1, controllers, (*choices, None), count)

    search(0, frozenset(), (), 0)
    return {group[0]: rank for group, rank in zip(groups, best_choices, strict=True)}, best_target


def next_primitive(installation, target):
    """Remove unsafe ownership, switch free devices, then activate dependencies first."""
    active = installation.active
    removed = (active - target) | installation.unsafe()
    for controller in sorted(removed):
        if not any(controller != other and controller in installation.closures[other] for other in active):
            return {"kind": "stop", "controller": controller}
    if removed:
        raise ValueError("unable to remove a blocked controller")

    for controller in sorted(target):
        for claim in installation.claims[controller]:
            device = installation.devices[claim.device]
            if device.mode != claim.mode:
                return {"kind": "mode", "device": claim.device, "mode": claim.mode,
                        "generation": device.generation}
    for controller in sorted(target - active):
        if all(parent in active for parent in installation.requirements[controller]):
            return {"kind": "start", "controller": controller}
    return None


def plan(installation, forbidden=frozenset()):
    """Select a service assignment and propose its next independently observable change."""
    selected, target = choose(installation, forbidden)
    return {"selected": selected, "command": next_primitive(installation, target)}
