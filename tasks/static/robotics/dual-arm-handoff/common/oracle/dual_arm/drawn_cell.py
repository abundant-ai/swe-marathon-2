"""Staging-cell facts transcribed from the revision C sheets in /app/examples/cell."""

from math import radians

import numpy as np

from .native_cell import encoded, transform

DRAWING = "STAGING CELL B HANDOFF LAYOUT"

# Sheet 1 gives plan positions, sheet 2 heights and pitch, sheet 3 the nest
# orientation. Millimetres from datum A; yaw, then pitch about Y', then roll
# about X''. The part frame at a station is the drawn station frame.
STATION_MM = (-29.0, -1.5, 298.0)
STATION_DEG = (60.5, -9.5, 0.0)
RAISED_OFFSET_MM = (40.0, 20.0, 140.0)
NEST_MM = (207.0, 139.5, 231.0)
NEST_DEG = (68.5, -14.5, -4.5)

# Sheet 4: both grippers closed from 160 ms to 900 ms on a 5 ms tick.
DWELL_TICKS = (900 - 160) // 5


def euler(yaw, pitch, roll):
    """Rotation for intrinsic Z, Y', X'' angles in degrees."""
    a, b, c = (radians(value) for value in (yaw, pitch, roll))
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    rx = np.array([[1, 0, 0], [0, np.cos(c), -np.sin(c)], [0, np.sin(c), np.cos(c)]])
    return rz @ ry @ rx


def drawn(millimetres, angles):
    return encoded(transform(np.array(millimetres) / 1000.0, euler(*angles)))


STATIONS = {
    "H1": drawn(STATION_MM, STATION_DEG),
    "H2": drawn(np.add(STATION_MM, RAISED_OFFSET_MM), STATION_DEG),
}


def resolve(spec):
    """Fill a layout window's handoff poses, dwell and destination pose."""
    layout = spec["layout"]
    if not isinstance(layout, dict):
        raise TypeError("drawn layout must be an object")
    labels = layout.get("stations")
    if (
        layout.get("drawing") != DRAWING
        or not isinstance(labels, list)
        or not labels
        or len(set(labels)) != len(labels)
        or any(label not in STATIONS for label in labels)
    ):
        raise ValueError("unknown drawn layout")
    if {"handoff_object_poses", "transfer_ticks"} & set(spec) or (
        "world_from_object" in spec["destination"]
    ):
        raise ValueError("a drawn layout window must not restate its facts")
    return {
        **spec,
        "handoff_object_poses": [STATIONS[label] for label in labels],
        "transfer_ticks": DWELL_TICKS,
        "destination": {
            **spec["destination"],
            "world_from_object": drawn(NEST_MM, NEST_DEG),
        },
    }
