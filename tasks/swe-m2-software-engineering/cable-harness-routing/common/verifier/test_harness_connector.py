"""Independent controls for keyed seating and interval contact/force evidence."""

from dataclasses import replace
from math import cos, sin
import unittest

import numpy as np

from harness_connector import ConnectorSnapshot, NativeContact, SeatRecipe, assess_connector


def around_z(radians):
    return [0.0, 0.0, sin(radians / 2), cos(radians / 2)]


class ConnectorAuditTest(unittest.TestCase):
    def setUp(self):
        self.recipe = SeatRecipe([0., 0., 0.], [0., 0., 0., 1.], [1., 0., 0.], .001)
        self.start, self.end = 10, 410
        self.trace = []
        for tick in range(self.end + 1):
            if tick < self.start:
                position, engaged = [-.003, 0., 0.], False
            elif tick == self.start:
                position, engaged = [0., 0., 0.], True
            else:
                position, engaged = [-.000058, 0., 0.], True
            load = [-3., 0., 0., 0., 0., 0.] if tick > self.start else [0.] * 6
            self.trace.append(ConnectorSnapshot(tick, position, around_z(0), engaged,
                                                tick >= self.start, load, ()))

    def check(self, **options):
        return assess_connector(self.trace, self.recipe, pull_start_tick=self.start, pull_end_tick=self.end,
                                **options)

    def reasons(self, **options):
        return {value.reason for value in self.check(**options).findings}

    def test_full_signed_pull_and_physical_release(self):
        result = self.check()
        self.assertTrue(result.passed)
        self.assertEqual(result.effective_pull_steps, 400)
        self.assertEqual(result.effective_pull_duration_s, .4)
        self.assertEqual(result.min_axial_pull_n, 3.)
        self.assertAlmostEqual(result.max_axial_withdrawal_m, .000058)

    def test_high_angle_rejected_even_with_engaged_interlock_and_only_58_micrometres_displacement(self):
        self.trace[-1] = replace(self.trace[-1], quaternion_xyzw=around_z(.03983928698657192))
        result = self.check()
        self.assertFalse(result.passed)
        self.assertAlmostEqual(result.max_pull_displacement_m, .000058)
        self.assertAlmostEqual(result.final_rotation_error_rad, .03983928698657192)
        self.assertIn("retention_rotation", {value.reason for value in result.findings})

    def test_transient_invalid_orientation_and_interlock_loss_despite_final_recovery(self):
        original = self.trace[20]
        self.trace[20] = replace(original, quaternion_xyzw=around_z(.008), interlock=False)
        result = self.check()
        self.assertFalse(result.passed)
        self.assertEqual(result.final_rotation_error_rad, 0)
        self.assertTrue({"retention_rotation", "interlock_lost"} <= {x.reason for x in result.findings})

    def test_precise_keying_includes_full_quaternion_not_only_connector_axis(self):
        flipped = [1, 0, 0, 0]
        self.trace[self.start] = replace(self.trace[self.start], quaternion_xyzw=flipped)
        result = self.check()
        self.assertFalse(result.passed)
        self.assertAlmostEqual(result.max_pull_rotation_error_rad, np.pi)

    def test_antipodal_quaternion_and_inclusive_bounds(self):
        self.trace[-1] = replace(self.trace[-1],
                                 quaternion_xyzw=list(-np.asarray(around_z(.006))),
                                 position_m=[-.0015, 0., 0.])
        self.assertTrue(self.check().passed)

    def test_wrong_axis_or_supporting_operator_moment(self):
        self.trace[25] = replace(self.trace[25], operator_wrench_world=[3., 0., 0., 0., 0., 0.])
        self.trace[35] = replace(self.trace[35], operator_wrench_world=[-3., .4, 0., 0., 0., 0.])
        self.trace[45] = replace(self.trace[45], operator_wrench_world=[-3., 0., 0., 0., 0., .012])
        result = self.check()
        self.assertTrue({"pull_force", "operator_moment", "pull_duration"} <= {x.reason for x in result.findings})
        self.assertEqual(result.min_axial_pull_n, -3.)

    def test_interlock_alone_does_not_authorize_pull_while_gripper_holds(self):
        self.trace[80] = replace(self.trace[80], gripper_released=False)
        self.trace[90] = replace(self.trace[90], gripper_released=True, gripper_wrench_world=[-.2, 0, 0, 0, 0, 0])
        self.trace[100] = replace(self.trace[100], gripper_released=None)
        reasons = self.reasons()
        self.assertTrue({"gripper_support", "release_unverified", "pull_duration"} <= reasons)

    def test_short_interrupted_or_unobserved_pull_fails(self):
        del self.trace[240]
        result = self.check()
        self.assertTrue({"native_trace_gap", "pull_history_incomplete", "pull_duration"}
                        <= {x.reason for x in result.findings})
        self.trace = self.trace[:380]
        self.assertIn("pull_history_incomplete", self.reasons())

    def test_independent_contact_pair_and_limit_checks(self):
        pair = NativeContact(("floor", "boot"), .52, -.00008)
        self.trace[40] = replace(self.trace[40], contacts=(pair,))
        self.assertTrue(self.check().passed)
        reasons = self.reasons(permitted_contacts=[("channel", "plug")],
                               max_contact_force_n=.5, max_contact_penetration_m=.000075)
        self.assertTrue({"forbidden_contact", "contact_force", "contact_penetration"} <= reasons)

    def test_missing_native_contacts_do_not_support_a_passing_claim(self):
        self.trace[35] = replace(self.trace[35], contacts=None)
        self.assertIn("contact_unverified", self.reasons())

    def test_absolute_position_and_relative_withdrawal_disagree(self):
        self.recipe = replace(self.recipe, displacement_limit_m=.0015)
        self.trace[self.start] = replace(self.trace[self.start], position_m=[.001, 0., 0.])
        self.trace[-1] = replace(self.trace[-1], position_m=[-.001, 0., 0.])
        result = self.check()
        self.assertLess(result.max_pull_position_error_m, .0015)
        self.assertAlmostEqual(result.max_pull_displacement_m, .002)
        self.assertIn("retention_displacement", {x.reason for x in result.findings})

    def test_route_result_is_an_independent_requirement(self):
        self.assertIn("route_unverified", self.reasons(require_route=True))
        class LostEarlierClip:
            passed = False
        self.assertIn("route_not_preserved", self.reasons(require_route=True, route=LostEarlierClip()))


if __name__ == "__main__":
    unittest.main()
