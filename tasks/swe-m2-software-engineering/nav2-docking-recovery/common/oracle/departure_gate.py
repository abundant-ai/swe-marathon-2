"""Qualification of the measured power release for an accepted departure."""

import math


FRESH_NS = 150_000_000
DWELL_NS = 150_000_000
MAX_GAP_NS = 70_000_000
SAFE_CURRENT_A = .10


class IsolationGate:
    """Keep a current-boot evidence streak independent of request acknowledgment."""

    def __init__(self, transaction):
        self.transaction = transaction
        self.boot = None
        self.current = None
        self.contact = False
        self.last_state_stamp = None
        self.last_sequence = None
        self.first_stamp = None
        self.last_safe_stamp = None
        self.count = 0

    def clear(self):
        self.first_stamp = self.last_safe_stamp = None
        self.count = 0

    def observe(self, packet, now_ns):
        if not isinstance(packet, dict) or packet.get("kind") != "state":
            return
        stamp = packet.get("stamp_ns")
        boot = packet.get("boot")
        seq = packet.get("seq")
        current = packet.get("current_amps")
        if (any(type(value) is not int for value in (stamp, boot, seq))
                or boot <= 0 or seq < 0 or not 0 <= now_ns - stamp <= FRESH_NS
                or type(packet.get("contactor_open")) is not bool
                or type(packet.get("contact")) is not bool
                or type(current) not in (int, float) or not math.isfinite(current)):
            return
        if self.boot is not None and boot < self.boot:
            return
        if boot != self.boot:
            self.boot = boot
            self.last_state_stamp = self.last_sequence = None
            self.clear()
        if (self.last_state_stamp is not None and
                (stamp <= self.last_state_stamp or seq <= self.last_sequence)):
            return
        self.last_state_stamp, self.last_sequence = stamp, seq
        self.current = current
        self.contact = packet["contact"]
        if (packet.get("transaction_id") != self.transaction or not packet["contactor_open"]
                or abs(current) > SAFE_CURRENT_A):
            self.clear()
            return
        if self.last_safe_stamp is None or stamp - self.last_safe_stamp > MAX_GAP_NS:
            self.clear()
            self.first_stamp = stamp
        self.last_safe_stamp = stamp
        self.count += 1

    def seated_live(self, now_ns):
        return (self.last_state_stamp is not None and 0 <= now_ns - self.last_state_stamp <= FRESH_NS
                and self.contact and self.current is not None and self.current > .50)

    def qualified(self, now_ns):
        if self.last_safe_stamp is None or not 0 <= now_ns - self.last_safe_stamp <= MAX_GAP_NS:
            self.clear()
            return False
        return self.count >= 4 and self.last_safe_stamp - self.first_stamp >= DWELL_NS
