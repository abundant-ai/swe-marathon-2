"""Analytic regressions for the independent coating process kernel."""

from math import cos, pi, sin
import unittest

import numpy as np

from surface_dose import RigidBody, SurfaceDose, TriangleMesh, first_hit


def panel(
    x: tuple[float, float], y: tuple[float, float], *, front: bool = True,
) -> TriangleMesh:
    """Create the indexed triangles of one rectangle in its local XY plane."""
    vertices = [(x[0], y[0], 0), (x[1], y[0], 0), (x[1], y[1], 0), (x[0], y[1], 0)]
    triangles = [(0, 1, 2), (0, 2, 3)] if front else [(0, 2, 1), (0, 3, 2)]
    return TriangleMesh(vertices, triangles)


def placed(
    name: str, mesh: TriangleMesh, *, offset: tuple[float, float, float] = (0, 0, 0),
) -> RigidBody:
    """Position a local panel with a pure translation."""
    pose = np.eye(4)
    pose[:3, 3] = offset
    return RigidBody(name, mesh, pose)


def recipe(
    dose: tuple[float, float] = (0.0, 1e8), *, fraction: float = 1, excess: float = 1e8,
) -> dict[str, tuple[float, float] | float]:
    """Make a qualification band without prescribing nozzle process kinematics."""
    return {"target_dose_ml_m2": dose, "min_covered_fraction": fraction, "max_off_target_ml": excess}


