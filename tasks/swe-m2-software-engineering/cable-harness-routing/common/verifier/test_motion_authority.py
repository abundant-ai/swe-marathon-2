"""Control exercises for lost plant receipts and obsolete command authority."""

import unittest

from harness_contract import MotionLimits, ObservationRef, Response
from motion_authority import MotionAuthority, Receipt, ReceiptStatus

LIMITS = MotionLimits((-2.0,) * 6, (2.0,) * 6, 9)
FIRST = ObservationRef("capture-1", 5, frozenset({"mark-1"}))
NEXT = ObservationRef("capture-2", 5, frozenset({"mark-2"}))
REVISED = ObservationRef("capture-3", 6, frozenset({"mark-3"}))


def move(observed: ObservationRef, command_id: str = "first-motion") -> dict[str, object]:
    """Form a legal motion reply scoped to the supplied observation."""
    return {
        "observation_id": observed.observation_id,
        "generation": observed.generation,
        "command_id": command_id,
        "status": "running",
        "action": {"kind": "move", "target_q_rad": [0.05] * 6, "ticks": 8},
    }


class MotionAuthorityTest(unittest.TestCase):
    """Exercise the same trusted ledger across controller disconnects."""

    def setUp(self) -> None:
        """Create a workcell and count actions that reached the actuator."""
        self.plant = MotionAuthority(FIRST, LIMITS)
        self.applied: list[Response] = []

    def execute(self, response: Response) -> ReceiptStatus:
        """Model a motion interrupted after it reached the actuator once."""
        self.applied.append(response)
        return "interrupted"

    def test_lost_receipt_replayed_after_next_capture(self) -> None:
        """A duplicate in the same generation cannot move the plant again."""
        original = move(FIRST)
        receipt = self.plant.submit(original, self.execute)
        self.plant.publish(NEXT, LIMITS)
        self.assertEqual(receipt, Receipt("first-motion", 5, "interrupted"))
        self.assertIs(self.plant.submit(original, self.execute), receipt)
        self.assertIs(self.plant.submit(move(NEXT), self.execute), receipt)
        self.assertIs(self.plant.last_receipt, receipt)
        self.assertEqual(len(self.applied), 1)

    def test_retry_cannot_substitute_command_or_reuse_capture(self) -> None:
        """Keep one decision per capture and reject changed actions under an old ID."""
        self.plant.submit(move(FIRST), self.execute)
        with self.assertRaises(ValueError):
            self.plant.submit(move(FIRST, "brand-new-id"), self.execute)
        self.plant.publish(NEXT, LIMITS)
        with self.assertRaises(ValueError):
            self.plant.submit(move(FIRST, "old-capture-with-new-id"), self.execute)
        changed = move(NEXT) | {"action": {"kind": "hold"}}
        with self.assertRaises(ValueError):
            self.plant.submit(changed, self.execute)
        self.assertEqual(len(self.applied), 1)

    def test_board_revision_reports_old_receipt_and_rejects_motion(self) -> None:
        """Expose the old receipt for recovery while requiring fresh authority."""
        old_receipt = self.plant.submit(move(FIRST), self.execute)
        self.plant.publish(REVISED, LIMITS)
        self.assertIs(self.plant.last_receipt, old_receipt)
        with self.assertRaises(ValueError):
            self.plant.submit(move(FIRST), self.execute)
        with self.assertRaisesRegex(ValueError, "belongs to an earlier board generation"):
            self.plant.submit(move(REVISED), self.execute)
        with self.assertRaises(ValueError):
            self.plant.publish(FIRST, LIMITS)
        revised_receipt = self.plant.submit(move(REVISED, "revised-motion"), self.execute)
        self.assertEqual(revised_receipt, Receipt("revised-motion", 6, "interrupted"))
        self.assertEqual([row.generation for row in self.applied], [5, 6])

    def test_grasp_retry_uses_original_ephemeral_point(self) -> None:
        """Replay the receipt after the camera replaced all point IDs."""
        original = move(FIRST) | {"action": {"kind": "acquire", "point_id": "mark-1", "mode": "pinch"}}
        receipt = self.plant.submit(original, self.execute)
        self.plant.publish(NEXT, LIMITS)
        retry = original | {"observation_id": NEXT.observation_id}
        self.assertIs(self.plant.submit(retry, self.execute), receipt)
        self.assertEqual(len(self.applied), 1)

    def test_unknown_actuator_outcome_cannot_be_reapplied(self) -> None:
        """Reserve the ID before calling an actuator that might move then fail."""
        def fail(response: Response) -> ReceiptStatus:
            """Record the physical invocation before raising a transport failure."""
            self.applied.append(response)
            raise ValueError("lost actuator acknowledgement")

        original = move(FIRST)
        with self.assertRaisesRegex(RuntimeError, "actuator failed") as failure:
            self.plant.submit(original, fail)
        self.assertEqual(str(failure.exception.__cause__), "lost actuator acknowledgement")
        with self.assertRaisesRegex(RuntimeError, "outcome is unknown"):
            self.plant.submit(original, self.execute)
        self.assertIsNone(self.plant.last_receipt)
        self.assertEqual(len(self.applied), 1)
