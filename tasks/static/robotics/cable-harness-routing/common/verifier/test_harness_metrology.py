"""Independent analytic controls for material coordinates and pose geometry."""

from math import cos, pi, sin
import unittest

import numpy as np

from harness_metrology import Centerline, ClipGate, Snapshot, assess_retention, measure_bend, observe_gate


def samples(xs, tags, *, y=0.0, z=0.0):
    return Centerline([(x, y, z) for x in xs], tags)


def circle_gate(*, center=(0.0, 0.0, 0.0), interval=(.12, .22), direction=1, key="center"):
    return ClipGate(key, center, [1, 0, 0], interval, through_direction=direction, radius_m=.016)


class MaterialCoordinatesTest(unittest.TestCase):
    def test_stretch_preserves_the_material_label(self):
        line = samples([-.03, .06], [.1, .4])
        np.testing.assert_allclose(line.point_at_material(.20), [0, 0, 0], atol=1e-14)
        np.testing.assert_allclose(line.point_at_arc(.03), [0, 0, 0], atol=1e-14)
        np.testing.assert_allclose(line.point_at_arc(0), [-.03, 0, 0], atol=1e-14)
        np.testing.assert_allclose(line.point_at_arc(.09), [.06, 0, 0], atol=1e-14)
        self.assertAlmostEqual(line.spatial_length_m, .09)
        self.assertEqual(line.material_range_m, (.1, .4))
        self.assertEqual(line.point_at_material(.4), (.06, 0, 0))

    def test_reject_wrong_unit_extrapolation_and_invalid_tags(self):
        line = samples([-.05, .05], [0, .1])
        for query in [-1e-6, 100, np.inf, float("nan"), True, ".02"]:
            with self.subTest(query=query), self.assertRaises(ValueError):
                line.point_at_material(query)
        for tags in [[0, .0], [.2, .1], [-.1, 0], [0, float("nan")]]:
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                samples([-.05, .05], tags)

    def test_coincident_points_preserve_all_material_without_fake_spatial_progress(self):
        line = samples([-.05, 0, 0, .05], [0, .05, .06, .11])
        self.assertEqual(line.point_at_material(.058), (0.0, 0.0, 0.0))
        self.assertEqual(line.point_at_arc(.05), (0.0, 0.0, 0.0))
        np.testing.assert_allclose(line.point_at_arc(.053), [.003, 0, 0], atol=1e-15)

    def test_snapshot_coordinates_are_owned(self):
        points = np.array([[-.01, 0., 0.], [.01, 0., 0.]])
        identity = np.array([.12, .14])
        measured = Centerline(points, identity)
        points[0] = np.nan
        identity[1] = .9
        self.assertEqual(measured.material_range_m, (.12, .14))
        with self.assertRaises(ValueError):
            measured.points_m[0, 0] = 0


