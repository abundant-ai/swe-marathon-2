"""Keep the aggregation and key-local families informative (python3 -I; reads only our own files).

A generated case lands in B-dedup, B-scope or K by what its policy and trace contain
(make_cases.py). Some of those cases do not depend on the rule after all: a value-domain `count`
whose trace never repeats a value, or `previous` where no other principal's event intervenes.
Such a case still checks core replay, so it moves to R. Whether a case depends on its rule is
read off the matching mutant's run (M-dedup for B-dedup, M-scope for B-scope, M-global for K): the
case depends on the rule when the mutant's answer differs from the release build's. Paired cases
keep their family whatever the mutant does; their pairs are built to exercise the rule.

Usage: retag.py --cases CASES.jsonl --gold RUN.json --mutant FAMILY=RUN.json [...] [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def answer(run: dict) -> tuple:
    first = run["runs"][0]
    return first["rc"], first["norm"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True, type=Path)
    ap.add_argument("--gold", required=True, type=Path)
    ap.add_argument("--mutant", action="append", required=True, help="FAMILY=RUN.json")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    gold = json.loads(a.gold.read_text())
    mutants = {}
    for spec in a.mutant:
        family, path = spec.split("=", 1)
        mutants[family] = json.loads(Path(path).read_text())
    lines = a.cases.read_text().splitlines()
    out, moved = [], {}
    for raw in lines:
        if not raw.strip():
            continue
        c = json.loads(raw)
        fam = c["family"]
        if fam in mutants and not c.get("pair"):
            m = mutants[fam].get(c["id"])
            if m is not None and answer(m) == answer(gold[c["id"]]):
                moved[fam] = moved.get(fam, 0) + 1
                c["family"] = "R"
        out.append(json.dumps(c, sort_keys=True))
    print(json.dumps({"moved_to_R": moved}))
    if a.write:
        a.cases.write_text("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
