"""Describe a recording of the private cases, for metrics.json.

- The cases kept, by kind; the ones left out, by reason: a run took more than the recorder's
  margin, did not finish the same way twice or perturbed, crashed, printed something that depends
  on the machine, or the recorder's selection dropped them (recorder.select); and how each case
  was settled (recorder.settle).
- How long the kept cases' runs took.
- How far the answers are upstream's: cases built from upstream's records or library whose kept
  form is upstream's code with at most its names changed (settled "base" or "as generated"), by
  kind; and the share of cases ported from APL suites.
- What submissions that implement nothing pass (`baselines`): printing nothing and exiting 0, 1
  or 2; and the strongest dispatcher with no interpreter in it (recorder.no_interpreter: the
  command line's answers, an echo of a program's leading literals, one constant per visible shape
  of case), by strategy. The largest share any one answer holds. The different outputs that only a
  run of the code given produces (runcases.distinct_outputs, which a reward needs
  runcases.DISTINCT_OUTPUTS of, leaving out the cases derivations.py derived) that the kept cases
  hold, and that the dispatcher's cases hold.
- The search for answers one documented function gives from a case's own literals or input
  (`--derived`, derivations.py's output): the cases derived, by kind, the sha256 of their ids, and
  the search's figures.
- A guard: the build stops (exit status 1) when the dispatcher's cases hold more than a third of
  runcases.DISTINCT_OUTPUTS, so that no set of cases brings a program with no interpreter in it
  near a reward unnoticed (`dispatcher_too_close`).
- The recording program (`--build`: its link, size and sha256, with the marker zeroed as the
  reference solution's copy has it), the build host, the recording's wall time, the sha256 of the
  kept ids and of the answers, so that two builds can be compared.

usage: python3 recording.py <all cases.json> <kept cases.json> <expected.json> <report.json> <out.json>
       --derived <derived.json> [--build <build.txt>]
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from recorder import free_cases, free_union
from runcases import DISTINCT_OUTPUTS, distinct_outputs

UPSTREAM_KINDS = (
    "expr",
    "apl",
    "script",
    "error",
    "worker",
    "display",
    "stdin",
    "module",
)


def baselines(kept: list[dict], expected: dict, derived: set[str]) -> dict:
    """The share of the kept cases each trivial submission passes, and the largest share of any
    one answer; and the different outputs that only a run of the code given produces
    (runcases.distinct_outputs, the `derived` cases left out) that passing every kept case reaches,
    and that passing the dispatcher's cases reaches."""
    total = len(kept) or 1
    answers = [
        (expected[case["id"]]["stdout"], expected[case["id"]]["exit"]) for case in kept
    ]
    free = free_cases(kept, expected)
    dispatcher = free_union(free)
    common = Counter(answers).most_common(1)
    return {
        "print_nothing_exit_0": round(answers.count(("", 0)) / total, 4),
        "print_nothing_exit_1": round(answers.count(("", 1)) / total, 4),
        "print_nothing_exit_2": round(answers.count(("", 2)) / total, 4),
        "no_interpreter_dispatcher": round(len(dispatcher) / total, 4),
        "no_interpreter_dispatcher_by_strategy": {
            how: len(ids) for how, ids in sorted(free.items())
        },
        "largest_answer_share": round(common[0][1] / total, 4) if common else 0.0,
        "distinct_outputs_kept": distinct_outputs(
            kept, expected, {case["id"] for case in kept}, derived
        ),
        "no_interpreter_dispatcher_distinct_outputs": distinct_outputs(
            kept, expected, dispatcher, derived
        ),
    }


