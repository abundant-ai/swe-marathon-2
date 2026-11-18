"""Describe a recording of the private cases, for metrics.json.

- The cases kept, by kind; the ones left out, by reason: a run took more than the recorder's
  margin, did not finish the same way twice or crashed, or the recorder's selection dropped them
  (runcases.select); and how each case was settled (runcases.settle).
- How long the kept cases' runs took.
- How far the answers are upstream's: run cases printing byte for byte what upstream publishes as
  the expected output of the test they were built from (each carries that file's sha256 as
  "upstream"), and error-test cases whose every diagnostic message is upstream's text verbatim
  (each carries the sha256 of every message its test's comments name, "upstream_messages").
- What submissions that implement nothing pass (`baselines`): printing nothing and exiting 1, or
  exiting 0; a dispatcher with the command line's answers and one constant answer per kind of
  case (runcases.free_cases); and that dispatcher with a perfect formatter.

usage: python3 recording.py <all cases.json> <kept cases.json> <expected.json> <report.json> <out.json> [--link <file>]

`--link` names the file where build.sh wrote how the recording compiler was linked (static or
dynamic), which the report repeats.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from runcases import diagnostics, free_cases, group

ENCODING = ("utf-8", "surrogateescape")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode(*ENCODING)).hexdigest()


def baselines(kept: list[dict], expected: dict, cli: set[str]) -> dict:
    """The share of the kept cases each trivial submission passes."""
    total = len(kept) or 1
    answers = [(expected[case["id"]]["stdout"], expected[case["id"]]["exit"]) for case in kept]
    dispatcher = {i for ids in free_cases(kept, expected, cli).values() for i in ids}
    formatter = dispatcher | {case["id"] for case in kept if group(case).startswith("format")}
    return {
        "print_nothing_exit_1": round(answers.count(("", 1)) / total, 4),
        "print_nothing_exit_0": round(answers.count(("", 0)) / total, 4),
        "command_line_table_and_constants": round(len(dispatcher) / total, 4),
        "formatter_only": round(len(formatter) / total, 4),
    }


def describe(cases: list[dict], kept: list[dict], expected: dict, report: dict) -> dict:
    kind = {case["id"]: case.get("kind", "?") for case in cases}
    seconds = sorted(max(report["seconds"][case["id"]]) for case in kept)
    upstream = [case for case in kept if case.get("upstream")]
    same = sum(1 for case in upstream if sha(expected[case["id"]]["stdout"]) == case["upstream"])
    errors = [case for case in kept if case.get("upstream_messages")]
    verbatim = Counter()
    for case in errors:
        known = set(case["upstream_messages"])
        found = [sha(str(item.get("message", ""))) in known for item in diagnostics(expected[case["id"]]["stdout"])]
        verbatim["all"] += bool(found) and all(found)
        verbatim["some"] += any(found)
    empty = Counter(str(expected[case["id"]]["exit"]) for case in kept if expected[case["id"]]["stdout"] == "")
    by_kind = lambda ids: dict(sorted(Counter(kind[i] for i in ids).items()))  # noqa: E731
    cli = {case["id"] for case in kept if case.get("kind") == "cli"} | set(report.get("cli", []))
    return {
        "cases_recorded": len(cases), "cases_kept": len(kept),
        "kinds_kept": by_kind(case["id"] for case in kept),
        "keep_seconds": report["keep_seconds"],
        "dropped_slow": by_kind(report["slow"]),
        "dropped_unsteady": by_kind(report["unsteady"]),
        "dropped_crashed": by_kind(report.get("crashed", [])),
        "dropped": {reason: by_kind(ids) for reason, ids in sorted(report.get("dropped", {}).items())},
        "settled": dict(sorted(Counter(report.get("settled", {}).values()).items())),
        "kept_seconds_max": seconds[-1] if seconds else 0.0,
        "kept_seconds_p99": seconds[int(0.99 * (len(seconds) - 1))] if seconds else 0.0,
        "kept_seconds_total": round(sum(seconds), 3),
        "run_cases_with_upstream_output": len(upstream), "run_cases_printing_upstream_output": same,
        "error_cases_with_upstream_messages": len(errors),
        "error_cases_all_messages_verbatim": verbatim["all"], "error_cases_some_message_verbatim": verbatim["some"],
        "empty_stdout_by_exit": dict(sorted(empty.items())),
        "baselines": baselines(kept, expected, cli),
    }


def main() -> None:
    args = sys.argv[1:]
    link = None
    if "--link" in args:
        at = args.index("--link")
        link = Path(args[at + 1]).read_text(encoding="utf-8").strip()
        del args[at:at + 2]
    cases, kept = (json.loads(Path(path).read_text(encoding="utf-8"))["cases"] for path in args[0:2])
    expected, report = (json.loads(Path(path).read_text(encoding="utf-8")) for path in args[2:4])
    described = describe(cases, kept, expected, report)
    if link is not None:
        described["link"] = link
    Path(args[4]).write_text(json.dumps(described, indent=1, sort_keys=True) + "\n")
    print(json.dumps(described, sort_keys=True))


if __name__ == "__main__":
    main()
