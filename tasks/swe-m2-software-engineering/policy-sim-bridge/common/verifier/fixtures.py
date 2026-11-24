"""Authored actor exports and independently generated canonical sensor data."""

from dataclasses import dataclass
from math import cos, sin
from random import Random
from typing import Any

import numpy as np

Record = dict[str, Any]
JOINTS = ("left-outer", "left-inner", "right-outer", "right-inner",
          "rear-outer", "rear-inner", "tool-pitch", "tool-roll")


@dataclass(frozen=True)
class Physical:
    """Sensor truth in named training joint and body coordinates."""

    q: dict[str, float]
    dq: dict[str, float]
    quaternion: list[float]
    body_gyro: list[float]
    command: list[float]


def matrix(q: list[float]) -> Any:
    """Convert a quaternion into a body-to-world matrix for synthetic telemetry."""
    w, x, y, z = np.asarray(q, dtype=float) / np.linalg.norm(q)
    return np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - w*z), 2 * (x*z + w*y)],
        [2 * (x*y + w*z), 1 - 2 * (x*x + z*z), 2 * (y*z - w*x)],
        [2 * (x*z - w*y), 2 * (y*z + w*x), 1 - 2 * (x*x + y*y)],
    ])


def shuffled(rng: Random, names: list[str]) -> list[str]:
    """Permute labels without modifying caller input."""
    return rng.sample(names, len(names))


def manifest(seed: int, layout: int, *, count: int = 6, history: int = 3,
             dt: int = 5_000_000, period: int = 4) -> Record:
    """Build a frozen actor, metadata and one independently permuted export bus."""
    training, backend = Random(seed), Random(seed * 41 + layout * 397)
    keys = list(JOINTS[:count])
    observe_order, action_order = shuffled(training, keys), shuffled(training, keys)
    bindings = {
        name: {"sensor": f"move-{layout}-{backend.randrange(1000000):06d}",
               "zero": backend.uniform(-0.28, 0.29), "sign": -1 if (i + layout) % 3 else 1,
               "reference": training.uniform(-0.22, 0.26)}
        for i, name in enumerate(keys)
    }
    actuator = {name: f"set-{layout}-{backend.randrange(1000000):06d}" for name in keys}
    drive_order = shuffled(backend, list(actuator.values()) + [f"unused-{layout}"])
    neutral = [backend.uniform(-0.16, 0.12) for _ in drive_order]
    terms = shuffled(training, ["gravity", "angular_velocity", "command",
                                  "joint_position", "joint_velocity", "last_action"])
    width = 9 + 3 * count
    mean = [training.uniform(-0.23, 0.31) for _ in range(width)]
    std = [training.uniform(0.53, 1.7) for _ in range(width)]
    clip = [training.uniform(0.52, 1.6) for _ in range(width)]
    sizes = (width * history, 11, 7, count)
    layers = [
        {"weights": [[training.uniform(-bound, bound) for _ in range(a)] for _ in range(b)],
         "bias": [training.uniform(-0.62, 0.67) for _ in range(b)], "activation": activation}
        for a, b, bound, activation in zip(sizes, sizes[1:], (0.20, 0.37, 0.52),
                                          ("tanh", "relu", "linear"))
    ]
    return {
        "model": {
            "joint_order": shuffled(backend, [j["sensor"] for j in bindings.values()] + [f"passive-{layout}"]),
            "actuator_order": drive_order, "neutral": neutral,
            "quaternion": "xyzw" if layout % 2 else "wxyz",
            "angular_frame": "body" if layout % 2 else "world",
        },
        "joints": bindings, "observation_order": observe_order, "action_order": action_order,
        "observation": {"terms": terms, "mean": mean, "std": std, "clip": clip, "history": history},
        "policy": {"layers": layers, "action_clip": [training.uniform(0.23, 0.61) for _ in keys]},
        "actions": {
            name: {"actuator": actuator[name], "scale": training.uniform(0.14, 0.47),
                   "minimum": bindings[name]["reference"] - 0.22 + 0.012 * i,
                   "maximum": bindings[name]["reference"] + 0.21 - 0.013 * i}
            for i, name in enumerate(keys)
        },
        "physics_dt_ns": dt, "policy_period_ticks": period, "watchdog_ticks": period + 3,
    }


