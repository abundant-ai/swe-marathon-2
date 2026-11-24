"""Replay a native rigid latch, carry, and release."""

from itertools import combinations

import mujoco
import numpy as np

from .core import Model, object_of, rollout, selection, tick_of
from .handoff_model import (
    Grasp,
    attach,
    checkpoint,
    guard,
    quaternion,
    retained,
    slice_of,
    validate_scene,
)


def jacobian(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    body: int,
    point: np.ndarray | None = None,
) -> np.ndarray:
    """Map native velocities to world linear and angular velocity at the selected body point."""
    jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    if body:
        reference = data.xpos[body] if point is None else point
        mujoco.mj_jac(model, data, jacp, jacr, reference, body)
    return np.vstack((jacp, jacr))


def mass_matrix(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    """Expand the current compiled native inertia from a forwarded state."""
    matrix = np.empty((model.nv, model.nv))
    mujoco.mj_fullM(model, matrix, data.qM)
    return matrix


def support_rows(
    model: mujoco.MjModel, data: mujoco.MjData, lift: np.ndarray
) -> np.ndarray:
    """Return reduced separation-speed rows for touching native contact features.

    The current source contact manifold is read before the topology event. A
    source contact may impose no restriction after the two frames are welded.
    """
    rows = []
    for contact in data.contact:
        if contact.dist > 0.0:
            continue
        a, b = model.geom_bodyid[[contact.geom1, contact.geom2]]
        first = jacobian(model, data, a, contact.pos)[:3]
        second = jacobian(model, data, b, contact.pos)[:3]
        row = contact.frame[:3] @ (second - first) @ lift
        if np.linalg.norm(row) > 1e-12:
            rows.append(row)
    if len(rows) > 8:
        raise ValueError("latch has more than eight nonzero touching contact rows")
    return np.asarray(rows).reshape(-1, lift.shape[1])


def support_projection(
    mass: np.ndarray, free: np.ndarray, rows: np.ndarray
) -> np.ndarray:
    """Project a candidate reduced velocity onto the compressive support cone.

    Enumerate the small set of possible active contact features. Compare primal
    solutions because redundant contact rows need not have unique multipliers.
    """
    separation = rows @ free
    if np.all(separation >= -1e-10):
        return free
    mobility = np.linalg.solve(mass, rows.T)
    contacts = rows @ mobility
    best = None
    best_cost = np.inf
    for count in range(1, len(rows) + 1):
        for selected in combinations(range(len(rows)), count):
            active = np.asarray(selected)
            force = np.linalg.lstsq(
                contacts[np.ix_(active, active)], -separation[active], rcond=None
            )[0]
            if np.any(force < -1e-9):
                continue
            delta = mobility[:, active] @ force
            trial = free + delta
            after = rows @ trial
            if max(np.abs(after[active])) > 1e-8 or min(after) < -1e-8:
                continue
            cost = delta @ mass @ delta
            if cost < best_cost:
                best, best_cost = trial, cost
    if best is None:
        raise ValueError("no admissible latch impulse")
    return best


def latch_state(
    source: Model, target: Model, before: mujoco.MjData, grasp: Grasp
) -> mujoco.MjData:
    """Build a reduced checkpoint from the measured pose and constrained momentum."""
    old, new = source.native, target.native
    after = mujoco.MjData(new)
    shared = retained(old, new, before, after, grasp)
    mujoco.mj_forward(new, after)
    original_body, new_body = (m.body(grasp.payload).id for m in (old, new))
    if (
        new.body_jntnum[new_body]
        or new.body_parentid[new_body] != new.body(grasp.carrier).id
        or not np.allclose(
            before.xpos[original_body], after.xpos[new_body], atol=1e-8, rtol=0
        )
        or not np.allclose(
            before.xmat[original_body], after.xmat[new_body], atol=1e-8, rtol=0
        )
    ):
        raise ValueError("compiled attachment does not preserve payload pose")

    _, freed = slice_of(old, old.joint(grasp.free_joint).id)
    E = np.zeros((old.nv, new.nv))
    for src, dst in shared:
        E[src, dst] = np.eye(src.stop - src.start)
    payload_velocity = jacobian(new, after, new_body)
    E[freed, :] = np.linalg.solve(
        jacobian(old, before, original_body)[:, freed], payload_velocity
    )

    source_mass = mass_matrix(old, before)
    impact_mass = E.T @ (source_mass @ E)
    incoming = E.T @ (source_mass @ before.qvel)
    free = np.linalg.solve(impact_mass, incoming)
    after.qvel[:] = support_projection(impact_mass, free, support_rows(old, before, E))
    after.qfrc_applied[:] = E.T @ before.qfrc_applied
    return after


def release_state(
    carried: Model, original: Model, before: mujoco.MjData, grasp: Grasp
) -> mujoco.MjData:
    """Return the payload to its original free chart with the instantaneous carried twist."""
    old, new = carried.native, original.native
    outgoing = mujoco.MjData(new)
    retained(old, new, before, outgoing, grasp)
    mujoco.mj_forward(old, before)
    a, b = (m.body(grasp.payload).id for m in (old, new))
    pose, dofs = slice_of(new, new.joint(grasp.free_joint).id)
    outgoing.qpos[pose] = np.r_[
        before.xpos[a], quaternion(before.xmat[a].reshape(3, 3))
    ]
    mujoco.mj_kinematics(new, outgoing)
    mujoco.mj_comPos(new, outgoing)
    inherited = jacobian(old, before, a) @ before.qvel
    outgoing.qvel[dofs] = np.linalg.solve(
        jacobian(new, outgoing, b)[:, dofs], inherited
    )
    outgoing.qfrc_applied[dofs] = 0.0
    return outgoing


def handoff(spec: dict) -> dict:
    """Perform the two exact event resets and native carry/release segments."""
    original_spec = object_of(spec["model"])
    source = Model.compile(original_spec)
    grasp = validate_scene(source.native, spec["latch"])
    start, before = source.start(object_of(spec["checkpoint"]))
    carrying, released = (object_of(spec[key]) for key in ("carry", "release"))
    release_tick = tick_of(carrying["end"], start + 1)
    tick_of(released["end"], release_tick + 1)
    if release_tick not in selection(carrying["checkpoint_ticks"], start, release_tick):
        raise ValueError("carry must save a checkpoint at the release boundary")

    mujoco.mj_forward(source.native, before)
    guard(before, grasp)
    attached_spec = attach(original_spec, source.native, before, grasp)
    attached = Model.compile(attached_spec)
    latched = checkpoint(attached, latch_state(source, attached, before, grasp), start)
    carry_report = rollout(attached, carrying, checkpoint=latched, checkpoints=True)
    _, carried = attached.start(carry_report["checkpoints"][-1])
    detached = checkpoint(
        source, release_state(attached, source, carried, grasp), release_tick
    )
    release_report = rollout(source, released, checkpoint=detached, checkpoints=True)
    return {
        "attached_model": attached_spec,
        "latch_checkpoint": latched,
        "carry": carry_report,
        "release_checkpoint": detached,
        "released": release_report,
    }
