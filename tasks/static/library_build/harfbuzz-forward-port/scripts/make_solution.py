"""Write the reference solution as source files: every file the reference change touches, as it reads after the change.

usage: make_solution.py ORACLE_PATCH ORACLE_TREE

ORACLE_PATCH is the output of scripts/pipeline/make_oracle.sh (a diff from our shipped 14.3.0 tree to 15.2.0's
library); ORACLE_TREE is the shipped tree with that diff applied. The files go to solution/private/tree/ (git-ignored,
staged into the bundle), the paths the change deletes to solution/private/deleted.txt; solution/solve.sh copies the
one and removes the other. Host side; it only copies files of our own trees.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent


def main() -> None:
    patch, tree = Path(sys.argv[1]), Path(sys.argv[2])
    out = TASK / "solution" / "private"
    target = out / "tree"
    if target.exists():
        raise SystemExit(f"{target} exists; remove it first")
    paths = sorted(
        set(
            re.findall(
                r"^diff -ruN a/(\S+) b/\S+$",
                patch.read_text(errors="replace"),
                re.MULTILINE,
            )
        )
    )
    changed, deleted = 0, []
    for rel in paths:
        src = tree / rel
        if src.is_file():
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target / rel)
            changed += 1
        else:
            deleted.append(rel)
    (out / "deleted.txt").write_text("".join(f"{p}\n" for p in deleted))
    print(f"{changed} files written, {len(deleted)} deleted paths listed")


if __name__ == "__main__":
    main()
