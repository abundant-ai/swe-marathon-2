#!/usr/bin/env python3
"""Assemble the explicitly declared Oddish runtime bundle."""

import argparse
import shutil
import tomllib
from pathlib import Path


SOURCE = Path(__file__).resolve().parent.parent
BUNDLE = "swe-m2_software-engineering_fleet-recovery"


def assemble(output: Path) -> None:
    def copy(source: Path, destination: Path):
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / source, target)

    task = tomllib.loads((SOURCE / "task.toml").read_text())
    for name in ("task.toml", "environment/Dockerfile", "environment/.dockerignore",
                 "environment/example/site.json",
                 "environment/example/PROVENANCE.md"):
        copy(Path(name), Path(name))
    native_debs=("traffic.deb", "utils.deb", "libccd2.deb", "SHA256SUMS", "SOURCES.md")
    example_names=("build_rmf_native.sh", "rmf_native.cpp", "README.md", "manifest.json", "observations.ndjson",
                   "competition-site.json", "competition-open.json", "contingent-site.json", "contingent-open.json")
    for name in native_debs:
        asset=Path("environment/native-rmf") / name
        copy(asset, asset)
    for name in example_names:
        asset=Path("environment/example/rmf") / name
        copy(asset, asset)
    contingent_step = "09-commit-contingent-traffic"
    competitive_steps = ("08-negotiate-competing-traffic", contingent_step)
    native_steps = ("07-reconcile-native-traffic", *competitive_steps)
    for entry in task["steps"]:
        step = Path("steps") / entry["name"]
        for name in ("instruction.md", "tests/Dockerfile", "tests/test.sh",
                     "tests/verify.py", "solution/solve.sh"):
            copy(step / name, step / name)
        for prefix, files in (
            ("common/oracle", ("__init__.py", "__main__.py")),
            ("common/verifier", ("fleet_grader.py", "fleet_world.py", "scenarios.py")),
        ):
            folder = "solution/fleet_recovery" if prefix.endswith("oracle") else "tests"
            for filename in files:
                copy(Path(prefix) / filename, step / folder / filename)
        if entry["name"] in ("04-schedule-elevators", "05-reserve-lift-corridors", "06-route-energy-constrained-fleet", *native_steps):
            copy(Path("common/oracle/elevators.py"), step / "solution/fleet_recovery/elevators.py")
            copy(Path("common/verifier/elevator_checks.py"), step / "tests/elevator_checks.py")
        if entry["name"] in ("05-reserve-lift-corridors", "06-route-energy-constrained-fleet", *native_steps):
            copy(Path("common/oracle/corridors.py"), step / "solution/fleet_recovery/corridors.py")
            copy(Path("common/verifier/corridor_checks.py"), step / "tests/corridor_checks.py")
        if entry["name"] in ("06-route-energy-constrained-fleet", *native_steps):
            copy(Path("common/oracle/network.py"), step / "solution/fleet_recovery/network.py")
            copy(Path("common/verifier/network_checks.py"), step / "tests/network_checks.py")
        if entry["name"] in native_steps:
            copy(Path("common/oracle/rmf_handover.py"), step / "solution/fleet_recovery/rmf_handover.py")
            copy(Path("common/verifier/rmf_checks.py"), step / "tests/rmf_checks.py")
            copy(Path("steps/07-reconcile-native-traffic/tests/traffic_smoke.cpp"),
                 step / "tests/traffic_smoke.cpp")
            for name in native_debs:
                copy(Path("environment/native-rmf") / name, step / "tests/native-rmf" / name)
            for name in ("rmf_native.cpp", "build_rmf_native.sh"):
                copy(Path("environment/example/rmf") / name, step / "tests" / name)
        if entry["name"] in competitive_steps:
            for name in ("competition.py", "competition_native.cpp"):
                copy(Path("common/oracle") / name, step / "solution/fleet_recovery" / name)
            copy(Path("common/verifier/competition_checks.py"), step / "tests/competition_checks.py")
        if entry["name"] == contingent_step:
            for name in ("contingent.py", "contingent_native.cpp"):
                copy(Path("common/oracle") / name, step / "solution/fleet_recovery" / name)
            copy(Path("common/verifier/contingent_checks.py"), step / "tests/contingent_checks.py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=SOURCE / "experiment" / "dist" / BUNDLE)
    args = parser.parse_args()
    assemble(args.output.resolve())
    print(args.output.resolve())


if __name__ == "__main__":
    main()
