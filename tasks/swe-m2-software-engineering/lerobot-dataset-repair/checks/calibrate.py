"""Validate the packed LeRobot verifier against the reference and no-op."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SLUG = "swe-m2_software-engineering_lerobot-dataset-repair"


def calibrate(bundle: Path, logs: Path) -> None:
    """Run the cumulative reference and absent-submission control with fixed expected scores."""
    with tempfile.TemporaryDirectory(prefix="lerobot-calibration-") as temporary:
        path = Path(temporary)
        reference, nop = path / "reference", path / "nop"
        reference.mkdir()
        nop.mkdir()
        checkpoints = sorted((bundle / "steps").iterdir())
        if len(checkpoints) != 4:
            raise ValueError("Expected four packaged checkpoints")
        for step in checkpoints:
            subprocess.run(["sh", step / "solution/solve.sh", reference], check=True)
            for name, app, target in (("reference", reference, 1.0), ("nop", nop, 0.0)):
                result = logs / step.name / name
                started = time.monotonic()
                subprocess.run([sys.executable, "-B", step / "tests/verify.py", "--app", app, "--logs", result],
                               check=True)
                score = json.loads((result / "checkpoint.json").read_text())["score"]
                print(f"{step.name} {name} {score:.6f} ({time.monotonic() - started:.2f} s)")
                if score != target:
                    raise RuntimeError(f"Unexpected score at {result}")


def shortcut(bundle: Path, logs: Path) -> float:
    """Calibrate a control that ignores joint episode assignment while retaining correct clocks."""
    with tempfile.TemporaryDirectory(prefix="lerobot-local-only-") as temporary:
        workspace = Path(temporary)
        step = sorted((bundle / "steps").iterdir())[-1]
        subprocess.run(["sh", step / "solution/solve.sh", workspace], check=True)
        clock = workspace / "lerobot_repair/clocked.py"
        code = clock.read_text()
        original = "if maximum(cases, forbidden=(episode, option)) < count:"
        if code.count(original) != 1:
            raise ValueError("The local-only control no longer matches the timing solver")
        clock.write_text(code.replace(original, "if len(choices) == 1:"))
        subprocess.run([sys.executable, "-B", step / "tests/verify.py", "--app", workspace, "--logs", logs],
                       check=True)
        report = json.loads((logs / "checkpoint.json").read_text())
        if not 0.25 <= report["score"] < 0.5 or any(report["fractions"][key] != 1.0
                                                   for key in ("audit", "plan", "publish", "publish_shifted")):
            raise RuntimeError("The shortcut control did not discriminate global recovery")
        return report["score"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "experiment/dist" / SLUG)
    parser.add_argument("--logs", type=Path, default=ROOT / "experiment/calibration")
    parser.add_argument("--shortcut-only", action="store_true")
    args = parser.parse_args()
    if args.shortcut_only:
        print(f"Local-only association control {shortcut(args.bundle, args.logs / 'local-only'):.6f}")
    else:
        calibrate(args.bundle, args.logs)
