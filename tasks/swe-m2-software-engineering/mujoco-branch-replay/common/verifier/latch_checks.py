"""Independent native witnesses for momentum-aware payload handoff."""

from copy import deepcopy
from itertools import combinations
from math import isfinite
from xml.etree import ElementTree

import mujoco
import numpy as np
from probes import STATE, identity, simulated

TOL = 1e-6
TIMESTEP = 0.001
HALF = np.array([0.102, 0.083, 0.055])
KEYS = {"attached_model", "latch_checkpoint", "carry", "release_checkpoint", "released"}
WIDTHS = {mujoco.mjtJoint.mjJNT_FREE: (7, 6), mujoco.mjtJoint.mjJNT_HINGE: (1, 1)}


def _text(vector):
    return " ".join(format(float(value), ".17g") for value in vector)


def _rotation(axis, angle):
    q = np.r_[np.cos(angle / 2), np.asarray(axis) * np.sin(angle / 2)]
    return _matrix(q)


def _matrix(quat):
    result = np.empty(9)
    mujoco.mju_quat2Mat(result, np.asarray(quat, dtype=float))
    return result.reshape(3, 3)


def _quat(rotation):
    q = np.empty(4)
    mujoco.mju_mat2Quat(q, np.ascontiguousarray(rotation.reshape(9)))
    return q


def _compile(description):
    return mujoco.MjModel.from_xml_string(
        description["xml"],
        {key: value.encode("utf-8") for key, value in description["assets"].items()},
    )


def _model(carrier, payload, articulated):
    actuator = (
        """
      <actuator>
        <general name="wrist-motor" joint="shoulder" dyntype="filterexact" dynprm=".03" gainprm="1.2"/>
      </actuator>"""
        if articulated
        else ""
    )
    xml = f"""
    <mujoco model="transfer-cell">
      <compiler angle="radian" alignfree="false" fusestatic="false"/>
      <size nuserdata="2"/>
      <option timestep="{TIMESTEP}" integrator="Euler" solver="Newton" iterations="25" cone="elliptic"/>
      <worldbody>
        <geom name="floor" type="plane" size="3 3 .1" friction=".37 .002 .0001"/>
        <body name="marker" pos=".72 -.50 .28" mocap="true">
          <geom name="marker-shell" type="sphere" size=".022" contype="0" conaffinity="0"/>
        </body>
        {carrier}
        {payload}
      </worldbody>
      {actuator}
    </mujoco>"""
    return {"xml": xml, "assets": {}}


def _carrier(name, site, articulated, payload=""):
    if not articulated:
        return f"""
        <body name="{name}" pos="0 0 .26">
          <freejoint name="moving-base" align="false"/>
          <inertial pos=".04 -.021 .019" mass="1.8" diaginertia=".014 .021 .025" quat=".996 .08935 0 0"/>
          <geom name="carrier-shell" type="box" size=".089 .11 .045"/>
          {site}{payload}
        </body>"""
    return f"""
    <body name="arm-base" pos="-.13 -.12 .085">
      <joint name="turn" type="hinge" axis="0 0 1"/>
      <geom name="turn-link" type="capsule" fromto="0 0 0 .21 0 .055" size=".032"
            density="650" contype="0" conaffinity="0"/>
      <body name="arm-link" pos=".21 0 .055">
        <joint name="shoulder" type="hinge" axis="0 1 0"/>
        <geom name="arm-link-shell" type="capsule" fromto="0 0 0 .23 0 .018" size=".027"
              density="620" contype="0" conaffinity="0"/>
        <body name="{name}" pos=".23 0 .018">
          <joint name="roll" type="hinge" axis="1 0 0"/>
          <geom name="carrier-shell" type="box" size=".038 .069 .035" pos=".012 .014 -.011"
                density="610" contype="0" conaffinity="0"/>
          {site}{payload}
        </body>
      </body>
    </body>"""


