"""Build native source and target states from the same authored physical readings."""

from copy import deepcopy

import mujoco
import numpy as np

from probes import STATE, identity, matches, simulated, update


BODY_XML = {
    "pusher": """<body name="pusher" pos="-.43 0 .13">
      <joint name="rail" type="slide" axis="1 0 0" damping=".7"/>
      <geom type="box" size=".07 .14 .08"/>
    </body>""",
    "object": """<body name="object" pos="-.18 .04 .13">
      <freejoint name="floating"/><geom type="box" size=".071 .062 .059" density="{density}"/>
    </body>""",
    "gimbal": """<body name="gimbal" pos=".2 .28 .27">
      <joint name="ball" type="ball" damping=".7"/>
      <geom type="box" size=".063 .05 .07"/>
      <body name="marker" pos=".10 0 0"><geom type="sphere" size=".025"/></body>
    </body>""",
    "clamp": """<body name="clamp" mocap="true" pos=".38 .02 .11">
      <geom type="box" size=".04 .12 .08"/>
    </body>""",
    "guide": """<body name="guide" mocap="true" pos=".18 -.23 .11">
      <geom type="box" size=".07 .072 .09"/>
    </body>""",
}
ACTUATOR = {
    "ram": '<general name="ram" joint="rail" dyntype="filterexact" dynprm=".06" gainprm="{gain}"/>',
    "tilt": '<motor name="tilt" joint="ball" gear="0 1 0 0 0 0"/>',
    "swing": '<general name="swing" joint="ball" dyntype="integrator" gear="0 0 1 0 0 0" gainprm="2"/>',
}
EQUALITIES = {
    "lock": '<joint name="lock" joint1="rail" polycoef=".12 0 0 0 0" active="false"/>',
    "seat": '<weld name="seat" body1="object" body2="clamp" active="false"/>',
}

# Sensor and controller records indexed by workcell identity, before compilation.
GENERALIZED = {
    "pusher": ([0.18], [0.13], [0.29], [0.25]),
    "object": ([-0.163, 0.06, 0.064, 0.9998, 0, 0, 0.01999899997499875],
               [0.03, -0.14, -0.07, 0, -0.06, 0.11],
               [0.1, -0.08, 0.33, 0.05, -0.09, 0.16],
               [-0.04, 0.12, 0.05, 0.01, 0.03, -0.02]),
    "gimbal": ([0.9805806756909201, 0, 0.19611613513818404, 0],
               [0.11, 0.06, -0.028], [-0.11, 0.54, 0.08], [0.03, -0.19, 0.043]),
}
CONTROLS = {"ram": (0.41, 0.21), "tilt": (-0.21, None), "swing": (0.06, -0.24)}
MOCAP = {
    "clamp": ([0.26, 0.22, 0.12], [0.9805806756909201, 0, 0, 0.19611613513818404]),
    "guide": ([0.35, -0.17, 0.12], [0.9950371902099893, 0, 0, -0.09950371902099893]),
}
BODY_ORDER = ("pusher", "object", "gimbal", "clamp", "guide")
ACTUATOR_ORDER = ("ram", "tilt", "swing")
EQ_ORDER = ("lock", "seat")


def model_source(bodies, actuators, equalities, *, density, friction, gain, iterations):
    """Emit a named MJCF layout in the given physical-body and input order."""
    written_bodies = "\n".join(BODY_XML[name].format(density=density) for name in bodies)
    written_actuators = "\n".join(ACTUATOR[name].format(gain=gain) for name in actuators)
    written_equalities = "\n".join(EQUALITIES[name] for name in equalities)
    return {
        "assets": {"surface.xml": f'<mujocoinclude><default><geom friction="{friction} .03 .002"/>'
                                  '</default></mujocoinclude>'},
        "xml": f"""<mujoco model="transfer calibration">
          <size nuserdata="3"/>
          <option timestep="0.004" integrator="implicitfast" iterations="{iterations}"/>
          <include file="surface.xml"/>
          <worldbody><geom type="plane" size="3 3 .1"/>{written_bodies}</worldbody>
          <actuator>{written_actuators}</actuator>
          <equality>{written_equalities}</equality>
        </mujoco>""",
    }


