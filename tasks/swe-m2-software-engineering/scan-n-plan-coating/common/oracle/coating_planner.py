"""Geometry-based coating of smooth connected treatment ribbons."""

from dataclasses import dataclass
from itertools import combinations
from math import ceil, cos, floor, isfinite, pi, tan
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def unit(vector):
    return vector / np.linalg.norm(vector, axis=-1, keepdims=True)


def xml_vector(node, key, default):
    return np.fromstring(node.get(key, default) if node is not None else default, sep=" ")


class SerialArm:
    """URDF serial-chain FK and nozzle Jacobian, in public joint wire order."""

    def __init__(self, model):
        source = ET.parse(model["urdf_path"]).getroot()
        declarations = {joint.find("child").get("link"): joint for joint in source.findall("joint")}
        names = model["arm_joints"]
        chain = []
        link = model["tool_frame"]
        lower, upper, velocity = np.zeros((3, len(names)))
        while link in declarations:
            joint = declarations[link]
            origin = joint.find("origin")
            xyz = xml_vector(origin, "xyz", "0 0 0")
            rpy = xml_vector(origin, "rpy", "0 0 0")
            orient = Rotation.from_euler("xyz", rpy).as_matrix()
            moving = joint.get("type") != "fixed"
            index = names.index(joint.get("name")) if moving else None
            axis = unit(xml_vector(joint.find("axis"), "xyz", "1 0 0")) if moving else None
            if moving:
                limit = joint.find("limit")
                lower[index], upper[index], velocity[index] = (
                    float(limit.get(field)) for field in ("lower", "upper", "velocity")
                )
            chain.append((xyz, orient, index, axis, link))
            link = joint.find("parent").get("link")
        if np.any(velocity <= 0):
            raise ValueError("Expected all commissioned revolute joints in the tool chain")
        self.chain = chain[::-1]
        self.base_link = link
        semantic = ET.parse(model["srdf_path"]).getroot()
        if source.tag != "robot" or semantic.tag != "robot" or source.get("name") != semantic.get("name"):
            raise ValueError("URDF and SRDF robot names differ")
        self.shapes = []
        for node in source.findall("link"):
            for collision in node.findall("collision"):
                origin = collision.find("origin")
                xyz = xml_vector(origin, "xyz", "0 0 0")
                orient = Rotation.from_euler("xyz", xml_vector(origin, "rpy", "0 0 0")).as_matrix()
                geom = next(iter(collision.find("geometry")))
                if geom.tag == "cylinder":
                    radius = float(geom.get("radius"))
                    extent = np.array([radius, radius, .5 * float(geom.get("length"))])
                elif geom.tag == "sphere":
                    extent = np.full(3, float(geom.get("radius")))
                elif geom.tag == "box":
                    extent = .5 * xml_vector(geom, "size", "")
                else:
                    raise ValueError(f"Unsupported arm collision primitive {geom.tag!r}")
                if not np.isfinite(extent).all() or np.any(extent <= 0):
                    raise ValueError("Invalid arm collision geometry")
                self.shapes.append((node.get("name"), xyz, orient, geom.tag, extent))
        self.exceptions = {
            frozenset((item.get("link1"), item.get("link2")))
            for item in semantic.findall("disable_collisions")
        }
        self.lower, self.upper, self.velocity = lower, upper, velocity
        self.shoulder = np.sum([entry[0] for entry in self.chain[:2]], axis=0)
        self.max_reach = sum(np.linalg.norm(entry[0]) for entry in self.chain[2:])

    def nozzle(self, q):
        position = np.zeros(3)
        matrix = np.eye(3)
        origins, axes = np.zeros((2, len(q), 3))
        for xyz, orient, index, axis, _ in self.chain:
            position = position + matrix @ xyz
            matrix = matrix @ orient
            if index is not None:
                origins[index], axes[index] = position, matrix @ axis
                matrix = matrix @ Rotation.from_rotvec(axis * q[index]).as_matrix()
        direction = matrix[:, 2]
        return position, direction, np.cross(axes, position - origins).T, np.cross(axes, direction).T

    def collision_shapes(self, q):
        position, matrix = np.zeros(3), np.eye(3)
        frames = {self.base_link: (position, matrix)}
        for xyz, orient, index, axis, child in self.chain:
            position = position + matrix @ xyz
            matrix = matrix @ orient
            if index is not None:
                matrix = matrix @ Rotation.from_rotvec(axis * q[index]).as_matrix()
            frames[child] = position, matrix
        shapes = []
        for link, xyz, orient, kind, extent in self.shapes:
            link_position, link_matrix = frames[link]
            shapes.append((link, Primitive(link_position + link_matrix @ xyz, link_matrix @ orient, kind, extent)))
        return shapes

    def inverse(self, target, direction, seed, lower, upper):
        def error(q):
            point, axis, dp, da = self.nozzle(q)
            delta = np.r_[4 * (point - target), axis - direction, 1e-5 * (q - seed)]
            return delta, np.vstack((4 * dp, da, 1e-5 * np.eye(6)))

        fitted = np.clip(seed, lower, upper)
        free = lower < upper
        if not np.all(free):
            def partial(q):
                state = fitted.copy()
                state[free] = q
                residual, jacobian = error(state)
                return residual, jacobian[:, free]
        else:
            partial = error

        if np.any(free):
            fitted[free] = least_squares(
                lambda q: partial(q)[0], fitted[free],
                jac=lambda q: partial(q)[1], bounds=(lower[free], upper[free]),
                ftol=1e-11, xtol=1e-11, gtol=1e-11, max_nfev=70,
            ).x
        p, axis, *_ = self.nozzle(fitted)
        if np.linalg.norm(p - target) > 0.00015 or np.linalg.norm(axis - direction) > 0.002:
            raise ValueError(f"IK residual: {np.linalg.norm(p-target):.6f} m, orientation {np.linalg.norm(axis-direction):.6f}")
        return fitted


