"""Load a public MoveIt arm model for independent MuJoCo pose and clearance checks."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
import math
from pathlib import Path
from xml.etree import ElementTree as ET

import mujoco
import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class ArmGeom:
    """Identify one native collision geom by its authoritative URDF link."""

    geom_id: int
    link: str
    name: str


def _required_name(node: ET.Element, attribute: str) -> str:
    """Return the nonempty XML name needed to link a model declaration."""
    value = node.get(attribute)
    if not value:
        raise ValueError(f"Missing {attribute} on {node.tag}")
    return value


def _robot_xml(path: Path) -> ET.Element:
    """Read a URDF or SRDF robot root without altering the commissioned file."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Malformed robot XML: {path}") from exc
    if root.tag != "robot":
        raise ValueError(f"Expected a robot root in {path}")
    return root


def _native_xml(root: ET.Element, source: Path) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Prepare native URDF XML and name each collision by its original link.

    Preserve fixed bodies, including the empty tool tip, through compilation.
    Explicit collision names keep the SRDF link identity independent of
    MuJoCo's body IDs for anchored or fixed geometry.
    """
    options = root.find("mujoco")
    if options is None:
        options = ET.SubElement(root, "mujoco")
    compiler = options.find("compiler")
    if compiler is None:
        compiler = ET.SubElement(options, "compiler")
    compiler.set("fusestatic", "false")
    compiler.set("discardvisual", "true")
    compiler.set("strippath", "false")
    attachments = []
    for link in root.findall("link"):
        link_name = _required_name(link, "name")
        for collision in link.findall("collision"):
            geom_name = f"scan_arm_collision_{len(attachments)}"
            collision.set("name", geom_name)
            attachments.append((link_name, geom_name))
            mesh = collision.find("geometry/mesh")
            if mesh is not None:
                name = _required_name(mesh, "filename")
                if "://" in name:
                    raise ValueError("Resolve robot mesh package URIs before native compilation")
                mesh.set("filename", str((source.parent / name).resolve()))
    return ET.tostring(root, encoding="unicode"), tuple(attachments)


def _read_exclusions(
    urdf: ET.Element, srdf: ET.Element, links: set[str],
) -> set[frozenset[str]]:
    """Read unordered SRDF exclusions and reject dangling configured link names."""
    if _required_name(urdf, "name") != _required_name(srdf, "name"):
        raise ValueError("SRDF robot name differs from the URDF")
    excluded = set()
    for entry in srdf.findall("disable_collisions"):
        pair = frozenset((_required_name(entry, "link1"), _required_name(entry, "link2")))
        if len(pair) != 2 or not pair <= links:
            raise ValueError("Invalid SRDF collision link pair")
        excluded.add(pair)
    return excluded


def _named_id(model: mujoco.MjModel, kind: mujoco.mjtObj, name: str) -> int:
    """Look up a commissioned name and fail visibly if the importer dropped it."""
    identity = mujoco.mj_name2id(model, kind, name)
    if identity < 0:
        raise ValueError(f"Native model omitted {kind.name} {name!r}")
    return identity


def _joint_addresses(
    model: mujoco.MjModel, declarations: dict[str, ET.Element], names: tuple[str, ...],
) -> tuple[IntArray, FloatArray, FloatArray, FloatArray]:
    """Collect native hinge coordinates and commissioned joint limits in wire order."""
    addresses, lower, upper, velocity = [], [], [], []
    for name in names:
        identity = _named_id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if model.jnt_type[identity] != mujoco.mjtJoint.mjJNT_HINGE or not model.jnt_limited[identity]:
            raise ValueError(f"Expected a bounded rotary hinge for joint {name!r}")
        bounds = declarations[name].find("limit")
        if bounds is None:
            raise ValueError(f"Missing limit element for joint {name!r}")
        lo, hi = (float(_required_name(bounds, field)) for field in ("lower", "upper"))
        speed = float(_required_name(bounds, "velocity"))
        if (not np.isfinite([lo, hi, speed]).all() or not lo < hi or speed <= 0
                or not np.allclose(model.jnt_range[identity], [lo, hi], atol=1e-12, rtol=0)):
            raise ValueError(f"Invalid or changed limits for joint {name!r}")
        addresses.append(int(model.jnt_qposadr[identity]))
        lower.append(lo)
        upper.append(hi)
        velocity.append(speed)
    return (np.array(addresses, dtype=np.int64), np.asarray(lower), np.asarray(upper), np.asarray(velocity))


class NativeArm:
    """Verifier-only adapter for the fixed-base, six-rotary-axis coating arm.

    The public model and data are available for composition with other
    native geometry queries. Numeric inputs are interpreted in declared
    arm-joint order. Each query observes the most recent set_q call.
    """

    def __init__(
        self, urdf_path: str | Path, srdf_path: str | Path, arm_joints: Sequence[str], tool_frame: str,
    ) -> None:
        """Compile URDF collision geometry and SRDF rules for one arm.

        Args:
            urdf_path: Path to the commissioned URDF, with local mesh paths if used.
            srdf_path: Matching semantic description containing link exclusions.
            arm_joints: Six distinct revolute URDF joint names in public wire order.
            tool_frame: URDF link whose positive Z is the nozzle's spray direction.

        Raises:
            ValueError: The supplied descriptions violate the arm contract or the
                native importer did not preserve a named joint, link or collision.
        """
        path = Path(urdf_path)
        urdf = _robot_xml(path)
        srdf = _robot_xml(Path(srdf_path))
        links = {_required_name(node, "name") for node in urdf.findall("link")}
        declarations = {_required_name(node, "name"): node for node in urdf.findall("joint")}
        names = tuple(arm_joints)
        moving = {name for name, node in declarations.items() if node.get("type") != "fixed"}
        if (len(names) != 6 or len(set(names)) != 6 or set(names) != moving
                or any(declarations[name].get("type") != "revolute" for name in names)):
            raise ValueError("Expected all six named rotary actuated joints")
        if tool_frame not in links:
            raise ValueError("Nozzle tool frame must name a commissioned link")
        disabled = _read_exclusions(urdf, srdf, links)
        xml, collisions = _native_xml(urdf, path)
        model = self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(model)
        self.arm_joints = names
        self.tool_frame = tool_frame
        self.tool_body_id = _named_id(model, mujoco.mjtObj.mjOBJ_BODY, tool_frame)
        self.qpos_addresses, self.lower_rad, self.upper_rad, self.max_velocity_rad_s = _joint_addresses(
            model, declarations, names,
        )
        for array in (self.qpos_addresses, self.lower_rad, self.upper_rad, self.max_velocity_rad_s):
            array.setflags(write=False)
        self.arm_geoms = tuple(
            ArmGeom(_named_id(model, mujoco.mjtObj.mjOBJ_GEOM, native), link, native)
            for link, native in collisions
        )
        self.self_pairs = tuple(
            (a.geom_id, b.geom_id) for a, b in combinations(self.arm_geoms, 2)
            if a.link != b.link and frozenset((a.link, b.link)) not in disabled
        )
        mujoco.mj_fwdPosition(self.model, self.data)

    def set_q(self, q_rad: ArrayLike) -> None:
        """Set six finite revolute angles and update native position geometry.

        Joint-limit qualification belongs to the trajectory check. This
        method therefore preserves supplied finite angles without clipping.
        """
        q = np.asarray(q_rad, dtype=np.float64)
        if q.shape != (len(self.arm_joints),) or not np.isfinite(q).all():
            raise ValueError("Expected six finite arm angles")
        self.data.qpos[self.qpos_addresses] = q
        # Position-only evaluation updates the transforms and collision geoms.
        # No simulation time or candidate-controlled velocities enter a query.
        mujoco.mj_fwdPosition(self.model, self.data)

    def world_from_tool(self) -> FloatArray:
        """Return an owned 4×4 world-from-tool pose in the URDF link convention."""
        transform = np.eye(4)
        transform[:3, :3] = self.data.xmat[self.tool_body_id].reshape(3, 3)
        transform[:3, 3] = self.data.xpos[self.tool_body_id]
        return transform

    def minimum_self_clearance(self, max_distance_m: float = 1e3) -> float:
        """Measure the least signed distance over all enabled collision pairs.

        Distances above max_distance_m are clipped by MuJoCo. Negative
        distance means penetration. A scene with no enabled pair has
        infinite self-clearance.
        """
        if not math.isfinite(max_distance_m) or max_distance_m <= 0:
            raise ValueError("Distance query cap must be finite and positive")
        return min(
            (mujoco.mj_geomDistance(self.model, self.data, a, b, max_distance_m, None) for a, b in self.self_pairs),
            default=math.inf,
        )
