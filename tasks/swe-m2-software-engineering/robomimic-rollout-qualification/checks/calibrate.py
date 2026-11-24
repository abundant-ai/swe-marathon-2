"""Run all packaged candidate and no-op reference checkpoints."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SLUG = "swe-m2_software-engineering_robomimic-rollout-qualification"


def calibrate(bundle: Path, logs: Path) -> None:
    """Exercise the packed verifier at every cumulative milestone."""
    with TemporaryDirectory(prefix="rollout-local-") as location:
        root = Path(location)
        reference, nop = root / "reference", root / "nop"
        reference.mkdir()
        nop.mkdir()
        for step in sorted((bundle / "steps").iterdir()):
            subprocess.run(["sh", step / "solution/solve.sh", reference], check=True)
            for name, app, target in (("reference", reference, 1.0), ("nop", nop, 0.0)):
                saved = logs / step.name / name
                started = time.monotonic()
                subprocess.run([sys.executable, "-B", step / "tests/verify.py", "--app", app, "--logs", saved], check=True)
                result = json.loads((saved / "checkpoint.json").read_text())
                print(f"{step.name} {name} {result['score']:.6f} ({time.monotonic() - started:.2f} seconds)")
                assert result["score"] == target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "experiment/dist" / SLUG)
    parser.add_argument("--logs", type=Path, default=ROOT / "experiment/calibration")
    args = parser.parse_args()
    calibrate(args.bundle, args.logs)
