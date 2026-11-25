"""Write the key the collect step signs its mark with: once, or anew for every uploaded version.

usage: delivery_key.py <task_dir> [--rotate]

The key is a prepared input like the others (environment/data/, kept out of Git). Packaging
stages it into the agent image, where only root can read it, and into the verifier's private
inputs. Without --rotate an existing key is kept; with it the key is replaced, so that a key read
out of one version's image signs nothing for the next.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


def main() -> None:
    target = Path(sys.argv[1]) / "environment" / "data" / "fsmaint.key"
    rotate = "--rotate" in sys.argv[2:]
    if target.exists() and not rotate:
        print(f"kept {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    fresh = target.with_name(target.name + ".new")
    descriptor = os.open(fresh, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(secrets.token_hex(32) + "\n")
    os.replace(fresh, target)
    print(f"{'replaced' if rotate else 'wrote'} {target}")


if __name__ == "__main__":
    main()
