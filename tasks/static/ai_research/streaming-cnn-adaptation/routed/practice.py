"""Exercise a two-camera service on reserved public development footage."""

import argparse
from copy import deepcopy

import numpy as np
import torch
from core_model import load, tensor
from online import Updater
from ordering import frame_order


def accuracy(model, x, y):
    with torch.no_grad():
        return float(np.mean(model.eval()(tensor(x)).argmax(1).numpy() == y))


def practice(path, schedule, slots=None):
    torch.set_num_threads(1)
    matrices = np.array(
        [
            [[0.07, 0.04, 0.82], [0.05, 0.74, 0.03], [0.69, 0.03, 0.08]],
            [[0.09, 0.69, 0.05], [0.075, 0.04, 0.57], [0.75, 0.03, 0.04]],
        ]
    )
    with np.load("development.npz") as data:
        images, labels, ids = data["x"], data["y"], data["ids"]
    with np.load("source.npz") as data:
        source, targets = data["x"][::13], data["y"][::13]
    for session in np.unique(ids[:, 0]):
        fixed = load(path)
        model = deepcopy(fixed)
        update = Updater(model)
        current = np.flatnonzero(ids[:, 0] == session).reshape(10, 4, 8)
        other = np.flatnonzero(ids[:, 0] != session).reshape(10, 4, 8)
        rng = np.random.default_rng(891)
        for indices, probe, mode in (
            (current[:, 1], current[:, 3], 0),
            (other[:, 1], other[:, 3], 1),
            (current[:, 2], current[:, 3], 0),
        ):
            order = frame_order(indices, rng, schedule)

            def render(indices):
                return np.clip(
                    np.rint(images[indices] @ matrices[mode].T), 0, 255
                ).astype(np.uint8)

            rgb = render(order)
            fresh = render(probe.ravel())
            local = np.asarray(slots[mode])[labels] if slots is not None else labels
            hits = []
            for frame, label in zip(rgb, local[order], strict=True):
                image = tensor(frame[None])
                with torch.no_grad():
                    hits.append(model.eval()(image).argmax().item() == label)
                update.update(image)
            print(
                f"session {session} camera {mode + 1} | stream frozen {accuracy(fixed, rgb, local[order]):.3f} adapted {np.mean(hits):.3f} | fresh {accuracy(model, fresh, local[probe.ravel()]):.3f} | original RGB {accuracy(model, source, targets):.3f}"
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", default="trained.npz")
    p.add_argument("--schedule", choices=("clips", "switches"), default="clips")

    def permutation(value):
        ids = [int(s) for s in value.split(",")]
        if sorted(ids) != list(range(10)):
            raise argparse.ArgumentTypeError(
                "Expected a permutation of category indices 0 through 9"
            )
        return ids

    for name in ("a", "b"):
        p.add_argument("--slots-" + name, type=permutation, default=list(range(10)))
    args = p.parse_args()
    practice(args.checkpoint, args.schedule, (args.slots_a, args.slots_b))
