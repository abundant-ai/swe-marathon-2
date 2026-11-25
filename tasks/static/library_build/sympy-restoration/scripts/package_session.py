"""Stage one working session of the 48-hour budget.

Oddish ends an attempt after 12 hours, so the budget stated in the instruction
is run as consecutive sessions, each one attempt. Session 1 is the task as it
is. A later session is the same task with two differences: `/app/sympy` starts
from the unit files the previous session delivered (the verifier saves them as
`candidate_unit_files.tar.gz`), and the timer counts the time already used.
Retired: the task now runs as one session, and its image has no timer, so this
packager refuses it.
The instruction, the verifier, the hidden inputs and the reference solution are
unchanged, so every session is graded like the task itself.

Bundles use the single-step layout, which every harness on Oddish accepts, and
carry their own task name: `...-48h-s1` for the first session, shared by all
runs, and `...-48h-<chain>-s<N>` for a later session of one run.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import tarfile
from pathlib import Path
from typing import Any

from package_regrade import submitted_files
from package_single_step import NAME_SUFFIX, flat_task_toml
from package_step import selected_files
from task_paths import EXPERIMENT_ROOT, STEP, TASK_ROOT

REFERENCE_PREFIX = "solution/data/"
TIMER = "environment/timer.sh"
DOCKERFILE = "environment/Dockerfile"
PROGRESS = "environment/data/progress.tar.gz"
OVERLAY_ANCHOR = "COPY timer.sh /app/timer.sh\n"
OVERLAY = (
    "# Unit files delivered by the previous working session.\n"
    "COPY data/progress.tar.gz /tmp/progress.tar.gz\n"
    "RUN tar xzf /tmp/progress.tar.gz -C /app && rm /tmp/progress.tar.gz\n"
)


def progress_archive(files: dict[str, bytes]) -> bytes:
    """Pack unit files into an archive whose bytes depend only on their content.

    Args:
        files: Names under `sympy/` mapped to file contents.

    Returns:
        A gzip-compressed tar with fixed owner, mode and times.
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(files):
            info = tarfile.TarInfo(name)
            info.size = len(files[name])
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(files[name]))
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", mtime=0) as zipped:
        zipped.write(raw.getvalue())
    return packed.getvalue()


def package_session(
    task_root: Path,
    session: int,
    chain: str | None,
    archive: Path | None,
    destination: Path,
) -> dict[str, Any]:
    """Stage the bundle of one working session.

    Args:
        task_root: Authoring source directory with prepared inputs in place.
        session: Number of the session, starting at 1.
        chain: Short name of the run this session continues; None for session 1.
        archive: `candidate_unit_files.tar.gz` of the previous session; None for session 1.
        destination: Local output directory; private verifier inputs are included.

    Returns:
        The staged task path, its content hash, its file count and the timing
        of the session.

    Raises:
        ValueError: Inputs are unprepared, the session lies outside the budget,
            or the previous session's files do not match the task's unit files.
    """
    if session < 1:
        raise ValueError("Sessions are numbered from 1")
    if (session == 1) != (chain is None and archive is None):
        raise ValueError(
            "Session 1 takes no chain and no archive; later sessions need both"
        )
    if chain is not None and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", chain):
        raise ValueError(
            "The chain name must be lower-case letters, digits and hyphens"
        )
    prefix = f"{STEP}/"
    inputs = selected_files(task_root)
    content = {
        (name.removeprefix(prefix)): path.read_bytes() for name, path in inputs.items()
    }
    if len(content) != len(inputs):
        raise ValueError(
            "A step file would overwrite a root file in the single-step layout"
        )
    config = flat_task_toml(content["task.toml"].decode("utf-8"))
    session_sec = int(
        re.search(
            r"^\[agent\]\ntimeout_sec = (\d+)$", config, flags=re.MULTILINE
        ).group(1)
    )
    if TIMER not in content:
        raise ValueError(
            "The chain of sessions is retired: the image has no timer to carry the time already used"
        )
    timer = content[TIMER].decode("utf-8")
    total_sec = int(re.search(r"^TOTAL_SEC=(\d+)$", timer, flags=re.MULTILINE).group(1))
    used_sec = (session - 1) * session_sec
    if used_sec >= total_sec:
        raise ValueError(
            f"Session {session} starts after the {total_sec} second budget is used up"
        )
    timer, count = re.subn(
        r"^USED_BEFORE_SEC=\d+$",
        f"USED_BEFORE_SEC={used_sec}",
        timer,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("timer.sh has no USED_BEFORE_SEC line")
    content[TIMER] = timer.encode("utf-8")
    suffix = "-48h-s1" if session == 1 else f"-48h-{chain}-s{session}"
    marker = f'{NAME_SUFFIX}"'
    if config.count(marker) != 1:
        raise ValueError("task.toml has no single-step task name to rename")
    config = config.replace(marker, f'{suffix}"')
    content["task.toml"] = config.encode("utf-8")
    slug = re.search(r'^name = "abundant/([^"]+)"', config, flags=re.MULTILINE).group(1)
    if archive is not None:
        reference = {
            name[len(REFERENCE_PREFIX) :]
            for name in content
            if name.startswith(REFERENCE_PREFIX)
        }
        delivered = submitted_files(archive)
        if set(delivered) != reference:
            raise ValueError(
                f"The previous session holds {len(delivered)} files; the task has {len(reference)} unit files with other names"
            )
        content[PROGRESS] = progress_archive(delivered)
        dockerfile = content[DOCKERFILE].decode("utf-8")
        if dockerfile.count(OVERLAY_ANCHOR) != 1:
            raise ValueError(
                "The agent Dockerfile has no timer line to place the unit files before"
            )
        content[DOCKERFILE] = dockerfile.replace(
            OVERLAY_ANCHOR, OVERLAY + OVERLAY_ANCHOR
        ).encode("utf-8")
    hashes = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(content.items())
    }
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = destination / "sessions" / digest[:12] / slug
    if staging.exists():
        shutil.rmtree(staging)
    names = {(name.removeprefix(prefix)): path for name, path in inputs.items()}
    for name, data in content.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if name in names:
            shutil.copymode(names[name], target)
    (staging.parent / "BUNDLE_MANIFEST.json").write_text(
        json.dumps({"sha256": digest, "files": hashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "task_path": str(staging.resolve()),
        "content_sha256": digest,
        "files": len(content),
        "session": session,
        "session_sec": session_sec,
        "used_before_sec": used_sec,
        "total_sec": total_sec,
        "last_session": used_sec + session_sec >= total_sec,
    }


def main() -> None:
    """Package one working session and print the result as JSON.

    Raises:
        ValueError: Runtime inputs, the session or the previous session's files are invalid.
        OSError: A source cannot be read or an output cannot be written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session",
        type=int,
        required=True,
        help="number of the session, starting at 1",
    )
    parser.add_argument(
        "--chain",
        help="short name of the run this session continues (sessions after the first)",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        help="candidate_unit_files.tar.gz of the previous session",
    )
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "dist")
    args = parser.parse_args()
    archive = args.archive.resolve() if args.archive else None
    print(
        json.dumps(
            package_session(
                TASK_ROOT, args.session, args.chain, archive, args.output.resolve()
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
