#!/usr/bin/env python3
"""Build the explicit policy bridge runtime bundle."""

import argparse
from pathlib import Path
import shutil
import tomllib

SOURCE = Path(__file__).resolve().parent.parent
BUNDLE = "swe-m2_software-engineering_policy-sim-bridge"


def assemble(output: Path) -> None:
    """Select only files used by an agent environment, verifier or solution."""
    task = tomllib.loads((SOURCE / "task.toml").read_text())
    files = [(name, name) for name in ("task.toml", "environment/.dockerignore",
                                      "environment/Dockerfile", "environment/example/manifest.json",
                                      "environment/example/sample.json")]
    public_assets = ("policy.onnx", "go2-headless.xml", "manifest.json", "starter.ndjson",
                     "README.md", "upstream-LICENSE", "menagerie-LICENSE", "course_example.py")
    for name in public_assets:
        asset = f"environment/example/locomotion/{name}"
        files.append((asset, asset))
    for entry in task["steps"]:
        step = f"steps/{entry['name']}"
        number = int(entry["name"][:2])
        for name in ("instruction.md", "tests/Dockerfile", "tests/requirements.txt", "tests/test.sh",
                     "tests/verify.py", "solution/solve.sh"):
            files.append((f"{step}/{name}", f"{step}/{name}"))
        references = ["__init__.py", "__main__.py", "model.py", "session.py", "calibration.py"]
        if number >= 6:
            references.append("drive.py")
        if number >= 7:
            references.append("locomotion.py")
        if number >= 8:
            references.extend(("course_nav.py", "course_planner.py"))
        if number == 9:
            references.append("scan_nav.py")
        for name in references:
            target = f"{step}/solution/policy_bridge/{name}"
            source = target if (SOURCE / target).is_file() else f"common/oracle/{name}"
            files.append((source, target))
        helpers = ["grade_bridge.py", "probes.py", "fixtures.py", "transport.py"]
        if number >= 4:
            helpers.append("native.py")
        if number >= 5:
            helpers.append("commission.py")
        if number >= 6:
            helpers.append("dynamics.py")
        if number >= 7:
            helpers.append("locomotion_native.py")
            for name in ("policy.onnx", "go2-headless.xml", "manifest.json", "upstream-LICENSE", "menagerie-LICENSE"):
                files.append((f"environment/example/locomotion/{name}",
                              f"{step}/tests/locomotion-assets/{name}"))
        if number >= 8:
            helpers.append("course_checks.py")
        for name in helpers:
            files.append((f"common/verifier/{name}", f"{step}/tests/{name}"))
        if number == 9:
            fixture = f"{step}/tests/scan_checks.py"
            files.append((fixture, fixture))
    for source, destination in files:
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / source, target)


def main() -> None:
    """Assemble the task into the selected local output directory."""
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, default=SOURCE / "experiment" / "dist" / BUNDLE)
    target = cli.parse_args().output.resolve()
    assemble(target)
    print(target)


if __name__ == "__main__":
    main()
