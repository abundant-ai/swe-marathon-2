"""Restore generated benchmark assets, or reproduce the exact evaluated runtime."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from oddish_fixtures import download

TASK = "swe-m2_ai-research_dense-functional-part-metrology-correct-9acadc32"
VERSION = 1
PROSPECTIVE_TASK = "swe-m2_ai-research_dense-functional-part-metrology-8cf9c423"
PROSPECTIVE_VERSION = 2
HERE = Path(__file__).resolve().parent
EXECUTABLES = {"environment/public/python", "tests/test.sh", "solution/solve.sh"}
GENERATED = {
    "environment/public/clip.mp4",
    "environment/public/frames.zip",
    "environment/public/observation.png",
}


def digest(path: Path) -> str:
    """Return SHA-256 of an existing file in the runtime inventory."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def restore(
    output: Path,
    bundle: Path | None,
    full_runtime: bool,
    *,
    prospective: bool = False,
    strict: bool = False,
    arm: str = "correct",
) -> None:
    """Fill missing fixtures in the task tree or reproduce the full Oddish bundle.

    Args:
        output: Authoring task directory, or a fresh directory for full_runtime.
        bundle: Source directory for the requested exact task revision. Without a bundle the program
            reads the frozen files via the authenticated Oddish API.
        full_runtime: Populate all pinned paths, including exact source and
            executable modes. A full-runtime directory must have no extra files.
        prospective: Select the first clean-workspace prospective evaluation revision.
        strict: Select the version-3 triplet with identical non-optical public files.
        arm: Select matching, substituted or withheld optical evidence on that revision.

    Any mismatched local file raises. Downloaded bytes are checked in a temporary
    directory before publishing. Interrupted restores can resume in place.
    """
    task, version, manifest = (
        (PROSPECTIVE_TASK, PROSPECTIVE_VERSION, "prospective-runtime-inventory.json")
        if prospective
        else (TASK, VERSION, "runtime-inventory.json")
    )
    if strict:
        task, version, manifest = PROSPECTIVE_TASK, 3, "strict-runtime-inventory.json"
    all_files = json.loads((HERE / manifest).read_text())
    if arm != "correct":
        if not (prospective or strict) or not full_runtime:
            raise ValueError(
                "An intervention arm requires a prospective full-runtime restore"
            )
        revision = json.loads(
            (
                HERE
                / (
                    "strict-intervention-inventories.json"
                    if strict
                    else "prospective-intervention-inventories.json"
                )
            ).read_text()
        )[arm]
        task, version = revision["task"], revision["version"]
        for name, sha in revision["changes_from_matched"].items():
            if sha is None:
                del all_files[name]
            else:
                all_files[name] = sha
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
        if bundle is None:
            download(task, version, missing, fetched)
        for name in missing:
            target = fetched / name
            if bundle is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(bundle / name, target)
            if digest(target) != inventory[name]:
                raise ValueError(f"Fixture checksum mismatch: {name}")
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
    """Create the maintained task from explicit runtime paths, excluding all author evidence."""
    author = HERE.parent
    if output.exists():
        raise FileExistsError(f"Choose a fresh runtime destination: {output}")
    restore(author, bundle, False, strict=True)
    names = json.loads((HERE / "strict-runtime-inventory.json").read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        staged = Path(tmp) / "runtime"
        staged.mkdir()
        for name in sorted(names):
            dest = staged / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(author / name, dest)
        staged.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        help="Read from a local copy of the selected evaluated revision",
    )
    dest = parser.add_mutually_exclusive_group()
    dest.add_argument(
        "--task-dir",
        type=Path,
        default=HERE.parent,
        help="Restore only generated fixtures here",
    )
    dest.add_argument(
        "--frozen-runtime",
        type=Path,
        help="Restore the first dense-video evaluation bundle here",
    )
    dest.add_argument(
        "--prospective-runtime",
        type=Path,
        help="Restore the exact clean-source evaluation bundle here",
    )
    dest.add_argument(
        "--strict-runtime",
        type=Path,
        help="Restore the exact version-3 experimental condition",
    )
    dest.add_argument(
        "--stage-runtime",
        type=Path,
        help="Stage the maintained task in a fresh runtime-only folder",
    )
    parser.add_argument(
        "--arm",
        choices=("correct", "swapped", "none"),
        default="correct",
        help="Select matching, swapped or missing images for a prospective or strict runtime",
    )
    args = parser.parse_args()
    if args.arm != "correct" and not (args.prospective_runtime or args.strict_runtime):
        parser.error("--arm requires --strict-runtime or --prospective-runtime")
    if args.stage_runtime is not None:
        stage_runtime(args.stage_runtime, args.bundle)
    elif args.strict_runtime is not None:
        restore(args.strict_runtime, args.bundle, True, strict=True, arm=args.arm)
    elif args.prospective_runtime is not None:
        restore(
            args.prospective_runtime, args.bundle, True, prospective=True, arm=args.arm
        )
    elif args.frozen_runtime is not None:
        restore(args.frozen_runtime, args.bundle, True)
    else:
        restore(args.task_dir, args.bundle, False, strict=True)
