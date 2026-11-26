"""Restore generated benchmark assets, or reproduce the exact evaluated runtime."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

TASK = "swe-m2_ai-research_clutter-object-metrology-swapped-c9e4647d"
VERSION = 1
HERE = Path(__file__).resolve().parent
EXECUTABLES = {"environment/public/python", "tests/test.sh", "solution/solve.sh"}
GENERATED = {"environment/public/observation.png", "solution/reference.npz"}


def digest(path: Path) -> str:
    """Return SHA-256 of an existing file in the runtime inventory."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def restore(output: Path, bundle: Path | None, full_runtime: bool) -> None:
    """Fill missing fixtures in the task tree or reproduce the full Oddish bundle.

    Args:
        output: Authoring task directory, or a fresh directory for full_runtime.
        bundle: Source version-1 runtime directory. Without a bundle the program
            reads the frozen files via the authenticated Oddish CLI.
        full_runtime: Populate all pinned paths, including exact source and
            executable modes. A full-runtime directory must have no extra files.

    Any mismatched local file raises. Downloaded bytes are checked in a temporary
    directory before publishing. Interrupted restores can resume in place.
    """
    all_files = json.loads((HERE / "runtime-inventory.json").read_text())
    inventory = {
        name: sha
        for name, sha in all_files.items()
        if full_runtime or name.startswith("tests/private/") or name in GENERATED
    }
    output.mkdir(parents=True, exist_ok=True)
    if full_runtime:
        extra = {
            str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()
        } - inventory.keys()
        if extra:
            raise ValueError(
                f"Full-runtime destination contains extra files: {sorted(extra)}"
            )
    missing = []
    for name, sha in inventory.items():
        local = output / name
        if local.exists():
            if digest(local) != sha:
                raise ValueError(
                    f"Existing file differs from the frozen runtime: {local}"
                )
        else:
            missing.append(name)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        fetched = Path(tmp)
        for name in missing:
            if bundle is None:
                data = subprocess.check_output(
                    ["oddish", "cat", TASK, name, "--version", str(VERSION)]
                )
            else:
                data = (bundle / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != inventory[name]:
                raise ValueError(f"Fixture checksum mismatch: {name}")
            target = fetched / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if name in EXECUTABLES:
                target.chmod(0o755)
        for name in missing:
            local = output / name
            local.parent.mkdir(parents=True, exist_ok=True)
            try:
                local.hardlink_to(fetched / name)
            except FileExistsError:
                if digest(local) != inventory[name]:
                    raise ValueError(f"Concurrent modification: {local}") from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle", type=Path, help="Read from a local version-1 runtime bundle"
    )
    dest = parser.add_mutually_exclusive_group()
    dest.add_argument(
        "--task-dir",
        type=Path,
        default=HERE.parent,
        help="Restore only generated fixtures here",
    )
    dest.add_argument(
        "--frozen-runtime", type=Path, help="Restore the entire evaluated bundle here"
    )
    args = parser.parse_args()
    restore(
        args.frozen_runtime or args.task_dir,
        args.bundle,
        args.frozen_runtime is not None,
    )
