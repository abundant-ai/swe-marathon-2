"""Read the public paired color chart, compile its fit into the updater and train the source CNN."""

import subprocess
import sys
from pathlib import Path

from fit import estimate, profiles


def commission(solution, work):
    source = (solution / "online.py").read_text()
    preview = work / "preview.png"
    if preview.exists():
        inverse = estimate(preview).tolist()
        profile = profiles(preview)
        source += f"\nINVERSE = {inverse!r}\nPROFILES = {profile!r}\n"
    (work / "online.py").write_text(source)
    subprocess.run([sys.executable, "train.py"], cwd=work, check=True)


if __name__ == "__main__":
    commission(Path(__file__).resolve().parent, Path("/app/work"))
