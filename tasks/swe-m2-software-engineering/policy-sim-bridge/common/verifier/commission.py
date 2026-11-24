"""Independent calibration cases and measured native closed-loop qualification."""

from copy import deepcopy
from math import cos, sin
from pathlib import Path

import mujoco
import numpy as np

from fixtures import JOINTS, Record, TruthPolicy, export, manifest
from native import drive, model, pose
from probes import verify
from transport import Stream, batch, dump, require, writable


def rig_capture(world: mujoco.MjModel, names: list[str], actions: list[str],
                start: int, drive_shift: float) -> dict[str, np.ndarray]:
    """Measure a deliberately independent articulated excitation in native MuJoCo."""
    data = mujoco.MjData(world)
    data.qpos[:] = [0.31 * cos(0.7 * i + drive_shift) for i in range(world.nq)]
    data.qvel[:] = [0.42 * sin(1.1 * i - drive_shift) for i in range(world.nv)]
    mujoco.mj_forward(world, data)
    qs, velocities, controls = [], [], []
    for tick in range(163):
        elapsed = tick * 0.005
        u = {name: (0.36 * sin((3.4 + 0.71 * i) * elapsed + 0.59 * i + drive_shift)
                    + 0.12 * cos((6.1 + i * 0.28) * elapsed - 0.5 * i + drive_shift))
             for i, name in enumerate(JOINTS)}
        for name, target in u.items():
            data.ctrl[world.actuator(f"servo-{name}").id] = target
        qs.append([data.qpos[world.joint(name).qposadr[0]] for name in names])
        velocities.append([data.qvel[world.joint(name).dofadr[0]] for name in names])
        controls.append([u[name] for name in actions])
        mujoco.mj_step(world, data)
    return {"time_ns": np.arange(len(qs)) * 5_000_000 + start,
            "position": np.array(qs), "velocity": np.array(velocities), "control": np.array(controls)}


def capture(exported: Record, measured: dict[str, np.ndarray],
            raw_times: np.ndarray, fitted_times: np.ndarray) -> Record:
    """Resample measured rig truth onto target timestamps, then permute independent buses."""
    model_bus = exported["model"]
    names, actions = list(exported["joints"]), exported["action_order"]
    known_mask = np.column_stack([np.interp(fitted_times, measured["time_ns"], values)
                                  for field in ("position", "velocity", "control")
                                  for values in measured[field].T])
    target = []
    for i, (stamp, values) in enumerate(zip(raw_times, known_mask, strict=True)):
        n, a = len(names), len(actions)
        angle, speed, command = values[:n], values[n:2*n], values[2*n:2*n+a]
        q = dict.fromkeys(model_bus["joint_order"], 0.47 * cos(i * 0.07) - 0.32)
        dq = dict.fromkeys(model_bus["joint_order"], -0.05 + 0.15 * sin(i * 0.18))
        ctrl = dict.fromkeys(model_bus["actuator_order"], 0.62 - 0.04 * i)
        for name, x, v in zip(names, angle, speed, strict=True):
            mapping = exported["joints"][name]
            q[mapping["sensor"]] = mapping["sign"] * x + mapping["zero"]
            dq[mapping["sensor"]] = mapping["sign"] * v
        for name, target_position in zip(actions, command, strict=True):
            mapping = exported["joints"][name]
            ctrl[exported["actions"][name]["actuator"]] = mapping["sign"] * target_position + mapping["zero"]
        target.append({"time_ns": int(stamp), "position": list(q.values()),
                       "velocity": list(dq.values()), "control": list(ctrl.values())})
    reference = [{"time_ns": int(stamp), **{field: values[i].tolist() for field, values in measured.items()
                                         if field != "time_ns"}}
                 for i, stamp in enumerate(measured["time_ns"])]
    return {"reference": reference, "target": target}


