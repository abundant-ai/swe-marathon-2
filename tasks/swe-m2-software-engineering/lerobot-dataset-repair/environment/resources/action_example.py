#!/usr/bin/env python3
"""Generate a small SO101 recording with staged writes and native readback."""

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


MODEL = "so101-headless.xml"
NOTICE = "SO101-MODEL-LICENSE.txt"
STEPS_PER_FRAME = 5


def simulate(model: mujoco.MjModel) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build one frame table and ledger by driving the supplied SO101 model.

    Args:
        model: Compiled SO101 with six position actuators in native order.

    Returns:
        Frame records and their ledger. Encoder fields come from the resulting
        native integration state. The generated inputs contain no receipt labels
        that disclose the executed write.
    """
    names = [model.actuator(axis).name for axis in range(model.nu)]
    leader_order = [5, 2, 0, 3, 1, 4]
    leader_scale = np.deg2rad([1.0, -1.0, 1.0, 1.0, -1.0, 1.0])
    leader_offset = np.array([0.0, 0.10, 0.0, -0.04, 0.0, 0.02])
    calibrations = {
        "policy-radians": {"joints": names, "scale_to_rad": [1.0] * model.nu,
                           "offset_rad": [0.0] * model.nu},
        "leader-degrees": {"joints": [names[i] for i in leader_order],
                           "scale_to_rad": leader_scale[leader_order].tolist(),
                           "offset_rad": leader_offset[leader_order].tolist()},
    }

    initial = np.array([0.10, -0.35, 0.44, -0.25, 0.21, 0.45])
    data = mujoco.MjData(model)
    data.qpos[:] = initial
    data.ctrl[:] = initial
    mujoco.mj_forward(model, data)

    policy_targets = initial + np.array([
        [0.12, -0.06, 0.0, 0.0, 0.0, 0.0],
        [0.06, 0.0, 0.10, 0.0, 0.0, 0.0],
        [0.0, 0.0, -0.04, 0.0, 0.0, 0.12],
        [0.08, -0.05, 0.04, 0.0, -0.08, 0.0],
    ])
    operator_targets = initial + np.array([
        [-0.13, 0.07, 0.0, 0.0, 0.0, 0.0],
        [-0.06, 0.0, -0.11, 0.05, 0.0, 0.0],
        [0.0, 0.0, -0.04, 0.0, 0.0, 0.12],
        [-0.03, 0.04, 0.0, 0.0, 0.10, 0.0],
    ])
    frames, windows = [], []
    for frame, (policy, operator) in enumerate(zip(policy_targets, operator_targets, strict=True)):
        index = 810 + frame
        frames.append({"index": index, "episode_index": 7, "frame_index": frame,
                       "timestamp": frame * model.opt.timestep * STEPS_PER_FRAME, "task_index": 0,
                       "observation.state": data.qpos.tolist(), "action": policy.tolist()})
        policy_write = {"receipt": f"policy-{frame}", "controller": "policy",
                        "calibration": "policy-radians", "target": policy.tolist()}
        operator_write = {"receipt": f"operator-{frame}", "controller": "operator",
                          "calibration": "leader-degrees",
                          "target": ((operator - leader_offset) / leader_scale)[leader_order].tolist()}
        if frame == 1:
            operator_write.update(dispatch_substep=2, interpolation="linear")
        if frame == 2:
            # Both receipts reach the same actuator target on the same schedule.
            policy_write.update(dispatch_substep=1)
            operator_write.update(dispatch_substep=1)

        held = data.ctrl.copy()
        for substep in range(STEPS_PER_FRAME):
            if frame == 1:
                if substep >= 2:
                    # The leader drive catches up over the final three native steps.
                    data.ctrl[:] = held + (operator - held) * ((substep - 1) / 3)
            elif frame != 2 or substep >= 1:
                data.ctrl[:] = policy
            mujoco.mj_step(model, data)

        sample = None
        if frame:
            velocity = data.qvel.tolist() if frame != 2 else [None] * model.nv
            sample = {"position_rad": data.qpos.tolist(), "velocity_rad_s": velocity}
        windows.append({"index": index, "writes": [operator_write, policy_write], "encoder_after": sample})

    ledger = {"model": MODEL, "calibrations": calibrations, "steps_per_frame": STEPS_PER_FRAME,
              "position_tolerance_rad": 0.0001, "velocity_tolerance_rad_s": 0.001,
              "episodes": [{"episode_index": 7, "initial": {"joints": names,
                            "position_rad": initial.tolist(), "velocity_rad_s": [0.0] * model.nv,
                            "held_target_rad": initial.tolist()}, "windows": windows}]}
    return frames, ledger


def main() -> None:
    """Write a self-contained example into the requested directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    destination = parser.parse_args().output_dir
    destination.mkdir(parents=True, exist_ok=True)
    resources = Path(__file__).resolve().parent
    for asset in (MODEL, NOTICE):
        shutil.copyfile(resources / asset, destination / asset)
    model = mujoco.MjModel.from_xml_path(str(destination / MODEL))
    frames, ledger = simulate(model)
    pq.write_table(pa.Table.from_pylist(frames), destination / "source.parquet")
    (destination / "write-ledger.json").write_text(json.dumps(ledger, indent=2, allow_nan=False) + "\n",
                                                  encoding="utf-8")


if __name__ == "__main__":
    main()
