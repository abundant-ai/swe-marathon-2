"""Load and validate paired robomimic demonstration recordings."""

from dataclasses import dataclass
from functools import cache
import json
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import h5py
import mujoco
import numpy as np


Json = dict[str, Any]
SIGNATURE = mujoco.mjtState.mjSTATE_FULLPHYSICS


def write(path: Path, value: Json) -> None:
    """Atomically publish one finite, deterministic JSON result."""
    data = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data)
            stream.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def as_text(value: object) -> str:
    """Read a UTF-8 attribute or named state field."""
    if isinstance(value, bytes):
        value = value.decode()
    if not isinstance(value, str) or not value:
        raise ValueError("Expected nonempty text")
    return value


def count(value: object, *, minimum: int = 0) -> int:
    """Read a real integer count from JSON or a native HDF5 attribute."""
    if type(value) is not int and not isinstance(value, np.integer) or value < minimum:
        raise ValueError("Invalid count")
    return int(value)


def finite(value: object) -> float:
    """Require a finite physical parameter."""
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("Invalid finite scalar")
    return float(value)


def array(value: object, shape: tuple[int, ...]) -> np.ndarray:
    """Read finite numeric data of an expected simulation shape."""
    result = np.asarray(value)
    if result.shape != shape or result.dtype.kind not in "iuf" or not np.isfinite(result).all():
        raise ValueError(f"Expected finite numeric array shaped {shape}")
    return result.astype(np.float64)


@cache
def parse_model(xml: str) -> mujoco.MjModel:
    """Load one pinned native simulation model from its embedded XML."""
    return mujoco.MjModel.from_xml_string(xml)


@dataclass(frozen=True)
class Controller:
    """Commissioned control timing, filter and geometric success threshold."""

    substeps: int
    delay: int
    alpha: float
    limits: list[float]
    joints: tuple[str, str]
    target: tuple[float, float]
    radius: float


@dataclass(frozen=True)
class Demo:
    """Native recording and reset state for one paired demonstration."""

    name: str
    pair: str
    role: str
    split: str
    xml: str
    states: np.ndarray
    actions: np.ndarray
    filtered: np.ndarray
    queue: np.ndarray

    @property
    def model(self) -> mujoco.MjModel:
        """Return the shared model used by this demonstration's fresh simulation."""
        return parse_model(self.xml)


@dataclass(frozen=True)
class Study:
    """A validated experimental dataset partitioned into complete pairs."""

    controls: Controller
    demos: dict[str, Demo]
    pairs: dict[str, dict[str, Demo]]


def joint_id(model: mujoco.MjModel, name: str) -> int:
    """Resolve a named slide joint to a valid native joint ID."""
    i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    if i < 0 or model.jnt_type[i] != mujoco.mjtJoint.mjJNT_SLIDE:
        raise ValueError(f"Unknown or unsupported joint {name}")
    return i


def controller(data: h5py.Group) -> Controller:
    """Read acquisition and goal settings from the stored robomimic environment definition."""
    env = json.loads(as_text(data.attrs["env_args"]))
    if env["env_name"] != "QualificationSlide-v1":
        raise ValueError("Unsupported evaluation environment")
    values = env["env_kwargs"]
    goal = values["goal"]
    joint_a, joint_b = map(as_text, goal["joints"])
    first, second = map(finite, goal["target"])
    limits = list(map(finite, values["action_limits"]))
    alpha, radius = finite(values["filter_alpha"]), finite(goal["radius"])
    if not limits or min(limits) <= 0 or not 0 < alpha <= 1 or radius <= 0 or joint_a == joint_b:
        raise ValueError("Invalid physical controls")
    return Controller(count(values["substeps"], minimum=1), count(values["delay"]), alpha,
                      limits, (joint_a, joint_b), (first, second), radius)


def read(path: Path) -> Study:
    """Validate all paired demos, masks, native model dimensions and reset conditions."""
    demos: dict[str, Demo] = {}
    pairs: dict[str, dict[str, Demo]] = {}
    with h5py.File(path, "r") as file:
        data = file["data"]
        controls = controller(data)
        membership = {}
        for split in ("train", "valid"):
            mask = file["mask"][split]
            if mask.ndim != 1:
                raise ValueError("Mask must be one-dimensional")
            for value in mask[()]:
                name = as_text(value)
                if name in membership or name not in data:
                    raise ValueError("Unknown or duplicated demonstration membership")
                membership[name] = split
        if not membership or set(membership) != set(data):
            raise ValueError("Exactly one split is required for every demonstration")
        for name in sorted(data):
            group = data[name]
            if not name.startswith("demo_") or not isinstance(group, h5py.Group):
                raise ValueError("Invalid demonstration")
            n = count(group.attrs["num_samples"], minimum=1)
            xml = as_text(group.attrs["model_file"])
            model = parse_model(xml)
            dims = mujoco.mj_stateSize(model, SIGNATURE)
            if dims <= 0 or model.nu != len(controls.limits):
                raise ValueError("Incompatible MuJoCo model")
            for joint in controls.joints:
                joint_id(model, joint)
            actions, states = array(group["actions"][()], (n, model.nu)), array(group["states"][()], (n, dims))
            initial = json.loads(as_text(group.attrs["controller_state"]))
            filtered = array(initial["filtered"], (model.nu,))
            raw_queue = initial["queue"]
            if controls.delay == 0 and raw_queue == []:
                raw_queue = np.zeros((0, model.nu))
            queue = array(raw_queue, (controls.delay, model.nu))
            pair, role = as_text(group.attrs["pair_id"]), as_text(group.attrs["role"])
            roles = pairs.setdefault(pair, {})
            if role not in ("success", "failure") or role in roles:
                raise ValueError("Invalid pair role")
            demo = Demo(name, pair, role, membership[name], xml, states, actions, filtered, queue)
            roles[role] = demos[name] = demo
    for roles in pairs.values():
        if len(roles) != 2:
            raise ValueError("Incomplete paired recordings")
        a, b = roles["success"], roles["failure"]
        if (a.split != b.split or a.xml != b.xml or not np.array_equal(a.states[0], b.states[0])
                or not np.array_equal(a.filtered, b.filtered) or not np.array_equal(a.queue, b.queue)):
            raise ValueError("Pair starts from different simulator or controller conditions")
    return Study(controls, demos, pairs)


def inspect(dataset: Path, output: Path) -> None:
    """Export trustworthy pair identities and demonstrator sample counts."""
    study = read(dataset)
    rows = []
    for pair, roles in sorted(study.pairs.items()):
        success, failure = roles["success"], roles["failure"]
        rows.append({"pair_id": pair, "split": success.split, "success_demo": success.name,
                     "failure_demo": failure.name, "success_samples": len(success.actions),
                     "failure_samples": len(failure.actions)})
    write(output, {"schema_version": 1, "pairs": rows})