def slice_ribbon(triangles):
    """Area-weighted principal cut, followed by exact triangle-plane segments."""
    raw = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area = np.linalg.norm(raw, axis=1)
    normals = unit(raw)
    center_points = triangles.mean(axis=1)
    center = np.average(center_points, weights=area, axis=0)
    _, principal = np.linalg.eigh(np.cov((center_points - center).T, aweights=area))
    major = principal[:, -1]
    projection = (triangles - center) @ major
    span = projection.max() - projection.min()
    samples = np.linspace(projection.min() + 0.001 * span, projection.max() - 0.001 * span, 151)
    centers = []
    outward = []
    for value in samples:
        midpoints = []
        face_normals = []
        lengths = []
        for tri, signed, normal in zip(triangles, projection - value, normals, strict=True):
            inside = signed >= 0
            if np.all(inside) or not np.any(inside):
                continue
            ends = [tri[i] + signed[i] / (signed[i] - signed[j]) * (tri[j] - tri[i])
                    for i, j in ((0, 1), (1, 2), (2, 0)) if inside[i] != inside[j]]
            length = np.linalg.norm(ends[1] - ends[0])
            if length > 0:
                midpoints.append((ends[0] + ends[1]) / 2)
                face_normals.append(normal)
                lengths.append(length)
        if not lengths:
            raise ValueError("No continuous centerline crosses the selected target")
        centers.append(np.average(midpoints, weights=lengths, axis=0))
        outward.append(unit(np.average(face_normals, weights=lengths, axis=0)))
    # Suppress facet quantization before requesting a differentiable joint path.
    along = np.linspace(-1, 1, len(samples))
    basis = np.polynomial.chebyshev.chebvander(along, 5)
    points = basis @ np.linalg.lstsq(basis, centers, rcond=None)[0]
    normals = unit(basis @ np.linalg.lstsq(basis, outward, rcond=None)[0])
    distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    return CubicSpline(distance, points), CubicSpline(distance, normals), float(distance[-1])


def bounds_ok(q0, q1, v0, v1, seconds, lower, upper, velocity, acceleration):
    """Check exact continuous cubic position, speed, and acceleration extrema."""
    change = q1 - q0
    b = 3 * change - seconds * (2 * v0 + v1)
    a = -2 * change + seconds * (v0 + v1)
    c = seconds * v0
    if np.any(np.maximum(np.abs(2 * b), np.abs(6 * a + 2 * b)) / seconds**2 > acceleration + 1e-10):
        return False
    for axis in range(len(q0)):
        aa, bb, cc, p = a[axis], b[axis], c[axis], q0[axis]
        roots = np.roots([3 * aa, 2 * bb, cc])
        locations = [0, 1, *(r.real for r in roots if abs(r.imag) < 1e-10 and 0 < r.real < 1)]
        if any(not lower[axis] - 1e-10 <= ((aa*u + bb)*u + cc)*u + p <= upper[axis] + 1e-10
               for u in locations):
            return False
        if aa != 0 and 0 < (extreme := -bb / (3 * aa)) < 1:
            locations.append(extreme)
        if any(abs((3*aa*u + 2*bb)*u + cc) / seconds > velocity[axis] + 1e-10 for u in locations):
            return False
    return True


def combine_path(initial, initial_speed, final_angle, points, speeds, period, active_stride, limits, cap):
    """Join a constant-speed spray sweep to dry rest-to-motion intervals."""
    rest = np.zeros(7)
    for q0, q1, v0, v1 in zip(points[:-1], points[1:], speeds[:-1], speeds[1:], strict=True):
        if not bounds_ok(q0, q1, v0, v1, period * active_stride, *limits):
            raise ValueError("An active interval exceeds a continuous joint bound")

    active = (len(points) - 1) * active_stride
    for lead in range(1, cap - active):
        if bounds_ok(initial, points[0], initial_speed, speeds[0], lead * period, *limits):
            break
    else:
        raise ValueError("No dry approach fits the duration and joint bounds")
    for tail in range(1, cap - active - lead + 1):
        duration = tail * period
        end = points[-1] + 0.5 * duration * speeds[-1]
        end[6] = final_angle
        if bounds_ok(points[-1], end, speeds[-1], rest, duration, *limits):
            return lead, tail, end
    raise ValueError("No stopped dry departure fits the duration and joint bounds")


def scalar(value, name):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def numbers(value, size, name):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name} must contain {size} numbers")
    return np.array([scalar(entry, name) for entry in value])


def index_list(value, count, name):
    if not isinstance(value, list) or any(type(i) is not int or not 0 <= i < count for i in value):
        raise ValueError(f"{name} contains an unknown face")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} contains a duplicate face")
    return value


def validated_pose(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a pose")
    translation = numbers(value.get("translation_m"), 3, name)
    quat = numbers(value.get("quaternion_xyzw"), 4, name)
    if abs(np.linalg.norm(quat) - 1) > 1e-6:
        raise ValueError(f"{name} must use a unit quaternion")
    return Rotation.from_quat(quat), translation


def geometry(value):
    if not isinstance(value, dict):
        raise ValueError("Mesh must be an object")
    if not isinstance(value.get("vertices_m"), list) or not value["vertices_m"]:
        raise ValueError("Mesh must contain vertices")
    vertices = np.array([numbers(v, 3, "vertices_m") for v in value["vertices_m"]])
    if not isinstance(value.get("triangles"), list) or not value["triangles"]:
        raise ValueError("Mesh must contain faces")
    faces = [index_list(face, len(vertices), "triangle") for face in value["triangles"]]
    if any(len(triangle) != 3 for triangle in faces):
        raise ValueError("Triangles must contain three vertex indices")
    indexed = np.asarray(faces)
    triangles = vertices[indexed]
    if np.any(np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0],
                                       triangles[:, 2] - triangles[:, 0]), axis=1) <= 0):
        raise ValueError("Mesh contains a degenerate face")
    return vertices, indexed