def _payload(name, site, position, rotation, *, attached=False, armature=0.0):
    joint = (
        ""
        if attached
        else f'<joint name="{name}-motion" type="free" armature="{armature}"/>'
    )
    return f"""
    <body name="{name}" pos="{_text(position)}" quat="{_text(_quat(rotation))}">
      {joint}
      <inertial pos="-.029 .037 .012" mass="1.22" diaginertia=".009 .013 .017" quat=".997 0 .0774 0"/>
      <geom name="payload-shell" type="box" size="{_text(HALF)}" friction=".39 .004 .0002"/>
      {site}
    </body>"""


def _site(name, translation, rotation):
    return f'<site name="{name}" pos="{_text(translation)}" quat="{_text(_quat(rotation))}" size=".012"/>'


def _body_pose(model, data, name):
    index = model.body(name).id
    return data.xpos[index].copy(), data.xmat[index].reshape(3, 3).copy()


def _slices(model, joint_name):
    index = model.joint(joint_name).id
    nq, nv = WIDTHS[model.jnt_type[index]]
    qpos, dof = model.jnt_qposadr[index], model.jnt_dofadr[index]
    return slice(qpos, qpos + nq), slice(dof, dof + nv)


def _payload_joint(model, payload):
    index = model.body_jntadr[model.body(payload).id]
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, index)


def _set_free(model, data, joint_name, position, rotation):
    qpos, _ = _slices(model, joint_name)
    data.qpos[qpos] = np.r_[position, _quat(rotation)]


def _spatial_jac(model, data, body_id, point):
    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))
    if body_id:
        mujoco.mj_jac(model, data, jacp, jacr, point, body_id)
    return np.vstack((jacp, jacr))


def _support(model, state):
    normals = []
    for contact in state.contact:
        if contact.dist > 0:
            continue
        first, second = (int(model.geom_bodyid[index]) for index in contact.geom)
        first_jac = _spatial_jac(model, state, first, contact.pos)[:3]
        second_jac = _spatial_jac(model, state, second, contact.pos)[:3]
        row = contact.frame[:3] @ (second_jac - first_jac)
        if np.linalg.norm(row) > 1e-12:
            normals.append(row)
    return np.asarray(normals, dtype=float).reshape(-1, model.nv)


def _impact(model, state, carrier, payload):
    """Compute source-space plastic impact through the KKT equations."""
    payload_id = model.body(payload).id
    carrier_id = model.body(carrier).id
    point = state.xpos[payload_id]
    capture = _spatial_jac(model, state, payload_id, point) - _spatial_jac(
        model, state, carrier_id, point
    )
    normals = _support(model, state)
    mass = np.empty((model.nv, model.nv))
    mujoco.mj_fullM(model, mass, state.qM)
    options = []
    for count in range(len(normals) + 1):
        for rows in combinations(range(len(normals)), count):
            active = np.vstack((capture, normals[list(rows)]))
            system = np.block(
                [[mass, -active.T], [active, np.zeros((len(active), len(active)))]]
            )
            right = np.r_[mass @ state.qvel, np.zeros(len(active))]
            solution, *_ = np.linalg.lstsq(system, right, rcond=None)
            speed = solution[: model.nv]
            impulse = solution[model.nv :]
            if np.linalg.norm(system @ solution - right, ord=np.inf) > 1e-9:
                continue
            if count and np.min(impulse[len(capture) :]) < -1e-9:
                continue
            if len(normals) and np.min(normals @ speed) < -1e-9:
                continue
            shift = speed - state.qvel
            options.append((float(shift @ mass @ shift), speed))
    if not options:
        raise AssertionError("trusted fixture has no feasible impact")
    return min(options, key=lambda item: item[0])[1]


def _checkpoint(description, model, state, tick):
    packed = np.empty(mujoco.mj_stateSize(model, STATE))
    mujoco.mj_getState(model, state, packed, STATE)
    return {
        "model_id": identity(description),
        "tick": tick,
        "integration": packed.tolist(),
    }


