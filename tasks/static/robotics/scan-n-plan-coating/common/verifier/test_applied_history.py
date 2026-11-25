"""Check measured receipt order, retry and missing-history behavior."""

import unittest

from applied_history import AppliedHistory, Motion, parse_receipt

PERIOD = 20_000_000
MOTION = Motion("coat-a", 4, 13)


def receipt(name: str, start: int, end: int, flow: float = 1.0) -> dict:
    """Make a measured interval with a known origin and control cadence."""
    return {
        "receipt_id": name,
        "command_id": MOTION.command_id,
        "scene_revision": MOTION.scene_revision,
        "samples": [
            {"t_ns": MOTION.issued_ns + i * PERIOD, "q_rad": [0] * 7,
             "qd_rad_s": [0] * 7, "flow_ml_s": flow}
            for i in range(start, end + 1)
        ],
    }


class AppliedHistoryTest(unittest.TestCase):
    """Verify the trusted history used to measure a resume mission."""

    def test_reverse_delivery_duplicates_and_gap_are_distinct(self) -> None:
        """Accept reverse delivery and repeats, and keep waiting on the hole."""
        issued = {MOTION.command_id: MOTION}
        first = parse_receipt(receipt("first", 0, 2), issued, PERIOD, 3)
        middle = parse_receipt(receipt("middle", 2, 4), issued, PERIOD, 3)
        last = parse_receipt(receipt("last", 4, 6), issued, PERIOD, 3)
        stopped_at = MOTION.issued_ns + 6 * PERIOD
        pending = AppliedHistory().extend([last, first, last])
        self.assertIsNone(pending.complete(MOTION, stopped_at))
        settled = pending.extend([middle])
        self.assertEqual(settled.complete(MOTION, stopped_at), (first, middle, last))
        self.assertEqual(pending.receipts, (first, last))

    def test_malformed_conflict_cannot_change_prior_history(self) -> None:
        """Reject changed duplicate content and a distinct overlapping interval."""
        issued = {MOTION.command_id: MOTION}
        initial = parse_receipt(receipt("shared", 0, 3), issued, PERIOD, 3)
        ledger = AppliedHistory().extend([initial])
        conflict = parse_receipt(receipt("shared", 0, 3, flow=2), issued, PERIOD, 3)
        overlap = parse_receipt(receipt("other", 2, 4), issued, PERIOD, 3)
        for rejected in (conflict, overlap):
            with self.assertRaises(ValueError):
                ledger.extend([rejected])
            self.assertEqual(ledger.receipts, (initial,))
        hole = receipt("hole", 0, 3)
        del hole["samples"][1]
        with self.assertRaisesRegex(ValueError, "unobserved"):
            parse_receipt(hole, issued, PERIOD, 3)