def commissioning(seed: int, count: int, condition: str) -> tuple[Record, Record, Record]:
    """Construct two separate excitation sessions and one known target convention."""
    candidate = manifest(seed, seed % 6 + 1, count=count, history=3, period=3)
    # One state-only joint demonstrates independent sensor and actuator identities.
    if condition != "deploy":
        candidate["action_order"] = candidate["action_order"][:-1]
    names, actions = list(candidate["joints"]), candidate["action_order"]
    train_model = model()
    fit_start, check_start = 39_000_000_000, 45_000_000_000
    fit, validation = (rig_capture(train_model, names, actions, at, phase)
                       for at, phase in ((fit_start, 0.17), (check_start, 1.12)))
    rate = 1400 if seed % 2 == 0 else -1800
    offset = -11_000_000 if seed % 3 else 8_000_000

    def resample(truth: dict[str, np.ndarray], start: int) -> Record:
        """Use independently staggered sample times and an actually drifting device clock."""
        stamps = np.array([start + 35_000_000 + i * 13_000_000 + i % 5 * 820_000 for i in range(49)])
        # Division of signed Python integers rounds toward minus infinity, including at the negative rate.
        time = stamps + offset + np.floor_divide((stamps - fit_start) * rate, 1_000_000)
        return capture(candidate, truth, stamps, time)

    spec = {
        "joint_names": names, "action_order": actions,
        "sensor_order": candidate["model"]["joint_order"], "actuator_order": candidate["model"]["actuator_order"],
        "clock": {"anchor_ns": fit_start, "offsets_ns": [8_000_000, -11_000_000, 0, -3_000_000],
                  "rates_ppm": [1400, -1800, 0], "max_gap_ns": 7_000_000},
        "limits": {"min_pairs": 26, "min_coverage": 0.9, "velocity_weight_s": 0.075,
                   "ambiguity": 2e-12, "max_position_rmse": 0.014,
                   "max_velocity_rmse": 0.025, "max_control_rmse": 0.010},
        "fit": resample(fit, fit_start), "validation": resample(validation, check_start),
    }
    exact = {
        "clock": {"offset_ns": offset, "rate_ppm": rate},
        "mapping": {name: {"sensor": mapping["sensor"], "sign": mapping["sign"], "zero": mapping["zero"],
                           "actuator": candidate["actions"][name]["actuator"] if name in actions else None}
                    for name, mapping in candidate["joints"].items()},
        "validation_pairs": len(spec["validation"]["target"]),
    }
    if condition == "duplicate-sensor":
        first = spec["sensor_order"].index(candidate["joints"][names[0]]["sensor"])
        duplicate = next(i for i, name in enumerate(spec["sensor_order"]) if name.startswith("passive-"))
        for reading in spec["fit"]["target"]:
            reading["position"][duplicate] = reading["position"][first] + 0.037
            reading["velocity"][duplicate] = reading["velocity"][first]
    elif condition == "duplicate-drive":
        first = spec["actuator_order"].index(candidate["actions"][actions[0]]["actuator"])
        duplicate = next(i for i, name in enumerate(spec["actuator_order"]) if name.startswith("unused-"))
        for reading in spec["fit"]["target"]:
            reading["control"][duplicate] = reading["control"][first]
    elif condition == "wrong-holdout":
        slot = spec["sensor_order"].index(candidate["joints"][names[0]]["sensor"])
        for reading in spec["validation"]["target"]:
            reading["position"][slot] += 0.16
    elif condition == "missing-fit":
        for reading in spec["fit"]["target"]:
            reading["time_ns"] += 5_000_000_000
    elif condition == "missing-holdout":
        for reading in spec["validation"]["target"]:
            reading["time_ns"] += 9_000_000_000
    return spec, candidate, exact


def check_map(actual: Record, exact: Record) -> None:
    """Check physically planted identities, clock and sign without fitting another model."""
    require(actual.get("clock") == exact["clock"], "wrong independently known clock grid coordinates")
    actual_map = actual.get("mapping")
    require(isinstance(actual_map, dict) and actual_map.keys() == exact["mapping"].keys(),
            "wrong canonical calibration channels")
    for joint, expected in exact["mapping"].items():
        found = actual_map[joint]
        require(all(found.get(k) == expected[k] for k in ("sensor", "sign", "actuator")),
                f"wrong independently planted sensor, sign or drive for {joint}")
        require(type(found.get("zero")) in (int, float) and abs(found["zero"] - expected["zero"]) <= 1e-8,
                f"wrong measured zero for {joint}")


