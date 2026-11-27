"""Generate a deployable scanner updater from the three public photographic handovers."""

import sys
from pathlib import Path

import numpy as np
from camera_oracle import OracleContext, commission
from PIL import Image


def build(context: OracleContext, *, train: bool = True) -> None:
    """Train the headquarters CNN, recover stock mappings and copy the observed chart swatches into the updater."""
    sys.path.insert(0, str(context.work))
    from core_model import load
    from gallery import decode

    work = context.work
    solution = context.solution
    commission(work, solution, train=train)
    # The decoder calibrates each later scanner from the in-stream image; the handover provides its identity.
    if (work / "site-handovers.png").exists():
        with Image.open(work / "site-handovers.png") as image:
            patches = np.asarray(
                image.convert("RGB").resize((12, 6), Image.Resampling.BOX)
            )
        cards = np.stack(np.split(patches, 2, axis=1))
        slots = decode(work / "inventory.png", load(work / "trained.npz"))
        with (work / "online.py").open("a") as out:
            out.write(f"\nSITE_CARDS = {cards.tolist()!r}\nSTOCK_IDS = {slots!r}\n")


def oracle(context: OracleContext) -> None:
    """Produce both submitted artifacts using only the candidate-facing inputs."""
    build(context)


if __name__ == "__main__":
    oracle(OracleContext(Path("/app/work"), Path(__file__).resolve().parent))
