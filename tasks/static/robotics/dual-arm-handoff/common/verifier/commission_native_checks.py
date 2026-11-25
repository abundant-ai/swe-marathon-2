"""Verify two calibrated physical UR5e frames against independent measurements."""

from copy import deepcopy
from math import atan2, cos, sin, sqrt

import mujoco
import numpy as np

SIDES = ("left", "right")


def axis_rotation(axis, angle):
    """Build a proper rotation from controlled metrology perturbations."""
    x, y, z = np.asarray(axis) / np.linalg.norm(axis)
    skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + sin(angle) * skew + (1.0 - cos(angle)) * (skew @ skew)


def rigid(rotation, center):
    """Build one rigid calibration truth pose in homogeneous coordinates."""
    result = np.eye(4)
    result[:3, :3] = rotation
    result[:3, 3] = center
    return result


def quaternion(rotation):
    """Derive a unit quaternion through the independent largest-component formula."""
    r = rotation
    squared = np.array(
        [
            1 + r[0, 0] - r[1, 1] - r[2, 2],
            1 - r[0, 0] + r[1, 1] - r[2, 2],
            1 - r[0, 0] - r[1, 1] + r[2, 2],
            1 + r[0, 0] + r[1, 1] + r[2, 2],
        ]
    )
    largest = int(np.argmax(squared))
    products = np.array(
        [
            [squared[0], r[0, 1] + r[1, 0], r[0, 2] + r[2, 0], r[2, 1] - r[1, 2]],
            [r[1, 0] + r[0, 1], squared[1], r[1, 2] + r[2, 1], r[0, 2] - r[2, 0]],
            [r[2, 0] + r[0, 2], r[2, 1] + r[1, 2], squared[2], r[1, 0] - r[0, 1]],
            [r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1], squared[3]],
        ]
    )
    q = products[largest] / (2 * sqrt(squared[largest]))
    return q / np.linalg.norm(q)


def wire_pose(transform, *, sign=1):
    """Serialize one metrology sample with the selected quaternion sign."""
    return {
        "translation_m": transform[:3, 3].tolist(),
        "quaternion_xyzw": (sign * quaternion(transform[:3, :3])).tolist(),
    }


def reported_pose(item):
    """Decode and validate a candidate-exported rigid pose."""
    raw_center, raw_quaternion = item["translation_m"], item["quaternion_xyzw"]
    if (
        type(raw_center) is not list
        or type(raw_quaternion) is not list
        or any(type(value) not in (int, float) for value in raw_center + raw_quaternion)
    ):
        raise ValueError("native calibration pose must contain plain numeric arrays")
    center = np.asarray(raw_center, dtype=float)
    q = np.asarray(raw_quaternion, dtype=float)
    if (
        center.shape != (3,)
        or q.shape != (4,)
        or not np.all(np.isfinite(center))
        or not np.all(np.isfinite(q))
    ):
        raise ValueError("invalid reported native calibration pose")
    if abs(np.linalg.norm(q) - 1.0) > 1e-6:
        raise ValueError("non-unit reported native calibration quaternion")
    x, y, z, w = q
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )
    return rigid(rotation, center)


def error(estimated, actual):
    """Compute translation norm and unsigned geodesic angle without pose libraries."""
    rotation = estimated[:3, :3] @ actual[:3, :3].T
    sine = 0.5 * np.linalg.norm(
        [
            rotation[2, 1] - rotation[1, 2],
            rotation[0, 2] - rotation[2, 0],
            rotation[1, 0] - rotation[0, 1],
        ]
    )
    cosine = 0.5 * float(np.trace(rotation) - 1.0)
    return np.linalg.norm(estimated[:3, 3] - actual[:3, 3]), atan2(sine, cosine)


def fk(model, data, joint_angles):
    """Read native site measurements independently of the calibration solver."""
    data.qpos[:] = joint_angles
    mujoco.mj_forward(model, data)
    site = data.site("attachment_site")
    return rigid(site.xmat.reshape(3, 3), site.xpos)


def commission_fixture(robot_xml, *, seed=78):
    """Create distinct metrology captures from planted paired UR5e frame transforms."""
    model = mujoco.MjModel.from_xml_string(robot_xml)
    data = mujoco.MjData(model)
    rng = np.random.default_rng(seed)
    reference_pose = np.array([-0.7, -1.18, 1.45, -0.89, 0.64, -0.32])
    captures, truth = {}, {}
    for i, side in enumerate(SIDES):
        base_angle = [0.76, -2.76][i] if seed == 78 else [-2.92, 1.11][i]
        base_center = [-0.61, 0.17, 0.21] if side == "left" else [0.74, -0.19, 0.27]
        world = rigid(
            axis_rotation([0.31, (-1) ** i * 0.49, 0.87], base_angle), base_center
        )
        flange_angle = [-0.44, 1.92][i] if seed == 78 else [2.90, -0.61][i]
        tool = rigid(
            axis_rotation([0.77, -0.39, (-1) ** i * 0.26], flange_angle),
            [0.026 - 0.07 * i, 0.028, 0.098 + 0.014 * i],
        )
        rejected = set(rng.choice(27, size=4 + i, replace=False))
        groups = {}
        for phase, count in (("fit", 27), ("validation", 12)):
            rows = []
            for j in range(count):
                center = reference_pose + (
                    0.3 if phase == "validation" else 0.0
                ) * np.array([1, 1, -1, 1, 1, -1])
                q = center + rng.uniform(-0.74, 0.74, 6)
                actual = world @ fk(model, data, q) @ tool
                if phase == "fit":
                    actual[:3, 3] += rng.normal(0.0, 0.00020, 3)
                    actual[:3, :3] = (
                        axis_rotation(rng.normal(size=3), rng.normal(0.0, 0.00045))
                        @ actual[:3, :3]
                    )
                    if j in rejected:
                        actual[:3, 3] += (
                            [0.026, -0.033, 0.021] if i == 0 else [-0.041, 0.031, 0.09]
                        )
                        actual[:3, :3] = (
                            axis_rotation([1.0, -0.2, 0.53], 0.19 if i else -0.31)
                            @ actual[:3, :3]
                        )
                rows.append(
                    {"q": q.tolist(), "marker": wire_pose(actual, sign=(-1) ** j)}
                )
            groups[phase] = rows
        captures[side] = groups
        truth[side] = {
            "world_from_base": wire_pose(world),
            "flange_from_marker": wire_pose(tool),
            "inliers": 27 - len(rejected),
        }
    spec = {
        "robot_xml": robot_xml,
        "captures": captures,
        "min_inliers": 16,
        "fit_threshold_m": 0.0025,
        "fit_threshold_rad": 0.007,
        "validation_threshold_m": 0.002,
        "validation_threshold_rad": 0.006,
    }
    return spec, truth


