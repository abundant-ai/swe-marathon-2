"""The private seeds: experiment/seeds.json, made once at random and never committed.

usage: seeds.py NAME   prints the seed called NAME ("scenarios" or "media"), making the file first if needed

A seed decides what the hidden scenarios ask and which private files they upload, so it stays out of the
repository and out of the README: anyone with the generators and a seed could make the same files.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "experiment" / "seeds.json"
NAMES = ("scenarios", "media")


def seed(name: str) -> int:
    seeds = json.loads(FILE.read_text()) if FILE.is_file() else {}
    if any(key not in seeds for key in NAMES):
        seeds = {key: seeds.get(key) or 10**8 + secrets.randbelow(9 * 10**8) for key in NAMES}
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps(seeds, indent=1, sort_keys=True) + "\n")
    return int(seeds[name])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in NAMES:
        raise SystemExit(__doc__)
    print(seed(sys.argv[1]))
