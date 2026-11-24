"""Compare submitted traces with independent native simulation and replay checks."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from math import isclose, isfinite
from pathlib import Path
import tempfile

import mujoco
import numpy as np


STATE = mujoco.mjtState.mjSTATE_INTEGRATION
SCENE = """
<mujoco model="transfer rig">
  <option timestep="{timestep}" integrator="{integrator}" iterations="12"/>
  <include file="contact.xml"/>
  <worldbody>
    <geom name="table" type="plane" size="3 3 .1"/>
    <body name="pusher" pos="-.36 0 .09">
      <joint name="slide" type="slide" axis="1 0 0" range="-.1 .75" damping="1.4"/>
      <geom type="box" size=".075 .15 .07" density="620"/>
    </body>
    <body name="part" pos="-.145 {offset} .095">
      <freejoint/>
      <geom type="box" size=".067 .086 .069" density="{density}"/>
    </body>
    <body name="fixture" mocap="true" pos=".55 0 .1">
      <geom type="box" size=".075 .22 .1"/>
    </body>
  </worldbody>
  <actuator>
    <general name="drive" joint="slide" dyntype="filterexact" dynprm=".035"
             gainprm="130" biastype="affine" biasprm="0 -130 -7"/>
  </actuator>
  <equality>
    <joint name="pin carriage" joint1="slide" polycoef=".15 0 0 0 0" active="false"/>
  </equality>
