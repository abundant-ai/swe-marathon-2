"""Stage the Battle Royale task for Oddish baselines and model evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
from tempfile import TemporaryDirectory

from package_inputs import BUNDLE_NAME, LINK_TARGET, STEP_NAME, TASK_ROOT, candidate_inputs


WORKDIR = "/workspace"
SUBMISSION = f"{WORKDIR}/submission"
GENERATED_NAMES = frozenset({
    ".git", ".pytest_cache", ".venv", "__pycache__", "experiment",
    "Binaries", "DerivedDataCache", "Intermediate", "Packaged", "Saved",
})
MANIFEST = "BUNDLE_MANIFEST.json"

AGENT_SETUP = '''
[[agent.setup_begin]]
user = "root"
timeout_sec = 300
command = """
set -eu
engine=/opt/unreal
owner="agent:$(id -gn agent)"
install -d -m 0755 "$engine/Epic/UnrealEngine/Intermediate/Build" "$engine/Epic/UnrealBuildTool"
chown "$owner" "$engine/Engine"
for cache in Epic Engine/Intermediate Engine/Programs/UnrealBuildTool Engine/Saved Engine/DerivedDataCache; do
    install -d -m 0755 "$engine/$cache"
    chown -R "$owner" "$engine/$cache"
done
"""

[[agent.setup_complete]]
user = "agent"
command = """
set -eu
test -w /workspace
engine=/opt/unreal
test -x "$engine/Engine/Build/BatchFiles/RunUAT.sh"
for cache in Epic Engine/Intermediate Engine/Programs/UnrealBuildTool Engine/Saved Engine/DerivedDataCache; do
    if ! test -w "$engine/$cache"; then
        echo "Unreal cache is unwritable: $engine/$cache" >&2
        exit 1
    fi
