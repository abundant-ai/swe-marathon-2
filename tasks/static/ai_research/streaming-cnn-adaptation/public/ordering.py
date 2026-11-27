"""Causal clip and camera-multiplex stream orderings."""

import numpy as np


def frame_order(clips, rng, schedule):
    if schedule == "clips":
        return clips[rng.permutation(len(clips))].ravel()
    if schedule != "switches":
        raise RuntimeError("Unknown trusted camera schedule")
    # Multiplex the ten camera tracks while retaining time order within each track.
    ordered = []
    last = None
    for column in range(clips.shape[1]):
        sources = rng.permutation(len(clips))
        if sources[0] == last:
            sources = np.roll(sources, 1)
        ordered.extend(clips[sources, column])
        last = sources[-1]
    return np.asarray(ordered)
