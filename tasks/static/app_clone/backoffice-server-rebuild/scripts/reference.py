"""The reference application: the Stockwell repository at the commit this task pins.

`common/STOCKWELL_COMMIT` names the commit of github.com/abundant-ai/stockwell (private). The
repository is read from `STOCKWELL_REPO`, or from a checkout next to this repository. The
checkout is extracted once into experiment/reference/<commit>, with:

- `backend/`: the server (FastAPI, SQLAlchemy) and its tools;
- `frontend/`: the web client (React, TypeScript), and `frontend/dist`, built here with npm;
- `requirements.txt`: the server's runtime packages, pinned with hashes from its lock file.
"""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
PIN = TASK_ROOT / "common" / "STOCKWELL_COMMIT"
PARTS = ("backend", "frontend")


def commit() -> str:
    return PIN.read_text().split()[0]


def repository() -> Path:
    """Return STOCKWELL_REPO or the stockwell checkout beside this repository."""
    return Path(os.environ.get("STOCKWELL_REPO", TASK_ROOT.parents[4] / "stockwell"))


def _run(command: list[str], cwd: Path) -> None:
    done = subprocess.run(command, check=False, cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} failed in {cwd}: {done.stderr[-600:]}")


def checkout() -> Path:
    """Extract the pinned commit, build the client and export the requirements, once.

    Raises:
        RuntimeError: The repository, the commit, uv or npm is not available.
    """
    pinned = commit()
    target = TASK_ROOT / "experiment" / "reference" / pinned
    ready = target / ".ready"
    if ready.is_file():
        return target
    done = subprocess.run(
        ["git", "-C", str(repository()), "archive", pinned, *PARTS],
        check=False,
        capture_output=True,
    )
    if done.returncode != 0:
        raise RuntimeError(
            f"Cannot read commit {pinned} from {repository()}: {done.stderr.decode()[-300:]}"
        )
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        try:
            archive.extractall(target, filter="data")
        except TypeError:  # Python before 3.11.4 has no extraction filters
            archive.extractall(target)
    _run(
        [
            "uv",
            "export",
            "--project",
            "backend",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            "requirements.txt",
        ],
        target,
    )
    _run(
        ["npm", "ci", "--no-audit", "--no-fund", "--loglevel=error"],
        target / "frontend",
    )
    _run(["npm", "run", "build"], target / "frontend")
    ready.write_text(pinned + "\n")
    return target


def python(reference: Path) -> list[str]:
    """A Python with the server's packages: STOCKWELL_PYTHON, or uv's environment for the checkout."""
    configured = os.environ.get("STOCKWELL_PYTHON")
    if configured:
        return [configured]
    return [
        "uv",
        "run",
        "--project",
        str(reference / "backend"),
        "--frozen",
        "--no-dev",
        "python",
    ]