def public_path(value, assets_root):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError("Robot model paths must be absolute")
    path = Path(value)
    if path.is_file():
        return path
    if assets_root is not None:
        for relative in [Path("cell") / path.name, Path(path.name)]:
            if (alternative := assets_root / relative).is_file():
                return alternative
    raise ValueError(f"Robot model asset is unavailable: {path}")


@dataclass(frozen=True)
class Geometry:
    triangles: np.ndarray
    rotation: Rotation
    translation: np.ndarray


class Workpiece:
    """Indexed public part and cell surfaces, placed by actual rotary angle."""

    def __init__(self, job):
        vertices, faces = geometry(job["part_mesh"])
        self.triangles = vertices[faces]
        self.targets = index_list(job["target_faces"], len(faces), "target_faces")
        masks = index_list(job["masked_faces"], len(faces), "masked_faces")
        if set(self.targets) & set(masks):
            raise ValueError("Target and masked faces overlap")
        self.axis_rotation, self.axis_translation = validated_pose(job["base_from_axis"], "base_from_axis")
        self.fixture = []
        self.world = []
        ids = set()
        for name, collection in [("fixture_collision", self.fixture), ("world_collision", self.world)]:
            if not isinstance(job[name], list):
                raise ValueError(f"{name} must be an array")
            for body in job[name]:
                identity = body["id"]
                if not isinstance(identity, str) or not identity or identity in ids:
                    raise ValueError("Invalid or duplicate collision body ID")
                ids.add(identity)
                points, indices = geometry(body["mesh"])
                r, t = validated_pose(body["pose"], "collision body pose")
                collection.append(Geometry(points[indices], r, t))

    def part_pose(self, angle, home):
        home_r, home_t = home
        turn = self.axis_rotation * Rotation.from_rotvec([0, 0, angle]) * self.axis_rotation.inv()
        return turn * home_r, turn.apply(home_t - self.axis_translation) + self.axis_translation

    def placements(self, angle, home):
        part_r, part_t = self.part_pose(angle, home)
        axis_turn = self.axis_rotation * Rotation.from_rotvec([0, 0, angle])
        return [
            (part_r, part_t),
            *((axis_turn * body.rotation, axis_turn.apply(body.translation) + self.axis_translation)
              for body in self.fixture),
            *((body.rotation, body.translation) for body in self.world),
        ]

    def max_rotational_radius(self, home):
        axis_inv = self.axis_rotation.inv()
        local_part_r = axis_inv * home[0]
        local_part_t = axis_inv.apply(home[1] - self.axis_translation)
        moving = [Geometry(self.triangles, local_part_r, local_part_t), *self.fixture]
        return max(np.linalg.norm((body.rotation.apply(body.triangles.reshape(-1, 3))
                                  + body.translation)[:, :2], axis=1).max() for body in moving)


@dataclass(frozen=True)
class Motion:
    start: np.ndarray
    velocity_at_start: np.ndarray
    final_angle: float
    period_ns: int
    max_ticks: int
    clearance: float
    lower: np.ndarray
    upper: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray

    @property
    def period_s(self):
        return self.period_ns * 1e-9

    @property
    def bounds(self):
        return self.lower, self.upper, self.velocity, self.acceleration


def parse_motion(job, arm, coordinated, start_velocity):
    raw = job["motion"]
    joint_min = np.maximum(numbers(raw["lower_rad"], 7, "lower_rad"), np.r_[arm.lower, -np.inf])
    joint_max = np.minimum(numbers(raw["upper_rad"], 7, "upper_rad"), np.r_[arm.upper, np.inf])
    rates = np.minimum(numbers(raw["max_velocity_rad_s"], 7, "max_velocity_rad_s"), np.r_[arm.velocity, np.inf])
    acceleration = numbers(raw["max_acceleration_rad_s2"], 7, "max_acceleration_rad_s2")
    start = numbers(job["start_q_rad"], 7, "start_q_rad")
    final_angle = scalar(job["final_positioner_rad"], "final_positioner_rad")
    clearance = scalar(raw["min_clearance_m"], "min_clearance_m")
    cadence, deadline = raw["control_period_ns"], raw["max_duration_ns"]
    if (type(cadence) is not int or type(deadline) is not int or cadence <= 0 or deadline <= 0
            or clearance < 0 or np.any(joint_min > joint_max)
            or np.any(rates < 0) or np.any(acceleration < 0)):
        raise ValueError("Invalid motion limits")
    if not coordinated and final_angle != start[6]:
        raise ValueError("A fixed plan must use one positioner angle")
    if start_velocity is None:
        start_velocity = np.zeros(7)
    else:
        start_velocity = numbers(list(start_velocity), 7, "start velocity")
    return Motion(start, start_velocity, final_angle, cadence, deadline // cadence, clearance,
                  joint_min, joint_max, rates, acceleration)


def check_recipe(recipe):
    for field in ("standoff_m", "surface_speed_mps", "target_dose_ml_m2"):
        low, high = numbers(recipe[field], 2, field)
        if not 0 <= low <= high:
            raise ValueError(f"Unordered or negative {field}")
    cone = scalar(recipe["cone_half_angle_rad"], "cone_half_angle_rad")
    normal = scalar(recipe["max_normal_error_rad"], "max_normal_error_rad")
    if not 0 < cone < pi / 2 or not 0 <= normal <= pi:
        raise ValueError("Invalid cone or normal bound")
    if (not 0 <= scalar(recipe["min_covered_fraction"], "min_covered_fraction") <= 1
            or scalar(recipe["max_off_target_ml"], "max_off_target_ml") < 0
            or scalar(recipe["max_flow_ml_s"], "max_flow_ml_s") < 0):
        raise ValueError("Invalid material limits")
    if recipe["standoff_m"][1] <= 0:
        raise ValueError("Maximum standoff must be positive")


@dataclass(frozen=True)
class Ribbon:
    points: CubicSpline
    normals: CubicSpline
    length: float


@dataclass(frozen=True)
class Sweep:
    positions: np.ndarray
    outward: np.ndarray
    angles: np.ndarray
    duration: float
    stride: int
    nominal_flow: float


