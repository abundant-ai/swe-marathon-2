"""Apply candidate edits and check the maintenance limit across each three-bank cabinet."""

import numpy as np
import submission
from contract import validate, validate_pace, validate_station


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


if __name__ == "__main__":
    with np.load("pairs.npz", allow_pickle=False) as raw:
        artifact = {}
        usage = []
        for i, inputs in enumerate(
            zip(*(raw[k] for k in ("W", "b", "v", "x", "tags", "bridge")), strict=True)
        ):
            w, b, h, x, t, j = inputs
            result = install(*inputs)
            usage.append(validate(w, b, h, j, *result[:4]))
            artifact.update(
                {
                    f"{k}{i}": v
                    for k, v in zip(
                        ("W", "b", "heads", "bridge", "pace"), result, strict=True
                    )
                }
            )
            if len(usage) == 3:
                validate_station(usage)
                usage = []
        if usage:
            raise ValueError("Incomplete station")
    np.savez("../output/artifact.npz", **artifact)
