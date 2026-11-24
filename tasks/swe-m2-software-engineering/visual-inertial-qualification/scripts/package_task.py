"""Stage robotics research runtime artifacts into an explicit Harbor bundle."""

import argparse
from pathlib import Path
import shutil
import tempfile
import tomllib

TASK = Path(__file__).resolve().parents[1]
PACKAGE = "visqual"


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
        for path in (TASK / "environment").rglob("*"):
            if path.is_file():
                copy(path, work / path.relative_to(TASK))
        for step in config["steps"]:
            relative = Path("steps", step["name"])
            for name in ("instruction.md", "tests/Dockerfile", "tests/test.sh", "tests/verify.py", "solution/solve.sh"):
                copy(TASK / relative / name, work / relative / name)
            for path in (TASK / "common" / "verifier").glob("*.py"):
                copy(path, work / relative / "tests" / path.name)
            for path in (TASK / "environment" / "resources").iterdir():
                copy(path, work / relative / "tests" / "fixture" / path.name)
            copy(TASK / "environment" / "requirements.txt", work / relative / "tests" / "requirements.txt")
            for path in (TASK / "common" / "oracle" / PACKAGE).glob("*.py"):
                copy(path, work / relative / "solution" / PACKAGE / path.name)
            if step["name"] == "04-calibrate-row-timing":
                copy(TASK / relative / "tests/rolling_probes.py", work / relative / "tests/rolling_probes.py")
                for name in ("__main__.py", "rolling.py"):
                    tail = Path("solution", PACKAGE, name)
                    copy(TASK / relative / tail, work / relative / tail)
            if step["name"] == "05-calibrate-inertial-motion":
                prior = Path("steps/04-calibrate-row-timing")
                copy(TASK / prior / "tests/rolling_probes.py", work / relative / "tests/rolling_probes.py")
                copy(TASK / prior / "tests/verify.py", work / relative / "tests/verify_rolling.py")
                copy(TASK / relative / "tests/inertial_probes.py", work / relative / "tests/inertial_probes.py")
                tail = Path("solution", PACKAGE, "rolling.py")
                copy(TASK / prior / tail, work / relative / tail)
                for name in ("__main__.py", "inertial.py"):
                    tail = Path("solution", PACKAGE, name)
                    copy(TASK / relative / tail, work / relative / tail)
        work.rename(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(parser.parse_args().output))
