"""Infer the active camera from incoming RGB before committing a first-layer correction."""

import torch

# The commissioning program fills these from its paired input photos.
INVERSE = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
PROFILES = []
STRENGTH = 1.0


def descriptor(images):
    """Measure each exposure using nine channel quantiles and its chromaticity."""
    channels = images.flatten(2)
    quantiles = torch.quantile(channels, channels.new_tensor([.15, .5, .85]), dim=-1)
    quantiles = quantiles.permute(1, 0, 2).flatten(1)
    means = channels.mean(-1).clamp_min(.005)
    chroma = means.log() - means.log().mean(-1, keepdim=True)
    return torch.cat((quantiles, chroma), dim=-1)


class Updater:
    def __init__(self, model):
        self.kernel = model.features[0].weight
        self.initial = self.kernel.detach().clone()
        inverse = self.initial.new_tensor(INVERSE)
        self.corrected = torch.einsum("ocxy,ci->oixy", self.initial, inverse)
        self.profiles = self.initial.new_tensor(PROFILES)
        self.log_odds = 0.

    @torch.no_grad()
    def update(self, image):
        if not self.profiles.numel():
            return
        current = descriptor(image)
        scales = self.profiles.flatten(0,1).std(0).clamp_min(.08)
        distance = ((self.profiles-current)/scales).square().mean(-1)
        near = distance.topk(3, largest=False).values.mean(-1)
        evidence = float((near[0]-near[1]).clamp(-2.,2.))
        self.log_odds = .65*self.log_odds + evidence
        probability = torch.sigmoid(self.kernel.new_tensor(3*self.log_odds))
        self.kernel.copy_(torch.lerp(self.initial, self.corrected, STRENGTH * probability))
