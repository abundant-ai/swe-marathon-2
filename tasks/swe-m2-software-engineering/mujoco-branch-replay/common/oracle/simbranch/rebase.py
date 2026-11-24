"""Move native checkpoint fields between compatible named MuJoCo models."""

import mujoco
import numpy as np

from .core import Model, object_of, rollout


OBJECT = mujoco.mjtObj
JOINT = mujoco.mjtJoint
EQUALITY = mujoco.mjtEq
TRANSMISSION = mujoco.mjtTrn
WIDTHS = {
    JOINT.mjJNT_FREE: (7, 6), JOINT.mjJNT_BALL: (4, 3),
    JOINT.mjJNT_SLIDE: (1, 1), JOINT.mjJNT_HINGE: (1, 1),
}
ENDPOINTS = {OBJECT.mjOBJ_BODY, OBJECT.mjOBJ_JOINT, OBJECT.mjOBJ_SITE}
EQUALITIES = {EQUALITY.mjEQ_JOINT, EQUALITY.mjEQ_CONNECT, EQUALITY.mjEQ_WELD}


def native_name(model, category, index):
    """Look up a required native identity, permitting absent equality endpoints."""
    if index == -1:
        return None
    name = mujoco.mj_id2name(model, category, index)
    if not name:
        raise ValueError("portable model entities require names")
    return name


def matching(source, target, category, count, excluded=((), ())):
    """Pair source and target native indices by entity name."""
    left = {native_name(source, category, i): i
            for i in range(getattr(source, count)) if i not in excluded[0]}
    right = {native_name(target, category, i): i
             for i in range(getattr(target, count)) if i not in excluded[1]}
    if left.keys() != right.keys():
        raise ValueError("the source and target entity names differ")
    return ((left[name], right[name]) for name in left)


def close(a, b):
    """Compare scalar or vector coordinates with a fixed absolute tolerance."""
    return np.allclose(a, b, rtol=0.0, atol=1e-12)


def move_block(source, target, first, second, width, field):
    """Write one named packed state block using model-specific offsets."""
    getattr(target, field)[second:second + width] = getattr(source, field)[first:first + width]


def transfer_bodies(left, right, captured, restored):
    """Move body wrenches and all independent mocap fields by name."""
    for source, target in matching(left, right, OBJECT.mjOBJ_BODY, "nbody"):
        parents = (native_name(left, OBJECT.mjOBJ_BODY, left.body_parentid[source]),
                   native_name(right, OBJECT.mjOBJ_BODY, right.body_parentid[target]))
        qa, qb = left.body_quat[source], right.body_quat[target]
        if (parents[0] != parents[1] or not close(left.body_pos[source], right.body_pos[target])
                or not (close(qa, qb) or close(qa, -qb))):
            raise ValueError("incompatible body frame")
        i, j = left.body_mocapid[source], right.body_mocapid[target]
        if (i < 0) != (j < 0):
            raise ValueError("mocap configuration changed")
        restored.xfrc_applied[target] = captured.xfrc_applied[source]
        if i >= 0:
            restored.mocap_pos[j] = captured.mocap_pos[i]
            restored.mocap_quat[j] = captured.mocap_quat[i]


def transfer_joints(left, right, captured, restored, excluded=((), ())):
    """Validate each joint coordinate frame and move qpos and DOF blocks."""
    for source, target in matching(left, right, OBJECT.mjOBJ_JOINT, "njnt", excluded):
        a, b = left.jnt_type[source], right.jnt_type[target]
        bodies = (native_name(left, OBJECT.mjOBJ_BODY, left.jnt_bodyid[source]),
                  native_name(right, OBJECT.mjOBJ_BODY, right.jnt_bodyid[target]))
        if (a != b or bodies[0] != bodies[1]
                or not close(left.jnt_pos[source], right.jnt_pos[target])
                or not close(left.jnt_axis[source], right.jnt_axis[target])):
            raise ValueError("incompatible joint frame")
        nq, nv = WIDTHS[a]
        i, j = left.jnt_qposadr[source], right.jnt_qposadr[target]
        if not close(left.qpos0[i:i + nq], right.qpos0[j:j + nq]):
            raise ValueError("neutral joint positions differ")
        move_block(captured, restored, i, j, nq, "qpos")
        i, j = left.jnt_dofadr[source], right.jnt_dofadr[target]
        for field in ("qvel", "qacc_warmstart", "qfrc_applied"):
            move_block(captured, restored, i, j, nv, field)


