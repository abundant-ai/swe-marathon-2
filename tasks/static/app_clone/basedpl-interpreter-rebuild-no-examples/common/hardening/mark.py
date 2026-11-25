"""Install the original `bpl` from its compressed build, with a build marker written in.

usage: python3 mark.py <bpl.xz> <build.txt> <marker file, or - for none> <installed path>

The compressed binary is the one build of the hardened original, made
with the all-zero marker `BPL-BUILD-MARKER-000…0`. Before anything is installed, its sha256 must be
the one build.txt records, so every image and the reference solution hold that build and nothing
else. With a marker file (both images' builds; never the solution's), the 32 hex digits it holds
replace the zeros, which occur exactly once; a build that is not this one is rejected.
Writes the installed binary (mode 0755) and, beside it, build.txt with the link mode, the sha256 of
the installed binary and the sha256 of the build without its marker.
"""

from __future__ import annotations

import hashlib
import lzma
import re
import sys
from pathlib import Path

ZERO = b"BPL-BUILD-MARKER-" + b"0" * 32


def facts(path: Path) -> dict[str, str]:
    """build.txt's `key value` lines as a dict."""
    return dict(
        line.split(" ", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if " " in line
    )


def marked(binary: bytes, marker: str) -> bytes:
    """`binary` with its zero marker replaced by `marker` (32 hex digits, not all zeros).

    Raises:
        SystemExit: The marker is malformed or the binary does not hold the zero marker once.
    """
    if not re.fullmatch(r"[0-9a-f]{32}", marker) or marker == "0" * 32:
        raise SystemExit(
            f"mark.py: a marker is 32 hex digits, not all zeros: {marker!r}"
        )
    if binary.count(ZERO) != 1:
        raise SystemExit(
            f"mark.py: the build holds the zero marker {binary.count(ZERO)} times, not once"
        )
    return binary.replace(ZERO, b"BPL-BUILD-MARKER-" + marker.encode())


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    packed, build, marker_file, target = (
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        sys.argv[3],
        Path(sys.argv[4]),
    )
    binary = lzma.decompress(packed.read_bytes())
    recorded = facts(build)
    if hashlib.sha256(binary).hexdigest() != recorded["sha256"]:
        raise SystemExit(
            "mark.py: the compressed binary is not the build that build.txt records"
        )
    installed = (
        binary
        if marker_file == "-"
        else marked(binary, Path(marker_file).read_text().strip())
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(installed)
    target.chmod(0o755)
    (target.parent / "build.txt").write_text(
        f"link {recorded.get('link', 'unknown')}\nsha256 {hashlib.sha256(installed).hexdigest()}\n"
        f"sha256_without_marker {recorded['sha256']}\n"
    )
    print((target.parent / "build.txt").read_text(), end="")


if __name__ == "__main__":
    main()
