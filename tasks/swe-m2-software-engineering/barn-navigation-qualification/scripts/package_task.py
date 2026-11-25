"""Stage the BARN navigation qualification into an explicit Harbor bundle.

Each step receives only the reference modules and verifier modules that its
checkpoint needs; later steps accumulate the earlier steps' files.
"""

import argparse
from pathlib import Path
import shutil
import tempfile
import tomllib

TASK = Path(__file__).resolve().parents[1]
PACKAGE = "barn_qualification"
ENVIRONMENT = ("Dockerfile", ".dockerignore", "example/NOTICE.txt", "example/barn-world-0-crop.json",
               "example/field-world-0.json", "example/movers-world-0.json")
ORACLE = [
    ("__init__.py", "__main__.py", "grid.py"),
    (),
    (),
    ("arena.py", "routing.py", "sensing.py", "motion.py", "pilot.py"),
    ("movers.py",),
]
VERIFIER = [
    ("grader.py", "probes.py", "transport.py", "layouts.py", "world_reference.py"),
    (),
    (),
    ("field.py", "courses.py"),
    (),
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
    with tempfile.TemporaryDirectory(dir=output, prefix=".barn-package-") as stage:
        work = Path(stage) / slug
        copy(TASK / "task.toml", work / "task.toml")
        for name in ENVIRONMENT:
            copy(TASK / "environment" / name, work / "environment" / name)
        oracle: list[str] = []
        verifier: list[str] = []
        for info, modules, checks in zip(config["steps"], ORACLE, VERIFIER, strict=True):
            relative = Path("steps", info["name"])
            for name in ("instruction.md", "tests/Dockerfile", "tests/test.sh", "tests/verify.py", "solution/solve.sh"):
                copy(TASK / relative / name, work / relative / name)
            oracle += modules
            verifier += checks
            for name in oracle:
                copy(TASK / "common" / "oracle" / name, work / relative / "solution" / PACKAGE / name)
            for name in verifier:
                copy(TASK / "common" / "verifier" / name, work / relative / "tests" / name)
        work.rename(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(parser.parse_args().output))
