"""Writes the dataset's tests.jsonl and README.md from the merged test list.

tests.jsonl has one line per recorded run:
  record      path of its record file in the dataset
  source      the OpenFOAM tutorial it comes from, or _generated/<group>/<case>
  program, args, cwd
  checks      the checks that count (see the README)
  masked      printed numbers that vary between identical runs and are not compared
  tolerances  allowed difference for numbers in data files that vary between identical runs
  seconds     how long OpenFOAM took (longest of the stability runs)

usage: dataset_card.py <merged tests.json> <records metadata dir> <tutorials.txt> <out dir>
                       [<verifier report of OpenFOAM>...]
  checks OpenFOAM failed in any of the given verifier reports (report.json[.gz], from grading
  the installed OpenFOAM as a submission) are dropped, and runs left without checks
"""
import collections
import gzip
import json
import os
import sys

from publish import tutorial_paths

CARD = """---
license: gpl-3.0
pretty_name: OpenFOAM Rebuild Tests
tags:
  - code
  - software-engineering
  - benchmark
  - testing
  - cfd
  - openfoam
configs:
  - config_name: default
    data_files: tests.jsonl
---

# OpenFOAM Rebuild Tests

Behavioural tests for rebuilding the command-line programs of
[OpenFOAM v2606](https://www.openfoam.com) (commit `{commit}`) from scratch.
Each test is one recorded run of a real OpenFOAM program: the folder it ran in,
the command, and everything the program printed, wrote, changed or removed.
A rebuilt program passes a test when, run with the same command on the same folder,
it produces the same result.

## Overview

| | |
|---|---|
| Recorded program runs | {records} |
| Checks | {checks} |
| Programs | {programs} |
| Sources | {tutorials} OpenFOAM tutorials and {generated} generated cases |

## Structure

```
tests.jsonl                                  one line per recorded run (shown in the viewer)
records/<tutorial path>/<NNN-program>.json   one file per recorded run
records/_generated/<group>/<case>/...        runs from generated cases
files/<h[:2]>/<h>                            file contents, named by their sha256
```

A record file holds:

- `command`: the program, its arguments, and the folder it ran in (`cwd`, relative to the
  case root). `root` and `host` are the recording machine's case path and host name, which
  the comparison replaces.
- `input`: every file in the case before the run, as path -> sha256 of its content in
  `files/`. A path ending in `/` is an empty folder; a value `link:<target>` is a
  symbolic link.
- `output`: every file the program created or changed, in the same form.
- `removed`: files the program deleted.
- `exit`, `stdout`, `stderr`: exit code and printed output.

## Checks

One run gives up to these checks, each counted as a test:

- `exit`: the exit code.
- `files`: no expected file missing, and no other file written, changed or removed.
- `stdout`, `stderr`: the printed output, line by line.
- `file <path>`: one expected output file.

Printed output is compared after removing what changes between identical runs: the
banner, date, time, host, process id, case paths and run times. Words must match exactly.
A number may differ by one unit in its last printed digit, or by the listed tolerance.
OpenFOAM data files are compared by structure, with the same rule for numbers; numbers
stored in binary may differ by a relative 1e-12. Other files must be identical.

## How the tests were made

Every OpenFOAM tutorial, and {generated} small cases written to exercise features no
tutorial uses, were run with every OpenFOAM program wrapped by a recorder. Solvers were
limited to a few time steps. Each recorded run was then replayed:

1. three times with OpenFOAM: anything that varies is masked or given a tolerance, and
   runs whose structure or whole numbers vary are dropped;
2. once with a program that does nothing and exits successfully: checks it passes are
   dropped;
3. once more with OpenFOAM: checks it fails are dropped;
4. twice with OpenFOAM wrapped as a submission and graded by the task's verifier, on a
   separate machine like the one used for grading: checks it fails in either run are
   dropped ({failed} checks: output that depends on timing or the machine, such as which
   parallel process reports an error first, or names listed in directory order).

Runs that compile code while running (`coded` boundary conditions, `#codeStream`) are not
included, nor runs that read files outside their case (the tutorials' shared `resources`
folder), which the grading machine does not have. Identical runs (same program, arguments, folder and input) are kept once.

## License

The case files come from OpenFOAM, which is Copyright (C) OpenCFD Ltd. and licensed
under the GNU General Public License v3; see `ATTRIBUTION.md` and `LICENSE`.
"""