def _fixed_sweep(ribbon, recipe, motion, direction, speed_fraction, standoff_fraction, span, edge_fraction):
    standoff = np.interp(standoff_fraction, [0, 1], recipe["standoff_m"])
    footprint = standoff * tan(recipe["cone_half_angle_rad"])
    begin, end = np.asarray(span) * ribbon.length
    # Begin and end inside a physical target edge. Residual endpoints internal
    # to a ribbon already include their overlap elsewhere.
    begin += edge_fraction * footprint if span[0] == 0 else 0
    end -= edge_fraction * footprint if span[1] == 1 else 0
    margin = end - begin
    if margin <= 0:
        raise ValueError("Treatment ribbon is too short for this footprint")
    speed = np.interp(speed_fraction, [0, 1], recipe["surface_speed_mps"])
    preferred_stride = max(1, round(0.035 / motion.period_s))
    for stride in range(preferred_stride, 0, -1):
        interval = motion.period_s * stride
        first = max(2, ceil(margin / (recipe["surface_speed_mps"][1] * interval)))
        last = floor(margin / (max(recipe["surface_speed_mps"][0], 1e-12) * interval))
        if first <= last:
            steps = int(np.clip(ceil(margin / (speed * interval)), first, last))
            break
    else:
        raise ValueError("No quantized pass meets the process speed interval")
    duration = steps * motion.period_s * stride
    station = np.linspace(begin, end, steps + 1)[::direction]
    normal = unit(ribbon.normals(station))
    positions = ribbon.points(station) + standoff * normal
    solid_angle = 2 * pi * (1 - cos(recipe["cone_half_angle_rad"]))
    dose_min, dose_max = recipe["target_dose_ml_m2"]
    nominal = dose_min + .69 * (dose_max - dose_min)
    flow = nominal * solid_angle * standoff**2 * (margin / duration) / (2 * footprint)
    return Sweep(positions, normal, np.full(len(positions), motion.start[6]), duration, stride,
                 min(recipe["max_flow_ml_s"], flow))


def _scheduled_angles(sweep, motion, arm, workpiece, home, coordinated):
    if not coordinated:
        yield sweep.angles
        return
    start, finish = motion.start[6], motion.final_angle
    speed_limit = motion.velocity[6]
    low, high = motion.lower[6], motion.upper[6]
    if speed_limit == 0 or high == low:
        if finish == start:
            yield sweep.angles
        return
    count = len(sweep.angles)
    shortlist = np.linspace(0, count - 1, 7).astype(int)
    position = sweep.positions[shortlist]
    seed_tip = arm.nozzle(motion.start[:6])[0]
    rotary_options = []
    # Enumerate active sectors independently of the start and requested
    # finish. A dry index may first bring the entire target into reach.
    grid = np.linspace(low, high, max(2, ceil((high - low) / .125) + 1))
    angle_centers = np.unique(np.r_[start, finish, .5 * (start + finish), grid])
    goal_speed = (finish - start) / max(sweep.duration, motion.period_s)
    speeds = np.unique(np.r_[0, speed_limit * np.array([-.85, -.58, -.35, -.2, .2, .35, .58, .85]),
                              np.clip(goal_speed, -.8 * speed_limit, .8 * speed_limit)])
    available_time = motion.max_ticks * motion.period_s - sweep.duration
    for speed in speeds:
        sweep_angle = speed * sweep.duration
        for center in angle_centers:
            first, last = center - .5 * sweep_angle, center + .5 * sweep_angle
            if min(first, last) < low or max(first, last) > high:
                continue
            travel = abs(first - start) + abs(finish - last)
            if travel / speed_limit > available_time:
                continue
            rotations = np.linspace(first, last, count)
            tip_goals = []
            for point, angle in zip(position, rotations[shortlist], strict=True):
                r, t = workpiece.part_pose(angle, home)
                tip_goals.append(r.apply(point) + t)
            reach = np.linalg.norm(np.asarray(tip_goals) - arm.shoulder, axis=1)
            if max(reach) > arm.max_reach + .03:
                continue
            seed_distance = np.linalg.norm(tip_goals[0] - seed_tip)
            # Avoid strongly bent or stretched configurations, unnecessary
            # indexing, and depending on a single shoulder posture.
            rank = (travel / speed_limit + 1.3 * seed_distance + .3 * max(reach)
                    + (0.22 if abs(speed) <= 1e-9 else 0))
            rotary_options.append((rank, rotations))
    rotary_options.sort(key=lambda entry: entry[0])
    for _, rotations in rotary_options[:28]:
        yield rotations


def _trajectory(sweep, angles, motion, arm, workpiece, home, arm_seed):
    points = []
    seed = arm_seed
    for position, normal, angle in zip(sweep.positions, sweep.outward, angles, strict=True):
        r, t = workpiece.part_pose(angle, home)
        seed = arm.inverse(r.apply(position) + t, -r.apply(normal), seed, motion.lower[:6], motion.upper[:6])
        points.append(np.r_[seed, angle])
    points = np.asarray(points)
    times = np.linspace(0, sweep.duration, len(points))
    speeds = CubicSpline(times, points)(times, 1)
    lead, tail, end = combine_path(
        motion.start, motion.velocity_at_start, motion.final_angle, points, speeds, motion.period_s,
        sweep.stride, motion.bounds, motion.max_ticks,
    )

    def row(tick, q, qd, flow):
        return {"t_ns": tick * motion.period_ns, "q_rad": q.tolist(), "qd_rad_s": qd.tolist(), "flow_ml_s": flow}

    return [
        row(0, motion.start, motion.velocity_at_start, 0.0),
        *(row(lead + i * sweep.stride, q, qd, sweep.nominal_flow if i < len(points) - 1 else 0.0)
          for i, (q, qd) in enumerate(zip(points, speeds, strict=True))),
        row(lead + (len(points) - 1) * sweep.stride + tail, end, np.zeros(7), 0.0),
    ]


