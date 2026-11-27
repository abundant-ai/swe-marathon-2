"""Restore generated benchmark assets, or reproduce the exact evaluated runtime."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

TASK = "swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a"
MAINTAINED_TASK = "swe-m2_ai-research_telephone-contact-reconstruction-release-e8e06a9c"
CLEAN_TASK = "swe-m2_ai-research_telephone-contact-reconstruction-clean-d662f1f9"
SNAPSHOTS = {
    "qualified": (
        "swe-m2_ai-research_telephone-contact-reconstruction-qa-correct-c51c7bb1",
        "qualified-inventory.json",
        7,
    ),
    "original": (TASK, "runtime-inventory.json", 1),
    "maintained": (MAINTAINED_TASK, "maintained-inventory.json", 1),
    "clean": (CLEAN_TASK, "clean-inventory.json", 1),
}
HERE = Path(__file__).resolve().parent
EXECUTABLES = {"environment/public/python", "tests/test.sh", "solution/solve.sh"}
GENERATED = {
    "environment/public/observation.png",
    "environment/public/frames.zip",
    "environment/public/clip.mp4",
}


def digest(path: Path) -> str:
    """Return SHA-256 of an existing file in the runtime inventory."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def restore(
    output: Path, bundle: Path | None, full_runtime: bool, snapshot: str = "original"
) -> None:
    """Fill missing fixtures in the task tree or reproduce the full Oddish bundle.

    Args:
        output: Authoring task directory, or a fresh directory for full_runtime.
        bundle: Source version-1 runtime directory. Without a bundle the program
            reads the frozen files via the authenticated Oddish CLI.
        full_runtime: Populate all pinned paths, including exact source and
            executable modes. A full-runtime directory must have no extra files.
        snapshot: Original model experiment, intermediate maintained baseline, or clean-rebuild release.

    Any mismatched local file raises. Downloaded bytes are checked in a temporary
    directory before publishing. Interrupted restores can resume in place.
    """
    remote, inventory_name, version = SNAPSHOTS[snapshot]
    all_files = json.loads((HERE / inventory_name).read_text())
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
                    ["oddish", "cat", remote, name, "--version", str(version)]
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


def stage_runtime(output: Path, bundle: Path | None) -> None:
    """Stage executable sources and measured fixtures, excluding historical fitted meshes."""
    source = HERE.parent
    if output.exists():
        raise FileExistsError(f"Choose a fresh runtime destination: {output}")
    restore(source, bundle, False)
    names = set(json.loads((HERE / "clean-inventory.json").read_text()))
    names = {name for name in names if not name.startswith("solution/")}
    names.update(
        str(p.relative_to(source))
        for p in (source / "solution").iterdir()
        if p.is_file() and p.suffix in {".py", ".sh", ".c", ".json"}
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        staged = Path(tmp) / "runtime"
        for name in sorted(names):
            dest = staged / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, dest)
        staged.rename(output)


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
    dest.add_argument(
        "--release-runtime",
        type=Path,
        help="Restore the exact separately hosted maintained baseline release here",
    )
    dest.add_argument(
        "--clean-runtime",
        type=Path,
        help="Restore the final public clean-rebuild baseline package here",
    )
    dest.add_argument(
        "--stage-runtime",
        type=Path,
        help="Stage the current RGB-only reference and executable task",
    )
    dest.add_argument(
        "--qualified-runtime",
        type=Path,
        help="Restore the qualified task with its repaired RGB-only oracle",
    )
    args = parser.parse_args()
    if args.qualified_runtime:
        restore(args.qualified_runtime, args.bundle, True, snapshot="qualified")
        raise SystemExit(0)
    if args.stage_runtime is not None:
        stage_runtime(args.stage_runtime, args.bundle)
        raise SystemExit(0)
    snapshot = (
        "clean"
        if args.clean_runtime
        else "maintained"
        if args.release_runtime
        else "original"
    )
    restore(
        args.clean_runtime
        or args.release_runtime
        or args.frozen_runtime
        or args.task_dir,
        args.bundle,
        any((args.clean_runtime, args.frozen_runtime, args.release_runtime)),
        snapshot,
    )
