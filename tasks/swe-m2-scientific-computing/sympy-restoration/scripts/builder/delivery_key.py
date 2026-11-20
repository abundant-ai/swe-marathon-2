"""Write the key the collect step signs its mark with, if there is none yet.

usage: delivery_key.py <task_dir>

The key is a prepared input like the others (environment/data/, kept out of Git). Packaging
stages it into the agent image, where only root can read it, and into the verifier's private
inputs.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


def main() -> None:
    target = Path(sys.argv[1]) / "environment" / "data" / "fsmaint.key"
    if target.exists():
        print(f"kept {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(secrets.token_hex(32) + "\n")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
