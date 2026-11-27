"""Build and audit a scanner renewal matrix from the original CORe50 archive."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def build(archive: Path, output: Path) -> None:
    """Retrain both reference starts, prepare the captures and construct all three conditions."""
    here = Path(__file__).resolve().parent
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        parent = Path(temp) / "stock"
        for command in (
            [here.parent / "inventory/build.py", archive.resolve(), parent],
            [here / "stage.py", parent, output],
            [here / "check.py", output],
        ):
            subprocess.run([sys.executable, "-B", *map(str, command)], check=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("destination", type=Path)
    args = p.parse_args()
    build(args.archive, args.destination)
