"""Private staging-cell facts that the candidate can only read from the drawings.

The verifier keeps these values. They are printed only as dimensions on the
cell sheets under /app/examples/cell/, and every packet the candidate receives
for the staging cell omits them. Lengths are millimetres in the world frame
(datum A). Angles are degrees, applied as yaw about Z, then pitch about the new
Y, then roll about the new X.
"""

from math import cos, radians, sin, sqrt

# Handoff station H1: grip midpoint and the left-to-right grip axis.
STATION_MM = (-29.0, -1.5, 298.0)
STATION_YAW_DEG = 60.5
STATION_PITCH_DEG = -9.5
STATION_ROLL_DEG = 0.0

# Raised alternative H2, offset from H1 in world axes with H1's orientation.
RAISED_OFFSET_MM = (40.0, 20.0, 140.0)

# Destination nest N1 for the receiving (right) arm.
NEST_MM = (207.0, 139.5, 231.0)
NEST_YAW_DEG = 68.5
NEST_PITCH_DEG = -14.5
NEST_ROLL_DEG = -4.5

# Controller timing: both grippers closed for the transfer dwell.
TICK_MS = 5
DWELL_START_MS = 160
DWELL_END_MS = 900
TRANSFER_TICKS = (DWELL_END_MS - DWELL_START_MS) // TICK_MS

# Drawing construction points (world, mm). They are public reference marks.
DOWEL_P1_MM = (-150.0, -90.0)
PLATE_F_MM = (120.0, 60.0)

# Superseded revision B geometry, drawn as void phantoms on the sheets.
SUPERSEDED_STATION_MM = (-95.0, 46.0, 281.0)
SUPERSEDED_DWELL_MS = (0, 800)


def quaternion_xyzw(yaw_deg, pitch_deg, roll_deg):
    """Return the unit quaternion for intrinsic Z, Y', X'' rotations."""
    hy, hp, hr = (radians(value) / 2 for value in (yaw_deg, pitch_deg, roll_deg))
    cy, sy, cp, sp, cr, sr = cos(hy), sin(hy), cos(hp), sin(hp), cos(hr), sin(hr)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    norm = sqrt(w * w + x * x + y * y + z * z)
    return [x / norm, y / norm, z / norm, w / norm]


def pose(translation_mm, yaw_deg, pitch_deg, roll_deg):
    """Build a spec pose record in metres from drawing units."""
    return {
        "translation_m": [value / 1000.0 for value in translation_mm],
        "quaternion_xyzw": quaternion_xyzw(yaw_deg, pitch_deg, roll_deg),
    }


def station_poses():
    """Return the private handoff station records H1 and H2."""
    raised = [a + b for a, b in zip(STATION_MM, RAISED_OFFSET_MM, strict=True)]
    angles = (STATION_YAW_DEG, STATION_PITCH_DEG, STATION_ROLL_DEG)
    return [pose(STATION_MM, *angles), pose(raised, *angles)]


def nest_pose():
    """Return the private destination record for the staging cell."""
    return pose(NEST_MM, NEST_YAW_DEG, NEST_PITCH_DEG, NEST_ROLL_DEG)
