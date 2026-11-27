"""Replay two public labeled development sessions with predict-before-update timing."""

import argparse

import numpy as np
import torch
from core_model import load, tensor
from online import Updater
from ordering import frame_order


def practice(checkpoint, schedule):
    torch.set_num_threads(1)
    with np.load("development.npz", allow_pickle=False) as f:
        rgb, y, ids = f["x"], f["y"], f["ids"]
    for session in np.unique(ids[:, 0]):
        model = load(checkpoint)
        frozen = load(checkpoint)
        editor = Updater(model)
        stream = np.flatnonzero(ids[:, 0] == session).reshape(-1, 8)
        rng = np.random.default_rng(620)
        stream = frame_order(stream, rng, schedule)
        hits = []
        for i in stream:
            x = tensor(rgb[i : i + 1])
            with torch.no_grad():
                before = frozen(x).argmax().item()
                after = model.eval()(x).argmax().item()
            editor.update(x.clone())
            hits.append((before == y[i], after == y[i]))
        print(
            f"session {session}, frozen and adaptive accuracy:", np.mean(hits, axis=0)
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", default="trained.npz")
    p.add_argument("--schedule", choices=("clips", "switches"), default="clips")
    args = p.parse_args()
    practice(args.checkpoint, args.schedule)
