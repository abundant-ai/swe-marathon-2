"""Stage a bundle that grades a stored submission again.

The bundle is the step bundle with one change: the solution's reference files
are replaced by the unit files of a past submission, which the verifier saves
as `candidate_unit_files.tar.gz`. Running the bundle with the `oracle` agent
installs those files and the verifier grades them. The task gets its own name,
so it never becomes a new version of the real task. The expected reward is
that of the submission, not 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

from package_step import selected_files
from task_paths import EXPERIMENT_ROOT, TASK_ROOT

REFERENCE_PREFIX = "solution/data/"
MAX_FILE_BYTES = 4 * 1024 * 1024


def submitted_files(archive: Path) -> dict[str, bytes]:
    """Read the unit files of a stored submission without extracting to disk.

    Args:
        archive: A `candidate_unit_files.tar.gz` written by the verifier.

    Returns:
        Archive-relative names (under `sympy/`) mapped to file contents.

    Raises:
        ValueError: A member is not a regular Python file under `sympy/`, has
            an unsafe name or is too large.
    """
    files: dict[str, bytes] = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            name = PurePosixPath(member.name)
            if (
                not member.isfile()
                or name.is_absolute()
                or ".." in name.parts
                or name.parts[:1] != ("sympy",)
                or name.suffix != ".py"
                or member.size > MAX_FILE_BYTES
            ):
                raise ValueError(f"Unexpected archive member: {member.name}")
            handle = tar.extractfile(member)
            if handle is None:
                raise ValueError(f"Unreadable archive member: {member.name}")
            files[name.as_posix()] = handle.read()
    return files


def package_regrade(
    task_root: Path, archive: Path, label: str, destination: Path
) -> dict[str, Any]:
    """Stage the step bundle with a stored submission in place of the reference.

    Args:
        task_root: Authoring source directory with prepared inputs in place.
        archive: The submission's `candidate_unit_files.tar.gz`.
        label: Short name for the submission, appended to the task name.
        destination: Local output directory; private verifier inputs are included.

    Returns:
        The staged task path, its content hash and its file count.

    Raises:
        ValueError: Inputs are unprepared, the label is malformed or the
            submission does not cover exactly the reference's files.
    """
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", label):
        raise ValueError("The label must be lower-case letters, digits and hyphens")
    inputs = selected_files(task_root)
    reference = {
        name[len(REFERENCE_PREFIX) :]
        for name in inputs
        if name.startswith(REFERENCE_PREFIX)
    }
    submitted = submitted_files(archive)
    if set(submitted) != reference:
        raise ValueError(
            f"The submission holds {len(submitted)} files; the reference holds {len(reference)} with other names"
        )
    content = {
        name: path.read_bytes()
        for name, path in inputs.items()
        if not name.startswith(REFERENCE_PREFIX)
    }
    content.update({REFERENCE_PREFIX + name: data for name, data in submitted.items()})
    config, count = re.subn(
        r'^(name = "abundant/[^"]+)"',
        rf'\1-regrade-{label}"',
        content["task.toml"].decode("utf-8"),
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("task.toml has no [task].name to rename")
    content["task.toml"] = config.encode("utf-8")
    slug = re.search(r'^name = "abundant/([^"]+)"', config, flags=re.MULTILINE).group(1)
    hashes = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(content.items())
    }
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = destination / "regrade" / digest[:12] / slug
    if staging.exists():
        shutil.rmtree(staging)
    for name, data in content.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if name in inputs:
            shutil.copymode(inputs[name], target)
    (staging.parent / "BUNDLE_MANIFEST.json").write_text(
        json.dumps({"sha256": digest, "files": hashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "task_path": str(staging.resolve()),
        "content_sha256": digest,
        "files": len(content),
    }


def main() -> None:
    """Package a regrade bundle and print the result as JSON.

    Raises:
        ValueError: Runtime inputs, the label or the submission are invalid.
        OSError: A source cannot be read or an output cannot be written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archive", type=Path, help="candidate_unit_files.tar.gz of the submission"
    )
    parser.add_argument(
        "--label", required=True, help="short name for the submission, e.g. t17"
    )
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "dist")
    args = parser.parse_args()
    print(
        json.dumps(
            package_regrade(
                TASK_ROOT, args.archive.resolve(), args.label, args.output.resolve()
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