def _restore(model, checkpoint):
    state = mujoco.MjData(model)
    mujoco.mj_setState(
        model, state, np.asarray(checkpoint["integration"], dtype=float), STATE
    )
    mujoco.mj_forward(model, state)
    return state


def _named(model, kind, count):
    return {mujoco.mj_id2name(model, kind, index): index for index in range(count)}


def _copy_named(source, destination, before, after, velocities):
    joints = _named(source, mujoco.mjtObj.mjOBJ_JOINT, source.njnt)
    for name in _named(destination, mujoco.mjtObj.mjOBJ_JOINT, destination.njnt):
        if name in joints:
            src_q, src_v = _slices(source, name)
            dst_q, dst_v = _slices(destination, name)
            after.qpos[dst_q] = before.qpos[src_q]
            after.qvel[dst_v] = velocities[src_v]
            after.qfrc_applied[dst_v] = before.qfrc_applied[src_v]
    objects = (mujoco.mjtObj.mjOBJ_BODY, mujoco.mjtObj.mjOBJ_ACTUATOR)
    for index, name in enumerate(
        destination.body(i).name for i in range(destination.nbody)
    ):
        src = mujoco.mj_name2id(source, objects[0], name)
        after.xfrc_applied[index] = before.xfrc_applied[src]
        if destination.body_mocapid[index] >= 0:
            old_id = source.body_mocapid[src]
            new_id = destination.body_mocapid[index]
            after.mocap_pos[new_id] = before.mocap_pos[old_id]
            after.mocap_quat[new_id] = before.mocap_quat[old_id]
    for index, name in enumerate(
        destination.actuator(i).name for i in range(destination.nu)
    ):
        src = mujoco.mj_name2id(source, objects[1], name)
        after.ctrl[index] = before.ctrl[src]
        length = destination.actuator_actnum[index]
        if length:
            old_addr = source.actuator_actadr[src]
            new_addr = destination.actuator_actadr[index]
            after.act[new_addr : new_addr + length] = before.act[
                old_addr : old_addr + length
            ]
    after.time = before.time
    after.userdata[:] = before.userdata


def _latch(fixture, carried, carried_desc):
    source, state, tick, carrier, payload = fixture
    locked = mujoco.MjData(carried)
    velocity = _impact(source, state, carrier, payload)
    _copy_named(source, carried, state, locked, velocity)
    mujoco.mj_forward(carried, locked)
    _, removed = _slices(source, _payload_joint(source, payload))
    src_body = source.body(payload).id
    dst_body = carried.body(payload).id
    source_jac = _spatial_jac(source, state, src_body, state.xpos[src_body])
    wrench = np.linalg.solve(source_jac[:, removed].T, state.qfrc_applied[removed])
    # A world-space wrench at the old free-body origin verifies force transport independently.
    mujoco.mj_applyFT(
        carried,
        locked,
        wrench[:3],
        wrench[3:],
        locked.xpos[dst_body],
        dst_body,
        locked.qfrc_applied,
    )
    return _checkpoint(carried_desc, carried, locked, tick)


def _release(fixture, carried, before, tick, source_desc):
    source, _, _, _, payload = fixture
    released = mujoco.MjData(source)
    _copy_named(carried, source, before, released, before.qvel)
    position, rotation = _body_pose(carried, before, payload)
    joint_name = _payload_joint(source, payload)
    _set_free(source, released, joint_name, position, rotation)
    mujoco.mj_forward(source, released)
    old_body = carried.body(payload).id
    new_body = source.body(payload).id
    twist = np.empty(6)
    mujoco.mj_objectVelocity(
        carried, before, mujoco.mjtObj.mjOBJ_XBODY, old_body, twist, 0
    )
    _, freed = _slices(source, joint_name)
    jac = _spatial_jac(source, released, new_body, released.xpos[new_body])
    released.qvel[freed] = np.linalg.solve(jac[:, freed], np.r_[twist[3:], twist[:3]])
    return _checkpoint(source_desc, source, released, tick)


