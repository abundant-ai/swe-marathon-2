"""The clean-room rule: which delivered files are copies of Dogwood's own source (reported).

The grading image lists the SHA-256 of every Rust and grammar source file of Dogwood 1.2.0's
crates, as written and with all whitespace removed (files of under 400 bytes without whitespace
are left out, so short boilerplate never matches). A delivered file with either digest is a copy
of Dogwood's source.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

DIGESTS = Path("/tests/upstream-sources.txt")
SUFFIXES = (".rs", ".pest")
LARGEST = 4 << 20
SPACE = b" \t\r\n"


def _digests() -> tuple[set[str], set[str]]:
    exact: set[str] = set()
    squeezed: set[str] = set()
    for line in DIGESTS.read_text().splitlines():
        kind, _, digest = line.partition(" ")
        (exact if kind == "exact" else squeezed).add(digest.strip())
    return exact, squeezed


def findings(project: Path, limit: int = 20) -> list[str]:
    """The delivered files that are Dogwood's own source, as paths relative to the project."""
    exact, squeezed = _digests()
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(project, followlinks=False):
        here = Path(dirpath)
        if here == project:
            dirnames[:] = [d for d in dirnames if d != "target"]
        for name in filenames:
            path = here / name
            if path.suffix not in SUFFIXES or path.is_symlink() or not path.is_file():
                continue
            if path.stat().st_size > LARGEST:
                continue
            data = path.read_bytes()
            if (
                hashlib.sha256(data).hexdigest() in exact
                or hashlib.sha256(data.translate(None, SPACE)).hexdigest() in squeezed
            ):
                found.append(str(path.relative_to(project)))
                if len(found) >= limit:
                    return found
    return found
