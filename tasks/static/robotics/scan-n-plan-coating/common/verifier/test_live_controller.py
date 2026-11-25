"""Check elapsed pump transients against held flow and command transitions."""

import unittest

from live_controller import LiveController, PressureSag
from trajectory import AXES, Knot


class LiveControllerTest(unittest.TestCase):
    def test_dry_motion_does_not_consume_first_prime_delay(self) -> None:
        """A completed dry approach leaves the same measured first wet deficit."""
        period = 20_000_000
        zero = (0.0,) * AXES
        job = {"motion": {"control_period_ns": period}, "start_q_rad": zero}
        plant = LiveController(job, flow_gain=0.9, prime_delay_periods=2)

        plant.accept("approach", 0, (Knot(0, zero, zero, 0.0), Knot(period, zero, zero, 0.0)))
        plant.advance()
        self.assertEqual(plant.mode, "stopped")

        plant.accept("spray", 0, (Knot(0, zero, zero, 1.0), Knot(4 * period, zero, zero, 0.0)))
        plant.advance()
        plant.set_permit(True)
        plant.advance()
        self.assertEqual(plant.emitted_ml, 0.0)
        self.assertAlmostEqual(plant.priming_suppressed_ml, 0.036)

        plant.advance(2)
        self.assertAlmostEqual(plant.emitted_ml, 0.036)
        self.assertAlmostEqual(plant.priming_suppressed_ml, 0.036)
        flows = [sample["flow_ml_s"] for sample in plant.finished[-1].receipts()[0]["samples"]]
        self.assertEqual(flows, [0.0, 0.0, 0.9, 0.9, 0.0])

    def test_pressure_deficit_persists_across_dry_motion_and_inhibition(self) -> None:
        """Consume missing volume only over elapsed permitted wet samples."""
        period = 20_000_000
        zero = (0.0,) * AXES
        job = {"motion": {"control_period_ns": period}, "start_q_rad": zero}
        plant = LiveController(job, pressure_sag=PressureSag(.020, .023, .25))
        dry = (Knot(0, zero, zero, 0.0), Knot(period, zero, zero, 0.0))
        wet = (Knot(0, zero, zero, 1.0), Knot(period, zero, zero, 0.0))

        plant.accept("approach", 0, dry)
        plant.advance()
        plant.accept("first-spray", 0, wet)
        plant.advance()
        self.assertAlmostEqual(plant.emitted_ml, .020)
        self.assertEqual(plant.pressure_samples, [])

        plant.accept("next-spray", 0, wet)
        plant.set_permit(True)
        plant.advance()
        self.assertAlmostEqual(plant.pressure_suppressed_ml, .015)
        plant.accept("dry-adjustment", 0, dry)
        plant.advance(3)
        self.assertAlmostEqual(plant.pressure_suppressed_ml, .015)

        plant.accept("finish-spray", 1, (Knot(0, zero, zero, 1.0), Knot(3 * period, zero, zero, 0.0)))
        plant.set_permit(False)
        plant.advance()
        self.assertAlmostEqual(plant.pressure_suppressed_ml, .015)
        plant.set_permit(True)
        plant.advance(2)
        self.assertAlmostEqual(plant.pressure_suppressed_ml, .023)
        self.assertAlmostEqual(plant.emitted_ml, .057)
        self.assertEqual([sample.motion_id for sample in plant.pressure_samples], ["next-spray", "finish-spray"])
        flows = [sample["flow_ml_s"] for sample in plant.finished[-1].receipts()[0]["samples"]]
        self.assertAlmostEqual(flows[1], .6)
        self.assertEqual((flows[0], flows[2], flows[3]), (0.0, 1.0, 0.0))

    def test_priming_and_pressure_sag_have_separate_loss_totals(self) -> None:
        """Observe dry priming, steady delivery, positive sag, then steady delivery again."""
        period = 20_000_000
        zero = (0.0,) * AXES
        job = {"motion": {"control_period_ns": period}, "start_q_rad": zero}
        plant = LiveController(
            job, flow_gain=0.8, prime_delay_periods=2, pressure_sag=PressureSag(.030, .018, .25),
        )
        plan = (Knot(0, zero, zero, 1.0), Knot(8 * period, zero, zero, 0.0))
        plant.accept("spray", 0, plan)

        plant.advance(2)
        self.assertEqual(plant.emitted_ml, 0.0)
        self.assertAlmostEqual(plant.priming_suppressed_ml, .032)
        self.assertEqual(plant.pressure_suppressed_ml, 0.0)

        plant.advance(2)
        self.assertAlmostEqual(plant.emitted_ml, .032)
        self.assertEqual(plant.pressure_samples, [])

        plant.advance(4)
        self.assertEqual(plant.mode, "stopped")
        self.assertAlmostEqual(plant.priming_suppressed_ml, .032)
        self.assertAlmostEqual(plant.pressure_suppressed_ml, .018)
        self.assertAlmostEqual(plant.emitted_ml, .078)
        self.assertAlmostEqual(
            plant.emitted_ml + plant.priming_suppressed_ml + plant.pressure_suppressed_ml,
            plant.requested_ml * plant.pump_gain,
        )
        self.assertEqual(
            [(sample.start_ns, sample.end_ns) for sample in plant.pressure_samples],
            [(4 * period, 5 * period), (5 * period, 6 * period)],
        )
        flows = [sample["flow_ml_s"] for sample in plant.finished[0].receipts()[0]["samples"]]
        for measured, expected in zip(flows, (0.0, 0.0, .8, .8, .2, .5, .8, .8, 0.0), strict=True):
            self.assertAlmostEqual(measured, expected)