def _fixture(scene):
    articulated = scene == "articulated"
    model_names = {
        "flight": ("floating-gripper", "sample-box"),
        "flat": ("cart", "coupon"),
        "separating": ("hoist", "part"),
        "articulated": ("wrist", "workpiece"),
    }
    carrier, payload = model_names[scene]
    names = {
        "carrier": carrier,
        "payload": payload,
        "carrier_site": carrier + "-capture",
        "payload_site": payload + "-capture",
        "max_distance_m": 0.016,
        "max_angle_rad": 0.10,
    }
    tick = 349 if articulated else 1019
    zero, unit = np.zeros(3), np.eye(3)
    armature = 0.024 if articulated else 0.0
    before = _compile(
        _model(
            _carrier(carrier, "", articulated),
            _payload(payload, "", zero, unit, armature=armature),
            articulated,
        )
    )
    data = mujoco.MjData(before)
    if articulated:
        data.qpos[:3] = [0.47, 0.19, -0.51]
        data.qvel[:3] = [0.39, -1.41, 0.52]
        data.act[0], data.ctrl[0] = 0.28, 0.16
        orientation = _rotation([1, 0, 0], 0.19) @ _rotation([0, 0, 1], 0.34)
        downward = [0.48, -0.37, -0.63, -0.21, 0.64, 0.31]
    else:
        rc = _rotation([0, 0, 1], 0.31) @ _rotation([1, 0, 0], -0.19)
        _set_free(
            before,
            data,
            "moving-base",
            [-0.11, -0.08, 0.32 if scene == "flight" else 0.23],
            rc,
        )
        data.qvel[:6] = [0.37, -0.14, -0.56, 0.60, -0.79, 0.90]
        orientation = _rotation([0, 0, 1], -0.24)
        if scene != "flat":
            orientation = (
                orientation @ _rotation([1, 0, 0], -0.17) @ _rotation([0, 1, 0], 0.12)
            )
        downward = [0.06, 0.20, 0.24, -0.44, 0.75, -0.62]
    mujoco.mj_forward(before, data)
    carrier_origin, carrier_orientation = _body_pose(before, data, carrier)
    height = 0.27 if scene == "flight" else np.abs(orientation[2]) @ HALF - 0.00003
    if articulated:
        payload_origin = np.r_[carrier_origin[:2] + [0.068, 0.058], height]
    else:
        payload_origin = np.array([0.162, 0.087, height])
    joint_name = _payload_joint(before, payload)
    _set_free(before, data, joint_name, payload_origin, orientation)
    _, free = _slices(before, joint_name)
    data.qvel[free] = downward
    data.time = tick * TIMESTEP
    data.userdata[:] = [-0.18, 0.27]
    data.mocap_pos[0] = [0.67, -0.46, 0.29]
    data.mocap_quat[0] = _quat(_rotation([0, 0, 1], -0.2))
    data.qfrc_applied[:] = np.linspace(0.13, -0.06, before.nv)
    data.qacc_warmstart[:] = np.linspace(-0.16, 0.21, before.nv)
    data.xfrc_applied[before.body(carrier).id] = [0.07, -0.11, 1.32, 0.01, 0, -0.02]
    data.xfrc_applied[before.body(payload).id] = [
        -0.05,
        0.08,
        0.14,
        0.002,
        -0.017,
        0.009,
    ]
    local_site = np.array([-0.022, 0.017, 0.006])
    marker_rotation = _rotation([0, 1, 0], 0.21)
    shared_origin = payload_origin + orientation @ local_site
    shared_rotation = orientation @ marker_rotation
    if scene == "flight":
        shared_origin += [0.003, -0.002, 0.004]
        shared_rotation = shared_rotation @ _rotation([0, 0, 1], 0.057)
    root_site = _site(
        names["carrier_site"],
        carrier_orientation.T @ (shared_origin - carrier_origin),
        carrier_orientation.T @ shared_rotation,
    )
    payload_site = _site(names["payload_site"], local_site, marker_rotation)
    source = _model(
        _carrier(carrier, root_site, articulated),
        _payload(payload, payload_site, zero, unit, armature=armature),
        articulated,
    )
    attached_payload = _payload(
        payload,
        payload_site,
        carrier_orientation.T @ (payload_origin - carrier_origin),
        carrier_orientation.T @ orientation,
        attached=True,
    )
    attached = _model(
        _carrier(carrier, root_site, articulated, attached_payload), "", articulated
    )
    source_model = _compile(source)
    start = mujoco.MjData(source_model)
    for field in (
        "qpos",
        "qvel",
        "act",
        "ctrl",
        "time",
        "userdata",
        "mocap_pos",
        "mocap_quat",
        "qfrc_applied",
        "xfrc_applied",
        "qacc_warmstart",
    ):
        if field == "time":
            start.time = data.time
        else:
            getattr(start, field)[...] = getattr(data, field)
    mujoco.mj_forward(source_model, start)
    if scene == "flight":
        hand = source_model.site(names["carrier_site"]).id
        object_site = source_model.site(names["payload_site"]).id
        gap = np.linalg.norm(start.site_xpos[hand] - start.site_xpos[object_site])
        relative = start.site_xmat[hand].reshape(3, 3).T @ start.site_xmat[
            object_site
        ].reshape(3, 3)
        angle = np.arccos(np.clip((np.trace(relative) - 1) / 2, -1, 1))
        assert (
            0.004 < gap < names["max_distance_m"]
            and 0.04 < angle < names["max_angle_rad"]
        )
    if scene == "flat":
        normals = _support(source_model, start)
        assert len(normals) == 4 and min(normals @ start.qvel) > 0.1
        assert (
            min(
                normals @ _impact_without_support(source_model, start, carrier, payload)
            )
            < -0.1
        )
    if articulated:
        normals = _support(source_model, start)
        assert (
            len(normals) == 1
            and min(
                normals @ _impact_without_support(source_model, start, carrier, payload)
            )
            < -0.05
        )

    transition = tick + 26
    carry_update = {"tick": tick + 9, "set": {"mocap_pos": [[0.58, -0.37, 0.32]]}}
    if articulated:
        carry_update["set"]["ctrl"] = [-0.11]
    final = transition + 22
    release_update = {
        "tick": transition + 5,
        "set": {"mocap_pos": [[0.57, -0.37, 0.31]]},
    }
    if articulated:
        release_update["set"]["ctrl"] = [0.22]
    spec = {
        "model": source,
        "checkpoint": _checkpoint(source, source_model, start, tick),
        "latch": names,
        "carry": {
            "end": transition,
            "sample_ticks": [tick, tick + 1, tick + 12, transition],
            "checkpoint_ticks": [tick, tick + 6, transition],
            "updates": [carry_update],
        },
        "release": {
            "end": final,
            "sample_ticks": [transition, transition + 1, transition + 11, final],
            "checkpoint_ticks": [transition, transition + 8, final],
            "updates": [release_update],
        },
    }
    return spec, (source_model, start, tick, carrier, payload), attached