def hermite(left, right, fraction):
    q0, q1 = np.asarray(left["q_rad"]), np.asarray(right["q_rad"])
    v0, v1 = np.asarray(left["qd_rad_s"]), np.asarray(right["qd_rad_s"])
    dt = (right["t_ns"] - left["t_ns"]) * 1e-9
    u = fraction
    return ((1 + 2*u) * (1 - u)**2 * q0 + (3 - 2*u) * u**2 * q1
            + dt * (u * (1 - u)**2 * v0 + u**2 * (u - 1) * v1))


@dataclass(frozen=True)
class SurfaceCells:
    centers: np.ndarray
    normals: np.ndarray
    weights: np.ndarray
    faces: np.ndarray

    @classmethod
    def make(cls, triangles, spacing=.008):
        p0, p1, p2 = triangles.transpose(1, 0, 2)
        d1, d2 = p1 - p0, p2 - p0
        raw_normals = np.cross(d1, d2)
        area = .5 * np.linalg.norm(raw_normals, axis=1)
        divisions = np.maximum(1, np.ceil(np.maximum.reduce([
            np.linalg.norm(d1, axis=1), np.linalg.norm(d2, axis=1), np.linalg.norm(p1 - p2, axis=1)
        ]) / spacing).astype(int))
        centers, normals, weights, face_ids = [], [], [], []
        for count in np.unique(divisions):
            selection = np.flatnonzero(divisions == count)
            ij = np.array([(i, j) for i in range(count) for j in range(count - i)])
            uv = np.concatenate(((ij + 1/3) / count, (ij[ij.sum(axis=1) < count - 1] + 2/3) / count))
            positions = p0[selection, None] + uv[:, :1] * d1[selection, None] + uv[:, 1:] * d2[selection, None]
            centers.extend(positions.reshape(-1, 3))
            normals.extend(np.repeat(unit(raw_normals[selection]), len(uv), axis=0))
            weights.extend(np.repeat(area[selection] / len(uv), len(uv)))
            face_ids.extend(np.repeat(selection, len(uv)))
        return cls(np.asarray(centers), np.asarray(normals), np.asarray(weights), np.asarray(face_ids))


class RaySurface:
    """Closest opaque surface hit for one or more directions from one point."""

    def __init__(self, triangles):
        self.a = triangles[:, 0]
        self.e1, self.e2 = triangles[:, 1] - self.a, triangles[:, 2] - self.a
        self.normals = unit(np.cross(self.e1, self.e2))

    def hit(self, origin, directions):
        delta = origin - self.a
        tvec = np.cross(delta, self.e1)
        cross = np.cross(directions[:, None, :], self.e2)
        det = np.einsum("rti,ti->rt", cross, self.e1)
        good = np.abs(det) > 1e-13
        factor = np.divide(1, det, where=good, out=np.zeros_like(det))
        u = factor * np.einsum("rti,ti->rt", cross, delta)
        v = factor * (directions @ tvec.T)
        t = factor * np.einsum("ti,ti->t", self.e2, tvec)
        distances = np.where(good & (u >= -1e-9) & (v >= -1e-9) & (u+v <= 1+1e-9) & (t > 1e-9), t, np.inf)
        ids = np.argmin(distances, axis=1)
        return distances[np.arange(len(ids)), ids], ids


@dataclass(frozen=True)
class MaterialState:
    """Measured dose on stable part-local cells and cumulative excess material."""

    part_dose_ml_m2: np.ndarray
    off_target_ml: float


