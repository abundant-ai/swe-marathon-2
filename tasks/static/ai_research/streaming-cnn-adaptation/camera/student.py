"""Distill a paired-camera teacher into the deployed weights using only images received so far."""

from collections import deque
from copy import deepcopy

import torch
from torch.nn import functional as F

INVERSE = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
PROFILES = []


def descriptor(images):
    channels = images.flatten(2)
    levels = channels.new_tensor((0.15, 0.5, 0.85))
    quantiles = torch.quantile(channels, levels, dim=-1).permute(1, 0, 2).flatten(1)
    means = channels.mean(-1).clamp_min(0.005).log()
    return torch.cat((quantiles, means - means.mean(-1, keepdim=True)), dim=-1)


class Updater:
    def __init__(self, model, rate=0.0003, retention=1.0):
        self.student = model.eval()
        self.teacher = deepcopy(model).eval().requires_grad_(False)
        self.inverse = model.readout.bias.new_tensor(INVERSE)
        self.forward = torch.linalg.inv(self.inverse)
        self.profiles = model.readout.bias.new_tensor(PROFILES)
        self.retention = retention
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=rate, weight_decay=0.0005
        )
        self.memory = deque(maxlen=64)
        self.rng = torch.Generator().manual_seed(112)
        self.odds = 0.0

    def update(self, image):
        if not self.profiles.numel():
            return
        with torch.no_grad():
            scale = self.profiles.flatten(0, 1).std(0).clamp_min(0.08)
            distances = ((self.profiles - descriptor(image)) / scale).square().mean(-1)
            near = distances.topk(3, largest=False).values.mean(-1)
            self.odds = 0.65 * self.odds + float((near[0] - near[1]).clamp(-2.0, 2.0))
            canonical = image
            if self.odds > 0:
                canonical = torch.einsum("ij,bjhw->bihw", self.inverse, image).clamp(
                    0, 1
                )
            self.memory.append(canonical.detach())
            chosen = torch.randperm(len(self.memory), generator=self.rng)[:7].tolist()
            original = torch.cat([canonical, *(self.memory[k] for k in chosen)])
            target = self.teacher(original)
            alternate = torch.einsum("ij,bjhw->bihw", self.forward, original).clamp(
                0, 1
            )
        with torch.enable_grad():
            on_source, on_board = self.student(torch.cat((original, alternate))).chunk(
                2
            )
            weights = self.retention
            loss = (
                F.smooth_l1_loss(on_board, target)
                + weights * F.smooth_l1_loss(on_source, target)
            ) / (1 + weights)
            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            self.optimizer.step()
