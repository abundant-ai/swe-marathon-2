"""Test a proposed site-17 handover on held-back pairs of public captures and a changed feeder."""

import argparse
import json

import numpy as np
from deployment import PAIR_GAIN, hidden, update
from worker import install


def simulate(data, product, register, recipes, frozen):
    models = []
    centers = []
    rates = []
    tensors = []
    identities = []
    for field in (product, register):
        w, b, h, x, t, j = [
            data[k][field] for k in ("W", "b", "v", "x", "tags", "bridge")
        ]
        nw, nb, _, nj, pace = install(w, b, h, x, t, j)
        s = {"W": nw, "b": nb, "bridge": nj}
        models.append(s)
        rates.append(np.zeros_like(pace) if frozen else pace)
        centers.append(hidden(x, s).reshape(len(x), -1).mean(0))
        marked = t[:, 64] != 255
        ids = t[marked, 68].astype(int)
        order = t[marked][np.argsort(ids)]
        identities.append(order[:, 64:66].astype(int))
        tensors.append(
            np.stack(
                [
                    x[(t[:, 67] == domain) & np.isin(t[:, 68], ids)][
                        np.argsort(t[(t[:, 67] == domain) & np.isin(t[:, 68], ids), 68])
                    ]
                    for domain in range(3)
                ]
            )
        )
    inds = np.indices((20, 20)).reshape(2, -1)
    first, second = inds
    tooling = [
        np.searchsorted([1, 2, 4, 5, 7], identity[index, 0])
        for identity, index in zip(identities, inds)
    ]
    rel = identities[0][first, 1] - identities[1][second, 1]
    hold = ((first + 2 * second) % 5) == 0
    g = np.random.default_rng(74520)
    heads = []
    results = []
    for phase, accepted in enumerate(((1,), (1, 3), (0, 2), (2,))):
        shift = phase % 2
        domain = phase % 2
        labels = np.isin((rel - recipes[shift, tooling[shift]]) % 4, accepted)
        mask = ~hold
        truth = labels[hold]
        train = labels[mask]
        loc = inds[:, mask]
        head = np.zeros((56, 56))
        bias = 0.0
        for n in range(48):
            ids = np.r_[
                g.choice(np.flatnonzero(~train), 24),
                g.choice(np.flatnonzero(train), 24),
            ]
            inputs = [z[domain, which[ids]] for z, which in zip(tensors, loc)]
            bias = update(models, inputs, centers, head, bias, train[ids], rates, shift)
        heads.append((head, bias, truth))
        feature = [
            hidden(z[2], s).reshape(20, -1) - c
            for z, s, c in zip(tensors, models, centers)
        ]
        row = []
        for old, b, y in heads:
            est = (
                ((feature[0] @ old)[first[hold]] * feature[1][second[hold]]).sum(1)
                * PAIR_GAIN
                + b
            ) > 0
            row.append(float(((est[y] == 1).mean() + (est[~y] == 0).mean()) / 2))
        results.append(row)
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product", required=True, type=int, choices=range(3))
    p.add_argument("--register", required=True, type=int, choices=range(3))
    p.add_argument("--day", nargs=5, required=True, type=int, choices=range(4))
    p.add_argument("--night", nargs=5, required=True, type=int, choices=range(4))
    a = p.parse_args()
    if a.product == a.register:
        p.error("Product and registration use distinct fields")
    with np.load("calibration.npz") as data:
        out = {
            k: simulate(data, a.product, a.register, np.array([a.day, a.night]), f)
            for k, f in [("continual", False), ("frozen_adapters", True)]
        }
    print(json.dumps(out))
