"""A residual color correction selected independently for each input image."""

import torch
from torch import nn


def camera_signature(images):
    flat = images.flatten(2)
    average = flat.mean(-1)
    std = flat.std(-1)
    chroma = (average + 0.01).log()
    chroma = chroma - chroma.mean(1, keepdim=True)
    rgb = torch.cat((average, std, chroma), dim=1)
    return torch.cat((rgb, rgb.square(), rgb[:, :3] * rgb[:, :3].roll(1, 1)), dim=1)


class CameraAdapter(nn.Module):
    def __init__(self):
        super().__init__()
        self.gate = nn.Linear(21, 1)
        self.delta = nn.Parameter(torch.zeros(3, 3))
        nn.init.zeros_(self.gate.weight)
        nn.init.zeros_(self.gate.bias)

    def forward(self, image):
        probability = self.gate(camera_signature(image)).sigmoid().reshape(-1, 1, 1, 1)
        residual = torch.einsum("ij,bjhw->bihw", self.delta, image)
        return (image + probability * residual).clamp(0, 1)
