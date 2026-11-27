"""Train the source CNN on the supplied labeled captures."""

import argparse

import numpy as np
import torch
from core_model import Classifier, save, tensor
from torch.nn import functional as F


def train(data="source.npz", output="trained.npz", seed=37, epochs=20):
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    with np.load(data, allow_pickle=False) as d:
        x, y = tensor(d["x"]), torch.from_numpy(d["y"])
    model = Classifier().train()
    opt = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.005)
    for epoch in range(epochs):
        for group in torch.randperm(len(y)).split(96):
            batch = x[group]
            if torch.rand(()) < 0.5:
                batch = batch.flip([-1])
            batch = (
                batch * torch.empty(len(group), 3, 1, 1).uniform_(0.85, 1.15)
                + torch.empty(len(group), 1, 1, 1).uniform_(-0.08, 0.08)
            ).clamp(0, 1)
            loss = F.cross_entropy(model(batch), y[group])
            opt.zero_grad()
            loss.backward()
            opt.step()
        if epoch == epochs * 3 // 4:
            for group in opt.param_groups:
                group["lr"] *= 0.25
    save(model.eval(), output)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="source.npz")
    p.add_argument("--out", default="trained.npz")
    p.add_argument("--seed", type=int, default=37)
    p.add_argument("--epochs", type=int, default=20)
    args = p.parse_args()
    train(args.data, args.out, args.seed, args.epochs)
