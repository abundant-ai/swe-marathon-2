"""The private seed: experiment/seeds.json, a 128-bit number made once at random and never committed.

usage: seeds.py cases   prints the case seed, making the file first if needed

The seed decides every private case, rewrite and document (scripts/make_cases.py), so it stays
out of the repository and out of the README: anyone with the generator, the pinned upstream
checkouts and the seed could make the same cases.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "experiment" / "seeds.json"
NAMES = ("cases",)


def value(name: str) -> int:
    """The seed called `name`, from experiment/seeds.json, which is made when missing."""
    seeds = json.loads(FILE.read_text()) if FILE.is_file() else {}
    if any(key not in seeds for key in NAMES):
        seeds = {key: seeds.get(key) or secrets.randbits(128) for key in NAMES}
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps(seeds, indent=1, sort_keys=True) + "\n")
    return int(seeds[name])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in NAMES:
        raise SystemExit(__doc__)
    print(value(sys.argv[1]))
