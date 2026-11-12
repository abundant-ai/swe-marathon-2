"""Build a self-contained, validated Harbor bundle containing only step 1."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

from harbor.models.task.task import Task

ROOT_FILES = ("task.toml", "README.md", "pyproject.toml", "uv.lock")
INPUT_DIRS = ("environment", "steps/01-build-rag", "scripts", "checks")
EXCLUDED_PARTS = {".venv", "__pycache__", ".pytest_cache", ".DS_Store"}


def selected_files(task_root: Path) -> list[Path]:
    """Select runtime inputs and author checks without caches or other steps.

    Args:
        task_root: Source task containing already prepared data.

    Returns:
        Sorted regular files eligible for the distribution.

    Raises:
        ValueError: An input is a symlink or private/public data is unprepared.
    """
    for required in (
        "environment/data/corpus.jsonl", "environment/data/HERB_LICENSE.txt",
        "steps/01-build-rag/tests/private/cases.jsonl",
        "steps/01-build-rag/tests/private/corpus.jsonl",
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
            if path.is_file() and path.suffix != ".pyc":
                files.append(path)
    return sorted(files)


def package_step(task_root: Path, destination: Path) -> dict[str, Any]:
    """Stage, validate, and archive a content-addressed step-1 task.

    Args:
        task_root: Authoring source directory.
        destination: Local output directory; private benchmark material is included.

    Returns:
        Paths, hashes, and record counts for the complete deliverable. Secrets,
        local virtualenvs, experiment outputs, and future steps are not included.

    Raises:
        ValueError: The staged task violates Harbor's task or input-path contracts.
    """
    files = selected_files(task_root)
    hashes = {str(path.relative_to(task_root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = destination / "bundles" / digest[:12] / "knowledge-work-assistant"
    staging.mkdir(parents=True, exist_ok=True)
    for path in files:
        target = staging / path.relative_to(task_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    manifest = {"sha256": digest, "files": hashes, "harbor_revision": "feea734de84bf2479b329dc6315a6d98d1596f4f"}
    (staging / "BUNDLE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    task = Task(staging)
    if [step.name for step in task.config.steps] != ["01-build-rag"]:
        raise ValueError("The deliverable must contain exactly step 1")
    archive = destination / "knowledge-work-assistant-step1.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                entry = bundle.gettarinfo(str(path), arcname=str(Path(staging.name) / path.relative_to(staging)))
                entry.uid = entry.gid = 0
                entry.uname = entry.gname = ""
                entry.mtime = 0
                with path.open("rb") as stream:
                    bundle.addfile(entry, stream)
    archive.chmod(0o600)
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{archive_hash}  {archive.name}\n")
    return {"task_path": str(staging.resolve()), "archive": str(archive.resolve()), "archive_sha256": archive_hash, "content_sha256": digest, "files": len(hashes), "bytes": archive.stat().st_size}


def main() -> None:
    """Build the local deliverable and print paths suitable for Harbor commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    print(json.dumps(package_step(Path(__file__).resolve().parents[1], args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
