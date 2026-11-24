"""Run the exact final package against reference and meaningful deficient controls."""

from argparse import ArgumentParser
import json
from pathlib import Path
from shutil import copytree
import subprocess
import sys
import tempfile


LEGACY = "04-schedule-handover"
FINAL = "05-run-protected-servo"


def grade(bundle: Path, artifact: Path, logs: Path, stage: int = 5) -> float:
    """Return the reward published by the chosen packed checkpoint."""
    step = bundle / "steps" / (FINAL if stage == 5 else LEGACY)
    subprocess.run([sys.executable, "-BI", step / "tests/verify.py", "--stage", str(stage),
                    "--artifact", artifact, "--logs", logs], check=True, timeout=75)
    return json.loads((logs / "checkpoint.json").read_text())["reward"]


def calibrate(bundle: Path, logs: Path) -> None:
    """Check correct behavior and ablations of feedback and confirmed authority."""
    predecessor = bundle / "steps" / LEGACY / "solution/control_recovery"
    reference = bundle / "steps" / FINAL / "solution/control_recovery"
    values = {"reference": grade(bundle, reference, logs / "reference"),
              "nop": grade(bundle, Path("/nonexistent-submission"), logs / "nop"),
              "legacy": grade(bundle, predecessor, logs / "legacy")}
    defects = {
        "open_loop": ("tracker.effort(cycle, owner)", "tracker.effort(open_loop(cycle), owner)",
                      """
def open_loop(cycle):
    q, qd, _ = cycle.target
    return replace(cycle, measured=(cycle.now, q, qd))
"""),
        "no_load_observer": ("tracker.observe(cycle)", "pass", ""),
        "premature_transfer": ("owner = authority.owner()", """
        owner = authority.owner()
        if cycle.pending and cycle.pending["kind"] == "transfer":
            owner = cycle.pending["device"]
        """.strip(), ""),
    }
    with tempfile.TemporaryDirectory(prefix="servo-controls-") as temporary:
        for name, (before, after, extra) in defects.items():
            artifact = Path(temporary) / name / "control_recovery"
            copytree(reference, artifact)
            path = artifact / "servo.py"
            source = path.read_text()
            assert source.count(before) == 1
            if name == "open_loop":
                source = source.replace("        tracker.observe(cycle)\n", "")
            path.write_text(source.replace(before, after) + extra)
            values[name] = grade(bundle, artifact, logs / name)
    print(json.dumps(values, sort_keys=True, indent=2))
    (logs / "summary.json").write_text(json.dumps(values, sort_keys=True, indent=2) + "\n")
    assert values["reference"] == 1.0 and values["nop"] == 0 and values["legacy"] == 0.2
    assert values["premature_transfer"] < 0.5 and values["open_loop"] < 0.5
    assert 0.2 <= values["no_load_observer"] < 1.0


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("logs", type=Path)
    settings = parser.parse_args()
    calibrate(settings.bundle, settings.logs)
