"""Make native HDF5 study fixtures and validate actual paired MuJoCo traces."""

from dataclasses import dataclass
import json
from math import fsum, hypot, isclose
from pathlib import Path
import shutil
from typing import Callable

import h5py
import mujoco
import numpy as np


SIGNATURE = mujoco.mjtState.mjSTATE_FULLPHYSICS
Run = Callable[..., int]


def dump(path: Path, payload: object) -> Path:
    """Write a trusted private scenario description."""
    path.write_text(json.dumps(payload) + "\n")
    return path


def result(path: Path) -> dict:
    """Read bounded JSON output without following a submitted symbolic link."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        return {}
    try:
        item = json.loads(path.read_text())
    except (OSError, ValueError, UnicodeError):
        return {}
    return item if isinstance(item, dict) else {}


def mjcf(reverse: bool, damping: float) -> str:
    """Build the private planar slide dynamics and intentionally reorder named motors."""
    motors = ['<motor name="sweep_y" joint="slide_y" gear="1.25"/>',
              '<motor name="sweep_x" joint="slide_x" gear="0.9"/>']
    if reverse:
        motors.reverse()
    return f"""<mujoco model="paired-slide">
      <option timestep="0.02" gravity="0 0 0"><flag warmstart="disable"/></option>
      <worldbody><body name="object">
        <joint name="slide_x" type="slide" axis="1 0 0" damping="{damping}"/>
        <joint name="slide_y" type="slide" axis="0 1 0" damping="{damping + 0.06}"/>
        <geom type="sphere" size="0.04" mass="0.75" rgba="0.7 0.2 0.1 1"/>
      </body></worldbody><actuator>{''.join(motors)}</actuator>
    </mujoco>"""


@dataclass(frozen=True)
class Episode:
    """Independently authored model and reset data shared by a trial."""

    pair: str
    demo: str
    role: str
    split: str
    model: mujoco.MjModel
    xml: str
    initial: tuple[float, float, float, float, float]
    initial_filter: tuple[float, float]
    pending: tuple[tuple[float, float], tuple[float, float]]


@dataclass
class Evaluator:
    """Independent fixture runner using direct Mujoco calls for measured truth."""

    episode: Episode
    env: dict
    delay: int

    def __post_init__(self) -> None:
        """Set physical and controller reset inputs before the first control command."""
        model = self.episode.model
        self.native = mujoco.MjData(model)
        self.native.time, *positions = self.episode.initial
        self.native.qpos[:] = positions[:2]
        self.native.qvel[:] = positions[2:]
        mujoco.mj_forward(model, self.native)
        self.signal = list(self.episode.initial_filter)
        self.initial_commands = ([[0.0, 0.0]] * max(0, self.delay - 2)
                                 + [list(item) for item in self.episode.pending][max(0, 2 - self.delay):])
        self.commands = []

    def measure(self) -> list[float]:
        """Capture the native full-physics state directly."""
        out = np.empty(mujoco.mj_stateSize(self.episode.model, SIGNATURE))
        mujoco.mj_getState(self.episode.model, self.native, out, SIGNATURE)
        return out.tolist()

    def move(self, action: list[float]) -> list[float]:
        """Measure the actuator signal and physics under the approved command."""
        limits = self.env["action_limits"]
        self.commands.append([sorted((-limit, value, limit))[1] for value, limit in zip(action, limits, strict=True)])
        step = len(self.commands) - 1
        delayed = self.initial_commands[step] if step < self.delay else self.commands[step - self.delay]
        self.signal = [previous + self.env["filter_alpha"] * (target - previous)
                       for previous, target in zip(self.signal, delayed, strict=True)]
        for axis, value in enumerate(self.signal):
            self.native.ctrl[axis] = value
        for _ in range(self.env["substeps"]):
            mujoco.mj_step(self.episode.model, self.native)
        return self.signal.copy()

    def success(self) -> bool:
        """Check the realized object motion against the study goal."""
        return hypot(*(float(p) - q for p, q in zip(self.native.qpos, self.env["goal"]["target"], strict=True))) <= self.env["goal"]["radius"]


def simple_demo(ep: Episode, env: dict, n: int) -> dict:
    """Author visibly different successful and unsuccessful recorded actions."""
    sim = Evaluator(ep, env, env["delay"])
    rows, commands = [], []
    signs = 1 if ep.role == "success" else -1
    by_motor = {ep.model.actuator(i).name: i for i in range(ep.model.nu)}
    for tick in range(n):
        x, y = sim.native.qpos
        dx, dy = sim.native.qvel
        gx, gy = env["goal"]["target"]
        request = [0.0, 0.0]
        request[by_motor["sweep_x"]] = signs * (5.0 * (gx - x) - 2.1 * dx)
        request[by_motor["sweep_y"]] = signs * (5.0 * (gy - y) - 2.1 * dy)
        before = sim.measure()
        applied = sim.move(request)
        commands.append(request)
        rows.append({"state_before": before, "applied": applied, "state_after": sim.measure()})
    return {"schema_version": 1, "demo": ep.demo, "first_divergence": None,
            "goal_success": sim.success(), "steps": rows, "final_state": sim.measure(), "_commands": commands}


def fixture(work: Path, variant: int) -> tuple[Path, dict, dict, dict]:
    """Create real MuJoCo paired recordings in a native robomimic HDF5 layout."""
    path = work / "demonstrations.hdf5"
    goal = [0.48 + variant * 0.02, -0.25 + variant * 0.035]
    env = {"substeps": 2, "delay": 2, "filter_alpha": 0.64, "action_limits": [0.82, 1.03],
           "goal": {"joints": ["slide_x", "slide_y"], "target": goal, "radius": 0.12}}
    demos = {}
    replays = {}
    pairs = [
        ("near", "train", ("demo_7", "demo_6"), (0.0, 0.26, -0.12, -0.01, 0.02)),
        ("test-bay", "valid", ("demo_41", "demo_5"), (0.34, 0.02, 0.03, 0.01, -0.02)),
        ("unseen-start", "valid", ("demo_19", "demo_11"), (0.65, -0.20, 0.20, 0.20, -0.10)),
    ]
    with h5py.File(path, "w") as file:
        data = file.create_group("data")
        data.attrs["env_args"] = json.dumps({"env_name": "QualificationSlide-v1", "type": 1, "env_kwargs": env})
        masks = file.create_group("mask")
        for split in ("train", "valid"):
            members = [name for _, group, roles, _ in pairs if group == split for name in roles]
            masks.create_dataset(split, data=np.array(members, dtype="S24"))
        for index, (pair, split, names, initial) in enumerate(pairs):
            xml = mjcf(bool((index + variant) % 2), 0.37 + index * 0.08)
            model = mujoco.MjModel.from_xml_string(xml)
            for role, name in zip(("success", "failure"), names, strict=True):
                episode = Episode(pair, name, role, split, model, xml, initial,
                                  (0.07 + index / 40, -0.06), ((0.17, -0.22), (-0.03, 0.31)))
                demos[name] = episode
                replay = simple_demo(episode, env, 58 + 2 * index if role == "success" else 33 + index)
                if replay["goal_success"] != (role == "success"):
                    raise RuntimeError("Invalid authored paired outcome")
                replays[name] = replay
                group = data.create_group(name)
                group.attrs["model_file"] = xml
                group.attrs["num_samples"] = len(replay["steps"])
                group.attrs["pair_id"] = pair
                group.attrs["role"] = role
                group.attrs["controller_state"] = json.dumps({"filtered": episode.initial_filter, "queue": episode.pending})
                group.create_dataset("states", data=np.array([row["state_before"] for row in replay["steps"]]))
                group.create_dataset("actions", data=np.array(replay["_commands"]))
    return path, env, demos, replays


def standard_policy(dataset: Path, variant: int) -> dict:
    """Construct frozen weights for a named, normalized observation contract."""
    observations = [
        {"kind": "applied", "name": "sweep_y", "mean": 0.13, "scale": 0.71},
        {"kind": "goal_error", "name": "slide_x", "mean": -0.07, "scale": 0.30},
        {"kind": "qvel", "name": "slide_y", "mean": 0.05, "scale": 1.21},
        {"kind": "qpos", "name": "slide_y", "mean": -0.09, "scale": 0.38},
        {"kind": "qvel", "name": "slide_x", "mean": 0.014, "scale": 0.71},
        {"kind": "goal_error", "name": "slide_y", "mean": 0.03, "scale": 0.32},
    ]
    return {"dataset": dataset.name, "split": "valid", "horizon": 32 + variant,
            "observations": observations, "actions": {
                "sweep_x": {"bias": 0.05, "weights": [0, 1.35, 0, 0, -1.22, 0.02]},
                "sweep_y": {"bias": -0.08, "weights": [0.16, -0.07, -2.1, 0.08, 0, 1.41]},
            }, "scenarios": [{"id": "nominal", "command_delay": 2, "observation_delay": 0},
                             {"id": "long-pipeline", "command_delay": 7, "observation_delay": 4},
                             {"id": "instant", "command_delay": 0, "observation_delay": 1}]}


def expected_qualification(demos: dict, env: dict, policy: dict) -> dict:
    """Run physically closed-loop independent trials without demonstration-tail leakage."""
    rows = []
    summary = {}
    for name in sorted(scenario["id"] for scenario in policy["scenarios"]):
        summary[name] = {"trials": 0, "successes": 0}
    for episode in sorted(demos.values(), key=lambda item: (item.pair, item.demo)):
        if episode.split != policy["split"]:
            continue
        for scenario in policy["scenarios"]:
            name = scenario["id"]
            sim = Evaluator(episode, env, scenario["command_delay"])
            actions, applied, saved = [], [], []
            first = None
            motor_ids = {episode.model.actuator(i).name: i for i in range(episode.model.nu)}
            joint_ids = {"slide_x": 0, "slide_y": 1}
            fields = policy["observations"]
            for step in range(policy["horizon"]):
                observed = []
                for field in fields:
                    spec = field["kind"]
                    if spec == "applied":
                        scalar = sim.signal[motor_ids[field["name"]]]
                    else:
                        index = joint_ids[field["name"]]
                        if spec == "qvel":
                            scalar = sim.native.qvel[index]
                        else:
                            q = sim.native.qpos[index]
                            scalar = q if spec == "qpos" else env["goal"]["target"][index] - q
                    observed.append((float(scalar) - field["mean"]) / field["scale"])
                saved.append(observed)
                selected = saved[max(0, step - scenario["observation_delay"])]
                action = [0.0] * episode.model.nu
                for key, weights in policy["actions"].items():
                    action[motor_ids[key]] = weights["bias"] + fsum(x * y for x, y in zip(weights["weights"], selected, strict=True))
                applied.append(sim.move(action))
                actions.append(action)
                if first is None and sim.success():
                    first = step + 1
            won = sim.success()
            rows.append({"pair_id": episode.pair, "scenario": name, "demo": episode.demo,
                         "recorded_role": episode.role, "goal_success": won, "first_goal_tick": first,
                         "final_state": sim.measure(), "actions": actions, "applied": applied})
            summary[name]["trials"] += 1
            summary[name]["successes"] += won
    return {"schema_version": 1, "rollouts": sorted(rows, key=lambda row: (row["pair_id"], row["scenario"], row["demo"])),
            "summary": summary}


def close(expected: object, actual: object) -> bool:
    """Compare structured results with independent physical numeric tolerances."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            close(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            close(a, b) for a, b in zip(expected, actual, strict=True))
    if isinstance(expected, float):
        return type(actual) in (float, int) and isclose(expected, actual, abs_tol=3e-8, rel_tol=1e-8)
    return type(actual) is type(expected) and actual == expected