done
"""
'''


def task_configuration(dockerfile: Path, *, prepare_agent: bool = False) -> str:
    """Use the image pinned in the source recipe for both running environments.

    Args:
        dockerfile: Maintained Battle Royale agent Dockerfile.
        prepare_agent: Prepare the stock image for builds by the agent.

    Returns:
        The TOML for a single step with an isolated build and startup verifier.

    Raises:
        ValueError: The base image is missing or lacks a SHA-256 digest.
    """
    base = re.search(r"^FROM ([^\s]+@sha256:[a-f0-9]{64})$", dockerfile.read_text(encoding="utf-8"), re.M)
    if base is None:
        raise ValueError(f"Expected a digest-pinned FROM image in {dockerfile}")
    image = base.group(1)
    setup = AGENT_SETUP if prepare_agent else ""
    return f'''schema_version = "1.4"
multi_step_reward_strategy = "final"
artifacts = [{{ source = "{SUBMISSION}", destination = "game/UEGame", exclude = ["Binaries", "Intermediate", "Saved", "DerivedDataCache", "Packaged"] }}]

[task]
name = "abundant/{BUNDLE_NAME}"
description = "Build and deliver a two-player Unreal Engine battle royale game."

[metadata]
ue_version = "5.8.4"
category = "unreal"
reward_type = "binary"
calibration_stage = "basic"

[agent]
user = "agent"
timeout_sec = 14400
{setup}
[environment]
docker_image = "{image}"
build_timeout_sec = 3600
cpus = 4
memory_mb = 16384
storage_mb = 409600
gpus = 0
workdir = "{WORKDIR}"
network_mode = "no-network"

[verifier]
environment_mode = "separate"
user = "root"
timeout_sec = 7200
network_mode = "no-network"

[verifier.environment]
docker_image = "{image}"
build_timeout_sec = 3600
cpus = 4
memory_mb = 16384
storage_mb = 409600
gpus = 0
workdir = "/tests"
network_mode = "no-network"

[verifier.env]
BATTLE_ROYALE_SUBMISSION = "{SUBMISSION}"

[[steps]]
name = "{STEP_NAME}"

[steps.verifier]
timeout_sec = 7200
'''


def public_markdown(text: str) -> str:
    """Relocate mounted task links when copying the public Markdown.

    Args:
        text: An original brief or component instruction.

    Returns:
        Markdown with absolute `/app/` link targets adjusted for the prebuilt image.
    """
    def relocate(match: re.Match[str]) -> str:
        """Rewrite a link only if its target starts at the old mount point."""
        target = match.group(1)
        if not target.startswith("/app/"):
            return match[0]
        start, end = match.start(1) - match.start(), match.end(1) - match.start()
        return f"{match[0][:start]}{WORKDIR}/{target.removeprefix('/app/')}{match[0][end:]}"

    return LINK_TARGET.sub(relocate, text)


def stage_files(task_root: Path, package: Path, *, prepare_agent: bool = False) -> None:
    """Copy the task's runtime files into a new package directory.

    Args:
        task_root: Maintained task sources with a complete Oracle and verifier.
        package: Empty staging directory for the task, including its generated TOML.
        prepare_agent: Include agent engine setup in the generated TOML.

    Raises:
        ValueError: A required source file is missing or a selected file is unsafe.
    """
    step = task_root / "steps" / STEP_NAME
    solution = step / "solution"
    instruction = step / "instruction.md"
    recipe = task_root / "environment" / "Dockerfile"
    solve = solution / "solve.sh"
    executable = (step / "tests" / "test.sh", step / "tests" / "prepare_engine.sh", solve)
    required = [
        recipe,
        task_root / "environment" / ".dockerignore",
        step / "tests" / "build_smoke.py",
        *executable,
    ]
    public = candidate_inputs(step)
    oracle_sources: list[Path] = []
    for source in solution.rglob("*"):
        if GENERATED_NAMES.intersection(source.relative_to(solution).parts) or source.suffix == ".pyc":
            continue
        if source.is_symlink() or (not source.is_file() and not source.is_dir()):
            raise ValueError(f"Expected a regular Oracle file or directory: {source}")
        if source.is_file() and source != solve:
            oracle_sources.append(source)
    if not oracle_sources:
        raise ValueError(f"Expected an Oracle project in {solution}")

    for source in [*public, *required, *oracle_sources]:
        if source.resolve() != source or not source.is_file():
            raise ValueError(f"Expected a regular package input: {source}")
        destination = package / source.relative_to(task_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source in public and source.suffix.lower() == ".md":
            text = public_markdown(source.read_text(encoding="utf-8"))
            if source == instruction:
                text = text.rstrip() + (
                    f"\n- Save the complete Unreal project as `{SUBMISSION}/BattleRoyale.uproject`."
                    f" Include `{SUBMISSION}/README.md` with the Linux build and launch instructions,"
                    " the steps for connecting both clients, and the game controls.\n"
                )
            destination.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(source, destination)
        if source in executable:
            destination.chmod(0o755)

    (package / "task.toml").write_text(task_configuration(recipe, prepare_agent=prepare_agent), encoding="utf-8")


def file_inventory(directory: Path) -> dict[str, tuple[str, int]]:
    """Fingerprint the regular files in a staged or existing package.

    Args:
        directory: Package directory whose contents and permission bits matter.

    Returns:
        Relative POSIX paths mapped to SHA-256 digests and permission modes.

    Raises:
        ValueError: The directory contains a symlink or other special file.
    """
    inventory: dict[str, tuple[str, int]] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise ValueError(f"Expected a regular packaged file or directory: {path}")
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            inventory[path.relative_to(directory).as_posix()] = (digest, stat.S_IMODE(path.stat().st_mode))
    return inventory


def package_baselines(task_root: Path, output_dir: Path, *, prepare_agent: bool = False) -> dict[str, str | int]:
    """Validate and publish an Oddish package beside an optional existing build.

    Args:
        task_root: Maintained Battle Royale task tree.
        output_dir: Parent of the generated task directory.
        prepare_agent: Include agent engine setup in the generated TOML.

    Returns:
        The absolute package path, manifest SHA-256, and number of staged files.

    Raises:
        FileExistsError: The requested destination already has different contents.
    """
    task_root = task_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir.resolve() / BUNDLE_NAME
    with TemporaryDirectory(prefix=".battle-royale-", dir=destination.parent) as temporary:
        staged = Path(temporary)
        stage_files(task_root, staged, prepare_agent=prepare_agent)
        inventory = file_inventory(staged)
        manifest = {"step": STEP_NAME, "files": {name: value[0] for name, value in inventory.items()}}
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (staged / MANIFEST).write_bytes(manifest_bytes)

        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir() or file_inventory(destination) != file_inventory(staged):
                raise FileExistsError(f"{destination} already exists with different contents. Choose another --output directory.")
        else:
            staged.rename(destination)

    return {
        "task_dir": str(destination),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_files": len(inventory),
    }


def main() -> None:
    """Build the package selected by CLI arguments and report its location."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Parent of the generated Oddish task directory")
    parser.add_argument("--prepare-agent", action="store_true", help="Enable Unreal builds inside the agent container")
    args = parser.parse_args()
    default_output = "model-ready" if args.prepare_agent else "baselines"
    output = args.output or TASK_ROOT / "experiment" / default_output
    print(json.dumps(package_baselines(TASK_ROOT, output, prepare_agent=args.prepare_agent), indent=2))


if __name__ == "__main__":
    main()
