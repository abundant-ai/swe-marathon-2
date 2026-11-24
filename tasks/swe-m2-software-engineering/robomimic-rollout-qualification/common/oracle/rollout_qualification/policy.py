"""Evaluate a frozen named-feature policy across held-out paired resets."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable

import mujoco
import numpy as np

from .dataset import Demo, Json, as_text, count, finite, joint_id, read, write
from .simulation import Simulation


@dataclass
class Frozen:
    """Compiled observations and affine weights in native actuator order."""

    observe: list[Callable[[], float]]
    weights: np.ndarray
    biases: np.ndarray

    def input(self) -> np.ndarray:
        """Recompute the ordered normalized observation vector."""
        return np.array([field() for field in self.observe])


def actuator(model: mujoco.MjModel, name: str) -> int:
    """Resolve a named actuator to its native index."""
    result = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
    if result < 0:
        raise ValueError(f"Unknown actuator {name}")
    return result


def observable(sim: Simulation, field: Json) -> Callable[[], float]:
    """Bind and normalize one live scalar requested by the frozen policy."""
    kind, name, mean, scale = field["kind"], as_text(field["name"]), finite(field["mean"]), finite(field["scale"])
    if scale <= 0:
        raise ValueError("Observation scale must be positive")
    if kind == "applied":
        index = actuator(sim.model, name)
        return lambda: (sim.filtered[index] - mean) / scale
    joint = joint_id(sim.model, name)
    position, velocity = sim.model.jnt_qposadr[joint], sim.model.jnt_dofadr[joint]
    if kind == "qpos":
        return lambda: (sim.data.qpos[position] - mean) / scale
    if kind == "qvel":
        return lambda: (sim.data.qvel[velocity] - mean) / scale
    if kind == "goal_error":
        goal = sim.config.target[sim.config.joints.index(name)]
        return lambda: (goal - sim.data.qpos[position] - mean) / scale
    raise ValueError("Unknown observation kind")


def policy(sim: Simulation, proposal: Json) -> Frozen:
    """Compile the ordered named observation and actuator contract."""
    observations = proposal["observations"]
    actions = proposal["actions"]
    if not isinstance(observations, list) or not observations or not isinstance(actions, dict) or len(actions) != sim.model.nu:
        raise ValueError("Incomplete frozen policy")
    reading = [observable(sim, field) for field in observations]
    weights = np.empty((sim.model.nu, len(reading)))
    biases = np.empty(sim.model.nu)
    for name, action in actions.items():
        i = actuator(sim.model, name)
        values = action["weights"]
        if not isinstance(values, list) or len(values) != len(reading):
            raise ValueError("Invalid weight dimension")
        weights[i] = list(map(finite, values))
        biases[i] = finite(action["bias"])
    return Frozen(reading, weights, biases)


def rollout(demo: Demo, sim: Simulation, frozen: Frozen, scenario: str, lag: int, horizon: int) -> Json:
    """Evaluate one closed-loop branch with sampled observation delay."""
    actions, applied, observations = [], [], []
    first = None
    for tick in range(horizon):
        observations.append(frozen.input())
        requested = frozen.weights @ observations[max(0, tick - lag)] + frozen.biases
        actions.append(requested.tolist())
        applied.append(sim.step(requested).tolist())
        if first is None and sim.success():
            first = tick + 1
    return {"pair_id": demo.pair, "scenario": scenario, "demo": demo.name, "recorded_role": demo.role,
            "goal_success": sim.success(), "first_goal_tick": first, "final_state": sim.state().tolist(),
            "actions": actions, "applied": applied}


def qualify(spec: Path, output: Path) -> None:
    """Qualify all selected paired branches and aggregate measured successes."""
    requested = json.loads(spec.read_text())
    local = Path(as_text(requested["dataset"]))
    horizon = count(requested["horizon"], minimum=1)
    split = requested["split"]
    scenarios = requested["scenarios"]
    if local.is_absolute() or split not in ("train", "valid") or not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Invalid qualification request")
    study = read(spec.parent / local)
    variants = {}
    for scenario in scenarios:
        name = as_text(scenario["id"])
        if name in variants:
            raise ValueError("Duplicate scenario")
        variants[name] = count(scenario["command_delay"]), count(scenario["observation_delay"])
    rows = []
    summary = {name: {"trials": 0, "successes": 0} for name in variants}
    selected = sorted((demo for demo in study.demos.values() if demo.split == split), key=lambda d: (d.pair, d.name))
    for pair in sorted({item.pair for item in selected}):
        for name, (delay, lag) in sorted(variants.items()):
            for demo in (item for item in selected if item.pair == pair):
                sim = Simulation(demo, study.controls, delay)
                result = rollout(demo, sim, policy(sim, requested), name, lag, horizon)
                rows.append(result)
                summary[name]["trials"] += 1
                summary[name]["successes"] += result["goal_success"]
    write(output, {"schema_version": 1, "rollouts": rows, "summary": summary})
