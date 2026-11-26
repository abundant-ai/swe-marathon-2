"""Copy the runtime files into experiment/dist/<bundle>/ for Oddish."""

from __future__ import annotations

import hashlib
import pathlib
import shutil

TASK = pathlib.Path(__file__).resolve().parents[1]
BUNDLE = TASK / "experiment" / "dist" / "swe-m2_ai-research_kev-finetune"
FILES = [
    "task.toml",
    "environment/Dockerfile",
    "environment/.dockerignore",
    "environment/kev-files.txt",
    "environment/resources/domain.md",
    "environment/resources/public-20.jsonl",
    "instruction.md",
    "tests/Dockerfile",
    "tests/.dockerignore",
    "tests/test.sh",
    "tests/verify.py",
    "tests/grader.py",
    "solution/solve.sh",
]
EXECUTABLE = {"tests/test.sh", "solution/solve.sh"}


def main() -> None:
    shutil.rmtree(BUNDLE, ignore_errors=True)
    digest = hashlib.sha256()
    for relative in FILES:
        source, target = TASK / relative, BUNDLE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o755 if relative in EXECUTABLE else 0o644)
        digest.update(relative.encode() + b"\0" + source.read_bytes())
    print(f"{BUNDLE}\nbundle sha256 {digest.hexdigest()}")


if __name__ == "__main__":
    main()
