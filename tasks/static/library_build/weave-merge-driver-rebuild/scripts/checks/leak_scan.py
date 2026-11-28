"""Check that no private case leaks into anything the agent can read.

Usage: python3 -I leak_scan.py PRIVATE_DIR FILE_OR_DIR [...]
Reports:
- any run of 3 consecutive non-blank lines of a private input found in a scanned file;
- any single private line of 40 characters or more found verbatim;
- the generator seed, if it appears.
Exits 1 on any hit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def norm_lines(text: str) -> list[str]:
    """Non-blank lines with surrounding whitespace removed."""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def main() -> int:
    """Scan every given file against every private input."""
    private = Path(sys.argv[1])
    cases = json.loads((private / "cases.json").read_text(encoding="utf-8"))
    seed_file = private / "generator-seed.json"
    seed = (
        str(json.loads(seed_file.read_text())["seed"]) if seed_file.exists() else None
    )
    trigrams, long_lines = set(), set()
    for c in cases:
        for key in ("base", "ours", "theirs"):
            lines = norm_lines(c[key])
            trigrams.update("\n".join(lines[i : i + 3]) for i in range(len(lines) - 2))
            long_lines.update(ln for ln in lines if len(ln) >= 40)
    files = []
    for arg in sys.argv[2:]:
        p = Path(arg)
        files += sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
    hits = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = norm_lines(text)
        for i in range(len(lines) - 2):
            if "\n".join(lines[i : i + 3]) in trigrams:
                hits.append(f"{f}: three private lines from line {i + 1}")
        hits += [f"{f}: private line: {ln[:80]}" for ln in lines if ln in long_lines]
        if seed and seed in text:
            hits.append(f"{f}: the generator seed")
    print(
        "\n".join(hits)
        if hits
        else f"no leaks in {len(files)} files ({len(cases)} cases)"
    )
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
