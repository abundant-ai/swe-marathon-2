"""Shared two-scanner bilinear readout and ordinary continual SGD used in commissioning."""

import numpy as np

PAIR_GAIN = 1.0
TRUNK_STEP = 0.065
READ_STEP = 0.065


def hidden(x, s):
    a = x[:, 0] @ s["W"][0].T + s["b"][0]
    early = np.maximum(a, 0.0)
    z = x[:, 1] @ s["W"][1].T + s["b"][1] + early @ s["bridge"].T
    late = np.maximum(z, 0.0)
    return np.stack([early, late], 1)


def update(states, inputs, centers, head, bias, y, paces, shift):
    """One simultaneous bilinear-head and two-trunk SGD step; biases and bridges retain the legacy wiring."""
    h = [hidden(x, s) for x, s in zip(inputs, states)]
    v = [a.reshape(len(a), -1) - c for a, c in zip(h, centers)]
    left = v[0] @ head
    right = v[1] @ head.T
    factor = PAIR_GAIN
    logits = factor * (left * v[1]).sum(1) + bias
    err = (1 / (1 + np.exp(-np.clip(logits, -40, 40))) - y) / len(y)
    head -= READ_STEP * factor * (v[0] * err[:, None]).T @ v[1]
    bias -= READ_STEP * err.sum()
    for x, s, ft, up, pace in zip(inputs, states, h, (right, left), paces):
        g = (up * (err * factor)[:, None]).reshape(ft.shape)
        late = g[:, 1] * (ft[:, 1] > 0)
        early = (g[:, 0] + late @ s["bridge"]) * (ft[:, 0] > 0)
        for k, grad in enumerate((early, late)):
            s["W"][k] -= TRUNK_STEP * pace[shift, k, :, None] * (grad.T @ x[:, k])
            s["b"][k] -= TRUNK_STEP * pace[shift, k] * grad.sum(0)
    return bias
