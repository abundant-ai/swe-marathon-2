"""Prepare the compatible MJCF and preserve named state around a payload topology edit."""

from dataclasses import dataclass
from math import atan2, isfinite, pi
from xml.etree import ElementTree

import mujoco
import numpy as np

from .core import Model, name_of, object_of
from .rebase import JOINT, OBJECT, WIDTHS, matching, native_name, transfer_actuators


@dataclass(frozen=True)
class Grasp:
    """Nominal source identities and guard limits for one declared attachment."""

    carrier: str
    payload: str
    free_joint: str
    carrier_site: int
    payload_site: int
    max_distance: float
    max_angle: float


def name_id(model: mujoco.MjModel, kind: mujoco.mjtObj, value: object) -> int:
    """Resolve a required named element in the current compiled coordinate layout."""
    name = name_of(value)
    result = mujoco.mj_name2id(model, kind, name)
    if result < 0:
        raise ValueError(f"unknown model element {name!r}")
    return result


def slice_of(model: mujoco.MjModel, index: int) -> tuple[slice, slice]:
    """Return native position and tangent slices of one joint."""
    qwidth, vwidth = WIDTHS[model.jnt_type[index]]
    q, v = model.jnt_qposadr[index], model.jnt_dofadr[index]
    return slice(q, q + qwidth), slice(v, v + vwidth)


def validate_scene(model: mujoco.MjModel, raw: object) -> Grasp:
    """Check that the declared source admits a physical leaf-to-carrier edit."""
    spec = object_of(raw)
    if model.nplugin or model.ntendon or model.neq or model.nflex:
        raise ValueError("unsupported model constraints or plugin state")
    carrier, payload = (name_of(spec[key]) for key in ("carrier", "payload"))
    cb, pb = (name_id(model, OBJECT.mjOBJ_BODY, key) for key in (carrier, payload))
    if (
        cb in (0, pb)
        or model.body_weldid[cb] == 0
        or model.body_mocapid[cb] >= 0
        or model.body_rootid[cb] == pb
        or model.body_mocapid[model.body_rootid[cb]] >= 0
        or model.body_parentid[pb] != 0
        or any(model.body_parentid[1:] == pb)
    ):
        raise ValueError(
            "expected a distinct dynamic carrier and a world-root payload leaf"
        )
    free = model.body_jntadr[pb]
    if model.body_jntnum[pb] != 1 or model.jnt_type[free] != JOINT.mjJNT_FREE:
        raise ValueError("expected one payload free joint")
    if model.nu and (
        np.any(model.actuator_trntype != mujoco.mjtTrn.mjTRN_JOINT)
        or free in model.actuator_trnid[:, 0]
    ):
        raise ValueError("expected actuator transmissions on retained joints")
    cs, ps = (
        name_id(model, OBJECT.mjOBJ_SITE, spec[key])
        for key in ("carrier_site", "payload_site")
    )
    if model.site_bodyid[cs] != cb or model.site_bodyid[ps] != pb:
        raise ValueError("each latch site must belong to its declared body")
    distance, angle = (spec[key] for key in ("max_distance_m", "max_angle_rad"))
    if (
        any(
            type(x) not in (float, int) or not isfinite(x) or x < 0
            for x in (distance, angle)
        )
        or angle > pi
    ):
        raise ValueError("invalid latch-site limits")
    return Grasp(
        carrier,
        payload,
        native_name(model, OBJECT.mjOBJ_JOINT, free),
        cs,
        ps,
        float(distance),
        float(angle),
    )


def guard(data: mujoco.MjData, grasp: Grasp) -> None:
    """Reject a latch whose native site poses are outside the commissioning limits."""
    a, b = grasp.carrier_site, grasp.payload_site
    separation = np.linalg.norm(data.site_xpos[a] - data.site_xpos[b])
    r = data.site_xmat[a].reshape(3, 3).T @ data.site_xmat[b].reshape(3, 3)
    rotation_sine = 0.5 * np.linalg.norm(
        [r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]
    )
    angle = atan2(float(rotation_sine), float((np.trace(r) - 1) * 0.5))
    if separation > grasp.max_distance + 1e-12 or angle > grasp.max_angle + 1e-10:
        raise ValueError("latch sites outside capture limits")


def quaternion(rotation: np.ndarray) -> np.ndarray:
    """Encode a native proper rotation as a scalar-first unit quaternion."""
    output = np.empty(4)
    mujoco.mju_mat2Quat(output, np.ascontiguousarray(rotation.reshape(9)))
    return output


