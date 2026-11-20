"""Reference solution: put back the original SymPy 1.14.0 source of every unit-bearing file."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

SETTLE_SECONDS = 10.0


@dataclass(frozen=True)
class OracleContext:
    """The original source files and the workspace they are copied into."""

    reference: Path
    workspace: Path


def oracle(context: OracleContext) -> None:
    """Produce the working submission in the application workspace.

    Copies each original source file that holds a restorable unit over its
    damaged counterpart; outside the unit bodies the two are the same. It then
    waits a moment, so that every file is completely written before the work
    ends.

    Args:
        context: The reference files and the workspace to write into.

    Raises:
        RuntimeError: The reference files are missing or a target is absent.
    """
    files = sorted(path for path in (context.reference / "sympy").rglob("*.py") if path.is_file())
    if not files:
        raise RuntimeError("Reference source files are missing")
    for source in files:
        target = context.workspace / source.relative_to(context.reference)
        if not target.is_file():
            raise RuntimeError(f"Workspace file is missing: {target}")
        shutil.copyfile(source, target)
    print(f"restored {len(files)} files")
    time.sleep(SETTLE_SECONDS)


if __name__ == "__main__":
    oracle(OracleContext(Path(__file__).resolve().parent / "data", Path("/app")))
