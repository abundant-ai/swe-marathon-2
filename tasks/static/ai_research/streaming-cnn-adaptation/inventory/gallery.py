"""Read a two-station photographic stock manifest and infer the local category IDs."""

import functools
import numpy as np
import torch
from PIL import Image
from core_model import tensor


def assignment(logits):
    @functools.lru_cache(None)
    def best(used):
        category = used.bit_count()
        if category == 10:
            return 0.0, ()
        choices = []
        for slot in range(10):
            if used & (1 << slot):
                continue
            score, tail = best(used | (1 << slot))
            choices.append((score + logits[slot, category], (slot,) + tail))
        return max(choices)

    return list(best(0)[1])


def decode(path, model):
    with Image.open(path) as sheet:
        photos = []
        for station in range(2):
            for slot in range(10):
                for view in range(2):
                    x, y = station * 208 + view * 96 + 4, slot * 112 + 4
                    photos.append(
                        np.asarray(
                            sheet.crop((x, y, x + 96, y + 96)).resize(
                                (32, 32), Image.Resampling.NEAREST
                            )
                        ).copy()
                    )
    with torch.no_grad():
        prob = (
            model.eval()(tensor(np.stack(photos)))
            .log_softmax(1)
            .reshape(2, 10, 2, 10)
            .mean(2)
            .numpy()
        )
    return [assignment(p) for p in prob]
