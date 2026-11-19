"""CPU reference checks for the experiment's stable global gradient clipping."""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from titans_task.clipping import clip_gradients  # noqa: E402


def main() -> None:
    """Compare clipping and AdamW updates against an independent FP64 norm."""
    for magnitude in (0.0, 1e-3, 1.0, 1e20, 1e35):
        actual = [torch.nn.Parameter(torch.ones(3)), torch.nn.Parameter(torch.ones(2))]
        reference = [torch.nn.Parameter(p.detach().clone()) for p in actual]
        for index, (left, right) in enumerate(zip(actual, reference, strict=True)):
            gradient = torch.arange(1, left.numel() + 1, dtype=torch.float32) * magnitude * (index + 1)
            left.grad = gradient.clone()
            right.grad = gradient.clone()
        total = torch.cat([p.grad.double() for p in reference]).norm()
        coefficient = (1.0 / (total + 1e-6)).clamp(max=1).float()
        for p in reference:
            p.grad.mul_(coefficient)
        clip_gradients(actual)
        for left, right in zip(actual, reference, strict=True):
            torch.testing.assert_close(left.grad, right.grad, rtol=2e-6, atol=1e-7)
        torch.optim.AdamW(actual, lr=1e-4).step()
        torch.optim.AdamW(reference, lr=1e-4).step()
        for left, right in zip(actual, reference, strict=True):
            torch.testing.assert_close(left, right, rtol=0, atol=1e-7)
    for value in (float('inf'), float('nan')):
        parameter = torch.nn.Parameter(torch.zeros(1))
        parameter.grad = torch.tensor([value])
        try:
            clip_gradients([parameter])
        except FloatingPointError:
            continue
        raise AssertionError('Accepted a nonfinite gradient')
    print('PASS stable clipping and AdamW parity, zero gradients, and nonfinite rejection')


if __name__ == '__main__':
    main()