def format_vector(values: np.ndarray) -> str:
    """Serialize a world pose component with round-trip numeric precision."""
    return " ".join(format(float(x), ".17g") for x in values)


def attach(
    spec: dict, source: mujoco.MjModel, state: mujoco.MjData, grasp: Grasp
) -> dict:
    """Reparent the original payload body element at the observed carrier-relative pose."""
    root = ElementTree.fromstring(spec["xml"])
    world = root.find("worldbody")
    if world is None or any(
        next(root.iter(tag), None) is not None
        for tag in ("include", "attach", "replicate", "composite", "flexcomp", "frame")
    ):
        raise ValueError("expected an explicit editable body tree")
    compiler = root.find("compiler")
    if compiler is not None and (
        compiler.get("alignfree") == "true" or compiler.get("fusestatic") == "true"
    ):
        raise ValueError("free-body alignment and static fusion must be disabled")
    bodies = {body.get("name"): body for body in world.iter("body")}
    if len(bodies) != source.nbody - 1 or None in bodies or "" in bodies:
        raise ValueError("every physical body must have an explicit name")
    carrier, payload = bodies[grasp.carrier], bodies[grasp.payload]
    joint = next(
        (
            child
            for child in payload
            if child.tag in ("freejoint", "joint")
            and child.get("name") == grasp.free_joint
        ),
        None,
    )
    if joint is None or joint.get("align") == "true" or payload not in world:
        raise ValueError("expected an unaligned, explicit payload free joint")

    a, b = (source.body(key).id for key in (grasp.carrier, grasp.payload))
    ra, rb = (state.xmat[i].reshape(3, 3) for i in (a, b))
    position = ra.T @ (state.xpos[b] - state.xpos[a])
    relative = quaternion(ra.T @ rb)

    # Pin the old inherited defaults before reparenting under another body's childclass.
    payload.set(
        "childclass", payload.get("childclass", world.get("childclass", "main"))
    )
    for spelling in ("quat", "axisangle", "xyaxes", "zaxis", "euler"):
        payload.attrib.pop(spelling, None)
    payload.set("pos", format_vector(position))
    payload.set("quat", format_vector(relative))
    payload.remove(joint)
    world.remove(payload)
    carrier.append(payload)
    for keyframes in root.findall("keyframe"):
        root.remove(keyframes)
    return {
        "xml": ElementTree.tostring(root, encoding="unicode"),
        "assets": spec["assets"],
    }


def retained(
    before_model: mujoco.MjModel,
    after_model: mujoco.MjModel,
    before: mujoco.MjData,
    after: mujoco.MjData,
    grasp: Grasp,
) -> list[tuple[slice, slice]]:
    """Transfer unaffected named inputs and report the shared tangent blocks."""
    old, new = before_model, after_model
    for i, j in matching(old, new, OBJECT.mjOBJ_BODY, "nbody"):
        after.xfrc_applied[j] = before.xfrc_applied[i]
        a, b = old.body_mocapid[i], new.body_mocapid[j]
        if (a < 0) != (b < 0):
            raise ValueError("mocap identity changed")
        if a >= 0:
            after.mocap_pos[b] = before.mocap_pos[a]
            after.mocap_quat[b] = before.mocap_quat[a]
    removed = tuple(
        (
            {j}
            if (j := mujoco.mj_name2id(model, OBJECT.mjOBJ_JOINT, grasp.free_joint))
            >= 0
            else set()
        )
        for model in (old, new)
    )
    blocks = []
    for i, j in matching(old, new, OBJECT.mjOBJ_JOINT, "njnt", removed):
        if old.jnt_type[i] != new.jnt_type[j]:
            raise ValueError("retained joint coordinates changed")
        q0, v0 = slice_of(old, i)
        q1, v1 = slice_of(new, j)
        after.qpos[q1] = before.qpos[q0]
        after.qvel[v1] = before.qvel[v0]
        after.qfrc_applied[v1] = before.qfrc_applied[v0]
        blocks.append((v0, v1))
    transfer_actuators(old, new, before, after)
    after.time = before.time
    after.userdata[:] = before.userdata
    after.qacc_warmstart[:] = 0.0
    return blocks


def checkpoint(model: Model, data: mujoco.MjData, tick: int) -> dict:
    """Snapshot the integration fields at the caller's unadvanced event boundary."""
    return {
        "model_id": model.identity,
        "tick": tick,
        "integration": model.integration(data),
    }
