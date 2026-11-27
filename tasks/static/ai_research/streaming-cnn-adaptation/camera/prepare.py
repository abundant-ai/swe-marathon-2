"""Create a paired camera-service intervention on the same split of real video frames."""

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

# Two fixed simulated board responses. Values map a canonical column RGB to output RGB.
RESPONSES = {
    "a": np.array([[0.04, 0.06, 0.80], [0.04, 0.63, 0.05], [0.60, 0.05, 0.03]]),
    "b": np.array([[0.82, 0.05, 0.04], [0.04, 0.72, 0.03], [0.07, 0.04, 0.53]]),
}


def observe(rgb, response):
    return np.clip(np.rint(rgb @ response.T), 0, 255).astype(np.uint8)


def calibration_sheet(rgb, response):
    tiles = rgb[::2]
    if tiles.shape != (10, 32, 32, 3):
        raise ValueError("Expected two observations from each of ten preview captures")
    def panel(frames):
        return np.concatenate([np.concatenate(frames[i:i+5], axis=1) for i in (0,5)], axis=0)
    pair = np.concatenate((panel(tiles), panel(observe(tiles,response))), axis=0)
    return Image.fromarray(pair).resize((640, 512), Image.Resampling.NEAREST)


def prepare(base, dest):
    dest.mkdir(parents=True, exist_ok=False)
    for file in ("source.npz", "development.npz", "source_probe.npz", "common.npz", "replicate.npz", "public-splits.json"):
        shutil.copy2(base / file, dest / file)
    for world, response in RESPONSES.items():
        with np.load(base / f"preview_{world}.npz") as captures:
            calibration_sheet(captures["x"], response).save(dest / f"preview_{world}.png")
        for block in ("arrival", "return", "probe", "middle", "middle_probe"):
            name = block if block.startswith("middle") else f"{world}_{block}"
            with np.load(base / (name + ".npz")) as z:
                np.savez_compressed(dest / f"{world}_{block}.npz",
                                    x=(z["x"] if block.startswith("middle") else observe(z["x"], response)), y=z["y"], ids=z["ids"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", type=Path)
    p.add_argument("dest", type=Path)
    args = p.parse_args()
    prepare(args.base, args.dest)
