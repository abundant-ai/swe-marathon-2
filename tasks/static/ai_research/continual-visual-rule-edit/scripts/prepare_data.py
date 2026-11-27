"""Restore generated benchmark assets, or reproduce the exact evaluated runtime."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from oddish_fixtures import download

HERE = Path(__file__).resolve().parent
EXECUTABLES = {"environment/public/python", "tests/test.sh", "solution/solve.sh"}
GENERATED = {"environment/public/observation.png", "environment/public/calibration.npz"}


def digest(path: Path) -> str:
    """Return SHA-256 of an existing file in the runtime inventory."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def pinned_condition(arm: str) -> tuple[dict[str, str], str, int]:
    """Read and authenticate the file inventory for one registered observation condition."""
    if arm == "qualified":
        files = json.loads((HERE / "qualified-inventory.json").read_text())
        return files, "swe-m2_ai-research_continual-visual-rule-edit-qa-correct-8ad21121", 4
    record = json.loads((HERE / "optical-conditions.json").read_text())[arm]
    files = json.loads((HERE / "runtime-inventory.json").read_text())
    for name, checksum in record["overrides"].items():
        if checksum is None:
            del files[name]
        else:
            files[name] = checksum
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != record["manifest_sha256"]:
        raise ValueError(f"Manifest mismatch for {arm}")
    return files, record["task"], record["version"]


def restore(
    output: Path, bundle: Path | None, full_runtime: bool, arm: str = "correct"
) -> None:
    """Fill missing fixtures in the task tree or reproduce the full Oddish bundle.

    Args:
        output: Authoring task directory, or a fresh directory for full_runtime.
        bundle: Source runtime directory for the chosen arm. Without a bundle the program
            reads the frozen files via the authenticated Oddish API.
        full_runtime: Populate all pinned paths, including exact source and
            executable modes. A full-runtime directory must have no extra files.

        arm: Registered observation condition to restore.

    Any mismatched local file raises. Downloaded bytes are checked in a temporary
    directory before publishing. Interrupted restores can resume in place.
    """
    all_files, task, version = pinned_condition(arm)
    inventory = {
        name: sha
        for name, sha in all_files.items()
        if full_runtime
        or name.startswith("tests/private/precision-pilot/data/")
        or name in GENERATED
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
            if full_runtime:
                expected_exec = 0o111 if name in EXECUTABLES else 0
                if local.stat().st_mode & 0o111 != expected_exec:
                    raise ValueError(
                        f"Existing executable mode differs from the frozen runtime: {local}"
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
    restore(author, bundle, False)
    names = json.loads((HERE / "runtime-inventory.json").read_text())
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
        "--bundle", type=Path, help="Read from a local bundle for the selected arm"
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
        "--stage-runtime",
        type=Path,
        help="Stage the current maintained source with the frozen data in a fresh directory",
    )
    parser.add_argument(
        "--arm",
        choices=("correct", "swapped", "none", "qualified"),
        default="correct",
        help="Optical condition to restore with --frozen-runtime; qualified restores the matched QA revision",
    )
    args = parser.parse_args()
    if args.arm != "correct" and args.frozen_runtime is None:
        parser.error("Use --frozen-runtime with --arm swapped or --arm none")
    if args.stage_runtime is not None:
        stage_runtime(args.stage_runtime, args.bundle)
    else:
        restore(
            args.frozen_runtime or args.task_dir,
            args.bundle,
            args.frozen_runtime is not None,
            args.arm,
        )