class CoatingDose:
    """Independent candidate-side cone estimate for planning and measured receipts."""

    def __init__(self, job, *, assets_root=None):
        self.workpiece = Workpiece(job)
        self.arm = _parse_robot(job, assets_root)
        self.part = SurfaceCells.make(self.workpiece.triangles)
        self.target = np.isin(self.part.faces, self.workpiece.targets)
        self.recipe = job["recipe"]

    def empty(self):
        return MaterialState(np.zeros(len(self.part.faces)), 0.0)

    def _place(self, arm, workpiece, home, q):
        transforms = workpiece.placements(q[6], home)
        nozzle, direction, *_ = arm.nozzle(q[:6])
        geometries = [workpiece.triangles, *(x.triangles for x in workpiece.fixture), *(x.triangles for x in workpiece.world)]
        placed = [
            (rotation.apply(triangles.reshape(-1, 3)) + translation).reshape(-1, 3, 3)
            for triangles, (rotation, translation) in zip(geometries, transforms, strict=True)
        ]
        return nozzle, direction, transforms, RaySurface(np.concatenate(placed))

    def _axis_point(self, workpiece, home, q):
        origin, axis, poses, ray = self._place(self.arm, workpiece, home, q)
        depth, face = ray.hit(origin, axis[None])
        if not np.isfinite(depth[0]) or face[0] not in workpiece.targets:
            return None
        rotation, position = poses[0]
        return rotation.inv().apply(origin + depth[0] * axis - position)

    def accumulate(self, trajectory, registration, *, scene_job=None, prior=None):
        """Add measured Hermite intervals using the registration that issued them."""
        material, _ = self.trace(trajectory, registration, scene_job=scene_job, prior=prior)
        return material

    def trace(self, trajectory, registration, *, scene_job=None, prior=None, verify_recipe=False):
        workpiece = self.workpiece if scene_job is None else Workpiece(scene_job)
        home = validated_pose(registration["base_from_part_home"], "base_from_part_home")
        prior = self.empty() if prior is None else prior
        dose = prior.part_dose_ml_m2.copy()
        off_target = prior.off_target_ml
        cosine = cos(self.recipe["cone_half_angle_rad"])
        solid_angle = 2 * pi * (1 - cosine)
        external = [SurfaceCells.make(x.triangles) for x in (*workpiece.fixture, *workpiece.world)]
        cells = [self.part, *external]
        minimum_standoff, maximum_standoff = self.recipe["standoff_m"]
        minimum_speed, maximum_speed = self.recipe["surface_speed_mps"]
        for left, right in zip(trajectory[:-1], trajectory[1:], strict=True):
            if left["flow_ml_s"] == 0:
                continue
            dt = (right["t_ns"] - left["t_ns"]) * 1e-9
            count = max(1, ceil(dt / .010))
            scale = left["flow_ml_s"] * dt / (solid_angle * count)
            for step in range(count):
                u = (step + .5) / count
                q = hermite(left, right, u)
                origin, axis, transforms, surface = self._place(self.arm, workpiece, home, q)
                if verify_recipe:
                    dist, hits = surface.hit(origin, axis[None])
                    if (hits[0] not in workpiece.targets or not minimum_standoff <= dist[0] <= maximum_standoff
                            or (-axis @ surface.normals[hits[0]]) < cos(self.recipe["max_normal_error_rad"])):
                        return MaterialState(dose, off_target), False
                    delta = min(.0001 / dt, .25 / count)
                    before, after = (self._axis_point(workpiece, home, hermite(left, right, u + sign * delta))
                                     for sign in (-1, 1))
                    if before is None or after is None:
                        return MaterialState(dose, off_target), False
                    speed = np.linalg.norm(after - before) / (2 * delta * dt)
                    if not minimum_speed <= speed <= maximum_speed:
                        return MaterialState(dose, off_target), False
                for index, (cloud, (rotation, location)) in enumerate(zip(cells, transforms, strict=True)):
                    relative = rotation.apply(cloud.centers) + location - origin
                    lengths = np.linalg.norm(relative, axis=1)
                    possible = np.flatnonzero((relative @ axis >= cosine * lengths) & (lengths > 1e-9))
                    if not len(possible):
                        continue
                    rays = relative[possible] / lengths[possible, None]
                    incidence = -np.einsum("ni,ni->n", rays, rotation.apply(cloud.normals[possible]))
                    facing = incidence > 0
                    possible, rays, incidence = possible[facing], rays[facing], incidence[facing]
                    visible_depth, _ = surface.hit(origin, rays)
                    visible = visible_depth >= lengths[possible] - 1e-8
                    possible, incidence = possible[visible], incidence[visible]
                    added = scale * incidence / lengths[possible]**2
                    if index == 0:
                        dose[possible] += added
                        selected = ~self.target[possible]
                        off_target += added[selected] @ cloud.weights[possible[selected]]
                    else:
                        off_target += added @ cloud.weights[possible]
        return MaterialState(dose, float(off_target)), True

    def coverage(self, material):
        low, high = self.recipe["target_dose_ml_m2"]
        good = (material.part_dose_ml_m2 >= low) & (material.part_dose_ml_m2 <= high) & self.target
        area = self.part.weights[self.target].sum()
        return float(self.part.weights[good].sum() / area) if area else 0.0

    def qualifies(self, material):
        return (self.coverage(material) >= self.recipe["min_covered_fraction"]
                and material.off_target_ml <= self.recipe["max_off_target_ml"])

    def spans(self, ribbon, prior):
        if prior is None or not np.any(prior.part_dose_ml_m2 > 0):
            return [(0, 1)]
        threshold = self.recipe["target_dose_ml_m2"][0]
        remaining = self.target & (prior.part_dose_ml_m2 < threshold)
        if not np.any(remaining):
            return []
        stations = np.linspace(0, ribbon.length, 41)
        centers = ribbon.points(stations)
        distances = np.linalg.norm(self.part.centers[self.target, None] - centers, axis=2)
        assignment = distances.argmin(axis=1)
        weights = self.part.weights[self.target]
        uncovered = remaining[self.target]
        total_area = np.bincount(assignment, weights=weights, minlength=len(stations))
        missed_area = np.bincount(assignment, weights=weights * uncovered, minlength=len(stations))
        # Ignore already coated slices with only edge cells missing: a second
        # whole pass would drive their well-covered centers over the upper dose.
        useful = (missed_area > .38 * total_area) & (total_area > 0)
        indices = np.flatnonzero(useful) if np.any(useful) else np.unique(assignment[uncovered])
        begin, end = stations[indices[[0, -1]]] / ribbon.length
        width = np.mean(self.recipe["standoff_m"]) * tan(self.recipe["cone_half_angle_rad"]) / ribbon.length
        return [(max(0.0, begin - scale * width), min(1.0, end + scale * width)) for scale in (.35, .70, 1.0)]



def _parse_robot(job, assets_root):
    model = dict(job["robot_model"])
    if (not isinstance(model.get("arm_joints"), list) or len(set(model["arm_joints"])) != 6
            or len(model["arm_joints"]) != 6
            or not isinstance(model.get("tool_frame"), str) or not model["tool_frame"]):
        raise ValueError("Invalid robot model coordinates")
    for field in ("urdf_path", "srdf_path"):
        model[field] = public_path(model[field], assets_root)
    return SerialArm(model)


@dataclass(frozen=True)
class Primitive:
    origin: np.ndarray
    orientation: np.ndarray
    kind: str
    extent: np.ndarray

    def box(self):
        span = np.abs(self.orientation) @ self.extent
        return self.origin - span, self.origin + span

    def support(self, direction):
        relative = self.orientation.T @ direction
        if self.kind == "cylinder":
            radial = np.linalg.norm(relative[:2])
            xy = relative[:2] * (self.extent[0] / radial) if radial > 1e-15 else np.zeros(2)
            local = np.r_[xy, np.copysign(self.extent[2], relative[2])]
        elif self.kind == "sphere":
            local = self.extent[0] * unit(relative)
        else:
            local = np.copysign(self.extent, relative)
        return self.origin + self.orientation @ local


