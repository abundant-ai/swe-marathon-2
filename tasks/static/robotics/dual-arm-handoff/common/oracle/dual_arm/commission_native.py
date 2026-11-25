"""Commission UR5e base and marker frames from independent pose observations."""

from dataclasses import dataclass
from math import isfinite

import mujoco
import numpy as np

SIDES = ("left", "right")


def scalar(value):
    """Read a finite JSON number without treating booleans as measurements."""
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("expected finite metrology number")
    return float(value)


def vector(value, width):
    """Read one measurement vector with its declared width."""
    if type(value) is not list or len(value) != width:
        raise ValueError("wrong metrology vector width")
    return np.asarray([scalar(component) for component in value])


def pose(rotation, translation):
    """Combine a rotation and translation into a homogeneous pose."""
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    return transform


def rotation_from_xyzw(value):
    """Convert a normalized world-frame quaternion to a native rotation matrix."""
    q = vector(value, 4)
    scale = np.max(np.abs(q))
    if scale == 0:
        raise ValueError("zero marker quaternion")
    unit = q / scale
    unit /= np.linalg.norm(unit)
    rotation = np.empty(9)
    mujoco.mju_quat2Mat(rotation, unit[[3, 0, 1, 2]])
    return rotation.reshape(3, 3)


def pose_from_json(value):
    """Decode a metrology pose using explicit metres and xyzw order."""
    if type(value) is not dict:
        raise ValueError("marker pose must be an object")
    return pose(
        rotation_from_xyzw(value["quaternion_xyzw"]), vector(value["translation_m"], 3)
    )


def pose_to_json(transform):
    """Encode a rigid pose using xyzw quaternion order."""
    q = np.empty(4)
    mujoco.mju_mat2Quat(q, transform[:3, :3].ravel())
    return {
        "translation_m": transform[:3, 3].tolist(),
        "quaternion_xyzw": q[[1, 2, 3, 0]].tolist(),
    }


def inverse(transforms):
    """Invert one or more SE(3) transforms analytically."""
    result = np.array(transforms, copy=True)
    rotation = np.swapaxes(transforms[..., :3, :3], -1, -2)
    result[..., :3, :3] = rotation
    result[..., :3, 3] = -np.einsum(
        "...ij,...j->...i", rotation, transforms[..., :3, 3]
    )
    return result


def project(rotation):
    """Find the nearest proper rotation matrix."""
    u, _, vt = np.linalg.svd(rotation)
    u[:, -1] *= np.linalg.det(u @ vt)
    return u @ vt


def rotation_logs(rotations):
    """Return SO(3) rotation vectors, including rotations near a half turn."""
    skew = 0.5 * np.stack(
        (
            rotations[..., 2, 1] - rotations[..., 1, 2],
            rotations[..., 0, 2] - rotations[..., 2, 0],
            rotations[..., 1, 0] - rotations[..., 0, 1],
        ),
        axis=-1,
    )
    sine = np.linalg.norm(skew, axis=-1)
    cosine = 0.5 * (np.trace(rotations, axis1=-2, axis2=-1) - 1)
    angles = np.arctan2(sine, cosine)
    factor = np.ones_like(sine)
    np.divide(angles, sine, where=sine > 1e-12, out=factor)
    logs = skew * factor[..., None]
    near_pi = (sine < 1e-6) & (cosine < 0)
    for index in zip(*np.nonzero(near_pi), strict=True):
        q = np.empty(4)
        mujoco.mju_mat2Quat(q, rotations[index].ravel())
        if q[0] < 0:
            q = -q
        logs[index] = q[1:] * (angles[index] / np.linalg.norm(q[1:]))
    return logs


def delta_pose(delta):
    """Use a local pose correction with a rotation-vector increment."""
    angular = delta[3:]
    angle = np.linalg.norm(angular)
    rotation = np.eye(3)
    if angle:
        q = np.empty(4)
        mujoco.mju_axisAngle2Quat(q, angular / angle, angle)
        matrix = np.empty(9)
        mujoco.mju_quat2Mat(matrix, q)
        rotation = matrix.reshape(3, 3)
    return pose(rotation, delta[:3])