def _impact_without_support(model, data, carrier, payload):
    body = model.body(payload).id
    point = data.xpos[body]
    relative = _spatial_jac(model, data, body, point) - _spatial_jac(
        model, data, model.body(carrier).id, point
    )
    mass = np.empty((model.nv, model.nv))
    mujoco.mj_fullM(model, mass, data.qM)
    force = np.linalg.solve(mass, relative.T)
    return data.qvel - force @ np.linalg.solve(relative @ force, relative @ data.qvel)


def _numbers_equal(actual, expected, *, absolute=3e-6, relative=1e-6):
    return np.allclose(actual, expected, rtol=relative, atol=absolute)


def _objects_equal(actual, expected, kind, count, fields):
    old = _named(expected, kind, count)
    new = _named(actual, kind, count)
    if old.keys() != new.keys() or len(old) != count:
        return False
    for name, i in old.items():
        j = new[name]
        for field in fields:
            if not _numbers_equal(
                getattr(actual, field)[j], getattr(expected, field)[i]
            ):
                return False
    return True


def _same_model(actual, expected):
    dimensions = (
        "nbody",
        "njnt",
        "nv",
        "nq",
        "ngeom",
        "nsite",
        "nu",
        "na",
        "nmocap",
        "nuserdata",
        "neq",
        "ntendon",
        "nplugin",
        "npair",
        "nexclude",
        "nflex",
    )
    if any(getattr(actual, key) != getattr(expected, key) for key in dimensions):
        return False
    options = (
        "timestep",
        "integrator",
        "solver",
        "iterations",
        "cone",
        "gravity",
        "wind",
        "magnetic",
        "density",
        "viscosity",
        "impratio",
        "tolerance",
        "ls_iterations",
        "ls_tolerance",
        "jacobian",
        "disableflags",
        "enableflags",
        "o_margin",
        "o_solref",
        "o_solimp",
        "o_friction",
    )
    if any(
        not _numbers_equal(
            getattr(actual.opt, key),
            getattr(expected.opt, key),
            absolute=1e-12,
            relative=1e-12,
        )
        for key in options
    ):
        return False
    kinds = mujoco.mjtObj
    bodies = ("body_pos", "body_ipos", "body_mass", "body_gravcomp", "body_margin")
    joints = (
        "jnt_type",
        "jnt_pos",
        "jnt_axis",
        "jnt_stiffness",
        "jnt_range",
        "jnt_limited",
        "jnt_margin",
        "jnt_solref",
        "jnt_solimp",
        "jnt_actfrcrange",
        "jnt_actfrclimited",
    )
    geoms = (
        "geom_type",
        "geom_size",
        "geom_pos",
        "geom_friction",
        "geom_contype",
        "geom_conaffinity",
        "geom_condim",
        "geom_priority",
        "geom_solmix",
        "geom_margin",
        "geom_gap",
        "geom_solref",
        "geom_solimp",
    )
    sites = ("site_type", "site_pos", "site_size")
    actuators = (
        "actuator_actnum",
        "actuator_dyntype",
        "actuator_gaintype",
        "actuator_biastype",
        "actuator_trntype",
        "actuator_gear",
        "actuator_dynprm",
        "actuator_gainprm",
        "actuator_biasprm",
        "actuator_ctrllimited",
        "actuator_ctrlrange",
        "actuator_forcelimited",
        "actuator_forcerange",
        "actuator_actlimited",
        "actuator_actrange",
        "actuator_actearly",
    )
    named_fields = (
        (kinds.mjOBJ_BODY, expected.nbody, bodies),
        (kinds.mjOBJ_JOINT, expected.njnt, joints),
        (kinds.mjOBJ_GEOM, expected.ngeom, geoms),
        (kinds.mjOBJ_SITE, expected.nsite, sites),
        (kinds.mjOBJ_ACTUATOR, expected.nu, actuators),
    )
    if any(not _objects_equal(actual, expected, *item) for item in named_fields):
        return False
    for kind, count, owner, attitude in (
        (kinds.mjOBJ_BODY, expected.nbody, "body_parentid", "body_quat"),
        (kinds.mjOBJ_JOINT, expected.njnt, "jnt_bodyid", None),
        (kinds.mjOBJ_GEOM, expected.ngeom, "geom_bodyid", "geom_quat"),
        (kinds.mjOBJ_SITE, expected.nsite, "site_bodyid", "site_quat"),
    ):
        for name, i in _named(expected, kind, count).items():
            j = mujoco.mj_name2id(actual, kind, name)
            old_owner = mujoco.mj_id2name(
                expected, kinds.mjOBJ_BODY, getattr(expected, owner)[i]
            )
            new_owner = mujoco.mj_id2name(
                actual, kinds.mjOBJ_BODY, getattr(actual, owner)[j]
            )
            if old_owner != new_owner:
                return False
            if attitude and not _numbers_equal(
                _matrix(getattr(actual, attitude)[j]),
                _matrix(getattr(expected, attitude)[i]),
            ):
                return False
            if kind == kinds.mjOBJ_BODY:
                old_axes, new_axes = (
                    _matrix(expected.body_iquat[i]),
                    _matrix(actual.body_iquat[j]),
                )
                old_tensor = (old_axes * expected.body_inertia[i]) @ old_axes.T
                new_tensor = (new_axes * actual.body_inertia[j]) @ new_axes.T
                if not _numbers_equal(new_tensor, old_tensor):
                    return False
                if (actual.body_mocapid[j] >= 0) != (expected.body_mocapid[i] >= 0):
                    return False
            if kind == kinds.mjOBJ_JOINT:
                old_q, old_v = _slices(expected, name)
                new_q, new_v = _slices(actual, name)
                for field in (
                    "dof_damping",
                    "dof_armature",
                    "dof_frictionloss",
                    "dof_solref",
                    "dof_solimp",
                ):
                    if not _numbers_equal(
                        getattr(actual, field)[new_v], getattr(expected, field)[old_v]
                    ):
                        return False
                if expected.jnt_type[i] == mujoco.mjtJoint.mjJNT_HINGE:
                    if not _numbers_equal(actual.qpos0[new_q], expected.qpos0[old_q]):
                        return False
                    if not _numbers_equal(
                        actual.qpos_spring[new_q], expected.qpos_spring[old_q]
                    ):
                        return False
    for name, i in _named(expected, kinds.mjOBJ_ACTUATOR, expected.nu).items():
        j = mujoco.mj_name2id(actual, kinds.mjOBJ_ACTUATOR, name)
        old_joint = mujoco.mj_id2name(
            expected, kinds.mjOBJ_JOINT, expected.actuator_trnid[i, 0]
        )
        new_joint = mujoco.mj_id2name(
            actual, kinds.mjOBJ_JOINT, actual.actuator_trnid[j, 0]
        )
        if old_joint != new_joint:
            return False
    return True