def transfer_actuators(left, right, captured, restored):
    """Preserve controls and stateful activation despite actuator declaration changes."""
    for source, target in matching(left, right, OBJECT.mjOBJ_ACTUATOR, "nu"):
        a, b = left.actuator_trntype[source], right.actuator_trntype[target]
        if a != TRANSMISSION.mjTRN_JOINT or b != a:
            raise ValueError("expected a portable joint transmission")
        actors = (native_name(left, OBJECT.mjOBJ_JOINT, left.actuator_trnid[source, 0]),
                  native_name(right, OBJECT.mjOBJ_JOINT, right.actuator_trnid[target, 0]))
        length = left.actuator_actnum[source]
        if (actors[0] != actors[1] or not close(left.actuator_gear[source], right.actuator_gear[target])
                or left.actuator_dyntype[source] != right.actuator_dyntype[target]
                or length != right.actuator_actnum[target]):
            raise ValueError("incompatible actuator")
        restored.ctrl[target] = captured.ctrl[source]
        if length:
            move_block(captured, restored, left.actuator_actadr[source],
                       right.actuator_actadr[target], length, "act")


def transfer_equalities(left, right, captured, restored):
    """Copy live enable flags for equalities with stable named endpoints."""
    for source, target in matching(left, right, OBJECT.mjOBJ_EQUALITY, "neq"):
        a, b = left.eq_type[source], right.eq_type[target]
        source_category, target_category = left.eq_objtype[source], right.eq_objtype[target]
        category = OBJECT.mjOBJ_JOINT if a == EQUALITY.mjEQ_JOINT else source_category
        if a != b or a not in EQUALITIES or category not in ENDPOINTS or source_category != target_category:
            raise ValueError("unsupported or incompatible equality")
        for index in ("eq_obj1id", "eq_obj2id"):
            first = native_name(left, category, getattr(left, index)[source])
            second = native_name(right, category, getattr(right, index)[target])
            if first != second:
                raise ValueError("equality endpoint changed")
        restored.eq_active[target] = captured.eq_active[source]


def migration_inputs(spec):
    source, target = (
        Model.compile(spec["source_model"]), Model.compile(spec["target_model"]),
    )
    left, right = source.native, target.native
    if (left.nplugin or right.nplugin or left.nuserdata != right.nuserdata
            or not close(left.opt.timestep, right.opt.timestep)):
        raise ValueError("incompatible integration ABI")
    tick, captured = source.start(object_of(spec["checkpoint"]))
    return source, target, tick, captured


def transfer_retained(left, right, captured, restored, excluded=((), ())):
    transfer_bodies(left, right, captured, restored)
    transfer_joints(left, right, captured, restored, excluded)
    transfer_actuators(left, right, captured, restored)
    transfer_equalities(left, right, captured, restored)
    restored.time = captured.time
    restored.userdata[:] = captured.userdata


def migration_result(target, tick, restored, spec):
    checkpoint = {"model_id": target.identity, "tick": tick, "integration": target.integration(restored)}
    return {"checkpoint": checkpoint,
            "resumed": rollout(target, spec, checkpoint=checkpoint, checkpoints=True)}


def rebase(spec):
    """Migrate a complete integration checkpoint and continue in target native order."""
    source, target, tick, captured = migration_inputs(spec)
    restored = mujoco.MjData(target.native)
    transfer_retained(source.native, target.native, captured, restored)
    return migration_result(target, tick, restored, spec)