class GateTest(unittest.TestCase):
    def test_same_geometry_wrong_material_tags_fails(self):
        expected = observe_gate(samples([-.08, .04], [.08, .2]), circle_gate())
        mislabeled = observe_gate(samples([-.08, .04], [.22, .34]), circle_gate())
        self.assertEqual(expected.status, "seated")
        self.assertEqual(mislabeled.status, "wrong_material")
        self.assertEqual(expected.crossings[0].point_m, mislabeled.crossings[0].point_m)
        self.assertAlmostEqual(expected.crossings[0].material_s_m, .16)
        self.assertAlmostEqual(mislabeled.crossings[0].material_s_m, .30)
        self.assertAlmostEqual(expected.crossings[0].spatial_s_m, .08)

    def test_signed_traversal_is_independent_from_material_lookup(self):
        wrong = samples([.04, -.04], [.1, .28])
        positive = observe_gate(wrong, circle_gate())
        negative = observe_gate(wrong, circle_gate(direction=-1))
        self.assertEqual(positive.status, "wrong_direction")
        self.assertEqual(negative.status, "seated")
        self.assertEqual(negative.crossings[0].direction, -1)
        self.assertAlmostEqual(negative.crossings[0].material_s_m, .19)

    def test_sample_exactly_on_plane_is_one_crossing(self):
        line = samples([-.04, 0, .04], [.1, .14, .3])
        result = observe_gate(line, circle_gate())
        self.assertEqual(result.status, "seated")
        self.assertEqual(len(result.crossings), 1)
        self.assertEqual(result.crossings[0].material_s_m, .14)

    def test_touch_endpoint_and_aperture_miss_do_not_count(self):
        gate = circle_gate()
        for line in (samples([-.04, 0, -.04], [.1, .15, .3]),
                     samples([-.04, 0], [.1, .15]),
                     samples([-.04, .04], [.1, .20], y=.017)):
            result = observe_gate(line, gate)
            self.assertEqual(result.status, "no_crossing")
            self.assertFalse(result.crossings)

    def test_nonadjacent_crossings_are_ambiguous_even_if_one_material_passes(self):
        line = Centerline([[-.04, 0, 0], [.04, 0, 0], [.04, .01, 0], [-.04, .01, 0]],
                          [.1, .24, .31, .48])
        measured = observe_gate(line, circle_gate())
        self.assertEqual(measured.status, "ambiguous")
        self.assertEqual([crossing.direction for crossing in measured.crossings], [1, -1])
        self.assertAlmostEqual(measured.crossings[0].material_s_m, .17)
        self.assertAlmostEqual(measured.crossings[1].material_s_m, .395)

    def test_coincident_material_span_and_coplanar_aperture_interval_are_ambiguous(self):
        gate = circle_gate()
        repeated = samples([-.05, 0, 0, .05], [.06, .14, .16, .28])
        through_plane = Centerline([[-.04, -.03, 0], [0, -.03, 0], [0, .03, 0], [.04, .03, 0]],
                                   [.08, .12, .22, .36])
        for line, interval in [(repeated, (.14, .16)), (through_plane, (.12, .22))]:
            result = observe_gate(line, gate)
            self.assertEqual(result.status, "ambiguous")
            self.assertEqual(result.coplanar_material_ranges_m, (interval,))

    def test_nontraversing_coplanar_branch_outside_aperture_does_not_hide_other_crossing(self):
        line = Centerline([[-.04, .06, 0], [0, .05, 0], [0, .04, 0],
                           [-.04, .04, 0], [-.04, 0, 0], [.04, 0, 0]],
                          [.01, .02, .03, .04, .10, .28])
        observation = observe_gate(line, circle_gate())
        self.assertTrue(observation.seated)
        self.assertEqual(len(observation.crossings), 1)
        self.assertEqual(observation.coplanar_material_ranges_m, ())

    def test_oriented_rectangle_and_inclusive_material_bounds(self):
        heading = pi / 4
        u = np.array([0, cos(heading), sin(heading)])
        v = np.cross([1, 0, 0], u)
        origin = np.array([.3, -.11, .67])
        gate = ClipGate("rectangle", origin, [12, 0, 0], (.2, .2),
                        half_extents_m=(.021, .005), u_axis=u)
        first = origin + .011 * u + .004 * v
        other = origin + .011 * u + .006 * v
        xyz = np.array([[-.025, 0, 0], [.025, 0, 0]])
        a = observe_gate(Centerline(xyz + first, [.1, .3]), gate)
        b = observe_gate(Centerline(xyz + other, [.1, .3]), gate)
        self.assertEqual(a.status, "seated")
        self.assertEqual(b.status, "no_crossing")
        # Both vertices lie outside the aperture but their coplanar edge crosses it.
        coplanar = observe_gate(Centerline([origin - .015*v, origin + .015*v], [.1, .3]), gate)
        self.assertEqual(coplanar.status, "ambiguous")