def calibration_case(app: Path, root: Path, seed: int, count: int, condition: str) -> Record:
    """Verify fit status, separable causes and physically meaningful holdout metrics."""
    spec, _, exact = commissioning(seed, count, condition)
    spec_path = dump(root / "commission.json", spec)
    output = writable(root / "out") / "calibration.json"
    result = batch(app, ["calibrate", "--spec", str(spec_path)], output)
    status = {"missing-fit": "insufficient_overlap", "missing-holdout": "validation_failed",
              "wrong-holdout": "validation_failed", "duplicate-drive": "ambiguous",
              "duplicate-sensor": "ambiguous"}.get(condition, "ok")
    require(result.get("status") == status, f"expected calibration {status}, got {result.get('status')}")
    if status in ("ambiguous", "insufficient_overlap"):
        require(result.get("validation_pairs") == 0 and all(k in result and result[k] is None for k in ("clock", "mapping", "metrics")),
                "an unresolved fit leaked a purported usable map")
    else:
        check_map(result, exact)
        count_expected = 0 if condition == "missing-holdout" else exact["validation_pairs"]
        require(result.get("validation_pairs") == count_expected, "wrong independent holdout overlap count")
        metrics = result.get("metrics")
        if count_expected == 0:
            require(metrics is None, "zero overlap must have null holdout metrics")
        else:
            expected = 0.16 / (count ** 0.5) if condition == "wrong-holdout" else 0.0
            ideal = {"position_rmse": expected, "velocity_rmse": 0.0, "control_rmse": 0.0}
            require(isinstance(metrics, dict) and all(type(metrics.get(key)) in (int, float)
                    and abs(metrics[key] - value) < 1e-8 for key, value in ideal.items()),
                    "holdout RMSEs do not match its independently planted error")
    return {"status": status, "canonical_joints": count, "qualified_pairs": result["validation_pairs"]}


def deployment_template(metadata: Record) -> Record:
    """Prepare the deployment manifest with bad placeholder bindings, but correct actor semantics."""
    draft = deepcopy(metadata)
    bindings = list(draft["joints"].values())
    lost = [entry["sensor"] for entry in bindings]
    act = list(draft["actions"].values())
    old = [entry["actuator"] for entry in act]
    for i, entry in enumerate(bindings):
        entry.update(sensor=lost[(i + 1) % len(lost)], sign=1, zero=0.0)
    for i, entry in enumerate(act):
        entry["actuator"] = old[(i + 2) % len(old)]
    return draft


def commissioned_rollout(app: Path, root: Path, seed: int, mass: float, damping: float,
                        fault: bool = False) -> Record:
    """Into a different-rig native plant apply actual controls inferred from commissioning."""
    spec, target_layout, expected_calibration = commissioning(seed, 6, "deploy")
    out = writable(root / "output")
    cal_path = out / "calibration.json"
    result = batch(app, ["calibrate", "--spec", str(dump(root / "recording.json", spec))], cal_path)
    require(result.get("status") == "ok", "failed to qualify the training-capture map before live actuation")
    check_map(result, expected_calibration)

    plant = model(mass_scale=mass, damping_scale=damping)
    actual, shadow = (mujoco.MjData(plant) for _ in range(2))
    for data in (actual, shadow):
        data.qpos[:] = np.linspace(-0.16, 0.31, num=plant.nq)
        data.qvel[:] = np.linspace(0.21, -0.13, num=plant.nv)
        mujoco.mj_forward(plant, data)
    start = shadow.qpos.copy()
    actor = TruthPolicy(target_layout)
    origin = 0
    updates = 0
    peak = 0.0
    with Stream(app, root / "actuator-stream", deployment_template(target_layout), calibration=cal_path) as stream:
        for tick in range(51):
            held = fault and 16 <= tick < 20
            arm = fault and tick == 20
            if arm:
                packet = {"kind": "arm", "tick": tick}
                control = actor.quiet("armed")
                actor = TruthPolicy(target_layout)
                origin = tick
            elif held:
                packet = {"kind": "step", "healthy": False, "tick": tick}
                control = actor.quiet("latched")
            else:
                packet = export(target_layout, pose(plant, actual, tick), tick, sign_flip=(tick % 2 == 1))
                if (tick - origin) % target_layout["policy_period_ticks"] == 0:
                    control = actor.evaluate(pose(plant, shadow, tick))
                    updates += 1
                else:
                    control = actor.quiet("held")
            received = stream.push(packet)
            verify(received, control)
            if fault and tick in (11, 17, 24):
                stream.restart()
                require(stream.push(packet) == received, "commissioned deployment lost a committed decision")
            drive(plant, actual, target_layout, received["control"])
            drive(plant, shadow, target_layout, control["control"])
            peak = max(peak, float(np.max(np.abs(actual.qpos - shadow.qpos))))
    motion = float(np.linalg.norm(shadow.qpos - start))
    require(motion > 0.12 and peak < 2e-8, "native deployment did not match its independent articulated shadow")
    return {"updates": updates, "peak_position_error_rad": peak, "motion_rad_l2": motion,
            "target_mass_scale": mass, "target_damping_scale": damping, "injected_restart": fault}
