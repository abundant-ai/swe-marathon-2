"""Describe a recording of the private cases, for metrics.json: the cases kept, by kind; the ones
left out because a run took more than the recorder's margin or did not finish the same way twice;
how long the kept cases' runs took; how many run cases print exactly what upstream publishes as
the expected output of the test they were built from (each such case carries that file's sha256
as "upstream"); and how many cases a program that prints nothing would pass, by exit code.

usage: python3 recording.py <all cases.json> <kept cases.json> <expected.json> <timing.json> <out.json> [--link <file>]

`--link` names the file where build.sh wrote how the recording compiler was linked (static or
dynamic), which the report repeats.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ENCODING = ("utf-8", "surrogateescape")


def describe(cases: list[dict], kept: list[dict], expected: dict, timing: dict) -> dict:
    kind = {case["id"]: case.get("kind", "?") for case in cases}
    seconds = sorted(max(timing["seconds"][case["id"]]) for case in kept)
    upstream = [case for case in kept if case.get("upstream")]
    same = sum(1 for case in upstream
               if hashlib.sha256(expected[case["id"]]["stdout"].encode(*ENCODING)).hexdigest() == case["upstream"])
    empty = Counter(str(expected[case["id"]]["exit"]) for case in kept if expected[case["id"]]["stdout"] == "")
    return {
        "cases_recorded": len(cases), "cases_kept": len(kept),
        "kinds_kept": dict(sorted(Counter(kind[case["id"]] for case in kept).items())),
        "keep_seconds": timing["keep_seconds"],
        "dropped_slow": dict(sorted(Counter(kind[i] for i in timing["slow"]).items())),
        "dropped_unsteady": dict(sorted(Counter(kind[i] for i in timing["unsteady"]).items())),
        "kept_seconds_max": seconds[-1] if seconds else 0.0,
        "kept_seconds_p99": seconds[int(0.99 * (len(seconds) - 1))] if seconds else 0.0,
        "kept_seconds_total": round(sum(seconds), 3),
        "run_cases_with_upstream_output": len(upstream), "run_cases_printing_upstream_output": same,
        "empty_stdout_by_exit": dict(sorted(empty.items())),
    }


def main() -> None:
    args = sys.argv[1:]
    link = None
    if "--link" in args:
        at = args.index("--link")
        link = Path(args[at + 1]).read_text(encoding="utf-8").strip()
        del args[at:at + 2]
    cases, kept = (json.loads(Path(path).read_text(encoding="utf-8"))["cases"] for path in args[0:2])
    expected, timing = (json.loads(Path(path).read_text(encoding="utf-8")) for path in args[2:4])
    report = describe(cases, kept, expected, timing)
    if link is not None:
        report["link"] = link
    Path(args[4]).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
