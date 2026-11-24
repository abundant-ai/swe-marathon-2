"""Run each independent case with its own state and record observable results."""

import argparse
import json
import shutil
import os
import subprocess
import tempfile
from pathlib import Path

from fleet_world import PhysicalConflict, Rejected
from scenarios import CHECKS, exercise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, required=True, choices=range(1, 10))
    parser.add_argument("--artifact", type=Path, default=Path("/app/fleet_recovery"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.chmod(0o700)
    (args.output / "reward.json").unlink(missing_ok=True)
    report = {}
    elevators = {}
    corridors = {}
    network = {}
    native_traffic = {}
    competition = {}
    contingent = {}
    backend_witness = None
    physical_conflict = False
    with tempfile.TemporaryDirectory(prefix="fleet-verifier-") as directory:
        root = Path(directory)
        root.chmod(0o755)
        app = root / "app"
        app.mkdir()
        source = args.artifact
        if source.is_dir() and not source.is_symlink():
            # Dereferencing a candidate artifact could expose verifier files.
            target = app / "fleet_recovery"
            target.mkdir()
            for item in source.rglob("*"):
                if item.is_symlink() or not item.is_file():
                    continue
                relative = item.relative_to(source)
                if any(parent.is_symlink() for parent in item.parents if parent != source.parent):
                    continue
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(item, destination)
                if item.stat().st_mode & 0o111:
                    destination.chmod(0o755)
        for name, first_stage, scenario, options in CHECKS:
            if first_stage <= args.stage:
                try:
                    observation = exercise(app, root / name, scenario, **options)
                except PhysicalConflict as error:
                    physical_conflict = True
                    report[name] = {"passed": False, "observation": str(error)}
                except Rejected as error:
                    report[name] = {"passed": False, "observation": str(error)}
                else:
                    report[name] = {"passed": True, "observation": observation}
        if args.stage >= 4:
            from elevator_checks import elevator_suite

            elevators = elevator_suite(app, root)
        if args.stage >= 5:
            from corridor_checks import corridor_suite

            corridors = corridor_suite(app, root)
        if args.stage >= 6:
            from network_checks import network_suite

            network = network_suite(app, root)
        if args.stage >= 7:
            from rmf_checks import native_suite

            smoke = os.environ.get("FLEET_RMF_PROOF", "/usr/local/bin/rmf-schedule-proof")
            backend_witness = subprocess.run([smoke],text=True,capture_output=True,check=True,timeout=8).stdout.splitlines()
            native_traffic = native_suite(app, root)
            physical_conflict |= any(value.get("physical_conflict") for value in native_traffic.values())
        if args.stage >= 8:
            from competition_checks import competition_suite

            competition = competition_suite(app, root)
            physical_conflict |= any(value.get("physical_conflict") for value in competition.values())
        if args.stage >= 9:
            from contingent_checks import contingent_suite

            contingent = contingent_suite(app, root)
            physical_conflict |= any(value.get("physical_conflict") for value in contingent.values())
    fraction = sum(case["passed"] for case in report.values()) / len(report)
    reward = fraction
    if args.stage >= 4:
        scheduled = sum(elevators.values()) / len(elevators) if elevators.get("joint_optimum_and_restart") else 0.0
        reward = 0.3 * fraction + 0.7 * scheduled
    if args.stage >= 5:
        active = corridors.get("route_swap_avoids_approach_conflict") or corridors.get("clearance_consensus_after_restart")
        current = sum(corridors.values()) / len(corridors) if active else 0.0
        reward = 0.2 * reward + 0.8 * current
    if args.stage >= 6:
        joint = network.get("shared_passage_detour") or network.get("charging_and_assignment")
        reward = 0.2 * reward + (0.8 * (sum(network.values()) / len(network)) if joint else 0.0)
    if native_traffic:
        completed = sum(value["passed"] for value in native_traffic.values())
        reward = .20 * reward + .80 * (completed / len(native_traffic))
    if competition:
        completed = sum(value["passed"] for value in competition.values())
        reward = .20 * reward + .80 * (completed / len(competition))
    if contingent:
        completed = sum(value["passed"] for value in contingent.values())
        reward = .20 * reward + .80 * (completed / len(contingent))
    if physical_conflict:
        reward = 0.0
    (args.output / "checkpoint.json").write_text(json.dumps(
        {"stage": args.stage, "reward": reward, "physical_conflict": physical_conflict,
         "checks": {name: case["passed"] for name, case in report.items()},
         "elevators": elevators,
         "corridors": corridors,
         "network": network,
         "rmf_traffic": native_traffic,
         "competition": competition,
         "contingent": contingent,
         "native_backend_witness": backend_witness,
         "observations": {name: case["observation"] for name, case in report.items()}},
        indent=2, sort_keys=True) + "\n")
    (args.output / "reward.json").write_text(json.dumps({"reward": reward}) + "\n")


if __name__ == "__main__":
    main()
