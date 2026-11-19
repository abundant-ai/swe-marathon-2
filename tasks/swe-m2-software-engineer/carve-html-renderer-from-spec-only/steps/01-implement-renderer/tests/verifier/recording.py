"""Describe a recording of the private cases, for metrics.json.

- The cases kept, by kind and by area; the ones left out, by reason: a run took more than the
  recorder's margin, did not finish the same way twice or perturbed, crashed, answered otherwise
  than the answer checked against the spec model, or the recorder's selection dropped them
  (recorder.select); and how each case was settled (`settled`).
- How long the kept cases' runs took.
- What programs that implement nothing pass (`baselines`): printing nothing and exiting 0 or 2;
  printing one empty line and exiting 0 (what the original prints for an empty document); a
  dispatcher with the command line's answers and one constant answer per kind of case
  (recorder.free_cases); and a program with the public conformance corpus and no renderer (the
  cases whose answer the corpus lookup would give, dropped at recording). The largest share any
  one answer holds.
- What a stock Djot engine scores on the kept cases (djot.js on the most obvious rewrite of each
  document into Djot, measured when the cases were made): exactly, and with the layout between tags
  forgiven. The share of cases that touch a place where Carve parses differently from Djot.
- The recording program (`--build`: its sha256, the release archive's, its version and the spec
  it implements), the build host, the recording's wall time and the sha256 of the kept ids, so
  that two builds can be compared.

usage: python3 recording.py <all cases.json> <kept cases.json> <expected.json> <report.json> <out.json> [--build <build.txt>]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from recorder import free_cases


def baselines(kept: list[dict], expected: dict) -> dict:
    """The share of the kept cases each trivial program passes, and the largest share of any
    one answer."""
    total = len(kept) or 1
    answers = [(expected[case["id"]]["stdout"], expected[case["id"]]["exit"]) for case in kept]
    dispatcher = {i for ids in free_cases(kept, expected).values() for i in ids}
    common = Counter(answers).most_common(1)
    return {
        "print_nothing_exit_0": round(answers.count(("", 0)) / total, 4),
        "print_nothing_exit_2": round(answers.count(("", 2)) / total, 4),
        "print_empty_line_exit_0": round(answers.count(("\n", 0)) / total, 4),
        "command_line_table_and_constants": round(len(dispatcher) / total, 4),
        "largest_answer_share": round(common[0][1] / total, 4) if common else 0.0,
    }


def corpus_lookup_share(kept: list[dict], report: dict) -> float:
    """The share of the cases a program with the public corpus and no renderer passes: those the
    recorder dropped because the corpus lookup gives their answer, over the cases that were steady
    enough to reach that check (the kept cases plus those dropped ones)."""
    lookup = len(report.get("lookup", []))
    return round(lookup / ((len(kept) + lookup) or 1), 4)


def describe(cases: list[dict], kept: list[dict], expected: dict, report: dict) -> dict:
    """The recording's description, from the generated cases, the kept cases, their answers and
    the recorder's report."""
    kind = {case["id"]: case.get("kind", "?") for case in cases}
    seconds = sorted(max(report["seconds"][case["id"]]) for case in kept)
    by_kind = lambda ids: dict(sorted(Counter(kind[i] for i in ids).items()))
    rendering = [case for case in kept if case.get("kind") != "cli"]
    share = lambda count: round(count / (len(rendering) or 1), 4)
    generated = {case["id"]: case for case in cases}
    return {
        "cases_recorded": len(cases), "cases_kept": len(kept),
        "kinds_kept": by_kind(case["id"] for case in kept),
        "areas_kept": dict(sorted(Counter(case.get("area", "cli") for case in kept).items())),
        "keep_seconds": report["keep_seconds"], "keep_cpu": report.get("keep_cpu"),
        "dropped_slow": by_kind(report["slow"]),
        "dropped_unsteady": by_kind(report["unsteady"]),
        "dropped_crashed": by_kind(report.get("crashed", [])),
        "dropped_differs": by_kind(report.get("differs", [])),
        "dropped_perturbed": by_kind(report.get("perturbed", [])),
        "dropped_corpus_lookup": by_kind(report.get("lookup", [])),
        "dropped_output_limit": by_kind(report.get("output_limit", [])),
        "dropped_memory_limit": by_kind(report.get("memory_limit", [])),
        "dropped_disk_limit": by_kind(report.get("disk_limit", [])),
        "dropped": {reason: by_kind(ids) for reason, ids in sorted(report.get("dropped", {}).items())},
        "settled": dict(sorted(Counter(generated[case["id"]].get("settled", "?") for case in kept).items())),
        "spec_model": dict(sorted(Counter(generated[case["id"]].get("model", "?") for case in kept).items())),
        "options": dict(sorted(Counter(arg for case in kept for arg in case["argv"] if arg.startswith("--")).items())),
        "stdin_cases": sum(1 for case in kept if not case["files"]),
        "host": report.get("host", {}), "wall_seconds": report.get("wall_seconds"),
        "kept_ids_sha256": report.get("kept_ids_sha256"),
        "kept_seconds_max": seconds[-1] if seconds else 0.0,
        "kept_seconds_p99": seconds[int(0.99 * (len(seconds) - 1))] if seconds else 0.0,
        "kept_seconds_total": round(sum(seconds), 3),
        "empty_stdout_by_exit": dict(sorted(Counter(str(expected[case["id"]]["exit"]) for case in kept
                                                    if expected[case["id"]]["stdout"] == "").items())),
        "baselines": dict(baselines(kept, expected), corpus_lookup=corpus_lookup_share(kept, report)),
        "djot_engine": {"exact": share(sum(bool(case.get("djot_exact")) for case in rendering)),
                        "layout_forgiven": share(sum(bool(case.get("djot_normalized")) for case in rendering))},
        "divergence_share": share(sum(1 for case in rendering if set(case.get("features", [])) - {"smart-typography"})),
    }


def main() -> None:
    args = sys.argv[1:]
    build = None
    if "--build" in args:
        at = args.index("--build")
        build = dict(line.split(" ", 1) for line in Path(args[at + 1]).read_text(encoding="utf-8").splitlines() if " " in line)
        del args[at:at + 2]
    cases, kept = (json.loads(Path(path).read_text(encoding="utf-8"))["cases"] for path in args[0:2])
    expected, report = (json.loads(Path(path).read_text(encoding="utf-8")) for path in args[2:4])
    described = describe(cases, kept, expected, report)
    if build is not None:
        described["build"] = build
    Path(args[4]).write_text(json.dumps(described, indent=1, sort_keys=True) + "\n")
    print(json.dumps(described, sort_keys=True))


if __name__ == "__main__":
    main()
