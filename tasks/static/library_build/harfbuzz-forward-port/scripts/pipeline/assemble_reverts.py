"""Assemble one patch directory that takes several units' changes out of 15.2.0 at once (development tooling).

usage: assemble_reverts.py OUT_DIR UNIT...

For each unit, its upstream commits' patches (CACHE/work/patches-lib/<unit>) are copied as
<commit time>-<unit>-<sha>.patch, so hb_build.sh and make_mutant.sh revert them newest first across units; a unit
with a hand-resolved revert (scripts/pipeline/reverts/<unit>/R.fwd.patch, written against 15.2.0) contributes that
forward patch instead. OUT_DIR must not exist. Mutant V is the tier-C units (notes/DESIGN.md section 10) in
patches-lib/ALLV; R_unbuilt (the F4 and F5 units) in patches-lib/ALLRu. Directory names starting with ALL make
hb_build.sh skip a commit that no longer reverts cleanly, and list it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent
CACHE = Path.home() / "Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port"
LIB = CACHE / "work" / "patches-lib"
HISTORY = CACHE / "dl" / "git" / "harfbuzz"


def commit_time(sha: str) -> str:
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    cmd = ["git", "-C", str(HISTORY), "show", "-s", "--format=%ct", sha]
    return subprocess.run(
        cmd, capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


def main() -> None:
    out, units = Path(sys.argv[1]), sys.argv[2:]
    out.mkdir()
    for unit in units:
        hand = PIPE / "reverts" / unit / "R.fwd.patch"
        if hand.exists():
            shutil.copy2(hand, out / f"z-{unit}.fwd.patch")
            continue
        patches = sorted((LIB / unit).glob("[0-9][0-9][0-9]-*.patch"))
        if not patches:
            raise SystemExit(f"no patches for unit {unit}")
        for p in patches:
            sha = p.stem.split("-", 1)[1]
            shutil.copy2(p, out / f"{commit_time(sha)}-{unit}-{sha}.patch")
    print(out.name, len(list(out.iterdir())), "patches for", len(units), "units")


if __name__ == "__main__":
    main()
