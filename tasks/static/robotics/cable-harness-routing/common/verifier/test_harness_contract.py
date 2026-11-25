"""Regression controls for public harness command authority."""

from dataclasses import replace
import unittest

from harness_contract import MotionLimits, ObservationRef, parse_response

LIMITS = MotionLimits((-2.0,) * 6, (2.0,) * 6, 8)
OBSERVED = ObservationRef("captured-14", 2, frozenset({"mark-visible"}))


def decision(action: dict, **changes: object) -> dict:
    """Produce an attributed command and the chosen control alteration."""
    return {
        "observation_id": OBSERVED.observation_id, "generation": OBSERVED.generation,
        "command_id": "logical-motion-1", "status": "running", "action": action,
    } | changes


class WireContractTest(unittest.TestCase):
    """Check authority, limits, and the separation from physical decisions."""

    def test_motion_only_from_current_generation(self) -> None:
        """An old observation cannot authorize otherwise valid motion."""
        action = {"kind": "move", "target_q_rad": [0.0] * 6, "ticks": 8}
        accepted = parse_response(decision(action), OBSERVED, LIMITS)
        self.assertEqual(accepted.action.target_q_rad, (0.0,) * 6)
        for change in ({"generation": 1}, {"observation_id": "captured-13"}, {"generation": True}):
            with self.assertRaises(ValueError):
                parse_response(decision(action, **change), OBSERVED, LIMITS)

    def test_grasp_and_probe_respect_disclosed_sensing_limits(self) -> None:
        """Only current visible points and bounded enabled probes may be requested."""
        grasp = {"kind": "acquire", "point_id": "mark-visible", "mode": "slide"}
        self.assertEqual(parse_response(decision(grasp), OBSERVED, LIMITS).action.mode, "slide")
        with self.assertRaises(ValueError):
            parse_response(decision(grasp | {"point_id": "occluded"}), OBSERVED, LIMITS)
        probe = {"kind": "probe", "target_q_rad": [0.0] * 6, "ticks": 4}
        with self.assertRaises(ValueError):
            parse_response(decision(probe), OBSERVED, LIMITS)
        enabled = replace(LIMITS, max_probe_ticks=3)
        with self.assertRaises(ValueError):
            parse_response(decision(probe), OBSERVED, enabled)
        self.assertEqual(parse_response(decision(probe | {"ticks": 3}), OBSERVED, enabled).action.ticks, 3)

    def test_terminal_claim_has_no_way_to_change_clip_state(self) -> None:
        """Completion can request a hold, and leaves mechanical truth to the verifier."""
        valid = decision({"kind": "hold"}, status="complete")
        self.assertEqual(parse_response(valid, OBSERVED, LIMITS).status, "complete")
        for action in ({"kind": "latch"}, {"kind": "release"}, {"kind": "move", "target_q_rad": [0.0] * 6, "ticks": 1}):
            with self.assertRaises(ValueError):
                parse_response(decision(action, status="complete"), OBSERVED, LIMITS)

    def test_nonfinite_and_boolean_joint_values_are_rejected(self) -> None:
        """Prevent invalid numerics from reaching the native actuator."""
        for invalid in (True, 2.001, float("nan"), float("inf"), 10**400):
            action = {"kind": "move", "target_q_rad": [invalid, 0, 0, 0, 0, 0], "ticks": 1}
            with self.assertRaises(ValueError):
                parse_response(decision(action), OBSERVED, LIMITS)
