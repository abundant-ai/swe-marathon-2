"""Run the packaged verifier against cumulative oracle and no-op applications."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SLUG = "swe-m2_software-engineering_versioned-mapping"


def calibrate(bundle: Path, logs: Path) -> None:
    """Require a full reference score and a zero no-op score at every checkpoint."""
    script_environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    logs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mapping-oracle-") as temporary:
        workspace = Path(temporary)
        oracle, nop = workspace / "oracle", workspace / "nop"
        oracle.mkdir()
        nop.mkdir()
        config = tomllib.loads((bundle / "task.toml").read_text())
        stages = [bundle / "steps" / step["name"] for step in config["steps"]]
        if not stages or set(stages) != set((bundle / "steps").iterdir()):
            raise ValueError("Packaged checkpoints must match task.toml")
        for stage in stages:
            subprocess.run(["sh", stage / "solution/solve.sh", oracle], check=True)
            for label, app, target in (("oracle", oracle, 1.0), ("nop", nop, 0.0)):
                outfile = logs / stage.name / label
                start = time.monotonic()
                subprocess.run(
                    [sys.executable, stage / "tests/verify.py", "--app", app, "--logs", outfile],
                    env=script_environment, check=True,
                )
                report = json.loads((outfile / "checkpoint.json").read_text())
                print(f"{stage.name} {label} score={report['score']:.6f} seconds={time.monotonic() - start:.3f}")
                if report["score"] != target:
                    raise RuntimeError(f"Unexpected score in {outfile}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "experiment" / "dist" / SLUG)
    parser.add_argument("--logs", type=Path, default=ROOT / "experiment" / "calibration")
    arguments = parser.parse_args()
    calibrate(arguments.bundle, arguments.logs)
