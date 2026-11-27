"""Drops from a dataset's tests.jsonl the printed output of parallel runs that abort. When one
process calls MPI_ABORT, Open MPI kills the others at no fixed point ("You may or may not see
output from other processes"), so what they print varies between identical runs; the exit code
and files are still checked.

usage: aborted_runs.py <dataset dir>   (needs the record files of the mpirun runs)
"""

import json
import os
import sys

ABORT = "MPI_ABORT was invoked"


def main():
    dataset = sys.argv[1]
    path = os.path.join(dataset, "tests.jsonl")
    dropped, tests = 0, []
    with open(path) as stream:
        for line in stream:
            t = json.loads(line)
            if t["program"] == "mpirun":
                with open(os.path.join(dataset, t["record"])) as f:
                    rec = json.load(f)
                if ABORT in rec["stderr"] or ABORT in rec["stdout"]:
                    kept = [n for n in t["checks"] if n not in ("stdout", "stderr")]
                    dropped += len(t["checks"]) - len(kept)
                    t["checks"] = kept
            if t["checks"]:
                tests.append(t)
    with open(path, "w") as stream:
        stream.writelines(json.dumps(t) + "\n" for t in tests)
    kept = sum(len(t["checks"]) for t in tests)
    print(f"dropped {dropped} checks; {kept} checks in {len(tests)} runs remain")


if __name__ == "__main__":
    main()
