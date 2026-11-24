#!/usr/bin/env python3
"""Package the ten-task robotics comparison outside the source checkout."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / "tasks" / "swe-m2-software-engineering"
SHORTLIST = (
    "policy-sim-bridge",
    "fixed-lag-fusion",
    "px4-estimator-recovery",
    "dual-arm-handoff",
    "lerobot-dataset-repair",
    "ros2-control-recovery",
    "fleet-recovery",
    "nav2-docking-recovery",
    "mujoco-branch-replay",
    "versioned-mapping",
)
TASK_DIRECTORY_OUTPUT = {
    "policy-sim-bridge", "px4-estimator-recovery", "fleet-recovery", "nav2-docking-recovery",
}
ATTEMPT_DEADLINE_SECONDS = 43_200
SUBMISSION_RESERVE_SECONDS = 1_200


def make_single_session(staged, destination):
    """Keep every brief and the final cumulative tests in a single Harbor session."""
    raw = (staged / "task.toml").read_text()
    config = tomllib.loads(raw)
    stages = [staged / "steps" / entry["name"] for entry in config["steps"]]
    if config["multi_step_reward_strategy"] != "final" or any(
        set(entry) != {"name"} for entry in config["steps"]
    ):
        raise ValueError(f"Review stage-level settings before adapting {staged.name}")
    for stage in stages:
        if {path.name for path in stage.iterdir()} != {"instruction.md", "tests", "solution"}:
            raise ValueError(f"Review the stage files before adapting {stage}")

    destination.mkdir()
    shutil.copytree(staged / "environment", destination / "environment")
    for directory in ("tests", "solution"):
        shutil.copytree(stages[-1] / directory, destination / directory)
    briefs = [stage.joinpath("instruction.md").read_bytes() for stage in stages]
    instruction = destination / "instruction.md"
    instruction.write_bytes(b"\n\n---\n\n".join(briefs))
    instruction.chmod(0o644)

    # Both images and the final verifier run inside the provider's attempt lease.
    original_seconds = int(config["agent"]["timeout_sec"]) * len(stages)
    setup_and_grade = sum(int(value) for value in (
        config["environment"]["build_timeout_sec"],
        config["verifier"]["environment"]["build_timeout_sec"],
        config["verifier"]["timeout_sec"],
    ))
    authoring_seconds = min(original_seconds, ATTEMPT_DEADLINE_SECONDS - setup_and_grade - SUBMISSION_RESERVE_SECONDS)
    if authoring_seconds <= 0:
        raise ValueError(f"No authoring time remains for {staged.name}")
    source_name = config["task"]["name"]
    comparison_name = f"{source_name}-top-ten"
    task = re.split(r"(?m)^\[\[steps\]\]\s*$", raw, maxsplit=1)[0]
    task = re.sub(r"(?m)^multi_step_reward_strategy\s*=.*\n", "", task)
    task = task.replace(f'name = "{source_name}"', f'name = "{comparison_name}"', 1)
    task = re.sub(
        r"(?m)(^\[agent\]\s*\n)timeout_sec\s*=.*$",
        rf"\g<1>timeout_sec = {authoring_seconds + SUBMISSION_RESERVE_SECONDS}", task, count=1,
    )
    task = task.replace(
        "[environment]\n", f"[agent.proximus]\ntime_budget_sec = {authoring_seconds}\n\n[environment]\n", 1,
    )

    dockerfile = destination / "environment" / "Dockerfile"
    docker = dockerfile.read_text()
    images = list(re.finditer(r"(?m)^FROM\s+[^\n]+\n", docker))
    if len(images) != 1:
        raise ValueError(f"Review tool installation stage for {dockerfile}")
    tools = (
        "RUN apt-get update && apt-get install -y --no-install-recommends bash git "
        "&& rm -rf /var/lib/apt/lists/*\n"
    )
    dockerfile.write_text(docker[:images[0].end()] + tools + docker[images[0].end():])
    if (
        config["environment"].get("network_mode") == "allowlist"
        and "deb.debian.org" not in config["environment"]["allowed_hosts"]
        and re.search(r"\b(?:python|debian):", images[0].group())
    ):
        updated_hosts = config["environment"]["allowed_hosts"] + ["deb.debian.org"]
        task = re.sub(r"(?m)^allowed_hosts\s*=.*$", "allowed_hosts = " + json.dumps(updated_hosts), task, count=1)
    parsed = tomllib.loads(task)
    if (
        "steps" in parsed or parsed["task"]["name"] != comparison_name
        or parsed["agent"]["timeout_sec"] != authoring_seconds + SUBMISSION_RESERVE_SECONDS
        or parsed["verifier"] != config["verifier"] or parsed["artifacts"] != config["artifacts"]
        or parsed["agent"].get("network_mode") != config["agent"].get("network_mode")
    ):
        raise ValueError(f"Invalid comparison config for {staged.name}")
    task_file = destination / "task.toml"
    task_file.write_text(task)
    task_file.chmod(0o644)
    inventory = hashlib.sha256()
    for file in sorted(destination.rglob("*")):
        if file.is_file():
            relative = file.relative_to(destination)
            inventory.update(f"{relative.as_posix()} {file.stat().st_mode:o} ".encode())
            inventory.update(hashlib.sha256(file.read_bytes()).digest())
    return {
        "task": comparison_name,
        "checkpoint_briefs": len(stages),
        "original_authoring_seconds": original_seconds,
        "proximus_authoring_seconds": authoring_seconds,
        "agent_timeout_seconds": parsed["agent"]["timeout_sec"],
        "verifier_timeout_seconds": parsed["verifier"]["timeout_sec"],
        "inventory_sha256": inventory.hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    dist = output / "dist"
    dist.mkdir()
    manifest = []
    with TemporaryDirectory(prefix="robotics-staged-bundles-") as temporary:
        for slug in SHORTLIST:
            name = f"swe-m2_software-engineering_{slug}"
            parent = Path(temporary) / slug
            parent.mkdir()
            bundle = parent / name
            package_output = bundle if slug in TASK_DIRECTORY_OUTPUT else parent
            subprocess.run(
                [sys.executable, "-B", str(FAMILY / slug / "scripts" / "package_task.py"),
                 "--output", str(package_output)], check=True,
            )
            manifest.append(make_single_session(bundle, dist / f"{name}-top-ten"))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
