"""Recover training labels from correlated drive writes and independent readback."""

from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


INTEGRATION = mujoco.mjtState.mjSTATE_INTEGRATION


@dataclass(frozen=True)
class Write:
    identifier: str
    controller: str
    target: tuple[float, ...]
    dispatch: int
    interpolation: str


def ordered_target(values, joints, canonical):
    """Read a complete actuator vector by name."""
    if len(values) != len(joints) or len(set(joints)) != len(canonical) or set(joints) != set(canonical):
        raise ValueError("Expected exactly the commissioned six joints")
    table = dict(zip(joints, values, strict=True))
    ordered = [float(table[name]) for name in canonical]
    if not np.isfinite(ordered).all():
        raise ValueError("A commanded value is not finite")
    return ordered


def writes(rows, canonical, calibrations, stride):
    """Normalize controller-specific action conventions before evaluating physics."""
    result = []
    for row in rows:
        transform = calibrations[row["calibration"]]
        values = ordered_target(row["target"], transform["joints"], canonical)
        values = np.asarray(values) * np.asarray(transform["scale_to_rad"]) + np.asarray(transform["offset_rad"])
        if not np.isfinite(values).all():
            raise ValueError("A canonical target is not finite")
        dispatch = row.get("dispatch_substep", 0)
        interpolation = row.get("interpolation", "step")
        if type(dispatch) is not int or not 0 <= dispatch < stride or interpolation not in ("step", "linear"):
            raise ValueError("Invalid write dispatch or interpolation")
        result.append(Write(row["receipt"], row["controller"], tuple(values), dispatch, interpolation))
    if not result or len({row.identifier for row in result}) != len(result):
        raise ValueError("Each command window needs distinct receipt identities")
    return result


def native_clone(model, data):
    """Keep the full native integration state needed to branch before contact."""
    result = np.empty(mujoco.mj_stateSize(model, INTEGRATION))
    mujoco.mj_getState(model, data, result, INTEGRATION)
    return result


def witnessed(data, sample, position_bound, rate_bound):
    """Assess only the present encoder fields, at their recorded capture."""
    for channel, value in enumerate(sample["position_rad"]):
        if value is not None and abs(value - data.qpos[channel]) > position_bound:
            return False
    for channel, value in enumerate(sample["velocity_rad_s"]):
        if value is not None and abs(value - data.qvel[channel]) > rate_bound:
            return False
    return True


def canonicalize_calibrations(calibrations, names):
    result = {}
    for name, entry in calibrations.items():
        result[name] = {"joints": entry["joints"],
                        "scale_to_rad": ordered_target(entry["scale_to_rad"], entry["joints"], names),
                        "offset_rad": ordered_target(entry["offset_rad"], entry["joints"], names)}
    return result


def restore(model, initial, names):
    data = mujoco.MjData(model)
    data.qpos[:] = ordered_target(initial["position_rad"], initial["joints"], names)
    data.qvel[:] = ordered_target(initial["velocity_rad_s"], initial["joints"], names)
    data.ctrl[:] = ordered_target(initial["held_target_rad"], initial["joints"], names)
    mujoco.mj_forward(model, data)
    return data


def recover(model, episode, names, calibrations, bounds, stride):
    """Keep every physically feasible write history until the last readback."""
    data = restore(model, episode["initial"], names)
    candidates = [(native_clone(model, data), ())]
    for row in episode["windows"]:
        available = writes(row["writes"], names, calibrations, stride)
        for attempt in available:
            if any(not low <= value <= high for value, (low, high) in
                   zip(attempt.target, model.actuator_ctrlrange, strict=True)):
                raise ValueError("A commanded target exceeds its delivered drive limits")
        observation = row["encoder_after"]
        survivors = []
        for snapshot, history in candidates:
            for attempt in available:
                mujoco.mj_setState(model, data, snapshot, INTEGRATION)
                previous = data.ctrl.copy()
                target = np.asarray(attempt.target)
                for substep in range(stride):
                    if substep >= attempt.dispatch:
                        fraction = ((substep-attempt.dispatch+1)/(stride-attempt.dispatch)
                                    if attempt.interpolation == "linear" else 1.)
                        data.ctrl[:] = previous + fraction*(target-previous)
                    mujoco.mj_step(model, data)
                if observation is None or witnessed(data, observation, *bounds):
                    survivors.append((native_clone(model, data), (*history, attempt)))
        candidates = survivors
        if not candidates:
            break
    decisions = []
    for tick, window in enumerate(episode["windows"]):
        options = sorted({history[tick].identifier: history[tick] for _, history in candidates}.values(),
                         key=lambda write: write.identifier)
        chosen = options[0] if len(options) == 1 else None
        status = "confirmed" if chosen else ("ambiguous" if options else "inconsistent")
        decisions.append({
            "index": window["index"], "decision": status,
            "action": chosen.target if chosen else None,
            "receipt": chosen.identifier if chosen else None,
            "controller": chosen.controller if chosen else None,
            "feasible_receipts": [item.identifier for item in options],
        })
    return decisions


def action_qualify(dataset: Path, ledger: Path, output: Path) -> None:
    """Join native row identities and publish a canonical, nullable action audit."""
    packet = json.loads(ledger.read_text())
    model = mujoco.MjModel.from_xml_path(str(ledger.parent / packet["model"]))
    joints = [model.actuator(index).name for index in range(model.nu)]
    calibrations = canonicalize_calibrations(packet["calibrations"], joints)
    table = pq.read_table(dataset, columns=["index", "episode_index", "frame_index"])
    keys = {row["index"]: (row["episode_index"], row["frame_index"]) for row in table.to_pylist()}
    if len(keys) != table.num_rows:
        raise ValueError("Native global row IDs are not unique")
    decisions = []
    for entry in packet["episodes"]:
        seen = [(row["index"], entry["episode_index"], tick) for tick, row in enumerate(entry["windows"])]
        if any(keys.get(index) != (episode, tick) for index, episode, tick in seen):
            raise ValueError("Ledger windows do not align to the native frame indices")
        decisions.extend(recover(model, entry, joints, calibrations,
                                 (packet["position_tolerance_rad"], packet["velocity_tolerance_rad_s"]),
                                 packet["steps_per_frame"]))
    indices = sorted(item["index"] for item in decisions)
    if indices != sorted(keys):
        raise ValueError("Ledger must cover each native row once")
    schema = pa.schema([("index", pa.int64()), ("decision", pa.string()),
                        ("action", pa.list_(pa.float64())), ("receipt", pa.string()),
                        ("controller", pa.string()), ("feasible_receipts", pa.list_(pa.string()))])
    result = pa.Table.from_pylist(sorted(decisions, key=lambda row: row["index"]), schema=schema)
    with NamedTemporaryFile(dir=output.parent, suffix=".parquet", delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        pq.write_table(result, staging)
        staging.replace(output)
    finally:
        staging.unlink(missing_ok=True)
