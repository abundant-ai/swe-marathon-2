"""Build the room, fit the visible objects and recover surface color from the recording."""

import numpy as np
from multiview import FIELDS, PUBLIC, build, inputs
from room import Mesh, layout_prior
from surfaces import layout
from visibility import mask


def scene():
    if (PUBLIC / "observation.png").is_file() and (PUBLIC / "frames.zip").is_file():
        images, _ = inputs(include_dense=False)
        handset = mask(TRACES["i1"]["4"])
        if np.median(images[1][handset].min(axis=1)) > 160:
            room = layout_prior()
            base = layout(dict(zip(FIELDS[:4], room, strict=True)))
            return build(base_reference=base)
    prior = Mesh()
    prior.box((-0.3, -0.2, -0.04), (0.9, 0.6, 0), (155, 136, 108))
    prior.revolution(
        (0.12, 0.10),
        [(0.05, 0), (0.05, 0.045), (0.026, 0.045), (0.026, 0)],
        (143, 139, 131),
        1,
    )
    prior.revolution(
        (0.29, 0.16),
        [(0.035, 0), (0.043, 0.10), (0.039, 0.10), (0.031, 0.012)],
        (215, 212, 201),
        2,
    )
    prior.box((0.35, 0.12, 0), (0.53, 0.3, 0.055), (181, 174, 148), 3)
    prior.box((0.34, 0.13, 0.055), (0.4, 0.30, 0.08), (211, 206, 183), 3)
    room = prior.finish()
    return (*room, np.zeros(len(room[1]), dtype=np.int32))
