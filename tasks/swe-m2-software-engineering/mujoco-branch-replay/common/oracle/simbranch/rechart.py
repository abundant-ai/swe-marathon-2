"""Preserve the physical checkpoint state across paired root-body coordinate charts."""

from dataclasses import dataclass
import math

import mujoco
import numpy as np

from .core import list_of, name_of, object_of
from .rebase import (EQUALITY, JOINT, OBJECT, close, migration_inputs, migration_result,
                     transfer_retained)


MIN_RANK = 1e-4


@dataclass(frozen=True)
class Chart:
    body: int
    joints: tuple[int, ...]
    positions: np.ndarray
    dofs: np.ndarray
    free: bool


def identify(model, kind, name):
    index = mujoco.mj_name2id(model, kind, name_of(name))
    if index < 0:
        raise ValueError(f"unknown chart entity {name}")
    return index


def chart(model, body_name, descriptor):
    body = identify(model, OBJECT.mjOBJ_BODY, body_name)
    if body == 0 or model.body_parentid[body] != 0 or model.body_mocapid[body] >= 0:
        raise ValueError("converted bodies must be physical children of world")
    descriptor = object_of(descriptor)
    begin, count = model.body_jntadr[body], model.body_jntnum[body]
    if set(descriptor) == {"free_joint"}:
        joints = (identify(model, OBJECT.mjOBJ_JOINT, descriptor["free_joint"]),)
        if count != 1 or joints != (begin,) or model.jnt_type[begin] != JOINT.mjJNT_FREE:
            raise ValueError("free descriptor must name the root body's sole free joint")
        p,v = model.jnt_qposadr[begin],model.jnt_dofadr[begin]
        return Chart(body,joints,np.arange(p,p+7),np.arange(v,v+6),True)
    if set(descriptor) != {"slides", "hinges"}:
        raise ValueError("invalid chart descriptor")
    slides, hinges = list_of(descriptor["slides"]), list_of(descriptor["hinges"])
    if len(slides) != 3 or len(hinges) != 3:
        raise ValueError("scalar chart needs three slides and three hinges")
    joints = tuple(identify(model,OBJECT.mjOBJ_JOINT,name) for name in slides+hinges)
    if count != 6 or joints != tuple(range(begin,begin+count)):
        raise ValueError("describe the six scalar joints in compiled order")
    ids = np.asarray(joints)
    kinds = [JOINT.mjJNT_SLIDE]*3+[JOINT.mjJNT_HINGE]*3
    if not np.array_equal(model.jnt_type[ids],kinds) or np.any(model.jnt_limited[ids]):
        raise ValueError("expected an unlimited scalar chart")
    linear, angular = model.jnt_axis[ids[:3]],model.jnt_axis[ids[3:]]
    if not close(linear@linear.T,np.eye(3)) or not close(angular@angular.T,np.eye(3)):
        raise ValueError("scalar chart axes must be orthonormal")
    if not close(model.jnt_pos[ids[3:]],model.jnt_pos[ids[3]]):
        raise ValueError("hinges must share one local pivot")
    return Chart(body,joints,model.jnt_qposadr[ids],model.jnt_dofadr[ids],False)


def axes(model, descriptor):
    begin = descriptor.joints[0]
    return model.jnt_axis[begin:begin+3],model.jnt_axis[begin+3:begin+6]


def body_rotation(data, chart):
    return data.xmat[chart.body].reshape(3,3)


def angle(value):
    return (value+math.pi)%(2*math.pi)-math.pi