class SurfaceDoseTest(unittest.TestCase):
    """Compare measurements with geometry and integrals known independently."""

    def test_full_plane_collects_the_emitted_volume(self) -> None:
        """A plane covering the complete cone subtends its full solid angle."""
        mesh = panel((-0.65, 0.65), (-0.65, 0.65))
        meter = SurfaceDose(mesh, (0, 1), subdivisions=144)
        hit = meter.sample([placed("part", mesh)], [0, 0, 1], [0, 0, -4],
                           flow_ml_s=7.2, duration_s=0.5, cone_half_angle_rad=0.42)
        result = meter.score(recipe())
        self.assertIsNotNone(hit)
        self.assertEqual(hit.face_index, 0)
        self.assertAlmostEqual(hit.distance_m, 1)
        self.assertAlmostEqual(result.target_area_m2, 1.69)
        self.assertAlmostEqual(result.target_deposited_ml, 3.6, delta=0.026)
        self.assertAlmostEqual(result.total_deposited_ml, result.target_deposited_ml)
        self.assertEqual(result.off_target_ml, 0)

    def test_analytic_oblique_single_cell(self) -> None:
        """Oblique incidence and range have the specified inverse-square dose."""
        mesh = TriangleMesh([(0, 0, 0), (0.3, 0, 0), (0, 0.6, 0)], [(0, 1, 2)])
        meter = SurfaceDose(mesh, (0,), subdivisions=1)
        center = np.array([0.1, 0.2, 0])
        origin = np.array([0, 0, 0.4])
        aim = center - origin
        distance = float(np.linalg.norm(aim))
        meter.sample([placed("part", mesh)], origin, aim, flow_ml_s=0.8,
                     duration_s=1.25, cone_half_angle_rad=0.17)
        density = 0.4 / (distance**3 * 2 * pi * (1 - cos(0.17)))
        result = meter.score(recipe((density - 1e-8, density + 1e-8), excess=0))
        self.assertAlmostEqual(result.target_min_ml_m2, density, places=9)
        self.assertAlmostEqual(result.target_deposited_ml, density * 0.09, places=10)
        self.assertTrue(result.qualified)

    def test_mask_and_unpainted_area_enter_the_correct_denominators(self) -> None:
        """Only coated target area counts toward coverage and any mask volume is excess."""
        vertices = [(-0.2, -0.1, 0), (0.2, -0.1, 0), (0.2, 0.1, 0), (-0.2, 0.1, 0),
                    (1.6, -0.3, 0), (2.0, -0.3, 0), (2.0, 0.3, 0), (1.6, 0.3, 0)]
        mesh = TriangleMesh(vertices, [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)])
        meter = SurfaceDose(mesh, (0, 2, 3), subdivisions=12)
        meter.sample([placed("part", mesh)], [0, 0, 0.6], [0, 0, -1], flow_ml_s=2.0,
                     duration_s=1.1, cone_half_angle_rad=0.5)
        result = meter.score(recipe((0.1, 100), fraction=0.13, excess=2.0))
        self.assertAlmostEqual(result.target_area_m2, 0.28)
        self.assertAlmostEqual(result.covered_area_m2, 0.04)
        self.assertAlmostEqual(result.covered_fraction, 1 / 7)
        self.assertEqual(result.target_min_ml_m2, 0)
        self.assertAlmostEqual(result.off_target_ml, result.target_deposited_ml)
        self.assertTrue(result.qualified)
        self.assertFalse(meter.score(recipe((0.1, 100), fraction=0.14, excess=0)).qualified)
        self.assertFalse(meter.score(recipe((0.1, 100), fraction=0.145, excess=2.0)).qualified)

    def test_fixture_backfaces_block_and_frontfaces_consume_volume(self) -> None:
        """The nearest hit blocks the part from either side and receives front dose only."""
        mesh = panel((-0.3, 0.3), (-0.3, 0.3))
        blocker = panel((-0.2, 0.2), (-0.2, 0.2), front=False)
        front = panel((-0.2, 0.2), (-0.2, 0.2))
        position = [0, 0, 1]
        args = {"flow_ml_s": 3, "duration_s": 1, "cone_half_angle_rad": 0.6}
        part = placed("part", mesh)
        meter = SurfaceDose(mesh, (0, 1), subdivisions=14)
        back_hit = meter.sample([part, placed("fixture", blocker, offset=(0, 0, 0.5))],
                                position, [0, 0, -1], **args)
        self.assertIsNotNone(back_hit)
        self.assertEqual(back_hit.body_id, "fixture")
        self.assertAlmostEqual(back_hit.distance_m, 0.5)
        self.assertAlmostEqual(back_hit.normal_error_rad, pi)
        np.testing.assert_allclose(back_hit.part_point, [0, 0, 0.5], atol=1e-14)
        self.assertEqual(meter.score(recipe()).total_deposited_ml, 0)
        meter.sample([placed("world-shell", front, offset=(0, 0, 0.5)), part],
                     position, [0, 0, -1], **args)
        result = meter.score(recipe((0.1, 10)))
        self.assertEqual(result.target_deposited_ml, 0)
        self.assertGreater(result.off_target_ml, 0.9)
        self.assertAlmostEqual(result.off_target_ml, meter.external_volume_ml["world-shell"])
        self.assertEqual(result.covered_fraction, 0)

    def test_remount_preserves_the_part_grid_and_hit_coordinates(self) -> None:
        """A rigid pose change leaves local hit location and received dose invariant."""
        mesh = panel((-0.2, 0.2), (-0.2, 0.2))
        meter = SurfaceDose(mesh, (0, 1), subdivisions=9, max_cell_edge_m=0.04)
        origin, axis = np.array([0.07, -0.06, 0.4]), np.array([0, 0, -1])
        arguments = {"flow_ml_s": 0.9, "duration_s": 0.5, "cone_half_angle_rad": 0.37}
        initial = meter.sample([placed("part", mesh)], origin, axis, **arguments)
        initial_dose = meter.part_dose_ml_m2
        angle = 0.92
        rotation = np.array([[cos(angle), 0, sin(angle)], [0, 1, 0], [-sin(angle), 0, cos(angle)]])
        shift = np.array([0.4, -0.17, 0.32])
        pose = np.eye(4)
        pose[:3, :3], pose[:3, 3] = rotation, shift
        mount = RigidBody("part", mesh, pose)
        moved = meter.sample([mount], rotation @ origin + shift, rotation @ axis, **arguments)
        self.assertIsNotNone(initial)
        self.assertIsNotNone(moved)
        np.testing.assert_allclose(initial.part_point, moved.part_point, atol=1e-14)
        np.testing.assert_allclose(initial.part_normal, moved.part_normal, atol=1e-14)
        np.testing.assert_allclose(moved.world_point, rotation @ initial.world_point + shift, atol=1e-14)
        np.testing.assert_allclose(moved.world_normal, rotation @ initial.world_normal, atol=1e-14)
        self.assertAlmostEqual(initial.distance_m, moved.distance_m)
        np.testing.assert_allclose(meter.part_dose_ml_m2, 2 * initial_dose, atol=1e-12)

    def test_half_open_receipt_splits_preserve_part_and_world_dose(self) -> None:
        """Touching held-flow subintervals integrate the original interval once."""
        mesh = panel((0.05, 0.30), (-0.25, 0.25))
        fixture = panel((-0.5, -0.05), (-0.4, 0.4))
        bodies = [placed("part", mesh), placed("guard", fixture, offset=(0, 0, 0.15))]
        whole = SurfaceDose(mesh, (0,))
        split = SurfaceDose(mesh, (0,))
        for meter, durations in ((whole, (0.75,)), (split, (0.125, 0.25, 0.375))):
            for duration in durations:
                meter.sample(bodies, [0.1, 0, 0.5], [0, 0, -1], flow_ml_s=1.3,
                             duration_s=duration, cone_half_angle_rad=1.0)
        # The state at the shared endpoint has no duration of its own.
        split.sample(bodies, [0.1, 0, 0.5], [0, 0, -1], flow_ml_s=19,
                     duration_s=0.0, cone_half_angle_rad=1.0)
        np.testing.assert_allclose(whole.part_dose_ml_m2, split.part_dose_ml_m2, atol=1e-14)
        for metric in ("off_target_ml", "target_deposited_ml", "total_deposited_ml"):
            self.assertAlmostEqual(getattr(whole.score(recipe()), metric), getattr(split.score(recipe()), metric))
        self.assertGreater(whole.external_volume_ml["guard"], 0)

    def test_body_face_ties_and_hierarchy_do_not_depend_on_iteration_order(self) -> None:
        """Shared triangles and repeated candidates have a deterministic nearest owner."""
        mesh = panel((-1.0, 1.0), (-1.0, 1.0))
        part = placed("part", mesh)
        cover = placed("a-cover", mesh)
        for bodies in ((part, cover), (cover, part)):
            hit = first_hit(bodies, [0, 0, 1], [0, 0, -1])
            self.assertIsNotNone(hit)
            self.assertEqual((hit.body_id, hit.face_index), ("a-cover", 0))
        vertices, triangles = [], []
        for i in range(7):
            for j in range(6):
                point = (float(i), float(j))
                next_vertex = len(vertices)
                vertices.extend([(point[0], point[1], 0), (point[0] + 1, point[1], 0),
                                 (point[0] + 1, point[1] + 1, 0), (point[0], point[1] + 1, 0)])
                triangles.extend([(next_vertex, next_vertex + 1, next_vertex + 2),
                                  (next_vertex, next_vertex + 2, next_vertex + 3)])
        grid = placed("part", TriangleMesh(vertices, triangles))
        hit = first_hit([grid], [4.7, 4.2, 1], [0, 0, -1])
        self.assertIsNotNone(hit)
        self.assertEqual(hit.face_index, 2 * (4 * 6 + 4))
        self.assertIsNone(first_hit([grid], [7.2, 2.0, 1], [0, 0, -1]))


if __name__ == "__main__":
    unittest.main()
