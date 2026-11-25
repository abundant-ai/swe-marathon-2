"""Build a self-contained, validated Harbor bundle containing only step 1."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

from harbor.models.task.config import TaskConfig
from harbor.models.task.task import Task
from task_paths import EXPERIMENT_ROOT, TASK_ROOT


def file_hash(path: Path) -> str:
    """Stream a runtime artifact into SHA-256 without loading a multi-GB corpus.

    Args:
        path: Existing regular file selected for packaging.

    Returns:
        Lowercase SHA-256 digest of its bytes.
    """
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


ROOT_FILES = ("task.toml", "instruction.md")
INPUT_DIRS = ("environment", "tests", "solution")
EXCLUDED_PARTS = {".venv", "__pycache__", ".pytest_cache", ".DS_Store", "experiment"}


def selected_files(task_root: Path) -> list[Path]:
    """Select runtime artifacts without authoring tools, caches, or other steps.

    Args:
        task_root: Source task containing already prepared data.

    Returns:
        Sorted regular files eligible for the distribution.

    Raises:
        ValueError: An input is a symlink or private/public data is unprepared.
    """
    for required in (
        "environment/data/corpus.json",
        "environment/resources/README.md",
        "tests/private/cases.json",
        "tests/private/corpus.json",
        "tests/private/rubrics.json",
    ):
        if not (task_root / required).is_file():
            raise ValueError(f"Prepare task data first; missing {required}")
    files = [task_root / name for name in ROOT_FILES]
    for directory in INPUT_DIRS:
        for path in (task_root / directory).rglob("*"):
            if EXCLUDED_PARTS.intersection(path.relative_to(task_root).parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Bundle inputs cannot be symlinks: {path}")
            if (
                path.is_file()
                and path.suffix != ".pyc"
                and ".pending." not in path.name
            ):
                files.append(path)
    return sorted(files)


def package_step(task_root: Path, destination: Path) -> dict[str, Any]:
    """Stage, validate, and archive a content-addressed step-1 task.

    Name the packaged directory after the declared task slug for Oddish preflight.

    Args:
        task_root: Authoring source directory.
        destination: Local output directory; private benchmark material is included.

    Returns:
        Paths, hashes, and record counts for the complete deliverable. Secrets,
        local virtualenvs, experiment outputs, and future steps are not included.

    Raises:
        ValueError: The staged task violates Harbor's task or input-path contracts.
    """
    config = TaskConfig.model_validate_toml((task_root / "task.toml").read_text())
    if config.task is None:
        raise ValueError("Packaging requires an explicit [task].name")
    task_slug = config.task.name.rsplit("/", 1)[-1]
    files = selected_files(task_root)
    inputs = {str(path.relative_to(task_root)): path for path in files}
    # Both isolated Harbor environments start their own protected CPU database.
    service = task_root / "common/chroma-service"
    for required in (
        "Dockerfile",
        "pyproject.toml",
        "uv.lock",
        "orange_chroma/server.py",
    ):
        if not (service / required).is_file():
            raise ValueError(f"Missing protected Chroma service input: {required}")
    for path in sorted(service.rglob("*")):
        if EXCLUDED_PARTS.intersection(path.relative_to(service).parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Service inputs cannot be symlinks: {path}")
        if path.is_file() and path.suffix != ".pyc":
            for target_context in ("environment", "tests"):
                inputs[
                    str(
                        Path(target_context)
                        / "chroma-service"
                        / path.relative_to(service)
                    )
                ] = path
    inputs["tests/docker-compose.yaml"] = task_root / "environment/docker-compose.yaml"
    # Harbor builds the verifier with tests/ as its isolated Docker context.
    # Stage identical GPU inputs there without maintaining a second source copy.
    for path in files:
        relative = path.relative_to(task_root)
        if relative.parts[0] == "environment" and relative.name not in {
            "Dockerfile",
            ".dockerignore",
            "docker-compose.yaml",
        }:
            inputs[
                str(Path("tests/gpu-runtime") / relative.relative_to("environment"))
            ] = path
    hashes = {name: file_hash(path) for name, path in inputs.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = destination / "bundles" / digest[:12] / task_slug
    staging.mkdir(parents=True, exist_ok=True)
    for name, path in inputs.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    manifest = {
        "sha256": digest,
        "files": hashes,
        "harbor_revision": "feea734de84bf2479b329dc6315a6d98d1596f4f",
    }
    (staging / "BUNDLE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    task = Task(staging)
    if task.has_steps or not (staging / "instruction.md").is_file():
        raise ValueError("Expected a single task-root instruction")
    archive = destination / "knowledge-work-assistant-step1.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                entry = bundle.gettarinfo(
                    str(path),
                    arcname=str(Path(staging.name) / path.relative_to(staging)),
                )
                entry.uid = entry.gid = 0
                entry.uname = entry.gname = ""
                entry.mtime = 0
                with path.open("rb") as stream:
                    bundle.addfile(entry, stream)
    archive.chmod(0o600)
    archive_hash = file_hash(archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{archive_hash}  {archive.name}\n"
    )
    return {
        "task_path": str(staging.resolve()),
        "archive": str(archive.resolve()),
        "archive_sha256": archive_hash,
        "content_sha256": digest,
        "files": len(hashes),
        "bytes": archive.stat().st_size,
    }


def main() -> None:
    """Package the task for local review or upload using explicit CLI settings.

    Used by the repository's packaging command after input preparation. Writes
    bundles under experiment/dist unless --output selects another destination,
    then prints their paths and hashes. Returns no value.

    Raises:
        ValueError: Runtime inputs or the packaged task contract are invalid.
        OSError: A source file cannot be read or an output cannot be written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "dist")
    args = parser.parse_args()
    print(json.dumps(package_step(TASK_ROOT, args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
