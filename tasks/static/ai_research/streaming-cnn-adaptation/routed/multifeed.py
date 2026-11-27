"""Use successive exposures to select a response and update the active color adapter."""

import torch

INVERSES = []
GATES = []
MODE = []


class Updater:
    def __init__(self, model):
        self.adapter = model.adapter
        self.evidence = torch.zeros(2)
        self.active = None

    @torch.no_grad()
    def update(self, image):
        if not GATES:
            return
        from adapter import camera_signature

        features = camera_signature(image)
        weights = image.new_tensor([gate[0] for gate in GATES])
        biases = image.new_tensor([gate[1] for gate in GATES])
        mode_w, mode_b = MODE
        logits = image.new_tensor(mode_w) @ features[0] + image.new_tensor(mode_b)
        scores = (logits[1:] - logits[1:].mean()).clamp(-5, 5)
        self.evidence.mul_(0.82).add_(scores)
        selected = int(self.evidence.argmax())
        if selected != self.active:
            self.active = selected
            self.adapter.gate.weight.copy_(weights[selected][None])
            self.adapter.gate.bias.copy_(biases[selected])
            self.adapter.delta.copy_(
                image.new_tensor(INVERSES[selected]) - torch.eye(3)
            )
