"""Fit the deployed CNN's affine weights to the unlabeled stream's activation statistics."""

from copy import deepcopy

import torch
from torch import nn


class Updater:
    def __init__(self, model):
        self.statistics = deepcopy(model)
        self.layers = []
        for deployed, tracking in zip(
            model.modules(), self.statistics.modules(), strict=True
        ):
            if isinstance(deployed, nn.BatchNorm2d):
                tracking.momentum = 0.006
                self.layers.append((deployed, tracking))

    @torch.no_grad()
    def update(self, image):
        self.statistics.train()(image)
        for deployed, tracking in self.layers:
            # Preserve the source inference buffers. Express the fitted normalization
            # as scale and offset weights in the model used for the next prediction.
            inv_scale = (tracking.running_var + tracking.eps).rsqrt()
            source_scale = (deployed.running_var + deployed.eps).sqrt()
            deployed.weight.copy_(tracking.weight * source_scale * inv_scale)
            offset = (deployed.running_mean - tracking.running_mean) * inv_scale
            deployed.bias.copy_(tracking.bias + tracking.weight * offset)
