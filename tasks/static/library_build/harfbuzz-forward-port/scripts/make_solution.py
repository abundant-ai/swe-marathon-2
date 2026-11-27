"""Write the reference solution as source files: every file the reference change touches, as it reads after the change.

usage: make_solution.py ORACLE_PATCH ORACLE_TREE

ORACLE_PATCH is the output of scripts/pipeline/make_oracle.sh (a diff from our shipped 14.3.0 tree to 15.2.0's
library); ORACLE_TREE is the shipped tree with that diff applied. The files go to solution/private/tree/ (git-ignored,
staged into the bundle), the paths the change deletes to solution/private/deleted.txt; solution/solve.sh copies the
one and removes the other. Host side; it only copies files of our own trees.

The reference tree must pass the verifier's own check for a copied 15.x release (release_markers in tests/verify.py):
it keeps the tree's version in meson.build, src/hb-version.h and NEWS, and holds none of the unit-test sources only
15.x has. Otherwise nothing is written.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent


def release_markers(tree: Path) -> list[str]:
    """tests/verify.py's check, run on one of our trees (the module only defines things when imported)."""
    spec = importlib.util.spec_from_file_location(
        "hbfp_verify", TASK / "tests" / "verify.py"
    )
    verify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verify)
    return verify.release_markers(tree)


def main() -> None:
    patch, tree = Path(sys.argv[1]), Path(sys.argv[2])
    out = TASK / "solution" / "private"
    target = out / "tree"
    if target.exists():
        raise SystemExit(f"{target} exists; remove it first")
    found = release_markers(tree)
    if found:
        raise SystemExit(
            f"{tree} reads as a copied 15.x release ({'; '.join(found)}); "
            "make it again with scripts/pipeline/make_oracle.sh"
        )
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