def physical(spec: Record, sample: float, shift: float = 0.0) -> Physical:
    """Describe a varying held-out multi-axis motion and command trace."""
    keys = list(spec["joints"])
    return Physical(
        {key: 0.18 * sin(0.37 * sample + 0.21 * i) - 0.16 * cos(1.17 * i) + shift
         for i, key in enumerate(keys)},
        {key: 0.43 * cos(0.29 * sample + i * 0.41) + 0.07 * i for i, key in enumerate(keys)},
        [0.91, 0.25 + 0.03 * sin(sample), -0.31, 0.22 + 0.04 * cos(sample)],
        [0.42 + 0.13 * cos(sample), -0.37 + 0.06 * sin(sample / 2), 0.25],
        [0.68 * sin(0.18 * sample), -0.49 * cos(0.14 * sample), 0.37 * sin(0.3 + sample)],
    )


def export(spec: Record, truth: Physical, tick: int, *, sign_flip: bool = False) -> Record:
    """Create a backend packet by applying sensor calibration to physical state."""
    model = spec["model"]
    qpos, qvel = dict.fromkeys(model["joint_order"], 1.29), dict.fromkeys(model["joint_order"], -1.71)
    for name, source in spec["joints"].items():
        qpos[source["sensor"]] = source["zero"] + source["sign"] * truth.q[name]
        qvel[source["sensor"]] = source["sign"] * truth.dq[name]
    quat = list(truth.quaternion)
    if model["quaternion"] == "xyzw":
        quat = quat[1:] + quat[:1]
    scale = -2.2 if sign_flip else 1.7
    gyro = truth.body_gyro if model["angular_frame"] == "body" else list(matrix(truth.quaternion) @ truth.body_gyro)
    return {"kind": "step", "tick": tick, "orientation": [scale * x for x in quat],
            "position": list(qpos.values()), "velocity": list(qvel.values()),
            "angular_velocity": gyro, "command": truth.command.copy()}


def standard_frame(spec: Record, inputs: Physical, last: list[float]) -> list[float]:
    """Derive normalized features directly from physical truth, bypassing export mapping."""
    order = spec["observation_order"]
    terms = {
        "gravity": list(-matrix(inputs.quaternion)[2, :]),
        "angular_velocity": inputs.body_gyro,
        "command": inputs.command,
        "joint_position": [inputs.q[name] - spec["joints"][name]["reference"] for name in order],
        "joint_velocity": [inputs.dq[name] for name in order],
        "last_action": last,
    }
    config = spec["observation"]
    values = [x for label in config["terms"] for x in terms[label]]
    standardized = (np.asarray(values) - config["mean"]) / config["std"]
    return list(np.clip(standardized, -np.asarray(config["clip"]), config["clip"]))


class TruthPolicy:
    """Compute expected evaluations in canonical coordinates and independent NumPy math."""

    def __init__(self, spec: Record) -> None:
        """Initialize an all-zero observation history and neutral bus."""
        self.spec = spec
        obs = spec["observation"]
        self.frames = [np.zeros(len(obs["mean"])) for _ in range(obs["history"])]
        self.last = [0.0] * len(spec["action_order"])
        self.bus = spec["model"]["neutral"].copy()

    def quiet(self, status: str) -> Record:
        """Compute neutral or held output with absent policy diagnostics."""
        active = self.bus if status == "held" else self.spec["model"]["neutral"]
        return {"status": status, "control": active.copy(), "observation": None, "action": None, "target": None}

    def evaluate(self, inputs: Physical) -> Record:
        """Run an independent dense tensor expression and direct named bus assignment."""
        spec, policy = self.spec, self.spec["policy"]
        self.frames.pop(0)
        self.frames.append(standard_frame(spec, inputs, self.last))
        stack = np.concatenate(self.frames)
        vector = stack
        for layer in policy["layers"]:
            vector = np.asarray(layer["weights"]) @ vector + layer["bias"]
            if layer["activation"] == "tanh":
                vector = np.tanh(vector)
            elif layer["activation"] == "relu":
                vector = np.maximum(vector, 0)
        caps = np.asarray(policy["action_clip"])
        self.last = list(np.clip(vector, -caps, caps))
        planned = {}
        targets = []
        for key, value in zip(spec["action_order"], self.last, strict=True):
            joint, drive = spec["joints"][key], spec["actions"][key]
            target = float(np.clip(joint["reference"] + drive["scale"] * value, drive["minimum"], drive["maximum"]))
            targets.append(target)
            planned[drive["actuator"]] = joint["zero"] + joint["sign"] * target
        self.bus = [planned.get(name, neutral)
                    for name, neutral in zip(spec["model"]["actuator_order"], spec["model"]["neutral"])]
        return {"status": "updated", "control": self.bus.copy(), "observation": list(stack),
                "action": self.last.copy(), "target": targets}
