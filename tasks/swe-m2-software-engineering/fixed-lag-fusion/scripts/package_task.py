"""Stage fixed-lag fusion runtime artifacts into an explicit Harbor bundle."""

import argparse
from pathlib import Path
import shutil
import tempfile
import tomllib

TASK = Path(__file__).resolve().parents[1]
MODULES = [
    ("__init__.py", "__main__.py", "contract.py", "gaussian.py"),
    ("calibration.py",),
    ("sensors.py",),
    ("session.py",),
    ("network.py",),
    ("integrity.py",),
    ("vision.py",),
    ("rewind.py",),
]


def copy(source: Path, target: Path) -> None:
    """Copy a named regular source file and its runtime permissions."""
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def package(output: Path) -> Path:
    """Produce a fresh bundle without including task-development files."""
    output.mkdir(parents=True, exist_ok=True)
    config = tomllib.loads((TASK / "task.toml").read_text(encoding="utf-8"))
    slug = config["task"]["name"].split("/")[-1]
    target = output / slug
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory(dir=output, prefix=".lagfusion-package-") as stage:
        work = Path(stage) / slug
        copy(TASK / "task.toml", work / "task.toml")
        for name in ("Dockerfile", ".dockerignore", "requirements.txt", "resources/README.md",
                     "resources/room1_xy.csv", "resources/native_track_example.py"):
            copy(TASK / "environment" / name, work / "environment" / name)
        modules = []
        for info, additions in zip(config["steps"], MODULES, strict=True):
            relative = Path("steps", info["name"])
            for name in ("instruction.md", "tests/Dockerfile", "tests/test.sh", "tests/verify.py", "solution/solve.sh"):
                copy(TASK / relative / name, work / relative / name)
            for name in ("reference.py", "probes.py", "checkpoint.py"):
                copy(TASK / "common" / "verifier" / name, work / relative / "tests" / name)
            copy(TASK / "environment" / "resources" / "room1_xy.csv", work / relative / "tests" / "room1_xy.csv")
            copy(TASK / "environment" / "requirements.txt", work / relative / "tests" / "requirements.txt")
            number = int(info["name"][:2])
            if number >= 5:
                copy(TASK / "common" / "verifier" / "network_probes.py", work / relative / "tests" / "network_probes.py")
            if number >= 6:
                copy(TASK / "common" / "verifier" / "integrity_probes.py", work / relative / "tests" / "integrity_probes.py")
            if number >= 7:
                copy(TASK / "common" / "verifier" / "vision_probes.py", work / relative / "tests" / "vision_probes.py")
            if number == 8:
                copy(TASK / relative / "tests/rewind_probes.py", work / relative / "tests/rewind_probes.py")
            modules.extend(additions)
            for name in modules:
                tail = Path("lagfusion", name)
                local = TASK / relative / "solution" / tail
                copy(local if local.is_file() else TASK / "common" / "oracle" / tail,
                     work / relative / "solution" / tail)
        work.rename(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(parser.parse_args().output))
