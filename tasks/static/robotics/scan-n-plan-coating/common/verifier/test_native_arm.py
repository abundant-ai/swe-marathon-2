"""Independent checks of the coating arm's native geometry adapter."""

from itertools import combinations
import math
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

import mujoco
import numpy as np

from native_arm import NativeArm


CELL = Path(__file__).resolve().parents[2] / "environment/resources/cell"
NAMES = ("turret_yaw", "shoulder_pitch", "elbow_pitch", "wrist_roll", "wrist_pitch", "nozzle_roll")


def translate(x: float, y: float, z: float) -> np.ndarray:
    """Construct one authored rigid translation."""
    transform = np.eye(4)
    transform[:3, 3] = x, y, z
    return transform


def rotate(axis: str, angle: float) -> np.ndarray:
    """Construct an elementary fixed-axis rotation without using the adapter."""
    c, s = math.cos(angle), math.sin(angle)
    matrices = {"x": ((1, 0, 0), (0, c, -s), (0, s, c)),
                "y": ((c, 0, s), (0, 1, 0), (-s, 0, c)),
                "z": ((c, -s, 0), (s, c, 0), (0, 0, 1))}
    transform = np.eye(4)
    transform[:3, :3] = matrices[axis]
    return transform


def direct_tool(q: np.ndarray) -> np.ndarray:
    """Multiply authored URDF origins and elementary rotations by hand."""
    yaw, shoulder, elbow, roll, pitch, nozzle = q
    return (translate(0, 0, 0.15) @ rotate("z", yaw)
            @ translate(0, 0, 0.12) @ rotate("y", shoulder)
            @ translate(0.34, 0, 0) @ rotate("y", elbow)
            @ translate(0.27, 0, 0) @ rotate("x", roll)
            @ translate(0.07, 0, 0) @ rotate("y", pitch)
            @ translate(0.05, 0, 0) @ rotate("y", math.pi / 2) @ rotate("z", nozzle)
            @ translate(0, 0, 0.074))


class NativeArmTest(unittest.TestCase):
    def test_forward_kinematics_in_world_frame(self) -> None:
        """Cross-check zero, pure pan, folded and coupled ordered hinges."""
        arm = NativeArm(CELL / "arm.urdf", CELL / "arm.srdf", NAMES, "tool_tip")
        for q in (np.zeros(6), np.array([math.pi / 2, 0, 0, 0, 0, 0]),
                  np.array([0, 1.4, -2.4, 0, 0, 0]), np.array([.38, -.75, .7, -.3, .55, 1.1])):
            arm.set_q(q)
            np.testing.assert_allclose(arm.world_from_tool(), direct_tool(q), atol=2e-15)
        reversed_arm = NativeArm(CELL / "arm.urdf", CELL / "arm.srdf", NAMES[::-1], "tool_tip")
        reversed_arm.set_q(q[::-1])
        np.testing.assert_allclose(reversed_arm.world_from_tool(), direct_tool(q), atol=2e-15)
        np.testing.assert_array_equal(arm.lower_rad, [-3.05, -2.35, -2.58, -3.05, -2.5, -3.1])
        np.testing.assert_array_equal(arm.upper_rad, [3.05, 2.35, 2.58, 3.05, 2.5, 3.1])
        np.testing.assert_array_equal(arm.max_velocity_rad_s, [2.4, 2.2, 2.5, 3.0, 3.0, 4.0])

    def test_signed_distances_and_semantic_exclusion(self) -> None:
        """Keep designed adjacent collisions excluded and real base collisions enabled."""
        arm = NativeArm(CELL / "arm.urdf", CELL / "arm.srdf", NAMES, "tool_tip")
        geoms = {g.link: g.geom_id for g in arm.arm_geoms}
        self.assertEqual(set(geoms),
                         {"base", "turret", "upper_arm", "forearm", "wrist_roll_link", "wrist_pitch_link", "nozzle"})
        excluded = {frozenset((entry.attrib["link1"], entry.attrib["link2"]))
                    for entry in ET.parse(CELL / "arm.srdf").getroot().findall("disable_collisions")}
        ids = {frozenset(x) for x in arm.self_pairs}
        self.assertEqual(ids, {frozenset((geoms[a], geoms[b]))
                               for a, b in combinations(geoms, 2) if frozenset((a, b)) not in excluded})
        arm.set_q(np.zeros(6))
        turret_upper = mujoco.mj_geomDistance(arm.model, arm.data, geoms["turret"], geoms["upper_arm"], 2, None)
        self.assertLess(turret_upper, -0.04)
        self.assertAlmostEqual(arm.minimum_self_clearance(), 0.05, places=12)
        self.assertAlmostEqual(arm.minimum_self_clearance(max_distance_m=0.03), 0.03)
        with tempfile.TemporaryDirectory() as where:
            srdf = ET.parse(CELL / "arm.srdf")
            root = srdf.getroot()
            root.remove(next(row for row in root.findall("disable_collisions")
                             if (row.get("link1"), row.get("link2")) == ("turret", "upper_arm")))
            file = Path(where) / "unfiltered.srdf"
            srdf.write(file)
            filtered = NativeArm(CELL / "arm.urdf", file, NAMES, "tool_tip")
            self.assertAlmostEqual(filtered.minimum_self_clearance(), turret_upper, places=10)
        arm.set_q([0, 1.4, -2.4, 0, 0, 0])
        base_upper = mujoco.mj_geomDistance(arm.model, arm.data, geoms["base"], geoms["upper_arm"], 2, None)
        self.assertIn(frozenset((geoms["base"], geoms["upper_arm"])), ids)
        self.assertLess(base_upper, -0.08)
        self.assertAlmostEqual(arm.minimum_self_clearance(), base_upper, places=10)

    def test_explicit_urdf_fusion_does_not_erase_fixed_frame(self) -> None:
        """Retain the public tool tip even when the supplied compiler would fuse it."""
        with tempfile.TemporaryDirectory() as where:
            tree = ET.parse(CELL / "arm.urdf")
            node = ET.SubElement(tree.getroot(), "mujoco")
            ET.SubElement(node, "compiler", fusestatic="true")
            file = Path(where) / "fused.urdf"
            tree.write(file)
            direct = mujoco.MjModel.from_xml_path(str(file))
            self.assertEqual(mujoco.mj_name2id(direct, mujoco.mjtObj.mjOBJ_BODY, "tool_tip"), -1)
            arm = NativeArm(file, CELL / "arm.srdf", NAMES, "tool_tip")
            self.assertGreaterEqual(arm.tool_body_id, 0)
            np.testing.assert_allclose(arm.world_from_tool(), direct_tool(np.zeros(6)), atol=2e-15)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"])
