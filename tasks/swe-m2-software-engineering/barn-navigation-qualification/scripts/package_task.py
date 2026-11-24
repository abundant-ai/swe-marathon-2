#!/usr/bin/env python3
"""Copy the explicit task build, verifier and solution contexts."""

import argparse
from pathlib import Path
import shutil
import tomllib

SOURCE = Path(__file__).resolve().parent.parent
BUNDLE = "swe-m2_software-engineering_barn-navigation-qualification"
APPLICATION = "barn_qualification"


def assemble(target: Path) -> None:
    """Materialize a runnable task outside the maintained source folders."""
    task = tomllib.loads((SOURCE / "task.toml").read_text())
    def copy(source: str, destination: str | None = None) -> None:
        """Copy one declared runtime file and keep its executable mode."""
        output = target / (destination or source)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / source, output)
    for filename in ("task.toml", "environment/.dockerignore", "environment/Dockerfile", "environment/example/barn-world-0-crop.json", "environment/example/NOTICE.txt"):
        copy(filename)
    for entry in task["steps"]:
        step = f"steps/{entry['name']}"
        for filename in ("instruction.md", "tests/Dockerfile", "tests/verify.py", "tests/test.sh", "solution/solve.sh"):
            copy(f"{step}/{filename}")
        for file in sorted((SOURCE / "common" / "oracle").glob("*.py")):
            copy(f"common/oracle/{file.name}", f"{step}/solution/{APPLICATION}/{file.name}")
        for file in sorted((SOURCE / "common" / "verifier").glob("*.py")):
            copy(f"common/verifier/{file.name}", f"{step}/tests/{file.name}")


def main() -> None:
    """Build the package at its default or explicit output path."""
    args = argparse.ArgumentParser()
    args.add_argument("--output", type=Path, default=SOURCE / "experiment" / "dist" / BUNDLE)
    output = args.parse_args().output.resolve()
    assemble(output)
    print(output)


if __name__ == "__main__":
    main()