def place(model, data, descriptor, xyz, rotation):
    if descriptor.free:
        quaternion = np.empty(4)
        mujoco.mju_mat2Quat(quaternion,np.ascontiguousarray(rotation.ravel()))
        for coefficient in quaternion:
            if coefficient != 0:
                if coefficient < 0:
                    quaternion *= -1
                break
        data.qpos[descriptor.positions] = np.r_[xyz,quaternion]
        return
    slide, hinge = axes(model,descriptor)
    previous = np.empty(9)
    mujoco.mju_quat2Mat(previous,model.body_quat[descriptor.body])
    zero = previous.reshape(3,3)
    cross = np.cross(hinge[0],hinge[1])
    basis = np.column_stack((hinge[0],hinge[1],cross))
    mat = basis.T@zero.T@rotation@basis
    middle = math.asin(float(np.clip(mat[0,2],-1.,1.)))
    if abs(math.cos(middle)) < MIN_RANK:
        raise ValueError("singular rotation at scalar chart")
    turn0 = math.atan2(-mat[1,2],mat[2,2])
    turn2 = (cross@hinge[2])*math.atan2(-mat[0,1],mat[0,0])
    pivot = model.jnt_pos[descriptor.joints[3]]
    before = xyz-(zero-rotation)@pivot
    z = zero.T@(before-model.body_pos[descriptor.body])
    data.qpos[descriptor.positions] = model.qpos0[descriptor.positions]+np.r_[
        slide@z,angle(turn0),middle,angle(turn2)]


def jacobian(model,data,descriptor, *, change=False):
    body = descriptor.body
    linear = np.empty((3,model.nv))
    angular = np.empty((3,model.nv))
    operation = mujoco.mj_jacDot if change else mujoco.mj_jac
    operation(model,data,linear,angular,data.xpos[body],body)
    return np.vstack((linear,angular))[:,descriptor.dofs]


def reject_bound_joint(model, excluded):
    if any(int(j) in excluded for j in model.actuator_trnid[:,0]):
        raise ValueError("actuator addresses a converted joint")
    for i, kind in enumerate(model.eq_type):
        if kind == EQUALITY.mjEQ_JOINT and (model.eq_obj1id[i] in excluded or model.eq_obj2id[i] in excluded):
            raise ValueError("joint equality addresses a converted joint")


def refresh(model, data):
    mujoco.mj_kinematics(model,data)
    mujoco.mj_comPos(model,data)
    mujoco.mj_comVel(model,data)


def rechart(spec):
    source,target,tick,capture = migration_inputs(spec)
    left,right = source.native,target.native
    transfers = []
    source_joint_ids,target_joint_ids = set(),set()
    for row in list_of(spec["charts"]):
        item = object_of(row)
        a,b = chart(left,item["body"],item["source"]),chart(right,item["body"],item["target"])
        if a.free == b.free or source_joint_ids.intersection(a.joints) or target_joint_ids.intersection(b.joints):
            raise ValueError("each body must change chart once")
        source_joint_ids.update(a.joints)
        target_joint_ids.update(b.joints)
        transfers.append((a,b))
    if not transfers:
        raise ValueError("expected at least one converted root body")
    reject_bound_joint(left,source_joint_ids)
    reject_bound_joint(right,target_joint_ids)
    out = mujoco.MjData(right)
    transfer_retained(left,right,capture,out,(source_joint_ids,target_joint_ids))
    refresh(left,capture)
    for a,b in transfers:
        place(right,out,b,capture.xpos[a.body],body_rotation(capture,a))
    refresh(right,out)
    for a,b in transfers:
        js,jt = jacobian(left,capture,a),jacobian(right,out,b)
        if min(np.linalg.svd(j,compute_uv=False)[-1] for j in (js,jt))<MIN_RANK:
            raise ValueError("singular chart Jacobian")
        tangent = np.linalg.solve(jt,js)
        out.qvel[b.dofs] = tangent@capture.qvel[a.dofs]
        out.qfrc_applied[b.dofs] = np.linalg.solve(tangent.T,capture.qfrc_applied[a.dofs])
        mujoco.mj_comVel(right,out)
        source_bias = jacobian(left,capture,a,change=True)@capture.qvel[a.dofs]
        target_bias = jacobian(right,out,b,change=True)@out.qvel[b.dofs]
        out.qacc_warmstart[b.dofs] = (tangent@capture.qacc_warmstart[a.dofs]
                                      +np.linalg.solve(jt,source_bias-target_bias))
    return migration_result(target,tick,out,spec)