def _bounded_arena(value):
    """Check an explicit native arena allocation before compiling the model."""
    root = ElementTree.Element("mujoco")
    ElementTree.SubElement(root, "size", memory=value)
    try:
        memory = mujoco.MjSpec.from_string(ElementTree.tostring(root, encoding="unicode")).memory
    except ValueError:
        return False
    return memory == mujoco.MjSpec().memory or memory <= 256 * 1024**2


def _submitted_model(description):
    if not isinstance(description, dict) or set(description) != {"xml", "assets"}:
        return None
    xml = description["xml"]
    if description["assets"] != {} or not isinstance(xml, str) or len(xml) > 30000:
        return None
    tree = ElementTree.fromstring(xml)
    if tree.tag != "mujoco":
        return None
    # These authored cases have no external assets or dynamically loaded components.
    external = {
        "include",
        "attach",
        "replicate",
        "composite",
        "flexcomp",
        "plugin",
        "extension",
    }
    for element in tree.iter():
        if element.tag in external or any(
            key.endswith("file") for key in element.attrib
        ):
            return None
        if element.tag == "size" and set(element.attrib) - {
            "nuserdata",
            "nuser_body",
            "nuser_geom",
            "nuser_jnt",
            "nuser_site",
            "nuser_actuator",
            "memory",
        }:
            return None
        if element.tag == "size":
            if "memory" in element.attrib and not _bounded_arena(element.attrib["memory"]):
                return None
            if any(int(value) > 16 for key, value in element.attrib.items() if key != "memory"):
                return None
    return _compile(description)


