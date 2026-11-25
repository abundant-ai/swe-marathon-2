"""Analytic controls for distinct entry, through-routing, and conservation."""

import unittest

from harness_metrology import Centerline, ClipGate, observe_gate
from harness_temporal import RouteClip, TemporalSnapshot, assess_route


X = [0., .08, .12, .23, .27, .35]
TAGS = [0., .08, .12, .23, .27, .35]


def route_clip(key, x, inward=1, through=1):
    tag = (x - .021, x + .021)
    mouth = ClipGate(key, [x, .04 * inward, .005], [0, inward, 0], tag,
                     half_extents_m=(.019, .004), u_axis=[1, 0, 0])
    seat = ClipGate(key, [x, .060 * inward, .005], [1, 0, 0], tag, through_direction=through,
                    half_extents_m=(.011, .004), u_axis=[0, 1, 0])
    return RouteClip(seat, mouth)


def measured(tick, first_y, second_y, latches=(), *, shift_x=0., tags=TAGS):
    points = [(x + shift_x, y, .005) for x, y in zip(X, [0, first_y, first_y, second_y, second_y, 0], strict=True)]
    return TemporalSnapshot(tick, Centerline(points, tags), frozenset(latches))


class TemporalRouteTest(unittest.TestCase):
    def setUp(self):
        self.first = route_clip("start", .1, 1)
        self.second = route_clip("return", .25, -1)
        self.route = [self.first, self.second]
        self.trace = [
            measured(0, .00, .00),
            measured(1, .03, .00),
            measured(2, .06, -.02, ("start",)),
            measured(3, .06, -.04, ("start",)),
            measured(4, .06, -.06, ("start", "return")),
            measured(5, .06, -.06, ("start", "return")),
        ]

    def test_opposite_lateral_entry_and_same_material_through_direction(self):
        result = assess_route(self.trace, self.route, max_snapshot_gap_ticks=1)
        self.assertTrue(result.passed)
        first, second = result.installations
        self.assertAlmostEqual(first.material_s_m, .1)
        self.assertAlmostEqual(second.material_s_m, .25)
        self.assertAlmostEqual(first.entry.tick, 1 + 1/3)
        self.assertAlmostEqual(second.entry.tick, 3.)
        self.assertTrue(first.entry.inward and second.entry.inward)
        for clip in self.route:
            self.assertEqual(observe_gate(self.trace[-1].line, clip.seat).crossings[0].direction, 1)

    def test_same_final_geometry_cannot_replace_temporal_entry(self):
        wrong_side = route_clip("return", .25, -1)
        # Declare the opposite direction for the same sheet of the mouth.
        flipped = ClipGate("return", wrong_side.mouth.origin_m, [0, 1, 0], (.23, .27),
                           half_extents_m=(.019, .004), u_axis=[1, 0, 0])
        result = assess_route(self.trace, [self.first, RouteClip(self.second.seat, flipped)])
        self.assertFalse(result.passed)
        self.assertIn((4, "outward_lateral_entry"), [(x.tick, x.reason) for x in result.findings])
        self.assertEqual(dict(result.final_occupants_m), {"start": .1, "return": .25})

    def test_valid_approach_for_other_material_cannot_authorize_current_tag(self):
        trace = [
            measured(0, 0., 0., shift_x=.065),
            measured(1, .035, 0., shift_x=.065),
            measured(2, .050, 0., shift_x=.065),
            measured(3, .060, 0., ("start",)),
            measured(4, .060, 0., ("start",)),
        ]
        result = assess_route(trace, [self.first])
        self.assertFalse(result.passed)
        self.assertIn("entry_outside_mouth", [x.reason for x in result.findings])
        self.assertTrue(observe_gate(trace[-1].line, self.first.seat).seated)

    def test_recent_bad_passage_invalidates_an_older_allowed_crossing(self):
        trace = [
            measured(0, 0., 0.),
            measured(1, .055, 0.),
            measured(2, 0., 0.),
            measured(3, .045, 0., shift_x=.06),
            measured(4, .06, 0., ("start",)),
            measured(5, .06, 0., ("start",)),
        ]
        result = assess_route(trace, [self.first])
        self.assertFalse(result.passed)
        self.assertIn("entry_outside_mouth", [x.reason for x in result.findings])

    def test_earlier_clip_lost_during_later_route_even_if_final_restored(self):
        trace = list(self.trace)
        trace[3] = measured(3, .014, -.04, ("start",))
        self.assertTrue(all("start" in frame.latched_clip_ids for frame in trace[2:]))
        result = assess_route(trace, self.route)
        self.assertFalse(result.passed)
        self.assertEqual(dict(result.final_occupants_m), {"start": .1, "return": .25})
        self.assertIn((3, "start", "seat_no_crossing"), [
            (finding.tick, finding.clip_id, finding.reason) for finding in result.findings
        ])

    def test_loss_of_latch_with_geometry_intact_fails(self):
        trace = list(self.trace)
        trace[3] = measured(3, .06, -.04)
        result = assess_route(trace, self.route)
        self.assertFalse(result.passed)
        self.assertIn("released_after_latch", [x.reason for x in result.findings])

    def test_retention_of_correct_geometry_without_authoritative_latch_fails_completion(self):
        trace = [measured(frame.tick, .06, -.06) for frame in self.trace]
        result = assess_route(trace, self.route)
        self.assertFalse(result.passed)
        self.assertEqual([x.reason for x in result.findings], ["missing_installation", "missing_installation"])

    def test_material_order_does_not_prescribe_chronological_latch_order(self):
        trace = [
            measured(0, 0., 0.),
            measured(1, 0., -.06, ("return",)),
            measured(2, .03, -.06, ("return",)),
            measured(3, .06, -.06, ("start", "return")),
        ]
        result = assess_route(trace, self.route)
        self.assertTrue(result.passed)
        self.assertEqual([x.clip_id for x in result.installations], ["return", "start"])
        invalid = assess_route(trace, list(reversed(self.route)))
        self.assertIn("material_order", [x.reason for x in invalid.findings])

    def test_wrong_through_direction_does_not_pass_correct_lateral_entry(self):
        wrong = route_clip("start", .1, 1, through=-1)
        result = assess_route(self.trace, [wrong, self.second])
        self.assertFalse(result.passed)
        self.assertIn("seat_wrong_direction", [x.reason for x in result.findings])

    def test_precise_preseated_id_is_available_from_an_earlier_verified_history(self):
        trace = self.trace[2:]
        without = assess_route(trace, self.route)
        self.assertFalse(without.passed)
        self.assertIn("missing_lateral_entry", [x.reason for x in without.findings])
        with_authority = assess_route(trace, self.route, carried_in={"start": .1}, max_material_drift_m=.004)
        self.assertTrue(with_authority.passed)
        self.assertTrue(with_authority.installations[0].carried_in)
        mismatch = assess_route(trace, self.route, carried_in={"start": .11}, max_material_drift_m=.004)
        self.assertIn("carried_material_mismatch", [x.reason for x in mismatch.findings])

    def test_gaps_and_changed_material_metadata_are_explicit(self):
        gap = assess_route([x for x in self.trace if x.tick != 3], self.route, max_snapshot_gap_ticks=1)
        self.assertFalse(gap.passed)
        self.assertIn("snapshot_gap", [x.reason for x in gap.findings])
        retagged = [self.trace[0], measured(1, .03, .00, tags=[x+.01 for x in TAGS])]
        with self.assertRaises(ValueError):
            assess_route(retagged, self.route)


if __name__ == "__main__":
    unittest.main()
