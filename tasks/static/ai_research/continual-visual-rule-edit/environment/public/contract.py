"""Enforce the joint scanner's six-row and twelve-outgoing-channel installation budget."""

import numpy as np


def validate(
    w: np.ndarray,
    b: np.ndarray,
    heads: np.ndarray,
    bridge: np.ndarray,
    new: np.ndarray,
    bias: np.ndarray,
    archive: np.ndarray,
    coupled: np.ndarray,
) -> tuple[int, int]:
    """Check one installation against the complete before-state received by its worker.

    The bridge's renewed late rows are incoming parameters of those neurons. Any
    other difference in the bridge is an early outgoing change. Union these with
    the corresponding direct legacy channels before counting. Raises ValueError
    for changed shape, invalid numeric values or an out-of-budget edit. The
    function does not mutate the station arrays.
    """
    for original, proposed in zip((w, b, heads, bridge), (new, bias, archive, coupled)):
        if (
            proposed.shape != original.shape
            or proposed.dtype.kind != "f"
            or proposed.dtype.itemsize not in (4, 8)
            or not np.isfinite(proposed).all()
        ):
            raise ValueError(
                "Each output must be a finite float32 or float64 array of the original shape"
            )
    changed = (w != new).any(2) | (b != bias)
    changes = changed.sum(axis=1)
    if changes.sum() > 6 or np.max(changes) > 4:
        raise ValueError("At most six renewed rows total and four in either layer")
    early_out = (heads[0] != archive[0]).any(0)
    late_out = (heads[1] != archive[1]).any(0)
    bridge_delta = bridge != coupled
    if bridge_delta.any() and not changed.any():
        raise ValueError("Change bridge parameters only with a hidden-row renewal")
    early_out = early_out | bridge_delta[~changed[1]].any(0)
    outgoing = np.array([early_out.sum(), late_out.sum()])
    if np.any((outgoing > 0) & (changes == 0)):
        raise ValueError("Redistribute outgoing channels only in a renewed layer")
    if outgoing.sum() > 12 or np.max(outgoing) > 8:
        raise ValueError(
            "At most twelve outgoing columns total and eight in either layer"
        )
    return int(changes.sum()), int(outgoing.sum())


def validate_pace(rates: np.ndarray) -> None:
    """Require a finite step multiplier between zero and one for each shift, layer and row."""
    if (
        rates.shape != (2, 2, 28)
        or rates.dtype.kind != "f"
        or rates.dtype.itemsize not in (4, 8)
        or not np.isfinite(rates).all()
        or np.min(rates) < 0
        or np.max(rates) > 1
    ):
        raise ValueError(
            "Learning rates must be finite float32 or float64 values in [0,1] with shape (2,2,28)"
        )


def validate_station(usage: list[tuple[int, int]]) -> None:
    """Pool the row and outgoing-channel budgets of the three physical scanners."""
    if len(usage) != 3:
        raise ValueError("Expected one part, lot and audit checkpoint")
    rows, columns = map(sum, zip(*usage))
    if sum(rows > 0 or cols > 0 for rows, cols in usage) > 2:
        raise ValueError(
            "A maintenance window may install checkpoint weights in at most two of three physical banks"
        )
    if rows > 9 or columns > 18:
        raise ValueError(
            f"The three scanners share nine renewed rows and eighteen outgoing columns. Received {rows} rows, {columns} columns"
        )
