"""Independent analytic and native trajectory checks of sampled scene clearance."""

import math
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

import mujoco
import numpy as np

from coating_scene import CoatingScene
from native_arm import NativeArm
from scene_clearance import INTERSECTION_M, SceneClearance, _primitive
from surface_dose import RigidBody, TriangleMesh


CELL = Path(__file__).resolve().parents[2] / "environment/resources/cell"
JOINTS = ("turret_yaw", "shoulder_pitch", "elbow_pitch", "wrist_roll", "wrist_pitch", "nozzle_roll")


def new_arm(urdf: Path | None = None) -> NativeArm:
    """Load the real coating arm or one primitive-variation URDF."""
    return NativeArm(urdf or CELL / "arm.urdf", CELL / "arm.srdf", JOINTS, "tool_tip")


def join_panels(quads: tuple[list[tuple[float, float, float]], ...]) -> TriangleMesh:
    """Build indexed triangles for the exact planar faces of the fixture."""
    vertices = []
    faces = []
    for quad in quads:
        start = len(vertices)
        vertices.extend(quad)
        faces.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))
    return TriangleMesh(vertices, faces)


def wall(x: float, y: float = .06, *, lower_z: float = .24, upper_z: float = .30) -> TriangleMesh:
    """Construct a rectangle in the constant-x plane near the nozzle."""
    return join_panels(([(x, -y, lower_z), (x, y, lower_z), (x, y, upper_z), (x, -y, upper_z)],))


def body(name: str, geometry: TriangleMesh, translation: tuple[float, float, float] = (0, 0, 0)) -> RigidBody:
    """Place indexed geometry with a constant translation in the chosen parent frame."""
    pose = np.eye(4)
    pose[:3, 3] = translation
    return RigidBody(name, geometry, pose)


class SceneClearanceTest(unittest.TestCase):
    def test_authored_nozzle_and_static_base_analytic_gaps(self) -> None:
        """Check cylinder half-length conversion and inclusion of the base."""
        clearance = SceneClearance(new_arm())
        tip_plane = body("end-plane", wall(.814))
        base_floor = body("base-floor", join_panels((
            [(-.03, -.03, -.012), (.03, -.03, -.012), (.03, .03, -.012), (-.03, .03, -.012)],
        )))
        self.assertAlmostEqual(clearance.at((tip_plane,)), .010, places=8)
        self.assertAlmostEqual(clearance.at((base_floor,)), .012, places=10)
        self.assertAlmostEqual(clearance.at((tip_plane, base_floor), distance_cap_m=.005), .005)
        self.assertAlmostEqual(clearance.at(()), .05)

    def test_swept_arm_and_rotary_fixture_have_interior_crossings(self) -> None:
        """Test a real base-pan sweep and a fixture rotation about the authored world frame."""
        arm = new_arm()
        clearance = SceneClearance(arm)
        blade = body("blade", wall(.775, .04, lower_z=.252, upper_z=.293))
        joints = np.zeros(6)
        arc = []
        for yaw in (-.4, -.2, 0., .2, .4):
            joints[0] = yaw
            arm.set_q(joints)
            arc.append(clearance.at((blade,)))
        self.assertGreater(arc[0], .02)
        self.assertGreater(arc[-1], .02)
        self.assertEqual(arc[2], INTERSECTION_M)
        arm.set_q(np.zeros(6))
        far_part = wall(2.0)
        scene = CoatingScene(far_part, np.eye(4), np.eye(4), (blade,), ())
        self.assertGreater(clearance.at(scene.place(-.4, np.eye(4))), .02)
        self.assertEqual(clearance.at(scene.place(0., np.eye(4))), INTERSECTION_M)
        self.assertGreater(clearance.at(scene.place(.4, np.eye(4))), .02)

    def test_open_u_fixture_retains_free_space_inside_its_hull(self) -> None:
        """Nozzle can occupy an open channel whose convex hull would collide."""
        fixture = join_panels(tuple(
            [[(.74, y, .235), (.834, y, .235), (.834, y, .305), (.74, y, .305)] for y in (-.055, .055)]
        ) + ([(.834, -.055, .235), (.834, .055, .235), (.834, .055, .305), (.834, -.055, .305)],))
        clearance = SceneClearance(new_arm())
        # The nearest surface is a sidewall's opening edge viewed from the
        # wrist pitch cylinder. The nozzle itself clears the back by 30 mm.
        self.assertAlmostEqual(clearance.at((body("return", fixture),)), math.hypot(.01, .025), places=8)
        self.assertEqual(clearance.at((body("moved-return", fixture, (-.042, 0, 0)),)), INTERSECTION_M)

    def test_box_sphere_and_unsupported_native_types(self) -> None:
        """Verify box side lengths and sphere radii survive both library conversions."""
        fixtures = (
            ("box", {"size": "0.036 0.036 0.074"}, .814),
            ("sphere", {"radius": "0.021"}, .798),
        )
        with tempfile.TemporaryDirectory() as output:
            for kind, attributes, plane in fixtures:
                urdf = ET.parse(CELL / "arm.urdf")
                geometry = urdf.getroot().find("link[@name='nozzle']/collision/geometry")
                geometry.clear()
                ET.SubElement(geometry, kind, attributes)
                path = Path(output) / "primitive.urdf"
                urdf.write(path)
                clearance = SceneClearance(new_arm(path))
                self.assertAlmostEqual(clearance.at((body("obstacle", wall(plane)),)), .010, places=8)
        with self.assertRaisesRegex(ValueError, "Unsupported MuJoCo"):
            _primitive(int(mujoco.mjtGeom.mjGEOM_CAPSULE), np.array([.01, .02, 0.]), "unsupported")

    def test_native_self_penetration_and_invalid_cap(self) -> None:
        """Use the commissioned SRDF even when no external surfaces are nearby."""
        arm = new_arm()
        arm.set_q([0, 1.4, -2.4, 0, 0, 0])
        clearance = SceneClearance(arm)
        native = arm.minimum_self_clearance()
        self.assertLess(native, -.08)
        self.assertAlmostEqual(clearance.at(()), native)
        with self.assertRaises(ValueError):
            clearance.at((), distance_cap_m=math.nan)


    def test_disjoint_arm_boxes_disprove_spurious_native_zero(self) -> None:
        """Reject a false cylinder contact on an actual remount recovery bridge."""
        arm = new_arm()
        arm.set_q([
            -.32472886061717593, -.7273432747382416, 1.439044346593914,
            .09114387138858215, -.7108482895811336, -2.2010646465342017e-17,
        ])
        clearance = SceneClearance(arm)
        centers, extents = clearance._place_arm()
        native_pair = {part.link: i for i, part in enumerate(arm.arm_geoms)}
        a, b = (native_pair[link] for link in ("turret", "wrist_pitch_link"))
        certified_gap = np.linalg.norm(np.maximum(np.abs(centers[a] - centers[b]) - extents[a] - extents[b], 0.0))
        self.assertGreater(certified_gap, .37)
        self.assertGreater(clearance.at(()), .025)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"])