def inspection(run: Run, work: Path, dataset: Path, demos: dict, replays: dict) -> dict:
    """Check native paired indexing and atomic refusal of a leaky split."""
    expected = {}
    for item in demos.values():
        row = expected.setdefault(item.pair, {"pair_id": item.pair, "split": item.split})
        row[item.role + "_demo"] = item.demo
        row[item.role + "_samples"] = len(replays[item.demo]["steps"])
    target = work / "inspection.json"
    inspected = run("inspect", "--dataset", dataset, "--output", target) == 0
    good = inspected and result(target) == {"schema_version": 1, "pairs": [row for _, row in sorted(expected.items())]}
    bad = work / "duplicate-mask.hdf5"
    shutil.copyfile(dataset, bad)
    with h5py.File(bad, "a") as file:
        file["mask/train"][0] = b"demo_41"
    prior = target.read_bytes() if good else b""
    unchanged = good and run("inspect", "--dataset", bad, "--output", target) not in (0, 124) and target.read_bytes() == prior
    return {"native_pair_index": good, "partition_rejection_atomic": unchanged}


def replay_probe(run: Run, work: Path, dataset: Path, captures: dict) -> dict:
    """Measure simulator traces for both labels and a planted state mismatch."""
    checks = {}
    target = work / "demo-replay.json"
    for name, role in (("demo_41", "successful"), ("demo_5", "failed")):
        expected = {key: value for key, value in captures[name].items() if key != "_commands"}
        good = run("replay", "--dataset", dataset, "--demo", name, "--output", target) == 0
        checks[role + "_actuation_replay"] = good and close(expected, result(target))
    divergent = work / "drifted-recording.hdf5"
    shutil.copyfile(dataset, divergent)
    with h5py.File(divergent, "a") as file:
        states = file["data/demo_41/states"]
        states[7, 1] += 0.06
    expected = {key: value for key, value in captures["demo_41"].items() if key != "_commands"}
    expected["first_divergence"] = 7
    checks["held_out_first_divergence"] = (
        run("replay", "--dataset", divergent, "--demo", "demo_41", "--output", target) == 0
        and close(expected, result(target)))
    return checks


