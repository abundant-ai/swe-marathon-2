"""Estimate camera-specific feature moments and class-frequency drift from previous frames."""

from copy import deepcopy

import torch
from torch import nn


class Updater:
    def __init__(self, model, momentum=0.006, layers=3, prior_strength=0.5):
        self.model = model
        self.tracking = deepcopy(model)
        self.layers = []
        self.bias = model.readout.bias.detach().clone()
        self.prior = torch.full_like(self.bias, 0.1)
        self.strength = prior_strength
        for deployed, track in zip(
            model.modules(), self.tracking.modules(), strict=True
        ):
            if isinstance(deployed, nn.BatchNorm2d):
                track.momentum = momentum if len(self.layers) < layers else 0.0
                self.layers.append((deployed, track))

    @torch.no_grad()
    def update(self, image):
        # The running marginal estimates a slow camera bias; a single object's repeated
        # views should have little influence on the class prior.
        logits = self.tracking.eval()(torch.cat((image, image.flip([-1]))))
        self.prior.lerp_(logits.softmax(-1).mean(0), 0.012)
        correction = (self.prior.clamp_min(0.025) / 0.1).log()
        self.model.readout.bias.copy_(self.bias - self.strength * correction)
        self.tracking.train()(image)
        for deployed, track in self.layers:
            inv = (track.running_var + track.eps).rsqrt()
            deployed.weight.copy_(
                track.weight * (deployed.running_var + deployed.eps).sqrt() * inv
            )
            deployed.bias.copy_(
                track.bias
                + track.weight * (deployed.running_mean - track.running_mean) * inv
            )
