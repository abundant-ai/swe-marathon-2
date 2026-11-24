#!/usr/bin/env python3
"""Assemble only the required hosted runtime files."""

import argparse
from pathlib import Path
import shutil
import tomllib

SOURCE = Path(__file__).resolve().parent.parent
BUNDLE = "swe-m2_software-engineering_nav2-docking-recovery"


def assemble(output: Path) -> None:
    """Build a Harbor bundle and preserve executable wrapper modes."""
    task = tomllib.loads((SOURCE / "task.toml").read_text())
    pairs = [(name, name) for name in (
        "task.toml", "environment/.dockerignore", "environment/Dockerfile",
        "environment/example/config.json", "environment/example/native_dock.py",
        "environment/install_jazzy.sh",
    )]
    for entry in task["steps"]:
        step = f"steps/{entry['name']}"
        for name in ("instruction.md", "tests/Dockerfile", "tests/test.sh",
                     "tests/verify.py", "solution/solve.sh"):
            pairs.append((f"{step}/{name}", f"{step}/{name}"))
        for filename in ("__init__.py", "__main__.py", "geometry.py", "controller.py", "staging.py"):
            pairs.append((f"common/oracle/{filename}", f"{step}/solution/dock_recovery/{filename}"))
        common = ("cases.py", "plant.py", "grade_docking.py")
        if step.endswith(("stage-and-reacquire", "compile-curvature-routes", "confirm-native-seating")):
            common += ("staging_cases.py", "staging_plant.py")
        if step.endswith(("compile-curvature-routes", "confirm-native-seating")):
            pairs.append(("common/oracle/compiler.py", f"{step}/solution/dock_recovery/compiler.py"))
            common += ("compile_checks.py",)
        if step.endswith("confirm-native-seating"):
            pairs.append(("common/oracle/native.py", f"{step}/solution/dock_recovery/native.py"))
            pairs.append(("environment/install_jazzy.sh", f"{step}/tests/install_jazzy.sh"))
            common += ("native_cases.py",)
        for filename in common:
            pairs.append((f"common/verifier/{filename}", f"{step}/tests/{filename}"))
    for source, relative in pairs:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / source, target)


def main() -> None:
    """Assemble the default or supplied destination and print its path."""
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, default=SOURCE / "experiment" / "dist" / BUNDLE)
    args = cli.parse_args()
    target = args.output.resolve()
    assemble(target)
    print(target)


if __name__ == "__main__":
    main()
