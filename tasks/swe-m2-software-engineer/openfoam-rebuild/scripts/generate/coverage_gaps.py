"""Lists what the test set never reaches, from the coverage job's per-file line counts, as targets
for the next round of generated cases.

A source file in which at most a couple of lines ran is code that was loaded but never used:
usually a model, boundary condition, scheme, function object or writer that OpenFOAM selects
by name from a dictionary (only its registration line runs when the library loads). Those are
grouped by folder, largest first. Generated scanners (*Scanner.cc, *Ragel.cc) are left out:
their line counts are state tables, not behaviour.

usage: coverage_gaps.py <coverage_files.json.gz> [top N]
"""
import collections
import gzip
import json
import re
import sys

UNUSED = 2   # lines run in a file that was loaded but not used (registration)
GENERATED = re.compile(r"(Scanner|Ragel)\.cc$")


def main():
    files = json.load(gzip.open(sys.argv[1]))
    top = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    files = {k: v for k, v in files.items() if v["lines"] and not GENERATED.search(k)}
    lines = sum(v["lines"] for v in files.values())
    covered = sum(v["covered"] for v in files.values())
    unused = {k: v for k, v in files.items() if v["covered"] <= UNUSED}
    print(f"{covered} of {lines} lines ({100 * covered / lines:.1f}%) without generated scanners")
    print(f"{len(unused)} files loaded but unused or never loaded: "
          f"{sum(v['lines'] - v['covered'] for v in unused.values())} uncovered lines")
    groups = collections.defaultdict(list)
    for k, v in unused.items():
        groups["/".join(k.split("/")[:-2])].append((v["lines"], k.rsplit("/", 2)[-2]))
    ranked = sorted(groups.items(), key=lambda g: -sum(n for n, _ in g[1]))
    for folder, members in ranked[:top]:
        names = sorted({m for _, m in members})
        print(f"{sum(n for n, _ in members):6}  {folder}: {', '.join(names[:12])}"
              f"{' ...' if len(names) > 12 else ''}")


if __name__ == "__main__":
    main()
