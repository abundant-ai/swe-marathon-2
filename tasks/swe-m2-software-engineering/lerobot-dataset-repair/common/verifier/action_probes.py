"""Construct independent physical witnesses for native LeRobot action labels."""

import json
from pathlib import Path
import shutil

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


STRIDE = 6
AXES = (0, 2, 1, 3, 4, 5)
POSITION_ERROR = .00033
VELOCITY_ERROR = .005
FIELDS = ("index", "decision", "action", "receipt", "controller", "feasible_receipts")


def coded_calibrations(model):
    """Create old degree and normalized motor adapters in different bus order."""
    joint_names = [model.actuator(index).name for index in range(model.nu)]
    limits = model.actuator_ctrlrange
    specs = {
        "leader-pre-migration": ((4,1,3,0,5,2), np.array([1.,-1.,1.,1.,1.,-1.])*np.pi/180,
                                 np.array([0.,np.pi/2,-np.pi/2,0.,0.,.03])),
        "rtc-client": ((2,0,5,3,1,4), (limits[:,1]-limits[:,0])/200,
                       (limits[:,1]+limits[:,0])/2),
    }
    records = {}
    for device, (order, scale, offset) in specs.items():
        indices = list(order)
        records[device] = {"joints":[joint_names[index] for index in indices],
                           "scale_to_rad":scale[indices].tolist(), "offset_rad":offset[indices].tolist()}
    return records, specs, joint_names


def source_write(identifier, target, controller, specs):
    calibration = "leader-pre-migration" if controller == "operator" else "rtc-client"
    order, scale, offset = specs[calibration]
    value = ((target-offset)/scale)[list(order)]
    return {"receipt":identifier, "target":value.tolist(), "controller":controller, "calibration":calibration}


def decision(index, options, selected, canonical, kind):
    if kind == "ambiguous":
        return {"index":index, "decision":kind, "action":None, "receipt":None,
                "controller":None, "feasible_receipts":sorted(item["receipt"] for item in options)}
    return {"index":index, "decision":"confirmed", "action":canonical[selected].tolist(),
            "receipt":options[selected]["receipt"], "controller":options[selected]["controller"],
            "feasible_receipts":[options[selected]["receipt"]]}