def _canonical_release_quaternions(actual, expected, free_q):
    """Allow either native quaternion representative for the newly restored free joint."""

    def canonical(vector, reference, start):
        if not isinstance(vector, list) or len(vector) != len(reference):
            return
        span = slice(start, start + 4)
        values = vector[span]
        if (
            all(type(value) in (float, int) for value in values)
            and np.dot(values, reference[span]) < 0
        ):
            vector[span] = [-value for value in values]

    def checkpoint(actual, expected):
        if isinstance(actual, dict):
            canonical(
                actual.get("integration"), expected["integration"], 1 + free_q.start + 3
            )

    checkpoint(actual.get("release_checkpoint"), expected["release_checkpoint"])
    after = actual.get("released")
    if not isinstance(after, dict):
        return
    for key in ("samples", "checkpoints"):
        entries = after.get(key)
        if not isinstance(entries, list):
            continue
        for data, truth in zip(entries, expected["released"][key]):
            if not isinstance(data, dict):
                continue
            if key == "samples":
                canonical(data.get("qpos"), truth["qpos"], free_q.start + 3)
            else:
                checkpoint(data, truth)


def _equal(actual, expected):
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(_equal(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_equal(a, b) for a, b in zip(actual, expected))
        )
    if isinstance(expected, (float, np.floating)):
        return (
            type(actual) in (int, float)
            and isfinite(actual)
            and abs(actual - expected) <= TOL
        )
    return type(actual) is type(expected) and actual == expected