@dataclass(frozen=True)
class Capture:
    """Known arm flange and independently measured world marker poses."""

    flange: np.ndarray
    marker: np.ndarray

    def subset(self, indices):
        """Select capture rows without changing their correspondence."""
        return Capture(self.flange[indices], self.marker[indices])

    def __len__(self):
        return len(self.flange)


def read_capture(raw, model, data, site):
    """Run native six-axis kinematics for each measured encoder position."""
    if type(raw) is not list:
        raise ValueError("capture must be an array")
    flange = []
    marker = []
    for row in raw:
        if type(row) is not dict:
            raise ValueError("capture row must be an object")
        data.qpos[:] = vector(row["q"], 6)
        mujoco.mj_kinematics(model, data)
        flange.append(pose(data.site_xmat[site].reshape(3, 3), data.site_xpos[site]))
        marker.append(pose_from_json(row["marker"]))
    return Capture(
        np.asarray(flange).reshape(-1, 4, 4), np.asarray(marker).reshape(-1, 4, 4)
    )


def informative(flange):
    """Require relative rotation around at least two independent axes."""
    if len(flange) < 3:
        return False
    relative = inverse(flange[0]) @ flange[1:]
    strength = np.linalg.svd(rotation_logs(relative[:, :3, :3]), compute_uv=False)
    return strength[1] > 1e-5 * np.sqrt(len(relative))


def initial(capture):
    """Solve the tool transform from relative poses, then reconstruct the base."""
    if not informative(capture.flange):
        return None
    a = inverse(capture.flange[0]) @ capture.flange[1:]
    b = inverse(capture.marker[0]) @ capture.marker[1:]
    identity = np.eye(3)
    system = np.concatenate(
        [
            np.kron(ra[:3, :3], identity) - np.kron(identity, rb[:3, :3].T)
            for ra, rb in zip(a, b, strict=True)
        ]
    )
    _, singular, vt = np.linalg.svd(system, full_matrices=False)
    if singular[-2] <= 1e-5 * np.sqrt(len(a)):
        return None
    matrix = vt[-1].reshape(3, 3)
    if np.linalg.det(matrix) < 0:
        matrix = -matrix
    tool_rotation = project(matrix)
    lhs = (a[:, :3, :3] - identity).reshape(-1, 3)
    rhs = (b[:, :3, 3] @ tool_rotation.T - a[:, :3, 3]).ravel()
    offset, _, rank, _ = np.linalg.lstsq(lhs, rhs, rcond=1e-9)
    if rank < 3:
        return None
    tool = pose(tool_rotation, offset)
    worlds = capture.marker @ inverse(capture.flange @ tool)
    world = pose(
        project(np.sum(worlds[:, :3, :3], axis=0)), np.mean(worlds[:, :3, 3], axis=0)
    )
    return world, tool


def errors(capture, transform):
    """Measure physical translation and geodesic orientation residuals."""
    world, tool = transform
    predicted = world @ capture.flange @ tool
    relative = predicted[:, :3, :3] @ np.swapaxes(capture.marker[:, :3, :3], 1, 2)
    return predicted[:, :3, 3] - capture.marker[:, :3, 3], rotation_logs(relative)


def refine(capture, transform, thresholds):
    """Jointly refine base and tool poses on the selected inlier capture."""
    diag = np.diag(np.full(12, 1e-6))

    def residual(current):
        dist, angles = errors(capture, current)
        return np.concatenate(
            (dist.ravel() / thresholds[0], angles.ravel() / thresholds[1])
        )

    def update(current, step):
        return delta_pose(step[:6]) @ current[0], delta_pose(step[6:]) @ current[1]

    for _ in range(12):
        residual_now = residual(transform)
        jac = np.column_stack(
            [(residual(update(transform, step)) - residual_now) / 1e-6 for step in diag]
        )
        step = np.linalg.lstsq(jac, -residual_now, rcond=1e-8)[0]
        if np.linalg.norm(step) < 1e-11:
            break
        for scale in (1.0, 0.5, 0.25, 0.125):
            proposal = update(transform, step * scale)
            if np.linalg.norm(residual(proposal)) < np.linalg.norm(residual_now):
                transform = proposal
                break
        else:
            break
    return transform


