"""Stage the flat single-step bundle that is uploaded as the task, and print its hash.

Usage: python3 -I scripts/package_task.py DEST_PARENT  (the bundle goes to DEST_PARENT/<task name>)
Copies from the task folder only what the platform runs:
- instruction.md and task.toml;
- environment/: Dockerfile, cargo-config.toml, registry/, docs/;
- tests/: Dockerfile, cargo-config.toml, registry/, test.sh, verify.py and the private cases,
  recorded results and stub rates;
- solution/: solve.sh, oracle.Cargo.lock and the staged upstream/ (scripts/stage_upstream.sh).
Notes, scripts, the README and the generator seed are not shipped. The bundle hash is the first 12
hex digits of the sha256 of the sorted "relative path, file sha256" lines.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
# The platform wants the folder named after the task (task.toml name without the org prefix).
TASK_DIR_NAME = "swe-m2_software-engineering_weave-merge-driver-rebuild"
FILES = [
    "instruction.md",
    "task.toml",
    "environment/Dockerfile",
    "environment/.dockerignore",
    "environment/cargo-config.toml",
    "environment/registry",
    "environment/docs",
    "environment/weave-collect",
    "tests/Dockerfile",
    "tests/.dockerignore",
    "tests/cargo-config.toml",
    "tests/registry",
    "tests/test.sh",
    "tests/verify.py",
    "tests/delivery_manifest.py",
    "tests/upstream-digests.txt",
    "tests/private/cases.json",
    "tests/private/expected.json",
    "tests/private/netting.json",
    "solution/solve.sh",
    "solution/oracle.Cargo.lock",
    "solution/upstream",
]


def bundle_hash(root: Path) -> str:
    """Hash of every file's relative path and content, in sorted order."""
    lines = []
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{p.relative_to(root).as_posix()} {digest}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()[:12]


def main() -> int:
    """Copy the shipped files into DEST (which must not exist) and print the hash."""
    dest = Path(sys.argv[1]) / TASK_DIR_NAME
    if dest.exists():
        raise SystemExit(f"{dest} exists; give a new folder")
    for rel in FILES:
        src = TASK / rel
        if not src.exists():
            raise SystemExit(
                f"missing {rel} (stage solution/upstream and export tests/private first)"
            )
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(
                src, target, ignore=shutil.ignore_patterns("target", ".git")
            )
        else:
            shutil.copy2(src, target)
    n = sum(1 for x in dest.rglob("*") if x.is_file())
    print(f"bundle {bundle_hash(dest)} ({n} files) in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