def _expected(spec, fixture, attached_description, model):
    latch = _latch(fixture, model, attached_description)
    carry = simulated({"model": attached_description, **spec["carry"]}, latch)
    endpoint = _restore(model, carry["checkpoints"][-1])
    release = _release(fixture, model, endpoint, spec["carry"]["end"], spec["model"])
    released = simulated({"model": spec["model"], **spec["release"]}, release)
    return {
        "latch_checkpoint": latch,
        "carry": carry,
        "release_checkpoint": release,
        "released": released,
    }


def _positive(run, spec, fixture, canonical_attachment):
    actual = run("handoff", spec)
    if not isinstance(actual, dict) or set(actual) != KEYS:
        return False
    canonical_model = _compile(canonical_attachment)
    try:
        model = _submitted_model(actual["attached_model"])
        if model is None or not _same_model(model, canonical_model):
            return False
        expected = _expected(spec, fixture, actual["attached_model"], model)
        observed = deepcopy({key: actual[key] for key in expected})
        free_q, _ = _slices(fixture[0], _payload_joint(fixture[0], fixture[-1]))
        _canonical_release_quaternions(observed, expected, free_q)
        return _equal(observed, expected)
    except (
        TypeError,
        ValueError,
        KeyError,
        OverflowError,
        RuntimeError,
        ElementTree.ParseError,
        mujoco.FatalError,
    ):
        return False


def checks_handoff(run):
    outcomes = {}
    fixtures = {}
    for scene, key in (
        ("flight", "latch_floating_carry_release"),
        ("flat", "coupled_floor_latch"),
        ("separating", "separating_contact_latch"),
        ("articulated", "actuated_carrier_latch"),
    ):
        spec, fixture, canonical_attachment = _fixture(scene)
        fixtures[scene] = spec
        outcomes[key] = _positive(run, spec, fixture, canonical_attachment)
    wrong_pose = deepcopy(fixtures["flight"])
    source = _compile(wrong_pose["model"])
    free_q, _ = _slices(source, _payload_joint(source, wrong_pose["latch"]["payload"]))
    wrong_pose["checkpoint"]["integration"][1 + free_q.start] += 0.30
    wrong_site = deepcopy(fixtures["flight"])
    wrong_site["latch"]["payload_site"] = wrong_site["latch"]["carrier_site"]
    wrong_angle = deepcopy(fixtures["flight"])
    wrong_angle["latch"]["max_angle_rad"] = 0.03
    missing_end = deepcopy(fixtures["articulated"])
    missing_end["carry"]["checkpoint_ticks"].pop()
    invalid_release = deepcopy(fixtures["separating"])
    invalid_release["release"]["updates"][0]["tick"] = (
        invalid_release["release"]["end"] + 1
    )
    outcomes["reject_invalid_handoff_atomically"] = all(
        run("handoff", case, invalid=True) is True
        for case in (wrong_pose, wrong_site, wrong_angle, missing_end, invalid_release)
    )
    return outcomes