def policy_probe(run: Run, work: Path, dataset: Path, env: dict, demos: dict, variant: int) -> dict:
    """Check observed policy traces under varied command delays and held-out resets."""
    policy = standard_policy(dataset, variant)
    supplied = dump(work / "frozen-policy.json", policy)
    output = work / "qualification.json"
    cli = ("qualify", "--spec", supplied, "--output", output)
    if run(*cli) != 0:
        return dict(closed_loop_trace=False, timing_success_metrics=False, rejects_bad_policy=False)
    expected = expected_qualification(demos, env, policy)
    actual = result(output)
    paired = actual.get("rollouts")
    complete = isinstance(paired, list) and expected["rollouts"] and len(paired) == len(expected["rollouts"])
    states = complete and all(
        isinstance(got, dict) and close({key: value for key, value in want.items() if key not in ["goal_success", "first_goal_tick"]},
                                       {key: value for key, value in got.items() if key not in ["goal_success", "first_goal_tick"]})
        for want, got in zip(expected["rollouts"], paired, strict=True))
    totals = complete and actual.get("schema_version") == 1 and close(expected, actual)
    before = output.read_bytes()
    policy["actions"]["sweep_y"]["weights"].pop()
    dump(supplied, policy)
    bad = run(*cli) not in (0, 124) and output.read_bytes() == before
    return {"closed_loop_trace": states, "timing_success_metrics": totals, "rejects_bad_policy": bad}


def verify(run: Run, work: Path, stage: int) -> dict[str, dict[str, bool]]:
    """Run original and changed model-order missions through cumulative commands."""
    source, env, demos, captures = fixture(work, 0)
    groups = {"inspect": inspection(run, work, source, demos, captures)}
    if stage >= 2:
        groups["replay"] = replay_probe(run, work, source, captures)
    if stage >= 3:
        groups["policy"] = policy_probe(run, work, source, env, demos, 0)
        alternate = work / "new-robot"
        alternate.mkdir(mode=0o777)
        alternate.chmod(0o1777)
        source, env, demos, _ = fixture(alternate, 1)
        groups["reordered"] = policy_probe(run, alternate, source, env, demos, 1)
    return groups
