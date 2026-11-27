"""Train the source CNN and install an a streaming affine normalization update."""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OracleContext:
    work: Path
    solution: Path


def oracle(context: OracleContext) -> None:
    shutil.copyfile(context.solution / "online.py", context.work / "online.py")
    subprocess.run([sys.executable, "train.py"], cwd=context.work, check=True)


if __name__ == "__main__":
    oracle(OracleContext(Path("/app/work"), Path(__file__).resolve().parent))
