"""The private seeds: experiment/seeds.json, made once at random and never committed.

usage: seeds.py NAME   prints the value called NAME ("cases" or "marker"), making the file first if needed

"cases" is the seed of scripts/make_cases.py, which decides every private case and rewrite, so it stays out
of the repository and out of the README: anyone with the generator, upstream's checkout and the seed could
make the same cases. "marker" is the build marker written into both images' copies of the original
(common/hardening/mark.py), which the verifier refuses to find in a submission.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "experiment" / "seeds.json"
NAMES = ("cases", "marker")


def make(name: str) -> int | str:
    """A new random value for the seed called `name`: a nine-digit case seed, or 32 hex digits
    that are not all zeros (the zero marker is the reference solution's)."""
    return (
        10**8 + secrets.randbelow(9 * 10**8)
        if name == "cases"
        else "f" + secrets.token_hex(16)[1:]
    )


def value(name: str) -> int | str:
    """The seed called `name`, from experiment/seeds.json, which is made (with every seed) when
    missing."""
    seeds = json.loads(FILE.read_text()) if FILE.is_file() else {}
    if any(key not in seeds for key in NAMES):
        seeds = {key: seeds.get(key) or make(key) for key in NAMES}
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps(seeds, indent=1, sort_keys=True) + "\n")
    return seeds[name]


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in NAMES:
        raise SystemExit(__doc__)
    print(value(sys.argv[1]))
