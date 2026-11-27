"""Fixed RGB classifier and numeric checkpoint format shared by training and deployment."""

import numpy as np
import torch
from torch import nn


class Classifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1, bias=False),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 48, 3, padding=1, bias=False),
            nn.BatchNorm2d(48),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((2, 2)),
        )
        self.readout = nn.Linear(192, 10)

    def forward(self, x):
        return self.readout(self.features(x).flatten(1))


def tensor(rgb):
    """Convert NHWC uint8 RGB to NCHW float32 in [0,1]."""
    return (
        torch.from_numpy(np.ascontiguousarray(rgb))
        .permute(0, 3, 1, 2)
        .float()
        .div_(255)
    )


def save(model, path):
    np.savez(
        path, **{k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}
    )


def load(path):
    model = Classifier()
    expected = model.state_dict()
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(expected):
            raise ValueError("Checkpoint fields do not match Classifier")
        values = {}
        for key, ref in expected.items():
            value = archive[key]
            if (
                value.shape != tuple(ref.shape)
                or value.dtype != ref.numpy().dtype
                or not np.isfinite(value).all()
            ):
                raise ValueError("Invalid tensor " + key)
            values[key] = torch.from_numpy(value.copy())
    model.load_state_dict(values)
    return model.eval()
