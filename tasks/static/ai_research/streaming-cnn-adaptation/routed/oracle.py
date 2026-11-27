"""Commission both modes from a paired preview and public RGB recordings."""

import subprocess
import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import torch
from PIL import Image


def commission(work, solution, *, train=True):
    sys.path.insert(0, str(work))
    from core_model import tensor
    from commission import fit_gate, fit_profiles
    from fit import estimate

    torch.set_num_threads(1)
    code = (solution / "online.py").read_text()
    if (work / "preview.png").exists():
        inverses = []
        with (
            Image.open(work / "preview.png") as sheet,
            tempfile.TemporaryDirectory() as temp,
        ):
            w, h = sheet.size
            for i in (0, 1):
                path = Path(temp) / "pair.png"
                sheet.crop((i * w // 2, 0, (i + 1) * w // 2, h)).save(path)
                inverses.append(estimate(path).tolist())
        with np.load(work / "source.npz") as data:
            source = tensor(data["x"][1::3])
        gates = [fit_gate(source, np.asarray(inverse)) for inverse in inverses]
        modes = fit_profiles(source, inverses)
        code += f"\nINVERSES = {inverses!r}\nGATES = {gates!r}\nMODE = {modes!r}\n"
    (work / "online.py").write_text(code)
    if train:
        subprocess.run([sys.executable, "train.py"], cwd=work, check=True)


@dataclass(frozen=True)
class OracleContext:
    work: Path
    solution: Path


def oracle(context: OracleContext) -> None:
    commission(context.work, context.solution)
    for schedule in ("clips", "switches"):
        subprocess.run(
            [sys.executable, "practice.py", "--schedule", schedule],
            cwd=context.work,
            check=True,
        )


if __name__ == "__main__":
    oracle(OracleContext(Path("/app/work"), Path(__file__).resolve().parent))
