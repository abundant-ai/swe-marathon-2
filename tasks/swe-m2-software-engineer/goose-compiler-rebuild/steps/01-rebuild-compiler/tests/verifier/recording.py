"""Describe a recording of the private cases, for metrics.json: how many cases were kept, of
which kinds; how many run cases print exactly what upstream publishes as the expected output of
the test they were built from (each such case carries that file's sha256 as "upstream"); and how
many cases a program that prints nothing would pass, by exit code.

usage: python3 recording.py <kept cases.json> <expected.json> <out.json>
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def describe(cases: list[dict], expected: dict) -> dict:
    upstream = [case for case in cases if case.get("upstream")]
    same = sum(1 for case in upstream
               if hashlib.sha256(expected[case["id"]]["stdout"].encode("utf-8")).hexdigest() == case["upstream"])
    empty = Counter(str(expected[case["id"]]["exit"]) for case in cases if expected[case["id"]]["stdout"] == "")
    return {"cases_kept": len(cases), "kinds_kept": dict(sorted(Counter(case.get("kind", "?") for case in cases).items())),
            "run_cases_with_upstream_output": len(upstream), "run_cases_printing_upstream_output": same,
            "empty_stdout_by_exit": dict(sorted(empty.items()))}


def main() -> None:
    cases = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["cases"]
    expected = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    report = describe(cases, expected)
    Path(sys.argv[3]).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
