"""Validate the export manifest and repair simulator coordinate conventions."""

from dataclasses import dataclass
from math import fsum, hypot, isfinite, tanh
from typing import Any

Record = dict[str, Any]


def number(value: object) -> float:
    """Accept only ordinary finite JSON numbers."""
    if type(value) not in (float, int) or not isfinite(value):
        raise ValueError("expected a finite number")
    return float(value)


def integer(value: object, minimum: int = 1) -> int:
    """Read an integer with a prescribed lower bound."""
    if type(value) is not int or value < minimum:
        raise ValueError("invalid integer")
    return value


def mapping(value: object) -> Record:
    """Require a JSON object."""
    if type(value) is not dict:
        raise ValueError("expected an object")
    return value


def vector(value: object, width: int) -> list[float]:
    """Read a fixed-width vector of finite components."""
    if type(value) is not list or len(value) != width:
        raise ValueError("vector width mismatch")
    return [number(item) for item in value]


def names(value: object) -> tuple[str, ...]:
    """Read a nonempty list of distinct nonempty identifiers."""
    if (type(value) is not list or not value
            or not all(type(item) is str and item for item in value)
            or len(set(value)) != len(value)):
        raise ValueError("expected distinct names")
    return tuple(value)


def positive(values: list[float]) -> None:
    """Validate scales that cannot be zero or negative."""
    if any(value <= 0 for value in values):
        raise ValueError("nonpositive scale")


def limit(x: float, lo: float, hi: float) -> float:
    """Clamp a value to a commissioned interval."""
    return min(hi, max(lo, x))


@dataclass(frozen=True)
class Joint:
    """One named training channel with conversion into simulator coordinates."""

    slot: int
    sign: int
    zero: float
    reference: float


@dataclass(frozen=True)
class Actuation:
    """An action coordinate and its position-actuator mapping."""

    slot: int
    scale: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class Layer:
    """Row-major weights and bias of one exported dense layer."""

    weights: tuple[list[float], ...]
    bias: list[float]
    activation: str


@dataclass(frozen=True)
class Contract:
    """A parsed observation layout and optional runnable actor."""

    all_joints: tuple[str, ...]
    orientation: str
    gyro: str
    observed: tuple[Joint, ...]
    commanded: tuple[Joint, ...]
    terms: tuple[str, ...]
    mean: list[float]
    std: list[float]
    clip: list[float]
    history: int
    actuators: tuple[Actuation, ...]
    neutral: list[float]
    layers: tuple[Layer, ...]
    action_clip: list[float]
    dt: int
    period: int
    watchdog: int | None


def parse(data: object, *, runnable: bool) -> Contract:
    """Validate names, references, complete observation shape and actor widths."""
    spec = mapping(data)
    model, obs = mapping(spec["model"]), mapping(spec["observation"])
    all_joints = names(model["joint_order"])
    orientation, gyro = model["quaternion"], model["angular_frame"]
    if orientation not in ("wxyz", "xyzw") or gyro not in ("body", "world"):
        raise ValueError("unknown orientation convention")
    joints = {}
    for name, raw in mapping(spec["joints"]).items():
        j = mapping(raw)
        sign = j["sign"]
        if not name or type(sign) is not int or sign not in (-1, 1):
            raise ValueError("invalid joint name or sign")
        joints[name] = Joint(all_joints.index(j["sensor"]), sign, number(j["zero"]), number(j["reference"]))
    if len({joint.slot for joint in joints.values()}) != len(joints):
        raise ValueError("duplicate sensor binding")
    observed = tuple(joints[name] for name in names(spec["observation_order"]))
    action_order = names(spec["action_order"])
    commanded = tuple(joints[name] for name in action_order)
    sizes = {"gravity": 3, "angular_velocity": 3, "command": 3,
             "joint_position": len(observed), "joint_velocity": len(observed), "last_action": len(commanded)}
    terms = names(obs["terms"])
    width = sum(sizes[key] for key in terms)
    mean, std, clip = (vector(obs[key], width) for key in ("mean", "std", "clip"))
    positive(std)
    positive(clip)
    history = integer(obs.get("history", 1))
    actuation: list[Actuation] = []
    layers: list[Layer] = []
    neutral, action_clip = [], []
    dt = period = 1
    watchdog = None
    if runnable:
        history = integer(obs["history"])
        channels = names(model["actuator_order"])
        neutral = vector(model["neutral"], len(channels))
        actions = mapping(spec["actions"])
        if set(actions) != set(action_order):
            raise ValueError("missing or extra action mappings")
        for name in action_order:
            entry = mapping(actions[name])
            lo, hi = number(entry["minimum"]), number(entry["maximum"])
            if lo > hi:
                raise ValueError("reversed action limits")
            actuation.append(Actuation(channels.index(entry["actuator"]), number(entry["scale"]), lo, hi))
        if len({item.slot for item in actuation}) != len(actuation):
            raise ValueError("duplicate actuator binding")
        actor = mapping(spec["policy"])
        action_clip = vector(actor["action_clip"], len(commanded))
        positive(action_clip)
        current_width = width * history
        for layer in actor["layers"]:
            layer = mapping(layer)
            rows = tuple(vector(row, current_width) for row in layer["weights"])
            kind = layer["activation"]
            if not rows or kind not in ("linear", "relu", "tanh"):
                raise ValueError("invalid dense layer")
            current_width = len(rows)
            layers.append(Layer(rows, vector(layer["bias"], current_width), kind))
        if not layers or current_width != len(commanded):
            raise ValueError("final policy width mismatch")
        dt, period = integer(spec["physics_dt_ns"]), integer(spec["policy_period_ticks"])
        if "watchdog_ticks" in spec:
            watchdog = integer(spec["watchdog_ticks"])
    return Contract(all_joints, orientation, gyro, observed, commanded, terms, mean, std, clip, history,
                    tuple(actuation), neutral, tuple(layers), action_clip, dt, period, watchdog)


