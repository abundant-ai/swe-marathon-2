"""Record the private scenarios with the pinned reference's own recorder (backend/tools/record_corpus.py).

usage: record_scenarios.py --count 2160 --trading 240 --seed 20261120 [--out FILE]

The legacy request streams are read from the Stockwell repository's history (STOCKWELL_REPO), and
every expected answer is the pinned server's.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reference import TASK_ROOT, checkout, python, repository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--trading", type=int, default=0)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, default=TASK_ROOT / "steps" / "01-rebuild-server" / "tests" / "private" / "scenarios.json")
    args = parser.parse_args()
    reference = checkout()
    tool = reference / "backend" / "tools" / "record_corpus.py"
    env = dict(os.environ, STOCKWELL_GIT=str(repository()))
    command = [*python(reference), "-B", str(tool), "--count", str(args.count), "--trading", str(args.trading), "--seed", str(args.seed),
               "--out", str(args.out.resolve())]
    return subprocess.run(command, cwd=reference / "backend", env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
