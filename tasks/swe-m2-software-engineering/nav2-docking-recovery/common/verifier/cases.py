"""Private authored workcell and charging fault cases."""

from typing import Any

Record = dict[str, Any]

CASES: tuple[Record, ...] = (
    {"name": "rotated-camera-capture", "stage": 1, "pose": [0.76, 0.11, 0.13],
     "tag_delay": 3, "tag_noise": 0.001, "distractor": True, "old_tags": True},
    {"name": "mirrored-offset-gate", "stage": 1, "pose": [0.69, -0.105, -0.11],
     "camera": [-0.16, -0.061, -2.81], "tag_offset": [-0.28, -0.062, -0.37],
     "tag_delay": 4, "tag_jump": 20, "tag_holes": [(33, 43)]},
    {"name": "duplicate-positive-current", "stage": 2, "pose": [0.63, -0.07, -0.07],
     "duplicate_current": True, "precontact_current": True},
    {"name": "contact-bounce-and-low-current", "stage": 2, "pose": [0.71, 0.08, 0.10],
     "switch_bounce": True, "low_break": True, "charge_delay": 11},
    {"name": "no-charge-stops-safely", "stage": 2, "pose": [0.67, -0.04, 0.01],
     "charges_on": 2, "expected": "failed", "contact_count": 1},
    {"name": "pallet-then-odom-reset", "stage": 3, "pose": [0.77, 0.07, 0.09],
     "pallet_ticks": 21, "reset_tick": 43, "odom_holes": [(37, 44)], "tag_delay": 3},
    {"name": "nonconducting-first-attempt", "stage": 3, "pose": [0.70, -0.075, -0.11],
     "charges_on": 2, "front_block_ticks": 8, "contact_count": 2, "deadline": 245},
    {"name": "permanent-pallet-guard", "stage": 3, "pose": [0.70, 0.092, 0.10],
     "pallet_ticks": 400, "expected": "failed", "deadline": 136, "failure_at_deadline": True,
     "contact_count": 0},
    {"name": "lost-approach-reply", "stage": 4, "pose": [0.78, 0.09, 0.10],
     "restart_on": "approach", "pallet_ticks": 17, "tag_delay": 3, "deadline": 205},
    {"name": "restart-mid-retreat", "stage": 4, "pose": [0.62, -0.06, -0.10],
     "restart_on": "retreat", "charges_on": 2, "contact_count": 2, "deadline": 245,
     "front_block_ticks": 5},
    {"name": "restart-does-not-refill-attempts", "stage": 4, "pose": [0.71, 0.04, 0.08],
     "restart_on": "last-contact", "charges_on": 8, "contact_count": 2, "expected": "failed",
     "deadline": 245},
)
