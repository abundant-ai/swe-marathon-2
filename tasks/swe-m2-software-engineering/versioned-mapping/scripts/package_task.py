"""Build the Oddish upload bundle from the authored checkpoint sources."""

import argparse
from pathlib import Path
import shutil
import tomllib


ROOT = Path(__file__).resolve().parents[1]
STEP_FILES = ("instruction.md", "tests/Dockerfile", "tests/test.sh", "tests/verify.py", "solution/solve.sh")
SOLUTION_STAGES = (("maps.py", "__init__.py", "__main__.py"), ("registration.py",), ("evidence.py",), ("releases.py",), ("canary.py",))


def package(output: Path) -> Path:
    """Copy named authoring assets, exposing only the current oracle capabilities."""
    configuration = tomllib.loads((ROOT / "task.toml").read_text())
    slug = configuration["task"]["name"].split("/")[1]
    target = (output if output.name == slug else output / slug).resolve()
    if target == ROOT or ROOT.is_relative_to(target):
        raise ValueError("Bundle may not overlap its source directory")

    paths = {name: ROOT / name for name in ("task.toml", "environment/Dockerfile", "environment/.dockerignore")}
    for index, step in enumerate(configuration["steps"]):
        base = Path("steps") / step["name"]
        for filename in STEP_FILES:
            relative = base / filename
            paths[relative] = ROOT / relative
        for source in sorted((ROOT / "common" / "verifier").glob("*.py")):
            if source.name != "canary_checks.py" or index == 4:
                paths[base / "tests" / source.name] = source
        for stage in SOLUTION_STAGES[:index + 1]:
            for filename in stage:
                paths[base / "solution" / "versioned_mapping" / filename] = ROOT / "common" / "oracle" / filename

    expected = {target / path for path in paths}
    directories = {parent for item in expected for parent in item.parents}
    for existing in target.rglob("*"):
        if existing.is_symlink() or existing not in (directories if existing.is_dir() else expected):
            raise ValueError(f"Unexpected bundle content {existing}")
    for path, source in paths.items():
        destination = target / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "experiment" / "dist")
    print(package(parser.parse_args().output))
