"""Estimate inverse color mixing from corresponding RGB values on the technician's sheet."""

import numpy as np
from PIL import Image


def estimate(path):
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float64)
    before, after = np.split(rgb, 2)
    before, after = (x.reshape(-1, 3) for x in (before, after))
    # Pair corresponding pixels, preserving precision where the sensor actually has support.
    inverse, _, rank, _ = np.linalg.lstsq(after, before, rcond=None)
    if rank != 3:
        raise ValueError("Preview does not span the three sensor channels")
    return inverse.T


def profiles(path):
    import torch
    from online import descriptor

    with Image.open(path) as im:
        native = np.array(im.convert("RGB").resize((160,128), Image.Resampling.NEAREST))
    tiles = native.reshape(4,32,5,32,3).transpose(0,2,4,1,3).reshape(20,3,32,32)
    return descriptor(torch.from_numpy(tiles.copy()).float()/255).reshape(2,10,-1).tolist()
