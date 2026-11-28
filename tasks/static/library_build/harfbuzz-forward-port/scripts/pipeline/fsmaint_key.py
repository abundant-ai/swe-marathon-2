"""The key the agent image's sweep signs its mark with, and the verifier reads that mark with.

usage: python -I scripts/pipeline/fsmaint_key.py [--new]

environment/data/fsmaint.key is made once, from 32 random bytes (64 hex digits and a newline), and
tests/private/fsmaint.key (the verifier image's root-only private folder) is kept equal to it. Both
folders are git-ignored. The agent image installs the key root-only (0600) at
/usr/local/lib/fsmaint/key; the verifier image has it at /tests/private/fsmaint.key. With --new, a
fresh key replaces both (rebuild both images then). package_task.py calls stage_key() too.
"""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
ENV_KEY = TASK / "environment" / "data" / "fsmaint.key"
TEST_KEY = TASK / "tests" / "private" / "fsmaint.key"


def write_private(path: Path, data: bytes) -> None:
    """Write `data` to `path` with mode 0600, through a new file renamed into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    made = path.with_name(f".{path.name}.{secrets.token_hex(4)}")
    fd = os.open(made, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.replace(made, path)
    os.chmod(path, 0o600)


def stage_key(new: bool = False) -> bytes:
    """Make the key when there is none (or when `new`), and put the same bytes where the verifier
    image gets them; the key's bytes."""
    if new or not ENV_KEY.exists():
        write_private(ENV_KEY, (secrets.token_hex(32) + "\n").encode())
    key = ENV_KEY.read_bytes()
    text = key.strip()
    if len(text) != 64 or any(c not in b"0123456789abcdef" for c in text):
        raise SystemExit(f"{ENV_KEY} is not a key of 64 hex digits")
    if not TEST_KEY.exists() or TEST_KEY.read_bytes() != key:
        write_private(TEST_KEY, key)
    os.chmod(ENV_KEY, 0o600)
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", action="store_true", help="replace the key")
    args = parser.parse_args()
    stage_key(args.new)
    print(f"{ENV_KEY.relative_to(TASK)} and {TEST_KEY.relative_to(TASK)} hold the key")


if __name__ == "__main__":
    main()