</mujoco>
"""


def model_variant(index):
    """Commission three variations of a loaded contact experiment."""
    parameters = [
        (0.004, "Euler", 0.012, 390, 0.77),
        (0.006, "implicit", -0.038, 640, 0.49),
        (0.003, "implicitfast", 0.056, 510, 1.18),
    ]
    step, solver, offset, density, friction = parameters[index]
    return {
        "xml": SCENE.format(timestep=step, integrator=solver, offset=offset, density=density),
        "assets": {"contact.xml": f'<mujocoinclude><default><geom friction="{friction} .01 .001"/>'
                                  '</default></mujocoinclude>'},
    }


def update(tick, **fields):
    return {"tick": tick, "set": fields}


def forces(y):
    return [[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, y, 0, 0, 0, 0.013], [0, 0, 0, 0, 0, 0]]


def base_spec(index):
    """Use separated actuation, external loads and moving fixture updates."""
    return {
        "model": model_variant(index), "end": 180, "sample_ticks": [180, 0, 37, 119, 63],
        "checkpoint_ticks": [63, 119, 180],
        "updates": [
            update(84, mocap_pos=[[0.46, 0.08 - index * 0.02, 0.10]]),
            update(0, ctrl=[0.46 + 0.08 * index]),
            update(39, xfrc_applied=forces(1.7 + index)),
            update(111, ctrl=[0.12]),
            update(127, eq_active=[1]),
            update(145, eq_active=[0]),
        ],
    }


def identity(spec):
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def simulated(spec, checkpoint=None, checkpoints=True):
    """Compute requested boundary evidence directly with the published MuJoCo API."""
    source = spec["model"]
    model = mujoco.MjModel.from_xml_string(source["xml"], {k: v.encode() for k, v in source["assets"].items()})
    model_id = identity(source)
    data = mujoco.MjData(model)
    start = 0
    if checkpoint:
        start = checkpoint["tick"]
        mujoco.mj_setState(model, data, np.asarray(checkpoint["integration"], dtype=np.float64), STATE)
    boundaries = sorted({start, spec["end"], *spec["sample_ticks"],
                         *(spec["checkpoint_ticks"] if checkpoints else []),
                         *(record["tick"] for record in spec["updates"])})
    by_tick = {}
    for event in spec["updates"]:
        by_tick.setdefault(event["tick"], {}).update(event["set"])
    samples, saved = [], []
    last = start
    for tick in boundaries:
        if tick > last:
            mujoco.mj_step(model, data, nstep=tick - last)
        if tick in spec["sample_ticks"]:
            samples.append(dict(tick=tick, qpos=list(data.qpos), qvel=list(data.qvel), act=list(data.act)))
        if checkpoints and tick in spec["checkpoint_ticks"]:
            integration = np.zeros(mujoco.mj_stateSize(model, STATE), dtype=np.float64)
            mujoco.mj_getState(model, data, integration, STATE)
            saved.append(dict(model_id=model_id, tick=tick, integration=integration.tolist()))
        for field, value in by_tick.get(tick, {}).items():
            getattr(data, field)[:] = value
        last = tick
    report = dict(model_id=model_id, samples=samples)
    if checkpoints:
        report["checkpoints"] = saved
    return report


def matches(actual, expected):
    """Require the requested structure and finite native trajectory values."""
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(matches(actual[key], expected[key]) for key in expected))
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(matches(a, b) for a, b in zip(actual, expected, strict=True)))
    if isinstance(expected, (float, np.floating)):
        try:
            return (type(actual) in (float, int) and isfinite(actual)
                    and isclose(actual, expected, abs_tol=2e-10, rel_tol=2e-9))
        except OverflowError:
            return False
    return type(actual) is type(expected) and actual == expected


def continuation(spec, checkpoint, *, ctrl, end):
    tick = checkpoint["tick"]
    return dict(spec, end=end, checkpoint=checkpoint, sample_ticks=[tick, tick + 9, end],
                checkpoint_ticks=[tick, end], updates=[update(tick, ctrl=[ctrl])])


def run_item(name, parent, request):
    return {
        "id": name, "parent": parent, **{key: request[key] for key in (
            "end", "sample_ticks", "checkpoint_ticks", "updates",
        )},
    }


def branch_graph(index):
    """Author alternative controls and nested forks from shared contact states."""
    spec = base_spec(index)
    root = simulated(spec)
    fork = root["checkpoints"][0]
    retain = continuation(spec, fork, ctrl=0.7, end=155)
    release = continuation(spec, fork, ctrl=-0.07, end=125)
    retain_result, release_result = (simulated(request, fork) for request in (retain, release))
    leaf_checkpoint = retain_result["checkpoints"][-1]
    leaf = continuation(spec, leaf_checkpoint, ctrl=0.18, end=210)
    leaf["updates"].append(update(172, qfrc_applied=[0.5] + [0] * 6))
    leaf_result = simulated(leaf, leaf_checkpoint)
    items = [
        run_item("leaf", {"id": "retain", "tick": 155}, leaf),
        run_item("release", {"id": "baseline", "tick": 63}, release),
        run_item("baseline", None, spec),
        run_item("retain", {"id": "baseline", "tick": 63}, retain),
    ]
    return spec["model"], items, dict(baseline=root, retain=retain_result, release=release_result, leaf=leaf_result)


def study_request(model, rows):
    return {"model": model, "runs": rows}


def study_report(model, outcomes, names):
    return {"model_id": identity(model), "runs": {name: outcomes[name] for name in names}}


def run_study(run, index, scenario):
    model, jobs, outcome = branch_graph(index)
    with tempfile.TemporaryDirectory(prefix="study-", dir=run.scratch) as temp:
        directory = Path(temp)
        directory.chmod(0o777)
        state = directory / "study"
        expected = study_report(model, outcome, outcome)
        packet = study_request(model, jobs)
        if scenario == "out_of_order":
            return matches(run("study", packet, state=state), expected)
        if scenario == "concurrent_retry":
            with ThreadPoolExecutor(2) as pool:
                calls = [pool.submit(run, "study", packet, state=state) for _ in range(2)]
                return all(matches(call.result(), expected) for call in calls)
        root = study_request(model, [jobs[2]])
        previous = study_report(model, outcome, ("baseline",))
        if scenario == "parallel_siblings":
            if not matches(run("study", root, state=state), previous):
                return False
            with ThreadPoolExecutor(2) as pool:
                queued = [
                    (jobs[index], pool.submit(run, "study", study_request(model, [jobs[index]]), state=state))
                    for index in (1, 3)
                ]
                for item, future in queued:
                    if not matches(future.result(), study_report(model, outcome, (item["id"],))):
                        return False
            dependent = study_request(model, [jobs[0], jobs[1]])
            return matches(run("study", dependent, state=state),
                           study_report(model, outcome, ("leaf", "release")))
        if scenario == "lost_reply":
            saved = run("study", root, state=state, lost_reply=True)
            child = study_request(model, [jobs[0], jobs[3]])
            completion = study_report(model, outcome, ("leaf", "retain"))
            return (saved and matches(run("study", child, state=state), completion)
                    and matches(run("study", root, state=state), previous))
        if not matches(run("study", root, state=state), previous):
            return False
        invalid = deepcopy(packet)
        if scenario == "changed_ancestor":
            invalid["runs"][2]["updates"][0]["set"]["mocap_pos"][0][0] += 0.032
        elif scenario == "partial_commit":
            invalid["runs"][0]["parent"]["tick"] = 154
        elif scenario == "different_assets":
            invalid["model"]["assets"]["contact.xml"] += "\n"
        elif scenario == "cycle":
            invalid["runs"][3]["parent"]["id"] = "leaf"
        if not run("study", invalid, state=state, invalid=True):
            return False
        if scenario == "partial_commit":
            changed = deepcopy(jobs[1])
            changed["updates"].append(update(116, mocap_pos=[[0.65, 0, 0.13]]))
            start = outcome["baseline"]["checkpoints"][0]
            outcome["release"] = simulated(dict(changed, model=model), start)
            jobs[1] = changed
            packet, expected = study_request(model, jobs), study_report(model, outcome, outcome)
        return (matches(run("study", packet, state=state), expected)
                and matches(run("study", root, state=state), previous))


def trace_input(spec):
    """Project shared fixtures onto the public trace-only request format."""
    return {key: spec[key] for key in ("model", "end", "sample_ticks", "updates")}


def checks(run, level):
    """Evaluate expanding simulation contracts and their independent witnesses."""
    results = {}
    for index in range(3):
        spec = base_spec(index)
        results[f"native_trace_{index}"] = matches(run("trace", trace_input(spec)), simulated(spec, checkpoints=False))
        if level >= 2:
            whole = simulated(spec)
            fork = whole["checkpoints"][0]
            suffix = continuation(spec, fork, ctrl=0.32, end=174)
            results[f"checkpoint_capture_{index}"] = matches(run("resume", spec), whole)
            results[f"native_restore_{index}"] = matches(run("resume", suffix), simulated(suffix, fork))
    if level < 3:
        malformed = base_spec(0)
        malformed["updates"].append(update(0, ctrl=[0.1]))
        results["reject_duplicate_update"] = run("trace", trace_input(malformed), invalid=True) is True
        if level == 2:
            model = base_spec(1)
            checkpoint = simulated(model)["checkpoints"][0]
            inconsistent = dict(checkpoint, tick=checkpoint["tick"] + 1)
            suffix = continuation(model, inconsistent, ctrl=0.31, end=165)
            results["reject_wrong_checkpoint_time"] = run("resume", suffix, invalid=True) is True
        return results
    scenarios = ("out_of_order", "concurrent_retry", "parallel_siblings", "lost_reply",
                 "changed_ancestor", "partial_commit", "different_assets", "cycle")
    final = {}
    for index, name in enumerate(scenarios):
        variant = index % 3
        retained = all(results[f"{prefix}_{variant}"]
                       for prefix in ("native_trace", "checkpoint_capture", "native_restore"))
        final[name] = retained and bool(run_study(run, variant, name))
    return final
