"""Overflow-resistant global gradient clipping for FP32 research runs."""

from collections.abc import Iterable

import torch
from torch import Tensor


def clip_gradients(parameters: Iterable[Tensor], maximum: float = 1.0) -> tuple[float, float]:
    """Clip finite dense gradients without overflowing their squared-norm reduction.

    Scale gradients by their largest absolute entry before computing the norm.
    This preserves a single global clipping factor and FP32 gradient storage.
    Report norms as Python floats so telemetry can represent larger reductions.

    Args:
        parameters: Parameters with optional dense floating-point gradients.
        maximum: Positive finite global norm bound.

    Returns:
        Norm before clipping and the norm implied by the applied global factor.

    Raises:
        FloatingPointError: A gradient has a nonfinite entry.
        ValueError: The clipping bound is nonpositive or nonfinite.
    """
    import math

    if not math.isfinite(maximum) or maximum <= 0:
        raise ValueError('Clipping bound must be positive and finite')
    with torch.no_grad():
        gradients = [parameter.grad for parameter in parameters if parameter.grad is not None]
        if not gradients:
            return 0.0, 0.0
        scale = torch.stack([gradient.abs().amax() for gradient in gradients]).amax()
        if not torch.isfinite(scale).item():
            raise FloatingPointError('Nonfinite gradient entries before clipping')
        if scale.item() == 0:
            return 0.0, 0.0
        normalized = torch.stack([(gradient / scale).norm() for gradient in gradients]).norm()
        coefficient = ((maximum / scale) / (normalized + 1e-6 / scale)).clamp(max=1.0)
        for gradient in gradients:
            gradient.mul_(coefficient)
        before = float(scale.item()) * float(normalized.item())
        return before, before * float(coefficient.item())