def _nearest_simplex(simplex):
    """Nearest point to the origin in a simplex of at most four vertices."""
    best_distance = np.inf
    best = None
    retained = None
    for count in range(1, len(simplex) + 1):
        for subset in combinations(simplex, count):
            rows = np.array(subset)
            if count == 1:
                point = rows[0]
            else:
                offset = rows[0]
                edges = rows[1:] - offset
                coordinates = np.linalg.lstsq(edges.T, -offset, rcond=None)[0]
                if np.any(coordinates < 0) or coordinates.sum() > 1:
                    continue
                point = offset + coordinates @ edges
            squared = point @ point
            if squared < best_distance:
                best_distance, best, retained = squared, point, subset
    return best, list(retained)


def _separated(first, second_support, second_center, minimum):
    """Seek a separating support plane with at least the requested gap."""
    direction = second_center - first.origin
    if np.linalg.norm(direction) < 1e-12:
        direction = np.array([1., 0., 0.])
    simplex = []
    for _ in range(24):
        length = np.linalg.norm(direction)
        point = first.support(direction) - second_support(-direction)
        if point @ direction <= -minimum * length - 1e-12:
            return True
        if any(np.linalg.norm(point - previous) <= 1e-12 for previous in simplex):
            break
        nearest, simplex = _nearest_simplex([*simplex, point])
        if np.linalg.norm(nearest) < minimum + 1e-12 or len(simplex) == 4:
            break
        direction = -nearest
    return False


def _box_gaps(low, high, other_low, other_high):
    return np.linalg.norm(np.maximum(np.maximum(other_low - high, low - other_high), 0), axis=-1)


class CollisionGuard:
    """Candidate-side conservative support separation against public geometry."""

    def __init__(self, arm, workpiece, home, minimum):
        self.arm, self.workpiece, self.home, self.minimum = arm, workpiece, home, minimum
        self.geometry = [workpiece.triangles, *(x.triangles for x in workpiece.fixture),
                         *(x.triangles for x in workpiece.world)]
        shape_radius = max(np.linalg.norm(item[1]) + np.linalg.norm(item[4]) for item in arm.shapes)
        self.arm_radius = sum(np.linalg.norm(entry[0]) for entry in arm.chain) + shape_radius
        self.part_radius = workpiece.max_rotational_radius(home)
        self.fixed = None

    def _surfaces(self, angle):
        transforms = self.workpiece.placements(angle, self.home)
        result = []
        for original, (rotation, translation) in zip(self.geometry, transforms, strict=True):
            points = (rotation.apply(original.reshape(-1, 3)) + translation).reshape(-1, 3, 3)
            result.append((points, points.min(axis=1), points.max(axis=1)))
        return result

    def clear_at(self, q, gap):
        gap = max(gap, 1e-10)
        shapes = self.arm.collision_shapes(q[:6])
        boxes = [shape.box() for _, shape in shapes]
        for i, (link, shape) in enumerate(shapes):
            low, high = boxes[i]
            for j in range(i):
                other_link, other_shape = shapes[j]
                if other_link == link or frozenset((link, other_link)) in self.arm.exceptions:
                    continue
                if (_box_gaps(low, high, *boxes[j]) < gap
                        and not _separated(shape, other_shape.support, other_shape.origin, gap)):
                    return False
        surfaces = self._surfaces(q[6]) if self.fixed is None else self.fixed
        for triangles, bounds_lo, bounds_hi in surfaces:
            for (_, primitive), (low, high) in zip(shapes, boxes, strict=True):
                near = np.flatnonzero(_box_gaps(low, high, bounds_lo, bounds_hi) < gap)
                for triangle in triangles[near]:
                    if not _separated(primitive, lambda d: triangle[np.argmax(triangle @ d)],
                                      triangle.mean(axis=0), gap):
                        return False
        return True

    @staticmethod
    def max_joint_rates(left, right, dt):
        left_v, right_v = (np.asarray(row["qd_rad_s"]) for row in (left, right))
        change = np.asarray(right["q_rad"]) - left["q_rad"]
        a = -2 * change + dt * (left_v + right_v)
        b = 3 * change - dt * (2 * left_v + right_v)
        ratio = np.divide(-b, 3 * a, where=np.abs(a) > 1e-15, out=np.zeros(7))
        ratio = np.clip(ratio, 0, 1)
        inner = (3 * a * ratio**2 + 2 * b * ratio) / dt + left_v
        return np.maximum.reduce([np.abs(left_v), np.abs(right_v), np.abs(inner)])

    def accepts(self, rows):
        if all(row["q_rad"][6] == rows[0]["q_rad"][6] and row["qd_rad_s"][6] == 0 for row in rows):
            self.fixed = self._surfaces(rows[0]["q_rad"][6])
        else:
            self.fixed = None
        for left, right in zip(rows[:-1], rows[1:], strict=True):
            dt = (right["t_ns"] - left["t_ns"]) * 1e-9
            rates = self.max_joint_rates(left, right, dt)
            arm_speed = self.arm_radius * rates[:6].sum()
            max_relative = max(2 * arm_speed, arm_speed + self.part_radius * rates[6])
            pending = [(0.0, 1.0, 0)]
            while pending:
                lo, hi, depth = pending.pop()
                midway = 0.5 * (lo + hi)
                q = hermite(left, right, midway)
                requested = self.minimum + (hi - lo) * dt * max_relative * .5
                if self.clear_at(q, requested):
                    continue
                if depth >= 11 or not self.clear_at(q, self.minimum):
                    return False
                pending.extend(((lo, midway, depth+1), (midway, hi, depth+1)))
        return True


def _scaled_flow(rows, factor):
    return [dict(row, flow_ml_s=row["flow_ml_s"] * factor) for row in rows]


