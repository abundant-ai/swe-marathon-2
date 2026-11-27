"""Fit a shared CNN readout to both camera responses from paired, unlabeled views."""

from copy import deepcopy

import torch
from torch.nn import functional as F

INVERSE = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
PROFILES = []


def descriptor(images):
    channels = images.flatten(2)
    levels = channels.new_tensor((0.15, 0.5, 0.85))
    values = torch.quantile(channels, levels, dim=-1).permute(1, 0, 2).flatten(1)
    means = channels.mean(-1).clamp_min(0.005).log()
    return torch.cat((values, means - means.mean(-1, keepdim=True)), dim=-1)


class Updater:
    def __init__(self, model, ridge=1.0, retention=4.0):
        self.student = model.readout
        self.teacher = deepcopy(model).eval().requires_grad_(False)
        self.inverse = self.student.weight.new_tensor(INVERSE)
        self.forward = torch.linalg.inv(self.inverse)
        self.profiles = self.student.weight.new_tensor(PROFILES)
        self.retention = retention
        self.odds = 0.0
        size = self.student.in_features
        self.precision = ridge * torch.eye(size)
        self.targets = torch.zeros_like(self.student.weight)

    @torch.no_grad()
    def update(self, image):
        if not self.profiles.numel():
            return
        scales = self.profiles.flatten(0, 1).std(0).clamp_min(0.08)
        distances = ((self.profiles - descriptor(image)) / scales).square().mean(-1)
        near = distances.topk(3, largest=False).values.mean(-1)
        self.odds = 0.65 * self.odds + float((near[0] - near[1]).clamp(-2.0, 2.0))
        orig = (
            torch.einsum("ij,bjhw->bihw", self.inverse, image).clamp(0, 1)
            if self.odds > 0
            else image
        )
        padded = F.pad(orig, (3, 3, 3, 3), mode="replicate")
        views = torch.cat(
            [
                padded[:, :, y : y + 32, x : x + 32]
                for x, y in ((3, 3), (0, 3), (6, 3), (3, 0), (3, 6))
            ]
        )
        views = torch.cat((views, views.flip([-1])))
        service = torch.einsum("ij,bjhw->bihw", self.forward, views).clamp(0, 1)
        original, board = (
            self.teacher.features(torch.cat((views, service))).flatten(1).chunk(2)
        )
        difference = self.teacher.readout(original) - self.teacher.readout(board)
        # Fit a minimum-change linear operator. Native feature rows anchor the old mapping.
        scale = board.norm(dim=1, keepdim=True).clamp_min(1e-5)
        b = board / scale
        a = F.normalize(original)
        self.precision.add_(b.T @ b + self.retention * (a.T @ a))
        self.targets.add_((difference / scale).T @ b)
        correction = torch.linalg.solve(self.precision, self.targets.T).T
        self.student.weight.copy_(self.teacher.readout.weight + correction)
