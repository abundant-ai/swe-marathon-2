"""Fixed-width numeric snapshots of the published CNN state."""

import numpy as np
import torch


class StateLayout:
    def __init__(self, model):
        self.model = model
        initial = model.state_dict(keep_vars=True)
        self.contract = {name: (value.shape, value.dtype) for name, value in initial.items()}
        self.numel = sum(value.numel() for value in initial.values())

    def tensors(self):
        state = self.model.state_dict(keep_vars=True)
        if state.keys() != self.contract.keys():
            raise ValueError("The published CNN tensor names changed")
        for name, (shape, dtype) in self.contract.items():
            value = state[name]
            if value.shape != shape or value.dtype != dtype:
                raise ValueError("The published CNN tensor contract changed: " + name)
            yield value

    def encode(self):
        return (
            np.concatenate(
                [t.detach().cpu().float().reshape(-1).numpy() for t in self.tensors()]
            )
            .astype("<f4", copy=False)
            .tobytes()
        )

    @torch.no_grad()
    def restore(self, raw):
        packed = np.frombuffer(raw, dtype="<f4").copy()
        if packed.size != self.numel or not np.isfinite(packed).all():
            raise ValueError("Invalid online CNN state")
        offset = 0
        for dst in self.tensors():
            size = dst.numel()
            dst.copy_(
                torch.from_numpy(packed[offset : offset + size]).reshape(dst.shape)
            )
            offset += size
