"""Heterogeneous form scanners and balanced, station-specific visual handovers."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if not (ROOT / "scanner_data.py").exists():
    sys.path.append(str(ROOT.parent))
import scanner_data as source

SEEDS = (907, 911, 919, 929, 937, 941)
SITE = (17, 23, 42, 58, 71, 86)
SPECIAL = (0, 1, 1, 0, 1, 0)
PANELS = np.array([[0, 1, 0, 1, 1, 0], [1, 0, 1, 0, 0, 1]])
DIGIT_PAIRS = ((0, 3), (1, 4), (2, 3), (0, 4), (1, 2), (0, 1))
POSE_PAIRS = ((0, 1), (0, 2), (1, 3), (1, 2), (0, 3), (2, 3))


def site_of(seed):
    return SEEDS.index(seed) if seed in SEEDS else 0


def prepare_backbones():
    with np.load(source.ROOT / "data" / "backbone.npz") as m:
        base = dict(m)
    raw, y, parts = source.partitions()
    pix, _d, pose = source.contents(raw, y, parts[0])
    x = pix / 16.0 - 0.30
    h = np.maximum(x @ base["w1"].T + base["b1"], 0)
    rng = np.random.default_rng(64031)
    w = rng.normal(0, 0.1, (48, 48))
    b = np.zeros(48)
    cls = rng.normal(0, 0.08, (48, 4))
    c = np.zeros(4)
    by_pose = [np.flatnonzero(pose == a) for a in range(4)]
    for _ in range(2200):
        i = rng.integers(len(h), size=96)
        j = np.array([rng.choice(by_pose[p]) for p in pose[i]])
        a = h[i] @ w.T + b
        ap = h[j] @ w.T + b
        v = np.maximum(a, 0)
        vp = np.maximum(ap, 0)
        err = (source.softmax(v @ cls + c) - np.eye(4)[pose[i]]) / len(i)
        cons = 0.13 * (v - vp) / len(i)
        g = (err @ cls.T + cons) * (a > 0)
        gp = -cons * (ap > 0)
        cls -= 0.055 * v.T @ err
        c -= 0.055 * err.sum(0)
        w -= 0.055 * (g.T @ h[i] + gp.T @ h[j])
        b -= 0.055 * (g + gp).sum(0)
    late = np.maximum(h @ w.T + b, 0)
    alt = {
        **base,
        "w2": w,
        "b2": b,
        "mu": np.array([h.mean(0), late.mean(0)]),
        "std": np.array([h.std(0), late.std(0)]).clip(0.12, None),
    }
    for k, m in enumerate((base, alt)):
        np.savez_compressed(ROOT / "data" / f"backbone-{k}.npz", **m)


def encode(pix, site):
    with np.load(ROOT / "data" / f"backbone-{SPECIAL[site]}.npz") as m:
        h = np.maximum((pix / 16.0 - 0.30) @ m["w1"].T + m["b1"], 0)
        v = np.maximum(h @ m["w2"].T + m["b2"], 0)
        return (np.stack([h, v], 1) - m["mu"]) / m["std"]


def coordinates(seed):
    return source.station_coords(seed)


def probes(seed):
    p, d, o = source.gallery()
    r = np.random.default_rng(82000 + seed)
    site = site_of(seed)
    idx = np.concatenate(
        [
            r.choice(np.flatnonzero((d == i) & (o == j)), 9, replace=False)
            for i in range(5)
            for j in range(4)
        ]
    )
    r.shuffle(idx)
    return source.turn(encode(p[idx], site), coordinates(seed)), np.c_[
        p[idx], source.DIGITS[d[idx]], o[idx], np.full(len(idx), SITE[site])
    ].astype(np.uint8)


def sheets():
    from PIL import Image, ImageDraw, ImageFont

    raw, y, parts = source.partitions()
    reviews = []
    for site in range(6):
        rng = np.random.default_rng(18321 + site)
        pool = parts[3]
        d = np.repeat(y[pool], 4)
        o = np.tile(np.arange(4), len(pool))
        yes = np.isin(d, DIGIT_PAIRS[site])
        rot = np.isin(o, POSE_PAIRS[site])
        # Five draws in every joint quadrant guarantee equal occupancy and
        # independence of the opposite disposition on either sheet.
        chosen = np.concatenate(
            [
                rng.choice(np.flatnonzero((yes == a) & (rot == b)), 5, replace=False)
                for a in (False, True)
                for b in (False, True)
            ]
        )
        rng.shuffle(chosen)
        pixels = source.rotations(raw[pool]).reshape(-1, 64)[chosen].reshape(-1, 8, 8)
        reviews.append((pixels, np.array([yes[chosen], rot[chosen]])))
    for group, key in enumerate("ab"):
        img = Image.new("RGB", (1020, 6 * 130), "#eeeae3")
        draw = ImageDraw.Draw(img)
        for site, (pix, rules) in enumerate(reviews):
            oy = 130 * site
            draw.text(
                (7, oy + 4),
                f"Station {SITE[site]}",
                font=ImageFont.load_default(size=17),
                fill="black",
            )
            selected = rules[PANELS[group, site]]
            for k, (text, mask) in enumerate(
                (("ACCEPT", selected), ("REJECT", ~selected))
            ):
                top = oy + 26 + 50 * k
                draw.text(
                    (10, top + 13),
                    text,
                    font=ImageFont.load_default(size=13),
                    fill="black",
                )
                for j, i in enumerate(np.flatnonzero(mask)):
                    tile = Image.fromarray(
                        np.rint((1 - pix[i] / 16.0) * 255).astype(np.uint8)
                    ).resize((44, 44), Image.Resampling.NEAREST)
                    img.paste(tile, (84 + 84 * j, top))
        img.save(ROOT / "images" / f"inspection-{key}.png")


if __name__ == "__main__":
    prepare_backbones()
    sheets()
