"""Build two different stock manifests with identical continuing video, cameras and source labels."""

import argparse
import shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def manifest(path, photos, assignments):
    sheet = Image.new("RGB", (416, 1120), "white")
    draw = ImageDraw.Draw(sheet)
    for station, slots in enumerate(assignments):
        for category, slot in enumerate(slots):
            x, y = station * 208 + 4, int(slot) * 112 + 4
            for view, photo in enumerate(photos[category]):
                sheet.paste(
                    Image.fromarray(photo).resize((96, 96), Image.Resampling.NEAREST),
                    (x + 96 * view, y),
                )
            draw.text(
                (x, y + 96),
                f"Station {station + 1}    Stock ID {slot:02d}",
                fill="black",
            )
    sheet.save(path)


def prepare(source, camera_data, dest):
    dest.mkdir(parents=True, exist_ok=False)
    for name in (
        "source.npz",
        "development.npz",
        "source_probe.npz",
        "public-splits.json",
        "preview_a.png",
    ):
        shutil.copy2(camera_data / name, dest / name)
    shutil.copy2(camera_data / "preview_a.png", dest / "preview_b.png")
    for tag in ("common", "replicate"):
        with np.load(camera_data / f"{tag}.npz") as data:
            np.savez(
                dest / f"{tag}.npz",
                **dict(data),
                **{"stock_delta": np.zeros((10, 10), np.float32)},
            )
    with np.load(source / "preview_a.npz") as captures:
        photos = np.stack([captures["x"][captures["y"] == i] for i in range(10)])
    assert photos.shape == (10, 2, 32, 32, 3)
    rng = np.random.default_rng(81037)
    base = [rng.permutation(10) for _ in range(2)]
    for world, shift in [("a", 0), ("b", 3)]:
        slots = [(a + shift) % 10 for a in base]
        manifest(dest / f"inventory_{world}.png", photos, slots)
        for block in ("arrival", "middle", "return", "probe", "middle_probe"):
            with np.load(camera_data / f"a_{block}.npz") as z:
                mode = int(block.startswith("middle"))
                np.savez_compressed(
                    dest / f"{world}_{block}.npz",
                    x=z["x"],
                    x_alt=z["x_alt"],
                    ids=z["ids"],
                    y=slots[mode][z["y"]],
                    y_alt=slots[1 - mode][z["y"]],
                )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("source", "camera_data", "dest"):
        p.add_argument(key, type=Path)
    args = p.parse_args()
    prepare(args.source, args.camera_data, args.dest)