def run_episode(model, seed, number, names, specs, start_index, uncertain=False, contradictory=False, delayed=False):
    """Enroll issued possibilities then record sparse motor samples after actual hardware writes."""
    rng = np.random.default_rng(seed)
    data = mujoco.MjData(model)
    initial_positions = np.array([.16, -.40, .46, .22, -.14, .48]) + rng.uniform(-.06,.06,6)
    data.qpos[:] = initial_positions
    data.ctrl[:] = initial_positions
    mujoco.mj_forward(model, data)
    reorder = [3, 4, 2, 5, 1, 0]
    initial = {"joints":[names[item] for item in reorder],
               "position_rad":initial_positions[reorder].tolist(), "velocity_rad_s":[0.]*6,
               "held_target_rad":initial_positions[reorder].tolist()}
    windows, expected, frames = [], [], []
    for tick in range(24):
        index = start_index+tick
        near = data.qpos.copy()+rng.uniform(-.01,.01,6)
        candidates = []
        for alternative in range(4):
            target = near.copy()
            target[AXES[tick%6]] += .072*(-1)**(alternative//2)
            target[AXES[(tick+2)%6]] += .067*(-1)**alternative
            candidates.append(target)
        ambiguous = uncertain and tick in (10, 11)
        if ambiguous:
            candidates[2] = candidates[0].copy()
        selected = 0 if ambiguous else int(rng.integers(4))
        permutation = rng.permutation(4)
        controller = ["policy","policy","operator","operator"]
        options = [source_write(f"rtc-{seed}-{tick}-{offset}", candidates[offset], controller[offset], specs)
                   for offset in range(4)]
        if delayed:
            for option in options:
                option["dispatch_substep"] = int(rng.integers(0,4))
                option["interpolation"] = "linear" if rng.integers(2) else "step"
            if ambiguous:
                for field in ("dispatch_substep","interpolation"):
                    options[2][field] = options[0][field]
        frames.append({"index":index, "episode_index":number, "frame_index":tick, "timestamp":tick/30,
                       "task_index":0, "observation.state":data.qpos.tolist(),
                       "action":candidates[(selected+1)%4].tolist()})
        actual = options[selected]
        prior = data.ctrl.copy()
        pending = candidates[selected]
        first = actual.get("dispatch_substep",0)
        ramp = np.linspace(prior,pending,STRIDE-first+1)[1:] if actual.get("interpolation")=="linear" else [
            pending for _ in range(STRIDE-first)
        ]
        for command in [prior]*first + list(ramp):
            data.ctrl[:] = command
            mujoco.mj_step(model, data)
        encoder = None
        if tick%3 == 2:
            position = (data.qpos+rng.uniform(-.00018,.00018,6)).tolist()
            velocity = (data.qvel+rng.uniform(-.0028,.0028,6)).tolist() if tick%6 == 5 else [None]*6
            if contradictory and tick == 14:
                position[1] += .30
            encoder = {"position_rad":position,"velocity_rad_s":velocity}
        windows.append({"index":index, "writes":[options[slot] for slot in permutation], "encoder_after":encoder})
        if ambiguous:
            expected.append(decision(index, [options[0],options[2]], selected, candidates, "ambiguous"))
        else:
            expected.append(decision(index, options, selected, candidates, "confirmed"))
    if contradictory:
        expected = [{"index":row["index"], "decision":"inconsistent", "action":None, "receipt":None,
                     "controller":None, "feasible_receipts":[]} for row in expected]
    return {"episode_index":number,"initial":initial,"windows":windows}, expected, frames


def probe(run, root, specs):
    """Compare submitted actions with executed controls and documented ambiguous alternatives."""
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    model_file = root/"model.xml"
    shutil.copyfile(Path(__file__).with_name("so101-headless.xml"), model_file)
    model = mujoco.MjModel.from_xml_path(str(model_file))
    calibrations, transform, names = coded_calibrations(model)
    episodes, expected, table = [], [], []
    for index, (seed, uncertain, contradictory, delayed) in enumerate(specs):
        episode, decisions, frames = run_episode(model, seed, index+12, names, transform, len(table),
                                                  uncertain=uncertain, contradictory=contradictory, delayed=delayed)
        episodes.append(episode)
        expected.extend(decisions)
        table.extend(frames)
    dataset, ledger, output = (root/name for name in ("source.parquet","write-ledger.json","labels.parquet"))
    pq.write_table(pa.Table.from_pylist(table),dataset)
    ledger.write_text(json.dumps({"model":model_file.name,"calibrations":calibrations,"steps_per_frame":STRIDE,
                      "position_tolerance_rad":POSITION_ERROR,"velocity_tolerance_rad_s":VELOCITY_ERROR,
                      "episodes":episodes},allow_nan=False))
    if run("action-qualify","--dataset",dataset,"--ledger",ledger,"--output",output):
        return False
    actual = pq.read_table(output).to_pylist()
    if len(actual)!=len(expected) or tuple(pq.read_schema(output).names)!=FIELDS:
        return False
    for proposed, reference in zip(actual,expected,strict=True):
        if any(proposed[key]!=reference[key] for key in FIELDS if key!="action"):
            return False
        measured, target = proposed["action"], reference["action"]
        if target is None:
            if measured is not None:
                return False
        elif measured is None or len(measured)!=model.nu or not np.allclose(measured,target,rtol=0,atol=1e-8):
            return False
    return True


def action_cases(run, root):
    """Qualify positive reconstructions, irreducible uncertainty and inconsistent episodes."""
    scenarios = {
        "staggered_native_writes":((105,False,False,False),(301,False,False,False)),
        "human_intervention_provenance":((186,True,False,False),),
        "mixed_boots_with_inconsistent_readback":((413,False,False,False),(627,False,True,False)),
        "interpolated_writes_and_handoff":((198,False,False,True),(687,True,False,True)),
    }
    outcomes = {}
    for name, spec in scenarios.items():
        try:
            outcomes[name] = probe(run, root/name, spec)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError):
            outcomes[name] = False
    return outcomes
