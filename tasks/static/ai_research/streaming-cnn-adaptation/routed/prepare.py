"""Build paired service-camera observations and identity-preserving source checkpoints."""

import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location("service_camera", ROOT / "camera/prepare.py")
camera = module_from_spec(spec)
spec.loader.exec_module(camera)

RESPONSES = {
    "a": (
        [[0.04, 0.06, 0.80], [0.04, 0.63, 0.05], [0.60, 0.05, 0.03]],
        [[0.08, 0.61, 0.03], [0.05, 0.03, 0.52], [0.73, 0.04, 0.05]],
    ),
    "b": (
        [[0.05, 0.02, 0.68], [0.64, 0.03, 0.06], [0.04, 0.77, 0.04]],
        [[0.71, 0.03, 0.05], [0.03, 0.04, 0.69], [0.05, 0.64, 0.04]],
    ),
}


def prepare(source, dest, *, reacquired=False):
    dest.mkdir(parents=True, exist_ok=False)
    for name in (
        "source.npz",
        "development.npz",
        "source_probe.npz",
        "public-splits.json",
    ):
        shutil.copy2(source / name, dest / name)
    for name in ("common", "replicate"):
        with np.load(source / (name + ".npz")) as archive:
            state = dict(archive)
        state.update(
            {
                "adapter.delta": np.zeros((3, 3), np.float32),
                "adapter.gate.weight": np.zeros((1, 21), np.float32),
                "adapter.gate.bias": np.zeros(1, np.float32),
            }
        )
        np.savez(dest / (name + ".npz"), **state)
    for world, pair in RESPONSES.items():
        matrices = np.asarray(pair)
        with np.load(source / f"preview_{world}.npz") as archive:
            if reacquired:
                from reacquire import make_panel

                rng = np.random.default_rng(511 if world == "a" else 719)
                panels = [make_panel(archive["x"], m, rng) for m in matrices]
            else:
                panels = [camera.calibration_sheet(archive["x"], m) for m in matrices]
        image = Image.new("RGB", (2 * panels[0].width, panels[0].height))
        for i, panel in enumerate(panels):
            image.paste(panel, (i * panel.width, 0))
        image.save(dest / f"preview_{world}.png")
        for key in ("arrival", "middle", "return", "probe", "middle_probe"):
            name = key if key.startswith("middle") else f"{world}_{key}"
            i = int(key.startswith("middle"))
            with np.load(source / (name + ".npz")) as archive:
                np.savez_compressed(
                    dest / f"{world}_{key}.npz",
                    x=camera.observe(archive["x"], matrices[i]),
                    x_alt=camera.observe(archive["x"], matrices[1 - i]),
                    y=archive["y"],
                    ids=archive["ids"],
                )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("--reacquired", action="store_true")
    args = parser.parse_args()
    prepare(args.source, args.dest, reacquired=args.reacquired)