def inliers(capture, transform, thresholds):
    """Classify each row against both fit thresholds in physical units."""
    error = np.stack(
        [np.linalg.norm(value, axis=1) for value in errors(capture, transform)], axis=1
    )
    mask = np.all(error <= thresholds, axis=1)
    return mask, (
        int(np.count_nonzero(mask)),
        -float(np.sum((error[mask] / thresholds) ** 2)),
    )


def robust_fit(capture, minimum, thresholds):
    """Select a deterministic robust consensus and require observable inliers."""
    if len(capture) < minimum or not informative(capture.flange):
        return None
    random = np.random.default_rng(31867)
    best = None
    best_score = (0, 0.0)
    selections = [np.arange(len(capture))]
    selections.extend(
        random.choice(len(capture), size=4, replace=False) for _ in range(96)
    )
    for subset in selections:
        candidate = initial(capture.subset(subset))
        if candidate is None:
            continue
        mask, score = inliers(capture, candidate, thresholds)
        if (
            score > best_score
            and score[0] >= minimum
            and informative(capture.flange[mask])
        ):
            best = candidate, mask
            best_score = score
            if score[0] == len(capture):
                break
    if best is None:
        return None
    fitted, mask = best
    for _ in range(3):
        proposal = refine(capture.subset(mask), fitted, thresholds)
        refined_mask, score = inliers(capture, proposal, thresholds)
        if score < best_score or not informative(capture.flange[refined_mask]):
            break
        improved = not np.array_equal(mask, refined_mask)
        fitted, mask, best_score = proposal, refined_mask, score
        if not improved:
            break
    return fitted, best_score[0]


def commission_native(spec):
    """Fit metrology using the fit rows and evaluate separate validation rows."""
    if type(spec) is not dict or type(spec["robot_xml"]) is not str:
        raise ValueError("expected a native robot model and calibration request")
    try:
        model = mujoco.MjModel.from_xml_string(spec["robot_xml"])
    except (ValueError, mujoco.FatalError) as error:
        raise ValueError("invalid native robot model") from error
    if (
        model.nq != 6
        or model.njnt != 6
        or np.any(model.jnt_type != mujoco.mjtJoint.mjJNT_HINGE)
    ):
        raise ValueError("native model must contain six hinged joints")
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "attachment_site")
    if site < 0:
        raise ValueError("native model has no attachment_site")
    data = mujoco.MjData(model)
    minimum = spec["min_inliers"]
    if type(minimum) is not int or minimum < 6:
        raise ValueError("min_inliers must be an integer of at least six")
    fit_bounds = np.asarray(
        [scalar(spec[k]) for k in ("fit_threshold_m", "fit_threshold_rad")]
    )
    validation_bounds = np.asarray(
        [
            scalar(spec[k])
            for k in ("validation_threshold_m", "validation_threshold_rad")
        ]
    )
    if np.any(fit_bounds <= 0) or np.any(validation_bounds <= 0):
        raise ValueError("metrology thresholds must be positive")
    supplied = spec["captures"]
    if type(supplied) is not dict or set(supplied) != set(SIDES):
        raise ValueError("expected independent captures for left and right arms")
    captures = {}
    for side in SIDES:
        group = supplied[side]
        if type(group) is not dict:
            raise ValueError("metrology group must be an object")
        fit, validation = (
            read_capture(group[key], model, data, site) for key in ("fit", "validation")
        )
        if not len(validation):
            raise ValueError("validation capture must contain at least one pose")
        captures[side] = fit, validation

    reports, validation_reports = {}, {}
    status = "ok"
    for side, (fit, validation) in captures.items():
        result = robust_fit(fit, minimum, fit_bounds)
        if result is None:
            return {"status": "unidentifiable", "calibration": None, "validation": None}
        transform, supported = result
        reports[side] = {
            "world_from_base": pose_to_json(transform[0]),
            "flange_from_marker": pose_to_json(transform[1]),
            "inliers": supported,
        }
        values = [
            float(np.sqrt(np.mean(np.sum(value**2, axis=1))))
            for value in errors(validation, transform)
        ]
        validation_reports[side] = {
            "translation_rmse_m": values[0],
            "rotation_rmse_rad": values[1],
        }
        if np.any(np.asarray(values) > validation_bounds):
            status = "validation_failed"
    return {"status": status, "calibration": reports, "validation": validation_reports}
