"""Find runs of N or more consecutive words shared by the specification and the upstream tag.

Usage: python3 -I verbatim_scan.py TAG_TARBALL SPEC_DIR [N]
Reads every text member of the tarball (docs, README, source and its comments) as data.
"""

from __future__ import annotations

import re
import sys
import tarfile
from pathlib import Path

WORD = re.compile(r"[A-Za-z0-9_']+")


def words(text: str) -> list[str]:
    """Lower-cased word tokens."""
    return [w.lower() for w in WORD.findall(text)]


def main() -> int:
    """Report every spec run of N words that occurs verbatim upstream."""
    tarball, spec_dir = sys.argv[1], Path(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    upstream: set[tuple[str, ...]] = set()
    with tarfile.open(tarball) as tf:
        for m in tf.getmembers():
            if not m.isfile() or m.size > 2_000_000:
                continue
            if not m.name.endswith((".md", ".rs", ".txt", ".toml", ".html")):
                continue
            fh = tf.extractfile(m)
            if fh is None:
                continue
            w = words(fh.read().decode("utf-8", "replace"))
            upstream.update(tuple(w[i : i + n]) for i in range(len(w) - n + 1))
    hits = 0
    for f in sorted(spec_dir.glob("[01][0-9]-*.md")):
        w = words(f.read_text(encoding="utf-8"))
        i = 0
        while i <= len(w) - n:
            if tuple(w[i : i + n]) in upstream:
                j = i + n
                while j < len(w) and tuple(w[j - n + 1 : j + 1]) in upstream:
                    j += 1
                print(f"{f.name}: {j - i} words: {' '.join(w[i:j])[:200]}")
                hits += 1
                i = j
            else:
                i += 1
    print(f"{hits} shared runs of {n}+ words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
