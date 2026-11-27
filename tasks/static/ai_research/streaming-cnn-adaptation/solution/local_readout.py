"""Update the CNN readout from past predictions on similar object views."""

from collections import deque

import torch


class Updater:
    def __init__(self, model, strength=1.5):
        self.model = model
        self.weight = model.readout.weight.detach().clone()
        self.bias = model.readout.bias.detach().clone()
        self.strength = strength
        self.history = deque(maxlen=24)
        self.center = None

    @torch.no_grad()
    def update(self, image):
        views = torch.cat(
            [image, image.flip([-1]), image.roll(2, -1), image.roll(-2, -1)]
        )
        features = self.model.features(views).flatten(1)
        mean = features.mean(0)
        self.center = mean if self.center is None else 0.95 * self.center + 0.05 * mean
        key = torch.nn.functional.normalize(mean, dim=0)
        logits = (features @ self.weight.T + self.bias).mean(0)
        self.history.append((key, logits.softmax(0)))
        keys, probabilities = map(torch.stack, zip(*self.history))
        weights = torch.exp((keys @ key - 1) / 0.045)
        posterior = (weights @ probabilities) / weights.sum()
        log_odds = posterior.clamp_min(0.01).log()
        residual = (log_odds - log_odds.mean()).clamp(-3, 3)
        # Restrict the update to directions distinct from the recent average appearance.
        direction = mean - self.center
        magnitude = direction.square().sum().clamp_min(mean.square().sum() * 0.15)
        correction = self.strength * torch.outer(residual, direction) / magnitude
        self.model.readout.weight.copy_(self.weight + correction)
        self.model.readout.bias.copy_(self.bias - correction @ self.center)