class BendTest(unittest.TestCase):
    def test_radius_of_known_circle(self):
        angles = np.linspace(-.8, .8, 81)
        radius = .12
        target = radius * np.column_stack((np.cos(angles), np.sin(angles), np.zeros_like(angles)))
        measured = measure_bend(Centerline(target, (angles + .8) * radius), half_window_m=.019,
                                max_native_gap_m=.003)
        self.assertEqual(measured.status, "finite")
        self.assertAlmostEqual(measured.minimum_radius_m, radius, delta=.0006)
        self.assertTrue(measured.passes_minimum(.10))
        self.assertFalse(measured.passes_minimum(.13))
        self.assertGreater(measured.sampled_centers, 60)

    def test_collinear_repeats_stay_straight_and_fold_is_zero_radius(self):
        straight = measure_bend(samples([0, .02, .02, .04, .06], [0, .02, .03, .05, .07]),
                                half_window_m=.012)
        self.assertEqual(straight.status, "straight")
        self.assertIsNone(straight.minimum_radius_m)
        self.assertTrue(straight.passes_minimum(.015))
        fold = measure_bend(samples([0, .02, .04, .02, 0], [0, .02, .04, .06, .08]),
                            half_window_m=.015)
        self.assertEqual(fold.status, "finite")
        self.assertEqual(fold.minimum_radius_m, 0)
        self.assertFalse(fold.passes_minimum(.001))

    def test_insufficient_native_resolution_and_short_lines_are_unresolved(self):
        cases = (
            (samples([0, .002, .004], [0, .002, .004]), .003, None),
            (samples([0, .02, .04], [0, .02, .04]), .012, .015),
            (samples([0, .04], [0, .04]), .012, None),
            (samples([.02, .02, .02], [0, .02, .04]), .012, None),
        )
        for line, half, max_gap in cases:
            with self.subTest(spatial_length=line.spatial_length_m):
                result = measure_bend(line, half_window_m=half, max_native_gap_m=max_gap)
                self.assertEqual(result.status, "unresolved")
                self.assertFalse(result.passes_minimum(0))


class RetentionTest(unittest.TestCase):
    def test_pull_leaves_and_recovers_while_fixture_switch_stays_true(self):
        stable = samples([-.04, .04], [.1, .28])
        moved = samples([-.04, .04], [.1, .28], y=.04)
        physical = [Snapshot(20, stable), Snapshot(21, moved), Snapshot(22, stable)]
        cabinet_switches = [True, True, True]
        self.assertTrue(all(cabinet_switches))
        result = assess_retention(physical, [circle_gate()])
        self.assertFalse(result.passed)
        self.assertEqual(result.first_crossings_m, result.last_crossings_m)
        self.assertEqual([(x.tick, x.clip_id, x.reason) for x in result.violations],
                         [(21, "center", "no_crossing")])

    def test_order_and_drift_are_measured_from_native_material_positions(self):
        first = circle_gate(center=(-.02, 0, 0), interval=(.06, .16), key="first")
        second = circle_gate(center=(.02, 0, 0), interval=(.12, .25), key="second")
        old = samples([-.04, .04], [.06, .22])
        slipped = samples([-.04, .04], [.074, .234])
        snapshots = [Snapshot(10, old), Snapshot(11, slipped)]
        self.assertTrue(assess_retention(snapshots, [first, second]).passed)
        self.assertFalse(assess_retention(snapshots, [second, first]).passed)
        result = assess_retention(snapshots, [first, second], max_material_drift_m=.005)
        self.assertFalse(result.passed)
        self.assertEqual([finding.reason for finding in result.violations],
                         ["material_drift", "material_drift"])

    def test_history_with_large_gap_or_only_one_snapshot_does_not_certify_retention(self):
        line = samples([-.04, .04], [.1, .28])
        gate = circle_gate()
        self.assertFalse(assess_retention([Snapshot(10, line)], [gate]).passed)
        self.assertTrue(assess_retention([Snapshot(10, line), Snapshot(12, line)], [gate]).passed)
        result = assess_retention([Snapshot(10, line), Snapshot(12, line)], [gate], max_snapshot_gap_ticks=1)
        self.assertEqual(result.violations[0].reason, "snapshot_gap")
        with self.assertRaises(ValueError):
            assess_retention([Snapshot(10, line), Snapshot(10, line)], [gate])


if __name__ == "__main__":
    unittest.main()