ATTRIBUTION = """# Attribution

The tests in this dataset were recorded by running the programs and tutorials of
OpenFOAM, together with cases derived from those tutorials. The case files and the
recorded outputs are derived from OpenFOAM, and its license terms apply to them.

## Original software

- **Software:** OpenFOAM v2606, by OpenCFD Ltd. ([openfoam.com](https://www.openfoam.com))
- **Repository:** [gitlab.com/openfoam/core/openfoam](https://gitlab.com/openfoam/core/openfoam/-/tree/{commit})
- **Commit:** `{commit}`
- **License:** GPL-3.0
"""


def launched(cmd):
    """The OpenFOAM program a run starts: the program itself, or the one mpirun starts."""
    if cmd["program"] != "mpirun":
        return cmd["program"]
    args, i = cmd["args"], 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-np", "-n", "--np") else 1
    return os.path.basename(args[i]) if i < len(args) else "mpirun"


TUTORIALS = "/opt/openfoam/tutorials/"   # where the recorded runs saw the tutorials
# Case files that name a file in the tutorials folder ($FOAM_TUTORIALS/resources/...) which the
# program reads without printing its path: {tutorial: program that reads it}. Found by searching
# all tutorial files other than scripts for FOAM_TUTORIALS; mangroveInteraction's setFieldsDict,
# the only other one, prints its path.
SILENT_READS = {
    "multiphase/reactingTwoPhaseEulerFoam/RAS/wallBoiling": "reactingTwoPhaseEulerFoam",
    "multiphase/reactingTwoPhaseEulerFoam/RAS/wallBoilingIATE": "reactingTwoPhaseEulerFoam",
}


def outside_case(record_dir, source):
    """Whether a recorded run reads a file from the tutorials folder: named in its arguments, in a
    case file whose path the program prints, or in a case file listed in SILENT_READS."""
    read = lambda n: open(os.path.join(record_dir, n), errors="replace").read()
    if SILENT_READS.get(source) == json.loads(read("cmd.json"))["program"]:
        return True
    return TUTORIALS in read("cmd.json") or TUTORIALS in read("stdout") or TUTORIALS in read("stderr")


def failed_checks(reports):
    """{record path: names of checks OpenFOAM failed} over verifier reports."""
    failed = collections.defaultdict(set)
    for path in reports:
        report = json.load(gzip.open(path) if path.endswith(".gz") else open(path))
        for record, checks in report["tests"].items():
            failed[record] |= {name for name, c in checks.items() if not c["passed"]}
    return failed


def main():
    merged, meta, tutorials_txt, out = sys.argv[1:5]
    failed = failed_checks(sys.argv[5:])
    commit = "481094fdf34f11ed6d0d603ee59a858a0124236d"
    names = tutorial_paths(tutorials_txt)
    tests = [t for t in json.load(open(merged))
             if not outside_case(os.path.join(meta, t["run"], "records", *t["id"].split("/")),
                                 names[t["id"].split("/")[0]])]
    dropped = 0
    for t in tests:
        rec = f"records/{names[t['id'].split('/')[0]]}/{t['id'].split('/')[1]}.json"
        dropped += len(set(t["checks"]) & failed[rec])
        t["checks"] = [c for c in t["checks"] if c not in failed[rec]]
    tests = [t for t in tests if t["checks"]]
    os.makedirs(out, exist_ok=True)
    sources = collections.Counter()
    programs = set()   # under mpirun, the program it starts
    with open(os.path.join(out, "tests.jsonl"), "w") as f:
        for t in tests:
            case, rec = t["id"].split("/")
            d = os.path.join(meta, t["run"], "records", case, rec)
            cmd = json.load(open(os.path.join(d, "cmd.json")))
            st = json.load(open(os.path.join(d, "stability.json")))
            src = names[case]
            sources[src] += 1
            programs.add(launched(cmd))
            f.write(json.dumps({
                "record": f"records/{src}/{rec}.json", "source": src,
                "program": cmd["program"], "args": cmd["args"], "cwd": cmd["cwd"],
                "checks": t["checks"], "masked": st.get("masked", []),
                "tolerances": st.get("tolerances", {}), "seconds": round(max(st["seconds"]), 3),
            }) + "\n")
    n_gen = sum(1 for s in sources if s.startswith("_generated/"))
    counts = dict(commit=commit, records=f"{len(tests):,}",
                  checks=f"{sum(len(t['checks']) for t in tests):,}",
                  programs=len(programs),
                  tutorials=len(sources) - n_gen, generated=n_gen, failed=f"{dropped:,}")
    open(os.path.join(out, "README.md"), "w").write(CARD.format(**counts))
    open(os.path.join(out, "ATTRIBUTION.md"), "w").write(ATTRIBUTION.format(commit=commit))
    print(counts)


if __name__ == "__main__":
    main()
