"""Stage robotics research runtime artifacts into an explicit Harbor bundle."""

import argparse
from pathlib import Path
import shutil
import tempfile
import tomllib

TASK = Path(__file__).resolve().parents[1]
PACKAGE = "wrenchlab"


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
        work.rename(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(parser.parse_args().output))
