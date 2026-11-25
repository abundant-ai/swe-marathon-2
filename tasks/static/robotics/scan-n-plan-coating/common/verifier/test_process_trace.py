"""Check the measured coating path between controller knots."""

from dataclasses import asdict
import unittest

import numpy as np
from numpy.typing import NDArray

from coating_scene import CoatingScene
from process_trace import ProcessTrace
from trajectory import parse_knots


class LinearTool:
    """Independent kinematics for a straight scan over an analytic plane."""

    def __init__(self) -> None:
        self.x = 0.0

    def set_q(self, q_rad: tuple[float, ...]) -> None:
        """Move the tool along X at one metre per radian for this test."""
        self.x = q_rad[0]

    def world_from_tool(self) -> NDArray[np.float64]:
        """Return the pose of a nozzle facing straight down from unit height."""
        pose = np.diag([1.0, -1.0, -1.0, 1.0])
        pose[:3, 3] = [self.x, 0.0, 1.0]
        return pose


def rows() -> list[dict[str, object]]:
    """Return a continuous one-second motion with held flow until its end."""
    return [
        {
            "t_ns": tick,
            "q_rad": [0.1 * tick / 1e9, 0, 0, 0, 0, 0, 0],
            "qd_rad_s": [0.1, 0, 0, 0, 0, 0, 0],
            "flow_ml_s": flow,
        }
        for tick, flow in ((0, 2.0), (500_000_000, 2.0), (1_000_000_000, 0.0))
    ]


def scene() -> CoatingScene:
    """Provide a square part marked entirely as eligible for the dose test."""
    return CoatingScene.from_job({
        "part_mesh": {
            "vertices_m": [[-.5, -.5, 0], [.5, -.5, 0], [.5, .5, 0], [-.5, .5, 0]],
            "triangles": [[0, 1, 2], [0, 2, 3]],
        },
        "base_from_axis": {"translation_m": [0, 0, 0], "quaternion_xyzw": [0, 0, 0, 1]},
    })


class TraceTest(unittest.TestCase):
    """Run surface-dose observations independently of the candidate planner."""

    def test_receipt_boundaries_preserve_material_and_process_speed(self) -> None:
        """The same plant motion must score equivalently when receipts are split."""
        recipe = {
            "cone_half_angle_rad": 0.2, "standoff_m": [0.95, 1.05],
            "max_normal_error_rad": 0.05, "surface_speed_mps": [0.09, 0.11],
            "target_dose_ml_m2": [1, 25], "min_covered_fraction": 0.08, "max_off_target_ml": 0.01,
        }
        part = scene()
        combined = ProcessTrace(part, [0, 1], recipe, subdivisions=24)
        for mode in ("combined", "split", "wrong-speed"):
            if mode == "combined":
                trace = combined
                segments = [rows()]
            elif mode == "split":
                trace = ProcessTrace(part, [0, 1], recipe, subdivisions=24)
                segments = [rows()[:2], rows()[1:]]
            else:
                trace = ProcessTrace(part, [0, 1], {**recipe, "surface_speed_mps": [0.2, 0.3]}, subdivisions=24)
                segments = [rows()]
            tool = LinearTool()
            for segment in segments:
                trace.append(
                    tool, parse_knots(segment, 50_000_000, 2, finish_disabled=False),
                    np.eye(4), max_step_ns=50_000_000,
                )
            result = trace.evidence()
            self.assertAlmostEqual(result.emitted_ml, 2.0)
            self.assertAlmostEqual(result.min_surface_speed_mps, 0.1, places=8)
            self.assertAlmostEqual(result.max_surface_speed_mps, 0.1, places=8)
            self.assertTrue(result.dose.qualified)
            if mode == "wrong-speed":
                self.assertEqual(result.off_recipe_samples, result.enabled_samples)
            else:
                self.assertEqual(result.off_recipe_samples, 0)
                self.assertEqual(asdict(combined.evidence()), asdict(result))
