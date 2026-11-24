"""Combines the records of several harvest runs into one list of tests.

A check is kept when its record is stable, the do-nothing program fails it, and OpenFOAM
passed it in the final check run. A record that repeats an earlier one (same program,
arguments, folder and input files) is dropped.

usage: merge.py <out.json> <run dir>...
  each run dir holds records/<case>/<NNN-program>/ and check.txt
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter

_RECORD = re.compile(r"^\s*\d+/\d+\s+\S+s\s+(?:\S*/)?records/(\S+)$")
_FAIL = re.compile(r"^\s+FAIL (.+?): ")


def gold_failures(check_txt):
    """{record: set of check names OpenFOAM failed in the final check run}"""
    out, rec = {}, None
    for line in open(check_txt, errors="replace"):
        m = _RECORD.match(line.rstrip("\n"))
        if m:
            rec = m.group(1)
            continue
        m = _FAIL.match(line)
        if m and rec:
            out.setdefault(rec, set()).add(m.group(1))
    return out


def checks(rec_dir):
    names = ["exit", "files", "stdout", "stderr"]
    out = json.load(open(os.path.join(rec_dir, "output.json")))
    return names + [f"file {p}" for p, v in out.items()
                    if not p.endswith("/") and not (isinstance(v, str) and v.startswith("link:"))]


def main():
    dest, runs = sys.argv[1], sys.argv[2:]
    tests, seen = [], {}
    drops = Counter()
    for run in runs:
        failed = gold_failures(os.path.join(run, "check.txt"))
        base = os.path.join(run, "records")
        for case in sorted(os.listdir(base)):
            if case == "store" or not os.path.isdir(os.path.join(base, case)):
                continue
            for r in sorted(os.listdir(os.path.join(base, case))):
                d = os.path.join(base, case, r)
                if not os.path.exists(os.path.join(d, "cmd.json")):
                    continue
                if not os.path.exists(os.path.join(d, "exit")):
                    drops["killed at the time limit"] += 1
                    continue
                st_path = os.path.join(d, "stability.json")
                st = json.load(open(st_path)) if os.path.exists(st_path) else {}
                if not st.get("stable"):
                    drops["out of scope" if st.get("out_of_scope") else "unstable"] += 1
                    continue
                cmd = json.load(open(os.path.join(d, "cmd.json")))
                key = hashlib.sha256(json.dumps(
                    [cmd["program"], cmd["args"], cmd["cwd"],
                     json.load(open(os.path.join(d, "input.json")))], sort_keys=True).encode()).hexdigest()
                if key in seen:
                    drops["repeats an earlier record"] += 1
                    continue
                seen[key] = d
                names = [n for n in checks(d) if n not in set(st.get("dummy_passes", ()))]
                bad = failed.get(f"{case}/{r}", set())
                drops["checks OpenFOAM failed in the check run"] += len(bad & set(names))
                names = [n for n in names if n not in bad]
                if not names:
                    drops["no check left"] += 1
                    continue
                tests.append({"id": f"{case}/{r}", "run": os.path.basename(os.path.normpath(run)),
                              "program": cmd["program"], "checks": names})
    json.dump(tests, open(dest, "w"), indent=0)
    progs = Counter(t["program"] for t in tests)
    print(f"{len(tests)} records, {sum(len(t['checks']) for t in tests)} checks, {len(progs)} programs")
    for k, v in drops.most_common():
        print(f"  dropped: {v} {k}")


if __name__ == "__main__":
    main()
