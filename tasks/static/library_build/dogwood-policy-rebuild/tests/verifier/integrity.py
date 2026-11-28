"""The clean-room rule: delivered files that are Dogwood's own source, or the 1.2.0 build itself.

The grading image lists the SHA-256 of every Rust and grammar source file of Dogwood 1.2.0's
crates, as written and with all whitespace removed (files of under 400 bytes without whitespace
are left out, so short boilerplate never matches), and the SHA-256 and size of the release build.
A delivered file with one of those digests is a copy of Dogwood's source or of its build, which
the brief rules out; the grader then scores the delivery 0.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from . import listing

DIGESTS = Path("/tests/upstream-sources.txt")
SUFFIXES = (".rs", ".pest")
LARGEST = 4 << 20
SPACE = b" \t\r\n"


def _digests() -> tuple[set[str], set[str], set[tuple[str, int]]]:
    exact: set[str] = set()
    squeezed: set[str] = set()
    builds: set[tuple[str, int]] = set()
    for line in DIGESTS.read_text().splitlines():
        kind, _, rest = line.partition(" ")
        if kind == "binary":
            digest, _, size = rest.strip().partition(" ")
            builds.add((digest, int(size)))
        elif kind == "exact":
            exact.add(rest.strip())
        elif kind == "squeezed":
            squeezed.add(rest.strip())
    return exact, squeezed, builds


def findings(project: Path, limit: int = 20) -> list[str]:
    """The delivered files that are Dogwood's own source or its 1.2.0 build, as paths relative to
    the project (at most `limit` of them)."""
    exact, squeezed, builds = _digests()
    sizes = {size for _, size in builds}
    found: list[str] = []
    for item in listing.walk(os.fsencode(project)):
        if not isinstance(item, listing.Entry) or item.kind != "f":
            continue
        size = item.st.st_size
        if size in sizes:
            digest = listing.sha256_of(item.path)
            if digest is not None and (digest, size) in builds:
                found.append(f"{item.rel} (the 1.2.0 build)")
        elif item.rel.endswith(SUFFIXES) and size <= LARGEST:
            try:
                with open(item.path, "rb") as f:
                    data = f.read(LARGEST + 1)
            except OSError:
                continue
            if (
                hashlib.sha256(data).hexdigest() in exact
                or hashlib.sha256(data.translate(None, SPACE)).hexdigest() in squeezed
            ):
                found.append(item.rel)
        if len(found) >= limit:
            break
    return found