def _choose_flow(rows, meter, registration, prior):
    base = meter.empty() if prior is None else prior
    observed, usable = meter.trace(rows, registration, prior=base, verify_recipe=True)
    if not usable:
        return None
    delta = observed.part_dose_ml_m2 - base.part_dose_ml_m2
    lost = observed.off_target_ml - base.off_target_ml
    # Leave margin for the coarser planner grid's finite-cone boundary error.
    available = .91 * (meter.recipe["max_off_target_ml"] - base.off_target_ml)
    ceiling = min(meter.recipe["max_flow_ml_s"] / max(row["flow_ml_s"] for row in rows),
                  available / max(lost, 1e-15))
    if ceiling <= 0:
        return None
    upper = min(ceiling, 1.5)
    possible = np.unique(np.r_[np.linspace(.55 * upper, upper, 19), min(1.0, upper)])
    best = None
    rank = None
    for factor in possible:
        estimate = MaterialState(base.part_dose_ml_m2 + factor * delta, base.off_target_ml + factor * lost)
        coverage = meter.coverage(estimate)
        if coverage >= meter.recipe["min_covered_fraction"]:
            # A small deposit margin is preferable to a larger nominal score
            # that would exhaust the full excess-material allowance.
            score = coverage - .08 * (estimate.off_target_ml / max(meter.recipe["max_off_target_ml"], 1e-15))
            if rank is None or score > rank:
                rank, best = score, factor
    return None if best is None else _scaled_flow(rows, best)


def _dry_finish(motion, guard):
    """Return to the commissioned angle after an already sufficient coating."""
    zero = np.zeros(7)
    for ticks in range(1, motion.max_ticks + 1):
        seconds = ticks * motion.period_s
        final = motion.start + .5 * seconds * motion.velocity_at_start
        final[6] = motion.final_angle
        if not bounds_ok(motion.start, final, motion.velocity_at_start, zero, seconds, *motion.bounds):
            continue
        rows = [
            {"t_ns": 0, "q_rad": motion.start.tolist(), "qd_rad_s": motion.velocity_at_start.tolist(),
             "flow_ml_s": 0.0},
            {"t_ns": ticks * motion.period_ns, "q_rad": final.tolist(), "qd_rad_s": zero.tolist(),
             "flow_ml_s": 0.0},
        ]
        if guard.accepts(rows):
            return rows
    return None


def _plan(job, registration, coordinated, assets_root, start_velocity, prior):
    if not isinstance(job, dict) or not isinstance(registration, dict):
        raise ValueError("Job and registration must be objects")
    identity = job["job_id"]
    revision = job["scene_revision"]
    if (not isinstance(identity, str) or not identity or registration.get("job_id") != identity
            or type(revision) is not int or revision < 0):
        raise ValueError("Invalid job or scene identity")
    registered = registration.get("status")
    if registered not in ("registered", "review"):
        raise ValueError("Unknown registration status")
    if not isinstance(registration.get("capture_epoch"), str) or not registration["capture_epoch"]:
        raise ValueError("Unknown registration epoch")
    index = registration.get("capture_ids")
    if not isinstance(index, list) or not all(isinstance(key, str) and key for key in index):
        raise ValueError("Invalid registration capture IDs")
    if registered == "review" and registration.get("base_from_part_home") is not None:
        raise ValueError("A registration under review has no active part pose")
    check_recipe(job["recipe"])
    meter = CoatingDose(job, assets_root=assets_root)
    workpiece = meter.workpiece
    arm = meter.arm
    motion = parse_motion(job, arm, coordinated, start_velocity)
    report = {"job_id": identity, "scene_revision": revision, "status": "blocked", "trajectory": []}
    if (registered == "review" or not workpiece.targets or meter.recipe["max_flow_ml_s"] <= 0
            or meter.recipe["surface_speed_mps"][1] <= 0
            or np.any(motion.start < motion.lower) or np.any(motion.start > motion.upper)
            or not motion.lower[6] <= motion.final_angle <= motion.upper[6]):
        return report
    home = validated_pose(registration.get("base_from_part_home"), "base_from_part_home")
    guard = CollisionGuard(arm, workpiece, home, motion.clearance)
    if prior is not None and meter.qualifies(prior):
        rows = _dry_finish(motion, guard)
        if rows is not None:
            return dict(report, status="ready", trajectory=rows)
        return report
    try:
        ribbon = Ribbon(*slice_ribbon(workpiece.triangles[workpiece.targets]))
    except (ValueError, np.linalg.LinAlgError):
        return report

    settings = [(.5, .55, .21), (.68, .55, .21), (.39, .70, .14), (.62, .30, .14), (.50, .65, .35)]
    for span in meter.spans(ribbon, prior):
        for speed_fraction, standoff_fraction, edge_fraction in settings:
            ranked = []
            for direction in (-1, 1):
                try:
                    sweep = _fixed_sweep(
                        ribbon, meter.recipe, motion, direction, speed_fraction, standoff_fraction, span, edge_fraction
                    )
                except ValueError:
                    continue
                for angles in _scheduled_angles(sweep, motion, arm, workpiece, home, coordinated):
                    try:
                        rows = _trajectory(sweep, angles, motion, arm, workpiece, home, motion.start[:6])
                    except ValueError:
                        continue
                    ranked.append(rows)
                    if len(ranked) >= 4:
                        break
            ranked.sort(key=lambda rows: rows[-1]["t_ns"])
            for rows in ranked:
                if not guard.accepts(rows):
                    continue
                chosen = _choose_flow(rows, meter, registration, prior)
                if chosen is not None:
                    report["status"], report["trajectory"] = "ready", chosen
                    return report
    return report


def plan(job: dict, registration: dict, *, coordinated: bool, assets_root: Path | None = None) -> dict:
    """Plan one fixed-positioner or coordinated pass against the public scene."""
    try:
        return _plan(job, registration, coordinated, assets_root, None, None)
    except (KeyError, TypeError, AttributeError, OverflowError, ET.ParseError) as error:
        raise ValueError("Malformed job, registration, or robot description") from error


def plan_residual(job: dict, registration: dict, *, assets_root: Path | None = None,
                  start_velocity_rad_s=None, prior: MaterialState | None = None) -> dict:
    """Plan surviving material work from a held controller readback."""
    try:
        return _plan(job, registration, True, assets_root, start_velocity_rad_s, prior)
    except (KeyError, TypeError, AttributeError, OverflowError, ET.ParseError) as error:
        raise ValueError("Malformed job, registration, or robot description") from error
