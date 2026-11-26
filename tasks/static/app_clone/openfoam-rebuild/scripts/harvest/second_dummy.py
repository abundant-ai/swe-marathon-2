"""Drops from a dataset's tests.jsonl the checks that a program which prints nothing, changes
nothing and exits with 1 passes (harvest_many.sh now replays that program too). Such a
program leaves the case as it was set up, so which checks it passes follows from the record.

usage: second_dummy.py <dataset dir> <verifier dir>
"""

import json
import os
import sys


def passes(rec, N, C):
    """Checks of the record that the exit-1 program passes."""
    out = set()
    if rec.exit == 1:
        out.add("exit")
    cmd = rec.command
    for stream in ("stdout", "stderr"):
        g = N.normalise(
            getattr(rec, stream),
            case_dir=cmd["root"],
            host=cmd["host"],
            home=cmd.get("home", "/home/dev"),
            install=(N.RECORDED_INSTALL,),
        )
        if C.compare_lines(g, N.normalise("")).ok:
            out.add(stream)
    if not rec.output and not rec.removed:
        out.add("files")
    return out


def main():
    dataset, verifier = sys.argv[1:3]
    sys.path.insert(0, os.path.dirname(os.path.abspath(verifier)))
    from verifier import compare as C
    from verifier import normalise as N
    from verifier import recorded as R

    path = os.path.join(dataset, "tests.jsonl")
    kept, dropped, tests = 0, 0, []
    with open(path) as stream:
        for line in stream:
            t = json.loads(line)
            rec = R.Record.load(
                os.path.join(dataset, t["record"]), os.path.join(dataset, "files")
            )
            gone = passes(rec, N, C)
            t["checks"] = [n for n in t["checks"] if n not in gone]
            dropped += sum(1 for n in json.loads(line)["checks"] if n in gone)
            kept += len(t["checks"])
            if t["checks"]:
                tests.append(t)
    with open(path, "w") as stream:
        stream.writelines(json.dumps(t) + "\n" for t in tests)
    print(f"dropped {dropped} checks; {kept} checks in {len(tests)} runs remain")


if __name__ == "__main__":
    main()