def describe(
    cases: list[dict], kept: list[dict], expected: dict, report: dict, derivations: dict
) -> dict:
    """The recording's description, from the generated cases, the kept cases, their answers, the
    recorder's report and derivations.py's output."""
    kind = {case["id"]: case.get("kind", "?") for case in cases}
    seconds = sorted(max(report["seconds"][case["id"]]) for case in kept)
    by_kind = lambda ids: dict(sorted(Counter(kind[i] for i in ids).items()))
    settled = report.get("settled", {})
    as_upstream = [
        case["id"]
        for case in kept
        if case.get("kind") in UPSTREAM_KINDS
        and case.get("form") != "built"
        and settled.get(case["id"]) in ("base", "as generated")
    ]
    return {
        "cases_recorded": len(cases),
        "cases_kept": len(kept),
        "kinds_kept": by_kind(case["id"] for case in kept),
        "apl_share": round(
            sum(1 for case in kept if case.get("kind") == "apl") / (len(kept) or 1), 4
        ),
        "keep_seconds": report["keep_seconds"],
        "keep_cpu": report.get("keep_cpu"),
        "dropped_slow": by_kind(report["slow"]),
        "dropped_unsteady": by_kind(report["unsteady"]),
        "dropped_crashed": by_kind(report.get("crashed", [])),
        "dropped_machine": by_kind(report.get("machine", [])),
        "dropped_perturbed": by_kind(report.get("perturbed", [])),
        "dropped_output_limit": by_kind(report.get("output_limit", [])),
        "dropped_memory_limit": by_kind(report.get("memory_limit", [])),
        "dropped_disk_limit": by_kind(report.get("disk_limit", [])),
        "dropped_setting_changes_nothing": by_kind(
            report.get("setting_changes_nothing", [])
        ),
        "main_runs": report.get("main_runs"),
        "main_env": report.get("main_env"),
        "host": report.get("host", {}),
        "wall_seconds": report.get("wall_seconds"),
        "kept_ids_sha256": report.get("kept_ids_sha256"),
        # The answers as the recorder wrote expected.json: two builds that keep the same ids and
        # record other bytes differ here.
        "expected_sha256": hashlib.sha256(
            json.dumps(expected, sort_keys=True).encode()
        ).hexdigest(),
        "dropped": {
            reason: by_kind(ids)
            for reason, ids in sorted(report.get("dropped", {}).items())
        },
        "settled": dict(sorted(Counter(settled.values()).items())),
        "kept_as_upstream_code": by_kind(as_upstream),
        "kept_seconds_max": seconds[-1] if seconds else 0.0,
        "kept_seconds_p99": seconds[int(0.99 * (len(seconds) - 1))] if seconds else 0.0,
        "kept_seconds_total": round(sum(seconds), 3),
        "empty_stdout_by_exit": dict(
            sorted(
                Counter(
                    str(expected[case["id"]]["exit"])
                    for case in kept
                    if expected[case["id"]]["stdout"] == ""
                ).items()
            )
        ),
        "baselines": baselines(kept, expected, set(derivations["derived"])),
        "derived": {
            "cases": by_kind(derivations["derived"]),
            "ids_sha256": hashlib.sha256(
                json.dumps(sorted(derivations["derived"])).encode()
            ).hexdigest(),
            **{
                key: derivations[key]
                for key in ("looked_at", "derivations", "passed_over", "functions")
            },
        },
    }


def dispatcher_too_close(described: dict, least: int = DISTINCT_OUTPUTS) -> str | None:
    """Why the recorded cases leave a program with no interpreter in it too close to a reward, or
    None where they do not.

    Called by main() after describing the recording. The strongest such program the recorder knows
    (recorder.no_interpreter, its error lookup trained on the cases' own answers included) must
    reach no more than a third of the different outputs a reward needs (`least`), so that the
    reward's threshold keeps a margin of three against it whatever cases a new seed or template
    brings.

    Args:
        described: describe()'s result; its baselines hold no_interpreter_dispatcher_distinct_outputs.
        least: The count a reward needs (runcases.DISTINCT_OUTPUTS).

    Returns:
        The reason the build stops, or None.
    """
    reached = described["baselines"]["no_interpreter_dispatcher_distinct_outputs"]
    if 3 * reached <= least:
        return None
    return (
        f"the cases a program with no interpreter in it answers hold {reached} different outputs that only a "
        f"run of the code given produces, more than a third of the {least} a reward needs"
    )


def main() -> None:
    args = sys.argv[1:]
    build = None
    if "--build" in args:
        at = args.index("--build")
        build = dict(
            line.split(" ", 1)
            for line in Path(args[at + 1]).read_text(encoding="utf-8").splitlines()
            if " " in line
        )
        del args[at : at + 2]
    if "--derived" not in args:
        raise SystemExit("recording.py: --derived <derived.json> is required")
    at = args.index("--derived")
    derivations = json.loads(Path(args[at + 1]).read_text(encoding="utf-8"))
    del args[at : at + 2]
    cases, kept = (
        json.loads(Path(path).read_text(encoding="utf-8"))["cases"]
        for path in args[0:2]
    )
    expected, report = (
        json.loads(Path(path).read_text(encoding="utf-8")) for path in args[2:4]
    )
    described = describe(cases, kept, expected, report, derivations)
    if build is not None:
        described["build"] = build
    Path(args[4]).write_text(json.dumps(described, indent=1, sort_keys=True) + "\n")
    print(json.dumps(described, sort_keys=True))
    reason = dispatcher_too_close(described)
    if reason:
        raise SystemExit(f"recording.py: {reason}")


if __name__ == "__main__":
    main()
