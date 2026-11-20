"""Package the Battle Royale brief and its runtime image recipe for review."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from io import BytesIO
import json
from os.path import normpath
from pathlib import Path
import re
import tarfile
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit


TASK_ROOT = Path(__file__).resolve().parents[1]
STEP_NAME = "01-build-game"
BUNDLE_NAME = "swe-m2_game-development_battle-royale"
LINK_TARGET = re.compile(r"!?\[[^\]\n]*\]\(([^\s)]+)\)")


def candidate_inputs(step_root: Path) -> list[Path]:
    """Find the brief and every local file linked from its Markdown.

    Args:
        step_root: The source step. Its workdir is mounted as /app.

    Returns:
        Sorted regular files inside the step, preserving their source paths.

    Raises:
        ValueError: A local link escapes the public inputs, uses a symlink, or is missing.
    """
    step_root = Path(normpath(step_root.absolute()))
    pending = [step_root / "instruction.md"]
    workdir = step_root / "workdir"
    selected: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in selected:
            continue
        if source.resolve() != source or not source.is_file():
            raise ValueError(f"Expected a regular step instruction or asset: {source}")
        selected.add(source)
        if source.suffix.lower() != ".md":
            continue
        for target in LINK_TARGET.findall(source.read_text(encoding="utf-8")):
            link = urlsplit(target)
            if link.scheme or link.netloc or not link.path:
                continue
            path = unquote(link.path)
            if path.startswith("/app/"):
                candidate = workdir / path.removeprefix("/app/")
            else:
                candidate = source.parent / path
            candidate = Path(normpath(candidate))
            if not candidate.is_relative_to(workdir):
                raise ValueError(f"{source}: linked input must stay within the candidate workdir: {target}")
            pending.append(candidate)
    return sorted(selected)


def package_inputs(task_root: Path, output_dir: Path) -> dict[str, str | int]:
    """Write a reproducible draft archive containing only the selected inputs.

    Args:
        task_root: Local Battle Royale source tree.
        output_dir: Location for the generated archive.

    Returns:
        Archive path, its SHA-256 hash and the number of source files included.
    """
    task_root = task_root.resolve()
    step_root = task_root / "steps" / STEP_NAME
    recipe = [task_root / name for name in ("environment/Dockerfile", "environment/.dockerignore")]
    for path in recipe:
        if path.resolve() != path or not path.is_file():
            raise ValueError(f"Expected a regular runtime recipe input: {path}")
    paths = [*recipe, *candidate_inputs(step_root)]
    files = {path.relative_to(task_root).as_posix(): path.read_bytes() for path in paths}
    manifest = {
        "step": STEP_NAME,
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    files["BUNDLE_MANIFEST.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()

    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / "battle-royale-step1-draft.tar.gz"
    with TemporaryDirectory(dir=output_dir) as temporary:
        staging = Path(temporary) / archive.name
        with staging.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as bundle:
                for name, content in sorted(files.items()):
                    entry = tarfile.TarInfo(f"{BUNDLE_NAME}/{name}")
                    entry.size = len(content)
                    bundle.addfile(entry, BytesIO(content))
        with staging.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        staging.replace(archive)
    return {"archive": str(archive.resolve()), "sha256": digest, "source_files": len(paths)}


def main() -> None:
    """Package the local draft and print the archive location and hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK_ROOT / "experiment/dist")
    args = parser.parse_args()
    print(json.dumps(package_inputs(TASK_ROOT, args.output), indent=2))


if __name__ == "__main__":
    main()
