"""Apply candidate edits and check the maintenance limit across each three-bank cabinet."""

import numpy as np
import submission
from contract import validate, validate_pace


def install(w, b, heads, x, tags, bridge):
    """Build one scanner. Four-array editors keep ordinary SGD rates."""
    raw = submission.edit(
        w.copy(), b.copy(), heads.copy(), x.copy(), tags.copy(), bridge.copy()
    )
    values = tuple(np.asarray(v) for v in raw)
    if len(values) == 4:
        values = (*values, np.ones((2, 2, 28)))
    if len(values) != 5:
        raise ValueError(
            "Return weights, biases, archived readout, bridge and optional rates"
        )
    validate(w, b, heads, bridge, *values[:4])
    validate_pace(values[4])
    return values
