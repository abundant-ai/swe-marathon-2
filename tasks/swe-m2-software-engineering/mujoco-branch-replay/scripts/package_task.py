"""Select the runtime files needed to build a simbranch task bundle."""

import argparse
from pathlib import Path
import shutil
import tempfile
import tomllib

TASK = Path(__file__).resolve().parents[1]
ORACLE = [
    ("__init__.py", "__main__.py", "core.py"),
    (),
    (),
    ("rebase.py",),
    ("rechart.py",),
]


def copy(source: Path, target: Path) -> None:
    """Copy one absolute authoring path into its chosen bundle target."""
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def package(parent: Path) -> Path:
    """Publish a clean runtime-only bundle under the task's submitting slug."""
    config = tomllib.loads((TASK / "task.toml").read_text(encoding="utf-8"))
    name = config["task"]["name"].split("/", 1)[1]
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / name
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory(prefix=".bundle-", dir=parent) as temporary:
        staged = Path(temporary) / name
        copy(TASK / "task.toml", staged / "task.toml")
        for name in ("Dockerfile", ".dockerignore", "resources/README.md"):
            copy(TASK / "environment" / name, staged / "environment" / name)
        requirements = TASK / "environment" / "requirements.txt"
        copy(requirements, staged / "environment" / requirements.name)
        runtime = []
        for step, modules in zip(config["steps"], ORACLE, strict=True):
            prefix = Path("steps", step["name"])
            for name in ("instruction.md", "tests/Dockerfile", "tests/test.sh", "tests/verify.py", "solution/solve.sh"):
                copy(TASK / prefix / name, staged / prefix / name)
            verifier_files = ("checkpoint.py", "probes.py")
            if step["name"] in ("04-rebase-checkpoint", "05-rechart-contact-fork"):
                verifier_files += ("rebase_checks.py",)
            if step["name"] == "05-rechart-contact-fork":
                verifier_files += ("chart_checks.py",)
            copy(requirements, staged / prefix / "tests" / requirements.name)
            for name in verifier_files:
                copy(TASK / "common" / "verifier" / name, staged / prefix / "tests" / name)
            runtime.extend(modules)
            for name in runtime:
                path = Path("simbranch", name)
                copy(TASK / "common" / "oracle" / path, staged / prefix / "solution" / path)
        staged.rename(target)
    return target


def main() -> None:
    """Build the configured bundle with optional caller-selected parent directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(parser.parse_args().output))


if __name__ == "__main__":
    main()
