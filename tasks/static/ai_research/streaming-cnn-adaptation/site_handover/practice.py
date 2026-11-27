"""Rehearse the untagged image API using public example cards and CORe50 development feeds."""

import argparse
from pathlib import Path

import numpy as np
import torch
from core_model import load, tensor
from online import Updater
from ordering import frame_order


def practice(checkpoint: Path, schedule: str) -> None:
    """Show the frozen and adaptive stock-ID accuracies on both example room itineraries."""
    torch.set_num_threads(1)
    with np.load("practice-handover.npz", allow_pickle=False) as data:
        for site_start in (0, 1):
            model = load(checkpoint)
            frozen = load(checkpoint)
            editor = Updater(model)
            editor.update(tensor(data["renewal"][None]))
            for visit in range(3):
                site = site_start ^ (visit % 2)
                x = data[f"x{visit}"]
                y = data[f"y{visit}_site{site}"]
                indices = frame_order(
                    np.arange(len(y)).reshape(10, 8),
                    np.random.default_rng(518 + visit),
                    schedule,
                )
                pairs = []
                for i, idx in enumerate(indices):
                    half = int(i >= len(indices) // 2)
                    if i in (0, len(indices) // 2):
                        editor.update(tensor(data[f"chart{visit}_{half}_{site}"][None]))
                    frame = tensor(x[half, idx : idx + 1])
                    with torch.no_grad():
                        pairs.append(
                            (
                                int(frozen(frame).argmax()) == y[idx],
                                int(model(frame).argmax()) == y[idx],
                            )
                        )
                    editor.update(frame.clone())
                print(
                    "start room",
                    site_start + 1,
                    "visit",
                    visit + 1,
                    "frozen and adapted",
                    np.mean(pairs, axis=0).tolist(),
                )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, default=Path("trained.npz"))
    p.add_argument("--schedule", choices=("clips", "switches"), default="clips")
    a = p.parse_args()
    practice(a.checkpoint, a.schedule)
