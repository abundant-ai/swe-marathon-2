"""Distill an augmented-view teacher into a causal ridge update of the CNN readout."""

from copy import deepcopy

import torch
from torch.nn import functional as F


class Updater:
    def __init__(self, model, ridge=2.0, strength=0.5, temperature=1.0):
        self.model = model
        self.teacher = deepcopy(model).eval()
        dimension = model.readout.in_features
        self.precision = torch.eye(dimension) / ridge
        self.correction = torch.zeros_like(model.readout.weight)
        self.strength = strength
        self.temperature = temperature

    @torch.no_grad()
    def update(self, image):
        # Average horizontal reflections and translations without wrapping the image.
        padded = F.pad(image, (2, 2, 2, 2), mode="replicate")
        width = image.size(-1)
        views = torch.cat(
            [
                padded[:, :, y : y + width, x : x + width]
                for y, x in ((2, 2), (0, 2), (4, 2), (2, 0), (2, 4))
            ]
        )
        views = torch.cat((views, views.flip((-1,))))
        features = self.teacher.features(views).flatten(1)
        logits = self.teacher.readout(features)
        target = logits.mean(0) / self.temperature
        residual = target - logits[0]
        vector = features[0]
        norm = vector.norm().clamp_min(1e-6)
        unit = vector / norm
        # Recursive least squares fits the discrepancy over all past inputs.
        projected = self.precision @ unit
        gain = projected / (1 + unit @ projected)
        self.precision.sub_(torch.outer(gain, projected))
        self.correction.add_(
            torch.outer(residual / norm - self.correction @ unit, gain)
        )
        self.model.readout.weight.copy_(
            self.teacher.readout.weight + self.strength * self.correction
        )
