#!/usr/bin/env python3
"""Command line entry:  python3 run.py job.mop out.json

Standalone PM7 port (H, C, N, O, F, P, S, Cl, Br).  Needs only numpy (scipy is not required).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pm7.driver import run_job  # noqa: E402
from pm7.system import read_mop  # noqa: E402


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: run.py job.mop out.json\n")
        return 2
    job = read_mop(argv[1])
    res = run_job(job)
    out = {
        "kind": "force" if job.force else ("sp" if job.one_scf else "opt"),
        "elements": [e for e in job.elements],
        "keywords": job.keywords,
    }
    out.update(res)
    with open(argv[2], "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
