"""Learn two visual feature layers from real UCI handwritten numeral captures."""

import hashlib
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE_SHA = "0d7b054fea010270e9b3f06411c654c5e59547732ad626381980baffe0a23fb0"
DIGITS = np.array([1, 2, 4, 5, 7])
SEEDS = (727, 733, 739, 743, 751, 757)
HIST = ((1, 4), (0, 2))  # local glyph indices and quarter-turn positions
N = 48


def softmax(s):
    v = np.exp(s - s.max(1, keepdims=True))
    return v / v.sum(1, keepdims=True)


def rotations(raw):
    return np.stack(
        [np.rot90(raw, k, axes=(1, 2)).reshape(len(raw), 64) for k in range(4)], axis=1
    )


def prepare_source(archive):
    source = Path(archive).read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError("Unexpected optical digit archive")
    with zipfile.ZipFile(archive) as z:
        for name, out in [("optdigits.tra", "train"), ("optdigits.tes", "test")]:
            a = np.loadtxt(z.open(name), delimiter=",", dtype=np.uint8)
            selected = np.isin(a[:, -1], DIGITS)
            a = a[selected]
            y = np.searchsorted(DIGITS, a[:, -1])
            np.savez_compressed(
                ROOT / "data" / f"{out}-captures.npz",
                images=a[:, :64].reshape(-1, 8, 8),
                digit=y,
            )


def captures(split):
    with np.load(ROOT / "data" / f"{split}-captures.npz") as f:
        return f["images"], f["digit"]


def partitions():
    raw, y = captures("train")
    r = np.random.default_rng(27531)
    parts = [[], [], [], []]
    for c in range(5):
        order = r.permutation(np.flatnonzero(y == c))
        cuts = np.array([0.58, 0.79, 0.94]) * len(order)
        for dest, indices in zip(parts, np.split(order, cuts.astype(int))):
            dest.extend(indices)
    return raw, y, [np.array(p) for p in parts]


def backbone():
    raw, target, groups = partitions()
    base = groups[0]
    x = rotations(raw[base]).reshape(-1, 64).astype(float) / 16 - 0.30
    d = np.repeat(target[base], 4)
    o = np.tile(np.arange(4), len(base))
    rng = np.random.default_rng(8821)
    w1 = rng.normal(0, 0.15, (48, 64))
    b1 = np.zeros(48)
    cls = rng.normal(0, 0.09, (48, 20))
    bias = np.zeros(20)
    y = np.eye(20)[4 * d + o]
    for _ in range(2400):
        i = rng.integers(len(x), size=96)
        inp = x[i]
        z = inp @ w1.T + b1
        h = np.maximum(z, 0)
        err = (softmax(h @ cls + bias) - y[i]) / len(i)
        grad = (err @ cls.T) * (z > 0)
        cls -= 0.075 * h.T @ err
        bias -= 0.075 * err.sum(0)
        w1 -= 0.075 * grad.T @ inp
        b1 -= 0.075 * grad.sum(0)
    h = np.maximum(x @ w1.T + b1, 0)
    w2 = rng.normal(0, 0.10, (48, 48))
    b2 = np.zeros(48)
    out = rng.normal(0, 0.09, (48, 5))
    c2 = np.zeros(5)
    for _ in range(2200):
        i = rng.integers(len(h), size=96)
        j = (i // 4) * 4 + rng.integers(4, size=len(i))
        h0 = h[i]
        h1 = h[j]
        z = h0 @ w2.T + b2
        zp = h1 @ w2.T + b2
        a = np.maximum(z, 0)
        p = np.maximum(zp, 0)
        loss = (softmax(a @ out + c2) - np.eye(5)[d[i]]) / len(i)
        pair = 0.13 * (a - p) / len(i)
        grad = (loss @ out.T + pair) * (z > 0)
        g2 = -pair * (zp > 0)
        out -= 0.055 * a.T @ loss
        c2 -= 0.055 * loss.sum(0)
        w2 -= 0.055 * (grad.T @ h0 + g2.T @ h1)
        b2 -= 0.055 * (grad + g2).sum(0)
    top = np.maximum(h @ w2.T + b2, 0)
    mu = np.array([h.mean(0), top.mean(0)])
    std = np.array([h.std(0), top.std(0)]).clip(0.12, None)
    np.savez_compressed(
        ROOT / "data" / "backbone.npz", w1=w1, b1=b1, w2=w2, b2=b2, mu=mu, std=std
    )


def encode(pixels):
    x = pixels.astype(float) / 16 - 0.30
    with np.load(ROOT / "data" / "backbone.npz") as m:
        h = np.maximum(x @ m["w1"].T + m["b1"], 0)
        top = np.maximum(h @ m["w2"].T + m["b2"], 0)
        return (np.stack([h, top], axis=1) - m["mu"]) / m["std"]


def measure(pixels):
    p = pixels.reshape(-1, 8, 8) / 16.0
    return np.column_stack(
        [
            p.mean((1, 2)),
            p[:, :4].mean((1, 2)) - p[:, 4:].mean((1, 2)),
            p[:, :, :4].mean((1, 2)) - p[:, :, 4:].mean((1, 2)),
            p[:, 2:6, 2:6].mean((1, 2)),
        ]
    )


def contents(raw, labels, ids):
    pixels = rotations(raw[ids]).reshape(-1, 64)
    digits = np.repeat(labels[ids], 4)
    pose = np.tile(np.arange(4), len(ids))
    return pixels, digits, pose


def gallery():
    raw, y, parts = partitions()
    p, d, o = contents(raw, y, parts[2])
    return p, d, o


def station_coords(seed):
    rng = np.random.default_rng(88000 + seed)
    return np.stack([np.linalg.qr(rng.normal(size=(48, 48)))[0] for _ in range(2)])


def turn(x, q):
    return np.einsum("nbd,bdk->nbk", x, q)


def probes(seed):
    p, d, o = gallery()
    rng = np.random.default_rng(90000 + seed)
    chosen = np.concatenate(
        [
            rng.choice(np.flatnonzero((d == i) & (o == k)), 9, replace=False)
            for i in range(5)
            for k in range(4)
        ]
    )
    rng.shuffle(chosen)
    pix = p[chosen]
    q = station_coords(seed)
    return turn(encode(pix), q), np.c_[pix, DIGITS[d[chosen]], o[chosen]].astype(
        np.uint8
    )


if __name__ == "__main__":
    import sys

    prepare_source(sys.argv[1])
    backbone()