def witnessed_checkpoint(source, bodies, actuators, equalities, tick, switch):
    """Encode independently known semantic inputs by their declaration order."""
    model = mujoco.MjModel.from_xml_string(source["xml"], {k: v.encode() for k, v in source["assets"].items()})
    data = mujoco.MjData(model)
    state_order = [GENERALIZED[name] for name in bodies if name in GENERALIZED]
    for i, field in enumerate(("qpos", "qvel", "qacc_warmstart", "qfrc_applied")):
        getattr(data, field)[:] = [value for joint in state_order for value in joint[i]]
    data.ctrl[:] = [CONTROLS[name][0] for name in actuators]
    data.act[:] = [CONTROLS[name][1] for name in actuators if CONTROLS[name][1] is not None]
    for field, index in (("mocap_pos", 0), ("mocap_quat", 1)):
        getattr(data, field)[:] = [MOCAP[name][index] for name in bodies if name in MOCAP]
    preorder = ["world"]
    for name in bodies:
        preorder.append(name)
        if name == "gimbal":
            preorder.append("marker")
    for index, name in enumerate(preorder):
        load = ("world", *BODY_ORDER, "marker").index(name)
        data.xfrc_applied[index] = [0.1 * load, -0.04 * load, 0.02 * load, 0, 0.014 * load, 0]
    data.eq_active[:] = [name == switch for name in equalities]
    data.userdata[:] = [0.7, -1.1, 19]
    data.time = tick * model.opt.timestep
    state = np.empty(mujoco.mj_stateSize(model, STATE), dtype=np.float64)
    mujoco.mj_getState(model, data, state, STATE)
    return {"model_id": identity(source), "tick": tick, "integration": state.tolist()}


def mission(index):
    order = [
        (tuple(reversed(BODY_ORDER)), ("swing", "tilt", "ram"), ("seat", "lock")),
        (("gimbal", "clamp", "pusher", "guide", "object"), ("tilt", "swing", "ram"), EQ_ORDER),
        (("guide", "pusher", "object", "clamp", "gimbal"), ("swing", "ram", "tilt"), ("seat", "lock")),
        (("object", "gimbal", "guide", "pusher", "clamp"), ACTUATOR_ORDER, ("seat", "lock")),
        (BODY_ORDER, ACTUATOR_ORDER, EQ_ORDER),
        (("clamp", "guide", "gimbal", "object", "pusher"), ("tilt", "ram", "swing"), ("seat", "lock")),
    ][index]
    source = model_source(BODY_ORDER, ACTUATOR_ORDER, EQ_ORDER, density=370, friction=.55, gain=75, iterations=8)
    target = model_source(*order, density=415 + 40 * index, friction=.44 + .12 * index,
                          gain=40 + index * 8, iterations=10 + index)
    start, end = 31 + index * 4, 138 + index * 13
    active = "lock" if index % 3 == 2 else None
    capture = witnessed_checkpoint(source, BODY_ORDER, ACTUATOR_ORDER, EQ_ORDER, start, active)
    expected = witnessed_checkpoint(target, *order, start, active)
    spec = {
        "source_model": source, "target_model": target, "checkpoint": capture, "end": end,
        "sample_ticks": [end, start, start + 20, end - 11], "checkpoint_ticks": [start, end - 11, end],
        "updates": [
            update(start + 4, ctrl=[0.22, -0.04, 0.09]),
            update(end - 17, eq_active=[0, 0]),
        ] if index != 5 else [],
    }
    return spec, {"checkpoint": expected, "resumed": simulated(dict(spec, model=target), expected)}


def checks_rebase(run):
    """Score valid physical continuations and reject selected genuine coordinate mismatches."""
    cases = {}
    for index, name in enumerate(("reorder_every_group", "free_and_ball", "mocap_and_eq",
                                  "retune_pusher", "physical_parameter_edit", "retain_inputs")):
        request, expected = mission(index)
        cases[name] = matches(run("rebase", request), expected)
    for name, old, new in (
        ("joint_axis", 'axis="1 0 0"', 'axis="0 1 0"'),
        ("joint_target", 'joint="rail" dyntype=', 'joint="ball" dyntype='),
        ("world_body_endpoint", 'body2="clamp"', 'body2="guide"'),
        ("timestep", 'timestep="0.004"', 'timestep="0.005"'),
        ("nonportable_user_state_size", 'nuserdata="3"', 'nuserdata="4"'),
    ):
        request, _ = mission(2)
        invalid = deepcopy(request)
        xml = invalid["target_model"]["xml"]
        assert old in xml
        invalid["target_model"]["xml"] = xml.replace(old, new, 1)
        cases["reject_" + name] = run("rebase", invalid, invalid=True) is True
    request, _ = mission(0)
    cases["reject_empty_capture"] = run("rebase", dict(request, checkpoint=None), invalid=True) is True
    return cases