def validate_fit(report, spec, truth, expected_status):
    """Grade actual transforms and independently recompute the holdout statistics."""
    if type(report) is not dict or report.get("status") != expected_status:
        return False
    model = mujoco.MjModel.from_xml_string(spec["robot_xml"])
    data = mujoco.MjData(model)
    for side in SIDES:
        result = report["calibration"][side]
        if (
            type(result["inliers"]) is not int
            or result["inliers"] != truth[side]["inliers"]
        ):
            return False
        world, tool = (
            reported_pose(result[key])
            for key in ("world_from_base", "flange_from_marker")
        )
        for estimate, key in ((world, "world_from_base"), (tool, "flange_from_marker")):
            error_m, error_rad = error(estimate, reported_pose(truth[side][key]))
            if error_m > 0.0018 or error_rad > 0.004:
                return False
        measures = report["validation"][side]
        residuals = [
            error(
                world @ fk(model, data, row["q"]) @ tool, reported_pose(row["marker"])
            )
            for row in spec["captures"][side]["validation"]
        ]
        expected = np.sqrt(np.mean(np.square(residuals), axis=0))
        observed = np.asarray(
            [measures["translation_rmse_m"], measures["rotation_rmse_rad"]]
        )
        if (
            observed.shape != (2,)
            or not np.all(np.isfinite(observed))
            or not np.allclose(observed, expected, rtol=2e-6, atol=5e-8)
        ):
            return False
    return True


def fit_case(run, robot_xml, seed):
    """Qualify two dissimilar arms under planted base, tool and outlier transforms."""
    spec, truth = commission_fixture(robot_xml, seed=seed)
    return validate_fit(run("commission-native", spec), spec, truth, "ok")


def validation_case(run, robot_xml):
    """Reject changed validation while preserving the fitted transforms."""
    spec, truth = commission_fixture(robot_xml, seed=127)
    clean = run("commission-native", spec)
    if not validate_fit(clean, spec, truth, "ok"):
        return False
    corrupted = deepcopy(spec)
    for row in corrupted["captures"]["right"]["validation"]:
        pose = reported_pose(row["marker"])
        pose[:3, 3] += [0.025, -0.019, 0.031]
        pose[:3, :3] = axis_rotation([-0.21, 0.49, 0.56], 0.039) @ pose[:3, :3]
        row["marker"] = wire_pose(pose)
    report = run("commission-native", corrupted)
    if not validate_fit(report, corrupted, truth, "validation_failed"):
        return False
    for side in SIDES:
        for key in ("world_from_base", "flange_from_marker"):
            a = reported_pose(clean["calibration"][side][key])
            b = reported_pose(report["calibration"][side][key])
            if max(error(a, b)) > 2e-6:
                return False
    return True


def degeneracy_case(run, robot_xml):
    """Protect commissioning when all known flange motions share one rotation axis."""
    spec, truth = commission_fixture(robot_xml, seed=78)
    model = mujoco.MjModel.from_xml_string(robot_xml)
    data = mujoco.MjData(model)
    world = reported_pose(truth["left"]["world_from_base"])
    tool = reported_pose(truth["left"]["flange_from_marker"])
    rows = []
    for angle in np.linspace(-1.7, 1.7, 27):
        q = [float(angle), -1.3, 1.7, -0.83, 0.3, -0.6]
        rows.append({"q": q, "marker": wire_pose(world @ fk(model, data, q) @ tool)})
    spec["captures"]["left"]["fit"] = rows
    return run("commission-native", spec) == {
        "status": "unidentifiable",
        "calibration": None,
        "validation": None,
    }


def invalid_case(run, robot_xml):
    """Reject a malformed late quaternion without modifying the existing report."""
    spec, _ = commission_fixture(robot_xml, seed=78)
    spec["captures"]["right"]["validation"][-1]["marker"]["quaternion_xyzw"] = [
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    return run("commission-native", spec, invalid=True) is True


def commission_native_checks(run, robot_xml):
    """Execute both independent successful fixtures and negative metrology controls."""
    probes = {
        "native_commission_asymmetric_base_and_tool": lambda: fit_case(
            run, robot_xml, 78
        ),
        "native_commission_rotated_marker_and_outliers": lambda: fit_case(
            run, robot_xml, 329
        ),
        "native_commission_validation_only_fault": lambda: validation_case(
            run, robot_xml
        ),
        "native_commission_single_axis_abstention": lambda: degeneracy_case(
            run, robot_xml
        ),
        "native_commission_malformed_capture_is_atomic": lambda: invalid_case(
            run, robot_xml
        ),
    }
    results = {}
    for key, check in probes.items():
        try:
            results[key] = bool(check())
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            results[key] = False
    return results
