"""Fit a compact camera detector on the public source set and the preview-derived response."""

import numpy as np
import torch
from adapter import camera_signature


def fit_gate(source, inverse):
    forward = torch.tensor(np.linalg.inv(inverse), dtype=source.dtype)
    with torch.no_grad():
        native = camera_signature(source)
        serviced = camera_signature(
            torch.einsum("ij,bjhw->bihw", forward, source).clamp(0, 1)
        )
        x = torch.cat((native, serviced))
        mean = x.mean(0)
        scale = x.std(0).clamp_min(0.02)
        x = (x - mean) / scale
        y = torch.cat((torch.zeros(len(source)), torch.ones(len(source))))
    w = torch.zeros(x.shape[1], requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([w, b], lr=0.5, max_iter=60)

    def closure():
        opt.zero_grad()
        loss = (
            torch.nn.functional.binary_cross_entropy_with_logits(x @ w + b, y)
            + 0.001 * w.square().sum()
        )
        loss.backward()
        return loss

    opt.step(closure)
    with torch.no_grad():
        weight = w / scale
        return weight.tolist(), float((b - mean @ weight).item())


def fit_profiles(source, inverses):
    """Train a mode selector on calibrated replicas, reserving the original class for retention."""
    matrices = [torch.tensor(np.linalg.inv(v), dtype=source.dtype) for v in inverses]
    values = [camera_signature(source)]
    for matrix in matrices:
        values.append(
            camera_signature(torch.einsum("ij,bjhw->bihw", matrix, source).clamp(0, 1))
        )
    x = torch.cat(values)
    average, scale = x.mean(0), x.std(0).clamp_min(0.02)
    x = (x - average) / scale
    y = torch.arange(len(values)).repeat_interleave(len(source))
    w = torch.zeros(len(values), x.shape[1], requires_grad=True)
    b = torch.zeros(len(values), requires_grad=True)
    opt = torch.optim.LBFGS([w, b], lr=0.7, max_iter=64)

    def closure():
        opt.zero_grad()
        loss = (
            torch.nn.functional.cross_entropy(x @ w.T + b, y)
            + 0.0005 * w.square().sum()
        )
        loss.backward()
        return loss

    opt.step(closure)
    with torch.no_grad():
        weight = w / scale
        bias = b - weight @ average
        return weight.tolist(), bias.tolist()
