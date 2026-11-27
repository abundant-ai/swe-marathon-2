"""Commission a camera adapter as frames arrive, retaining a fixed RGB reference path."""

import torch

INVERSE = []
GATE = []


class Updater:
    def __init__(self, model):
        self.adapter = model.adapter
        self.score = 0.0
        self.ready = False

    @torch.no_grad()
    def update(self, image):
        if not GATE:
            return
        from adapter import camera_signature

        weight, bias = GATE
        detector = image.new_tensor(weight)
        probability = torch.sigmoid(camera_signature(image) @ detector + bias).item()
        # A single anomalous color should contribute only weak evidence for switching on a new calibration.
        self.score = max(0.0, self.score + probability - 0.35)
        if not self.ready and self.score < 1.5:
            return
        self.ready = True
        self.adapter.gate.weight.copy_(detector[None])
        self.adapter.gate.bias.fill_(bias)
        self.adapter.delta.copy_(image.new_tensor(INVERSE) - torch.eye(3))