def body_vector(q: list[float], v: list[float]) -> list[float]:
    """Rotate a world vector into body by conjugating its unit quaternion."""
    w, x, y, z = q
    a, b, c = v
    cross = [y * c - z * b, z * a - x * c, x * b - y * a]
    i, j, k = cross
    double = [y * k - z * j, z * i - x * k, x * j - y * i]
    return [p - 2 * w * s + 2 * t for p, s, t in zip(v, cross, double, strict=True)]


def frame(contract: Contract, sample: Record, last: list[float]) -> list[float]:
    """Read a sensor packet and build the exact standardized training frame."""
    width = len(contract.all_joints)
    qpos = vector(sample["position"], width)
    qvel = vector(sample["velocity"], width)
    quat = vector(sample["orientation"], 4)
    if contract.orientation == "xyzw":
        quat = [quat[3], *quat[:3]]
    scale = max(map(abs, quat))
    if scale == 0:
        raise ValueError("zero quaternion")
    quat = [part / scale for part in quat]
    length = hypot(*quat)
    quat = [part / length for part in quat]
    gyro = vector(sample["angular_velocity"], 3)
    parts = {
        "gravity": body_vector(quat, [0.0, 0.0, -1.0]),
        "angular_velocity": body_vector(quat, gyro) if contract.gyro == "world" else gyro,
        "command": vector(sample["command"], 3),
        "joint_position": [j.sign * (qpos[j.slot] - j.zero) - j.reference for j in contract.observed],
        "joint_velocity": [j.sign * qvel[j.slot] for j in contract.observed],
        "last_action": vector(last, len(contract.commanded)),
    }
    raw = [v for term in contract.terms for v in parts[term]]
    return [limit(number((value - mean) / std), -clip, clip)
            for value, mean, std, clip in zip(raw, contract.mean, contract.std, contract.clip, strict=True)]


def execute(contract: Contract, features: list[float]) -> tuple[list[float], list[float], list[float]]:
    """Run the frozen actor and project its canonical targets onto named actuators."""
    output = features
    for layer in contract.layers:
        output = [number(fsum(a * b for a, b in zip(row, output, strict=True)) + bias)
                  for row, bias in zip(layer.weights, layer.bias, strict=True)]
        if layer.activation == "relu":
            output = [max(0.0, x) for x in output]
        elif layer.activation == "tanh":
            output = [tanh(x) for x in output]
    action = [limit(x, -clip, clip) for x, clip in zip(output, contract.action_clip, strict=True)]
    control = contract.neutral.copy()
    targets = []
    for x, j, a in zip(action, contract.commanded, contract.actuators, strict=True):
        goal = limit(j.reference + a.scale * x, a.minimum, a.maximum)
        targets.append(goal)
        control[a.slot] = number(j.zero + j.sign * goal)
    return action, targets, control
