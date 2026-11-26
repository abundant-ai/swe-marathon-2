"""Scan agent-facing files for wording that makes the work read like an evaluation.

Author tool (never packaged). Everything the developer receives (the design folder, the
starter project, the QA kit, its command output and the strings of shipped binaries) must
read like a studio brief. This lists every hit of the words below, plus open TODO markers.

Usage:
  python scripts/check_agent_text.py [--release] PATH [PATH ...]

Directories are scanned recursively. --release also fails on TODO(owner) and TODO(panel)
markers, which must all be settled before anything ships.
"""

import argparse
import re
import sys
from pathlib import Path

# Words and phrases that have made solvers call a task "an evaluation" or "a benchmark",
# or that name our process. Matched case-insensitively on word boundaries.
WORDS = [
    "attempt",
    "audit",
    "baseline",
    "benchmark",
    "budget",
    "cannot be told apart",
    "comparison",
    "deadline",
    "evaluate",
    "evaluated",
    "evaluation",
    "evaluator",
    "exactly as the",
    "grade",
    "graded",
    "grader",
    "grading",
    "harbor",
    "harness",
    "hidden",
    "judge",
    "metric",
    "metrics",
    "oddish",
    "oracle",
    "pass rate",
    "private",
    "public",
    "reference",
    "reward",
    "rubric",
    "scenario",
    "scenarios",
    "score",
    "scored",
    "scores",
    "scoring",
    "sealed",
    "seed",
    "seeds",
    "suite",
    "test",
    "tested",
    "testing",
    "tests",
    "timeout",
    "told apart",
    "trial",
    "trials",
    "verifier",
    "verify",
    "verified",
    "verification",
]
PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in WORDS) + r")\b", re.IGNORECASE
)
TODO = re.compile(r"TODO\((owner|panel)\)")
TEXT_SUFFIXES = {
    ".md",
    ".json",
    ".txt",
    ".gd",
    ".tscn",
    ".tres",
    ".godot",
    ".cfg",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".import",
}


def files(paths):
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix in TEXT_SUFFIXES:
                    yield f
        elif p.is_file():
            yield p


def scan(path):
    hits, todos = [], []
    text = path.read_text(errors="replace")
    for n, line in enumerate(text.splitlines(), start=1):
        for m in PATTERN.finditer(line):
            hits.append((n, m.group(0), line.strip()))
        for m in TODO.finditer(line):
            todos.append((n, m.group(0)))
    return hits, todos


def main():
    ap = argparse.ArgumentParser(
        description="Scan agent-facing files for evaluation wording."
    )
    ap.add_argument("--release", action="store_true")
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    n_hits = n_todos = 0
    for f in files(args.paths):
        hits, todos = scan(f)
        for n, word, line in hits:
            print(f"{f}:{n}: '{word}': {line[:140]}")
        for n, marker in todos:
            print(f"{f}:{n}: open {marker}")
        n_hits += len(hits)
        n_todos += len(todos)
    print(f"{n_hits} wording hits, {n_todos} open TODO markers")
    failed = n_hits > 0 or (args.release and n_todos > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
