"""Package the task as the flat single-step bundle that is uploaded, and print its content hash.

Usage: python3 -I package.py [--output DIR]

The bundle holds only what Harbor and the two images read: `task.toml`, `instruction.md`,
`environment/` (its Dockerfile, cargo config, registry list, hand-off hooks and the shipped docs), `tests/` (the
grader, its Dockerfile and the private cases and bundles it copies), and `solution/` (`solve.sh`
and upstream's own source, staged by `stage_oracle.py`). Development folders (`checks/`,
`scripts/`, `notes/`, `experiment/`), the README, caches and the private set's seeds and tags stay
out.

Needs, made beforehand and not committed:
- tests/private/cases.jsonl and tests/private/bundles/ (make_cases.py, run_cases.py,
  select_cases.py, retag.py);
- solution/upstream/ (stage_oracle.py).

The content hash is the SHA-256 of the sorted JSON map of every file's own SHA-256; the bundle
goes to OUTPUT/flat/<first 12 hex digits>/<task slug>/, so packaging twice from the same tree
gives the same directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store", ".git"}
PRIVATE_KEEP = ("cases.jsonl", "bundles")
EXECUTABLE = {
    "environment/handoff/reserve",
    "environment/handoff/wait-uplink",
    "environment/handoff/handoff",
}


def wanted(rel: Path) -> bool:
    if SKIP_PARTS.intersection(rel.parts) or rel.suffix == ".pyc":
        return False
    if rel.parts[:2] == ("tests", "private"):
        return len(rel.parts) > 2 and rel.parts[2] in PRIVATE_KEEP
    return True


def collect() -> dict[str, bytes]:
    for need in (
        TASK_ROOT / "tests" / "private" / "cases.jsonl",
        TASK_ROOT / "tests" / "private" / "bundles",
        TASK_ROOT / "solution" / "upstream" / "Cargo.toml",
        TASK_ROOT / "environment" / "docs" / "guide",
    ):
        if not need.exists():
            raise SystemExit(f"missing {need.relative_to(TASK_ROOT)}: make it first")
    content = {
        "task.toml": (TASK_ROOT / "task.toml").read_bytes(),
        "instruction.md": (TASK_ROOT / "instruction.md").read_bytes(),
    }
    for top in ("environment", "tests", "solution"):
        for path in sorted((TASK_ROOT / top).rglob("*")):
            rel = path.relative_to(TASK_ROOT)
            if path.is_symlink():
                raise SystemExit(f"{rel} is a link; the bundle holds files only")
            if path.is_file() and wanted(rel):
                content[rel.as_posix()] = path.read_bytes()
    return dict(sorted(content.items()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=TASK_ROOT / "experiment" / "dist")
    a = ap.parse_args()
    content = collect()
    slug = re.search(
        r'^name = "abundant/([^"]+)"', content["task.toml"].decode(), flags=re.MULTILINE
    ).group(1)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in content.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = a.output.resolve() / "flat" / digest[:12] / slug
    if staging.exists():
        shutil.rmtree(staging)
    for name, data in content.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if name.endswith(".sh") or name in EXECUTABLE:
            target.chmod(0o755)
    print(
        json.dumps(
            {
                "task_path": str(staging),
                "content_sha256": digest,
                "files": len(content),
                "bytes": sum(len(d) for d in content.values()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
