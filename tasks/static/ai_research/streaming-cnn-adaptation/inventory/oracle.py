"""Train the source network, decode the stock photographs, and exercise both stream schedules."""

import subprocess
import sys
from pathlib import Path

from camera_oracle import OracleContext, commission


def oracle(context: OracleContext) -> None:
    work, solution = context.work, context.solution
    commission(work, solution)
    from core_model import load
    from gallery import decode

    options = []
    if (work / "inventory.png").exists():
        stock = decode(work / "inventory.png", load(work / "trained.npz"))
        with (work / "online.py").open("a") as out:
            out.write(f"\nSTOCK_IDS = {stock!r}\n")
        for name, ids in zip(("a", "b"), stock, strict=True):
            options.extend([f"--slots-{name}", ",".join(map(str, ids))])
    for schedule in ("clips", "switches"):
        subprocess.run(
            [sys.executable, "practice.py", "--schedule", schedule, *options],
            cwd=work,
            check=True,
        )


if __name__ == "__main__":
    oracle(OracleContext(Path("/app/work"), Path(__file__).resolve().parent))
