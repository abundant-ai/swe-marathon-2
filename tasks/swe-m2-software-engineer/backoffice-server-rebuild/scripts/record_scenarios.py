"""Record the private scenarios with the pinned reference's own recorder (backend/tools/record_corpus.py).

usage: record_scenarios.py --count 2160 --trading 240 --seed 20261120 [--out FILE] [--media DIR]

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
    parser.add_argument("--media", type=Path, default=TASK_ROOT / "experiment" / "media" / "private",
                        help="the uploads the media scenarios use (scripts/make_media.py); never the set shipped as samples")
    args = parser.parse_args()
    reference = checkout()
    tool = reference / "backend" / "tools" / "record_corpus.py"
    env = dict(os.environ, STOCKWELL_GIT=str(repository()))
    command = [*python(reference), "-B", str(tool), "--count", str(args.count), "--trading", str(args.trading), "--seed", str(args.seed),
               "--out", str(args.out.resolve())]
    if (args.media / "manifest.json").is_file():
        command += ["--media", str(args.media.resolve())]
    else:
        print(f"no media set at {args.media}: recording without the media theme (make it with scripts/make_media.py)", file=sys.stderr)
    return subprocess.run(command, cwd=reference / "backend", env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
